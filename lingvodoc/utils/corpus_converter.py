# -*- coding: utf-8 -*-
import os
import re
import base64
import hashlib
import math
import shutil
import transaction
import tempfile
import urllib
import warnings
import logging
import requests
import pprint
from collections import defaultdict, OrderedDict
from pathvalidate import sanitize_filename
from urllib import request
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_, create_engine, or_, tuple_
from lingvodoc.models import (
    Client,
    DBSession,
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
    Group

)
from pyramid.httpexceptions import HTTPError
from lingvodoc.cache.caching import TaskStatus
from lingvodoc.scripts import elan_parser
from lingvodoc.models import (
    user_to_group_association,

)
from lingvodoc.utils.elan_functions import tgt_to_eaf
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary)
from lingvodoc.utils.search import get_id_to_field_dict

EAF_TIERS = {
    "literary translation": "Translation of Paradigmatic forms",
    "text": "Transcription of Paradigmatic forms",
    "Word of Paradigmatic forms": "Word of Paradigmatic forms",
    "word": "Word",
    "transcription": "Transcription",
    "translation": "Translation"
}


log = logging.getLogger(__name__)


with warnings.catch_warnings():
    warnings.filterwarnings('error')
    try:
        from pydub import AudioSegment
    except Warning as e:
        log.debug("If you want to use Elan converter under Windows,\
         keep in mind, that the result dictionary won't contain sounds")


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


def update_perspective_fields(req,
                              perspective_client_id,
                              perspective_object_id,
                              client):
    response = dict()
    # perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=perspective_client_id,
    #                                                                object_id=perspective_object_id).first()
    perspective = CACHE.get(objects =
        {
            DictionaryPerspective : ((perspective_client_id,  perspective_object_id), )
        },
    DBSession=DBSession)

    client = DBSession.query(Client).filter_by(id=client.id).first() #variables['auth']
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
    if perspective and not perspective.marked_for_deletion:
        try:
            link_gist = DBSession.query(TranslationGist)\
                .join(TranslationAtom)\
                .filter(TranslationGist.type == 'Service',
                        TranslationAtom.content == 'Link',
                        TranslationAtom.locale_id == 2)\
                .order_by(TranslationGist.client_id)\
                .first()
            link_ids = {'client_id':link_gist.client_id, 'object_id': link_gist.object_id}
        except NoResultFound:
            return {'error': str("Something wrong with the base")}
        fields = DBSession.query(DictionaryPerspectiveToField)\
            .filter_by(parent=perspective)\
            .all()
        DBSession.flush()
        #for field in fields: ## ?
        #    DBSession.delete(field)
        if not int(len(fields)):
            position = 1  # TODO: postition fix
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


def create_object(content, obj, data_type, filename, folder_name, storage, json_input=True, byte_content=False):
    import errno
    storage_path, filename = object_file_path(obj, storage["path"], folder_name, filename, True)
    directory = os.path.dirname(storage_path)  # TODO: find out, why object_file_path were not creating dir
    try:
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    with open(storage_path, 'wb+') as f:
        if byte_content:
            f.write(content)
        elif json_input:
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

def create_entity(
    le_client_id,
    le_object_id,
    field_client_id,
    field_object_id,
    data_type,
    client_id,
    content = None,
    filename = None,
    self_client_id = None,
    self_object_id = None,
    link_client_id = None,
    link_object_id = None,
    folder_name = None,
    storage = None,
    byte_content = False):

    entity = Entity(client_id=client_id,
                    field_client_id=field_client_id,
                    field_object_id=field_object_id,
                    parent_client_id=le_client_id,
                    parent_object_id=le_object_id)

    if self_client_id and self_object_id:
        entity.self_client_id = self_client_id
        entity.self_object_id = self_object_id

    hash = None
    real_location = None
    url = None
    if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
        ##entity.data_type = data_type
        real_location, url = create_object(content, entity, data_type, filename, folder_name, storage, byte_content=byte_content)
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
        if data_type == "sound":
            data_type_dict = {"data_type": "sound"}
            if old_meta:
                new_meta = old_meta #json.loads(old_meta)
                new_meta.update(data_type_dict)
            else:
                new_meta = data_type_dict
            entity.additional_metadata = new_meta #json.dumps(new_meta)
    elif data_type == 'link':
        try:
            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content
    entity.publishingentity.accepted = True

    # DBSession.add(entity)
    CACHE.set(objects = [entity, ], DBSession=DBSession)

    # means that the function was called from CopyField and so need to be sure that sound has been copied before copying markups
    if byte_content:
        DBSession.flush()
    return (entity.client_id, entity.object_id)


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


