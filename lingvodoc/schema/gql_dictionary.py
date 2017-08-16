import graphene

from lingvodoc.models import (
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession,
    Client as dbClient,
    Language as dbLanguage,
    User as dbUser
)
from lingvodoc.schema.gql_user import User

"""
from lingvodoc.views.v2.views import (
    translation_service_search
)
"""

from lingvodoc.schema.gql_holders import (
    ResponseError
)

from lingvodoc.views.v2.translations import translationgist_contents

# from lingvodoc.schema.gql_language import Language


def translation_service_search(searchstring):
    translationatom = DBSession.query(dbTranslationAtom)\
        .join(dbTranslationGist).\
        filter(dbTranslationAtom.content == searchstring,
               dbTranslationAtom.locale_id == 2,
               dbTranslationGist.type == 'Service')\
        .order_by(dbTranslationAtom.client_id)\
        .first()
    response = translationgist_contents(translationatom.parent)
    return response

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    StateHolder,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    ObjectVal
)

from lingvodoc.views.v2.delete import real_delete_dictionary
from lingvodoc.views.v2.utils import (
    check_client_id
)


class Dictionary(graphene.ObjectType):
    # TODO: resolve_dataType(?)
    """
     #created_at                       | timestamp without time zone | NOT NULL
     #object_id                        | bigint                      | NOT NULL
     #client_id                        | bigint                      | NOT NULL
     #parent_object_id                 | bigint                      |
     #parent_client_id                 | bigint                      |
     #translation_gist_client_id       | bigint                      | NOT NULL
     #translation_gist_object_id       | bigint                      | NOT NULL
     #state_translation_gist_client_id | bigint                      | NOT NULL
     #state_translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion              | boolean                     | NOT NULL
     #category                         | bigint                      |
     #domain                           | bigint                      |
     #additional_metadata              | jsonb                       |
     + status
     + .translation
     + dataType
    Test:
    query myQuery
    {
       dictionary(id:[126, 3])
       {
          id
          translation
          created_at
          parent_id
          marked_for_deletion
          translation_gist_id
          additional_metadata
              {
              blob_description
              }
        }

    }

    """

    dbType = dbDictionary
    dbObject = None
    category = graphene.Int()
    domain = graphene.Int()
    # parent_object_id
    # translation_gist_client_id
    # state_translation_gist_client_id
    triumph = graphene.Boolean()
    status = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder, TranslationHolder)


    @fetch_object('status')
    def resolve_status(self, args, context, info):
        atom = DBSession.query(dbTranslationAtom).filter_by(
            parent_client_id=self.dbObject.state_translation_gist_client_id,
            parent_object_id=self.dbObject.state_translation_gist_object_id,
            locale_id=int(context.get('locale_id'))).first()
        if atom:
            return atom.content
        else:
            return None



    def resolve_triumph(self, args, context, info):
        return True

class CreateDictionary(graphene.Mutation):


    """
    example:
mutation  {
        create_dictionary(id:[449,2491],translation_gist_id: [714, 3], parent_id: [500, 121], additional_metadata: {hash:"1234567"}) {
            triumph
            dictionary{
                id
                translation
                marked_for_deletion
                created_at
                translation
                            additional_metadata{
             hash
            }
            }

        }

             delete_dictionary(id:[449,2491]) {
            triumph
            dictionary{
                id
                translation
                created_at
                translation
                marked_for_deletion

                            additional_metadata{
             hash
            }
            }

        }
    }
    """


    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        additional_metadata = ObjectVal()

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()


    @staticmethod
    @client_id_check()
    def mutate(root, args, context, info):
        ids = args.get("id")
        client_id = ids[0] if ids else context["client_id"]
        object_id = ids[1] if ids else None
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0]
        parent_object_id = parent_id[1]

        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0]
        translation_gist_object_id = translation_gist_id[1]
        duplicate_check = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).all()
        if duplicate_check:
            raise ResponseError(message="Dictionary with such ID already exists in the system")



        parent = DBSession.query(dbLanguage).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()

        additional_metadata = args.get('additional_metadata')
        if not additional_metadata:
            additional_metadata = None

        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']


        dbentityobj = dbDictionary(client_id=client_id,
                                   object_id=object_id,
                                   state_translation_gist_object_id=state_translation_gist_object_id,
                                   state_translation_gist_client_id=state_translation_gist_client_id,
                                   parent=parent,
                                   translation_gist_client_id=translation_gist_client_id,
                                   translation_gist_object_id=translation_gist_object_id,
                                   additional_metadata=additional_metadata
                                   )

        dictionary = Dictionary(id=[dbentityobj.client_id, dbentityobj.object_id])
        dictionary.dbObject = dbentityobj
        DBSession.flush()
        return CreateDictionary(dictionary=dictionary, triumph=True)


class UpdateDictionary(graphene.Mutation):
    """
    example:
    mutation  {
        update_dictionary(id:[949,2492], additional_metadata: {hash:"new hash"}) {
            triumph
            dictionary{
                id
                translation
                marked_for_deletion
                created_at
                translation
                            additional_metadata{
             hash
            }
            }
        }
    }

    (this example works)
    returns:
    {
      "update_dictionary": {
        "triumph": true,
        "dictionary": {
          "id": [
            949,
            2492
          ],
          "translation": "Словарь башкирского языка",
          "marked_for_deletion": false,
          "created_at": "2017-08-16T10:25:35",
          "additional_metadata": {
            "hash": "new hash"
          }
        }
      }
    }
    """
    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        additional_metadata = ObjectVal()

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, args, context, info):
        id = args.get('id')
        client_id = id[0]
        object_id = id[1]
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0] if parent_id else None
        parent_object_id = parent_id[1] if parent_id else None
        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0] if translation_gist_id else None
        translation_gist_object_id = translation_gist_id[1] if translation_gist_id else None
        additional_metadata = args.get('additional_metadata')

        dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if dbdictionary and not dbdictionary.marked_for_deletion:
                if parent_client_id:
                    dbdictionary.parent_client_id = parent_client_id
                if parent_object_id:
                    dbdictionary.parent_object_id = parent_object_id
                if translation_gist_client_id:
                    dbdictionary.translation_gist_client_id = translation_gist_client_id
                if translation_gist_object_id:
                    dbdictionary.translation_gist_object_id = translation_gist_object_id
                if additional_metadata:
                    old_meta = dbdictionary.additional_metadata
                    old_meta.update(additional_metadata)
                    dbdictionary.additional_metadata = old_meta

                dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
                dictionary.dbObject = dbdictionary
                return UpdateDictionary(dictionary=dictionary, triumph=True)
        raise ResponseError(message="Error: No such dictionary in the system")

class DeleteDictionary(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, args, context, info):
        ids = args.get('id')
        client_id, object_id = ids
        dbentityobj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()

        if dbentityobj and not dbentityobj.marked_for_deletion:
            dbentityobj = dbentityobj.parent
            del_object(dbentityobj)
            dictionary = Dictionary(id=id)
            dictionary.dbObject = dbentityobj
            return DeleteDictionary(dictionary=dictionary, triumph=True)
        raise ResponseError(message="No such entity in the system")
