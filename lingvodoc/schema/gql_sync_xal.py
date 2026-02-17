from time import time as now
from datetime import datetime
from itertools import zip_longest as zipp
import numbers
import pickle
import gzip
import sys
import os
import logging
import traceback
from sqlalchemy import func

from lingvodoc.models import (
    DBSession,
    Client,
    User,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Field as dbFields,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    Dictionary as dbDictionary,
    Language as dbLanguage,
    DictionaryPerspectiveToField as dbDictionaryPerspectiveToField,
    DictionaryPerspective as dbDictionaryPerspective,
    PublishingEntity as dbPublishingEntity,
    ParserResult as dbParserResult
)

import requests
from lingvodoc.schema.gql_holders import ResponseError

'''
from lingvodoc.cache.caching import TaskStatus
from lingvodoc.queue.celery import celery
from pyramid.security import authenticated_userid
from lingvodoc.utils.proxy import try_proxy
from psycopg2.extensions import AsIs
from sqlalchemy import FLOAT
import json
'''

from pdb import set_trace as A

log = logging.getLogger(__name__)
min_date = 1735689600.0  # 2025-01-01 00:00:00
hidden = none = []

# Tuples: (dbModel, parents, children)
tree = {
    'parserresult': (dbParserResult, ['entity'], none),
    'publishing': (dbPublishingEntity, hidden, none),
    'entity': (dbEntity, ['entity', 'field', 'publishing'], none),  # cycle
    'lexical': (dbLexicalEntry, hidden, ['entity']),
    'field': (dbFields, ['gist'], none),
    'perstofield': (dbDictionaryPerspectiveToField, ['perstofield', 'field'], none),  # cycle
    'perspective': (dbDictionaryPerspective, ['dictionary', 'gist'], ['perstofield', 'lexical']),
    'dictionary': (dbDictionary, ['language', 'gist'], hidden),
    'language': (dbLanguage, ['language', 'gist'], hidden),  # cycle
    'atom': (dbTranslationAtom, hidden, none),
    'gist': (dbTranslationGist, hidden, ['atom'])
}


def key2str(*key):
    return ','.join([str(k) for k in key])


# For debugging
def whats_time(**epoch_times):
    print('\n' + ' || '.join(map(lambda k: f"{k:<30}", epoch_times.keys())))
    for v1, v2 in zipp(list(epoch_times.values()), list(epoch_times.values())[1:]):
        value = datetime.fromtimestamp(v1) if isinstance(v1, numbers.Number) else v1
        sign = (
            '\n' if v2 is None else
            ' || ' if not isinstance(v2, numbers.Number) else
            ' == ' if v1 == v2 else ' << ' if v1 < v2 else ' >> ')
        print(f"{str(value):<30}", end=sign)


