from passlib.hash import bcrypt
from lingvodoc.views.v2.utils import (
    get_user_by_client_id,
    view_field_from_object
)
from lingvodoc.utils.verification import check_client_id
import sqlalchemy.exc
from sqlalchemy.exc import IntegrityError
import psycopg2.errors

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
    Entity,
    Passhash,
    Grant,
    Organization
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
from pyramid.security import authenticated_userid, forget
# from pyramid.chameleon_zpt import render_template_to_response
from pyramid.renderers import render_to_response
from lingvodoc.exceptions import CommonException

import sys
import multiprocessing

import logging
import urllib
import json
import requests
from pyramid.request import Request
import time
from webob.multidict import MultiDict, NoVars
from lingvodoc.schema.query import schema, Context

from copy import deepcopy

if sys.platform == 'darwin':
    multiprocessing.set_start_method('spawn')
import os
from lingvodoc.utils.creation import translationgist_contents, add_user_to_group
from hashlib import sha224
from base64 import urlsafe_b64decode
from sqlalchemy.orm.attributes import flag_modified
from lingvodoc.utils.proxy import ProxyPass
from lingvodoc.utils.elan_functions import eaf_wordlist
import datetime

log = logging.getLogger(__name__)


#
# def version_decorator(pyramid_dec):
#     def inner(**kwargs):
#         kwargs2 = deepcopy(kwargs)
#         kwargs2['route_name'] = 'v2/' + kwargs2['route_name']
#         # pyramid_dec(**kwargs2)  # - just calling view_config don't register the view, it should be in return
#         return pyramid_dec(**kwargs2)(pyramid_dec)(**kwargs)
#         # return pyramid_dec(**kwargs)
#
#     return inner
#
#
# # def version_decorator(func):
# #     def inner(**kwargs):
# #         kwargs['route_name'] = 'v2/' + kwargs['route_name']
# #         return func(**kwargs)
# #     return inner
#
#
# @version_decorator
# def view_config(**kwargs):
#     return pyramid_view_config(**kwargs)
#
#
# def testing_add_view(request):
#     return {'answer': 'v2'}
#
#
# # @view_config(route_name='v2/testing_decorator', renderer='json')
# @view_config(route_name='testing_decorator', renderer='json')
# def testing_decorator(request):
#     return {'42': 'v2'}
#
#
# view_config = pyramid_view_config
#
# @view_config(route_name='testing_scan', renderer='json')
# @view_config(route_name='v2/testing_scan', renderer='json')
# def testing_scan(request):
#     return {"version": 2}

def save_persp_media(persp, sound, markup, storage):
    entities = DBSession.query(Entity).join(LexicalEntry).filter(
        LexicalEntry.parent == persp).filter(or_(Entity.field == sound, Entity.field == markup))
    count = entities.count()
    entities = entities.all()

    for entity in entities:
        url = entity.content
        filename = url.split('/')
        filename = filename[len(filename) - 1]
        fullfilename = storage + filename
        while os.path.exists(fullfilename):
            filename = 'double_' + filename
            fullfilename = storage + filename
        with open(fullfilename, 'wb') as temp_file:
            sound_file = urllib.request.urlopen(urllib.parse.quote(url, safe='/:'))
            temp_file.write(sound_file.read())
    return {storage: count}


@view_config(route_name='save_media', renderer='json', permission='admin')
def save_media(request):
    lex_sound = DBSession.query(Field).filter_by(client_id=66, object_id=12).one()
    lex_markup = DBSession.query(Field).filter_by(client_id=66, object_id=23).one()
    par_sound = DBSession.query(Field).filter_by(client_id=66, object_id=21).one()
    par_markup = DBSession.query(Field).filter_by(client_id=66, object_id=27).one()

    lex_persps = [(671, 13), (671, 2389), (671, 4770), (671, 7177), (671, 12797), (671, 14224), (742, 5), (748, 1799),
                  (671, 10419), (671, 15155)]
    lex_persps = DBSession.query(DictionaryPerspective).filter(
        tuple_(DictionaryPerspective.client_id, DictionaryPerspective.object_id).in_(lex_persps))
    par_persps = [(671, 14), (671, 2390), (671, 4771), (671, 7178), (671, 14225), (742, 6), (748, 1802), (671, 1042),
                  (748, 553)]
    par_persps = DBSession.query(DictionaryPerspective).filter(
        tuple_(DictionaryPerspective.client_id, DictionaryPerspective.object_id).in_(par_persps))
    storage_path = 'saved_media\\'
    if not os.path.exists('saved_media'):
        os.mkdir('saved_media')
    res = dict()
    for persp in lex_persps:
        storage = storage_path + persp.parent.get_translation(2)
        if not os.path.exists(storage):
            os.mkdir(storage)
        storage += '\\' + persp.get_translation(2)
        if not os.path.exists(storage):
            os.mkdir(storage)
        storage += '\\'
        count = save_persp_media(persp, lex_sound, lex_markup, storage)
        res.update(count)
    for persp in par_persps:
        storage = storage_path + persp.parent.get_translation(2)
        if not os.path.exists(storage):
            os.mkdir(storage)
        storage += '\\' + persp.get_translation(2)
        if not os.path.exists(storage):
            os.mkdir(storage)
        storage += '\\'
        count = save_persp_media(persp, par_sound, par_markup, storage)
        res.update(count)
    return res


