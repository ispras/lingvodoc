__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Email,
    Group,
    Passhash,
    User,
    Field,
    Locale,
    TranslationAtom,
    TranslationGist,
    user_to_group_association,
    ObjectTOC,
    Language,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    LexicalEntry,
    Entity,
    UserBlobs
)
from lingvodoc.views.v2.utils import (
    get_user_by_client_id
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPNotFound,
    HTTPInternalServerError,
    HTTPOk,
    HTTPUnauthorized
)
from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.security import (
    authenticated_userid,
    forget,
    remember
)
from pyramid.view import view_config

from sqlalchemy import (
    or_,
    tuple_
)

import datetime
import logging
import json
from lingvodoc.views.v2.utils import add_user_to_group

log = logging.getLogger(__name__)
import datetime
import requests
from sqlalchemy.dialects.postgresql import insert

row2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}


def basic_tables_content():
    response = dict()
    for table in [Client, User, BaseGroup, Field, Locale, TranslationAtom, TranslationGist, Group, Language]:
        tmp_resp = [row2dict(entry) for entry in DBSession.query(table)]
        if tmp_resp:
            if 'id' in tmp_resp[0]:
                tmp_resp = {str(o['id']): o for o in tmp_resp}
            else:
                tmp_dict = dict()
                for entry in tmp_resp:
                    if str(entry['client_id']) not in tmp_dict:
                        tmp_dict[str(entry['client_id'])] = {str(entry['object_id']): entry}
                    else:
                        tmp_dict[str(entry['client_id'])][str(entry['object_id'])] = entry
                tmp_resp = tmp_dict
        response[table.__tablename__] = tmp_resp
    response['user_to_group_association'] = DBSession.query(user_to_group_association).all()

    return response


@view_config(route_name='basic_sync', renderer='json', request_method='POST')
def basic_sync(request):
    import requests
    return_date_time = lambda r: {key: datetime.datetime.fromtimestamp(r[key]) if key == 'created_at' else r[key] for
                                  key in r}
    settings = request.registry.settings
    existing = basic_tables_content()
    # print(existing['locale'])
    path = settings['desktop']['central_server'] + 'synchronisation/basic/server'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    status = session.get(path)
    server = status.json()
    new_entries = list()
    langs = list()
    for table in [Locale, User, Client, BaseGroup, TranslationGist, TranslationAtom, Field, Group, Language]:
        curr_server = server[table.__tablename__]
        curr_existing = existing[table.__tablename__]
        curr_old = list()
        if hasattr(table, 'id'):
            for key in curr_server:
                if key in curr_existing:
                    if curr_server[key] != curr_existing[key]:
                        kwargs = return_date_time(curr_server[key])
                        curr_old.append(kwargs)
                else:
                    kwargs = return_date_time(curr_server[key])
                    if table != Language:
                        new_entries.append(table(**kwargs))
                    else:
                        langs.append(table(**kwargs))
        else:
            for client_id in curr_server:
                if client_id in curr_existing:
                    for object_id in curr_server[client_id]:
                        if object_id in curr_existing[client_id]:
                            if curr_server[client_id][object_id] != curr_existing[client_id][object_id]:
                                kwargs = return_date_time(curr_server[client_id][object_id])
                                curr_old.append(kwargs)
                        else:
                            kwargs = return_date_time(curr_server[client_id][object_id])
                            if table != Language:
                                new_entries.append(table(**kwargs))
                            else:
                                langs.append(table(**kwargs))

                else:
                    for object_id in curr_server[client_id]:
                        kwargs = return_date_time(curr_server[client_id][object_id])
                        if table != Language:
                            new_entries.append(table(**kwargs))
                        else:
                            langs.append(table(**kwargs))

        all_entries = DBSession.query(table).all()
        if hasattr(table, 'client_id'):
            for entry in all_entries:
                client_id = str(entry.client_id)
                object_id = str(entry.object_id)
                if client_id in curr_server:
                    if object_id in curr_server[client_id]:
                        for key, value in list(return_date_time(curr_server[client_id][object_id]).items()):
                            setattr(entry, key, value)
        else:
            for entry in all_entries:
                id = str(entry.id)
                if id in curr_server:
                    for key, value in list(return_date_time(curr_server[id]).items()):
                        setattr(entry, key, value)
        new_entries.extend(all_entries)

    parent_langs_ids = DBSession.query(Language.client_id, Language.object_id).all()
    parent_langs = [lang for lang in langs if not lang.parent_client_id]
    parent_langs_ids.extend([(lang.client_id, lang.object_id) for lang in langs if not lang.parent_client_id])
    new_langs = [lang for lang in langs if (lang.client_id, lang.object_id) not in parent_langs_ids]
    while new_langs:
        parent_langs.extend([lang for lang in langs if (
        lang.client_id, lang.object_id) not in parent_langs_ids and (
        lang.parent_client_id, lang.parent_object_id) in parent_langs_ids])
        parent_langs_ids.extend([(lang.client_id, lang.object_id) for lang in langs if (
        lang.client_id, lang.object_id) not in parent_langs_ids and (
        lang.parent_client_id, lang.parent_object_id) in parent_langs_ids])
        new_langs = [lang for lang in langs if (lang.client_id, lang.object_id) not in parent_langs_ids]
    new_entries.extend(parent_langs)

    DBSession.bulk_save_objects(new_entries)
    request.response.status = HTTPOk.code
    return HTTPOk(json_body={})


