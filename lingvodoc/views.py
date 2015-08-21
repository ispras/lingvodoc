from pyramid.response import response
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
    Base
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
from pyramid.response import Fileresponse

import os
import datetime
import base64

import time

import keystoneclient.v3 as keystoneclient
import swiftclient.client as swiftclient
import random
import sqlalchemy
from sqlalchemy import create_engine
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
        DBSession.commit()
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
        DBSession.commit()

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

        language = Language(object_id=len(client.languages)+1, client_id=variables['auth'], translation_string = translation_string)
        DBSession.add(language)
        if parent:
            language.parent = parent
        DBSession.commit()
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
        DBSession.commit()
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
        DBSession.commit()
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
        dictionary = Dictionary(object_id=len(client.dictionaries)+1,
                                client_id=variables['auth'],
                                name=name,
                                state='WiP',
                                parent = parent)
        DBSession.add(dictionary)
        editbase = DBSession.query(BaseGroup).filter_by(name='edit')  # TODO: add roles for dictionary instead
        viewbase = DBSession.query(BaseGroup).filter_by(name='view')
        edit = Group(parent = editbase,
                     subject = 'dictionary' + str(dictionary.object_id) + '_' + str(dictionary.client_id)
                     )
        edit.users.append(user)
        DBSession.add(edit)
        view = Group(parent = viewbase,
                     subject = 'dictionary' + str(dictionary.object_id) + '_' + str(dictionary.client_id)
                     )
        view.users.append(user)
        DBSession.add(view)
        DBSession.commit()
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
        DBSession.commit()
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
        DBSession.commit()
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

        perspective = DictionaryPerspective(object_id=len(client.perspectives)+1,
                                client_id=variables['auth'],
                                name=name,
                                state='WiP',
                                parent = parent)
        DBSession.add(perspective)
        editbase = DBSession.query(BaseGroup).filter_by(name='edit')
        viewbase = DBSession.query(BaseGroup).filter_by(name='view')
        edit = Group(parent = editbase,
                     subject = 'perspective' + str(perspective.object_id) + '_' + str(perspective.client_id)
                     )
        edit.users.append(user)
        DBSession.add(edit)
        view = Group(parent = viewbase,
                     subject = 'perspective' + str(perspective.object_id) + '_' + str(perspective.client_id)
                     )
        view.users.append(user)
        DBSession.add(view)
        DBSession.commit()
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


@view_config(route_name = 'dictionaries', renderer = 'json')
def dictionaries_list(request):  # TODO: TODO, also login and perspective fields
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
    # geo coordinates
    response = dict()
    return response




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
