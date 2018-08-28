# coding: utf-8
import os
import sqlite3
import base64
import hashlib
import random
import string
import time
import logging
import shutil
import transaction
from collections import defaultdict
from pathvalidate import sanitize_filename
from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.attributes import flag_modified
from lingvodoc.cache.caching import TaskStatus
from lingvodoc.utils.creation import update_metadata
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
    PublishingEntity,
    user_to_group_association
)
from lingvodoc.utils.search import get_id_to_field_dict


def find_lexical_entries_by_tags(tags, field_client_id, field_object_id):
    return DBSession.query(LexicalEntry) \
        .join(LexicalEntry.entity) \
        .join(Entity.publishingentity) \
        .join(Entity.field) \
        .filter(Entity.content.in_(tags),
                PublishingEntity.accepted == True,
                Field.client_id == field_client_id,
                Field.object_id == field_object_id).all()

def find_all_tags(lexical_entry, field_client_id, field_object_id):
    tag = None
    for entity in lexical_entry.entity:
        if entity.field.data_type == 'Grouping Tag':
            tag = entity.content
            break
    if not tag:
        return []
    else:
        tags = [tag]
        new_tags = [tag]
        while new_tags:
            lexical_entries = find_lexical_entries_by_tags(new_tags, field_client_id, field_object_id)
            new_tags = list()
            for lex in lexical_entries:
                entities = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .join(Entity.publishingentity) \
                    .filter(Entity.parent == lex,
                            PublishingEntity.accepted == True,
                            Field.client_id == field_client_id,
                            Field.object_id == field_object_id).all()
                for entity in entities:
                    if entity.content not in tags:
                        tags.append(entity.content)
                        new_tags.append(entity.content)
        return tags

def create_group_entity(request, client, user):  # tested
        response = dict()
        req = request
        tags = list()
        if 'tag' in req:
            tags.append(req['tag'])
        field_client_id=req['field_client_id']
        field_object_id=req['field_object_id']
        field = DBSession.query(Field).\
            filter_by(client_id=field_client_id, object_id=field_object_id).first()

        if not field:
            return {'error': str("No such field in the system")}

        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if not parent:
                return {'error': str("No such lexical entry in the system")}
            par_tags = find_all_tags(parent, field_client_id, field_object_id)
            for tag in par_tags:
                if tag not in tags:
                    tags.append(tag)
        if not tags:
            n = 10  # better read from settings
            tag = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                         for c in range(n))
            tags.append(tag)
        lexical_entries = find_lexical_entries_by_tags(tags, field_client_id, field_object_id)
        for par in req['connections']:
            parent = DBSession.query(LexicalEntry).\
                filter_by(client_id=par['client_id'], object_id=par['object_id']).first()
            if parent not in lexical_entries:
                lexical_entries.append(parent)

        for lex in lexical_entries:
            for tag in tags:
                tag_entity = DBSession.query(Entity) \
                    .join(Entity.field) \
                    .filter(Entity.parent == lex,
                            Field.client_id == field_client_id,
                            Field.object_id == field_object_id,
                            Entity.content == tag).first()
                if not tag_entity:
                    tag_entity = Entity(client_id=client.id,
                                        field=field, content=tag, parent=lex)

                    group = DBSession.query(Group).join(BaseGroup).filter(
                        BaseGroup.subject == 'lexical_entries_and_entities',
                        Group.subject_client_id == tag_entity.parent.parent.client_id,
                        Group.subject_object_id == tag_entity.parent.parent.object_id,
                        BaseGroup.action == 'create').one()
                    if user in group.users:
                        tag_entity.publishingentity.accepted = True



def get_dict_attributes(sqconn):
    dict_trav = sqconn.cursor()
    dict_trav.execute("""SELECT
                        dict_name,
                        dict_identificator,
                        dict_description
                        FROM
                        dict_attributes
                        WHERE
                        id = 1;""")
    req = dict()
    for dictionary in dict_trav:
        req['dictionary_name'] = dictionary[0]
        req['dialeqt_id'] = dictionary[1]
    return req


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


def create_field(translation_gist_client_id, translation_gist_object_id, data_type_translation_gist_client_id,
                 data_type_translation_gist_object_id, client):
    try:
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        field = Field(client_id=client.id, ###
                                            data_type_translation_gist_client_id=data_type_translation_gist_client_id,
                                            data_type_translation_gist_object_id=data_type_translation_gist_object_id,
                                            translation_gist_client_id=translation_gist_client_id,
                                            translation_gist_object_id=translation_gist_object_id
                                            )

        DBSession.add(field)
        DBSession.flush()

        return {'object_id': field.object_id,
                'client_id': field.client_id}
    except KeyError as e:
        return {'error': str(e)}


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


