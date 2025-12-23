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

from sqlalchemy import FLOAT
from pdb import set_trace as A

log = logging.getLogger(__name__)
min_date = '1735689600.0'  # 2025-01-01 00:00:00


def key2str(*key):
    return ','.join([str(k) for k in key])


def ListChanges(info, id, host, debug_flag=False):

    if host != 'isp':
        return ResponseError("Exception: only 'isp' host is supported for now")

    print('locking client')
    log.error('locking client')

    request = info.context.request
    try_proxy(request)
    DBSession.execute("LOCK TABLE client IN EXCLUSIVE MODE;")
    variables = {'auth': authenticated_userid(request)}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    if not client:
        raise ResponseError('try to login again')

    client_id = request.authenticated_userid
    user_id = Client.get_user_by_client_id(client_id).id

    is_admin = (user_id == 1)

    task = TaskStatus(user_id, "Synchronisation with server", '', 5)
    task.set(1, 1, "Started", "")

    changes = collections.defaultdict(list)
    changes_for_sync = {}
    error = None

    def get_db_objects(dbModel, key, self_id=None, parent_id=None):
        nonlocal error

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
                        < func.date_part('EPOCH', dbModel.updated_at)
                        + 100)  # for debugging
                .all())

        try:
            for obj in db_objects:
                # '_sa_instance_state' is an object so is not json-serializable, we'll fix this
                changes[key].append({**obj.__dict__, '_sa_instance_state': None})
                metadata = obj.additional_metadata or {}
                '''
                if hasattr(obj, 'content'):
                    changes[key].append({
                        'content': obj.content,
                        'metadata': metadata,
                        'marked_for_deletion': obj.marked_for_deletion,
                        'updated_at': obj.updated_at
                    })
                '''
                changes_for_sync[(obj.client_id, obj.object_id)] = obj

                # if it's syncing we add some delta to now() because after the transaction ends
                # the field 'updated_at' will be automatically set to current time
                # so the changing of 'xal_synced_at' field should be "before" the stored syncing time
                '''
                if now() - metadata.get('xal_synced_at', 0) > 60:
                    obj.additional_metadata = {**metadata, 'xal_synced_at': now() + 60}
                else:
                    return (
                        ResponseError("Not enough time from previous synchronization, wait a minute"))
                '''
        except Exception:
            traceback_string = ''.join(traceback.format_exception(*sys.exc_info()))

            log.warning('xal_synced_at: exception')
            log.warning(traceback_string)

            error = ResponseError('Exception:\n' + traceback_string)

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

    def process_db_objects(key, ids):
        dbModel, parents, children = tree[key]
        objects = get_db_objects(dbModel, key, **ids)

        for obj in objects:
            for p_key in parents:
                p_ids = (
                    {'self_id': (obj.self_client_id, obj.self_object_id)}
                    if key == p_key == 'perstofield' or key == p_key == 'entity' else

                    {'self_id': (obj.entity_client_id, obj.entity_object_id)}
                    if p_key == 'entity' else

                    {'self_id': (obj.field_client_id, obj.field_object_id)}
                    if p_key == 'field' else

                    {'self_id': (obj.translation_gist_client_id, obj.translation_gist_object_id)}
                    if p_key == 'gist' else

                    {'self_id': (obj.client_id, obj.object_id)}
                    if p_key == 'publishing' else

                    {'self_id': (obj.parent_client_id, obj.parent_object_id)}
                )
                if any(x is None for x in p_ids['self_id']):
                    continue

                process_db_objects(p_key, p_ids)

            for c_key in children:
                c_ids = {'parent_id': (obj.client_id, obj.object_id)}
                process_db_objects(c_key, c_ids)

    process_db_objects('perspective', {'self_id': id})

    pickle_path = None

    # Pickling by perspective id
    try:
        storage = request.registry.settings['storage']
        storage_dir = os.path.join(storage['path'], 'xal_sync')
        pickle_path = os.path.join(storage_dir, key2str(*id))
        os.makedirs(storage_dir, exist_ok=True)

        with gzip.open(pickle_path, 'wb') as f:
            pickle.dump(changes_for_sync, f)

        if debug_flag:
            print(f'{pickle_path=}')

    except Exception as e:
        return ResponseError(f"Cannot write pickle file {pickle_path or ''}: {e}")

    return error or changes


def ApplySync(id, debug_flag=False):

    pickle_path = None
    # Getting pickle file from xal by id
    pass

    changes_for_sync = None

    try:
        with gzip.open(pickle_path, 'rb') as f:
            changes_for_sync = pickle.load(f)

        os.remove(pickle_path)

    except Exception as e:
        return ResponseError(f"Cannot read file '{pickle_path}': {e}")
