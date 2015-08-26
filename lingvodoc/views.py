from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy.exc import DBAPIError

from .models import (
    DBSession,
    Dictionary,
    User,
    Client,
    Email,
    Passhash,
    Group,
    BaseGroup,
    Language,
    Locale,
    UITranslationString,
    UserEntitiesTranslationString,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveField,
    LexicalEntry,
    LevelOneEntity,
    LevelTwoEntity,
    GroupingEntity,
    PublishLevelOneEntity,
    PublishGroupingEntity,
    PublishLevelTwoEntity,
    Base,
    Organization
    )

from sqlalchemy.orm import sessionmaker
from pyramid.security import (
    Everyone,
    Allow,
    Deny
    )

from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from sqlalchemy.orm import joinedload, subqueryload, noload, join, joinedload_all

from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict, HTTPInternalServerError
from pyramid.httpexceptions import HTTPUnauthorized
from pyramid.security import authenticated_userid
from pyramid.security import forget
from pyramid.security import remember
from pyramid.view import forbidden_view_config

# from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response
from pyramid.response import FileResponse

import os
import datetime
import base64

import time

import keystoneclient.v3 as keystoneclient
import swiftclient.client as swiftclient
import random
import sqlalchemy
from sqlalchemy import create_engine

from sqlalchemy.inspection import inspect
# import redis


class CommonException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


@view_config(route_name='language', renderer='json', request_method='GET')
def view_language(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).one()
    if language:
        response['parent_client_id'] = language.parent_client_id
        response['parent_object_id'] = language.parent_object_id
        response['client_id'] = language.client_id
        response['object_id'] = language.object_id
        response['translation_string']=language.translation_string
        response['marked_for_deletion']=language.marked_for_deletion
        if language.locale:
            response['locale_exist'] = True
        else:
            response['locale_exist'] = False
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such language in the system")}


@view_config(route_name='language', renderer='json', request_method='PUT')
def edit_language(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    parent_client_id = request.matchdict.get('parent_client_id')
    parent_object_id = request.matchdict.get('parent_object_id')
    translation_string = request.matchdict.get('translation_string')
    language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).one()
    if language:
        language.parent_client_id = parent_client_id
        language.parent_object_id = parent_object_id
        language.translation_string = translation_string
        response['status'] = 200
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such language in the system")}


@view_config(route_name='language', renderer='json', request_method='DELETE')
def delete_language(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).one()
    if language:
        language.marked_for_deletion = True

    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such language in the system")}


@view_config(route_name = 'language', renderer = 'json', request_method = 'POST')
def create_language(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        try:
            parent_client_id = request.POST.getone('parent_client_id')
            parent_object_id = request.POST.getone('parent_object_id')
        except:
            parent_client_id = None
            parent_object_id = None
        translation_string = request.POST.getone('translation_string')

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = None
        if parent_client_id and parent_object_id:
            parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id)

        client.languages += 1
        language = Language(object_id=client.languages, client_id=variables['auth'], translation_string = translation_string)
        DBSession.add(language)
        DBSession.flush()
        if parent:
            language.parent = parent
        request.response.status = HTTPOk.code
        return {'status': request.response.status,
                'object_id': language.object_id,
                'client_id': language.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='dictionary', renderer='json', request_method='GET') # Authors  -- names of users, who can edit?
