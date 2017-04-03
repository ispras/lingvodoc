# -*- coding: utf-8 -*-
import sqlite3
import base64
import requests
import json
import hashlib
import logging
from multiprocessing.util import register_after_fork
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
    DBSession as SyncDBSession,
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

from sqlalchemy.orm import (
    sessionmaker,
)

from lingvodoc.scripts import elan_parser
from pdb import set_trace

EAF_TIERS = {
    "literary translation": "Translation of Paradigmatic forms",
    "text": "Transcription of Paradigmatic forms",

    "word": "Word",
    "transcription": "Transcription",
    "translation": "Translation"
}
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def make_request(path, cookies, req_type='get', json_data=None):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    session.mount('http://', adapter)
    # log.error(path)
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
    translationatom = SyncDBSession.query(TranslationAtom) \
        .join(TranslationGist). \
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service') \
        .one()
    response = translationgist_contents(translationatom.parent)
    return response


def update_perspective_fields(req, perspective_client_id, perspective_object_id, client):
    response = dict()
    perspective = SyncDBSession.query(DictionaryPerspective).filter_by(client_id=perspective_client_id,
                                                                       object_id=perspective_object_id).first()
    client = SyncDBSession.query(Client).filter_by(id=client.id).first()  # variables['auth']
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")

    if perspective and not perspective.marked_for_deletion:
        try:
            link_gist = SyncDBSession.query(TranslationGist) \
                .join(TranslationAtom) \
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id': link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            return {'error': str("Something wrong with the base")}
        fields = SyncDBSession.query(DictionaryPerspectiveToField) \
            .filter_by(parent=perspective) \
            .all()
        SyncDBSession.flush()
        for field in fields:  ## ?
            SyncDBSession.delete(field)
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
    SyncDBSession.flush()
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


def object_file_path(obj, base_path, filename, create_dir=False):
    filename = sanitize_filename(filename)
    storage_dir = os.path.join(base_path, obj.__tablename__, str(obj.client_id), str(obj.object_id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)
    return storage_path, filename


def create_object(content, obj, data_type, filename, storage, json_input=True):
    import errno
    storage_path, filename = object_file_path(obj, storage["path"], filename, True)
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
                   str(obj.client_id), '/',
                   str(obj.object_id), '/',
                   filename))

    return real_location, url


