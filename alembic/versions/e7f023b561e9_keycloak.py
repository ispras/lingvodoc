"""Migration of user authentication and authorization to Keycloak

Revision ID: e7f023b561e9
Revises: 937b38aec86f
Create Date: 2025-11-22 21:11:59.386480

"""
import random

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
import time

# External imports.

from alembic import context, op

import distutils

import keycloak
import keycloak.uma_permissions as uma_permissions

from keycloak.exceptions import KeycloakPostError

from passlib.hash import bcrypt

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

import lingvodoc.acl as acl

import lingvodoc.cache.caching as caching

from lingvodoc.cache.caching import initialize_cache

import lingvodoc.models as models

from lingvodoc.models import (
    BaseGroup,
    Client,
    Group,
    LOCALE_DICT,
    User,
    user_to_group_association
)

log = logging.getLogger('keycloak')

# Deferring DBSession initialization to be able to execute 'alembic history'.

DBSession = None


class Token:
    """
    Token refreshment manager, partially based on ChatGPT-suggested code.
    """

    def __init__(self, url, token_info_dict):

        self.leeway = 15

        self.url = url
        self.token_info_dict = token_info_dict

        self.request_token()

    def request_token(self):

        response = requests.post(
            self.url,
            data = self.token_info_dict,
        )

        response_json = response.json()

        if 'error' in response_json:
            log.error(response_json)

        response.raise_for_status()

        self.response_json = response_json
        self.response_time = time.time()

        self.expires_in = self.response_time + int(response_json['expires_in'])

        if 'refresh_expires_in' in response_json:
            self.refresh_expires_in = self.response_time + int(response_json['refresh_expires_in'])

    def refresh_token(self):

        token_info_dict = {
            'client_id': self.token_info_dict['client_id'],
            'client_secret': self.token_info_dict['client_secret'],
            'grant_type' : 'refresh_token',
            'refresh_token' : self.response_json['refresh_token'],
        }

        response = requests.post(
            self.url,
            data = token_info_dict,
        )

        response_json = response.json()

        if 'error' in response_json:
            log.error(response_json)

        response.raise_for_status()

        self.response_json = response_json
        self.response_time = time.time()

        self.expires_in = self.response_time + int(response_json['expires_in'])

        if 'refresh_expires_in' in response_json:
            self.refresh_expires_in = self.response_time + int(response_json['refresh_expires_in'])

    def get_token(self):

        if time.time() < self.expires_in - self.leeway:
            return self.response_json['access_token']

        # Need to refresh the token.
        #
        # If we have the refresh token, we use it, otherwise it's as usual.

        if 'refresh_token' in self.response_json:
            self.refresh_token()
        else:
            self.request_token()

        return self.response_json['access_token']

