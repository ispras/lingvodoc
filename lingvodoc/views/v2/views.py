from lingvodoc.views.v2.utils import (
    get_user_by_client_id,
    view_field_from_object,
    check_client_id
)
from sqlalchemy.exc import IntegrityError

from pyramid.response import Response
from pyramid.view import view_config
from lingvodoc.models import (
    DBSession,
    Locale,
    TranslationAtom,
    TranslationGist,
    BaseGroup,
    User,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    Field,
    Client,
    Group,
    UserBlobs,
    Language,
    ObjectTOC,
    LexicalEntry,
    Dictionary,
    Entity
)

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_
)
from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.security import authenticated_userid
# from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response
from lingvodoc.exceptions import CommonException

import sys
import multiprocessing

if sys.platform == 'darwin':
    multiprocessing.set_start_method('spawn')

import logging
log = logging.getLogger(__name__)
import json
import requests
from pyramid.request import Request
from time import time
from lingvodoc.schema.query import schema

@view_config(route_name='fix_groups', renderer='json', permission='admin')
def fix_groups(request):
    for dictionary in DBSession.query(Dictionary):
        for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):

            groups = DBSession.query(Group).filter_by(base_group_id=base.id,
                              subject_object_id=dictionary.object_id,
                                                      subject_client_id=dictionary.client_id).all()
            if len(groups) > 1:
                users = list()
                for group in groups:
                    for user in group.users:
                        if user not in users:
                            users.append(user)
                winner = groups[0]
                for user in users:
                    if user not in winner.users:
                        winner.users.append(user)
                for delete_group in groups[1:]:
                    DBSession.delete(delete_group)
    for perspective in DBSession.query(DictionaryPerspective):
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):

            groups = DBSession.query(Group).filter_by(base_group_id=base.id,
                              subject_object_id=perspective.object_id,
                                                      subject_client_id=perspective.client_id).all()
            if len(groups) > 1:
                users = list()
                for group in groups:
                    for user in group.users:
                        if user not in users:
                            users.append(user)
                winner = groups[0]
                for user in users:
                    if user not in winner.users:
                        winner.users.append(user)
                for delete_group in groups[1:]:
                    DBSession.delete(delete_group)

    base_id = 26

    groups = DBSession.query(Group).filter_by(base_group_id=base_id,
                      subject_override = True).all()
    if len(groups) > 1:
        users = list()
        for group in groups:
            for user in group.users:
                if user not in users:
                    users.append(user)
        winner = groups[0]
        for user in users:
            if user not in winner.users:
                winner.users.append(user)
        for delete_group in groups[1:]:
            DBSession.delete(delete_group)

    return {}

@view_config(route_name='testing', renderer='json', permission='admin')
def testing(request):
    return {}

@view_config(route_name='main', renderer='templates/main.pt', request_method='GET')
def main_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    variables = {'client_id': client_id, 'user': user}
    return render_to_response('templates/main.pt', variables, request=request)


@view_config(route_name='all_statuses', renderer='json', request_method='GET')
def all_statuses(request):
    from pyramid.request import Request
    import json

    response = list()
    for status in ['WiP', 'Published', 'Limited access', 'Hidden']:

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': status}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        response.append(resp.json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_locales', renderer='json', request_method='GET')
def all_locales(request):
    response = list()
    locales = DBSession.query(Locale).all()
    for locale in locales:
        locale_json = dict()
        locale_json['shortcut'] = locale.shortcut
        locale_json['intl_name'] = locale.intl_name
        locale_json['created_at'] = locale.created_at
        locale_json['id'] = locale.id
        response.append(locale_json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_locales_desktop', renderer='json', request_method='GET')
def all_locales_desktop(request):
    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'all_locales'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    status = session.get(path)
    if status.status_code == 200:
        request.response.status = HTTPOk.code
        return status.json()
    else:
        # print(status.status_code)
        request.response.status = HTTPInternalServerError.code
        return {'error': 'no connection'}


@view_config(route_name='published_dictionaries_desktop', renderer='json', request_method='POST')
def published_dictionaries_desktop(request):
    req = request.json_body
    req['visible'] = True
    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'published_dictionaries'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)

    cookies = json.loads(request.cookies.get('server_cookies'))
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    status = session.post(path, json=req, cookies=cookies)
    if status.status_code == 200:
        request.response.status = HTTPOk.code
        return status.json()
    else:
        print(status.status_code)
        request.response.status = HTTPInternalServerError.code
        return {'error':'no connection'}


@view_config(route_name='all_perspectives_desktop', renderer='json', request_method='GET')
def all_perspectives_desktop(request):
    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'perspectives'
    published = request.params.get('published', None)
    path += '?visible=true'
    if published:
        path += '&published=true'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    cookies = json.loads(request.cookies.get('server_cookies'))
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    status = session.get(path, cookies=cookies)
    if status.status_code == 200:
        request.response.status = HTTPOk.code
        return status.json()
    else:
        print(status.status_code)
        request.response.status = HTTPInternalServerError.code
        return {'error':'no connection'}


