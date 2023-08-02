"""Migrate users from Lingvodoc to Keycloak

Revision ID: 477131175d56
Revises: 98a07e65f1bb
Create Date: 2023-04-20 15:57:54.428738

"""
import distutils
import logging
import secrets
import traceback
from json import dumps

import transaction
from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakOpenIDConnection, KeycloakUMA, KeycloakOperationError, \
    KeycloakGetError, KeycloakPostError, KeycloakPutError
from sqlalchemy import and_, pool, engine_from_config, select

from alembic import op
from sqlalchemy.orm import Session

from lingvodoc.models import (

    User,
    BaseGroup, Group, user_to_group_association)

LOCALES_DICT = {"ru": 1, "en": 2}

from lingvodoc.keycloakld import KeycloakSession
import lingvodoc.cache.caching as caching

# revision identifiers, used by Alembic.
revision = '477131175d56'
down_revision = '98a07e65f1bb'
branch_labels = None
depends_on = None
from alembic import context

config = context.config

LOG = logging.getLogger('keycloak')

Session = Session(bind=op.get_bind())
from lingvodoc.cache.caching import (
    initialize_cache
)

def upgrade():
    LOG.debug('CONNECT TO THE KEYCLOAK')

    cache_kwargs = config.get_section('cache:redis:args')
    cache_kwargs.pop("here")
    LOG.info(dumps(cache_kwargs))
    if cache_kwargs:
        initialize_cache(cache_kwargs)
    else:
        raise Exception("Could not migrate users without redis. Check configuration")

    keycloak_dict = config.get_section("keycloak")
    if keycloak_dict:
        KeycloakSession.client_name = keycloak_dict["client_name"]
        KeycloakSession.keycloak_admin = KeycloakAdmin(server_url=keycloak_dict["server_url"],
                                                       username=keycloak_dict["admin"],
                                                       password=keycloak_dict["password"],
                                                       realm_name=keycloak_dict["realm_name_admin"],
                                                       auto_refresh_token=["get", "post", "put", "delete"])
        KeycloakSession.keycloak_admin.realm_name = keycloak_dict["realm_name"]
        KeycloakSession.openid_client = KeycloakOpenID(server_url=keycloak_dict["server_url"],
                                                       client_id=keycloak_dict["client_name"],
                                                       realm_name=keycloak_dict["realm_name"],
                                                       client_secret_key=keycloak_dict["client_secret_key"])
        keycloak_connection = KeycloakOpenIDConnection(
            custom_headers={"Content-Type": "application/x-www-form-urlencoded"},
            server_url=keycloak_dict["server_url"],
            realm_name=keycloak_dict["realm_name"],
            client_id=keycloak_dict["client_name"],
            client_secret_key=keycloak_dict["client_secret_key"])
        LOG.debug('set keycloak_connection')
        uma = KeycloakUMA(connection=keycloak_connection)
        KeycloakSession.keycloak_uma = uma
        KeycloakSession.keycloak_url = keycloak_dict["client_secret_key"]

        migrate_users(keycloak_dict["user_password"])
        transaction.manager.commit()

    pass


def downgrade():
    LOG.debug('unroll keycloak')
    pass


def add_permissions(client_id):
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

def migrate_users(password="secret"):
    REDIS_CACHE = caching.CACHE
    if REDIS_CACHE is None:
        REDIS_CACHE = caching.CACHE
    client_id = KeycloakSession.keycloak_admin.get_client_id(client_id=KeycloakSession.client_name)
    add_permissions(client_id)
    LOG.debug('START MIGRATION TO THE KEYCLOAK')
    users = Session.query(User).all()
    REDIS_CACHE.set_pure("keys", [])
    for user in users:
        with open("users_test_alembic.txt", 'a+') as f:
            user_name = user_login = secrets.token_hex(8)
            user_email = user_name + "@ispras.ru"
            try:
                keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(user.login)
                if keycloak_user_id is not None:
                    KeycloakSession.keycloak_admin.set_user_password(user_id=keycloak_user_id, password=password,
                                                                     temporary=False)
                    if Session.query(User).filter_by(id=keycloak_user_id).first() is None:
                        Session.query(User).filter_by(id=user.id).update(values={"id": keycloak_user_id},
                                                                           synchronize_session='fetch')
                        Session.flush()
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

                    Session.query(User).filter_by(id=user.id).update(values={"id": keycloak_user_id},
                                                                       synchronize_session='fetch')
                    Session.flush()

                    create_user_associated_resources(REDIS_CACHE, keycloak_user_id)



            except (KeycloakGetError, KeycloakOperationError, KeycloakPostError, KeycloakPutError, Exception) as e:
                logging.debug(str(e))
                if user:
                    f.write(
                        "User with error: {} user email {} error: {}\n".format(user.__dict__, user_email,
                                                                               str(e)))
    keys = REDIS_CACHE.get_pure("keys")
    if keys is not None:
        for key in keys:
            attributes = {}
            try:
                resource = REDIS_CACHE.get_pure(key)
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
        REDIS_CACHE.rem(keys)

def create_user_associated_resources(REDIS_CACHE, keycloak_user_id=None, ):
    if keycloak_user_id is None:
        raise KeycloakOperationError(error_message="User id could not be null")
    subjects = ["dictionary", "language", "translation_string", "edit_user", "perspective_role", "dictionary_role",
                "organization", "perspective", "lexical_entries_and_entities", "approve_entities", "merge",
                "translations", "grant", "dictionary_status", "perspective_status"]
    actions = ["approve", "create", "delete", "edit", "view"]
    for subject in subjects:
        for action in actions:
            objects = Session.query(BaseGroup, Group, user_to_group_association, Group.subject_client_id,
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
                        if REDIS_CACHE.get_pure(name) is None:
                            REDIS_CACHE.set_pure(name, resource_to_create)
                        else:
                            resource = REDIS_CACHE.get_pure(name)
                            resource["scopes"].append(scope)
                            resource["scopes"] = list(set(resource["scopes"]))
                            temp = resource["attributes"].get(scope, None)
                            if temp is None:
                                temp = [keycloak_user_id]
                            else:
                                temp.append(keycloak_user_id)
                            resource["attributes"][scope] = list(set(temp))
                            REDIS_CACHE.set_pure(name, resource)

                        keys = REDIS_CACHE.get_pure("keys")

                        if keys is not None:
                            keys.append(name)
                            keys = list(set(keys))
                            REDIS_CACHE.set_pure("keys", keys)
