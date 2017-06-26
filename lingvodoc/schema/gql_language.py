import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    Language as dbLanguage,
    Dictionary as dbDictionary,
    DBSession
)

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    TranslationHolder,
    fetch_object
)
from lingvodoc.schema.gql_dictionary import Dictionary


class Language(graphene.ObjectType):
    """
     #created_at                 | timestamp without time zone | NOT NULL
     #object_id                  | bigint                      | NOT NULL
     #client_id                  | bigint                      | NOT NULL
     #parent_object_id           | bigint                      |
     #parent_client_id           | bigint                      |
     #translation_gist_client_id | bigint                      | NOT NULL
     #translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion        | boolean                     | NOT NULL
     #additional_metadata        | jsonb                       |
     + translation
    """
    dbType = dbLanguage
    dbObject = None

    dataType = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, TranslationHolder)
    @fetch_object()
    def resolve_dictionaries(self, args, context, info):
        result = list()
        for dictionary in DBSession.query(dbDictionary).filter(and_(dbDictionary.parent_object_id == self.dbObject.object_id,
                                                         dbDictionary.parent_client_id == self.dbObject.client_id)):
            result.append(Dictionary(id=[dictionary.client_id, dictionary.object_id]))
        return result

    def resolve_dataType(self, args, context, info):
        return 'language'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))

    #@fetch_object()
    #def resolve_created_at(self, args, context, info):
    #    return self.dbObject.created_at