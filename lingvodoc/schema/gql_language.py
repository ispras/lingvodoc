import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    Language as dbLanguage,
    Dictionary as dbDictionary,
    Client,
    User as dbUser,
    DBSession
)

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError
)

# from lingvodoc.schema.gql_dictionary import Dictionary

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
    dictionaries = graphene.List(lambda: Dictionary)

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
        create_language(id: [949,18], translation_gist_id: [662, 3], parent_id: [1, 47], locale_exist: true) {
            language {
                id
                translation_gist_id
            }
        }
    }

    (this example works)
    {
      "create_language": {
        "language": {
          "id": [
            949,
            18
          ],
          "translation_gist_id": [
            662,
            3
          ]
        }
      }
    }
    """

    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        locale_exist = graphene.Boolean()

    language = graphene.Field(Language)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, args, context, info):
        id = args.get('id')
        client_id = id[0] if id else context["client_id"]
        object_id = id[1] if id else None
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0] if parent_id else None
        parent_object_id = parent_id[1] if parent_id else None

        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0]
        translation_gist_object_id = translation_gist_id[1]

        client = DBSession.query(Client).filter_by(id=client_id).first()
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        parent = None
        if parent_client_id and parent_object_id:
            parent = DBSession.query(dbLanguage).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()

        dblanguage = dbLanguage(
            client_id=client_id,
            object_id=object_id,
            translation_gist_client_id=translation_gist_client_id,
            translation_gist_object_id=translation_gist_object_id
        )
        DBSession.add(dblanguage)

        if parent:
            dblanguage.parent = parent

        DBSession.flush()
        language = Language(id=[dblanguage.client_id, dblanguage.object_id])
        language.dbObject = dblanguage
        return CreateLanguage(language=language, triumph=True)

class UpdateLanguage(graphene.Mutation):
    """
    example:
       mutation  {
        update_language(id: [949,18], translation_gist_id: [660, 4]) {
            language {
                id
                translation_gist_id
            }
        }
    }

    (this example works)
    returns:
   {
      "update_language": {
        "language": {
          "id": [
            949,
            18
          ],
          "translation_gist_id": [
            660,
            4
          ]
        }
      }
    }
    """
    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)

    language = graphene.Field(Language)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, args, context, info):
        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        dblanguage = DBSession.query(dbLanguage).filter_by(client_id=client_id, object_id=object_id).first()

        if dblanguage and not dblanguage.marked_for_deletion:
            parent_id = args.get('parent_id')
            if parent_id:
                dblanguage.parent_client_id = parent_id[0]
                dblanguage.parent_object_id = parent_id[1]

            translation_gist_id = args.get('translation_gist_id')
            if translation_gist_id:
                dblanguage.translation_gist_client_id = translation_gist_id[0]
                dblanguage.translation_gist_object_id = translation_gist_id[1]

            language = Language(id=[dblanguage.client_id, dblanguage.object_id])
            language.dbObject = dblanguage
            return UpdateLanguage(language=language, triumph=True)
        raise ResponseError(message="Error: No such language in the system")

class DeleteLanguage(graphene.Mutation):
    """
    example:
     mutation  {
        delete_language(id: [949,13]) {
            language {
                id
            }
        }
    }

    (this example works)
    {
      "delete_language": {
        "language": {
          "id": [
            949,
            13
          ]
        }
      }
    }
    """

    class Input:
        id = graphene.List(graphene.Int)

    language = graphene.Field(Language)
    triumph = graphene.Boolean()

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
            return DeleteLanguage(language=language, triumph=True)
        raise ResponseError(message="No such language in the system")

from .gql_dictionary import Dictionary