__author__ = 'alexander'

from keycloak.exceptions import KeycloakGetError, KeycloakAuthenticationError

import lingvodoc.cache.caching as caching

from lingvodoc.exceptions import CommonException
from lingvodoc.models import (
    BaseGroup,
    Client,
    DBSession,
    Group,
    User, LOCALES_DICT
)
from lingvodoc.views.v2.utils import (
    get_user_by_client_id
)

from pyramid.httpexceptions import HTTPFound, HTTPForbidden
from pyramid.request import Request
from pyramid.view import forbidden_view_config

from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPNotFound,
    HTTPInternalServerError,
    HTTPOk,
    HTTPUnauthorized,
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
import logging
import json
from lingvodoc.utils.creation import add_user_to_group
from pyramid_mailer.message import Message
from pyramid.request import Request
import datetime
from time import sleep
from hashlib import md5
import requests
import traceback
import pprint

log = logging.getLogger(__name__)
from lingvodoc.keycloakld import KeycloakSession




@view_config(route_name='signup', renderer='templates/signup.pt', request_method='GET')
def signup_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/signup.pt', variables, request=request)


def new_user(login, name, email, password):
    """
    Creates a new user account with specified info.
    """

    try:
        user_id = KeycloakSession.keycloak_admin.create_user({"email": email,
                                                               "username": login,
                                                               "enabled": False,
                                                               "firstName": name,
                                                               "attributes": {
                                                                   "locale": ["ru"]}, },
                                                              exist_ok=False)
        KeycloakSession.keycloak_admin.set_user_password(user_id=user_id, password=password, temporary=False)
    except KeycloakGetError as e:
        raise CommonException("The user could not be registered" + e.error_message)

    # sync keyclaok db with lingvodoc
    new_user = User(id=user_id, created_at=datetime.datetime.utcnow())
    DBSession.add(new_user)

    KeycloakSession.keycloak_admin.assign_client_role(user_id=user_id,
                                                       client_id=KeycloakSession.keycloak_admin.get_client_id(
                                                           "lingvodoc"),
                                                       roles=[KeycloakSession.keycloak_admin.get_client_role(
                                                           client_id=KeycloakSession.keycloak_admin.get_client_id(
                                                               "lingvodoc"),
                                                           role_name="Can create dictionaries"),
                                                           KeycloakSession.keycloak_admin.get_client_role(
                                                               client_id=KeycloakSession.keycloak_admin.get_client_id(
                                                                   "lingvodoc"),
                                                               role_name="Can create languages"),
                                                           KeycloakSession.keycloak_admin.get_client_role(
                                                               client_id=KeycloakSession.keycloak_admin.get_client_id(
                                                                   "lingvodoc"),
                                                               role_name="Can create translation strings")])

    basegroups = []
    basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create dictionaries").first()]
    basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create languages").first()]
    basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create translation strings").first()]

    groups = []
    for base in basegroups:
        groups += [DBSession.query(Group).filter_by(subject_override=True, base_group_id=base.id).first()]

    for group in groups:
        add_user_to_group(new_user, group)

    DBSession.flush()


