__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    Organization,
    User
)
from lingvodoc.views.v2.utils import (
    get_user_by_client_id
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
from pyramid.request import Request
from pyramid.response import Response
from pyramid.security import authenticated_userid
from pyramid.view import view_config

from sqlalchemy.exc import IntegrityError

import logging

log = logging.getLogger(__name__)
from lingvodoc.views.v2.utils import add_user_to_group


@view_config(route_name='organizations', renderer='templates/organizations.pt', request_method='GET')
def organizations_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    if user is None:
        response = Response()
        return HTTPFound(location=request.route_url('login'), headers=response.headers)
    variables = {'client_id': client_id, 'user': user }
    return render_to_response('templates/organizations.pt', variables, request=request)


@view_config(route_name='organization_list', renderer='json', request_method='GET')
def view_organization_list(request):  # TODO: test
    response = dict()
    organizations = []
    for organization in DBSession.query(Organization).filter_by(marked_for_deletion=False).all():
        path = request.route_url('organization',
                                 organization_id=organization.id)
        subreq = Request.blank(path)
        subreq.method = 'GET'
        subreq.headers = request.headers
        resp = request.invoke_subrequest(subreq)
        answ = dict()
        answ = resp.json
        answ['organization_id'] = organization.id
        organizations += [answ]
    response['organizations'] = organizations
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='create_organization', renderer='json', request_method='POST')
def create_organization(request):  # TODO: test
    try:

        variables = {'auth': request.authenticated_userid}
        req = request.json_body
        name = req['name']
        about = req['about']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        organization = Organization(name=name,
                                    about=about)
        if user not in organization.users:
            organization.users.append(user)
        DBSession.add(organization)
        DBSession.flush()
        bases = DBSession.query(BaseGroup).filter_by(subject='organization')
        for base in bases:
            group = Group(parent=base, subject_object_id=organization.id)
            add_user_to_group(user, group)
            DBSession.add(group)
        request.response.status = HTTPOk.code
        return {'organization_id': organization.id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


@view_config(route_name='organization', renderer='json', request_method='GET')
def view_organization(request):  # TODO: test
    response = dict()
    organization_id = request.matchdict.get('organization_id')
    organization = DBSession.query(Organization).filter_by(id=organization_id).first()
    if organization:
        if not organization.marked_for_deletion:
            response['name'] = organization.name
            response['about'] = organization.about
            users = []
            for user in organization.users:
                users += [user.id]
            response['users'] = users
            additional_metadata = organization.additional_metadata
            if additional_metadata is None:
                additional_metadata = dict()
            response['additional_metadata'] = additional_metadata
            admins = list()
            if additional_metadata.get('admins'):
                admins = additional_metadata['admins']
            response['admin'] = admins
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such organization in the system")}


@view_config(route_name='organization', renderer='json', request_method='PUT')
def edit_organization(request):  # TODO: test
    try:
        DBSession.execute("LOCK TABLE user_to_organization_association IN EXCLUSIVE MODE;")
        response = dict()
        organization_id = request.matchdict.get('organization_id')
        organization = DBSession.query(Organization).filter_by(id=organization_id).first()

        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        creator = DBSession.query(User).filter_by(id=client.user_id).first()
        if not creator:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        if organization:
            if not organization.marked_for_deletion:
                req = request.json_body
                if 'add_users' in req:
                    for user_id in req['add_users']:
                        user = DBSession.query(User).filter_by(id=user_id).first()
                        if user not in organization.users:
                            if not user in organization.users:
                                organization.users.append(user)
                            bases = DBSession.query(BaseGroup).filter_by(subject='organization')
                            for base in bases:
                                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                                         subject_object_id=organization.id).first()
                                add_user_to_group(user, group)
                if 'delete_users' in req:
                    for user_id in req['delete_users']:
                        if user_id == creator.id:
                            raise CommonException("You shouldn't delete yourself")
                        user = DBSession.query(User).filter_by(id=user_id).first()
                        if user in organization.users:
                            organization.users.remove(user)
                            bases = DBSession.query(BaseGroup).filter_by(subject='organization')
                            for base in bases:
                                group = DBSession.query(Group).filter_by(base_group_id=base.id,
                                                                         subject_object_id=organization.id).first()
                                group.users.remove(user)
                if 'name' in req:
                    organization.name = req['name']
                if 'about' in req:
                    organization.about = req['about']
                request.response.status = HTTPOk.code
                return response

        request.response.status = HTTPNotFound.code
        return {'error': str("No such organization in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}


@view_config(route_name='organization', renderer='json', request_method='DELETE')
def delete_organization(request):  # TODO: test
    response = dict()
    organization_id = request.matchdict.get('organization_id')
    organization = DBSession.query(Organization).filter_by(id=organization_id).first()
    if organization:
        if not organization.marked_for_deletion:
            organization.marked_for_deletion = True
            request.response.status = HTTPOk.code
            return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such organization in the system")}
