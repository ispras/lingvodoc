from pyramid.security import Allow, Deny, Everyone

from .models import (
    DBSession,
    User,
    Client,
    Group,
    BaseGroup,
    acl_by_groups,
    acl_by_groups_single_id,
    user_to_group_association,
    user_to_organization_association,
    organization_to_group_association,
    DictionaryPerspective
    )

from pyramid.security import forget

from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload

import logging
from time import time
log = logging.getLogger(__name__)


def get_effective_client_id(client_id, request):
    """
    Returns client id to be used for permission checking.
    """

    if request.registry.settings.get("desktop") and request.registry.settings["desktop"].get("desktop"):
        return request.cookies.get('client_id')

    else:
        return client_id

def groupfinder(client_id, request, factory = None, subject = None):

    client_id = get_effective_client_id(client_id, request)

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
        try:
            user = DBSession.query(User) \
                        .join(Client) \
                        .filter(Client.id == client_id).first()

        except AttributeError as e:
                log.error('forget in acl.py')
                forget(request)
                return None

        groupset = set()
        if user is not None and user.id == 1:
            groupset.add('Admin')
        return groupset

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

        # If the user is deactivated, we won't allow any actions except for viewing.

        if not user.is_active and base_group.action != 'view':
            continue

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

            # If the user is deactivated, we won't allow any actions except for viewing.

            if not user.is_active and base_group.action != 'view':
                continue

            if group.subject_override:
                group_name = base_group.action + ":" + base_group.subject + ":" + str(group.subject_override)
            else:
                group_name = base_group.action + ":" + base_group.subject \
                             + ":" + str(group.subject_client_id) + ":" + str(group.subject_object_id)

            groupset.add(group_name)

    log.debug("GROUPSET: %d, %s", len(groupset), list(sorted(groupset)))
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
        if acl_principal in principal_set:

            # Checking carefully, because acl_permission can be, for example, special ALL_PERMISSIONS
            # object.
            
            if not hasattr(acl_permission, '__iter__'):
                if acl_permission == action:
                    return True

            elif action in acl_permission:
                return True

    return False


def check_direct(client_id, request, action, subject, subject_id):
    """
    Checks if a given action on a given subject is permitted for the specified client, accesses DB directly,
    so should be faster.
    """

    client_id = get_effective_client_id(client_id, request)

    if not client_id:
        return False

    try:
        user = Client.get_user_by_client_id(client_id)

    except:
        return False

    # Subject is specified by a client_id/object_id pair.

    if isinstance(subject_id, (list, tuple)):
        subject_client_id, subject_object_id = subject_id[:2]

        # Special case for 'approve_entities' perspective subject, permission depends on perspective's
        # state, see function acls_by_groups() in models.py.

        if subject == 'approve_entities':

            perspective = DBSession.query(DictionaryPerspective).filter_by(
                client_id=subject_client_id, object_id=subject_object_id).first()

            if (perspective and
                (perspective.state == 'Published' or perspective.state == 'Limited access') and
                (action == 'view' or action == 'preview')):

                return True

        # If the user is deactivated, we won't allow any actions except for viewing.

        if not user.is_active and action != 'view':
            return False

        # Ok, checking as usual, first through by-user permissions...

        user_count = DBSession.query(BaseGroup, Group, user_to_group_association).filter(and_(
            BaseGroup.subject == subject,
            BaseGroup.action == action,
            Group.base_group_id == BaseGroup.id,
            or_(Group.subject_override, and_(
                Group.subject_client_id == subject_client_id,
                Group.subject_object_id == subject_object_id)),
            user_to_group_association.c.user_id == user.id,
            user_to_group_association.c.group_id == Group.id)).limit(1).count()

        if user_count > 0:
            return True

        # ...and then through by-organization permissions.

        organization_count = DBSession.query(BaseGroup, Group,
            user_to_organization_association, organization_to_group_association).filter(and_(
                BaseGroup.subject == subject,
                BaseGroup.action == action,
                Group.base_group_id == BaseGroup.id,
                or_(Group.subject_override, and_(
                    Group.subject_client_id == subject_client_id,
                    Group.subject_object_id == subject_object_id)),
                user_to_organization_association.c.user_id == user.id,
                organization_to_group_association.c.organization_id ==
                    user_to_organization_association.c.organization_id,
                organization_to_group_association.c.group_id == Group.id)).limit(1).count()

        if organization_count > 0:
            return True

        return False

    # Subject is specified by a single object_id.

    elif isinstance(subject_id, int):
        subject_object_id = subject_id

        # If the user is deactivated, we won't allow any actions except for viewing.

        if not user.is_active and action != 'view':
            return False

        # Checking as usual, first through by-user permissions...

        user_count = DBSession.query(BaseGroup, Group, user_to_group_association).filter(and_(
            BaseGroup.subject == subject,
            BaseGroup.action == action,
            Group.base_group_id == BaseGroup.id,
            or_(Group.subject_override,
                Group.subject_object_id == subject_object_id),
            user_to_group_association.c.user_id == user.id,
            user_to_group_association.c.group_id == Group.id)).limit(1).count()

        if user_count > 0:
            return True

        # ...and then through by-organization permissions.

        organization_count = DBSession.query(BaseGroup, Group,
            user_to_organization_association, organization_to_group_association).filter(and_(
                BaseGroup.subject == subject,
                BaseGroup.action == action,
                Group.base_group_id == BaseGroup.id,
                or_(Group.subject_override,
                    Group.subject_object_id == subject_object_id),
                user_to_organization_association.c.user_id == user.id,
                organization_to_group_association.c.organization_id ==
                    user_to_organization_association.c.organization_id,
                organization_to_group_association.c.group_id == Group.id)).limit(1).count()

        if organization_count > 0:
            return True

        return False

    # There could be subjects with no id, because they don't exist yet.
    # In that case we only need to check if user is authorized to create this type of objects.

    else:
        # If the user is deactivated, we won't allow any actions except for viewing.

        if not user.is_active and action != 'view':
            return False

        user_count = DBSession.query(BaseGroup, Group, user_to_group_association).filter(and_(
            BaseGroup.subject == subject,
            BaseGroup.action == action,
            Group.base_group_id == BaseGroup.id,
            Group.subject_override,
            user_to_group_association.c.user_id == user.id,
            user_to_group_association.c.group_id == Group.id)).limit(1).count()

        if user_count > 0:
            return True

        # There probably shouldn't be organizations with admin permissions.

        return False

    # Ok, we have a subject we do not know hot to process, so we terminate with error.
    # 
    # In the normal course of operation we shouldn't ever be able to reach this code, but if we somehow do,
    # we at least should know that something is not right.

    raise NotImplementedError

