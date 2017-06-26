from lingvodoc.views.v2.utils import (
    get_user_by_client_id,
    view_field_from_object,
    check_client_id
)
from sqlalchemy.exc import IntegrityError

from pyramid.response import Response
from pyramid.view import view_config
from lingvodoc.models import (
    DBSession,
    Locale,
    TranslationAtom,
    TranslationGist,
    BaseGroup,
    User,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    Field,
    Client,
    Group,
    UserBlobs,
    Language,
    ObjectTOC,
    LexicalEntry,
    Dictionary,
    Entity
)

from sqlalchemy import (
    func,
    or_,
    and_,
    tuple_,
    not_
)
from pyramid.httpexceptions import (
    HTTPBadRequest,
    HTTPConflict,
    HTTPFound,
    HTTPInternalServerError,
    HTTPNotFound,
    HTTPOk
)
from pyramid.security import authenticated_userid
# from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response
from lingvodoc.exceptions import CommonException

import sys
import multiprocessing

if sys.platform == 'darwin':
    multiprocessing.set_start_method('spawn')

import logging
log = logging.getLogger(__name__)
import json
import requests
from pyramid.request import Request
from time import time

from lingvodoc.schema.query import schema

from copy import deepcopy
from lingvodoc.views.v2.translations import translationgist_contents




@view_config(route_name='fix_groups', renderer='json', permission='admin')
def fix_groups(request):
    for dictionary in DBSession.query(Dictionary):
        for base in DBSession.query(BaseGroup).filter_by(dictionary_default=True):

            groups = DBSession.query(Group).filter_by(base_group_id=base.id,
                              subject_object_id=dictionary.object_id,
                                                      subject_client_id=dictionary.client_id).all()
            if len(groups) > 1:
                users = list()
                for group in groups:
                    for user in group.users:
                        if user not in users:
                            users.append(user)
                winner = groups[0]
                for user in users:
                    if user not in winner.users:
                        winner.users.append(user)
                for delete_group in groups[1:]:
                    DBSession.delete(delete_group)
    for perspective in DBSession.query(DictionaryPerspective):
        for base in DBSession.query(BaseGroup).filter_by(perspective_default=True):

            groups = DBSession.query(Group).filter_by(base_group_id=base.id,
                              subject_object_id=perspective.object_id,
                                                      subject_client_id=perspective.client_id).all()
            if len(groups) > 1:
                users = list()
                for group in groups:
                    for user in group.users:
                        if user not in users:
                            users.append(user)
                winner = groups[0]
                for user in users:
                    if user not in winner.users:
                        winner.users.append(user)
                for delete_group in groups[1:]:
                    DBSession.delete(delete_group)

    base_id = 26

    groups = DBSession.query(Group).filter_by(base_group_id=base_id,
                      subject_override = True).all()
    if len(groups) > 1:
        users = list()
        for group in groups:
            for user in group.users:
                if user not in users:
                    users.append(user)
        winner = groups[0]
        for user in users:
            if user not in winner.users:
                winner.users.append(user)
        for delete_group in groups[1:]:
            DBSession.delete(delete_group)

    return {}

def translation_service_search(searchstring):
    translationatom = DBSession.query(TranslationAtom)\
        .join(TranslationGist).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service')\
        .order_by(TranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response

def translation_service_search_all(searchstring):
    tralationgist = DBSession.query(TranslationGist)\
        .join(TranslationAtom).\
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2)\
        .order_by(TranslationGist.client_id)\
        .first()
    response = {"client_id": tralationgist.client_id, "object_id": tralationgist.object_id}
    #response = translationgist_contents(translationatom.parent)
    return response


