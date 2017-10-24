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
                      # TranslationHolder,
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

    or
    mutation  {
    create_entity(parent_id: [66, 69], field_id: [66, 6], content: "test") {
        entity {
            created_at,
	content
        }

    triumph
    }
    }
    """
    # Used for convenience

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()  # TODO context acl check
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

        lexical_entry = DBSession.query(dbLexicalEntry).filter_by(client_id=parent_id[0], object_id=parent_id[1]).one()
        info.context.acl_check('create', 'lexical_entries_and_entities',
                               (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

        additional_metadata = None
        if 'additional_metadata' in args:
            additional_metadata = args["additional_metadata"]
        field_id = args.get('field_id')
        self_id = args.get("self_id")
        link_id = args.get("link_id")
        locale_id = args.get("locale_id", 2)
        filename = args.get("filename")
        content = args.get("content")
        registry = args.get("registry")

        dbentity = create_entity(id, parent_id, additional_metadata, field_id, self_id, link_id, locale_id,
                                 filename, content, registry, info.context.request, True)

        entity = Entity(id=[dbentity.client_id, dbentity.object_id])  # TODO: more args
        entity.dbObject = dbentity
        return CreateEntity(entity=entity, triumph=True)

        # if not perm_check(client_id, "field"):
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
        dbpublishingentity = DBSession.query(dbPublishingEntity).filter_by(client_id=client_id,
                                                                           object_id=object_id).first()
        # lexical_entry = dbpublishingentity.parent.parent
        lexical_entry = DBSession.query(dbLexicalEntry).join(dbLexicalEntry.entity).join(
            dbEntity.publishingentity).filter(dbPublishingEntity.client_id == client_id,
                                              dbPublishingEntity.object_id == object_id).one()
        if dbpublishingentity:
            published = args.get('published')
            accepted = args.get('accepted')
            if published and not dbpublishingentity.published:
                info.context.acl_check('create', 'approve_entities',
                                       (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

            if published is not None and not published and dbpublishingentity.published:
                info.context.acl_check('delete', 'approve_entities',
                                       (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

            if accepted and not dbpublishingentity.accepted:
                info.context.acl_check('create', 'lexical_entries_and_entities',
                                       (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

            if accepted is not None and not accepted and dbpublishingentity.accepted:
                raise ResponseError(message="not allowed action")

            if published:
                dbpublishingentity.published = published
            if accepted:
                dbpublishingentity.accepted = accepted

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
        lexical_entry = dbentity.parent
        info.context.acl_check('delete', 'lexical_entries_and_entities',
                               (lexical_entry.parent_client_id, lexical_entry.parent_object_id))
        if dbentity and not dbentity.marked_for_deletion:
            del_object(dbentity)
            entity = Entity(id=id)
            entity.dbObject = dbentity
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
    entities = graphene.List(Entity)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client = DBSession.query(Client).filter_by(id=info.context["client_id"]).first()
        if not client:
            raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                           info.context["client_id"])
        entity_objects = args.get('entities')
        dbentities_list = list()
        request = info.context.request
        entities = list()
        for entity_obj in entity_objects:
            id = entity_obj.get("id")
            if id is None:
                id = (info.context["client_id"], None)

            parent_id = entity_obj.get("parent_id")
            if not parent_id:
                raise ResponseError(message="Bad lexical_entry object")
            lexical_entry = DBSession.query(dbLexicalEntry) \
                .filter_by(client_id=parent_id[0], object_id=parent_id[1]).one()
            info.context.acl_check('create', 'lexical_entries_and_entities',
                                   (lexical_entry.parent_client_id, lexical_entry.parent_object_id))

            additional_metadata = None
            if 'additional_metadata' in entity_obj:
                additional_metadata = entity_obj["additional_metadata"]
            field_id = entity_obj.get('field_id')
            if not field_id:
                raise ResponseError('no field_id provided')
            self_id = entity_obj.get("self_id")
            link_id = entity_obj.get("link_id")
            locale_id = entity_obj.get("locale_id", 2)
            filename = entity_obj.get("filename")
            content = entity_obj.get("content")
            registry = entity_obj.get("registry")

            dbentity = create_entity(id, parent_id, additional_metadata, field_id, self_id, link_id, locale_id,
                                     filename, content, registry, request, False)

            dbentities_list.append(dbentity)

        DBSession.bulk_save_objects(dbentities_list)
        DBSession.flush()
        for dbentity in dbentities_list:
            entity =  Entity(id=[dbentity.client_id, dbentity.object_id])
            entity.dbObject = dbentity
            entities.append(entity)
        return BulkCreateEntity(entities=entities, triumph=True)
