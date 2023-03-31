import graphene

from lingvodoc.models import (
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Client,
    Group as dbGroup,
    Grant as dbGrant,
    Organization as dbOrganization,
    Dictionary as dbDictionary,
    DBSession
)

from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    IdHolder,
    AdditionalMetadata,
    CreatedAt,
    TypeHolder,
    JSONString
)

from lingvodoc.models import (
    UserRequest as dbUserRequest,
)

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

from uuid import uuid4
from sqlalchemy.orm.attributes import flag_modified

from sqlalchemy import (
    func,
    tuple_,
    case
)

from lingvodoc.cache.caching import CACHE

class Subject(graphene.ObjectType):
    """
    graphene object that have all metadata attributes
    if new attributes of metadata are added, then this class has to be updated
    """
    grant_id = graphene.Int()
    user_id = graphene.String()
    org_id = graphene.Int()
    dictionary_id = LingvodocID()


class UserRequest(LingvodocObjectType): # show only
    """
     #id                  | bigint                      | NOT NULL DEFAULT nextval('userrequest_id_seq'::regclass)
     #sender_id           | bigint                      | NOT NULL
     #recipient_id        | bigint                      | NOT NULL
     #created_at          | timestamp without time zone | NOT NULL
     #broadcast_uuid      | character varying(36)       | NOT NULL
     #type                | character varying(1000)     | NOT NULL
     #message             | character varying(1000)     |
     #subject             | jsonb                       |
     #additional_metadata | jsonb                       |

        query myQuery {
          userrequest(id: 5) {
                id
						created_at
						type
						sender_id
						message recipient_id broadcast_uuid subject
           }
        }
    """
    dbType = dbUserRequest
    sender_id = graphene.Int()
    recipient_id = graphene.String()
    broadcast_uuid = graphene.String()
    message = graphene.String()
    # subject = JSONString()
    subject = graphene.Field(Subject)
    class Meta:
        interfaces = (IdHolder, AdditionalMetadata, CreatedAt, TypeHolder)

    @fetch_object("sender_id")
    def resolve_sender_id(self, info):
        return self.dbObject.sender_id

    @fetch_object("recipient_id")
    def resolve_recipient_id(self, info):
        return self.dbObject.recipient_id

    @fetch_object("broadcast_uuid")
    def resolve_broadcast_uuid(self, info):
        return self.dbObject.broadcast_uuid

    @fetch_object("message")
    def resolve_message(self, info):
        return self.dbObject.message



    @fetch_object()
    def resolve_subject(self, info):
        db_object = self.dbObject

        # initializes dict with None, for keys nonexistent in dbObject.additional_metadata
        # list of keys is taken from Metadata attributes
        subject_dict = {i: None for i in Subject().__class__.__dict__ if not i.startswith("_")}

        if db_object.subject:
            new_meta = {key: db_object.subject[key] for key in db_object.subject if key in subject_dict}
            subject_dict.update(new_meta)
        if 'client_id' in db_object.subject and 'object_id' in db_object.subject:
            subject_dict['dictionary_id'] = [db_object.subject['client_id'], db_object.subject['object_id']]
        if 'user_id' in db_object.subject and db_object.subject['user_id'] is not None:
            subject_dict['user_id'] = str(db_object.subject['user_id'])
        subject_object = Subject(**subject_dict)
        return subject_object

    # @fetch_object("subject")
    # def resolve_subject(self, info):
    #     return self.dbObject.subject
    # def data_type(self):
    #     return DBSession.query(TranslationAtom.content).filter_by(
    #     parent_client_id=self.data_type_translation_gist_client_id,
    #     parent_object_id=self.data_type_translation_gist_object_id,
    #     locale_id=2).scalar()

