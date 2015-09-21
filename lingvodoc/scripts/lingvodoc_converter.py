import sqlite3
import re
import sys
import os
import subprocess
import glob
import json

import argparse
import base64

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


def construct_sound(sqconn, word_id):
    attachments_find = sqconn.cursor()
    attachments_find.execute("""SELECT
                                blobid,
                                type,
                                name,
                                description
                                FROM dict_blobs_description
                                WHERE
                                wordid = (?)
                                """, [word_id])
    sounds = []
    for attach_description in attachments_find:
        sound = dict()
        blobid = attach_description[0]
        blobtype = attach_description[1]
        sound['name'] = attach_description[2]
        sound['mime'] = 'wav'

        if not any([blobid, blobtype, sound['name']]):
            print("Inconsistent blob description, skipping")
            continue

        # blobtype sound - 1 ; praat - 2
        get_blobs = sqconn.cursor()
        get_blobs.execute("""SELECT
                                mainblob,
                                secblob
                                FROM blobs
                                WHERE id = (?);
                                """, [blobid])
        for blobs in get_blobs:
            if blobs[1] and blobs[1] != 'None':
                sound['content'] = base64.urlsafe_b64encode(blobs[1])
            else:
                sound['content'] = base64.urlsafe_b64encode(blobs[0])

#                print('markup')
#                sound['markups'] = [{'content': str(blobs[1])}]

        sounds.append(sound)
    # TODO: fix this hack
    if sounds:
        return [sounds[0]]
    else:
        return None


def construct_basic_metaword(sqconn, cursor):
    original_word_id = cursor[0]

    req = dict()
    req['entries'] = [{'content': cursor[1]}]
    req['transcriptions'] = [{'content': cursor[3]}]
    req['translations'] = [{'content': cursor[4]}]
    if cursor[5] != "None":
        req['etymology_tags'] = [{'content': cursor[5]}]
    sound = construct_sound(sqconn, original_word_id)
    if sound:
        req['sounds'] = sound

    return original_word_id, req

def construct_basic_paradigm(sqconn, cursor):
    original_paradigm_id = cursor[0]
    req = dict()
    req['entries'] = [{'content': cursor[1]}]
    req['transcriptions'] = [{'content': cursor[3]}]
    req['translations'] = [{'content': cursor[4]}]
    req['sounds'] = construct_sound(sqconn, original_paradigm_id)

    return original_paradigm_id, req

import simplejson

def convert_db(sqconn, session, args):

    req = get_dict_attributes(sqconn)

    create_dictionary = session.post(args.server_url+'create_dictionary', req)
    result = json.loads(create_dictionary.text)
    if 'status' not in result:
        exit(-1)
    if result['status'] != '200 OK':
        exit(-2)

    dictionary_id = result['dictionary_id']
    dictionary_client_id = result['dictionary_client_id']

    word_traversal = sqconn.cursor()
    word_traversal.execute("""SELECT
                            id,
                            word,
                            regular_form,
                            transcription,
                            translation,
                            etimology_tag,
                            is_a_regular_form
                            FROM
                            dictionary
                            WHERE
                            is_a_regular_form=1;""")
    add_word_route = args.server_url + 'dictionaries/' + str(dictionary_client_id) + '/' + str(dictionary_id) + '/metawords/'
#    print(add_word_route)

    words_list = []
    original_word_ids = []

    for sqword in word_traversal:
            original_word_id, req = construct_basic_metaword(sqconn, sqword)
            words_list.append(req)
            original_word_ids.append(original_word_id)
    print (len(words_list))
    result = session.post(add_word_route, json={"metawords": words_list})


            #print(req)
    #        print(create_basic_metaword.tex
    metawords = json.loads(result.text)

    check_paradigms_existance = sqconn.cursor()
    check_paradigms_existance.execute("""SELECT
                            id,
                            word,
                            regular_form,
                            transcription,
                            translation,
                            etimology_tag,
                            is_a_regular_form
                            FROM
                            dictionary
                            WHERE
                            is_a_regular_form=0;""")

    pars_total = 0
    for par in check_paradigms_existance:
        pars_total += 1

    if pars_total > 0:
        zipped_metaword = zip(original_word_ids, metawords['metawords'])
        # import pdb
        # pdb.set_trace()

        for word in zipped_metaword:
            original_word_id = word[0]

            metaword = word[1]

            add_paradigm_route = add_word_route + \
                                 str(metaword['metaword_client_id']) + '/' + \
                                 str(metaword['metaword_id']) + '/' + 'metaparadigms'

            paradigm_traversal = sqconn.cursor()
            paradigm_traversal.execute("""SELECT
                                    id,
                                    word,
                                    regular_form,
                                    transcription,
                                    translation,
                                    etimology_tag,
                                    is_a_regular_form
                                    FROM
                                    dictionary
                                    WHERE
                                    regular_form = (?);""", [original_word_id])

            par_list = []
            for sqparadigm in paradigm_traversal:
                print ("par")
                original_paradigm_id, paradigm_request = construct_basic_paradigm(sqconn, sqparadigm)
                par_list.append(paradigm_request)

            result = session.post(add_paradigm_route, json={"metaparadigms": par_list})



