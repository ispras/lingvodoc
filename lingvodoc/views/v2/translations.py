from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    Language,
    User,
    TranslationAtom,
    TranslationGist
)

from lingvodoc.views.v2.utils import (
    all_languages,
    cache_clients,
    check_for_client,
    get_user_by_client_id,
    group_by_languages,
    group_by_organizations,
    user_counter
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPForbidden,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.renderers import render_to_response
from pyramid.request import Request
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config

import sqlalchemy
from sqlalchemy import (
    func,
    tuple_,
    case
)
from sqlalchemy.exc import IntegrityError

import datetime
import json
from sqlalchemy.orm.exc import NoResultFound
from lingvodoc.views.v2.utils import json_request_errors, translation_atom_decorator
# search (filter by input, type and (?) locale)


def translationgist_contents(translationgist):
    result = dict()
    result['client_id'] = translationgist.client_id
    result['object_id'] = translationgist.object_id
    result['type'] = translationgist.type
    result['created_at'] = translationgist.created_at.timestamp()
    contains = []
    for translationatom in translationgist.translationatom:
        contains.append(translationatom_contents(translationatom))
    result['contains'] = contains
    return result


def translationatom_contents(translationatom):
    result = dict()
    result['content'] = translationatom.content
    result['locale_id'] = translationatom.locale_id
    result['client_id'] = translationatom.client_id
    result['object_id'] = translationatom.object_id
    result['parent_client_id'] = translationatom.parent_client_id
    result['parent_object_id'] = translationatom.parent_object_id
    result['created_at'] = translationatom.created_at.timestamp()
    return result


@view_config(route_name='translationgist', renderer='json', request_method='GET')
def view_translationgist(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    translationgist = DBSession.query(TranslationGist).filter_by(client_id=client_id, object_id=object_id).first()
    if translationgist:
        response = translationgist_contents(translationgist)
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such translationgist in the system")}


@view_config(route_name='translationgist', renderer='json', request_method='DELETE', permission='delete')
def delete_translationgist(request):
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    translationgist = DBSession.query(TranslationGist).filter_by(client_id=client_id, object_id=object_id).first()
    if translationgist and not translationgist.marked_for_deletion:
        for translationatom in translationgist.translationatom:
            translationatom.marked_for_deletion = True
        translationgist.marked_for_deletion = True
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such translationgist in the system")}


@view_config(route_name='create_translationgist', renderer='json', request_method='POST', permission='create')
def create_translationgist(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        type = req['type']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        translationgist = TranslationGist(client_id=variables['auth'], type=type)
        DBSession.add(translationgist)
        DBSession.flush()
        basegroups = []
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can delete translationgist").first()]
        groups = []
        for base in basegroups:
            group = Group(subject_client_id=translationgist.client_id, subject_object_id=translationgist.object_id, parent=base)
            groups += [group]
        for group in groups:
            if group not in user.groups:
                user.groups.append(group)
        request.response.status = HTTPOk.code
        return {'object_id': translationgist.object_id,
                'client_id': translationgist.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(decorator=translation_atom_decorator, route_name='translationatom', renderer='json', request_method='GET')
def view_translationatom(request):
    response = translationatom_contents(request.object)
    # print(request.__dict__)
    # del request.object
    # print(request.__dict__)
    return response


@view_config(route_name='translationatom', renderer='json', request_method='PUT')
def edit_translationatom(request):
    response = dict()
    req = request.json_body
    content = req['content']
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    translationatom = DBSession.query(TranslationAtom).filter_by(client_id=client_id, object_id=object_id).first()
    if translationatom:
        translationatom.content = content
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such translationatom in the system")}


@view_config(route_name='create_translationatom', renderer='json', request_method='POST', permission='create')
def create_translationatom(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        parent_client_id = req['parent_client_id']
        parent_object_id = req['parent_object_id']
        locale_id = req['locale_id']
        content = req['content']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        parent = DBSession.query(TranslationGist).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent.marked_for_deletion:
            translationatom = TranslationAtom(client_id=variables['auth'],
                                              parent=parent,
                                              locale_id=locale_id,
                                              content=content)
            DBSession.add(translationatom)
            DBSession.flush()
            basegroups = []
            basegroups += [DBSession.query(BaseGroup).filter_by(name="Can edit translationatom").first()]
            groups = []
            for base in basegroups:
                group = Group(subject_client_id=translationatom.client_id, subject_object_id=translationatom.object_id, parent=base)
                groups += [group]
            for group in groups:
                if group not in user.groups:
                    user.groups.append(group)
            request.response.status = HTTPOk.code
            return {'object_id': translationatom.object_id,
                    'client_id': translationatom.client_id}
        else:
            raise KeyError("TranslationGist deleted")
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(decorator=json_request_errors, route_name='translation_search', renderer='json', request_method='POST')
def translation_search(request):
    response = list()
    req = request.json_body
    searchstring = req['searchstring']
    type = req.get('type', None)
    translationatoms = DBSession.query(TranslationAtom).filter(TranslationAtom.content.like('%'+searchstring+'%'))
    if type:
        translationatoms = translationatoms.join(TranslationGist).filter(TranslationGist.type == type).all()
    else:
        translationatoms = translationatoms.all()
    translationgists = list()
    for translationatom in translationatoms:
        parent = translationatom.parent
        if parent not in translationgists:
            translationgists.append(parent)
    if translationgists:
        for translationgist in translationgists:
            response.append(translationgist_contents(translationgist))
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No result")}


@view_config(route_name='translation_service_search', renderer='json', request_method='POST')
def translation_service_search(request):
    try:
        req = request.json_body
    except AttributeError:
        request.response.status = HTTPBadRequest.code
        return {'error': "invalid json"}
    except ValueError:
        request.response.status = HTTPBadRequest.code
        return {'error': "invalid json"}
    searchstring = req['searchstring']
    try:
        translationatom = DBSession.query(TranslationAtom)\
            .join(TranslationGist).\
            filter(TranslationAtom.content == searchstring,
                   TranslationAtom.locale_id == 2,
                   TranslationGist.type == 'Service')\
            .one()
        response = translationgist_contents(translationatom.parent)
        request.response.status = HTTPOk.code
        return response

    except NoResultFound:
        request.response.status = HTTPNotFound.code
        return {'error': str("No result")}