@view_config(route_name='signup', renderer='json', request_method='POST')
def signup_post(request):
    try:
        req = request.json_body
        login = req['login']
        name = req['name']
        email = req['email']
        password = req['password']

        # If we require user signup approval, we save user data and send pending approval email.

        signup_settings = request.registry.settings['signup']
        if signup_settings.get('approve'):

            if 'address' not in signup_settings:
                raise Exception('User signup approval email address is not specified')

            user_dict = {
                'login': login,
                'name': name,
                'email': email,
                'password': password}

            user_digest = md5(repr(list(sorted(user_dict.items()))).encode('utf-8')).hexdigest()
            cache_key = 'signup:' + user_digest

            cache_result = caching.CACHE.get(cache_key)

            # If we already have info of this user saved, it means that we already have their registration
            # pending approval, so we do nothing.

            if cache_result:
                return {'result': 'Already have signup of such user pending approval.'}

            # Otherwise we save user info and send signup approval email.

            caching.CACHE.set(cache_key, user_dict)

            if 'api_url' in req:
                approve_url = req['api_url'] + '/signup_approve?key={0}'.format(user_digest)

            else:
                approve_url = request.route_url('signup_approve') + '?key={0}'.format(user_digest)

            message = Message(
                subject='User \'{0}\' signup approval'.format(login),
                sender='noreply@ispras.ru',
                recipients=signup_settings['address'],
                body='User signup is pending approval. User\'s data:\n\n'
                     'Login: {0}\nName: {1}\nEmail: {2}\n\n'
                     'To approve, please follow this link:\n{3}\n'.format(
                    login, name, email, approve_url))

            request.registry.mailer.send_immediately(message, fail_silently=False)
            return {'result': 'Signup approval pending.'}

        # No approval required, we just create new user account.

        new_user(login, name, email, password)
        try:
            new_user(login, name, email, password)
        except  KeycloakGetError as e:
            return {'error': 'The user could not be registered because {}'.format(e.error_message)}
        return {'result': 'Signup success.'}

    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'status': request.response.status, 'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}

    except ValueError as e:
        request.response.status = HTTPConflict.code
        return {'status': request.response.status, 'error': str(e)}

    # Some unknown error.

    except Exception as exception:

        request.response.status = HTTPInternalServerError.code
        return {'status': request.response.status, 'error': repr(exception)}


@view_config(route_name='signup_approve', renderer='json')
def signup_approve(request):
    """
    Used to approve moderated user signups.
    """

    log.debug('signup_approve')

    try:
        user_digest = request.params.get('key')

        if not user_digest:
            return {'error': 'No signup identifier supplied.'}

        log.debug('signup_approve {0}'.format(user_digest))

        cache_key = 'signup:' + user_digest
        cache_result = caching.CACHE.get(cache_key)

        if cache_result is None:
            return {'error': 'Unknown signup identifier. Perhaps this signup was already approved?'}

        log.debug('signup_approve {0}:\n{1}'.format(user_digest, pprint.pformat(cache_result)))

        # Checking if we have any user accounts with supplied login or email.
        #
        # NOTE: In normal operation this shouldn't be possible, as the same checks are made during signup,
        # but this is useful for debugging.

        login = cache_result['login']
        name = cache_result['name']
        email = cache_result['email']

        # Creating new user account, removing user data from cache, sending notification email.
        try:
            new_user(**cache_result)
        except  KeycloakGetError as e:
            caching.CACHE.rem(cache_key)
            return {'error': 'The user could not be registered because {}'.format(e.error_message)}

        caching.CACHE.rem(cache_key)
        message = Message(
            subject='Signup approval notification',
            sender='noreply@ispras.ru',
            recipients=[email],
            body='User account \'{0}\' ({1}) with your '
                 'email address was registred at Lingvodoc {2}.\n'.format(
                login, name, request.application_url))

        log.debug('signup_approve {0}:\n'
                  'From: {1}\nTo: {2}\nSubject: {3}\n{4}'.format(user_digest,
                                                                 message.sender, ', '.join(message.recipients),
                                                                 message.subject, message.body.rstrip()))

        request.registry.mailer.send_immediately(message, fail_silently=False)
        return {'result': 'Signup success.'}

    # Handling any possible exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('signup_approve: exception')
        log.debug(traceback_string)

        request.response.status = HTTPInternalServerError.code
        return {'error': repr(exception), 'traceback': traceback_string}


@view_config(route_name='login', renderer='templates/login.pt', request_method='GET')
def login_get(request):
    variables = {'auth': authenticated_userid(request)}
    return render_to_response('templates/login.pt', variables, request=request)


