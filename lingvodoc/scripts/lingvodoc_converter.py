import sqlite3
import re
import sys
import os
import subprocess
import glob
import json

import argparse
import base64
import requests
import json
import hashlib

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

def upload_audio(upload_url, audio_sequence, markup_sequence, session):
    status = session.post(upload_url, json.dumps(audio_sequence))
    print(status.text)
    audio_ids_list = json.loads(status.text)
    if markup_sequence:
        for k in range(0, len(audio_ids_list)):
            parent_client_id = audio_ids_list[k]['client_id']
            parent_object_id = audio_ids_list[k]['object_id']
            markup_sequence[k]["parent_client_id"] = parent_client_id
            markup_sequence[k]["parent_object_id"] = parent_object_id
        status = session.post(upload_url, json.dumps(markup_sequence))
    print(status.text)


def upload_audio_simple(session, ids_mapping, sound_and_markup_cursor, upload_url, audio_hashes, entity_types, locale_id=1):
    audio_sequence = []
    for cursor in sound_and_markup_cursor:
        blob_id = cursor[0]
        audio = cursor[1]
        filename = cursor[2]
        word_id = cursor[3]

        if hashlib.sha224(audio).hexdigest() not in audio_hashes:

            audio_element = {"locale_id": locale_id,
                             "level": "leveloneentity",
                             "data_type": "sound",
                             "filename": filename,
                             "entity_type": entity_types[0],
                             "parent_client_id": ids_mapping[int(word_id)][0],
                             "parent_object_id": ids_mapping[int(word_id)][1],
                             "content": base64.urlsafe_b64encode(audio).decode()}
            audio_sequence.append(audio_element)
            if len(audio_sequence) > 50:
                upload_audio(upload_url, audio_sequence, None, session)
                audio_sequence = []
    if len(audio_sequence) != 0:
        upload_audio(upload_url, audio_sequence, None, session)
        audio_sequence = []


def upload_audio_with_markup(session, ids_mapping, sound_and_markup_cursor, upload_url, audio_hashes, entity_types, locale_id=1):
    audio_sequence = []
    markup_sequence = []
    for cursor in sound_and_markup_cursor:
        blob_id = cursor[0]
        audio = cursor[1]
        markup = cursor[2]
        common_name = cursor[3]
        word_id = cursor[4]
        audio_hashes.add(hashlib.sha224(audio).hexdigest())

        audio_element = {"locale_id": locale_id,
                         "level": "leveloneentity",
                         "data_type": "sound",
                         "filename": common_name + ".wav",
                         "entity_type": entity_types[0],
                         "parent_client_id": ids_mapping[int(word_id)][0],
                         "parent_object_id": ids_mapping[int(word_id)][1],
                         "content": base64.urlsafe_b64encode(audio).decode()}
        audio_sequence.append(audio_element)

        markup_element = {
            "locale_id": locale_id,
            "level": "leveltwoentity",
            "data_type": "markup",
            "filename": common_name + ".TextGrid",
            "entity_type": entity_types[1],
            # need to set after push "parent_client_id": ids_mapping[int(word_id)][0],
            # need to set after push "parent_object_id": ids_mapping[int(word_id)][1],
            "content": base64.urlsafe_b64encode(markup).decode()}
        markup_sequence.append(markup_element)

        if len(audio_sequence) > 50:
            upload_audio(upload_url, audio_sequence, markup_sequence, session)
            audio_sequence = []
            markup_sequence = []

    if len(audio_sequence) != 0:
        upload_audio(upload_url, audio_sequence, markup_sequence, session)
        audio_sequence = []
        markup_sequence = []


