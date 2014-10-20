from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy.exc import DBAPIError

from .models import (
    DBSession,
    MetaWord,
    WordEntry,
    Dictionary,
    User,
    Client,
    Email,
    Passhash,
    Group,
    BaseGroup
    )

from pyramid.security import (
    Everyone,
    Allow,
    Deny
    )


from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.httpexceptions import HTTPNotFound, HTTPOk, HTTPBadRequest, HTTPConflict
from pyramid.httpexceptions import HTTPUnauthorized
from pyramid.security import authenticated_userid
from pyramid.security import forget
from pyramid.security import remember
from pyramid.view import forbidden_view_config

#from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response

import datetime


class CommonException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def group_filter(session, base_group_name, subject):
    group_limited = session.query(BaseGroup).filter(BaseGroup.name == base_group_name).first()
    groups_fit = []
    for group in group_limited.groups:
        if group.subject == subject:
            groups_fit.append(group)
    return groups_fit


def forbidden_view(request):
    # do not allow a user to login if they are already logged in
    if authenticated_userid(request):
        return HTTPForbidden()

    loc = request.route_url('login', _query=(('next', request.path),))
    return HTTPFound(location=loc)

@view_config(route_name='register/validate', renderer='json', request_method='POST')
def validate(request):
    try:
        param = request.matchdict.get('param')
        print(param)
        value = request.POST.getone(param)
        if param == 'email':
            dbentry = DBSession.query(Email).filter_by(email=value).first()
            if dbentry:
                raise CommonException("The user with this email is already registered")
        elif param == 'login':
            dbentry = DBSession.query(User).filter_by(login=value).first()
            if dbentry:
                raise CommonException("The user with this login is already registered")
        else:
            raise KeyError

        request.response.status = HTTPOk.code
        return {'status': request.response.status}

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='home', renderer='templates/home.pt')
def main_page(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/home.pt', variables, request=request)


@view_config(route_name='register', renderer='templates/register.pt', request_method='GET')
def register_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/register.pt', variables, request=request)


@view_config(route_name='register', renderer='json', request_method='POST')
def register_post(request):
    try:
        login = request.POST.getone('login')
        name = request.POST.getone('name')
        email = request.POST.getone('email')
        password = request.POST.getone('password')

        if DBSession.query(User).filter_by(login=login).first():
            raise CommonException("The user with this login is already registered")
        if DBSession.query(Email).filter_by(email=email).first():
            raise CommonException("The user with this email is already registered")
        new_user = User(login=login, name=name, signup_date=datetime.datetime.utcnow(), is_active=True)
        pwd = Passhash(password=password)
        email = Email(email=email)
        new_user.password = pwd
        new_user.email.append(email)
        DBSession.add(new_user)
        DBSession.flush()

        # adding user to needed groups
        for group in group_filter(DBSession, 'can_create_dictionaries', 'ANY'):
            new_user.groups.append(group)

        for group in group_filter(DBSession, 'adm_can_create_languages', 'ANY'):
            new_user.groups.append(group)

        for group in group_filter(DBSession, 'adm_can_edit_languages', 'ANY'):
            new_user.groups.append(group)

        for group in group_filter(DBSession, 'adm_can_create_organizations', 'ANY'):
            new_user.groups.append(group)

        return login_post(request)

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}


@view_config(route_name='login', renderer='templates/login.pt', request_method='GET')
def login_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/login.pt', variables, request=request)


@view_config(route_name='login', renderer='json', request_method='POST')
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


@view_config(route_name='logout', renderer='json')
def logout_any(request):
    next = request.params.get('next') or request.route_url('home')
    headers = forget(request)
    return HTTPFound(location=next, headers=headers)


@view_config(route_name='dashboard', renderer='templates/dashboard.pt', request_method='GET')
def dashboard(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/dashboard.pt', variables, request=request)


@view_config(route_name='create_dictionary_page', renderer='templates/create_dictionary_page.pt', request_method='GET')
def create_dictionary_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/create_dictionary_page.pt', variables, request=request)

@view_config(route_name='create_dictionary', renderer='json', request_method='POST')
def create_dictionary_post(request):
    variables = {'auth': authenticated_userid(request)}
    return {'status': 200}


@view_config(route_name="create_language_page", renderer='templates/create_language.pt', request_method='GET')
def create_language_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/create_language.pt', variables, request=request)

@view_config(route_name="create_language", renderer='json', request_method='POST')
def create_language_post(request):
    return {'status': 200}

#@view_config(route_name='login', renderer='')
def login(request):
    """
    user authentication on-site ('user-to-project').
    :param request:
    :return:
    """

    return


#@view_config(route_name='logout')
def logout(request):
    """
    user logout button on-site ('api')
    :param request:
    :return:
    """
    return


#@view_config(route_name='register')
def register(request):
    """
    user registration page on-site ('user-to-project').
    :param request:
    :return:
    """
    return


#@view_config(route_name='acquire_client_key')
def acquire_client_key(request):
    """
    get key for client program ('client-to-server')
    :param request:
    :return:
    """
    return


#@view_config(route_name='dictionaries.list', renderer='json', permission='view')
def list_dictionaries(request):
    """
    list existing dictionaries ('user-to-project')
    :param request: filter=all,approved,pending
    :return:
    """
    return {'Dicts': [request.context.dictionaries.first()]}


#@view_config(route_name='dictionary')
def view_dictionary(request):
    return


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

