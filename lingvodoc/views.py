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


def find_by_translation_string(locale_id, translation_string):
        trstr = DBSession.query(UserEntitiesTranslationString).\
            filter_by(locale_id=locale_id, translation_string=translation_string).first()
        if not trstr:
            trstr = DBSession.query(UserEntitiesTranslationString).\
                filter_by(locale_id=1, translation_string=translation_string).first()
        if not trstr:
            return translation_string
        return trstr.translation


def add_translation_to_translation_string(locale_id, translation, translation_string, client_id):
        client = DBSession.query(Client).filter_by(id=client_id).first()
        uets = DBSession.query(UserEntitiesTranslationString).filter_by(locale_id=locale_id,
                                                                        translation_string=translation_string).first()
        if not uets:
            client.uets += 1
            uets = UserEntitiesTranslationString(object_id=client.uets,
                                                 client_id=client.id,
                                                 locale_id=locale_id,
                                                 translation_string=translation_string,
                                                 translation=translation)
            DBSession.add(uets)
            DBSession.flush()
        else:
            uets.translation = translation


def find_locale_id(request):
    try:
        return int(request.cookies['locale_id'])
    except:
        return 1


@view_config(route_name='language', renderer='json', request_method='GET')
def view_language(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).first()
    if language:
        if not language.marked_for_deletion:
            response['parent_client_id'] = language.parent_client_id
            response['parent_object_id'] = language.parent_object_id
            response['client_id'] = language.client_id
            response['object_id'] = language.object_id
            response['translation_string'] = find_by_translation_string(locale_id=find_locale_id(request),
                                                                        translation_string=language.translation_string)
            if language.locale:
                response['locale_exist'] = True
            else:
                response['locale_exist'] = False

            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such language in the system")}


@view_config(route_name='language', renderer='json', request_method='PUT')
def edit_language(request):
    try:
        response = dict()
        client_id = request.matchdict.get('client_id')
        object_id = request.matchdict.get('object_id')
        client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).first()
        if language:
            if not language.marked_for_deletion:
                req = request.json_body
                if 'parent_client_id' in req:
                    language.parent_client_id = req['parent_client_id']
                if 'parent_object_id' in req:
                    language.parent_object_id = req['parent_object_id']
                if 'translation' in req:
                    add_translation_to_translation_string(locale_id=find_locale_id(request),
                                                          translation_string=language.translation_string,
                                                          translation=req['translation'], client_id=client.id)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such language in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': HTTPBadRequest.code, 'error': str(e)}



@view_config(route_name='language', renderer='json', request_method='DELETE')
def delete_language(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).first()
    if language:
        if not language.marked_for_deletion:
            language.marked_for_deletion = True
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such language in the system")}


@view_config(route_name='create_language', renderer='json', request_method='POST')
def create_language(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        try:
            parent_client_id = req['parent_client_id']
            parent_object_id = req['parent_object_id']
        except:
            parent_client_id = None
            parent_object_id = None

        translation_string = req['translation_string']
        translation = req['translation']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = None
        if parent_client_id and parent_object_id:
            parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        add_translation_to_translation_string(locale_id=find_locale_id(request), translation = translation,
                                              translation_string = translation_string, client_id = client.id)
        client.languages += 1
        language = Language(object_id=client.languages, client_id=variables['auth'],
                            translation_string = translation_string)
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
        return {'status': HTTPBadRequest.code, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': HTTPInternalServerError.code, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': HTTPConflict.code, 'error': str(e)}


@view_config(route_name='dictionary', renderer='json', request_method='GET')  # Authors -- names of users, who can edit?
def view_dictionary(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            response['parent_client_id'] = dictionary.parent_client_id
            response['parent_object_id'] = dictionary.parent_object_id
            response['client_id'] = dictionary.client_id
            response['object_id'] = dictionary.object_id
            response['name'] = find_by_translation_string(locale_id=find_locale_id(request),
                                                          translation_string=dictionary.name)
            response['state'] = dictionary.state
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name='dictionary', renderer='json', request_method='PUT')
def edit_dictionary(request):
    try:
        response = dict()
        client_id = request.matchdict.get('client_id')
        object_id = request.matchdict.get('object_id')
        client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if dictionary:
            if not dictionary.marked_for_deletion:
                req = request.json_body
                if 'parent_client_id' in req:
                    dictionary.parent_client_id = req['parent_client_id']
                if 'parent_object_id' in req:
                    dictionary.parent_object_id = req['parent_object_id']
                if 'name_translation' in req:
                    add_translation_to_translation_string(locale_id=find_locale_id(request),
                                                          translation_string=dictionary.name,
                                                          translation=req['name_translation'], client_id=client.id)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response

        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='dictionary', renderer='json', request_method='DELETE')
