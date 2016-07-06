__author__ = 'alexander'


from lingvodoc.models import (
    DBSession,
    DictionaryPerspective,
    GroupingEntity,
    LevelOneEntity,
    LexicalEntry
)

from pyramid.httpexceptions import (
    HTTPNotFound,
    HTTPOk
)
from pyramid.request import Request

import json


def approve_all_logic(lexes, object_id, headers):
    entities = []
    for lex in lexes:
        levones = DBSession.query(LevelOneEntity).filter_by(parent=lex).all()
        for levone in levones:
            entities += [{'type': 'leveloneentity',
                                 'client_id': levone.client_id,
                                 'object_id': levone.object_id}]
            for levtwo in levone.leveltwoentity:
                entities += [{'type': 'leveltwoentity',
                                     'client_id':levtwo.client_id,
                                     'object_id':levtwo.object_id}]
        groupents = DBSession.query(GroupingEntity).filter_by(parent=lex).all()
        for groupent in groupents:
            entities += [{'type': 'groupingentity',
                                 'client_id': groupent.client_id,
                                 'object_id': groupent.object_id}]
    return entities