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
from pyramid.httpexceptions import (
    HTTPError
)

from lingvodoc.scripts import elan_parser

EAF_TIERS = {
    "literary translation": "Translation of Paradigmatic forms",
    "text": "Transcription of Paradigmatic forms",

    "word": "Word",
    "transcription": "Transcription",
    "translation": "Translation"
}
log = logging.getLogger(__name__)
log.setLevel(logging.WARNING)
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings('error')
    try:
        from pydub import AudioSegment
    except Warning as e:
        log.debug("If you want to use Elan converter under Windows, keep in mind, that the result dictionary won't contain sounds")

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
        .one()
    response = translationgist_contents(translationatom.parent)
    return response

def translation_service_search_all(searchstring):
    translationatom = DBSession.query(TranslationAtom)\
        .join(TranslationGist).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2)\
        .one()
    response = translationgist_contents(translationatom.parent)
    return response

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
            entity.link_client_id = link_client_id
            entity.link_object_id = link_object_id
        except (KeyError, TypeError):
            return {'Error': "The field is of link type. You should provide client_id and object id in the content"}
    else:
        entity.content = content
    entity.publishingentity.accepted = True

    DBSession.add(entity)
    #log.debug(filename)
    return (entity.client_id, entity.object_id)


def convert_five_tiers(
                dictionary_client_id,
                dictionary_object_id,
                user_id,
                origin_client_id,
                origin_object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                sound_url=None
                ):

    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)

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
        with tempfile.NamedTemporaryFile() as temp:
            try:
               sound_file = request.urlopen(sound_url)
            except HTTPError as e:
                return {'error': str(e.read().decode("utf8", 'ignore'))}
            with open(temp.name,'wb') as output:
                output.write(sound_file.read())
            full_audio = AudioSegment.from_wav(temp.name)
            temp.flush()

    field_ids = {}
    with transaction.manager:
        client = DBSession.query(Client).filter_by(id=user_id).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           user_id)
        user = DBSession.query(User).filter_by(id=client.user_id).first()
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
        for name in all_fieldnames:
            data_type_query = DBSession.query(Field) \
                .join(TranslationGist,
                      and_(Field.translation_gist_object_id == TranslationGist.object_id,
                           Field.translation_gist_client_id == TranslationGist.client_id))\
                .join(TranslationGist.translationatom)
            field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                                 TranslationAtom.content == name).one() # todo: a way to find this fields if wwe cannot use one
            field_ids[name] = (field.client_id, field.object_id)
            print(name, (field.client_id, field.object_id))
        fp_structure = [field_ids[x] for x in ("Word", "Transcription", "Translation", "Sound", "Markup", "Etymology", "Backref")]
        sp_structure = [field_ids[x] for x in ("Word of Paradigmatic forms", "Transcription of Paradigmatic forms", "Translation of Paradigmatic forms", "Sounds of Paradigmatic forms", "Paradigm Markup", "Backref")]
        DBSession.flush()
        """
        parent_client_id = gist_client_id
        parent_object_id = gist_object_id

        parent = DBSession.query(TranslationGist).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()

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
        """
        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
        for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
            new_group = Group(parent=base,
                              subject_object_id=dictionary_object_id, subject_client_id=dictionary_client_id)
            if user not in new_group.users:
                new_group.users.append(user)
            DBSession.add(new_group)
            DBSession.flush()


        origin_metadata= {"origin_client_id": origin_client_id,
                              "origin_object_id": origin_object_id
                              }
        resp = translation_service_search_all("Lexical Entries")
        persp_translation_gist_client_id, persp_translation_gist_object_id = resp['client_id'], resp['object_id']
        parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        first_perspective = None
        second_perspective = None
        for perspective in DBSession.query(DictionaryPerspective).filter_by(parent=parent):
            structure = []
            fields = DBSession.query(DictionaryPerspectiveToField)\
                        .filter_by(parent=perspective)\
                        .all()
            DBSession.flush()
            for p_to_field in fields:
                structure.append((p_to_field.field_client_id, p_to_field.field_object_id))

            if structure == fp_structure:
                first_perspective = perspective
            elif structure == sp_structure:
                second_perspective = perspective

            print(structure, fp_structure, structure==fp_structure)
            print(structure, sp_structure, structure==sp_structure)
            structure[:] = []
        print(first_perspective, second_perspective)
        """
        # FIRST PERSPECTIVE
        """


        if first_perspective is not None:
            perspective = first_perspective
        else:
            perspective = DictionaryPerspective(client_id=client.id, ###
                                                state_translation_gist_object_id=state_translation_gist_object_id,
                                                state_translation_gist_client_id=state_translation_gist_client_id,
                                                parent=parent,
                                                # import_source=req.get('import_source'),
                                                # import_hash=req.get('import_hash'),
                                                additional_metadata=origin_metadata,
                                                translation_gist_client_id=persp_translation_gist_client_id,
                                                translation_gist_object_id=persp_translation_gist_object_id
                                                )

            perspective.additional_metadata = origin_metadata
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
        resp = translation_service_search_all("Paradigms")
        persp_translation_gist_client_id, persp_translation_gist_object_id = resp['client_id'], resp['object_id']
        parent = DBSession.query(Dictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        if not parent:
            return {'error': str("No such dictionary in the system")}
        if second_perspective is not None:
            perspective = second_perspective
        else:
            perspective = DictionaryPerspective(client_id=client.id, ### variables['auth']
                                                state_translation_gist_object_id=state_translation_gist_object_id,
                                                state_translation_gist_client_id=state_translation_gist_client_id,
                                                parent=parent,
                                                # import_source=req.get('import_source'),
                                                # import_hash=req.get('import_hash'),
                                                additional_metadata=origin_metadata,
                                                translation_gist_client_id=persp_translation_gist_client_id,
                                                translation_gist_object_id=persp_translation_gist_object_id
                                                )
            perspective.additional_metadata = origin_metadata
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
        sp_field_names = ("Word of Paradigmatic forms", "Transcription of Paradigmatic forms", "Translation of Paradigmatic forms", "Sounds of Paradigmatic forms", "Backref")
        sp_fields_dict = {}
        fields_list = []
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
        link_dict = defaultdict(list)
        dubl = []

        log = logging.getLogger(__name__)
        try:
           eaffile = request.urlopen(eaf_url)
        except HTTPError as e:
            return {'error': str(e.read().decode("utf8", 'ignore'))}
        with tempfile.NamedTemporaryFile() as temp:
            temp.write(eaffile.read())
            converter = elan_parser.Elan(temp.name)
            converter.parse()
            final_dicts = converter.proc()
            temp.flush()

        for phrase in final_dicts:
            perspective = DBSession.query(DictionaryPerspective).\
            filter_by(client_id=second_perspective_client_id, object_id = second_perspective_object_id).first() #sec?
            if not perspective:
                return {'error': str("No such perspective in the system")}
            lexentr = LexicalEntry(client_id=client.id,
                                   parent_object_id=second_perspective_object_id, parent=perspective)
            DBSession.add(lexentr)
            sp_lexical_entry_client_id = lexentr.client_id
            sp_lexical_entry_object_id = lexentr.object_id
            curr_dict = None
            for word_translation in phrase:
                if type(word_translation) is not list:
                    curr_dict = word_translation
                    main_tier_text = " ".join([word_translation[i][1].text for i in word_translation if len(word_translation[i]) > 1 and type(word_translation[i][1].text) is str])
                    if main_tier_text:
                        create_entity(sp_lexical_entry_client_id, sp_lexical_entry_object_id, field_ids["Word of Paradigmatic forms"][0], field_ids["Word of Paradigmatic forms"][1],
                            None, client, main_tier_text, filename=None, storage=storage)
                    if not no_sound:
                        if word.time[1] < len(full_audio):
                            with tempfile.NamedTemporaryFile() as temp:
                                full_audio[ word.time[0]: word.time[1]].export(temp.name, format="wav")
                                audio_slice = temp.read()
                                create_entity(sp_lexical_entry_client_id, sp_lexical_entry_object_id, field_ids["Sounds of Paradigmatic forms"][0], field_ids["Sounds of Paradigmatic forms"][1],
                                    None, client, filename="%s.wav" %(word.index) , folder_name="sound1", content=base64.urlsafe_b64encode(audio_slice).decode(), storage=storage)
                                temp.flush()


                else:
                    word = word_translation[0]
                    tier_name = word.tier
                    new = " ".join([i.text for i in word_translation])
                    create_entity(sp_lexical_entry_client_id, sp_lexical_entry_object_id, field_ids[EAF_TIERS[tier_name]][0], field_ids[EAF_TIERS[tier_name]][1],
                        None, client, new, filename=None, storage=storage)
            for word in curr_dict:
                column = [word] + curr_dict[word]
                cort = reversed(tuple(i.text for i in column))
                if cort in link_dict:
                    fp_lexical_entry_client_id, fp_lexical_entry_object_id = link_dict[cort]
                else:
                    perspective = DBSession.query(DictionaryPerspective).\
                    filter_by(client_id=first_perspective_client_id, object_id = first_perspective_object_id).first()
                    if not perspective:
                        return {'error': str("No such perspective in the system")}
                    lexentr = LexicalEntry(client_id=client.id,
                                           parent_object_id=first_perspective_object_id, parent=perspective)
                    DBSession.add(lexentr)
                    fp_lexical_entry_client_id = lexentr.client_id
                    fp_lexical_entry_object_id = lexentr.object_id
                    create_entity(fp_lexical_entry_client_id, fp_lexical_entry_object_id, field_ids[EAF_TIERS[word.tier]][0], field_ids[EAF_TIERS[word.tier]][1],
                        None, client, word.text, filename=None, storage=storage)

                    link_dict[cort] = (fp_lexical_entry_client_id, fp_lexical_entry_object_id)

                    for other_word in curr_dict[word]:
                        create_entity(fp_lexical_entry_client_id, fp_lexical_entry_object_id, field_ids[EAF_TIERS[other_word.tier]][0], field_ids[EAF_TIERS[other_word.tier]][1],
                            None, client, other_word.text, filename=None, storage=storage)
                    if not no_sound:
                        if word.time[1] < len(full_audio):
                            with tempfile.NamedTemporaryFile() as temp:
                                full_audio[ word.time[0]: word.time[1]].export(temp.name, format="wav")
                                audio_slice = temp.read()
                                create_entity(fp_lexical_entry_client_id, fp_lexical_entry_object_id, field_ids["Sound"][0], field_ids["Sound"][1],
                                    None, client, filename="%s.wav" %(word.index) , folder_name="sound1", content=base64.urlsafe_b64encode(audio_slice).decode(), storage=storage)
                                temp.flush()

                dubl_tuple = ((sp_lexical_entry_client_id, sp_lexical_entry_object_id), (fp_lexical_entry_client_id, fp_lexical_entry_object_id))
                if not  dubl_tuple in dubl:
                    dubl.append(dubl_tuple)
                    create_entity(sp_lexical_entry_client_id, sp_lexical_entry_object_id, field_ids["Backref"][0], field_ids["Backref"][1],
                        None, client, filename=None, link_client_id=fp_lexical_entry_client_id, link_object_id=fp_lexical_entry_object_id, storage=storage)
                    create_entity(fp_lexical_entry_client_id, fp_lexical_entry_object_id, field_ids["Backref"][0], field_ids["Backref"][1],
                        None, client, filename=None, link_client_id=sp_lexical_entry_client_id, link_object_id=sp_lexical_entry_object_id, storage=storage)
    print("done")
    return






def convert_all(dictionary_client_id,
                dictionary_object_id,
                user_id,
                client_id,
                object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                sound_url=None
                ):
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    convert_five_tiers(
                dictionary_client_id,
                dictionary_object_id,
                user_id,
                client_id,
                object_id,
                sqlalchemy_url,
                storage,
                eaf_url,
                sound_url
                )