import graphene
from lingvodoc.models import (
    Grant as dbGrant,
)
from lingvodoc.schema.gql_holders import (
    DateTime,
    JSONString,
    IdHolder,
    CreatedAt,
    AdditionalMetadata,
    TranslationGistHolder
)

class Grant(graphene.ObjectType):
    """
     #id                                | bigint                      | NOT NULL DEFAULT nextval('grant_id_seq'::regclass)
     #translation_gist_client_id        | bigint                      | NOT NULL
     #translation_gist_object_id        | bigint                      | NOT NULL
     #issuer_translation_gist_client_id | bigint                      | NOT NULL
     #issuer_translation_gist_object_id | bigint                      | NOT NULL
     #begin                             | date                        |
     #end                               | date                        |
     #created_at                        | timestamp without time zone | NOT NULL
     #issuer_url                        | character varying(2048)     | NOT NULL
     #grant_url                         | character varying(2048)     | NOT NULL
     #grant_number                      | character varying(1000)     | NOT NULL
     #owners                            | jsonb                       |
     #additional_metadata               | jsonb                       |
    """
    dbType = dbGrant
    dbObject = None
    issuer_translation_gist_id = graphene.Int()
    begin = DateTime()
    end = DateTime()
    issuer_url = graphene.String()
    grant_url = graphene.String()
    grant_number = graphene.String()
    owners = JSONString()

    class Meta:
        interfaces = (CreatedAt,
                      TranslationGistHolder,
                      IdHolder,
                      AdditionalMetadata
                    )
    pass