def delete_dictionary(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            dictionary.marked_for_deletion = True
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name='create_dictionary', renderer='json', request_method='POST')
def create_dictionary(request):
    try:

        variables = {'auth': request.authenticated_userid}
        req = request.json_body
        parent_client_id = req['parent_client_id']
        parent_object_id = req['parent_object_id']
        name = req['name']
        translation = req['translation']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        parent = DBSession.query(Language).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        add_translation_to_translation_string(locale_id=find_locale_id(request), translation=translation,
                                              translation_string=name, client_id=client.id)

        client.dictionaries += 1
        dictionary = Dictionary(object_id=client.dictionaries,
                                client_id=variables['auth'],
                                name=name,
                                state='WiP',
                                parent=parent)
        DBSession.add(dictionary)
        DBSession.flush()
        for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):
            new_group = Group(parent=base,
                              subject='dictionary' + str(dictionary.object_id) + '_' + str(dictionary.client_id))
            new_group.users.append(user)
            DBSession.add(new_group)
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


@view_config(route_name='dictionary_status', renderer='json', request_method='GET')
def view_dictionary_status(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            response['state'] = dictionary.state
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name='dictionary_status', renderer='json', request_method='PUT')
def edit_dictionary_status(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            req = request.json_body
            state = req['state']
            dictionary.state = state
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name='perspective', renderer='json', request_method='GET')
def view_perspective(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}


            response['parent_client_id'] = perspective.parent_client_id
            response['parent_object_id'] = perspective.parent_object_id
            response['client_id'] = perspective.client_id
            response['object_id'] = perspective.object_id
            response['name'] = find_by_translation_string(locale_id=find_locale_id(request),
                                                          translation_string=perspective.name)
            response['state'] = perspective.state
            response['marked_for_deletion'] = perspective.marked_for_deletion
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name='perspective', renderer='json', request_method='PUT')
def edit_perspective(request):
    try:
        response = dict()
        client_id = request.matchdict.get('perspective_client_id')
        object_id = request.matchdict.get('perspective_id')
        client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        parent_client_id = request.matchdict.get('dictionary_client_id')
        parent_object_id = request.matchdict.get('dictionary_object_id')
        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

        perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
        if perspective:
            if not perspective.marked_for_deletion:
                if perspective.parent != parent:
                    request.response.status = HTTPNotFound.code
                    return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
                req = request.json_body
                if 'name_translation' in req:
                    add_translation_to_translation_string(locale_id=find_locale_id(request),
                                                          translation_string=perspective.name,
                                                          translation=req['name_translation'], client_id = client.id)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response
        else:
            request.response.status = HTTPNotFound.code
            return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='perspective', renderer='json', request_method='DELETE')
