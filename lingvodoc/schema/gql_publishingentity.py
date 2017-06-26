import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    CreatedAt,
    Published,
    Accepted,
)
from lingvodoc.models import (
    PublishingEntity as dbPublishingEntity,
)
class PublishingEntity(graphene.ObjectType):
    """
     #created_at | timestamp without time zone | NOT NULL
     #object_id  | bigint                      | NOT NULL
     #client_id  | bigint                      | NOT NULL
     #published  | boolean                     | NOT NULL
     #accepted   | boolean                     | NOT NULL
    """
    dbType = dbPublishingEntity
    dbObject = None
    class Meta:
        interfaces = (CreatedAt,
                      CompositeIdHolder,
                      Published,
                      Accepted
                    )
    pass