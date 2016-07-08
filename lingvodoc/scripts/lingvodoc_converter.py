import sqlite3
import base64
import requests
import json
import hashlib
import logging

from lingvodoc.queue.client import QueueClient


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
    log = logging.getLogger(__name__)
    status = session.post(upload_url, json=audio_sequence)
    log.debug(status.text)
    audio_ids_list = json.loads(status.text)
    if markup_sequence:
        for k in range(0, len(audio_ids_list)):
            parent_client_id = audio_ids_list[k]['client_id']
            parent_object_id = audio_ids_list[k]['object_id']
            markup_sequence[k]["parent_client_id"] = parent_client_id
            markup_sequence[k]["parent_object_id"] = parent_object_id
        status = session.post(upload_url, json=markup_sequence)
    log.debug(status.text)


def upload_markup(upload_url, search_url, markup_sequence, session):
    log = logging.getLogger(__name__)
    for entry in markup_sequence:
        audio_hash = entry[0]
        markup_element = entry[1]
        entity_metadata_search = search_url + '&searchstring=%s&searchtype=ound'% audio_hash  # TODO: change ound to sound, when found how to do lowercase like
        status = session.get(entity_metadata_search)
        ents = json.loads(status.text)
        if ents:
            existing_entity = ents[0]
            if existing_entity:
                parent_client_id = existing_entity['client_id']
                parent_object_id = existing_entity['object_id']
                markup_element["parent_client_id"] = parent_client_id
                markup_element["parent_object_id"] = parent_object_id
    new_markup_sequence = [o[1] for o in markup_sequence if o[1].get("parent_client_id")]
    result = [o for o in markup_sequence if o[1].get("parent_client_id") is None]
    status = session.post(upload_url, json=new_markup_sequence)
    log.debug(status.text)
    return result


def upload_audio_simple(session, ids_mapping, sound_and_markup_cursor, upload_url, audio_hashes, entity_types,
                        client_id, is_a_regular_form, locale_id=1):
    audio_sequence = []
    for cursor in sound_and_markup_cursor:
        blob_id = cursor[0]
        audio = cursor[1]
        filename = cursor[2]
        word_id = cursor[3]
        audio_hash = hashlib.sha224(audio).hexdigest()
        if audio_hash not in audio_hashes:
            audio_hashes.add(audio_hash)

            audio_element = {"locale_id": locale_id,
                             "level": "leveloneentity",
                             "data_type": "sound",
                             "filename": filename,
                             "entity_type": entity_types[0],
                             "parent_client_id": ids_mapping[int(word_id)][0],
                             "parent_object_id": ids_mapping[int(word_id)][1],
                             "content": base64.urlsafe_b64encode(audio).decode()}
            if not is_a_regular_form:
                audio_element['additional_metadata'] = json.dumps({"hash": audio_hash,
                                                                   "client_id": client_id,
                                                                   "row_id": cursor[4]})
            else:
                audio_element['additional_metadata'] = json.dumps({"hash":  audio_hash })
            audio_sequence.append(audio_element)
            if len(audio_sequence) > 50:
                upload_audio(upload_url, audio_sequence, None, session)
                audio_sequence = []
    if len(audio_sequence) != 0:
        upload_audio(upload_url, audio_sequence, None, session)
        audio_sequence = []


