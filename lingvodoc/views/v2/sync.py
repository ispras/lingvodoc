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


def create_nested_content(tmp_resp):
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
    return tmp_resp


def basic_tables_content(user_id = None, client_id=None):
    response = dict()
    for table in [Client, User, BaseGroup, Field, Locale, TranslationAtom, TranslationGist, Group, Language]:
        tmp_resp = [row2dict(entry) for entry in DBSession.query(table)]
        if tmp_resp:
            tmp_resp = create_nested_content(tmp_resp)
        response[table.__tablename__] = tmp_resp
    if not user_id:
        response['user_to_group_association'] = DBSession.query(user_to_group_association).all()
    elif client_id:
        tmp_resp = [row2dict(entry) for entry in DBSession.query(Group).filter_by(subject_client_id=client_id)]
        if tmp_resp:
            tmp_resp = create_nested_content(tmp_resp)
        response['group'] = tmp_resp
        response['user_to_group_association'] = DBSession.query(user_to_group_association)\
            .join(Group).filter(user_to_group_association.c.user_id==user_id, Group.subject_client_id==client_id).all()
    else:
        response['user_to_group_association'] = DBSession.query(user_to_group_association).filter_by(user_id=user_id).all()
    return response


@view_config(route_name='version', renderer='json', request_method='GET')
def check_version(request):
    return {}


@view_config(route_name='check_version', renderer='json', request_method='GET')
def check_version(request):
    # from pyramid.request import Request  # todo: check version
    # settings = request.registry.settings
    # path = settings['desktop']['central_server'] + 'version'
    # session = requests.Session()
    # session.headers.update({'Connection': 'Keep-Alive'})
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    # adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    # session.mount('http://', adapter)
    # status = session.get(path, cookies=cookies)
    # server_version = status.json()
    #
    # path = request.route_url('version')
    # subreq = Request.blank(path)
    # subreq.method = 'GET'
    # subreq.headers = request.headers
    # resp = request.invoke_subrequest(subreq)
    return {}


@view_config(route_name='basic_sync', renderer='json', request_method='POST')
def basic_sync(request):
    import requests
    import transaction

    return_date_time = lambda r: {key: datetime.datetime.fromtimestamp(r[key]) if key == 'created_at' else r[key] for
                                  key in r}
    settings = request.registry.settings
    existing = basic_tables_content()
    # print(existing['locale'])
    path = settings['desktop']['central_server'] + 'sync/basic/server'
    with open('authentication_data.json', 'r') as f:
        cookies = json.loads(f.read())
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    status = session.get(path, cookies=cookies)
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
    # client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    # if not client:
    #     request.response.status = HTTPNotFound.code
    #     return {'error': str("Try to login again")}
    # user = DBSession.query(User).filter_by(id=client.user_id).first()
    # if not user:
    #     request.response.status = HTTPNotFound.code
    #     return {'error': str("Try to login again")}

    for entry in server['user_to_group_association']:
        if not DBSession.query(user_to_group_association).filter_by(user_id=entry[0], group_id=entry[1]).first():
            insertion = user_to_group_association.insert().values(user_id=entry[0], group_id=entry[1])
            DBSession.execute(insertion)
    request.response.status = HTTPOk.code
    return HTTPOk(json_body={})


@view_config(route_name='basic_sync_server', renderer='json', request_method='GET')
def basic_sync_server(request):
    client =DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    if client:
        user =DBSession.query(User).filter_by(id=client.user_id).first()
        return basic_tables_content(user.id)
    request.response.status = HTTPNotFound.code
    return {'error': str("Try to login again")}


@view_config(route_name='basic_sync_desktop', renderer='json', request_method='GET')
def basic_sync_desktop(request):
    client =DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    if client:
        user =DBSession.query(User).filter_by(id=client.user_id).first()
        return basic_tables_content(user.id, client_id=client.id)
    request.response.status = HTTPNotFound.code
    return {'error': str("Try to login again")}


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


def make_request(path, req_type='get', json_data=None, data=None, files = None):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    with open('authentication_data.json', 'r') as f:
        cookies = json.loads(f.read())
    session.mount('http://', adapter)
    if req_type == 'get':
        status = session.get(path, cookies=cookies)
    elif data or files:
        status = session.post(path, cookies=cookies, data = data, files = files)
    elif req_type == 'post':
        status = session.post(path, json=json_data, cookies=cookies)
    else:
        return None
    return status