@view_config(route_name='login', request_method='POST', renderer='json')
def login_post(request):
    login = request.POST.get('login', '')
    password = request.POST.get('password', '')
    log.debug(login)
    keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(login)
    token = KeycloakSession.create_token(login, password)
    if keycloak_user_id and token:
        client = Client(user_id=keycloak_user_id)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, userid=client.id, max_age=315360000)
        response = Response()
        response.headers = headers
        locale_id = LOCALES_DICT.get(KeycloakSession.keycloak_admin.get_user(keycloak_user_id)["attributes"].get("locale", None)[0], None)
        if not locale_id:
            locale_id = 1
        response.set_cookie('locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('client_id', value=str(client.id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('auth_tkt', value=token['access_token'], max_age=datetime.timedelta(days=3650),
                            samesite='lax')
        response.set_cookie('refresh_token', value=token['refresh_token'], max_age=datetime.timedelta(days=3650),
                            samesite='lax')
        return HTTPOk(headers=response.headers, json_body={})
    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='signin', renderer='json', request_method='POST')
def signin(request):
    req = request.json_body
    login = req['login']
    password = req['password']
    desktop = req.get('desktop', False)

    keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(login)
    token = KeycloakSession.create_token(login, password)
    if keycloak_user_id and token:

        client = Client(user_id=keycloak_user_id, is_browser_client=not desktop)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, userid=client.id, max_age=315360000)
        response = Response()
        response.headers = headers

        locale_id = LOCALES_DICT.get(KeycloakSession.keycloak_admin.get_user(keycloak_user_id).get("attributes", None).get("locale", None)[0], None)
        if not locale_id:
            locale_id = 1

        response.set_cookie('locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('client_id', value=str(client.id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('auth_tkt', value=token['access_token'], max_age=datetime.timedelta(days=3650),
                            samesite='lax')
        response.set_cookie('refresh_token', value=token['refresh_token'], max_age=datetime.timedelta(days=3650),
                            samesite='lax')
        result = dict()
        result['client_id'] = client.id
        request.response.status = HTTPOk.code

        return HTTPOk(headers=response.headers, json_body=result)

    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='sync_signin', renderer='json', request_method='POST')
def sync_signin(request):
    req = request.json_body
    login = req['login']
    password = req['password']

    keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(login)
    token = KeycloakSession.create_token(login, password)
    if keycloak_user_id and token:
        request.response.status = HTTPOk.code
        return HTTPOk(json_body={})

    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='desk_signin', renderer='json', request_method='POST')
def desk_signin(request):
    req = request.json_body
    req['desktop'] = True
    settings = request.registry.settings
    try:
        path = settings['desktop']['central_server'] + 'signin'
        session = requests.Session()
        session.headers.update({'Connection': 'Keep-Alive'})
        adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
        session.mount('http://', adapter)
        status = session.post(path, json=req)
        client_id = status.json()['client_id']
        cookies = status.cookies.get_dict()

        response = Response()
        headers = remember(request, userid=client_id, max_age=315360000)
        response.headers = headers
        locale_id = cookies['locale_id']
        response.set_cookie('locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('client_id', value=str(client_id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('server_cookies', value=json.dumps(cookies), max_age=datetime.timedelta(days=3650),
                            samesite='lax')
        sub_headers = response.headers
        sub_headers = dict(sub_headers)
        sub_headers['Cookie'] = sub_headers['Set-Cookie']
        if status.status_code == 200:
            path = request.route_url('basic_sync')
            subreq = Request.blank(path)
            subreq.method = 'POST'
            subreq.headers = sub_headers
            print('headers', subreq.headers)
            resp = request.invoke_subrequest(subreq)
            if resp.status_code == 200:
                headers = remember(request, userid=client_id, max_age=315360000)
                response = Response()
                response.headers = headers
                locale_id = cookies['locale_id']
                response.set_cookie('locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650),
                                    samesite='lax')
                response.set_cookie('client_id', value=str(client_id), max_age=datetime.timedelta(days=3650),
                                    samesite='lax')
                response.set_cookie('server_cookies', value=json.dumps(cookies), max_age=datetime.timedelta(days=3650),
                                    samesite='lax')
                result = dict()
                result['client_id'] = client_id
                request.response.status = HTTPOk.code
                return HTTPOk(headers=response.headers, json_body=result)
    except HTTPUnauthorized:
        return HTTPUnauthorized(json_body={'error': 'Login or password is wrong, please retry'})
    # except Exception:
    #     return HTTPServiceUnavailable(json_body={'error': 'You have no internet connection or Lingvodoc server is unavailable; please retry later.'})


