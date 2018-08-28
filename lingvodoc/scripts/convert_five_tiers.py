# -*- coding: utf-8 -*-
import json
import os
import re
import base64
import hashlib
import shutil
import transaction
import tempfile
import warnings
import logging
from collections import defaultdict
from pathvalidate import sanitize_filename
from urllib import request
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import create_engine
from sqlalchemy import and_
from lingvodoc.models import (
    Client,
    DBSession,
    TranslationAtom,
    TranslationGist,
    Field,
    Entity,
    LexicalEntry,
    Dictionary,
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
log.setLevel(logging.WARNING)

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

    DBSession.add(entity)
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




def convert_five_tiers(
                dictionary_client_id,
                dictionary_object_id,
                client_id,
                origin_client_id,
                origin_object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                task_status,
                locale_id,
                sound_url=None
                ):
    task_status.set(1, 1, "Preparing")
    no_sound = True
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
               sound_file = request.urlopen(sound_url)
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
        #
        #     data_type_query = DBSession.query(Field) \
        #         .join(TranslationGist,
        #               and_(Field.translation_gist_object_id == TranslationGist.object_id,
        #                    Field.translation_gist_client_id == TranslationGist.client_id))\
        #         .join(TranslationGist.translationatom)
        #     field = data_type_query.filter(TranslationAtom.locale_id == 2,
        #                                    TranslationAtom.content == name)\
        #                            .order_by(TranslationAtom.client_id)\
        #                            .first()
        #
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


        origin_metadata= {"origin_id": (origin_client_id, origin_object_id)}

        parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id,
                                                       object_id=dictionary_object_id).first()
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
            first_perspective = DictionaryPerspective(client_id=client.id, ###
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
            second_perspective = DictionaryPerspective(client_id=client.id, ### variables['auth']
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
        dubl = []
        try:
           eaffile = request.urlopen(eaf_url)
        except HTTPError as e:
            return {'error': str(e.read().decode("utf8", 'ignore'))}
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(eaffile.read())
            converter = elan_parser.Elan(temp.name)
            converter.parse()
            final_dicts = converter.proc()
        lex_rows = {}
        par_rows = {}
        task_status.set(8, 60, "Uploading sounds and words")

        for phrase in final_dicts:
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
                else:
                    word = word_translation[0]
                    tier_name = word.tier
                    new = " ".join([i.text for i in word_translation if i.text is not None])
                    if new:
                        paradigm_words.append(elan_parser.Word(text=new, tier=tier_name, time=word.time))
            par_row  = tuple([x.text for x in paradigm_words])
            if not par_row in par_rows:
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
                    lexentr = LexicalEntry(client_id=client.id,
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
                                create_entity(sp_lexical_entry_client_id,
                                              sp_lexical_entry_object_id,
                                              field_ids[EAF_TIERS[other_word.tier]][0],
                                              field_ids[EAF_TIERS[other_word.tier]][1],
                                              None,
                                              client,
                                              other_word.text,
                                              locale_id=locale_id,
                                              filename=None,
                                              storage=storage)
                    else:
                        if other_word.text:
                            create_entity(sp_lexical_entry_client_id,
                                          sp_lexical_entry_object_id,
                                          field_ids[EAF_TIERS[other_word.tier]][0],
                                          field_ids[EAF_TIERS[other_word.tier]][1],
                                          None,
                                          client,
                                          other_word.text,
                                          filename=None,
                                          storage=storage,
                                          locale_id=locale_id)
            else:
                sp_lexical_entry_client_id, sp_lexical_entry_object_id = par_rows[par_row]
            if not no_sound:
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
                                        ext = "wav"
                                    filename = "%s.%s" % (fname, ext)
                                else:
                                    filename = 'noname.wav'
                                create_entity(sp_lexical_entry_client_id,
                                              sp_lexical_entry_object_id,
                                              field_ids["Sounds of Paradigmatic forms"][0],
                                              field_ids["Sounds of Paradigmatic forms"][1],
                                              None,
                                              client,
                                              filename=filename,
                                              folder_name="corpus_paradigm_sounds",
                                              content=base64.urlsafe_b64encode(audio_slice).decode(),
                                              storage=storage,
                                              locale_id=locale_id)
                        else:
                            common_name = word.index
                            if common_name:
                                fname, ext = os.path.splitext(common_name)
                                ext = ext.replace(".", "").replace(" ", "")
                                fname = fname.replace(".", "_")
                                if not ext:
                                    ext = "wav"
                                filename = "%s.%s" % (fname, ext)
                            else:
                                filename = 'noname.wav'
                            create_entity(sp_lexical_entry_client_id,
                                          sp_lexical_entry_object_id,
                                          field_ids["Sounds of Paradigmatic forms"][0],
                                          field_ids["Sounds of Paradigmatic forms"][1],
                                          None,
                                          client,
                                          filename=filename,
                                          folder_name="corpus_paradigm_sounds",
                                          content=base64.urlsafe_b64encode(audio_slice).decode(),
                                          storage=storage,
                                          locale_id=locale_id)

                        temp.flush()
            p_match_dict.clear()
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
                        lexentr = LexicalEntry(client_id=client.id,
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
                                    create_entity(fp_lexical_entry_client_id,
                                                  fp_lexical_entry_object_id,
                                                  field_ids[EAF_TIERS[other_word.tier]][0],
                                                  field_ids[EAF_TIERS[other_word.tier]][1],
                                                  None,
                                                  client,
                                                  other_word.text,
                                                  filename=None,
                                                  storage=storage,
                                                  locale_id=locale_id
                                                  )
                        else:
                            if other_word.text:
                                create_entity(fp_lexical_entry_client_id,
                                              fp_lexical_entry_object_id,
                                              field_ids[EAF_TIERS[other_word.tier]][0],
                                              field_ids[EAF_TIERS[other_word.tier]][1],
                                              None,
                                              client,
                                              other_word.text,
                                              filename=None,
                                              storage=storage,
                                              locale_id=locale_id
                                              )
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
                                    ext = "wav"
                                filename = "%s.%s" % (fname, ext)
                            else:
                                filename = 'noname.wav'
                            if max_sim:
                                if not hash in hashes:
                                    hashes.append(hash)
                                    create_entity(fp_lexical_entry_client_id,
                                                  fp_lexical_entry_object_id,
                                                  field_ids["Sound"][0],
                                                  field_ids["Sound"][1],
                                                  None,
                                                  client,
                                                  filename=filename ,
                                                  folder_name="corpus_lexical_entry_sounds",
                                                  content=base64.urlsafe_b64encode(audio_slice).decode(),
                                                  storage=storage,
                                                  locale_id=locale_id)
                            else:
                                create_entity(fp_lexical_entry_client_id,
                                              fp_lexical_entry_object_id,
                                              field_ids["Sound"][0],
                                              field_ids["Sound"][1],
                                              None,
                                              client,
                                              filename=filename,
                                              folder_name="corpus_lexical_entry_sounds",
                                              content=base64.urlsafe_b64encode(audio_slice).decode(),
                                              storage=storage,
                                              locale_id=locale_id
                                              )
                            temp.flush()
                fp_le_ids = (fp_lexical_entry_client_id, fp_lexical_entry_object_id)
                sp_le_ids = (sp_lexical_entry_client_id, sp_lexical_entry_object_id)
                dubl_tuple = (sp_le_ids, fp_le_ids)
                if not dubl_tuple in dubl:
                    dubl.append(dubl_tuple)
                    if max_sim:
                        if not (sp_le_ids, fp_le_ids) in links :
                            create_entity(sp_lexical_entry_client_id,
                                          sp_lexical_entry_object_id,
                                          field_ids["Backref"][0],
                                          field_ids["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=fp_lexical_entry_client_id,
                                          link_object_id=fp_lexical_entry_object_id,
                                          storage=storage,
                                          locale_id=locale_id)
                        if not (fp_le_ids, sp_le_ids) in links:
                            create_entity(fp_lexical_entry_client_id,
                                          fp_lexical_entry_object_id,
                                          field_ids["Backref"][0],
                                          field_ids["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=sp_lexical_entry_client_id,
                                          link_object_id=sp_lexical_entry_object_id,
                                          storage=storage,
                                          locale_id=locale_id)
                    else:
                        create_entity(sp_lexical_entry_client_id,
                                      sp_lexical_entry_object_id,
                                      field_ids["Backref"][0],
                                      field_ids["Backref"][1],
                                      None,
                                      client,
                                      filename=None,
                                      link_client_id=fp_lexical_entry_client_id,
                                      link_object_id=fp_lexical_entry_object_id,
                                      storage=storage,
                                      locale_id=locale_id)
                        create_entity(fp_lexical_entry_client_id,
                                      fp_lexical_entry_object_id,
                                      field_ids["Backref"][0],
                                      field_ids["Backref"][1],
                                      None,
                                      client,
                                      filename=None,
                                      link_client_id=sp_lexical_entry_client_id,
                                      link_object_id=sp_lexical_entry_object_id,
                                      storage=storage,
                                      locale_id=locale_id)
                column[:] = []
                match_dict.clear()

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
        lexes_with_text = [x for x in lexes if x[2].field.data_type == "Text" and
                           (x[2].field.client_id, x[2].field.object_id) in field_ids.values() and not
                            x[2].marked_for_deletion and not x[1].marked_for_deletion and not x[0].marked_for_deletion]
        p_lexes_with_text_after_update = [x for x in p_lexes if x[2].field.data_type == "Text" and
                           (x[2].field.client_id, x[2].field.object_id) in field_ids.values() and not
                            x[2].marked_for_deletion and not x[1].marked_for_deletion and not x[0].marked_for_deletion]
        task_status.set(9, 90, "Uploading translations with marks")

        noms = []  # words with NOM/INF mark
        conjs = []
        new_lex_entries = {}

        for t in lexes_with_text:
            t_fids = (t[2].field.client_id, t[2].field.object_id)
            if field_ids["Translation"] == t_fids:
                translation_text = t[2].content
                if re.search("[-]NOM|[-]INF|[-]SG.NOM", translation_text):
                    noms.append(t)
                if re.search("[1-3][Dd][Uu]|[1-3][Pp][Ll]|[1-3][Ss][Gg]", translation_text):
                    conjs.append(t)
        for t in p_lexes_with_text_after_update:
            if t in p_lexes_with_text:
                continue
            t_fids = (t[2].field.client_id, t[2].field.object_id)
            if field_ids["Translation of Paradigmatic forms"] == t_fids:
                translation_text = t[2].content
                tag = re.search('[1-3][Dd][Uu]|[1-3][Pp][Ll]|[1-3][Ss][Gg]', translation_text)
                create_le_flag = None
                if tag:
                    create_le_flag = True
                    tag_name = tag.group(0)
                    if translation_text[:3] == tag.group(0):
                        for conj in conjs:
                            if tag_name == conj[2].content:
                                sp_le_ids = (t[1].client_id, t[1].object_id)
                                fp_le_ids = (conj[1].client_id, conj[1].object_id)
                                if not (sp_le_ids, fp_le_ids) in links:
                                    create_entity(t[1].client_id,
                                                  t[1].object_id,
                                                  field_ids["Backref"][0],
                                                  field_ids["Backref"][1],
                                                  None,
                                                  client,
                                                  filename=None,
                                                  link_client_id=conj[1].client_id,
                                                  link_object_id=conj[1].object_id,
                                                  storage=storage,
                                                  locale_id=locale_id)

                                if not (fp_le_ids, sp_le_ids) in links:
                                    create_entity(conj[1].client_id,
                                                  conj[1].object_id,
                                                  field_ids["Backref"][0],
                                                  field_ids["Backref"][1],
                                                  None,
                                                  client,
                                                  filename=None,
                                                  link_client_id=t[1].client_id,
                                                  link_object_id=t[1].object_id,
                                                  storage=storage,
                                                  locale_id=locale_id)
                                create_le_flag = False
                                break
                    else:
                        create_le_flag = False
                        reg = re.search('[-.][\dA-Z]+', t[2].content)
                        if reg:
                            create_le_flag = True
                            for x in noms:
                                mark_w_text = reg.start()
                                nom_clean_text = re.search('[-.][\dA-Z]+', x[2].content).start()
                                if x[2].content[:nom_clean_text] == t[2].content[:mark_w_text]:
                                    sp_le_ids = (t[1].client_id, t[1].object_id)
                                    fp_le_ids = (x[1].client_id, x[1].object_id)
                                    if not (sp_le_ids, fp_le_ids) in links:
                                        create_entity(t[1].client_id,
                                                      t[1].object_id,
                                                      field_ids["Backref"][0],
                                                      field_ids["Backref"][1],
                                                      None,
                                                      client,
                                                      filename=None,
                                                      link_client_id=x[1].client_id,
                                                      link_object_id=x[1].object_id,
                                                      storage=storage,
                                                      locale_id=locale_id)

                                    if not (fp_le_ids, sp_le_ids) in links:
                                        create_entity(x[1].client_id,
                                                      x[1].object_id,
                                                      field_ids["Backref"][0],
                                                      field_ids["Backref"][1],
                                                      None,
                                                      client,
                                                      filename=None,
                                                      link_client_id=t[1].client_id,
                                                      link_object_id=t[1].object_id,
                                                      storage=storage,
                                                      locale_id=locale_id)
                                    create_le_flag = False
                                    break
                else:
                    create_le_flag = False
                    reg = re.search('[-.][\dA-Z]+', t[2].content)
                    if reg:
                        create_le_flag = True
                        for x in noms:
                            mark_w_text = reg.start()
                            nom_clean_text = re.search('[-.][\dA-Z]+', x[2].content).start()
                            if x[2].content[:nom_clean_text] == t[2].content[:mark_w_text]:
                                sp_le_ids = (t[1].client_id, t[1].object_id)
                                fp_le_ids = (x[1].client_id, x[1].object_id)
                                if not (sp_le_ids, fp_le_ids) in links:
                                    create_entity(t[1].client_id,
                                                  t[1].object_id,
                                                  field_ids["Backref"][0],
                                                  field_ids["Backref"][1],
                                                  None,
                                                  client,
                                                  filename=None,
                                                  link_client_id=x[1].client_id,
                                                  link_object_id=x[1].object_id,
                                                  storage=storage,
                                                  locale_id=locale_id)

                                if not (fp_le_ids, sp_le_ids) in links:
                                    create_entity(x[1].client_id,
                                                  x[1].object_id,
                                                  field_ids["Backref"][0],
                                                  field_ids["Backref"][1],
                                                  None,
                                                  client,
                                                  filename=None,
                                                  link_client_id=t[1].client_id,
                                                  link_object_id=t[1].object_id,
                                                  storage=storage,
                                                  locale_id=locale_id)
                                create_le_flag = False
                                break
                if create_le_flag:
                    before_dash = re.search('[-.][\dA-Z]+', translation_text)
                    if before_dash:
                        translation_text = translation_text[:before_dash.start()]
                    if not translation_text in new_lex_entries:
                        lexentr = LexicalEntry(client_id=client.id,
                                               parent_object_id=first_perspective_object_id, parent=first_perspective)
                        DBSession.add(lexentr)
                        new_fp_lexical_entry_client_id = lexentr.client_id
                        new_fp_lexical_entry_object_id = lexentr.object_id
                        new_lex_entries[translation_text] = (new_fp_lexical_entry_client_id,
                                                             new_fp_lexical_entry_object_id)

                        create_entity(new_fp_lexical_entry_client_id,
                                      new_fp_lexical_entry_object_id,
                                      field_ids["Translation"][0],
                                      field_ids["Translation"][1],
                                      None,
                                      client,
                                      translation_text,
                                      filename=None,
                                      storage=storage,
                                      locale_id=locale_id
                                      )
                        sp_le_ids = (t[1].client_id, t[1].object_id)
                        fp_le_ids = (new_fp_lexical_entry_client_id, new_fp_lexical_entry_object_id)
                        if not (sp_le_ids, fp_le_ids) in links:
                            create_entity(t[1].client_id,
                                          t[1].object_id,
                                          field_ids["Backref"][0],
                                          field_ids["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=new_fp_lexical_entry_client_id,
                                          link_object_id=new_fp_lexical_entry_object_id,
                                          storage=storage,
                                          locale_id=locale_id)

                        if not (fp_le_ids, sp_le_ids) in links:
                            create_entity(new_fp_lexical_entry_client_id,
                                          new_fp_lexical_entry_object_id,
                                          field_ids["Backref"][0],
                                          field_ids["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=t[1].client_id,
                                          link_object_id=t[1].object_id,
                                          storage=storage,
                                          locale_id=locale_id)
                    else:
                        new_fp_lexical_entry_client_id = new_lex_entries[translation_text][0]
                        new_fp_lexical_entry_object_id = new_lex_entries[translation_text][1]
                        sp_le_ids = (t[1].client_id, t[1].object_id)
                        fp_le_ids = (new_fp_lexical_entry_client_id, new_fp_lexical_entry_object_id)
                        if not (sp_le_ids, fp_le_ids) in links:
                            create_entity(t[1].client_id,
                                          t[1].object_id,
                                          field_ids["Backref"][0],
                                          field_ids["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=new_fp_lexical_entry_client_id,
                                          link_object_id=new_fp_lexical_entry_object_id,
                                          storage=storage,
                                          locale_id=locale_id)

                        if not (fp_le_ids, sp_le_ids) in links:
                            create_entity(new_fp_lexical_entry_client_id,
                                          new_fp_lexical_entry_object_id,
                                          field_ids["Backref"][0],
                                          field_ids["Backref"][1],
                                          None,
                                          client,
                                          filename=None,
                                          link_client_id=t[1].client_id,
                                          link_object_id=t[1].object_id,
                                          storage=storage,
                                          locale_id=locale_id)
    task_status.set(10, 100, "Finished", "")






def convert_all(dictionary_client_id,
                dictionary_object_id,
                client_id,
                origin_client_id,
                origin_object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                locale_id,
                task_key,
                cache_kwargs,
                sound_url=None
                ):
    from lingvodoc.cache.caching import initialize_cache
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)
    try:
        convert_five_tiers(
                    dictionary_client_id,
                    dictionary_object_id,
                    client_id,
                    origin_client_id,
                    origin_object_id,
                    sqlalchemy_url,
                    storage,
                    eaf_url,
                    task_status,
                    locale_id,
                    sound_url
                    )
    except Exception as e:
        log.error("Converting failed")
        log.error(e.__traceback__)
        task_status.set(None, -1, "Conversion failed")
        raise
    DBSession.flush()