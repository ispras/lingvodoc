import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    Relationship,
    MovedTo,
    fetch_object
)

from lingvodoc.models import (
    Entity as dbEntity,
)
from lingvodoc.schema.gql_entity import Entity

class LexicalEntry(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #marked_for_deletion | boolean                     | NOT NULL
     #moved_to            | text                        |
     #additional_metadata | jsonb                       |
    """
    entities = graphene.List(Entity)

    dbType = dbEntity
    dbObject = None

    class Meta:
        interfaces = (CompositeIdHolder, AdditionalMetadata, CreatedAt, MarkedForDeletion, Relationship, MovedTo)
        #only_fields = ['id', 'additional_metadata', 'created_at', "marked_for_deletion"]

    @fetch_object('entities')
    def resolve_entities(self, args, context, info):
        result = list()
        for db_entity in self.dbObject.entity:
            gr_entity_object = Entity(id=[db_entity.client_id, db_entity.object_id])
            gr_entity_object.dbObject = db_entity
            result.append(gr_entity_object)
        return result[:2]