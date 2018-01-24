import graphene
from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
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
    LingvodocID,
    acl_check_by_id
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

class Column(LingvodocObjectType):
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


class CreateColumn(graphene.Mutation):
    """
    example:
    mutation  {
        create_column(parent_id: [1204,19664], field_id: [66, 6],
  position: 1) {
            triumph
            column{
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
        parent_id = LingvodocID(required=True)
        field_id = LingvodocID(required=True)
        self_id = LingvodocID()
        link_id = LingvodocID()
        position = graphene.Int(required=True)

    column = graphene.Field(Column)
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
    @acl_check_by_id("edit", "perspective", id_key="parent_id")
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
        column = Column(id=[field_object.client_id, field_object.object_id])
        column.dbObject = field_object
        return CreateColumn(column=column, triumph=True)


class UpdateColumn(graphene.Mutation):
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
        self_id = LingvodocID()
        link_id = LingvodocID()
        position = graphene.Int()

    column = graphene.Field(Column)
    triumph = graphene.Boolean()

    @staticmethod
    # @acl_check_by_id("edit", "perspective", id_key="parent_id")
    def mutate(root, info, **args):
        id = args.get("id")
        client_id, object_id = id
        field_object = DBSession.query(dbDictionaryPerspectiveToField).filter_by(client_id=client_id,
                                                                                 object_id=object_id).first()
        if not field_object or field_object.marked_for_deletion:
            raise ResponseError(message="Error: No such field object in the system")

        info.context.acl_check('edit', 'perspective',
                                   (field_object.parent_client_id, field_object.parent_object_id))
        field_id = args.get('field_id')
        self_id = args.get('self_id')
        link_id = args.get('link_id')
        position = args.get('position')
        if field_id:
            field_object.field_client_id, field_object.field_object_id = field_id
        if self_id:
            field_object.self_client_id, field_object.self_object_id = self_id
        if link_id:
            field_object.link_client_id, field_object.link_object_id = link_id
        if position:
            field_object.position = position
        column = Column(id=[field_object.client_id, field_object.object_id])
        column.dbObject = field_object
        return UpdateColumn(column=column, triumph=True)



class DeleteColumn(graphene.Mutation):
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

    column = graphene.Field(Column)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("perspective", "edit", id_key="parent_id")
    def mutate(root, info, **args):
        id = args.get('id')
        client_id, object_id = id
        column_object = DBSession.query(dbDictionaryPerspectiveToField).filter_by(client_id=client_id,
                                                                                 object_id=object_id).first()
        if not column_object or column_object.marked_for_deletion:
            raise ResponseError(message="No such column object in the system")
        del_object(column_object)
        column = Column(id=id)
        column.dbObject = column_object
        return DeleteColumn(column=column, triumph=True)

