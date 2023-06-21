"""Migrate users from Lingvodoc to Keycloak

Revision ID: 477131175d56
Revises: 98a07e65f1bb
Create Date: 2023-04-20 15:57:54.428738

"""
import distutils
import logging

import transaction
from keycloak import KeycloakAdmin, KeycloakOpenID, KeycloakOpenIDConnection, KeycloakUMA, KeycloakOperationError, \
    KeycloakGetError, KeycloakPostError
from sqlalchemy import and_, pool, engine_from_config
from lingvodoc.models import (
    DBSession,
    User,
    BaseGroup, Group, user_to_group_association, Base)

LOCALES_DICT = {"ru": 1, "en": 2}

from lingvodoc.keycloakld import KeycloakSession

# revision identifiers, used by Alembic.
revision = '477131175d56'
down_revision = '98a07e65f1bb'
branch_labels = None
depends_on = None

from alembic.config import Config

config = Config("alembic.ini")

LOG = logging.getLogger('keycloak')


def upgrade():
    LOG.debug('CONNECT TO THE KEYCLOAK')

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
        LOG.debug(KeycloakSession.keycloak_admin.connection.realm_name)
        KeycloakSession.keycloak_uma = uma
        KeycloakSession.keycloak_url = keycloak_dict["client_secret_key"]

        engine = engine_from_config(
            config.get_section(config.config_ini_section),
            prefix='sqlalchemy.',
            poolclass=pool.NullPool)
        DBSession.configure(bind=engine)
        Base.metadata.bind = engine

        add_mappers(keycloak_dict["client_name"])
        migrate_users()
        transaction.manager.commit()

    pass


def downgrade():
    LOG.debug('unroll keycloak')
    pass


def migrate_users():
    LOG.debug('START MIGRATION TO THE KEYCLOAK')
    users = DBSession.query(User).all()
    for user in users:
        try:
            keycloak_user_id = KeycloakSession.keycloak_admin.get_user_id(user.login)
            if keycloak_user_id:
                KeycloakSession.keycloak_admin.set_user_password(user_id=keycloak_user_id, password="secret",
                                                                 temporary=False)
            else:
                attributes = dict()
                create_user_associated_resources(attributes, user)
                attributes.update({"locale": [LOCALES_DICT.get(user.default_locale_id, "en")]})
                user_id = KeycloakSession.keycloak_admin.create_user({"email": user.email.email,
                                                                      "username": user.login,
                                                                      "enabled": user.is_active,
                                                                      "createdTimestamp": user.created_at,
                                                                      "firstName": user.name,
                                                                      "credentials": [
                                                                          {"value": "secret", "type": "password"}],
                                                                      "attributes": attributes,
                                                                      })
                LOG.debug("User created:" + user.login)

                DBSession.query(User).filter_by(id=user.id).update(values={"id": user_id},
                                                                   synchronize_session='fetch')
                DBSession.flush()

        except (KeycloakGetError, KeycloakOperationError, KeycloakPostError, Exception) as e:
            logging.debug(str(e))
            with open("users.txt", 'a+') as f:
                if user:
                    f.write("user: {} error: {}\n".format(user.__dict__, str(e)))


def create_user_associated_resources(attributes=None, user=User):
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
                scope = "urn:" + KeycloakSession.client_name + ":scopes:" + action
                resource = "urn:" + KeycloakSession.client_name + ":resources:" + subject
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
                            created_resource = KeycloakSession.keycloak_uma.resource_set_create(resource_to_create)
                        except (KeycloakGetError, KeycloakOperationError, KeycloakPostError):
                            logging.debug("Keycloak could not create resource with name " + name)
                            try:
                                already_created_resource = KeycloakSession.keycloak_uma.resource_set_list_ids(
                                    name=name)
                                already_created_resource = KeycloakSession.keycloak_uma.resource_set_read(
                                    already_created_resource[0])
                                if len(already_created_resource) > 0:
                                    already_created_resource["scopes"].append(
                                        {'name': scope})
                                    KeycloakSession.keycloak_uma.resource_set_update(
                                        already_created_resource["_id"], already_created_resource)
                            except (KeycloakGetError, KeycloakOperationError, KeycloakPostError) as e:
                                logging.debug("Keycloak could not update resource with new scope" + e.error_message)
                if len(ids) > 0:
                    attributes.update({resource + ";" + scope: ids})
    return attributes


def add_mappers(client_name):
    id = KeycloakSession.keycloak_admin.get_client_id(client_id=client_name)
    subjects = ["dictionary", "language", "translation_string", "edit_user", "perspective_role", "dictionary_role",
                "organization", "perspective", "lexical_entries_and_entities", "approve_entities", "merge",
                "translations", "grant", "dictionary_status", "perspective_status"]
    actions = ["approve", "create", "delete", "edit", "view"]
    for subject in subjects:
        for action in actions:
            try:
                KeycloakSession.keycloak_admin.add_mapper_to_client(
                    client_id=id,
                    payload={
                        "name": action + '_' + subject,
                        "protocol": "openid-connect",
                        "protocolMapper": "oidc-usermodel-attribute-mapper",
                        "consentRequired": "false",
                        "config": {
                            "aggregate.attrs": "false",
                            "userinfo.token.claim": "true",
                            "multivalued": "false",
                            "user.attribute": "urn:" + KeycloakSession.client_name + ":resources:" + subject + ";" + "urn:" + KeycloakSession.client_name + ":scopes:" + action,
                            "id.token.claim": "true",
                            "access.token.claim": "true",
                            "claim.name": "urn:" + KeycloakSession.client_name + ":resources:" + subject + ";" + "urn:" + KeycloakSession.client_name + ":scopes:" + action}
                    },
                )
            except KeycloakPostError as e:
                logging.debug(e.error_message)

    LOG.debug('MAPPERS ADDED TO THE KEYCLOAK')
