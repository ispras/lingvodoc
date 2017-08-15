import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    Relationship,
    MovedTo,
    fetch_object,
    client_id_check,
    del_object,
    ResponseError,
)

from lingvodoc.models import (
    Entity as dbEntity,
    Client,
    DBSession,
    DictionaryPerspective as dbDictionaryPerspective,
    Group as dbGroup,
    LexicalEntry as dbLexicalEntry,
    User as dbUser,
    ObjectTOC as dbObjectTOC
)
from lingvodoc.schema.gql_entity import Entity
from lingvodoc.views.v2.utils import check_client_id
from lingvodoc.views.v2.delete import real_delete_lexical_entry

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

class CreateLexicalEntry(graphene.Mutation):
    """
    example:
    mutation {
        create_lexicalentry(id: [949,21], perspective_id: [71,5]) {
            field {
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_lexicalentry": {
        "field": {
          "id": [
            949,
            21
          ]
        },
        "triumph": true
      }
    }
    """

    class Input:
        id = graphene.List(graphene.Int)
        perspective_id = graphene.List(graphene.Int)

    field = graphene.Field(LexicalEntry)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, args, context, info):
        perspective_id = args.get('perspective_id')
        perspective_client_id = perspective_id[0]
        perspective_object_id = perspective_id[1]

        id = args.get('id')
        object_id = None
        client_id_from_args = None
        if len(id) == 1:
            client_id_from_args = id[0]
        elif len(id) == 2:
            client_id_from_args = id[0]
            object_id = id[1]

        client_id = context["client_id"]
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        perspective = DBSession.query(dbDictionaryPerspective). \
            filter_by(client_id=perspective_client_id, object_id=perspective_object_id).first()
        if not perspective:
            raise ResponseError(message="No such perspective in the system")

        if client_id_from_args:
            if check_client_id(authenticated=client.id, client_id=client_id_from_args):
                client_id = client_id_from_args
            else:
                raise ResponseError(message="Error: client_id from another user")

        dblexentry = dbLexicalEntry(object_id=object_id, client_id=client_id,
                               parent_object_id=perspective_object_id, parent=perspective)
        DBSession.add(dblexentry)
        DBSession.flush()
        lexicalentry = LexicalEntry(id=[dblexentry.client_id, dblexentry.object_id])
        lexicalentry.dbObject = dblexentry
        return CreateLexicalEntry(field=lexicalentry, triumph=True)

class DeleteLexicalEntry(graphene.Mutation):
    """
    example:
    mutation {
        delete_lexicalentry(id: [949,21]) {
            field {
                id
            }
            triumph
        }
    }
    now returns:
        {
      "errors": [
        "No such entity in the system"
      ]
    }
    """

    class Input:
        id = graphene.List(graphene.Int)

    field = graphene.Field(LexicalEntry)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        id = args.get('id')
        object_id = id[0]
        client_id = id[1]

        dblexicalentry = DBSession.query(dbLexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
        if dblexicalentry and not dblexicalentry.marked_for_deletion:
            del_object(dblexicalentry)
            objecttoc = DBSession.query(dbObjectTOC).filter_by(client_id=dblexicalentry.client_id,
                                                             object_id=dblexicalentry.object_id).one()
            del_object(objecttoc)
            lexicalentry = LexicalEntry(id=[dblexicalentry.client_id, dblexicalentry.object_id])
            lexicalentry.dbObject = dblexicalentry
            return DeleteLexicalEntry(field=lexicalentry, triumph=True)
        raise ResponseError(message="No such entity in the system")