@view_config(route_name='fix_fields', renderer='json', permission='admin')
def fix_fields(request):
    # Paradigmatic Forms / Link - 1 212
    # Backref / Link - 1 213
    # Comment / Text - 674 5
    # Markup / Markup - 66 23
    # Etymology / Grouping Tag - 66 25
    # Paradigm Markup / Markup - 66 27
    # Mark
    # Phonological Transcription: 671 14204
    # wrong phon 671 16070

    """

    """
    # # Mark
    # /671/15154/perspective/748/553/
    # Transcription field:
    #"""
    empty_lang = DBSession.query(Language.client_id, Language.object_id).filter(Language.marked_for_deletion == True,
        Language.client_id==31, Language.object_id==26).first()
    if empty_lang:
        return {'ok': 'already done'}


    # Phon tr
    entities = DBSession.query(Entity).join(LexicalEntry).filter(and_(Entity.field_client_id == 671,
                                                                 Entity.field_object_id == 16070,
                                                                 LexicalEntry.parent_client_id == 671,
                                                                 LexicalEntry.parent_object_id ==10419))
    for entity in entities:
        entity.field_client_id = 671
        entity.field_object_id = 14204

    # Phon change link
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=742, object_id=7548).one()
    tmp_field.field_client_id = 671
    tmp_field.field_object_id = 14204

    tmp_field = DBSession.query(Field).filter_by(client_id=671, object_id=16070).one()
    tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=671,
                                                     object_id=16070).one()
    tmp_objecttoc.marked_for_deletion = True
    ####


    old_order_fields = DBSession.query(DictionaryPerspectiveToField).filter_by(parent_client_id=748, parent_object_id=553).all()
    for p_to_field in old_order_fields:
        old_position = p_to_field.position
        if old_position >= 2:
            p_to_field.position = old_position + 1
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=748,
                                                parent_object_id=553,
                                                field_client_id=66,
                                                field_object_id=17,
                                                position=2)
    DBSession.add(field_object)


    # /dictionary/671/12796/perspective/748/1802/
    # Markup to paradigm Markup
    perspfield = DBSession.query(DictionaryPerspectiveToField).filter_by(parent_client_id=748,
                                                                         parent_object_id=1802,
                                                                         field_client_id=66,
                                                                         field_object_id=23,
                                                                         marked_for_deletion=False).one()
    perspfield.field_client_id = 66
    perspfield.field_object_id = 27
    # markup marked for deletion #  TODO: del link
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=742, object_id=7586).one()
    tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=742,
                                                     object_id=7586).one()
    tmp_objecttoc.marked_for_deletion = True

    # change Transcription position
    old_order_fields = DBSession.query(DictionaryPerspectiveToField).filter_by(parent_client_id=748, parent_object_id=1802).all()
    for p_to_field in old_order_fields:
        old_position = p_to_field.position
        if old_position >= 2:
            p_to_field.position = old_position + 1
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=742, object_id=7585).one()
    tmp_field.position = 2


    # Paradigmatic forms -> backref
    #
    entities = DBSession.query(Entity).join(LexicalEntry).filter(and_(Entity.field_client_id == 1,
                                                                 Entity.field_object_id == 212,
                                                                 Entity.marked_for_deletion == False,
                                                                 LexicalEntry.parent_client_id == 671,
                                                                 LexicalEntry.parent_object_id ==12797))
    for entity in entities:
        entity.field_client_id = 1
        entity.field_object_id = 213
    # PF deletion
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=742, object_id=7574).one()
    tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=742,
                                                     object_id=7574).one()
    tmp_objecttoc.marked_for_deletion = True

    # Transcription deletion 7599
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=742, object_id=7599).one()
    tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=742,
                                                     object_id=7599).one()
    tmp_objecttoc.marked_for_deletion = True


    persp_ids = [((91, 4), (91, 5)), ((588, 4), (588, 5)), ((93, 5), (93, 6)), ((92, 5), (92, 6)), ((274, 5), (274, 6)),
                 ((504, 5), (504, 6)), ((654, 4), (654, 5)), ((96, 5), (96, 6)), ((562, 8), (562, 14)),
                 ((505, 4), (505, 5)), ((107, 5), (107, 6)), ((304, 17), (304, 37)), ((476, 5), (476, 6)),
                 ((94, 5), (94, 6)), ((639, 5), (639, 11)), ((577, 7), (577, 13)), ((269, 5), (269, 6)),
                 ((336, 12), (336, 17))]
    res = list()
    for persp in persp_ids:
        field_object = DictionaryPerspectiveToField(client_id=1,
                                                    parent_client_id=persp[0][0],
                                                    parent_object_id=persp[0][1],
                                                    field_client_id=1,
                                                    field_object_id=212,
                                                    link_client_id=persp[1][0],
                                                    link_object_id=persp[1][1],
                                                    position=12)  # todo: fix positions everywhere
        DBSession.add(field_object)
        field_object = DictionaryPerspectiveToField(client_id=1,
                                                    parent_client_id=persp[1][0],
                                                    parent_object_id=persp[1][1],
                                                    field_client_id=1,
                                                    field_object_id=213,
                                                    link_client_id=persp[0][0],
                                                    link_object_id=persp[0][1],
                                                    position=11)
        DBSession.add(field_object)

    # delete useless fields from 304 16
     # 2016-12-23 13:24:18.711311 |        30 |       304 |               16 |              304 |                |                |             167 |              33 |                |                | f                   |       12
     # 2016-12-23 13:24:18.711311 |        31 |       304 |               16 |              304 |                |                |             167 |              33 |                |                | f                   |       13
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=304, object_id=30).one()
    tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=304,
                                                     object_id=30).one()
    tmp_objecttoc.marked_for_deletion = True

    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=304, object_id=31).one()
    tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=304,
                                                     object_id=31).one()
    tmp_objecttoc.marked_for_deletion = True

    # add
    tmp_persp = ((304, 16), (304, 23))
    tmp_field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=tmp_persp[0][0],
                                                parent_object_id=tmp_persp[0][1],
                                                field_client_id=1,
                                                field_object_id=212,
                                                link_client_id=tmp_persp[1][0],
                                                link_object_id=tmp_persp[1][1],
                                                position=12)  # todo: fix positions everywhere
    DBSession.add(tmp_field_object)
    tmp_field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=tmp_persp[1][0],
                                                parent_object_id=tmp_persp[1][1],
                                                field_client_id=1,
                                                field_object_id=213,
                                                link_client_id=tmp_persp[0][0],
                                                link_object_id=tmp_persp[0][1],
                                                position=11)
    DBSession.add(tmp_field_object)

    # del terrible and useless fields from /81/4/perspective/81/5/
    # "Translation missing for your locale and fallback locale"
    empty_fields = DBSession.query(DictionaryPerspectiveToField).filter_by(field_client_id=167, field_object_id=33).all()
    for field in empty_fields:
        field.marked_for_deletion = True

        tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=field.client_id,
                                                         object_id=field.object_id).one()
        tmp_objecttoc.marked_for_deletion = True

    # tmp_field = DBSession.query(Field).filter_by(client_id=167, object_id=33).one()  #todo: think about desktop and sync
    # tmp_field.marked_for_deletion = True

    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=167,
                                                     object_id=33).one()
    tmp_objecttoc.marked_for_deletion = True

    persp_ids = [(804, 16), (776, 23), (776, 32), (738, 12395), (804, 18), (804, 19), (805, 7), (798, 14413), (687, 9),
                 (804, 17), (804, 15), (767, 7), (770, 1451), (769, 7), (770, 27127), (776, 7), (770, 42641), (798, 16),
                 (799, 435), (800, 7), (777, 7)]
    res = list()
    for persp in persp_ids:
        field_object = DictionaryPerspectiveToField(client_id=1,
                                                    parent_client_id=persp[0],
                                                    parent_object_id=persp[1],
                                                    field_client_id=674,
                                                    field_object_id=5,
                                                    position=3)  # todo: fix positions everywhere
        DBSession.add(field_object)

    # 514, 3 => pos1 + field
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=514, object_id=11).one()
    tmp_field.position = 1

    # add markup
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=514,
                                                parent_object_id=3,
                                                field_client_id=66,
                                                field_object_id=23,
                                                self_client_id=514,
                                                self_object_id=12,
                                                position=12)  # todo: fix positions everywhere
    DBSession.add(field_object)
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=515,
                                                parent_object_id=3,
                                                field_client_id=66,
                                                field_object_id=23,
                                                self_client_id=515,
                                                self_object_id=12,
                                                position=12)  # todo: fix positions everywhere
    DBSession.add(field_object)
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=519,
                                                parent_object_id=3,
                                                field_client_id=66,
                                                field_object_id=23,
                                                self_client_id=519,
                                                self_object_id=12,
                                                position=12)  # todo: fix positions everywhere
    DBSession.add(field_object)


    # add etymology
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=514, object_id=2178).one()
    tmp_field.position = 10
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=514,
                                                parent_object_id=3,
                                                field_client_id=66,
                                                field_object_id=25,
                                                position=9)  # todo: fix positions everywhere
    DBSession.add(field_object)

    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=515, object_id=2429).one()
    tmp_field.position = 10
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=515,
                                                parent_object_id=3,
                                                field_client_id=66,
                                                field_object_id=25,
                                                position=9)  # todo: fix positions everywhere
    DBSession.add(field_object)

    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=519, object_id=2402).one()
    tmp_field.position = 10
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=519,
                                                parent_object_id=3,
                                                field_client_id=66,
                                                field_object_id=25,
                                                position=9)  # todo: fix positions everywhere
    DBSession.add(field_object)


    # happy three perspectives
    # Transcription <=> translation
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=514, object_id=6).one()
    tmp_field.position = 3
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=514, object_id=7).one()
    tmp_field.position = 2

    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=515, object_id=6).one()
    tmp_field.position = 9
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=515, object_id=7).one()
    tmp_field.position = 8

    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=519, object_id=6).one()
    tmp_field.position = 9
    tmp_field = DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=519, object_id=7).one()
    tmp_field.position = 8

    # add Paradigm markup
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=514,
                                                parent_object_id=4,
                                                field_client_id=66,
                                                field_object_id=27,
                                                self_client_id=514,
                                                self_object_id=8,
                                                position=9)  # todo: fix positions everywhere

    DBSession.add(field_object)

    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=515,
                                                parent_object_id=4,
                                                field_client_id=66,
                                                field_object_id=27,
                                                self_client_id=515,
                                                self_object_id=8,
                                                position=9)  # todo: fix positions everywhere

    DBSession.add(field_object)
    field_object = DictionaryPerspectiveToField(client_id=1,
                                                parent_client_id=519,
                                                parent_object_id=4,
                                                field_client_id=66,
                                                field_object_id=27,
                                                self_client_id=519,
                                                self_object_id=8,
                                                position=9)  # todo: fix positions everywhere

    DBSession.add(field_object)

   # "dictionary ids: (799, 21), Perspective ids: (799, 26), link: http://lingvodoc.ispras.ru/#/dictionary/799/21/perspective/799/26/view vvvorobeva", - dictionary deleted
   # "dictionary ids: (748, 1796), Perspective ids: (748, 1799), link: http://lingvodoc.ispras.ru/#/dictionary/748/1796/perspective/748/1799/view yhnnh", - empty
   # "dictionary ids: (770, 4), Perspective ids: (770, 7), link: http://lingvodoc.ispras.ru/#/dictionary/770/4/perspective/770/7/view julianor", - empty
   # "dictionary ids: (769, 3613), Perspective ids: (769, 3616), link: http://lingvodoc.ispras.ru/#/dictionary/769/3613/perspective/769/3616/view nadiakrass", - dictionary deleted
   # "dictionary ids: (769, 3619), Perspective ids: (769, 3622), link: http://lingvodoc.ispras.ru/#/dictionary/769/3619/perspective/769/3622/view nadiakrass", - dictionary deleted
   # "dictionary ids: (769, 3625), Perspective ids: (769, 3630), link: http://lingvodoc.ispras.ru/#/dictionary/769/3625/perspective/769/3630/view nadiakrass", - dictionary deleted
   # "dictionary ids: (769, 3633), Perspective ids: (769, 3636), link: http://lingvodoc.ispras.ru/#/dictionary/769/3633/perspective/769/3636/view nadiakrass", - dictionary deleted
    persp_ids = [(799, 26), (748, 1799), (770, 7), (769, 3616), (769, 3622), (769, 3630), (769, 3636)]
    persps = DBSession.query(DictionaryPerspective).filter(tuple_(DictionaryPerspective.client_id, DictionaryPerspective.object_id).in_(persp_ids))
    for persp in persps:
        persp.marked_for_deletion = True

        tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=persp.client_id,
                                                         object_id=persp.object_id).one()
        tmp_objecttoc.marked_for_deletion = True

    dict_ids = [(748, 1796), (770, 4)]
    dicts = DBSession.query(Dictionary).filter(tuple_(Dictionary.client_id, Dictionary.object_id).in_(dict_ids))
    for dicty in dicts:
        dicty.marked_for_deletion = True

        tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=dicty.client_id,
                                                         object_id=dicty.object_id).one()
        tmp_objecttoc.marked_for_deletion = True
    yhnnh_persp = [(671, 15155)]
    persp_ids = yhnnh_persp + [(398, 3), (563, 4), (424, 3), (623, 5), (91, 4), (588, 4), (93, 5), (589, 5), (514, 3), (136, 3), (400, 4), (585, 3), (92, 5), (652, 3), (620, 3), (495, 5), (359, 3), (339, 5), (247, 5), (425, 4), (569, 4), (655, 4), (256, 5), (101, 5), (80, 3), (418, 4), (67, 4), (77, 5), (515, 3), (657, 4), (66, 5), (528, 5), (79, 5), (579, 5), (653, 3), (580, 3), (274, 5), (70, 5), (662, 10), (85, 4), (625, 3), (296, 5), (100, 5), (504, 5), (407, 5), (498, 4), (139, 4), (219, 4), (114, 4), (654, 4), (581, 3), (96, 5), (624, 3), (524, 5), (112, 3), (143, 4), (153, 2), (408, 5), (519, 3), (435, 12), (562, 8), (159, 4), (640, 3), (583, 3), (220, 5), (502, 4), (656, 3), (630, 3), (523, 5), (473, 4), (522, 5), (586, 3), (503, 5), (660, 8), (631, 4), (527, 5), (638, 5), (265, 5), (126, 4), (477, 5), (84, 4), (505, 4), (81, 5), (637, 5), (635, 5), (82, 4), (595, 5), (435, 14), (267, 5), (277, 3), (478, 5), (309, 4), (311, 3), (474, 4), (303, 3), (534, 4), (283, 5), (107, 5), (304, 16), (304, 17), (160, 3), (224, 3), (481, 5), (310, 3), (312, 3), (379, 5), (476, 5), (479, 5), (94, 5), (380, 5), (377, 5), (83, 5), (330, 4), (475, 3), (71, 5), (95, 4), (378, 5), (376, 5), (636, 5), (108, 5), (157, 5), (155, 5), (75, 4), (285, 5), (144, 4), (147, 5), (140, 3), (217, 5), (218, 5), (226, 4), (596, 5), (78, 4), (639, 5), (105, 4), (150, 5), (146, 5), (242, 5), (260, 5), (254, 5), (259, 5), (243, 5), (257, 5), (248, 5), (255, 5), (245, 5), (251, 5), (264, 5), (246, 5), (69, 5), (577, 7), (258, 5), (271, 5), (261, 5), (263, 5), (266, 5), (275, 4), (272, 5), (268, 5), (282, 5), (269, 5), (273, 5), (270, 5), (284, 5), (280, 5), (278, 5), (281, 5), (279, 5), (289, 5), (358, 4), (324, 3), (482, 5), (329, 3), (480, 5), (340, 5), (222, 5), (341, 5), (333, 4), (336, 12), (555, 3), (326, 4), (342, 3), (332, 4), (533, 4), (334, 4), (262, 5), (133, 5)]
    for persp_id in persp_ids:
        perspfield = DBSession.query(DictionaryPerspectiveToField).filter_by(parent_client_id=persp_id[0],
                                                                             parent_object_id=persp_id[1],
                                                                             field_client_id=1,
                                                                             field_object_id=212,
                                                                             marked_for_deletion=False).one()
        perspfield.field_client_id = 1
        perspfield.field_object_id = 213
    dicts = DBSession.query(DictionaryPerspective)
    #return
    persp_ids = [(304, 17), (577, 7), (577, 6), (514, 3), (515, 3), (519, 3), (512, 5), (304, 16)]+ [(336, 12)]
    resp = translation_service_search_all("Lexical Entries")
    le_translation_gist_client_id, le_translation_gist_object_id = 1, 159 # 1, 159
    persps = DBSession.query(DictionaryPerspective).filter(tuple_(DictionaryPerspective.client_id, DictionaryPerspective.object_id).in_(persp_ids))
    for persp in persps:
        persp.translation_gist_client_id = le_translation_gist_client_id
        persp.translation_gist_object_id = le_translation_gist_object_id

    # translation change type to dictionary: 577 2, 304 10, 512 2,
    gist_ids = [(577, 2), (304, 10), (512, 2)]
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(gist_ids))
    for translation_gist in translation_gists:
        translation_gist.type = "Dictionary"

    # change translation type to language  304 12
    gist_ids = [(304, 12)]
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(gist_ids))
    for translation_gist in translation_gists:
        translation_gist.type = "Language"

    # translation to translation/languages: 334 2/500, 116, 508, 51; 480 2/500, 95, 500, 99, 500, 104; 631 2/629, 6; 333 2/ 500, 98, 500, 105, 500, 125; 479 2/ 500, 100. 500, 126

    # rename: (508, 51) - Selkup селькупский язык,(500, 125) - Forest dialect of Enents language Энецкий лесной диалект # new gist 500, 125
    gist = TranslationGist(client_id=1, type="Language")
    DBSession.add(gist)
    DBSession.flush()
    atom = TranslationAtom(client_id=1, content="Selkup", locale_id=2, parent=gist)
    DBSession.add(atom)
    DBSession.flush()
    atom = TranslationAtom(client_id=1, content="Cелькупский язык", locale_id=1, parent=gist)
    DBSession.add(atom)
    DBSession.flush()
    selkup_ids = [(508, 51)]
    language = DBSession.query(Language).filter(
        tuple_(Language.client_id, Language.object_id).in_(selkup_ids)).one()
    language.translation_gist_client_id = gist.client_id
    language.translation_gist_object_id = gist.object_id

    gist = TranslationGist(client_id=1, type="Language")
    DBSession.add(gist)
    DBSession.flush()
    atom = TranslationAtom(client_id=1, content="Forest dialect of Enents language", locale_id=2, parent=gist)
    DBSession.add(atom)
    DBSession.flush()
    atom = TranslationAtom(client_id=1, content="Энецкий лесной диалект", locale_id=1, parent=gist)
    DBSession.add(atom)
    DBSession.flush()
    enets_ids = [(500, 125)]
    language = DBSession.query(Language).filter(
        tuple_(Language.client_id, Language.object_id).in_(enets_ids)).one()
    language.translation_gist_client_id = gist.client_id
    language.translation_gist_object_id = gist.object_id
    # langs = [(500, 116),  (500, 95), (500, 99), (500, 104), (629, 6), (500, 98), (500, 105), (500, 100), (500, 126)]  # marked_for_deletion = True
    langs = [(500, 116),  (500, 95), (500, 99), (500, 104), (629, 6), (500, 98), (500, 105), (500, 100), (500, 126)]
    languages = DBSession.query(Language).filter(
        tuple_(Language.client_id, Language.object_id).in_(langs))
    for language in languages:
        language.marked_for_deletion = True
        tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=language.client_id,
                                                         object_id=language.object_id).one()
        tmp_objecttoc.marked_for_deletion = True
    #change translation to lexical entries: 336 12 (fixed)

    #change translation to correct Paradigms 748 1802 748 553
    resp = translation_service_search_all("Paradigms")
    par_translation_gist_client_id, par_translation_gist_object_id = resp['client_id'], resp['object_id'] # 1, 159
    persp_ids = [(748, 553), (748, 1802)]
    persps = DBSession.query(DictionaryPerspective).filter(tuple_(DictionaryPerspective.client_id, DictionaryPerspective.object_id).in_(persp_ids))
    for persp in persps:
        persp.translation_gist_client_id = par_translation_gist_client_id
        persp.translation_gist_object_id = par_translation_gist_object_id
    res = dict()
    persp_gists = [(1, 26), (1, 159)]
    # res['wrong_perspectives'] = ["http://localhost:6544/dictionary/%s/%s/perspective/%s/%s" % (o[0], o[1], o[2], o[3],)
    res['wrong_perspectives'] = ["http://localhost:6543/dictionary/%s/%s/perspectives  %s %s" % (o[0], o[1], o[2], o[3])
                                 for o in DBSession.query(DictionaryPerspective.parent_client_id,
                                                          DictionaryPerspective.parent_object_id,
                                                          DictionaryPerspective.client_id,
                                                          DictionaryPerspective.object_id).join(Dictionary).filter(not_(
            tuple_(DictionaryPerspective.translation_gist_client_id,
                   DictionaryPerspective.translation_gist_object_id).in_(
                persp_gists)), DictionaryPerspective.marked_for_deletion == False,
        Dictionary.marked_for_deletion == False, Dictionary.category == 0).all()]
    res['wrong_perspectives'] = sorted(res['wrong_perspectives'])


    new_langs = DBSession.query(Dictionary.parent_client_id, Dictionary.parent_object_id).filter(
        Dictionary.marked_for_deletion == False).all()
    # new_langs = set(new_langs)
    new_langs = DBSession.query(Language.client_id, Language.object_id, Language.parent_client_id,
                                Language.parent_object_id).filter(
        tuple_(Language.client_id, Language.object_id).in_(new_langs)).all()
    langs = list()
    DBSession.flush()
    while new_langs != langs:
        langs = deepcopy(new_langs)
        for lang in langs:
            if lang[2] and lang[3]:
                parent = DBSession.query(Language.client_id, Language.object_id, Language.parent_client_id,
                                Language.parent_object_id).filter_by(client_id=lang[2],
                                                             object_id=lang[3]).one()
                if parent not in new_langs:
                    new_langs.append(parent)
    langs = [(o[0], o[1]) for o in langs]
    empty_langs = DBSession.query(Language).filter(
        not_(tuple_(Language.client_id, Language.object_id).in_(langs)), Language.client_id != 1).all()

    for lang in empty_langs:
        lang.marked_for_deletion = True
        objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=lang.client_id, object_id=lang.object_id).one()
        objecttoc.marked_for_deletion = True
    DBSession.flush()
    empty_langs = DBSession.query(Language.client_id, Language.object_id).filter(Language.marked_for_deletion == False,
        not_(tuple_(Language.client_id, Language.object_id).in_(langs))).all()

    res['empty_langs'] = empty_langs
    res['non_empty_langs'] = [tuple(o) for o in langs]
    return res

