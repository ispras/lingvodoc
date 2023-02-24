
import logging

import graphene
from sqlalchemy.orm import aliased

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
    LingvodocID,
    fetch_object,
)
from lingvodoc.schema.gql_field import Field
from lingvodoc.models import (
    DBSession,
    DictionaryPerspectiveToField as dbColumn,
    Field as dbField,
)

from lingvodoc.utils.creation import create_dictionary_persp_to_field


# Setting up logging.
log = logging.getLogger(__name__)


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
    dbType = dbColumn

    field = graphene.Field(Field)

    class Meta:
        interfaces = (CreatedAt,
                      CompositeIdHolder,
                      Relationship,
                      SelfHolder,
                      FieldHolder,
                      ParentLink,
                      MarkedForDeletion,
                      Position)

    @fetch_object('field')
    def resolve_field(self, info):

        field = (

            DBSession

                .query(dbField)

                .filter_by(
                    client_id = self.dbObject.field_client_id,
                    object_id = self.dbObject.field_object_id)

                .first())

        gql_field = Field(id = field.id)
        gql_field.dbObject = field

        return gql_field


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
      "create_column": {
        "triumph": true,
        "column": {
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

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        id = args.get("id")
        client_id = id[0] if id else info.context["client_id"]
        object_id = id[1] if id else None
        id = [client_id, object_id]
        parent_id = args.get('parent_id')
        info.context.acl_check('edit', 'perspective', parent_id)
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
        update_column(id: [949, 2493], position: 5) {
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
      "update_column": {
        "triumph": true,
        "column": {
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
    def mutate(root, info, **args):

        id = args.get("id")
        client_id, object_id = id

        field_object = (
            DBSession.query(dbColumn).filter_by(
                client_id=client_id, object_id=object_id).first())

        if not field_object or field_object.marked_for_deletion:
            raise ResponseError(message="Error: No such field object in the system")

        info.context.acl_check(
            'edit', 'perspective', field_object.parent_id)

        field_id = args.get('field_id')
        self_id = args.get('self_id')
        link_id = args.get('link_id')
        position = args.get('position')

        if field_id:
            field_object.field_client_id, field_object.field_object_id = field_id

        # Attaching or de-attaching as a nested field.

        if self_id:

            field_object.self_client_id, field_object.self_object_id = (
                self_id if self_id[0] > 0 else (None, None))

        if link_id:
            field_object.link_client_id, field_object.link_object_id = link_id

        if position:
            field_object.position = position

        column = Column(id = field_object.id)
        column.dbObject = field_object

        return UpdateColumn(column=column, triumph=True)



class DeleteColumn(graphene.Mutation):
    """
    example:
      mutation  {
       delete_column(id: [949, 2493]) {
            triumph
            column{
                id
            }
        }
    }

    (this example works)
    returns:

    {
      "delete_column": {
        "triumph": true,
        "column": {
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

    column_list = graphene.List(Column)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, id, **args):

        __debug_flag__ = False

        # Recursively getting the column with any other linked columns.

        base_cte = (

            DBSession

                .query(
                    dbColumn)

                .filter_by(
                    client_id = id[0],
                    object_id = id[1])

                .cte(
                    recursive = True))

        recursive_query = (

            DBSession

                .query(
                    dbColumn)

                # Additional filtration by parent id to make use of the index, right now we don't have an
                # index by self id.

                .filter(
                    dbColumn.parent_client_id == base_cte.c.parent_client_id,
                    dbColumn.parent_object_id == base_cte.c.parent_object_id,
                    dbColumn.self_client_id == base_cte.c.client_id,
                    dbColumn.self_object_id == base_cte.c.object_id))

        source_cte = (

            aliased(
                dbColumn,
                base_cte.union(
                    recursive_query)))

        column_list = (

            DBSession

                .query(
                    source_cte)

                .filter(
                    source_cte.marked_for_deletion == False)

                .all())

        if __debug_flag__:

            log.debug(
                f'\n column_list:\n {column_list}')

        if not column_list:

            return (
                ResponseError(
                    f'No column {id[0]}/{id[1]} in the system.'))

        if all(column.marked_for_deletion for column in column_list):

            return (
                ResponseError(
                    f'Column {id[0]}/{id[0]} is deleted.'))

        info.context.acl_check(
            'edit', 'perspective', column_list[0].parent_id)

        client_id = (
            info.context.get('client_id'))

        gql_column_list = []

        for column in column_list:

            if not column.marked_for_deletion:

                del_object(
                    column, 'delete_column', client_id)

            gql_column = (
                Column(id = column.id))

            gql_column.dbObject = (
                column)

            gql_column_list.append(gql_column_list)

        return (

            DeleteColumn(
                column_list = column_list,
                triumph = True))

