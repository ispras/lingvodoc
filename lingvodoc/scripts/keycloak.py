
# Standard library imports.

import logging

# External imports.

import keycloak


# Setting up logging, if we are not being run as a script.

if __name__ != '__main__':

    log = logging.getLogger(__name__)
    log.debug('module init')


# If we are being run as a script.

LINGVODOC_REALM_NAME = 'lingvodoc'

if __name__ == '__main__':

    keycloak_admin = keycloak.KeycloakAdmin(
        server_url = 'http://localhost:8080',
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
    #       realm.get('realm') == LINGVODOC_REALM_NAME
    #       for realm in realms
    #   )

    result = keycloak_admin.create_realm(
        {'realm': LINGVODOC_REALM_NAME, 'enabled': True},
        skip_exists = True
    )

    pass