class AcceptUserRequest(graphene.Mutation):
    """
    mutation {
       accept_userrequest(id: 6, accept: true) {
          triumph
        }
    }
    """
    class Arguments:
        id = graphene.Int(required=True)
        accept = graphene.Boolean(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        userrequest_id = args.get('id')

        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        if not client:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        recipient_id = user.id

        userrequest = DBSession.query(dbUserRequest).filter_by(id=userrequest_id, recipient_id=recipient_id).first()
        if userrequest:
            accept = args.get('accept')
            if accept is True:
                if userrequest.type == 'grant_permission':
                    grant = DBSession.query(dbGrant).filter_by(id=userrequest.subject['grant_id']).first()
                    if grant.owners is None:
                        grant.owners = list()
                    user = DBSession.query(dbUser).filter_by(id=userrequest.subject['user_id']).one()
                    if userrequest.subject['user_id'] not in grant.owners:
                        grant.owners.append(userrequest.subject['user_id'])
                        flag_modified(grant, 'owners')
                    if grant.additional_metadata is not None and grant.additional_metadata.get('roles'):
                        for role in grant.additional_metadata['roles']:
                            group = DBSession.query(dbGroup).filter_by(id=role).one()
                            if user not in group.users:
                                group.users.append(user)

                elif userrequest.type == 'add_dict_to_grant':
                    grant = DBSession.query(dbGrant).filter_by(id=userrequest.subject['grant_id']).first()
                    if grant.additional_metadata is None:
                        grant.additional_metadata = dict()
                    if grant.additional_metadata.get('participant') is None:
                        grant.additional_metadata['participant'] = list()

                    # dict_ids = {'client_id': userrequest.subject['dictionary_id'][0],
                    #             'object_id': userrequest.subject['dictionary_id'][1]}

                    dict_ids = {'client_id': userrequest.subject['client_id'],
                                'object_id': userrequest.subject['object_id']}
                    # Seems like must be cached, but current caching model doesn't support it
                    cur_dict = DBSession.query(dbDictionary).filter_by(client_id=dict_ids['client_id'],
                                                                     object_id=dict_ids['object_id'],
                                                                       marked_for_deletion=False).first()
                    if not cur_dict:
                        raise ResponseError('such dictionary doesn\'t exist')

                    if dict_ids not in grant.additional_metadata['participant']:
                        grant.additional_metadata['participant'].append(dict_ids)

                    subject_id_list = [
                        (cur_dict.client_id, cur_dict.object_id)]

                    for persp in cur_dict.dictionaryperspective:

                        subject_id_list.append(
                            (persp.client_id, persp.object_id))

                    grant_admins = DBSession.query(dbUser).filter(dbUser.id.in_(grant.owners))
                    if grant.additional_metadata is None:
                        grant.additional_metadata = dict()
                    if grant.additional_metadata.get('roles', None) is None:
                        grant.additional_metadata['roles'] = list()

                    # All permissions for the dictionary and its perspectives.

                    perm_groups = (

                        DBSession.query(dbGroup)

                            .filter(
                                tuple_(dbGroup.subject_client_id, dbGroup.subject_object_id)
                                    .in_(subject_id_list))

                            .all())

                    # Adding all permissions to the grant and granting all permissions to the grant's
                    # admins.
                    #
                    # Roles list can be quite lengthy, more then 1000 items in one case, and we can have up
                    # to 32 and more permission groups for a standard dictionary with 2 perspectives, so we
                    # check role incidence efficiently using a set.

                    role_set = (
                        set(grant.additional_metadata['roles']))

                    for group in perm_groups:

                        if group.id not in role_set:
                            grant.additional_metadata['roles'].append(group.id)

                        for admin in grant_admins:
                            if group not in admin.groups:
                                admin.groups.append(group)

                    flag_modified(grant, 'additional_metadata')

                elif userrequest.type == 'participate_org':
                    DBSession.execute("LOCK TABLE user_to_organization_association IN EXCLUSIVE MODE;")
                    org_id = userrequest.subject['org_id']
                    user_id = userrequest.subject['user_id']
                    organization = DBSession.query(dbOrganization).filter_by(id=org_id).first()
                    user = DBSession.query(dbUser).filter_by(id=user_id).first()
                    if user not in organization.users:
                        if not user in organization.users:
                            organization.users.append(user)

                elif userrequest.type == 'administrate_org':
                    org_id = userrequest.subject['org_id']
                    user_id = userrequest.subject['user_id']
                    organization = DBSession.query(dbOrganization).filter_by(id=org_id).first()
                    if organization.additional_metadata is None:
                        organization.additional_metadata = dict()
                    if organization.additional_metadata.get('admins') is None:
                        organization.additional_metadata['admins'] = list()
                    old_meta = organization.additional_metadata
                    old_admins_list = old_meta['admins']
                    old_authors_list = [str(i) for i in old_admins_list]
                    organization.update_additional_metadata(
                        {'admins': old_authors_list})
                    organization.additional_metadata['admins'].append(str(user_id))
                    flag_modified(organization, 'additional_metadata')

                # Adding dictionary to organization.

                elif userrequest.type == 'add_dict_to_org':

                    dict_id = (
                        userrequest.subject['client_id'],
                        userrequest.subject['object_id'])

                    org_id = userrequest.subject['org_id']

                    # dictionary = (
                    #     DBSession.query(dbDictionary).filter_by(
                    #         client_id = dict_id[0],
                    #         object_id = dict_id[1]).first())
                    dictionary = CACHE.get(objects =
                        {
                            dbDictionary : (dict_id, )
                        },
                    DBSession=DBSession)

                    if not dictionary:
                        raise ResponseError('No such dictionary.')

                    elif dictionary.marked_for_deletion:
                        raise ResponseError('Dictionary is deleted.')

                    organization = (
                        DBSession.query(dbOrganization).filter_by(
                            id = org_id).first())

                    if not organization:
                        raise ResponseError('No such organization.')

                    dict_item = {
                        'client_id': dict_id[0],
                        'object_id': dict_id[1]}

                    if organization.additional_metadata is None:

                        organization.additional_metadata = {
                            'participant': [dict_item]}

                    elif 'participant' not in organization.additional_metadata:
                        organization.additional_metadata['participant'] = [dict_item]

                    else:
                        organization.additional_metadata['participant'].append(dict_item)

                    flag_modified(organization, 'additional_metadata')

                else:

                    raise ResponseError(
                        'Unknown request type \'{}\'.'.format(
                            userrequest.type))

                broadcast_uuid = userrequest.broadcast_uuid
                family = DBSession.query(dbUserRequest).filter_by(id=userrequest_id, broadcast_uuid=broadcast_uuid).all()
                for userreq in family:
                    DBSession.delete(userreq)

            else:
                DBSession.delete(userrequest)

            return AcceptUserRequest(triumph=True)
        raise ResponseError(message="No such userrequest in the system")


def create_one_userrequest(request):

    userrequest = dbUserRequest(**request)

    DBSession.add(userrequest)
    DBSession.flush()

    return userrequest


class CreateGrantPermission(graphene.Mutation):
    """
    mutation {
        create_grant_permission(grant_id: 2) {
            triumph
        }
    }
    """
    class Arguments:
        grant_id = graphene.Int(required=True)

    #userrequest = graphene.Field(UserRequest)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        if not client:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()

        user_id = user.id
        grant_id = int(args.get('grant_id'))

        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'grant_permission'
        req['subject'] = {'grant_id': grant_id, 'user_id': str(user_id)}
        req['message'] = ''
        if DBSession.query(dbUserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            raise ResponseError(message="Request already exists")

        grantadmins = list()
        group = DBSession.query(dbGroup).join(dbBaseGroup).filter(dbBaseGroup.subject == 'grant',
                                                              dbGroup.subject_override == True,
                                                              dbBaseGroup.action == 'approve').one()

        for user in group.users:
            if user not in grantadmins:
                grantadmins.append(user)

        if not grantadmins:
            raise ResponseError("No administrators")

        for grantadmin in grantadmins:
            req['recipient_id'] = grantadmin.id
            create_one_userrequest(req)

        return CreateGrantPermission(triumph=True)

class AddDictionaryToGrant(graphene.Mutation):
    """
    mutation  {
        add_dictionary_to_grant(dictionary_id:[69,4], grant_id:1) {
            triumph
        }
    }

    answer:
    {
        "data": {
            "add_dictionary_to_grant": {
                "triumph": true
            }
        }
    }
    """
    class Arguments:
        dictionary_id = LingvodocID(required=True)
        grant_id = graphene.Int(required=True)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        dictionary_id = args.get("dictionary_id")
        grant_id = args.get("grant_id")
        context_client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=context_client_id).first()

        if not client:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        client_id, object_id = dictionary_id
        user_id = user.id
        # request_json = {"dictionary_id": [client_id, object_id], "grant_id": grant_id}
        request_json = {"client_id": client_id, "object_id": object_id, "grant_id": grant_id}
        req = dict()
        req['sender_id'] = str(user_id)
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'add_dict_to_grant'
        req['subject'] = request_json
        req['message'] = ''
        info.context.acl_check('edit', 'dictionary',
                               (client_id,object_id))
        cur_dict = DBSession.query(dbDictionary).filter_by(client_id=client_id,
                                                         object_id=object_id,
                                                           marked_for_deletion=False).first()
        if not cur_dict:
            raise ResponseError('such dictionary doesn\'t exist')
        if DBSession.query(dbUserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            raise ResponseError(message="Request already exists")


        grant = DBSession.query(dbGrant).filter_by(id=grant_id).first()
        grantadmins = grant.owners
        if not grantadmins:
            raise ResponseError(message="No administrators")

        for grantadmin in grantadmins:
            req['recipient_id'] = grantadmin
            create_one_userrequest(req)

        return AddDictionaryToGrant(triumph=True)

class AdministrateOrg(graphene.Mutation):
    """
    mutation  {
        administrate_org(org_id: 1) {
            triumph
        }
    }
    """
    class Arguments:
        org_id = graphene.Int(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        if not client:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()

        user_id = user.id
        org_id = args.get('org_id')
        req = dict()
        req['sender_id'] = str(user_id)
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'administrate_org'
        req['subject'] = {'org_id': org_id, 'user_id': str(user_id)}
        req['message'] = ''
        if DBSession.query(dbUserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            raise ResponseError(message="Request already exists")

        orgadmins = list()
        group = DBSession.query(dbGroup).join(dbBaseGroup).filter(dbBaseGroup.subject == 'organization',
                                                              dbGroup.subject_override == True,
                                                              dbBaseGroup.action == 'approve').one()

        for user in group.users:
            if user not in orgadmins:
                orgadmins.append(user)
        if not orgadmins:
            raise ResponseError(message="No administrators")
        for orgadmin in orgadmins:
            req['recipient_id'] = orgadmin.id
            create_one_userrequest(req)

        return AdministrateOrg(triumph=True)

class ParticipateOrg(graphene.Mutation):
    """
    mutation  {
        participate_org(org_id: 1) {
            triumph
        }
    }
    """
    class Arguments:
        org_id = graphene.Int(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        if not client:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()

        user_id = user.id
        org_id = args.get('org_id')
        req = dict()
        req['sender_id'] = str(user_id)
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'participate_org'
        req['subject'] = {'org_id': org_id, 'user_id': str(user_id)}
        req['message'] = ''
        if DBSession.query(dbUserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            raise ResponseError(message="Request already exists")

        orgadmins = list()
        org = DBSession.query(dbOrganization).filter_by(id=org_id).first()

        if org.additional_metadata:
            orgadmins = list(map(str,org.additional_metadata.get('admins', ['1'])))

        # If the org does not have any administrators, we'll send the request to the main administrator
        # user.

        for orgadmin in orgadmins:
            req['recipient_id'] = orgadmin
            create_one_userrequest(req)

        return ParticipateOrg(triumph=True)

class AddDictionaryToOrganization(graphene.Mutation):
    """
    mutation  {
        add_dictionary_to_organization(dictionary_id: [657, 3], organization_id: 1) {
            triumph
        }
    }
    """

    class Arguments:
        dictionary_id = LingvodocID(required=True)
        organization_id = graphene.Int(required=True)

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):

        client_id = info.context.get('client_id')

        dictionary_id = args.get('dictionary_id')
        organization_id = args.get('organization_id')

        client = (
            DBSession
                .query(Client)
                .filter_by(id = client_id)
                .first())

        if not client:
            raise ResponseError('This client id is orphaned. Try to logout and then login once more.')

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()

        request = {
            'broadcast_uuid': str(uuid4()),
            'message': '',
            'sender_id': user.id,
            'subject': {
                'client_id': dictionary_id[0],
                'object_id': dictionary_id[1],
                'org_id': organization_id},
            'type': 'add_dict_to_org'}

        info.context.acl_check('edit', 'dictionary', dictionary_id)

        # dictionary = (
        #     DBSession.query(dbDictionary).filter_by(
        #         client_id = dictionary_id[0],
        #         object_id = dictionary_id[1]).first())
        dictionary = CACHE.get(objects =
            {
                dbDictionary : (args["dictionary_id"], )
            },
        DBSession=DBSession)
        if not dictionary:
            raise ResponseError('No such dictionary.')

        elif dictionary.marked_for_deletion:
            raise ResponseError('Dictionary is deleted.')

        if DBSession.query(dbUserRequest).filter_by(
            type = request['type'],
            subject = request['subject'],
            message = request['message']).first():

            raise ResponseError('Request already exists.')

        organization = (
            DBSession.query(dbOrganization).filter_by(
                id = organization_id).first())

        if not organization:
            raise ResponseError('No such organization.')

        admin_list = []

        if organization.additional_metadata:
            admin_list = list(map(str,organization.additional_metadata.get('admins', ['1'])))

        # If the organization does not have any administrators, we'll send the request to the main
        # administrator user.

        for user_id in admin_list:
            request['recipient_id'] = user_id
            create_one_userrequest(request)

        return AddDictionaryToOrganization(triumph = True)

# class DeleteUserRequest(graphene.Mutation):
#     """
#     mutation {
#         delete_userrequest(id: 7) {
#             triumph
#         }
#     }
#
#     """
#     class Arguments:
#         id = graphene.Int()
#
#     triumph = graphene.Boolean()
#
#     @staticmethod
#     def mutate(root, info, **args):
#         userrequest_id = args.get('id')
#         userrequest = DBSession.query(dbUserRequest).filter_by(id=userrequest_id).first()
#         if userrequest:
#             DBSession.delete(userrequest)
#             return DeleteUserRequest(triumph=True)
#         raise ResponseError(message="No such userrequest in the system")
