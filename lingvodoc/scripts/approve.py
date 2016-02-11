import sqlite3
import base64
import requests
import json
import hashlib
import logging


def approve_batch(session, approve_url, entities):
    status = session.patch(approve_url, json={'entities': entities})
    return status


def approve(session, server_url,dictionary_client_id, dictionary_object_id, client_id, object_id):
    from time import time
    start = time()
    connect_url = server_url + 'dictionary/%s/%s/perspective/%s/%s/all_count' % (dictionary_client_id,
                                                                                 dictionary_object_id,
                                                                                 client_id, object_id)
    status = session.get(connect_url)

    count = json.loads(status.text)['count']
    connect_url = server_url + 'dictionary/%s/%s/perspective/%s/%s/all?count=%s' % (dictionary_client_id,
                                                                                 dictionary_object_id,
                                                                                 client_id, object_id,
                                                                                count)
    approve_url = server_url + 'dictionary/%s/%s/perspective/%s/%s/approve' % (dictionary_client_id,
                                                                                 dictionary_object_id,
                                                                                 client_id, object_id)
    perspective = session.get(connect_url)
    perspective = json.loads(perspective.text)
    entities = list()
    for lexicalentry in perspective['lexical_entries']:
        for entity in lexicalentry['contains']:
            if entity['level'] in ['leveloneentity', 'groupingentity']:
                not_publ = True
                if entity.get('contains'):
                    for entity2 in entity['contains']:
                        if 'publ' in entity2['level']:
                            if not entity2['marked_for_deletion']:
                                not_publ = False
                        else:
                            if entity2['level'] == 'leveltwoentity':
                                not_publ_2 = True
                                if entity2.get('contains'):
                                    for entity3 in entity2['contains']:
                                        if 'publ' in entity3['level']:
                                            if not entity3['marked_for_deletion']:
                                                not_publ_2 = False
                                                break
                                    if not_publ_2:
                                        entity2['type'] = entity2['level']
                                        entities += [entity2]
                                        if len(entities) > 100:
                                            approve_batch(session, approve_url, entities)
                                            entities = list()
                if not_publ:
                    entity['type'] = entity['level']
                    entities += [entity]
                    if len(entities) > 100:
                        approve_batch(session, approve_url, entities)
                        entities = list()
    approve_batch(session, approve_url, entities)
    return {'time': time() - start}


def approve_all_outer(login, password_hash, dictionary_client_id, dictionary_object_id,
                      perspective_client_id, perspective_object_id,  server_url="http://localhost:6543/"):
    log = logging.getLogger(__name__)
    log.debug("Starting convert_one")
    log.debug("Creating session")
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=3, pool_maxsize=3, max_retries=3)
    session.mount('http://', adapter)
    log.debug("Going to login")
    login_data = {"login": login, "passwordhash": password_hash}
    log.debug("Login data: " + login_data['login'] + login_data['passwordhash'])
    cookie_set = session.post(server_url + 'cheatlogin', json=login_data)
    log.debug("Login status:" + str(cookie_set.status_code))
    if cookie_set.status_code != 200:
        log.error("Cheat login for conversion was unsuccessful")
        exit(-1)
    try:
        status = approve(session, server_url,
                         dictionary_client_id, dictionary_object_id, perspective_client_id, perspective_object_id)
    except Exception as e:
        log.error("approving failed")
        log.error(e.__traceback__)
        raise
    log.error(status)
    return status
