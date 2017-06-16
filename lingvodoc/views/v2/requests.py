
from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    Language,
    User,
    UserRequest,
    Grant
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
from uuid import uuid4

import datetime
import json
from sqlalchemy.orm.exc import NoResultFound
from lingvodoc.views.v2.utils import json_request_errors, translation_atom_decorator, add_user_to_group, check_client_id
from lingvodoc.views.v2.delete import real_delete_translation_gist
# search (filter by input, type and (?) locale)


def userrequest_contents(userrequest):
    result = dict()
    result['id'] = userrequest.id
    result['sender_id'] = userrequest.sender_id
    result['recipient_id'] = userrequest.recipient_id
    result['broadcast_uuid'] = userrequest.broadcast_uuid
    result['type'] = userrequest.type
    result['subject'] = userrequest.subject
    result['message'] = userrequest.message
    result['created_at'] = userrequest.created_at
    result['additional_metadata'] = userrequest.additional_metadata
    return result


# @view_config(route_name='all_userrequests', renderer='json', request_method='GET', permission='view')  # why would we need all of them?
# def all_userrequests(request):
#     response = list()
#     userrequests = DBSession.query(UserRequest).order_by(UserRequest.grant_number).all()
#     for userrequest in userrequests:
#         response.append(userrequest_contents(userrequest))
#     return response


@view_config(route_name='get_current_userrequests', renderer='json', request_method='GET')
def get_current_userrequests(request):
    response = list()

    variables = {'auth': request.authenticated_userid}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()

    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       variables['auth'])
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")

    userrequests = DBSession.query(UserRequest).filter(UserRequest.recipient_id == user.id).order_by(UserRequest.created_at).all()
    for userrequest in userrequests:
        response.append(userrequest_contents(userrequest))
    return response


@view_config(route_name='userrequest', renderer='json', request_method='GET')  # only recipient can see it?
def view_userrequest(request):
    response = dict()
    userrequest_id = request.matchdict.get('id')
    userrequest = DBSession.query(UserRequest).filter_by(id=userrequest_id).first()
    if userrequest:
        response = userrequest_contents(userrequest)
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such userrequest in the system")}


@view_config(route_name='accept_userrequest', renderer='json', request_method='POST')  # only recipient can see it?
def accept_userrequest(request):
    response = dict()
    userrequest_id = request.matchdict.get('id')

    variables = {'auth': request.authenticated_userid}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()

    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       variables['auth'])
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")
    recipient_id = user.id

    userrequest = DBSession.query(UserRequest).filter_by(id=userrequest_id, recipient_id=recipient_id).first()
    if userrequest:
        req = request.json_body
        accept = req['accept']
        if accept is True:
            pass  #case for all types of requests
            if userrequest.type == 'grant_permission':
                # req['subject'] = {'grant_id': grant_id, 'user_id': user_id}
                grant = DBSession.query(Grant).filter_by(id=userrequest.subject['grant_id']).first()
                if grant.owners is None:
                    grant.owners = list()
                if userrequest.subject['user_id'] not in grant.owners:
                    grant.owners.append(userrequest.subject['user_id'])
            else:
                pass
            broadcast_uuid = userrequest.broadcast_uuid
            family = DBSession.query(UserRequest).filter_by(id=userrequest_id, broadcast_uuid=broadcast_uuid).all()
            for userreq in family:
                DBSession.delete(userreq)
        else:
            DBSession.delete(userrequest)
        return response

    request.response.status = HTTPNotFound.code
    return {'error': str("No such userrequest in the system")}


@view_config(route_name='userrequest', renderer='json', request_method='DELETE', permission='admin')  # delete grant???
def delete_userrequest(request):
    response = dict()
    userrequest_id = request.matchdict.get('id')
    userrequest = DBSession.query(UserRequest).filter_by(id=userrequest_id).first()
    if userrequest:
        DBSession.delete(userrequest)
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such userrequest in the system")}

def create_one_userrequest(req, client_id):
    sender_id = req['sender_id']
    recipient_id = req['recipient_id']
    broadcast_uuid = req['broadcast_uuid']  # generate it
    type = req['type']
    subject = req['subject']
    message = req['message']
    client = DBSession.query(Client).filter_by(id=client_id).first()

    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       client_id)
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")

    userrequest = UserRequest(sender_id=sender_id,
                              recipient_id=recipient_id,
                              broadcast_uuid=broadcast_uuid,
                              type=type,
                              subject=subject,
                              message=message
                              )
    DBSession.add(userrequest)
    DBSession.flush()
    return userrequest.id


# @view_config(route_name='create_userrequest', renderer='json', request_method='POST', permission='create')
# def create_userrequest(request):
#     try:
#         variables = {'auth': request.authenticated_userid}
#         client_id = variables['auth']
#
#
#         request.response.status = HTTPOk.code
#         return {'id': req_id}
#     except KeyError as e:
#         request.response.status = HTTPBadRequest.code
#         return {'error': str(e)}
#
#     except IntegrityError as e:
#         request.response.status = HTTPInternalServerError.code
#         return {'error': str(e)}
#
#     except CommonException as e:
#         request.response.status = HTTPConflict.code
#         return {'error': str(e)}


@view_config(route_name='get_grant_permission', renderer='json', request_method='GET')
def get_grant_permission(request):
    try:
        variables = {'auth': request.authenticated_userid}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()

        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        user_id = user.id
        client_id = variables['auth']
        grant_id= request.matchdict.get('id')
        # req = request.json_body
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'grant_permission'
        req['subject'] = {'grant_id': grant_id, 'user_id': user_id}
        req['message'] = ''


        grantadmins = list()
        # groups = DBSession.query(Group).filter_by(parent=parentbase, subject_override = True).all()

        group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'grant',
                                                              Group.subject_override == True,
                                                              BaseGroup.action == 'approve').one()

        for user in group.users:
            if user not in grantadmins:
                grantadmins.append(user)

        for grantadmin in grantadmins:
            req['recipient_id'] = grantadmin.id
            req_id = create_one_userrequest(req, client_id)


        request.response.status = HTTPOk.code
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