def delete_perspective(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
            perspective.marked_for_deletion = True
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name = 'create_perspective', renderer = 'json', request_method = 'POST')
def create_perspective(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        parent_client_id = request.matchdict.get('dictionary_client_id')
        parent_object_id = request.matchdict.get('dictionary_object_id')
        req = request.json_body
        name = req['name']
        translation = req['translation']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            request.response.status = HTTPNotFound.code
            return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

        client.perspectives += 1
        add_translation_to_translation_string(locale_id=find_locale_id(request), translation_string=name,
                                              translation=translation, client_id=client.id)
        perspective = DictionaryPerspective(object_id=client.perspectives,
                                client_id=variables['auth'],
                                name=name,
                                state='WiP',
                                parent = parent)
        DBSession.add(perspective)
        DBSession.flush()
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):
            new_group = Group(parent = base,
                     subject = 'perspective' + str(perspective.object_id) + '_' + str(perspective.client_id)
                     )
            new_group.users.append(user)
            DBSession.add(new_group)
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
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
            response['state'] = perspective.state
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_status', renderer = 'json', request_method = 'PUT')
def edit_perspective_status(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('dictionary_client_id')
    parent_object_id = request.matchdict.get('dictionary_object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
            req = request.json_body
            state = req['state']
            perspective.state = state
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name = 'dictionary_roles', renderer = 'json', request_method = 'GET')
def view_dictionary_roles(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            users = []
            groups = DBSession.query(Group).filter_by(subject = 'dictionary' + str(object_id) + '_' + str(client_id))
            roles = dict()
            for group in groups:
                perm = group.BaseGroup.readable_name
                users = []
                for user in group.users:
                    users += [user.id]
                roles[perm] = users
            response['roles'] = roles
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary_roles', renderer = 'json', request_method = 'POST')
def edit_dictionary_roles(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    req = request.json_body
    user_id = req['user_id']
    role_names = req['role_names']
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            user = DBSession.query(User).filter_by(id=user_id).first()
            if user:
                for role_name in role_names:
                    base = DBSession.query(BaseGroup).filter_by(name=role_name).first()
                    if not base:
                        request.response.status = HTTPNotFound.code
                        return {'status': HTTPNotFound.code, 'error': str("No such role in the system")}

                    group = DBSession.query(Group).filter_by(base_group_id = base.id,
                                                             subject = 'dictionary' + str(object_id) + '_' + str(client_id)).first()
                    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
                    userlogged = DBSession.query(User).filter_by(id=client.user_id).first()
                    if userlogged in group.users:
                        group.users.append(user)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response
            else:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such user in the system")}
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'dictionary_roles', renderer = 'json', request_method = 'DELETE')
def delete_dictionary_roles(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    req = request.json_body
    user_id = req['user_id']
    role_names = req['role_names']
    dictionary = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
    if dictionary:
        if not dictionary.marked_for_deletion:
            user = DBSession.query(User).filter_by(id=user_id).first()
            if user:
                for role_name in role_names:
                    base = DBSession.query(BaseGroup).filter_by(name=role_name).first()
                    if not base:
                        request.response.status = HTTPNotFound.code
                        return {'status': HTTPNotFound.code, 'error': str("No such role in the system")}

                    group = DBSession.query(Group).filter_by(base_group_id = base.id,
                                                             subject = 'dictionary' + str(object_id) + '_' + str(client_id)).first()
                    if user in group.users:
                        group.users.remove(user)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response
            else:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such user in the system")}
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'GET')
def view_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
            users = []
            groups = DBSession.query(Group).filter_by(subject = 'perspective' + str(object_id) + '_' + str(client_id))
            roles = dict()
            for group in groups:
                perm = group.BaseGroup.readable_name
                users = []
                for user in group.users:
                    users += [user.id]
                roles[perm] = users
            response['roles'] = roles
            request.response.status = HTTPOk.code
            response['status'] = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'POST')
def edit_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')

    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
            req = request.json_body
            user_id = req['user_id']
            role_names = req['role_names']
            user = DBSession.query(User).filter_by(id=user_id).first()
            if user:
                for role_name in role_names:
                    base = DBSession.query(BaseGroup).filter_by(name=role_name).first()
                    if not base:
                        request.response.status = HTTPNotFound.code
                        return {'status': HTTPNotFound.code, 'error': str("No such role in the system")}

                    group = DBSession.query(Group).filter_by(base_group_id = base.id,
                                                             subject = 'perspective' + str(object_id) + '_' + str(client_id)).first()
                    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
                    userlogged = DBSession.query(User).filter_by(id=client.user_id).first()
                    if userlogged in group.users:
                        group.users.append(user)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response
            else:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such user in the system")}
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name = 'perspective_roles', renderer = 'json', request_method = 'DELETE')
def delete_perspective_roles(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    req = request.json_body
    user_id = req['user_id']
    role_names = req['role_names']
    parent_client_id = request.matchdict.get('client_id')
    parent_object_id = request.matchdict.get('object_id')
    parent = DBSession.query(Dictionary).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
    if not parent:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        if not perspective.marked_for_deletion:
            if perspective.parent != parent:
                request.response.status = HTTPNotFound.code
                return {'status': HTTPNotFound.code, 'error': str("No such pair of dictionary/perspective in the system")}
            req = request.json_body
            user_id = req['user_id']
            role_names = req['role_names']
            user = DBSession.query(User).filter_by(id=user_id).first()
            if user:
                for role_name in role_names:
                    base = DBSession.query(BaseGroup).filter_by(name=role_name).first()
                    if not base:
                        request.response.status = HTTPNotFound.code
                        return {'status': HTTPNotFound.code, 'error': str("No such role in the system")}

                    group = DBSession.query(Group).filter_by(base_group_id = base.id,
                                                             subject = 'perspective' + str(object_id) + '_' + str(client_id)).first()
                    if user in group.users:
                        group.users.remove(user)
                request.response.status = HTTPOk.code
                response['status'] = HTTPOk.code
                return response
            else:
                request.response.status = HTTPNotFound.code
                return {'status': request.response.status, 'error': str("No such user in the system")}
    request.response.status = HTTPNotFound.code
    return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name='signin', renderer='json', request_method='POST')
