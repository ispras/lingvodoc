import graphene
from sqlalchemy import and_
from lingvodoc.models import DBSession
from lingvodoc.schema.gql_holders import (
    fetch_object,
    ObjectVal
)
from lingvodoc.models import (
    Entity as dbEntity,

)
from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    CreatedAt,
    Relationship,
    SelfHolder,
    FieldHolder,
    ParentLink,
    MarkedForDeletion,
    AdditionalMetadata,
    LocaleId,
    Content,
    del_object,
    ResponseError
)
from sqlalchemy import (
    and_,
)

# Read
class Entity(graphene.ObjectType):
     # TODO: Accepted, entity_type
    content = graphene.String()
    data_type = graphene.String()
    dbType = dbEntity
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      MarkedForDeletion,
                      Relationship,
                      SelfHolder,
                      FieldHolder,
                      ParentLink,
                      Content,
                      #TranslationHolder,
                      LocaleId
                      )


    @fetch_object('data_type')
    def resolve_data_type(self, args, context, info):
        return self.dbObject.field.data_type

# Create
class CreateEntity(graphene.Mutation):
    class Input:
        """
        input values from request. Look at "LD methods" exel table
        """
        translation_gist_id = graphene.List(graphene.Int)
        data_type_translation_gist_id = graphene.List(graphene.Int)

    # Result object

    field = graphene.Field(Entity)


    """
    example:
    mutation  {
        create_field( translation_gist_id: [662, 2], data_type_translation_gist_id: [1, 47]) {
            field {
                id
            }
            status
        }
    }
    or
    mutation  {
        create_field( translation_gist_id: [662, 2], data_type_translation_gist_id: [1, 47]) {
            status
        }
    }
    """
    # Used for convenience

    status = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        client_id = context["client_id"]
        if client_id:
            data_type_translation_gist_id = args.get('data_type_translation_gist_id')
            translation_gist_id = args.get('translation_gist_id')
            dbentityobj = dbEntity(client_id=client_id,
                          object_id=None,
                          data_type_translation_gist_client_id=data_type_translation_gist_id[0],
                          data_type_translation_gist_object_id=data_type_translation_gist_id[1],
                          translation_gist_client_id=translation_gist_id[0],
                          translation_gist_object_id=translation_gist_id[1],
                          marked_for_deletion=False
                          )
            # if args.get('is_translatable', None): # TODO: fix it
            #     field.is_translatable = bool(args['is_translatable'])
            DBSession.add(dbentityobj)
            DBSession.flush()
            entity = Entity(id = [dbentityobj.client_id, dbentityobj.object_id])
            entity.dbObject = dbentityobj
            return CreateEntity(entity=entity, status="OK")

            #if not perm_check(client_id, "field"):
            #    return ResponseError(message = "Permission Denied (Entity)")


# Update
"""
example #1:
mutation  {
    update_entity(id: [ 742, 5494], additional_metadata: {hash:"1234567"} ) {
        entity {
            created_at,
            additional_metadata{
            hash
            }
        }

    status
    }
}
example #2:
mutation  {
    update_entity(id: [ 742, 5494], additional_metadata: {hash:"12345"} ){status}
}
resolve:
{
    "update_entity": {
        "status": true
    }
}
"""
class UpdateEntity(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)
        additional_metadata = ObjectVal()
        parent_id = graphene.List(graphene.Int)
        self_id = graphene.List(graphene.Int)
        field_id = graphene.List(graphene.Int)
        link_id = graphene.List(graphene.Int)
        content = graphene.String()
        locale_id = graphene.Int()

    entity = graphene.Field(Entity)
    additional_metadata = ObjectVal()  # TODO: deprecated, used in additional_metadata holder
    status = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        # client_id used in ACL func as arg
        client_id = context["client_id"]

        # ntity id
        id = args.get('id')

        # params, that can`t been resolved from Entity object

        restricted_fields = ["id", "created_at"]

        # Other params from request

        update_args = {k: v for k, v in args.items() if k not in restricted_fields}
        dbentity_obj = DBSession.query(dbEntity).filter(
            and_(dbEntity.client_id == id[0],
            dbEntity.object_id == id[1])
        ).first()
        if dbentity_obj and not dbentity_obj.marked_for_deletion:
            for arg in update_args:
                # attributes are used later in fetch_object decorator
                setattr(dbentity_obj, arg, update_args[arg] )

            entity = Entity( **args)
            entity.dbObject = dbentity_obj # speeds up queries

            return UpdateEntity(entity=entity, status = "OK")

# Delete
"""
query:
mutation  {
    delete_entity(id: [879, 8]) {
    entity{id, content, created_at}
    status
    }
}
response:
{
    "delete_entity": {
        "entity": {
            "id": [
                879,
                8
            ],
            "content": "123",
            "created_at": "2017-06-27T09:49:24"
        },
        "status": true
    }
}
or
{
    "errors": [
        "No such entity in the system"
    ]
}
"""
class DeleteEntity(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    status = graphene.Boolean()
    entity = graphene.Field(Entity)

    @staticmethod
    def mutate(root, args, context, info):
        #client_id = context.authenticated_userid
        client_id = context["client_id"]
        id = args.get('id')

        dbentityobj = DBSession.query(dbEntity).filter(
            and_(dbEntity.client_id == id[0], dbEntity.object_id == id[1])
        ).first()
        if dbentityobj and not dbentityobj.marked_for_deletion:
            del_object(dbentityobj)
            entity = Entity(id = id)
            entity.dbObject=dbentityobj
            return DeleteEntity(entity=entity, status="OK")
        return ResponseError(message="No such entity in the system")