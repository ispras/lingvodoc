import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    Language as dbLanguage,
    Dictionary as dbDictionary,
    DBSession
)

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    TranslationHolder,
    fetch_object,
    del_object
)

from lingvodoc.schema.gql_dictionary import Dictionary


class Language(graphene.ObjectType):
    """
     #created_at                 | timestamp without time zone | NOT NULL
     #object_id                  | bigint                      | NOT NULL
     #client_id                  | bigint                      | NOT NULL
     #parent_object_id           | bigint                      |
     #parent_client_id           | bigint                      |
     #translation_gist_client_id | bigint                      | NOT NULL
     #translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion        | boolean                     | NOT NULL
     #additional_metadata        | jsonb                       |
     + translation
    """
    dbType = dbLanguage
    dbObject = None

    dataType = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, TranslationHolder)

    @fetch_object()
    def resolve_dictionaries(self, args, context, info):
        result = list()
        for dictionary in DBSession.query(dbDictionary).filter(
                and_(dbDictionary.parent_object_id == self.dbObject.object_id,
                     dbDictionary.parent_client_id == self.dbObject.client_id)):
            result.append(Dictionary(id=[dictionary.client_id, dictionary.object_id]))
        return result

    def resolve_dataType(self, args, context, info):
        return 'language'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))

        # @fetch_object()
        # def resolve_created_at(self, args, context, info):
        #    return self.dbObject.created_at


class CreateLanguage(graphene.Mutation):


    """
    example:
    mutation  {
        create_language(translation_gist_id: [662, 2], parent_id: [1, 47], locale_exist: true) {
            status
        }
    }
    """


    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        locale_exist = graphene.Boolean()


    field = graphene.Field(Language)
    status = graphene.Boolean()


    @staticmethod
    def mutate(root, args, context, info):
        try:
            parent_id = args.get('parent_id')
            parent_client_id = parent_id[0]
            parent_object_id = parent_id[1]
        except:
            parent_client_id = None
            parent_object_id = None


        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0]
        translation_gist_object_id = translation_gist_id[1]

        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        if client_id:
            if not object_id:
                object_id = None

            dbentityobj = dbLanguage(
                client_id=client_id,
                object_id=object_id,
                translation_gist_client_id=translation_gist_client_id,
                translation_gist_object_id=translation_gist_object_id
            )
            DBSession.add(dbentityobj)

            if parent_client_id and parent_object_id:
                parent = DBSession.query(dbLanguage).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
            if parent:
                dbentityobj.parent = parent

            DBSession.flush()
            language = Language(id=[dbentityobj.client_id, dbentityobj.object_id])
            language.dbObject = dbentityobj
            return CreateLanguage(field=language, status=True)


class DeleteLanguage(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    field = graphene.Field(Language)
    status = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        id = args.get('id')

        client_id = id[0]
        object_id = id[1]
        dbentityobj = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()

        if dbentityobj and not dbentityobj.marked_for_deletion:
            # dbentryobj = dbentityobj.parent - ?

            del_object(dbentityobj)
            language = Language(id=id)
            language.dbObject = dbentityobj
            return DeleteLanguage(field=language, status=True)
        return ResponseError(message="No such entity in the system")