def del_object(tmp_object):
    tmp_object.marked_for_deletion = True
    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=tmp_object.client_id,
                                                     object_id=tmp_object.object_id).one()
    tmp_objecttoc.marked_for_deletion = True

def transfer_language(transferred_lng_ids, target_lng_ids):
    transferred_lng = DBSession.query(Language).filter(
        tuple_(Language.client_id, Language.object_id) == transferred_lng_ids).one()

    del_gists = DBSession.query(TranslationGist).filter(and_(TranslationGist.client_id == transferred_lng.translation_gist_client_id,
                                                        TranslationGist.object_id == transferred_lng.translation_gist_object_id,
                                                             TranslationGist.marked_for_deletion == False)).all()
    for gist in del_gists:
        del_atoms = DBSession.query(TranslationAtom).filter(and_(TranslationAtom.parent_client_id == gist.client_id,
                                                        TranslationAtom.parent_object_id == gist.object_id))
        #print("deleted language: ", transferred_lng_ids)
        for atom in del_atoms:
            #print("atom: ", atom.content )
            tmp_atom = DBSession.query(TranslationAtom).filter_by(client_id=atom.client_id, object_id=atom.object_id).one()
            del_object(tmp_atom)
        tmp_gist = DBSession.query(TranslationGist).filter_by(client_id=gist.client_id, object_id=gist.object_id).one()
        del_object(tmp_gist)


    # find all dictionaries and languages
    dictionaries = DBSession.query(Dictionary).filter(tuple_(Dictionary.parent_client_id, Dictionary.parent_object_id) == transferred_lng_ids).all()
    for dictionary in dictionaries:
        dictionary.parent_client_id = target_lng_ids[0]
        dictionary.parent_object_id = target_lng_ids[1]
        #print("dictionary moved: ", dictionary.client_id, dictionary.object_id)
    languages = DBSession.query(Language).filter(tuple_(Language.parent_client_id, Language.parent_object_id) == transferred_lng_ids).all()
    for language in languages:
        language.parent_client_id = target_lng_ids[0]
        language.parent_object_id = target_lng_ids[1]
    #print(transferred_lng.client_id, transferred_lng.object_id)
    del_object(transferred_lng)

