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
    Email
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


class CommonException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

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


@view_config(route_name='register', renderer='json', request_method='GET')
def register_get(request):
    return {'status': 200}

@view_config(route_name='register', renderer='json', request_method='POST')
def register_post(request):
    did_fail = False
    try:
        login = request.POST.getone('login')
        name = request.POST.getone('name')
        email = request.POST.getone('email')
        password = request.POST.getone('password')

        if DBSession.query(User).filter_by(login=login).first():
            raise CommonException("The user with this login is already registered")
        if DBSession.query(Email).filter_by(email=email).first():
            raise CommonException("The user with this email is already registered")

    except CommonException as e:
        return {'failed_attempt': True, 'reason': str(e)}

    except KeyError as e:
        return {'failed_attempt': True, 'reason': str(e)}

'''
    id = Column(Integer, primary_key=True)
    login = Column(Unicode(length=30), unique=True)
    name = Column(UnicodeText)
    # this stands for name in English
    intl_name = Column(UnicodeText)
    default_locale_id = Column(ForeignKey("Locale.id"))
    birthday = Column(Date)
    signup_date = Column(DateTime)
    # it's responsible for "deleted user state". True for active, False for deactivated.
    is_active = Column(Boolean)
    clients = relationship("Client", backref='User')
    groups = relationship("Group", secondary=user_to_group_association, backref="Users")
    password = relationship("Passhash", uselist=False)
    email = relationship("Email")
    about = relationship("About")

    return {'failed_attempt': did_fail}
'''

@view_config(route_name='login', renderer='json', request_method='GET')
def login_get(request):
    return {'status': 200}


@view_config(route_name='login', renderer='json', request_method='POST')
def login_view(request):
    next = request.params.get('next') or request.route_url('home')
    login = request.POST.get('login', '')
    password = request.POST.get('password', '')

    user = DBSession.query(User).filter_by(login=login).first()
    if user and user.check_password(password):
        client = Client(user_id=user.id)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, principal=client.id)
        return HTTPFound(location=next, headers=headers)
# TODO: delete debug info
    return {
        'login': login,
        'next': next,
        'users': user.login,
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

