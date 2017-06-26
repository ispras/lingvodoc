import graphene

from lingvodoc.schema.gql_holders import (
    CompositeIdHolder,
    TranslationGistHolder,
    AdditionalMetadata,
    CreatedAt,
    MarkedForDeletion,
    DataTypeTranslationGistId,
    IsTranslatable,
    #TranslationHolder
    fetch_object,
    del_object

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

    locale_id2 = graphene.Int() ##########
    data_type = graphene.String()
    translation = graphene.String()
    dbType = dbField
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder,
                      TranslationGistHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      MarkedForDeletion,
                      DataTypeTranslationGistId,
                      IsTranslatable,
                      #TranslationHolder
                      )

    #@fetch_object("data_type")
    #def resolve_data_type(self, args, context, info):
    #    pass#print (self.dbObject.data_type)
    #    #return self.dbObject.data_type

    @fetch_object("translation")
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))


class CreateField(graphene.Mutation):
    class Input:
        translation_gist_id = graphene.List(graphene.Int)
        data_type_translation_gist_id = graphene.List(graphene.Int)


    marked_for_deletion = graphene.Boolean()
    field = graphene.Field(Field)
    status_code = graphene.Boolean()
    errors = graphene.List(graphene.String)
    id = graphene.List(graphene.Int)

    @staticmethod
    def mutate(root, args, context, info):
        #subject = 'language'
        client_id = context["client_id"]
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
            return CreateField(field=field)

            #if not perm_check(client_id, "field"):
            #    return ResponseError(message = "Permission Denied (Field)")



class UpdateField(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)



    field = graphene.Field(Field)


    @staticmethod
    def mutate(root, args, context, info):
        #print(args.get('locale_id'))
        #client_id = context.authenticated_userid
        client_id = context["client_id"]
        #print(args)
        id = args.get('id')
        dbfield_obj = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
        field = Field( **args)
        field.dbObject = dbfield_obj
        return UpdateField(field=field)


class DeleteField(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    marked_for_deletion = graphene.Boolean()
    field = graphene.Field(Field)

    @staticmethod
    def mutate(root, args, context, info):
        #client_id = context.authenticated_userid
        client_id = context["client_id"]
        id = args.get('id')
        fieldobj = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
        del_object(fieldobj)
        field = Field(id = id)
        return DeleteField(field=field)

