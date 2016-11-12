__author__ = 'alexander'

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Email,
    Group,
    Passhash,
    User
)
from lingvodoc.views.v2.utils import (
    get_user_by_client_id
)

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPNotFound,
    HTTPInternalServerError,
    HTTPOk,
    HTTPUnauthorized
)
from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.security import (
    authenticated_userid,
    forget,
    remember
)
from pyramid.view import view_config

from sqlalchemy import (
    or_
)

import datetime
import logging
import json
from lingvodoc.views.v2.utils import add_user_to_group

log = logging.getLogger(__name__)


@view_config(route_name='basic_sync', renderer='json', request_method='POST')
def basic_sync(request):
    req = request.json_body
    login = req['login']
    password = req['password']

    user = DBSession.query(User).filter_by(login=login).first()
    if user and user.check_password(password):
        request.response.status = HTTPOk.code
        return HTTPOk(json_body={})
    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='basic_sync_server', renderer='json', request_method='GET')
def basic_sync_server(request):
    response = dict()
    row2dict = lambda r: {c.name: getattr(r, c.name) for c in r.__table__.columns}
    print(type(row2dict(Client)))
    print(row2dict(Client))
    client = DBSession.query(Client).first()
    response['clients'] = row2dict(client)
    # response['users'] = row2dict(User)
    # response['basegroups'] = row2dict(BaseGroup)
    return response