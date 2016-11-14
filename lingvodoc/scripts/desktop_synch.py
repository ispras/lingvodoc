# -*- coding: utf-8 -*-
import sqlite3
import base64
import requests
import json
import hashlib
import logging

import os
import base64
import hashlib
import shutil
import transaction
import tempfile
from pydub import AudioSegment
from collections import defaultdict
from pathvalidate import sanitize_filename
from urllib import request

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import create_engine
from sqlalchemy import and_
from lingvodoc.models import (
    Client,
    DBSession,
    UserBlobs,
    TranslationAtom,
    TranslationGist,
    Field,
    Entity,
    LexicalEntry,
    Dictionary,
    Language,
    User,
    DictionaryPerspectiveToField,
    DictionaryPerspective,
    BaseGroup,
    Group,
    PublishingEntity

)

from lingvodoc.scripts import elan_parser

EAF_TIERS = {
    "literary translation": "Translation of Paradigmatic forms",
    "text": "Transcription of Paradigmatic forms",

    "word": "Word",
    "transcription": "Transcription",
    "translation": "Translation"
}


def make_request(path, req_type='get', json_data=None):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    with open('authentication_data.json', 'r') as f:
        cookies = json.loads(f.read())
    session.mount('http://', adapter)
    if req_type == 'get':
        status = session.get(path, cookies=cookies)
    elif req_type == 'post':
        status = session.post(path, json=json_data, cookies=cookies)
    else:
        return None
    return status


def translationatom_contents(translationatom):
    result = dict()
    result['content'] = translationatom.content
    result['locale_id'] = translationatom.locale_id
    result['client_id'] = translationatom.client_id
    result['object_id'] = translationatom.object_id
    result['parent_client_id'] = translationatom.parent_client_id
    result['parent_object_id'] = translationatom.parent_object_id
    result['created_at'] = str(translationatom.created_at)
    return result


def translationgist_contents(translationgist):
    result = dict()
    result['client_id'] = translationgist.client_id
    result['object_id'] = translationgist.object_id
    result['type'] = translationgist.type
    result['created_at'] = str(translationgist.created_at)
    contains = []
    for translationatom in translationgist.translationatom:
        contains.append(translationatom_contents(translationatom))
    result['contains'] = contains
    return result


def translation_service_search(searchstring):
    translationatom = DBSession.query(TranslationAtom) \
        .join(TranslationGist). \
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service') \
        .one()
    response = translationgist_contents(translationatom.parent)
    return response


def update_perspective_fields(req, perspective_client_id, perspective_object_id, client):
    response = dict()
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=perspective_client_id,
                                                                   object_id=perspective_object_id).first()
    client = DBSession.query(Client).filter_by(id=client.id).first()  # variables['auth']
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")

    if perspective and not perspective.marked_for_deletion:
        try:
            link_gist = DBSession.query(TranslationGist) \
                .join(TranslationAtom) \
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id': link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            return {'error': str("Something wrong with the base")}
        fields = DBSession.query(DictionaryPerspectiveToField) \
            .filter_by(parent=perspective) \
            .all()
        DBSession.flush()
        for field in fields:  ## ?
            DBSession.delete(field)
        position = 1
        for field in req:
            create_nested_field(field=field,
                                perspective=perspective,
                                client_id=client.id,
                                upper_level=None,
                                link_ids=link_ids, position=position)
            position += 1

        return response
    else:
        return {'error': str("No such perspective in the system")}


def create_nested_field(field, perspective, client_id, upper_level, link_ids, position):
    field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                parent=perspective,
                                                field_client_id=field['client_id'],
                                                field_object_id=field['object_id'],
                                                upper_level=upper_level,
                                                position=position)
    if field.get('link'):
        field_object.link_client_id = field['link']['client_id']
        field_object.link_object_id = field['link']['object_id']
    DBSession.flush()
    contains = field.get('contains', None)
    if contains:
        inner_position = 1
        for subfield in contains:
            create_nested_field(subfield,
                                perspective,
                                client_id,
                                upper_level=field_object,
                                link_ids=link_ids,
                                position=inner_position)
            inner_position += 1
    return


