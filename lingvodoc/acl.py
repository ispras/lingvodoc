from pyramid.security import Allow, Deny, Everyone

from .models import (
    DBSession,
    User,
    Client,
    Group,
    BaseGroup
    )

from pyramid.security import forget

from sqlalchemy.orm import joinedload

import logging
from time import time
log = logging.getLogger(__name__)


def groupfinder(client_id, request):
    if request.registry.settings.get("desktop") and request.registry.settings["desktop"].get("desktop"):
        client_id = request.cookies.get('client_id')
    if not client_id:
        return None
    subject = None
    factory = request.matched_route.factory
    if not factory:
        return []
    try:
        subject = request.matched_route.factory.get_subject()
    except AttributeError as e:
        pass
    if subject == 'no op subject':
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

    grouplist = []
    if user.id == 1:
        grouplist.append('Admin')
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
        grouplist.append(group_name)
    for org in user.organizations:
        for group in org.groups:
            base_group = group.BaseGroup
            if group.subject_override:
                group_name = base_group.action + ":" + base_group.subject + ":" + str(group.subject_override)
            else:
                group_name = base_group.action + ":" + base_group.subject \
                             + ":" + str(group.subject_client_id) + ":" + str(group.subject_object_id)
            grouplist.append(group_name)
    log.debug("GROUPLIST: %d, %s", len(grouplist), grouplist)
    # log.error("GROUPLIST: %d, %s", len(grouplist), grouplist)
    return grouplist  # todo: caching