@view_config(route_name='remove_dicts_from_grants', renderer='json', permission='admin')
def remove_dicts_from_grants(request):
    ids = request.json
    for dict_id in ids:
        for grant in DBSession.query(Grant).all():
            if grant.additional_metadata and grant.additional_metadata['participant'] and dict_id in \
                    grant.additional_metadata['participant']:
                grant.additional_metadata['participant'].remove(dict_id)
                flag_modified(grant, 'additional_metadata')


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
                                              subject_override=True).all()
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
    translationatom = DBSession.query(TranslationAtom) \
        .join(TranslationGist). \
        filter(TranslationAtom.content == searchstring,
               TranslationAtom.locale_id == 2,
               TranslationGist.type == 'Service') \
        .order_by(TranslationAtom.client_id) \
        .first()
    response = translationgist_contents(translationatom.parent)
    return response


def add_role(name, subject, action, admin, perspective_default=False, dictionary_default=False):
    base_group = BaseGroup(name=name,
                           subject=subject,
                           action=action,
                           perspective_default=perspective_default,
                           dictionary_default=dictionary_default)
    DBSession.add(base_group)
    DBSession.flush()
    group = Group(base_group_id=base_group.id, subject_override=True)
    DBSession.add(group)
    group.users.append(admin)
    DBSession.flush()
    return base_group


from lingvodoc.utils.creation import update_metadata
from lingvodoc.models import PublishingEntity
from lingvodoc.models import UserRequest as dbUserRequest
from lingvodoc.utils.search import translation_gist_search
import transaction

import random
import string
from lingvodoc.utils.search import get_id_to_field_dict
import itertools
from time import ctime
import operator
from lingvodoc.schema.gql_holders import delete_message, del_object
from lingvodoc.utils.creation import update_metadata
from uuid import uuid4