def convert_five_tiers(dictionary_id,
                client_id,
                sqlalchemy_url,
                storage,
                markup_id,
                locale_id,
                task_status,
                cache_kwargs,
                translation_gist_id,
                language_id,
                sound_url,
                no_sound_flag):

    task_status.set(1, 1, "Preparing")

    field_ids = {}
    with transaction.manager:

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

        # markup_entity = DBSession.query(Entity).filter_by(client_id=markup_id[0], object_id=markup_id[1]).first()
        markup_entity = CACHE.get(objects =
            {
                Entity : (markup_id, )
            },
        DBSession=DBSession)

        if not markup_entity:
            raise KeyError("No such file")

        if dictionary_id:
            dictionary_client_id, dictionary_object_id = dictionary_id
        else:
            gist_client_id, gist_object_id = translation_gist_id
            language_client_id, language_object_id = language_id
            #dbdictionary_obj = create_dbdictionary(id=[client_id, None],
            #                                       parent_id=parent_id,
            #                                       translation_gist_id=dictionary_translation_gist_id,
            #                                       add_group=True)
            #DBSession.add(dbdictionary_obj)
            #DBSession.flush()
            lang_parent = DBSession.query(Language).filter_by(client_id=language_client_id,
                                                              object_id=language_object_id).first()

            # Getting license from the markup's dictionary.

            license = (

                DBSession
                    .query(Dictionary.additional_metadata['license'].astext)
                    .filter(
                        LexicalEntry.client_id == markup_entity.parent_client_id,
                        LexicalEntry.object_id == markup_entity.parent_object_id,
                        DictionaryPerspective.client_id == LexicalEntry.parent_client_id,
                        DictionaryPerspective.object_id == LexicalEntry.parent_object_id,
                        Dictionary.client_id == DictionaryPerspective.parent_client_id,
                        Dictionary.object_id == DictionaryPerspective.parent_object_id)
                    .scalar())

            resp = translation_service_search("WiP")
            state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']

            dictionary = (

                Dictionary(
                    client_id = client_id,
                    state_translation_gist_object_id = state_translation_gist_object_id,
                    state_translation_gist_client_id = state_translation_gist_client_id,
                    parent = lang_parent,
                    translation_gist_client_id = gist_client_id,
                    translation_gist_object_id = gist_object_id,
                    additional_metadata = {
                        'license': license or 'proprietary'}))

            DBSession.add(dictionary)
            DBSession.flush()

            dictionary_id = dictionary.id

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
            #dictionary_client_id, dictionary_object_id = dbdictionary_obj.client_id, dbdictionary_obj.object_id

        no_sound = True

        if not no_sound_flag:

            # sound_entity = DBSession.query(Entity).filter_by(client_id=markup_entity.self_client_id, object_id=markup_entity.self_object_id).first()
            sound_entity = CACHE.get(objects =
                {
                    Entity : ((markup_entity.self_client_id, markup_entity.self_object_id), )
                },
            DBSession=DBSession)

            sound_url = None
            if sound_entity:
                sound_url = sound_entity.content
            if sound_url:
                no_sound = False

        with warnings.catch_warnings():
            warnings.filterwarnings('error')
            try:
                from pydub import AudioSegment
            except Warning as e:
                no_sound = True
        if not no_sound:
            sound_format = "wav"
            if sound_url.endswith(".mp3"):
                sound_format = "mp3"
            if sound_url.endswith(".flac"):
                sound_format = "flac"
            with tempfile.NamedTemporaryFile() as temp:
                try:
                    sound_file = request.urlopen(urllib.parse.quote(sound_url, safe='/:'))
                except HTTPError as e:
                    return {'error': str(e.read().decode("utf8", 'ignore'))}
                with open(temp.name,'wb') as output:
                    output.write(sound_file.read())
                if sound_format == "wav":
                    full_audio = AudioSegment.from_wav(temp.name)
                elif sound_format == "mp3":
                    full_audio = AudioSegment.from_mp3(temp.name)
                elif sound_format == "flac":
                    full_audio = AudioSegment.from_file(temp.name, "flac")
                temp.flush()





        origin_perspective = markup_entity.parent.parent
        origin_client_id = origin_perspective.client_id
        origin_object_id = origin_perspective.object_id


        origin_metadata= {"origin_id": (origin_client_id, origin_object_id)}

        # parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id,
        #                                                object_id=dictionary_object_id).first()
        parent = CACHE.get(objects =
            {
                Dictionary : ((dictionary_client_id, dictionary_object_id), )
            },
        DBSession=DBSession)

        if not parent:
            return {'error': str("No such dictionary in the system")}
        if not check_dictionary_perm(user.id, dictionary_client_id, dictionary_object_id):
            task_status.set(None, -1, "Wrong permissions: dictionary")
            return
        first_perspective = None
        second_perspective = None
        for perspective in DBSession.query(DictionaryPerspective).filter_by(parent=parent, marked_for_deletion=False):
            structure = set()
            fields = DBSession.query(DictionaryPerspectiveToField)\
                        .filter_by(parent=perspective)\
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
        p_lexes = []
        if second_perspective:
            p_lexes = DBSession.query(DictionaryPerspective, LexicalEntry, Entity)\
                .filter(and_(DictionaryPerspective.object_id==second_perspective.object_id,
                        DictionaryPerspective.client_id==second_perspective.client_id))\
                .join(LexicalEntry, and_( LexicalEntry.parent_object_id==DictionaryPerspective.object_id,
                                          LexicalEntry.parent_client_id==DictionaryPerspective.client_id))\
                .join(Entity, and_(LexicalEntry.object_id==Entity.parent_object_id,
                                   LexicalEntry.client_id==Entity.parent_client_id))

        hashes = [x[2].additional_metadata["hash"]  for x in lexes if x[2].field.data_type == "Sound"]
        hashes = hashes[:] + [x[2].additional_metadata["hash"]  for x in p_lexes if x[2].field.data_type == "Sound"]
        links = [((x[2].link.client_id, x[2].link.object_id), (x[1].client_id, x[1].object_id))
                 for x in lexes if x[2].field.data_type == "Link" and
                 not x[2].marked_for_deletion and not x[1].marked_for_deletion and not x[0].marked_for_deletion]
        links = links[:] + [((x[2].link.client_id, x[2].link.object_id), (x[1].client_id, x[1].object_id))
                 for x in p_lexes if x[2].field.data_type == "Link" and
                 not x[2].marked_for_deletion and not x[1].marked_for_deletion and not x[0].marked_for_deletion]
        lexes_with_text = [x for x in lexes if x[2].field.data_type == "Text" and
                           (x[2].field.client_id, x[2].field.object_id) in field_ids.values() and not
                           x[2].marked_for_deletion and not x[1].marked_for_deletion and not x[0].marked_for_deletion]
        p_lexes_with_text = [x for x in p_lexes if x[2].field.data_type == "Text" and
                           (x[2].field.client_id, x[2].field.object_id) in field_ids.values() and not
                            x[2].marked_for_deletion and not x[1].marked_for_deletion and not x[0].marked_for_deletion]
        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
        """
        # FIRST PERSPECTIVE
        """
        task_status.set(3, 8, "Handling words perspective")
        if first_perspective is None:
            resp = translation_service_search_all("Lexical Entries")
            persp_translation_gist_client_id, persp_translation_gist_object_id = resp['client_id'], resp['object_id']
            first_perspective = DictionaryPerspective(client_id=client_id, ###
                                                state_translation_gist_object_id=state_translation_gist_object_id,
                                                state_translation_gist_client_id=state_translation_gist_client_id,
                                                parent=parent,
                                                # import_source=req.get('import_source'),
                                                # import_hash=req.get('import_hash'),
                                                additional_metadata=origin_metadata,
                                                translation_gist_client_id=persp_translation_gist_client_id,
                                                translation_gist_object_id=persp_translation_gist_object_id
                                                )

            first_perspective.additional_metadata = origin_metadata
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
        if second_perspective is None:
            second_perspective = DictionaryPerspective(client_id=client_id, ### variables['auth']
                                                state_translation_gist_object_id=state_translation_gist_object_id,
                                                state_translation_gist_client_id=state_translation_gist_client_id,
                                                parent=parent,
                                                # import_source=req.get('import_source'),
                                                # import_hash=req.get('import_hash'),
                                                additional_metadata=origin_metadata,
                                                translation_gist_client_id=persp_translation_gist_client_id,
                                                translation_gist_object_id=persp_translation_gist_object_id
                                                )
            second_perspective.additional_metadata = origin_metadata
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
        sp_field_names = ("Word of Paradigmatic forms",
                          "Transcription of Paradigmatic forms",
                          "Translation of Paradigmatic forms",
                          "Sounds of Paradigmatic forms",
                          "Backref")
        sp_fields_dict = {}
        fields_list = []
        for fieldname in sp_field_names:
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
        dubl = set()

        # Getting field data types.

        field_data_type_list = (

            DBSession

                .query(
                    Field.client_id,
                    Field.object_id,
                    TranslationAtom.content)

                .filter(

                    tuple_(
                        Field.client_id, Field.object_id)

                        .in_(
                            field_ids.values()),

                    TranslationAtom.locale_id == 2,
                    TranslationAtom.parent_client_id ==
                        Field.data_type_translation_gist_client_id,
                    TranslationAtom.parent_object_id ==
                        Field.data_type_translation_gist_object_id)

                .all())

        field_data_type_dict = {
            (field_cid, field_oid): data_type.lower()
            for field_cid, field_oid, data_type in field_data_type_list}

        for field_name, field_id in field_ids.items():
            field_data_type_dict[field_name] = field_data_type_dict[field_id]

        log.debug('\n' +
            pprint.pformat(field_data_type_dict))

        # Parsing and processing markup.

        le_sound_fid = field_ids['Sound']
        le_sound_dtype = field_data_type_dict[le_sound_fid]

        pa_sound_fid = field_ids['Sounds of Paradigmatic forms']
        pa_sound_dtype = field_data_type_dict[pa_sound_fid]

        backref_fid = field_ids['Backref']
        backref_dtype = field_data_type_dict[backref_fid]

        resp = requests.get(markup_entity.content)
        if not resp:
            raise KeyError("Cannot access file")
        content = resp.content
        result = False
        with tempfile.NamedTemporaryFile() as temp:
            markup = tgt_to_eaf(content, markup_entity.additional_metadata)
            temp.write(markup.encode("utf-8"))
            converter = elan_parser.Elan(temp.name)
            converter.parse()
            final_dicts = converter.proc()

        lex_rows = {}
        par_rows = {}
        task_status.set(8, 60, "Uploading sounds and words")

        current_percent = 60

        # Showing what we've got from the corpus.

        def f(value):

            if isinstance(value, elan_parser.Word):
                return value.get_tuple()

            elif isinstance(value, list):
                return [f(x) for x in value]

            return (
                OrderedDict(
                    ((f(x), f(y)) for x, y in value.items())))

        log.debug(
            '\nfinal_dicts:\n' +
            pprint.pformat(f(final_dicts), width = 192))

        # Processing corpus info.

        for phrase_index, phrase in enumerate(final_dicts):

            log.debug(
                f'\nphrase {phrase_index}:\n' +
                pprint.pformat(f(phrase), width = 192))

            curr_dict = {}
            paradigm_words = []
            for word_translation in phrase:
                if type(word_translation) is not list:
                    curr_dict = word_translation
                    mt_words = [word_translation[i][1].text for i in word_translation
                                if len(word_translation[i]) > 1 and word_translation[i][1].text is not None]
                    mt_times = [word_translation[i][1].time for i in word_translation
                                if len(word_translation[i]) > 1 and word_translation[i][1].time is not None]

                    main_tier_text = " ".join(mt_words)
                    main_tier_time = None
                    if mt_times:
                        main_tier_time = (mt_times[0], mt_times[-1])
                    if main_tier_text:
                        paradigm_words.append(elan_parser.Word(text=main_tier_text,
                                                               tier="Word of Paradigmatic forms",
                                                               time=main_tier_time)
                                              )
                        log.debug(
                            '\nparadigm_word:\n' +
                            pprint.pformat(
                                paradigm_words[-1].get_tuple(), width = 192))
                else:
                    word = word_translation[0]
                    tier_name = word.tier
                    new = " ".join([i.text for i in word_translation if i.text is not None])
                    if new:
                        paradigm_words.append(elan_parser.Word(text=new, tier=tier_name, time=word.time))
                        log.debug(
                            '\nparadigm_word:\n' +
                            pprint.pformat(
                                paradigm_words[-1].get_tuple(), width = 192))

            par_row  = tuple([x.text for x in paradigm_words])

            log.debug(
                '\nparadigm_words:\n' +
                pprint.pformat(f(paradigm_words), width = 192) +
                '\npar_row:\n' +
                pprint.pformat(par_row, width = 192))

            sp_lexical_entry_client_id = None
            sp_lexical_entry_object_id = None

            if par_row and par_row not in par_rows:
                p_match_dict = defaultdict(list)
                for pword in paradigm_words:
                    match = [x for x in p_lexes_with_text if x[2].content == pword.text]  #LEX COUNT OR RANDOM
                    for t in match:
                        if field_ids[EAF_TIERS[pword.tier]] == (t[2].field.client_id, t[2].field.object_id):
                           p_match_dict[t[1]].append(t)
                p_match_dict = { k: v for k, v in p_match_dict.items() if len(v) >= 2 or len(v) == 1 and
                                 [x[1] for x in p_lexes_with_text].count(k) == 1}
                max_sim = None
                for le in p_match_dict:
                    if max_sim is None:
                        max_sim = le
                    else:
                        if len(p_match_dict[le]) >= len(p_match_dict[max_sim]):
                                max_sim = le
                if max_sim:
                    sp_lexical_entry_client_id = max_sim.client_id
                    sp_lexical_entry_object_id = max_sim.object_id
                else:
                    lexentr = LexicalEntry(client_id=client_id,
                                           parent_object_id=second_perspective_object_id,
                                           parent=second_perspective)
                    DBSession.add(lexentr)
                    sp_lexical_entry_client_id = lexentr.client_id
                    sp_lexical_entry_object_id = lexentr.object_id

                par_rows[par_row] = (sp_lexical_entry_client_id, sp_lexical_entry_object_id)
                for other_word in paradigm_words:
                    if max_sim:
                        text_and_field = (other_word.text, field_ids[EAF_TIERS[other_word.tier]])
                        sim = [(x[2].content, (x[2].field.client_id, x[2].field.object_id)) for x in p_match_dict[max_sim]]
                        if text_and_field not in sim:
                            if other_word.text:
                                field_id = field_ids[EAF_TIERS[other_word.tier]]
                                create_entity(sp_lexical_entry_client_id,
                                              sp_lexical_entry_object_id,
                                              field_id[0],
                                              field_id[1],
                                              field_data_type_dict[field_id],
                                              client_id,
                                              other_word.text,
                                              filename=None,
                                              storage=storage)
                    else:
                        if other_word.text:
                            field_id = field_ids[EAF_TIERS[other_word.tier]]
                            create_entity(sp_lexical_entry_client_id,
                                          sp_lexical_entry_object_id,
                                          field_id[0],
                                          field_id[1],
                                          field_data_type_dict[field_id],
                                          client_id,
                                          other_word.text,
                                          filename=None,
                                          storage=storage)
            elif par_row:
                sp_lexical_entry_client_id, sp_lexical_entry_object_id = par_rows[par_row]
            if par_row and not no_sound:
                if word.time[1] <= len(full_audio):
                    with tempfile.NamedTemporaryFile() as temp:
                        full_audio[ word.time[0]: word.time[1]].export(temp.name, format=sound_format)
                        audio_slice = temp.read()
                        if max_sim:
                            hash = hashlib.sha224(audio_slice).hexdigest()
                            if not hash in hashes:
                                hashes.append(hash)
                                common_name = word.index
                                if common_name:
                                    fname, ext = os.path.splitext(common_name)
                                    ext = ext.replace(".", "").replace(" ", "")
                                    fname = fname.replace(".", "_")
                                    if not ext:
                                        ext = 'flac' if sound_format == 'flac' else 'wav'
                                    filename = "%s.%s" % (fname, ext)
                                else:
                                    filename = 'noname.flac'
                                create_entity(sp_lexical_entry_client_id,
                                              sp_lexical_entry_object_id,
                                              pa_sound_fid[0],
                                              pa_sound_fid[1],
                                              pa_sound_dtype,
                                              client_id,
                                              filename=filename,
                                              folder_name="corpus_paradigm_sounds",
                                              content=base64.urlsafe_b64encode(audio_slice).decode(),
                                              storage=storage)
                        else:
                            common_name = word.index
                            if common_name:
                                fname, ext = os.path.splitext(common_name)
                                ext = ext.replace(".", "").replace(" ", "")
                                fname = fname.replace(".", "_")
                                if not ext:
                                    ext = 'flac' if sound_format == 'flac' else 'wav'
                                filename = "%s.%s" % (fname, ext)
                            else:
                                filename = 'noname.flac'
                            create_entity(sp_lexical_entry_client_id,
                                          sp_lexical_entry_object_id,
                                          pa_sound_fid[0],
                                          pa_sound_fid[1],
                                          pa_sound_dtype,
                                          client_id,
                                          filename=filename,
                                          folder_name="corpus_paradigm_sounds",
                                          content=base64.urlsafe_b64encode(audio_slice).decode(),
                                          storage=storage)

                        temp.flush()
            paradigm_words[:] = []
            for word in curr_dict:
                if curr_dict:
                    if word.tier == "translation":
                         translation_word_text = word.text
                         if translation_word_text:
                             if re.search('[-.][\dA-Z]+', translation_word_text) and \
                                not re.search("[-]INF", translation_word_text) and \
                                not re.search("[-]SG.NOM", translation_word_text) and \
                                not re.search("[-]NOM", translation_word_text):
                                tag = re.search("[1-3][Dd][Uu]|[1-3][Pp][Ll]|[1-3][Ss][Gg]", translation_word_text)
                                if tag:
                                    text_without_tag = translation_word_text.replace(tag.group(0), "")
                                    if len(text_without_tag) > 0:
                                        continue
                                else:
                                    continue
                column = [word] + curr_dict[word]
                lex_row = tuple([x.text for x in column])
                if not [x.text for x in column if x.text is not None]:
                    column[:] = []
                    continue
                if not lex_row in lex_rows:
                    match_dict = defaultdict(list)
                    for crt in tuple(i for i in column):
                        match = [x for x in lexes_with_text if x[2].content == crt.text]
                        for t in match:
                            if field_ids[EAF_TIERS[crt.tier]] == (t[2].field.client_id, t[2].field.object_id):
                               match_dict[t[1]].append(t)
                    match_dict = { k: v for k, v in match_dict.items() if len(v) >= 2 or len(v) == 1 and
                                   [x[1] for x in lexes_with_text].count(k) == 1}
                    max_sim = None
                    for le in match_dict:
                        if max_sim is None:
                            max_sim = le
                        else:
                            if len(match_dict[le]) >= len(match_dict[max_sim]):
                                max_sim = le
                    if max_sim:
                        fp_lexical_entry_client_id = max_sim.client_id
                        fp_lexical_entry_object_id = max_sim.object_id
                    else:
                        lexentr = LexicalEntry(client_id=client_id,
                                               parent_object_id=first_perspective_object_id, parent=first_perspective)
                        DBSession.add(lexentr)
                        fp_lexical_entry_client_id = lexentr.client_id
                        fp_lexical_entry_object_id = lexentr.object_id
                    lex_rows[lex_row] = (fp_lexical_entry_client_id, fp_lexical_entry_object_id)
                    for other_word in column:
                        if max_sim:
                            text_and_field = (other_word.text, field_ids[EAF_TIERS[other_word.tier]])
                            sim = [(x[2].content, (x[2].field.client_id, x[2].field.object_id))
                                   for x in match_dict[max_sim]]
                            if text_and_field not in sim:
                                if other_word.text:
                                    field_id = field_ids[EAF_TIERS[other_word.tier]]
                                    create_entity(fp_lexical_entry_client_id,
                                                  fp_lexical_entry_object_id,
                                                  field_id[0],
                                                  field_id[1],
                                                  field_data_type_dict[field_id],
                                                  client_id,
                                                  other_word.text,
                                                  filename=None,
                                                  storage=storage)
                        else:
                            if other_word.text:
                                field_id = field_ids[EAF_TIERS[other_word.tier]]
                                create_entity(fp_lexical_entry_client_id,
                                              fp_lexical_entry_object_id,
                                              field_id[0],
                                              field_id[1],
                                              field_data_type_dict[field_id],
                                              client_id,
                                              other_word.text,
                                              filename=None,
                                              storage=storage)
                else:
                    fp_lexical_entry_client_id, fp_lexical_entry_object_id = lex_rows[lex_row]
                if not no_sound:
                    if word.time[1] <= len(full_audio):
                        with tempfile.NamedTemporaryFile() as temp:
                            full_audio[ word.time[0]: word.time[1]].export(temp.name, format=sound_format)
                            audio_slice = temp.read()
                            hash = hashlib.sha224(audio_slice).hexdigest()
                            common_name = word.index
                            if common_name:
                                fname, ext = os.path.splitext(common_name)
                                ext = ext.replace(".", "").replace(" ", "")
                                fname = fname.replace(".", "_")
                                if not ext:
                                    ext = 'flac' if sound_format == 'flac' else 'wav'
                                filename = "%s.%s" % (fname, ext)
                            else:
                                filename = 'noname.flac'
                            if max_sim:
                                if not hash in hashes:
                                    hashes.append(hash)
                                    create_entity(fp_lexical_entry_client_id,
                                                  fp_lexical_entry_object_id,
                                                  le_sound_fid[0],
                                                  le_sound_fid[1],
                                                  le_sound_dtype,
                                                  client_id,
                                                  filename=filename ,
                                                  folder_name="corpus_lexical_entry_sounds",
                                                  content=base64.urlsafe_b64encode(audio_slice).decode(),
                                                  storage=storage)
                            else:
                                create_entity(fp_lexical_entry_client_id,
                                              fp_lexical_entry_object_id,
                                              le_sound_fid[0],
                                              le_sound_fid[1],
                                              le_sound_dtype,
                                              client_id,
                                              filename=filename,
                                              folder_name="corpus_lexical_entry_sounds",
                                              content=base64.urlsafe_b64encode(audio_slice).decode(),
                                              storage=storage)
                            temp.flush()

                fp_le_ids = (fp_lexical_entry_client_id, fp_lexical_entry_object_id)
                sp_le_ids = (sp_lexical_entry_client_id, sp_lexical_entry_object_id)

                # If we don't have a paradigm entry (e.g. when we have no paradigm text and no paradigm
                # translation in the corpus), we obviously do not establish any links.

                if sp_le_ids == (None, None):
                    continue

                dubl_tuple = (sp_le_ids, fp_le_ids)
                if not dubl_tuple in dubl:
                    dubl.add(dubl_tuple)
                    if max_sim:
                        if not (sp_le_ids, fp_le_ids) in links :
                            create_entity(sp_lexical_entry_client_id,
                                          sp_lexical_entry_object_id,
                                          backref_fid[0],
                                          backref_fid[1],
                                          backref_dtype,
                                          client_id,
                                          filename=None,
                                          link_client_id=fp_lexical_entry_client_id,
                                          link_object_id=fp_lexical_entry_object_id,
                                          storage=storage)
                        if not (fp_le_ids, sp_le_ids) in links:
                            create_entity(fp_lexical_entry_client_id,
                                          fp_lexical_entry_object_id,
                                          backref_fid[0],
                                          backref_fid[1],
                                          backref_dtype,
                                          client_id,
                                          filename=None,
                                          link_client_id=sp_lexical_entry_client_id,
                                          link_object_id=sp_lexical_entry_object_id,
                                          storage=storage)
                    else:
                        create_entity(sp_lexical_entry_client_id,
                                      sp_lexical_entry_object_id,
                                      backref_fid[0],
                                      backref_fid[1],
                                      backref_dtype,
                                      client_id,
                                      filename=None,
                                      link_client_id=fp_lexical_entry_client_id,
                                      link_object_id=fp_lexical_entry_object_id,
                                      storage=storage)
                        create_entity(fp_lexical_entry_client_id,
                                      fp_lexical_entry_object_id,
                                      backref_fid[0],
                                      backref_fid[1],
                                      backref_dtype,
                                      client_id,
                                      filename=None,
                                      link_client_id=sp_lexical_entry_client_id,
                                      link_object_id=sp_lexical_entry_object_id,
                                      storage=storage)
                column[:] = []
                match_dict.clear()

            # Checking if need to update task progress.

            percent = (
                60 + int(math.floor(phrase_index * 30 / len(final_dicts))))

            if percent > current_percent:

                task_status.set(8, percent, "Uploading sounds and words")
                current_percent = percent

        # Current data of lexical entries and paradigms.

        lexes_with_text = []

        le_word_fid = field_ids['Word']
        le_word_dtype = field_data_type_dict[le_word_fid]

        le_xcript_fid = field_ids['Transcription']
        le_xcript_dtype = field_data_type_dict[le_xcript_fid]

        le_xlat_fid = field_ids['Translation']
        le_xlat_dtype = field_data_type_dict[le_xlat_fid]

        if first_perspective:

            le_text_fid_list = [
                le_word_fid,
                le_xcript_fid,
                le_xlat_fid]

            lexes_with_text = (

                DBSession
                    .query(Entity)

                    .filter(
                        Entity.marked_for_deletion == False,
                        LexicalEntry.client_id == Entity.parent_client_id,
                        LexicalEntry.object_id == Entity.parent_object_id,
                        LexicalEntry.marked_for_deletion == False,
                        LexicalEntry.parent_client_id == first_perspective.client_id,
                        LexicalEntry.parent_object_id == first_perspective.object_id,

                        tuple_(
                            Entity.field_client_id,
                            Entity.field_object_id)

                            .in_(le_text_fid_list))

                    .all())

        p_lexes_with_text_after_update = []

        pa_word_fid = field_ids['Word of Paradigmatic forms']
        pa_xcript_fid = field_ids['Transcription of Paradigmatic forms']
        pa_xlat_fid = field_ids['Translation of Paradigmatic forms']

        if second_perspective:

            pa_text_fid_list = [
                pa_word_fid,
                pa_xcript_fid,
                pa_xlat_fid]

            p_lexes_with_text_after_update = (

                DBSession
                    .query(Entity)

                    .filter(
                        Entity.marked_for_deletion == False,
                        LexicalEntry.client_id == Entity.parent_client_id,
                        LexicalEntry.object_id == Entity.parent_object_id,
                        LexicalEntry.marked_for_deletion == False,
                        LexicalEntry.parent_client_id == second_perspective.client_id,
                        LexicalEntry.parent_object_id == second_perspective.object_id,

                        tuple_(
                            Entity.field_client_id,
                            Entity.field_object_id)

                            .in_(pa_text_fid_list))

                    .all())

        # Info of words and transcriptions in the first perspective.

        task_status.set(9, 90, "Uploading translations with marks")

        noms = []  # words with NOM/INF mark
        conjs = []
        new_lex_entries = {}

        le_xlat_dict = {}

        le_word_dict = defaultdict(set)
        le_xcript_dict = defaultdict(set)

        for t in lexes_with_text:

            if t.field_id == le_word_fid:

                le_word_dict[t.parent_id].add(
                    t.content.strip().lower())

            elif t.field_id == le_xcript_fid:

                le_xcript_dict[t.parent_id].add(
                    t.content.strip().lower())

            # Translation.

            else:

                translation_text = t.content

                if re.search("[-]NOM|[-]INF|[-]SG.NOM", translation_text):
                    noms.append(t)

                if re.search("[1-3][Dd][Uu]|[1-3][Pp][Ll]|[1-3][Ss][Gg]", translation_text):
                    conjs.append(t)

                le_xlat_dict[
                    translation_text.strip().lower()] = (

                    t.parent_id)

        # Updated words and transcriptions in the second perspective.

        pa_already_set = set(
            t[2].id for t in p_lexes_with_text)

        p_lexes_with_text_after_update = [

            t
            for t in p_lexes_with_text_after_update
            if t.id not in pa_already_set]

        pa_word_dict = defaultdict(list)
        pa_xcript_dict = defaultdict(list)

        for t in p_lexes_with_text_after_update:

            if t.field_id == pa_word_fid:
                pa_word_dict[t.parent_id].append(t.content)

            elif t.field_id == pa_xcript_fid:
                pa_xcript_dict[t.parent_id].append(t.content)

        def establish_link(
            le_entry_id,
            pa_entry_id,
            pa_xlat):
            """
            Establishes link between lexical and paradigmatic entries, adds paradigmatic words and/or
            transcriptions to lexical entries if required.
            """

            if not (le_entry_id, pa_entry_id) in links:

                create_entity(
                    le_entry_id[0],
                    le_entry_id[1],
                    backref_fid[0],
                    backref_fid[1],
                    backref_dtype,
                    client_id,
                    link_client_id = pa_entry_id[0],
                    link_object_id = pa_entry_id[1])

            if not (pa_entry_id, le_entry_id) in links:

                create_entity(
                    pa_entry_id[0],
                    pa_entry_id[1],
                    backref_fid[0],
                    backref_fid[1],
                    backref_dtype,
                    client_id,
                    link_client_id = le_entry_id[0],
                    link_object_id = le_entry_id[1])

            # Adding paradigmatic word and transcriptions to lexical entries.

            for pa_word in pa_word_dict[pa_entry_id]:

                word_key = (
                    pa_word.strip().lower())

                le_word_set = (
                    le_word_dict[le_entry_id])

                if word_key not in le_word_set:

                    le_word_set.add(word_key)

                    create_entity(
                        le_entry_id[0],
                        le_entry_id[1],
                        le_word_fid[0],
                        le_word_fid[1],
                        le_word_dtype,
                        client_id,
                        pa_word)

            for pa_xcript in pa_xcript_dict[pa_entry_id]:

                xcript_key = (
                    pa_xcript.strip().lower())

                le_xcript_set = (
                    le_xcript_dict[le_entry_id])

                if xcript_key not in le_xcript_set:

                    le_xcript_set.add(xcript_key)

                    create_entity(
                        le_entry_id[0],
                        le_entry_id[1],
                        le_xcript_fid[0],
                        le_xcript_fid[1],
                        le_xcript_dtype,
                        client_id,
                        pa_xcript)

        # Linking updated paradigms.

        for t in p_lexes_with_text_after_update:

            if t.field_id != pa_xlat_fid:
                continue

            translation_text = t.content
            tag = re.search('[1-3][Dd][Uu]|[1-3][Pp][Ll]|[1-3][Ss][Gg]', translation_text)
            create_le_flag = None

            if tag:

                create_le_flag = True
                tag_name = tag.group(0)

                if translation_text[:3] == tag.group(0):

                    for conj in conjs:

                        if tag_name == conj.content:

                            sp_le_ids = t.parent_id
                            fp_le_ids = conj.parent_id

                            if not (sp_le_ids, fp_le_ids) in links:
                                create_entity(t.parent_client_id,
                                              t.parent_object_id,
                                              backref_fid[0],
                                              backref_fid[1],
                                              backref_dtype,
                                              client_id,
                                              link_client_id=conj.parent_client_id,
                                              link_object_id=conj.parent_object_id)

                            if not (fp_le_ids, sp_le_ids) in links:
                                create_entity(conj.parent_client_id,
                                              conj.parent_object_id,
                                              backref_fid[0],
                                              backref_fid[1],
                                              backref_dtype,
                                              client_id,
                                              link_client_id=t.parent_client_id,
                                              link_object_id=t.parent_object_id)

                            create_le_flag = False
                            break

                else:

                    create_le_flag = False
                    reg = re.search('[-.][\dA-Z]+', t.content)

                    if reg:

                        create_le_flag = True

                        for x in noms:

                            mark_w_text = reg.start()
                            nom_clean_text = re.search('[-.][\dA-Z]+', x.content).start()

                            if x.content[:nom_clean_text] == t.content[:mark_w_text]:

                                establish_link(
                                    x.parent_id,
                                    t.parent_id,
                                    t.content[:mark_w_text])

                                create_le_flag = False
                                break
            else:

                create_le_flag = False
                reg = re.search('[-.][\dA-Z]+', t.content)

                if reg:

                    create_le_flag = True

                    for x in noms:

                        mark_w_text = reg.start()
                        nom_clean_text = re.search('[-.][\dA-Z]+', x.content).start()

                        if x.content[:nom_clean_text] == t.content[:mark_w_text]:

                            establish_link(
                                x.parent_id,
                                t.parent_id,
                                t.content[:mark_w_text])

                            create_le_flag = False
                            break

            if create_le_flag:

                before_dash = re.search('[-.][\dA-Z]+', translation_text)

                if before_dash:
                    translation_text = translation_text[:before_dash.start()]

                if not translation_text in new_lex_entries:

                    lexentr = (

                        LexicalEntry(
                            client_id=client_id,
                            parent=first_perspective))

                    DBSession.add(lexentr)
                    new_fp_lexical_entry_client_id = lexentr.client_id
                    new_fp_lexical_entry_object_id = lexentr.object_id

                    lexentr_id = (
                        new_fp_lexical_entry_client_id,
                        new_fp_lexical_entry_object_id)

                    new_lex_entries[translation_text] = lexentr_id

                    create_entity(
                        new_fp_lexical_entry_client_id,
                        new_fp_lexical_entry_object_id,
                        le_xlat_fid[0],
                        le_xlat_fid[1],
                        le_xlat_dtype,
                        client_id,
                        translation_text)

                    le_xlat_dict[
                        translation_text.strip().lower()] = (

                        lexentr_id)

                    establish_link(
                        lexentr_id,
                        t.parent_id,
                        translation_text)

                else:

                    establish_link(
                        new_lex_entries[translation_text],
                        t.parent_id,
                        translation_text)

    task_status.set(10, 100, "Finished", "")

    return dictionary_id


def convert_all(dictionary_id,
                client_id,
                sqlalchemy_url,
                storage,
                markup_id,
                locale_id,
                task_key,
                cache_kwargs,
                translation_gist_id,
                language_id,
                sound_url,
                no_sound_flag = False,
                synchronous = False):

    if not synchronous:
        from lingvodoc.cache.caching import initialize_cache
        engine = create_engine(sqlalchemy_url)
        DBSession.configure(bind=engine)
        initialize_cache(cache_kwargs)

    global CACHE
    from lingvodoc.cache.caching import CACHE

    task_status = TaskStatus.get_from_cache(task_key)

    try:

        result = (

            convert_five_tiers(
                dictionary_id,
                client_id,
                sqlalchemy_url,
                storage,
                markup_id,
                locale_id,
                task_status,
                cache_kwargs,
                translation_gist_id,
                language_id,
                sound_url,
                no_sound_flag))

    except Exception as err:
        task_status.set(None, -1, "Conversion failed: %s" % str(err))
        raise

    DBSession.flush()
    return result
