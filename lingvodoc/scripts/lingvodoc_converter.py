import sqlite3
import re
import sys
import os
import subprocess
import glob
import json

import argparse


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


def construct_basic_metaword(cursor):
    original_word_id = cursor[0]

    req = dict()
    req['entries'] = [{'content': cursor[1]}]
    req['transcriptions'] = [{'content': cursor[3]}]
    req['translations'] = [{'content': cursor[4]}]
    if cursor[5] != "None":
        req['etymology_tags'] = [{'content': cursor[5]}]
    return original_word_id, req



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
    print(add_word_route)

    for sqword in word_traversal:
        original_word_id, req = construct_basic_metaword(sqword)
        create_basic_metaword = session.post(add_word_route, json=req)
        #print(req)
        print(create_basic_metaword.text)

    return

    for sqword in word_traversal:
        if is_word:
            if pgword_id == 0:
                insert_word_in_pg = pgconn.cursor()
                insert_word_in_pg.execute("""INSERT INTO
                                            words
                                            (word, transcription, translation, tag, dictionary_id)
                                            VALUES
                                            (%s, %s, %s, %s, %s)
                                            returning id
                                            """, [word, transcription, translation, etimtag, dict_id])
                pgconn.commit()

                for res in insert_word_in_pg:
                    pgword_id = res[0]
                if pgword_id == 0:
                    words_failed += 1
                else:
                    words_inserted += 1

        if not is_word:
            if pgparadigm_id == 0:
                original_find = sqconn.cursor()
                original_find.execute("""SELECT
                                        word,
                                        transcription,
                                        translation,
                                        etimology_tag
                                        FROM
                                        dictionary
                                        WHERE
                                        id = (?);
                                        """, [regform])
                original_word_tuple = None
                for original_word in original_find:
                    original_word_tuple = [original_word[0],
                                           original_word[1],
                                           original_word[2],
                                           original_word[3]]

                if not original_word_tuple:
                    #print("Minor failure: orphaned paradigm.")
                    words_failed += 1
                    continue

                find_corresponding_word = pgconn.cursor()
                find_corresponding_word.execute("""SELECT
                                                id
                                                FROM
                                                words
                                                WHERE
                                                transcription = (%s)
                                                """, [original_word_tuple[1]])
                originated = 0
                for orig in find_corresponding_word:
                    originated = orig[0]
                if originated == 0:
                    #print ("Minor inconsistency; skip", transcription, regform)
                    words_failed += 1
                    continue

                insert_word_in_pg = pgconn.cursor()
                insert_word_in_pg.execute("""INSERT INTO
                                            paradigms
                                            (word, transcription, translation, word_id)
                                            VALUES
                                            (%s, %s, %s, %s)
                                            returning id
                                            """, [word, transcription, translation, orig])
                pgconn.commit()

                for res in insert_word_in_pg:
                    pgparadigm_id = res[0]
                if pgparadigm_id == 0:
                    words_failed += 1
                else:
                    words_inserted += 1

        attachments_find = sqconn.cursor()
        attachments_find.execute("""SELECT
                                blobid,
                                type,
                                name,
                                description
                                FROM dict_blobs_description
                                WHERE
                                wordid = (?);
                                """, [word_id])

        for attach_description in attachments_find:
            blobid = attach_description[0]
            blobtype = attach_description[1]
            blobname = unicode(attach_description[2])
            blobdescription = unicode(attach_description[3])
            mainblob = ""
            secblob = ""

            if not any([blobid, blobtype, blobname, blobdescription]):
                ##print "Inconsistent blob description, skipping"
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
                mainblob = blobs[0]
                secblob = blobs[1]

            #if is_word:
            if blobtype == 1:
                have_found = False
                check_blob = pgconn.cursor()
                if is_word:
                    check_blob.execute("""SELECT
                                        id
                                        FROM
                                        word_sounds
                                        WHERE
                                        sound_file_name = (%s) AND word_id = (%s)
                                        """, [blobname, pgword_id])
                else:
                    check_blob.execute("""SELECT
                                        id
                                        FROM
                                        paradigm_sounds
                                        WHERE
                                        sound_file_name = (%s) AND paradigm_id = (%s)
                                        """, [blobname, pgparadigm_id])

                for found in check_blob:
                    if found[0]:
                        have_found = True
                if have_found:
                    ##print "We have this blob already"
                    continue
                if blobname == "":
                    continue

                insert_blob = pgconn.cursor()
                if is_word:
                    insert_blob.execute("""INSERT INTO
                                        word_sounds
                                        (word_id,
                                        description,
                                        sound_file_name,
                                        sound_content_type,
                                        sound_file_size)
                                        VALUES
                                        (%s, %s, %s, %s, %s)
                                        RETURNING id
                                        """, [pgword_id, blobdescription, blobname, "sound/wav", len(mainblob)])
                else:
                    insert_blob.execute("""INSERT INTO
                                        paradigm_sounds
                                        (paradigm_id,
                                        description,
                                        sound_file_name,
                                        sound_content_type,
                                        sound_file_size)
                                        VALUES
                                        (%s, %s, %s, %s, %s)
                                        RETURNING id
                                        """, [pgparadigm_id, blobdescription, blobname, "sound/wav", len(mainblob)])
                pgconn.commit()

                pgblobid = 0
                for inserted in insert_blob:
                    pgblobid = inserted[0]

                re.findall('...', str(pgblobid).zfill(9))
                if is_word:
                    base_path = blobs_path + "word_sounds/sounds/" + '/'.join(re.findall('...', str(pgblobid).zfill(9)))
                else:
                    base_path = blobs_path + "paradigm_sounds/sounds/" + '/'.join(re.findall('...', str(pgblobid).zfill(9)))
                write_wav_blob_path = base_path + '/original/'
                write_mp3_blob_path = base_path + '/mp3/'
                if not os.path.exists(write_wav_blob_path):
                    os.makedirs(write_wav_blob_path)
                if not os.path.exists(write_mp3_blob_path):
                    os.makedirs(write_mp3_blob_path)

                write_wav_blob_path += "/" + blobname
                ##print write_wav_blob_path

                with open(write_wav_blob_path, "w") as f:
                    f.write(mainblob)
                f.close()

                mp3blobname = None
                #                    #print blobname
                if os.path.splitext(os.path.basename(blobname))[1] == ".wav":
                    mp3blobname = os.path.splitext(os.path.basename(blobname))[0] + ".mp3"

                if mp3blobname is not None:

                    wav = write_wav_blob_path
                    mp3 = write_mp3_blob_path + mp3blobname
                    cmd = 'lame --preset insane "%s" "%s"' % (wav, mp3)
                    #print cmd
                    DEVNULL = open(os.devnull, 'wb')
                    subprocess.call(cmd, shell=True, stdout=DEVNULL)
            if blobtype == 2:
                have_found = False
                check_blob = pgconn.cursor()
                if is_word:
                    check_blob.execute("""SELECT
                                        id
                                        FROM
                                        word_praats
                                        WHERE
                                        sound_file_name = (%s) AND word_id = (%s)
                                        """, [blobname + ".wav", pgword_id])
                else:
                    check_blob.execute("""SELECT
                                        id
                                        FROM
                                        paradigm_praats
                                        WHERE
                                        sound_file_name = (%s) AND paradigm_id = (%s)
                                        """, [blobname + ".wav", pgparadigm_id])

                for found in check_blob:
                    if found[0]:
                        have_found = True
                if have_found:
                    ##print "We have this blob already"
                    continue
                if blobname == "":
                    continue
                if mainblob is None or secblob is None:
                    #print "Broken markup! ", blobname
                    continue

                insert_blob = pgconn.cursor()
                if is_word:
                    insert_blob.execute("""INSERT INTO
                                        word_praats
                                        (word_id,
                                        description,
                                        sound_file_name,
                                        sound_content_type,
                                        markup_file_name,
                                        markup_content_type,
                                        sound_file_size,
                                        markup_file_size)
                                        VALUES
                                        (%s, %s, %s, %s, %s, %s, %s, %s)
                                        RETURNING id
                                        """, [pgword_id,
                                              blobdescription,
                                              blobname + ".wav",
                                              "sound/wav",
                                              blobname + ".TextGrid",
                                              "markup/praat",
                                              len(mainblob),
                                              len(secblob)])
                else:
                    insert_blob.execute("""INSERT INTO
                                        paradigm_praats
                                        (paradigm_id,
                                        description,
                                        sound_file_name,
                                        sound_content_type,
                                        markup_file_name,
                                        markup_content_type,
                                        sound_file_size,
                                        markup_file_size)
                                        VALUES
                                        (%s, %s, %s, %s, %s, %s, %s, %s)
                                        RETURNING id
                                        """, [pgparadigm_id,
                                              blobdescription,
                                              blobname + ".wav",
                                              "sound/wav",
                                              blobname + ".TextGrid",
                                              "markup/praat",
                                              len(mainblob),
                                              len(secblob)])
                pgconn.commit()

                pgblobid = 0
                for inserted in insert_blob:
                    pgblobid = inserted[0]

                re.findall('...', str(pgblobid).zfill(9))
                if is_word:
                    base_sound_path = blobs_path + "word_praats/sounds/" + '/'.join(re.findall('...', str(pgblobid).zfill(9)))
                    base_markup_path = blobs_path + "word_praats/markups/" + '/'.join(re.findall('...', str(pgblobid).zfill(9)))
                else:
                    base_sound_path = blobs_path + "paradigm_praats/sounds/" + '/'.join(re.findall('...', str(pgblobid).zfill(9)))
                    base_markup_path = blobs_path + "paradigm_praats/markups/" + '/'.join(re.findall('...', str(pgblobid).zfill(9)))
                write_wav_blob_path = base_sound_path + '/original/'
                write_textgrid_blob_path = base_markup_path + '/original/'
                if not os.path.exists(write_wav_blob_path):
                    os.makedirs(write_wav_blob_path)
                if not os.path.exists(write_textgrid_blob_path):
                    os.makedirs(write_textgrid_blob_path)

                write_wav_blob_path += "/" + blobname + ".wav"
                ##print write_wav_blob_path
                with open(write_wav_blob_path, "w") as f:
                    f.write(mainblob)
                f.close()

                write_textgrid_blob_path += "/" + blobname + ".TextGrid"
                #print "Have markup: ", write_textgrid_blob_path
                with open(write_textgrid_blob_path, "w") as f:
                    f.write(secblob)
                f.close()


    #print "SUMMARY:"
    #print "words total: ", words_total
    #print "words inserted: ", words_inserted
    #print "words failed: ", words_failed
    return 0, "convert successful!"


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
