from .models import (
    DBSession,
    MetaWord,
    WordEntry,
    Dictionary,
    User,
    Client,
    Group,
    BaseGroup
    )

from pyramid.security import forget

def groupfinder(client_id, request):
    if not client_id:
        return None
    try:
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(User).filter_by(id=client.user_id).first()
    except AttributeError as e:
        forget(request)
        return None
    if not user:
        return None
    grouplist = []
    for group in user.groups:
        base_group = DBSession.query(BaseGroup).filter(BaseGroup.id == group.base_group_id).first()
        grouplist.append(base_group.name + ":" + group.subject)
    return grouplist