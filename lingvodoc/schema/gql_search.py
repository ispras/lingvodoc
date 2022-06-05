import collections
import datetime
import gzip
import hashlib
import io
import itertools
import logging
import os
import os.path
import pickle
import pprint
import re
import traceback

# Just in case, don't have that on Windows.

try:
    import resource
except:
    pass

import shutil
import time

import graphene
import xlsxwriter

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CreatedAt,
    IdHolder,
    MarkedForDeletion,
    AdditionalMetadata,
    Name,
    About,
    del_object,
    acl_check_by_id,
    ResponseError,
    LingvodocID,
    ObjectVal
)
from lingvodoc.models import (
    Organization as dbOrganization,
    Client,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbDictionaryPerspective,
    Language as dbLanguage,
    LexicalEntry as dbLexicalEntry,
    Entity as dbEntity,
    PublishingEntity as dbPublishingEntity,
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    DBSession,
    Field as dbField,
    TranslationGist as dbTranslationGist,
    TranslationAtom as dbTranslationAtom,
    DictionaryPerspectiveToField as dbDictionaryPerspectiveToField)
from lingvodoc.schema.gql_entity import Entity
from lingvodoc.schema.gql_dictionary import Dictionary
from lingvodoc.schema.gql_dictionaryperspective import DictionaryPerspective, entries_with_entities
from lingvodoc.schema.gql_lexicalentry import LexicalEntry
from lingvodoc.scripts.save_dictionary import Save_Context

from lingvodoc.utils.search import (
    recursive_sort,
    translation_gist_search
)

import lingvodoc.utils as utils

from lingvodoc.utils import (
    ids_to_id_query,
    ids_to_id_cte,
    ids_to_id_cte_query,
)

from lingvodoc.views.v2.utils import (
    storage_file,
    as_storage_file
)

from sqlalchemy import (
    and_,
    Boolean,
    cast,
    exists,
    func,
    not_,
    or_,
    tuple_,
    union
)
from sqlalchemy.orm.util import aliased
from itertools import chain

from poioapi.eaf_search import eaf_search

import re


# Setting up logging.
log = logging.getLogger(__name__)


def graphene_obj(dbobj, cur_cls):
    obj = cur_cls(id=(dbobj.client_id, dbobj.object_id))
    obj.dbObject = dbobj
    return obj

def has_wildcard(elem):
    wild_cards = {'@', '?'}
    for wild_card in wild_cards:
        if wild_card in elem:
            return True
    return False

def add_as_strict(elem):
    query = elem.replace('"', '')
    return query

def add_as_like(elem):
    query = '%' + elem.replace('"', '').replace('@', '%').replace('?', '_') + '%'
    return query

def boolean_search(test_string,  exclude_char = '-'):
    regex = '(-?"[^\n\r]+?"|[^\s\n\r]+)'
    and_blocks_strings = test_string.split(" | ")
    and_blocks_strings = [x.lower() for x in and_blocks_strings]
    #print(and_blocks_strings)
    and_blocks = []
    for block_string in and_blocks_strings:
        and_blocks.append(re.findall(regex, block_string))
    #print(and_blocks)

    and_blocks_queries = []
    #excludes = []
    for and_block in and_blocks:
        and_blocks_queries.append([])
        and_block_queries = and_blocks_queries[len(and_blocks_queries) - 1]
        for element in and_block:
            if element.startswith(exclude_char):
                element = element[1:]
                and_block_queries.append({"matching_type": 'exclude',
                                          "search_string": element})
                #excludes.append(element[1:])
                continue
            if '"' in element:
                if has_wildcard(element):
                    query = add_as_like(element)
                    and_block_queries.append({"matching_type": 'substring',
                                          "search_string": query})
                else:
                    query = add_as_strict(element)
                    and_block_queries.append({"matching_type": 'full_string',
                                          "search_string": query})
            else:
                query = add_as_like(element)
                and_block_queries.append({"matching_type": 'substring',
                                          "search_string": query})
    return and_blocks_queries


def save_xlsx_data(
    xlsx_context,
    dictionary_list,
    perspective_list,
    lexical_entry_list):
    """
    Exports search results to as Xlsx data.
    """

    # Ordering perspectives in the same way as dictionaries later, by creation time descending.

    perspective_list = sorted(
        perspective_list,
        key = lambda perspective: perspective.created_at,
        reverse = True)

    perspective_dict = collections.defaultdict(list)
    lexical_entry_dict = collections.defaultdict(list)

    for perspective in perspective_list:

        parent = perspective.parent
        perspective_dict[(parent.client_id, parent.object_id)].append(perspective)

    for lexical_entry in lexical_entry_list:

        parent = lexical_entry.parent
        lexical_entry_dict[(parent.client_id, parent.object_id)].append(lexical_entry)

    # Dictionary and language info.

    dictionary_dict = collections.defaultdict(list)

    language_id_set = set()
    language_list = []

    def f(language):
        """
        Recursively gathers containing languages.
        """

        language_id = (
            language.client_id, language.object_id)

        if language_id in language_id_set:
            return

        language_list.append(language)
        language_id_set.add(language_id)

        parent = language.parent

        if parent is not None:
            f(language.parent)

    # Standard dictionary ordering, creation time descending, see resolve_dictionaries(), order_by() clause.

    dictionary_list = sorted(
        dictionary_list,
        key = lambda dictionary: dictionary.created_at,
        reverse = True)

    for dictionary in dictionary_list:

        parent = dictionary.parent
        dictionary_dict[(parent.client_id, parent.object_id)].append(dictionary)

        f(parent)

    # Standard language ordering, see resolve_language_tree().

    language_list.sort(
        key = lambda language: (
            language.parent_client_id or -1,
            language.parent_object_id or -1,
            language.additional_metadata['younger_siblings']))

    visited = set()
    stack = set()
    result = list()
    recursive_sort(language_list, visited, stack, result)

    language_dict = collections.defaultdict(list)
    id_to_language_dict = {}

    for language in language_list:

        parent_id = (
            language.parent_client_id, language.parent_object_id)

        language_dict[parent_id].append(language)

        language_id = (
            language.client_id, language.object_id)

        id_to_language_dict[language_id] = language

    # And now determining standard main language for each language and grouping dictionaries by main
    # language.

    standard_dict = {}

    group_dict = collections.defaultdict(list)
    group_list = []

    standard_language_id_query = (

        DBSession

            .query(
                dbLanguage.client_id, 
                dbLanguage.object_id)

            .filter(
                dbLanguage.marked_for_deletion == False,
                cast(dbLanguage.additional_metadata['toc_mark'], Boolean)))

    standard_language_id_set = (
        set(tuple(id) for id in standard_language_id_query.all()))

    standard_language_id_set.update(
        utils.standard_language_id_set)

    def f(
        language_id,
        standard_id = None):

        if language_id in standard_language_id_set:

            standard_id = language_id
            group_list.append(standard_id)

        standard_dict[language_id] = standard_id

        # First sublanguages, and only then own dictionaries.

        for language in language_dict[language_id]:

            f(
                (language.client_id, language.object_id),
                standard_id)

        group_dict[standard_id].extend(dictionary_dict[language_id])

    f((None, None))

    if group_dict[None]:
        group_list.append(None)

    # Showing what we've got.

    log.debug(
        '\nlen(dictionary_list): {0}'
        '\nlen(language_list): {1}'
        '\nlen(language_dict): {2}'
        '\nlanguage_dict:\n{3}'
        '\nlen(standard_dict): {4}'
        '\nstandard_dict:\n{5}'
        '\nlen(group_dict): {6}'
        '\ngroup_dict:\n{7}'
        '\nlen(group_list): {8}'
        '\ngroup_list:\n{9}'.format(
            len(dictionary_list),
            len(language_list),
            len(language_dict),
            pprint.pformat(language_dict, width = 192),
            len(standard_dict),
            pprint.pformat(standard_dict, width = 192),
            len(group_dict),
            pprint.pformat(group_dict, width = 192),
            len(group_list),
            pprint.pformat(group_list, width = 192)))

    # Saving data of all found lexical entries.

    for language_id in group_list:

        if language_id is None:

            language_name = '(ungrouped)'

        else:

            language = id_to_language_dict[language_id]
            language_name = language.get_translation(xlsx_context.locale_id)

        dictionary_list = group_dict[language_id]

        log.debug(
            '\n{0}: {1} dictionaries'.format(
                repr(language_name),
                len(dictionary_list)))

        if not dictionary_list:
            continue

        xlsx_context.ready_worksheet(language_name)

        # Another dictionary and its perspectives.

        for dictionary in dictionary_list:

            for perspective in perspective_dict[
                (dictionary.client_id, dictionary.object_id)]:

                xlsx_context.ready_perspective(
                    perspective,
                    dictionary,
                    worksheet_flag = False,
                    list_flag = True)

                for lexical_entry in lexical_entry_dict[
                    (perspective.client_id, perspective.object_id)]:

                    xlsx_context.save_lexical_entry(
                        lexical_entry, published = True, accepted = True)