def create_entity(session, le_client_id, le_object_id, field_client_id, field_object_id,
                  additional_metadata, client_id, object_id, content=None, filename=None,
                  link_client_id=None, link_object_id=None,
                  self_client_id=None, self_object_id=None, up_lvl=None, locale_id=2,
                  storage=None, published=False, accepted=False):  # tested
    upper_level = None
    tr_atom = session.query(TranslationAtom).join(TranslationGist, and_(
        TranslationAtom.locale_id == 2,
        TranslationAtom.parent_client_id == TranslationGist.client_id,
        TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
        TranslationGist.client_id == Field.data_type_translation_gist_client_id,
        TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
        Field.client_id == field_client_id, Field.object_id == field_object_id).first()
    data_type = tr_atom.content.lower()

    entity = Entity(client_id=client_id,
                    object_id=object_id,
                    field_client_id=field_client_id,
                    field_object_id=field_object_id,
                    self_client_id=self_client_id,
                    self_object_id=self_object_id,
                    locale_id=locale_id,
                    additional_metadata=additional_metadata,
                    parent_client_id=le_client_id,
                    parent_object_id=le_object_id)
    if upper_level:
        entity.upper_level = upper_level

    hash = None
    real_location = None
    url = None
    if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
        real_location, url = create_object(content, entity, data_type, filename, storage)
        entity.content = url
        old_meta = entity.additional_metadata
        need_hash = True
        if old_meta:
            if old_meta.get('hash'):
                need_hash = False
        if need_hash:
            hash = hashlib.sha224(base64.urlsafe_b64decode(content)).hexdigest()
            hash_dict = {'hash': hash}
            if old_meta:
                old_meta.update(hash_dict)
            else:
                old_meta = hash_dict
            entity.additional_metadata = old_meta
        if 'markup' in data_type:
            name = filename.split('.')
            ext = name[len(name) - 1]
            if ext.lower() == 'textgrid':
                data_type = 'praat markup'
            elif ext.lower() == 'eaf':
                data_type = 'elan markup'
        entity.additional_metadata['data_type'] = data_type
    elif data_type == 'link':
        try:

            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            pass
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content
    if published:
        entity.publishingentity.published = True
    if accepted:
        entity.publishingentity.accepted = True
    # TODO: it's very dirty unstable hack, fix it ASAP later (need to divide sync and async logic strictly)
    # SyncDBSession.add(entity)
    # log.debug(filename)
    return entity, entity.publishingentity


def create_objects(server, existing, session):
    new_entries = list()
    new_entities = list()
    publ_entities = list()
    for table in [Dictionary, DictionaryPerspective, DictionaryPerspectiveToField, LexicalEntry, Entity,
                  PublishingEntity]:
        curr_server = server[table.__tablename__]
        curr_existing = existing[table.__tablename__]
        curr_old = list()
        for client_id in curr_server:
            if client_id in curr_existing:
                for object_id in curr_server[client_id]:
                    if object_id in curr_existing[client_id]:
                        if curr_server[client_id][object_id] != curr_existing[client_id][object_id]:
                            kwargs = curr_server[client_id][object_id]
                            curr_old.append(kwargs)
                    else:
                        kwargs = curr_server[client_id][object_id]
                        if table == Entity:
                            new_entities.append(kwargs)
                        elif table == PublishingEntity:
                            if existing['entity'].get(client_id) and existing['entity'][client_id].get(object_id):
                                publ_entities.append(table(**kwargs))
                        else:
                            new_entries.append(table(**kwargs))

            else:
                for object_id in curr_server[client_id]:
                    kwargs = curr_server[client_id][object_id]
                    if table == Entity:
                        new_entities.append(kwargs)
                    elif table == PublishingEntity:
                        if existing['entity'].get(client_id) and existing['entity'][client_id].get(object_id):
                            publ_entities.append(table(**kwargs))
                    else:
                        new_entries.append(table(**kwargs))

        all_entries = session.query(table).all()
        for entry in all_entries:
            client_id = str(entry.client_id)
            object_id = str(entry.object_id)
            if client_id in curr_server:
                if object_id in curr_server[client_id]:
                    if table != Entity:
                        for key, value in list(curr_server[client_id][object_id].items()):
                            setattr(entry, key, value)
                    else:
                        entry.parent_client_id = curr_server[client_id][object_id]['parent_client_id']
                        entry.parent_object_id = curr_server[client_id][object_id]['parent_object_id']
        new_entries.extend(all_entries)
    return new_entries, new_entities, publ_entities


row2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}
dict2strippeddict = lambda r, r_class: {key: r[key] for key in r if key in [c.name for c in r_class.__table__.columns]}


def create_nested_content(tmp_resp):
    tmp_dict = dict()
    for entry in tmp_resp:
        if str(entry['client_id']) not in tmp_dict:
            tmp_dict[str(entry['client_id'])] = {str(entry['object_id']): entry}
        else:
            tmp_dict[str(entry['client_id'])][str(entry['object_id'])] = entry
    tmp_resp = tmp_dict
    return tmp_resp


def create_tmp_resp(table, query, response):
    tmp_resp = [row2dict(entry) for entry in query]
    if tmp_resp:
        tmp_resp = create_nested_content(tmp_resp)
    else:
        tmp_resp = dict()
    response[table.__tablename__] = tmp_resp


def basic_tables_content(client_id, object_id, session):
    response = dict()
    query = session.query(Dictionary).filter_by(client_id=client_id,
                                                object_id=object_id).all()
    create_tmp_resp(Dictionary, query, response)
    query = session.query(DictionaryPerspective).filter_by(parent_client_id=client_id,
                                                           parent_object_id=object_id).all()
    create_tmp_resp(DictionaryPerspective, query, response)
    query = session.query(DictionaryPerspectiveToField).join(DictionaryPerspectiveToField.parent) \
        .filter(DictionaryPerspective.parent_client_id == client_id,
                DictionaryPerspective.parent_object_id == object_id).all()
    create_tmp_resp(DictionaryPerspectiveToField, query, response)
    query = session.query(LexicalEntry).join(LexicalEntry.parent) \
        .filter(DictionaryPerspective.parent_client_id == client_id,
                DictionaryPerspective.parent_object_id == object_id).all()
    create_tmp_resp(LexicalEntry, query, response)
    query = session.query(Entity).join(Entity.parent).join(LexicalEntry.parent) \
        .filter(DictionaryPerspective.parent_client_id == client_id,
                DictionaryPerspective.parent_object_id == object_id).all()
    create_tmp_resp(Entity, query, response)
    query = session.query(PublishingEntity).join(PublishingEntity.parent).join(Entity.parent).join(
        LexicalEntry.parent) \
        .filter(DictionaryPerspective.parent_client_id == client_id,
                DictionaryPerspective.parent_object_id == object_id).all()
    create_tmp_resp(PublishingEntity, query, response)
    return response


