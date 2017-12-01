import datetime
from collections import defaultdict
from itertools import chain
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
from lingvodoc.utils.creation import create_gists_with_atoms, update_metadata, add_user_to_group
from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CommonFieldsComposite,
    StateHolder,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    ObjectVal,
    acl_check_by_id,
    LingvodocID,
    UserAndOrganizationsRoles
)

from lingvodoc.utils import statistics
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field,
                                      edit_role)

class UserToRoles(graphene.ObjectType):
    id_user = graphene.Int()
    roles = graphene.List(graphene.Int)

    def resolve_roles(self, info):
        return self.user_id

    def resolve_id_user(self, info):
        return self.roles


class Dictionary(LingvodocObjectType):  # tested
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

          dictionary(id: [126, 3], starting_time: 0, ending_time: 100) { statistic   ... # todo timestamp
    """

    dbType = dbDictionary
    category = graphene.Int()
    domain = graphene.Int()
    roles = graphene.Field(UserAndOrganizationsRoles)
    statistic = graphene.Field(ObjectVal, starting_time=graphene.Int(), ending_time=graphene.Int())
    status = graphene.String()

    perspectives = graphene.List('lingvodoc.schema.gql_dictionaryperspective.DictionaryPerspective', )
    persp = graphene.Field('lingvodoc.schema.gql_dictionaryperspective.DictionaryPerspective')
    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder)


    @property
    def persp_class(self):
        return self._meta.fields['persp'].type

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
            raise ResponseError(message="Time period is not chosen")
        locale_id = info.context.get('locale_id')
        return statistics.stat_dictionary((self.dbObject.client_id, self.dbObject.object_id),
                                   starting_time,
                                   ending_time,
                                   locale_id=locale_id
                                   )
    @fetch_object()
    def resolve_perspectives(self, info):
        if not self.id:
            raise ResponseError(message="Dictionary with such ID doesn`t exists in the system")
        dictionary_client_id, dictionary_object_id = self.id  #self.dbObject.client_id, self.dbObject.object_id

        perspectives = list()
        child_persps = DBSession.query(dbDictionaryPerspective)\
            .filter_by(parent_client_id=dictionary_client_id, parent_object_id=dictionary_object_id).all()
        for persp in child_persps:
            persp_object = self.persp_class(id = [persp.client_id, persp.object_id])
            persp_object.dbObject = persp
            perspectives.append(persp_object)
        return perspectives

    @fetch_object(ACLSubject='dictionary_role', ACLKey='id')
    def resolve_roles(self, info):
        client_id, object_id = self.dbObject.client_id, self.dbObject.object_id
        dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not dictionary or dictionary.marked_for_deletion:
            raise ResponseError(message="Dictionary with such ID doesn`t exists in the system")


        bases = DBSession.query(dbBaseGroup).filter_by(dictionary_default=True)
        roles_users = defaultdict(list)
        roles_organizations = defaultdict(list)
        for base in bases:
            group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                     subject_object_id=object_id,
                                                     subject_client_id=client_id).first()
            if not group:
                continue
            for user in group.users:
                roles_users[user.id].append(base.id)
            for org in group.organizations:
                roles_organizations[org.id].append(base.id)
        roles_users = [{"user_id": x, "roles_ids": roles_users[x]} for x in roles_users]
        roles_organizations = [{"user_id": x, "roles_ids": roles_organizations[x]} for x in roles_organizations]
        return UserAndOrganizationsRoles(roles_users=roles_users, roles_organizations=roles_organizations)

    @fetch_object('category')
    def resolve_category(self, info):
        return self.dbObject.category

    @fetch_object('domain')
    def resolve_domain(self, info):
        return self.dbObject.domain
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


	"dictionary_atoms": [
		{
			"content": "dictionary_cool_name3",
			"locale_id": 2
		}
	],
	"metadata": {
		"hash": "1234567"
	},
	"persp_tr": [
		{
			"translation_atoms": [
				{
					"locale_id": 2,
					"content": "The first perspective"
				}
			],
			"fake_id": "0ce97e69-ece9-400b-a625-e7a20110246e3",
			"fields": [
				{
					"field_id": [
						1,
						213
					],
					"link": {
						"fake_id": "2e3684b7-6d81-4d103-a10e10-295517ad2f75"
					}
				},
				{
									"field_id": [
						66,
						6
					]
				},
				{
					"field_id": [
						66,
						12
					],
					"fake_id": "FIELD_LINK_FAKE_ID-ae10aee"
				},
				{
					"field_id": [
						66,
						23
					],
					"self_fake_id": "FIELD_LINK_FAKE_ID-ae10aee"
				}

			]
		},
		{
			"translation_atoms": [
				{
					"locale_id": 2,
					"content": "The second perspective"
				}
			],
			"fake_id": "2e3684b7-6d81-4d103-a10e10-295517ad2f75",
			"fields": [
				{
					"field_id": [
						1,
						213
					],

					"link": {
						"fake_id": "0ce97e69-ece9-400b-a625-e7a20110246e3"
					}
				}
			]
		}
	]
}
    """

    class Arguments:
        id = LingvodocID()
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID(required=True)
        additional_metadata = ObjectVal()
        perspectives = graphene.List(ObjectVal)
        translation_atoms = graphene.List(ObjectVal)
        category = graphene.Int()
        domain = graphene.Int()

    class FieldInfo(object):
        id = None
        fake_id = None
        link_fake_id = None
        field_id = None
        field_fake_id = None
        self_fake_id = None
        perspective_obj = None
        def __init__(self, perspective_obj=None):
            self.perspective_obj = perspective_obj

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()
    perspectives = graphene.List(Dictionary)
    translation_atoms = graphene.List(ObjectVal)

    @staticmethod
    def get_by_fake_id(fake_to_id, fake_id):
        if fake_id not in fake_to_id:
            raise ResponseError(message="Fake_ids don`t match")
        return fake_to_id[fake_id]

    @staticmethod
    @client_id_check()  # tested
    def mutate(root, info, **args):
        # TODO: complex_create with fields
        ids = args.get("id")
        client_id = ids[0] if ids else info.context["client_id"]
        object_id = ids[1] if ids else None
        parent_id = args.get('parent_id')
        tr_atoms = args.get("translation_atoms")
        translation_gist_id = args.get('translation_gist_id')
        translation_gist_id = create_gists_with_atoms(tr_atoms, translation_gist_id, [client_id,object_id])
        additional_metadata = args.get("additional_metadata")
        category = args.get("category")
        domain = args.get("domain")
        ids = [client_id, object_id]
        dbdictionary_obj = create_dbdictionary(id=ids,
                                               parent_id=parent_id,
                                               translation_gist_id=translation_gist_id,
                                               additional_metadata=additional_metadata,
                                               category=category,
                                               domain=domain)
        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj

        persp_args = args.get("perspectives")
        # TODO:  rename it
        persp_fake_ids = dict()
        field_fake_ids = dict()
        persp_fields_list = defaultdict(list)
        if persp_args:
            for next_persp in persp_args:
                atoms_to_create = next_persp.get("translation_atoms")
                persp_translation_gist_id = next_persp.get("translation_gist_id")
                persp_translation_gist_id = create_gists_with_atoms(atoms_to_create, persp_translation_gist_id, [client_id,object_id])
                parent_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
                new_persp = create_perspective(id=(client_id, None),
                                        parent_id=parent_id,  # TODO: use all object attrs
                                        translation_gist_id=persp_translation_gist_id
                                        )

                if "fake_id" in next_persp:
                    perspective_fake_id = next_persp['fake_id']
                    persp_fake_ids[perspective_fake_id] = new_persp

                if "fields" in next_persp:
                    new_fields = next_persp["fields"]
                    for new_ptofield in new_fields:
                        field_info = CreateDictionary.FieldInfo(perspective_obj=new_persp)
                        if not "field_id" in new_ptofield:
                            raise ResponseError(message="One of fields in list has not field_id")
                        field_info.field_id = new_ptofield["field_id"]
                        if "self_fake_id" in new_ptofield:
                            field_info.self_fake_id = new_ptofield["self_fake_id"]
                        if 'fake_id' in new_ptofield:
                            field_info.fake_id = new_ptofield['fake_id']
                        if new_ptofield.get('link') and new_ptofield['link'].get('fake_id'):
                            field_info.link_fake_id = new_ptofield['link'].get('fake_id')
                        persp_fields_list[new_persp].append(field_info)
            for persp in persp_fields_list:
                counter = 0
                fields = persp_fields_list[persp]
                for field in fields:
                    counter += 1
                    link_id = field.link_fake_id # TODO: rename field.link_id to fake_link_id
                    field_id = field.field_id
                    fake_id = field.fake_id
                    self_fake_id = field.self_fake_id
                    self_id = None
                    parent_id = (persp.client_id, persp.object_id)
                    if link_id:
                        persp_to_link = CreateDictionary.get_by_fake_id(persp_fake_ids, link_id)
                        link_id=(persp_to_link.client_id, persp_to_link.object_id)
                    if self_fake_id:
                        self_id = CreateDictionary.get_by_fake_id(field_fake_ids, self_fake_id)
                    persp_to_field = create_dictionary_persp_to_field(id=id,
                                                     parent_id=parent_id,
                                                     field_id=field_id,
                                                     upper_level=self_id,
                                                     link_id=link_id,
                                                     position=counter)
                    if fake_id:
                        field_fake_ids[fake_id] = persp_to_field

        return CreateDictionary(dictionary=dictionary,
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
        id = LingvodocID(required=True)
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID()
        additional_metadata = ObjectVal()


    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    def update_dictionary(ids,
                          parent_id=None,
                          translation_gist_id=None,
                          additional_metadata=None,
                          ):
        if not ids:
            raise ResponseError(message="dict id not found")
        client_id, object_id = ids
        db_dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not db_dictionary or db_dictionary.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")

        if parent_id:
            language_client_id, language_object_id = parent_id
            parent = DBSession.query(dbLanguage).filter_by(client_id=language_client_id, object_id = language_object_id)
            if not parent:
                raise ResponseError(message="Error: No such language in the system")
            db_dictionary.parent_client_id = language_client_id
            db_dictionary.parent_object_id = language_object_id
        if translation_gist_id:
            db_dictionary.translation_gist_client_id, translation_gist_object_id = translation_gist_id

        update_metadata(db_dictionary, additional_metadata)
        return db_dictionary

    @staticmethod
    @acl_check_by_id('edit', 'dictionary')  # tested
    def mutate(root, info, **args):  # tested
        ids = args.get('id')
        if not ids:
            ids = (info.context["client_id"], None)
        parent_id = args.get('parent_id')
        translation_gist_id = args.get('translation_gist_id')
        additional_metadata = args.get('additional_metadata')
        dbdictionary = UpdateDictionary.update_dictionary(ids,
                                                          parent_id=parent_id,
                                                          translation_gist_id=translation_gist_id,
                                                          additional_metadata=additional_metadata
                                                          )
        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        return UpdateDictionary(dictionary=dictionary, triumph=True)

class UpdateDictionaryStatus(graphene.Mutation):
    """
    mutation  {
        update_dictionary_status(id:[475, 2], state_translation_gist_id: [1, 123]) {
            triumph
            dictionary{
                id
                translation
                marked_for_deletion
                created_at
                status
                translation
            additional_metadata{
             hash
            }
            }
        }
    }
    """
    class Arguments:
        id = LingvodocID(required=True)
        state_translation_gist_id = LingvodocID(required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("edit", "dictionary_status")
    def mutate(root, info, **args):
        client_id, object_id = args.get('id')
        state_translation_gist_client_id, state_translation_gist_object_id = args.get('state_translation_gist_id')
        dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if dbdictionary and not dbdictionary.marked_for_deletion:
            dbdictionary.state_translation_gist_client_id = state_translation_gist_client_id
            dbdictionary.state_translation_gist_object_id = state_translation_gist_object_id
            atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=state_translation_gist_client_id,
                                                              parent_object_id=state_translation_gist_object_id,
                                                              locale_id=info.context.get('locale_id')).first()
            dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id], status=atom.content)
            dictionary.dbObject = dbdictionary
            return UpdateDictionaryStatus(dictionary=dictionary, triumph=True)
        raise ResponseError(message="No such dictionary in the system")