def change_entity_field(entities, field_client_id, field_object_id):
    for entity in DBSession.query(Entity).filter(tuple_(Entity.client_id, Entity.object_id).in_(entities)).all():
        entity.field_client_id = field_client_id
        entity.field_object_id = field_object_id

@view_config(route_name='testing', renderer='json')
def testing(request):
    transfer_language((500, 97), (508, 47)) # Самодийский язык-> Samoyed
    transfer_language((31, 30), (508, 49)) # Enets language/Forest dialect+Tundra Enets-> Uralic/Samoyed/Enez/
    transfer_language((31, 29), (508, 48)) # Nenez language/ Nenez-> Uralic/Samoyed/Nenez/
    transfer_language((31, 23), (508, 38)) # Saami language/ -> Uralic/Saami
    transfer_language((31, 28), (508, 45)) # Mansi+Yakyt/ -> Uralic/Mansi
    transfer_language((500, 96), (508, 45)) # Mansi-> Uralic/Mansi
    transfer_language((31, 32), (252, 42)) # tubulars language-> Altai language/Northern dialect/Tubalars dialect
    transfer_language((121, 7), (633, 23)) # Evenki language-> tungusskie/Evenki
    transfer_language((221, 5), (508, 50)) # Nganasan language-> Samoyed/Nganasan
    transfer_language((357, 6), (508, 41)) # Mari language-> Uralic/Mari
    transfer_language((375, 13), (500, 124)) # Казахский язык -> Kazakh
    transfer_language((493, 9), (508, 38)) # Саамские языки -> Uralic/Saami
    transfer_language((718, 5), (678, 9)) # Yakut  -> Uralic/Mansi-> Yakut
    transfer_language((799, 7), (508, 44)) # Eastern Khanty -> Uralic Khanty
    transfer_language((799, 44), (508, 44)) # Eastern Khanty -> Uralic Khanty
    transfer_language((31, 31), (508, 51)) # Selkup language -> Uralic/Samoyed/Selkup
    transfer_language((31, 25), (508, 42)) # Komi-Zyrian -> Uralic-Komi
    transfer_language((500, 125), (33, 85)) # Forest dialect of Enents language -> Forest dialect

    # fix 2
    #print("="*5)
    # Башкирско-русский словарь, Оренбург, 1899, составитель В.В.Катаринский при помощи башкира Куватова -> Bashkir

    transfer_language((472, 29), (500, 121))
    # Татарский язык (Словарь, 1880 г.) -> Tatar
    transfer_language((472, 26), (500, 122))
    return {"status": "languages fixed"}