def upload_audio_with_markup(session, ids_mapping, sound_and_markup_cursor, upload_url, search_url, audio_hashes, markup_hashes,
                             entity_types, client_id, is_a_regular_form, locale_id=1):
    audio_sequence = []
    markup_sequence = []
    markup__without_audio_sequence = []
    for cursor in sound_and_markup_cursor:
        blob_id = cursor[0]
        audio = cursor[1]
        markup = cursor[2]
        common_name = cursor[3]
        word_id = cursor[4]
        if not audio or not markup:
            continue
        audio_hash = hashlib.sha224(audio).hexdigest()
        markup_hash = hashlib.sha224(markup).hexdigest()
        if audio_hash not in audio_hashes:
            audio_hashes.add(audio_hash)
            audio_element = {"locale_id": locale_id,
                             "level": "leveloneentity",
                             "data_type": "sound",
                             "filename": common_name + ".wav",
                             "entity_type": entity_types[0],
                             "parent_client_id": ids_mapping[int(word_id)][0],
                             "parent_object_id": ids_mapping[int(word_id)][1],
                             "content": base64.urlsafe_b64encode(audio).decode()}
            if not is_a_regular_form:
                audio_element['additional_metadata'] = json.dumps({"hash": audio_hash,
                                                                   "client_id": client_id,
                                                                   "row_id": cursor[5]})
            else:
                audio_element['additional_metadata'] = json.dumps({"hash":  audio_hash })
            audio_sequence.append(audio_element)


            markup_hashes.add(markup_hash)
            markup_element = {
                "locale_id": locale_id,
                "level": "leveltwoentity",
                "data_type": "markup",
                "filename": common_name + ".TextGrid",
                "entity_type": entity_types[1],
                # need to set after push "parent_client_id": ids_mapping[int(word_id)][0],
                # need to set after push "parent_object_id": ids_mapping[int(word_id)][1],
                "content": base64.urlsafe_b64encode(markup).decode(),
                "additional_metadata": json.dumps({"hash":  markup_hash})}
            markup_sequence.append(markup_element)
        else:
            if markup_hash not in markup_hashes:

                markup_hashes.add(markup_hash)
                markup_element = {
                    "locale_id": locale_id,
                    "level": "leveltwoentity",
                    "data_type": "markup",
                    "filename": common_name + ".TextGrid",
                    "entity_type": entity_types[1],
                    "content": base64.urlsafe_b64encode(markup).decode(),
                    "additional_metadata": json.dumps({"hash":  markup_hash})}
                markup__without_audio_sequence.append((audio_hash, markup_element))
                if len(markup__without_audio_sequence) > 50:
                    markup__without_audio_sequence = upload_markup(upload_url, search_url,
                                                                   markup__without_audio_sequence, session)

        if len(audio_sequence) > 50:
            upload_audio(upload_url, audio_sequence, markup_sequence, session)
            audio_sequence = []
            markup_sequence = []
            if len(markup__without_audio_sequence) > 50:
                markup__without_audio_sequence = upload_markup(upload_url, search_url,
                                                               markup__without_audio_sequence, session)

    if len(audio_sequence) != 0:
        upload_audio(upload_url, audio_sequence, markup_sequence, session)
        audio_sequence = []
        markup_sequence = []

    if len(markup__without_audio_sequence) != 0:
        markup__without_audio_sequence = upload_markup(upload_url, search_url, markup__without_audio_sequence, session)


#def change_dict_status(session, converting_status_url, status, task_id, progress):
# def change_dict_status(task_id, progress):
#     #session.put(converting_status_url, json={'status': status})
#     QueueClient.update_progress(task_id, progress)


