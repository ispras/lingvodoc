# coding: utf-8
import os
import sqlite3
import base64
import json
import hashlib
import random
import string
import time
import logging
import shutil
import transaction
from pathvalidate import sanitize_filename
from sqlalchemy import create_engine
from sqlalchemy import and_
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker
)

from pyramid.paster import (
    get_appsettings,
    )

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk
)

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
        user = DBSession.query(User).filter_by(id=client.user_id).first()
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
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
    client = DBSession.query(Client).filter_by(id=client.id).first() #variables['auth']
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")


    if perspective and not perspective.marked_for_deletion:
        try:
            link_gist = DBSession.query(TranslationGist)\
                .join(TranslationAtom)\
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2).one()
            link_ids = {'client_id':link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            return {'error': str("Something wrong with the base")}
        fields = DBSession.query(DictionaryPerspectiveToField)\
            .filter_by(parent=perspective)\
            .all()
        DBSession.flush()
        for field in fields: ## ?
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



"""
from sqlalchemy import and_
import os
import shutil
import swiftclient.client as swiftclient
def openstack_upload(settings, file, file_name, content_type,  container_name):
    #storage = settings['storage']
    #authurl = storage['authurl']
    #user = storage['user']
    #key = storage['key']
    #auth_version = storage['auth_version']
    #tenant_name = storage['tenant_name']
    authurl = "http://10.10.10.121:5000/v2.0"
    store = "http://adelaide.intra.ispras.ru/horizon/project/containers"
    user = "admin"
    key = "tester"
    auth_version = "2.0"
    tenant_name = "admin"
    conn = swiftclient.Connection(authurl=authurl, user=user, key=key,  auth_version=auth_version,
                                  tenant_name=tenant_name)
    #storageurl = conn.get_auth()[0]
    conn.put_container(container_name)
    obje = conn.put_object(container_name, file_name,
                    contents = file,
                    content_type = content_type)
    #obje = conn.get_object(container_name, file_name)
    return str(obje)
"""


def object_file_path(obj, base_path, folder_name, filename, create_dir=False):
    filename = sanitize_filename(filename)
    storage_dir = os.path.join(base_path, obj.__tablename__, folder_name, str(obj.client_id), str(obj.object_id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)
    return storage_path, filename


def create_object(content, obj, data_type, filename, folder_name, storage, json_input=True):
    import errno
    # here will be object storage write as an option. Fallback (default) is filesystem write
    #settings = request.registry.settings
    #storage = "openstack" #settings['storage']
    #if storage == 'openstack':
    """
    if json_input:
        content = base64.urlsafe_b64decode(content)

    # TODO: openstack objects correct naming
    #filename = str(obj.data_type) + '/' + str(obj.client_id) + '_' + str(obj.object_id)
    #real_location = openstack_upload(content, filename, obj.data_type, 'test')
    filename = str(data_type) + '/' + str(obj.client_id) + '_' + str(obj.object_id)
    real_location = openstack_upload(content,obj, filename, data_type, 'test')
    """
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
                  link_client_id=None, link_object_id=None, folder_name=None, up_lvl=None, locale_id=2, storage=None):  # tested
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
            new_meta = old_meta #json.loads(old_meta)
            if new_meta.get('hash'):
                need_hash = False
        if need_hash:
            hash = hashlib.sha224(base64.urlsafe_b64decode(content)).hexdigest()
            hash_dict = {'hash': hash}
            if old_meta:
                new_meta = old_meta #json.loads(old_meta)
                new_meta.update(hash_dict)
            else:
                new_meta = hash_dict
            entity.additional_metadata = new_meta #json.dumps(new_meta)
        old_meta = entity.additional_metadata
        if data_type == "markup":
            data_type_dict = {"data_type": "praat markup"}
            if old_meta:
                new_meta = old_meta #json.loads(old_meta)
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta #json.dumps(new_meta)
    elif data_type == 'link':
        try:
            pass
            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content


    DBSession.add(entity)
    #log.debug(filename)
    return (entity.client_id, entity.object_id)



def upload_audio_with_markup(sound_ids, ids_map, fields_dict, sound_and_markup_cursor, audio_hashes, markup_hashes, folder_name,
                        user_id, is_a_regular_form, client, storage):
    log = logging.getLogger(__name__)
    sound_field = "Sound"
    markup_field = "Markup"
    if "Sounds of Paradigmatic forms" in fields_dict:
        sound_field = "Sounds of Paradigmatic forms"
    if "Paradigm markup" in fields_dict:
        markup_field = "Paradigm markup"

    markup__without_audio_sequence = []
    audio_sequence = []
    for cursor in sound_and_markup_cursor:
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
        if not audio or not markup:
            continue
        sound_ids.add(word_id)
        audio_hash = hashlib.sha224(audio).hexdigest()
        markup_hash = hashlib.sha224(markup).hexdigest()
        if audio_hash not in audio_hashes:
            ###filename = common_name + ".wav"
            if common_name:
                fname = os.path.splitext(common_name)[0]
                fname = fname.replace(".", "_")
                filename = "%s.wav" % fname
            else:
                filename = 'noname.noext'
            audio_hashes.add(audio_hash)

            '''
            if not is_a_regular_form:
                audio_element['additional_metadata'] = json.dumps({"hash": audio_hash,
                                                                   "client_id": client_id,
                                                                   "row_id": cursor[4]})
            '''
            audio_sequence.append((ids_map[int(word_id)][0], ids_map[int(word_id)][1], fields_dict[sound_field][0], fields_dict[sound_field][1],
                                    None, client, filename, audio))
            lvl = create_entity(ids_map[int(word_id)][0], ids_map[int(word_id)][1], fields_dict[sound_field][0], fields_dict[sound_field][1],
                    None, client, filename=filename, content=base64.urlsafe_b64encode(audio).decode(), folder_name=folder_name, storage=storage)
            #markup_hashes.add(markup_hash)
        if markup and markup_hash not in markup_hashes:
            if lvl:
                if common_name:
                    fname = os.path.splitext(common_name)[0]
                    fname = fname.replace(".", "_")
                    filename = "%s.TextGrid" % fname
                else:
                    filename = 'noname.noext'

                markup_hashes.add(markup_hash)
                create_entity(ids_map[int(word_id)][0], ids_map[int(word_id)][1], fields_dict[markup_field][0], fields_dict[markup_field][1],
                        None, client, filename=filename, content=base64.urlsafe_b64encode(markup).decode(), folder_name=folder_name, up_lvl=lvl, storage=storage)
                markup__without_audio_sequence.append((audio_hash, markup_hash))

            if len(markup__without_audio_sequence) > 50:
                DBSession.flush()
        if len(audio_sequence) > 50:
            DBSession.flush()
            audio_sequence = []
            if len(markup__without_audio_sequence) > 50:
                DBSession.flush()
    if len(audio_sequence) != 0:
        DBSession.flush()
        audio_sequence = []
    if len(markup__without_audio_sequence) != 0:
        DBSession.flush()

def upload_audio(sound_ids, ids_map, fields_dict, sound_and_markup_cursor, audio_hashes, markup_hashes, folder_name,
                        user_id, is_a_regular_form, client, storage):
    log = logging.getLogger(__name__)
    sound_field = "Sound"
    markup_field = "Markup"
    if "Sounds of Paradigmatic forms" in fields_dict:
        sound_field = "Sounds of Paradigmatic forms"
    if "Paradigm markup" in fields_dict:
        markup_field = "Paradigm markup"

    markup__without_audio_sequence = []
    audio_sequence = []
    for cursor in sound_and_markup_cursor:
        blob_id = cursor[0]
        description_type = int(cursor[5])
        if description_type == 1:
            audio = cursor[2]
            markup = cursor[1]
        common_name = str(cursor[3])
        word_id = cursor[4]
        if word_id in sound_ids:
            continue
        sound_ids.add(word_id)
        audio_hash = hashlib.sha224(audio).hexdigest()
        if audio_hash not in audio_hashes:
            ###filename = common_name + ".wav"
            if common_name:
                fname = os.path.splitext(common_name)[0]
                fname = fname.replace(".", "_")
                filename = "%s.wav" % fname
            else:
                filename = 'noname.noext'
            audio_hashes.add(audio_hash)
            '''
            if not is_a_regular_form:
                audio_element['additional_metadata'] = json.dumps({"hash": audio_hash,
                                                                   "client_id": client_id,
                                                                   "row_id": cursor[4]})
            '''
            audio_sequence.append((ids_map[int(word_id)][0], ids_map[int(word_id)][1], fields_dict[sound_field][0], fields_dict[sound_field][1],
                                    None, client, filename, audio))
            lvl = create_entity(ids_map[int(word_id)][0], ids_map[int(word_id)][1], fields_dict[sound_field][0], fields_dict[sound_field][1],
                    None, client, filename=filename, content=base64.urlsafe_b64encode(audio).decode(), folder_name=folder_name, storage=storage)
            if len(markup__without_audio_sequence) > 50:
                DBSession.flush()
        if len(audio_sequence) > 50:
            DBSession.flush()
            audio_sequence = []
            if len(markup__without_audio_sequence) > 50:
                DBSession.flush()
    if len(audio_sequence) != 0:
        DBSession.flush()
        audio_sequence = []
    if len(markup__without_audio_sequence) != 0:
        DBSession.flush()



def translation_service_search(searchstring):
    translationatom = DBSession.query(TranslationAtom)\
        .join(TranslationGist).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service')\
        .one()
    response = translationgist_contents(translationatom.parent)
    return response


def create_gist(client_id, type):
    gist = TranslationGist(client_id=client_id, type=type)
    #DBSession.add(gist)
    #DBSession.flush()
    return gist


def get_translation(translation_gist_client_id, translation_gist_object_id, locale_id):
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    translation = DBSession.query(TranslationAtom).filter_by(parent_client_id=translation_gist_client_id,
                                                             parent_object_id=translation_gist_object_id,
                                                             locale_id=locale_id).first()
    DBSession.flush()
    return translation.content


def convert_db_new(manager, sqconn, language_client_id, language_object_id, user_id, gist_client_id, gist_object_id, storage,
                   locale_id=2):
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    field_ids = {}
    with manager:
        client = DBSession.query(Client).filter_by(id=user_id).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           user_id)
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            log.debug("ERROR")

        fields = DBSession.query(Field).filter_by().all()
        DBSession.flush()
        for field_obj in fields:
            try:
                field_client_id = int(field_obj.client_id)
                field_object_id = int(field_obj.object_id)
                name = get_translation(field_obj.translation_gist_client_id, field_obj.translation_gist_object_id, locale_id)
                field_ids[name] = (field_client_id, field_object_id)
            except:
                pass
        dict_attributes = get_dict_attributes(sqconn)

        # """
        translationgist = TranslationGist(client_id=user_id, type="Dictionary")
        DBSession.add(translationgist)
        DBSession.flush()
        gist_client_id = translationgist.client_id
        gist_object_id = translationgist.object_id
        # """
        parent_client_id = gist_client_id
        parent_object_id = gist_object_id

        parent = DBSession.query(TranslationGist).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent.marked_for_deletion:

            # """
            translationatom = TranslationAtom(client_id=client.id,
                                              parent=parent,
                                              locale_id=locale_id,
                                              content=dict_attributes["dictionary_name"])
            DBSession.add(translationatom)
            DBSession.flush()
            atom_client_id = translationatom.client_id
            atom_object_id = translationatom.object_id

            log.debug(dict_attributes["dictionary_name"])
            language_client_id = atom_client_id
            language_object_id = atom_object_id
            # """
            lang_parent = DBSession.query(Language).filter_by(client_id=language_client_id, object_id=language_object_id).first()

            resp = translation_service_search("WiP")
            state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
            dictionary = Dictionary(client_id=user_id,
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
                                  subject_object_id=dictionary.object_id, subject_client_id=dictionary.client_id)
                if user not in new_group.users:
                    new_group.users.append(user)
                DBSession.add(new_group)
                DBSession.flush()
        """
        # FIRST PERSPECTIVE
        """
        translationgist = TranslationGist(client_id=user_id, type="Dictionary")

        DBSession.add(translationgist)
        #####DBSession.flush()

        gist_client_id = translationgist.client_id
        gist_object_id = translationgist.object_id
        parent_client_id = gist_client_id
        parent_object_id = gist_object_id
        locale_id = 2
        parent = DBSession.query(TranslationGist).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent.marked_for_deletion:
            persp_translationatom = TranslationAtom(client_id=client.id,
                                              parent=parent,
                                              locale_id=locale_id,
                                              content="Лексические входы")
            DBSession.add(persp_translationatom)
            DBSession.flush()
        persp_translation_gist_client_id = gist_client_id
        persp_translation_gist_object_id = gist_object_id


        parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
        perspective = DictionaryPerspective(client_id=client.id, ###
                                            state_translation_gist_object_id=state_translation_gist_object_id,
                                            state_translation_gist_client_id=state_translation_gist_client_id,
                                            parent=parent,
                                            # import_source=req.get('import_source'),
                                            # import_hash=req.get('import_hash'),
                                            # additional_metadata=additional_metadata,
                                            translation_gist_client_id=persp_translation_gist_client_id,
                                            translation_gist_object_id=persp_translation_gist_object_id
                                            )
        # if is_template is not None:
        #     perspective.is_template = is_template
        DBSession.add(perspective)
        owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
        owner = owner_client.user
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
            new_group = Group(parent=base,
                              subject_object_id=perspective.object_id, subject_client_id=perspective.client_id)
            if user not in new_group.users:
                new_group.users.append(user)
            if owner not in new_group.users:
                new_group.users.append(owner)
            DBSession.add(new_group)
            DBSession.flush()
        first_perspective_client_id = perspective.client_id
        first_perspective_object_id = perspective.object_id

        """
        # SECOND PERSPECTIVE
        """
        translationgist = TranslationGist(client_id=user_id, type="Dictionary")

        DBSession.add(translationgist)
        gist_client_id = translationgist.client_id
        gist_object_id = translationgist.object_id
        parent_client_id = gist_client_id
        parent_object_id = gist_object_id
        parent = DBSession.query(TranslationGist).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent.marked_for_deletion:
            persp_translationatom = TranslationAtom(client_id=client.id,
                                              parent=parent,
                                              locale_id=locale_id,
                                              content="Парадигмы")
            DBSession.add(persp_translationatom)
            DBSession.flush()
        persp_translation_gist_client_id = gist_client_id
        persp_translation_gist_object_id = gist_object_id
        parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        if not parent:
            return {'error': str("No such dictionary in the system")}
        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
        perspective = DictionaryPerspective(client_id=client.id, ### variables['auth']
                                            state_translation_gist_object_id=state_translation_gist_object_id,
                                            state_translation_gist_client_id=state_translation_gist_client_id,
                                            parent=parent,
                                            # import_source=req.get('import_source'),
                                            # import_hash=req.get('import_hash'),
                                            # additional_metadata=additional_metadata,
                                            translation_gist_client_id=persp_translation_gist_client_id,
                                            translation_gist_object_id=persp_translation_gist_object_id
                                            )
        # if is_template is not None:
        #     perspective.is_template = is_template
        DBSession.add(perspective)
        owner_client = DBSession.query(Client).filter_by(id=parent.client_id).first()
        owner = owner_client.user
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
            new_group = Group(parent=base,
                              subject_object_id=perspective.object_id, subject_client_id=perspective.client_id)
            if user not in new_group.users:
                new_group.users.append(user)
            if owner not in new_group.users:
                new_group.users.append(owner)
            DBSession.add(new_group)
        second_perspective_client_id = perspective.client_id
        second_perspective_object_id = perspective.object_id
        get_fp_ids = sqconn.cursor()
        get_fp_ids.execute("select id from dictionary where is_a_regular_form=1")
        count_cursor = sqconn.cursor()
        count_cursor.execute("select count(*) from dictionary where is_a_regular_form=1")
        words_count = count_cursor.fetchone()[0]
        count_cursor2 = sqconn.cursor()
        count_cursor2.execute("select count(*) from dictionary where is_a_regular_form=0")
        words_count2 = count_cursor2.fetchone()[0]
        ids_dict = dict()
        for i in range(words_count):
            perspective = DBSession.query(DictionaryPerspective).\
                filter_by(client_id=first_perspective_client_id, object_id = first_perspective_object_id).first()
            if not perspective:
                return {'error': str("No such perspective in the system")}
            lexentr = LexicalEntry(object_id=DBSession.query(LexicalEntry).filter_by(client_id=client.id).count() + 1, client_id=client.id,
                                   parent_object_id=first_perspective_object_id, parent=perspective)
            DBSession.add(lexentr)
            lexical_entry_client_id = lexentr.client_id
            lexical_entry_object_id = lexentr.object_id
            ids_dict[i] = (lexical_entry_client_id, lexical_entry_object_id)
        DBSession.flush()
        ids_dict2 = dict()
        for i in range(words_count2):
            perspective = DBSession.query(DictionaryPerspective).\
                filter_by(client_id=first_perspective_client_id, object_id = second_perspective_object_id).first()
            if not perspective:
                return {'error': str("No such perspective in the system")}
            lexentr = LexicalEntry(object_id=DBSession.query(LexicalEntry).filter_by(client_id=client.id).count() + 1, client_id=client.id,
                                   parent_object_id=second_perspective_object_id, parent=perspective)
            DBSession.add(lexentr)
            lexical_entry_client_id = lexentr.client_id
            lexical_entry_object_id = lexentr.object_id
            ids_dict2[i] = (lexical_entry_client_id, lexical_entry_object_id)
        DBSession.flush()
        get_sp_ids = sqconn.cursor()
        get_sp_ids.execute("select id from dictionary where is_a_regular_form=0")
        ids_mapping2 = dict()
        i = 0
        sp_le_id_dict = {}
        for id_cursor in get_sp_ids:
            id = id_cursor[0]
            sp_le_id_dict[id] = i
            client_id = ids_dict2[i][0]
            object_id = ids_dict2[i][1]
            ids_mapping2[int(id)] = (client_id, object_id)
            i += 1
        get_fp_ids = sqconn.cursor()
        get_fp_ids.execute("select id from dictionary where is_a_regular_form=1")
        ids_mapping = dict()
        i = 0
        fp_le_id_dict = {}
        for id_cursor in get_fp_ids:
            id = id_cursor[0]
            fp_le_id_dict[id] = i
            client_id = ids_dict[i][0]
            object_id = ids_dict[i][1]
            ids_mapping[id] = (client_id, object_id)
            i += 1
        fp_fields_dict = {}
        """
        # FIRST PERSPECTIVE FIELDS CREATION
        """
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
        sp_field_names = ("Word of Paradigmatic forms", "Transcription of Paradigmatic forms", "Translation of Paradigmatic forms", "Sounds of Paradigmatic forms", "Backref")
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
                       "client_id": field_ids["Paradigm markup"][0],
                       "object_id": field_ids["Paradigm markup"][1]
                    }
                    ]
                    }
                )
            else:
                fields_list.append({"client_id": field_ids[fieldname][0], "object_id": field_ids[fieldname][1]})
            sp_fields_dict[fieldname] = (field_ids[fieldname][0], field_ids[fieldname][1])
        sp_fields_dict["Paradigm markup"] = (field_ids["Paradigm markup"][0], field_ids["Paradigm markup"][1])
        update_perspective_fields(fields_list, second_perspective_client_id, second_perspective_object_id, client)
        columns = ("word", "Transcription", "translation")
        # First Perspective entity
        sqcursor = sqconn.cursor()
        for column in columns:
            sqcursor.execute("select id,%s from dictionary where is_a_regular_form=1" % column)
            for row in sqcursor:
                row_id = int(row[0])
                content = row[1]
                name = None
                if column == "word":
                    name = "Word"
                if column == "Transcription":
                    name = "Transcription"
                if column == "translation":
                    name = "Translation"
                create_entity(ids_dict[fp_le_id_dict[row_id]][0], ids_dict[fp_le_id_dict[row_id]][1], fp_fields_dict[name][0], fp_fields_dict[name][1],
                    None, client, content, filename=None, storage=storage)
        # Second Perspective entity
        sqcursor = sqconn.cursor()
        for column in columns:
            sqcursor.execute("select id,%s from dictionary where is_a_regular_form=0" % column)
            for row in sqcursor:
                row_id = int(row[0])
                content = row[1]
                name = None
                if column == "word":
                    name = "Word of Paradigmatic forms"
                if column == "Transcription":
                    name = "Transcription of Paradigmatic forms"
                if column == "translation":
                    name = "Translation of Paradigmatic forms"
                create_entity(ids_dict2[sp_le_id_dict[row_id]][0], ids_dict2[sp_le_id_dict[row_id]][1], sp_fields_dict[name][0], sp_fields_dict[name][1],
                    None, client, content, filename=None, storage=storage)
        sqcursor = sqconn.cursor()
        sqcursor.execute("select id,regular_form from dictionary where is_a_regular_form=0")
        for le_cursor in sqcursor:
            fp_id = int(le_cursor[1])
            sp_id = int(le_cursor[0])
            if fp_id in ids_mapping:
                create_entity(ids_dict[fp_le_id_dict[fp_id]][0], ids_dict[fp_le_id_dict[fp_id]][1], fp_fields_dict["Backref"][0], fp_fields_dict["Backref"][1],
                    None, client, filename=None, link_client_id=ids_dict2[sp_le_id_dict[sp_id]][0], link_object_id=ids_dict2[sp_le_id_dict[sp_id]][1], storage=storage)
                create_entity(ids_dict2[sp_le_id_dict[sp_id]][0], ids_dict2[sp_le_id_dict[sp_id]][1], sp_fields_dict["Backref"][0], sp_fields_dict["Backref"][1],
                    None, client, filename=None, link_client_id=ids_dict[fp_le_id_dict[fp_id]][0], link_object_id=ids_dict[fp_le_id_dict[fp_id]][1], storage=storage)
        #DBSession.flush()
        # if req.get('is_translatable', None):
        #         field.is_translatable = bool(req['is_translatable'])
        audio_hashes = set()
        markup_hashes = set()
        DBSession.flush()
        """
        perspective_search = server_url + 'dictionary/%s/%s/perspective/%s/%s/all' % (dictionary['client_id'],
                                                                                            dictionary['object_id'],
                                                                                            perspective['client_id'],
                                                                                            perspective['object_id'])
        search_url = server_url + 'meta_search' \
                                  '?perspective_client_id=%d&perspective_object_id=%d' % (perspective['client_id'],
                                                                                       perspective['object_id'])

        status = session.get(perspective_search)
        lexes = json.loads(status.text)['lexical_entries']
        sound_types = ['Sound', 'Paradigm sound']
        markup_types = ['Praat markup', "Paradigm Praat markup"]
        for lex in lexes:
            for entry in lex['contains']:
                meta = entry.get('additional_metadata')
                if meta:
                    hsh = meta.get('hash')
                    if hsh:
                        if entry['entity_type'] in sound_types:
                            audio_hashes.add(hsh)
                if entry.get('contains'):
                    for ent in entry['contains']:
                        meta = entry.get('additional_metadata')
                        if meta:
                            hsh = meta.get('hash')
                            if hsh:
                                if ent['entity_type'] in markup_types:
                                    markup_hashes.add(hsh)
        """
        """
        Sound and Markup
        """
        audio_ids = set()
        paradigm_audio_ids = set()
        sound_and_markup_word_cursor = sqconn.cursor()
        sound_and_markup_word_cursor.execute("""select blobs.id,
                                                blobs.secblob,
                                                blobs.mainblob,
                                                dict_blobs_description.name,
                                                dictionary.id,
                                                dict_blobs_description.type
                                                from blobs, dict_blobs_description, dictionary
                                                where dict_blobs_description.blobid=blobs.id
                                                and dict_blobs_description.wordid=dictionary.id
                                                and dictionary.is_a_regular_form=1;""")

        folder_name = "praat_markup"
        upload_audio_with_markup(audio_ids, ids_mapping, fp_fields_dict, sound_and_markup_word_cursor, audio_hashes, markup_hashes, folder_name,
                            user_id, True, client, storage)
        upload_audio(audio_ids, ids_mapping, fp_fields_dict, sound_and_markup_word_cursor, audio_hashes, markup_hashes, folder_name,
                            user_id, True, client, storage)
        paradigm_sound_and_markup_cursor = sqconn.cursor()
        paradigm_sound_and_markup_cursor.execute("""select blobs.id,
                                                    blobs.secblob,
                                                    blobs.mainblob,
                                                    dict_blobs_description.name,
                                                    dictionary.id,
                                                    dict_blobs_description.type
                                                    from blobs, dict_blobs_description, dictionary
                                                    where dict_blobs_description.blobid=blobs.id
                                                    and dict_blobs_description.wordid=dictionary.id
                                                    and dictionary.is_a_regular_form=0;""")


        folder_name = "paradigm_praat_markup"
        upload_audio_with_markup(paradigm_audio_ids, ids_mapping2, sp_fields_dict, paradigm_sound_and_markup_cursor, audio_hashes, markup_hashes, folder_name,
                            user_id, True, client, storage)
        upload_audio(paradigm_audio_ids, ids_mapping2, sp_fields_dict, paradigm_sound_and_markup_cursor, audio_hashes, markup_hashes, folder_name,
                            user_id, True, client, storage)
        """
        Etimology_tag
        """

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
            # status = session.post(connect_url, json=item)
            # log.debug(status.text)

        """
        suggestions_url = server_url + 'merge/suggestions'

        suggestions_params = {'threshold': 1.0,
                              'levenstein': 0,
                              'client_id': perspective['client_id'],
                              'object_id': perspective['object_id']}
        # status = session.post(suggestions_url, json=suggestions_params)

        for entry in json.loads(status.text):
            if entry['confidence'] >= 1.0:
                first_entry = entry['suggestion'][0]
                second_entry = entry['suggestion'][1]
                lex_move_url = server_url + 'lexical_entry/%d/%d/move' % (second_entry['lexical_entry_client_id'],
                                                                           second_entry['lexical_entry_object_id'])
                move_params = {'client_id': first_entry['lexical_entry_client_id'],
                               'object_id': first_entry['lexical_entry_object_id'],
                               'real_delete': True}
                # status = session.patch(lex_move_url, json=move_params)

            else:
                break
        """
        dictionary = {}
        return dictionary


def convert_all(blob_client_id, blob_object_id, language_client_id, language_object_id, user_id, gist_client_id, gist_object_id, sqlalchemy_url, storage):
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    blob = DBSession.query(UserBlobs).filter_by(client_id=blob_client_id, object_id=blob_object_id).first()
    DBSession.flush()
    filename = blob.real_storage_path
    log.debug("user_id: %s" % user_id)
    log.debug("Starting convert_one")
    log.debug("Creating session")
    sqconn = sqlite3.connect(filename)
    log.debug("Connected to sqlite3 database")
    try:
        status = convert_db_new(transaction.manager, sqconn, language_client_id, language_object_id, user_id, gist_client_id, gist_object_id, storage)
    except Exception as e:
        log.error("Converting failed")
        log.error(e.__traceback__)
        raise
    log.debug(status)
    return status


if __name__ == "__main__":
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    logging.basicConfig(format='%(asctime)s\t%(levelname)s\t[%(name)s]\t%(message)s')