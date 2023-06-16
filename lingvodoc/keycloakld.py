from keycloak.uma_permissions import UMAPermission
from pyramid.authentication import CallbackAuthenticationPolicy
from sqlalchemy import and_, or_

from .models import (
    DBSession,
    User,
    BaseGroup, LOCALES_DICT, Group, user_to_group_association)

import logging
import warnings

from keycloak.exceptions import KeycloakError, KeycloakGetError, KeycloakOperationError, KeycloakPostError, \
    KeycloakPutError
from pyramid.interfaces import IAuthenticationPolicy
from pyramid.security import Everyone, Authenticated
from zope.interface import implementer

LOG = logging.getLogger(__name__)


class KeycloakLD:
    def __init__(self, openid_client, keycloak_admin, keycloak_uma, client_name="lingvodoc"):
        self._openid_client = openid_client
        self._keycloak_admin = keycloak_admin
        self._keycloak_uma = keycloak_uma
        self.client_name = client_name

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


KeycloakSession = KeycloakLD(openid_client=None, keycloak_admin=None, keycloak_uma=None)


@implementer(IAuthenticationPolicy)
class KeycloakBasedAuthenticationPolicy(CallbackAuthenticationPolicy):
    def __init__(self, openid_client,
                 access_token_cookie_name="auth_tkt",
                 refresh_token_cookie_name="refresh_token"):

        self._openid_client = openid_client
        self.access_token_cookie_name = access_token_cookie_name
        self.refresh_token_cookie_name = refresh_token_cookie_name

    def authenticated_userid(self, request):

        access_token, refresh_token, client_id = request.unauthenticated_userid
        if not access_token:
            return None

        principal = self._introspect(access_token)
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

    def unauthenticated_userid(self, request):
        access_token = request.cookies.get(self.access_token_cookie_name)
        refresh_token = request.cookies.get(self.refresh_token_cookie_name)
        client_id = request.cookies.get("client_id")

        return access_token, refresh_token, client_id

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

    def _introspect(self, access_token):
        principal = {}
        try:
            principal = self._openid_client.introspect(access_token)
        except KeycloakError as e:
            LOG.debug("Could not introspect token: {}".format(str(e)))

        return principal

    def _active_principal(self, principal):
        return bool(principal) and principal.get("active") is True