def signin(request):
    next = request.params.get('next') or request.route_url('home')
    req = request.json_body
    login = req['login']
    password = req['password']
    # login = request.POST.get('login', '')
    # password = request.POST.get('password', '')

    user = DBSession.query(User).filter_by(login=login).first()
    if user and user.check_password(password):
        client = Client(user_id=user.id)
        user.clients.append(client)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, principal=client.id)
        response = Response()
        response.headers = headers
        locale_id = user.default_locale_id
        if not locale_id:
            locale_id = 1
        response.set_cookie(key='locale_id', value=str(locale_id))
        return HTTPFound(location=next, headers=response.headers)
    return HTTPUnauthorized(location=request.route_url('login'))


def all_languages(lang):
    langs = [(lang.object_id, lang.client_id)]
    for la in lang.language:
        langs += all_languages(la)
    return langs


def check_for_client(obj, clients):
    if obj.client_id in clients:
        return True
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


@view_config(route_name = 'dictionaries', renderer = 'json', request_method='POST')
def dictionaries_list(request):
    req = request.json_body
    user_created = None
    if 'user_created' in req:
        user_created = req['user_created']
    user_participated = None
    if 'user_participated' in req:
        user_participated = req['user_participated']
    organization_participated = None
    if 'organization_participated' in req:
        organization_participated = req['organization_participated']
    language_object_id = None
    if 'language_object_id' in req:
        language_object_id = req['language_object_id']
        language_client_id = req['language_client_id']
    dicts = DBSession.query(Dictionary)
    if user_created:
        clients = DBSession.query(Client).filter_by(user_id=user_created).all()
        cli = [o.id for o in clients]
        dicts = dicts.filter(Dictionary.client_id.in_(cli))
    if language_object_id:
        lang = DBSession.query(Language).filter_by(object_id=language_object_id, client_id=language_client_id).first()
        langs = all_languages(lang)
        lang_obj = [o[0] for o in langs]
        lang_cli = [o[1] for o in langs]
        dicts = dicts.filter(Dictionary.parent_client_id.in_(lang_cli), Dictionary.parent_object_id.in_(lang_obj))
    # add geo coordinates
    if organization_participated:
        organization = DBSession.query(Organization).filter_by(id=organization_participated).first()
        print('ORGANIZATION', organization.name)
        users = organization.users
        users_id = [o.id for o in users]
        print('USERS', users_id)

        clients = DBSession.query(Client).filter(Client.user_id.in_(users_id)).all()
        cli = [o.id for o in clients]
        print('CLIENTS', cli)

        dictstemp = []
        for dicti in dicts:
            if check_for_client(dicti, cli):
                dictstemp += [dicti]
        dict_obj = [o.object_id for o in dictstemp]
        dict_cli = [o.client_id for o in dictstemp]
        dicts = dicts.filter(Dictionary.client_id.in_(dict_cli), Dictionary.object_id.in_(dict_obj))

    if user_participated:
        clients = DBSession.query(Client).filter(Client.user_id.in_(user_participated)).all()
        cli = [o.id for o in clients]

        dictstemp = []
        for dicti in dicts:
            if check_for_client(dicti, cli):
                dictstemp += [dicti]
        dict_obj = [o.object_id for o in dictstemp]
        dict_cli = [o.client_id for o in dictstemp]
        dicts = dicts.filter(Dictionary.client_id.in_(dict_cli), Dictionary.object_id.in_(dict_obj))

    dictionaries = [{'object_id':o.object_id,'client_id':o.client_id} for o in dicts]
    response = dict()
    response['dictionaries'] = dictionaries
    request.response.status = HTTPOk.code
    response['status'] = HTTPOk.code

    return response