@view_config(route_name='testing_translations', renderer='json')
def testing_translations(request):
    """
    res = dict()
    res['dictionary'] = list()
    res['perspective'] = list()
    res['language'] = list()
    res['field'] = list()
    res['parents'] = list()
    dicts = DBSession.query(Dictionary.translation_gist_client_id, Dictionary.translation_gist_object_id).all()
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(dicts)).filter(
        TranslationGist.type != 'Dictionary')
    for gist in translation_gists:
        res['dictionary'].append(translationgist_contents(gist))
    persps = DBSession.query(DictionaryPerspective.translation_gist_client_id,
                             DictionaryPerspective.translation_gist_object_id).all()
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(persps)).filter(
        TranslationGist.type != 'Perspective')
    for gist in translation_gists:
        res['perspective'].append(translationgist_contents(gist))
    langs = DBSession.query(Language.translation_gist_client_id, Language.translation_gist_object_id).all()
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(langs)).filter(
        TranslationGist.type != 'Language')
    for gist in translation_gists:
        res['language'].append(translationgist_contents(gist))
    fields = DBSession.query(Field.translation_gist_client_id, Field.translation_gist_object_id).all()
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(fields)).filter(
        TranslationGist.type != 'Field')
    for gist in translation_gists:
        res['field'].append(translationgist_contents(gist))
    all_langs = DBSession.query(Language.client_id, Language.object_id).all()
    parents = DBSession.query(Dictionary.client_id, Dictionary.object_id, Dictionary.parent_client_id,
                              Dictionary.parent_object_id).filter(or_(
        not_(tuple_(Dictionary.parent_client_id, Dictionary.parent_object_id).in_(all_langs)),
        and_(Dictionary.parent_object_id == None, Dictionary.parent_client_id == None)
    )).all()
    res['dictionary_language'] = list()
    atoms = DBSession.query(TranslationAtom.parent_client_id, TranslationAtom.parent_object_id).filter(
        or_(and_(TranslationAtom.content.like('%оварь%'), TranslationAtom.locale_id == 1),
            and_(TranslationAtom.content.like('%ictionary%'), TranslationAtom.locale_id == 2))
        ).all()
    translation_gists = DBSession.query(TranslationGist).filter(
        tuple_(TranslationGist.client_id, TranslationGist.object_id).in_(atoms)).filter(
        TranslationGist.type == 'Language')
    for gist in translation_gists:
        res['dictionary_language'].append(translationgist_contents(gist))

    res['parents'] = parents
    """
    import collections
    res = collections.defaultdict(list)
    all_gists = []
    atoms = []
    gists =  DBSession.query(Dictionary).all()
    for gist in all_gists:
        gists.append((gist.translation_gist_client_id, gist.translation_gist_object_id))
        for atom in DBSession.query(TranslationAtom).filter(and_(
                        TranslationAtom.parent_client_id==gist.translation_gist_client_id),
                        TranslationAtom.parent_object_id==gist.translation_gist_object_id).all():
            atoms.append((atom.client_id, atom.object_id))
    for transl_gist in DBSession.query(TranslationGist).filter(and_(
                    TranslationGist.marked_for_deletion==False,
                    TranslationGist.type != "Service")  # We must be careful here
                    ).all():
        if not (transl_gist.client_id, transl_gist.object_id) in gists:
            tr_atoms = DBSession.query(TranslationAtom).filter(and_(
                TranslationAtom.parent_client_id == transl_gist.client_id,
                TranslationAtom.parent_object_id == transl_gist.object_id,
                TranslationAtom.marked_for_deletion==False)
                ).all()
            for tratom in tr_atoms:
                if not (tratom.client_id, tratom.object_id) in atoms:
                    res["(%s, %s) [%s]" % (transl_gist.client_id,
                                           transl_gist.object_id,
                                           transl_gist.type)].append( tratom.content)
                    tmp_atom = DBSession.query(TranslationAtom).filter_by(client_id=tratom.client_id,
                                                                          object_id=tratom.object_id).one()
                    tmp_atom.marked_for_deletion = True

                    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=tratom.client_id,
                                                                         object_id=tratom.object_id).one()
                    tmp_objecttoc.marked_for_deletion = True
            del_object(transl_gist)

    return res

