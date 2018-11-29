import collections
import copy
import ctypes
import datetime
import gzip
import hashlib
import io
import itertools
import logging
import math
import os.path
import pprint
import shutil
import textwrap
import time
import traceback
import urllib.parse

import graphene
from lingvodoc.utils.elan_functions import tgt_to_eaf
import requests
from lingvodoc.schema.gql_entity import (
    Entity,
    CreateEntity,
    UpdateEntity,
    DeleteEntity,
    UpdateEntityContent,
    BulkCreateEntity,
    ApproveAllForUser)
from lingvodoc.schema.gql_column import (
    Column,
    CreateColumn,
    UpdateColumn,
    DeleteColumn
)
from lingvodoc.schema.gql_basegroup import (
    BaseGroup,
)
from lingvodoc.schema.gql_group import (
    Group
)
from lingvodoc.schema.gql_organization import (
    Organization,
    CreateOrganization,
    UpdateOrganization,
    #DeleteOrganization
)
# from lingvodoc.schema.gql_publishingentity import (
#     PublishingEntity
# )
from lingvodoc.schema.gql_translationatom import (
    TranslationAtom,
    CreateTranslationAtom,
    UpdateTranslationAtom,
    DeleteTranslationAtom)
from lingvodoc.schema.gql_translationgist import (
    TranslationGist,
    CreateTranslationGist,
    DeleteTranslationGist
)
from lingvodoc.schema.gql_userblobs import (
    UserBlobs,
    CreateUserBlob,
    DeleteUserBlob
)
from lingvodoc.schema.gql_field import (
    Field,
    CreateField,
    # UpdateField,
    # DeleteField
)

from lingvodoc.schema.gql_dictionary import (
    Dictionary,
    CreateDictionary,
    UpdateDictionary,
    UpdateDictionaryStatus,
    AddDictionaryRoles,
    DeleteDictionaryRoles,
    DeleteDictionary,
    UpdateDictionaryAtom)

from lingvodoc.schema.gql_search import AdvancedSearch
from lingvodoc.schema.gql_search import AdvancedSearchSimple

from lingvodoc.schema.gql_lexicalentry import (
    LexicalEntry,
    CreateLexicalEntry,
    DeleteLexicalEntry,
    BulkDeleteLexicalEntry,
    BulkCreateLexicalEntry,
    ConnectLexicalEntries,
    DeleteGroupingTags
)

from lingvodoc.schema.gql_language import (
    Language,
    CreateLanguage,
    UpdateLanguage,
    DeleteLanguage,
    MoveLanguage,
    UpdateLanguageAtom)
from lingvodoc.schema.gql_merge import MergeBulk
from lingvodoc.schema.gql_dictionaryperspective import (
    DictionaryPerspective,
    CreateDictionaryPerspective,
    UpdateDictionaryPerspective,
    UpdatePerspectiveStatus,
    AddPerspectiveRoles,
    DeletePerspectiveRoles,
    DeleteDictionaryPerspective,
    UpdatePerspectiveAtom)
from lingvodoc.schema.gql_user import (
    User,
    CreateUser,
    UpdateUser,
    ActivateDeactivateUser
)
from lingvodoc.schema.gql_grant import (
    Grant,
    CreateGrant,
    UpdateGrant,
    # DeleteGrant
)
from lingvodoc.schema.gql_sync import (
    DownloadDictionary,
    DownloadDictionaries,
    Synchronize
)

# from lingvodoc.schema.gql_email import (
#     Email
# )
from lingvodoc.schema.gql_holders import (
    PermissionException,
    ResponseError,
    ObjectVal,
    client_id_check,
    LingvodocID,
    # LevelAndId
)

from lingvodoc.schema.gql_userrequest import (
    UserRequest,
    CreateGrantPermission,
    AddDictionaryToGrant,
    AdministrateOrg,
    ParticipateOrg,
    AcceptUserRequest,
    # DeleteUserRequest
)

import lingvodoc.acl as acl
import time
import random
import string
from lingvodoc.models import (
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    Language as dbLanguage,
    Organization as dbOrganization,
    Field as dbField,
    Group as dbGroup,
    BaseGroup as dbBaseGroup,
    User as dbUser,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    DictionaryPerspectiveToField as dbPerspectiveToField,
    Locale as dbLocale,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Email as dbEmail,
    UserBlobs as dbUserBlobs,
    UserRequest as dbUserRequest,
    Grant as dbGrant,
    DictionaryPerspective as dbDictionaryPerspective,
    Client,
    PublishingEntity as dbPublishingEntity
)
from pyramid.request import Request

from lingvodoc.utils.proxy import try_proxy, ProxyPass
from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_,
    create_engine
)
from lingvodoc.views.v2.utils import (
    view_field_from_object,
    storage_file,
    as_storage_file
)
from sqlalchemy.orm import aliased

from sqlalchemy.sql.functions import coalesce
from lingvodoc.schema.gql_tasks import Task, DeleteTask
from lingvodoc.schema.gql_convert_dictionary import ConvertDictionary, ConvertFiveTiers
from pyramid.security import authenticated_userid

from lingvodoc.utils.phonology import (
    gql_phonology as utils_phonology,
    gql_phonology_skip_list as utils_phonology_skip_list,
    gql_phonology_tier_list as utils_phonology_tier_list,
    gql_phonology_link_perspective_data,
    gql_sound_and_markup)

from lingvodoc.utils import starling_converter
from lingvodoc.utils.search import translation_gist_search, recursive_sort, eaf_words, find_all_tags, find_lexical_entries_by_tags

import lingvodoc.cache.caching as caching
from lingvodoc.cache.caching import initialize_cache, TaskStatus

import lingvodoc.views.v2.phonology as phonology
from lingvodoc.views.v2.phonology import (
    AudioPraatLike,
    format_textgrid_result,
    Phonology_Parameters,
    process_sound,
    process_textgrid)

from lingvodoc.views.v2.utils import anonymous_userid

from sqlite3 import connect
from lingvodoc.utils.merge import merge_suggestions
import tempfile
from lingvodoc.views.v2.save_dictionary.core import async_save_dictionary
import json

RUSSIAN_LOCALE = 1
ENGLISH_LOCALE = 2

from pyramid.httpexceptions import (
    HTTPError,
    HTTPOk
)

from lingvodoc.scripts import elan_parser
from lingvodoc.utils.creation import create_entity

from lingvodoc.queue.celery import celery


import cchardet as chardet

from celery.utils.log import get_task_logger

import numpy
import pathvalidate
import pydub
import pympi
import transaction
import xlsxwriter


# Setting up logging.
log = logging.getLogger(__name__)


# Trying to set up celery logging.
celery_log = get_task_logger(__name__)
celery_log.setLevel(logging.DEBUG)


# Mikhail Oslon's analysis functions.

try:
    liboslon = ctypes.CDLL('liboslon.so')

    phonemic_analysis_f = liboslon.PhonemicAnalysis_GetAllOutput
    cognate_analysis_f = liboslon.CognateAnalysis_GetAllOutput
    cognate_acoustic_analysis_f = liboslon.CognateAcousticAnalysis_GetAllOutput

except:
    phonemic_analysis_f = None
    cognate_analysis_f = None
    cognate_acoustic_analysis_f = None


class TierList(graphene.ObjectType):
    tier_count = graphene.Field(ObjectVal)
    total_count = graphene.Int()


class SkipList(graphene.ObjectType):
    markup_count = graphene.Int()
    neighbour_list = graphene.Field(ObjectVal)
    skip_list = graphene.Field(ObjectVal)
    total_neighbour_count = graphene.Int()
    total_skip_count = graphene.Int()


class Link_Perspective_Data(graphene.ObjectType):
    field_data_list = graphene.List(ObjectVal)
    perspective_id_list = graphene.List(LingvodocID)


class LexicalEntriesAndEntities(graphene.ObjectType):
    entities = graphene.List(Entity)
    lexical_entries = graphene.List(LexicalEntry)


class Permissions(graphene.ObjectType):
    edit = graphene.List(DictionaryPerspective)
    view = graphene.List(DictionaryPerspective)
    publish = graphene.List(DictionaryPerspective)
    limited = graphene.List(DictionaryPerspective)


class StarlingField(graphene.InputObjectType):
    starling_name = graphene.String(required=True)
    starling_type = graphene.Int(required=True)
    field_id = LingvodocID(required=True)
    fake_id = graphene.String()
    link_fake_id = LingvodocID()  # graphene.String()


class StarlingDictionary(graphene.InputObjectType):
    blob_id = LingvodocID()
    parent_id = LingvodocID(required=True)
    perspective_gist_id = LingvodocID()
    perspective_atoms = graphene.List(ObjectVal)
    translation_gist_id = LingvodocID()
    translation_atoms = graphene.List(ObjectVal)
    field_map = graphene.List(StarlingField, required=True)
    add_etymology = graphene.Boolean(required=True)


class DialeqtInfo(graphene.ObjectType):
    dictionary_name = graphene.String()
    dialeqt_id = graphene.String()


class MergeSuggestions(graphene.ObjectType):
    match_result = graphene.List(ObjectVal)
    user_has_permissions = graphene.Boolean()


def get_dict_attributes(sqconn):
    dict_trav = sqconn.cursor()
    dict_trav.execute("""SELECT
                        dict_name,
                        dict_identificator,
                        dict_description
                        FROM
                        dict_attributes
                        WHERE
                        id = 1;""")
    req = dict()
    for dictionary in dict_trav:
        req['dictionary_name'] = dictionary[0]
        req['dialeqt_id'] = dictionary[1]
    return req