def search_mechanism(
    dictionaries,
    category,
    search_strings,
    publish,
    accept,
    adopted,
    etymology,
    diacritics,
    yield_batch_count,
    category_field_cte_query,
    xlsx_context = None,
    load_entities = True,
    __debug_flag__ = False):

    """
    1) published dictionaries
    2) field filter
    3) metadata filter
    4)
    """
    # 1) old filter

    if __debug_flag__:

        # If we are in debug mode, we try to load already computed search data to reduce debugging time.

        dictionary_id_list = sorted(dictionaries.all())
        field_id_list = sorted(category_field_cte_query.all())

        search_list = [

            [sorted(search_string.items())
                for search_string in search_block]

            for search_block in search_strings]

        search_digest = hashlib.md5(

            repr([
                dictionary_id_list,
                category,
                search_list,
                publish,
                accept,
                adopted,
                etymology,
                diacritics,
                field_id_list])

                .encode('utf-8')).hexdigest()

        search_data_file_name = (
            '__search_data_{0}__.gz'.format(search_digest))

        # Checking if we have saved data.

        if os.path.exists(search_data_file_name):

            with gzip.open(search_data_file_name, 'rb') as search_data_file:

                (lexical_entry_id_list,
                    perspective_id_list,
                    dictionary_id_list) = pickle.load(search_data_file)

            # Loading search data.

            lexical_entry_list = (

                DBSession.query(dbLexicalEntry)

                    .filter(
                        tuple_(dbLexicalEntry.client_id, dbLexicalEntry.object_id).in_(
                            lexical_entry_id_list))
                        
                    .all())

            perspective_list = (

                DBSession.query(dbDictionaryPerspective)
                
                    .filter(
                        tuple_(dbDictionaryPerspective.client_id, dbDictionaryPerspective.object_id).in_(
                            perspective_id_list))
                        
                    .all())

            dictionary_list = (

                DBSession.query(dbDictionary)
                
                    .filter(
                        tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(
                            dictionary_id_list))
                        
                    .all())

            # Compiling search results.

            result_lexical_entries = (

                entries_with_entities(
                    lexical_entry_list,
                    accept = True,
                    delete = False,
                    mode = None,
                    publish = True,
                    check_perspective = False))

            res_perspectives = [
                graphene_obj(dbpersp, DictionaryPerspective) for dbpersp in perspective_list]

            res_dictionaries = [
                graphene_obj(dbdict, Dictionary) for dbdict in dictionary_list]

            return [], result_lexical_entries, res_perspectives, res_dictionaries

    lexes = (

        DBSession

            .query(
                dbLexicalEntry.client_id,
                dbLexicalEntry.object_id)

            .filter(
                dbLexicalEntry.marked_for_deletion == False,
                dbLexicalEntry.parent_client_id == dbDictionaryPerspective.client_id,
                dbLexicalEntry.parent_object_id == dbDictionaryPerspective.object_id,
                dbDictionaryPerspective.marked_for_deletion == False,

                tuple_(
                    dbDictionaryPerspective.parent_client_id,
                    dbDictionaryPerspective.parent_object_id)
                    .in_(DBSession.query(dictionaries.cte()))))

    if adopted is not None or etymology is not None:
        lexes.join(dbLexicalEntry.entity)
        if adopted is False:
            lexes = lexes.filter(~func.lower(dbEntity.content).contains('заим.%'))
        elif adopted:
            lexes = lexes.filter(func.lower(dbEntity.content).contains('заим.%'))
        if etymology is not None:
            gist = translation_gist_search('Grouping Tag')
            fields = DBSession.query(dbField.client_id, dbField.object_id).filter(
                tuple_(dbField.data_type_translation_gist_client_id,
                       dbField.data_type_translation_gist_object_id) == (gist.client_id, gist.object_id))
            if etymology:
                lexes = lexes.filter(not_(tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(fields)))
            else:
                lexes = lexes.filter(tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(fields))

    lexes_cte = lexes.cte()

    # get all_entity_content_filter

    all_entity_content_filter = list()
    all_block_field_set = set()
    fields_flag = True

    if diacritics == 'ignore':

        xform_func = func.diacritic_xform
        xform_bag_func = func.diacritic_xform_bag

    else:

        xform_func = func.lower
        xform_bag_func = func.lower_bag

    if category == 0:
        for search_block in search_strings:

            all_block_field_set.update(
                tuple(sb.get("field_id")) for sb in search_block if sb.get("field_id"))

            for search_string in search_block:
                if not search_string.get("field_id"):
                    fields_flag = False

                if search_string.get('matching_type') == "substring":

                    curr_bs_search_blocks = (
                        boolean_search(search_string["search_string"]))

                    for ss in chain.from_iterable(curr_bs_search_blocks):

                        xform_ss = xform_func(ss["search_string"])

                        if ss.get('matching_type') == "substring":

                            all_entity_content_filter.append(
                                xform_func(dbEntity.content).like(xform_ss))

                        elif ss.get('matching_type') == "full_string":

                            all_entity_content_filter.append(
                                xform_func(dbEntity.content) == xform_ss)

                        elif ss.get('matching_type') == "regexp":

                            all_entity_content_filter.append(
                                xfrom_func(dbEntity.content).op('~*')(xform_ss))

                elif search_string.get('matching_type') == "full_string":

                    all_entity_content_filter.append(
                        xform_func(dbEntity.content) ==
                            xform_func(search_string["search_string"]))

                elif search_string.get('matching_type') == "regexp":

                    all_entity_content_filter.append(
                        xform_func(dbEntity.content).op('~*')(
                            xform_func(search_string["search_string"])))

    elif category == 1:
        for search_block in search_strings:
            for search_string in search_block:
                if not search_string.get("field_id"):
                    fields_flag = False

                if search_string.get('matching_type') == "substring":

                    curr_bs_search_blocks = (
                        boolean_search(search_string["search_string"]))

                    for ss in chain.from_iterable(curr_bs_search_blocks):

                        xform_ss = xform_func(ss["search_string"])

                        if ss.get('matching_type') == "substring":

                            all_entity_content_filter.append(
                                xform_func(dbEntity.additional_metadata['bag_of_words'].astext)
                                    .like(xform_ss))

                        elif ss.get('matching_type') == "full_string":

                            all_entity_content_filter.append(
                                xform_bag_func(dbEntity.additional_metadata['bag_of_words'])
                                    .op('@>')(func.to_jsonb(xform_ss)))

                        elif ss.get('matching_type') == "regexp":

                            all_entity_content_filter.append(
                                xform_func(dbEntity.additional_metadata['bag_of_words'].astext)
                                    .op('~*')(xform_ss))

                elif search_string.get('matching_type') == "full_string":

                    all_entity_content_filter.append(
                        xform_bag_func(dbEntity.additional_metadata['bag_of_words'])
                            .op('@>')(func.to_jsonb(xform_func(search_string["search_string"]))))

                elif search_string.get('matching_type') == "regexp":

                    all_entity_content_filter.append(
                        xform_func(dbEntity.additional_metadata['bag_of_words'].astext)
                            .op('~*')(xform_func(search_string["search_string"])))

    # all_entity_content_filter = and_(or_(*all_entity_content_filter))

    if fields_flag and category == 0:

        all_block_field_cte = ids_to_id_cte(all_block_field_set)

        all_block_field_query = (

            DBSession

                .query(all_block_field_cte)

                .filter(
                    tuple_(
                        all_block_field_cte.c.client_id,
                        all_block_field_cte.c.object_id)

                        .in_(category_field_cte_query)))

        all_entity_content_filter = (

            and_(
                or_(*all_entity_content_filter),

                tuple_(dbEntity.field_client_id, dbEntity.field_object_id)
                    .in_(all_block_field_query)))

    else:

        all_entity_content_filter = (

            and_(
                or_(*all_entity_content_filter),

                tuple_(dbEntity.field_client_id, dbEntity.field_object_id)
                    .in_(category_field_cte_query)))

    # filter unused entitities
    field_filter = True
    select_query = []
    if field_filter:
        select_query += [dbEntity.field_client_id, dbEntity.field_object_id]
    if category == 1:
        select_query += [dbEntity.additional_metadata]
    else:
        select_query += [dbEntity.content]
    published_filter = []
    if accept is not None:
        published_filter += [dbPublishingEntity.accepted == accept]
    if publish is not None:
        published_filter += [dbPublishingEntity.published == publish]
    if published_filter:
        published_to_entity = [dbPublishingEntity.client_id == dbEntity.client_id,
         dbPublishingEntity.object_id == dbEntity.object_id]
        published_filter = published_to_entity + published_filter

        all_entities_cte = DBSession.query(dbEntity.parent_client_id,
                                       dbEntity.parent_object_id,
                                       *select_query).filter(
                dbEntity.marked_for_deletion == False,
                *published_filter,
                all_entity_content_filter).cte()  # only published entities

    # persp filter
    #DBSession.query(dbLexicalEntry).filter(dbLexicalEntry.parent_client_id, dbLexicalEntry.parent_object_id)



    # old mechanism + cte
    full_or_block = list()

    for search_block in search_strings:
        and_lexes_sum = list()
        for search_string in search_block:
            inner_and = list()
            cur_dbEntity = all_entities_cte.c
            if search_string.get('field_id'):
                inner_and.append(cur_dbEntity.field_client_id == search_string["field_id"][0])
                inner_and.append(cur_dbEntity.field_object_id == search_string["field_id"][1])
            else:
                inner_and.append(
                    tuple_(cur_dbEntity.field_client_id, cur_dbEntity.field_object_id)
                        .in_(category_field_cte_query))

            matching_type = search_string.get('matching_type')
            if not matching_type in ("full_string", "substring", "regexp", "exclude"):
                raise ResponseError(message='wrong matching_type')

            if category == 1:

                if matching_type == "full_string":

                    inner_and.append(
                        xform_bag_func(cur_dbEntity.additional_metadata['bag_of_words'])
                            .op('@>')(func.to_jsonb(xform_func(search_string["search_string"]))))

                elif matching_type == 'substring':

                    curr_bs_search_blocks = (
                        boolean_search(search_string["search_string"]))

                    for ss in chain.from_iterable(curr_bs_search_blocks):

                        xform_ss = xform_func(ss["search_string"])

                        if ss.get('matching_type') == "substring":

                            inner_and.append(
                                xform_func(cur_dbEntity.additional_metadata['bag_of_words'].astext)
                                    .like(xform_ss))

                        elif ss.get('matching_type') == "full_string":

                            inner_and.append(
                                xform_bag_func(cur_dbEntity.additional_metadata['bag_of_words'])
                                    .op('@>')(func.to_jsonb(xform_ss)))

                        elif ss.get('matching_type') == "regexp":

                            inner_and.append(
                                xform_func(cur_dbEntity.additional_metadata['bag_of_words'].astext)
                                    .op('~*')(xform_ss))

                elif matching_type == 'regexp':

                    inner_and.append(
                        xform_func(cur_dbEntity.additional_metadata['bag_of_words'].astext)
                            .op('~*')(xform_func(search_string["search_string"])))

            else:

                if matching_type == "full_string":

                    inner_and.append(
                        xform_func(cur_dbEntity.content) ==
                            xform_func(search_string["search_string"]))

                elif matching_type == 'substring':

                    curr_bs_search_blocks = (
                        boolean_search(search_string["search_string"]))

                    bs_or_block_list = list()

                    for bs_or_block in curr_bs_search_blocks:

                        bs_and = list()

                        for ss in bs_or_block:

                            xform_ss = xform_func(ss["search_string"])

                            if ss.get('matching_type') == "substring":

                                bs_and.append(
                                    xform_func(cur_dbEntity.content).like(xform_ss))

                            elif ss.get('matching_type') == "full_string":

                                bs_and.append(
                                    xform_func(cur_dbEntity.content) == xform_ss)

                            elif ss.get('matching_type') == "regexp":

                                bs_and.append(
                                    xform_func(cur_dbEntity.content).op('~*')(xform_ss))

                            elif ss.get('matching_type') == "exclude":

                                bs_and.append(
                                    xform_func(cur_dbEntity.content) != xform_ss)

                        bs_or_block_list.append(and_(*bs_and))

                    inner_and.append(or_(*bs_or_block_list))

                elif matching_type == 'regexp':

                    inner_and.append(
                        xform_func(cur_dbEntity.content).op('~*')(
                            xform_func(search_string["search_string"])))

            and_lexes_query = (

                DBSession
                
                    .query(
                        all_entities_cte.c.parent_client_id,
                        all_entities_cte.c.parent_object_id)

                    .filter(and_(*inner_and).self_group())

                    .distinct())

            and_lexes_sum.append(and_lexes_query)

        and_lexes_sum.append(
            DBSession.query(lexes_cte))

        and_lexes_sum_query = (

            and_lexes_sum[0].intersect(
                *and_lexes_sum[1:]))

        full_or_block.append(and_lexes_sum_query)

    # Searching for and getting lexical entries.

    resolved_search = None

    if full_or_block:

        entry_id_query = (
            full_or_block[0])

        if len(full_or_block) > 1:

            entry_id_query = (

                entry_id_query.union(
                    *full_or_block[1:]))

        entry_query = (

            DBSession

                .query(dbLexicalEntry)

                .filter(
                    dbLexicalEntry.marked_for_deletion == False,

                    tuple_(
                        dbLexicalEntry.client_id,
                        dbLexicalEntry.object_id)
                        .in_(entry_id_query)))

        # Showing overall entry query.

        log.debug(
            '\nentry_query:\n' +
            str(entry_query.statement.compile(compile_kwargs = {"literal_binds": True})))

        resolved_search = entry_query.all()

    if not resolved_search:

        # Saving search results data, if required.

        if __debug_flag__:

            with gzip.open(
                search_data_file_name, 'wb') as search_data_file:

                pickle.dump(([], [], []), search_data_file)

        return [], [], [], []

    if load_entities:

        result_lexical_entries = (

            # Don't need to check for perspective deletion, we explicitly look only in undeleted dictionaries
            # and undeleted perspectives.

            entries_with_entities(
                resolved_search,
                accept = True,
                delete = False,
                mode = None,
                publish = True,
                check_perspective = False))

    else:

        result_lexical_entries = [graphene_obj(entry, LexicalEntry) for entry in resolved_search]

    perspective_ids = (
        set(le.dbObject.parent_id for le in result_lexical_entries))

    if len(perspective_ids) > 2:
        perspective_ids = ids_to_id_query(perspective_ids)

    tmp_perspectives_query = (

        DBSession

            .query(
                dbDictionaryPerspective)

            .filter(
                tuple_(
                    dbDictionaryPerspective.client_id,
                    dbDictionaryPerspective.object_id)
                    .in_(perspective_ids)))

    log.debug(
        '\ntmp_perspectives_query:\n' +
        str(tmp_perspectives_query.statement.compile(compile_kwargs = {"literal_binds": True})))

    tmp_perspectives = tmp_perspectives_query.all()
    res_perspectives = [graphene_obj(dbpersp, DictionaryPerspective) for dbpersp in tmp_perspectives]

    dictionary_ids = (
        set(le.dbObject.parent_id for le in res_perspectives))

    if len(dictionary_ids) > 2:
        dictionary_ids = ids_to_id_query(dictionary_ids)

    tmp_dictionaries_query = (

        DBSession

            .query(
                dbDictionary)

            .filter(
                tuple_(
                    dbDictionary.client_id,
                    dbDictionary.object_id)
                    .in_(dictionary_ids)))

    log.debug(
        '\ntmp_dictionaries_query:\n' +
        str(tmp_dictionaries_query.statement.compile(compile_kwargs = {"literal_binds": True})))

    tmp_dictionaries = tmp_dictionaries_query.all()
    res_dictionaries = [graphene_obj(dbdict, Dictionary) for dbdict in tmp_dictionaries]

    # Saving search results data, if required.

    if __debug_flag__:

        with gzip.open(
            search_data_file_name, 'wb') as search_data_file:

            search_data = (

                sorted(
                    (entry.client_id, entry.object_id)
                    for entry in resolved_search),

                sorted(
                    (perspective.client_id, perspective.object_id)
                    for perspective in tmp_perspectives),

                sorted(
                    (dictionary.client_id, dictionary.object_id)
                    for dictionary in tmp_dictionaries))

            pickle.dump(
                search_data, search_data_file)

    return [], result_lexical_entries, res_perspectives, res_dictionaries

