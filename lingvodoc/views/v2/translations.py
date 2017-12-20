from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    User,
    TranslationAtom,
    TranslationGist,
    ObjectTOC
)
"""
from lingvodoc.views.v2.utils import (
    all_languages,
    cache_clients,
    check_for_client,
    get_user_by_client_id,
    group_by_languages,
    group_by_organizations,
    user_counter
)
"""
from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError

from sqlalchemy.orm.exc import NoResultFound
from lingvodoc.views.v2.utils import json_request_errors, translation_atom_decorator#, add_user_to_group, check_client_id
from lingvodoc.utils.creation import add_user_to_group, translationgist_contents, translationatom_contents
from lingvodoc.utils.verification import check_client_id
# search (filter by input, type and (?) locale)
from lingvodoc.cache.caching import CACHE


@view_config(route_name='all_translationgists', renderer='json', request_method='GET', permission='view')
def all_translationgists(request):
    response = list()
    gists = DBSession.query(TranslationGist).order_by(TranslationGist.type).all()
    for translation_gist in gists:
        response.append(translationgist_contents(translation_gist))
    return response

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
        # if 'desktop' in request.registry.settings:
        #     real_delete_translation_gist(translationgist, request.registry.settings)
        # else:
        translationgist.marked_for_deletion = True
        objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=translationgist.client_id,
                                                         object_id=translationgist.object_id).one()
        objecttoc.marked_for_deletion = True
        for translationatom in translationgist.translationatom:
            translationatom.marked_for_deletion = True
            objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=translationatom.client_id,
                                                             object_id=translationatom.object_id).one()
            objecttoc.marked_for_deletion = True
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such translationgist in the system")}


@view_config(route_name='create_translationgist', renderer='json', request_method='POST', permission='create')
def create_translationgist(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        object_id = req.get('object_id', None)
        type = req['type']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()

        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']) or user.id == 1:
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}
        translationgist = TranslationGist(client_id=client_id,object_id=object_id, type=type)
        DBSession.add(translationgist)
        DBSession.flush()
        basegroups = list()
        basegroups.append(DBSession.query(BaseGroup).filter_by(name="Can delete translationgist").first())
        if not object_id:
            groups = []
            for base in basegroups:
                group = Group(subject_client_id=translationgist.client_id, subject_object_id=translationgist.object_id, parent=base)
                groups += [group]
            for group in groups:
                add_user_to_group(user, group)
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


@view_config(route_name='translationatom', renderer='json', request_method='PUT', permission='edit')
def edit_translationatom(request):
    response = dict()
    req = request.json_body
    content = req['content']
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    translationatom = DBSession.query(TranslationAtom).filter_by(client_id=client_id, object_id=object_id).first()
    if translationatom:
        key = "translation:%s:%s:%s" % (
            str(translationatom.parent_client_id),
            str(translationatom.parent_object_id),
            str(translationatom.locale_id))
        CACHE.rem(key)
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
        object_id = req.get('object_id', None)
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        parent = DBSession.query(TranslationGist).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']) or user.id == 1:
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}

        if not parent.marked_for_deletion:
            translationatom = TranslationAtom(client_id=client_id,
                                              object_id=object_id,
                                              parent=parent,
                                              locale_id=locale_id,
                                              content=content)
            DBSession.add(translationatom)
            DBSession.flush()
            if not object_id:
                basegroups = []
                basegroups += [DBSession.query(BaseGroup).filter_by(name="Can edit translationatom").first()]
                if not object_id:
                    groups = []
                    for base in basegroups:
                        group = Group(subject_client_id=translationatom.client_id, subject_object_id=translationatom.object_id, parent=base)
                        groups += [group]
                    for group in groups:
                        add_user_to_group(user, group)
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