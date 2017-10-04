from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    Language,
    User,
    UserRequest,
    Grant,
    Organization,
    Dictionary,
    DictionaryPerspective
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

from sqlalchemy.orm.attributes import flag_modified
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

    userrequests = DBSession.query(UserRequest).filter(UserRequest.recipient_id == user.id).order_by(
        UserRequest.created_at).all()
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
            if userrequest.type == 'grant_permission':
                # req['subject'] = {'grant_id': grant_id, 'user_id': user_id}
                grant = DBSession.query(Grant).filter_by(id=userrequest.subject['grant_id']).first()
                if grant.owners is None:
                    grant.owners = list()
                user = DBSession.query(User).filter_by(id=userrequest.subject['user_id']).one()
                if userrequest.subject['user_id'] not in grant.owners:
                    grant.owners.append(userrequest.subject['user_id'])
                    flag_modified(grant, 'owners')
                if grant.additional_metadata is not None and grant.additional_metadata.get('roles'):
                    for role in grant.additional_metadata['roles']:
                        group = DBSession.query(Group).filter_by(id=role).one()
                        if user not in group.users:
                            group.users.append(user)
            elif userrequest.type == 'add_dict_to_grant':
                grant = DBSession.query(Grant).filter_by(id=userrequest.subject['grant_id']).first()
                if grant.additional_metadata is None:
                    grant.additional_metadata = dict()
                if grant.additional_metadata.get('participant') is None:
                    grant.additional_metadata['participant'] = list()

                dict_ids = {'client_id': userrequest.subject['client_id'],
                            'object_id': userrequest.subject['object_id']}

                no_grants = True
                for tmp_grant in DBSession.query(Grant).all():
                    if tmp_grant.additional_metadata and tmp_grant.additional_metadata.get('participant') and dict_ids in \
                            tmp_grant.additional_metadata['participant']:
                        no_grants = False
                        break

                if dict_ids not in grant.additional_metadata['participant']:
                    grant.additional_metadata['participant'].append(dict_ids)

                # if no_grants:
                #     dict_authors = DBSession.query(User).join(Group).join(BaseGroup).filter(
                #         Group.subject_client_id == dict_ids['client_id'],
                #         Group.subject_object_id == dict_ids['object_id'],
                #         BaseGroup.subject == 'dictionary_role',
                #         BaseGroup.action == 'delete').all()
                state_group = DBSession.query(Group).join(BaseGroup).filter(
                    Group.subject_client_id == dict_ids['client_id'],
                    Group.subject_object_id == dict_ids['object_id'],
                    BaseGroup.subject == 'dictionary_status',
                    BaseGroup.action == 'edit'
                ).first()
                approve_groups = list()
                cur_dict = DBSession.query(Dictionary).filter_by(client_id=dict_ids['client_id'], object_id=dict_ids['object_id']).first()
                persp_ids = list()
                for persp in cur_dict.dictionaryperspective:
                    persp_ids.append((persp.client_id, persp.object_id))
                    approve_group = DBSession.query(Group).join(BaseGroup).filter(
                        Group.subject_client_id == persp.client_id,
                        Group.subject_object_id == persp.object_id,
                        BaseGroup.subject == 'perspective_status',
                        BaseGroup.action == 'edit'
                    ).first()
                    if approve_group:
                        approve_groups.append(approve_group)
                    approve_group = DBSession.query(Group).join(BaseGroup).filter(
                        Group.subject_client_id == persp.client_id,
                        Group.subject_object_id == persp.object_id,
                        BaseGroup.subject == 'approve_entities',
                        BaseGroup.action == 'create'
                    ).first()
                    if approve_group:
                        approve_groups.append(approve_group)
                    approve_group = DBSession.query(Group).join(BaseGroup).filter(
                        Group.subject_client_id == persp.client_id,
                        Group.subject_object_id == persp.object_id,
                        BaseGroup.subject == 'approve_entities',
                        BaseGroup.action == 'delete'
                    ).first()
                    if approve_group:
                        approve_groups.append(approve_group)

                grant_admins = DBSession.query(User).filter(User.id.in_(grant.owners))
                if grant.additional_metadata is None:
                    grant.additional_metadata = dict()
                if grant.additional_metadata.get('roles', None) is None:
                    grant.additional_metadata['roles'] = list()
                for admin in grant_admins:
                    perm_groups = DBSession.query(Group).filter_by(subject_client_id=cur_dict.client_id, subject_object_id=cur_dict.object_id).all()
                    for group in perm_groups:
                        if group.id not in grant.additional_metadata['roles']:
                            grant.additional_metadata['roles'].append(group.id)
                        if group not in admin.groups:
                            admin.groups.append(group)
                    perm_groups = DBSession.query(Group).filter(tuple_(Group.subject_client_id, Group.subject_object_id).in_(persp_ids)).all()
                    for group in perm_groups:
                        if group.id not in grant.additional_metadata['roles']:
                            grant.additional_metadata['roles'].append(group.id)
                        if group not in admin.groups:
                            admin.groups.append(group)
                flag_modified(grant, 'additional_metadata')
                    # state_group.users.append(admin) # or only for some permissions?
                    # for group in approve_groups:
                    #     group.users.append(admin)

            elif userrequest.type == 'participate_org':
                DBSession.execute("LOCK TABLE user_to_organization_association IN EXCLUSIVE MODE;")
                org_id = userrequest.subject['org_id']
                user_id = userrequest.subject['user_id']
                organization = DBSession.query(Organization).filter_by(id=org_id).first()
                user = DBSession.query(User).filter_by(id=user_id).first()
                if user not in organization.users:
                    if not user in organization.users:
                        organization.users.append(user)
            elif userrequest.type == 'administrate_org':
                org_id = userrequest.subject['org_id']
                user_id = userrequest.subject['user_id']
                organization = DBSession.query(Organization).filter_by(id=org_id).first()
                user = DBSession.query(User).filter_by(id=user_id).first()
                if organization.additional_metadata is None:
                    organization.additional_metadata = dict()
                if organization.additional_metadata.get('admins') is None:
                    organization.additional_metadata['admins'] = list()
                organization.additional_metadata['admins'].append(user_id)
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
        grant_id = int(request.matchdict.get('id'))
        # req = request.json_body
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'grant_permission'
        req['subject'] = {'grant_id': grant_id, 'user_id': user_id}
        req['message'] = ''
        if DBSession.query(UserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            request.response.status = HTTPBadRequest.code
            return {'error': 'request already exists'}

        grantadmins = list()
        # groups = DBSession.query(Group).filter_by(parent=parentbase, subject_override = True).all()

        group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'grant',
                                                              Group.subject_override == True,
                                                              BaseGroup.action == 'approve').one()

        for user in group.users:
            if user not in grantadmins:
                grantadmins.append(user)

        if not grantadmins:
            request.response.status = HTTPBadRequest.code
            return {'error': 'no administrators'}

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