@view_config(route_name='testing', renderer='json', permission='admin')
def testing(request):
    # Hello, testing, my old friend
    # I've come to use you once again

    # convert old metadata to jsonb format
    # type1: Manually deleted
    # type2: Manually deleted. object with this translationgist: [1834,61]
    # type3: Manually deleted. gist: [1834,59]
    # convert to
    # jsonb

    try:
        with transaction.manager:
            for objecttoc in DBSession.query(ObjectTOC).filter(ObjectTOC.additional_metadata != None).all():
                meta = objecttoc.additional_metadata
                #print(meta)
                new_meta=None
                if meta == "Manually deleted":  # type 1
                    new_meta=delete_message("del_object", None)
                    objecttoc.additional_metadata = new_meta
                    flag_modified(objecttoc, 'additional_metadata')
                elif "object with this" in meta: # type 2
                    obj_str = meta.split("[")[1].split("]")[0].split(",")
                    obj_id=(int(obj_str[0]), int(gist_str[1]))
                    new_meta=delete_message("del_object", None, subject=obj_id)
                    objecttoc.additional_metadata = new_meta
                    flag_modified(objecttoc, 'additional_metadata')
                    objecttoc.additional_metadata = new_meta
                    flag_modified(objecttoc, 'additional_metadata')
                elif "Manually deleted. gist: [" in meta: # type 3
                    gist_str = meta.split("[")[1].split("]")[0].split(",")
                    gist_id=(int(gist_str[0]), int(gist_str[1]))
                    new_meta=delete_message("del_object", None, subject=gist_id)
                    objecttoc.additional_metadata = new_meta
                    flag_modified(objecttoc, 'additional_metadata')
                elif "garbage_collector" in str(meta): # skip
                    pass
                else:
                    print(meta)

            # Restore Mark`s deletions
            #
            # NOTE: after changing all created_at to proper UTC-based Unix timestamps (previously they were
            # shifted by UTC - MSK difference) following time constants can be no longer right.

            entities_to_delete = set()
            i = 0
            j = 0
            for persp_id in ((1501,62090), (1501,62853), (2451,245)):
                restore_time = 1569283200  # 24.09
                if persp_id[1] == 62853:
                    restore_time = 1571961600  # 25.10
                if persp_id[1] == 62090:
                    restore_time = 1569283200  # 24.09
                perspective = DBSession.query(DictionaryPerspective).filter_by(client_id=persp_id[0],
                                                                               object_id=persp_id[1]).first()
                lexical_entries = DBSession.query(LexicalEntry).filter(LexicalEntry.parent==perspective).all()
                #le_to_delete = set()
                for le in lexical_entries:
                    entities = DBSession.query(Entity).filter(Entity.parent==le).all()
                    if le.marked_for_deletion:
                        le.marked_for_deletion = False
                        le_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=le.client_id,
                                                                         object_id=le.object_id).one()
                        le_objecttoc.marked_for_deletion = False
                        i+=1

                    import collections
                    sort = collections.defaultdict(dict)
                    for e in entities:
                        sort[e.field_object_id][e.created_at] = e

                    filtered_list = set()
                    for e in sort:
                        maxtime = max(sort[e].keys())
                        filtered_list.add(sort[e][maxtime])


                    for entity in entities:
                        if entity.created_at > restore_time:
                            entities_to_delete.add(entity)
                        # restore
                        if entity.marked_for_deletion and entity in filtered_list:
                            if not "*" in entity.content and len(entity.content) > 0:
                                entity.marked_for_deletion = False
                                objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=entity.client_id,
                                                                                 object_id=entity.object_id).one()
                                objecttoc.marked_for_deletion = False
                                j+=1


            ent_count = len(entities_to_delete)
            task_id = str(uuid4())
            # deletion
            for entity in entities_to_delete:
                print("delete: ", entity.content)
                del_object(entity, "del_object", 1, counter=ent_count, task_id=task_id)  # count

            return "%s entities deleted, %s le undeleted, %s ent undelted" % (ent_count, i, j)
    except Exception as err:
        print(str(err))
        return str(err)


    # class ObjectId:
    #
    #     object_id_counter = 0
    #
    #     @property
    #     def next(self):
    #         self.object_id_counter += 1
    #         return self.object_id_counter
    #
    # def get_child_languages(parent_languages):
    #     """
    #     Returns child_langs set
    #
    #     (Uralic) -> set([UralicObject])
    #     |       \
    #     |        \
    #     (lang_1, lang_2)  -> set([lang_1, lang_2])
    #
    #     """
    #     child_langs = set()
    #     for parent_language in parent_languages:
    #         for lng_obj in DBSession.query(Language).filter_by(parent=parent_language, marked_for_deletion=False):
    #             child_langs.add(lng_obj)
    #     return child_langs
    #
    # def get_all_persp_by_lang(lng_obj):
    #     dictionaries = DBSession.query(Dictionary).filter_by(parent=lng_obj, marked_for_deletion=False).all()
    #     perspectives = set()
    #     for dictionary in dictionaries:
    #         perspectives.update(set(
    #             DBSession.query(DictionaryPerspective).filter_by(parent=dictionary, marked_for_deletion=False).all()))
    #     return perspectives
    #
    # def get_child_lang_list(parent_uralic_lang_id):
    #     parent_uralic_obj = DBSession.query(Language).filter_by(client_id=parent_uralic_lang_id[0],
    #                                                             object_id=parent_uralic_lang_id[1]).first()
    #     parent_lang = parent_uralic_obj
    #     all_languages = set([parent_uralic_obj])
    #     next_siblings = set([parent_uralic_obj])
    #
    #     while next_siblings:
    #         next_siblings = get_child_languages(next_siblings)
    #         all_languages.update(next_siblings)
    #     return all_languages
    #
    # def get_persps_by_field(proto_form_id):
    #     persp_list = set()
    #     for persp_obj in all_persps:
    #         for ptofield in DBSession.query(DictionaryPerspectiveToField).filter_by(parent=persp_obj).all():
    #             if ptofield.field_client_id == proto_form_id[0] and ptofield.field_object_id == proto_form_id[1]:
    #                 persp_list.add(ptofield.parent)
    #     return persp_list
    #
    # def comparator_func(x):
    #     perspective, lexical_entry, entity = x
    #     return entity.content
    #     # return entity.content[:5]
    #
    # def set_tag_for_group(key, group, etymology_field_id, operation_tag):
    #     group_list = list(group)
    #     match_list = []
    #     # 1) count each
    #
    #     for perspective, lexical_entry, entity in group_list:
    #         meaning_entity = DBSession.query(Entity).filter_by(parent_client_id=lexical_entry.client_id,
    #                                                            parent_object_id=lexical_entry.object_id,
    #                                                            field_client_id=66,
    #                                                            field_object_id=10,
    #                                                            marked_for_deletion=False).first()
    #         if meaning_entity:
    #             meaning_entity.content
    #             match_list.append(entity.content)
    #     match_set = set(match_list)
    #
    #     stat_list = []
    #     for word in match_set:
    #         stat_list.append((match_list.count(word), word))
    #
    #     connect_meaning_connect_text = None
    #     stat_list.sort(key=operator.itemgetter(0))
    #
    #     connect_meaning = None
    #     if stat_list:
    #         connect_meaning = stat_list[0]
    #
    #     if connect_meaning:
    #         match_n, text = connect_meaning[0], connect_meaning[1]
    #         if match_n >= 2:
    #             connect_meaning_connect_text = text
    #
    #     for perspective, lexical_entry, entity in group_list:
    #         if entity.content != connect_meaning_connect_text:
    #             continue
    #         tag = "%s_%s" % (key, operation_tag)
    #         tag_entity = Entity(client_id=client_id, object_id=obj_id.next,
    #                             field_client_id=etymology_field_id[0], field_object_id=etymology_field_id[1],
    #                             parent_client_id=lexical_entry.client_id, parent_object_id=lexical_entry.object_id,
    #                             content=tag)
    #         tag_entity.publishingentity.accepted = True
    #         tag_entity.publishingentity.published = True  ##
    #         DBSession.add(tag_entity)
    #         DBSession.flush()
    #
    # def set_tag_for_child_group(key, group, etymology_field_id, operation_tag, parent_persp):
    #     group_list = list(group)
    #     if not parent_persp in [(x[0].client_id, x[0].object_id) for x in group_list]:
    #         return
    #     for perspective, lexical_entry, entity in group_list:
    #         tag = "%s_%s" % (key, operation_tag)
    #         tag_entity = Entity(client_id=client_id, object_id=obj_id.next,
    #                             field_client_id=etymology_field_id[0], field_object_id=etymology_field_id[1],
    #                             parent_client_id=lexical_entry.client_id, parent_object_id=lexical_entry.object_id,
    #                             content=tag)
    #         tag_entity.publishingentity.accepted = True
    #         tag_entity.publishingentity.published = True  ##
    #         c2 += 1
    #         DBSession.add(tag_entity)
    #         DBSession.flush()
    #
    # def get_entity_list_query(persps_with_field, filter_field_id):
    #     word_entity_queries = list()
    #     for persp in persps_with_field:
    #         lexes = DBSession.query(DictionaryPerspective, LexicalEntry, Entity) \
    #             .filter(and_(DictionaryPerspective.object_id == persp.object_id,
    #                          DictionaryPerspective.client_id == persp.client_id,
    #                          DictionaryPerspective.marked_for_deletion == False)) \
    #             .join(LexicalEntry, and_(LexicalEntry.parent_object_id == DictionaryPerspective.object_id,
    #                                      LexicalEntry.parent_client_id == DictionaryPerspective.client_id,
    #                                      LexicalEntry.marked_for_deletion == False)) \
    #             .join(Entity, and_(LexicalEntry.object_id == Entity.parent_object_id,
    #                                LexicalEntry.client_id == Entity.parent_client_id,
    #                                tuple_(Entity.field_client_id, Entity.field_object_id).in_([(filter_field_id)]),
    #                                Entity.content != "",
    #                                Entity.content != " ",
    #                                Entity.marked_for_deletion == False,
    #                                )
    #                   ).join(Entity.publishingentity).filter(PublishingEntity.accepted == True)
    #         # lexes = [x for x in lexes.all() if x[2].publishingentity.accepted != False]
    #         word_entity_queries.append(lexes)
    #     return word_entity_queries
    #
    # def is_leaf(lng):
    #     if not DBSession.query(Language).filter(and_(Language.language == None,
    #                                                  Language.client_id == lng.client_id,
    #                                                  Language.object_id == lng.object_id)).first():
    #         return False
    #     return True
    #
    # def gist_search_lng(searchstring):
    #     translationatom = DBSession.query(TranslationAtom) \
    #         .join(TranslationGist). \
    #         filter(TranslationAtom.content == searchstring,
    #                TranslationAtom.locale_id == 2,
    #                TranslationGist.type == 'Language') \
    #         .first()
    #     if translationatom and translationatom.parent:
    #         translationgist = translationatom.parent
    #         return translationgist
    #
    # try:
    #     with transaction.manager:
    #         # print = logging.warning
    #         c = 0
    #         c2 = 0
    #         old_client_id = 1
    #         old_client = DBSession.query(Client).filter_by(id=old_client_id).first()
    #         user = DBSession.query(User).filter_by(id=old_client.user_id).first()
    #         client = Client(user_id=1)
    #         user.clients.append(client)
    #         DBSession.add(client)
    #         DBSession.flush()
    #         client_id = client.id
    #         obj_id = ObjectId()
    #
    #         lang_list = ["Chuvash", "Yakut", "Dolgan", "Khakas", "Chulym", "Karachay-Balkar", "Kumyk", "Bashkir",
    #                      "Tatar", "Kazakh", "Altay", "Chalkan", "Altai-Kizhi", "Telengit", "Modern Uyghur", "Uzbek",
    #                      "Crimean Tatar", "Azerbaijan", "Tofa", "Tuvan", "Shor", "Nogay", "Azerbaijan"]
    #         all_languages = list()
    #         for l in lang_list:
    #             if l == "Chuvash":
    #                 obj = DBSession.query(Language).filter_by(client_id=1574, object_id=272283).first()
    #             elif l == "Yakut":
    #                 obj = DBSession.query(Language).filter_by(client_id=678, object_id=9).first()
    #             elif l == "Tofa":
    #                 obj = DBSession.query(Language).filter_by(client_id=1574, object_id=116718).first()
    #             else:
    #                 tr_gist = gist_search_lng(l)
    #                 obj = DBSession.query(Language).filter_by(translation_gist_client_id=tr_gist.client_id,
    #                                                           translation_gist_object_id=tr_gist.object_id,
    #                                                           marked_for_deletion=False).first()
    #             all_languages.append(obj)
    #             print(l, obj)
    #         if len(all_languages) != len(lang_list):
    #             return "Translation gist not found"
    #         restrict_keys = ["заим.", "заим. русс.", "заим. русс. ", "заим. перс."]
    #
    #         # return
    #         ########
    #         ########
    #
    #         for next_lang in all_languages:
    #             all_persps = set()
    #             print("Language: ", (next_lang.client_id, next_lang.object_id))
    #             persps = get_all_persp_by_lang(next_lang)
    #             all_persps.update(persps)
    #             # all_persps
    #             field_ids = get_id_to_field_dict()
    #             etymology_field_id = field_ids.get("Etymology")
    #             # proto_form_id = (742, 4309)
    #             word_field_id = field_ids.get("Word")
    #             meaning_field_id = (66, 10)
    #
    #             # getting perspectives with "Word" field
    #             persps_with_word = get_persps_by_field(word_field_id)
    #             operation_tag = str(client_id) + ctime() + "_" + ''.join(
    #                 random.SystemRandom().choice(string.ascii_uppercase + string.digits)
    #                 for c in range(10))
    #
    #             word_entities = get_entity_list_query(persps_with_word, word_field_id)
    #             words = itertools.chain.from_iterable(word_entities)
    #             sorted_words = sorted(words, key=comparator_func)
    #             for key, group in itertools.groupby(sorted_words, key=comparator_func):
    #                 if key in restrict_keys or "заим." in key:
    #                     continue
    #                 d = list(group)
    #                 if len(d) > 1:
    #                     c += 1
    #                     set_tag_for_group(key, d, etymology_field_id, operation_tag)
    #                     # print
    #                     print("==========")
    #                     print(key)
    #                     for x in d:
    #                         print("(%s)\n[ http://83.149.198.133/dictionary/%s/%s/perspective/%s/%s/view ]" % (
    #                             x[2].content, x[0].parent_client_id, x[0].parent_object_id, x[0].client_id,
    #                             x[0].object_id))
    #             DBSession.flush()
    #             print(4)
    #         return c, c2
    # except Exception as err:
    #     print(str(err))
    #     return str(err)


