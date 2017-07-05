
from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    Language,
    User,
    Grant,
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
from lingvodoc.views.v2.utils import json_request_errors, translation_atom_decorator, add_user_to_group, check_client_id
from lingvodoc.views.v2.delete import real_delete_translation_gist
# search (filter by input, type and (?) locale)


def grant_contents(grant, locale_id=2):
    result = dict()
    result['id'] = grant.id
    result['issuer_translation_gist_client_id'] = grant.issuer_translation_gist_client_id
    result['issuer_translation_gist_object_id'] = grant.issuer_translation_gist_object_id
    result['translation_gist_object_id'] = grant.translation_gist_object_id
    result['translation_gist_client_id'] = grant.translation_gist_client_id
    result['translation'] = grant.get_translation(locale_id)
    result['issuer'] = grant.get_issuer_translation(locale_id)
    result['issuer_url'] = grant.issuer_url
    result['grant_url'] = grant.grant_url
    result['grant_number'] = grant.grant_number
    result['begin'] = grant.begin.strftime("%d.%m.%Y")
    result['end'] = grant.end.strftime("%d.%m.%Y")
    owners = grant.owners
    if owners is None:
        owners = []
    result['owners'] = owners 
    result['created_at'] = grant.created_at
    additional_metadata = grant.additional_metadata
    if additional_metadata is None:
        additional_metadata = dict()
    result['additional_metadata'] = additional_metadata
    return result


@view_config(route_name='all_grants', renderer='json', request_method='GET')
def all_grants(request):
    response = list()
    locale_id = request.cookies['locale_id']
    grants = DBSession.query(Grant).order_by(Grant.grant_number).all()
    for grant in grants:
        response.append(grant_contents(grant, locale_id))
    return response


@view_config(route_name='grant', renderer='json', request_method='GET')
def view_grant(request):
    response = dict()
    locale_id = request.cookies['locale_id']
    grant_id = request.matchdict.get('id')
    grant = DBSession.query(Grant).filter_by(id=grant_id).first()
    if grant:
        response = grant_contents(grant, locale_id)
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such grant in the system")}


@view_config(route_name='grant', renderer='json', request_method='DELETE', permission='admin')  # delete grant???
def delete_grant(request):
    response = dict()
    grant_id = request.matchdict.get('id')
    grant = DBSession.query(Grant).filter_by(id=grant_id).first()
    if grant:
        DBSession.delete(grant)
        request.response.status = HTTPOk.code
        return response
    request.response.status = HTTPNotFound.code
    return {'error': str("No such grant in the system")}


@view_config(route_name='grant', renderer='json', request_method='PUT', permission='admin')
def edit_grant(request):  # tested & in docs
    try:
        response = dict()
        grant_id = request.matchdict.get('id')
        client = DBSession.query(Client).filter_by(id=request.authenticated_userid).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.")
        grant = DBSession.query(Grant).filter_by(id=grant_id).first()
        if grant and not grant.marked_for_deletion:
            req = request.json_body
            if 'issuer_translation_gist_client_id' in req:
                grant.issuer_translation_gist_client_id = req['issuer_translation_gist_client_id']

            additional_metadata = req.get('additional_metadata')
            if additional_metadata:
                if additional_metadata.get('participant'):
                    request.response.status = HTTPBadRequest.code
                    return {'error': 'protected field'}

                old_meta = grant.additional_metadata
                old_meta.update(additional_metadata)
                grant.additional_metadata = old_meta
            request.response.status = HTTPOk.code
            return response
        request.response.status = HTTPNotFound.code
        return {'error': str("No such grant in the system")}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}


@view_config(route_name='create_grant', renderer='json', request_method='POST', permission='admin')
def create_grant(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        issuer_translation_gist_client_id = req['issuer_translation_gist_client_id']
        issuer_translation_gist_object_id = req['issuer_translation_gist_object_id']
        translation_gist_client_id = req['translation_gist_client_id']
        translation_gist_object_id = req['translation_gist_object_id']
        issuer_url = req['issuer_url']
        grant_url = req['grant_url']
        grant_number = req['grant_number']
        begin = req['begin']
        end = req['end']
        # owners = req['owners']
        # additional_metadata = req['additional_metadata']
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()

        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        grant = Grant(issuer_translation_gist_client_id=issuer_translation_gist_client_id,
                      issuer_translation_gist_object_id=issuer_translation_gist_object_id,
                      translation_gist_client_id=translation_gist_client_id,
                      translation_gist_object_id=translation_gist_object_id,
                      issuer_url=issuer_url,
                      grant_url=grant_url,
                      grant_number=grant_number,
                      begin=datetime.datetime.strptime(begin, "%d.%M.%Y").date(),
                      end=datetime.datetime.strptime(end, "%d.%M.%Y").date()
                      )
        DBSession.add(grant)
        DBSession.flush()

        request.response.status = HTTPOk.code
        return {'id': grant.id}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}