@view_config(route_name='perspective_fields', renderer='json', request_method='GET')
def view_perspective_fields(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')
    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")
    locale_id = find_locale_id(request)
    if perspective:
        fields = []
        for field in perspective.dictionaryperspectivefield:

            data = dict()
            if field.level == 'L1E' or field.level == 'GE':
                data['entity_type'] = find_by_translation_string(locale_id=locale_id,
                                                                 translation_string=field.entity_type)

                data['data_type'] = find_by_translation_string(locale_id=find_locale_id(request),
                                                               translation_string=field.data_type)
                data['position'] = field.position
                data['state'] = field.state
                if field.dictionaryperspectivefield:
                    contains = []
                    for field2 in field.dictionaryperspectivefield:
                        data2 = dict()
                        data2['entity_type'] = find_by_translation_string(locale_id=locale_id,
                                                                          translation_string=field2.entity_type)

                        data2['data_type'] = find_by_translation_string(locale_id=locale_id,
                                                                        translation_string=field2.data_type)
                        data2['state'] = field2.state
                        data2['position'] = field2.position
                        contains += [data2]
                    data['contains'] = contains
                if field.group:
                    group = DBSession.query(UserEntitiesTranslationString).\
                        filter_by(translation_string=field.group, locale_id=locale_id).first()
                    data['group'] = group.translation
                fields += [data]
        response['fields'] = fields
        request.response.status = HTTPOk.code
        response['status'] = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name='perspective_fields', renderer = 'json', request_method='DELETE')  # Probably very wrong
def delete_perspective_fields(request):
    response = dict()
    client_id = request.matchdict.get('perspective_client_id')
    object_id = request.matchdict.get('perspective_id')

    perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
    if perspective:
        req = request.json_body
        cli_id = req['field_client_id']
        obj_id = req['field_object_id']
        field = DBSession.query(DictionaryPerspectiveField).filter_by(client_id=cli_id, object_id=obj_id).first()
        if field:
            field.marked_for_deletion = True
        else:
            request.response.status = HTTPNotFound.code
            return {'status': request.response.status, 'error': str("No such field in the system")}
        request.response.status = HTTPOk.code
        response['status'] = HTTPOk.code
        return response
    else:
        request.response.status = HTTPNotFound.code
        return {'status': HTTPNotFound.code, 'error': str("No such perspective in the system")}