def convert_db_new(sqconn, session, language_client_id, language_object_id, server_url,
                   dictionary_client_id, dictionary_object_id, perspective_client_id, perspective_object_id,
                   locale_id=1, task_id=None):

    log = logging.getLogger(__name__)
    dict_attributes = get_dict_attributes(sqconn)
    if not dictionary_client_id or not dictionary_object_id:
        create_dictionary_request = {"parent_client_id": language_client_id,
                                     "parent_object_id": language_object_id,
                                     "translation": dict_attributes['dictionary_name'],
                                     "translation_string": dict_attributes['dictionary_name']}
        status = session.post(server_url + 'dictionary', json=create_dictionary_request)
        dictionary = json.loads(status.text)
    else:
        dictionary = {'client_id': dictionary_client_id, 'object_id': dictionary_object_id}
    client_id = dictionary['client_id']

    converting_status_url = server_url + 'dictionary/%s/%s/state' % (dictionary['client_id'], dictionary['object_id'])

    # There is no way to move this redefinition because single-task version uses `converting_status_url`
    # which is assigned here
    def async_progress_bar(progress):
        QueueClient.update_progress(task_id, progress)

    def single_progress_bar(progress):
        session.put(converting_status_url, json={'status': 'Converting {0}%'.format(str(progress))})

    change_dict_status = single_progress_bar if task_id is None else async_progress_bar

    change_dict_status(5)
    perspective_create_url = server_url + 'dictionary/%s/%s/perspective' % (
    dictionary['client_id'], dictionary['object_id'])

    if not perspective_client_id or not perspective_object_id:
        create_perspective_request = {"translation": "Этимологический словарь из Lingvodoc 0.98",
                                      "translation_string": "Lingvodoc 0.98 etymology dictionary",
                                      "import_source": "Lingvodoc-0.98",
                                      "import_hash": dict_attributes['dialeqt_id']}

        status = session.post(perspective_create_url, json=create_perspective_request)
        perspective = json.loads(status.text)
    else:
        perspective = {'client_id': perspective_client_id, 'object_id': perspective_object_id}
    converting_perspective_status_url = server_url + 'dictionary/%s/%s/perspective/%s/%s/state' % \
                                                     (dictionary['client_id'], dictionary['object_id'],
                                                      perspective['client_id'], perspective['object_id'])
    change_dict_status(10)

    create_perspective_fields_request = session.get(server_url + 'dictionary/1/1/perspective/1/1/fields')
    perspective_fields_create_url = perspective_create_url + '/%s/%s/fields' % (perspective['client_id'],
                                                                                perspective['object_id'])
    status = session.post(perspective_fields_create_url, json=create_perspective_fields_request.text)

    get_all_ids = sqconn.cursor()
    get_all_ids.execute("select id from dictionary where is_a_regular_form=1")

    create_lexical_entries_url = perspective_create_url + '/%s/%s/lexical_entries' % (
    perspective['client_id'], perspective['object_id'])
    count_cursor = sqconn.cursor()
    count_cursor.execute("select count(*) from dictionary where is_a_regular_form=1")
    words_count = count_cursor.fetchone()[0]
    lexical_entries_create_request = {"count": words_count}
    status = session.post(create_lexical_entries_url, json=lexical_entries_create_request)
    ids_dict = json.loads(status.text)

    ids_mapping = dict()
    i = 0
    for id_cursor in get_all_ids:
        id = id_cursor[0]
        client_id = ids_dict[i]['client_id']
        object_id = ids_dict[i]['object_id']
        ids_mapping[id] = (client_id, object_id)
        i += 1

    create_entities_url = server_url + 'dictionary/%s/%s/perspective/%s/%s/entities' % (dictionary['client_id'],
                                                                                        dictionary['object_id'],
                                                                                        perspective['client_id'],
                                                                                        perspective['object_id'])

    change_dict_status(15)

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
                element['additional_metadata'] = json.dumps({"client_id": client_id, "row_id": ld_cursor[2]})
            push_list.append(element)
        return push_list

    def prepare_and_upload_text_entities(id_column, is_a_regular_form, text_column, entity_type):
        sqcursor = sqconn.cursor()
        if is_a_regular_form:
            sqcursor.execute("select %s,%s from dictionary where is_a_regular_form=1" % (id_column, text_column))
        else:
            sqcursor.execute("select %s,%s,id from dictionary where is_a_regular_form=0" % (id_column, text_column))
        push_list = create_entity_list(ids_mapping, sqcursor, "leveloneentity", 'text', entity_type, is_a_regular_form)
        return session.post(create_entities_url, json=push_list)

    for column_and_type in [("word", "Word"),
                            ("transcription", "Transcription"),
                            ("translation", "Translation")]:
        status = prepare_and_upload_text_entities("id", True, column_and_type[0], column_and_type[1])
        log.debug(status.text)

    for column_and_type in [("word", "Paradigm word"),
                            ("transcription", "Paradigm transcription"),
                            ("translation", "Paradigm translation")]:
        status = prepare_and_upload_text_entities("regular_form", False, column_and_type[0], column_and_type[1])
        log.debug(status.text)

    change_dict_status(35)

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
    markup_hashes = set()


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
    entity_types = ['Sound', 'Praat markup']
    upload_audio_with_markup(session, ids_mapping, sound_and_markup_word_cursor, create_entities_url, search_url,
                             audio_hashes, markup_hashes, entity_types, client_id, True, locale_id)
    log.debug(audio_hashes)

    change_dict_status(45)

    paradigm_sound_and_markup_cursor = sqconn.cursor()
    paradigm_sound_and_markup_cursor.execute("""select blobs.id,
                                                blobs.secblob,
                                                blobs.mainblob,
                                                dict_blobs_description.name,
                                                dictionary.regular_form,
                                                dictionary.id
                                                from blobs, dict_blobs_description, dictionary
                                                where dict_blobs_description.blobid=blobs.id
                                                and dict_blobs_description.wordid=dictionary.id
                                                and dict_blobs_description.type=2
                                                and dictionary.is_a_regular_form=0;""")

    entity_types = ['Paradigm sound', "Paradigm Praat markup"]
    upload_audio_with_markup(session, ids_mapping, paradigm_sound_and_markup_cursor, create_entities_url, search_url,
                             audio_hashes, markup_hashes, entity_types, client_id, False, locale_id)
    log.debug(audio_hashes)

    change_dict_status(60)

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
    upload_audio_simple(session, ids_mapping, simple_word_sound_cursor, create_entities_url, audio_hashes, entity_types,
                        client_id, True, locale_id)

    change_dict_status(70)

    simple_paradigm_sound_cursor = sqconn.cursor()
    simple_paradigm_sound_cursor.execute("""select blobs.id,
                                            blobs.mainblob,
                                            dict_blobs_description.name,
                                            dictionary.regular_form,
                                            dictionary.id
                                            from blobs, dict_blobs_description, dictionary
                                            where dict_blobs_description.blobid=blobs.id
                                            and dict_blobs_description.wordid=dictionary.id
                                            and dict_blobs_description.type=1
                                            and dictionary.is_a_regular_form=0;""")
    entity_types = ['Paradigm sound']
    upload_audio_simple(session, ids_mapping, simple_paradigm_sound_cursor, create_entities_url, audio_hashes,
                        entity_types, client_id, False, locale_id)

    change_dict_status(80)

    connect_url = server_url + 'dictionary/%s/%s/perspective/%s/%s/lexical_entry/connect' % (dictionary['client_id'],
                                                                                             dictionary['object_id'],
                                                                                             perspective['client_id'],
                                                                                             perspective['object_id'])
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
                "connections": [{"client_id": client_id, "object_id": object_id}]}
        status = session.post(connect_url, json=item)
        log.debug(status.text)
    suggestions_url = server_url + 'merge/suggestions'

    suggestions_params = {'threshold': 1.0,
                          'levenstein': 0,
                          'client_id': perspective['client_id'],
                          'object_id': perspective['object_id']}
    status = session.post(suggestions_url, json=suggestions_params)
    for entry in json.loads(status.text):
        if entry['confidence'] >= 1.0:
            first_entry = entry['suggestion'][0]
            second_entry = entry['suggestion'][1]
            lex_move_url = server_url + 'lexical_entry/%d/%d/move' % (second_entry['lexical_entry_client_id'],
                                                                       second_entry['lexical_entry_object_id'])
            move_params = {'client_id': first_entry['lexical_entry_client_id'],
                           'object_id': first_entry['lexical_entry_object_id'],
                           'real_delete': True}
            status = session.patch(lex_move_url, json=move_params)

        else:
            break

    change_dict_status(95)

    change_dict_status(100)
    return dictionary


