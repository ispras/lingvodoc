import collections

import minio
import tempfile
from time import time as now
import pickle
import gzip
import sys
import os
import re

import graphene
import logging
import traceback
from datetime import datetime
from sqlalchemy import func, literal, tuple_, and_
from lingvodoc.queue.celery import celery
from lingvodoc.cache.caching import TaskStatus
from pyramid.security import authenticated_userid

from lingvodoc.models import (
    DBSession,
    Client,
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

from lingvodoc.schema.gql_holders import (
    fetch_object,
    client_id_check,
    del_object,
    acl_check_by_id,
    ResponseError,
    LingvodocID,
    ObjectVal
)

from lingvodoc.utils.proxy import try_proxy
from psycopg2.extensions import AsIs

from sqlalchemy import FLOAT
from pdb import set_trace as A

log = logging.getLogger(__name__)
min_date = '1735689600.0'  # 2025-01-01 00:00:00


def key2str(*key):
    return ','.join([str(k) for k in key])


def ListChanges(info, perspective_id, remote, debug_flag=False):

    if remote != 'isp':
        return ResponseError("Exception: only 'isp' host is supported for now")

    print('locking client')
    log.error('locking client')

    request = info.context.request
    try_proxy(request)  # ??
    DBSession.execute("LOCK TABLE client IN EXCLUSIVE MODE;")  # ??
    client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()

    if not client:
        raise ResponseError('try to login again')

    client_id = request.authenticated_userid
    user_id = Client.get_user_by_client_id(client_id).id

    task = TaskStatus(user_id, "Synchronisation with server", '', 5)
    task.set(1, 1, "Started", "")

    is_admin = (user_id == 1)
    id_pool = set()
    result = {'errors': []}

    def get_db_objects(dbModel, table, self_id=None, parent_id=None):

        if (dbModel is None or
                (self_id is None and parent_id is None)):
            return []

        dbFilter = [
            dbModel.client_id == self_id[0],
            dbModel.object_id == self_id[1]
        ] if self_id is not None else [
            dbModel.parent_client_id == parent_id[0],
            dbModel.parent_object_id == parent_id[1]
        ]

        db_objects = (
            DBSession
                .query(dbModel)
                .filter(*dbFilter,
                        func.coalesce(dbModel.additional_metadata['xal_synced_at'].astext, min_date).cast(FLOAT)
                        < func.date_part('EPOCH', dbModel.updated_at))
                        #+ 100)  # for debugging
                .all())

        try:
            for obj in db_objects:
                composite_id = (obj.client_id, obj.object_id)

                if composite_id not in id_pool:
                    id_pool.add(composite_id)
                else:
                    result['errors'].append(f"Objects double: {table=} and {composite_id=}")
                    continue

                columns = vars(obj)
                # '_sa_instance_state' is an object so is not json-serializable, we'll fix this
                columns.pop('_sa_instance_state')
                result[composite_id] = {'table': table, **columns}

        except Exception:
            traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))

            log.warning('xal_synced_at: exception')
            log.warning(traceback_string)

            result['errors'].append('Exception:\n' + traceback_string)
            return []

        return db_objects

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
            A()

    process_db_objects('perspective', {'self_id': perspective_id})

    pickle_path = None

    # Pickling by perspective id
    try:
        storage = request.registry.settings['storage']
        storage_dir = os.path.join(storage['path'], 'xal_sync')
        pickle_path = os.path.join(storage_dir, key2str(*perspective_id))
        os.makedirs(storage_dir, exist_ok=True)

        with gzip.open(pickle_path, 'wb') as f:
            pickle.dump(result, f)

        if debug_flag:
            print(f'{pickle_path=}')

    except Exception as e:
        return ResponseError(f"Cannot write pickle file {pickle_path or ''}: {e}")

    return result


def merge_changes(info, perspective_id, remote, foreign_changes, debug_flag=False):

    message = []
    request = info.context.request
    storage = request.registry.settings['storage']
    storage_dir = os.path.join(storage['path'], f'{remote}_sync')
    pickle_path = os.path.join(storage_dir, key2str(*perspective_id))

    # Getting pickle file from xal by id
    try:
        with gzip.open(pickle_path, 'rb') as f:
            local_changes = pickle.load(f)

        for composite_id, foreign_dict in foreign_changes.items():
            # Service keys
            if composite_id in ['errors']:
                continue

            # Get table name and delete it from the dict
            # for further inserting of dict items into database
            if (table := foreign_dict.pop('table', None)) is None:
                print(f"No foreign table is set for {composite_id=}")
                continue

            adding_flag = False
            updating_flag = False

            if (local_dict := local_changes.get(composite_id)) is None:
                adding_flag = True
            else:
                foreign_metadata = foreign_dict.get('additional_metadata') or {}
                synced_at_key = f'{remote}_synced_at'
                synced_at = foreign_metadata.get(synced_at_key, min_date)

                # if it's syncing we add some delta to now() because after the transaction ends
                # the field 'updated_at' will be automatically set to current time
                # so the changing of 'xal_synced_at' field should be "before" the stored syncing time
                if now() - synced_at > 60:
                    foreign_dict['additional_metadata'] = {**foreign_metadata, synced_at_key: now() + 60}
                else:
                    message.append(
                        f"Not enough time from previous synchronization, wait a minute: {table=}, {composite_id=}")
                    continue

                local_update = local_dict.pop('updated_at')
                foreign_update = foreign_dict.pop('updated_at')

                if foreign_update > max(synced_at, local_update):
                    updating_flag = True
                else:
                    continue

            if adding_flag:
                columns = AsIs(','.join(foreign_dict))
                values = tuple(foreign_dict.values())
                DBSession.execute(
                    f"insert into {table} ({columns}) values {values};")
                # Debug
                print(f"Added {table=}, {composite_id=}")

            elif updating_flag:
                client_id = foreign_dict.pop('client_id')
                object_id = foreign_dict.pop('object_id')
                settings = AsIs(','.join(f'{k} = {v}' for k, v in foreign_dict.items()))
                DBSession.execute(
                    f"update {table} set {settings} where client_id = {client_id} and object_id = {object_id};")
                # Debug
                print(f"Updated {table=}, {composite_id=}")

        DBSession.flush()
        os.remove(pickle_path)

    except Exception as e:
        return ResponseError(f"Cannot read file '{pickle_path}': {e}")
