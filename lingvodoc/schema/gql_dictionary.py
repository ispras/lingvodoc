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
from sqlalchemy.orm.attributes import flag_modified
from lingvodoc.schema.gql_user import User

from lingvodoc.views.v2.utils import update_metadata
from lingvodoc.schema.gql_holders import (
    ResponseError
)
from lingvodoc.views.v2.translations import translationgist_contents
# from lingvodoc.schema.gql_language import Language
from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    StateHolder,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    ObjectVal,
    acl_check_by_id
)
from lingvodoc.views.v2.delete import real_delete_dictionary
from lingvodoc.views.v2.utils import (
    check_client_id
)


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
    query myQuery {
      dictionary(id: [126, 3]) {
        id
        translation
        created_at
        parent_id
        marked_for_deletion
        translation_gist_id
        additional_metadata {
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
    persp = graphene.Field('lingvodoc.schema.gql_dictionaryperspective.DictionaryPerspective')
    cr_persp = graphene.Field('lingvodoc.schema.gql_dictionaryperspective.CreateDictionaryPerspective')
    perspectives = graphene.List('lingvodoc.schema.gql_dictionaryperspective.DictionaryPerspective', )
    persptofields = graphene\
        .Field('lingvodoc.schema.gql_dictipersptofield.DictionaryPerspectiveToField')
    cr_persptofields = graphene\
        .Field('lingvodoc.schema.gql_dictipersptofield.CreateDictionaryPerspectiveToField')

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder, TranslationHolder)
    # @property

    @property
    def persp_class(self):
        return self._meta.fields['persp'].type

    @property
    def create_persp(self):
        return self._meta.fields['cr_persp'].type

    @property
    def persptofield_class(self):
        return self._meta.fields['persptofields'].type

    @property
    def create_persptofield(self):
        return self._meta.fields['cr_persptofields'].type

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

    def resolve_perspectives(self, args, context, info):
        if hasattr(self, "perspectives"):
            return self.perspectives
###
# CrUd functions
#
###


class CreateDictionary(graphene.Mutation):
    """
    example:
    mutation {
      create_dictionary(id: [449, 2527], translation_gist_id: [714, 3], parent_id: [500, 121],
      additional_metadata: {hash: "1234567"}) {
        triumph
        dictionary {
          id
          translation
          marked_for_deletion
          created_at
          translation
          additional_metadata {
            hash
          }
        }
      }
    }
    """

    class Input:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int, required=True)
        parent_id = graphene.List(graphene.Int, required=True)
        additional_metadata = ObjectVal()
        perspectives = graphene.List(ObjectVal)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()
    perspectives = graphene.List(Dictionary)

    @staticmethod
    def create_dbdictionary(client_id=None,
                            object_id=None,
                            parent_client_id=None,
                            parent_object_id=None,
                            translation_gist_client_id=None,
                            translation_gist_object_id=None,
                            additional_metadata=None):
        duplicate_check = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).all()
        if duplicate_check:
            raise ResponseError(message="Dictionary with such ID already exists in the system")
        parent = DBSession.query(dbLanguage).filter_by(client_id=parent_client_id, object_id=parent_object_id).first()
        resp = translation_service_search("WiP")
        state_translation_gist_object_id, state_translation_gist_client_id = resp['object_id'], resp['client_id']
        dbdictionary_obj = dbDictionary(client_id=client_id,
                                        object_id=object_id,
                                        state_translation_gist_object_id=state_translation_gist_object_id,
                                        state_translation_gist_client_id=state_translation_gist_client_id,
                                        parent=parent,
                                        translation_gist_client_id=translation_gist_client_id,
                                        translation_gist_object_id=translation_gist_object_id,
                                        additional_metadata=additional_metadata
                                        )
        return dbdictionary_obj

    @staticmethod
    @acl_check_by_id('create', 'dictionary')
    @client_id_check()
    def mutate(root, args, context, info):
        ids = args.get("id")
        client_id = ids[0] if ids else context["client_id"]
        object_id = ids[1] if ids else None
        parent_client_id, parent_object_id = args.get('parent_id')
        translation_gist_client_id, translation_gist_object_id = args.get('translation_gist_id')
        additional_metadata = args.get("additional_metadata")

        dbdictionary_obj = CreateDictionary.create_dbdictionary(client_id=client_id,
                                                                object_id=object_id,
                                                                parent_client_id=parent_client_id,
                                                                parent_object_id=parent_object_id,
                                                                translation_gist_client_id=translation_gist_client_id,
                                                                translation_gist_object_id=translation_gist_object_id,
                                                                additional_metadata=additional_metadata)
        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj


        DictionaryPerspective = dictionary.persp_class
        CreateDictionaryPerspective = dictionary.create_persp
        DictionaryPerspectiveToField = dictionary.persptofield_class
        CreateDictionaryPerspectiveToField = dictionary.create_persptofield
        persp_args = args.get("perspectives")
        created_persps = []
        fields_dict = {}

        fake_ids = dict()
        if persp_args:
            for child_persp in persp_args:
                persp_translation_gist_id = child_persp["translation_gist_id"]
                new_persp = CreateDictionaryPerspective\
                    .create_perspective(client_id=client_id,
                                        object_id=object_id,
                                        parent_client_id=dbdictionary_obj.client_id,
                                        parent_object_id=dbdictionary_obj.object_id,  # use all object attrs
                                        translation_gist_client_id=persp_translation_gist_id[0],  # TODO: fix it
                                        translation_gist_object_id=persp_translation_gist_id[1]
                                        )
                created_persps.append(new_persp)
                if "fake_id" in child_persp:
                    fake_ids[child_persp['fake_id']] = new_persp
                fields_dict[new_persp] = []

                if "fields" in child_persp:
                    new_fields = child_persp["fields"]
                    for new_ptofield in new_fields:
                        fields_dict[new_persp].append(new_ptofield)
            for persp in fields_dict:
                for field in fields_dict[persp]:
                    if field.get('link') and field['link'].get('fake_id'):
                        field['link'] = fake_ids[field['link']['fake_id']]

            dictionary.perspectives = [DictionaryPerspective(id=[persp.client_id, persp.object_id],
                                                             translation_gist_id=[persp.translation_gist_client_id,
                                                                                  persp.translation_gist_object_id],
                                                             fields=[DictionaryPerspectiveToField(id=[persp.client_id,
                                                                                                      persp.object_id],
                                                                                                  parent_id=[persp.client_id,
                                                                                                             persp.object_id],
                                                                                                  field_id=[f.client_id, f.object_id]
                                                                                                  ) for f in fields_dict[persp]]

                                                             ) for persp in created_persps]
        return CreateDictionary(dictionary=dictionary,
                                # perspectives=[PERSPECTIVE(id=[persp.client_id, persp.object_id],
                                #                           translation_gist_id=[persp.translation_gist_client_id,
                                #                                                persp.translation_gist_object_id]
                                #                           ) for persp in created_persps],
                                triumph=True)


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
        id = graphene.List(graphene.Int, required=True)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int)
        additional_metadata = ObjectVal()

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    def update_dictionary(client_id=None,
                          object_id=None,
                          parent_client_id=None,
                          parent_object_id=None,
                          translation_gist_client_id=None,
                          translation_gist_object_id=None,
                          additional_metadata=None
                          ):
        db_dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not db_dictionary or db_dictionary.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")

        if parent_client_id:
            db_dictionary.parent_client_id = parent_client_id
        if parent_object_id:
            db_dictionary.parent_object_id = parent_object_id
        if translation_gist_client_id:
            db_dictionary.translation_gist_client_id = translation_gist_client_id
        if translation_gist_object_id:
            db_dictionary.translation_gist_object_id = translation_gist_object_id
        update_metadata(db_dictionary, additional_metadata)
        return db_dictionary

    @staticmethod
    @client_id_check()
    @acl_check_by_id('edit', 'dictionary')
    def mutate(root, args, context, info):
        ids = args.get('id')
        client_id = ids[0] if ids else context["client_id"]
        object_id = ids[1] if ids else None
        parent_id = args.get('parent_id')
        parent_client_id = parent_id[0] if parent_id else None
        parent_object_id = parent_id[1] if parent_id else None
        translation_gist_id = args.get('translation_gist_id')
        translation_gist_client_id = translation_gist_id[0] if translation_gist_id else None
        translation_gist_object_id = translation_gist_id[1] if translation_gist_id else None
        additional_metadata = args.get('additional_metadata')
        dbdictionary = UpdateDictionary.update_dictionary(client_id=client_id,
                                                          object_id=object_id,
                                                          parent_client_id=parent_client_id,
                                                          parent_object_id=parent_object_id,
                                                          translation_gist_client_id=translation_gist_client_id,
                                                          translation_gist_object_id=translation_gist_object_id,
                                                          additional_metadata=additional_metadata
                                                          )
        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        return UpdateDictionary(dictionary=dictionary, triumph=True)


class DeleteDictionary(graphene.Mutation):
    """
    mutation {
      delete_dictionary(id: [449, 2491]) {
        triumph
        dictionary {
          id
          translation
          created_at
          translation
          marked_for_deletion
          additional_metadata {
            hash
          }
        }
      }
    }
    """
    class Input:
        id = graphene.List(graphene.Int, required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    @acl_check_by_id('delete', 'dictionary')
    def mutate(root, args, context, info):
        ids = args.get('id')
        if not ids:
            raise ResponseError(message="id not found")
        client_id = ids[0]
        object_id = ids[1]
        dbdictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbdictionary_obj or dbdictionary_obj.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")
        del_object(dbdictionary_obj)
        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj
        return DeleteDictionary(dictionary=dictionary, triumph=True)


