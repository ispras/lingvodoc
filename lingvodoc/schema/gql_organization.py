import graphene
from lingvodoc.schema.gql_holders import (CreatedAt,
    IdHolder,
    MarkedForDeletion,
    AdditionalMetadata,
    Name,
    About
)
from lingvodoc.models import (
    Grant as dbOrganization,
)
class Organization(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL DEFAULT nextval('organization_id_seq'::regclass)
     #marked_for_deletion | boolean                     | NOT NULL
     #name                | text                        |
     #about               | text                        |
     #additional_metadata | jsonb                       |
    """
    dbType = dbOrganization
    dbObject = None
    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                      MarkedForDeletion,
                      AdditionalMetadata,
                      Name,
                      About
                    )
    pass