#                    folder_name=None, up_lvl=None, locale_id=2,
#                   storage=None)


def create_new_entities(new_entities, storage, session, cookies):  # add queue
    entities_objects = list()
    for entity in new_entities:
        content = entity.get('content')
        data_type = entity['data_type'].lower()
        filename = None
        if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
            full_name = content.split('/')
            filename = full_name[len(full_name) - 1]
            content = make_request(content, cookies)
            if content.status_code != 200:
                log.error(entity['content'])
                session.rollback()
                return

            content = content.content
            content = base64.urlsafe_b64encode(content)

        entity_obj, publ_obj = create_entity(session,
                                             entity['parent_client_id'],
                                             entity['parent_object_id'],
                                             entity['field_client_id'],
                                             entity['field_object_id'],
                                             entity.get('additional_metadata'),
                                             entity['client_id'],
                                             entity['object_id'],
                                             content,
                                             filename,
                                             entity.get('link_client_id'),
                                             entity.get('link_object_id'),
                                             locale_id=entity.get('locale_id'),
                                             storage=storage,
                                             published=entity.get('published'),
                                             accepted=entity.get('accepted'),
                                             )

        entities_objects.append(entity_obj)
        entities_objects.append(publ_obj)
    return entities_objects


def download(
        client_id,
        object_id,
        central_server,
        storage,
        sqlalchemy_url,
        cookies
):  # :(

    engine = create_engine(sqlalchemy_url)
    register_after_fork(engine, engine.dispose)
    log = logging.getLogger(__name__)
    Session = sessionmaker(bind=engine)
    session = Session()
    log.setLevel(logging.DEBUG)
    # with transaction.manager:
    new_jsons = dict()
    for table in [Dictionary, DictionaryPerspective, DictionaryPerspectiveToField,
                  LexicalEntry, Entity, PublishingEntity]:
        new_jsons[table.__tablename__] = list()
    # new_entity_jsons = list()
    dictionary_json = make_request(central_server + 'dictionary/%s/%s' % (client_id, object_id), cookies)
    if dictionary_json.status_code != 200:
        log.error('dict fail', dictionary_json.status_code)
        session.rollback()
        return
    dictionary_json = dictionary_json.json()
    if dictionary_json['category'] == 'lingvodoc.ispras.ru/corpora':
        dictionary_json['category'] = 1
    else:
        dictionary_json['category'] = 0
    new_jsons['dictionary'].append(dict2strippeddict(dictionary_json, Dictionary))
    perspectives_json = make_request(central_server + 'dictionary/%s/%s/perspectives' % (client_id, object_id), cookies)
    if perspectives_json.status_code != 200:
        log.error('pesrps fail', perspectives_json.status_code)
        session.rollback()
        return
    perspectives_json = perspectives_json.json()
    for perspective_json in perspectives_json:
        # if dictionary_json['category'] == 'lingvodoc.ispras.ru/corpora':
        #     dictionary_json['category'] = 1
        # else:
        #     dictionary_json['category'] = 0
        meta_json = make_request(central_server + 'dictionary/%s/%s/perspective/%s/%s/meta' % (
            client_id,
            object_id,
            perspective_json['client_id'],
            perspective_json['object_id']), cookies, 'post',
                                 json_data=perspective_json.get('additional_metadata', dict()))
        if meta_json.status_code != 200:
            log.error('meta fail', meta_json.status_code)
            session.rollback()
            return
        perspective_json['additional_metadata'] = meta_json.json()

        fields_json = make_request(central_server + 'dictionary/%s/%s/perspective/%s/%s/fields' % (
            client_id,
            object_id,
            perspective_json['client_id'],
            perspective_json['object_id']), cookies, 'get')
        if fields_json.status_code != 200:
            log.error('fields fail', fields_json.status_code)
            session.rollback()
            return
        for field_json in fields_json.json():
            new_jsons['dictionaryperspectivetofield'].append(
                dict2strippeddict(field_json, DictionaryPerspectiveToField))  # todo: think about it

        new_jsons['dictionaryperspective'].append(dict2strippeddict(perspective_json, DictionaryPerspective))
        count_json = make_request(central_server + 'dictionary/%s/%s/perspective/%s/%s/all_count' % (
            client_id,
            object_id,
            perspective_json['client_id'],
            perspective_json['object_id']), cookies)
        if count_json.status_code != 200:
            log.error('count fail', count_json.status_code)
            session.rollback()
            return
        count_json = count_json.json()
        all_json = make_request(central_server + 'dictionary/%s/%s/perspective/%s/%s/all?start_from=0&count=%s' % (
            client_id,
            object_id,
            perspective_json['client_id'],
            perspective_json['object_id'],
            count_json['count']), cookies)
        published_json = None

        if all_json.status_code != 200:
            if all_json.status_code == 403:
                count_json = make_request(central_server + 'dictionary/%s/%s/perspective/%s/%s/published_count' % (
                    client_id,
                    object_id,
                    perspective_json['client_id'],
                    perspective_json['object_id']), cookies)
                if count_json.status_code != 200:
                    log.error('count fail', count_json.status_code)
                    session.rollback()
                    return
                count_json = count_json.json()
                published_json = make_request(
                    central_server + 'dictionary/%s/%s/perspective/%s/%s/published?start_from=0&count=%s' % (
                        client_id,
                        object_id,
                        perspective_json['client_id'],
                        perspective_json['object_id'],
                        count_json['count']), cookies)
                if published_json.status_code != 200:
                    log.error('published fail', all_json.status_code)
                    session.rollback()
                    return
                else:
                    publ_json = published_json.json()
                    if len(publ_json) > 0 and publ_json[0].get('contains') and len(publ_json[0]['contains']) > 0 and \
                            published_json.json()[0]['contains'][0].get('content') and 'entity hidden: you' in \
                            published_json.json()[0]['contains'][0]['content'].lower():
                        published_json = make_request(
                            central_server + 'dictionary/%s/%s/perspective/%s/%s/published?start_from=0&count=%s' % (
                                client_id,
                                object_id,
                                perspective_json['client_id'],
                                perspective_json['object_id'],
                                20), cookies)
                        if published_json.status_code != 200:
                            session.rollback()
                            return

            else:
                log.error('get all fail', all_json.status_code)
                session.rollback()
                return
        if published_json:
            all_json = published_json
        all_json = all_json.json()
        for lexical_entry_json in all_json:
            new_jsons['lexicalentry'].append(dict2strippeddict(lexical_entry_json, LexicalEntry))
            for entity_json in lexical_entry_json['contains']:
                if not entity_json.get('self_client_id'):
                    # if entity.json.get('link_client_id') and entity.json.get('link_object_id'):s

                    new_jsons['entity'].append(entity_json)

                    new_jsons['publishingentity'].append(dict2strippeddict(entity_json, PublishingEntity))
                    for inner_entity in entity_json['contains']:  # TODO: infinite nesting
                        new_jsons['entity'].append(inner_entity)
                        new_jsons['publishingentity'].append(dict2strippeddict(inner_entity, PublishingEntity))
    response = basic_tables_content(client_id, object_id, session)
    for key in new_jsons:
        tmp = create_nested_content(new_jsons[key])
        new_jsons[key] = tmp

    new_objects, new_entities, publ_entities = create_objects(new_jsons, response, session)

    session.bulk_save_objects(new_objects)

    session.bulk_save_objects(create_new_entities(new_entities, storage=storage, session=session, cookies=cookies))
    session.bulk_save_objects(publ_entities)
    log.error('dictionary %s %s downloaded' % (client_id, object_id))
    session.commit()
    engine.dispose()
    return


def download_dictionary(
        client_id,
        object_id,
        central_server,
        storage,
        sqlalchemy_url,
        cookies
):
    download(
        client_id,
        object_id,
        central_server,
        storage,
        sqlalchemy_url,
        cookies
    )
