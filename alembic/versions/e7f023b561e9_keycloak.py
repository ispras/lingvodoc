"""Migration of user authentication and authorization to Keycloak

Revision ID: e7f023b561e9
Revises: 937b38aec86f
Create Date: 2025-11-22 21:11:59.386480

"""

# revision identifiers, used by Alembic.
revision = 'e7f023b561e9'
down_revision = '937b38aec86f'
branch_labels = None
depends_on = None

# Standard library imports.

import collections
import itertools
import json
import logging
import pprint
import re
import requests

# External imports.

from alembic import context, op

import distutils
import keycloak

from keycloak.exceptions import KeycloakPostError

import secrets

from sqlalchemy import (
    and_,
    engine_from_config,
    func,
    pool,
    select
)

from sqlalchemy.orm import Session

import transaction

# Lingvodoc imports.

import lingvodoc.cache.caching as caching

from lingvodoc.cache.caching import initialize_cache

from lingvodoc.models import (
    BaseGroup,
    Group,
    LOCALE_DICT,
    User,
    user_to_group_association
)

log = logging.getLogger('keycloak')

# Deferring DBSession initialization to be able to execute 'alembic history'.

DBSession = None


def upgrade():

    global DBSession
    DBSession = Session(bind = op.get_bind())

    config = context.config

    # Cache access config.

    cache_kwargs = config.get_section('cache:redis:args')
    cache_kwargs.pop('here')

    log.info(json.dumps(cache_kwargs))

    if not cache_kwargs:
        raise Exception('Could not migrate users without Redis. Please check configuration.')

    initialize_cache(cache_kwargs)

    # Keycloak access config.

    keycloak_dict = config.get_section('keycloak')

    if not keycloak_dict:
        raise Exception('Could not migrate users without Keycloak. Please check configuration.')

    # Initializing Keycloak DB, psql console `psql -U postgres`:
    #
    #   ALTER ROLE postgres PASSWORD 'postgres';
    #   CREATE DATABASE keycloak;
    #
    # Can check if the password works by `psql -h 127.0.0.1 -U postgres keycloak`, or
    # `psql -h 127.0.0.1 -U postgres -W keycloak` to force the password check.
    #
    # Starting Keycloak in development mode:
    #
    #   export KEYCLOAK_ADMIN=admin KEYCLOAK_ADMIN_PASSWORD=admin
    #   bin/kc.sh start-dev --db postgres --db-username postgres --db-password postgres
    #
    # After Keycloak start and actual Keycloak DB initialization, adjust Keycloak DB for our needs, psql
    # console `psql -U postgres keycloak`:
    #
    #   ALTER TABLE resource_attribute ALTER COLUMN value TYPE text;

    # Creating the realm if required.

    keycloak_admin = keycloak.KeycloakAdmin(
        server_url = keycloak_dict['server_url'],
        username = 'admin',
        password = 'admin',
        realm_name = 'master',
        client_id = 'admin-cli',
        verify = True,
    )

    # How to check existence of a realm (don't need that really, can just create with skip):
    #
    #   realms = keycloak_admin.get_realms()
    #
    #   lingvodoc_realm_exists = any(
    #       realm.get('realm') == keycloak_dict['realm_name']
    #       for realm in realms
    #   )

    realm_info_dict = {
        'enabled': True,
        'duplicateEmailsAllowed': True,
        'loginWithEmailAllowed': False,
        'realm': keycloak_dict['realm_name'],
        'registrationEmailAsUsername': False,

    }

    realm = keycloak_admin.create_realm(
        realm_info_dict,
        skip_exists = True,
    )

    log.debug(
        '.create_realm():\n' +
        pprint.pformat(realm, width = 108)
    )

    # Checking that the realm was actually created through REST API:
    #
    #   export BASE=http://localhost:8080
    #
    #   export TOKEN=$(
    #       curl \
    #           --request POST \
    #           --url $BASE/realms/master/protocol/openid-connect/token \
    #           --header 'Content-Type: application/x-www-form-urlencoded' \
    #           --data client_id=admin-cli \
    #           --data grant_type=password \
    #           --data username=admin \
    #           --data password=admin \
    #       | jq -r '.access_token' \
    #   )
    #
    #   curl -s \
    #       -H "Authorization: Bearer $TOKEN" \
    #       $BASE/admin/realms \
    #   | jq -r '.[].realm'
    #
    # The received token can have quite low expiration period, down to just 1 minute, so be aware, might
    # need to execute info request quickly enough.
    #
    # Token can be decoded to get expiration info, ChatGPT-provided way:
    #
    #   python3 - << 'PY' "$TOKEN"
    #   import sys, base64, json
    #   t = sys.argv[1]
    #   try:
    #       payload = t.split('.')[1]
    #       padding = '=' * ((4 - len(payload) % 4) % 4)
    #       data = base64.urlsafe_b64decode(payload + padding).decode()
    #       print(json.dumps(json.loads(data), indent=2))
    #   except Exception as e:
    #       print("decode error:", e)
    #   PY

    # Getting realms to check that the Lingvodoc realm exists.

    realms = keycloak_admin.get_realms()

    log.debug(
        '.get_realms():\n' +
        pprint.pformat(
            [realm['realm'] for realm in realms],
            width = 108
        )
    )

    # Now going to operate in the Lingvodoc realm, for setting up things here.

    keycloak_admin = keycloak.KeycloakAdmin(
        server_url = keycloak_dict['server_url'],
        username = 'admin',
        password = 'admin',
        realm_name = keycloak_dict['realm_name'],
        client_id = 'admin-cli',
        verify = True,
        user_realm_name = 'master',
    )

    # We need to edit user login validation, so that we can leave as many as possible Lingvodoc logins
    # unchanged.
    #
    # Doing this through raw requests as it looks like python-keycloak does not have API for this.

    token_info_dict = {
        'client_id': 'admin-cli',
        'grant_type': 'password',
        'password': 'admin',
        'username': 'admin',
    }

    response = requests.post(
        keycloak_dict['server_url'] + 'realms/master/protocol/openid-connect/token',
        data = token_info_dict,
    )

    response.raise_for_status()
    response_json = response.json()

    access_token = response_json['access_token']

    response = requests.get(
        keycloak_dict['server_url'] + 'admin/realms/' + keycloak_dict['realm_name'] + '/users/profile',
        headers = {'Authorization': 'Bearer ' + access_token},
    )

    response.raise_for_status()
    response_json = response.json()

    profile = response.json()

    for section in profile['attributes']:

        validations = section['validations']

        validations.pop('person-name-prohibited-characters', None)
        validations.pop('up-username-not-idn-homograph', None)
        validations.pop('username-prohibited-characters', None)

        length = validations.get('length', None)

        if length is not None:
            length.pop('min', None)

    # Can check that below actually worked by going to the web interface and checking. Select required realm
    # in Manage realms, go Realm settings, User profile tab, JSON editor.

    response = requests.put(
        keycloak_dict['server_url'] + 'admin/realms/' + keycloak_dict['realm_name'] + '/users/profile',
        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/json',
        },
        data = json.dumps(profile),
    )

    response.raise_for_status()

    # Deletion of a perhaps already existing client, to initialize cleanly.
    #
    #    client_uuid = keycloak_admin.get_client_id(keycloak_dict['client_id'])
    #    if client_uuid:
    #
    #        delete_result = keycloak_admin.delete_client(client_uuid)
    #
    #        log.debug(
    #            '.delete_client():\n' +
    #            pprint.pformat(delete_result, width = 108)
    #        )

    # Creating a confidential client to handle automated set up and servicing.

    client_info_dict = {
        'clientId': keycloak_dict['client_id'],
        'directAccessGrantsEnabled': False,
        'enabled': True,
        'name': keycloak_dict['client_name'],
        'protocol': 'openid-connect',
        'publicClient': False,
        'serviceAccountsEnabled': True,
        'standardFlowEnabled': False,
    }

    client_uuid = keycloak_admin.create_client(
        client_info_dict,
        skip_exists = True
    )

    log.debug(
        '.create_client():\n' +
        pprint.pformat(client_uuid, width = 108)
    )

    # Get client secret, would need to put it into the server config later.

    client_secret = keycloak_admin.get_client_secrets(client_uuid)

    log.debug(
        '.get_client_secrets():\n' +
        pprint.pformat(client_secret, width = 108)
    )

    # Giving the client full control of the Lingvodoc realm.

    service_user = keycloak_admin.get_client_service_account_user(client_uuid)

    log.debug(
        '.get_client_service_account_user():\n' +
        pprint.pformat(service_user, width = 108)
    )

    realm_management_uuid = keycloak_admin.get_client_id('realm-management')
    realm_admin_role = keycloak_admin.get_client_role(realm_management_uuid, 'realm-admin')

    assign_result = keycloak_admin.assign_client_role(
        user_id = service_user['id'],
        client_id = realm_management_uuid,
        roles = [realm_admin_role]
    )

    log.debug(
        '.assign_client_role():\n' +
        pprint.pformat(assign_result, width = 108)
    )

    # Enabling authorization services for the client; this is proper procedure, can't just supply
    # 'authorizationServicesEnabled': True during creation, need to enable after.

    client = keycloak_admin.get_client(client_uuid)
    client['authorizationServicesEnabled'] = True

    keycloak_admin.update_client(client_uuid, client)

    log.debug(
        'client:\n' +
        pprint.pformat(client, width = 108)
    )

    # Creating users.
    #
    # Considered if we should have user logins with standard Keycloak restrictions, like length and
    # restricted character set, but it's easier to set up Keycloak without them.
    #
    # Still need to ensure logins are case-insensitively unique.

    # Keycloak treats logins as case-insensitive, so we'll have to uniquify the logins beforehand. Keycloak
    # also does not support logins shorter than 3 characters, so we pad the offending logins. And logins
    # also better not have whitespace.
    #
    # And we'd prefer as little disruption as possible, so we're going to adjust logins in a bit complicated
    # manner, in two phases.

    def normalize_login(login: str):
        """
        Normalizes user's login to be acceptable to Keycloak.

        No whitespace, no shorter than 3 characters.
        """

        login = login.strip()
        login = re.sub(r'\s+', '_', login)

        if len(login) < 3:
            login += '_' * (3 - len(login))

        return login

    users = DBSession.query(User).all()

    # First, going through logins that need not be adjusted at all, but still might need to be uniquified.
    #
    # Need to be careful with login updates to not break the DB's unique login constraint.

    adjusted_login_dict = {}
    keycloak_login_dict = {}

    normalized_login_set = {
        normalize_login(user.login)
        for user in users
    }

    for user in users:

        original_login = user.login
        normalized_login = normalize_login(original_login)

        if normalized_login != original_login:
            continue

        keycloak_login = normalized_login.lower()

        # Also skipping logins that would shadow existing ones.

        if (keycloak_login != normalized_login and
            keycloak_login in normalized_login_set):

            continue

        # Uniquifying if required.

        adjusted_login = normalized_login

        if keycloak_login in keycloak_login_dict:

            for i in itertools.count(1):

                adjusted_login = normalized_login + '_' + str(i)

                if adjusted_login.lower() not in keycloak_login_dict:
                    break

            keycloak_login = adjusted_login.lower()

        adjusted_login_dict[adjusted_login] = user
        keycloak_login_dict[keycloak_login] = user

        if adjusted_login != original_login:

            log.debug(f' login: {repr(original_login)} -> {repr(adjusted_login)}')

            user.login = adjusted_login
            DBSession.flush()

    # Now the second phase, processing logins that need to be adjusted.

    for user in users:

        original_login = user.login

        if original_login in adjusted_login_dict:
            continue

        normalized_login = normalize_login(original_login)

        keycloak_login = normalized_login.lower()

        # Uniquifying if required.

        adjusted_login = normalized_login

        if keycloak_login in keycloak_login_dict:

            for i in itertools.count(1):

                adjusted_login = normalized_login + '_' + str(i)

                if adjusted_login.lower() not in keycloak_login_dict:
                    break

            keycloak_login = adjusted_login.lower()

        adjusted_login_dict[adjusted_login] = user
        keycloak_login_dict[keycloak_login] = user

        if adjusted_login != original_login:

            log.debug(f' login: {repr(original_login)} -> {repr(adjusted_login)}')

            user.login = adjusted_login
            DBSession.flush()

    user_id_dict = {user.id: user for user in users}
    user_login_dict = {user.login: user for user in users}

    for user in users:

        user_login = user.login
        user_uuid = keycloak_admin.get_user_id(user_login)

        # Creating user if required.

        if user_uuid is None:

            attributes = {'locale': [LOCALE_DICT.get(user.default_locale_id, 'en')]}

            email = user.email.email

            user_info_dict = {
                'email': email,
                'username': user_login,
                'enabled': user.is_active,
                'createdTimestamp': user.created_at,
                'firstName': user.name,
                'attributes': attributes,
                'credentials': [
                    {'value': 'secret', 'type': 'password'}
                ],
            }

            # If email does not look good, we don't specify it.

            if not re.fullmatch(r'[^@\s\t\r\n]+@[^@\s\t\r\n]+\.[^@\s\t\r\n]+', email):
                del user_info_dict['email']

            user_uuid = keycloak_admin.create_user(user_info_dict)

        # Updating user id if required.

        if user.id != user_uuid:

            user.id = user_uuid
            DBSession.flush()

    raise NotImplementedError

    # Adding permission info to Keycloak.
    #
    # Getting permission categories from the DB:
    #
    #   select distinct subject from basegroup order by subject;
    #
    # Getting actions from the DB:
    #
    #   select distinct action from basegroup order by action;

    subjects = [
        'approve_entities',
        'dictionary',
        'dictionary_role',
        'dictionary_status',
        'edit_user',
        'grant',
        'language',
        'lexical_entries_and_entities',
        'merge',
        'organization',
        'perspective',
        'perspective_role',
        'perspective_status'
        'translation_string',
        'translations',
    ]

    actions = [
        'approve',
        'create',
        'delete',
        'edit',
        'view'
    ]

    # Creating scopes and policies.
    #
    # Though wait, do we actually even need this?

    for action in actions:

        scope_info_dict = {
            'name': 'urn:' + keycloak_dict['client_name'] + ':scopes:' + action,
            'displayName': f'can {action}',
        }

        scope_result = keycloak_admin.create_client_authz_scopes(
            client_uuid,
            scope_info_dict
        )

        log.debug(
            '.create_client_authz_scopes():\n' +
            pprint.pformat(scope_result, width = 108)
        )

    # Getting scopes and policies.

    scopes = keycloak_admin.get_client_authz_scopes(client_id = client_uuid)
    policies = keycloak_admin.get_client_authz_policies(client_id = client_uuid)

    # ...

    result = (

        DBSession

            .query(
                BaseGroup,
                Group,
                func.jsonb_agg(user_to_group_association.c.user_id),
            )

            .filter(
                BaseGroup.id == Group.base_group_id,
                Group.id == user_to_group_association.c.group_id,
            )

            .group_by(BaseGroup, Group)
    )

    # Three possibilities for a group:
    #
    # 1. Subject override is true, for all subjects of this kind and this action.
    # 2. Subject is standard (client id, object id) pair.
    # 3. Subject is a single identifier stored as an object id, e.g. an organization.

    scope_str = 'urn:' + keycloak_dict['client_name'] + ':scopes:'
    type_str = 'urn:' + keycloak_dict['client_name'] + ':resources:'

    resource_dict = {}

    # __DEBUG__
    #for base_group, group, user_id_list in result.yield_per(1024):
    for base_group, group, user_id_list in result.limit(1024):

        resource_scope = scope_str + base_group.action
        resource_type = type_str + base_group.subject

        # Override group.

        if group.subject_override:

            name = (
                base_group.subject
            )

        # Single id.

        elif group.subject_client_id is None:

            name = (
                base_group.subject + "/" +
                str(group.subject_object_id)
            )

        # Standard composite id.

        else:

            name = (
                base_group.subject + "/" +
                str(group.subject_client_id) + "/" +
                str(group.subject_object_id)
            )

        # Creating or updating resource data.

        resource = resource_dict.get(name)

        if resource is None:

            resource = {
                'attributes': collections.defaultdict(set),
                'name': name,
                'scopes': set(),
                'type': type_str,
                'uri': name,
            }

            resource_dict[name] = resource

        resource['scopes'].add(resource_scope)
        resource['attributes'][resource_scope].update(user_id_list)

    # Already existing resources.

    resources = keycloak_admin.get_client_authz_resources(client_id = client_uuid)

    # Resource creation and permission test check.

    resource = list(resource_dict.values())[0]

    resource['scopes'] = list(resource['scopes'])

    resource['attributes'] = {
        scope: list(user_id_set)
        for scope, user_id_set in resource['attributes'].items()
    }

    resource_result = keycloak_admin.create_client_authz_resource(
        client_uuid,
        resource,
        skip_exists = True,
    )

    if '_id' not in resource_result:

        for resource_already in resources:

            if resource_already['name'] == resource['name']:
                resource_result = resource_already
                break

    raise NotImplementedError

    # Creating resources.

    for resource in resource_dict.values():

        raise NotImplementedError

    raise NotImplementedError


def downgrade():
    pass