@view_config(route_name='perspective_fields', renderer = 'json', request_method='POST')
def create_perspective_fields(request):
    try:
        variables = {'auth': authenticated_userid(request)}
        parent_client_id = request.matchdict.get('perspective_client_id')
        parent_object_id = request.matchdict.get('perspective_id')
        dictionary_client_id = request.matchdict.get('dictionary_client_id')
        dictionary_object_id = request.matchdict.get('dictionary_object_id')
        fields = request.json_body['fields']

        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=parent_client_id,
                                                                       object_id=parent_object_id).first()
        if not perspective:
            request.response.status = HTTPNotFound.code
            return {'status': HTTPNotFound.code, 'error': str("No such dictionary in the system")}

        locale_id = find_locale_id(request)

        for entry in fields:
            client.fields += 1
            field = DictionaryPerspectiveField(object_id=client.fields,
                                               client_id=variables['auth'],
                                               entity_type=entry['entity_type'],
                                               data_type=entry['data_type'],
                                               parent=perspective,
                                               state=entry['state'])
            if 'group' in entry:
                field.group = entry['group']
                add_translation_to_translation_string(locale_id=locale_id,
                                                      translation_string=entry['group'],
                                                      translation=entry['group_translation'], client_id=client.id)
            field.level = entry['level']
            field.position = entry['position']
            if 'contains' in entry:
                for ent in entry['contains']:
                    client.fields += 1
                    field2 = DictionaryPerspectiveField(object_id=client.fields,
                                                        client_id=variables['auth'],
                                                        entity_type=ent['entity_type'],
                                                        data_type=ent['data_type'],
                                                        level='L2E',
                                                        parent=perspective,
                                                        parent_entity=field,
                                                        state=entry['state'])
                    field2.position = ent['position']
                    DBSession.add(field2)
                    DBSession.flush()
                    add_translation_to_translation_string(locale_id=locale_id,
                                                          translation_string=ent['entity_type'],
                                                          translation=ent['entity_type_translation'],
                                                          client_id=client.id)
                    add_translation_to_translation_string(locale_id=locale_id,
                                                          translation_string=ent['data_type'],
                                                          translation=ent['data_type_translation'], client_id=client.id)
                    if 'group' in ent:
                        field.group = entry['group']  # is there need for group on second level?
                        add_translation_to_translation_string(locale_id=locale_id,
                                                              translation_string=ent['group'],
                                                              translation=ent['group_translation'], client_id=client.id)
            DBSession.add(field)
            DBSession.flush()
            add_translation_to_translation_string(locale_id=locale_id,
                                                  translation_string=entry['entity_type'],
                                                  translation=entry['entity_type_translation'], client_id=client.id)
            add_translation_to_translation_string(locale_id=locale_id,
                                                  translation_string=entry['data_type'],
                                                  translation=entry['data_type_translation'], client_id=client.id)
        request.response.status = HTTPOk.code
        return {'status': request.response.status,
                'object_id': perspective.object_id,
                'client_id': perspective.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': HTTPNotFound.code, 'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'status': HTTPNotFound.code, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': HTTPNotFound.code, 'error': str(e)}

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


@view_config(route_name='testing', renderer='json')
def testing(request):
    from pyramid.request import Request
    return Request({})


@view_config(route_name='login', renderer='templates/login.pt', request_method='GET')
def login_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/login.pt', variables, request=request)


@view_config(route_name='login', request_method='POST')
def login_post(request):
    next = request.params.get('next') or request.route_url('dashboard')
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


@view_config(route_name='signup', renderer='templates/signup.pt', request_method='GET')
def signup_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/signup.pt', variables, request=request)

@view_config(route_name='signup', renderer='json', request_method='POST')
def signup_post(request):
    try:
        login = request.POST.getone('login')
        name = request.POST.getone('name')
        email = request.POST.getone('email')
        password = request.POST.getone('password')

        day = request.POST.getone('day')
        month = request.POST.getone('month')
        year = request.POST.getone('year')
        birthday = datetime.datetime.strptime(day + month + year, "%d%m%Y").date()

        if DBSession.query(User).filter_by(login=login).first():
            raise CommonException("The user with this login is already registered")
        if DBSession.query(Email).filter_by(email=email).first():
            raise CommonException("The user with this email is already registered")
        new_user = User(login=login, name=name, signup_date=datetime.datetime.utcnow(), intl_name=login, birthday=birthday, is_active=True)
        pwd = Passhash(password=password)
        email = Email(email=email)
        new_user.password = pwd
        new_user.email.append(email)
        DBSession.add(new_user)
        DBSession.flush()
        return login_post(request)

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}

    except ValueError as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='dashboard', renderer='templates/dashboard.pt', request_method='GET')
def dashboard(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/dashboard.pt', variables, request=request)


@view_config(route_name='edit_perspective', renderer='templates/create_perspective.pt', request_method='GET')
def create_perspective(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/create_perspective.pt', variables, request=request)








@view_config(route_name='testing', renderer='json')
def testing(request):
    result = dict()
    # get = dict()
    # for entry in dir(request.GET):
    #     get[str(entry)] = str(entry)
    # result['GET'] = get
    # get = dict()
    # for entry in dir(request.params):
    #     get[str(entry)] = str(entry)
    # result['params'] = get
    # result['POST'] = request.POST.get['id']

    result['method'] = request.method
    result['matchdict'] = request.matchdict.get('id')
    result['get'] = request.GET.get('id')
    result['post'] = request.POST.get('id')

    if 'id2' in request.json_body:
        result['json_body'] = request.json_body['id2']
    print(request.json_body)
    return result
