import functools
from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakOpenIDConnection, KeycloakUMA

from pyramid.authentication import CallbackAuthenticationPolicy
import logging
import warnings

from keycloak.exceptions import KeycloakError
from pyramid.interfaces import IAuthenticationPolicy
from pyramid.security import Everyone, Authenticated
from zope.interface import implementer

LOG = logging.getLogger(__name__)


class KeycloakLD:
    def __init__(self, openid_client=None, keycloak_admin=None, keycloak_uma=None, realm_name=None, server_url=None,
                 admin=None, password=None, realm_name_admin=None, client_name=None, client_secret_key=None, timeout=None):
        self._openid_client = openid_client
        self._keycloak_admin = keycloak_admin
        self._keycloak_uma = keycloak_uma
        self.client_name = client_name
        self.realm_name = realm_name
        self.server_url = server_url
        self.admin = admin
        self.password = password
        self.realm_name_admin = realm_name_admin
        self.client_secret_key = client_secret_key
        self.timeout = timeout

    @property
    def client_name(self):
        return self._client_name

    @client_name.setter
    def client_name(self, value):
        self._client_name = value

    @property
    def openid_client(self):
        return self._openid_client

    @openid_client.setter
    def openid_client(self, value):
        self._openid_client = value

    @property
    def keycloak_admin(self):
        return self._keycloak_admin

    @keycloak_admin.setter
    def keycloak_admin(self, value):
        self._keycloak_admin = value

    @property
    def keycloak_uma(self):
        return self._keycloak_uma

    @keycloak_uma.setter
    def keycloak_uma(self, value):
        self._keycloak_uma = value

    def create_token(self, login, password):
        try:
            token = self._openid_client.token(
                login, password)
            return token
        except KeycloakError as e:
            LOG.debug("Could not create the token: {}"
                      .format(str(e)))
            return None
    def connect(self, realm_name, server_url, admin, password, realm_name_admin, client_name, client_secret_key, timeout):
        self.realm_name = realm_name
        self.server_url = server_url
        self.admin = admin
        self.password = password
        self.realm_name_admin = realm_name_admin
        self.client_secret_key = client_secret_key
        self.client_name = client_name
        self.keycloak_url = client_secret_key
        self.timeout = timeout
        self.keycloak_admin = KeycloakAdmin(server_url=server_url,
                                            username=admin,
                                            password=password,
                                            realm_name=realm_name_admin,
                                            auto_refresh_token=["get", "post", "put", "delete"], timeout=timeout)
        self.keycloak_admin.realm_name = realm_name
        self.openid_client = KeycloakOpenID(server_url=server_url,
                                            client_id=client_name,
                                            realm_name=realm_name,
                                            client_secret_key=client_secret_key, timeout=timeout)

        uma = KeycloakUMA(connection=KeycloakOpenIDConnection(
            custom_headers={"Content-Type": "application/x-www-form-urlencoded"},
            server_url=server_url,
            realm_name=realm_name,
            client_id=client_name,
            client_secret_key=client_secret_key, timeout=timeout))
        self.keycloak_uma = uma

KeycloakSession = KeycloakLD()

def handle_with(handler, *exceptions):
    try:
        handler, cleanup = handler
    except TypeError:
        cleanup = lambda f, e: None

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            e = None
            try:
                return func(*args, **kwargs)
            except exceptions or Exception as e:
                return handler(func, e)
            finally:
                cleanup(func, exceptions)

        return wrapper

    return decorator


def message(func, e):
    if type(e) is AttributeError:
        KeycloakSession.connect(KeycloakSession.realm_name, KeycloakSession.server_url, KeycloakSession.admin,
                                KeycloakSession.password, KeycloakSession.realm_name_admin, KeycloakSession.client_name,
                                KeycloakSession.client_secret_key, KeycloakSession.timeout)

    else:
        logging.warning("Exception", type(e).__name__)
        logging.warning(str(e))

@implementer(IAuthenticationPolicy)
class KeycloakBasedAuthenticationPolicy(CallbackAuthenticationPolicy):
    def __init__(self, openid_client,
                 access_token_cookie_name="auth_tkt",
                 refresh_token_cookie_name="refresh_token"):

        self._openid_client = openid_client
        self.access_token_cookie_name = access_token_cookie_name
        self.refresh_token_cookie_name = refresh_token_cookie_name

    @handle_with(message, AttributeError)
    def authenticated_userid(self, request):

        access_token, refresh_token, client_id = request.unauthenticated_userid
        if not access_token:
            return None

        principal = self._introspect(access_token)
        principal = principal if principal is not None else {}
        principal["ld_client"] = client_id

        if not self._active_principal(principal):
            if not refresh_token:
                return None
            try:
                token_response = self._openid_client.refresh_token(
                    refresh_token)
            except KeycloakError as e:
                LOG.debug("Could not refresh the token: {}"
                          .format(str(e)))
                return None

            access_token = token_response.get("access_token")
            request.response.set_cookie(
                self.access_token_cookie_name, access_token)

            refresh_token = token_response.get("refresh_token")
            request.response.set_cookie(
                self.refresh_token_cookie_name, refresh_token)

            principal = self._introspect(access_token)
            principal["ld_client"] = client_id
            if not self._active_principal(principal):
                return None

        return client_id

    @handle_with(message, AttributeError)
    def unauthenticated_userid(self, request):
        access_token = request.cookies.get(self.access_token_cookie_name)
        refresh_token = request.cookies.get(self.refresh_token_cookie_name)
        client_id = request.cookies.get("client_id")

        return access_token, refresh_token, client_id

    @handle_with(message, AttributeError)
    def effective_principals(self, request):
        principals = [Everyone]
        user_principal = request.authenticated_userid

        if user_principal:
            roles = user_principal.get('realm_access', {}).get('roles', [])
            principals.append(Authenticated)
            for role in roles:
                principals.append(role)

        return principals

    def remember(self, request, userid, **kw):
        warnings.warn("Session is managed by Keycloak itself. Using remember()"
                      " has no effect.", stacklevel=3)
        return []

    @handle_with(message, AttributeError)
    def forget(self, request):
        refresh_token = request.cookies.get(self.refresh_token_cookie_name)

        try:
            self._openid_client.logout(refresh_token)
        except KeycloakError as e:
            LOG.debug("could not log out from keycloak: {}".format(str(e)))

        return [("Set-Cookie",
                 "{cookie_name}=; path=/; "
                 "expires=Thu, 01 Jan 1970 00:00:00 GMT"
                 .format(cookie_name=self.access_token_cookie_name)),
                ("Set-Cookie",
                 "{cookie_name}=; path=/; "
                 "expires=Thu, 01 Jan 1970 00:00:00 GMT"
                 .format(cookie_name=self.refresh_token_cookie_name))]

    @handle_with(message, AttributeError)
    def _introspect(self, access_token):
        principal = {}
        try:
            principal = self._openid_client.introspect(access_token)
            principal = principal if principal is not None else {}
        except KeycloakError as e:
            LOG.debug("Could not introspect token: {}".format(str(e)))

        return principal

    def _active_principal(self, principal):
        return bool(principal) and principal.get("active") is True
