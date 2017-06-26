import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    CreatedAt,
    MarkedForDeletion,
    TypeHolder
)

from lingvodoc.models import (
    TranslationGist as dbTranslationGist,
)
class TranslationGist(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #type                | text                        |
    """
    dbType = dbTranslationGist
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder,
                      CreatedAt,
                      MarkedForDeletion,
                      TypeHolder

                      )
