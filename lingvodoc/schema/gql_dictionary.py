import datetime
import graphene
from lingvodoc.models import (
    Dictionary as dbDictionary,
    TranslationAtom as dbTranslationAtom,
    TranslationGist as dbTranslationGist,
    DBSession,
    Client as dbClient,
    Language as dbLanguage,
    User as dbUser,
    Field as dbField,
    DictionaryPerspective as dbDictionaryPerspective,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    Organization as dbOrganization
)
from sqlalchemy.orm.attributes import flag_modified
from lingvodoc.schema.gql_user import User

from lingvodoc.views.v2.utils import (
    update_metadata,
    cache_clients)
from lingvodoc.schema.gql_holders import (
    ResponseError
)
from lingvodoc.views.v2.translations import translationgist_contents
from lingvodoc.views.v2.utils import cache_clients
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
from graphene.types.generic import GenericScalar
from lingvodoc.views.v2.utils import  add_user_to_group
from lingvodoc.utils import statistics

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

class UserAndOrganizationsRoles(graphene.ObjectType):
    roles_users = graphene.List(graphene.String)
    roles_organizations = graphene.List(graphene.String)

    def resolve_roles_users(self, info):
        return self.roles_users

    def resolve_roles_organizations(self, info):
        return self.roles_organizations

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
         roles{
             roles_users
             roles_organizations
         }
      }
    }
    or

          dictionary(id: [126, 3], starting_time: 0, ending_time: 100) { statistic   ...
    """

    dbType = dbDictionary
    dbObject = None
    category = graphene.Int()
    domain = graphene.Int()
    roles = graphene.Field(UserAndOrganizationsRoles)
    statistic = graphene.Field(ObjectVal, starting_time=graphene.Int(), ending_time=graphene.Int())
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
        interfaces = (CommonFieldsComposite, StateHolder)
    # @property

    @property  # TODO: delete
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

    @fetch_object()
    def resolve_statistic(self, info, starting_time=None, ending_time=None):
        #print(starting_time)
        if starting_time is None or ending_time is None:
            raise ResponseError(message="Time error")
        locale_id = info.context.get('locale_id')
        return statistics.stat_dictionary((self.dbObject.client_id, self.dbObject.object_id),
                                   starting_time,
                                   ending_time,
                                   locale_id=locale_id
                                   )

    def resolve_triumph(self, info):
        return True

    @client_id_check()
    def resolve_perspectives(self, info):
        if not self.id:
            raise ResponseError(message="Dictionary with such ID doesn`t exists in the system")
        dictionary_client_id, dictionary_object_id = self.id  #self.dbObject.client_id, self.dbObject.object_id

        perspectives = list()
        child_persps = DBSession.query(dbDictionaryPerspective)\
            .filter_by(parent_client_id=dictionary_client_id, parent_object_id=dictionary_object_id).all()
        for persp in child_persps:
            persp.dbObject = persp
            perspectives.append(persp)
        return perspectives
    @fetch_object()
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
        #return response
        return UserAndOrganizationsRoles(roles_users=roles_users, roles_organizations=roles_organizations)

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

    complex_create:
    mutation CreateDictionary1($persp_tr:[ObjectVal],
        $metadata: ObjectVal,
        $dictionary_atoms:[ObjectVal]){
        create_dictionary(
                parent_id: [500, 121],
                additional_metadata: $metadata,
                translation_atoms: $dictionary_atoms,
                perspectives: $persp_tr
     ) {
        dictionary {
          id
          perspectives {
            id
            created_at
            translation
          }
          translation
        }
      }
    }
    ============================
      # variables:
    ============================

    {
       "dictionary_atoms":[
          {
             "content":"dictionary_name",
             "locale_id":2
          }
       ],
       "metadata":{
          "hash":"1234567"
       },
       "persp_tr":[
          {
             "translation_atoms":[
                {
                   "locale_id":2,
                   "content":"The first perspective"
                }
             ],
             "fake_id":"0ce97e69-ece9-400b-a625-e7a20110246e3",
             "fields":[
                {
                   "field_id":[
                      1,
                      213
                   ],
                   "link":{
                      "fake_id":"2e3684b7-6d81-4d103-a10e10-295517ad2f75"
                   }
                }
             ]
          },
          {
             "translation_atoms":[
                {
                   "locale_id":2,
                   "content":"The second perspective"
                }
             ],
             "fake_id":"2e3684b7-6d81-4d103-a10e10-295517ad2f75",
             "fields":[
                {
                   "field_id":[
                      1,
                      213
                   ],
                   "link":{
                      "fake_id":"0ce97e69-ece9-400b-a625-e7a20110246e3"
                   }
                }
             ]
          }
       ]
    }
    """

    class Arguments:
        id = graphene.List(graphene.Int)
        translation_gist_id = graphene.List(graphene.Int)
        parent_id = graphene.List(graphene.Int, required=True)
        additional_metadata = ObjectVal()
        perspectives = graphene.List(ObjectVal)
        translation_atoms = graphene.List(ObjectVal)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()
    perspectives = graphene.List(Dictionary)
    translation_atoms = graphene.List(ObjectVal)

    @staticmethod
    #@client_id_check()
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
        tr_atoms = args.get("translation_atoms")
        if type(tr_atoms) is not list:  # TODO: look at this
            translation_gist_id = args.get('translation_gist_id')
            if not translation_gist_id:
                raise ResponseError(message="translation_gist_id arg not found")
            translation_gist_client_id = translation_gist_id[0]
            translation_gist_object_id = translation_gist_id[1]
        else:
            client = DBSession.query(dbClient).filter_by(id=client_id).first()

            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            dbtranslationgist = dbTranslationGist(client_id=client_id, object_id=object_id, type="Language")
            translation_gist_client_id = dbtranslationgist.client_id
            translation_gist_object_id = dbtranslationgist.object_id
            DBSession.add(dbtranslationgist)
            DBSession.flush()
            basegroups = list()
            basegroups.append(DBSession.query(dbBaseGroup).filter_by(name="Can delete translationgist").first())
            if not object_id:
                groups = []
                for base in basegroups:
                    group = dbGroup(subject_client_id=translation_gist_client_id, subject_object_id=translation_gist_object_id,
                                  parent=base)
                    groups += [group]
                for group in groups:
                    add_user_to_group(user, group)

            for atom_dict in tr_atoms:
                if "locale_id" in atom_dict and "content" in atom_dict:
                    locale_id = atom_dict["locale_id"]
                    content = atom_dict["content"]
                    dbtranslationatom = dbTranslationAtom(client_id=client_id,
                                                          object_id=object_id,
                                                          parent=dbtranslationgist,
                                                          locale_id=locale_id,
                                                          content=content)
                    DBSession.add(dbtranslationatom)
                    DBSession.flush()
                    if not object_id:
                        basegroups = []
                        basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can edit translationatom").first()]
                        if not object_id:
                            groups = []
                            for base in basegroups:
                                group = dbGroup(subject_client_id=dbtranslationatom.client_id,
                                                subject_object_id=dbtranslationatom.object_id,
                                                parent=base)
                                groups += [group]
                            for group in groups:
                                add_user_to_group(user, group)
                else:
                    raise ResponseError(message="locale_id and content args not found")
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
                if "translation_atoms" in child_persp:
                    client = DBSession.query(dbClient).filter_by(id=client_id).first()
                    user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
                    atoms_to_create = child_persp["translation_atoms"]
                    dbtranslationgist = dbTranslationGist(client_id=client_id, object_id=object_id, type="Language")
                    translation_gist_client_id = dbtranslationgist.client_id
                    translation_gist_object_id = dbtranslationgist.object_id
                    persp_translation_gist_id = [translation_gist_client_id, translation_gist_object_id]
                    DBSession.add(dbtranslationgist)
                    DBSession.flush()
                    basegroups = list()
                    basegroups.append(DBSession.query(dbBaseGroup).filter_by(name="Can delete translationgist").first())
                    if not object_id:
                        groups = []
                        for base in basegroups:
                            group = dbGroup(subject_client_id=translation_gist_client_id, subject_object_id=translation_gist_object_id,
                                          parent=base)
                            groups += [group]
                        for group in groups:
                            add_user_to_group(user, group)

                    for atom_dict in atoms_to_create:
                        if "locale_id" in atom_dict and "content" in atom_dict:
                            locale_id = atom_dict["locale_id"]
                            content = atom_dict["content"]
                            dbtranslationatom = dbTranslationAtom(client_id=client_id,
                                                                  object_id=object_id,
                                                                  parent=dbtranslationgist,
                                                                  locale_id=locale_id,
                                                                  content=content)
                            DBSession.add(dbtranslationatom)
                            DBSession.flush()
                            if not object_id:
                                basegroups = []
                                basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can edit translationatom").first()]
                                if not object_id:
                                    groups = []
                                    for base in basegroups:
                                        group = dbGroup(subject_client_id=dbtranslationatom.client_id,
                                                        subject_object_id=dbtranslationatom.object_id,
                                                        parent=base)
                                        groups += [group]
                                    for group in groups:
                                        add_user_to_group(user, group)
                        else:
                            raise ResponseError(message="locale_id and content args not found")
                else:
                    if "translation_gist_id" in child_persp:
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

# class UpdateDictionaryStatus(graphene.Mutation):
#     """
#     mutation  {
#         update_dictionary_status(id:[475, 2], state_translation_gist_id: [1, 123]) {
#             triumph
#             dictionary{
#                 id
#                 translation
#                 marked_for_deletion
#                 created_at
#                 status
#                 translation
#                             additional_metadata{
#              hash
#             }
#             }
#         }
#     }
#     """
#     class Arguments:
#         id = graphene.List(graphene.Int)
#         state_translation_gist_id = graphene.List(graphene.Int)
#
#     dictionary = graphene.Field(Dictionary)
#     triumph = graphene.Boolean()
#
#     @staticmethod
#     @client_id_check()
#     def mutate(root, info, **args):
#         client_id, object_id = args.get('id')
#         state_translation_gist_client_id, state_translation_gist_object_id = args.get('state_translation_gist_id')
#         dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
#         if dbdictionary and not dbdictionary.marked_for_deletion:
#             dbdictionary.state_translation_gist_client_id = state_translation_gist_client_id
#             dbdictionary.state_translation_gist_object_id = state_translation_gist_object_id
#             atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=state_translation_gist_client_id,
#                                                               parent_object_id=state_translation_gist_object_id,
#                                                               locale_id=info.context.get('locale_id')).first()
#             dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id], status=atom.content)
#             dictionary.dbObject = dbdictionary
#             return UpdateDictionaryStatus(dictionary=dictionary, triumph=True)
#         raise ResponseError(message="No such dictionary in the system")

class UpdateDictionaryRoles(graphene.Mutation):
    class Arguments:
        id = graphene.List(graphene.Int)
        roles_users = ObjectVal()
        roles_organizations = ObjectVal()

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    #@client_id_check
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if dbdictionary and not dbdictionary.marked_for_deletion:
            if roles_users:
                for role_name in roles_users:
                    base = DBSession.query(dbBaseGroup).filter_by(name=role_name, dictionary_default=True).first()
                    if not base:
                        raise ResponseError(message="No such role in the system")
                    group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                             subject_object_id=object_id,
                                                             subject_client_id=client_id).first()

                    client = DBSession.query(dbClient).filter_by(id=info.context.get('client_id')).first()

                    userlogged = DBSession.query(dbUser).filter_by(id=client.user_id).first()
                    permitted = False
                    if userlogged in group.users:
                        permitted = True
                    if not permitted:
                        for org in userlogged.organizations:
                            if org in group.organizations:
                                permitted = True
                                break
                    if not permitted:
                        override_group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                                          subject_override=True).first()
                        if userlogged in override_group.users:
                            permitted = True

                    if permitted:
                        users = roles_users[role_name]
                        for userid in users:
                            user = DBSession.query(dbUser).filter_by(id=userid).first()
                            if user:
                                if user not in group.users:
                                    group.users.append(user)
                    else:
                        raise ResponseError(message="Not enough permission")
            if roles_organizations:
                for role_name in roles_organizations:
                    base = DBSession.query(dbBaseGroup).filter_by(name=role_name, dictionary_default=True).first()
                    if not base:
                        raise ResponseError(message="No such role in the system")

                    group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                               subject_object_id=object_id,
                                                               subject_client_id=client_id).first()

                    client = DBSession.query(dbClient).filter_by(id=info.context.get('client_id')).first()

                    userlogged = DBSession.query(dbUser).filter_by(id=client.user_id).first()
                    permitted = False
                    if userlogged in group.users:
                        permitted = True
                    if not permitted:
                        for org in userlogged.organizations:
                            if org in group.organizations:
                                permitted = True
                                break
                    if not permitted:
                        override_group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                                          subject_override=True).first()
                        if userlogged in override_group.users:
                            permitted = True

                    if permitted:
                        orgs = roles_organizations[role_name]
                        for orgid in orgs:
                            org = DBSession.query(dbOrganization).filter_by(id=orgid).first()
                            if org:
                                if org not in group.organizations:
                                    group.organizations.append(org)
                    else:
                        raise ResponseError(message="Not enough permission")

            dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
            dictionary.dbObject = dbdictionary
            return UpdateDictionaryRoles(dictionary=dictionary, triumph=True)
        raise ResponseError(message="No such dictionary in the system")


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