def convert_one(filename, login, password_hash, language_client_id, language_object_id,
                dictionary_client_id, dictionary_object_id, perspective_client_id, perspective_object_id,
                server_url="http://localhost:6543/", task_id=None):
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    log.debug("Starting convert_one")
    log.debug("Creating session")
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    log.debug("Going to login")
    login_data = {"login": login, "passwordhash": password_hash}
    log.debug("Login data: " + login_data['login'] + login_data['passwordhash'])
    cookie_set = session.post(server_url + 'cheatlogin', json=login_data)
    log.debug("Login status:" + str(cookie_set.status_code))
    if cookie_set.status_code != 200:
        log.error("Cheat login for conversion was unsuccessful")
        exit(-1)
    sqconn = sqlite3.connect(filename)
    log.debug("Connected to sqlite3 database")
    try:
        status = convert_db_new(sqconn, session, language_client_id, language_object_id, server_url,
                                dictionary_client_id, dictionary_object_id, perspective_client_id,
                                perspective_object_id, task_id=task_id)
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
    log.debug("!!!!!!!!!! YOU SHOULD NOT SEE IT !!!!!!!!")
    convert_one(filename="/Users/al/Movies/dicts-current/nenets_kaninski.sqlite", login="",
                password_hash="",
                language_client_id=33, language_object_id=24, server_url="http://lingvodoc.ispras.ru/")
