import collections
import copy
import ctypes
import itertools
import logging
import pprint
import textwrap
import time
import traceback

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
    DeleteDictionary
)

from lingvodoc.schema.gql_search import AdvancedSearch

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
    MoveLanguage
)
from lingvodoc.schema.gql_merge import MergeBulk
from lingvodoc.schema.gql_dictionaryperspective import (
    DictionaryPerspective,
    CreateDictionaryPerspective,
    UpdateDictionaryPerspective,
    UpdatePerspectiveStatus,
    AddPerspectiveRoles,
    DeletePerspectiveRoles,
    DeleteDictionaryPerspective,
)
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
    tuple_
)
from lingvodoc.views.v2.utils import (
    view_field_from_object,
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
from lingvodoc.cache.caching import TaskStatus

from lingvodoc.views.v2.phonology import Phonology_Parameters
from lingvodoc.views.v2.utils import anonymous_userid

from sqlite3 import connect
from lingvodoc.utils.merge import merge_suggestions
import tempfile
from lingvodoc.views.v2.save_dictionary.core import async_save_dictionary
import json

RUSSIAN_LOCALE = 1
ENGLISH_LOCALE = 2

from pyramid.httpexceptions import (
    HTTPError
)

from lingvodoc.scripts import elan_parser
from lingvodoc.utils.creation import create_entity


# Setting up logging.
log = logging.getLogger(__name__)


# Mikhail Oslon's analysis functions.

try:
    liboslon = ctypes.CDLL('liboslon.so')

    phonemic_analysis_f = liboslon.PhonemicAnalysis_GetAllOutput
    cognate_analysis_f = liboslon.CognateAnalysis_GetAllOutput

except:
    phonemic_analysis_f = None
    cognate_analysis_f = None


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
    all_fields = graphene.List(Field)
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
        def get_sorted_metadata_keys(dictionary_metadata, metadata_name):
            authors = [x[0].get(metadata_name) for x in dictionary_metadata if x[0] != None]
            authors_set = set()
            for author_list in authors:
                if author_list:
                    for author in author_list:
                        authors_set.add(author)
            authors_list = sorted(list(authors_set))
            return authors_list

        menu_json_data = {}
        dictionary_metadata = DBSession.query(dbDictionary.additional_metadata).filter(dbDictionary.marked_for_deletion==False,
                                                                           dbDictionary.additional_metadata!={}).all()
        authors_list = get_sorted_metadata_keys(dictionary_metadata, "authors")
        #menu_json_data["hasAudio"] = [0,1]
        menu_json_data["authors"] = authors_list
        menu_json_data["humanSettlement"] = get_sorted_metadata_keys(dictionary_metadata, "humanSettlement")
        menu_json_data["years"] = get_sorted_metadata_keys(dictionary_metadata, "years")
        menu_json_data["kind"] = ["Expedition", "Archive"]
        menu_json_data["nativeSpeakersCount"] = ["vulnerable",
                                                 "definitely endangerd",
                                                 "critically endangerd", "extinct",
                                                 "severely endangered",
                                                 "safe"]

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

        user_id = DBSession.query(Client).filter(client_id == Client.id).first().user_id
        editor_basegroup = DBSession.query(dbBaseGroup).filter(
            and_(dbBaseGroup.subject == "lexical_entries_and_entities", dbBaseGroup.action == "create")).first()
        editable_perspectives = DBSession.query(dbDictionaryPerspective).join(dbGroup, and_(
            dbDictionaryPerspective.client_id == dbGroup.subject_client_id,
            dbDictionaryPerspective.object_id == dbGroup.subject_object_id)).join(dbGroup.users).filter(
            and_(dbUser.id == user_id, dbGroup.base_group_id == editor_basegroup.id)).all()
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

    def resolve_advanced_search(self, info, search_strings, languages=None, dicts_to_filter=None, tag_list=None, category=None, adopted=None, etymology=None, mode='published'):

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
        return AdvancedSearch().constructor(languages, dicts_to_filter, tag_list, category, adopted, etymology, search_strings, publish, accept)

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

    def resolve_all_fields(self, info):
        fields = DBSession.query(dbField).filter_by(marked_for_deletion=False).all() #todo: think about desktop and sync
        gql_fields = list()
        for db_field in fields:
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
        if mode is not None:
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
        text_field_id=LingvodocID(required=True)

    triumph = graphene.Boolean()
    entity_count = graphene.Int()
    result = graphene.String()

    @staticmethod
    def mutate(self, info, **args):
        """
        mutation PhonemicAnalysis {
          phonemic_analysis(
            perspective_id: [70, 5],
            text_field_id: [66, 8])
          {
            triumph
            entity_count
            result
          }
        }
        """

        perspective_cid, perspective_oid = args['perspective_id']
        text_field_cid, text_field_oid = args['text_field_id']

        try:

            log.debug(
                'phonemic_analysis {0}/{1}: text field {2}/{3}, phonemic_analysis_f {4}'.format(
                    perspective_cid, perspective_oid,
                    text_field_cid, text_field_oid,
                    repr(phonemic_analysis_f)))

            if phonemic_analysis_f is None:

                return ResponseError(message =
                    'Analysis library is absent, please contact system administrator.')

            # Query for non-deleted, published and accepted entities of the specified perspective with the
            # specified field.

            data_query = DBSession.query(dbEntity).filter(
                dbLexicalEntry.parent_client_id == perspective_cid,
                dbLexicalEntry.parent_object_id == perspective_oid,
                dbLexicalEntry.marked_for_deletion == False,
                dbEntity.parent_client_id == dbLexicalEntry.client_id,
                dbEntity.parent_object_id == dbLexicalEntry.object_id,
                dbEntity.field_client_id == text_field_cid,
                dbEntity.field_object_id == text_field_oid,
                dbEntity.marked_for_deletion == False,
                dbPublishingEntity.client_id == dbEntity.client_id,
                dbPublishingEntity.object_id == dbEntity.object_id,
                dbPublishingEntity.published == True,
                dbPublishingEntity.accepted == True)

            # Counting text entities we have. If we haven't got any, we return empty result.

            total_count = data_query.count()

            log.debug(
                'phonemic_analysis {0}/{1}: {2} text field {3}/{4} entities'.format(
                    perspective_cid, perspective_oid,
                    total_count,
                    text_field_cid, text_field_oid))

            if total_count <= 0:

                return PhonemicAnalysis(
                    triumph = True,
                    entity_count = total_count,
                    result = u'')

            # Otherwise we perform phonemic analysis.

            text_list = [entity.content
                for entity in data_query.all()
                if len(entity.content) > 0]

            if len(text_list) <= 0:

                return PhonemicAnalysis(
                    triumph = True,
                    entity_count = total_count,
                    result = u'No text entities with non-empty contents.')

            text_list[-1] += u'\r\n'
            input = u'\r\n'.join(text_list)

            log.debug(
                'phonemic_analysis {0}/{1}: text field {2}/{3}'
                '\ninput:\n{4}'.format(
                    perspective_cid, perspective_oid,
                    text_field_cid, text_field_oid,
                    repr(input)))

            # Calling analysis library.

            input_buffer = ctypes.create_unicode_buffer(input)

            output_buffer_size = 1048576
            output_buffer = ctypes.create_unicode_buffer(output_buffer_size)

            result = phonemic_analysis_f(input_buffer, output_buffer)
            call_count = 1

            while result != 1 and call_count < 4:

                output_buffer_size *= 2
                output_buffer = ctypes.create_unicode_buffer(output_buffer_size)

                result = phonemic_analysis_f(input_buffer, output_buffer)
                call_count += 1

            # If we don't have a good result, we return an error.

            log.debug(
                'phonemic_analysis {0}/{1}: text field {2}/{3}: result {4}'.format(
                    perspective_cid, perspective_oid,
                    text_field_cid, text_field_oid,
                    result))

            if result != 1:

                return ResponseError(message =
                    'All {0} library call tries resulted in error.'.format(call_count))

            output = output_buffer.value

            log.debug(
                'phonemic_analysis {0}/{1}: text field {2}/{3}:\noutput:\n{4}'.format(
                    perspective_cid, perspective_oid,
                    text_field_cid, text_field_oid,
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
                'phonemic_analysis {0}/{1}: text field {2}/{3}:'
                '\nwrapped output:\n{4}'.format(
                    perspective_cid, perspective_oid,
                    text_field_cid, text_field_oid,
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

            return ResponseError(message = 'External error')


class CognateAnalysis(graphene.Mutation):

    class Arguments:
        group_field_id=LingvodocID(required=True)
        perspective_info_list=graphene.List(graphene.List(LingvodocID), required=True)

    triumph = graphene.Boolean()
    dictionary_count = graphene.Int()
    group_count = graphene.Int()
    text_count = graphene.Int()
    result = graphene.String()

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
        field_client_id,
        field_object_id,
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

        for perspective_id, text_field_id in perspective_info_list:

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
                    dbEntity.field_client_id == field_client_id,
                    dbEntity.field_object_id == field_object_id,
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
                    dbEntity.field_client_id == field_client_id,
                    dbEntity.field_object_id == field_object_id,
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

            tag_query = (
                    
                DBSession.query(
                    dbEntity.parent_client_id,
                    dbEntity.parent_object_id,
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
                        field_client_id = field_client_id,
                        field_object_id = field_object_id,
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
    def mutate(self, info, **args):
        """
        mutation CognateAnalysis {
          cognate_analysis(
            group_field_id: [66, 25],
            perspective_info_list: [[70, 5], [66, 8]])
          {
            triumph
            entity_count
            result
          }
        }
        """

        group_field_cid, group_field_oid = args['group_field_id']

        perspective_info_list = [
            (tuple(perspective_id), tuple(text_field_id))
            for perspective_id, text_field_id in args['perspective_info_list']]

        try:

            log.debug(
                 'cognate_analysis:'
                 '\ngroup field: {0}/{1}'
                 '\nperspectives and text fields: {2}'
                 '\ncognate_analysis_f: {3}'.format(
                    group_field_cid, group_field_oid,
                    perspective_info_list,
                    repr(cognate_analysis_f)))

            if cognate_analysis_f is None:

                return ResponseError(message =
                    'Analysis library is absent, please contact system administrator.')

            locale_id = info.context.get('locale_id') or 2

            # Gathering entry grouping data.

            perspective_dict = collections.defaultdict(dict)

            entry_already_set = set()
            group_list = []

            tag_dict = collections.defaultdict(set)
            text_dict = {}

            entry_already_set, group_list, group_time = (

                CognateAnalysis.tag_data_aggregated(
                    perspective_info_list, group_field_cid, group_field_oid))

            log.debug(
                'cognate_analysis: {0} entries, {1} groups, {2:.2f}s elapsed time'.format(
                len(entry_already_set), len(group_list), group_time))

            # Getting text data for each perspective.

            for index, (perspective_id, text_field_id) in enumerate(perspective_info_list):

                perspective = DBSession.query(dbDictionaryPerspective).filter_by(
                    client_id = perspective_id[0], object_id = perspective_id[1]).first()

                perspective_name = perspective.get_translation(locale_id)
                dictionary_name = perspective.parent.get_translation(locale_id)

                perspective_dict[perspective_id]['perspective_name'] = perspective_name
                perspective_dict[perspective_id]['dictionary_name'] = dictionary_name

                log.debug(
                    'cognate_analysis {0}/{1}: {2} - {3}'.format(
                    perspective_id[0], perspective_id[1],
                    dictionary_name, perspective_name))

                # Getting text data, leaving only texts belonging to lexical entries without other texts.

                text_data_list = DBSession.query(
                    dbLexicalEntry.client_id,
                    dbLexicalEntry.object_id,
                    dbEntity).filter(
                        dbLexicalEntry.parent_client_id == perspective_id[0],
                        dbLexicalEntry.parent_object_id == perspective_id[1],
                        dbLexicalEntry.marked_for_deletion == False,
                        dbEntity.parent_client_id == dbLexicalEntry.client_id,
                        dbEntity.parent_object_id == dbLexicalEntry.object_id,
                        dbEntity.field_client_id == text_field_id[0],
                        dbEntity.field_object_id == text_field_id[1],
                        dbEntity.marked_for_deletion == False,
                        dbPublishingEntity.client_id == dbEntity.client_id,
                        dbPublishingEntity.object_id == dbEntity.object_id,
                        dbPublishingEntity.published == True,
                        dbPublishingEntity.accepted == True)

                for entry_client_id, entry_object_id, entity in text_data_list.all():
                    
                    entry_id = (entry_client_id, entry_object_id)

                    if entry_id in text_dict:
                        text_dict[entry_id] = (index, None)

                    else:
                        text_dict[entry_id] = (index, entity.content)

            # Ok, and now we form the source data for analysis.

            result_list = []
            perspective_list = []

            for perspective_id, text_field_id in perspective_info_list:
                perspective_data = perspective_dict[perspective_id]

                perspective_list.append(
                    perspective_data['dictionary_name'] + ' - ' + 
                    perspective_data['perspective_name'])

            log.debug('\n' +
                pprint.pformat(perspective_list, width = 108))

            result_list.append(perspective_list)

            # Each group of lexical entries.

            non_unique_count = 0
            not_enough_count = 0

            total_text_count = 0

            for entry_id_set in group_list:

                text_list = [None] * len(perspective_info_list)
                text_count = 0

                for entry_id in entry_id_set:

                    if entry_id not in text_dict:
                        continue

                    # Processing text data of each entry of the group.

                    index, text = text_dict[entry_id]

                    if text is None:
                        continue

                    if text_list[index] is None:

                        text_list[index] = text.strip()
                        text_count += 1

                    else:

                        text_list = None
                        break

                # Dropping groups with multiple text from the same dictionary and groups with no more than a
                # single text.

                if text_list is None:

                    non_unique_count += 1
                    continue

                if text_count <= 1:

                    not_enough_count += 1
                    continue

                log.debug('\n' +
                    pprint.pformat(text_list, width = 108))

                result_list.append([
                    text or '' for text in text_list])

                total_text_count += text_count

            # Showing what we've gathered.

            log.debug('\n' +
                pprint.pformat(result_list, width = 108))

            log.debug('cognate_analysis:'
                '\nlen(group_list): {0}'
                '\nlen(result_list): {1}'
                '\nnon_unique_count: {2}'
                '\nnot_enough_count: {3}'
                '\ntext_count: {4}'.format(
                    len(group_list),
                    len(result_list),
                    non_unique_count,
                    not_enough_count,
                    total_text_count))

            input = ''.join(
                ''.join(text + '\0' for text in text_list)
                for text_list in result_list)

            log.debug(
                'cognate_analysis: input:\n{0}\n{1} columns, {2} rows'.format(
                repr(input), len(perspective_info_list), len(result_list)))

            # Checking if we have any data at all.

            if len(result_list) <= 1:

                return CognateAnalysis(
                    triumph = True,
                    dictionary_count = len(perspective_info_list),
                    group_count = len(result_list) - 1,
                    text_count = total_text_count,
                    result = u'')

            # Calling analysis library.

            input_buffer = ctypes.create_unicode_buffer(input)

            output_buffer_size = 1048576
            output_buffer = ctypes.create_unicode_buffer(output_buffer_size)

            result = cognate_analysis_f(
                input_buffer, len(result_list), len(perspective_info_list), output_buffer)

            call_count = 1

            while result != 1 and call_count < 4:

                output_buffer_size *= 2
                output_buffer = ctypes.create_unicode_buffer(output_buffer_size)

                result = cognate_analysis_f(
                    input_buffer, len(result_list), len(perspective_info_list), output_buffer)

                call_count += 1

            # If we don't have a good result, we return an error.

            log.debug('cognate_analysis: result {0}'.format(result))

            if result != 1:

                return ResponseError(message =
                    'All {0} library call tries resulted in error.'.format(call_count))

            output = output_buffer.value

            log.debug('cognate_analysis: output:\n{0}'.format(repr(output)))

            # Reflowing output.

            line_list = output.split('\r\n')

            text_wrapper = textwrap.TextWrapper(
                width = 108, tabsize = 4)

            reflow_list = []

            for line in line_list:
                reflow_list.extend(text_wrapper.wrap(line))

            wrapped_output = '\n'.join(reflow_list)

            log.debug('cognate_analysis: wrapped output:\n{0}'.format(wrapped_output))

            # Returning result.

            return CognateAnalysis(
                triumph = True,
                dictionary_count = len(perspective_info_list),
                group_count = len(result_list) - 1,
                text_count = total_text_count,
                result = wrapped_output)

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('cognate_analysis: exception')
            log.debug(traceback_string)

            return ResponseError(message = 'External error')


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
    move_language = MoveLanguage.Field()
    delete_language = DeleteLanguage.Field()
    create_dictionary = CreateDictionary.Field()
    update_dictionary = UpdateDictionary.Field()
    update_dictionary_status = UpdateDictionaryStatus.Field()
    #update_dictionary_roles = UpdateDictionaryRoles.Field()
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
