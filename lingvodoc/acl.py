from pyramid.security import Allow, Deny, Authenticated, Everyone

from .models import (
    DBSession,
    Dictionary,
    User,
    Client,
    Group,
    BaseGroup
    )

from pyramid.security import forget

from sqlalchemy.orm import joinedload

import logging
log = logging.getLogger(__name__)


def groupfinder(client_id, request):
    if not client_id:
        return None

    try:
        user = DBSession.query(User) \
                        .options(joinedload('groups').joinedload('BaseGroup')) \
                        .options(joinedload('organizations').joinedload('groups').joinedload('BaseGroup')) \
                        .join(Client) \
                        .filter(Client.id == client_id).first()

        groups = DBSession.query(Group)\
            .options(joinedload('BaseGroup')) \
            .filter(Group.users.contains(user)).all()

    except AttributeError as e:
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
    log.error("GROUPLIST: %d, %s", len(grouplist), grouplist)
    return grouplist


class DummyDeny(object):
    def __init__(self, request):
        try:
            client_id = request.authenticated_userid
            if not client_id:
                print("Not authorized")
                return
            client = DBSession.query(Client).filter_by(id=client_id).first()
            user = DBSession.query(User).filter_by(id=client.user_id).first()
            dictionary_client_id = request.matchdict['client_id']
            dictionary_id = request.matchdict['dictionary_id']
            self.__acl__ = [
                (Allow, 'can_add_words:' + str(dictionary_id) + ':' + str(dictionary_client_id), 'edit'),
                (Deny, Everyone, 'edit')
            ]
        except KeyError as e:
            print("Not authorized", str(e))


# class Article(object):
#     def __init__(self, request):
#         matchdict = request.matchdict
#         article = matchdict.get('article', None)
#         if article == '1':
#             self.__acl__ = [ (Allow, 'editor', 'view') ]