def ListChanges(info, perspective_id, remote, sync_for, debug_flag=False):

    request = info.context.request
    settings = request.registry.settings
    local = settings['desktop']['local']
    desktop = settings['desktop']['desktop']
    local_result = {'warns': []}
    id_pool = set()

    def store_data(side, data):
        pickle_path = 'no_store'

        # Don't store result locally
        # if query went from remote server
        if request.json_body.get('target_synced_at'):
            return pickle_path

        try:
            storage = settings['storage']
            storage_dir = os.path.join(storage['path'], f'{side}_sync')
            pickle_path = os.path.join(storage_dir, key2str(*perspective_id))
            os.makedirs(storage_dir, exist_ok=True)

            with gzip.open(pickle_path, 'wb') as f:
                pickle.dump(data, f)

        except Exception as e:
            return ResponseError(f"Cannot write pickle file {pickle_path or ''}: {e}")

        return pickle_path

    def target_synced_at():
        perspective_metadata = (
            DBSession
                .query(
                    dbDictionaryPerspective.additional_metadata)
                .filter_by(
                    client_id = perspective_id[0],
                    object_id = perspective_id[1])
                .one()
        )[0] or {}

        return perspective_metadata.get(f'{sync_for}_synced_at', min_date)

    def get_db_objects(dbModel, table, self_id=None, parent_id=None):

        try:
            if (dbModel is None or
                    (self_id is None and parent_id is None)):
                return []

            if self_id is not None:
                composite_id = key2str(self_id[0], self_id[1])

                # Checking before request to database
                if composite_id in id_pool:
                    local_result['warns'].append(
                        f"Objects double: {table=} and {composite_id=}")
                    return []

                dbFilter = [
                    dbModel.client_id == self_id[0],
                    dbModel.object_id == self_id[1]]
            else:
                dbFilter = [
                    dbModel.parent_client_id == parent_id[0],
                    dbModel.parent_object_id == parent_id[1]]

            relatives_cte = (
                DBSession
                    .query(dbModel)
                    .filter(*dbFilter)
                    .cte())

            # Getting related objects which are updated
            # after 'target_synced_at' date
            changed_objects = (
                DBSession
                    .query(relatives_cte)
                    .filter(local_result['target_synced_at']
                            < func.date_part('EPOCH', relatives_cte.c.updated_at))
                    .all())

            # Getting all related objects to get next relations
            relatives = (
                DBSession
                    .query(relatives_cte)
                    .all())

            for obj in changed_objects:
                composite_id = key2str(obj.client_id, obj.object_id)

                if composite_id not in id_pool:
                    id_pool.add(composite_id)
                else:
                    local_result['warns'].append(
                        f"Objects double: {table=} and {composite_id=}")
                    continue

                columns = obj._asdict()
                # '_sa_instance_state' is an object so is not json-serializable, we'll fix this
                columns.pop('_sa_instance_state', None)
                local_result[composite_id] = {'table': table, **columns}

        except Exception:
            traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))

            log.warning('get_db_objects: exception')
            log.warning(traceback_string)

            local_result['warns'].append('Exception:\n' + traceback_string)
            return []

        return relatives

    def process_db_objects(table, ids):
        try:
            dbModel, parents, children = tree[table]
            objects = get_db_objects(dbModel, table, **ids)

            for obj in objects:
                for p_table in parents:
                    p_ids = (
                        {'self_id': (obj.self_client_id, obj.self_object_id)}
                        if table == p_table == 'perstofield' or table == p_table == 'entity' else

                        {'self_id': (obj.entity_client_id, obj.entity_object_id)}
                        if p_table == 'entity' else

                        {'self_id': (obj.field_client_id, obj.field_object_id)}
                        if p_table == 'field' else

                        {'self_id': (obj.translation_gist_client_id, obj.translation_gist_object_id)}
                        if p_table == 'gist' else

                        {'self_id': (obj.client_id, obj.object_id)}
                        if p_table == 'publishing' else

                        {'self_id': (obj.parent_client_id, obj.parent_object_id)}
                    )
                    if any(x is None for x in p_ids['self_id']):
                        continue

                    process_db_objects(p_table, p_ids)

                for c_table in children:
                    c_ids = {'parent_id': (obj.client_id, obj.object_id)}
                    process_db_objects(c_table, c_ids)

        except Exception as e:
            print(str(e))

    # Get client_id from security data or from json_body (set manually)
    if not (client_id := request.authenticated_userid):
        raise ResponseError('no client_id is in request')

    ### Create client if it absents on remote server ###

    if not (client := DBSession.query(Client).filter_by(id=client_id).first()):
        if local == 'isp':
            raise ResponseError('try to login again')
        else:
            if not (user_id := request.json_body.get('user_id')):
                raise ResponseError('no user id is in request')
            if not (user := DBSession.query(User).filter_by(id=user_id).first()):
                raise ResponseError('no such user is in db')

            # Add new client
            client_args = {
                'id': client_id,
                'user_id': user_id,
                'is_browser_client': not desktop
            }

            client = Client(**client_args)
            user.clients.append(client)
            DBSession.add(client)
            DBSession.flush()
    else:
        if not (user_id := Client.get_user_by_client_id(client_id).id):
            raise ResponseError(f'no any user for this {client_id=}')

    ##### Cross-server query #####

    if local != remote:
        # Changing req_path and req_data to query from remote server
        if remote_server := settings['desktop'].get(f'{remote}_server'):
            client_path = remote_server + 'api' + request.path
        else:
            raise NotImplementedError

        # Get and set session
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
        session = requests.Session()
        session.headers.update({'Connection': 'Keep-Alive'})
        session.mount('http://', adapter)

        req_args = {
            'json': {
                **request.json_body,
                'user_id': user_id,
                'target_synced_at': target_synced_at()
            },
            'cookies': request.cookies
        }

        # Query
        remote_resp = session.post(client_path, **req_args)
        resp_status = remote_resp.status_code
        remote_result = (remote_resp.json()
                         .get('data', {})
                         .get('list_changes', {}))

        if resp_status == 200:
            pickle_path = store_data(remote, remote_result)

            if debug_flag:
                print(f'\nFOREIGN ({pickle_path} <- {remote}): {now()=} {str(remote_result)[-500:]=}')

            return remote_result
        else:
            raise ResponseError(f'{resp_status=} from {remote=}')

    ##### End of cross-server query #####

    '''
    task = TaskStatus(user_id, "Synchronisation with server", '', 5)
    task.set(1, 1, "Started", "")
    '''

    # For remote query get 'target_synced_at' from request json
    # for local query get it from database
    local_result['target_synced_at'] = (
            request.json_body.get('target_synced_at') or target_synced_at())
    process_db_objects('perspective', {'self_id': perspective_id})

    # Pickling by perspective id
    pickle_path = store_data(local, local_result)

    if debug_flag:
        print(f'\nLOCAL ({local} -> {pickle_path}): {now()=} {str(local_result)[-500:]=}')

    return local_result