class Query(graphene.ObjectType):
    client = graphene.String()
    dictionaries = graphene.List(Dictionary, published=graphene.Boolean(),
                                 mode=graphene.Int(),
                                 category=graphene.Int(),
                                 proxy=graphene.Boolean())
    dictionary = graphene.Field(Dictionary, id=LingvodocID())
    perspectives = graphene.List(DictionaryPerspective, published=graphene.Boolean())
    perspective = graphene.Field(DictionaryPerspective, id=LingvodocID())
    entity = graphene.Field(Entity, id=LingvodocID())
    language = graphene.Field(Language, id=LingvodocID())
    languages = graphene.List(Language)
    user = graphene.Field(User, id=graphene.Int())
    users = graphene.List(User, search=graphene.String())
    field = graphene.Field(Field, id=LingvodocID())
    translationgist = graphene.Field(TranslationGist, id=LingvodocID())
    userblob = graphene.Field(UserBlobs, id=LingvodocID())
    translationatom = graphene.Field(TranslationAtom, id=LingvodocID())
    organization = graphene.Field(Organization, id=LingvodocID())
    organizations = graphene.List(Organization)
    lexicalentry = graphene.Field(LexicalEntry, id=LingvodocID())
    basic_search = graphene.Field(LexicalEntriesAndEntities, searchstring=graphene.String(),
                                  can_add_tags=graphene.Boolean(),
                                  perspective_id=LingvodocID(), field_id=LingvodocID(),
                                  search_in_published=graphene.Boolean())
    advanced_lexicalentries = graphene.List(LexicalEntry, searchstrings=graphene.List(ObjectVal),
                                            perspectives=LingvodocID(),
                                            adopted=graphene.Boolean(),
                                            adopted_type=LingvodocID(),
                                            with_entimology=graphene.Boolean())
    translationgists = graphene.List(TranslationGist, gists_type=graphene.String())
    translation_search = graphene.List(TranslationGist, searchstring=graphene.String(),
                                       translation_type=graphene.String())
    translation_service_search = graphene.Field(TranslationGist, searchstring=graphene.String())
    advanced_translation_search = graphene.List(TranslationGist, searchstrings=graphene.List(graphene.String))
    all_locales = graphene.List(ObjectVal)
    user_blobs = graphene.List(UserBlobs, data_type=graphene.String(), is_global=graphene.Boolean())
    userrequest = graphene.Field(UserRequest, id=graphene.Int())
    userrequests = graphene.List(UserRequest)
    all_basegroups = graphene.List(BaseGroup)
    all_data_types = graphene.List(TranslationGist)
    all_fields = graphene.List(Field, common=graphene.Boolean())
    common_fields = graphene.List(Field)
    all_statuses = graphene.List(TranslationGist)
    template_fields = graphene.List(Field, mode=graphene.String())
    template_modes = graphene.List(graphene.String)
    grant = graphene.Field(Grant, id=graphene.Int())
    grants = graphene.List(Grant)
    column = graphene.Field(Column, id=LingvodocID())

    phonology_tier_list = graphene.Field(TierList, perspective_id=LingvodocID(required=True))
    phonology_skip_list = graphene.Field(SkipList, perspective_id=LingvodocID(required=True))

    phonology_link_perspective_data = graphene.Field(
        Link_Perspective_Data,
        perspective_id = LingvodocID(required = True),
        field_id_list = graphene.List(LingvodocID, required = True))

    connected_words = graphene.Field(LexicalEntriesAndEntities, id=LingvodocID(required=True),
                                     field_id=LingvodocID(required=True), mode=graphene.String())
    advanced_search = graphene.Field(AdvancedSearch,
                                     languages=graphene.List(LingvodocID),
                                     dicts_to_filter=graphene.List(LingvodocID),
                                     tag_list=graphene.List(graphene.String),
                                     category=graphene.Int(),
                                     adopted=graphene.Boolean(),
                                     etymology=graphene.Boolean(),
                                     search_strings=graphene.List(graphene.List(ObjectVal), required=True),
                                     mode=graphene.String(),
                                     search_metadata=ObjectVal(),
                                     simple=graphene.Boolean())
    advanced_search_simple = graphene.Field(AdvancedSearchSimple,
                                     languages=graphene.List(LingvodocID),
                                     dicts_to_filter=graphene.List(LingvodocID),
                                     tag_list=graphene.List(graphene.String),
                                     category=graphene.Int(),
                                     adopted=graphene.Boolean(),
                                     etymology=graphene.Boolean(),
                                     search_strings=graphene.List(graphene.List(ObjectVal)),
                                     mode=graphene.String())
    search_strings = graphene.List(graphene.List(ObjectVal))
    convert_markup = graphene.Field(
        graphene.String, id=LingvodocID(required=True))

    eaf_wordlist = graphene.Field(
        graphene.List(graphene.String), id=LingvodocID(required=True))
    language_tree = graphene.List(Language)
    permission_lists = graphene.Field(Permissions, proxy=graphene.Boolean(required=True))
    tasks = graphene.List(Task)
    is_authenticated = graphene.Boolean()
    dictionary_dialeqt_get_info = graphene.Field(DialeqtInfo, blob_id=LingvodocID(required=True))
    convert_five_tiers_validate = graphene.Boolean(markup_id=LingvodocID(required=True))
    merge_suggestions = graphene.Field(MergeSuggestions, perspective_id=LingvodocID(required=True),
                                       algorithm=graphene.String(required=True),
                                       entity_type_primary=graphene.String(),
                                       entity_type_secondary=graphene.String(),
                                       levenshtein=graphene.Int(),
                                       threshold=graphene.Float(),
                                       field_selection_list=graphene.List(ObjectVal), )
    select_tags_metadata = ObjectVal()


    def resolve_select_tags_metadata(self, info):
        def get_sorted_metadata_keys(metadata_name):
            all_values = DBSession.query(dbDictionary.additional_metadata[metadata_name]) \
                .filter(dbDictionary.additional_metadata[metadata_name] != None,
                        dbDictionary.marked_for_deletion==False)
            all_authors_lists = [value for value, in all_values]
            values_iterator = itertools.chain.from_iterable(all_authors_lists)
            uniq_values = set(values_iterator)
            soreted_values = sorted(list(uniq_values))
            return soreted_values

        menu_json_data = {}
        authors_list = get_sorted_metadata_keys("authors")
        menu_json_data["hasAudio"] = [False, True]
        menu_json_data["authors"] = authors_list
        menu_json_data["humanSettlement"] = get_sorted_metadata_keys("humanSettlement")
        menu_json_data["years"] = get_sorted_metadata_keys("years")
        menu_json_data["kind"] = ["Expedition", "Archive"]
        menu_json_data["nativeSpeakersCount"] = ["Vulnerable",
                                                 "Definitely endangered",
                                                 "Critically endangered",
                                                 "Extinct",
                                                 "Severely endangered",
                                                 "Safe"]
        return menu_json_data



    def resolve_merge_suggestions(self, info, perspective_id, algorithm, threshold=0.1,
                                  entity_type_primary='Transcription',
                                  entity_type_secondary='Translation',
                                  levenshtein=1,
                                  field_selection_list=None
                                  ):
        request = info.context.request
        locale_id = info.context.get('locale_id')

        old_field_selection_list = copy.deepcopy(field_selection_list)

        for field_selection in old_field_selection_list:
            field_selection['client_id'] = field_selection['field_id'][0]
            field_selection['object_id'] = field_selection['field_id'][1]

        result = merge_suggestions(request=request,
                                   perspective_client_id=perspective_id[0],
                                   perspective_object_id=perspective_id[1],
                                   algorithm=algorithm,
                                   entity_type_primary=entity_type_primary,
                                   entity_type_secondary=entity_type_secondary,
                                   threshold=threshold, levenshtein=levenshtein,
                                   field_selection_list=old_field_selection_list,
                                   locale_id=locale_id)

        return MergeSuggestions(user_has_permissions=result['user_has_permissions'],
                                match_result=result['match_result'])

    def resolve_convert_five_tiers_validate(self, info, markup_id):
        client_id, object_id = markup_id
        entity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
        if not entity:
            raise KeyError("No such file")
        resp = requests.get(entity.content)
        if not resp:
            raise ResponseError("Cannot access file")
        content = resp.content
        result = False
        with tempfile.NamedTemporaryFile() as temp:
            markup = tgt_to_eaf(content, entity.additional_metadata)
            temp.write(markup.encode("utf-8"))
            elan_check = elan_parser.ElanCheck(temp.name)
            elan_check.parse()
            if elan_check.check():
                result = True
            temp.flush()
        return result

    """
        from urllib import request
        from urllib.parse import quote
        #request = urllib.request #info.context.request
        try:
            result = False
            file_name = eaf_url.split("/")[-1]
            folder = "/".join(eaf_url.split("/")[:-1])
            eaffile = request.urlopen("%s/%s" % (folder, quote(file_name)))
        except HTTPError as e:
            raise ResponseError(message=str(e))
        except KeyError as e:
            raise ResponseError(message=str(e))
        with tempfile.NamedTemporaryFile() as temp:
            markup = tgt_to_eaf(eaffile.read(), {"data_type": "praat"})
            temp.write(markup)
            elan_check = elan_parser.ElanCheck(temp.name)
            elan_check.parse()
            if elan_check.check():
                result = True
            temp.flush()
        return result
    """

    def resolve_dictionary_dialeqt_get_info(self, info, blob_id):  # TODO: test
        blob_client_id, blob_object_id = blob_id
        blob = DBSession.query(dbUserBlobs).filter_by(client_id=blob_client_id, object_id=blob_object_id).first()
        if blob:
            filename = blob.real_storage_path
            sqconn = connect(filename)
            try:
                dict_attributes = get_dict_attributes(sqconn)
            except:
                raise ResponseError(message="database disk image is malformed")
            return DialeqtInfo(dictionary_name=dict_attributes['dictionary_name'], dialeqt_id=dict_attributes["dialeqt_id"])
        raise ResponseError(message="No such blob in the system")

    def resolve_tasks(self, info):
        request = info.context.request
        client_id = authenticated_userid(request)
        if not client_id:
            tasks_dicts = TaskStatus.get_user_tasks(anonymous_userid(request), clear_out=True)
            tasks = [Task(**task_dict) for task_dict in tasks_dicts]
            return tasks
        user = Client.get_user_by_client_id(authenticated_userid(request))
        tasks_dicts = TaskStatus.get_user_tasks(user.id, clear_out=True)
        tasks = [Task(**task_dict) for task_dict in tasks_dicts]
        return tasks

    def resolve_permission_lists(self, info, proxy):
        request = info.context.request
        if proxy:
            try_proxy(request)
        client_id = authenticated_userid(request)

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'Published'}
        headers = dict()
        if request.headers.get('Cookie'):
            headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)

        if 'error' not in resp.json:
            published_gist_object_id, published_gist_client_id = resp.json['object_id'], resp.json['client_id']
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])

        subreq = Request.blank('/translation_service_search')
        subreq.method = 'POST'
        subreq.headers = request.headers
        subreq.json = {'searchstring': 'Limited access'}  # todo: fix
        headers = dict()
        if request.headers.get('Cookie'):
            headers = {'Cookie': request.headers['Cookie']}
        subreq.headers = headers
        resp = request.invoke_subrequest(subreq)

        if 'error' not in resp.json:
            limited_gist_object_id, limited_gist_client_id = resp.json['object_id'], resp.json['client_id']
        else:
            raise KeyError("Something wrong with the base", resp.json['error'])


        dblimited = DBSession.query(dbDictionaryPerspective).filter(
            and_(dbDictionaryPerspective.state_translation_gist_client_id == limited_gist_client_id,
                 dbDictionaryPerspective.state_translation_gist_object_id == limited_gist_object_id)
        )

        # limited_perms = [("limited", True), ("read", False), ("write", False), ("publish", False)]
        limited = list()
        for dbperspective in dblimited.all():
            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
            perspective.dbObject = dbperspective
            perspective.list_name='limited'
            limited.append(perspective)
            # fulfill_permissions_on_perspectives(intermediate, pers, limited_perms)


        dbpublished = DBSession.query(dbDictionaryPerspective).filter(
            and_(dbDictionaryPerspective.state_translation_gist_client_id == published_gist_client_id,
                 dbDictionaryPerspective.state_translation_gist_object_id == published_gist_object_id)
        )
        existing = list()
        view = list()
        for dbperspective in dbpublished.all():
            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
            perspective.dbObject = dbperspective
            perspective.list_name='view'
            view.append(perspective)
            existing.append([dbperspective.client_id, dbperspective.object_id])

        if not client_id:
            return Permissions(limited=limited, view=view, edit=list(), publish=list())

        user = DBSession.query(Client).filter(client_id == Client.id).first()
        if not user:
            return None
        user_id = user.user_id
        editor_basegroup = DBSession.query(dbBaseGroup).filter(
            and_(dbBaseGroup.subject == "lexical_entries_and_entities", dbBaseGroup.action == "create")).first()
        editable_perspectives = DBSession.query(dbDictionaryPerspective).join(dbGroup, and_(
            dbDictionaryPerspective.client_id == dbGroup.subject_client_id,
            dbDictionaryPerspective.object_id == dbGroup.subject_object_id)).join(dbGroup.users).filter(
            and_(dbUser.id == user_id,
                 dbGroup.base_group_id == editor_basegroup.id,
                 dbDictionaryPerspective.marked_for_deletion == False)).all()
        edit = list()
        for dbperspective in editable_perspectives:
            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
            perspective.dbObject = dbperspective
            perspective.list_name='edit'
            edit.append(perspective)

        reader_basegroup = DBSession.query(dbBaseGroup).filter(
            and_(dbBaseGroup.subject == "approve_entities", dbBaseGroup.action == "view")).first()
        readable_perspectives = DBSession.query(dbDictionaryPerspective).join(dbGroup, and_(
            dbDictionaryPerspective.client_id == dbGroup.subject_client_id,
            dbDictionaryPerspective.object_id == dbGroup.subject_object_id)).join(dbGroup.users).filter(
            and_(dbUser.id == user_id, dbGroup.base_group_id == reader_basegroup.id)).all()

        view = list()
        for dbperspective in readable_perspectives:
            if [dbperspective.client_id, dbperspective.object_id] not in existing:
                perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
                perspective.dbObject = dbperspective
                perspective.list_name='view'
                view.append(perspective)

        publisher_basegroup = DBSession.query(dbBaseGroup).filter(
            and_(dbBaseGroup.subject == "approve_entities", dbBaseGroup.action == "create")).first()

        approvable_perspectives = DBSession.query(dbDictionaryPerspective).join(dbGroup, and_(
            dbDictionaryPerspective.client_id == dbGroup.subject_client_id,
            dbDictionaryPerspective.object_id == dbGroup.subject_object_id)).join(dbGroup.users).filter(
            and_(dbUser.id == user_id, dbGroup.base_group_id == publisher_basegroup.id)).all()
        publish = list()
        for dbperspective in approvable_perspectives:
            perspective = DictionaryPerspective(id=[dbperspective.client_id, dbperspective.object_id])
            perspective.dbObject = dbperspective
            perspective.list_name='publish'
            publish.append(perspective)
        return Permissions(limited=limited, view=view, edit=edit, publish=publish)


    def resolve_language_tree(self, info):
        langs = DBSession.query(dbLanguage).filter_by(marked_for_deletion=False).order_by(dbLanguage.parent_client_id,
                                                                                        dbLanguage.parent_object_id,
                                                                                        dbLanguage.additional_metadata[
                                                                                            'younger_siblings']).all()
        visited = set()
        stack = set()
        result = list()
        recursive_sort(langs, visited, stack, result)

        def create_levelandid(item):
            obj = Language(id=[item[1], item[2]])
            obj.dbObject = item[3]
            return obj

        result = [create_levelandid(i) for i in result]
        if len(result) != len(langs):
            lang_set = {(l.dbObject.client_id, l.dbObject.object_id) for l in result}
            errors = [(lang.client_id, lang.object_id) for lang in langs if (lang.client_id, lang.object_id) not in lang_set]
            print(errors)
        return result

    def resolve_advanced_search(self, info, search_strings=None, languages=None, dicts_to_filter=None, tag_list=None, category=None, adopted=None, etymology=None, search_metadata=None, mode='published', simple=True):

        if mode == 'all':
            publish = None
            accept = True
        elif mode == 'published':
            publish = True
            accept = True
        elif mode == 'not_accepted':
            publish = None
            accept = False
        elif mode == 'deleted':
            publish = None
            accept = None
        elif mode == 'all_with_deleted':
            publish = None
            accept = None
        else:
            raise ResponseError(message="mode: <all|published|not_accepted>")
        # if not search_strings:
        #     raise ResponseError(message="search_strings is empty")
        if simple:
            return AdvancedSearchSimple().constructor(languages, dicts_to_filter, tag_list, category, adopted, etymology,
                                            search_strings, publish, accept)
        return AdvancedSearch().constructor(languages, dicts_to_filter, tag_list, category, adopted, etymology, search_strings, publish, accept, search_metadata)

    def resolve_advanced_search_simple(self, info, search_strings, languages=None, dicts_to_filter=None, tag_list=None, category=None, adopted=None, etymology=None, search_metadata=None, mode='published'):

        if mode == 'all':
            publish = None
            accept = True
        elif mode == 'published':
            publish = True
            accept = True
        elif mode == 'not_accepted':
            publish = None
            accept = False
        elif mode == 'deleted':
            publish = None
            accept = None
        elif mode == 'all_with_deleted':
            publish = None
            accept = None
        else:
            raise ResponseError(message="mode: <all|published|not_accepted>")
        if not search_strings:
            raise ResponseError(message="search_strings is empty")
        return AdvancedSearchSimple().constructor(languages, dicts_to_filter, tag_list, category, adopted, etymology,
                                            search_strings, publish, accept)

    def resolve_template_modes(self, info):
        return ['corpora']

    def resolve_template_fields(self, info, mode=None):
        response = list()
        request = info.context.request
        if mode == 'corpora':
            data_type_query = DBSession.query(dbField) \
                .join(dbTranslationGist,
                      and_(dbField.translation_gist_object_id == dbTranslationGist.object_id,
                           dbField.translation_gist_client_id == dbTranslationGist.client_id)) \
                .join(dbTranslationGist.translationatom)
            sound_field = data_type_query.filter(dbTranslationAtom.locale_id == 2,
                                                 dbTranslationAtom.content == 'Sound').one()  # todo: a way to find this fields if wwe cannot use one
            markup_field = data_type_query.filter(dbTranslationAtom.locale_id == 2,
                                                  dbTranslationAtom.content == 'Markup').one()
            comment_field = data_type_query.filter(dbTranslationAtom.locale_id == 2,
                                                    dbTranslationAtom.content == 'Comment').one()
            sound_field =view_field_from_object(request=request, field=sound_field)
            markup_field = view_field_from_object(request=request, field=markup_field)
            comment_field = view_field_from_object(request=request, field=comment_field)
            fake_id_1 = '6f355d7a-e68d-44ab-9cf6-36f78e8f1b34'  # chosen by fair dice roll
            fake_id_2 = '51fbe0b6-2cea-4d40-a994-f6bb6f501d48'  # guaranteed to be random
            f = Field(id=[sound_field["client_id"], sound_field["object_id"]], fake_id = fake_id_1)
            f2 = Field(id=[markup_field["client_id"], markup_field["object_id"]], fake_id = fake_id_2, self_fake_id = fake_id_1)
            f.dbObject = DBSession.query(dbField).filter_by(client_id=sound_field["client_id"], object_id=sound_field["object_id"]).first()
            f2.dbObject = DBSession.query(dbField).filter_by(client_id=markup_field["client_id"], object_id=markup_field["object_id"]).first()
            response.append(f)
            response.append(f2)

            f3 = Field(id=[comment_field["client_id"], comment_field["object_id"]])
            f3.dbObject = DBSession.query(dbField).filter_by(client_id=comment_field["client_id"]).first()
            response.append(f3)
            # response[0]['contains'] = [view_field_from_object(request=request, field=markup_field)]
            # response.append(view_field_from_object(request=request, field=markup_field))
            # response.append(view_field_from_object(request=request, field=comment_field))
            #
            # return response
            #
            # response.append(TranslationGist(id=[sound_field.translation_gist_client_id, sound_field.data_type_translation_gist_object_id]))
            # response.append(TranslationGist(id=[markup_field.data_type_translation_gist_client_id, markup_field.data_type_translation_gist_object_id]))
            # response.append(TranslationGist(id=[comment_field.data_type_translation_gist_client_id, comment_field.data_type_translation_gist_object_id]))
            return response
        else:
            raise ResponseError(message='no such mode')
    def resolve_all_statuses(self, info):
        request = info.context.request
        gql_statuses = list()
        for status in ['WiP', 'Published', 'Limited access', 'Hidden']:
            db_tr_gist = translation_gist_search(status)
            gql_tr_gist = TranslationGist(id=[db_tr_gist.client_id, db_tr_gist.object_id ])
            gql_tr_gist.dbObject = db_tr_gist
            gql_statuses.append(gql_tr_gist)
        return gql_statuses

    def resolve_all_fields(self, info, common=False):
        fields = DBSession.query(dbField).filter_by(marked_for_deletion=False).all()
        if common:
            field_to_psersp_dict = collections.defaultdict(list)
            p_to_field = DBSession.query(dbPerspectiveToField.parent_client_id,
                                         dbPerspectiveToField.parent_object_id,
                                         dbPerspectiveToField.field_client_id,
                                         dbPerspectiveToField.field_object_id).filter(
                dbPerspectiveToField.marked_for_deletion == False
            ).all()

            for perspective_client_id, perspective_object_id, field_client_id, field_object_id in p_to_field:
                field_to_psersp_dict[(field_client_id, field_object_id)].append((perspective_client_id,
                                                                                 perspective_object_id))
        gql_fields = list()
        for db_field in fields:
            if common:
                if len(field_to_psersp_dict[(db_field.client_id, db_field.object_id)]) <= 3:
                    continue
                if db_field.data_type != "Text":
                    continue
            gql_field = Field(id=[db_field.client_id, db_field.object_id])
            gql_field.dbObject = db_field
            gql_fields.append(gql_field)

        return gql_fields




    def resolve_all_data_types(self, info):
        response = list()
        for data_type in ['Text', 'Image', 'Sound', 'Markup', 'Link', 'Grouping Tag']:
            db_tr_gist = translation_gist_search(data_type)
            gql_tr_gist = TranslationGist(id=[db_tr_gist.client_id, db_tr_gist.object_id ])
            gql_tr_gist.dbObject = db_tr_gist
            response.append(gql_tr_gist)
        return response

    def resolve_dictionaries(self, info, published=None, mode=None, category=None, proxy=False):
        """
        example:

        query DictionaryList {
            dictionaries(published: true) {
                id
                translation
                parent_id
                translation_gist_id
                state_translation_gist_id
                category
                domain
            }
        }
        """
        request = info.context.request
        if proxy:
            try_proxy(request)

        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        dbdicts = None
        if published:
            db_published_gist = translation_gist_search('Published')
            state_translation_gist_client_id = db_published_gist.client_id
            state_translation_gist_object_id = db_published_gist.object_id
            db_la_gist = translation_gist_search('Limited access')
            limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id


            dbdicts = DBSession.query(dbDictionary).filter(dbDictionary.marked_for_deletion == False).filter(
                or_(and_(dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                         dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id),
                    and_(dbDictionary.state_translation_gist_object_id == limited_object_id,
                         dbDictionary.state_translation_gist_client_id == limited_client_id))). \
                join(dbPerspective) \
                .filter(or_(and_(dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                                 dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                            and_(dbPerspective.state_translation_gist_object_id == limited_object_id,
                                 dbPerspective.state_translation_gist_client_id == limited_client_id))). \
                filter(dbPerspective.marked_for_deletion == False)

        else:
            if not dbdicts:
                dbdicts = DBSession.query(dbDictionary).filter(dbDictionary.marked_for_deletion == False)

        if category is not None:
            if category:
                dbdicts = dbdicts.filter(dbDictionary.category == 1)
            else:
                dbdicts = dbdicts.filter(dbDictionary.category == 0)
        dbdicts = dbdicts.order_by(dbDictionary.created_at.desc())
        if mode is not None and client:
            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            if not mode:
                # available
                clients = DBSession.query(Client).filter(Client.user_id.in_([user.id])).all()  # user,id?
                cli = [o.id for o in clients]
                #response['clients'] = cli
                dbdicts = dbdicts.filter(dbDictionary.client_id.in_(cli))
            else:
                #  my_dictionaries
                dictstemp = []
                group_tuples = []
                isadmin = False
                for group in user.groups: # todo: LOOK AT ME this is really bad. rewrite me from group point of view
                    if group.parent.dictionary_default:
                        if group.subject_override:
                            isadmin = True
                            break
                        dcttmp = (group.subject_client_id, group.subject_object_id)
                        if dcttmp not in dictstemp:
                            dictstemp += [dcttmp]
                    if group.parent.perspective_default:
                        if group.subject_override:
                            isadmin = True
                            break
                    group_tuples.append((group.subject_client_id, group.subject_object_id))

                list_remainder = group_tuples[:1000]
                group_tuples = group_tuples[1000:]
                dicti = list()
                while list_remainder:
                    dicti+= DBSession.query(dbDictionary) \
                        .join(dbDictionaryPerspective) \
                        .filter(tuple_(dbDictionaryPerspective.client_id, dbDictionaryPerspective.object_id).in_(list_remainder)) \
                        .all()
                    list_remainder = group_tuples[:1000]
                    group_tuples = group_tuples[1000:]
                for d in dicti:
                    dcttmp = (d.client_id, d.object_id)
                    if dcttmp not in dictstemp:
                        dictstemp += [dcttmp]
                if not isadmin:
                    dbdicts = [o for o in dbdicts if (o.client_id, o.object_id) in dictstemp]

        dictionaries_list = list()
        for dbdict in dbdicts:
            gql_dict = Dictionary(id=[dbdict.client_id, dbdict.object_id])
            gql_dict.dbObject = dbdict
            dictionaries_list.append(gql_dict)
        return dictionaries_list

    def resolve_dictionary(self, info, id):
        return Dictionary(id=id)

    def resolve_perspectives(self,info, published=None):
        """
        example:

        query LanguagesList {
            perspectives(published: true) {
                id
                translation
                parent_id
                translation_gist_id
                state_translation_gist_id
                import_source
                import_hash
            }
        }
        """
        context = info.context
        if published:
            db_published_gist = translation_gist_search('Published')
            state_translation_gist_client_id = db_published_gist.client_id
            state_translation_gist_object_id = db_published_gist.object_id
            db_la_gist = translation_gist_search('Limited access')
            limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id

            """
            atom_perspective_name_alias = aliased(dbTranslationAtom, name="PerspectiveName")
            atom_perspective_name_fallback_alias = aliased(dbTranslationAtom, name="PerspectiveNameFallback")
            persps = DBSession.query(dbPerspective,
                                     dbTranslationAtom,
                                     coalesce(atom_perspective_name_alias.content,
                                              atom_perspective_name_fallback_alias.content,
                                              "No translation for your locale available").label("Translation")
                                     ).filter(dbPerspective.marked_for_deletion == False)
            """
            persps = DBSession.query(dbPerspective).filter(
                or_(and_(dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                         dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                    and_(dbPerspective.state_translation_gist_object_id == limited_object_id,
                         dbDictionary.state_translation_gist_client_id == limited_client_id))). \
                filter(dbPerspective.marked_for_deletion == False).all()
        else:
            persps = DBSession.query(dbPerspective).filter(dbPerspective.marked_for_deletion == False).all()


        perspectives_list = []

        for db_persp in persps:
            gql_persp =  DictionaryPerspective(id=[db_persp.client_id, db_persp.object_id])
            gql_persp.dbObject = db_persp
            perspectives_list.append(gql_persp)
        return perspectives_list


    def resolve_perspective(self, info, id):
        return DictionaryPerspective(id=id)

    def resolve_language(self, info, id):
        return Language(id=id)

    def resolve_languages(self, info):
        """
        example:

        query LanguagesList {
            languages {
                id
                translation
                parent_id
                translation_gist_id
            }
        }
        """
        context = info.context


        languages = DBSession.query(dbLanguage).filter_by(marked_for_deletion = False).all()
        languages_list = list()
        for db_lang in languages:
            gql_lang = Language(id=[db_lang.client_id, db_lang.object_id])
            gql_lang.dbObject = db_lang
            languages_list.append(gql_lang)

        return languages_list

    def resolve_entity(self, info, id):
        return Entity(id=id)

    def resolve_user(self, info, id=None):
        if id is None:
            client_id = info.context.get('client_id')
            client = DBSession.query(Client).filter_by(id=client_id).first()
            id = client.user_id
        return User(id=id)

    def resolve_is_authenticated(self, info):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()
        if not client:
            return False
        return True

    def resolve_users(self, info, search=None):
        """
        example:

        query UsersList {
            users(search: "modis") {
                login
                name
                intl_name
            }
        }
        """
        users = DBSession.query(dbUser).join(dbUser.email)
        if search:
            name = search + '%'
            users = users.filter(or_(
                dbUser.name.startswith(name),
                dbUser.login.startswith(name),
                dbUser.intl_name.startswith(name),
                dbEmail.email.startswith(name)
            ))
        users_list = list()
        for db_user in users:
            gql_user = User(name=db_user.name)
            gql_user.dbObject = db_user
            users_list.append(gql_user)

        return users_list


    # def resolve_datetime(self, args, context, info):
    #     id = args.get('id')
    #     return DateTime(id=id)

    def resolve_basegroup(self, info, id):
        return BaseGroup(id=id)

    def resolve_client(self, info):
        context = info.context
        return context.get('client')

    def resolve_column(self, info, id):
        return Column(id=id)

    def resolve_group(self, info, id):
        return Group(id=id)

    def resolve_organization(self, info, id):
        return Organization(id=id)

    def resolve_organizations(self, info):
        organizations = DBSession.query(dbOrganization).filter_by(marked_for_deletion=False).all()
        organizations_list = list()
        for db_organisation in organizations:
            gql_organisation = Organization(id=db_organisation.id)
            gql_organisation.dbObject = db_organisation
        return organizations_list

    # def resolve_passhash(self, args, context, info):
    #     id = args.get('id')
    #     return Passhash(id=id)

    # def resolve_objecttoc(self, args, context, info):
    #     id = args.get('id')
    #     return ObjectTOC(id=id)


    def resolve_translationatom(self, info, id):
        return TranslationAtom(id=id)

    def resolve_translationgist(self, info, id):
        return TranslationGist(id=id)

    def resolve_translationgists(self, info, gists_type=None):
        """
        example:
        query GistsList {
            translationgists {
                id
                type
            }
        }
        """

        gists_query = DBSession.query(dbTranslationGist).filter_by(marked_for_deletion=False)
        if gists_type:
            gists_query = gists_query.filter(dbTranslationGist.type == gists_type)
        else:
            gists_query = gists_query.order_by(dbTranslationGist.type)
        gists = gists_query.all()
        gists_list = list()
        for db_gist in gists:
            gql_gist = TranslationGist(id=[db_gist.client_id, db_gist.object_id])
            gql_gist.dbObject = db_gist
            gists_list.append(gql_gist)

        return gists_list

    def resolve_translation_search(self, info, searchstring, translation_type=None):
        """
        query TranslationsList {
            translation_search(searchstring: "словарь") {
                id
                type
                translationatoms {
                     id
                     content
                }
            }
        }
        """
        translationatoms = DBSession.query(dbTranslationAtom).filter(dbTranslationAtom.content.like('%' + searchstring + '%'))
        if translation_type:
            translationatoms = translationatoms.join(dbTranslationGist).filter(dbTranslationGist.type == translation_type).all()
        else:
            translationatoms = translationatoms.all()

        translationgists = list()
        for translationatom in translationatoms:
            parent = translationatom.parent
            if parent not in translationgists:
                translationgists.append(parent)

        if translationgists:
            translationgists_list = list()
            for translationgist in translationgists:
                # translationatoms_list = list()
                # for translationatom in translationgist.translationatom:
                #     translationatom_object = TranslationAtom(id=[translationatom.client_id, translationatom.object_id],
                #                                              parent_id=[translationatom.parent_client_id,
                #                                                         translationatom.parent_object_id],
                #                                              content=translationatom.content,
                #                                              locale_id=translationatom.locale_id,
                #                                              created_at=translationatom.created_at
                #                                              )
                #     translationatoms_list.append(translationatom_object)
                translationgist_object = TranslationGist(id=[translationgist.client_id, translationgist.object_id])
                                                         # type=translationgist.type,
                                                         # created_at=translationgist.created_at,
                                                         # translationatoms=translationatoms_list)
                translationgists_list.append(translationgist_object)
            return translationgists_list
        raise ResponseError(message="Error: no result")

    def resolve_translation_service_search(self, info, searchstring):
        """
        query TranslationsList {
            translation_service_search(searchstring: "Converting 80%") {
                id
                type
                translationatoms {
                     id
                     content
                }
            }
        }
        """
        db_translationgist = translation_gist_search(searchstring)
        if not db_translationgist:
            raise ResponseError(message="Error: no result")
        # translationatoms_list = list()
        # for db_translationatom in db_translationgist.translationatom:
        #     translationatom_object = TranslationAtom(id=[db_translationatom.client_id, db_translationatom.object_id])
        #     translationatom_object.dbObject = db_translationatom
        #     translationatoms_list.append(translationatom_object)
        gql_translationgist = TranslationGist(id=[db_translationgist.client_id, db_translationgist.object_id])
        gql_translationgist.dbObject = db_translationgist
        return gql_translationgist


    def resolve_advanced_translation_search(self, info, searchstrings):
        """
        query TranslationsList {
            advanced_translation_search(searchstrings: ["Converting 80%", "Available dictionaries"]) {
                id
                type
                translationatoms {
                     id
                     content
                }
            }
        }
        """
        if not searchstrings:
            raise ResponseError(message="Error: no search strings")




        atoms_query = DBSession.query(dbTranslationAtom).join(dbTranslationGist). \
                filter(dbTranslationAtom.locale_id == 2,
                       dbTranslationGist.type == 'Service',
                       dbTranslationGist.marked_for_deletion==False,
                       dbTranslationAtom.marked_for_deletion==False)
        atoms = atoms_query.all()

        string_to_gist = dict()
        for atom in atoms:
            if atom.content in searchstrings:
                string_to_gist[atom.content] = atom.parent

        translationgists_list = list()
        for ss in searchstrings:
            if ss in string_to_gist:
                translationgist = string_to_gist[ss]
                gql_translationgist = TranslationGist(id=[translationgist.client_id, translationgist.object_id] , translation=ss)
                gql_translationgist.dbObject = translationgist
                translationgists_list.append(gql_translationgist)
            else:
                translationgists_list.append(None)
        # for ss in searchstrings:
        #     gist = DBSession.query(atoms).filter(dbTranslationAtom.content=="Link").first()
        #     translationgist = DBSession.query(dbTranslationGist) \
        #             .join(dbTranslationAtom). \
        #         filter(dbTranslationAtom.content == ss,
        #                dbTranslationAtom.locale_id == 2,
        #                dbTranslationGist.type == 'Service',
        #                dbTranslationGist.marked_for_deletion==False,
        #                dbTranslationAtom.marked_for_deletion==False) \
        #         .first()
        #     if translationgist:
        #         gql_translationgist = TranslationGist(id=[translationgist.client_id, translationgist.object_id])
        #         gql_translationgist.dbObject = translationgist
        #         translationgists_list.append(gql_translationgist)
        #     else:
        #         translationgists_list.append(None)



        return translationgists_list
        # raise ResponseError(message="Error: no result")

    def resolve_userblob(self, info, id):
        return UserBlobs(id=id)

    def resolve_field(self, info, id):
        return Field(id=id)

    def resolve_lexicalentry(self, info, id):
        return LexicalEntry(id=id)

    def resolve_all_locales(self, info):
        response = list()
        locales = DBSession.query(dbLocale).all()
        for locale in locales:
            locale_json = dict()
            locale_json['shortcut'] = locale.shortcut
            locale_json['intl_name'] = locale.intl_name
            locale_json['created_at'] = locale.created_at
            locale_json['id'] = locale.id
            response.append(locale_json)
        return response


    def resolve_basic_search(self, info, searchstring, search_in_published, field_id=None, perspective_id=None, can_add_tags=None): #basic_search() function
        """
        query EntriesList {
            basic_search(searchstring: "следить", search_in_published: true) {
                id
                entities {
                     id
                     content
                }
            }
        }

        """

        if searchstring:
            if len(searchstring) >= 1:
                field = None
                if field_id:
                    field_client_id, field_object_id = field_id[0], field_id[1]
                    field = DBSession.query(dbField).filter_by(client_id=field_client_id, object_id=field_object_id).first()

                client_id = info.context.get('client_id')
                group = DBSession.query(dbGroup).filter(dbGroup.subject_override == True).join(dbBaseGroup) \
                    .filter(dbBaseGroup.subject == 'lexical_entries_and_entities', dbBaseGroup.action == 'view') \
                    .join(dbUser, dbGroup.users).join(Client) \
                    .filter(Client.id == client_id).first()

                published_cursor = None

                if group:
                    results_cursor = DBSession.query(dbEntity).join(dbEntity.publishingentity).filter(dbEntity.content.like('%'+searchstring+'%'), dbEntity.marked_for_deletion == False)
                    if perspective_id:
                        perspective_client_id, perspective_object_id = perspective_id
                        results_cursor = results_cursor.join(dbLexicalEntry) \
                            .join(dbPerspective) \
                            .filter(dbPerspective.client_id == perspective_client_id,
                                    dbPerspective.object_id == perspective_object_id)

                    if search_in_published is not None:
                        results_cursor.filter(dbPublishingEntity.published == search_in_published)

                    results_cursor.filter(dbPublishingEntity.accepted==True)
                else:
                    results_cursor = DBSession.query(dbEntity).join(dbEntity.publishingentity) \
                        .join(dbEntity.parent) \
                        .join(dbPerspective)

                    if not perspective_id:
                        published_cursor = results_cursor

                    if search_in_published is not None:
                        results_cursor.filter(dbPublishingEntity.published == search_in_published)

                    results_cursor.filter(dbPublishingEntity.accepted==True)

                    ignore_groups = False
                    db_published_gist = translation_gist_search('Published')
                    state_translation_gist_client_id = db_published_gist.client_id
                    state_translation_gist_object_id = db_published_gist.object_id

                    if perspective_id:
                        perspective_client_id, perspective_object_id = perspective_id
                        results_cursor = results_cursor.filter(dbPerspective.client_id == perspective_client_id,
                                                               dbPerspective.object_id == perspective_object_id)
                        persp = DBSession.query(dbPerspective).filter_by(client_id=perspective_client_id,
                                                                                 object_id=perspective_object_id).first()
                        if persp and persp.state_translation_gist_client_id == state_translation_gist_client_id and persp.state_translation_gist_object_id == state_translation_gist_object_id:
                            ignore_groups = True
                    else:
                        published_cursor = results_cursor

                    if not ignore_groups:
                        results_cursor = results_cursor.join(dbGroup, and_(
                            dbPerspective.client_id == dbGroup.subject_client_id,
                            dbPerspective.object_id == dbGroup.subject_object_id)) \
                            .join(dbBaseGroup) \
                            .join(dbUser, dbGroup.users) \
                            .join(Client) \
                            .filter(Client.id == client_id,
                                    dbEntity.content.like('%' + searchstring + '%'), dbEntity.marked_for_deletion == False)
                    else:
                        results_cursor = results_cursor.filter(dbEntity.content.like('%' + searchstring + '%'),
                                                               dbEntity.marked_for_deletion == False)
                    if published_cursor:
                        published_cursor = published_cursor \
                            .join(dbPerspective.parent).filter(
                            dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                            dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id,
                            dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                            dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id,
                            dbEntity.content.like('%' + searchstring + '%'))

                if can_add_tags and not group:
                    results_cursor = results_cursor \
                        .filter(dbBaseGroup.subject == 'lexical_entries_and_entities',
                                or_(dbBaseGroup.action == 'create', dbBaseGroup.action == 'view')) \
                        .group_by(dbEntity).having(func.count('*') == 2)
                elif not group:
                    results_cursor = results_cursor.filter(dbBaseGroup.subject == 'lexical_entries_and_entities',
                                                   dbBaseGroup.action == 'view')

                if field:
                    results_cursor = results_cursor.join(dbPerspective.dictionaryperspectivetofield).filter(
                        dbPerspectiveToField.field == field)
                    if published_cursor:
                        published_cursor = published_cursor.join(
                            dbPerspective.dictionaryperspectivetofield).filter(
                            dbPerspectiveToField.field == field)

                entries = list()

                for item in results_cursor:
                    if item.parent_client_id==1125 and item.parent_object_id==29:
                        pass
                    if item.parent not in entries:
                        entries.append(item.parent)

                if published_cursor:
                    for item in published_cursor:
                        if item.parent not in entries:
                            entries.append(item.parent)

                lexes = list()
                for entry in entries:
                    if not entry.marked_for_deletion:
                        if (entry.parent_client_id, entry.parent_object_id) in dbPerspective.get_deleted():
                            continue
                        if (entry.parent_client_id, entry.parent_object_id) in dbPerspective.get_hidden():
                            continue
                        lexes.append(entry)

                lexes_composite_list = [(lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id)
                        for lex in lexes]

                entities = dbLexicalEntry.graphene_track_multiple(lexes_composite_list,
                                                           publish=search_in_published, accept=True)

                def graphene_entity(cur_entity, cur_publishing):
                    ent = Entity(id = (cur_entity.client_id, cur_entity.object_id))
                    ent.dbObject = cur_entity
                    ent.publishingentity = cur_publishing
                    return ent

                def graphene_obj(dbobj, cur_cls):
                    obj = cur_cls(id=(dbobj.client_id, dbobj.object_id))
                    obj.dbObject = dbobj
                    return obj

                entities = [graphene_entity(entity[0], entity[1]) for entity in entities]
                lexical_entries = [graphene_obj(lex, LexicalEntry) for lex in lexes]
                return LexicalEntriesAndEntities(entities=entities, lexical_entries=lexical_entries)


        raise ResponseError(message="Bad string")

    def resolve_advanced_lexicalentries(self, info, searchstrings, perspectives=None, adopted=None,
                                        adopted_type=None, with_etimology=None): #advanced_search() function

        """
        query EntriesList {
            advanced_lexicalentries(searchstrings: [{searchstring: "смотреть следить"}]) {
                id
                entities {
                     id
                     content
                }
            }
        }

        """
        request = info.context.get('request')

        if not perspectives:
            db_published_gist = translation_gist_search('Published')
            state_translation_gist_client_id = db_published_gist.client_id
            state_translation_gist_object_id = db_published_gist.object_id
            db_la_gist = translation_gist_search('Limited access')
            limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id

            perspectives = [(persp.client_id, persp.object_id) for persp in DBSession.query(dbPerspective).filter(
                dbPerspective.marked_for_deletion == False,
                or_(and_(dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id,
                         dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id),
                    and_(dbPerspective.state_translation_gist_client_id == limited_client_id,
                         dbPerspective.state_translation_gist_object_id == limited_object_id))).all()]

        def make_query(searchstring, perspectives):
            results_cursor = DBSession.query(dbLexicalEntry).join(dbEntity.parent) \
                .join(dbEntity.field).join(dbTranslationAtom,
                                         and_(dbField.translation_gist_client_id == dbTranslationAtom.parent_client_id,
                                              dbField.translation_gist_object_id == dbTranslationAtom.parent_object_id,
                                              dbField.marked_for_deletion == False)) \
                .distinct(dbEntity.parent_client_id, dbEntity.parent_object_id)
            if perspectives:
                results_cursor = results_cursor.filter(
                    tuple_(dbLexicalEntry.parent_client_id, dbLexicalEntry.parent_object_id).in_(perspectives))
            if not searchstring["searchstring"]:
                raise ResponseError(message="Error: bad argument 'searchstring'.")
            search_parts = searchstring["searchstring"].split()
            search_expression = dbEntity.content.like('%' + search_parts[0] + '%')
            to_do_or = searchstring.get('search_by_or', True)

            for part in search_parts[1:]:
                search_expression = or_(search_expression, dbEntity.content.like('%' + part + '%'))
            if 'entity_type' in searchstring and searchstring['entity_type']:
                search_expression = and_(search_expression, dbField.client_id == searchstring['entity_type'][0],
                                         dbField.object_id == searchstring['entity_type'][1])

            results_cursor = results_cursor.filter(search_expression)
            return results_cursor, to_do_or

        if not searchstrings[0]:
            raise ResponseError(message="Error: bad argument 'searchstrings'")

        results_cursor, to_do_or = make_query(searchstrings[0], perspectives)

        pre_results = set(results_cursor.all())
        if adopted:
            results_cursor = DBSession.query(dbLexicalEntry).join(dbEntity.parent).filter(
                dbEntity.content.like('%заим.%'))
            if adopted_type:
                results_cursor = results_cursor.join(dbEntity.field) \
                    .join(dbTranslationAtom,
                          and_(dbField.translation_gist_client_id == dbTranslationAtom.parent_client_id,
                               dbField.translation_gist_object_id == dbTranslationAtom.parent_object_id,
                               dbField.marked_for_deletion == False)) \
                    .filter(dbTranslationAtom.content == adopted_type,
                            dbTranslationAtom.locale_id == 2)
            pre_results = pre_results & set(results_cursor.all())
        if with_etimology:
            results_cursor = DBSession.query(dbLexicalEntry).join(dbEntity.parent).join(dbEntity.field) \
                .join(dbTranslationAtom,
                      and_(dbField.data_type_translation_gist_client_id == dbTranslationAtom.parent_client_id,
                           dbField.data_type_translation_gist_object_id == dbTranslationAtom.parent_object_id,
                           dbField.marked_for_deletion == False)) \
                .filter(dbTranslationAtom.content == 'Grouping Tag',
                        dbTranslationAtom.locale_id == 2)

        pre_results = pre_results & set(results_cursor.all())

        for search_string in searchstrings[1:]:
            results_cursor, to_do_or_new = make_query(search_string, perspectives)
            if to_do_or:
                pre_results = pre_results | set(results_cursor.all())
            else:
                pre_results = pre_results & set(results_cursor.all())
            to_do_or = to_do_or_new

        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in pre_results]

        lexical_entries = dbLexicalEntry.track_multiple(lexes_composite_list, int(request.cookies.get('locale_id') or 2),
                                              publish=True, accept=True)

        lexical_entries_list = list()
        for entry in lexical_entries:
            entities = []
            for ent in entry['contains']:
                del ent["contains"]
                del ent["level"]
                del ent["accepted"]
                del ent["published"]
                if "link_client_id" in ent and "link_object_id" in ent:
                    ent["link_id"] = (ent["link_client_id"], ent["link_object_id"])
                else:
                    ent["link_id"] = None
                ent["field_id"] = (ent["field_client_id"], ent["field_object_id"])
                if "self_client_id" in ent and "self_object_id" in ent:
                    ent["self_id"] = (ent["self_client_id"], ent["self_object_id"])
                else:
                    ent["self_id"] = None
                if "content" not in ent:
                    ent["content"] = None
                if "additional_metadata" in ent:
                    ent["additional_metadata_string"] = ent["additional_metadata"]
                    del ent["additional_metadata"]
                if 'entity_type' in ent:
                    del ent['entity_type']

                gr_entity_object = Entity(id=[ent['client_id'],
                                              ent['object_id']],
                                          # link_id = (ent["link_client_id"], ent["link_object_id"]),
                                          parent_id=(ent["parent_client_id"], ent["parent_object_id"]),
                                          **ent  # all other args from sub_result
                                          )
                entities.append(gr_entity_object)

            del entry["published"]
            del entry["contains"]
            del entry["level"]
            gr_lexicalentry_object = LexicalEntry(id=[entry['client_id'],
                                                      entry['object_id']],
                                                  entities=entities, **entry)

            lexical_entries_list.append(gr_lexicalentry_object)
        return lexical_entries_list

    # @client_id_check()
    def resolve_user_blobs(self, info, data_type=None, is_global=None):
        allowed_global_types = ["sociolinguistics", "pdf"]
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user_blobs = list()
        if not data_type and is_global:
            raise ResponseError("Error: cannot list globally without data_type")
        if data_type and is_global:
            if data_type in allowed_global_types:
                user_blobs = DBSession.query(dbUserBlobs).filter_by(marked_for_deletion=False, data_type=data_type).all()
            else:
                raise ResponseError(message="Error: you can not list that data type globally.")
        elif not client:
            raise ResponseError('not authenticated')
        if data_type:
            if not is_global:
                user_blobs = DBSession.query(dbUserBlobs).filter_by(marked_for_deletion=False, user_id=client.user_id, data_type=data_type).all()
        else:
            user_blobs = DBSession.query(dbUserBlobs).filter_by(marked_for_deletion=False, user_id=client.user_id).all()
        user_blobs_list = list()
        for db_blob in user_blobs:
            gql_blob = UserBlobs(id=[db_blob.client_id, db_blob.object_id])
            gql_blob.dbObject = db_blob
            user_blobs_list.append(gql_blob)
        return user_blobs_list

    def resolve_userrequest(self, info, id):
        """
        query myQuery {
          userrequest(id: 6) {
                id
           }
        }
        """
        return UserRequest(id=id)

    #@client_id_check()
    def resolve_userrequests(self, info):
        """
        query myQuery {
          userrequests {
                id
                sender_id
                type
           }
        }
        """
        client_id = info.context.get('client_id')

        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        userrequests = DBSession.query(dbUserRequest).filter(dbUserRequest.recipient_id == user.id).order_by(
            dbUserRequest.created_at).all()
        userrequests_list = list()
        for db_userrequest in userrequests:
            gql_userrequest = UserRequest(id=db_userrequest.id)
            userrequests_list.append(gql_userrequest)
        return userrequests_list

    def resolve_all_basegroups(self, info):  # tested
        basegroups = list()
        for basegroup_object in DBSession.query(dbBaseGroup).all():
            basegroup = BaseGroup(id=basegroup_object.id)
            basegroup.dbObject = basegroup_object
            basegroups.append(basegroup)
        return basegroups

    def resolve_grant(self, info, id):
        return Grant(id=id)

    def resolve_grants(self, info):
        """
        query myQuery {
          grants {
                id
           }
        }
        """
        grants = DBSession.query(dbGrant).order_by(dbGrant.grant_number).all()
        grants_list = list()
        for dbgrant in grants:
            grant =  Grant(id=dbgrant.id)
            grant.dbObject = dbgrant
            grants_list.append(grant)

        return grants_list

    def resolve_phonology_tier_list(self, info, perspective_id):
        """
        query MyQuery {
          phonology_tier_list(perspective_id: [330, 4]) {
            tier_count
            total_count
          }
        }
        """

        answer = utils_phonology_tier_list(*perspective_id)
        return TierList(**answer)

    def resolve_phonology_skip_list(self, info, perspective_id):
        """
        query MyQuery {
          phonology_skip_list(perspective_id: [1251, 14]) {
            markup_count
            neighbour_list
            skip_list
            total_neighbour_count
            total_skip_count
          }
        }
        """

        answer = utils_phonology_skip_list(*perspective_id)
        return SkipList(**answer)

    def resolve_phonology_link_perspective_data(self, info, perspective_id, field_id_list):
        """
        query MyQuery {
          phonology_link_perspective_data(
            perspective_id: [657, 4],
            field_id_list: [[1, 213]])
          {
            perspective_id_list
          }
        }
        """

        answer = gql_phonology_link_perspective_data(perspective_id, field_id_list)
        return Link_Perspective_Data(**answer)

    # def resolve_convert_starling(self, info, starling_dictionaries):
    #     """
    #     query myQuery {
    #         convert_starling(parent_id:[1,1] blob_id:[1,1] translation_atoms:[], add_etymology:true , field_map:{min_created_at:1})
    #     }
    #     """
    #     cache_kwargs = info.context["request"].registry.settings["cache_kwargs"]
    #     sqlalchemy_url = info.context["request"].registry.settings["sqlalchemy.url"]
    #     task_names = []
    #     for st_dict in starling_dictionaries:
    #         # TODO: fix
    #         task_names.append(st_dict.get("translation_atoms")[0].get("content"))
    #     name = ",".join(task_names)
    #     user_id = Client.get_user_by_client_id(info.context["client_id"]).id
    #     task = TaskStatus(user_id, "Starling dictionary conversion", name, 10)
    #     starling_converter.convert(info, starling_dictionaries, cache_kwargs, sqlalchemy_url, task.key)
    #     return True

    def resolve_connected_words(self, info, id, field_id, mode=None):
        response = list()
        client_id = id[0]
        object_id = id[1]
        field_client_id = field_id[0]
        field_object_id = field_id[1]
        if mode == 'all':
            publish = None
            accept = True
        elif mode == 'published':
            publish = True
            accept = True
        elif mode == 'not_accepted':
            publish = None
            accept = False
        elif mode == 'deleted':
            publish = None
            accept = None
        elif mode == 'all_with_deleted':
            publish = None
            accept = None
        else:
            raise ResponseError(message="mode: <all|published|not_accepted>")
        lexical_entry = DBSession.query(dbLexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
        if not lexical_entry or lexical_entry.marked_for_deletion:
            raise ResponseError(message="No such lexical entry in the system")
        tags = find_all_tags(lexical_entry, field_client_id, field_object_id, accept, publish)
        lexes = find_lexical_entries_by_tags(tags, field_client_id, field_object_id, accept, publish)
        lexes_composite_list = [(lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id)
                                for lex in lexes]
        entities = dbLexicalEntry.graphene_track_multiple(lexes_composite_list,
                                                   publish=publish, accept=accept)

        def graphene_entity(cur_entity, cur_publishing):
            ent = Entity(id = (cur_entity.client_id, cur_entity.object_id))
            ent.dbObject = cur_entity
            ent.publishingentity = cur_publishing
            return ent

        def graphene_obj(dbobj, cur_cls):
            obj = cur_cls(id=(dbobj.client_id, dbobj.object_id))
            obj.dbObject = dbobj
            return obj

        entities = [graphene_entity(entity[0], entity[1]) for entity in entities]
        lexical_entries = [graphene_obj(lex, LexicalEntry) for lex in lexes]
        return LexicalEntriesAndEntities(entities=entities, lexical_entries=lexical_entries)



    def resolve_eaf_wordlist(self, info, id):
        # TODO: delete
        import tempfile
        import pympi
        import sys
        import os
        import random
        import string
        import requests
        from sqlalchemy.exc import IntegrityError
        from lingvodoc.exceptions import CommonException
        from lingvodoc.scripts.convert_rules import praat_to_elan

        # TODO: permission check
        """
        query myQuery {
            convert_markup(id: [742, 5494] )
        }
        """
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()

        try:
            # out_type = req['out_type']
            client_id, object_id = id

            entity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
            if not entity:
                raise KeyError("No such file")
            resp = requests.get(entity.content)
            if not resp:
                raise ResponseError("Cannot access file")
            content = resp.content
            try:
                n = 10
                filename = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                                  for c in range(n))
                # extension = os.path.splitext(blob.content)[1]
                f = open(filename, 'wb')
            except Exception as e:
                return ResponseError(message=str(e))
            try:
                f.write(content)
                f.close()
                if os.path.getsize(filename) / (10 * 1024 * 1024.0) < 1:
                    if 'data_type' in entity.additional_metadata :
                        if 'praat' in entity.additional_metadata['data_type']:
                            textgrid_obj = pympi.TextGrid(file_path=filename)
                            eaf_obj = textgrid_obj.to_eaf()
                            word_list = eaf_words(eaf_obj)
                            return word_list
                            #elan = to_eaf("-",eafobj)

                        elif 'elan' in entity.additional_metadata['data_type']:
                            #with open(filename, 'r') as f:
                            #    return f.read()
                            eaf_obj = pympi.Eaf(file_path=filename)
                            word_list = eaf_words(eaf_obj)
                            return word_list
                        else:
                            raise KeyError("Not allowed convert option")
                        raise KeyError('File too big')
                    raise KeyError("Not allowed convert option")
                raise KeyError('File too big')
            except Exception as e:
                raise ResponseError(message=e)
            finally:
                os.remove(filename)
                pass
        except KeyError as e:
            raise ResponseError(message=str(e))

        except IntegrityError as e:
            raise ResponseError(message=str(e))

        except CommonException as e:
            raise ResponseError(message=str(e))


    def resolve_convert_markup(self, info, id):


        # TODO: permission check
        """
        query myQuery {
            convert_markup(id: [742, 5494] )
        }
        """
        # client_id = info.context.get('client_id')
        # client = DBSession.query(Client).filter_by(id=client_id).first()
        # user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        client_id, object_id = id
        entity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
        if not entity:
            raise KeyError("No such file")
        resp = requests.get(entity.content)
        if not resp:
            raise ResponseError("Cannot access file")
        content = resp.content
        return tgt_to_eaf(content, entity.additional_metadata)





class PerspectivesAndFields(graphene.InputObjectType):
    perspective_id = LingvodocID()
    field_id = LingvodocID()

class StarlingEtymologyObject(graphene.InputObjectType):
    starling_perspective_id = LingvodocID()
    perspectives_and_fields = graphene.List(PerspectivesAndFields)

class StarlingEtymology(graphene.Mutation):

    class Arguments:
        etymology_field_id = LingvodocID()
        complex_list = graphene.List(StarlingEtymologyObject)

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request

        client_id = info.context.get('client_id')

        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")
        if user.id != 1:
            raise ResponseError(message="not admin")

        etymology_field_id = args['etymology_field_id']
        etymology_field = DBSession.query(dbField).filter_by(client_id=etymology_field_id[0],
                                                             object_id=etymology_field_id[1],
                                                             marked_for_deletion=False).first()
        if not etymology_field:
            raise ResponseError(message='no such field')
        timestamp = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                for c in range(10))
        for complex_element in args['complex_list']:
            starling_ids = complex_element['starling_perspective_id']
            starling_perspective = DBSession.query(dbDictionaryPerspective).filter_by(client_id=starling_ids[0],
                                                                                      object_id=starling_ids[1],
                                                                                      marked_for_deletion=False).first()
            if not starling_perspective:
                raise ResponseError(message='no such starling perspective')
            for persp_and_field in complex_element['perspectives_and_fields']:
                persp_ids = persp_and_field['perspective_id']
                cur_persp = DBSession.query(dbDictionaryPerspective).filter_by(client_id=persp_ids[0],
                                                                               object_id=persp_ids[1],
                                                                               marked_for_deletion=False).first()
                field_id = persp_and_field['field_id']
                field = DBSession.query(dbField).filter_by(client_id=field_id[0],
                                                           object_id=field_id[1],
                                                           marked_for_deletion=False).first()
                if not cur_persp:
                    raise ResponseError(message='no such perspective')

                StarlingEntity = aliased(dbEntity)
                StarlingLexicalEntry = aliased(dbLexicalEntry)
                result = DBSession.query(dbEntity, dbLexicalEntry, StarlingEntity, StarlingLexicalEntry).filter(
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    StarlingEntity.parent_client_id == StarlingLexicalEntry.client_id,
                    StarlingEntity.parent_object_id == StarlingLexicalEntry.object_id,
                    dbLexicalEntry.parent_client_id == cur_persp.client_id,
                    dbLexicalEntry.parent_object_id == cur_persp.object_id,
                    StarlingLexicalEntry.parent_client_id == starling_perspective.client_id,
                    StarlingLexicalEntry.parent_object_id == starling_perspective.object_id,
                    dbEntity.content == StarlingEntity.content,
                    dbEntity.field == field).all()
                for sub_res in result:
                    first_lex = sub_res[1]
                    second_lex = sub_res[3]
                    tag = sub_res[0].content + timestamp
                    first_tag = dbEntity(client_id = client.id, parent=first_lex, content=tag, field=etymology_field)
                    first_tag.publishingentity.accepted = True
                    first_tag.publishingentity.published = True
                    DBSession.add(first_tag)
                    second_tag = dbEntity(client_id = client.id, parent=second_lex, content=tag, field=etymology_field)
                    second_tag.publishingentity.accepted = True
                    second_tag.publishingentity.published = True
                    DBSession.add(second_tag)

        return StarlingEtymology(triumph=True)