def search_mechanism_simple(
    dictionaries,
    category,
    state_gist_id,
    limited_gist_id,
    search_strings,
    publish,
    accept,
    adopted,
    etymology,
    yield_batch_count,
    category_fields,
    xlsx_context = None):

    state_translation_gist_client_id, state_translation_gist_object_id = state_gist_id
    limited_client_id, limited_object_id = limited_gist_id
    dictionaries = dictionaries.filter(dbDictionary.category == category)
    if publish:
        dictionaries = dictionaries.filter(dbDictionary.marked_for_deletion == False).filter(
            or_(and_(dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                     dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id),
                and_(dbDictionary.state_translation_gist_object_id == limited_object_id,
                     dbDictionary.state_translation_gist_client_id == limited_client_id))). \
            join(dbDictionaryPerspective) \
            .filter(or_(
            and_(dbDictionaryPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                 dbDictionaryPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
            and_(dbDictionaryPerspective.state_translation_gist_object_id == limited_object_id,
                 dbDictionaryPerspective.state_translation_gist_client_id == limited_client_id))). \
            filter(dbDictionaryPerspective.marked_for_deletion == False)
    lexes = DBSession.query(dbLexicalEntry.client_id, dbLexicalEntry.object_id).join(dbLexicalEntry.parent) \
        .join(dbDictionaryPerspective.parent) \
        .filter(dbLexicalEntry.marked_for_deletion==False,
                tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(dictionaries))

    if adopted is not None or etymology is not None:
        lexes.join(dbLexicalEntry.entity)
        if adopted is False:
            lexes = lexes.filter(~func.lower(dbEntity.content).contains('заим.%'))
        elif adopted:
            lexes = lexes.filter(func.lower(dbEntity.content).contains('заим.%'))
        if etymology is not None:
            gist = translation_gist_search('Grouping Tag')
            fields = DBSession.query(dbField.client_id, dbField.object_id).filter(
                tuple_(dbField.data_type_translation_gist_client_id,
                       dbField.data_type_translation_gist_object_id) == (gist.client_id, gist.object_id))
            if etymology:
                lexes = lexes.filter(not_(tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(fields)))
            else:
                lexes = lexes.filter(tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(fields))

    aliases = list()
    and_block = list()
    for search_block in search_strings:
        cur_dbEntity = aliased(dbEntity)
        cur_dbPublishingEntity = aliased(dbPublishingEntity)
        aliases.append(cur_dbEntity)
        aliases.append(cur_dbPublishingEntity)
        # add entity alias in aliases
        or_block = list()
        for search_string in search_block:
            inner_and_block = list()
            if search_string.get('field_id'):
                inner_and_block.append(cur_dbEntity.field_client_id == search_string["field_id"][0])
                inner_and_block.append(cur_dbEntity.field_object_id == search_string["field_id"][1])
            else:
                inner_and_block.append(
                    tuple_(cur_dbEntity.field_client_id, cur_dbEntity.field_object_id)
                        .in_(category_fields_cte_query))

            matching_type = search_string.get('matching_type')
            if matching_type == "full_string":
                if category == 1:
                    inner_and_block.append(cur_dbEntity.additional_metadata['bag_of_words'].contains([search_string["search_string"].lower()]))
                else:
                    inner_and_block.append(func.lower(cur_dbEntity.content) == func.lower(search_string["search_string"]))
            elif matching_type == 'substring':
                if category == 1:
                    inner_and_block.append(func.lower(cur_dbEntity.additional_metadata['bag_of_words'].astext).like("".join(['%', search_string["search_string"].lower(), '%'])))
                else:

                    inner_and_block.append(func.lower(cur_dbEntity.content).like("".join(['%', search_string["search_string"].lower(), '%'])))
            elif matching_type == 'regexp':
                if category == 1:
                    inner_and_block.append(func.lower(cur_dbEntity.additional_metadata['bag_of_words'].astext).op('~*')(search_string["search_string"]))
                else:
                    inner_and_block.append(func.lower(cur_dbEntity.content).op('~*')(search_string["search_string"]))
            else:
                raise ResponseError(message='wrong matching_type')

            or_block.append(and_(*inner_and_block))
        if publish is not None:
            and_block.append(cur_dbPublishingEntity.published == publish)
        if accept is not None:
            and_block.append(cur_dbPublishingEntity.accepted == accept)
        and_block.append(cur_dbEntity.marked_for_deletion == False)
        and_block.append(cur_dbEntity.client_id == cur_dbPublishingEntity.client_id)
        and_block.append(cur_dbEntity.object_id == cur_dbPublishingEntity.object_id)
        and_block.append(cur_dbEntity.parent_client_id == dbLexicalEntry.client_id)
        and_block.append(cur_dbEntity.parent_object_id == dbLexicalEntry.object_id)
        and_block.append(or_(*or_block))
    and_block.append(dbLexicalEntry.parent_client_id == dbDictionaryPerspective.client_id)
    and_block.append(dbLexicalEntry.parent_object_id == dbDictionaryPerspective.object_id)
    and_block.append(dbDictionaryPerspective.parent_client_id == dbDictionary.client_id)
    and_block.append(dbDictionaryPerspective.parent_object_id == dbDictionary.object_id)
    and_block = and_(*and_block)
    aliases_len = len(aliases)
    aliases.append(dbLexicalEntry)
    aliases.append(dbDictionaryPerspective)
    aliases.append(dbDictionary)

    search = DBSession.query(*aliases).filter(and_block, tuple_(dbLexicalEntry.client_id, dbLexicalEntry.object_id).in_(
        lexes)).yield_per(yield_batch_count)
    resolved_search = [entity for entity in search]

    def graphene_entity(entity, publishing):
        ent = Entity(id=(entity.client_id, entity.object_id))
        ent.dbObject = entity
        ent.publishingentity = publishing
        return ent


    full_entities_and_publishing = set()
    for i in range(int(aliases_len / 2)):
        counter = i * 2
        entities_and_publishing = {(entity[counter], entity[counter+1]) for entity in resolved_search}
        full_entities_and_publishing |= entities_and_publishing

    # res_entities = [graphene_entity(entity[0], entity[1]) for entity in full_entities_and_publishing]
    tmp_lexical_entries = {entity[aliases_len ] for entity in resolved_search}
    res_lexical_entries = [graphene_obj(ent, LexicalEntry) for ent in tmp_lexical_entries]
    tmp_perspectives = {entity[aliases_len + 1] for entity in resolved_search}
    res_perspectives = [graphene_obj(ent, DictionaryPerspective) for ent in tmp_perspectives]
    tmp_dictionaries = {entity[aliases_len + 2] for entity in resolved_search}
    res_dictionaries = [graphene_obj(ent, Dictionary) for ent in tmp_dictionaries]

    return [], res_lexical_entries, res_perspectives, res_dictionaries


def dictionaries_with_audio_ids():


    sound_field_id_list = get_sound_field_ids()

    sound_entities_cte = DBSession.query(dbEntity.parent_client_id, dbEntity.parent_object_id).filter(
            tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(sound_field_id_list),
            dbEntity.marked_for_deletion == False,
            dbPublishingEntity.client_id == dbEntity.client_id,
            dbPublishingEntity.object_id == dbEntity.object_id,
            dbPublishingEntity.accepted == True).cte()


    lexical_entries_with_sound = DBSession.query(dbLexicalEntry.parent_client_id,
                                                 dbLexicalEntry.parent_object_id).filter(
            dbLexicalEntry.marked_for_deletion == False,
            sound_entities_cte.c.parent_client_id == dbLexicalEntry.client_id,
            sound_entities_cte.c.parent_object_id == dbLexicalEntry.object_id).cte()
    sound_persps_cte = DBSession.query(lexical_entries_with_sound).distinct().cte()
    sound_dicts_cte = DBSession.query(dbDictionaryPerspective.parent_client_id,
                                      dbDictionaryPerspective.parent_object_id).filter(
        tuple_(dbDictionaryPerspective.client_id,
               dbDictionaryPerspective.object_id).in_(sound_persps_cte)).distinct().cte()
    audio_dicts_ids = DBSession.query(sound_dicts_cte).all()
    return audio_dicts_ids


def get_sound_field_ids():
    FieldTranslationAtom = aliased(dbTranslationAtom, name='FieldTranslationAtom')
    sound_field_id_list = DBSession.query(
        dbField.client_id, dbField.object_id).filter(
        dbField.marked_for_deletion == False,
        dbTranslationAtom.parent_client_id == dbField.data_type_translation_gist_client_id,
        dbTranslationAtom.parent_object_id == dbField.data_type_translation_gist_object_id,
        dbTranslationAtom.locale_id == 2,
        dbTranslationAtom.content == "Sound",
        dbTranslationAtom.marked_for_deletion == False,
        FieldTranslationAtom.parent_client_id == dbField.translation_gist_client_id,
        FieldTranslationAtom.parent_object_id == dbField.translation_gist_object_id,
        FieldTranslationAtom.locale_id == 2,
        FieldTranslationAtom.marked_for_deletion == False).all()
    return sound_field_id_list

# def get_not_text_field_ids():
#     FieldTranslationAtom = aliased(dbTranslationAtom, name='FieldTranslationAtom')
#     sound_field_id_list = DBSession.query(
#
#         dbField.client_id, dbField.object_id).filter(
#         dbField.marked_for_deletion == False,
#         dbTranslationAtom.parent_client_id == dbField.data_type_translation_gist_client_id,
#         dbTranslationAtom.parent_object_id == dbField.data_type_translation_gist_object_id,
#         dbTranslationAtom.locale_id == 2,
#         dbTranslationAtom.content != "Text",
#         dbTranslationAtom.marked_for_deletion == False,
#         FieldTranslationAtom.parent_client_id == dbField.translation_gist_client_id,
#         FieldTranslationAtom.parent_object_id == dbField.translation_gist_object_id,
#         FieldTranslationAtom.locale_id == 2,
#         FieldTranslationAtom.marked_for_deletion == False).all()
#     return sound_field_id_list


def save_xlsx(info, xlsx_context, xlsx_filename):

    xlsx_context.workbook.close()

    storage = info.context.request.registry.settings['storage']
    time_str = '{0:.6f}'.format(time.time())

    storage_dir = (

        os.path.join(
            storage['path'],
            'map_search',
            time_str))

    os.makedirs(storage_dir, exist_ok = True)

    xlsx_path = os.path.join(
        storage_dir, xlsx_filename)

    with open(xlsx_path, 'wb') as xlsx_file:

        xlsx_context.stream.seek(0)
        shutil.copyfileobj(xlsx_context.stream, xlsx_file)

    return ''.join([
        storage['prefix'],
        storage['static_route'],
        'map_search', '/',
        time_str, '/',
        xlsx_filename])


class AdvancedSearch(LingvodocObjectType):
    entities = graphene.List(Entity)
    lexical_entries = graphene.List(LexicalEntry)
    perspectives = graphene.List(DictionaryPerspective)
    dictionaries = graphene.List(Dictionary)
    xlsx_url = graphene.String()

    @classmethod
    def constructor(
        cls,
        info,
        languages,
        dicts_to_filter,
        tag_list,
        category,
        adopted,
        etymology,
        diacritics,
        search_strings,
        publish,
        accept,
        search_metadata,
        xlsx_export = False,
        cognates_flag = True,
        load_entities = True,
        __debug_flag__ = False):

        try:

            yield_batch_count = 200
            dictionaries = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter_by(
                marked_for_deletion=False)
            d_filter = []

            if dicts_to_filter:

                dictionary_ids = dicts_to_filter

                if len(dictionary_ids) > 2:
                    dictionary_ids = ids_to_id_cte_query(dictionary_ids)

                d_filter.append(tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(dictionary_ids))

            if languages:

                if dicts_to_filter:

                    dictionaries = dictionaries.join(dbLanguage)

                    language_ids = languages

                    if len(language_ids) > 2:
                        language_ids = ids_to_id_cte_query(language_ids)

                    d_filter.append(
                        and_(

                            tuple_(
                                dbDictionary.parent_client_id,
                                dbDictionary.parent_object_id)
                                .in_(language_ids),

                            dbLanguage.marked_for_deletion == False))

            dictionaries = dictionaries.filter(or_(*d_filter)).distinct()

            if publish:
                db_published_gist = translation_gist_search('Published')
                state_translation_gist_client_id = db_published_gist.client_id
                state_translation_gist_object_id = db_published_gist.object_id
                db_la_gist = translation_gist_search('Limited access')
                limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id

                dictionaries = (

                    dictionaries

                        .filter(
                            or_(and_(dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                                     dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id),
                                and_(dbDictionary.state_translation_gist_object_id == limited_object_id,
                                     dbDictionary.state_translation_gist_client_id == limited_client_id)))

                        .join(dbDictionaryPerspective)

                        .filter(
                            dbDictionaryPerspective.marked_for_deletion == False,
                            or_(
                                and_(dbDictionaryPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                                     dbDictionaryPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                                and_(dbDictionaryPerspective.state_translation_gist_object_id == limited_object_id,
                                     dbDictionaryPerspective.state_translation_gist_client_id == limited_client_id))))

            if search_metadata:
                meta_filter_ids = set()
                not_found_flag = False
                for meta_key in ["authors", "years"]:
                    meta_data = search_metadata.get(meta_key)
                    if meta_data:
                        dicts_with_tags = set()
                        for text_tag in meta_data:
                            single_tag_dicts = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter(
                                dbDictionary.marked_for_deletion == False,
                                dbDictionary.additional_metadata[meta_key] != None,
                                dbDictionary.additional_metadata[meta_key].contains([text_tag])).all()
                            dicts_with_tags.update(single_tag_dicts)
                        if dicts_with_tags:
                            meta_filter_ids.update(dicts_with_tags)
                        else:
                            not_found_flag = True
                kind = search_metadata.get("kind")
                if kind:
                    dicts_with_kind = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter(
                        dbDictionary.marked_for_deletion == False,
                        dbDictionary.additional_metadata["kind"] != None,
                        dbDictionary.additional_metadata["kind"].astext == kind).all()
                    if dicts_with_kind:
                        meta_filter_ids.update(dicts_with_kind)
                    else:
                        not_found_flag = True
                if "hasAudio" in search_metadata:
                    has_audio = search_metadata["hasAudio"]
                    if has_audio is not None:
                        if has_audio:
                            audio_dict_ids = dictionaries_with_audio_ids()
                            dictionaries = dictionaries\
                                .filter(
                                    tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(audio_dict_ids)
                                )
                        else:
                            audio_dict_ids = dictionaries_with_audio_ids()
                            dictionaries = dictionaries\
                                .filter(
                                    not_(
                                    tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(audio_dict_ids)
                                    )
                                )

                if not_found_flag:
                    dictionaries = []
                else:
                    if meta_filter_ids:
                        dictionaries = dictionaries \
                            .filter(tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(meta_filter_ids))
            if tag_list:
                tag_ids = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter(
                    dbDictionary.marked_for_deletion == False,
                    dbDictionary.additional_metadata["tag_list"] != None,
                    dbDictionary.additional_metadata["tag_list"].contains(tag_list)).all()
                dictionaries = dictionaries \
                    .filter(tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(tag_ids))

            res_entities = list()
            res_lexical_entries = list()
            res_perspectives = list()
            res_dictionaries = list()
            if not search_strings:
                res_dictionaries = [
                    graphene_obj(
                        DBSession.query(dbDictionary).filter(tuple_(dbDictionary.client_id, dbDictionary.object_id) == x).first(),
                        Dictionary) for x in dictionaries]
                perspective_objects = DBSession.query(dbDictionaryPerspective).filter(
                   dbDictionaryPerspective.marked_for_deletion==False,
                   tuple_(dbDictionaryPerspective.parent_client_id,
                   dbDictionaryPerspective.parent_object_id).in_([(x.dbObject.client_id, x.dbObject.object_id) for x in res_dictionaries])).all()
                res_perspectives = [graphene_obj(x, DictionaryPerspective) for x in perspective_objects]

                return cls(entities=[], lexical_entries=[], perspectives=res_perspectives, dictionaries=res_dictionaries)



            text_data_type = translation_gist_search('Text')

            text_field_query = DBSession.query(dbField.client_id, dbField.object_id).\
                filter(dbField.data_type_translation_gist_client_id == text_data_type.client_id,
                       dbField.data_type_translation_gist_object_id == text_data_type.object_id)

            markup_data_type = translation_gist_search('Markup')
            markup_field_query = DBSession.query(dbField.client_id, dbField.object_id). \
                filter(dbField.data_type_translation_gist_client_id == markup_data_type.client_id,
                       dbField.data_type_translation_gist_object_id == markup_data_type.object_id)

            # Setting up export to an XLSX file, if required.

            xlsx_context = (

                None if not xlsx_export else

                Save_Context(
                    info.context.get('locale_id'),
                    DBSession,
                    cognates_flag = cognates_flag,
                    __debug_flag__ = __debug_flag__))

            # normal dictionaries
            if category != 1:
                res_entities, res_lexical_entries, res_perspectives, res_dictionaries = search_mechanism(
                    dictionaries=dictionaries,
                    category=0,
                    search_strings=search_strings,
                    publish=publish,
                    accept=accept,
                    adopted=adopted,
                    etymology=etymology,
                    diacritics=diacritics,
                    category_field_cte_query=DBSession.query(text_field_query.cte()),
                    yield_batch_count=yield_batch_count,
                    xlsx_context=xlsx_context,
                    load_entities=load_entities,
                    __debug_flag__=__debug_flag__
                )

            # corpora
            if category != 0:
                tmp_entities, tmp_lexical_entries, tmp_perspectives, tmp_dictionaries = search_mechanism(
                    dictionaries=dictionaries,
                    category=1,
                    search_strings=search_strings,
                    publish=publish,
                    accept=accept,
                    adopted=adopted,
                    etymology=etymology,
                    diacritics=diacritics,
                    category_field_cte_query=DBSession.query(markup_field_query.cte()),
                    yield_batch_count=yield_batch_count,
                    xlsx_context=xlsx_context,
                    load_entities=load_entities,
                    __debug_flag__=__debug_flag__
                )
                res_entities += tmp_entities
                res_lexical_entries += tmp_lexical_entries
                res_perspectives += tmp_perspectives
                res_dictionaries += tmp_dictionaries

            # Exporting search results as an XLSX data, if required.

            if xlsx_context is not None:

                if __debug_flag__:

                    start_time = time.time()

                save_xlsx_data(
                    xlsx_context,
                    [dictionary.dbObject for dictionary in res_dictionaries],
                    [perspective.dbObject for perspective in res_perspectives],
                    [lexical_entry.dbObject for lexical_entry in res_lexical_entries])

                if __debug_flag__:

                    elapsed_time = time.time() - start_time
                    resident_memory = utils.get_resident_memory()

                    log.debug(
                        '\nelapsed_time, resident_memory: {0:.3f}s, {1:.3f}m'.format(
                        elapsed_time,
                        resident_memory / 1048576.0))

            # Saving XLSX-exported search results, if required.

            xlsx_url = None
            
            if xlsx_export:

                query_str = '_'.join([
                    search_string["search_string"]
                    for search_block in search_strings
                    for search_string in search_block])

                xlsx_filename = ('Search_' + query_str)[:64] + '.xlsx'

                xlsx_url = save_xlsx(
                    info, xlsx_context, xlsx_filename)

                # Saving resulting Excel workbook for debug purposes, if required.

                if __debug_flag__:

                    xlsx_context.stream.seek(0)

                    with open(xlsx_filename, 'wb') as xlsx_file:
                        shutil.copyfileobj(xlsx_context.stream, xlsx_file)

            return cls(
                entities=res_entities,
                lexical_entries=res_lexical_entries,
                perspectives=res_perspectives,
                dictionaries=res_dictionaries,
                xlsx_url=xlsx_url)

        except Exception as exception:

            traceback_string = (
                    
                ''.join(
                    traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1])

            log.warning('advanced_search: exception')
            log.warning(traceback_string)

            return (
                ResponseError(
                    message = 'Exception:\n' + traceback_string))


class AdvancedSearchSimple(LingvodocObjectType):
    entities = graphene.List(Entity)
    lexical_entries = graphene.List(LexicalEntry)
    perspectives = graphene.List(DictionaryPerspective)
    dictionaries = graphene.List(Dictionary)
    xlsx_url = graphene.String()

    @classmethod
    def constructor(
        cls,
        info,
        languages,
        dicts_to_filter,
        tag_list,
        category,
        adopted,
        etymology,
        search_strings,
        publish,
        accept,
        xlsx_export = False,
        cognates_flag = True,
        __debug_flag__ = False):

        yield_batch_count = 200
        dictionaries = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter_by(
            marked_for_deletion=False)
        d_filter = []
        if dicts_to_filter:
            d_filter.append(tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(dicts_to_filter))
        if languages:
            if dicts_to_filter:
                d_filter.append(
                    tuple_(dbDictionary.parent_client_id, dbDictionary.parent_object_id).in_(languages)
                )
        dictionaries = dictionaries.filter(or_(*d_filter)).distinct()
        if tag_list:
            dictionaries = dictionaries.filter(dbDictionary.additional_metadata["tag_list"].contains(tag_list))

        res_entities = list()
        res_lexical_entries = list()
        res_perspectives = list()
        res_dictionaries = list()

        db_published_gist = translation_gist_search('Published')
        state_translation_gist_client_id = db_published_gist.client_id
        state_translation_gist_object_id = db_published_gist.object_id
        db_la_gist = translation_gist_search('Limited access')
        limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id

        text_data_type = translation_gist_search('Text')
        text_fields = DBSession.query(dbField.client_id, dbField.object_id).\
            filter(dbField.data_type_translation_gist_client_id == text_data_type.client_id,
                   dbField.data_type_translation_gist_object_id == text_data_type.object_id).all()

        markup_data_type = translation_gist_search('Markup')
        markup_fields = DBSession.query(dbField.client_id, dbField.object_id). \
            filter(dbField.data_type_translation_gist_client_id == markup_data_type.client_id,
                   dbField.data_type_translation_gist_object_id == markup_data_type.object_id).all()

        # Setting up export to an XLSX file, if required.

        xlsx_context = (

            None if not xlsx_export else

            Save_Context(
                info.context.get('locale_id'),
                DBSession,
                cognates_flag = cognates_flag,
                __debug_flag__ = __debug_flag__))

        # normal dictionaries
        if category != 1:
            res_entities, res_lexical_entries, res_perspectives, res_dictionaries = search_mechanism_simple(
                dictionaries=dictionaries,
                category=0,
                state_gist_id = (state_translation_gist_client_id,
                                state_translation_gist_object_id),
                limited_gist_id = (limited_client_id, limited_object_id),
                search_strings=search_strings,
                publish=publish,
                accept=accept,
                adopted=adopted,
                etymology=etymology,
                category_fields=text_fields,
                yield_batch_count=yield_batch_count,
                xlsx_context=xlsx_context
            )


        # corpora
        if category != 0:
            tmp_entities, tmp_lexical_entries, tmp_perspectives, tmp_dictionaries = search_mechanism_simple(
                dictionaries=dictionaries,
                category=1,
                state_gist_id=(state_translation_gist_client_id,
                               state_translation_gist_object_id),
                limited_gist_id=(limited_client_id,
                                 limited_object_id),
                search_strings=search_strings,
                publish=publish,
                accept=accept,
                adopted=adopted,
                etymology=etymology,
                category_fields=markup_fields,
                yield_batch_count=yield_batch_count,
                xlsx_context=xlsx_context
            )
            res_entities += tmp_entities
            res_lexical_entries += tmp_lexical_entries
            res_perspectives += tmp_perspectives
            res_dictionaries += tmp_dictionaries

        # Exporting search results as an XLSX data, if required.

        if xlsx_context is not None:

            save_xlsx_data(
                xlsx_context,
                [dictionary.dbObject for dictionary in res_dictionaries],
                [perspective.dbObject for perspective in res_perspectives],
                [lexical_entry.dbObject for lexical_entry in res_lexical_entries])

        # Saving XLSX-exported search results, if required.

        xlsx_url = None
        
        if xlsx_export:

            query_str = '_'.join([
                search_string["search_string"]
                for search_block in search_strings
                for search_string in search_block])

            xlsx_filename = ('Search_' + query_str)[:64] + '.xlsx'

            xlsx_url = save_xlsx(
                info, xlsx_context, xlsx_filename)

            # Saving resulting Excel workbook for debug purposes, if required.

            if __debug_flag__:

                xlsx_context.stream.seek(0)

                with open(xlsx_filename, 'wb') as xlsx_file:
                    shutil.copyfileobj(xlsx_context.stream, xlsx_file)

        return cls(
            entities=res_entities,
            lexical_entries=res_lexical_entries,
            perspectives=res_perspectives,
            dictionaries=res_dictionaries,
            xlsx_url=xlsx_url)


class EafSearch(LingvodocObjectType):

    result_list = graphene.List(ObjectVal)
    xlsx_url = graphene.String()

    @classmethod
    def constructor(
        cls,
        info,
        perspective_id = None,
        search_query = None,
        __debug_flag__ = False):

        log.debug(
            '\neaf_search'
            '\n  perspective_id: {0}'
            '\n  search_query: {1}'
            '\n  __debug_flag__: {2}'.format(
                perspective_id,
                search_query,
                __debug_flag__))

        # Getting query string to use for XLSX file name.

        def f(query_dict):

            value = query_dict.get('value')

            if isinstance(value, list):

                for generator in map(f, value):
                    yield from generator

            elif isinstance(value, str):

                yield value

        query_str = '_'.join(f(search_query))

        xlsx_filename = (
            ('Search_' + query_str)[:64] + '.xlsx')

        # Constructing path and URL to the resulting XLSX file.

        storage = info.context.request.registry.settings['storage']
        time_str = '{0:.6f}'.format(time.time())

        storage_dir = (

            os.path.join(
                storage['path'],
                'eaf_search',
                time_str))

        os.makedirs(storage_dir, exist_ok = True)

        xlsx_path = os.path.join(
            storage_dir, xlsx_filename)

        xlsx_url = ''.join([
            storage['prefix'],
            storage['static_route'],
            'eaf_search', '/',
            time_str, '/',
            xlsx_filename])

        log.debug(
            '\neaf_search'
            '\n  xlsx_path: {0}'
            '\n  xlsx_url: {1}'.format(
                xlsx_path,
                xlsx_url))

        # Preparing to get EAF data.

        field_query = (DBSession
                
            .query(
                dbField.client_id, dbField.object_id)

            .filter(
                dbField.marked_for_deletion == False,
                dbField.data_type_translation_gist_client_id == dbTranslationGist.client_id,
                dbField.data_type_translation_gist_object_id == dbTranslationGist.object_id,
                dbTranslationGist.marked_for_deletion == False,
                dbTranslationAtom.parent_client_id == dbTranslationGist.client_id,
                dbTranslationAtom.parent_object_id == dbTranslationGist.object_id,
                dbTranslationAtom.marked_for_deletion == False,
                dbTranslationAtom.locale_id == 2,
                dbTranslationAtom.content == 'Markup'))

        eaf_query = (DBSession
                
            .query(
                dbEntity.client_id,
                dbEntity.object_id,
                dbEntity.content)

            .filter(
                tuple_(dbEntity.field_client_id, dbEntity.field_object_id)
                    .in_(field_query.subquery()),
                dbEntity.marked_for_deletion == False,
                dbEntity.parent_client_id == dbLexicalEntry.client_id,
                dbEntity.parent_object_id == dbLexicalEntry.object_id,
                dbEntity.content.op('~*')('.*\\.eaf.*'),
                dbLexicalEntry.marked_for_deletion == False,
                dbLexicalEntry.moved_to == None))

        if perspective_id is not None:

            eaf_query = eaf_query.filter(
                dbLexicalEntry.parent_client_id == perspective_id[0],
                dbLexicalEntry.parent_object_id == perspective_id[1])

        else:

            eaf_query = eaf_query.filter(
                dbLexicalEntry.parent_client_id == dbDictionaryPerspective.client_id,
                dbLexicalEntry.parent_object_id == dbDictionaryPerspective.object_id,
                dbDictionaryPerspective.marked_for_deletion == False)

        eaf_count = eaf_query.count()

        # Processing EAF corpora.

        result_list = []

        open(xlsx_path, 'w').close()

        storage_f = (
            as_storage_file if __debug_flag__ else storage_file)

        for index, (entity_client_id, entity_object_id, eaf_url) in (
            enumerate(eaf_query.yield_per(256))):

            log.debug(
                '\neaf_search {0}/{1}: entity {2}/{3} {4}'.format(
                    index + 1,
                    eaf_count,
                    entity_client_id,
                    entity_object_id,
                    repr(eaf_url)))

            sheet_name = (
                'entity_{0}_{1}'.format(
                    entity_client_id, entity_object_id))

            with storage_f(storage, eaf_url) as eaf_file:

                eaf_search(
                    eaf_file,
                    xlsx_path,
                    search_query,
                    sheet_name,
                    result_list)

        # If we do not have any results, we try to ensure that no unnecessary empty XLSX files are left.

        if not result_list:
            
            try:
                os.remove(xlsx_path)

            except:
                pass

            xlsx_url = None

        # Saving debug copy, if required.

        elif __debug_flag__:
            shutil.copy(xlsx_path, '__eaf_search__.xlsx')

        log.debug(
            '\neaf_search'
            '\nlen(result_list): {0}'
            '\nresult_list: {1}'.format(
                len(result_list),
                pprint.pformat(result_list, width = 192)))

        return cls(
            result_list = result_list,
            xlsx_url = xlsx_url)