def update_perspective_fields(req, perspective_client_id, perspective_object_id, client):
    response = dict()
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=perspective_client_id,
                                                                   object_id=perspective_object_id).first()
    client = DBSession.query(Client).filter_by(id=client.id).first() #variables['auth']
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
    if perspective and not perspective.marked_for_deletion:
        try:
            link_gist = DBSession.query(TranslationGist)\
                .join(TranslationAtom)\
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2).first()
            link_ids = {'client_id':link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            return {'error': str("Something wrong with the base")}
        fields = DBSession.query(DictionaryPerspectiveToField)\
            .filter_by(parent=perspective)\
            .all()
        DBSession.flush()
        #for field in fields:
        #    DBSession.delete(field)
        if not int(len(fields)):
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
                  additional_metadata, client, content= None, filename=None,
                  link_client_id=None, link_object_id=None, folder_name=None, up_lvl=None, locale_id=2, storage=None):
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
    if additional_metadata is not None:
        entity = Entity(client_id=client.id,
                        field_client_id=field_client_id,
                        field_object_id=field_object_id,
                        locale_id=locale_id,
                        additional_metadata=additional_metadata,
                        parent=parent)
    else:
        entity = Entity(client_id=client.id,
                        field_client_id=field_client_id,
                        field_object_id=field_object_id,
                        locale_id=locale_id,
                        #additional_metadata=additional_metadata,
                        parent=parent)
    if upper_level:
        entity.upper_level = upper_level
    if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
        ##entity.data_type = data_type
        real_location, url = create_object(content, entity, data_type, filename, folder_name, storage)
        entity.content = url
        old_meta = entity.additional_metadata
        need_hash = True
        if old_meta:
            new_meta = old_meta
            if new_meta.get('hash'):
                need_hash = False
        if need_hash:
            hash = hashlib.sha224(base64.urlsafe_b64decode(content)).hexdigest()
            hash_dict = {'hash': hash}
            if old_meta:
                new_meta = old_meta
                new_meta.update(hash_dict)
            else:
                new_meta = hash_dict
            entity.additional_metadata = new_meta
            #flag_modified(entity, 'additional_metadata')
        old_meta = entity.additional_metadata
        if data_type == "markup":
            data_type_dict = {"data_type": "praat markup"}
            if old_meta:
                new_meta = old_meta
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta
            #flag_modified(entity, 'additional_metadata')
        if data_type == "sound":
            data_type_dict = {"data_type": "sound"}
            if old_meta:
                new_meta = old_meta
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta
            #flag_modified(entity, 'additional_metadata')
    elif data_type == 'link':
        try:
            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content
    entity.publishingentity.accepted = True
    DBSession.add(entity)
    DBSession.flush()
    return (entity.client_id, entity.object_id)

def upload_audio_with_markup(sound_ids, ids_map, fields_dict, sound_and_markup_cursor, audio_hashes, markup_hashes,
                             folder_name, client_id, is_a_regular_form, client, storage, locale_id=2):
    log = logging.getLogger(__name__)
    sound_field = "Sound"
    markup_field = "Markup"
    if "Sounds of Paradigmatic forms" in fields_dict:
        sound_field = "Sounds of Paradigmatic forms"
    if "Paradigm Markup" in fields_dict:
        markup_field = "Paradigm Markup"
    markup_counter = 0
    audio_counter = 0
    for cursor in sound_and_markup_cursor:
        markup_update_flag = False
        lvl = None
        blob_id = cursor[0]
        description_type = int(cursor[5])
        if description_type == 1:
            audio = cursor[2]
            markup = cursor[1]
        if description_type == 2:
            audio = cursor[1]
            markup = cursor[2]
        common_name = str(cursor[3])
        word_id = cursor[4]
        blob_description = cursor[5]
        sound_metadata = {}
        if blob_description is not None:
            sound_metadata.update({"blob_description": blob_description, "original_filename": common_name})
        if not audio or not markup:
            continue
        sound_ids.add(word_id)
        audio_hash = hashlib.sha224(audio).hexdigest()
        markup_hash = hashlib.sha224(markup).hexdigest()
        if audio_hash not in audio_hashes:
            if common_name:
                fname, ext = os.path.splitext(common_name)
                ext = ext.replace(".", "").replace(" ", "")
                fname = fname.replace(".", "_")
                if not ext:
                    ext = "wav"
                filename = "%s.%s" % (fname, ext)
            else:
                filename = 'noname.wav'
            audio_counter += 1
            sound_metadata.update({"hash": audio_hash})
            lvl = create_entity(ids_map[int(word_id)][0],
                                ids_map[int(word_id)][1],
                                fields_dict[sound_field][0],
                                fields_dict[sound_field][1],
                                sound_metadata,
                                client,
                                locale_id=locale_id,
                                filename=filename,
                                content=base64.urlsafe_b64encode(audio).decode(),
                                folder_name="%s_sounds"%folder_name,
                                storage=storage)
        else:
            lvl = audio_hashes[audio_hash][0]
            markup_update_flag = True
        if markup and markup_hash not in markup_hashes:
            if lvl:
                if common_name:
                    fname, ext = os.path.splitext(common_name)
                    ext = ext.replace(".", "").replace(" ", "")
                    fname = fname.replace(".", "_")
                    if not ext:
                        ext = "TextGrid"
                    filename = "%s.%s" % (fname, ext)
                else:
                    filename = 'noname.TextGrid'
                markup_hashes.add(markup_hash)
    
                if not markup_update_flag:
                    le_id = ids_map[int(word_id)]
                else:
                    le_id = audio_hashes[audio_hash][1]
                sound_metadata.update({"hash": markup_hash})
                create_entity(le_id[0],
                              le_id[1],
                              fields_dict[markup_field][0],
                              fields_dict[markup_field][1],
                              sound_metadata,
                              client,
                              locale_id=locale_id,
                              filename=filename,
                              content=base64.urlsafe_b64encode(markup).decode(),
                              folder_name="%s_markup"%folder_name,
                              up_lvl=lvl,
                              storage=storage)
                markup_counter += 1
            if markup_counter > 50:
                DBSession.flush()
        if audio_counter > 50:
            DBSession.flush()
            audio_counter = 0
            if markup_counter > 50:
                DBSession.flush()
        sound_metadata.clear()
    DBSession.flush()