@view_config(route_name='new_client_server', renderer='json', request_method='POST')
def new_client_server(request):
    old_client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
    if old_client:
        user = old_client.user
        if user:
            client = Client(user_id=user.id, is_browser_client=True)
            user.clients.append(client)
            DBSession.add(client)
            DBSession.flush()
            headers = remember(request, userid=client.id, max_age=315360000)
            response = Response()
            response.headers = headers
            locale_id = LOCALES_DICT.get(KeycloakSession.keycloak_admin.get_user(user.id).get("attributes", None).get("locale", None)[0], None)
            if not locale_id:
                locale_id = 1
            response.set_cookie('locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650), samesite='lax')
            response.set_cookie('client_id', value=str(client.id), max_age=datetime.timedelta(days=3650), samesite='lax')
            result = dict()
            result['client_id'] = client.id
            request.response.status = HTTPOk.code
            return HTTPOk(headers=response.headers, json_body=result)
    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='new_client', renderer='json', request_method='POST')
def new_client(request):
    settings = request.registry.settings

    path = settings['desktop']['central_server'] + 'sync/client/server'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    status = session.post(path, cookies=json.loads(request.cookies.get('server_cookies')))
    cookies = status.cookies.get_dict()
    client_id = status.json()['client_id']

    if status.status_code == 200:
        headers = remember(request, userid=client_id)
        response = Response()
        response.headers = headers
        locale_id = cookies['locale_id']
        response.set_cookie('locale_id', value=str(locale_id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('client_id', value=str(client_id), max_age=datetime.timedelta(days=3650), samesite='lax')
        response.set_cookie('server_cookies', value=json.dumps(cookies), max_age=datetime.timedelta(days=3650),
                            samesite='lax')
        result = dict()
        result['client_id'] = client_id
        result['server_cookies'] = cookies
        request.response.status = HTTPOk.code
        response.status = HTTPOk.code
        response.json_body = result
        return HTTPOk(headers=response.headers, json_body=result)
    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='cheatlogin', request_method='POST', renderer='json')
def login_cheat(request):  # TODO: test
    next = request.params.get('next') or request.route_url('dashboard')
    login = request.json_body.get('login', '')
    passwordhash = request.json_body.get('passwordhash', '')
    log.debug("Logging in with cheat method:" + login)
    user = DBSession.query(User).filter_by(login=login).first()
    keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(login)
    if user and user.password.hash == passwordhash:
        log.debug("Login successful")
        client = Client(user_id=keycloak_user_id)
        DBSession.add(client)
        DBSession.flush()
        headers = remember(request, userid=client.id)
        response = Response()
        response.headers = headers
        locale_id = LOCALES_DICT.get(KeycloakSession.keycloak_admin.get_user(keycloak_user_id).get("attributes", None).get("locale", None)[0], None)
        if not locale_id:
            locale_id = 1
        response.set_cookie('locale_id', value=str(locale_id), samesite='lax')
        response.set_cookie('client_id', value=str(client.id), samesite='lax')
        return response

    log.debug("Login unsuccessful for " + login)
    return HTTPUnauthorized(location=request.route_url('login'))


@view_config(route_name='logout', renderer='json')
def logout_any(request):  # tested
    response = Response()
    response.headers = forget(request)
    response.set_cookie('client_id', value=None)
    response.set_cookie('auth_tkt', value=None)
    response.set_cookie('refresh_token', value=None)
    response.status_code = 200
    response.json_body = {}
    return response


@view_config(route_name='profile', renderer='templates/profile.pt', request_method='GET')
def profile_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    if user is None:
        response = Response()
        return HTTPFound(location=request.route_url('login'), headers=response.headers)
    variables = {'client_id': client_id, 'user': user}
    return render_to_response('templates/profile.pt', variables, request=request)


@view_config(route_name='users', renderer='json', request_method='GET')
def users_list(request):
    response = dict()
    response['users'] = KeycloakSession.keycloak_admin.get_users()
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='get_user_info', renderer='json', request_method='GET')
def get_user_info(request):  # tested
    response = dict()
    client_id = request.params.get('client_id')
    user_id = request.params.get('user_id')
    if client_id:
        client = DBSession.query(Client).filter_by(id=client_id).first()
        if not client:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such client in the system")}
        user = KeycloakSession.keycloak_admin.get_user(client.user_id)
        if not user:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such user in the system")}
    elif user_id:
        user = KeycloakSession.keycloak_admin.get_user(user_id)
        if not user:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such user in the system")}
    else:
        client = DBSession.query(Client).filter_by(id=authenticated_userid(request)).first()
        if not client:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such client in the system")}
        user = KeycloakSession.keycloak_admin.get_user(client.user_id)
        if not user:
            request.response.status = HTTPNotFound.code
            return {'error': str("No such user in the system")}
    response['id'] = user["id"]
    response['login'] = user["username"]
    response['name'] = user["firstName"]
    response['intl_name'] = user["username"]
    response['default_locale_id'] = LOCALES_DICT.get(user.get("attributes", None).get("locale", None)[0], None)
    response['created_at'] = user["createdTimestamp"]
    response['is_active'] = user["enabled"]
    response['email'] = user["email"]

    # organizations = []
    # for organization in user.organizations:
    #     organizations += [{'organization_id': organization.id}]
    # response['organizations'] = organizations
    #
    # if request.params.get('roles'):
    #
    #     roles = list()
    #     for group in user.groups:
    #         role = dict()
    #         role['name'] = group.parent.name
    #         role['subject_override'] = group.subject_override
    #         if group.subject_client_id:
    #             role['subject_client_id'] = group.subject_client_id
    #         if group.subject_object_id:
    #             role['subject_object_id'] = group.subject_object_id
    #         roles.append(role)
    #     response['roles'] = roles
    #
    # request.response.status = HTTPOk.code
    return response


