import collections
from time import time as now
from datetime import datetime
import pickle
import gzip
import sys
import os
import re
import logging
import traceback
import requests
from sqlalchemy import func
from itertools import zip_longest, starmap
from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.models import (
    DBSession,
    Client as dbClient,
    User as dbUser,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Field as dbField,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    Dictionary as dbDictionary,
    Language as dbLanguage,
    DictionaryPerspectiveToField as dbDictionaryPerspectiveToField,
    DictionaryPerspective as dbDictionaryPerspective,
    PublishingEntity as dbPublishingEntity,
    ParserResult as dbParserResult,
    Parser as dbParser
)

from lingvodoc.cache.caching import TaskStatus
from lingvodoc.queue.celery import celery

from pdb import set_trace as A

log = logging.getLogger(__name__)
min_date = 1735689600.0  # 2025-01-01 00:00:00
none = ''

# Ordered (!) models to create entries from the beginning
db_model = {
    # Translations
    'TranslationGist': dbTranslationGist,
    'TranslationAtom': dbTranslationAtom,

    # Language tree
    'Language': dbLanguage,
    'Dictionary': dbDictionary,
    'DictionaryPerspective': dbDictionaryPerspective,

    # Fields
    'Field': dbField,
    'DictionaryPerspectiveToField': dbDictionaryPerspectiveToField,

    # Lexical entries
    'LexicalEntry': dbLexicalEntry,
    'Entity': dbEntity,
    'PublishingEntity': dbPublishingEntity,

    # Parser results
    'Parser': dbParser,
    'ParserResult': dbParserResult
}

# Tuple means relative: (his_dbModel, my_suffix, his_suffix)
db_tree = {
    dbParser: [],

    dbParserResult: [
        (dbParser, 'parser_', none)
    ],

    dbPublishingEntity: [],

    dbField: [
        (dbTranslationGist, 'translation_gist_', none),
        (dbTranslationGist, 'data_type_translation_gist_', none)
    ],

    dbEntity: [
        (dbPublishingEntity, none, none),
        (dbField, 'field_', none),
        (dbEntity, 'self_', none),
        (dbLexicalEntry, 'link_', none),
        (dbParserResult, none, 'entity_')
    ],

    dbLexicalEntry: [
        (dbEntity, none, 'parent_')
    ],

    dbDictionaryPerspectiveToField: [
        (dbDictionaryPerspective, 'link_', none),
        (dbDictionaryPerspectiveToField, 'self_', none),
        (dbField, 'field_', none)
    ],

    # Entry point
    dbDictionaryPerspective: [
        (dbDictionary, 'parent_', none),
        (dbTranslationGist, 'translation_gist_', none),
        (dbTranslationGist, 'state_translation_gist_', none),
        (dbDictionaryPerspectiveToField, none, 'parent_'),
        (dbLexicalEntry, none, 'parent_')
    ],

    dbDictionary: [
        (dbLanguage, 'parent_', none),
        (dbTranslationGist, 'translation_gist_', none),
        (dbTranslationGist, 'state_translation_gist_', none)
    ],

    dbLanguage: [
        (dbLanguage, 'parent_', none),
        (dbTranslationGist, 'translation_gist_', none)
    ],

    dbTranslationGist: [
        (dbTranslationAtom, none, 'parent_')
    ],

    dbTranslationAtom: []
}


def key2str(*key):
    return ','.join([str(k) for k in key])


# For debugging
def whats_time(epoch_times, no_caption=False):
    headers = list(epoch_times.keys())
    values = list(epoch_times.values())
    next_values = list(epoch_times.values())[1:]

    def cell(value, width):
        return f"{str(value)[:width]:<{width}}"

    def is_stamp(value):
        return isinstance(value, float)

    if not no_caption:
        caption = ' || '.join(starmap(cell, headers))
        print(f"\n{caption}", flush=True)

    for (_, w), v1, v2 in zip_longest(headers, values, next_values):
        v = datetime.fromtimestamp(v1) if is_stamp(v1) else v1
        sign = (
            '\n' if v2 is None else
            ' || ' if not is_stamp(v2) else
            ' == ' if v1 == v2 else ' << ' if v1 < v2 else ' >> ')
        print(cell(v, w), end=sign)


