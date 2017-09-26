import graphene
from lingvodoc.models import (
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession,
    Client as dbClient,
    Language as dbLanguage,
    User as dbUser,
    DictionaryPerspective as dbDictionaryPerspective,
    BaseGroup as dbBaseGroup,
    Group as dbGroup
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
#from lingvodoc.schema.gql_dictionaryperspective import DictionaryPerspective
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
         perspectives{id translation}
      }
    }
    """

    dbType = dbDictionary
    dbObject = None
    category = graphene.Int()
    domain = graphene.Int()
    roles = graphene.List(ObjectVal)
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
    def create_persptofield(self):  # TODO: to delete
        return self._meta.fields['cr_persptofields'].type

    @fetch_object('status')
    def resolve_status(self, info):
        context = info.context
        atom = DBSession.query(dbTranslationAtom).filter_by(
            parent_client_id=self.dbObject.state_translation_gist_client_id,
            parent_object_id=self.dbObject.state_translation_gist_object_id,
            locale_id=int(context.get('locale_id'))).first()
        if atom:
            return atom.content
        else:
            return None

    def resolve_triumph(self, info):
        return True

    @client_id_check()
    def resolve_perspectives(self, info):
        dictionary_client_id, dictionary_object_id = self.id  #self.dbObject.client_id, self.dbObject.object_id

        perspectives = list()
        child_persps = DBSession.query(dbDictionaryPerspective)\
            .filter_by(parent_client_id=dictionary_client_id, parent_object_id=dictionary_object_id).all()
        for persp in child_persps:
            persp.dbObject = persp
            perspectives.append(persp)
        return perspectives

    def resolve_roles(self, info):
        response = dict()
        client_id, object_id = self.dbObject.client_id, self.dbObject.object_id
        dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not dictionary or dictionary.marked_for_deletion:
            raise ResponseError(message="Dictionary with such ID already exists in the system")


        bases = DBSession.query(dbBaseGroup).filter_by(dictionary_default=True)
        roles_users = dict()
        roles_organizations = dict()
        for base in bases:
            group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                     subject_object_id=object_id,
                                                     subject_client_id=client_id).first()
            perm = base.name
            users = []
            for user in group.users:
                users += [user.id]
            organizations = []
            for org in group.organizations:
                organizations += [org.id]
            roles_users[perm] = users
            roles_organizations[perm] = organizations
        response['roles_users'] = roles_users
        response['roles_organizations'] = roles_organizations

        #request.response.status = HTTPOk.code
        return response

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

    class Arguments:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int, required=True)
        parent_id = graphene.List(graphene.Int, required=True)
        additional_metadata = ObjectVal()
        perspectives = graphene.List(ObjectVal)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()
    perspectives = graphene.List(Dictionary)

    @staticmethod
    @client_id_check()
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

        client = DBSession.query(dbClient).filter_by(id=client_id).first()
        user = client.user
        for base in DBSession.query(dbBaseGroup).filter_by(dictionary_default=True):
            new_group = dbGroup(parent=base,
                              subject_object_id=dbdictionary_obj.object_id,
                              subject_client_id=dbdictionary_obj.client_id)
            if user not in new_group.users:
                new_group.users.append(user)
            DBSession.add(new_group)
            DBSession.flush()
        return dbdictionary_obj

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        ids = args.get("id")
        client_id = ids[0] if ids else info.context["client_id"]
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
        # rename it
        fields_dict = dict()
        field_ids = dict()
        persp_fake_ids = dict()
        if persp_args:
            for child_persp in persp_args:
                persp_translation_gist_id = child_persp["translation_gist_id"]
                obj_id = None
                if "id" in child_persp:
                    obj_id = child_persp["id"][1]
                new_persp = CreateDictionaryPerspective\
                    .create_perspective(client_id=client_id,
                                        object_id=obj_id,
                                        parent_client_id=dbdictionary_obj.client_id,
                                        parent_object_id=dbdictionary_obj.object_id,  # use all object attrs
                                        translation_gist_client_id=persp_translation_gist_id[0],  # TODO: fix it
                                        translation_gist_object_id=persp_translation_gist_id[1]
                                        )
                created_persps.append(new_persp)
                if "fake_id" in child_persp:
                    child_id = child_persp['fake_id']
                    persp_fake_ids[child_id] = new_persp

                if "fields" in child_persp:
                    new_fields = child_persp["fields"]
                    for new_ptofield in new_fields:
                        if new_ptofield.get('link') and new_ptofield['link'].get('fake_id'):
                            field_ids[new_ptofield['link'].get('fake_id')] = (new_ptofield['field_id'][0],
                                                                              new_ptofield['field_id'][1])
                            if new_persp not in fields_dict:
                                fields_dict[new_persp] = []
                            fields_dict[new_persp].append(new_ptofield['link'].get('fake_id'))  # put field id
                for persp in fields_dict:
                    for fake_link in fields_dict[persp]:
                        if fake_link in persp_fake_ids:
                            persp_to_link = persp_fake_ids[fake_link]
                            CreateDictionaryPerspectiveToField\
                                .create_dictionary_persp_to_field(client_id=client_id,
                                                                  parent_client_id=persp.client_id,
                                                                  parent_object_id=persp.object_id,
                                                                  field_client_id=field_ids[fake_link][0],
                                                                  field_object_id=field_ids[fake_link][1],
                                                                  self_client_id=None,
                                                                  self_object_id=None,
                                                                  link_client_id=persp_to_link.client_id,
                                                                  link_object_id=persp_to_link.object_id,
                                                                  position=1)

                    #if field.get('link') and field['link'].get('fake_id'):
                    #    #field['link'] = fake_ids[field['link']['fake_id']]


                dictionary.perspectives = [DictionaryPerspective(id=[persp.client_id, persp.object_id],
                                                                 translation_gist_id=[persp.translation_gist_client_id,
                                                                                      persp.translation_gist_object_id],
                                                                 # fields=[DictionaryPerspectiveToField(id=[persp.client_id,
                                                                 #                                          persp.object_id],
                                                                 #                                      parent_id=[persp.client_id,
                                                                 #                                                 persp.object_id],
                                                                 #                                      field_id=[f.client_id, f.object_id]
                                                                 #                                      ) for f in fields_dict[persp]]

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
    class Arguments:
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
    def mutate(root, info, **args):
        ids = args.get('id')
        client_id = ids[0] if ids else info.context["client_id"]
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
    class Arguments:
        id = graphene.List(graphene.Int, required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    @acl_check_by_id('delete', 'dictionary')
    def mutate(root, info, **args):
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