@view_config(route_name='get_user_info', renderer='json', request_method='PUT')
def edit_user_info(request):  # TODO: Alex

    response = dict()

    req = request.json_body
    user = None

    variables = {'auth': request.authenticated_userid}
    client = DBSession.query(Client).filter_by(id=variables['auth']).first()
    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       variables['auth'])
    user = KeycloakSession.keycloak_admin.get_user(client.user_id)
    if not user:
        raise CommonException("This client id is orphaned. Try to logout and then login once more.")

    new_password = req.get('new_password')
    old_password = req.get('old_password')

    if new_password:
        if not old_password:
            request.response.status = HTTPBadRequest.code
            return {'error': str("Need old password to confirm")}
        try:
            token = KeycloakSession.openid_client.token(user["username"], old_password)

        except KeycloakAuthenticationError:
            return {'error': str("Wrong password")}
        KeycloakSession.keycloak_admin.set_user_password(user_id=client.user_id, password=new_password, temporary=False)

    name = req.get('name', user["username"])
    email = req.get('email', user["username"])

    default_locale_id = req.get('default_locale_id', user["attributes"].get("locale", None)[0])
    if default_locale_id:
        user["attributes"]["locale"] = default_locale_id
    KeycloakSession.keycloak_admin.update_user(user_id = client.user_id, payload={'username': name, 'email': email, "attributes": user["attributes"]})
    request.response.status = HTTPOk.code
    return response