@view_config(route_name='basic_sync_server', renderer='json', request_method='GET')
def basic_sync_server(request):
    return basic_tables_content()


@view_config(route_name='all_toc', renderer='json', request_method='GET')
def all_toc(request):
    tmp_resp = [row2dict(entry) for entry in DBSession.query(ObjectTOC)]
    return tmp_resp


# @view_config(route_name='sync_dict', renderer='json', request_method='GET')
# def sync_dict(request):
#     tmp_resp = [row2dict(entry) for entry in DBSession.query(ObjectTOC)]
#     return tmp_resp


@view_config(route_name='diff_server', renderer='json', request_method='POST')
def diff_server(request):
    existing = [row2dict(entry) for entry in DBSession.query(ObjectTOC)]
    req = request.json_body
    upload = list()
    for entry in req:
        if entry not in existing:
            upload.append(entry)
    return upload


def make_request(path, req_type='get', json_data=None):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    with open('authentication_data.json', 'r') as f:
        cookies = json.loads(f.read())
    session.mount('http://', adapter)
    if req_type == 'get':
        status = session.get(path, cookies=cookies)
    elif req_type == 'post':
        status = session.post(path, json=json_data, cookies=cookies)
    else:
        return None
    return status


@view_config(route_name='diff_desk', renderer='json', request_method='POST')
def diff_desk(request):
    settings = request.registry.settings
    existing = [row2dict(entry) for entry in DBSession.query(ObjectTOC)]
    central_server = settings['desktop']['central_server']
    path = central_server + 'synchronisation/difference/server'
    server = make_request(path, 'post', existing).json()
    language = list()
    dictionary = list()
    perspective = list()
    lexicalentry = list()
    entity = list()
    userblobs = list()
    translationgist = list()
    translationatom = list()
    for entry in server:
        if entry['table_name'] == 'language':
            language.append(entry)
        if entry['table_name'] == 'dictionary':
            dictionary.append(entry)
        if entry['table_name'] == 'dictionaryperspective':
            perspective.append(entry)
        if entry['table_name'] == 'lexicalentry':
            lexicalentry.append(entry)
        if entry['table_name'] == 'entity':
            entity.append(entry)
        if entry['table_name'] == 'userblobs':
            userblobs.append(entry)
        if entry['table_name'] == 'translationgist':
            translationgist.append(entry)
        if entry['table_name'] == 'translationatom':
            translationatom.append(entry)
    # todo: batches
    for entry in translationgist:
        desk_gist = DBSession.query(TranslationGist).filter_by(client_id=entry['client_id'],
                                                               object_id=entry['object_id']).one()
        path = central_server + 'translationgist'
        make_request(path, 'post', row2dict(desk_gist))
    for entry in translationatom:
        desk_atom = DBSession.query(TranslationAtom).filter_by(client_id=entry['client_id'],
                                                               object_id=entry['object_id']).one()
        path = central_server + 'translationatom'
        make_request(path, 'post', row2dict(desk_atom))
    for entry in language:
        desk_lang = DBSession.query(Language).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).one()
        path = central_server + 'language'
        make_request(path, 'post', row2dict(desk_lang))
    for entry in dictionary:
        desk_dict = DBSession.query(Dictionary).filter_by(client_id=entry['client_id'],
                                                          object_id=entry['object_id']).one()
        path = central_server + 'dictionary'
        make_request(path, 'post', row2dict(desk_dict))
    for entry in perspective:
        desk_persp = DBSession.query(DictionaryPerspective).filter_by(client_id=entry['client_id'],
                                                                      object_id=entry['object_id']).one()
        path = central_server + 'dictionary/%s/%s/perspective' % (
            desk_persp.parent_client_id, desk_persp.parent_object_id)
        make_request(path, 'post', row2dict(desk_persp))
    for entry in lexicalentry:
        desk_lex = DBSession.query(LexicalEntry).filter_by(client_id=entry['client_id'],
                                                           object_id=entry['object_id']).one()
        path = central_server + 'lexical_entry'
        make_request(path, 'post', row2dict(desk_lex))
    for entry in entity:
        desk_ent = DBSession.query(Entity).filter_by(client_id=entry['client_id'],
                                                     object_id=entry['object_id']).one()
        path = central_server + 'lexical_entry/%s/%s/entity'  # todo: normal content upload
        make_request(path, 'post', row2dict(desk_ent))
    for entry in userblobs:
        desk_blob = DBSession.query(UserBlobs).filter_by(client_id=entry['client_id'],
                                                         object_id=entry['object_id']).one()
        path = central_server + 'todo'  # todo: normal content upload
        make_request(path, 'blob_upload', row2dict(desk_blob))
    return