@view_config(route_name='garbage_collector', renderer='json', permission='admin')
def garbage_collector(request):
    """
    This route uses global utils module for all the kinds of garbage detection
    :param request:
    :return:
    """
    from lingvodoc.utils import garbage_collector
    collection_time = datetime.datetime.now(datetime.timezone.utc).timestamp()
    null_entities = garbage_collector.get_null_entities()
    empty_entities = garbage_collector.get_empty_entities()
    entities_deleted = 0
    for entity in null_entities:
        entity.mark_deleted(garbage_collector.gc_message(collection_time,
                                                         "Entity with null content (not link)",
                                                         entity))
        entities_deleted += 1
    for entity in empty_entities:
        entity.mark_deleted(garbage_collector.gc_message(collection_time,
                                                         "Entity with empty string content",
                                                         entity))
        entities_deleted += 1

    empty_dictionaries, no_content_dictionaries, useful_dictionaries = garbage_collector.get_useless_dictionaries()
    dicts_deleted = 0
    perps_deleted = 0
    gists_deleted = 0
    for dictionary in empty_dictionaries:
        dictionary_gist = DBSession.query(TranslationGist).filter(
            and_(TranslationGist.client_id == dictionary.translation_gist_client_id,
                 TranslationGist.object_id == dictionary.translation_gist_object_id)).one()

        dictionary_gist.mark_deleted(garbage_collector.gc_message(collection_time,
                                                                  "Gist for dictionary with no perspectives",
                                                                  dictionary))
        dictionary.mark_deleted(garbage_collector.gc_message(collection_time,
                                                             "Dictionary with no perspectives",
                                                             dictionary))
        gists_deleted += 1
        dicts_deleted += 1

    for dictionary in no_content_dictionaries:
        dictionary_gist = DBSession.query(TranslationGist). \
            filter(and_(TranslationGist.client_id == dictionary.translation_gist_client_id,
                        TranslationGist.object_id == dictionary.translation_gist_object_id)).one()
        dictionary_gist.mark_deleted(garbage_collector.gc_message(collection_time,
                                                                  "Gist for dictionary with no content",
                                                                  dictionary))
        dictionary.mark_deleted(garbage_collector.gc_message(collection_time,
                                                             "Dictionary with no content",
                                                             dictionary))
        gists_deleted += 1
        dicts_deleted += 1

        for perspective in dictionary.dictionaryperspective:
            perspective_gist = DBSession.query(TranslationGist). \
                filter(and_(TranslationGist.client_id == perspective.translation_gist_client_id,
                            TranslationGist.object_id == perspective.translation_gist_object_id)).one()
            perspective_gist.mark_deleted(garbage_collector.gc_message(collection_time,
                                                                       "Gist for perspective from dictionary with no content",
                                                                       perspective))
            perspective.mark_deleted(garbage_collector.gc_message(collection_time,
                                                                  "Perspective from dictionary with no content",
                                                                  dictionary))
            perps_deleted += 1
            gists_deleted += 1

    return {"entities_deleted": entities_deleted,
            "dictionaries_deleted": dicts_deleted,
            "perspectives_deleted": perps_deleted,
            "gists_deleted": gists_deleted}