class AddDictionaryRoles(graphene.Mutation):
    """
        mutation myQuery {
            add_dictionary_roles(id: [1279,4], user_id:2 , roles_users:[7,10,11,14,19,25,17,33]){
						triumph

					}
        }
    """
    class Arguments:
        id = LingvodocID(required=True)
        user_id = graphene.Int(required=True)
        roles_users = graphene.List(graphene.Int)
        roles_organizations = graphene.List(graphene.Int)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("create", "dictionary_role")
    def mutate(root, info, **args):
        dictionary_client_id, dictionary_object_id = args.get('id')
        user_id = args.get("user_id")
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        client_id = info.context.get('locale_id')
        if not dbdictionary or dbdictionary.marked_for_deletion:
            raise ResponseError(message="No such dictionary in the system")
        if roles_users:
            for role_id in roles_users:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True)
        if roles_organizations:
            for role_id in roles_organizations:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True, organization=True)
        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        return AddDictionaryRoles(dictionary=dictionary, triumph=True)

class DeleteDictionaryRoles(graphene.Mutation):
    """
        mutation myQuery {
            delete_dictionary_roles(id: [1279,4], user_id:2 , roles_users:[7]){
						triumph

					}
        }
    """
    class Arguments:
        id = LingvodocID(required=True)
        user_id = graphene.Int(required=True)
        roles_users = graphene.List(graphene.Int)
        roles_organizations = graphene.List(graphene.Int)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id("delete", "dictionary_role")
    def mutate(root, info, **args):
        dictionary_client_id, dictionary_object_id = args.get('id')
        user_id = args.get("user_id")
        roles_users = args.get('roles_users')
        roles_organizations = args.get('roles_organizations')
        dbdictionary = DBSession.query(dbDictionary).filter_by(client_id=dictionary_client_id, object_id=dictionary_object_id).first()
        client_id = info.context.get('locale_id')

        if not dbdictionary or dbdictionary.marked_for_deletion:
            raise ResponseError(message="No such dictionary in the system")
        if roles_users:
            for role_id in roles_users:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True, action="delete")

        if roles_organizations:
            for role_id in roles_organizations:
                edit_role(dbdictionary, user_id, role_id, client_id, dictionary_default=True, organization=True,
                          action="delete")


        dictionary = Dictionary(id=[dbdictionary.client_id, dbdictionary.object_id])
        dictionary.dbObject = dbdictionary
        return DeleteDictionaryRoles(dictionary=dictionary, triumph=True)



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
        id = LingvodocID(required=True)

    dictionary = graphene.Field(Dictionary)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('delete', 'dictionary')
    def mutate(root, info, **args):
        ids = args.get('id')
        client_id, object_id = ids
        dbdictionary_obj = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not dbdictionary_obj or dbdictionary_obj.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")
        del_object(dbdictionary_obj)
        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj
        return DeleteDictionary(dictionary=dictionary, triumph=True)


