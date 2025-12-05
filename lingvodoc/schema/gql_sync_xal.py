import collections

import minio
import tempfile
from time import time as now
import os
import re

import graphene
import logging

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
    Parser as dbParser,
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

from sqlalchemy.orm import aliased
from pdb import set_trace as A

log = logging.getLogger(__name__)


def ListChanges(info, id, host, debug_flag=False):

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

    def add_to_result(dbObject, key):
        if dbObject is None:
            return None

        updated_at = dbObject.updated_at
        metadata = dbObject.additional_metadata or {}
        synced_at = metadata.get('xal_synced_at', 0)

        if updated_at > synced_at:
            changes[key].append([synced_at, updated_at, dbObject])
            dbObject.additional_metadata = {**metadata, 'xal_synced_at': updated_at}
            return True
        else:
            return False

    def get_db_objects(dbModel, key, self_id=None, parent_id=None):

        if (dbModel is None or
                (self_id is None and parent_id is None)):
            return []

        dbFilter = [
            dbModel.marked_for_deletion == False
        ] if key != 'publishing' else []

        if self_id is not None:
            cid, oid = self_id
            dbFilter.extend([
                dbModel.client_id == cid,
                dbModel.object_id == oid
            ])
        else:
            cid, oid = parent_id
            dbFilter.extend([
                dbModel.parent_client_id == cid,
                dbModel.parent_object_id == oid
            ])

        db_objects = (
            DBSession
                .query(dbModel)
                .filter(*dbFilter)
                .all()
        ) or []

        for obj in db_objects:
            add_to_result(obj, key)

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
    #A()
    return changes