@view_config(route_name='main', renderer='templates/main.pt', request_method='GET')
def main_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    variables = {'client_id': client_id, 'user': user}
    return render_to_response('templates/main.pt', variables, request=request)


@view_config(route_name='all_statuses', renderer='json', request_method='GET')
def all_statuses(request):
    from pyramid.request import Request
    import json

    response = list()
    for status in ['WiP', 'Published', 'Limited access', 'Hidden']:

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': status}
        headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        response.append(resp.json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_locales', renderer='json', request_method='GET')
def all_locales(request):
    response = list()
    locales = DBSession.query(Locale).all()
    for locale in locales:
        locale_json = dict()
        locale_json['shortcut'] = locale.shortcut
        locale_json['intl_name'] = locale.intl_name
        locale_json['created_at'] = locale.created_at
        locale_json['id'] = locale.id
        response.append(locale_json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_locales_desktop', renderer='json', request_method='GET')
def all_locales_desktop(request):
    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'all_locales'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    status = session.get(path)
    if status.status_code == 200:
        request.response.status = HTTPOk.code
        return status.json()
    else:
        # print(status.status_code)
        request.response.status = HTTPInternalServerError.code
        return {'error': 'no connection'}


@view_config(route_name='published_dictionaries_desktop', renderer='json', request_method='POST')
def published_dictionaries_desktop(request):
    req = request.json_body
    req['visible'] = True
    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'published_dictionaries'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)

    cookies = json.loads(request.cookies.get('server_cookies'))
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    status = session.post(path, json=req, cookies=cookies)
    if status.status_code == 200:
        request.response.status = HTTPOk.code
        return status.json()
    else:
        print(status.status_code)
        request.response.status = HTTPInternalServerError.code
        return {'error':'no connection'}


@view_config(route_name='all_perspectives_desktop', renderer='json', request_method='GET')
def all_perspectives_desktop(request):
    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'perspectives'
    published = request.params.get('published', None)
    path += '?visible=true'
    if published:
        path += '&published=true'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    cookies = json.loads(request.cookies.get('server_cookies'))
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    status = session.get(path, cookies=cookies)
    if status.status_code == 200:
        request.response.status = HTTPOk.code
        return status.json()
    else:
        print(status.status_code)
        request.response.status = HTTPInternalServerError.code
        return {'error':'no connection'}


@view_config(route_name='permissions_on_perspectives_desktop', renderer='json', request_method='GET')
def permissions_on_perspectives_desktop(request):

    settings = request.registry.settings
    path = settings['desktop']['central_server'] + 'permissions/perspectives'
    session = requests.Session()
    session.headers.update({'Connection': 'Keep-Alive'})
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=10)
    session.mount('http://', adapter)
    cookies = json.loads(request.cookies.get('server_cookies'))
    # with open('authentication_data.json', 'r') as f:
    #     cookies = json.loads(f.read())
    status = session.get(path, cookies=cookies)
    server_perms = status.json()
    path = request.route_url('permissions_on_perspectives')
    subreq = Request.blank(path)
    subreq.method = 'GET'
    subreq.headers = request.headers
    resp = request.invoke_subrequest(subreq)
    desktop_perms = resp.json

    def remove_keys(obj, rubbish):
        if isinstance(obj, dict):
            obj = {
                key: remove_keys(value, rubbish)
                for key, value in obj.items()
                if key not in rubbish and value is not None}
        elif isinstance(obj, list):
            obj = [remove_keys(item, rubbish)
                   for item in obj
                   if item not in rubbish]
        return obj

    server_perms.update(desktop_perms)
    return remove_keys(server_perms, ['publish'])



