from time import time as now
from datetime import datetime
import pickle
import gzip
import sys
import os
import logging
import traceback
import requests
from sqlalchemy import func, tuple_
from sqlalchemy.dialects.postgresql import insert
from itertools import zip_longest, starmap
from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.utils import ids_to_id_query

from lingvodoc.models import (
    DBSession,
    Client as dbClient,
    User as dbUser,
    ENGLISH_LOCALE,
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
    Parser as dbParser,
    BaseGroup as dbBaseGroup,
    ObjectTOC as dbObjectTOC,
    Group as dbGroup,
    UserToGroupAssociation as dbUserToGroup
)

from pdb import set_trace as A

log = logging.getLogger(__name__)
min_date = 1735689600.0  # 2025-01-01 00:00:00
none = ''

# Ordered models to create entries from independent ones
# Suffixes are for ordering entries by subjection within groups
db_model_data = {
    # Translations
    'TranslationGist': (dbTranslationGist, None),
    'TranslationAtom': (dbTranslationAtom, None),

    # Language tree
    'Language': (dbLanguage, 'parent_'),
    'Dictionary': (dbDictionary, None),
    'DictionaryPerspective': (dbDictionaryPerspective, None),

    # Fields
    'Field': (dbField, None),
    'DictionaryPerspectiveToField': (dbDictionaryPerspectiveToField, 'self_'),

    # Lexical entries
    'LexicalEntry': (dbLexicalEntry, None),
    'Entity': (dbEntity, 'self_'),
    'PublishingEntity': (dbPublishingEntity, None),

    # Parser results
    'Parser': (dbParser, None),
    'ParserResult': (dbParserResult, None)
}

# Base groups without any relation to subjects
user_base_groups = [*range(1, 5), 9, 18, 30, 31, 32]
# Subjects for groups with relations
tables_for_roles = ['Language', 'Dictionary', 'DictionaryPerspective', 'TranslationGist', 'TranslationAtom']
tables_for_summary = ['Language', 'Dictionary', 'Field', 'Entity']

db_model_roles = {
    'User': (dbUser, ['id']),
    'Client': (dbClient, ['id']),
    'ObjectTOC': (dbObjectTOC, ['client_id', 'object_id']),
    'BaseGroup': (dbBaseGroup, ['id']),
    'Group': (dbGroup, ['id']),
    'UserToGroup': (dbUserToGroup, ['user_id', 'group_id'])
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
        # fields are created or updated with perspective itself
        # no need to collect them for every entity
        # (dbField, 'field_', none),
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


def summary(result):
    return {k: result[k] for k in result if k in tables_for_summary}


def key2str(*key):
    return ','.join([str(k) for k in key])


# For debugging
def report(epoch_times, no_caption=False):
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


def CheckPermissions(info, subject_id, action='edit'):
    # For now everyone with allowed_sync == True and any permission
    # for the perspective on remote host can add this perspective locally

    client_id = info.context.client_id
    user_id = dbClient.get_user_by_client_id(client_id)

    return (
        user_id == 1 or
        action == 'create' or
        info.context.acl_check_if(action, 'perspective', subject_id))


def CheckPerspective(perspective_id):
    db_perspective = (
        DBSession
            .query(
                dbDictionaryPerspective)
            .filter_by(
                client_id=perspective_id[0],
                object_id=perspective_id[1],
                marked_for_deletion=False)
            .first())

    return (
        db_perspective is not None)


def as_dict(obj):
    try:
        return obj._asdict()
    except AttributeError:
        return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}


def as_dicts(obj):
    # If object is cte
    if type(obj) is not list:
        obj = DBSession.query(obj).all()

    return [as_dict(x) for x in obj]