@view_config(route_name='permissions_on_perspectives_desktop', renderer='json', request_method='GET')
def permissions_on_perspectives_desktop(request):

    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'permissions/perspectives'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    cookies = json.loads(request.cookies.get('server_cookies'))
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    status = session.get(path, cookies=cookies)
    server_perms = status.json()
    path = request.route_url('permissions_on_perspectives')
    subreq = Request.blank(path)
    subreq.method = 'GET'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    desktop_perms = resp.json

    def remove_keys(obj, rubbish):
        if isinstance(obj, dict):
            obj = {
                key: remove_keys(value, rubbish)
                for key, value in obj.items()
                if key not in rubbish and value is not None}
        elif isinstance(obj, list):
            obj = [remove_keys(item, rubbish)
                   for item in obj
                   if item not in rubbish]
        return obj

    server_perms.update(desktop_perms)
    return remove_keys(server_perms, ['publish'])



def dict_ids(obj):
    return {"client_id": obj.client_id,
            "object_id": obj.object_id}


@view_config(route_name='corpora_fields', renderer='json', request_method='GET')
def corpora_fields(request):
    response = list()
    data_type_query = DBSession.query(Field) \
        .join(TranslationGist,
              and_(Field.translation_gist_object_id == TranslationGist.object_id,
                   Field.translation_gist_client_id == TranslationGist.client_id)) \
        .join(TranslationGist.translationatom)
    sound_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                         TranslationAtom.content == 'Sound').one()  # todo: a way to find this fields if wwe cannot use one
    markup_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                          TranslationAtom.content == 'Markup').one()
    comment_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                            TranslationAtom.content == 'Comment').one()
    response.append(view_field_from_object(request=request, field=sound_field))
    response[0]['contains'] = [view_field_from_object(request=request, field=markup_field)]
    response.append(view_field_from_object(request=request, field=markup_field))
    response.append(view_field_from_object(request=request, field=comment_field))
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_data_types', renderer='json', request_method='GET')
def all_data_types(request):
    from pyramid.request import Request
    import json

    response = list()
    for data_type in ['Text', 'Image', 'Sound', 'Markup', 'Link', 'Grouping Tag']:

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': data_type}
        # headers = {'Cookie': request.headers['Cookie']}
        # subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        response.append(resp.json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='create_group', renderer='json', request_method='POST', permission='logged_in')  # todo: other permission?
def create_group(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        if not DBSession.query(Group).filter_by(id=req['id']).first():
            group = Group(id=req['id'],
                             base_group_id=req['base_group_id'],
                             subject_client_id=req['subject_client_id'],
                             subject_object_id=req['subject_object_id'])
            DBSession.add(group)
            for user_id in req['users']:
                curr_user = DBSession.query(User).filter_by(id=user_id).first()
                if curr_user not in group.users:
                    group.users.append(curr_user)

        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

@view_config(route_name='create_persp_to_field', renderer='json', request_method='POST', permission='edit')  # todo: other permission?
def create_persp_to_field(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']):
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}


        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']):
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}


        if not DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=req['client_id'], object_id=req['object_id']).first():
            field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                        object_id=req['object_id'],
                                                        parent_client_id=req['parent_client_id'],
                                                        parent_object_id=req['parent_object_id'],
                                                        field_client_id=req['field_client_id'],
                                                        field_object_id=req['field_object_id'],
                                                        self_client_id=req['self_client_id'],
                                                        self_object_id=req['self_object_id'],
                                                        link_client_id=req.get('link_client_id'),
                                                        link_object_id=req.get('link_object_id'),
                                                        position=req['position'])
            DBSession.add(field_object)
        else:
            request.response.status = HTTPBadRequest.code
            return {'error': 'This field already exists'}

        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


#TODO: Remove it
@view_config(route_name='testing_graphene', renderer='json', request_method='POST')
def testing_graphene(request):
    published = request.params.get('published')
    if published is None:
        published = False

    request_string = """
query  perspective{  perspective(id: [630,9])
{id translation tree{id translation dataType}
fields{id translation}
lexicalEntries{id entities{id content fieldType}}
}}
    """
    request_string = request.body.decode("utf-8")
    # result = schema.execute('query  dictionary{ client dictionaries(published: %s){translation status} dictionary(id: [70,4]){id translation}}' % str(published).lower(),
    #                         context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
    #                                        'locale_id': 1,
    #                                        'request': request})
    client_id = request.authenticated_userid
    if not client_id:
        client_id = None
    #user_id =  get_user_by_client_id(authenticated_userid(request))
    # if not client_id:
    #     user_id = None
    # else:
    #     user_id = get_user_by_client_id(client_id).id
    result = schema.execute(request_string,
                           context_value={'client_id': client_id,
                       'locale_id': 2,
                       'request': request})


    # result = schema.execute(
    #     'query  perspective{  perspective(id: [70,5])'
    #     '{id translation '
    #     'lexicalEntries{id entities{id content fieldType}}'
    #     '}}',
    #     context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
    #                    'locale_id': 2,
    #                    'request': request})
    #print(result.data, result.errors, result.invalid)

    if result.invalid:
        return {'errors': [str(e) for e in result.errors]}
    if result.errors:
        return {'errors': [str(e) for e in result.errors]}
    return result.data

conn_err_msg = """\
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to run the "initialize_lingvodoc_db" script
    to initialize your database tables.  Check your virtual
    environment's "bin" directory for this script and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.

After you fix the problem, please restart the Pyramid application to
try it again.
"""