def dict_ids(obj):
    return {"client_id": obj.client_id,
            "object_id": obj.object_id}


@view_config(route_name='corpora_fields', renderer='json', request_method='GET')
def corpora_fields(request):
    response = list()
    data_type_query = DBSession.query(Field) \
        .join(TranslationGist,
              and_(Field.translation_gist_object_id == TranslationGist.object_id,
                   Field.translation_gist_client_id == TranslationGist.client_id)) \
        .join(TranslationGist.translationatom)
    sound_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                         TranslationAtom.content == 'Sound').one()  # todo: a way to find this fields if wwe cannot use one
    markup_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                          TranslationAtom.content == 'Markup').one()
    comment_field = data_type_query.filter(TranslationAtom.locale_id == 2,
                                            TranslationAtom.content == 'Comment').one()
    response.append(view_field_from_object(request=request, field=sound_field))
    response[0]['contains'] = [view_field_from_object(request=request, field=markup_field)]
    response.append(view_field_from_object(request=request, field=markup_field))
    response.append(view_field_from_object(request=request, field=comment_field))
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='all_data_types', renderer='json', request_method='GET')
def all_data_types(request):
    from pyramid.request import Request
    import json

    response = list()
    for data_type in ['Text', 'Image', 'Sound', 'Markup', 'Link', 'Grouping Tag']:

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': data_type}
        # headers = {'Cookie': request.headers['Cookie']}
        # subreq.headers = headers
        resp = request.invoke_subrequest(subreq)
        response.append(resp.json)
    request.response.status = HTTPOk.code
    return response