def recursive_sort(langs, visited, stack, result):
    for lang in langs:
        parent = (lang.parent_client_id, lang.parent_object_id)
        if parent == (None, None):
            parent = None
        previous = None
        siblings = None
        if 'younger_siblings' in lang.additional_metadata:
            siblings = lang.additional_metadata['younger_siblings']
        if siblings:
            previous = siblings[len(siblings) - 1]
            previous = tuple(previous)
        ids = (lang.client_id, lang.object_id)
        if (not parent or parent in visited) and (not previous or previous in visited) and ids not in visited:
            level = 0
            if previous:
                subres = [(res[1], res[2]) for res in result]
                index = subres.index(previous)
                level = result[index][0]
                limit = len(result)
                while index < limit:
                    if result[index][0] < level:
                        index = index - 1
                        break
                    index += 1

                result.insert(index + 1, [level, lang.client_id, lang.object_id,
                                          "__".join(["__" for i in range(level)]) + lang.get_translation(2)])

            elif parent and previous is None:
                subres = [(res[1], res[2]) for res in result]
                index = subres.index(parent)
                level = result[index][0] + 1
                result.insert(index + 1, [level, lang.client_id, lang.object_id,
                                          "__".join(["__" for i in range(level)]) + lang.get_translation(2)])
            else:
                result.append([level, lang.client_id, lang.object_id,
                               "__".join(["__" for i in range(level)]) + lang.get_translation(2)])

            visited.add(ids)

            if lang in stack:
                stack.remove(lang)

            recursive_sort(list(stack), visited, stack, result)
        else:
            stack.add(lang)
    return


