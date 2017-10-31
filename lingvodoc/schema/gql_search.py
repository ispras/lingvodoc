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
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    DBSession
)

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_
)
from lingvodoc.views.v2.utils import add_user_to_group



class AdvancedSearch(graphene.ObjectType):

    def constructor(self, languages, tag_list, category, adopted, etymology, search_strings):
        dictionaries = DBSession.query(dbDictionary)
        if languages:
            dictionaries = dictionaries.join(dbDictionary.parent).filter(
                tuple_(dbDictionary.parent_client_id, dbDictionary.parent_object_id).in_(languages))
        if tag_list:
            # all tags should be in additional_metadata under tag_list key
            dictionaries = dictionaries
        if category is not None:
            dictionaries = dictionaries.filter(dbDictionary.category == category)

        basic_search = DBSession.query(dbLexicalEntry)\
            .join(dbLexicalEntry.parent).join(dbDictionaryPerspective.parent)
        or_block = list()
        for search_block in search_strings:
            and_block = list()
            for search_string in search_block:
                and_block.append(content = search_string)
            or_block.append(and_(and_block))
        or_block = or_(or_block)

        search = basic_search.filter(or_block, dbDictionary.in_(dictionaries))