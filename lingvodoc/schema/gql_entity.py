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
    client_id_check
)
from sqlalchemy import (
    and_,
)

# from lingvodoc.views.v2.utils import (
#     create_object
# )

import base64
import hashlib

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
    with open(storage_path, 'wb+') as f:
        if json_input:
            f.write(base64.urlsafe_b64decode(content))
        else:
            shutil.copyfileobj(content, f)

    real_location = storage_path
    print(storage)
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
                      LocaleId
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
        id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int, required=True)
        additional_metadata = ObjectVal()
        field_id = graphene.List(graphene.Int, required=True)
        self_id = graphene.List(graphene.Int)
        link_id = graphene.List(graphene.Int)
        locale_id = graphene.Int()
        filename = graphene.String()
        content = graphene.String()
        registry = ObjectVal()

    # Result object

    entity = graphene.Field(Entity)


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

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get('id')
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        lexical_entry_id = args.get('parent_id')
        if not lexical_entry_id:
            raise ResponseError(message="Lexical entry not found")
        parent_client_id, parent_object_id = lexical_entry_id
        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        parent = DBSession.query(dbLexicalEntry).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        if not parent:
            raise ResponseError(message="No such lexical entry in the system")

        additional_metadata = args.get('additional_metadata')
        upper_level = None

        field_client_id, field_object_id = args.get('field_id')
        tr_atom = DBSession.query(dbTranslationAtom).join(dbTranslationGist, and_(
            dbTranslationAtom.locale_id == 2,
            dbTranslationAtom.parent_client_id == dbTranslationGist.client_id,
            dbTranslationAtom.parent_object_id == dbTranslationGist.object_id)).join(dbField, and_(
            dbTranslationGist.client_id == dbField.data_type_translation_gist_client_id,
            dbTranslationGist.object_id == dbField.data_type_translation_gist_object_id)).filter(
            dbField.client_id == field_client_id, dbField.object_id == field_object_id).first()
        if not tr_atom:
             raise ResponseError(message="No such field in the system")
        data_type = tr_atom.content.lower()

        if args.get('self_id'):
            self_client_id, self_object_id = args.get('self_id')
            upper_level = DBSession.query(dbEntity).filter_by(client_id=self_client_id,
                                                            object_id=self_object_id).first()
            if not upper_level:
                raise ResponseError(message="No such upper level in the system")
        dbentity = dbEntity(client_id=client_id,
                        object_id=object_id,
                        field_client_id=field_client_id,
                        field_object_id=field_object_id,
                        locale_id=args.get('locale_id'),
                        additional_metadata=additional_metadata,
                        parent=parent)
        group = DBSession.query(dbGroup).join(dbBaseGroup).filter(dbBaseGroup.subject == 'lexical_entries_and_entities',
                                                              dbGroup.subject_client_id == dbentity.parent.parent.client_id,
                                                              dbGroup.subject_object_id == dbentity.parent.parent.object_id,
                                                              dbBaseGroup.action == 'create').one()

        override_group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
            dbBaseGroup.subject == 'lexical_entries_and_entities',
            dbGroup.subject_override == True,
            dbBaseGroup.action == 'create').one()
        if user in group.users or user in override_group.users:
            dbentity.publishingentity.accepted = True
        if upper_level:
            dbentity.upper_level = upper_level

        filename = args.get('filename')
        real_location = None
        url = None
        blob = info.context.request.POST.pop("blob")
        content= args.get("content")
        if data_type == 'image' or data_type == 'sound' or 'markup' in data_type:
            filename=blob.filename
            content = blob.file
            #filename=
            real_location, url = create_object(args, content, dbentity, data_type, filename, "entity_sounds", {})
            dbentity.content = url
            old_meta = dbentity.additional_metadata
            need_hash = True
            if old_meta:
                if old_meta.get('hash'):
                    need_hash = False
            if need_hash:
                hash = hashlib.sha224(base64.urlsafe_b64decode(content)).hexdigest()
                hash_dict = {'hash': hash}
                if old_meta:
                    old_meta.update(hash_dict)
                else:
                    old_meta = hash_dict
                dbentity.additional_metadata = old_meta
            if 'markup' in data_type:
                name = filename.split('.')
                ext = name[len(name) - 1]
                if ext.lower() == 'textgrid':
                    data_type = 'praat markup'
                elif ext.lower() == 'eaf':
                    data_type = 'elan markup'
            dbentity.additional_metadata['data_type'] = data_type
        elif data_type == 'link':
            if args.get('link_id'):
                link_client_id, link_object_id = args.get('link_id')
                dbentity.link_client_id = link_client_id
                dbentity.link_object_id = link_object_id
            else:
                raise ResponseError(message="The field is of link type. You should provide client_id and object id in the content")
        else:
            dbentity.content = content

            # if args.get('is_translatable', None): # TODO: fix it
            #     field.is_translatable = bool(args['is_translatable'])
        DBSession.add(dbentity)
        DBSession.flush()
        entity = Entity(id = [dbentity.client_id, dbentity.object_id])
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
        id = graphene.List(graphene.Int)
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
        id = graphene.List(graphene.Int)

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
