import graphene
from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    CreatedAt,
    Relationship,
    SelfHolder,
    FieldHolder,
    ParentLink,
    MarkedForDeletion,
    Position,
    client_id_check,
    del_object,
    ResponseError,
    TranslationHolder,
    TranslationGistHolder,
    LingvodocID
)
from lingvodoc.models import (
    DictionaryPerspectiveToField as dbDictionaryPerspectiveToField,
    Client,
    User as dbUser,
    TranslationGist as dbTranslationGist,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    ObjectTOC,
    DBSession
)

from lingvodoc.utils.creation import create_dictionary_persp_to_field

class DictionaryPerspectiveToField(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #self_client_id      | bigint                      |
     #self_object_id      | bigint                      |
     #field_client_id     | bigint                      | NOT NULL
     #field_object_id     | bigint                      | NOT NULL
     #link_client_id      | bigint                      |
     #link_object_id      | bigint                      |
     #marked_for_deletion | boolean                     | NOT NULL
     #position            | integer                     | NOT NULL
    """
    dbObject = None
    dbType = dbDictionaryPerspectiveToField

    class Meta:
        interfaces = (CreatedAt,
                      CompositeIdHolder,
                      Relationship,
                      SelfHolder,
                      FieldHolder,
                      ParentLink,
                      MarkedForDeletion,
                      Position)
    pass


class CreateDictionaryPerspectiveToField(graphene.Mutation):
    """
    example:
    mutation  {
        create_perspective_to_field(id: [949, 2493], parent_id: [949, 2491], field_id: [949, 5], self_id: [949, 2493],
         link_id: [5, 6], position: 1) {
            triumph
            perspective_to_field{
                id
                position
            }
        }
    }

    (this example works)
    returns:

    {
      "create_perspective_to_field": {
        "triumph": true,
        "perspective_to_field": {
          "id": [
            949,
            2493
          ],
          "position": 1
        }
      }
    }
    """

    class Arguments:
        id = LingvodocID()
        parent_id = LingvodocID()
        field_id = LingvodocID()
        self_id = LingvodocID()
        link_id = LingvodocID()
        position = graphene.Int()

    perspective_to_field = graphene.Field(DictionaryPerspectiveToField)
    triumph = graphene.Boolean()

    #@staticmethod
    # def create_dictionary_persp_to_field(client_id=None,
    #                                      object_id=None,
    #                                      parent_client_id=None,
    #                                      parent_object_id=None,
    #                                      field_client_id=None,
    #                                      field_object_id=None,
    #                                      self_client_id=None,
    #                                      self_object_id=None,
    #                                      link_client_id=None,
    #                                      link_object_id=None,
    #                                      position=1):
    #     if DBSession.query(dbDictionaryPerspectiveToField).filter_by(client_id=client_id,
    #                                                                  object_id=object_id).first():
    #         raise ResponseError(message="This field already exists")
    #     field_object = dbDictionaryPerspectiveToField(client_id=client_id,
    #                                                   object_id=object_id,
    #                                                   parent_client_id=parent_client_id,
    #                                                   parent_object_id=parent_object_id,
    #                                                   field_client_id=field_client_id,
    #                                                   field_object_id=field_object_id,
    #                                                   self_client_id=self_client_id,
    #                                                   self_object_id=self_object_id,
    #                                                   link_client_id=link_client_id,
    #                                                   link_object_id=link_object_id,
    #                                                   position=position
    #                                                   )
    #     DBSession.add(field_object)
    #     DBSession.flush()
    #     return field_object

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        parent_id = args.get('parent_id')
        field_id = args.get('field_id')
        self_id = args.get('self_id')
        link_id = args.get('link_id')
        position = args.get('position')
        field_object = create_dictionary_persp_to_field(id=id,
                                              parent_id=parent_id,
                                              field_id=field_id,
                                              self_id=self_id,
                                              link_id=link_id,
                                              position=position)
        DBSession.add(field_object)
        DBSession.flush()
        perspective_to_field = DictionaryPerspectiveToField(id=[field_object.client_id, field_object.object_id])
        perspective_to_field.dbObject = field_object
        return CreateDictionaryPerspectiveToField(perspective_to_field=perspective_to_field, triumph=True)


class UpdateDictionaryPerspectiveToField(graphene.Mutation):
    """
    example:
      mutation  {
        update_perspective_to_field(id: [949, 2493], position: 5) {
            triumph
            perspective_to_field{
                id
                position
            }
        }
    }

    (this example works)
    returns:

    {
      "update_perspective_to_field": {
        "triumph": true,
        "perspective_to_field": {
          "id": [
            949,
            2493
          ],
          "position": 5
        }
      }
    }
    """

    class Arguments:
        id = LingvodocID(required=True)
        parent_id = LingvodocID()
        field_id = LingvodocID()
        link_id = LingvodocID()
        position = graphene.Int()

    perspective_to_field = graphene.Field(DictionaryPerspectiveToField)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get("id")
        client_id, object_id = id
        field_object = DBSession.query(dbDictionaryPerspectiveToField).filter_by(client_id=client_id,
                                                                                 object_id=object_id).first()
        if not field_object or not field_object.marked_for_deletion:
            raise ResponseError(message="Error: No such field object in the system")

        parent_id = args.get('parent_id')
        field_id = args.get('field_id')
        link_id = args.get('link_id')
        position = args.get('position')
        if parent_id:
            field_object.parent_client_id, field_object.parent_object_id = parent_id
        if field_id:
            field_object.field_client_id, field_object.field_object_id = field_id
        if link_id:
            field_object.link_client_id, field_object.link_object_id = link_id
        if position:
            field_object.position = position
        perspective_to_field = DictionaryPerspectiveToField(id=[field_object.client_id, field_object.object_id])
        perspective_to_field.dbObject = field_object
        return UpdateDictionaryPerspectiveToField(perspective_to_field=perspective_to_field, triumph=True)



class DeleteDictionaryPerspectiveToField(graphene.Mutation):
    """
    example:
      mutation  {
       delete_perspective_to_field(id: [949, 2493]) {
            triumph
            perspective_to_field{
                id
            }
        }
    }

    (this example works)
    returns:

    {
      "delete_perspective_to_field": {
        "triumph": true,
        "perspective_to_field": {
          "id": [
            949,
            2493
          ]
        }
      }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)

    perspective_to_field = graphene.Field(DictionaryPerspectiveToField)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get('id')
        client_id, object_id = id
        field_object = DBSession.query(dbDictionaryPerspectiveToField).filter_by(client_id=client_id,
                                                                                 object_id=object_id).first()
        if not field_object or field_object.marked_for_deletion:
            raise ResponseError(message="No such field object in the system")
        del_object(field_object)
        perspective_to_field = DictionaryPerspectiveToField(id=id)
        perspective_to_field.dbObject = field_object
        return DeleteDictionaryPerspectiveToField(perspective_to_field=perspective_to_field, triumph=True)