@view_config(route_name='testing_langs', renderer='json', permission='admin')
def testing_langs(request):
    langs = DBSession.query(Language).filter_by(marked_for_deletion=False).order_by(Language.parent_client_id,
                                                                                    Language.parent_object_id,
                                                                                    Language.additional_metadata[
                                                                                        'younger_siblings']).all()
    visited = set()
    stack = set()
    result = list()
    recursive_sort(langs, visited, stack, result)
    return result


@view_config(route_name='main', renderer='templates/main.pt', request_method='GET')
def main_get(request):
    client_id = authenticated_userid(request)
    user = get_user_by_client_id(client_id)
    variables = {'client_id': client_id, 'user': user}
    return render_to_response('templates/main.pt', variables, request=request)


@view_config(route_name='new_interface', renderer='templates/new_interface.pt', request_method='GET')
def new_interface(request):
    """
    Temporary view for the new React-based interface.
    """

    # Patterned after the 'main' view, see function 'main_get' in lingvodoc.views.v2.

    return render_to_response('templates/new_interface.pt', {}, request=request)


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


# @view_config(route_name='all_dictionary_roles', renderer='json', request_method='GET')
# def all_dictionary_roles(request):
#     bases = DBSession.query(BaseGroup).filter_by(dictionary_default = True).all()
#     response = list()
#     for base in bases:
#         response.append({"name": base.name, "subject": base.subject, "action": base.action})
#     request.response.status = HTTPOk.code
#     return response
#
# @view_config(route_name='all_perspective_roles', renderer='json', request_method='GET')
# def all_dictionary_roles(request):
#     from pyramid.request import Request
#     import json
#
#     response = list()
#     for status in ['WiP', 'Published', 'Limited access', 'Hidden']:
#         subreq = Request.blank('/translation_service_search')
#         subreq.method = 'POST'
#         subreq.headers = request.headers
#         subreq.json = {'searchstring': status}
#         headers = {'Cookie': request.headers['Cookie']}
#         subreq.headers = headers
#         resp = request.invoke_subrequest(subreq)
#         response.append(resp.json)
#     request.response.status = HTTPOk.code
#     return response


