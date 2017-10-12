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

from lingvodoc.views.v2.utils import (
    update_metadata,
    cache_clients)

from lingvodoc.schema.gql_holders import (
    CommonFieldsComposite,
    StateHolder,
    TranslationHolder,
    fetch_object,
    del_object,
    client_id_check,
    ResponseError,
    ObjectVal,
    acl_check_by_id,
    LingvodocID
)

from lingvodoc.views.v2.utils import  add_user_to_group
from lingvodoc.utils import statistics
from lingvodoc.utils.creation import (create_perspective,
                                      create_dbdictionary,
                                      create_dictionary_persp_to_field)

class UserAndOrganizationsRoles(graphene.ObjectType):
    roles_users = graphene.List(graphene.String)
    roles_organizations = graphene.List(graphene.String)

    def resolve_roles_users(self, info):
        return self.roles_users

    def resolve_roles_organizations(self, info):
        return self.roles_organizations

class Dictionary(graphene.ObjectType):  # tested
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
    dbObject = None
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
            raise ResponseError(message="Time error")
        locale_id = info.context.get('locale_id')
        return statistics.stat_dictionary((self.dbObject.client_id, self.dbObject.object_id),
                                   starting_time,
                                   ending_time,
                                   locale_id=locale_id
                                   )
    @client_id_check()
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
        response = dict()
        client_id, object_id = self.dbObject.client_id, self.dbObject.object_id
        dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not dictionary or dictionary.marked_for_deletion:
            raise ResponseError(message="Dictionary with such ID doesn`t exists in the system")


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
					"fake_id": "123",
					"self_fake_id": "321",
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
        id = LingvodocID()
        translation_gist_id = LingvodocID()
        parent_id = LingvodocID(required=True)
        additional_metadata = ObjectVal()
        perspectives = graphene.List(ObjectVal)
        translation_atoms = graphene.List(ObjectVal)

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
        if fake_id in fake_to_id:
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
        if type(tr_atoms) is not list:  # TODO: look at this
            if not translation_gist_id:
                raise ResponseError(message="translation_gist_id arg not found")
        else:
            client = DBSession.query(dbClient).filter_by(id=client_id).first()

            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            dbtranslationgist = dbTranslationGist(client_id=client_id, object_id=object_id, type="Language")
            DBSession.add(dbtranslationgist)
            DBSession.flush()
            translation_gist_client_id = dbtranslationgist.client_id
            translation_gist_object_id = dbtranslationgist.object_id
            translation_gist_id = [translation_gist_client_id, translation_gist_object_id]
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

        id = [client_id, object_id]
        dbdictionary_obj = create_dbdictionary(id=id,
                                               parent_id=parent_id,
                                               translation_gist_id=translation_gist_id,
                                               additional_metadata=additional_metadata)
        dictionary = Dictionary(id=[dbdictionary_obj.client_id, dbdictionary_obj.object_id])
        dictionary.dbObject = dbdictionary_obj

        persp_args = args.get("perspectives")
        created_persps = []
        # TODO:  rename it
        persp_fake_ids = dict()
        field_fake_ids = dict()
        persp_fields_list = defaultdict(list)
        if persp_args:
            for next_persp in persp_args:

                if "translation_atoms" in next_persp:
                    client = DBSession.query(dbClient).filter_by(id=client_id).first()
                    user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
                    atoms_to_create = next_persp["translation_atoms"]
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
                                                                  object_id=None,
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
                    if "translation_gist_id" in next_persp:
                        persp_translation_gist_id = next_persp["translation_gist_id"]
                    else:
                        ResponseError(message="Translation gist not found")

                parent_id = [dbdictionary_obj.client_id, dbdictionary_obj.object_id]
                new_persp = create_perspective(id=(client_id, None),
                                        parent_id=parent_id,  # use all object attrs
                                        translation_gist_id=persp_translation_gist_id
                                        )
                field_info = CreateDictionary.FieldInfo(perspective_obj=new_persp)
                if "fake_id" in next_persp:
                    perspective_fake_id = next_persp['fake_id']
                    persp_fake_ids[perspective_fake_id] = new_persp

                if "fields" in next_persp:
                    new_fields = next_persp["fields"]
                    for new_ptofield in new_fields:
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
                    self_id = field.self_fake_id
                    field_id = field.field_id
                    fake_id = field.fake_id
                    parent_id = (persp.client_id, persp.object_id)
                    if link_id:
                        persp_to_link = CreateDictionary.get_by_fake_id(persp_fake_ids, link_id)
                        link_id=(persp_to_link.client_id, persp_to_link.object_id)
                    if self_id:
                        self_id = CreateDictionary.get_by_fake_id(field_fake_ids, self_id)
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
                          additional_metadata=None
                          ):
        if not ids:
            raise ResponseError(message="dict id not found")
        client_id, object_id = ids
        db_dictionary = DBSession.query(dbDictionary).filter_by(client_id=client_id, object_id=object_id).first()
        if not db_dictionary or db_dictionary.marked_for_deletion:
            raise ResponseError(message="Error: No such dictionary in the system")

        if parent_id:
            db_dictionary.parent_client_id, db_dictionary.parent_object_id = parent_id
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

class UpdateDictionaryRoles(graphene.Mutation):
    class Arguments:
        id = LingvodocID(required=True)
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


