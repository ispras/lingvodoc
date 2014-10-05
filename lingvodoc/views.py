from pyramid.response import Response
from pyramid.view import view_config

from sqlalchemy.exc import DBAPIError

from .models import (
    DBSession,
    MetaWord,
    WordEntry,
    Dictionary,
    User
    )

from pyramid.security import (
    Everyone,
    Allow,
    Deny
    )


from pyramid.httpexceptions import HTTPForbidden
from pyramid.httpexceptions import HTTPFound
from pyramid.httpexceptions import HTTPNotFound
from pyramid.security import authenticated_userid
from pyramid.security import forget
from pyramid.security import remember
from pyramid.view import forbidden_view_config


@view_config(route_name='home', renderer='json')
def demo(request):
    __acl__ = [(Deny, Everyone, 'view')]
    return {'status': 200}


def forbidden_view(request):
    # do not allow a user to login if they are already logged in
    if authenticated_userid(request):
        return HTTPForbidden()

    loc = request.route_url('login', _query=(('next', request.path),))
    return HTTPFound(location=loc)


def login_view(request):
    next = request.params.get('next') or request.route_url('home')
    login = ''
    did_fail = False
    if 'submit' in request.POST:
        login = request.POST.get('login', '')
        passwd = request.POST.get('passwd', '')

        user = User.get(login, None)
        if user and user.check_password(passwd):
            headers = remember(request, login)
            return HTTPFound(location=next, headers=headers)
        did_fail = True

    return {
        'login': login,
        'next': next,
        'failed_attempt': did_fail,
        'users': User,
    }







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

