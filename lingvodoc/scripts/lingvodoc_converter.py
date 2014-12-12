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
            sound['content'] = base64.urlsafe_b64encode(blobs[0])
#            if blobs[1] and blobs[1] != 'None':
#                print('markup')
#                sound['markups'] = [{'content': str(blobs[1])}]

        sounds.append(sound)
    # TODO: fix this hack
    return [sounds[0]]


def construct_basic_metaword(sqconn, cursor):
    original_word_id = cursor[0]

    req = dict()
    req['entries'] = [{'content': cursor[1]}]
    req['transcriptions'] = [{'content': cursor[3]}]
    req['translations'] = [{'content': cursor[4]}]
    if cursor[5] != "None":
        req['etymology_tags'] = [{'content': cursor[5]}]
    req['sounds'] = construct_sound(sqconn, original_word_id)

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
    for sqword in word_traversal:
            original_word_id, req = construct_basic_metaword(sqconn, sqword)
            words_list.append(req)
    print (len(words_list))
    result = session.post(add_word_route, json={"metawords": words_list})


            #print(req)
    #        print(create_basic_metaword.tex
    metaword = json.loads(result.text)
    import pprint
    p = pprint.PrettyPrinter()
    p.pprint(metaword)

            # add_paradigm_route = add_word_route + \
            #                      str(metaword['metaword_client_id']) + '/' + \
            #                      str(metaword['metaword_id']) + '/' + 'metaparadigms'
            #
            # paradigm_traversal = sqconn.cursor()
            # paradigm_traversal.execute("""SELECT
            #                         id,
            #                         word,
            #                         regular_form,
            #                         transcription,
            #                         translation,
            #                         etimology_tag,
            #                         is_a_regular_form
            #                         FROM
            #                         dictionary
            #                         WHERE
            #                         regular_form = (?);""", [original_word_id])
            #
            # for sqparadigm in paradigm_traversal:
            #     print ("par")
            #     original_paradigm_id, preq = construct_basic_paradigm(sqconn, sqparadigm)
            #     result = session.post(add_paradigm_route, json=preq)


def get_args():
    parser = argparse.ArgumentParser(description='Dictionary converter for lingvodoc 2.0')
    parser.add_argument('--login', '-l', type=str, required=False, default='demo',
                        help='Choose the IMDG to test')
    parser.add_argument('--password', '-p', type=str, required=False, default='demopass')
    parser.add_argument('--server-url', '-a', type=str, required=False, default='http://localhost:6543/')
    parser.add_argument('--dictionaries-folder', '-i', type=str, required=False, default='/Users/al/Movies/dicts-10.02.2014/')

    opts = parser.parse_args()
    print(opts.__dict__)
    return opts

import requests

if __name__ == '__main__':
    args = get_args()

    session = requests.Session()
    r = session.post(args.server_url+'login', data={'login': args.login, 'password': args.password})

    sqlitefilelist = glob.glob(args.dictionaries_folder + "/*.sqlite")
    print(sqlitefilelist)
    for sqlitefile in sqlitefilelist:
        sqconn = sqlite3.connect(sqlitefile)
        convert_db(sqconn, session, args)