class PhonemicAnalysis(graphene.Mutation):

    class Arguments:
        perspective_id=LingvodocID(required=True)
        transcription_field_id=LingvodocID(required=True)
        translation_field_id=LingvodocID(required=True)

    triumph = graphene.Boolean()
    entity_count = graphene.Int()
    result = graphene.String()

    @staticmethod
    def mutate(self, info, **args):
        """
        mutation PhonemicAnalysis {
          phonemic_analysis(
            perspective_id: [70, 5],
            transcription_field_id: [66, 8],
            translation_field_id: [66, 10])
          {
            triumph
            entity_count
            result
          }
        }
        """

        perspective_cid, perspective_oid = args['perspective_id']

        transcription_field_cid, transcription_field_oid = args['transcription_field_id']
        translation_field_cid, translation_field_oid = args['translation_field_id']

        locale_id = info.context.get('locale_id') or 2

        __debug_flag__ = False

        try:

            perspective = DBSession.query(dbDictionaryPerspective).filter_by(
                client_id = perspective_cid, object_id = perspective_oid).first()

            perspective_name = perspective.get_translation(locale_id)
            dictionary_name = perspective.parent.get_translation(locale_id)

            # Showing phonemic analysis info, checking phonemic analysis library presence.

            log.debug(
                '\nphonemic_analysis {0}/{1}:'
                '\n  dictionary: {2}'
                '\n  perspective: {3}'
                '\n  transcription field: {4}/{5}'
                '\n  translation field: {6}/{7}'
                '\n  locale_id: {8}'
                '\n  phonemic_analysis_f: {9}'.format(
                    perspective_cid, perspective_oid,
                    repr(dictionary_name.strip()),
                    repr(perspective_name.strip()),
                    transcription_field_cid, transcription_field_oid,
                    translation_field_cid, translation_field_oid,
                    locale_id,
                    repr(phonemic_analysis_f)))

            if phonemic_analysis_f is None:

                return ResponseError(message =
                    'Analysis library is absent, please contact system administrator.')

            # Query for non-deleted, published and accepted entities of the specified perspective with the
            # specified field.

            dbTranslation = aliased(dbEntity, name = 'Translation')
            dbPublishingTranslation = aliased(dbPublishingEntity, name = 'PublishingTranslation')

            data_query = (

                DBSession.query(dbEntity).filter(
                    dbLexicalEntry.parent_client_id == perspective_cid,
                    dbLexicalEntry.parent_object_id == perspective_oid,
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.field_client_id == transcription_field_cid,
                    dbEntity.field_object_id == transcription_field_oid,
                    dbEntity.marked_for_deletion == False,
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True)

                .outerjoin(dbTranslation, and_(
                    dbTranslation.parent_client_id == dbEntity.parent_client_id,
                    dbTranslation.parent_object_id == dbEntity.parent_object_id,
                    dbTranslation.field_client_id == translation_field_cid,
                    dbTranslation.field_object_id == translation_field_oid,
                    dbTranslation.marked_for_deletion == False))

                .outerjoin(dbPublishingTranslation, and_(
                    dbPublishingTranslation.client_id == dbTranslation.client_id,
                    dbPublishingTranslation.object_id == dbTranslation.object_id,
                    dbPublishingTranslation.published == True,
                    dbPublishingTranslation.accepted == True))

                .add_columns(
                    func.array_agg(dbTranslation.content))

                .group_by(dbEntity))

            # Counting text entities we have. If we haven't got any, we return empty result.

            total_count = data_query.count()

            log.debug(
                'phonemic_analysis {0}/{1}: {2} transcription entities'.format(
                    perspective_cid, perspective_oid,
                    total_count,
                    transcription_field_cid, transcription_field_oid))

            if total_count <= 0:

                return PhonemicAnalysis(
                    triumph = True,
                    entity_count = total_count,
                    result = u'')

            # Otherwise we are going to perform phonemic analysis.

            data_list = [

                (entity.content,
                    translation_list[0] if translation_list else '')

                for entity, translation_list in data_query.all()
                if len(entity.content) > 0]

            if len(data_list) <= 0:

                return PhonemicAnalysis(
                    triumph = True,
                    entity_count = total_count,
                    result = u'No transcription entities with non-empty contents.')

            # Preparing analysis input.

            input = (
                '{0} - {1}\0\0'.format(dictionary_name, perspective_name) +

                ''.join(
                    '{0}\0{1}\0'.format(transcription, translation)
                    for transcription, translation in data_list))

            log.debug(
                'phonemic_analysis {0}/{1}: '
                'transcription field {2}/{3}, translation field {4}/{5}'
                '\ndata_list:\n{6}'
                '\ninput ({7} rows):\n{8}'.format(
                    perspective_cid, perspective_oid,
                    transcription_field_cid, transcription_field_oid,
                    translation_field_cid, translation_field_oid,
                    pprint.pformat(data_list, width = 108),
                    len(data_list) + 1,
                    pprint.pformat([input[i : i + 256]
                        for i in range(0, len(input), 256)], width = 144)))

            # Saving to a file, if required.

            if __debug_flag__:

                perspective = DBSession.query(dbDictionaryPerspective).filter_by(
                    client_id = perspective_cid, object_id = perspective_oid).first()

                perspective_name = perspective.get_translation(2)
                dictionary_name = perspective.parent.get_translation(2)

                input_file_name = (
                    'input phonemic {0} {1} {2}.utf16'.format(
                    dictionary_name.strip(),
                    perspective_name.strip(),
                    len(data_list) + 1))

                with open(input_file_name, 'wb') as input_file:
                    input_file.write(input.encode('utf-16'))

            # Calling analysis library, starting with getting required output buffer size and continuing
            # with analysis proper.

            output_buffer_size = phonemic_analysis_f(
                None, len(data_list) + 1, None, 0)

            if output_buffer_size <= 0:
                return ResponseError(message = 'Invalid output buffer size')

            log.debug(
                'phonemic_analysis {0}/{1}: output buffer size {2}'.format(
                perspective_cid, perspective_oid,
                output_buffer_size))

            input_buffer = ctypes.create_unicode_buffer(input)
            output_buffer = ctypes.create_unicode_buffer(output_buffer_size + 256)

            result = phonemic_analysis_f(
                input_buffer, len(data_list) + 1, output_buffer, 0)

            # If we don't have a good result, we return an error.

            log.debug(
                'phonemic_analysis {0}/{1}: '
                'transcription field {2}/{3}, translation field {4}/{5}: result {6}'.format(
                    perspective_cid, perspective_oid,
                    transcription_field_cid, transcription_field_oid,
                    translation_field_cid, translation_field_oid,
                    result))

            if result != 1:
                return ResponseError(message =
                    'Phonemic analysis library call error {0}'.format(result))

            output = output_buffer.value

            log.debug(
                'phonemic_analysis {0}/{1}: '
                'transcription field {2}/{3}, translation field {4}/{5}:'
                '\noutput:\n{6}'.format(
                    perspective_cid, perspective_oid,
                    transcription_field_cid, transcription_field_oid,
                    translation_field_cid, translation_field_oid,
                    repr(output)))

            # Reflowing output.

            line_list = output.split('\r\n')

            text_wrapper = textwrap.TextWrapper(
                width = 108, tabsize = 4)

            reflow_list = []

            for line in line_list:
                reflow_list.extend(text_wrapper.wrap(line))

            wrapped_output = '\n'.join(reflow_list)

            log.debug(
                'phonemic_analysis {0}/{1}: '
                'transcription field {2}/{3}, translation field {4}/{5}:'
                '\nwrapped output:\n{6}'.format(
                    perspective_cid, perspective_oid,
                    transcription_field_cid, transcription_field_oid,
                    translation_field_cid, translation_field_oid,
                    wrapped_output))

            # Returning result.

            return PhonemicAnalysis(
                triumph = True,
                entity_count = total_count,
                result = wrapped_output)

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('phonemic_analysis: exception')
            log.debug(traceback_string)

            return ResponseError(message =
                'Exception:\n' + traceback_string)


