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
    and_,
    or_,
    tuple_
)

import datetime
import logging
import json
import base64
import os
from lingvodoc.models import categories
from lingvodoc.views.v2.utils import add_user_to_group
import datetime
import requests
from sqlalchemy.dialects.postgresql import insert
from lingvodoc.views.v2.delete import (
real_delete_dictionary,
real_delete_translation_gist,
real_delete_language,
real_delete_entity,
real_delete_lexical_entry,
real_delete_object,
real_delete_perspective
)
import urllib
from pdb import set_trace
from lingvodoc.cache.caching import TaskStatus

log = logging.getLogger(__name__)
row2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}
dict2ids = lambda r: {'client_id': r['client_id'], 'object_id': r['object_id']}


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
    path = settings['desktop']['central_server'] + 'sync/basic/server'
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    cookies = json.loads(request.cookies.get('server_cookies'))
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    status = session.get(path, cookies=cookies)
    server = status.json()
    new_entries = list()
    old_langs = dict()
    langs = list()

    # todo: rework diff
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

        if table != Language:
            all_entries = DBSession.query(table).all()
            if hasattr(table, 'client_id'):
                    for entry in all_entries:
                        client_id = str(entry.client_id)
                        object_id = str(entry.object_id)
                        if client_id in curr_server and object_id in curr_server[client_id]:
                            for key, value in list(return_date_time(curr_server[client_id][object_id]).items()):
                                setattr(entry, key, value)
            else:
                for entry in all_entries:
                    id = str(entry.id)
                    if id in curr_server:
                        for key, value in list(return_date_time(curr_server[id]).items()):
                            if key != 'counter' and table != User:
                                setattr(entry, key, value)
            new_entries.extend(all_entries)
        else:
            old_langs = curr_server
    DBSession.flush()
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
    for entry in DBSession.query(Language).all():
        client_id = str(entry.client_id)
        object_id = str(entry.object_id)
        if client_id in curr_server and object_id in old_langs[client_id]:
                for key, value in list(return_date_time(curr_server[client_id][object_id]).items()):
                    setattr(entry, key, value)
    DBSession.bulk_save_objects(new_entries)
    #todo: delete everything marked_for_deletion? but then next time it will download them again and again and again
    #todo: make request to server with existing objecttocs. server will return objecttocs for deletion
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

    existing = [row2dict(entry) for entry in
                DBSession.query(ObjectTOC).filter(ObjectTOC.table_name.in_(['language',
                                                                            'field']))]

    central_server = settings['desktop']['central_server']
    for_deletion = make_request(central_server + 'sync/delete/server', cookies,
                                'post', existing)

    language = list()
    field = list()
    for entry in for_deletion.json():
        if entry['table_name'] == 'language':
            language.append(entry)
        if entry['table_name'] == 'field':
            field.append(entry)

    for entry in language:
        desk_lang = DBSession.query(Language).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_lang:
            real_delete_language(desk_lang, settings)

    for entry in field:
        desk_field = DBSession.query(Field).filter_by(client_id=entry['client_id'],
                                                      object_id=entry['object_id']).first()
        if desk_field:
            real_delete_object(desk_field)


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

    # todo: rework diff
    tmp_list = DBSession.query(ObjectTOC).yield_per(10000).enable_eagerloads(False)
    existing = [row2dict(entry) for entry in tmp_list]
    req = request.json_body
    upload = list()
    existing = [dict2ids(o) for o in existing]
    log.error('before looking through giant list')
    for entry in req:
        if dict2ids(entry) not in existing:
            upload.append(entry)
    log.error('after looking through giant list')
    return upload


@view_config(route_name='diff_group_server', renderer='json', request_method='POST')
def diff_group_server(request):

    # todo: rework diff
    upload = list()
    groups = DBSession.query(Group).all()
    existing = [entry.id for entry in groups]
    req = request.json_body
    for entry in req:
        if entry not in existing:
            upload.append(entry)
    return upload


@view_config(route_name='delete_sync_server', renderer='json', request_method='POST')
def delete_sync_server(request):
    non_existing = [row2dict(entry) for entry in DBSession.query(ObjectTOC).filter_by(marked_for_deletion=True)]
    req = request.json_body
    for_deletion = list()
    non_existing = [dict2ids(o) for o in non_existing]
    for entry in req:
        if dict2ids(entry) in non_existing:
            for_deletion.append(entry)
    return for_deletion