@view_config(route_name='create_group', renderer='json', request_method='POST', permission='logged_in')  # todo: other permission?
def create_group(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")
        if not DBSession.query(Group).filter_by(id=req['id']).first():
            group = Group(id=req['id'],
                             base_group_id=req['base_group_id'],
                             subject_client_id=req['subject_client_id'],
                             subject_object_id=req['subject_object_id'])
            DBSession.add(group)
            for user_id in req['users']:
                curr_user = DBSession.query(User).filter_by(id=user_id).first()
                if curr_user not in group.users:
                    group.users.append(curr_user)

        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

@view_config(route_name='create_persp_to_field', renderer='json', request_method='POST', permission='edit')  # todo: other permission?
def create_persp_to_field(request):
    try:
        variables = {'auth': request.authenticated_userid}

        req = request.json_body
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           variables['auth'])
        user = DBSession.query(User).filter_by(id=client.user_id).first()
        if not user:
            raise CommonException("This client id is orphaned. Try to logout and then login once more.")

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']):
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}


        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated = client.id, client_id=req['client_id']):
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}


        if not DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=req['client_id'], object_id=req['object_id']).first():
            field_object = DictionaryPerspectiveToField(client_id=client_id,
                                                        object_id=req['object_id'],
                                                        parent_client_id=req['parent_client_id'],
                                                        parent_object_id=req['parent_object_id'],
                                                        field_client_id=req['field_client_id'],
                                                        field_object_id=req['field_object_id'],
                                                        self_client_id=req['self_client_id'],
                                                        self_object_id=req['self_object_id'],
                                                        link_client_id=req.get('link_client_id'),
                                                        link_object_id=req.get('link_object_id'),
                                                        position=req['position'])
            DBSession.add(field_object)
        else:
            request.response.status = HTTPBadRequest.code
            return {'error': 'This field already exists'}

        return {}
    except KeyError as e:
        request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        request.response.status = HTTPConflict.code
        return {'error': str(e)}


#TODO: Remove it
@view_config(route_name='testing_graphene', renderer='json', request_method='POST')
def testing_graphene(request):
    published = request.params.get('published')
    if published is None:
        published = False

    request_string = """
query  perspective{  perspective(id: [630,9])
{id translation tree{id translation dataType}
fields{id translation}
lexicalEntries{id entities{id content fieldType}}
}}
    """
    request_string = request.body.decode("utf-8")
    # result = schema.execute('query  dictionary{ client dictionaries(published: %s){translation status} dictionary(id: [70,4]){id translation}}' % str(published).lower(),
    #                         context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
    #                                        'locale_id': 1,
    #                                        'request': request})
    client_id = request.authenticated_userid
    if not client_id:
        client_id = None
    #user_id =  get_user_by_client_id(authenticated_userid(request))
    # if not client_id:
    #     user_id = None
    # else:
    #     user_id = get_user_by_client_id(client_id).id
    result = schema.execute(request_string,
                           context_value={'client_id': client_id,
                       'locale_id': 2,
                       'request': request})


    # result = schema.execute(
    #     'query  perspective{  perspective(id: [70,5])'
    #     '{id translation '
    #     'lexicalEntries{id entities{id content fieldType}}'
    #     '}}',
    #     context_value={'client': get_user_by_client_id(authenticated_userid(request)).name,
    #                    'locale_id': 2,
    #                    'request': request})
    #print(result.data, result.errors, result.invalid)

    if result.invalid:
        return {'errors': [str(e) for e in result.errors]}
    if result.errors:
        return {'errors': [str(e) for e in result.errors]}
    return result.data

conn_err_msg = """\
Pyramid is having a problem using your SQL database.  The problem
might be caused by one of the following things:

1.  You may need to run the "initialize_lingvodoc_db" script
    to initialize your database tables.  Check your virtual
    environment's "bin" directory for this script and try to run it.

2.  Your database server may not be running.  Check that the
    database server referred to by the "sqlalchemy.url" setting in
    your "development.ini" file is running.

After you fix the problem, please restart the Pyramid application to
try it again.
"""