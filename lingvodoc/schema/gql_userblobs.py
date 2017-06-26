import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    UserId,
    Content,
    DataType
)

from lingvodoc.models import (
    UserBlobs as dbUserBlobs,
)

class UserBlobs(graphene.ObjectType):
    """
    #created_at          | timestamp without time zone | NOT NULL
    #object_id           | bigint                      | NOT NULL
    #client_id           | bigint                      | NOT NULL
    #marked_for_deletion | boolean                     | NOT NULL
    #user_id             | bigint                      |
    #name                | text                        | NOT NULL
    #content             | text                        | NOT NULL
    #real_storage_path   | text                        | NOT NULL
    #data_type           | text                        | NOT NULL
    #additional_metadata | jsonb                       |
    """
    dbType = dbUserBlobs
    dbObject = None
    real_storage_path = graphene.String()

    class Meta:
        interfaces = (CompositeIdHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      MarkedForDeletion,
                      UserId,
                      Content,
                      DataType)
    pass