def make_request(path, cookies, req_type='get', json_data=None, data=None, files = None):
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
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
    log.error('in diff_desk')
    error_happened = False
    client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    if not client:
        request.response.status = HTTPNotFound.code
        return {'error': str("Try to login again")}
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        request.response.status = HTTPNotFound.code
        return {'error': str("Try to login again")}
    settings = request.registry.settings
    log.error('before getting objecttoc list in diff_desk')
    existing = [row2dict(entry) for entry in DBSession.query(ObjectTOC)]
    central_server = settings['desktop']['central_server']
    path = central_server + 'sync/difference/server'
    # task_key = None
    req = request.json_body
    task_key = req['task_key']
    task_status = TaskStatus.get_from_cache(task_key)

    #todo: make request to server with existing objecttocs. server will return objecttocs for deletion
    #todo: delete deleted objects

    cookies = json.loads(request.cookies.get('server_cookies'))
    server = make_request(path, cookies, 'post', existing).json()
    task_status.set(3, 20, "Recieved list of objects for uploading", "")
    for_deletion = make_request(central_server + 'sync/delete/server', cookies, 'post', existing)
    task_status.set(4, 25, "Recieved list of objects for deleting", "")
    language = list()
    dictionary = list()
    perspective = list()
    field = list()
    dictionaryperspectivetofield = list()
    lexicalentry = list()
    entity = list()
    userblobs = list()
    translationgist = list()
    translationatom = list()

    # todo: rework diff
    for entry in server:
        if entry['table_name'] == 'language':
            language.append(entry)
        if entry['table_name'] == 'dictionary':
            dictionary.append(entry)
        if entry['table_name'] == 'dictionaryperspective':
            perspective.append(entry)
        if entry['table_name'] == 'dictionaryperspectivetofield':
            dictionaryperspectivetofield.append(entry)
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
        if entry['table_name'] == 'field':
            field.append(entry)
    # todo: batches
    log.error('before uploading in diff_desk')

    groups = list()
    for group in DBSession.query(Group).all():
        groups.append(group.id)

    path = central_server + 'sync/difference/server/group'
    upload_groups = make_request(path, cookies, 'post', groups)
    upload_groups = upload_groups.json()

    for entry in upload_groups:
        group = DBSession.query(Group).filter_by(id=entry).first()
        if group and group.subject_client_id and get_user_by_client_id(group.subject_client_id).id == user.id:
            path = central_server + 'group'
            gr_req = row2dict(group)
            gr_req['users']=[user.id]
            status = make_request(path, cookies, 'post', gr_req)
            if status.status_code != 200:
                request.response.status = HTTPInternalServerError.code
                return {'error': str("internet error 1")}

    task_status.set(5, 30, "Uploaded groups", "")


    for entry in translationgist:
        desk_gist = DBSession.query(TranslationGist).filter_by(client_id=entry['client_id'],
                                                               object_id=entry['object_id']).one()
        path = central_server + 'translationgist'
        status = make_request(path, cookies, 'post', row2dict(desk_gist))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 2")}

    for entry in translationatom:
        desk_atom = DBSession.query(TranslationAtom).filter_by(client_id=entry['client_id'],
                                                               object_id=entry['object_id']).one()
        path = central_server + 'translationatom'
        status = make_request(path, cookies, 'post', row2dict(desk_atom))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 3")}

    task_status.set(6, 35, "Uploaded translations", "")

    for entry in language:
        desk_lang = DBSession.query(Language).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).one()
        path = central_server + 'language'
        status = make_request(path, cookies, 'post', row2dict(desk_lang))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 4")}

    task_status.set(7, 40, "Uploaded languages", "")


    for entry in dictionary:
        desk_dict = DBSession.query(Dictionary).filter_by(client_id=entry['client_id'],
                                                          object_id=entry['object_id']).one()
        path = central_server + 'dictionary'
        desk_json = row2dict(desk_dict)
        desk_json['category'] = categories[desk_json['category']]
        status = make_request(path, cookies, 'post', desk_json)
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 5")}
    task_status.set(8, 45, "Uploaded dictionaries", "")

    for entry in perspective:
        desk_persp = DBSession.query(DictionaryPerspective).filter_by(client_id=entry['client_id'],
                                                                      object_id=entry['object_id']).one()
        path = central_server + 'dictionary/%s/%s/perspective' % (
            desk_persp.parent_client_id, desk_persp.parent_object_id)
        status = make_request(path, cookies, 'post', row2dict(desk_persp))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 6")}
    task_status.set(9, 50, "Uploaded perspectives", "")

    for entry in field:
        desk_field = DBSession.query(Field).filter_by(client_id=entry['client_id'],
                                                           object_id=entry['object_id']).one()
        path = central_server + 'field'
        status = make_request(path, cookies, 'post', row2dict(desk_field))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 7")}

    # set_trace()
    for entry in dictionaryperspectivetofield:
        desk_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=entry['client_id'],
                                                           object_id=entry['object_id']).one()
        # if desk_field.parent_client_id == client.id:
        persp = desk_field.parent
        path = central_server + 'dictionary/%s/%s/perspective/%s/%s/field' % (persp.parent_client_id,
                                                                                      persp.parent_object_id,
                                                                                      persp.client_id,
                                                                                      persp.object_id)
        status = make_request(path, cookies, 'post', row2dict(desk_field))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 8")}
    task_status.set(10, 55, "Uploaded fields", "")

    for entry in lexicalentry:
        desk_lex = DBSession.query(LexicalEntry).filter_by(client_id=entry['client_id'],
                                                           object_id=entry['object_id']).one()
        persp = desk_lex.parent
        path = central_server + 'dictionary/%s/%s/perspective/%s/%s/lexical_entry' % (persp.parent_client_id,
                                                                                      persp.parent_object_id,
                                                                                      persp.client_id,
                                                                                      persp.object_id)
        status = make_request(path, cookies, 'post', row2dict(desk_lex))
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 9")}
    task_status.set(11, 65, "Uploaded lexical entries", "")

    grouping_tags = dict()
    for entry in entity:
        do_not_add = False
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
        changed_content = False
        filename = None
        if desk_ent.additional_metadata:
            tr_atom = DBSession.query(TranslationAtom).join(TranslationGist, and_(
                TranslationAtom.locale_id == 2,
                TranslationAtom.parent_client_id == TranslationGist.client_id,
                TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
                TranslationGist.client_id == Field.data_type_translation_gist_client_id,
                TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
                Field.client_id == desk_ent.field_client_id, Field.object_id == desk_ent.field_object_id).first()
            data_type = tr_atom.content.lower()
            # data_type = desk_ent.additional_metadata.get('data_type')
            if data_type:
                data_type = data_type.lower()
                if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
                    full_name = desk_ent.content.split('/')
                    filename = full_name[len(full_name) - 1]
                    content_resp = make_request(desk_ent.content, cookies)
                    if content_resp.status_code != 200:
                        log.error(desk_ent.content)
                        do_not_add = True
                        error_happened = True
                    else:
                        content = content_resp.content
                        content = base64.urlsafe_b64encode(content)
                        changed_content = True

        # if ent_req['content']:   # todo: find out, why if content is failing
        #     ent_req['content'] = urllib.parse.quote(content, safe = '/:')
        if changed_content:
            # ent_req['content'] = urllib.parse.quote(content)
            ent_req['content'] = content
        ent_req['filename'] = filename
        if desk_ent.field.data_type == 'Grouping Tag':
            field_ids = str(desk_ent.field.client_id) + '_' + str(desk_ent.field.object_id)
            if field_ids not in grouping_tags:
                grouping_tags[field_ids] = {'field_client_id': desk_ent.field.client_id,
                                            'field_object_id': desk_ent.field.object_id,
                                            'tag_groups': dict()}
            if desk_ent.content not in grouping_tags[field_ids]['tag_groups']:
                grouping_tags[field_ids]['tag_groups'][desk_ent.content] = [row2dict(desk_ent)]
            else:
                grouping_tags[field_ids]['tag_groups'][desk_ent.content].append(row2dict(desk_ent))
        else:
            if not do_not_add:
                status = make_request(path, cookies, 'post', ent_req)
                if status.status_code != 200:
                    set_trace()
                    error_happened = True
                    # request.response.status = HTTPInternalServerError.code
                    # return {'error': str("internet error 11")}
    task_status.set(12, 80, "Uploaded entities", "")
    for entry in grouping_tags:
        path = central_server + 'group_entity/bulk'
        req = grouping_tags[entry]
        req['counter'] = client.counter
        status = make_request(path, cookies, 'post', req)
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 42")}
        client.counter = status.json()['counter']
        DBSession.flush()
    task_status.set(13, 80, "Uploaded etymology", "")
    for entry in userblobs:
        desk_blob = DBSession.query(UserBlobs).filter_by(client_id=entry['client_id'],
                                                         object_id=entry['object_id']).one()
        path = central_server + 'blob'
        data = {'object_id': desk_blob.object_id, 'data_type': desk_blob.data_type, 'client_id': desk_blob.client_id}
        files = {'blob': open(desk_blob.real_storage_path, 'rb')}

        status = make_request(path, cookies, 'post', data=data, files=files)
        if status.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': str("internet error 12")}
    task_status.set(14, 85, "Uploaded userblobs", "")

    log.error('before deletion in diff_desk')
    language = list()
    dictionary = list()
    perspective = list()
    field = list()
    dictionaryperspectivetofield = list()
    lexicalentry = list()
    entity = list()
    for entry in for_deletion.json():
        if entry['table_name'] == 'language':
            language.append(entry)
        if entry['table_name'] == 'dictionary':
            dictionary.append(entry)
        if entry['table_name'] == 'dictionaryperspective':
            perspective.append(entry)
        if entry['table_name'] == 'dictionaryperspectivetofield':
            dictionaryperspectivetofield.append(entry)
        if entry['table_name'] == 'lexicalentry':
            lexicalentry.append(entry)
        if entry['table_name'] == 'entity':
            entity.append(entry)
        if entry['table_name'] == 'field':
            field.append(entry)

    for entry in language:
        desk_lang = DBSession.query(Language).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_lang:
            real_delete_language(desk_lang, settings)

    for entry in dictionary:
        desk_dict = DBSession.query(Dictionary).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_dict:
            real_delete_dictionary(desk_dict, settings)

    for entry in perspective:
        desk_persp = DBSession.query(DictionaryPerspective).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_persp:
            real_delete_perspective(desk_persp, settings)

    for entry in field:
        desk_field = DBSession.query(Field).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_field:
            real_delete_object(desk_field)

    for entry in dictionaryperspectivetofield:
        desk_persp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_persp_field:
            real_delete_object(desk_persp_field)

    for entry in lexicalentry:
        desk_lex = DBSession.query(LexicalEntry).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_lex:
            real_delete_lexical_entry(desk_lex, settings)

    for entry in entity:
        desk_ent = DBSession.query(Entity).filter_by(client_id=entry['client_id'],
                                                        object_id=entry['object_id']).first()
        if desk_ent:
            real_delete_entity(desk_ent, settings)
    if error_happened:
        request.response.status = HTTPInternalServerError.code
        return {'error': str("internet error 43")}
    # task_status.set(15, 85, "Deletion complete", "")

    return


@view_config(route_name='download_all', renderer='json', request_method='POST')
def download_all(request):
    import requests
    import transaction
    from pyramid.request import Request
    print('locking client')
    log.error('locking client')

    DBSession.execute("LOCK TABLE client IN EXCLUSIVE MODE;")
    client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    if not client:
        request.response.status = HTTPNotFound.code
        return {'error': str("Try to login again")}

    client_id = request.authenticated_userid
    user_id = Client.get_user_by_client_id(client_id).id

    task = TaskStatus(user_id, "Synchronisation with server", '', 16)
    task.set(1, 10, "Started", "")
    path = request.route_url('check_version')
    subreq = Request.blank(path)
    subreq.method = 'GET'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    if resp.status_code != 200:
        request.response.status = HTTPInternalServerError.code
        return {'error': 'network error 1'}

    path = request.route_url('basic_sync')
    subreq = Request.blank(path)
    subreq.method = 'POST'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    if resp.status_code != 200:
        request.response.status = HTTPInternalServerError.code
        return {'error': 'network error 2'}
    task.set(2, 15, "Basic synchronisation completed", "")

    path = request.route_url('diff_desk')
    subreq = Request.blank(path)
    subreq.method = 'POST'
    subreq.headers = request.headers
    subreq.json = {'task_key': task.key}
    log.error('before diff_desk')
    resp = request.invoke_subrequest(subreq)
    log.error('after diff_desk')
    if resp.status_code != 200:
        request.response.status = HTTPInternalServerError.code
        return {'error': 'network error 3'}
    task.set(15, 95, "All data uploaded to server", "")

    for dict_obj in DBSession.query(Dictionary).all():
        path = request.route_url('download_dictionary')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {"client_id": dict_obj.client_id,
                       "object_id": dict_obj.object_id}
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': 'network error 4'}

    path = request.route_url('new_client')
    subreq = Request.blank(path)
    subreq.method = 'POST'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    if resp.status_code != 200:
        request.response.status = HTTPInternalServerError.code
        return {'error': 'network error 5'}
    else:
        cookies = resp.json['server_cookies']
        # client_id = cookies['client_id']
        client_id = resp.json['client_id']
        headers = remember(request, principal=client_id, max_age=315360000)
        response = Response()
        response.headers = headers
        locale_id = cookies['locale_id']
        response.set_cookie(key='locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650))
        response.set_cookie(key='client_id', value=str(client_id), max_age=datetime.timedelta(days=3650))
        response.set_cookie(key='server_cookies', value=json.dumps(cookies), max_age=datetime.timedelta(days=3650))
        result = dict()
        result['client_id'] = client_id

        path = request.route_url('basic_sync')
        subreq = Request.blank(path)
        subreq.method = 'POST'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        if resp.status_code != 200:
            request.response.status = HTTPInternalServerError.code
            return {'error': 'network error 2'}
        task.set(16, 100, "Synchronisation complete (New data still can be downloading from server, look a other tasks)", "")

        request.response.status = HTTPOk.code

        return HTTPOk(headers=response.headers, json_body=result)

        # request.response.status = HTTPOk.code
        # return HTTPOk(json_body={})