def object_file_path(obj, base_path, folder_name, filename, create_dir=False):
    filename = sanitize_filename(filename)
    storage_dir = os.path.join(base_path, obj.__tablename__, folder_name, str(obj.client_id), str(obj.object_id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)
    return storage_path, filename


def create_object(content, obj, data_type, filename, folder_name, storage, json_input=True):
    import errno
    storage_path, filename = object_file_path(obj, storage["path"], folder_name, filename, True)
    directory = os.path.dirname(storage_path)  # TODO: find out, why object_file_path were not creating dir
    try:
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    with open(storage_path, 'wb+') as f:
        if json_input:
            f.write(base64.urlsafe_b64decode(content))
        else:
            shutil.copyfileobj(content, f)

    real_location = storage_path

    url = "".join((storage["prefix"],
                   storage["static_route"],
                   obj.__tablename__,
                   '/',
                   folder_name,
                   '/',
                   str(obj.client_id), '/',
                   str(obj.object_id), '/',
                   filename))
    return real_location, url


def create_entity(le_client_id, le_object_id, field_client_id, field_object_id,
                  additional_metadata, client, content=None, filename=None,
                  link_client_id=None, link_object_id=None, folder_name=None, up_lvl=None, locale_id=2,
                  storage=None):  # tested
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    parent = DBSession.query(LexicalEntry).filter_by(client_id=le_client_id, object_id=le_object_id).first()
    if not parent:
        return {'error': str("No such lexical entry in the system")}
    upper_level = None
    tr_atom = DBSession.query(TranslationAtom).join(TranslationGist, and_(
        TranslationAtom.locale_id == 2,
        TranslationAtom.parent_client_id == TranslationGist.client_id,
        TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
        TranslationGist.client_id == Field.data_type_translation_gist_client_id,
        TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
        Field.client_id == field_client_id, Field.object_id == field_object_id).first()
    data_type = tr_atom.content.lower()
    if up_lvl:
        upper_level = DBSession.query(Entity).filter_by(client_id=up_lvl[0],
                                                        object_id=up_lvl[1]).first()

    entity = Entity(client_id=client.id,
                    field_client_id=field_client_id,
                    field_object_id=field_object_id,
                    locale_id=locale_id,
                    ###additional_metadata=additional_metadata,
                    parent=parent)

    if upper_level:
        entity.upper_level = upper_level

    hash = None
    real_location = None
    url = None
    if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
        pass
        ##entity.data_type = data_type
        real_location, url = create_object(content, entity, data_type, filename, folder_name, storage)
        entity.content = url
        old_meta = entity.additional_metadata
        need_hash = True
        if old_meta:
            new_meta = old_meta  # json.loads(old_meta)
            if new_meta.get('hash'):
                need_hash = False
        if need_hash:
            hash = hashlib.sha224(base64.urlsafe_b64decode(content)).hexdigest()
            hash_dict = {'hash': hash}
            if old_meta:
                new_meta = old_meta  # json.loads(old_meta)
                new_meta.update(hash_dict)
            else:
                new_meta = hash_dict
            entity.additional_metadata = new_meta  # json.dumps(new_meta)
        old_meta = entity.additional_metadata
        if data_type == "markup":
            data_type_dict = {"data_type": "praat markup"}
            if old_meta:
                new_meta = old_meta  # json.loads(old_meta)
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta  # json.dumps(new_meta)
    elif data_type == 'link':
        try:
            pass
            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content
    entity.publishingentity.accepted = True

    DBSession.add(entity)
    # log.debug(filename)
    return (entity.client_id, entity.object_id)


def download(
        client_id,
        object_id,
        sqlalchemy_url,
        central_server,
        storage
):
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    with transaction.manager:
        dictionary_json = make_request(central_server+'dictionary/%s/%s'%(client_id,object_id))
        log.error(dictionary_json)

    return


def download_dictionary(
        client_id,
        object_id,
        sqlalchemy_url,
        central_server,
        storage
):
    download(
        client_id,
        object_id,
        sqlalchemy_url,
        central_server,
        storage
    )