import requests
import json


def create_entity_list(ids_mapping, cursor, level, data_type, entity_type, locale_id=1):
    push_list = []
    for ld_cursor in cursor:
        ld_id = int(ld_cursor[0])
        content = ld_cursor[1]
        parent_client_id = ids_mapping[ld_id][0]
        parent_object_id = ids_mapping[ld_id][1]
        element = {"locale_id": locale_id,
                   "level": level,
                   "data_type": data_type,
                   "entity_type": entity_type,
                   "parent_client_id": parent_client_id,
                   "parent_object_id": parent_object_id,
                   "content": content}
        push_list.append(element)
    return push_list

def convert_db_new(sqconn, session, language_client_id, language_object_id):
    dict_attributes = get_dict_attributes(sqconn)
    create_dictionary_request = {"parent_client_id": language_client_id,
                                 "parent_object_id": language_object_id,
                                 "translation": dict_attributes['dictionary_name'],
                                 "name": dict_attributes['dictionary_name']}
    status = session.post('http://localhost:6543/dictionary', data=json.dumps(create_dictionary_request))
    dictionary = json.loads(status.text)

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

    # print(len(ids_mapping))
    # print(words_count)
    # print(i)

    create_entities_url = 'http://localhost:6543/dictionary/1/1/perspective/1/1/entities'

    def prepare_and_upload_text_entities(id_column, is_a_regular_form, text_column, entity_type):
        sqcursor = sqconn.cursor()
        sqcursor.execute("select %s,%s from dictionary where is_a_regular_form=(?)" % (id_column, text_column),
                         [is_a_regular_form])
        push_list = create_entity_list(ids_mapping, sqcursor, "leveloneentity", 'text', entity_type)
        return session.post(create_entities_url, json.dumps(push_list))

    for column_and_type in [("word", "Word"),
                            ("transcription", "Transcription"),
                            ("translation", "Translation")]:
        status = prepare_and_upload_text_entities("id", 1, column_and_type[0], column_and_type[1])
        print(status.text)

    for column_and_type in [("word", "Paradigm word"),
                            ("transcription", "Paradigm transcription"),
                            ("translation", "Paradigm translation")]:
        status = prepare_and_upload_text_entities("regular_form", 0, column_and_type[0], column_and_type[1])
        print(status.text)
    # word_cursor = sqconn.cursor()
    # word_cursor.execute("select id, word from dictionary where is_a_regular_form=1")
    # push_list = create_entity_list(ids_mapping, word_cursor, 'leveloneentity', 'text', 'Word')
    # status = session.post(create_entities_url, json.dumps(push_list))
    #
    # paradigm_word_cursor = sqconn.cursor()
    # paradigm_word_cursor.execute("select regular_form, word from dictionary where is_a_regular_form=0")
    # push_list = create_entity_list(ids_mapping, paradigm_word_cursor, 'leveloneentity', 'text', 'Paradigm word')
    # status = session.post(create_entities_url, json.dumps(push_list))

    return dictionary


def convert_one(filename, client_id, login, password_hash, language_client_id, language_object_id):
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
    convert_one(filename="/tmp/userblobs/dialeqt_dictionary/2/2/nenets_kaninski.sqlite", client_id=2, login="admin",
                password_hash="$2a$12$IMhcUHE4AtlP/M7fSg.RrOlVtrsyRteK92dRZpfffDjEMYeopmMdG",
                language_client_id=1, language_object_id=1)