def upload_audio(sound_ids, ids_map, fields_dict, sound_and_markup_cursor, audio_hashes, markup_hashes, folder_name,
                 client_id, is_a_regular_form, client, storage, locale_id=2):
    sound_field = "Sound"
    if "Sounds of Paradigmatic forms" in fields_dict:
        sound_field = "Sounds of Paradigmatic forms"
    audio_counter = 0
    for cursor in sound_and_markup_cursor:
        blob_id = cursor[0]
        description_type = int(cursor[5])
        if description_type == 1:
            audio = cursor[2]
            markup = cursor[1]
        common_name = str(cursor[3])
        word_id = cursor[4]
        blob_description = cursor[5]
        sound_metadata = {}
        if blob_description is not None:
            sound_metadata.update({"blob_description": blob_description, "original_filename": common_name})
        if word_id in sound_ids:
            continue
        sound_ids.add(word_id)
        audio_hash = hashlib.sha224(audio).hexdigest()
        if audio_hash not in audio_hashes:
            if common_name:
                fname, ext = os.path.splitext(common_name)
                ext = ext.replace(".", "").replace(" ", "")
                fname = fname.replace(".", "_")
                if not ext:
                    ext = "wav"
                filename = "%s.%s" % (fname, ext)
            else:
                filename = 'noname.wav'

            audio_counter += 1
            lvl = create_entity(ids_map[int(word_id)][0],
                                ids_map[int(word_id)][1],
                                fields_dict[sound_field][0],
                                fields_dict[sound_field][1],
                                sound_metadata,
                                client,
                                locale_id=locale_id,
                                filename=filename,
                                content=base64.urlsafe_b64encode(audio).decode(),
                                folder_name="%s_sounds" % folder_name,
                                storage=storage)
            audio_hashes[audio_hash] = None
        if audio_counter > 50:
            DBSession.flush()
            audio_counter = 0
    DBSession.flush()




def translation_service_search(searchstring):
    translationatom = DBSession.query(TranslationAtom)\
        .join(TranslationGist).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service')\
        .order_by(TranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response

def translation_service_search_all(searchstring):
    tralationgist = DBSession.query(TranslationGist)\
        .join(TranslationAtom).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2)\
        .order_by(TranslationGist.client_id)\
        .first()
    response = {"client_id": tralationgist.client_id, "object_id": tralationgist.object_id}
    #response = translationgist_contents(translationatom.parent)
    return response



def check_perspective_perm(user_id, perspective_client_id, perspective_object_id):
    #user_id = Client.get_user_by_client_id(client_id).id
    create_base_group = DBSession.query(BaseGroup).filter_by(
        subject = 'lexical_entries_and_entities', action = 'create').first()
    user_create = DBSession.query(user_to_group_association, Group).filter(and_(
        user_to_group_association.c.user_id == user_id,
        user_to_group_association.c.group_id == Group.id,
        Group.base_group_id == create_base_group.id,
        Group.subject_client_id == perspective_client_id,
        Group.subject_object_id == perspective_object_id)).limit(1).count() > 0
    return user_create


def check_dictionary_perm(user_id, dictionary_client_id, dictionary_object_id):
    #user_id = Client.get_user_by_client_id(client_id).id
    create_base_group = DBSession.query(BaseGroup).filter_by(
        subject = 'perspective', action = 'create').first()
    user_create = DBSession.query(user_to_group_association, Group).filter(and_(
        user_to_group_association.c.user_id == user_id,
        user_to_group_association.c.group_id == Group.id,
        Group.base_group_id == create_base_group.id,
        Group.subject_client_id == dictionary_client_id,
        Group.subject_object_id == dictionary_object_id)).limit(1).count() > 0
    return user_create

