import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    TranslationGistHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    DataTypeTranslationGistId,
    DataType,
    IsTranslatable,
    TranslationHolder,
    #TranslationHolder
    fetch_object,
    del_object,
    client_id_check,
    FakeIds,
    LingvodocID
)

from lingvodoc.models import (
    Field as dbField,
    DBSession
)
from sqlalchemy import (
    and_
)

class Field(graphene.ObjectType):
    """
     #created_at                           | timestamp without time zone | NOT NULL
     #object_id                            | bigint                      | NOT NULL
     #client_id                            | bigint                      | NOT NULL
     #translation_gist_client_id           | bigint                      | NOT NULL
     #translation_gist_object_id           | bigint                      | NOT NULL
     #data_type_translation_gist_client_id | bigint                      | NOT NULL
     #data_type_translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion                  | boolean                     | NOT NULL
     #is_translatable                      | boolean                     | NOT NULL
     #additional_metadata                  | jsonb                       |
     + .translation
    """

    #data_type = graphene.String()
    dbType = dbField
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder,
                      TranslationGistHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      MarkedForDeletion,
                      DataTypeTranslationGistId,
                      DataType,
                      IsTranslatable,
                      TranslationHolder,
                      FakeIds
                      )

    # @fetch_object("data_type")
    # def resolve_data_type(self, args, context, info):
    #    pass#print (self.dbObject.data_type)
    #    return self.dbObject.data_type

    # @fetch_object("translation")
    # def resolve_translation(self, info):
    #     context = info.context
    #     return self.dbObject.get_translation(context.get('locale_id'))


class CreateField(graphene.Mutation):
    """
    mutation  {
    create_field( translation_gist_id: [662, 2], data_type_translation_gist_id: [1, 47]) {
        field {
            id
        }

    }
}
    """
    class Arguments:
        # TODO: id?
        translation_gist_id = id = LingvodocID()
        data_type_translation_gist_id = LingvodocID()


    marked_for_deletion = graphene.Boolean()
    field = graphene.Field(Field)
    triumph = graphene.Boolean()


    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        #subject = 'language'
        client_id = info.context["client_id"]
        if client_id:
            data_type_translation_gist_id = args.get('data_type_translation_gist_id')
            translation_gist_id = args.get('translation_gist_id')
            dbfield = dbField(client_id=client_id,
                          object_id=None,
                          data_type_translation_gist_client_id=data_type_translation_gist_id[0],
                          data_type_translation_gist_object_id=data_type_translation_gist_id[1],
                          translation_gist_client_id=translation_gist_id[0],
                          translation_gist_object_id=translation_gist_id[1],
                          marked_for_deletion=False
                          )
            # if args.get('is_translatable', None):
            #     field.is_translatable = bool(args['is_translatable'])
            DBSession.add(dbfield)
            DBSession.flush()
            field = Field(id = [dbfield.client_id, dbfield.object_id])
            field.dbObject = dbfield
            return CreateField(field=field, triumph = True)

            #if not perm_check(client_id, "field"):
            #    return ResponseError(message = "Permission Denied (Field)")



class UpdateField(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)
    field = graphene.Field(Field)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        #print(args.get('locale_id'))
        #client_id = context.authenticated_userid
        client_id = info.context["client_id"]
        #print(args)
        id = args.get('id')
        dbfield_obj = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
        field = Field( **args)
        field.dbObject = dbfield_obj  # TODO: fix Update
        return UpdateField(field=field, triumph = True)


class DeleteField(graphene.Mutation):
    """
    mutation  {
    delete_field(id: [880,2]) {
        field {
            created_at,
            translation
        }

    }
}
    """
    class Arguments:
        id = LingvodocID(required=True)

    marked_for_deletion = graphene.Boolean()
    field = graphene.Field(Field)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        #client_id = context.authenticated_userid
        client_id = info.context["client_id"]
        id = args.get('id')
        fieldobj = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
        del_object(fieldobj)
        field = Field(id = id)
        return DeleteField(field=field, triumph = True)