@view_config(route_name='diff_desk', renderer='json', request_method='POST')
def diff_desk(request):
    import base64
    from lingvodoc.models import categories
    client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    if not client:
        request.response.status = HTTPNotFound.code
        return {'error': str("Try to login again")}
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        request.response.status = HTTPNotFound.code
        return {'error': str("Try to login again")}
    settings = request.registry.settings
    existing = [row2dict(entry) for entry in DBSession.query(ObjectTOC)]
    central_server = settings['desktop']['central_server']
    path = central_server + 'sync/difference/server'
    server = make_request(path, 'post', existing).json()
    language = list()
    dictionary = list()
    perspective = list()
    field = list()
    lexicalentry = list()
    entity = list()
    userblobs = list()
    translationgist = list()
    translationatom = list()
    print(server)
    for entry in server:
        if entry['table_name'] == 'language':
            language.append(entry)
        if entry['table_name'] == 'dictionary':
            dictionary.append(entry)
        if entry['table_name'] == 'dictionaryperspective':
            perspective.append(entry)
        if entry['table_name'] == 'dictionaryperspectivetofield':
            field.append(entry)
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
    for group in DBSession.query(Group).filter_by(subject_client_id=authenticated_userid(request)).all():
        path = central_server + 'group'
        gr_req = row2dict(group)
        gr_req['users']=[user.id]
        status = make_request(path, 'post', gr_req)
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
        desk_json = row2dict(desk_dict)
        desk_json['category'] = categories[desk_json['category']]
        make_request(path, 'post', desk_json)
    for entry in perspective:
        desk_persp = DBSession.query(DictionaryPerspective).filter_by(client_id=entry['client_id'],
                                                                      object_id=entry['object_id']).one()
        path = central_server + 'dictionary/%s/%s/perspective' % (
            desk_persp.parent_client_id, desk_persp.parent_object_id)
        status = make_request(path, 'post', row2dict(desk_persp))
    for entry in field:
        desk_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=entry['client_id'],
                                                           object_id=entry['object_id']).one()
        persp = desk_field.parent
        path = central_server + 'dictionary/%s/%s/perspective/%s/%s/field' % (persp.parent_client_id,
                                                                                      persp.parent_object_id,
                                                                                      persp.client_id,
                                                                                      persp.object_id)
        status = make_request(path, 'post', row2dict(desk_field))
        if status.status_code != 200:
            print(status.status_code)
    for entry in lexicalentry:
        desk_lex = DBSession.query(LexicalEntry).filter_by(client_id=entry['client_id'],
                                                           object_id=entry['object_id']).one()
        persp = desk_lex.parent
        path = central_server + 'dictionary/%s/%s/perspective/%s/%s/lexical_entry' % (persp.parent_client_id,
                                                                                      persp.parent_object_id,
                                                                                      persp.client_id,
                                                                                      persp.object_id)
        status = make_request(path, 'post', row2dict(desk_lex))
        if status.status_code != 200:
            print(status.status_code)
    for entry in entity:
        desk_ent = DBSession.query(Entity).filter_by(client_id=entry['client_id'],
                                                     object_id=entry['object_id']).one()
        lex = desk_ent.parent
        persp = lex.parent
        path = central_server + 'dictionary/%s/%s/perspective/%s/%s/lexical_entry/%s/%s/entity' % (
            persp.parent_client_id,
            persp.parent_object_id,
            persp.client_id,
            persp.object_id,
            lex.client_id,
            lex.object_id)  # todo: normal content upload
        ent_req = row2dict(desk_ent)
        content = desk_ent.content
        filename = None
        if desk_ent.additional_metadata:
            data_type = desk_ent.additional_metadata.get('data_type')
            if data_type:
                data_type = data_type.lower()
                if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
                    full_name = desk_ent.content.split('/')
                    # print(full_name)
                    filename = full_name[len(full_name) - 1]
                    content = make_request(desk_ent.content)
                    if content.status_code != 200:
                        log.error(desk_ent.content)
                        DBSession.rollback()
                        return

                    content = content.content
                    content = base64.urlsafe_b64encode(content)

        ent_req['content'] = content
        ent_req['filename'] = filename
        status = make_request(path, 'post', ent_req)
        if status.status_code != 200:
            print(status.status_code)
    for entry in userblobs:
        desk_blob = DBSession.query(UserBlobs).filter_by(client_id=entry['client_id'],
                                                         object_id=entry['object_id']).one()
        path = central_server + 'blob'  # todo: normal content upload


        data = {'object_id':desk_blob.object_id, 'data_type':desk_blob.data_type}
        files = {'blob':open(desk_blob.real_storage_path, 'rb')}

        status = make_request(path, 'post', data=data, files=files)
        if status.status_code != 200:
            print(status.status_code)
    return


@view_config(route_name='download_all', renderer='json', request_method='POST')
def download_all(request):
    import requests
    import transaction
    from pyramid.request import Request
    path = request.route_url('check_version')
    subreq = Request.blank(path)
    subreq.method = 'GET'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    path = request.route_url('basic_sync')
    subreq = Request.blank(path)
    subreq.method = 'POST'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    path = request.route_url('diff_desk')
    subreq = Request.blank(path)
    subreq.method = 'POST'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    for dict_obj in DBSession.query(Dictionary).all():
        path = request.route_url('download_dictionary')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {"client_id":dict_obj.client_id,
                                                       "object_id":dict_obj.object_id}
        resp = request.invoke_subrequest(subreq)

    path = request.route_url('new_client')
    subreq = Request.blank(path)
    subreq.method = 'POST'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    request.response.status = HTTPOk.code
    return HTTPOk(json_body={})