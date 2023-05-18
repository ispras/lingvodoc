from lingvodoc.keycloakld import KeycloakSession

from lingvodoc import DBSession
from lingvodoc.models import Client


def check_lingvodoc_id(ids):
    if ids is None or\
            type(ids) is not list or\
            len(ids) != 2 or\
            type(ids[0]) is not int or\
            type(ids[1]) is not int:
        return False
    return True


def check_client_id(authenticated, client_id):
    # TODO: single request
    result = DBSession.query(Client.user_id).filter(Client.id.in_([authenticated,client_id]))\
        .group_by(Client.user_id)
    return result.count() == 1

def check_is_admin(user_id):
    if next(filter(lambda user: user['id'] == user_id, KeycloakSession.keycloak_admin.get_realm_role_members("admin"))):
        return True
    if user_id == "1":
        return True
    elif user_id == 1:
        return True
    else:
        return False
def check_is_active(user_id):
    return KeycloakSession.keycloak_admin.get_user(user_id)['enabled'] == True