def convert_db_new(sqconn, session, language_client_id, language_object_id, locale_id=1):
    dict_attributes = get_dict_attributes(sqconn)
    create_dictionary_request = {"parent_client_id": language_client_id,
                                 "parent_object_id": language_object_id,
                                 "translation": dict_attributes['dictionary_name'],
                                 "name": dict_attributes['dictionary_name']}
    status = session.post('http://localhost:6543/dictionary', data=json.dumps(create_dictionary_request))
    dictionary = json.loads(status.text)
    client_id = dictionary['client_id']

    perspective_create_url = 'http://localhost:6543/dictionary/%s/%s/perspective' % (dictionary['client_id'], dictionary['object_id'])
    create_perspective_request = {"translation": "Этимологический словарь из Lingvodoc 0.97",
                                  "name": "Lingvodoc 0.97 etymology dictionary"}

    status = session.post(perspective_create_url, data=json.dumps(create_perspective_request))
    perspective = json.loads(status.text)

    create_perspective_fields_request = session.get('http://localhost:6543/dictionary/1/1/perspective/1/1/fields')
    perspective_fields_create_url = perspective_create_url + '/%s/%s/fields' % (perspective['client_id'], perspective['object_id'])
    status = session.post(perspective_fields_create_url, data=create_perspective_fields_request)

    get_all_ids = sqconn.cursor()
    get_all_ids.execute("select id from dictionary where is_a_regular_form=1")

    create_lexical_entries_url = perspective_create_url + '/%s/%s/lexical_entries' % (perspective['client_id'], perspective['object_id'])
    count_cursor = sqconn.cursor()
    count_cursor.execute("select count(*) from dictionary where is_a_regular_form=1")
    words_count = count_cursor.fetchone()[0]
    lexical_entries_create_request = json.dumps({"count": words_count})
    status = session.post(create_lexical_entries_url, lexical_entries_create_request)
    ids_dict = json.loads(status.text)

    ids_mapping = dict()
    i = 0
    for id_cursor in get_all_ids:
        id = id_cursor[0]
        client_id = ids_dict[i]['client_id']
        object_id = ids_dict[i]['object_id']
        ids_mapping[id] = (client_id, object_id)
        i += 1

    create_entities_url = 'http://localhost:6543/dictionary/%s/%s/perspective/%s/%s/entities' % (dictionary['client_id'],
                                                                                                 dictionary['object_id'],
                                                                                                 perspective['client_id'],
                                                                                                 perspective['object_id'])

    def create_entity_list(mapping, cursor, level, data_type, entity_type, is_a_regular_form, locale_id=1):
        push_list = []
        for ld_cursor in cursor:
            ld_id = int(ld_cursor[0])
            content = ld_cursor[1]
            parent_client_id = mapping[ld_id][0]
            parent_object_id = mapping[ld_id][1]
            element = {"locale_id": locale_id,
                       "level": level,
                       "data_type": data_type,
                       "entity_type": entity_type,
                       "parent_client_id": parent_client_id,
                       "parent_object_id": parent_object_id,
                       "content": content}
            if not is_a_regular_form:
                element['additional_metadata'] = '{"client_id": %s, "row_id": %s}' % (client_id, ld_cursor[2])
            push_list.append(element)
        return push_list

    def prepare_and_upload_text_entities(id_column, is_a_regular_form, text_column, entity_type):
        sqcursor = sqconn.cursor()
        if is_a_regular_form:
            sqcursor.execute("select %s,%s from dictionary where is_a_regular_form=1" % (id_column, text_column))
        else:
            sqcursor.execute("select %s,%s,id from dictionary where is_a_regular_form=0" % (id_column, text_column))
        push_list = create_entity_list(ids_mapping, sqcursor, "leveloneentity", 'text', entity_type, is_a_regular_form)
        return session.post(create_entities_url, json.dumps(push_list))


    for column_and_type in [("word", "Word"),
                            ("transcription", "Transcription"),
                            ("translation", "Translation")]:
        status = prepare_and_upload_text_entities("id", True, column_and_type[0], column_and_type[1])
        print(status.text)

    for column_and_type in [("word", "Paradigm word"),
                            ("transcription", "Paradigm transcription"),
                            ("translation", "Paradigm translation")]:
        status = prepare_and_upload_text_entities("regular_form", False, column_and_type[0], column_and_type[1])
        print(status.text)


    sound_and_markup_word_cursor = sqconn.cursor()
    sound_and_markup_word_cursor.execute("""select blobs.id,
                                            blobs.secblob,
                                            blobs.mainblob,
                                            dict_blobs_description.name,
                                            dictionary.id
                                            from blobs, dict_blobs_description, dictionary
                                            where dict_blobs_description.blobid=blobs.id
                                            and dict_blobs_description.wordid=dictionary.id
                                            and dict_blobs_description.type=2
                                            and dictionary.is_a_regular_form=1;""")

    audio_hashes = set()
    entity_types = ['Sound', 'Praat markup']
    upload_audio_with_markup(session, ids_mapping, sound_and_markup_word_cursor, create_entities_url, audio_hashes, entity_types, locale_id)
    print(audio_hashes)

    paradigm_sound_and_markup_cursor = sqconn.cursor()
    paradigm_sound_and_markup_cursor.execute("""select blobs.id,
                                                blobs.secblob,
                                                blobs.mainblob,
                                                dict_blobs_description.name,
                                                dictionary.regular_form
                                                from blobs, dict_blobs_description, dictionary
                                                where dict_blobs_description.blobid=blobs.id
                                                and dict_blobs_description.wordid=dictionary.id
                                                and dict_blobs_description.type=2
                                                and dictionary.is_a_regular_form=0;""")

    entity_types = ['Paradigm sound', "Paradigm Praat markup"]
    upload_audio_with_markup(session, ids_mapping, paradigm_sound_and_markup_cursor, create_entities_url, audio_hashes, entity_types, locale_id)
    print(audio_hashes)


    simple_word_sound_cursor = sqconn.cursor()
    simple_word_sound_cursor.execute("""select blobs.id,
                                        blobs.mainblob,
                                        dict_blobs_description.name,
                                        dictionary.id
                                        from blobs, dict_blobs_description, dictionary
                                        where dict_blobs_description.blobid=blobs.id
                                        and dict_blobs_description.wordid=dictionary.id
                                        and dict_blobs_description.type=1
                                        and dictionary.is_a_regular_form=1;""")
    entity_types = ['Sound']
    upload_audio_simple(session, ids_mapping, simple_word_sound_cursor, create_entities_url, audio_hashes, entity_types, locale_id)

    simple_paradigm_sound_cursor = sqconn.cursor()
    simple_paradigm_sound_cursor.execute("""select blobs.id,
                                            blobs.mainblob,
                                            dict_blobs_description.name,
                                            dictionary.regular_form
                                            from blobs, dict_blobs_description, dictionary
                                            where dict_blobs_description.blobid=blobs.id
                                            and dict_blobs_description.wordid=dictionary.id
                                            and dict_blobs_description.type=1
                                            and dictionary.is_a_regular_form=0;""")
    entity_types = ['Paradigm sound']
    upload_audio_simple(session, ids_mapping, simple_paradigm_sound_cursor, create_entities_url, audio_hashes, entity_types, locale_id)

    connect_url = 'http://localhost:6543/dictionary/%s/%s/perspective/%s/%s/connect' % (dictionary['client_id'],
                                                                                        dictionary['object_id'],
                                                                                        perspective['client_id'],
                                                                                        perspective['object_id'])
    etymology_cursor = sqconn.cursor()
    etymology_cursor.execute("""select id, etimology_tag
                                FROM dictionary
                                WHERE etimology_tag NOT NULL; """)
    for cursor in etymology_cursor:
        id = int(cursor[0])
        client_id = ids_mapping[id][0]
        object_id = ids_mapping[id][1]
        item = {"entity_type": "Etymology", "content": cursor[1], "connections": [{"client_id": client_id, "object_id": object_id}]}
        status = session.post(connect_url, json.dumps(item))
        print(status.text)

    return dictionary


def convert_one(filename, login, password_hash, language_client_id, language_object_id):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=4)
    session.mount('http://', adapter)
    cookie_set = session.post('http://localhost:6543/cheatlogin', data={'login': login, 'passwordhash': password_hash})
    sqconn = sqlite3.connect(filename)
    status = convert_db_new(sqconn, session, language_client_id, language_object_id)
    print(status)
    return status

if __name__ == "__main__":
    convert_one(filename="/tmp/userblobs/dialeqt_dictionary/2/2/nenets_kaninski.sqlite", login="admin",
                password_hash="$2a$12$IMhcUHE4AtlP/M7fSg.RrOlVtrsyRteK92dRZpfffDjEMYeopmMdG",
                language_client_id=1, language_object_id=1)