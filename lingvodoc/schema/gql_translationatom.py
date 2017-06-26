import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    Relationship,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    Content,
    LocaleId
)
from lingvodoc.models import (
    TranslationAtom as dbTranslationAtom,
)


class TranslationAtom(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #locale_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #content             | text                        | NOT NULL
     #additional_metadata | jsonb                       |
    """
    dbType = dbTranslationAtom
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder, Relationship, AdditionalMetadata, CreatedAt, MarkedForDeletion,  Content, LocaleId)
    pass