@view_config(route_name='home_page_text', renderer='string', request_method='GET')
def home_page_text(request):
    path = 'home_page_text.html'
    if not os.path.exists(path):
        request.override_renderer = 'json'
        return {'error': 'no text file'}
    with open(path, 'r') as text_file:
        text = text_file.read()
        return text


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
        return {'error': 'no connection'}


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
        return {'error': 'no connection'}


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


@view_config(route_name='create_group', renderer='json', request_method='POST',
             permission='logged_in')  # todo: other permission?
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


@view_config(route_name='create_persp_to_field', renderer='json', request_method='POST',
             permission='edit')  # todo: other permission?
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
            if check_client_id(authenticated=client.id, client_id=req['client_id']) or user.id == 1:
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}

        client_id = variables['auth']
        if 'client_id' in req:
            if check_client_id(authenticated=client.id, client_id=req['client_id']) or user.id == 1:
                client_id = req['client_id']
            else:
                request.response.status_code = HTTPBadRequest
                return {'error': 'client_id from another user'}

        if not DBSession.query(DictionaryPerspectiveToField).filter_by(client_id=req['client_id'],
                                                                       object_id=req['object_id']).first():
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


@view_config(route_name='change_user_password', renderer="json", request_method='POST', permission='admin')
def change_user_password(request):
    login = request.matchdict.get('login')
    req = request.json_body
    user = DBSession.query(User).filter_by(login=login).first()
    if not user:
        raise CommonException("This login is orphaned")
    new_password = req.get('password')
    if not new_password:
        request.response.status = HTTPBadRequest.code
        return {'error': str("Need new password to confirm")}
    old_hash = DBSession.query(Passhash).filter_by(user_id=user.id).first()
    old_hash.hash = bcrypt.encrypt(new_password)
    request.response.status = HTTPOk.code
    return {"success": True}