def convert_db_new(dictionary_client_id, dictionary_object_id, blob_client_id, blob_object_id, language_client_id, language_object_id, client_id, gist_client_id, gist_object_id, storage,
                   locale_id, task_status):
    log = logging.getLogger(__name__)
    #from lingvodoc.cache.caching import CACHE
    task_status.set(1, 1, "Preparing")
    hashes = dict()
    markups = set()
    time.sleep(3)
    field_ids = {}
    with transaction.manager:
        blob = DBSession.query(UserBlobs).filter_by(client_id=blob_client_id, object_id=blob_object_id).first()
        filename = blob.real_storage_path
        log.debug("client_id: %s" % client_id)
        log.debug("Starting convert_one")
        log.debug("Creating session")
        sqconn = sqlite3.connect(filename)
        log.debug("Connected to sqlite3 database")
        client = DBSession.query(Client).filter_by(id=client_id).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           client_id)
        user = client.user
        if not user:
            log.debug("ERROR")
            return {}
        all_fieldnames = ("Markup",
                          "Paradigm Markup",
                          "Word",
                          "Transcription",
                          "Translation",
                          "Sound",
                          "Etymology",
                          "Backref",
                          "Word of Paradigmatic forms",
                          "Transcription of Paradigmatic forms",
                          "Translation of Paradigmatic forms",
                          "Sounds of Paradigmatic forms"
                         )
        task_status.set(2, 5, "Checking fields")
        field_ids = get_id_to_field_dict()
        # for name in all_fieldnames:
        #     data_type_query = DBSession.query(Field) \
        #         .join(TranslationGist,
        #               and_(Field.translation_gist_object_id == TranslationGist.object_id,
        #                    Field.translation_gist_client_id == TranslationGist.client_id))\
        #         .join(TranslationGist.translationatom)
        #     #todo: a way to find this fields if wwe cannot use one
        #     field = data_type_query.filter(TranslationAtom.locale_id == 2,
        #                                    TranslationAtom.content == name)\
        #                            .order_by(TranslationAtom.client_id)\
        #                            .first()
        #     field_ids[name] = (field.client_id, field.object_id)
        fp_fields = ("Word", "Transcription", "Translation", "Sound", "Markup", "Etymology", "Backref")
        sp_fields = ("Word of Paradigmatic forms",
                     "Transcription of Paradigmatic forms",
                     "Translation of Paradigmatic forms",
                     "Sounds of Paradigmatic forms",
                     "Paradigm Markup",
                     "Backref")
        fp_structure = set([field_ids[x] for x in fp_fields])
        sp_structure = set([field_ids[x] for x in sp_fields])
        DBSession.flush()
        update_flag = False
        if dictionary_client_id is not None and dictionary_object_id is not None:
            update_flag = True
            if not check_dictionary_perm(user.id, dictionary_client_id, dictionary_object_id):
                task_status.set(None, -1, "Wrong permissions: dictionary")
                return
        try:
            dict_attributes = get_dict_attributes(sqconn)
        except:
            task_status.set(None, -1, "Conversion failed: database disk image is malformed")
            return {}
        if not update_flag:
            lang_parent = DBSession.query(Language).filter_by(client_id=language_client_id,
                                                              object_id=language_object_id).first()

            resp = translation_service_search("WiP")
            state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
            dictionary = Dictionary(client_id=client_id,
                                    state_translation_gist_object_id=state_translation_gist_object_id,
                                    state_translation_gist_client_id=state_translation_gist_client_id,
                                    parent=lang_parent,
                                    translation_gist_client_id=gist_client_id,
                                    translation_gist_object_id=gist_object_id
                                          )
                                    #additional_metadata=additional_metadata)
            DBSession.add(dictionary)
            DBSession.flush()

            dictionary_client_id = dictionary.client_id
            dictionary_object_id = dictionary.object_id
            for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
                new_group = Group(parent=base,
                                  subject_object_id=dictionary.object_id,
                                  subject_client_id=dictionary.client_id)
                if user not in new_group.users:
                    new_group.users.append(user)
                DBSession.add(new_group)
                DBSession.flush()
        perspective_metadata = {"authors": ""}
        authors = sqconn.cursor()
        authors.execute("select dict_author, dict_coauthors from dict_attributes  where id=1;")
        author, coauthors = authors.fetchone()
        authors_set = set()
        if author is not None:
            for word in author.split(","):
                if word:
                    authors_set.add(word.strip())
        if coauthors is not None:
            for word in coauthors.split(","):
                if word:
                    authors_set.add(word.strip())
        authors_string = ", ".join(authors_set)
        if authors_string:
            perspective_metadata = {"authors": authors_string}
        parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id,
                                                       object_id=dictionary_object_id).first()

        if not parent:
            return {'error': str("No such dictionary in the system")}
        if parent.additional_metadata:
            old_meta = parent.additional_metadata
            if authors_set:
                if "authors" in old_meta:
                        old_authors_str = old_meta["authors"]
                        new_authors_set = set()
                        for old_word in old_authors_str.split(","):
                            if old_word:
                                new_authors_set.add(old_word.strip())
                        old_authors_set = new_authors_set.copy()
                        for author in authors_set:
                            if not author in new_authors_set:
                                if author:
                                    new_authors_set.add(author.strip())
                        if new_authors_set != old_authors_set:
                            new_authors_string = ", ".join(new_authors_set)
                            parent.additional_metadata["authors"] = new_authors_string
        else:
            parent.additional_metadata = perspective_metadata
        flag_modified(parent, 'additional_metadata')
        if not update_flag:
            """
            # FIRST PERSPECTIVE
            """
            task_status.set(3, 8, "Handling words perspective")
            resp = translation_service_search_all("Lexical Entries")
            persp_translation_gist_client_id, persp_translation_gist_object_id = resp['client_id'], resp['object_id']

            first_perspective = DictionaryPerspective(client_id=client.id, ###
                                                state_translation_gist_object_id=state_translation_gist_object_id,
                                                state_translation_gist_client_id=state_translation_gist_client_id,
                                                parent=parent,
                                                import_source="Lingvodoc-0.98",
                                                import_hash=dict_attributes['dialeqt_id'],
                                                #additional_metadata=perspective_metadata,
                                                translation_gist_client_id=persp_translation_gist_client_id,
                                                translation_gist_object_id=persp_translation_gist_object_id
                                                )
            # if is_template is not None:
            #     perspective.is_template = is_template
            DBSession.add(first_perspective)
            owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
            owner = owner_client.user
            for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
                new_group = Group(parent=base,
                                  subject_object_id=first_perspective.object_id,
                                  subject_client_id=first_perspective.client_id)
                if user not in new_group.users:
                    new_group.users.append(user)
                if owner not in new_group.users:
                    new_group.users.append(owner)
                DBSession.add(new_group)
                DBSession.flush()
            first_perspective_client_id = first_perspective.client_id
            first_perspective_object_id = first_perspective.object_id
            """
            # SECOND PERSPECTIVE
            """
            task_status.set(4, 12, "Handling paradigms perspective")
            resp = translation_service_search_all("Paradigms")
            persp_translation_gist_client_id, persp_translation_gist_object_id = resp['client_id'], resp['object_id']
            second_perspective = DictionaryPerspective(client_id=client.id, ### variables['auth']
                                                state_translation_gist_object_id=state_translation_gist_object_id,
                                                state_translation_gist_client_id=state_translation_gist_client_id,
                                                parent=parent,
                                                import_source="Lingvodoc-0.98",
                                                import_hash=dict_attributes['dialeqt_id'],
                                                #additional_metadata=perspective_metadata,
                                                translation_gist_client_id=persp_translation_gist_client_id,
                                                translation_gist_object_id=persp_translation_gist_object_id
                                                )
            # if is_template is not None:
            #     perspective.is_template = is_template
            DBSession.add(second_perspective)
            owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
            owner = owner_client.user
            for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
                new_group = Group(parent=base,
                                  subject_object_id=second_perspective.object_id,
                                  subject_client_id=second_perspective.client_id)
                if user not in new_group.users:
                    new_group.users.append(user)
                if owner not in new_group.users:
                    new_group.users.append(owner)
                DBSession.add(new_group)
            second_perspective_client_id = second_perspective.client_id
            second_perspective_object_id = second_perspective.object_id
        else:
            first_perspective = None
            second_perspective = None
            for perspective in DBSession.query(DictionaryPerspective).filter_by(parent=parent,
                                                                                marked_for_deletion=False):
                structure = set()
                fields = DBSession.query(DictionaryPerspectiveToField)\
                            .filter_by(parent=perspective,
                                       marked_for_deletion=False)\
                            .all()
                DBSession.flush()
                for p_to_field in fields:
                    structure.add((p_to_field.field_client_id, p_to_field.field_object_id))
                if not fp_structure.difference(structure):
                    if not check_perspective_perm(user.id, perspective.client_id, perspective.object_id):
                        task_status.set(None, -1, "Wrong permissions: perspective")
                        return
                    first_perspective = perspective
                elif not sp_structure.difference(structure):
                    if not check_perspective_perm(user.id, perspective.client_id, perspective.object_id):
                        task_status.set(None, -1, "Wrong permissions: perspective")
                        return
                    second_perspective = perspective
                structure.clear()
            lexes = []
            if first_perspective:
                lexes = DBSession.query(DictionaryPerspective, LexicalEntry, Entity)\
                    .filter(and_(DictionaryPerspective.object_id==first_perspective.object_id,
                            DictionaryPerspective.client_id==first_perspective.client_id))\
                    .join(LexicalEntry, and_( LexicalEntry.parent_object_id==DictionaryPerspective.object_id,
                                              LexicalEntry.parent_client_id==DictionaryPerspective.client_id))\
                    .join(Entity, and_(LexicalEntry.object_id==Entity.parent_object_id,
                                       LexicalEntry.client_id==Entity.parent_client_id))
                first_perspective_client_id = first_perspective.client_id
                first_perspective_object_id = first_perspective.object_id
            else:
                task_status.set(None, -1, "Conversion failed: Lexical Entries perspective not found")
                return {}
            p_lexes = []
            if second_perspective:
                p_lexes = DBSession.query(DictionaryPerspective, LexicalEntry, Entity)\
                    .filter(and_(DictionaryPerspective.object_id==second_perspective.object_id,
                            DictionaryPerspective.client_id==second_perspective.client_id))\
                    .join(LexicalEntry, and_( LexicalEntry.parent_object_id==DictionaryPerspective.object_id,
                                              LexicalEntry.parent_client_id==DictionaryPerspective.client_id))\
                    .join(Entity, and_(LexicalEntry.object_id==Entity.parent_object_id,
                                       LexicalEntry.client_id==Entity.parent_client_id))
                second_perspective_client_id = second_perspective.client_id
                second_perspective_object_id = second_perspective.object_id
            else:
                task_status.set(None, -1, "Conversion failed: Paradigms perspective not found")
                return {}
            #hashes = [x[2].additional_metadata["hash"]  for x in lexes if x[2].field.data_type == "Sound"]
            #hashes = hashes[:] + \
            #         [x[2].additional_metadata["hash"]  for x in p_lexes if x[2].field.data_type == "Sound"]
            #hashes = set(hashes)
            hashes = {key[2].additional_metadata["hash"]: ((key[2].client_id, key[2].object_id), (key[1].client_id, key[1].object_id)) for key in lexes if key[2].field.data_type == "Sound"}
            par_hashes = {key[2].additional_metadata["hash"]: ((key[2].client_id, key[2].object_id), (key[1].client_id, key[1].object_id)) for key in p_lexes if key[2].field.data_type == "Sound"}
            hashes.update(par_hashes)
            markups = [x[2].additional_metadata["hash"]  for x in lexes if x[2].field.data_type == "Markup"]
            markups = markups[:] + \
                      [x[2].additional_metadata["hash"]  for x in p_lexes if x[2].field.data_type == "Markup"]
            markups = set(markups)
            links = [((x[2].link.client_id, x[2].link.object_id), (x[1].client_id, x[1].object_id))
                     for x in lexes if x[2].field.data_type == "Link"]
            links = links[:] + [((x[2].link.client_id, x[2].link.object_id), (x[1].client_id, x[1].object_id))
                     for x in p_lexes if x[2].field.data_type == "Link"]

        """
        # FIRST PERSPECTIVE FIELDS CREATION
        """
        fp_fields_dict = {}
        fp_field_names = ("Word", "Transcription", "Translation", "Sound", "Etymology", "Backref")
        fields_list = []
        for fieldname in fp_field_names: #

            if fieldname == "Backref":
                fields_list.append(
                    {
                    "client_id": field_ids[fieldname][0],
                    "object_id": field_ids[fieldname][1],
                    "link":{
                        "client_id": second_perspective_client_id,
                        "object_id": second_perspective_object_id
                    }
                    }
                )

            elif fieldname == "Sound":
                fields_list.append(
                    {
                    "client_id": field_ids[fieldname][0],
                    "object_id": field_ids[fieldname][1],
                    "contains":[{
                       "client_id": field_ids["Markup"][0],
                       "object_id": field_ids["Markup"][1]
                    }
                    ]
                    }
                )
            else:
                fields_list.append({"client_id": field_ids[fieldname][0], "object_id": field_ids[fieldname][1]})
            fp_fields_dict[fieldname] = (field_ids[fieldname][0], field_ids[fieldname][1])
        fp_fields_dict["Markup"] = (field_ids["Markup"][0], field_ids["Markup"][1])
        update_perspective_fields(fields_list, first_perspective_client_id, first_perspective_object_id, client )
        """
        # Creating fields of the second perspective
        """
        sp_fields_dict = {}
        fields_list = []
        sp_field_names = ("Word of Paradigmatic forms",
                          "Transcription of Paradigmatic forms",
                          "Translation of Paradigmatic forms",
                          "Sounds of Paradigmatic forms",
                          "Backref")
        for fieldname in sp_field_names: #
            if fieldname == "Backref":
                fields_list.append(
                    {
                    "client_id": field_ids[fieldname][0],
                    "object_id": field_ids[fieldname][1],
                    "link":{
                        "client_id": first_perspective_client_id,
                        "object_id": first_perspective_object_id
                    }
                    }
                )
            elif fieldname == "Sounds of Paradigmatic forms":
                fields_list.append(
                    {
                    "client_id": field_ids[fieldname][0],
                    "object_id": field_ids[fieldname][1],
                    "contains":[{
                       "client_id": field_ids["Paradigm Markup"][0],
                       "object_id": field_ids["Paradigm Markup"][1]
                    }
                    ]
                    }
                )
            else:
                fields_list.append({"client_id": field_ids[fieldname][0], "object_id": field_ids[fieldname][1]})
            sp_fields_dict[fieldname] = (field_ids[fieldname][0], field_ids[fieldname][1])
        sp_fields_dict["Paradigm Markup"] = (field_ids["Paradigm Markup"][0], field_ids["Paradigm Markup"][1])
        update_perspective_fields(fields_list, second_perspective_client_id, second_perspective_object_id, client)
        ###################
        ## Entities
        ###################
        if update_flag:
            audio_hashes = hashes
            markup_hashes = markups
            lexes_with_text = [x for x in lexes if x[2].field.data_type == "Text" and
                               (x[2].field.client_id, x[2].field.object_id) in field_ids.values()]
            p_lexes_with_text = [x for x in p_lexes if x[2].field.data_type == "Text"
                                 and (x[2].field.client_id, x[2].field.object_id) in field_ids.values()]
        else:
            audio_hashes = dict()
            markup_hashes = set()
        ###################
        ## Lexical entries
        ###################
        ids_mapping = {}
        sqcursor = sqconn.cursor()
        sqcursor.execute("""select
                  id,
                  word,
                  Transcription,
                  translation
                  from dictionary
            where dictionary.is_a_regular_form=1""")
        for row in sqcursor:
            wordid = int(row[0])
            word = row[1]
            transcription = row[2]
            translation = row[3]
            if update_flag:
                match_dict = defaultdict(list)
                for lex in lexes_with_text:
                    if lex[2].content:
                        if lex[2].content == word:
                            if field_ids["Word"] == (lex[2].field.client_id, lex[2].field.object_id):
                                match_dict[lex[1]].append(lex)
                        if lex[2].content == transcription:
                            if field_ids["Transcription"] == (lex[2].field.client_id, lex[2].field.object_id):
                                match_dict[lex[1]].append(lex)
                        if lex[2].content == translation:
                            if field_ids["Translation"] == (lex[2].field.client_id, lex[2].field.object_id):
                                match_dict[lex[1]].append(lex)
                match_dict = { k: v for k, v in match_dict.items()
                               if len(v) >= 2 or len(v) == 1 and [x[1] for x in lexes_with_text].count(k) == 1}
                max_sim = None
                for le in match_dict:
                    if max_sim is None:
                        max_sim = le
                    else:
                        if len(match_dict[le]) >= len(match_dict[max_sim]):
                                max_sim = le
                if max_sim:
                    lexical_entry_client_id = max_sim.client_id
                    lexical_entry_object_id = max_sim.object_id
                    sim = [x[2].content for x in match_dict[max_sim]]
                    if not word in sim and word:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      fp_fields_dict["Word"][0],
                                      fp_fields_dict["Word"][1],
                                      None,
                                      client,
                                      word,
                                      filename=None,
                                      storage=storage)
                    if not transcription in sim and transcription:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      fp_fields_dict["Transcription"][0],
                                      fp_fields_dict["Transcription"][1],
                                      None,
                                      client,
                                      transcription,
                                      filename=None,
                                      storage=storage)
                    if not translation in sim and translation:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      fp_fields_dict["Translation"][0],
                                      fp_fields_dict["Translation"][1],
                                      None,
                                      client,
                                      translation,
                                      filename=None,
                                      storage=storage)
                else:
                    lexentr = LexicalEntry( client_id=client.id,
                                           parent_object_id=first_perspective_object_id, parent=first_perspective)
                    DBSession.add(lexentr)
                    lexical_entry_client_id = lexentr.client_id
                    lexical_entry_object_id = lexentr.object_id
                    if word:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      fp_fields_dict["Word"][0],
                                      fp_fields_dict["Word"][1],
                                      None,
                                      client,
                                      word,
                                      filename=None,
                                      storage=storage)
                    if transcription:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      fp_fields_dict["Transcription"][0],
                                      fp_fields_dict["Transcription"][1],
                                      None,
                                      client,
                                      transcription,
                                      filename=None,
                                      storage=storage)
                    if translation:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      fp_fields_dict["Translation"][0],
                                      fp_fields_dict["Translation"][1],
                                      None,
                                      client,
                                      translation,
                                      filename=None,
                                      storage=storage)
            else:
                lexentr = LexicalEntry(client_id=client.id,
                                       parent_object_id=first_perspective_object_id,
                                       parent=first_perspective)
                DBSession.add(lexentr)
                lexical_entry_client_id = lexentr.client_id
                lexical_entry_object_id = lexentr.object_id
                if word:
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  fp_fields_dict["Word"][0],
                                  fp_fields_dict["Word"][1],
                                  None,
                                  client,
                                  word,
                                  filename=None,
                                  storage=storage)
                if transcription:
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  fp_fields_dict["Transcription"][0],
                                  fp_fields_dict["Transcription"][1],
                                  None,
                                  client,
                                  transcription,
                                  filename=None,
                                  storage=storage)
                if translation:
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  fp_fields_dict["Translation"][0],
                                  fp_fields_dict["Translation"][1],
                                  None,
                                  client,
                                  translation,
                                  filename=None,
                                  storage=storage)
            ids_mapping[wordid] = (lexical_entry_client_id, lexical_entry_object_id)
        ###################
        ## Paradigms
        ###################
        sqcursor = sqconn.cursor()
        sqcursor.execute("""select
                  id,
                  word,
                  Transcription,
                  translation,
                  regular_form
                  from dictionary
            where dictionary.is_a_regular_form=0""")
        for row in sqcursor:
            wordid = int(row[0])
            word = row[1]
            transcription = row[2]
            translation = row[3]
            regular_form = int(row[4])
            if update_flag:
                p_match_dict = defaultdict(list)
                for lex in p_lexes_with_text:
                    entity = lex[2]
                    entity_field_ids = (entity.field.client_id, entity.field.object_id)
                    if entity.content:
                        if entity.content == word:
                            if field_ids["Word of Paradigmatic forms"] == entity_field_ids:
                                p_match_dict[lex[1]].append(lex)
                        if entity.content == transcription:
                            if field_ids["Transcription of Paradigmatic forms"] == entity_field_ids:
                                p_match_dict[lex[1]].append(lex)
                        if entity.content == translation:
                            if field_ids["Translation of Paradigmatic forms"] == entity_field_ids:
                                p_match_dict[lex[1]].append(lex)
                p_match_dict = { k: v for k, v in p_match_dict.items()
                                 if len(v) >= 2 or len(v) == 1 and [x[1] for x in p_lexes_with_text].count(k) == 1}
                max_sim = None
                for le in p_match_dict:
                    if max_sim is None:
                        max_sim = le
                    else:
                        if len(p_match_dict[le]) >= len(p_match_dict[max_sim]):
                                max_sim = le
                if max_sim:
                    lexical_entry_client_id = max_sim.client_id
                    lexical_entry_object_id = max_sim.object_id
                    sim = [x[2].content for x in p_match_dict[max_sim]]
                    if not word in sim and word:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      sp_fields_dict["Word of Paradigmatic forms"][0],
                                      sp_fields_dict["Word of Paradigmatic forms"][1],
                                      None,
                                      client,
                                      word,
                                      filename=None,
                                      storage=storage)
                    if not transcription in sim and transcription:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      sp_fields_dict["Transcription of Paradigmatic forms"][0],
                                      sp_fields_dict["Transcription of Paradigmatic forms"][1],
                                      None,
                                      client,
                                      transcription,
                                      filename=None,
                                      storage=storage)
                    if not translation in sim and translation:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      sp_fields_dict["Translation of Paradigmatic forms"][0],
                                      sp_fields_dict["Translation of Paradigmatic forms"][1],
                                      None,
                                      client,
                                      translation,
                                      filename=None,
                                      storage=storage)
                else:
                    lexentr = LexicalEntry(client_id=client.id,
                                           parent_object_id=second_perspective_object_id,
                                           parent=second_perspective)
                    DBSession.add(lexentr)
                    lexical_entry_client_id = lexentr.client_id
                    lexical_entry_object_id = lexentr.object_id
                    if word:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      sp_fields_dict["Word of Paradigmatic forms"][0],
                                      sp_fields_dict["Word of Paradigmatic forms"][1],
                                      None,
                                      client,
                                      word,
                                      filename=None,
                                      storage=storage)
                    if transcription:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      sp_fields_dict["Transcription of Paradigmatic forms"][0],
                                      sp_fields_dict["Transcription of Paradigmatic forms"][1],
                                      None,
                                      client,
                                      transcription,
                                      filename=None,
                                      storage=storage)
                    if translation:
                        create_entity(lexical_entry_client_id,
                                      lexical_entry_object_id,
                                      sp_fields_dict["Translation of Paradigmatic forms"][0],
                                      sp_fields_dict["Translation of Paradigmatic forms"][1],
                                      None,
                                      client,
                                      translation,
                                      filename=None,
                                      storage=storage)
            else:
                lexentr = LexicalEntry(client_id=client.id,
                                       parent_object_id=second_perspective_object_id,
                                       parent=second_perspective)
                DBSession.add(lexentr)
                lexical_entry_client_id = lexentr.client_id
                lexical_entry_object_id = lexentr.object_id
                if word:
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  sp_fields_dict["Word of Paradigmatic forms"][0],
                                  sp_fields_dict["Word of Paradigmatic forms"][1],
                                  None,
                                  client,
                                  word,
                                  filename=None,
                                  storage=storage)
                if transcription:
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  sp_fields_dict["Transcription of Paradigmatic forms"][0],
                                  sp_fields_dict["Transcription of Paradigmatic forms"][1],
                                  None,
                                  client,
                                  transcription,
                                  filename=None,
                                  storage=storage)
                if translation:
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  sp_fields_dict["Translation of Paradigmatic forms"][0],
                                  sp_fields_dict["Translation of Paradigmatic forms"][1],
                                  None,
                                  client,
                                  translation,
                                  filename=None,
                                  storage=storage)
            ids_mapping[wordid] = lexical_entry_client_id, lexical_entry_object_id
            if regular_form in ids_mapping:
                if update_flag:
                    if max_sim:
                        sp_le_client_id, sp_le_object_id = ids_mapping[regular_form]
                        fp_le_ids = (lexical_entry_client_id, lexical_entry_object_id)
                        sp_le_ids = (sp_le_client_id, sp_le_object_id)
                        if not (sp_le_ids, fp_le_ids) in links:
                            create_entity(sp_le_client_id,
                                          sp_le_object_id,
                                          fp_fields_dict["Backref"][0],
                                          fp_fields_dict["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=lexical_entry_client_id,
                                          link_object_id=lexical_entry_object_id,
                                          storage=storage)
                            create_entity(lexical_entry_client_id,
                                          lexical_entry_object_id,
                                          sp_fields_dict["Backref"][0],
                                          sp_fields_dict["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=sp_le_client_id,
                                          link_object_id=sp_le_object_id,
                                          storage=storage)
                else:
                    sp_le_client_id, sp_le_object_id = ids_mapping[regular_form]
                    fp_le_ids = (lexical_entry_client_id, lexical_entry_object_id)
                    sp_le_ids = (sp_le_client_id, sp_le_object_id)
                    create_entity(sp_le_client_id,
                                  sp_le_object_id,
                                  fp_fields_dict["Backref"][0],
                                  fp_fields_dict["Backref"][1],
                                  None,
                                  client,
                                  filename=None,
                                  link_client_id=lexical_entry_client_id,
                                  link_object_id=lexical_entry_object_id,
                                  storage=storage)
                    create_entity(lexical_entry_client_id,
                                  lexical_entry_object_id,
                                  sp_fields_dict["Backref"][0],
                                  sp_fields_dict["Backref"][1],
                                  None,
                                  client,
                                  filename=None,
                                  link_client_id=sp_le_client_id,
                                  link_object_id=sp_le_object_id,
                                  storage=storage)
        # if req.get('is_translatable', None):
        #         field.is_translatable = bool(req['is_translatable'])
        DBSession.flush()
        """
        Sound and Markup
        """
        try:
            audio_ids = set()
            paradigm_audio_ids = set()
            sound_and_markup_word_cursor = sqconn.cursor()
            task_status.set(8, 60, "Uploading sounds and markups")
            sound_and_markup_word_cursor.execute("""select blobs.id,
                                                    blobs.secblob,
                                                    blobs.mainblob,
                                                    dict_blobs_description.name,
                                                    dictionary.id,
                                                    dict_blobs_description.type,
                                                    dict_blobs_description.description
                                                    from blobs, dict_blobs_description, dictionary
                                                    where dict_blobs_description.blobid=blobs.id
                                                    and dict_blobs_description.wordid=dictionary.id
                                                    and dictionary.is_a_regular_form=1;""")

            folder_name = "lexical_entry"
            upload_audio_with_markup(audio_ids,
                                     ids_mapping,
                                     fp_fields_dict,
                                     sound_and_markup_word_cursor,
                                     audio_hashes, markup_hashes,
                                     folder_name,
                                     client_id,
                                     True,
                                     client,
                                     storage)
            sound_and_markup_word_cursor = sqconn.cursor()
            sound_and_markup_word_cursor.execute("""select blobs.id,
                                                    blobs.secblob,
                                                    blobs.mainblob,
                                                    dict_blobs_description.name,
                                                    dictionary.id,
                                                    dict_blobs_description.type,
                                                    dict_blobs_description.description
                                                    from blobs, dict_blobs_description, dictionary
                                                    where dict_blobs_description.blobid=blobs.id
                                                    and dict_blobs_description.wordid=dictionary.id
                                                    and dictionary.is_a_regular_form=1;""")
            upload_audio(audio_ids,
                         ids_mapping,
                         fp_fields_dict,
                         sound_and_markup_word_cursor,
                         audio_hashes,
                         markup_hashes,
                         folder_name,
                         client_id,
                         True,
                         client,
                         storage,
                         locale_id=locale_id)
            task_status.set(8, 70, "Uploading sounds and markups")
            paradigm_sound_and_markup_cursor = sqconn.cursor()
            paradigm_sound_and_markup_cursor.execute("""select blobs.id,
                                                        blobs.secblob,
                                                        blobs.mainblob,
                                                        dict_blobs_description.name,
                                                        dictionary.id,
                                                        dict_blobs_description.type,
                                                        dict_blobs_description.description
                                                        from blobs, dict_blobs_description, dictionary
                                                        where dict_blobs_description.blobid=blobs.id
                                                        and dict_blobs_description.wordid=dictionary.id
                                                        and dictionary.is_a_regular_form=0;""")
            folder_name = "paradigm"
            upload_audio_with_markup(paradigm_audio_ids,
                                     ids_mapping,
                                     sp_fields_dict,
                                     paradigm_sound_and_markup_cursor,
                                     audio_hashes,
                                     markup_hashes,
                                     folder_name,
                                     client_id,
                                     True,
                                     client,
                                     storage,
                                     locale_id=locale_id)
            task_status.set(8, 80, "Uploading sounds and markups")
            paradigm_sound_and_markup_cursor = sqconn.cursor()
            paradigm_sound_and_markup_cursor.execute("""select blobs.id,
                                                        blobs.secblob,
                                                        blobs.mainblob,
                                                        dict_blobs_description.name,
                                                        dictionary.id,
                                                        dict_blobs_description.type,
                                                        dict_blobs_description.description
                                                        from blobs, dict_blobs_description, dictionary
                                                        where dict_blobs_description.blobid=blobs.id
                                                        and dict_blobs_description.wordid=dictionary.id
                                                        and dictionary.is_a_regular_form=0;""")
            upload_audio(paradigm_audio_ids,
                         ids_mapping,
                         sp_fields_dict,
                         paradigm_sound_and_markup_cursor,
                         audio_hashes,
                         markup_hashes,
                         folder_name,
                         client_id,
                         True,
                         client,
                         storage)
        except:
            task_status.set(None, -1, "Conversion failed: Uploading sounds and markups failed")
            return {}
        """
        Etimology_tag
        """
        task_status.set(9, 90, "Handling etymology")
        etymology_cursor = sqconn.cursor()
        etymology_cursor.execute("""select id, etimology_tag
                                    FROM dictionary
                                    WHERE etimology_tag NOT NULL
                                    and dictionary.is_a_regular_form=1; """)
        for cursor in etymology_cursor:
            id = int(cursor[0])
            client_id = ids_mapping[id][0]
            object_id = ids_mapping[id][1]
            item = {"entity_type": "Etymology", "tag": cursor[1],
                    "field_client_id": field_ids["Etymology"][0],
                    "field_object_id": field_ids["Etymology"][1],
                    "connections": [{"client_id": client_id, "object_id": object_id}]}
            create_group_entity(item, client, user)
        task_status.set(10, 100, "Finished", "")
        return {}

def convert_all(dictionary_client_id, dictionary_object_id, blob_client_id, blob_object_id,
                language_client_id, language_object_id, client_id, gist_client_id, gist_object_id,
                sqlalchemy_url, storage, locale_id, task_key, cache_kwargs):
    log = logging.getLogger(__name__)
    time.sleep(3)
    #from lingvodoc.cache.caching import CACHE
    from lingvodoc.cache.caching import initialize_cache
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)
    try:
        engine = create_engine(sqlalchemy_url)
        DBSession.configure(bind=engine)
        status = convert_db_new(dictionary_client_id, dictionary_object_id, blob_client_id, blob_object_id,
                                language_client_id, language_object_id, client_id, gist_client_id, gist_object_id,
                                storage, locale_id, task_status)
    except Exception as e:
        log.error("Converting failed")
        log.error(e.__traceback__)
        task_status.set(None, -1, "Conversion failed")
        raise
    log.debug(status)
    log.debug('Finished')
    return status

if __name__ == "__main__":
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t[%(name)s]\t%(message)s')