@celery.task
def async_cognate_analysis(
    base_language_id,
    language_name,
    group_field_id,
    perspective_info_list,
    mode,
    locale_id,
    storage,
    task_key,
    cache_kwargs,
    sqlalchemy_url,
    __debug_flag__):
    """
    Sets up and launches cognate analysis in asynchronous mode.
    """

    # NOTE: copied from phonology.
    #
    # This is a no-op with current settings, we use it to enable logging inside celery tasks, because
    # somehow this does it, and otherwise we couldn't set it up.

    logging.debug('async_cognate_analysis')

    # Ok, and now we go on with task execution.

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)
    initialize_cache(cache_kwargs)

    task_status = TaskStatus.get_from_cache(task_key)

    with transaction.manager:

        try:
            CognateAnalysis.perform_cognate_analysis(
                base_language_id,
                language_name,
                group_field_id,
                perspective_info_list,
                mode,
                locale_id,
                storage,
                task_status,
                __debug_flag__)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug(
                'cognate_analysis {0}/{1}: exception'.format(
                *base_language_id))

            log.debug(traceback_string)

            if task_status is not None:

                task_status.set(5, 100,
                    'Finished (ERROR), exception:\n' + traceback_string)


class CognateAnalysis(graphene.Mutation):

    class Arguments:
        base_language_id=LingvodocID(required=True)
        group_field_id=LingvodocID(required=True)
        perspective_info_list=graphene.List(graphene.List(LingvodocID), required=True)
        mode=graphene.String()

    triumph = graphene.Boolean()
    dictionary_count = graphene.Int()
    group_count = graphene.Int()
    not_enough_count = graphene.Int()
    transcription_count = graphene.Int()
    translation_count = graphene.Int()
    result = graphene.String()
    xlsx_url = graphene.String()

    @staticmethod
    def tag_data_std(
        entry_already_set,
        group_list,
        perspective_id,
        field_client_id,
        field_object_id):
        """
        Gets lexical entry grouping data using current standard methods, computes elapsed time.
        """

        start_time = time.time()

        tag_data_list = (DBSession.query(
            dbLexicalEntry, func.count('*'))

            .filter(
                dbLexicalEntry.parent_client_id == perspective_id[0],
                dbLexicalEntry.parent_object_id == perspective_id[1],
                dbLexicalEntry.marked_for_deletion == False,
                dbEntity.parent_client_id == dbLexicalEntry.client_id,
                dbEntity.parent_object_id == dbLexicalEntry.object_id,
                dbEntity.field_client_id == field_client_id,
                dbEntity.field_object_id == field_object_id,
                dbEntity.marked_for_deletion == False,
                dbPublishingEntity.client_id == dbEntity.client_id,
                dbPublishingEntity.object_id == dbEntity.object_id,
                dbPublishingEntity.published == True,
                dbPublishingEntity.accepted == True)

            .group_by(
                dbLexicalEntry.client_id,
                dbLexicalEntry.object_id))

        # Processing each lexical entry with at least one tag.

        for entry, count in tag_data_list.all():

            if (entry.client_id, entry.object_id) in entry_already_set:
                continue

            tag_set = find_all_tags(
                entry, field_client_id, field_object_id, True, True)

            entry_list = find_lexical_entries_by_tags(
                tag_set, field_client_id, field_object_id, True, True)

            entry_id_set = set(
                (tag_entry.client_id, tag_entry.object_id)
                for tag_entry in entry_list)

            entry_already_set.update(entry_id_set)
            group_list.append(entry_id_set)

        return time.time() - start_time

    @staticmethod
    def find_group(
        entry_client_id,
        entry_object_id,
        field_client_id,
        field_object_id):
        """
        Retrieves all lexical entries grouped with a given id-specified entry.
        """

        entry_id_set = set((
            (entry_client_id, entry_object_id),))

        tag_query = (

            DBSession.query(
                dbEntity.content)

            .filter(
                dbEntity.parent_client_id == entry_client_id,
                dbEntity.parent_object_id == entry_object_id,
                dbEntity.field_client_id == field_client_id,
                dbEntity.field_object_id == field_object_id,
                dbEntity.marked_for_deletion == False,
                dbPublishingEntity.client_id == dbEntity.client_id,
                dbPublishingEntity.object_id == dbEntity.object_id,
                dbPublishingEntity.published == True,
                dbPublishingEntity.accepted == True))

        tag_list = list(tag_query.all())
        tag_set = set(tag_list)

        # While we have tags we don't have all lexical entries for,
        # we get these all entries of these tags...

        while tag_list:

            entry_id_query = (

                DBSession.query(
                    dbLexicalEntry.client_id,
                    dbLexicalEntry.object_id)

                .filter(
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.field_client_id == field_client_id,
                    dbEntity.field_object_id == field_object_id,
                    dbEntity.marked_for_deletion == False,
                    dbEntity.content.in_(tag_list),
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True))

            entry_id_list = []

            for entry_id in entry_id_query.all():
                if entry_id not in entry_id_set:

                    entry_id_set.add(entry_id)
                    entry_id_list.append(entry_id)

            # And then get all tags for entries we haven't already done it for.

            tag_query = (

                DBSession.query(
                    dbEntity.content)

                .filter(
                    tuple_(dbEntity.parent_client_id, dbEntity.parent_object_id)
                        .in_(entry_id_list),
                    dbEntity.field_client_id == field_client_id,
                    dbEntity.field_object_id == field_object_id,
                    dbEntity.marked_for_deletion == False,
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True))

            tag_list = []

            for tag in tag_query.all():
                if tag not in tag_set:

                    tag_set.add(tag)
                    tag_list.append(tag)

        return entry_id_set

    @staticmethod
    def tag_data_optimized(
        entry_already_set,
        group_list,
        perspective_id,
        field_client_id,
        field_object_id):
        """
        Gets lexical entry grouping data using (hopefully) optimized version of the current standard
        methods, computes elapsed time.
        """

        start_time = time.time()

        tag_data_list = (

            DBSession.query(
                dbLexicalEntry.client_id,
                dbLexicalEntry.object_id,
                func.count('*'))

            .filter(
                dbLexicalEntry.parent_client_id == perspective_id[0],
                dbLexicalEntry.parent_object_id == perspective_id[1],
                dbLexicalEntry.marked_for_deletion == False,
                dbEntity.parent_client_id == dbLexicalEntry.client_id,
                dbEntity.parent_object_id == dbLexicalEntry.object_id,
                dbEntity.field_client_id == field_client_id,
                dbEntity.field_object_id == field_object_id,
                dbEntity.marked_for_deletion == False,
                dbPublishingEntity.client_id == dbEntity.client_id,
                dbPublishingEntity.object_id == dbEntity.object_id,
                dbPublishingEntity.published == True,
                dbPublishingEntity.accepted == True)

            .group_by(
                dbLexicalEntry.client_id,
                dbLexicalEntry.object_id))

        # Processing each lexical entry with at least one tag.

        for entry_client_id, entry_object_id, count in tag_data_list.all():

            if (entry_client_id, entry_object_id) in entry_already_set:
                continue

            entry_id_set = CognateAnalysis.find_group(
                entry_client_id, entry_object_id,
                field_client_id, field_object_id)

            entry_already_set.update(entry_id_set)
            group_list.append(entry_id_set)

        return time.time() - start_time

    @staticmethod
    def tag_data_aggregated(
        perspective_info_list,
        tag_field_id,
        statistics_flag = False,
        optimize_flag = False):
        """
        Gets lexical entry grouping data using aggregated retrieval, computes elapsed time.
        """

        start_time = time.time()

        entry_id_dict = collections.defaultdict(set)
        tag_dict = collections.defaultdict(set)

        tag_set = set()

        # All tags for tagged lexical entries in specified perspectives.

        for perspective_id, transcription_field_id, translation_field_id in perspective_info_list:

            tag_query = (

                DBSession.query(
                    dbEntity.parent_client_id,
                    dbEntity.parent_object_id,
                    dbEntity.content)

                .filter(
                    dbLexicalEntry.parent_client_id == perspective_id[0],
                    dbLexicalEntry.parent_object_id == perspective_id[1],
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.field_client_id == tag_field_id[0],
                    dbEntity.field_object_id == tag_field_id[1],
                    dbEntity.marked_for_deletion == False,
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True))

            for entry_client_id, entry_object_id, tag in tag_query.all():

                entry_id_dict[(entry_client_id, entry_object_id)].add(tag)
                tag_set.add(tag)

        tag_list = tag_set

        # While we have tags we don't have all lexical entries for,
        # we get all entries of these tags...

        while tag_list:

            entry_id_query = (

                DBSession.query(
                    dbEntity.parent_client_id,
                    dbEntity.parent_object_id,
                    dbEntity.content)

                .filter(
                    dbLexicalEntry.marked_for_deletion == False,
                    dbEntity.parent_client_id == dbLexicalEntry.client_id,
                    dbEntity.parent_object_id == dbLexicalEntry.object_id,
                    dbEntity.field_client_id == tag_field_id[0],
                    dbEntity.field_object_id == tag_field_id[1],
                    dbEntity.marked_for_deletion == False,
                    dbEntity.content.in_(tag_list),
                    dbPublishingEntity.client_id == dbEntity.client_id,
                    dbPublishingEntity.object_id == dbEntity.object_id,
                    dbPublishingEntity.published == True,
                    dbPublishingEntity.accepted == True))

            entry_id_list = []

            for entry_client_id, entry_object_id, tag in entry_id_query.all():

                entry_id = entry_client_id, entry_object_id
                tag_dict[tag].add(entry_id)

                if entry_id not in entry_id_dict:
                    entry_id_list.append(entry_id)

            # And then get all tags for entries we haven't already done it for.

            tag_list = []

            entry_id_list.sort()
            log.debug('len(entry_id_list): {0}'.format(len(entry_id_list)))

            for i in range((len(entry_id_list) + 16383) // 16384):

                tag_query = (

                    DBSession.query(
                        dbEntity.parent_client_id,
                        dbEntity.parent_object_id,
                        dbEntity.content)

                    # We have to split entries into parts due to the danger of stack overflow in Postgres.

                    .filter(
                        tuple_(dbEntity.parent_client_id, dbEntity.parent_object_id)
                            .in_(entry_id_list[i * 16384 : (i + 1) * 16384]),
                        dbEntity.field_client_id == tag_field_id[0],
                        dbEntity.field_object_id == tag_field_id[1],
                        dbEntity.marked_for_deletion == False,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True))

                for entry_client_id, entry_object_id, tag in tag_query.all():

                    entry_id = entry_client_id, entry_object_id
                    entry_id_dict[entry_id].add(tag)

                    if tag not in tag_dict:
                        tag_list.append(tag)

        # And now grouping lexical entries by tags.

        entry_already_set = set()
        group_list = []

        for entry_id, entry_tag_set in entry_id_dict.items():

            if entry_id in entry_already_set:
                continue

            entry_already_set.add(entry_id)

            group_entry_id_set = set((entry_id,))
            group_tag_set = set(entry_tag_set)

            current_tag_list = entry_tag_set

            # Recursively gathering grouped entries through their tags.

            while current_tag_list:

                tag_list = []

                for current_tag in current_tag_list:
                    for current_entry_id in tag_dict[current_tag]:

                        if current_entry_id in group_entry_id_set:
                            continue

                        group_entry_id_set.add(current_entry_id)

                        for tag in entry_id_dict[current_entry_id]:
                            if tag not in group_tag_set:

                                group_tag_set.add(tag)
                                tag_list.append(tag)

                current_tag_list = tag_list

            # Saving entry group data.

            entry_already_set.update(group_entry_id_set)
            group_list.append(group_entry_id_set)

        # Computing tag statistics for each entry group, if required.

        if statistics_flag:

            redundant_group_count = 0
            redundant_tag_count = 0
            redundant_entity_count = 0

            redundant_group_tag_count = 0
            redundant_group_entry_count = 0
            redundant_group_entity_count = 0

            delta_entity_count = 0

            # Processing each entry group.

            for entry_id_set in group_list:

                tag_set = set.union(
                    *(entry_id_dict[entry_id]
                        for entry_id in entry_id_set))

                tag_list = list(sorted(
                    (tag, len(tag_dict[tag]))
                        for tag in tag_set))

                partial_tag_set = set((tag_list[0][0],))
                partial_entry_id_set = set(tag_dict[tag_list[0][0]])

                index = 1

                # How many partial tag groups we need to cover the entry group completely?

                while (
                    len(partial_entry_id_set) < len(entry_id_set) and
                    index < len(tag_list)):

                    partial_tag_set.add(tag_list[index][0])
                    partial_entry_id_set.update(tag_dict[tag_list[index][0]])

                    index += 1

                group_entity_count = (

                    sum(len(tag_dict[tag])
                        for tag in tag_set))

                # Checking if we have some redundant partial tag groups.

                if index < len(tag_list):

                    redundant_group_count += 1
                    redundant_tag_count += len(tag_list) - index

                    for tag, count in tag_list[index:]:
                        redundant_entity_count += count

                    redundant_group_tag_count += len(tag_list)
                    redundant_group_entry_count += len(entry_id_set)

                    redundant_group_entity_count += group_entity_count

                delta_entity_count += group_entity_count - len(entry_id_set)

            # Showing gathered statistics.

            log.debug(
                '\ngroup_count: {0}/{1}, with {2} tags, {3} entries, {4} entities'
                '\ntag_count: {5}/{6}, {5}/{7} among redundant groups'
                '\nentity_count: {8}/{9}, {8}/{10} among redundant groups'
                '\ndelta(entity): {11}, minimum(entity): {12}'.format(
                    redundant_group_count, len(group_list),
                    redundant_group_tag_count,
                    redundant_group_entry_count,
                    redundant_group_entity_count,
                    redundant_tag_count, len(tag_dict),
                    redundant_group_tag_count,
                    redundant_entity_count,
                    sum(len(entry_id_set)
                        for entry_id_set in tag_dict.values()),
                    redundant_group_entity_count,
                    delta_entity_count,
                    len(entry_id_dict)))

        # If required, optimizing lexical entry groups by ensuring that each group has exactly one tag.

        if optimize_flag:

            redundant_tag_list = []

            for entry_id_set in group_list:

                tag_set = set.union(
                    *(entry_id_dict[entry_id]
                        for entry_id in entry_id_set))

                count, tag = max(
                    (len(tag_dict[tag]), tag)
                    for tag in tag_set)

                # Creating tag entities we need to link current group via selected tag.

                for entry_id in entry_id_set - tag_dict[tag]:

                    tag_entity = dbEntity(
                        client_id = entry_id[0],
                        parent_client_id = entry_id[0],
                        parent_object_id = entry_id[1],
                        field_client_id = tag_field_id[0],
                        field_object_id = tag_field_id[1],
                        content = tag)

                    tag_entity.publishingentity.published = True
                    tag_entity.publishingentity.accepted = True

                tag_set.remove(tag)
                redundant_tag_list.extend(tag_set)

            # Removing tag entities of the redundant tags.

            entity_id_query = (

                dbEntity.__table__
                    .update()
                    .where(and_(
                        dbEntity.marked_for_deletion == False,
                        dbEntity.content.in_(redundant_tag_list),
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True))
                    .values(marked_for_deletion = True)
                    .returning(dbEntity.client_id, dbEntity.object_id))

            entity_id_list = list(
                entity_id_query.execute())

            log.debug('entity_id_list: {0} entities\n{1}'.format(
                len(entity_id_list), pprint.pformat(entity_id_list)))

            # Optimization is not fully implemented at the moment.

            raise NotImplementedError

        return entry_already_set, group_list, time.time() - start_time

    @staticmethod
    def export_xlsx(
        base_language_id,
        mode,
        output_str,
        __debug_flag__ = False):
        """
        Parses results of the cognate analysis and exports them as an XLSX file.
        """

        workbook_stream = io.BytesIO()

        workbook = xlsxwriter.Workbook(workbook_stream, {'in_memory': True})
        worksheet_results = workbook.add_worksheet('Results')

        index = output_str.find('\0')
        size_list = list(map(int, output_str[:index].split(',')))

        log.debug(
            'cognate_analysis {0}/{1}: result table size {2}'.format(
            base_language_id[0], base_language_id[1],
            size_list))

        max_width = 0
        row_count = 0

        def export_table(table_index, table_str, n_col, n_row):
            """
            Parses from the binary output and exports to the XLSX workbook a table with specified width and
            height.
            """

            nonlocal index

            nonlocal max_width
            nonlocal row_count

            if n_col > max_width:

                max_width = n_col
                worksheet_results.set_column(0, max_width - 1, 16)

            row_list = []

            for i in range(n_row):

                value_list = []

                # Another row of analysis result values.

                for j in range(n_col):

                    index_next = output_str.find('\0', index + 1)
                    value = output_str[index + 1 : index_next]

                    value_list.append(value)
                    index = index_next

                split_list_list = [
                    value.split('|') for value in value_list]

                item_list_count = max(map(len, split_list_list))

                # Some values may actually be sequences, so we check and process them if they are.

                for i in range(item_list_count):

                    item_list = [
                        split_list[i] if i < len(split_list) else ''
                        for split_list in split_list_list]

                    row_list.append(item_list)

                    worksheet_results.write_row(
                        'A{0}'.format(row_count + 1),
                        item_list)

                    row_count += 1

                # Going on another row of analysis results.

                if output_str[index + 1] != '\0':
                    raise NotImplementedError

                index += 1

            log.debug(
                'cognate_analysis {0}/{1}: {2} table {3}:\n{4}'.format(
                base_language_id[0], base_language_id[1],
                table_str, table_index,
                pprint.pformat(row_list, width = 144)))

            # Returning table data.

            return row_list

        # Getting analysis result info, exporting it to the XLSX workbook.

        for table_index, howmany in enumerate(range(len(size_list) // 2)):

            n_col, n_row = size_list[howmany * 2 : howmany * 2 + 2]
            export_table(table_index, 'result', n_col, n_row)

        # And now we parse formant plot data, if we have any.

        if len(output_str) > index + 1:

            if output_str[index + 1] != '\0':
                raise NotImplementedError

            index += 1
            index_next = output_str.find('\0', index + 1)

            size_list = list(map(int,
                output_str[index + 1 : index_next].split(',')))

            index = index_next

            log.debug(
                'cognate_analysis {0}/{1}: plot table size {2}'.format(
                base_language_id[0], base_language_id[1],
                size_list))

            # Getting plot info, exporting it to the XLSX workbook, generating plots.
        
            worksheet_table_2d = workbook.add_worksheet('F-table')
            worksheet_chart = workbook.add_worksheet('F-chart')

            table_2d_row_index = 0
            chart_2d_count = 0

            for table_index, howmany in enumerate(range(len(size_list) // 2)):

                n_col, n_row = size_list[howmany * 2 : howmany * 2 + 2]

                row_list = export_table(
                    table_index, 'plot', n_col, n_row)

                plot_title = row_list[0][0]
                
                if not plot_title:
                    continue

                # Getting formant series info.

                series_title_list = []
                series_data_list = []

                for row in row_list[1:]:

                    if not row[0]:
                        continue

                    elif not row[1]:

                        series_title_list.append(row[0])
                        series_data_list.append([])

                    else:

                        series_data_list[-1].append(
                            tuple(map(float, row[1:])))

                log.debug(
                    'cognate_analysis {0}/{1}: plot data {2}:\n{3}\n{4}\n{5}'.format(
                    base_language_id[0], base_language_id[1],
                    table_index,
                    repr(plot_title),
                    pprint.pformat(series_title_list, width = 144),
                    pprint.pformat(series_data_list, width = 144)))

                # Proceeding with plot generation only if we have enough data.

                if sum(map(len, series_data_list)) <= 1:
                    continue

                chart_data_2d_list = []

                min_2d_f1, max_2d_f1 = None, None
                min_2d_f2, max_2d_f2 = None, None

                # Generating plot data.

                for series_index, (series_title, series_data) in enumerate(
                    zip(series_title_list, series_data_list)):

                    f_2d_list = list(map(
                        lambda f_tuple: numpy.array(f_tuple[:2]), series_data))

                    f_3d_list = list(map(
                        numpy.array, series_data))

                    if len(f_2d_list) <= 0:
                        continue

                    (filtered_2d_list, outlier_2d_list, mean_2d, ellipse_list,
                        filtered_3d_list, outlier_3d_list, mean_3d, sigma_2d, inverse_3d) = (

                        phonology.chart_data(f_2d_list, f_3d_list))

                    chart_data_2d_list.append((
                        len(filtered_2d_list), len(f_2d_list), series_title,
                        filtered_2d_list, outlier_2d_list, mean_2d, ellipse_list))

                    # Updating F1/F2 maximum/minimum info.

                    f1_list, f2_list = zip(*filtered_2d_list)

                    min_f1_list, max_f1_list = min(f1_list), max(f1_list)
                    min_f2_list, max_f2_list = min(f2_list), max(f2_list)

                    if min_2d_f1 == None or min_f1_list < min_2d_f1:
                        min_2d_f1 = min_f1_list

                    if max_2d_f1 == None or max_f1_list > max_2d_f1:
                        max_2d_f1 = max_f1_list

                    if min_2d_f2 == None or min_f2_list < min_2d_f2:
                        min_2d_f2 = min_f2_list

                    if max_2d_f2 == None or max_f2_list > max_2d_f2:
                        max_2d_f2 = max_f2_list

                # Compiling info of the formant scatter chart data series.

                chart_dict_list, table_2d_row_index = (
                    
                    phonology.chart_definition_list(
                        chart_data_2d_list, worksheet_table_2d,
                        min_2d_f1, max_2d_f1, min_2d_f2, max_2d_f2,
                        row_index = table_2d_row_index))

                if chart_dict_list:

                    # Generating the chart, if we have any data.

                    chart = workbook.add_chart({'type': 'scatter'})

                    chart.set_title({
                        'name': plot_title})

                    chart.set_x_axis({
                        'major_gridlines': {'visible': True},
                        'name': 'F2 (Hz)',
                        'reverse': True})

                    chart.set_y_axis({
                        'major_gridlines': {'visible': True},
                        'name': 'F1 (Hz)',
                        'reverse': True})

                    chart.set_legend({
                        'position': 'top'})

                    for chart_dict in chart_dict_list:
                        chart.add_series(chart_dict)

                    chart.set_style(11)
                    chart.set_size({'width': 1024, 'height': 768})

                    worksheet_chart.insert_chart(
                        'A{0}'.format(chart_2d_count * 40 + 1), chart)

                    chart_2d_count += 1

        workbook.close()

        # Saving resulting Excel workbook for debug purposes, if required.

        if __debug_flag__:

            language = DBSession.query(dbLanguage).filter_by(
                client_id = base_language_id[0], object_id = base_language_id[1]).first()

            xlsx_file_name = (
                'cognate{0} {1} {2} {3}.xlsx'.format(
                ' acoustic' if mode == 'acoustic' else '',
                language.get_translation(2),
                *base_language_id))

            workbook_stream.seek(0)

            with open(xlsx_file_name, 'wb') as xlsx_file:
                shutil.copyfileobj(workbook_stream, xlsx_file)

        return workbook_stream

    @staticmethod
    def acoustic_data(
        base_language_id,
        sound_entity_id,
        sound_url,
        markup_entity_id,
        markup_url,
        storage,
        __debug_flag__):
        """
        Extracts acoustic data from a pair of sound recording and its markup, using cache in a manner
        compatible with phonological analysis.
        """

        log_str = (
            'cognate_analysis {0}/{1}: sound entity {2}/{3}, markup entity {4}/{5}'.format(
                base_language_id[0], base_language_id[1],
                sound_entity_id[0], sound_entity_id[1],
                markup_entity_id[0], markup_entity_id[1]))

        log.debug(
            '{0}\nsound_url: {1}\nmarkup_url: {2}'.format(
            log_str, sound_url, markup_url))

        # Checking if we have already cached sound/markup analysis result.

        cache_key = 'phonology:{0}:{1}:{2}:{3}'.format(
            sound_entity_id[0], sound_entity_id[1],
            markup_entity_id[0], markup_entity_id[1])

        cache_result = caching.CACHE.get(cache_key)

        if cache_result == 'no_vowel':

            log.debug('{0} [CACHE {1}]: no vowel'.format(
                log_str, cache_key))

            return None

        # Cached exception result.

        elif (isinstance(cache_result, tuple) and
            cache_result[0] == 'exception'):

            exception, traceback_string = cache_result[1:3]

            log.debug(
                '{0} [CACHE {1}]: exception'.format(
                log_str, cache_key))

            log.debug(traceback_string)

            return None

        # We have a cached analysis result.

        elif cache_result:

            textgrid_result_list = cache_result

            log.debug(
                '{0} [CACHE {1}]:\n{2}'.format(
                log_str, cache_key,
                format_textgrid_result(
                    [None], textgrid_result_list)))

        # Ok, we don't have a cached result, so we are going to perform sound/markup analysis.

        else:

            try:

                storage_f = (
                    as_storage_file if __debug_flag__ else storage_file)

                sound_bytes = None

                # Getting markup, checking if we have a tier that needs to be processed.

                with storage_f(storage, markup_url) as markup_stream:
                    markup_bytes = markup_stream.read()

                try:
                    textgrid = pympi.Praat.TextGrid(xmax = 0)

                    textgrid.from_file(
                        io.BytesIO(markup_bytes),
                        codec = chardet.detect(markup_bytes)['encoding'])

                except:

                    # If we failed to parse TextGrid markup, we assume that sound and markup files
                    # were accidentally swapped and try again.

                    sound_bytes = markup_bytes
                    markup_url, sound_url = sound_url, markup_url

                    with storage_f(storage, markup_url) as markup_stream:
                        markup_bytes = markup_stream.read()

                    textgrid = pympi.Praat.TextGrid(xmax = 0)

                    textgrid.from_file(
                        io.BytesIO(markup_bytes),
                        codec = chardet.detect(markup_bytes)['encoding'])

                # Processing markup, getting info we need.

                tier_data_list, vowel_flag = process_textgrid(textgrid)

                log.debug(
                    '{0}:\ntier_data_list:\n{1}\nvowel_flag: {2}'.format(
                    log_str,
                    pprint.pformat(tier_data_list, width = 144),
                    vowel_flag))

                if not vowel_flag:

                    log.debug('{0}: no vowel'.format(log_str))
                    caching.CACHE.set(cache_key, 'no_vowel')

                    return None

                # Ok, we have usable markup, and now we retrieve the sound file to analyze it.

                extension = os.path.splitext(
                    urllib.parse.urlparse(sound_url).path)[1]

                sound = None
                with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

                    if sound_bytes is None:

                        with storage_f(storage, sound_url) as sound_stream:
                            sound_bytes = sound_stream.read()

                    temp_file.write(sound_bytes)
                    temp_file.flush()

                    sound = AudioPraatLike(pydub.AudioSegment.from_file(temp_file.name))

                # Analysing sound, showing and caching analysis results.

                textgrid_result_list = process_sound(
                    tier_data_list, sound)

                log.debug(
                    '{0}:\n{1}'.format(
                    log_str,
                    format_textgrid_result(
                        [None], textgrid_result_list)))

                caching.CACHE.set(cache_key, textgrid_result_list)

            # We have exception during sound/markup analysis, we save its info in the cache.

            except Exception as exception:

                traceback_string = ''.join(traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1]

                log.debug('{0}: exception'.format(log_str))
                log.debug(traceback_string)

                caching.CACHE.set(cache_key, ('exception', exception,
                    traceback_string.replace('Traceback', 'CACHEd traceback')))

                return None

        # Ok, now we have sound/markup analysis results, we extract info of the first vowel from the first
        # vowel-containing tier.

        def f():

            for tier_index, tier_name, tier_result_list in textgrid_result_list:

                if (tier_result_list == 'no_vowel' or
                    tier_result_list == 'no_vowel_selected'):
                    continue

                for tier_result in tier_result_list:

                    for (interval_str, interval_r_length, f_list,
                        sign_longest, sign_highest, source_index) in tier_result.interval_data_list:

                        interval_str_list = interval_str.split()

                        return [interval_str.split()[0], interval_str.split()[-3]] + f_list[:3]

        # Showing what we've finally got and returning it.

        result = f()

        log.debug(
            '{0}: {1}'.format(
            log_str, result))

        return result

    @staticmethod
    def perform_cognate_analysis(
        base_language_id,
        language_name,
        group_field_id,
        perspective_info_list,
        mode,
        locale_id,
        storage,
        task_status = None,
        __debug_flag__ = False):
        """
        Performs cognate analysis in either synchronous or asynchronous mode.
        """

        if task_status is not None:
            task_status.set(1, 0, 'Gathering grouping data')

        # Gathering entry grouping data.

        perspective_dict = collections.defaultdict(dict)

        entry_already_set = set()
        group_list = []

        tag_dict = collections.defaultdict(set)
        text_dict = {}

        if not __debug_flag__:

            entry_already_set, group_list, group_time = (

                CognateAnalysis.tag_data_aggregated(
                    perspective_info_list, group_field_id))

        else:

            # If we are in debug mode, we try to load existing tag data to reduce debugging time.

            tag_data_digest = hashlib.md5(

                repr(list(group_field_id) +
                    [perspective_info[0] for perspective_info in perspective_info_list])

                    .encode('utf-8')).hexdigest()

            tag_data_file_name = \
                '__tag_data_{0}_{1}_{2}__.gz'.format(
                    base_language_id[0], base_language_id[1], tag_data_digest)

            import pickle

            if os.path.exists(tag_data_file_name):

                with gzip.open(tag_data_file_name, 'rb') as tag_data_file:
                    entry_already_set, group_list, group_time = pickle.load(tag_data_file)

            else:

                # Don't have existing data, so we gather it and then save it for later use.

                entry_already_set, group_list, group_time = (

                    CognateAnalysis.tag_data_aggregated(
                        perspective_info_list, group_field_id))

                with gzip.open(tag_data_file_name, 'wb') as tag_data_file:
                    pickle.dump((entry_already_set, group_list, group_time), tag_data_file)

        log.debug(
            'cognate_analysis {0}/{1}: {2} entries, {3} groups, {4:.2f}s elapsed time'.format(
            base_language_id[0], base_language_id[1],
            len(entry_already_set),
            len(group_list),
            group_time))

        if task_status is not None:
            task_status.set(2, 5, 'Gathering analysis source data')

        # Getting text data for each perspective.

        dbTranslation = aliased(dbEntity, name = 'Translation')
        dbSound = aliased(dbEntity, name = 'Sound')
        dbMarkup = aliased(dbEntity, name = 'Markup')

        dbPublishingTranslation = aliased(dbPublishingEntity, name = 'PublishingTranslation')
        dbPublishingSound = aliased(dbPublishingEntity, name = 'PublishingSound')
        dbPublishingMarkup = aliased(dbPublishingEntity, name = 'PublishingMarkup')

        for index, (perspective_id, transcription_field_id, translation_field_id) in \
            enumerate(perspective_info_list):

            # Getting and showing perspective info.

            perspective = DBSession.query(dbDictionaryPerspective).filter_by(
                client_id = perspective_id[0], object_id = perspective_id[1]).first()

            perspective_name = perspective.get_translation(locale_id)
            dictionary_name = perspective.parent.get_translation(locale_id)

            perspective_dict[perspective_id]['perspective_name'] = perspective_name
            perspective_dict[perspective_id]['dictionary_name'] = dictionary_name

            log.debug(
                '\ncognate_analysis {0}/{1}:'
                '\n  dictionary {2}/{3}: {4}'
                '\n  perspective {5}/{6}: {7}'.format(
                base_language_id[0], base_language_id[1],
                perspective.parent_client_id, perspective.parent_object_id,
                repr(dictionary_name.strip()),
                perspective_id[0], perspective_id[1],
                repr(perspective_name.strip())))

            # Getting text data.

            transcription_query = (

                DBSession.query(
                    dbLexicalEntry.client_id,
                    dbLexicalEntry.object_id).filter(
                        dbLexicalEntry.parent_client_id == perspective_id[0],
                        dbLexicalEntry.parent_object_id == perspective_id[1],
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbEntity.field_client_id == transcription_field_id[0],
                        dbEntity.field_object_id == transcription_field_id[1],
                        dbEntity.marked_for_deletion == False,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True)

                .add_columns(
                    func.array_agg(dbEntity.content).label('transcription'))

                .group_by(dbLexicalEntry)).subquery()

            translation_query = (

                DBSession.query(
                    dbLexicalEntry.client_id,
                    dbLexicalEntry.object_id).filter(
                        dbLexicalEntry.parent_client_id == perspective_id[0],
                        dbLexicalEntry.parent_object_id == perspective_id[1],
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbEntity.field_client_id == translation_field_id[0],
                        dbEntity.field_object_id == translation_field_id[1],
                        dbEntity.marked_for_deletion == False,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True)

                .add_columns(
                    func.array_agg(dbEntity.content).label('translation'))

                .group_by(dbLexicalEntry)).subquery()

            # Main query for transcription/translation data.

            data_query = (
                DBSession.query(transcription_query)

                .outerjoin(translation_query, and_(
                    transcription_query.c.client_id == translation_query.c.client_id,
                    transcription_query.c.object_id == translation_query.c.object_id))

                .add_columns(
                    translation_query.c.translation))

            # If we need to do an acoustic analysis, we also get sound/markup data.

            if mode == 'acoustic':

                sound_markup_query = (

                    DBSession.query(
                        dbLexicalEntry.client_id,
                        dbLexicalEntry.object_id).filter(
                            dbLexicalEntry.parent_client_id == perspective_id[0],
                            dbLexicalEntry.parent_object_id == perspective_id[1],
                            dbLexicalEntry.marked_for_deletion == False,
                            dbMarkup.parent_client_id == dbLexicalEntry.client_id,
                            dbMarkup.parent_object_id == dbLexicalEntry.object_id,
                            dbMarkup.marked_for_deletion == False,
                            dbMarkup.additional_metadata.contains({'data_type': 'praat markup'}),
                            dbPublishingMarkup.client_id == dbMarkup.client_id,
                            dbPublishingMarkup.object_id == dbMarkup.object_id,
                            dbPublishingMarkup.published == True,
                            dbPublishingMarkup.accepted == True,
                            dbSound.client_id == dbMarkup.self_client_id,
                            dbSound.object_id == dbMarkup.self_object_id,
                            dbSound.marked_for_deletion == False,
                            dbPublishingSound.client_id == dbSound.client_id,
                            dbPublishingSound.object_id == dbSound.object_id,
                            dbPublishingSound.published == True,
                            dbPublishingSound.accepted == True)

                    .add_columns(

                        func.jsonb_agg(func.jsonb_build_array(
                            dbSound.client_id, dbSound.object_id, dbSound.content,
                            dbMarkup.client_id, dbMarkup.object_id, dbMarkup.content))

                        .label('sound_markup'))

                    .group_by(dbLexicalEntry)).subquery()

                # Adding sound/markup retrieval to the main query.

                data_query = (
                    data_query

                    .outerjoin(sound_markup_query, and_(
                        transcription_query.c.client_id == sound_markup_query.c.client_id,
                        transcription_query.c.object_id == sound_markup_query.c.object_id))

                    .add_columns(
                        sound_markup_query.c.sound_markup))

            # If we are in asynchronous mode, we need to look up how many data rows we need
            # to process for this perspective.

            if task_status is not None:

                row_count = data_query.count()

                log.debug(
                    'cognate_analysis {0}/{1}: perspective {2}/{3}: {4} data rows'.format(
                    base_language_id[0], base_language_id[1],
                    perspective_id[0], perspective_id[1],
                    row_count))

            # Grouping transcriptions and translations by lexical entries.

            for row_index, row in enumerate(data_query.all()):

                entry_id = tuple(row[:2])
                transcription_list, translation_list = row[2:4]

                transcription_list = (
                    [] if not transcription_list else [
                        transcription.strip()
                        for transcription in transcription_list
                        if transcription.strip()])

                # If we have no trascriptions for this lexical entry, we skip it altogether.

                if not transcription_list:
                    continue

                translation_list = (
                    [] if not translation_list else [
                        translation.strip()
                        for translation in translation_list
                        if translation.strip()])

                # If we are fetching additional acoustic data, it's possible we have to process
                # sound recordings and markup this lexical entry has.

                if len(row) > 4 and row[4]:

                    row_list = row[4][0]

                    result = (
                        CognateAnalysis.acoustic_data(
                            base_language_id,
                            tuple(row_list[0:2]), row_list[2],
                            tuple(row_list[3:5]), row_list[5],
                            storage,
                            __debug_flag__))

                    # Updating task progress, if required.

                    if task_status is not None:

                        percent = int(math.floor(90.0 *
                            (index + float(row_index + 1) / row_count) /
                            len(perspective_info_list)))

                        task_status.set(2, 5 + percent, 'Gathering analysis source data')

                    entry_data_list = (index,
                        transcription_list,
                        translation_list,
                        result)

                # No additional acoustic data.

                else:
                    entry_data_list = (index, transcription_list, translation_list)

                text_dict[entry_id] = entry_data_list

        if task_status is not None:
            task_status.set(3, 95, 'Performing analysis')

        # Ok, and now we form the source data for analysis.

        result_list = [[]]
        perspective_list = []

        for perspective_id, transcription_field_id, translation_field_id in perspective_info_list:

            perspective_data = perspective_dict[perspective_id]

            perspective_str = '{0} - {1}'.format(
                perspective_data['dictionary_name'],
                perspective_data['perspective_name'])

            perspective_list.append(perspective_str)
            result_list[0].extend([perspective_str, ''])

        log.debug('\n' +
            pprint.pformat(perspective_list, width = 108))

        # Each group of lexical entries.

        not_enough_count = 0

        total_transcription_count = 0
        total_translation_count = 0

        for entry_id_set in group_list:

            group_transcription_list = [[]
                for i in range(len(perspective_info_list))]

            group_translation_list = [[]
                for i in range(len(perspective_info_list))]

            group_acoustic_list = [None
                for i in range(len(perspective_info_list))]

            transcription_count = 0
            translation_count = 0

            for entry_id in entry_id_set:

                if entry_id not in text_dict:
                    continue

                # Processing text data of each entry of the group.

                entry_data_list = text_dict[entry_id]
                index, transcription_list, translation_list = entry_data_list[:3]

                group_transcription_list[index].extend(transcription_list)
                group_translation_list[index].extend(translation_list)

                transcription_count += len(transcription_list)
                translation_count += len(translation_list)

                if (len(entry_data_list) > 3 and
                    entry_data_list[3] and
                    group_acoustic_list[index] is None):

                    group_acoustic_list[index] = entry_data_list[3]

            # Dropping groups with transcriptions from no more than a single dictionary.

            if sum(min(1, len(transcription_list))
                for transcription_list in group_transcription_list) <= 1:

                not_enough_count += 1
                continue

            total_transcription_count += transcription_count
            total_translation_count += translation_count

            result_list.append([])

            group_zipper = zip(
                group_transcription_list,
                group_translation_list,
                group_acoustic_list)

            for transcription_list, translation_list, acoustic_list in group_zipper:

                result_list[-1].append('|'.join(transcription_list))
                result_list[-1].append('|'.join(translation_list))

                if mode == 'acoustic':
                    result_list[-1].extend(acoustic_list or ['', '', '', '', ''])

        # Showing what we've gathered.

        log.debug(
            '\ncognate_analysis {0}/{1}:'
            '\n  len(group_list): {2}'
            '\n  len(result_list): {3}'
            '\n  not_enough_count: {4}'
            '\n  transcription_count: {5}'
            '\n  translation_count: {6}'
            '\n  result_list:\n{7}'.format(
                base_language_id[0], base_language_id[1],
                len(group_list),
                len(result_list),
                not_enough_count,
                total_transcription_count,
                total_translation_count,
                pprint.pformat(result_list, width = 108)))

        # If we have no data at all, we return empty result.

        if len(result_list) <= 1:

            return CognateAnalysis(
                triumph = True,
                dictionary_count = len(perspective_info_list),
                group_count = len(group_list),
                not_enough_count = not_enough_count,
                transcription_count = total_transcription_count,
                translation_count = total_translation_count,
                result = '',
                xlsx_url = '')

        analysis_f = (
            cognate_acoustic_analysis_f if mode == 'acoustic' else
            cognate_analysis_f)

        # Preparing analysis input.

        input = ''.join(
            ''.join(text + '\0' for text in text_list)
            for text_list in result_list)

        log.debug(
            '\ncognate_analysis {0}/{1}:'
            '\nanalysis_f: {2}'
            '\ninput ({3} columns, {4} rows):\n{5}'.format(
                base_language_id[0], base_language_id[1],
                repr(analysis_f),
                len(perspective_info_list),
                len(result_list),
                pprint.pformat([input[i : i + 256]
                    for i in range(0, len(input), 256)], width = 144)))

        # Saving input to a file, if required.

        if __debug_flag__:

            input_file_name = (
                'input cognate{0} {1} {2} {3}.utf16'.format(
                ' acoustic' if mode == 'acoustic' else '',
                language_name.strip(),
                len(perspective_info_list),
                len(result_list)))

            with open(input_file_name, 'wb') as input_file:
                input_file.write(input.encode('utf-16'))

        # Calling analysis library, starting with getting required output buffer size and continuing
        # with analysis proper.

        output_buffer_size = analysis_f(
            None, len(perspective_info_list), len(result_list), None, 1)

        log.debug(
            'cognate_analysis {0}/{1}: output buffer size {2}'.format(
            base_language_id[0], base_language_id[1],
            output_buffer_size))

        input_buffer = ctypes.create_unicode_buffer(input)
        output_buffer = ctypes.create_unicode_buffer(output_buffer_size + 256)

        result = analysis_f(
            input_buffer, len(perspective_info_list), len(result_list), output_buffer, 1)

        # If we don't have a good result, we return an error.

        log.debug(
            'cognate_analysis {0}/{1}: result {2}'.format(
            base_language_id[0], base_language_id[1],
            result))

        if result <= 0:

            if task_status is not None:

                task_status.set(5, 100,
                    'Finished (ERROR): library call error {0}'.format(result))

            return ResponseError(message =
                'Cognate analysis library call error {0}'.format(result))

        output = output_buffer.value

        log.debug(
            'cognate_analysis {0}/{1}:\noutput:\n{2}'.format(
            base_language_id[0], base_language_id[1],
            pprint.pformat([output[i : i + 256]
                for i in range(0, len(output), 256)], width = 144)))

        # Reflowing output.

        line_list = output.split('\r\n')

        text_wrapper = textwrap.TextWrapper(
            width = max(196, len(perspective_info_list) * 40), tabsize = 20)

        reflow_list = []

        for line in line_list:
            reflow_list.extend(text_wrapper.wrap(line))

        wrapped_output = '\n'.join(reflow_list)

        log.debug(
            'cognate_analysis {0}/{1}:\nwrapped output:\n{2}'.format(
            base_language_id[0], base_language_id[1],
            wrapped_output))

        # Getting binary output for parsing and exporting.

        result_binary = analysis_f(
            input_buffer, len(perspective_info_list), len(result_list), output_buffer, 2)

        log.debug(
            'cognate_analysis {0}/{1}: result_binary {2}'.format(
            base_language_id[0], base_language_id[1],
            result_binary))

        if result <= 0:

            if task_status is not None:

                task_status.set(5, 100,
                    'Finished (ERROR): library call (binary) error {0}'.format(result_binary))

            return ResponseError(message =
                'Cognate analysis library call (binary) error {0}'.format(result_binary))

        # Showing what we've got from the binary output call, indicating task's final stage, if required.

        output_binary = output_buffer[:result_binary]

        log.debug(
            'cognate_analysis {0}/{1}:\noutput_binary:\n{2}'.format(
            base_language_id[0], base_language_id[1],
            pprint.pformat([output_binary[i : i + 256]
                for i in range(0, len(output_binary), 256)], width = 144)))

        if task_status is not None:
            task_status.set(4, 99, 'Exporting analysis results to XLSX')

        # Parsing analysis results and exporting them as an Excel file.

        workbook_stream = CognateAnalysis.export_xlsx(
            base_language_id, mode, output_binary, __debug_flag__)

        current_datetime = datetime.datetime.now(datetime.timezone.utc)

        xlsx_filename = pathvalidate.sanitize_filename(
            '{0} cognate{1} analysis {2:04d}.{3:02d}.{4:02d}.xlsx'.format(
                language_name[:64],
                ' acoustic' if mode == 'acoustic' else '',
                current_datetime.year,
                current_datetime.month,
                current_datetime.day))

        cur_time = time.time()

        storage_dir = os.path.join(storage['path'], 'cognate', str(cur_time))

        # Storing Excel file with the results.

        xlsx_path = os.path.join(storage_dir, xlsx_filename)
        os.makedirs(os.path.dirname(xlsx_path), exist_ok = True)

        workbook_stream.seek(0)

        with open(xlsx_path, 'wb') as xlsx_file:
            shutil.copyfileobj(workbook_stream, xlsx_file)

        xlsx_url = ''.join([
            storage['prefix'], storage['static_route'],
            'cognate', '/', str(cur_time), '/', xlsx_filename])

        if task_status is not None:
            task_status.set(5, 100, 'Finished', result_link = xlsx_url)

        # Returning result.

        return CognateAnalysis(
            triumph = True,
            dictionary_count = len(perspective_info_list),
            group_count = len(group_list),
            not_enough_count = not_enough_count,
            transcription_count = total_transcription_count,
            translation_count = total_translation_count,
            result = wrapped_output,
            xlsx_url = xlsx_url)

    @staticmethod
    def mutate(self, info, **args):
        """
        mutation CognateAnalysis {
          cognate_analysis(
            base_language_id: [],
            group_field_id: [66, 25],
            perspective_info_list: [[[70, 5], [66, 8]]])
          {
            triumph
            entity_count
            dictionary_count
            group_count
            not_enough_count
            text_count
            result
          }
        }
        """

        base_language_id = args['base_language_id']

        group_field_id = args['group_field_id']
        perspective_info_list = args['perspective_info_list']

        mode = args.get('mode')

        __debug_flag__ = False

        try:

            # Getting base language info.

            locale_id = info.context.get('locale_id') or 2

            language = DBSession.query(dbLanguage).filter_by(
                client_id = base_language_id[0], object_id = base_language_id[1]).first()

            language_name = language.get_translation(locale_id)

            request = info.context.request
            storage = request.registry.settings['storage']

            # Showing cognate analysis info, checking cognate analysis library presence.

            log.debug(
                 '\ncognate_analysis {0}/{1}:'
                 '\n  language: {2}'
                 '\n  group field: {3}/{4}'
                 '\n  perspectives and transcription/translation fields: {5}'
                 '\n  mode: {6}'
                 '\n  cognate_analysis_f: {7}'
                 '\n  cognate_acoustic_analysis_f: {8}'.format(
                    base_language_id[0], base_language_id[1],
                    repr(language_name.strip()),
                    group_field_id[0], group_field_id[1],
                    perspective_info_list,
                    repr(mode),
                    repr(cognate_analysis_f),
                    repr(cognate_acoustic_analysis_f)))

            # Checking if we have analysis function ready.

            analysis_f = (
                cognate_acoustic_analysis_f if mode == 'acoustic' else
                cognate_analysis_f)

            if analysis_f is None:

                return ResponseError(message =
                    'Analysis library fuction \'{0}()\' is absent, '
                    'please contact system administrator.'.format(
                        'CognateAcousticAnalysis_GetAllOutput' if mode == 'acoustic' else
                        'CognateAnalysis_GetAllOutput'))

            perspective_info_list = [

                (tuple(perspective_id),
                    tuple(transcription_field_id),
                    tuple(translation_field_id))

                for perspective_id,
                    transcription_field_id,
                    translation_field_id in perspective_info_list]

            # If we are to use acoustic data, we will launch cognate analysis in asynchronous mode.

            if mode == 'acoustic':

                client_id = request.authenticated_userid

                user_id = (
                    Client.get_user_by_client_id(client_id).id
                        if client_id else anonymous_userid(request))

                task_status = TaskStatus(
                    user_id, 'Cognate acoustic analysis', language_name, 5)

                # Launching cognate acoustic analysis asynchronously.

                request.response.status = HTTPOk.code

                async_cognate_analysis.delay(
                    base_language_id,
                    language_name,
                    group_field_id,
                    perspective_info_list,
                    mode,
                    locale_id,
                    storage,
                    task_status.key,
                    request.registry.settings['cache_kwargs'],
                    request.registry.settings['sqlalchemy.url'],
                    __debug_flag__)

                # Signifying that we've successfully launched asynchronous cognate acoustic analysis.

                return CognateAnalysis(triumph = True)

            # We do not use acoustic data, so we perform cognate analysis synchronously.

            else:

                return CognateAnalysis.perform_cognate_analysis(
                    base_language_id,
                    language_name,
                    group_field_id,
                    perspective_info_list,
                    mode,
                    locale_id,
                    storage,
                    None,
                    __debug_flag__)

        # Exception occured while we tried to perform cognate analysis.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug(
                'cognate_analysis {0}/{1}: exception'.format(
                *base_language_id))

            log.debug(traceback_string)

            return ResponseError(message =
                'Exception:\n' + traceback_string)


class Phonology(graphene.Mutation):

    class Arguments:
        perspective_id=LingvodocID(required=True)
        limit=graphene.Int()
        limit_exception=graphene.Int()
        limit_no_vowel=graphene.Int()
        limit_result=graphene.Int()
        group_by_description=graphene.Boolean(required=True)
        maybe_translation_field=LingvodocID()
        only_first_translation=graphene.Boolean(required=True)
        vowel_selection=graphene.Boolean(required=True)
        maybe_tier_list=graphene.List(graphene.String)
        keep_list=graphene.List(graphene.Int)
        join_list=graphene.List(graphene.Int)
        chart_threshold=graphene.Int()
        generate_csv=graphene.Boolean()
        link_field_list=graphene.List(LingvodocID)
        link_perspective_list=graphene.List(graphene.List(LingvodocID))
        synchronous=graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    # @client_id_check()

    def mutate(self, info, **args):
        """
        query MyQuery {
          phonology(
            perspective_id: [126, 5],
            group_by_description: false,
            only_first_translation: false,
            vowel_selection: false,
            maybe_tier_list: [],
            maybe_translation_field: [66, 19])
        }
        """

        parameters = Phonology_Parameters.from_graphql(args)

        locale_id = info.context.get('locale_id')
        request = info.context.get('request')

        utils_phonology(request, locale_id, parameters)

        return Phonology(triumph=True)


class SoundAndMarkup(graphene.Mutation):

    class Arguments:
        perspective_id = LingvodocID(required = True)
        published_mode = graphene.String(required = True)

    triumph = graphene.Boolean()

    def mutate(self, info, **args):
        """
        query MyQuery {
          sound_and_markup(
            perspective_id: [657, 4])
        }
        """

        locale_id = info.context.get('locale_id')
        request = info.context.get('request')

        gql_sound_and_markup(request, locale_id, args['perspective_id'], args['published_mode'])

        return SoundAndMarkup(triumph = True)


def save_dictionary(dict_id, request, user_id, locale_id, publish):
    my_args = dict()
    my_args["client_id"] = dict_id[0]
    my_args["object_id"] = dict_id[1]
    my_args["locale_id"] = locale_id
    my_args["storage"] = request.registry.settings["storage"]
    my_args['sqlalchemy_url'] = request.registry.settings["sqlalchemy.url"]
    try:
        dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=dict_id[0],
                                                                 object_id=dict_id[1]).first()
        gist = DBSession.query(dbTranslationGist). \
            filter_by(client_id=dictionary_obj.translation_gist_client_id,
                      object_id=dictionary_obj.translation_gist_object_id).first()
        dict_name = gist.get_translation(locale_id)
        task = TaskStatus(user_id, "Saving dictionary", dict_name, 4)
    except:
        raise ResponseError('bad request')
    my_args['dict_name'] = dict_name
    my_args["task_key"] = task.key
    my_args["cache_kwargs"] = request.registry.settings["cache_kwargs"]
    my_args["published"] = publish
    res = async_save_dictionary.delay(**my_args)
    return


class SaveDictionary(graphene.Mutation):

    class Arguments:
        id = LingvodocID(required=True)
        mode = graphene.String(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    # @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 2)
        dict_id = args['id']
        mode = args['mode']
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        user_id = user.id

        dictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=dict_id[0],
                                                               object_id=dict_id[1]).first()
        if mode == 'published':
            publish = True
        elif mode == 'all':
            publish = None
        else:
            raise ResponseError(message="mode: <all|published>")

        for persp in dictionary_obj.dictionaryperspective:
            if mode == 'all':
                info.context.acl_check('view', 'lexical_entries_and_entities',
                                   (persp.client_id, persp.object_id))

        save_dictionary(dict_id, request, user_id, locale_id, publish)

        return DownloadDictionary(triumph=True)

class SaveAllDictionaries(graphene.Mutation):

    class Arguments:
        mode = graphene.String(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    # @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 2)
        mode = args['mode']
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        user_id = user.id
        if user_id != 1:
            raise ResponseError(message="not admin")
        # counter = 0
        dictionaries = DBSession.query(dbDictionary).filter_by(marked_for_deletion=False).all()
        if mode == 'published':
            publish = True
        elif mode == 'all':
            publish = None

        else:
            raise ResponseError(message="mode: <all|published>")
        for dictionary in dictionaries:
            save_dictionary([dictionary.client_id, dictionary.object_id], request, user_id, locale_id, publish)
            # if not counter % 5:
            #     time.sleep(5)
            # counter += 1

        return DownloadDictionary(triumph=True)


class MoveColumn(graphene.Mutation):
    class Arguments:
        perspective_id = LingvodocID(required=True)
        from_id = LingvodocID(required=True)
        to_id = LingvodocID(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    # @client_id_check()
    def mutate(root, info, **args):
        request = info.context.request
        locale_id = int(request.cookies.get('locale_id') or 2)
        perspective_id = args['perspective_id']
        from_id = args['from_id']
        to_id = args['to_id']
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        user_id = user.id
        client_ids = DBSession.query(Client.id).filter(Client.user_id==user_id).all()
        # if user_id != 1:
        #     raise ResponseError(message="not admin")
        # counter = 0
        perspective = DBSession.query(dbDictionaryPerspective).filter_by(client_id=perspective_id[0],
                                                                         object_id=perspective_id[1],
                                                                         marked_for_deletion=False).first()
        if not perspective:
            raise ResponseError('No such perspective')
        info.context.acl_check('view', 'lexical_entries_and_entities',
                           (perspective.client_id, perspective.object_id))

        lexes = DBSession.query(dbLexicalEntry).join(dbEntity).join(dbPublishingEntity).filter(
            dbLexicalEntry.parent_client_id == perspective_id[0],
            dbLexicalEntry.parent_object_id == perspective_id[1],
            dbLexicalEntry.marked_for_deletion == False,
            dbEntity.client_id.in_(client_ids),
            dbEntity.field_client_id == from_id[0],
            dbEntity.field_object_id == from_id[1],
            dbEntity.marked_for_deletion == False,
            dbPublishingEntity.accepted == True).all()

        for lex in lexes:
            entities = DBSession.query(dbEntity).join(dbPublishingEntity).filter(
                dbEntity.client_id.in_(client_ids),
                dbEntity.parent_client_id == lex.client_id,
                dbEntity.parent_object_id == lex.object_id,
                dbEntity.field_client_id == from_id[0],
                dbEntity.field_object_id == from_id[1],
                dbEntity.marked_for_deletion == False,
                dbPublishingEntity.accepted == True).all()
            for entity in entities:
                existing = DBSession.query(dbEntity).join(dbPublishingEntity).filter(
                    dbEntity.parent_client_id == lex.client_id,
                    dbEntity.parent_object_id == lex.object_id,
                    dbEntity.field_client_id == to_id[0],
                    dbEntity.field_object_id == to_id[1],
                    dbEntity.marked_for_deletion == False,
                    dbPublishingEntity.accepted == True,
                    dbEntity.content == entity.content).first()
                if not existing:
                    self_id = None
                    if entity.self_client_id and entity.self_object_id:
                        self_id = [entity.self_client_id, entity.self_object_id]
                    link_id = None
                    if entity.link_client_id and entity.link_object_id:
                        link_id = [entity.link_client_id, entity.link_object_id]
                    create_entity(id=[client.id, None],
                                  parent_id=[lex.client_id, lex.object_id],
                                  field_id=to_id,
                                  self_id=self_id,
                                  additional_metadata=entity.additional_metadata,
                                  link_id=link_id,
                                  locale_id=entity.locale_id,
                                  filename=None,
                                  content=entity.content,
                                  registry=None,
                                  request=request,
                                  )
                entity.marked_for_deletion = True

        return MoveColumn(triumph=True)



class MyMutations(graphene.ObjectType):
    """
    Mutation classes.
    It may be replaced by
    create_field = gql_field.CreateField.Field()
    for more beautiful imports
    """
    convert_starling = starling_converter.GqlStarling.Field()#graphene.Field(starling_converter.GqlStarling,  starling_dictionaries=graphene.List(StarlingDictionary))
    convert_dialeqt = ConvertDictionary.Field()
    convert_corpus = ConvertFiveTiers.Field()
    create_field = CreateField.Field()
    # update_field = UpdateField.Field()
    # delete_field = DeleteField.Field()
    create_entity = CreateEntity.Field()
    update_entity = UpdateEntity.Field()
    delete_entity = DeleteEntity.Field()
    update_entity_content = UpdateEntityContent.Field()
    approve_all_for_user = ApproveAllForUser.Field()
    bulk_create_entity = BulkCreateEntity.Field()
    create_user = CreateUser.Field()
    update_user = UpdateUser.Field()
    activate_deactivate_user = ActivateDeactivateUser.Field();
    create_language = CreateLanguage.Field()
    update_language = UpdateLanguage.Field()
    update_language_atom = UpdateLanguageAtom.Field()
    move_language = MoveLanguage.Field()
    delete_language = DeleteLanguage.Field()
    create_dictionary = CreateDictionary.Field()
    update_dictionary = UpdateDictionary.Field()
    update_dictionary_status = UpdateDictionaryStatus.Field()
    update_dictionary_atom = UpdateDictionaryAtom.Field()
    add_dictionary_roles = AddDictionaryRoles.Field()
    delete_dictionary_roles = DeleteDictionaryRoles.Field()
    delete_dictionary = DeleteDictionary.Field()
    create_organization = CreateOrganization.Field()
    update_organization = UpdateOrganization.Field()
    #delete_organization = DeleteOrganization.Field()
    create_translationatom = CreateTranslationAtom.Field()
    update_translationatom = UpdateTranslationAtom.Field()
    delete_translationatom = DeleteTranslationAtom.Field()
    create_translationgist = CreateTranslationGist.Field()
    delete_translationgist = DeleteTranslationGist.Field()
    create_lexicalentry = CreateLexicalEntry.Field()
    delete_lexicalentry = DeleteLexicalEntry.Field()
    bulk_delete_lexicalentry = BulkDeleteLexicalEntry.Field()
    bulk_create_lexicalentry = BulkCreateLexicalEntry.Field()
    join_lexical_entry_group = ConnectLexicalEntries.Field()
    leave_lexical_entry_group = DeleteGroupingTags.Field()
    create_perspective = CreateDictionaryPerspective.Field()
    update_perspective = UpdateDictionaryPerspective.Field()
    update_perspective_status = UpdatePerspectiveStatus.Field()
    update_perspective_atom = UpdatePerspectiveAtom.Field()
    add_perspective_roles = AddPerspectiveRoles.Field()
    delete_perspective_roles = DeletePerspectiveRoles.Field()
    delete_perspective = DeleteDictionaryPerspective.Field()
    create_column = CreateColumn.Field()
    update_column = UpdateColumn.Field()
    delete_column = DeleteColumn.Field()
    create_grant = CreateGrant.Field()
    update_grant = UpdateGrant.Field()
    # delete_grant = DeleteGrant.Field()
    create_userblob = CreateUserBlob.Field()
    delete_userblob = DeleteUserBlob.Field()
    create_grant_permission = CreateGrantPermission.Field()
    add_dictionary_to_grant = AddDictionaryToGrant.Field()
    administrate_org = AdministrateOrg.Field()
    participate_org = ParticipateOrg.Field()
    accept_userrequest = AcceptUserRequest.Field()
    #delete_userrequest = DeleteUserRequest.Field()
    download_dictionary = DownloadDictionary.Field()
    save_dictionary = SaveDictionary.Field()
    save_all_dictionaries = SaveAllDictionaries.Field()
    download_dictionaries = DownloadDictionaries.Field()
    synchronize = Synchronize.Field()
    delete_task = DeleteTask.Field()
    starling_etymology = StarlingEtymology.Field()
    phonemic_analysis = PhonemicAnalysis.Field()
    cognate_analysis = CognateAnalysis.Field()
    phonology = Phonology.Field()
    sound_and_markup = SoundAndMarkup.Field()
    merge_bulk = MergeBulk.Field()
    move_column = MoveColumn.Field()

schema = graphene.Schema(query=Query, auto_camelcase=False, mutation=MyMutations)

class Context(dict):
    """
    Context for graphene query execution, works as dict for arbitrary key-value associations and supports
    ACL-based permission checking.
    """

    def __init__(self, context_dict):
        """
        Initializes query execution context by initializing context key-value dictionary and, hopefully,
        getting client id and request data.
        """

        dict.__init__(self, context_dict)

        self.client_id = context_dict.get('client_id')
        self.request = context_dict.get('request')
        self.locale_id = context_dict.get('locale_id')
        self.headers = context_dict.get('headers')
        self.cookies = context_dict.get('cookies')

        self.cache = {}

    def acl_check_if(self, action, subject, subject_id):
        """
        Checks if the client has permission to perform given action on a specified subject via ACL.
        """
        if type(subject_id) is list:
            subject_id = tuple(subject_id)

        if (action, subject, subject_id) in self.cache:
            return self.cache[(action, subject, subject_id)]

        result = acl.check_direct(self.client_id, self.request, action, subject, subject_id)
        self.cache[(action, subject, subject_id)] = result

        return result

    def acl_check(self, action, subject, subject_id):
        """
        Checks if the client has permission to perform given action on a specified subject via ACL, raises
        permission exception otherwise.
        """

        if not self.acl_check_if(action, subject, subject_id):
            raise PermissionException(self.client_id, action, subject, subject_id)

    def acl_check_with_id_if(self, action, subject, args):
        """
        Checks via ACL if the client has permission to perform given action on a specified subject, with
        subject identifier extracted from query execution arguments.
        """

        return self.acl_check_if(action, subject, args.get('id'))