def CheckPermissions(info, perspective_id, debug_flag=False):
    result = info.context.acl_check_if('edit', 'perspective', perspective_id)
    return result


def ListChanges(info, perspective_id, remote, sync_between, debug_flag=False):

    request = info.context.request

    # The next variables are added manually but unavailable by graphql
    variables = request.json_body.get('variables', {})
    user_id = variables.get('user_id')
    sync_point = variables.get('sync_point')

    settings = request.registry.settings
    local = settings['proxy']['local']

    # Get not local suffix from sync_between
    sync_for = sync_between[not sync_between.index(local)]

    local_result = {'warns': []}
    id_pool = set()
    clients = set()
    count = 0
    repeats = 0

    def store_data(side, data):
        pickle_path = 'no_store'

        # Don't store result locally
        # if query went from remote server
        if sync_point is not None:
            return pickle_path

        try:
            storage = settings['storage']
            storage_dir = os.path.join(storage['path'], f'{side}_sync')
            pickle_path = os.path.join(storage_dir, key2str(*perspective_id))
            os.makedirs(storage_dir, exist_ok=True)

            with gzip.open(pickle_path, 'wb') as f:
                pickle.dump({'stamp': now(), **data}, f)

        except Exception as e:
            raise ResponseError(f"Cannot write pickle file {pickle_path or ''}: {e}")

        return pickle_path

    def get_sync_point():
        perspective_metadata = ((
            DBSession
                .query(
                    dbDictionaryPerspective.additional_metadata)
                .filter_by(
                    client_id = perspective_id[0],
                    object_id = perspective_id[1])
                .first()
        ) or (None,))[0] or {}

        return perspective_metadata.get(f'{sync_for}_synced_at', min_date)

    def client_list():

        result = (
            DBSession
                .query(
                    dbClient.id,
                    dbClient.user_id)
                .filter(
                    dbClient.id.in_(clients))
                .distinct().all())

        return result

    def get_db_objects(model, coid, suff):

        nonlocal count
        nonlocal repeats
        table = model.__name__

        # Controlling already processed elements
        pool_item = key2str(*coid, table, suff)
        if pool_item in id_pool:
            repeats += 1
            return []
        id_pool.add(pool_item)

        try:
            dbFilter = [
                getattr(model, f'{suff}client_id') == coid[0],
                getattr(model, f'{suff}object_id') == coid[1]
            ]

            relatives_cte = (
                DBSession
                    .query(model)
                    .filter(*dbFilter)
                    .cte())

            # Getting related objects which are updated
            # after 'sync_point' date
            changed_objects = (
                DBSession
                    .query(relatives_cte)
                    .filter(local_result['sync_point']
                            < func.date_part('EPOCH', relatives_cte.c.updated_at))
                    .all())

            # Getting all related objects to get next relations
            relatives = (
                DBSession
                    .query(relatives_cte)
                    .all())

            for obj in changed_objects:
                clients.add(obj.client_id)

                # '_sa_instance_state' is an object so is not json-serializable, we'll fix this
                columns = obj._asdict()
                columns.pop('_sa_instance_state', None)

                composite_id = key2str(obj.client_id, obj.object_id, table)
                local_result[composite_id] = columns

                if debug_flag:
                    whats_time({
                        ('Sync point', 20): local_result['sync_point'],
                        ('Updated at', 20): obj.updated_at,
                        ('Composite id', 20): composite_id,
                        ('Deleted', 12):
                            obj.marked_for_deletion if hasattr(obj, 'marked_for_deletion') else 'n/a',
                        ('Content', 20): getattr(obj, 'content', 'n/a')
                    }, no_caption=bool(count))

                count += 1

        except Exception:
            traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))

            log.warning('get_db_objects: exception')
            log.warning(traceback_string)

            local_result['warns'].append('Exception:\n' + traceback_string)
            return []

        return relatives

    def process_db_objects(*args):

        model, _, _ = args

        try:
            objects = get_db_objects(*args)
            relatives = db_tree[model]

            def get_id(obj, suff):
                return [
                    getattr(obj, f"{suff}client_id"),
                    getattr(obj, f"{suff}object_id")]

            for obj in objects:
                for model, our_suff, his_suff in relatives:
                    process_db_objects(model, get_id(obj, our_suff), his_suff)

        except Exception as e:
            print(str(e))

    # Get client_id from security data
    if not (client_id := request.authenticated_userid):
        raise ResponseError('no client_id is in request')

    ### Create client if it absents on remote server ###

    if not (client := DBSession.query(dbClient).filter_by(id=client_id).first()):
        if local == 'isp':
            raise ResponseError('try to login again')
        else:
            if user_id is None:
                raise ResponseError('no user id is in request')
            if not (user := DBSession.query(dbUser).filter_by(id=user_id).first()):
                raise ResponseError('no such user is in db')

            # Add new client
            client_args = {
                'id': client_id,
                'user_id': user_id,
                'is_browser_client': True
            }

            client = dbClient(**client_args)
            user.clients.append(client)
            DBSession.add(client)
            DBSession.flush()
    else:
        if not (user_id := dbClient.get_user_by_client_id(client_id).id):
            raise ResponseError(f'no any user for this {client_id=}')

    ##### Cross-server query #####

    if local != remote:
        # Changing req_path and req_data to query from remote server
        if remote_server := settings['proxy'].get(f'{remote}_server'):
            client_path = remote_server + 'api' + request.path
        else:
            raise NotImplementedError

        # Get and set session
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
        session = requests.Session()
        session.headers.update({'Connection': 'Keep-Alive'})
        session.mount('http://', adapter)

        variables = {
            **request.json_body.get('variables', {}),
            'user_id': user_id,
            'sync_point': get_sync_point()
        }

        req_args = {
            'json': {
                **request.json_body,
                'variables': variables
            },
            'cookies': request.cookies
        }

        # Query
        remote_resp = session.post(client_path, **req_args)
        resp_status = remote_resp.status_code
        remote_result = ((remote_resp.json()
                         .get('data') or {})
                         .get('list_changes'))

        if resp_status == 200:
            pickle_path = store_data(remote, remote_result)

            if debug_flag:
                print(f'Foreign stored: {pickle_path} <- {remote}')

            return remote_result
        else:
            raise ResponseError(f'{resp_status=} from {remote=}')

    ##### End of cross-server query #####

    '''
    task = TaskStatus(user_id, "Synchronisation with server", '', 5)
    task.set(1, 1, "Started", "")
    '''

    if debug_flag:
        print('\nPreparing sync...')

    # For remote query get 'sync_point' from request json
    # for local query get it from database
    local_result['sync_point'] = sync_point or get_sync_point()
    process_db_objects(dbDictionaryPerspective, perspective_id, none)

    if local == 'isp' and sync_point is not None:
        local_result['clients'] = client_list()

    # Pickling by perspective id
    pickle_path = store_data(local, local_result)

    if debug_flag:
        print(f'\nSkipped repeats: {repeats}')
        print(f'Local stored: {local} -> {pickle_path}')

    return local_result


