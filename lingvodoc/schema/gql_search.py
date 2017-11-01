import graphene
from lingvodoc.schema.gql_holders import (CreatedAt,
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
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    DBSession
)
from lingvodoc.schema.gql_entity import Entity

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_
)


class AdvancedSearch(graphene.ObjectType):
    entities = graphene.Field(Entity)
    @classmethod
    def constructor(cls, languages, tag_list, category, adopted, etymology, search_strings):
        dictionaries = DBSession.query(dbDictionary)
        if languages:
            dictionaries = dictionaries.join(dbDictionary.parent).filter(
                tuple_(dbDictionary.parent_client_id, dbDictionary.parent_object_id).in_(languages))
        if tag_list:
            # all tags should be in additional_metadata under tag_list key
            dictionaries = dictionaries
        if category is not None:
            dictionaries = dictionaries.filter(dbDictionary.category == category)

        basic_search = DBSession.query(dbEntity).join(dbEntity.parent)\
            .join(dbLexicalEntry.parent).join(dbDictionaryPerspective.parent)
        and_block = list()
        for search_block in search_strings:
            or_block = list()
            for search_string in search_block:
                inner_and_block = list()
                if 'field_id' in search_string:
                    inner_and_block.append(dbEntity.field_client_id == search_string["field_id"][0])
                    inner_and_block.append(dbEntity.field_object_id == search_string["field_id"][1])
                matching_type = search_string.get('matching_type')
                if matching_type == "full_string":
                    inner_and_block.append(dbEntity.content == search_string["search_string"])
                elif matching_type == 'substring':
                    inner_and_block.append(dbEntity.content.like("".join(['%', search_string["search_string"], '%'])))
                elif matching_type == 'regexp':
                    inner_and_block.append(dbEntity.content.op('~*')(search_string["search_string"]))

                or_block.append(and_(inner_and_block))

            and_block.append(or_(or_block))
        and_block = and_(and_block)

        search = basic_search.filter(and_block, dbDictionary.in_(dictionaries))

    def resolve_entities(self, info):
        pass
