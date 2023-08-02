import functools
import secrets
import string
import random

from pyramid.authentication import CallbackAuthenticationPolicy
import logging
import warnings

from keycloak.exceptions import KeycloakError, KeycloakPutError
from pyramid.interfaces import IAuthenticationPolicy
from pyramid.security import Everyone, Authenticated
from sqlalchemy import and_
from zope.interface import implementer

from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakOpenIDConnection, KeycloakUMA, KeycloakOperationError, \
    KeycloakGetError, KeycloakPostError

from lingvodoc import DBSession

from lingvodoc.models import (
    User, Group, user_to_group_association)
from lingvodoc.models import LOCALES_DICT, BaseGroup
import lingvodoc.cache.caching as caching

LOG = logging.getLogger(__name__)


class KeycloakLD:
    REDIS_CACHE = caching.CACHE

    def __init__(self, openid_client=None, keycloak_admin=None, keycloak_uma=None, realm_name=None, server_url=None,
                 admin=None, password=None, realm_name_admin=None, client_name=None, client_secret_key=None,
                 timeout=None):
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

    def connect(self, realm_name, server_url, admin, password, realm_name_admin, client_name, client_secret_key,
                timeout):
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
                                            realm_name=realm_name,
                                            auto_refresh_token=["get", "post", "put", "delete"], timeout=timeout)
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

    # self.add_attribute("modis", "dictionary", "edit", 108, 3)
    def add_attribute(self, user_login, object_name, action, object_client_id, object_object_id):
        resource, scope, attributes, keycloak_user_id = self.set_attribute_fields(action,
                                                                                  user_login,
                                                                                  object_name,
                                                                                  object_client_id,
                                                                                  object_object_id)
        try:
            if attributes is None:
                attributes = [keycloak_user_id]
            else:
                attributes.append(keycloak_user_id)
            resource["attributes"][scope] = list(set(attributes))

            KeycloakSession.keycloak_uma.resource_set_update(
                resource["_id"], resource)
        except (KeycloakGetError, KeycloakOperationError, KeycloakPostError) as e:
            logging.debug(
                "Keycloak could not update resource with new attribute by user_id " + str(keycloak_user_id) + str(
                    e.error_message))

    # self.delete_attribute("modis", "dictionary", "edit", 108, 3)
    def delete_attribute(self, user_login, object_name, action, object_client_id, object_object_id):
        resource, scope, attributes, keycloak_user_id = self.set_attribute_fields(action,
                                                                                  object_name,
                                                                                  user_login,
                                                                                  object_client_id,
                                                                                  object_object_id)
        try:
            if attributes is None:
                raise KeycloakPostError(error_message="Could not find resource attribute")
            else:
                users_ids = list(resource["attributes"][scope])
                users_ids.remove(keycloak_user_id)
                attributes.append(keycloak_user_id)
                resource["attributes"][scope] = users_ids
                KeycloakSession.keycloak_uma.resource_set_update(
                    resource["_id"], resource)
        except (KeycloakGetError, KeycloakOperationError, KeycloakPostError) as e:
            logging.debug(
                "Keycloak could not update resource with new attribute by user_id " + str(keycloak_user_id) + str(
                    e.error_message))

    def set_attribute_fields(self, action, object_name, user_login, object_client_id, object_object_id):
        scope = "urn:" + self.client_name + ":scopes:" + action
        resource_name = str(object_name) + "/" + str(object_client_id) + "/" + str(
            object_object_id)
        keycloak_user_id = self.keycloak_admin.get_user_id(user_login)

        resource_ids = self.keycloak_uma.resource_set_list_ids(
            name=resource_name)
        resource = KeycloakSession.keycloak_uma.resource_set_read(
            resource_ids[0])

        attributes = resource["attributes"].get(scope, None)

        return resource, scope, attributes, keycloak_user_id

    def add_permissions(self, client_id):
        LOG.debug('ADD PERMISSIONS TO THE KEYCLOAK')
        subjects = ["dictionary", "language", "translation_string", "edit_user", "perspective_role", "dictionary_role",
                    "organization", "perspective", "lexical_entries_and_entities", "approve_entities", "merge",
                    "translations", "grant", "dictionary_status", "perspective_status"]
        actions = ["approve", "create", "delete", "edit", "view"]
        policies = KeycloakSession.keycloak_admin.get_client_authz_policies(client_id=client_id)
        scopes = KeycloakSession.keycloak_admin.get_client_authz_scopes(client_id=client_id)
        scope_id = policy_id = ""
        scopes_id_list = [scope["id"] for scope in scopes]
        for subject in subjects:
            try:
                for action in actions:
                    for scope in scopes:
                        if scope.get("name") == "urn:" + KeycloakSession.client_name + ":scopes:" + action:
                            scope_id = scope.get("id")
                            break
                    for policy in policies:
                        if policy.get("description") == "urn:" + KeycloakSession.client_name + ":policies:" + action:
                            policy_id = policy.get("id")
                            break
                    KeycloakSession.keycloak_admin.create_client_authz_scope_based_permission(
                        client_id=client_id,
                        payload={
                            "type": "resource",
                            "logic": "POSITIVE",
                            "decisionStrategy": "UNANIMOUS",
                            "name": "Resource owner can " + str(action) + " " + str(subject),
                            "resourceType": "urn:" + KeycloakSession.client_name + ":resources:" + subject,
                            "resources": [],
                            "scopes": [scope_id],
                            "policies": [policy_id]
                        }, skip_exists=True)
                for policy in policies:
                    if policy.get("name") == "Superadmin":
                        policy_id = policy.get("id")
                        break
                KeycloakSession.keycloak_admin.create_client_authz_scope_based_permission(
                    client_id=client_id,
                    payload={
                        "type": "resource",
                        "logic": "POSITIVE",
                        "decisionStrategy": "UNANIMOUS",
                        "name": "Superadmin can do everything with " + str(subject),
                        "resourceType": "urn:" + KeycloakSession.client_name + ":resources:" + subject,
                        "resources": [],
                        "scopes": scopes_id_list,
                        "policies": [policy_id]
                    }, skip_exists=True)
            except KeycloakPostError as e:
                logging.debug(e.error_message)
        LOG.debug('PERMISSIONS ADDED TO THE KEYCLOAK')

    def migrate_users(self, password="secret"):
        if self.REDIS_CACHE is None:
            self.REDIS_CACHE = caching.CACHE
        client_id = KeycloakSession.keycloak_admin.get_client_id(client_id=KeycloakSession.client_name)
        self.add_permissions(client_id)
        LOG.debug('START MIGRATION TO THE KEYCLOAK')
        users = DBSession.query(User).all()
        self.REDIS_CACHE.set_pure("keys", [])
        for user in users:
            with open("users_test_alembic.txt", 'a+') as f:
                user_name = user_login = secrets.token_hex(8)
                user_email = user_name + "@ispras.ru"
                try:
                    keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(user.login)
                    if keycloak_user_id is not None:
                        KeycloakSession.keycloak_admin.set_user_password(user_id=keycloak_user_id, password=password,
                                                                         temporary=False)
                        if DBSession.query(User).filter_by(id=keycloak_user_id).first() is None:
                            DBSession.query(User).filter_by(id=user.id).update(values={"id": keycloak_user_id},
                                                                               synchronize_session='fetch')
                            DBSession.flush()
                        else:
                            f.write(
                                "User already migrated or duplicated: {} user email {} , Keycloak ID: {}\n".format(
                                    user.__dict__, str(user.email.email),
                                    keycloak_user_id))

                    else:
                        attributes = dict()

                        attributes.update({"locale": [LOCALES_DICT.get(user.default_locale_id, "en")]})
                        if user.email.email == "":
                            f.write("Missing user email {} error: {} user will be created with email: {}\n".format(
                                user.__dict__, "Missing user email", user_email))

                        else:
                            user_email = str(user.email.email)
                        if user.name == "":
                            f.write(
                                "Missing user name {}  user email {} error: {} user will be created with name: {}\n".format(
                                    user.__dict__, user_email,
                                    "Missing user name", user_name))
                        else:
                            user_name = user.name
                        if user.login == "":
                            f.write(
                                "Missing user login {} user email {} error: {} user will be created with email: {}\n".format(
                                    user.__dict__, user_email,
                                    "Missing user login", user_login))
                        else:
                            user_login = user.login

                        for key, value in attributes.items():
                            attributes[key] = ','.join(map(str, attributes[key]))

                        keycloak_user_id = KeycloakSession.keycloak_admin.create_user({"email": user_email,
                                                                              "username": user_login,
                                                                              "enabled": user.is_active,
                                                                              "createdTimestamp": user.created_at,
                                                                              "firstName": user_name,
                                                                              "attributes": attributes,
                                                                              "credentials": [
                                                                                  {"value": "secret",
                                                                                   "type": "password"}],
                                                                              })

                        DBSession.query(User).filter_by(id=user.id).update(values={"id": keycloak_user_id},
                                                                           synchronize_session='fetch')
                        DBSession.flush()

                        self.create_user_associated_resources(keycloak_user_id)



                except (KeycloakGetError, KeycloakOperationError, KeycloakPostError, KeycloakPutError, Exception) as e:
                    logging.debug(str(e))
                    if user:
                        f.write(
                            "User with error: {} user email {} error: {}\n".format(user.__dict__, user_email,
                                                                                   str(e)))
        keys = self.REDIS_CACHE.get_pure("keys")
        if keys is not None:
            for key in keys:
                attributes = {}
                try:
                    resource = self.REDIS_CACHE.get_pure(key)
                    attributes = resource.get("attributes", None)
                    if attributes is not None:
                        for key, value in attributes.items():
                            attributes[key] = ','.join(map(str, attributes[key]))
                        resource["attributes"] = attributes
                    KeycloakSession.keycloak_uma.resource_set_create(resource)

                except (KeycloakGetError, KeycloakOperationError, KeycloakPostError, KeycloakPutError, Exception) as e:
                    logging.debug(
                        "Keycloak could not update resource with key: " + key + "with error: " + str(
                            e.error_message)+"\n")
            self.REDIS_CACHE.rem(keys)

    def create_user_associated_resources(self, keycloak_user_id=None, ):
        if keycloak_user_id is None:
            raise KeycloakOperationError(error_message="User id could not be null")
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
                    user_to_group_association.c.user_id == str(keycloak_user_id),
                    user_to_group_association.c.group_id == Group.id)).all()
                if len(objects):
                    scope = "urn:" + str(KeycloakSession.client_name) + ":scopes:" + str(action)
                    type = "urn:" + str(KeycloakSession.client_name) + ":resources:" + str(subject)
                    for obj in objects:
                        if obj.Group.subject_client_id and obj.Group.subject_object_id:
                            name = str(subject) + "/" + str(obj.Group.subject_client_id) + "/" + str(
                                obj.Group.subject_object_id)

                            resource_to_create = {
                                "name": name,
                                "scopes": [scope],
                                "type": type,
                                "uri": str(obj.Group.subject_client_id) + "/" + str(
                                    obj.Group.subject_object_id),
                                "attributes": {scope: [keycloak_user_id]}
                            }
                            if self.REDIS_CACHE.get_pure(name) is None:
                                self.REDIS_CACHE.set_pure(name, resource_to_create)
                            else:
                                resource = self.REDIS_CACHE.get_pure(name)
                                resource["scopes"].append(scope)
                                resource["scopes"] = list(set(resource["scopes"]))
                                temp = resource["attributes"].get(scope, None)
                                if temp is None:
                                    temp = [keycloak_user_id]
                                else:
                                    temp.append(keycloak_user_id)
                                resource["attributes"][scope] = list(set(temp))
                                self.REDIS_CACHE.set_pure(name, resource)

                            keys = self.REDIS_CACHE.get_pure("keys")

                            if keys is not None:
                                keys.append(name)
                                keys = list(set(keys))
                                self.REDIS_CACHE.set_pure("keys", keys)

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
        logging.warning("Could not connect to the Keycloak")

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