def view_dictionary(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        response['parent_client_id'] = dictionary.parent_client_id
        response['parent_object_id'] = dictionary.parent_object_id
        response['client_id'] = dictionary.client_id
        response['object_id'] = dictionary.object_id
        response['name'] = dictionary.name
        response['state'] = dictionary.state
        response['marked_for_deletion'] = dictionary.marked_for_deletion
        # response['authors']
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name='dictionary', renderer='json', request_method='PUT')
def edit_dictionary(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    parent_client_id = request.matchdict.get('parent_client_id')
    parent_object_id = request.matchdict.get('parent_object_id')
    name = request.matchdict.get('name')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        dictionary.parent_client_id = parent_client_id
        dictionary.parent_object_id = parent_object_id
        dictionary.name = name
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name='dictionary', renderer='json', request_method='DELETE')
def delete_dictionary(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        dictionary.marked_for_deletion = True
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response

    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary', renderer = 'json', request_method = 'POST')
def create_dictionary(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        parent_client_id = request.POST.getone('parent_client_id')
        parent_object_id = request.POST.getone('parent_object_id')
        name = request.POST.getone('name')

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id)
        client.dictionaries += 1
        dictionary = Dictionary(object_id=client.dictionaries,
                                client_id=variables['auth'],
                                name=name,
                                state='WiP',
                                parent = parent)
        DBSession.add(dictionary)
        DBSession.flush()
        editbase = DBSession.query(BaseGroup).filter_by(name='edit')  # TODO: add roles for dictionary instead
        viewbase = DBSession.query(BaseGroup).filter_by(name='view')
        edit = Group(parent = editbase,
                     subject = 'dictionary' + str(dictionary.object_id) + '_' + str(dictionary.client_id)
                     )
        edit.users.append(user)
        DBSession.add(edit)
        DBSession.flush()
        view = Group(parent = viewbase,
                     subject = 'dictionary' + str(dictionary.object_id) + '_' + str(dictionary.client_id)
                     )
        view.users.append(user)
        DBSession.add(view)
        DBSession.flush()
        request.response.status = HTTPOk.code
        return {'status': request.response.status,
                'object_id': dictionary.object_id,
                'client_id': dictionary.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name = 'dictionary_status', renderer = 'json', request_method = 'GET')
def view_dictionary_status(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        response['client_id'] = dictionary.client_id
        response['object_id'] = dictionary.object_id
        response['state'] = dictionary.state
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary_status', renderer = 'json', request_method = 'PUT')
def edit_dictionary_status(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    state = request.matchdict.get('state')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        response['client_id'] = dictionary.client_id
        response['object_id'] = dictionary.object_id
        response['state'] = dictionary.state
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name='perspective', renderer='json', request_method='GET') # Authors  -- names of users, who can edit?
def view_perspective(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        response['parent_client_id'] = perspective.parent_client_id
        response['parent_object_id'] = perspective.parent_object_id
        response['client_id'] = perspective.client_id
        response['object_id'] = perspective.object_id
        response['name'] = perspective.name  # ?
        response['state'] = perspective.state
        response['marked_for_deletion'] = perspective.marked_for_deletion
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name='perspective', renderer='json', request_method='PUT')
def edit_perspective(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    parent_client_id = request.matchdict.get('dictionary_parent_client_id')
    parent_object_id = request.matchdict.get('dictionary_parent_object_id')
    name = request.matchdict.get('name')
    dictionary = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        dictionary.parent_client_id = parent_client_id
        dictionary.parent_object_id = parent_object_id
        dictionary.name = name
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name='perspective', renderer='json', request_method='DELETE')
def delete_perspective(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    dictionary = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        dictionary.marked_for_deletion = True
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response

    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'perspective', renderer = 'json', request_method = 'POST')
def create_perspective(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        parent_client_id = request.matchdict.get('client_id')
        parent_object_id = request.matchdict.get('object_id')
        name = request.POST.getone('name')

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id)
        client.perspectives += 1
        perspective = DictionaryPerspective(object_id=client.perspectives,
                                client_id=variables['auth'],
                                name=name,
                                state='WiP',
                                parent = parent)
        DBSession.add(perspective)
        DBSession.flush()
        editbase = DBSession.query(BaseGroup).filter_by(name='edit')
        viewbase = DBSession.query(BaseGroup).filter_by(name='view')
        edit = Group(parent = editbase,
                     subject = 'perspective' + str(perspective.object_id) + '_' + str(perspective.client_id)
                     )
        edit.users.append(user)
        DBSession.add(edit)
        DBSession.flush()
        view = Group(parent = viewbase,
                     subject = 'perspective' + str(perspective.object_id) + '_' + str(perspective.client_id)
                     )
        view.users.append(user)
        DBSession.add(view)
        DBSession.flush()
        request.response.status = HTTPOk.code
        return {'status': request.response.status,
                'object_id': perspective.object_id,
                'client_id': perspective.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name = 'perspective_status', renderer = 'json', request_method = 'GET')
def view_perspective_status(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    perspective = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        response['client_id'] = perspective.client_id
        response['object_id'] = perspective.object_id
        response['state'] = perspective.state
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'perspective_status', renderer = 'json', request_method = 'PUT')
def edit_perspective_status(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    state = request.matchdict.get('state')
    perspective = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        response['client_id'] = perspective.client_id
        response['object_id'] = perspective.object_id
        response['state'] = perspective.state
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary_roles', renderer = 'json', request_method = 'GET')
def view_dictionary_roles(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        users = []
        groups = DBSession.query(Group)
        for group in groups:
            perm = group.BaseGroup.name
            name = 'dictionary' + str(object_id) + '_' + str(client_id)
            if name in group.subject:
                for user in group.users:
                    users += [(user.id, perm)]
        response['users'] = users
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary_roles', renderer = 'json', request_method = 'POST')
def edit_dictionary_roles(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    user_id = request.POST.getone('user_id')
    role_name = request.POST.getone('role_name')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        user = DBSession.query(User).filter_by(id=user_id).one()
        if user:
            base = DBSession.query(BaseGroup).filter_by(name=role_name)
            if not base:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such role in the system")}

            groups = base.groups
            for group in groups:
                perm = group.BaseGroup.name
                name = 'dictionary' + str(object_id) + '_' + str(client_id)
                if name in group.subject:
                    group.users.append(user)
                    request.response.status = HTTPOk.code
                    response['status'] = request.response.status
        else:
            request.response.status = HTTPNotFound.code
            return {'status': request.response.status, 'error': str("No such user in the system")}
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary_roles', renderer = 'json', request_method = 'DELETE')
def delete_dictionary_roles(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    user_id = request.DELETE.getone('user_id')
    role_name = request.DELETE.getone('role_name')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    if dictionary:
        user = DBSession.query(User).filter_by(id=user_id).one()
        if user:
            base = DBSession.query(BaseGroup).filter_by(name=role_name)
            if not base:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such role in the system")}

            groups = base.groups
            for group in groups:
                perm = group.BaseGroup.name
                name = 'dictionary' + str(object_id) + '_' + str(client_id)
                if name in group.subject:
                    group.users.remove(user)
                    request.response.status = HTTPOk.code
                    response['status'] = request.response.status
        else:
            request.response.status = HTTPNotFound.code
            return {'status': request.response.status, 'error': str("No such user in the system")}
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'GET')
def view_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        users = []
        groups = DBSession.query(Group)
        for group in groups:
            perm = group.BaseGroup.name
            name = 'perspective' + str(object_id) + '_' + str(client_id)
            if name in group.subject:
                for user in group.users:
                    users += [(user.id, perm)]
        response['users'] = users
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'POST')
def edit_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    user_id = request.POST.getone('user_id')
    role_name = request.POST.getone('role_name')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        user = DBSession.query(User).filter_by(id=user_id).one()
        if user:
            base = DBSession.query(BaseGroup).filter_by(name=role_name)
            if not base:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such role in the system")}

            groups = base.groups
            for group in groups:
                perm = group.BaseGroup.name
                name = 'perspective' + str(object_id) + '_' + str(client_id)
                if name in group.subject:
                    group.users.append(user)
                    request.response.status = HTTPOk.code
                    response['status'] = request.response.status
        else:
            request.response.status = HTTPNotFound.code
            return {'status': request.response.status, 'error': str("No such user in the system")}
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'DELETE')
def delete_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    user_id = request.DELETE.getone('user_id')
    role_name = request.DELETE.getone('role_name')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        user = DBSession.query(User).filter_by(id=user_id).one()
        if user:
            base = DBSession.query(BaseGroup).filter_by(name=role_name)
            if not base:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such role in the system")}

            groups = base.groups
            for group in groups:
                perm = group.BaseGroup.name
                name = 'perspective' + str(object_id) + '_' + str(client_id)
                if name in group.subject:
                    group.users.remove(user)
                    request.response.status = HTTPOk.code
                    response['status'] = request.response.status
        else:
            request.response.status = HTTPNotFound.code
            return {'status': request.response.status, 'error': str("No such user in the system")}
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such perspective in the system")}


@view_config(route_name='signin', renderer='json', request_method='POST')
def signin(request):
    next = request.params.get('next') or request.route_url('home')
    login = request.POST.get('login', '')
    password = request.POST.get('password', '')

    user = DBSession.query(User).filter_by(login=login).first()
    if user and user.check_password(password):
        client = Client(user_id=user.id)
        user.clients.append(client)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, principal=client.id)
        return HTTPFound(location=next, headers=headers)
    return HTTPUnauthorized(location=request.route_url('login'))


def all_languages(language):
    languages = []
    for lang in language.language:
        languages += [lang]
        languages += all_languages(lang)
    return languages


def check_for_client(obj, clients):
    try:
        if obj.client_id in clients:
            return True
    except:
        return False
    for entry in dir(obj):
        if entry in inspect(type(obj)).relationships:
            i = inspect(obj.__class__).relationships[entry]
            if i.direction.name == "ONETOMANY":
                x = getattr(obj, str(entry))
                answer = False
                for xx in x:
                    answer = answer or check_for_client(xx, clients)
                    if answer:
                        break
                return answer
    return False


@view_config(route_name = 'dictionaries', renderer = 'json')
def dictionaries_list(request):
    user_created = None
    try:
        user_created = request.matchdict.get('user_created')
    except:
        pass
    user_participated = None
    try:
        user_participated = request.matchdict.get('user_participated')
    except:
        pass
    organization_participated = None
    try:
        organization_participated = request.matchdict.get('organization_participated')
    except:
        pass
    language = None
    try:
        language = request.matchdict.get('language')
    except:
        pass
    dicts = DBSession.query(Dictionary)
    if user_created:
        clients = DBSession.query(Client.id).filter_by(user_id=user_created).all()
        dicts = dicts.filter(Dictionary.client_id.in_(clients))
    if organization_participated:
        organization = DBSession.query(Organization).filter_by(id=organization_participated).first()
        users = organization.users
        users_id = []
        for user in users:
            users_id += [user.id]
        clients = DBSession.query(Client.id).filter(Client.user_id.in_(users_id)).all()
        dicts = dicts.filter(Dictionary.client_id.in_(clients))
    if language:
        lang = DBSession.query(Language).filter_by(id=language).first()
        langs = all_languages(lang)
        dicts = dicts.filter(Dictionary.parent.in_(langs))
    # add geo coordinates
    if user_participated:
        clients = DBSession.query(Client.id).filter_by(user_id=user_participated).all()

        dictstemp = []
        for dicti in dicts:
            if check_for_client(dicti, clients):
                dictstemp += [dicti]
        dicts = dictstemp

    dictionaries = []
    for dicti in dicts:
        dictionaries += [{'object_id': dicti.object_id, 'client_id': dicti.client_id}]
    response = dict()
    response['dictionaries'] = dictionaries

    return response


@view_config(route_name='perspective_fields', renderer = 'json', request_method='GET')
def view_perspective_fields(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        fields = []
        for field in perspective.dictionaryperspectivefield:
            data = dict()
            if field.level == 'L1E' or field.level == 'GE':
                data['entity_type'] = field.entity_type
                data['data_type'] = field.data_type
                data['state'] = field.state
                if field.dictionaryperspectivefield:
                    contains = []
                    for field2 in field.dictionaryperspectivefield:
                        data2 = dict()
                        data2['entity_type'] = field2.entity_type
                        data2['data_type'] = field2.data_type
                        data2['state'] = field2.state
                        contains += [data2]
                    data['contains'] = contains
                if field.group:
                    data['group'] = field.group
            fields += [data]
        response['fields'] = fields
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such perspective in the system")}


@view_config(route_name='perspective_fields', renderer = 'json', request_method='DELETE')
def delete_perspective_fields(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_object_id')
    cli_id = request.DELETE.get('field_client_id')
    obj_id = request.DELETE.get('field_object_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).one()
    if perspective:
        field = DBSession.query(DictionaryPerspectiveField).filter_by(client_id=cli_id, object_id=obj_id).one()
        if field:
            field.marked_for_deletion = True
        else:
            request.response.status = HTTPNotFound.code
            return {'status': request.response.status, 'error': str("No such field in the system")}
        request.response.status = HTTPOk.code
        response['status'] = request.response.status
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': request.response.status, 'error': str("No such perspective in the system")}


@view_config(route_name='perspective_fields', renderer = 'json', request_method='POST')
def create_perspective_fields(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        parent_client_id = request.matchdict.get('client_id')
        parent_object_id = request.matchdict.get('object_id')
        fields = request.POST.getone('fields')

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=parent_client_id, object_id=parent_object_id)
        for entry in fields:
            client.fields += 1
            field = DictionaryPerspectiveField(object_id=client.fields,
                                    client_id=variables['auth'], entity_type=entry['entity_type'], data_type=entry['data_type'])
            DBSession.add(field)
            DBSession.flush()
            if 'group' in entry:
                field.group = entry['group']
            if 'level'in entry:
                field.level = entry['level']
            else:
                field.level = 'L1E'
            if 'contains' in entry:
                for ent in entry['contains']:
                    client.fields += 1
                    field2 = DictionaryPerspectiveField(object_id=client.fields,
                                                        client_id=variables['auth'],
                                                        entity_type=entry['entity_type'],
                                                        data_type=entry['data_type'],
                                                        level = 'L2E')
                    DBSession.add(field2)
                    DBSession.flush()
                    if 'group' in entry:
                        field.group = entry['group']  # is there need for group on second level?
            request.response.status = HTTPOk.code
            return {'status': request.response.status,
                    'object_id': perspective.object_id,
                    'client_id': perspective.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}

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


def openstack_upload(settings, file, file_name, content_type,  container_name):
    storage = settings['storage']
    authurl = storage['authurl']
    user = storage['user']
    key = storage['key']
    auth_version = storage['auth_version']
    tenant_name = storage['tenant_name']
    conn = swiftclient.Connection(authurl=authurl, user=user, key=key,  auth_version=auth_version,
                                  tenant_name=tenant_name)
    #storageurl = conn.get_auth()[0]
    conn.put_container(container_name)
    obje = conn.put_object(container_name, file_name,
                    contents = file,
                    content_type = content_type)
    #obje = conn.get_object(container_name, file_name)
    return str(obje)


@view_config(route_name='upload', renderer='templates/upload.pt')
def openstack_conn(request):

    if request.method == "POST":
        fil = request.params['file']
        file = fil.file
        file_name = 'acl_improved/' + fil.filename
        openstack_upload(request.registry.settings, file, file_name, 'text/plain', 'testing_python_script')
        url = request.route_url('home')
        return HTTPFound(location=url)
    return dict()


def searchby(reqtype):
    res = []
    engine = create_engine('sqlite:///sqlalchemy_example.db')
    Base.metadata.bind = engine
    DBSession = sessionmaker()
    DBSession.bind = engine
    session = DBSession()
    levonefirst = sqlalchemy.orm.aliased(LevelOneEntity, name="levonefirst")
    levone = sqlalchemy.orm.aliased(LevelOneEntity, name="levone")
    # some = session.query(LexicalEntry, func.min(levonefirst.object_id).label('obj_id')).\
    #     join(levonefirst).\
    #     filter(levonefirst.entity_type == reqtype).\
    #     order_by(my_order('obj_id')).\
    #     group_by(LexicalEntry.object_id)
    # subq = some.subquery()
    # something = session.query(subq.c.object_id, subq.c.obj_id, levone.entity_type, levone.content).\
    #     join(levone).filter(levone.entity_type=='2').\
    #     order_by(my_order('obj_id'))
        # add_column(levone.content).\
        # add_column(levone.entity_type).\
    something = session.query(LexicalEntry.object_id).order_by()
    for ent in something:
        res += [ent]
    return res


@view_config(route_name='testing', renderer = 'string')
def testing(request):
    res = dict()
    engine = create_engine('sqlite:///sqlalchemy_example.db')
    Base.metadata.bind = engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(engine)
    DBSession = sessionmaker()
    DBSession.bind = engine
    session = DBSession()
    types = ['1','2','3','4']
    entries = []
    for i in range(100):
        lex_entr = LexicalEntry(object_id=i, client_id=1)
        entries += [lex_entr]
        session.add(lex_entr)
    # for i in range(100000):
    #     entity = LevelOneEntity(object_id=i, client_id=1, parent=random.choice(entries), entity_type=random.choice(types), content=str(i))
    #     session.add(entity)
    session.commit()
    start = time.time()
    res['result'] = searchby('1')
    end = time.time()
    res['time'] = end-start
    return res