def ListRoles(user_id, subject_ids, debug_flag=False):

    # Getting tree of entries for current user_id or subject_id
    try:
        if user_id is not None:
            filter_by_args = [dbGroup.base_group_id.in_(user_base_groups),
                              dbGroup.id == dbUserToGroup.group_id,
                              dbUserToGroup.user_id == user_id]

        elif subject_ids is not None:

            if len(subject_ids) == 0:
                return None

            filter_by_args = [tuple_(
                                dbGroup.subject_client_id,
                                dbGroup.subject_object_id
                              ).in_(ids_to_id_query(subject_ids))]
        else:
            raise NotImplementedError()

        Group = (
            DBSession
                .query(dbGroup)
                .filter(*filter_by_args)
                .distinct()
                .cte())

        if user_id:
            filter_user_to_group = filter_by_args
        else:
            filter_user_to_group = [dbUserToGroup.group_id == Group.c.id]

        UserToGroup = (
            DBSession
                .query(dbUserToGroup)
                .filter(*filter_user_to_group)
                .distinct()
                .cte())

        BaseGroup = (
            DBSession
                .query(dbBaseGroup)
                .filter(dbBaseGroup.id == Group.c.base_group_id)
                .distinct()
                .all())

        ObjectTOC = (
            DBSession
                .query(dbObjectTOC)
                .filter(dbObjectTOC.client_id == Group.c.subject_client_id,
                        dbObjectTOC.object_id == Group.c.subject_object_id)
                .distinct()
                .all()) if subject_ids else []

        User = (
            DBSession
                .query(dbUser)
                .filter(dbUser.id == UserToGroup.c.user_id)
                .distinct()
                .all()) if subject_ids else []

        Client = (
            DBSession
                .query(dbClient)
                .filter(dbClient.id == Group.c.subject_client_id)
                .distinct()
                .all()) if subject_ids else []

        return {
            'User': as_dicts(User),
            'Client': as_dicts(Client),
            'ObjectTOC': as_dicts(ObjectTOC),
            'BaseGroup': as_dicts(BaseGroup),
            'Group': as_dicts(Group),
            'UserToGroup': as_dicts(UserToGroup)
        }

    # Debugging
    except Exception as e:
        if debug_flag:
            A()
        raise


def MergeRoles(roles_data, debug_flag=False):

    if roles_data is None:
        log.warning("\nNo any update for roles")
        return

    try:
        # Add new entries to database
        for table in db_model_roles:
            model, index = db_model_roles[table]
            for row in roles_data[table]:
                stmt = (
                    insert(model)
                        .values(**row)
                        .on_conflict_do_nothing(index_elements=index))
                DBSession.execute(stmt)
            DBSession.flush()

        log.warning("\nAdded roles!")

    # Debugging
    except Exception as e:
        if debug_flag:
            A()
        raise


