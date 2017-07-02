from pyramid.security import Allow, Deny, Everyone

from .models import (
    DBSession,
    User,
    Client,
    Group,
    BaseGroup,
    acl_by_groups,
    acl_by_groups_single_id
    )

from pyramid.security import forget

from sqlalchemy.orm import joinedload

import logging
from time import time
log = logging.getLogger(__name__)


def groupfinder(client_id, request, factory = None, subject = None):

    if request.registry.settings.get("desktop") and request.registry.settings["desktop"].get("desktop"):
        client_id = request.cookies.get('client_id')
    if not client_id:
        return None

    try:
        factory = factory or request.matched_route.factory
    except AttributeError as e:
        pass

    if not subject:
        try:
            subject = factory.get_subject()
        except AttributeError as e:
            pass

    if not subject or subject == 'no op subject':
        return []

    try:
        user = DBSession.query(User) \
                        .join(Client) \
                        .filter(Client.id == client_id).first()

        groups = DBSession.query(Group)\
            .join(BaseGroup)\
            .join(Group.users)\
            .options(joinedload('BaseGroup')) \
            .filter(User.id == user.id)
        if subject:
            groups = groups.filter(BaseGroup.subject == subject)
        groups = groups.all()

    except AttributeError as e:
            log.error('forget in acl.py')
            forget(request)
            return None

    if not user:
        return None

    groupset = set()
    if user.id == 1:
        groupset.add('Admin')
    for group in groups:
        base_group = group.BaseGroup
        if group.subject_override:
            group_name = base_group.action + ":" + base_group.subject + ":" + str(group.subject_override)
        else:
            if group.subject_client_id:
                group_name = base_group.action + ":" + base_group.subject \
                             + ":" + str(group.subject_client_id) + ":" + str(group.subject_object_id)
            else:
                 group_name = base_group.action + ":" + base_group.subject \
                             + ":" + str(group.subject_object_id)
        groupset.add(group_name)
    for org in user.organizations:
        for group in org.groups:
            base_group = group.BaseGroup
            if group.subject_override:
                group_name = base_group.action + ":" + base_group.subject + ":" + str(group.subject_override)
            else:
                group_name = base_group.action + ":" + base_group.subject \
                             + ":" + str(group.subject_client_id) + ":" + str(group.subject_object_id)
            groupset.add(group_name)
    log.debug("GROUPSET: %d, %s", len(groupset), list(groupset))
    return groupset # todo: caching


def check(client_id, request, action, subject, subject_id):
    """
    Checks if a given action on a given subject is permitted for the specified client.
    """

    principal_set = groupfinder(
        client_id, request, subject = subject)

    # Subject is specified by a single object_id.

    if isinstance(subject_id, int):
        acl_list = acl_by_groups_single_id(subject_id, subject)

    # Subject is specified by a client_id/object_id pair.

    elif isinstance(subject_id, (list, tuple)):
        acl_list = acl_by_groups(subject_id[1], subject_id[0], subject)

    # Ok, just trying something.

    else:
        acl_list = acl_by_groups(None, None, subject)

    # And now checking, see pyramid/authorization.py, method 'permits' of class 'ACLAuthorizationPolicy' for
    # reference.

    for acl_action, acl_principal, acl_permission in acl_list:

        if acl_principal in principal_set and acl_permission == action:
            return True

    return False

