__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.views.v2.utils import (
    get_user_by_client_id,
    language_info
)
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    Language,
    User
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError


@view_config(route_name='languages', renderer='templates/languages.pt', request_method='GET')
def languages_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    if user is None:
        response = Response()
        return HTTPFound(location=request.route_url('login'), headers=response.headers)
    variables = {'client_id': client_id, 'user': user}
    return render_to_response('templates/languages.pt', variables, request=request)


@view_config(route_name='language', renderer='json', request_method='GET')
def view_language(request):  # tested & in docs
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
            response['translation_gist_client_id'] = language.translation_gist_client_id
            response['translation_gist_object_id'] = language.translation_gist_object_id
            response['translation'] = language.get_translation(request.cookies['locale_id'])
            if language.locale:
                response['locale_exist'] = True
            else:
                response['locale_exist'] = False

            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such language in the system")}


@view_config(route_name='language', renderer='json', request_method='PUT')
def edit_language(request):  # tested & in docs
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
                # TODO: Status 500 will be returned if arguments are invalid; add try/catch
                req = request.json_body
                if 'parent_client_id' in req:
                    language.parent_client_id = req['parent_client_id']
                if 'parent_object_id' in req:
                    language.parent_object_id = req['parent_object_id']
                if 'translation_gist_client_id' in req:
                    language.translation_gist_client_id = req['translation_gist_client_id']
                if 'translation_gist_object_id' in req:
                    language.translation_gist_object_id = req['translation_gist_object_id']
                request.response.status = HTTPOk.code
                return response
        request.response.status = HTTPNotFound.code
        return {'error': str("No such language in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}


@view_config(route_name='language', renderer='json', request_method='DELETE', permission='delete')
def delete_language(request):  # tested & in docs
    response = dict()
    client_id = request.matchdict.get('client_id')
    object_id = request.matchdict.get('object_id')
    language = DBSession.query(Language).filter_by(client_id=client_id, object_id=object_id).first()
    if language:
        if not language.marked_for_deletion:
            language.marked_for_deletion = True
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such language in the system")}


@view_config(route_name='create_language', renderer='json', request_method='POST', permission='create')
def create_language(request):  # tested & in docs
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        try:
            parent_client_id = req['parent_client_id']
            parent_object_id = req['parent_object_id']
        except:
            parent_client_id = None
            parent_object_id = None
        translation_gist_client_id = req['translation_gist_client_id']
        translation_gist_object_id = req['translation_gist_object_id']
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
        language = Language(client_id=variables['auth'],
                                translation_gist_client_id=translation_gist_client_id,
                                translation_gist_object_id=translation_gist_object_id)
        DBSession.add(language)
        if parent:
            language.parent = parent
        DBSession.flush()
        basegroups = []
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can edit languages").first()]
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can delete languages").first()]
        groups = []
        for base in basegroups:
            group = Group(subject_client_id=language.client_id, subject_object_id=language.object_id, parent=base)
            groups += [group]
        for group in groups:
            if group not in user.groups:
                user.groups.append(group)
        request.response.status = HTTPOk.code
        return {'object_id': language.object_id,
                'client_id': language.client_id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='get_languages', renderer='json', request_method='GET')
def view_languages_list(request):  # tested & in docs
    response = list()
    langs = []
    languages = DBSession.query(Language).filter_by(parent=None, marked_for_deletion=False).all()
    if languages:
        for lang in languages:
            langs += [language_info(lang, request)]
    response = langs

    request.response.status = HTTPOk.code
    return response