def MergeChanges(info, perspective_id, sync_between, debug_flag=False):

    if not CheckPermissions(perspective_id, debug_flag):
        raise ResponseError("You have no permissions to do sync")

    message = []
    request = info.context.request
    settings = request.registry.settings
    local = settings['proxy']['local']
    remote = sync_between[not sync_between.index(local)]
    storage_path = settings['storage']['path']

    def set_synced_at(synced_at):
        db_perspective = (
            DBSession
                .query(
                    dbDictionaryPerspective)
                .filter_by(
                    client_id = perspective_id[0],
                    object_id = perspective_id[1])
                .one()
        )

        perspective_metadata = db_perspective.additional_metadata or {}
        db_perspective.additional_metadata = {
            **perspective_metadata,
            f'{remote}_synced_at': synced_at}

        #db_perspective.updated_at = synced_at

    def is_comp_id(comp_id):
        return bool(re.match(r'^\d+,\d+,\w+$', comp_id))

    local_pickle_path = os.path.join(
        storage_path,
        f'{local}_sync',
        key2str(*perspective_id)
    )
    foreign_pickle_path = os.path.join(
        storage_path,
        f'{remote}_sync',
        key2str(*perspective_id)
    )

    # We should order changes according to foreign_keys between tables
    # So an entry can't be added into 'dictionaryperspective' table
    # before its parent is not added into 'dictionary' table and so on
    # Tables are placed correctly in db_model dictionary in advance

    def ordered(changes):
        try:
            changes_by_table = collections.defaultdict(dict)
            for composite_key, value in changes.items():
                if is_comp_id(composite_key):
                    _, _, table = composite_key.split(',')
                    changes_by_table[table][composite_key] = value

            result = {}
            for table in db_model:
                result.update(changes_by_table[table])

            return result

        # Debugging
        except Exception as e:
            raise

    # Reading pickle files
    try:
        with gzip.open(local_pickle_path, 'rb') as f:
            local_changes = pickle.load(f)

    except Exception as e:
        raise ResponseError(f"Cannot read file '{local_pickle_path}': {e}")

    try:
        with gzip.open(foreign_pickle_path, 'rb') as f:
            foreign_changes = pickle.load(f)

    except Exception as e:
        raise ResponseError(f"Cannot read file '{foreign_pickle_path}': {e}")

    try:
        current_synced_at = local_changes['sync_point']
        next_synced_at = current_synced_at

        # Adding users and clients met in perspective into remote database
        if local != 'isp':
            client_list = foreign_changes['clients']
            for client_id, user_id in client_list:

                if not (user := DBSession.query(dbUser).filter_by(id=user_id).first()):
                    user = dbUser(id=user_id)
                    DBSession.add(user)

                if not DBSession.query(dbClient).filter_by(id=client_id).first():
                    client = dbClient(id=client_id, user_id=user_id)
                    DBSession.add(client)
                    user.clients.append(client)

            DBSession.flush()

        # Iterate by local changes to get maximal updating point
        # this time will be new sync_point (not real time)
        for composite_id, local_dict in local_changes.items():
            # Service keys e.g. 'warns'
            if not is_comp_id(composite_id):
                continue

            local_update = local_dict.get('updated_at')
            next_synced_at = max(next_synced_at, local_update)

        if debug_flag:
            print('\nApplying sync...')

        count = 0

        for composite_id, foreign_dict in ordered(foreign_changes).items():
            # Service keys e.g. 'warns'
            if not is_comp_id(composite_id):
                continue

            local_dict = local_changes.get(composite_id, {})
            local_update = local_dict.get('updated_at', min_date)
            local_content = local_dict.get('content', '')
            foreign_update = foreign_dict.get('updated_at')
            foreign_content = foreign_dict.get('content', '')

            client_id, object_id, table = composite_id.split(',')
            model = db_model[table]

            db_object = (
                DBSession
                    .query(model)
                    .filter_by(
                        client_id=client_id,
                        object_id=object_id)
                    .first())

            action = 'n/a'

            if db_object is None:
                # Add new object
                db_object = model(**foreign_dict)
                DBSession.add(db_object)

                action = 'added'

            elif foreign_update > local_update:
                # Delete client_id and object_id
                # from dict to avoid collision
                foreign_dict.pop('client_id', None)
                foreign_dict.pop('object_id', None)

                for k, v in foreign_dict.items():
                    setattr(db_object, k, v)

                action = 'updated'

            next_synced_at = max(next_synced_at, foreign_update)

            if debug_flag:
                whats_time({
                    ('Sync time', 20): current_synced_at,
                    ('Foreign update', 20): foreign_update,
                    ('Local update', 20): local_update,
                    ('Action', 8): action,
                    ('Composite id', 20): composite_id,
                    ('Foreign content', 20): foreign_content
                }, no_caption=bool(count))

            count += 1

        if next_synced_at > current_synced_at:
            set_synced_at(next_synced_at)
            DBSession.flush()

        os.remove(local_pickle_path)
        os.remove(foreign_pickle_path)

        if debug_flag:
            print('\nComplete!')

        return {'triumph': True, 'message': message}

    except Exception:
        message.append('Something wrong with changes merging')
        traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))
        log.warning(message[-1])
        log.warning(traceback_string)

        return {
            'triumph': False,
            'message': message
        }
