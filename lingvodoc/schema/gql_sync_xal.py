from time import time as now
import pickle
import gzip
import sys
import os
import logging
import traceback
from sqlalchemy import func #, literal, tuple_, and_
from lingvodoc.cache.caching import TaskStatus
from lingvodoc.queue.celery import celery
from pyramid.security import authenticated_userid

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

from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.utils.proxy import try_proxy
from psycopg2.extensions import AsIs

from sqlalchemy import FLOAT
from pdb import set_trace as A

import requests
import json

log = logging.getLogger(__name__)
min_date = '1735689600.0'  # 2025-01-01 00:00:00

result = {'errors': []}
id_pool = set()
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


def get_db_objects(dbModel, table, self_id=None, parent_id=None, remote='xal'):

    if (dbModel is None or
            (self_id is None and parent_id is None)):
        return []

    if self_id is not None:
        composite_id = key2str(self_id[0], self_id[1])

        # Checking before request to database
        if composite_id in id_pool:
            result['errors'].append(f"Objects double: {table=} and {composite_id=}")
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

    changed_objects = (
        DBSession
            .query(relatives_cte)
            .filter(func.coalesce(relatives_cte.c.additional_metadata[f'{remote}_synced_at'].astext, min_date)
                    .cast(FLOAT) < func.date_part('EPOCH', relatives_cte.c.updated_at))
            .all())

    relatives = (
        DBSession
            .query(relatives_cte)
            .all())

    try:
        for obj in changed_objects:
            composite_id = key2str(obj.client_id, obj.object_id)

            if composite_id not in id_pool:
                id_pool.add(composite_id)
            else:
                result['errors'].append(f"Objects double: {table=} and {composite_id=}")
                continue

            columns = obj._asdict()
            # '_sa_instance_state' is an object so is not json-serializable, we'll fix this
            columns.pop('_sa_instance_state', None)
            result[composite_id] = {'table': table, **columns}

    except Exception:
        traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))

        log.warning(f'{remote}_synced_at: exception')
        log.warning(traceback_string)

        result['errors'].append('Exception:\n' + traceback_string)
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


def ListChanges(info, perspective_id, remote, debug_flag=False):

    request = info.context.request
    settings = request.registry.settings
    local = settings['desktop']['local']
    desktop = settings['desktop']['desktop']

    def store_data(side, data):
        pickle_path = 'no_store'

        if request.json_body.get('no_local_store'):
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
                'no_local_store': True
            },
            'cookies': request.cookies
        }

        # Query
        client_resp = session.post(client_path, **req_args)
        client_json = client_resp.json()
        resp_status = client_resp.status_code

        if resp_status == 200:
            pickle_path = store_data(remote, client_json)

            if debug_flag:
                print(f'\nFOREIGN ({pickle_path} <- {remote}): {now()=} {str(client_json)[-500:]=}')

            return client_json
        else:
            raise ResponseError(f'{resp_status=} from {remote=}')

    ##### End of cross-server query #####

    '''
    task = TaskStatus(user_id, "Synchronisation with server", '', 5)
    task.set(1, 1, "Started", "")
    '''

    process_db_objects('perspective', {'self_id': perspective_id})

    # Pickling by perspective id
    pickle_path = store_data(local, result)

    if debug_flag:
        print(f'\nLOCAL ({local} -> {pickle_path}): {now()=} {str(result)[-500:]=}')

    return result


def MergeChanges(info, perspective_id, remote, debug_flag=False):

    message = []
    request = info.context.request
    settings = request.registry.settings
    local = settings['desktop']['local']
    storage_path = settings['storage']['path']

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
            local_changes = pickle.load(f).get('data', {}).get('list_changes', {})

    except Exception as e:
        return ResponseError(f"Cannot read file '{local_pickle_path}': {e}")

    try:
        with gzip.open(foreign_pickle_path, 'rb') as f:
            foreign_changes = pickle.load(f).get('data', {}).get('list_changes', {})

    except Exception as e:
        return ResponseError(f"Cannot read file '{foreign_pickle_path}': {e}")

    try:
        for composite_id, foreign_dict in foreign_changes.items():
            # Service keys e.g. 'errors'
            if composite_id in ['errors']:
                continue

            # Get table name and delete it from the dict
            # for further inserting of dict items into database
            if (table := foreign_dict.pop('table', None)) is None:
                print(f"No foreign table is set for {composite_id=}")
                continue

            client_id, object_id = composite_id.split(',')
            model, _, _ = tree[table]

            object_to_change = (
                DBSession
                    .query(model)
                    .filter_by(
                        client_id=client_id,
                        object_id=object_id)
                    .first()
            )

            adding_flag = False
            updating_flag = False

            if object_to_change is None:
                adding_flag = True
            else:
                foreign_metadata = foreign_dict.get('additional_metadata') or {}
                synced_at_key = f'{remote}_synced_at'
                synced_at = foreign_metadata.get(synced_at_key, min_date)

                # if it's syncing we add some delta to now() because after the transaction ends
                # the field 'updated_at' will be automatically set to current time
                # so the changing of 'xal_synced_at' field should be "before" the stored syncing time
                delta = 60
                time_to_sync = now() - float(synced_at) > delta
                shifted_time = now() + delta

                if not time_to_sync:
                    message.append(
                        f"Not enough time from previous synchronization, wait a minute: {table=}, {composite_id=}")
                    continue

                local_update = float(
                    local_changes
                        .get(composite_id, {})
                        .get('updated_at', min_date))

                foreign_update = float(foreign_dict.pop('updated_at'))

                # Preparing foreign_dict for db updating
                if foreign_update > local_update:
                    updating_flag = True
                    foreign_dict.pop('client_id')
                    foreign_dict.pop('object_id')
                    foreign_dict['additional_metadata'] = {
                        **foreign_metadata,
                        synced_at_key: shifted_time
                    }

            if adding_flag:
                columns = AsIs(','.join(foreign_dict))
                values = tuple(foreign_dict.values())
                DBSession.execute(
                    f"insert into {table} ({columns}) values {values};")
                # Debug
                print(f"Added {table=}, {composite_id=}")

            elif updating_flag:
                A()

                '''
                settings = AsIs(','.join(f'{k} = {v}' for k, v in foreign_dict.items()))
                DBSession.execute(
                    f"update {table} set {settings} where client_id = {client_id} and object_id = {object_id};")
                '''
                # Debug
                print(f"Updated {table=}, {composite_id=}")

        DBSession.flush()
        #os.remove(local_pickle_path)
        #os.remove(foreign_pickle_path)

        return {'triumph': True, 'message': message}

    except Exception as e:
        message.append('Something wrong with changes merging')
        print(f'{message[-1]}: {e}')
        return {
            'triumph': False,
            'message': message
        }
