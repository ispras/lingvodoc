import itertools

import graphene
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
    LingvodocID
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
from lingvodoc.utils.search import translation_gist_search

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_,
    not_,
    exists,
    union
)
from sqlalchemy.orm.util import aliased
from itertools import chain


import re


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

def search_mechanism(dictionaries, category, state_gist_id, limited_gist_id, search_strings, publish, accept, adopted,
                     etymology, yield_batch_count, category_fields):


    """
    1) published dictionaries
    2) field filter
    3) metadata filter
    4)
    """
    # 1) old filter

    lexes = DBSession.query(dbLexicalEntry.client_id, dbLexicalEntry.object_id).join(dbLexicalEntry.parent) \
        .join(dbDictionaryPerspective.parent).filter(
        dbLexicalEntry.parent_client_id==dbDictionaryPerspective.client_id,
        dbLexicalEntry.parent_object_id==dbDictionaryPerspective.object_id,
        dbDictionaryPerspective.marked_for_deletion==False,
        dbLexicalEntry.marked_for_deletion==False,
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

    lexes = lexes.all()
    lexes = set([tuple(x) for x in lexes])

    # get all_entity_content_filter

    all_entity_content_filter = list()
    all_block_fields = list()
    fields_flag = True
    if category == 0:
        for search_block in search_strings:
            all_block_fields+=[tuple(sb.get("field_id")) for sb in search_block if
                            sb.get("field_id") and tuple(sb.get("field_id")) in category_fields]
            for search_string in search_block:
                if not search_string.get("field_id"):
                    fields_flag = False

                if search_string.get('matching_type') == "substring":
                    curr_bs_search_blocks = boolean_search(search_string["search_string"])
                    for ss in chain.from_iterable(curr_bs_search_blocks):
                        if ss.get('matching_type') == "substring":
                            all_entity_content_filter.append(
                                func.lower(dbEntity.content).like(ss["search_string"]))
                        elif ss.get('matching_type') == "full_string":
                            all_entity_content_filter.append(
                                func.lower(dbEntity.content) == func.lower(ss["search_string"])
                            )
                        elif ss.get('matching_type') == "regexp":
                            all_entity_content_filter.append(
                                func.lower(dbEntity.content).op('~*')(ss["search_string"]))

                elif search_string.get('matching_type') == "full_string":
                    all_entity_content_filter.append(
                        func.lower(dbEntity.content) == func.lower(search_string["search_string"]))
                elif search_string.get('matching_type') == "regexp":
                    all_entity_content_filter.append(
                        func.lower(dbEntity.content).op('~*')(search_string["search_string"]))
    elif category == 1:
        for search_block in search_strings:
            for search_string in search_block:
                if not search_string.get("field_id"):
                    fields_flag = False
                if search_string.get('matching_type') == "substring":
                    curr_bs_search_blocks = boolean_search(search_string["search_string"])
                    for ss in chain.from_iterable(curr_bs_search_blocks):
                        if ss.get('matching_type') == "substring":
                            corpus_word_list = func.lower(dbEntity.additional_metadata['bag_of_words'].astext)
                            all_entity_content_filter.append(func.lower(corpus_word_list).like(ss["search_string"]))
                        elif ss.get('matching_type') == "full_string":
                            all_entity_content_filter.append(dbEntity.additional_metadata['bag_of_words'].contains(
                        [ss["search_string"].lower()]))
                        elif ss.get('matching_type') == "regexp":
                            all_entity_content_filter.append(
                                func.lower(dbEntity.additional_metadata['bag_of_words'].astext).op('~*')(
                                    ss["search_string"]))

                elif search_string.get('matching_type') == "full_string":
                    all_entity_content_filter.append(dbEntity.additional_metadata['bag_of_words'].contains(
                        [search_string["search_string"].lower()]))
                elif search_string.get('matching_type') == "regexp":
                    all_entity_content_filter.append(
                                func.lower(dbEntity.additional_metadata['bag_of_words'].astext).op('~*')(
                                    search_string["search_string"]))

    # all_entity_content_filter = and_(or_(*all_entity_content_filter))

    if fields_flag and category==0:

        all_entity_content_filter=and_(or_(*all_entity_content_filter),

            tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(all_block_fields)
        )
    else:
        all_entity_content_filter=and_(or_(*all_entity_content_filter),
            tuple_(dbEntity.field_client_id, dbEntity.field_object_id).in_(category_fields)
        )

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
                #tuple_(dbEntity.parent_client_id, dbEntity.parent_object_id).in_(lexes),
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
            if 'field_id' in search_string:
                inner_and.append(cur_dbEntity.field_client_id == search_string["field_id"][0])
                inner_and.append(cur_dbEntity.field_object_id == search_string["field_id"][1])
            else:
                inner_and.append(tuple_(cur_dbEntity.field_client_id,
                                        cur_dbEntity.field_object_id).in_(category_fields))

            matching_type = search_string.get('matching_type')
            if not matching_type in ("full_string", "substring", "regexp", "exclude"):
                raise ResponseError(message='wrong matching_type')

            if category == 1:
                if matching_type == "full_string":
                    inner_and.append(cur_dbEntity.additional_metadata['bag_of_words'].contains(
                        [search_string["search_string"].lower()]))
                elif matching_type == 'substring':
                    curr_bs_search_blocks = boolean_search(search_string["search_string"])
                    for ss in chain.from_iterable(curr_bs_search_blocks):
                        if ss.get('matching_type') == "substring":
                            corpus_word_list = func.lower(cur_dbEntity.additional_metadata['bag_of_words'].astext)
                            inner_and.append(func.lower(corpus_word_list).like(ss["search_string"]))
                        elif ss.get('matching_type') == "full_string":
                            inner_and.append(dbEntity.additional_metadata['bag_of_words'].contains(
                        [ss["search_string"].lower()]))
                        elif ss.get('matching_type') == "regexp":
                            inner_and.append(
                                func.lower(dbEntity.additional_metadata['bag_of_words'].astext).op('~*')(
                                    ss["search_string"]))
                elif matching_type == 'regexp':
                    inner_and.append(func.lower(cur_dbEntity.additional_metadata['bag_of_words'].astext).op('~*')(
                        search_string["search_string"]))
            else:
                if matching_type == "full_string":
                    inner_and.append(func.lower(cur_dbEntity.content) == func.lower(search_string["search_string"]))
                elif matching_type == 'substring':
                    curr_bs_search_blocks = boolean_search(search_string["search_string"])
                    bs_or_block_list = list()
                    for bs_or_block in curr_bs_search_blocks:
                        bs_and = list()
                        for ss in bs_or_block:
                            if ss.get('matching_type') == "substring":
                                bs_and.append(func.lower(cur_dbEntity.content).like(ss["search_string"]))
                            elif ss.get('matching_type') == "full_string":
                                bs_and.append(
                                    func.lower(cur_dbEntity.content) == func.lower(ss["search_string"]))
                            elif ss.get('matching_type') == "regexp":
                                bs_and.append(func.lower(cur_dbEntity.content).op('~*')(ss["search_string"]))
                            elif ss.get('matching_type') == "exclude":
                                bs_and.append(func.lower(cur_dbEntity.content) != func.lower(ss["search_string"]))
                        bs_or_block_list.append(and_(*bs_and))
                    inner_and.append(or_(*bs_or_block_list))
                elif matching_type == 'regexp':
                    inner_and.append(func.lower(cur_dbEntity.content).op('~*')(search_string["search_string"]))
            and_lexes = DBSession.query(all_entities_cte.c.parent_client_id,
                                all_entities_cte.c.parent_object_id)\
                                .filter(and_(*inner_and).self_group())\
                                .yield_per(yield_batch_count).distinct().all()
            and_lexes_sum.append(set([tuple(x) for x in and_lexes if tuple(x) in lexes]))


        and_lexes_inter = set.intersection(*[x for x in and_lexes_sum])
        full_or_block.append(and_lexes_inter)

    all_results = set()
    for or_element in full_or_block:
        all_results = all_results.union(or_element)

    if not all_results:
        return [], [], [], []
    resolved_search = DBSession.query(dbLexicalEntry)\
        .filter(dbLexicalEntry.marked_for_deletion==False,
                tuple_(dbLexicalEntry.client_id,
                       dbLexicalEntry.object_id).in_(list(all_results )))
    result_lexical_entries = entries_with_entities(resolved_search, accept=True, delete=False, mode=None, publish=True)

    def graphene_obj(dbobj, cur_cls):
        obj = cur_cls(id=(dbobj.client_id, dbobj.object_id))
        obj.dbObject = dbobj
        return obj

    #result_lexical_entries = [graphene_obj(x, LexicalEntry) for x in resolved_search.all()]
    tmp_perspectives = set([le.dbObject.parent for le in result_lexical_entries])
    res_perspectives = [graphene_obj(dbpersp, DictionaryPerspective) for dbpersp in tmp_perspectives]
    tmp_dictionaries = set([le.dbObject.parent for le in res_perspectives])
    res_dictionaries = [graphene_obj(dbdict, Dictionary) for dbdict in tmp_dictionaries]
    return [], result_lexical_entries, res_perspectives , res_dictionaries

def search_mechanism_simple(dictionaries, category, state_gist_id, limited_gist_id, search_strings, publish, accept, adopted,
                     etymology, yield_batch_count, category_fields):
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
            if 'field_id' in search_string:
                inner_and_block.append(cur_dbEntity.field_client_id == search_string["field_id"][0])
                inner_and_block.append(cur_dbEntity.field_object_id == search_string["field_id"][1])
            else:
                inner_and_block.append(tuple_(cur_dbEntity.field_client_id, cur_dbEntity.field_object_id).in_(category_fields))

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

class AdvancedSearch(LingvodocObjectType):
    entities = graphene.List(Entity)
    lexical_entries = graphene.List(LexicalEntry)
    perspectives = graphene.List(DictionaryPerspective)
    dictionaries = graphene.List(Dictionary)

    @classmethod
    def constructor(cls, languages, dicts_to_filter, tag_list, category, adopted, etymology, search_strings, publish, accept, search_metadata):
        yield_batch_count = 200
        dictionaries = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter_by(
            marked_for_deletion=False)
        if dicts_to_filter:
            dictionaries = dictionaries.filter(
                tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(dicts_to_filter))
        if languages:
            lang_dicts = dictionaries.join(dbDictionary.parent).filter(
                tuple_(dbDictionary.parent_client_id, dbDictionary.parent_object_id).in_(languages))
            dictionaries = dictionaries.union(lang_dicts)
        if tag_list:
            dictionaries = dictionaries.filter(dbDictionary.additional_metadata["tag_list"].contains(tag_list))
        if publish:
            db_published_gist = translation_gist_search('Published')
            state_translation_gist_client_id = db_published_gist.client_id
            state_translation_gist_object_id = db_published_gist.object_id
            db_la_gist = translation_gist_search('Limited access')
            limited_client_id, limited_object_id = db_la_gist.client_id, db_la_gist.object_id
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

        if search_metadata:
            if "kind" in search_metadata:
                kind = search_metadata.get("kind")
                if kind:
                    dictionaries = dictionaries.filter(
                        dbDictionary.additional_metadata["kind"] != None,
                        dbDictionary.additional_metadata["kind"].astext == kind)
            if "authors" in search_metadata:
                authors = search_metadata.get("authors")
                if authors:
                    dictionaries = dictionaries.filter(
                        dbDictionary.additional_metadata["authors"] != None,
                        dbDictionary.additional_metadata["authors"].contains(authors))
            if "years" in search_metadata:
                years = search_metadata.get("years")
                if years:
                    dictionaries = dictionaries.filter(
                        dbDictionary.additional_metadata["years"] != None,
                        dbDictionary.additional_metadata["years"].contains(years))
            if "hasAudio" in search_metadata:
                has_audio = search_metadata["hasAudio"]
                if has_audio is not None:
                    if has_audio:
                        audio_dict_ids = dictionaries_with_audio_ids()
                        dictionaries = dictionaries\
                            .filter(tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(audio_dict_ids))
                    else:
                        audio_dict_ids = dictionaries_with_audio_ids()
                        dictionaries = dictionaries\
                            .filter(
                                not_(
                                tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(audio_dict_ids)
                                )
                            )



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
        text_fields = DBSession.query(dbField.client_id, dbField.object_id).\
            filter(dbField.data_type_translation_gist_client_id == text_data_type.client_id,
                   dbField.data_type_translation_gist_object_id == text_data_type.object_id).all()

        markup_data_type = translation_gist_search('Markup')
        markup_fields = DBSession.query(dbField.client_id, dbField.object_id). \
            filter(dbField.data_type_translation_gist_client_id == markup_data_type.client_id,
                   dbField.data_type_translation_gist_object_id == markup_data_type.object_id).all()

        # normal dictionaries
        if category != 1:
            res_entities, res_lexical_entries, res_perspectives, res_dictionaries = search_mechanism(
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
                yield_batch_count=yield_batch_count
            )


        # corpora
        if category != 0:
            tmp_entities, tmp_lexical_entries, tmp_perspectives, tmp_dictionaries = search_mechanism(
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
                yield_batch_count=yield_batch_count
            )
            res_entities += tmp_entities
            res_lexical_entries += tmp_lexical_entries
            res_perspectives += tmp_perspectives
            res_dictionaries += tmp_dictionaries

        return cls(entities=res_entities, lexical_entries=res_lexical_entries, perspectives=res_perspectives, dictionaries=res_dictionaries)


class AdvancedSearchSimple(LingvodocObjectType):
    entities = graphene.List(Entity)
    lexical_entries = graphene.List(LexicalEntry)
    perspectives = graphene.List(DictionaryPerspective)
    dictionaries = graphene.List(Dictionary)

    @classmethod
    def constructor(cls, languages, dicts_to_filter, tag_list, category, adopted, etymology, search_strings, publish, accept):
        yield_batch_count = 200
        dictionaries = DBSession.query(dbDictionary.client_id, dbDictionary.object_id).filter_by(
            marked_for_deletion=False)
        if dicts_to_filter:
            dictionaries = dictionaries.filter(
                tuple_(dbDictionary.client_id, dbDictionary.object_id).in_(dicts_to_filter))
        if languages:
            lang_dicts = dictionaries.join(dbDictionary.parent).filter(
                tuple_(dbDictionary.parent_client_id, dbDictionary.parent_object_id).in_(languages))
            dictionaries = dictionaries.union(lang_dicts)
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
                yield_batch_count=yield_batch_count
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
                yield_batch_count=yield_batch_count
            )
            res_entities += tmp_entities
            res_lexical_entries += tmp_lexical_entries
            res_perspectives += tmp_perspectives
            res_dictionaries += tmp_dictionaries

        return cls(entities=res_entities, lexical_entries=res_lexical_entries, perspectives=res_perspectives, dictionaries=res_dictionaries)