def ListChanges(info, perspective_id, remote, sync_between, debug_flag=False):

    request = info.context.request

    # The next variables are added manually but unavailable by graphql
    variables = request.json_body.get('variables', {})
    #user_id = variables.get('user_id')
    sync_point = variables.get('sync_point')
    locale_id = (
        int(request.cookies.get('locale_id') or ENGLISH_LOCALE))
    foreign_side = sync_point is not None

    settings = request.registry.settings
    local = settings['proxy']['local']

    # Get not local suffix from sync_between
    sync_for = sync_between[not sync_between.index(local)]

    local_result = {'warns': []}
    subject_ids = set()
    id_pool = set()
    client_ids = set()
    count = 0
    repeats = 0

    def store_data(side, data):

        pickle_path = 'no_store'

        # Don't store result locally
        # if query went from remote server
        if foreign_side:
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

        client_user_ids = (
            DBSession
                .query(
                    dbClient.id,
                    dbClient.user_id)
                .filter(
                    dbClient.id.in_(client_ids))
                .all())

        user_ids = set(user_id for _, user_id in client_user_ids)

        user_objs = (
            DBSession
                .query(
                    dbUser)
                .filter(
                    dbUser.id.in_(user_ids))
                .all())

        user_dict = {obj.id: as_dict(obj) for obj in user_objs}

        return client_user_ids, user_dict

    def get_db_objects(model, coid, suff):

        nonlocal count
        nonlocal repeats
        table = model.__name__

        if table not in local_result:
            local_result[table] = {}

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
                client_ids.add(obj.client_id)
                obj_coid = key2str(obj.client_id, obj.object_id)
                local_result[table][obj_coid] = as_dict(obj)

                if table in tables_for_roles:
                    subject_ids.add((obj.client_id, obj.object_id))

                if debug_flag:
                    report({
                        ('Sync point', 20): local_result['sync_point'],
                        ('Updated at', 20): obj.updated_at,
                        ('Composite id', 20): f"{obj_coid},{table}",
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
            log.warning(str(e))

    # Get client_id from security data
    if not (client_id := request.authenticated_userid):
        raise ResponseError('no client_id is in request')

    '''
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
    '''

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
            # no any need
            # 'user_id': user_id,
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
                log.warning(f'Foreign stored: {pickle_path} <- {remote}')

            return summary(remote_result)
        else:
            raise ResponseError(f'{resp_status=} from {remote=}')

    ##### End of cross-server query #####

    if debug_flag:
        log.warning('\nPreparing sync...')

    # For remote query get 'sync_point' from request json
    # for local query get it from database
    local_result['sync_point'] = sync_point or get_sync_point()

    ##### Running main recursion from here #####
    process_db_objects(dbDictionaryPerspective, perspective_id, none)

    if local == 'isp' and foreign_side:
        local_result['clients'] = client_list()

    if foreign_side:
        # Update result with roles for subjects
        local_result['roles'] = ListRoles(None, subject_ids, debug_flag)

    # Pickling by perspective id
    pickle_path = store_data(local, local_result)

    if debug_flag:
        log.warning(f'\nSkipped repeats: {repeats}')
        log.warning(f'Local stored: {local} -> {pickle_path}')

    return local_result if foreign_side else summary(local_result)


def MergeChanges(info, perspective_id, sync_between, action='edit', debug_flag=False):

    if not CheckPermissions(info, perspective_id, action):
        return {
            'triumph': False,
            'message': "You have no permissions to do sync"
        }

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

        # Doesn't work
        # db_perspective.updated_at = synced_at

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
            client_user_ids, user_dict = foreign_changes['clients']

            for client_id, user_id in client_user_ids:

                if not DBSession.query(dbUser).filter_by(id=user_id).first():
                    user = dbUser(**user_dict[str(user_id)])
                    DBSession.add(user)

                if not DBSession.query(dbClient).filter_by(id=client_id).first():
                    client = dbClient(id=client_id, user_id=user_id)
                    DBSession.add(client)

            DBSession.flush()

        # Iterate by local changes to get maximal updating point
        # this time will be new sync_point (not real time)
        for table in db_model_data:
            for local_dict in local_changes.get(table, {}).values():
                local_update = local_dict.get('updated_at')
                next_synced_at = max(next_synced_at, local_update)

        if debug_flag:
            log.warning('\nApplying sync...')

        count = 0

        for table in db_model_data:
            table_data = foreign_changes.get(table, {})
            model, suff = db_model_data[table]

            # Sorting within groups by recursion field to make None values before any other
            if suff is not None:
                table_data = dict(sorted(table_data.items(), key=lambda item: bool(item[1][suff + 'client_id'])))

            for obj_coid, foreign_dict in table_data.items():
                local_dict = local_changes.get(table, {}).get(obj_coid, {})
                local_update = local_dict.get('updated_at', min_date)
                foreign_update = foreign_dict.get('updated_at')
                foreign_content = foreign_dict.get('content', '')

                client_id, object_id = obj_coid.split(',')

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
                    report({
                        ('Sync time', 20): current_synced_at,
                        ('Foreign update', 20): foreign_update,
                        ('Local update', 20): local_update,
                        ('Action', 8): action,
                        ('Composite id', 20): f"{obj_coid},{table}",
                        ('Foreign content', 20): foreign_content
                    }, no_caption=bool(count))

                count += 1

            DBSession.flush()

        if next_synced_at > current_synced_at:
            set_synced_at(next_synced_at)
            DBSession.flush()

        # Add roles for current perspective
        MergeRoles(foreign_changes['roles'], debug_flag)

        os.remove(local_pickle_path)
        os.remove(foreign_pickle_path)

        if debug_flag:
            log.warning('\nComplete!')

        return {'triumph': True, 'message': ""}

    except Exception:
        message = "Something went wrong with merging of changes"
        traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))
        log.warning(message)
        log.warning(traceback_string)

        return {
            'triumph': False,
            'message': message
        }
