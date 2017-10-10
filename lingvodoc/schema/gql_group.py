import graphene
from lingvodoc.models import (
    Grant as dbGroup,
)
from lingvodoc.schema.gql_holders import (
    IdHolder,
    CreatedAt,
    LingvodocID
)
class Group(graphene.ObjectType):
    """
     #created_at        | timestamp without time zone | NOT NULL
     #id                | uuid                        | NOT NULL
     #old_id            | bigint                      |
     #base_group_id     | bigint                      | NOT NULL
     #subject_client_id | bigint                      |
     #subject_object_id | bigint                      |
     #subject_override  | boolean                     |
    """
    dbType = dbGroup
    dbObject = None
    old_id = graphene.String() # uuid
    base_group_id = graphene.Int()
    subject_id = LingvodocID()
    subject_override = graphene.Boolean()

    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                    )
    pass