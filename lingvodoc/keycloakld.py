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

    def migrate_users(self):

        users = DBSession.query(User).all()
        for user in users:
            if user.login == "aralova":
                try:
                    keycloak_user_id = self._keycloak_admin.get_user_id(user.login)
                    if keycloak_user_id:
                        self._keycloak_admin.set_user_password(user_id=keycloak_user_id, password="secret", temporary=False)
                    else:
                        attributes = dict()
                        self.create_user_associated_resources(attributes, user)
                        attributes.update({"locale": [LOCALES_DICT.get(user.default_locale_id, "en")]})
                        user_id = self._keycloak_admin.create_user({"email": user.email.email,
                                                                    "username": user.login,
                                                                    "enabled": user.is_active,
                                                                    "createdTimestamp": user.created_at,
                                                                    "firstName": user.name,
                                                                    "credentials": [
                                                                        {"value": "secret", "type": "password"}],
                                                                    "attributes": attributes,
                                                                    })

                        DBSession.query(User).filter_by(id=user.id).update(values={"id": user_id},
                                                                           synchronize_session='fetch')
                        DBSession.flush()

                except (KeycloakGetError, KeycloakOperationError, KeycloakPostError, Exception) as e:
                    logging.debug(e.error_message)
                    with open("users.txt", 'a+') as f:
                        if user:
                            f.write("user: {} error: {}\n".format(user.__dict__, e.error_message))

    def create_user_associated_resources(self, attributes=None, user=User):
        if attributes is None:
            attributes = dict()
        subjects = ["dictionary", "language", "translation_string", "edit_user", "perspective_role", "dictionary_role",
                    "organization", "perspective", "lexical_entries_and_entities", "approve_entities", "merge",
                    "translations", "grant", "dictionary_status", "perspective_status"]
        actions = ["approve", "create", "delete", "edit", "view"]
        for subject in subjects:
            for action in actions:
                objects = DBSession.query(BaseGroup, Group, user_to_group_association, Group.subject_client_id,
                                          Group.subject_object_id).filter(and_(
                    BaseGroup.subject == subject,
                    BaseGroup.action == action,
                    Group.base_group_id == BaseGroup.id,
                    user_to_group_association.c.user_id == user.id,
                    user_to_group_association.c.group_id == Group.id)).all()
                ids = list()
                if len(objects) > 0:
                    scope = "urn:" + self.client_name + ":scopes:" + action
                    resource = "urn:" + self.client_name + ":resources:" + subject
                    for obj in objects:
                        # по всем найденым объектам проверяем, есть ли id
                        if obj.Group.subject_client_id and obj.Group.subject_object_id:
                            ids.append(str(obj.Group.subject_client_id) + "/" + str(obj.Group.subject_object_id))
                            name = subject + "/" + str(obj.Group.subject_client_id) + "/" + str(
                                obj.Group.subject_object_id)

                            resource_to_create = {
                                "name": name,
                                "scopes": [scope],
                                "type": resource,
                                "uri": str(obj.Group.subject_client_id) + "/" + str(
                                    obj.Group.subject_object_id),
                            }
                            try:
                                created_resource = self.keycloak_uma.resource_set_create(resource_to_create)
                            except (KeycloakGetError, KeycloakOperationError, KeycloakPostError) :
                                logging.debug("Keycloak could not create resource with name " + name)
                                try:
                                    already_created_resource = self.keycloak_uma.resource_set_list_ids(
                                        name=name)
                                    already_created_resource = self.keycloak_uma.resource_set_read(
                                        already_created_resource[0])
                                    if len(already_created_resource) > 0:
                                        already_created_resource["scopes"].append(
                                            {'name': scope})
                                        self.keycloak_uma.resource_set_update(
                                            already_created_resource["_id"], already_created_resource)
                                except (KeycloakGetError, KeycloakOperationError, KeycloakPostError) as e:
                                    logging.debug("Keycloak could not update resource with new scope" + e.error_message)
                    if len(ids) > 0:
                        attributes.update({resource + ";" + scope: ids})
        return attributes

    def add_mappers(self):
        subjects = ["dictionary", "language", "translation_string", "edit_user", "perspective_role", "dictionary_role",
                    "organization", "perspective", "lexical_entries_and_entities", "approve_entities", "merge",
                    "translations", "grant", "dictionary_status", "perspective_status"]
        actions = ["approve", "create", "delete", "edit", "view"]
        for subject in subjects:
            for action in actions:
                try:
                    self.keycloak_admin.add_mapper_to_client(
                        # client_id='****',
                        payload={
                            "name": action + '_' + subject,
                            "protocol": "openid-connect",
                            "protocolMapper": "oidc-usermodel-attribute-mapper",
                            "consentRequired": "false",
                            "config": {
                                "aggregate.attrs": "false",
                                "userinfo.token.claim": "true",
                                "multivalued": "false",
                                "user.attribute": "urn:" + self.client_name + ":resources:" + subject + ";" + "urn:" + self.client_name + ":scopes:" + action,
                                "id.token.claim": "true",
                                "access.token.claim": "true",
                                "claim.name": "urn:" + self.client_name + ":resources:" + subject + ";" + "urn:" + self.client_name + ":scopes:" + action}
                        }, )
                except KeycloakPostError as e:
                    logging.debug(e.error_message)


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
