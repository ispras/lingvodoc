from .models import (
    DBSession,
    MetaWord,
    WordEntry,
    Dictionary,
    User,
    Client
    )


def groupfinder(client_id, request):
    client = DBSession.query(Client).filter_by(id=client_id).first()
    user = DBSession.query(User).filter_by(id=client.user_id).first()
    if not user:
        return None
    grouplist = []
    for group in user.groups:
        grouplist.append(group.name)
    return grouplist