@view_config(route_name='add_dictionary_to_grant', renderer='json', request_method='POST')
def add_dictionary_to_grant(request):
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
        request_json = request.json_body
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'add_dict_to_grant'
        req['subject'] = request_json
        req['message'] = ''
        if DBSession.query(UserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            request.response.status = HTTPBadRequest.code
            return {'error': 'request already exists'}

        grantadmins = list()

        grant = DBSession.query(Grant).filter_by(id=request_json['grant_id']).first()
        grantadmins = grant.owners
        if not grantadmins:
            request.response.status = HTTPBadRequest.code
            return {'error': 'no administrators'}

        for grantadmin in grantadmins:
            req['recipient_id'] = grantadmin
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


@view_config(route_name='administrate_org', renderer='json', request_method='GET')
def administrate_org(request):
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
        org_id = int(request.matchdict.get('id'))
        # req = request.json_body
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'administrate_org'
        req['subject'] = {'org_id': org_id, 'user_id': user_id}
        req['message'] = ''
        if DBSession.query(UserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            request.response.status = HTTPBadRequest.code
            return {'error': 'request already exists'}

        orgadmins = list()
        # groups = DBSession.query(Group).filter_by(parent=parentbase, subject_override = True).all()

        group = DBSession.query(Group).join(BaseGroup).filter(BaseGroup.subject == 'organization',
                                                              Group.subject_override == True,
                                                              BaseGroup.action == 'approve').one()

        for user in group.users:
            if user not in orgadmins:
                orgadmins.append(user)
        if not orgadmins:
            request.response.status = HTTPBadRequest.code
            return {'error': 'no administrators'}
        for orgadmin in orgadmins:
            req['recipient_id'] = orgadmin.id
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


@view_config(route_name='participate_org', renderer='json', request_method='GET')
def participate_org(request):
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
        org_id = int(request.matchdict.get('id'))
        # req = request.json_body
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'participate_org'
        req['subject'] = {'org_id': org_id, 'user_id': user_id}
        req['message'] = ''
        if DBSession.query(UserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            request.response.status = HTTPBadRequest.code
            return {'error': 'request already exists'}

        orgadmins = list()
        # groups = DBSession.query(Group).filter_by(parent=parentbase, subject_override = True).all()

        org = DBSession.query(Organization).filter_by(id=org_id).first()
        if not org.additional_metadata:
            request.response.status = HTTPBadRequest.code
            return {'error': 'no administrators'}

        orgadmins = org.additional_metadata.get('admins')

        if not orgadmins:
            request.response.status = HTTPBadRequest.code
            return {'error': 'no administrators'}

        for orgadmin in org.additional_metadata['admins']:
            req['recipient_id'] = orgadmin
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
