import os
import shutil
from pathvalidate import sanitize_filename
import graphene
from sqlalchemy import and_
from lingvodoc.models import DBSession
from lingvodoc.schema.gql_holders import (
    fetch_object,
    ObjectVal
)
from lingvodoc.models import (
    Entity as dbEntity,
    Client,
    User as dbUser,
    DBSession,
    LexicalEntry as dbLexicalEntry,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    Field as dbField,
    Group as dbGroup,
    BaseGroup as dbBaseGroup,
    PublishingEntity as dbPublishingEntity

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
    ResponseError,
    client_id_check,
    Published,
    Accepted,
    LingvodocID

)
from sqlalchemy import (
    and_,
)

# from lingvodoc.views.v2.utils import (
#     create_object
# )

import base64
import hashlib

from lingvodoc.utils.creation import create_entity

def object_file_path(obj, base_path, folder_name, filename, create_dir=False):
    filename = sanitize_filename(filename)
    storage_dir = os.path.join(base_path, obj.__tablename__, folder_name, str(obj.client_id), str(obj.object_id))
    if create_dir:
        os.makedirs(storage_dir, exist_ok=True)
    storage_path = os.path.join(storage_dir, filename)
    return storage_path, filename

def create_object(content, obj, data_type, filename, folder_name, storage, json_input=True):
    import errno
    storage_path, filename = object_file_path(obj, storage["path"], folder_name, filename, True)
    directory = os.path.dirname(storage_path)  # TODO: find out, why object_file_path were not creating dir
    try:
        os.makedirs(directory)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise
    with open(str(storage_path), 'wb+') as f:
        if json_input:
            f.write(content)
        else:
            shutil.copyfileobj(content, f)

    real_location = storage_path
    url = "".join((storage["prefix"],
                  storage["static_route"],
                  obj.__tablename__,
                  '/',
                  folder_name,
                  '/',
                  str(obj.client_id), '/',
                  str(obj.object_id), '/',
                  filename))
    return real_location, url

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
                      LocaleId,
                      Published,
                      Accepted
                      )


    @fetch_object('data_type')
    def resolve_data_type(self, info):
        return self.dbObject.field.data_type

# Create
class CreateEntity(graphene.Mutation):
    class Arguments:
        """
        input values from request. Look at "LD methods" exel table
        """
        id = LingvodocID()
        parent_id = LingvodocID(required=True)
        additional_metadata = ObjectVal()
        field_id = LingvodocID(required=True)
        self_id = LingvodocID()
        link_id = LingvodocID()
        locale_id = graphene.Int()
        filename = graphene.String()
        content = graphene.String()
        registry = ObjectVal()

    # Result object

    entity = graphene.Field(Entity)


    """
    example:
    curl -i -X POST  -H "Cookie: auth_tkt="
    -H "Content-Type: multipart/form-data" -F "blob=@белка.wav" -F 'query=mutation {
            create_entity(parent_id: [66, 69],  field_id:  [66,12] ) {entity{id, parent_id} triumph}}' http://localhost:6543/graphql

    """
    # Used for convenience

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        parent_id = None
        if 'parent_id' in args:
            parent_id = args["parent_id"]
        else:
            raise ResponseError(message="Lexical entry not found")

        additional_metadata = None
        if 'additional_metadata' in args:
            additional_metadata = args["additional_metadata"]

        field_id = None
        if 'field_id' in args:
            field_id = args["field_id"]

        self_id = None
        if 'self_id' in args:
            self_id = args["self_id"]

        link_id = None
        if 'link_id' in args:
            link_id = args["link_id"]

        locale_id = 2
        if 'locale_id' in args:
            locale_id = args["locale_id"]

        filename = None
        if 'filename' in args:
            filename = args["filename"]

        content = None
        if 'content' in args:
            content = args["content"]

        registry = None
        if 'registry' in args:
            registry = args["registry"]

        dbentity = create_entity(id, parent_id, additional_metadata, field_id, self_id, link_id, locale_id,
                                 filename, content, registry, info.context.request, True)

        entity = Entity(id = [dbentity.client_id, dbentity.object_id]) # TODO: more args
        entity.dbObject = dbentity
        return CreateEntity(entity=entity, triumph=True)

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

class UpdateEntity(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)
        published = graphene.Boolean()
        accepted = graphene.Boolean()

    entity = graphene.Field(Entity)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        dbpublishingentity = DBSession.query(dbPublishingEntity).filter_by(client_id=client_id, object_id=object_id).first()
        if dbpublishingentity:
            if args.get('published'):
                dbpublishingentity.published = args.get('published')
            if args.get('accepted'):
                dbpublishingentity.accepted = args.get('accepted')

            dbentity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
            entity = Entity(id=[dbentity.client_id, dbentity.object_id])
            entity.dbObject = dbentity
            return UpdateEntity(entity=entity, triumph=True)
        raise ResponseError(message="No such entity in the system")

class DeleteEntity(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)

    triumph = graphene.Boolean()
    entity = graphene.Field(Entity)

    @staticmethod
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')

        dbentity = DBSession.query(dbEntity).filter_by(client_id=client_id, object_id=object_id).first()
        if dbentity and not dbentity.marked_for_deletion:

            del_object(dbentity)
            entity = Entity(id = id)
            entity.dbObject=dbentity
            return DeleteEntity(entity=entity, triumph=True)
        raise ResponseError(message="No such entity in the system")

class BulkCreateEntity(graphene.Mutation):
    """
    mutation {
            bulk_create_entity(entities: [{id: [1199, 4], parent_id: [66, 69],  field_id:  [66, 6]}]) {
                   triumph
        }
    }
    """
    class Arguments:
        entities = graphene.List(ObjectVal)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        entity_objects = args.get('entities')
        dbentities_list = list()
        request = info.context.request

        for entity_obj in entity_objects:
            id = None
            if 'id' in entity_obj:
                id = entity_obj["id"]
            else:
                raise ResponseError(message="Bad entity object")

            parent_id = None
            if 'parent_id' in entity_obj:
                parent_id = entity_obj["parent_id"]

            additional_metadata = None
            if 'additional_metadata' in entity_obj:
                additional_metadata = entity_obj["additional_metadata"]

            field_id = None
            if 'field_id' in entity_obj:
                field_id = entity_obj["field_id"]

            self_id = None
            if 'self_id' in entity_obj:
                self_id = entity_obj["self_id"]

            link_id = None
            if 'link_id' in entity_obj:
                link_id = entity_obj["link_id"]

            locale_id = 2
            if 'locale_id' in entity_obj:
                locale_id = entity_obj["locale_id"]

            filename = None
            if 'filename' in entity_obj:
                filename = entity_obj["filename"]

            content = None
            if 'content' in entity_obj:
                content = entity_obj["content"]

            registry = None
            if 'registry' in entity_obj:
                registry = entity_obj["registry"]

            dbentity = create_entity(id, parent_id, additional_metadata, field_id, self_id, link_id, locale_id,
                                     filename, content, registry, request, False)

            dbentities_list.append(dbentity)

        DBSession.bulk_save_objects(dbentities_list)
        DBSession.flush()
        return BulkCreateEntity(triumph=True)