def upgrade():

    global DBSession
    DBSession = Session(bind = op.get_bind())
    models.DBSession = DBSession

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
    #   export KEYCLOAK_ADMIN=admin KEYCLOAK_ADMIN_PASSWORD=admin JAVA_OPTS_KC_HEAP="-Xms256m -Xmx2048m"
    #   bin/kc.sh start-dev --db postgres --db-username postgres --db-password postgres
    #
    # Default JAVA_OPTS_KC_HEAP in kc.sh are "-Xms64m -Xmx512m", we're increasing due to having got out of
    # memory termination at least once.
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
    #
    # Also, we don't set users' last names, so we need to mark them as not required so that users won't be
    # asked to fill them in on first login and we'd be able to log in as users non-interactively.

    token_info_dict = {
        'client_id': 'admin-cli',
        'grant_type': 'password',
        'password': 'admin',
        'username': 'admin',
    }

    server_url = keycloak_dict['server_url']
    realm_name = keycloak_dict['realm_name']

    response = requests.post(
        f'{server_url}realms/master/protocol/openid-connect/token',
        data = token_info_dict,
    )

    response.raise_for_status()
    response_json = response.json()

    access_token = response_json['access_token']

    response = requests.get(
        f'{server_url}admin/realms/{realm_name}/users/profile',
        headers = {'Authorization': 'Bearer ' + access_token},
    )

    response.raise_for_status()
    response_json = response.json()

    user_profile = response.json()

    for section in user_profile['attributes']:

        validations = section['validations']

        validations.pop('person-name-prohibited-characters', None)
        validations.pop('up-username-not-idn-homograph', None)
        validations.pop('username-prohibited-characters', None)

        length = validations.get('length', None)

        if length is not None:
            length.pop('min', None)

        section.pop('required', None)

    # Can check that below actually worked by going to the web interface and checking. Select required realm
    # in Manage realms, go Realm settings, User profile tab, JSON editor.

    response = requests.put(
        f'{server_url}admin/realms/{realm_name}/users/profile',
        headers = {
            'Authorization': 'Bearer ' + access_token,
            'Content-Type': 'application/json',
        },
        data = json.dumps(user_profile),
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
    #
    # Setting 'directAccessGrantsEnabled' to True to allow user logins, getting user tokens through the
    # client by user login and user password.

    client_info_dict = {
        'clientId': keycloak_dict['client_id'],
        'directAccessGrantsEnabled': True,
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

    # Debugging with limited data if required.
    users = DBSession.query(User).limit(64).all()
    #users = DBSession.query(User).limit(128).all()
    #users = DBSession.query(User).all()

    # First, going through logins that need not be adjusted at all, but still might need to be uniquified.
    #
    # Need to be careful with login updates to not break the DB's unique login constraint.

    adjusted_login_dict = {}

    keycloak_login_dict = {
        user.login.lower(): user
        for user in users
    }

    for user in users:

        user_login = user.login
        keycloak_login = user_login.lower()

        # We have an empty login, we skip it.

        if not user_login:
            continue

        # Uniquifying if required.

        adjusted_login = user_login

        if keycloak_login_dict[keycloak_login] != user:

            for i in itertools.count(1):

                adjusted_login = user_login + '_' + str(i)

                if adjusted_login.lower() not in keycloak_login_dict:
                    break

            keycloak_login = adjusted_login.lower()

        adjusted_login_dict[adjusted_login] = user
        keycloak_login_dict[keycloak_login] = user

        if adjusted_login != user_login:

            log.debug(f' login: {repr(user_login)} -> {repr(adjusted_login)}')

            user.login = adjusted_login
            DBSession.flush()

    id_user_dict = {}
    login_user_dict = {}

    user_password_dict = {}

    password_chars = '123456780abcdefghijklmnopqrstuvwxyz'
    rng = random.Random()

    user_data_list = []
    user_data_dict = {}

    # Progress tracking.

    progress_length = len(users)
    progress_percent = 0

    def progress_f(progress_str, count):

        nonlocal progress_percent

        progress_current = count * 100 // progress_length
        if progress_current > progress_percent:

            progress_percent = progress_current
            print(f' {progress_str}: {progress_percent}% ({count}/{progress_length})')

    for index, user in enumerate(users):

        user_login = user.login
        user_uuid = keycloak_admin.get_user_id(user_login)

        # We have an empty login, we skip it.

        if not user_login:
            continue

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
            #
            # Emails can't have neither starting nor ending dots in the local part (the part before the @),
            # e.g. 'elena.ant.@gmail.com' is an invalid one.

            if not re.fullmatch(r'^(?!\.)[^@\s\r\n]+(?<!\.)@[^@\s\r\n]+\.[^@\s\r\n]+', email):
                del user_info_dict['email']

            user_uuid = keycloak_admin.create_user(user_info_dict)

        # Otherwise getting user info.

        else:

            user_info_dict = keycloak_admin.get_user(user_uuid)

        # Setting up user's password.
        #
        # We're using temporary passwords of the XXXX-XXXX form, formed from digits and lower case English
        # letters.

        password = []

        password.extend(rng.choice(password_chars) for _ in range(4))
        password.append('-')
        password.extend(rng.choice(password_chars) for _ in range(4))

        password = ''.join(password)

        keycloak_admin.set_user_password(
            user_id = user_uuid,
            password = password,
            temporary = False,
        )

        # Updating user id if required.

        if user.id != user_uuid:
            user.id = user_uuid

        user.password.hash = bcrypt.encrypt(password)
        DBSession.flush()

        id_user_dict[user_uuid] = user
        login_user_dict[user_login] = user

        user_password_dict[user] = password

        user_data_info_dict = {
            'email': user_info_dict.get('email'),
            'enabled': user_info_dict['enabled'],
            'id': user_uuid,
            'info': user_info_dict,
            'login': user_login,
            'password': password,
        }

        user_data_list.append(user_data_info_dict)
        user_data_dict[user_uuid] = user_data_info_dict

        progress_f('users', index + 1)

    with open('user_data.json', 'w') as user_data_file:

        user_data_file.write(
            json.dumps(
                user_data_list,
                ensure_ascii = False,
                indent = 2,
            )
        )

    __debug_user_id_set__ = {user.id for user in users}

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

    # First step is to compile data of all the resources we'd like to have; we're not yet checking the
    # possibly already existing ones.

    scope_str = 'urn:' + keycloak_dict['client_name'] + ':scopes:'
    type_str = 'urn:' + keycloak_dict['client_name'] + ':resources:'

    resource_dict = {}

    test_dict = collections.defaultdict(set)

    # Debugging with limited data if required.
    result = result.limit(256)
    #result = result.limit(512)

    progress_length = result.count()
    progress_percent = 0

    for index, (base_group, group, user_id_list) in enumerate(result.yield_per(1024)):

        # Debugging with limited data if required.

        user_id_list = [
            user_id
            for user_id in user_id_list
            if user_id in __debug_user_id_set__
        ]

        if not user_id_list:
            continue

        resource_scope = scope_str + base_group.action
        resource_type = type_str + base_group.subject

        # Override group.

        if group.subject_override:

            name = (
                base_group.subject
            )

            subject_id = None

        # Single id.

        elif group.subject_client_id is None:

            name = (
                base_group.subject + "/" +
                str(group.subject_object_id)
            )

            subject_id = group.subject_object_id

        # Standard composite id.

        else:

            name = (
                base_group.subject + "/" +
                str(group.subject_client_id) + "/" +
                str(group.subject_object_id)
            )

            subject_id = (group.subject_client_id, group.subject_object_id)

        # Creating or updating resource data.

        resource = resource_dict.get(name)

        if resource is None:

            resource = {
                'attributes': {},
                'name': name,
                'scopes': set(),
                'type': resource_type,
                'uri': name,
            }

            resource_dict[name] = resource

        resource['scopes'].add(resource_scope)

        resource['attributes'].update({
            f'{base_group.action}:{user_id}': True
            for user_id in user_id_list
        })

        acl_item = (base_group.subject, subject_id, base_group.action)

        for user_id in user_id_list:
            test_dict[user_id].add(acl_item)

        progress_f('acls', index + 1)

    # Not getting already existing resources all at once, we can have hundreds of thousands of them, it's
    # unwieldy and we can get a timeout.
    #
    #   existing_resources = keycloak_admin.get_client_authz_resources(client_id = client_uuid)
    #
    #   existing_name_dict = {
    #       existing_resource['name']: existing_resource
    #       for existing_resource in existing_resources
    #   }

    # Creating resources.

    resource_results = []

    progress_length = len(resource_dict)
    progress_percent = 0

    for index, resource in enumerate(resource_dict.values()):

        resource['scopes'] = list(resource['scopes'])

        resource_result = keycloak_admin.create_client_authz_resource(
            client_uuid,
            resource,
            skip_exists = True,
        )

        if '_id' not in resource_result:

            response = requests.get(
                f'{server_url}admin/realms/{realm_name}/clients/{client_uuid}/authz/resource-server/resource',
                headers = {'Authorization': 'Bearer ' + access_token},
                params = {'name': resource['name'], 'exactName': True}
            )

            response.raise_for_status()
            response_json = response.json()

            resource_result = None

            for resource_value in response_json:

                if resource_value['name'] == resource['name']:
                    resource_result = resource_value
                    break

            if resource_result is None:
                raise NotImplementedError

        resource_results.append(resource_result)

        progress_f('resources', index + 1)

    # Creating the policy.

    token_info_dict = {
        'client_id': keycloak_dict['client_name'],
        'client_secret': client_secret['value'],
        'grant_type': 'client_credentials',
    }

    access_token = Token(
        f'{server_url}realms/{realm_name}/protocol/openid-connect/token',
        token_info_dict,
    )

    policy_info_dict = {
        'name': 'resource-acl-policy',
        'type': 'script-resource-acl.js',
        'logic': 'POSITIVE',
        'decisionStrategy': 'UNANIMOUS',
    }

    response = requests.post(
        f'{server_url}admin/realms/{realm_name}/clients/{client_uuid}/authz/resource-server/policy',
        headers = {
            'Authorization': 'Bearer ' + access_token.get_token(),
            'Content-Type': 'application/json',
        },
        data = json.dumps(policy_info_dict),
    )

    if response.status_code != 409:

        response.raise_for_status()
        response_json = response.json()

    else:

        response = requests.get(
        f'{server_url}admin/realms/{realm_name}/clients/{client_uuid}/authz/resource-server/policy/search',
            headers = {
                'Authorization': 'Bearer ' + access_token.get_token(),
                'Content-Type': 'application/json',
            },
            params = {'name': 'resource-acl-policy'},
            verify = True
        )

        response.raise_for_status()
        response_json = response.json()

    policy = response_json

    # Creating permissions.

    progress_length = len(resource_results)
    progress_percent = 0

    for index, resource_result in enumerate(resource_results):

        permission_info_dict = {
            'type': 'resource',
            'name': resource_result['name'],
            'logic': 'POSITIVE',
            'decisionStrategy': 'UNANIMOUS',
            'resources': [resource_result['_id']],
            'policies': [policy['id']],
        }

        response = requests.post(
            f'{server_url}admin/realms/{realm_name}/clients/{client_uuid}/authz/resource-server/permission/resource',
            headers = {
                'Authorization': 'Bearer ' + access_token.get_token(),
                'Content-Type': 'application/json',
            },
            data = json.dumps(permission_info_dict),
        )

        if response.status_code != 409:

            response.raise_for_status()
            response_json = response.json()

        else:

            response = requests.get(
            f'{server_url}admin/realms/{realm_name}/clients/{client_uuid}/authz/resource-server/permission/search',
                headers = {
                    'Authorization': 'Bearer ' + access_token.get_token(),
                    'Content-Type': 'application/json',
                },
                params = {'name': permission_info_dict['name']},
                verify = True
            )

            response.raise_for_status()
            response_json = response.json()

        progress_f('permissions', index + 1)

    # Testing resource access.
    #
    # We'd need user's access token for this.

    attribute = list(resource_result['attributes'].keys())[0]
    scope, user_uuid = attribute.split(':')

    user_data_info_dict = user_data_dict[user_uuid]

    keycloak_connection = keycloak.KeycloakOpenIDConnection(
        custom_headers = {'Content-Type': 'application/x-www-form-urlencoded'},
        server_url = server_url,
        realm_name = realm_name,
        client_id = keycloak_dict['client_name'],
        client_secret_key = client_secret['value'],
    )

    keycloak_openid = keycloak_connection.keycloak_openid

    token_info_dict = keycloak_openid.token(
        username = user_data_info_dict['login'],
        password = user_data_info_dict['password'],
    )

    user_token = token_info_dict['access_token']

    keycloak_uma = keycloak.KeycloakUMA(connection = keycloak_connection)

    permission = uma_permissions.UMAPermission(
        resource = resource_result['name'],
        scope = resource_result['scopes'][0]['name']
    )

    is_allowed = keycloak_uma.permissions_check(user_token, [permission])

    resource_name = resource_result['name']
    log.debug(f'{user_uuid}: {resource_name}.{scope} -> {is_allowed}')

    # Same by the raw requests.

    token_info_dict = {
        'client_id': keycloak_dict['client_name'],
        'client_secret': client_secret['value'],
        'grant_type': 'password',
        'username': user_data_info_dict['login'],
        'password': user_data_info_dict['password'],
    }

    user_token = Token(
        f'{server_url}realms/{realm_name}/protocol/openid-connect/token',
        token_info_dict,
    )

    check_info_dict = {
        'audience': keycloak_dict['client_name'],
        'grant_type': 'urn:ietf:params:oauth:grant-type:uma-ticket',
        'permission': resource_result['name'] + '#' + resource_result['scopes'][0]['name'],
        'response_mode': 'decision',
    }

    response = requests.post(
        f'{server_url}realms/{realm_name}/protocol/openid-connect/token',
        headers = {
            'Authorization': 'Bearer ' + user_token.get_token(),
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        data = check_info_dict,
    )

    response_json = response.json()
    response.raise_for_status()

    log.debug(f'{user_uuid}: {resource_name}.{scope} -> {response_json}')

    # Now we're going to test for all users, for all resource scopes that the users have permissions for,
    # and for some that the users don't have permissions for.
    #
    # One of the aims is to compare efficiency with the direct DB acl checking, so better disable all the
    # logging, by e.g. setting level = ERROR in alembic.ini for all the loggers.

    # Preparing test data.

    acl_item_set = set()

    test_accept_dict = {
        user_uuid: list(user_acl_item_set)
        for user_uuid, user_acl_item_set in test_dict.items()
    }

    for user_acl_item_set in test_dict.values():
        acl_item_set.update(user_acl_item_set)

    acl_item_list = list(acl_item_set)
    test_reject_dict = {}

    for user_uuid, user_acl_item_set in test_dict.items():

        # For each user, a number of ACL items that are to be rejected.

        reject_acl_item_list = []

        while len(reject_acl_item_list) < len(user_acl_item_set):

            acl_item = rng.choice(acl_item_list)

            if acl_item not in user_acl_item_set:
                reject_acl_item_list.append(acl_item)

        test_reject_dict[user_uuid] = reject_acl_item_list

    # Getting user tokens and client ids for testing.

    user_token_dict = {}
    user_client_id_dict = {}

    progress_length = len(test_dict.keys())
    progress_percent = 0

    for index, user_uuid in enumerate(test_dict.keys()):

        # Skipping non-active users.

        user_data_info_dict = user_data_dict[user_uuid]

        if not user_data_info_dict['enabled']:
            continue

        # Token.

        token_info_dict = {
            'client_id': keycloak_dict['client_name'],
            'client_secret': client_secret['value'],
            'grant_type': 'password',
            'username': user_data_info_dict['login'],
            'password': user_data_info_dict['password'],
        }

        user_token_dict[user_uuid] = Token(
            f'{server_url}realms/{realm_name}/protocol/openid-connect/token',
            token_info_dict,
        )

        # Client.

        user = DBSession.query(User).filter_by(id = user_uuid).first()
        client = Client(user_id = user_uuid)

        user.clients.append(client)

        DBSession.add(client)
        DBSession.flush()

        user_client_id_dict[user_uuid] = client.id

        progress_f('test tokens and clients', index + 1)

    # Testing.

    def access_test(user_token, subject, subject_id, action):

        if subject_id is None:
            name = subject

        elif subject_id is int:
            name = f'{subject}/{subject_id}'

        else:
            name = f'{subject}/{subject_id[0]}/{subject_id[1]}'

        scope = scope_str + action

        check_info_dict = {
            'audience': keycloak_dict['client_name'],
            'grant_type': 'urn:ietf:params:oauth:grant-type:uma-ticket',
            'permission': name + '#' + scope,
            'response_mode': 'decision',
        }

        response = requests.post(
            f'{server_url}realms/{realm_name}/protocol/openid-connect/token',
            headers = {
                'Authorization': 'Bearer ' + user_token.get_token(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            data = check_info_dict,
        )

        response_json = response.json()

        result = response_json.get('result', False)
        return result

    # Keycloak testing.

    start_time = time.time()
    test_count = 0

    progress_length = len(test_dict.keys())
    progress_percent = 0

    for index, user_uuid in enumerate(test_dict.keys()):

        accept_list = test_accept_dict[user_uuid]
        reject_list = test_reject_dict[user_uuid]

        # Skipping non-active users.

        user_token = user_token_dict.get(user_uuid)

        if user_token is None:
            continue

        for subject, subject_id, action in accept_list:

            result = access_test(user_token, subject, subject_id, action)
            assert result

        for subject, subject_id, action in reject_list:

            result = access_test(user_token, subject, subject_id, action)
            assert not result

        test_count += len(accept_list)
        test_count += len(reject_list)

        progress_f('keycloak acl tests', index + 1)

    elapsed_time = time.time() - start_time
    print(f'Keycloak ACL elapsed time: {elapsed_time:.3f}s, {test_count} tests, {elapsed_time / test_count:.6f}s per test, {test_count / elapsed_time:.3f} tests per s')

    # Previous direct DB testing.

    start_time = time.time()

    progress_length = len(test_dict.keys())
    progress_percent = 0

    for index, user_uuid in enumerate(test_dict.keys()):

        accept_list = test_accept_dict[user_uuid]
        reject_list = test_reject_dict[user_uuid]

        # Skipping non-active users.

        user_client_id = user_client_id_dict.get(user_uuid)

        if user_client_id is None:
            continue

        for subject, subject_id, action in accept_list:

            result = acl.check_direct(user_client_id, None, action, subject, subject_id, session = DBSession)
            assert result

        for subject, subject_id, action in reject_list:

            # Due to mix between subject id and subject overrides checks we can have positives when specific
            # ACL item is not expected to be positive, so we don't assert here.

            result = acl.check_direct(user_client_id, None, action, subject, subject_id, session = DBSession)

        progress_f('direct db acl tests', index + 1)

    elapsed_time = time.time() - start_time
    print(f'Direct DB ACL elapsed time: {elapsed_time:.3f}s, {test_count} tests, {elapsed_time / test_count:.3f}s per test, {test_count / elapsed_time:.6f} tests per s')

    raise NotImplementedError

    pass


def downgrade():
    pass