# TODO: Remove it
@view_config(route_name='graphql', renderer='json')
def graphql(request):
    """
    #####################
    ### application/json
    #####################

    {"variables": {}, "query": "query perspective{ perspective(id: [630,9]) {id translation tree{id} fields{id} }}"}

    or a batch of queries:

    [
        {"variables": {}, "query": "query perspective{ perspective(id: [630,9]) {id translation tree{id} fields{id} }}"},
        {"variables": {}, "query": "query myQuery{ entity(id:[ 742, 5494, ] ) { id}}"}
    ]

    #####################
    ### application/graphql
    #####################

    query perspective{ perspective(id: [630,9]) {id translation tree{id} fields{id} }}"

    #####################
    ### application/multipart/form-data
    #####################

    MultiDict([
    ('graphql', "mutation create_entity..."),
     ('blob', FieldStorage('blob', 'PA_1313_lapetkatpuwel (1).wav')),
     ('blob', FieldStorage('blob', 'PA_1313_lapetkatpuwel (1).wav')),
     ])

    """
    # TODO: rewrite this footwrap
    sp = request.tm.savepoint()
    try:
        batch = False
        variable_values = {}
        variables = {'auth': request.authenticated_userid}
        client_id = variables["auth"]
        results = list()

        if not client_id:
            client_id = None

        locale_id = int(request.cookies.get('locale_id') or 2)

        if request.content_type in ['application/x-www-form-urlencoded', 'multipart/form-data'] \
                and type(request.POST) == MultiDict:
            data = request.POST

            if not data:
                return {'errors': [{"message": 'empty request'}]}
            elif not "operations" in data:
                return {'errors': [{"message": 'operations key not found'}]}
            elif not "query" in data["operations"]:
                return {'errors': [{"message": 'query key not found in operations'}]}
            elif not "1" in data:
                return {'errors': [{"message": '1 key not found'}]}

            request_string = request.POST.pop("operations")
            request_string = request_string.rstrip()
            # body = request_string.decode('utf-8')
            json_req = json.loads(request_string)
            if "query" not in json_req:
                return {'errors': [{"message": 'query key not found'}]}
            request_string = json_req["query"]
            request_string = request_string.rstrip()
            if "variables" in json_req:
                variable_values = json_req["variables"]

            '''
            if data and "file" in data and "graphene" in data:
                # We can get next file from the list inside file upload mutation resolve
                # use request.POST.popitem()
                request_string = request.POST.popitem()  # data["graphene"]
                # todo: file usage
                # files = data.getall("file")
            else:
                request.response.status = HTTPBadRequest.code
                return {'errors': [{"message": 'wrong data'}]}

            '''
        elif request.content_type == "application/graphql" and type(request.POST) == NoVars:
            request_string = request.body.decode("utf-8")
        elif request.content_type == "application/json" and type(request.POST) == NoVars:
            body = request.body.decode('utf-8')
            json_req = json.loads(body)
            if type(json_req) is list:
                batch = True
            if not batch:
                if "query" not in json_req:
                    return {'errors': [{"message": 'query key not found'}]}
                request_string = json_req["query"]
                if "variables" in json_req:
                    variable_values = json_req["variables"]
            else:
                for query in json_req:
                    if "query" not in query:
                        return {'errors': [{"message": 'query key not found'}]}
                    request_string = query["query"]
                    if "variables" in query:
                        variable_values = query["variables"]
                    result = schema.execute(request_string,
                                            context_value=Context({
                                                'client_id': client_id,
                                                'locale_id': locale_id,
                                                'request': request,
                                                'headers': request.headers,
                                                'cookies': dict(request.cookies)}),
                                            variable_values=variable_values)
                    if result.invalid:
                        return {'errors': [{"message": str(e)} for e in result.errors]}
                    if result.errors:
                        sp.rollback()
                        return {"data": None, 'errors': [{"message": str(e)} for e in result.errors]}
                    results.append(result.data)
                # TODO: check errors
                return {"data": results}
        else:
            request.response.status = HTTPBadRequest.code
            return {'errors': [{"message": 'wrong content type'}]}
        if not batch:
            t_start_real, t_start_process = (time.time(), time.process_time())
            result = schema.execute(request_string,
                                    context_value=Context({
                                        'client_id': client_id,
                                        'locale_id': locale_id,
                                        'request': request}),
                                    variable_values=variable_values)
            t_end_real, t_end_process = (time.time(), time.process_time())
            t_elapsed_real = t_end_real - t_start_real
            t_elapsed_process = t_end_process - t_start_process
            log.debug(
                '\nschema.execute() elapsed time real, process: '
                f'{t_elapsed_real:.6f}s, {t_elapsed_process:.6f}s')
            request.response.headerlist.append((
                'Server-Timing',
                f'real;dur={t_elapsed_real:.6f}, process;dur={t_elapsed_process:.6f}'))

            if result.errors:
                for error in result.errors:
                    if hasattr(error, 'original_error'):
                        if type(error.original_error) == ProxyPass:
                            return json.loads(error.original_error.response_body.decode("utf-8"))

            if result.invalid:

                return {
                    'errors': [{'message': str(e)} for e in result.errors],
                    'time_real': t_elapsed_real,
                    'time_process': t_elapsed_process}

            if result.errors:

                # If we had an attempt to proceed with failed transaction because of another error, we don't
                # need its superfluous error info.

                if len(result.errors) > 1:

                    errors = [

                        error
                        for error in result.errors

                        if (not isinstance(
                                error.original_error,
                                sqlalchemy.exc.InternalError) or

                            not isinstance(
                                error.original_error.orig,
                                psycopg2.errors.InFailedSqlTransaction))]

                else:

                    errors = result.errors

                return {
                    'data': None,
                    'errors': [{'message': str(e)} for e in errors],
                    'time_real': t_elapsed_real,
                    'time_process': t_elapsed_process}

            return {
                'data': result.data,
                'time_real': t_elapsed_real,
                'time_process': t_elapsed_process}

    except ProxyPass as e:
        return e.response_body

    except KeyError as e:
        # request.response.status = HTTPBadRequest.code
        return {'error': str(e)}

    except IntegrityError as e:
        # request.response.status = HTTPInternalServerError.code
        return {'error': str(e)}

    except CommonException as e:
        # request.response.status = HTTPConflict.code
        return {'error': str(e)}
    except ValueError as e:
        # request.response.status = HTTPConflict.code
        return {'error': str(e)}


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