def MergeChanges(info, perspective_id, sync_between, debug_flag=False):

    message = []
    request = info.context.request
    settings = request.registry.settings
    local = settings['desktop']['local']
    sync_between.remove(local)
    remote = sync_between[0]
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

        db_perspective.updated_at = synced_at

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
        return ResponseError(f"Cannot read file '{local_pickle_path}': {e}")

    try:
        with gzip.open(foreign_pickle_path, 'rb') as f:
            foreign_changes = pickle.load(f)

    except Exception as e:
        return ResponseError(f"Cannot read file '{foreign_pickle_path}': {e}")

    try:
        current_synced_at = local_changes['target_synced_at']
        next_synced_at = current_synced_at

        '''
        delta = 60
        time_to_sync = (now() - target_synced_at > delta)
        if not time_to_sync:
            message.append(
                "Not enough time from previous synchronization, wait a minute")
            return {
                'triumph': False,
                'message': message
            }
        '''

        for composite_id, foreign_dict in foreign_changes.items():
            # Service keys e.g. 'warns'
            if composite_id in ['warns', 'target_synced_at']:
                continue

            # Get table name and delete it from the dict
            # for further inserting of dict items into database
            if (table := foreign_dict.pop('table', None)) is None:
                print(f"No foreign table is set for {composite_id=}")
                continue

            local_dict = local_changes.get(composite_id, {})
            local_update = local_dict.get('updated_at', min_date)
            local_content = local_dict.get('content', '')
            foreign_update = foreign_dict.get('updated_at')
            foreign_content = foreign_dict.get('content', '')

            model, _, _ = tree[table]
            client_id, object_id = composite_id.split(',')

            db_object = (
                DBSession
                    .query(model)
                    .filter_by(
                        client_id=client_id,
                        object_id=object_id)
                    .first())


            if debug_flag and foreign_dict['client_id'] == 12435:
                whats_time(**{
                    'Sync time': current_synced_at,
                    'Foreign update': foreign_update,
                    'Local update': local_update,
                    'Table': table,
                    'Foreign content': foreign_content})

            if db_object is None:
                # Add new object
                db_object = model(**foreign_dict)
                DBSession.add(db_object)

                if debug_flag:
                    print(f"Added {table=}, {composite_id=}, {foreign_content=}")

            elif foreign_update > local_update:
                # Delete client_id and object_id
                # from dict to avoid collision
                foreign_dict.pop('client_id', None)
                foreign_dict.pop('object_id', None)

                for k, v in foreign_dict.items():
                    setattr(db_object, k, v)

                if debug_flag:
                    print(f"Updated {table=}, {composite_id=}, {foreign_content=}")

            next_synced_at = max(next_synced_at, local_update, foreign_update)

        set_synced_at(next_synced_at)
        DBSession.flush()
        os.remove(local_pickle_path)
        os.remove(foreign_pickle_path)

        if debug_flag:
            print("=" * 20 + "\n")

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
