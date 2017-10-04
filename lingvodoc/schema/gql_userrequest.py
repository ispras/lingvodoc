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
    acl_check_by_id
)

from uuid import uuid4
from sqlalchemy.orm.attributes import flag_modified

from sqlalchemy import (
    func,
    tuple_,
    case
)

class UserRequest(graphene.ObjectType): # show only
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
    """
    dbType = dbUserRequest
    dbObject = None
    sender_id = graphene.Int()
    recipient_id = graphene.Int()
    broadcast_uuid = graphene.String()
    message = graphene.String()
    subject = JSONString()
    class Meta:
        interfaces = (IdHolder, AdditionalMetadata, CreatedAt, TypeHolder)
    pass

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
        id = graphene.Int()
        accept = graphene.Boolean()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        userrequest_id = args.get('id')
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")
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

                    dict_ids = {'client_id': userrequest.subject['client_id'],
                                'object_id': userrequest.subject['object_id']}

                    no_grants = True
                    for tmp_grant in DBSession.query(dbGrant).all():
                        if tmp_grant.additional_metadata and tmp_grant.additional_metadata.get(
                                'participant') and dict_ids in \
                                tmp_grant.additional_metadata['participant']:
                            no_grants = False
                            break

                    if dict_ids not in grant.additional_metadata['participant']:
                        grant.additional_metadata['participant'].append(dict_ids)

                    state_group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
                        dbGroup.subject_client_id == dict_ids['client_id'],
                        dbGroup.subject_object_id == dict_ids['object_id'],
                        dbBaseGroup.subject == 'dictionary_status',
                        dbBaseGroup.action == 'edit'
                    ).first()
                    approve_groups = list()
                    cur_dict = DBSession.query(dbDictionary).filter_by(client_id=dict_ids['client_id'],
                                                                     object_id=dict_ids['object_id']).first()
                    persp_ids = list()
                    for persp in cur_dict.dictionaryperspective:
                        persp_ids.append((persp.client_id, persp.object_id))
                        approve_group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
                            dbGroup.subject_client_id == persp.client_id,
                            dbGroup.subject_object_id == persp.object_id,
                            dbBaseGroup.subject == 'perspective_status',
                            dbBaseGroup.action == 'edit'
                        ).first()

                        if approve_group:
                            approve_groups.append(approve_group)
                        approve_group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
                            dbGroup.subject_client_id == persp.client_id,
                            dbGroup.subject_object_id == persp.object_id,
                            dbBaseGroup.subject == 'approve_entities',
                            dbBaseGroup.action == 'create'
                        ).first()
                        if approve_group:
                            approve_groups.append(approve_group)
                        approve_group = DBSession.query(dbGroup).join(dbBaseGroup).filter(
                            dbGroup.subject_client_id == persp.client_id,
                            dbGroup.subject_object_id == persp.object_id,
                            dbBaseGroup.subject == 'approve_entities',
                            dbBaseGroup.action == 'delete'
                        ).first()
                        if approve_group:
                            approve_groups.append(approve_group)

                    grant_admins = DBSession.query(dbUser).filter(dbUser.id.in_(grant.owners))
                    if grant.additional_metadata is None:
                        grant.additional_metadata = dict()
                    if grant.additional_metadata.get('roles', None) is None:
                        grant.additional_metadata['roles'] = list()
                    for admin in grant_admins:
                        perm_groups = DBSession.query(dbGroup).filter_by(subject_client_id=cur_dict.client_id,
                                                                       subject_object_id=cur_dict.object_id).all()
                        for group in perm_groups:
                            if group.id not in grant.additional_metadata['roles']:
                                grant.additional_metadata['roles'].append(group.id)
                            if group not in admin.groups:
                                admin.groups.append(group)
                        perm_groups = DBSession.query(dbGroup).filter(
                            tuple_(dbGroup.subject_client_id, dbGroup.subject_object_id).in_(persp_ids)).all()
                        for group in perm_groups:
                            if group.id not in grant.additional_metadata['roles']:
                                grant.additional_metadata['roles'].append(group.id)
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
                    user = DBSession.query(dbUser).filter_by(id=user_id).first()
                    if organization.additional_metadata is None:
                        organization.additional_metadata = dict()
                    if organization.additional_metadata.get('admins') is None:
                        organization.additional_metadata['admins'] = list()
                    organization.additional_metadata['admins'].append(user_id)
                else:
                    pass

                broadcast_uuid = userrequest.broadcast_uuid
                family = DBSession.query(dbUserRequest).filter_by(id=userrequest_id, broadcast_uuid=broadcast_uuid).all()
                for userreq in family:
                    DBSession.delete(userreq)

            else:
                DBSession.delete(userrequest)

            return AcceptUserRequest(triumph=True)
        raise ResponseError(message="No such userrequest in the system")



def create_one_userrequest(req, client_id):
    sender_id = req['sender_id']
    recipient_id = req['recipient_id']
    broadcast_uuid = req['broadcast_uuid']  # generate it
    type = req['type']
    subject = req['subject']
    message = req['message']
    client = DBSession.query(Client).filter_by(id=client_id).first()

    if not client:
        raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                       client_id)
    user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
    if not user:
        raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

    userrequest = dbUserRequest(sender_id=sender_id,
                              recipient_id=recipient_id,
                              broadcast_uuid=broadcast_uuid,
                              type=type,
                              subject=subject,
                              message=message
                              )
    DBSession.add(userrequest)
    DBSession.flush()
    return userrequest.id

class CreateGrantPermission(graphene.Mutation):
    """
    mutation {
        create_grant_permission(grant_id: 2) {
            triumph
        }
    }
    """
    class Arguments:
        grant_id = graphene.Int()

    #userrequest = graphene.Field(UserRequest)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user_id = user.id
        grant_id = int(args.get('grant_id'))

        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'grant_permission'
        req['subject'] = {'grant_id': grant_id, 'user_id': user_id}
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
            create_one_userrequest(req, client_id)

        return CreateGrantPermission(triumph=True)

class AddDictionaryToGrant(graphene.Mutation):
    """
    mutation  {
        add_dictionary_to_grant(request_json: {grant_id: 2, user_id: 21}) {
            triumph
        }
    }
    """
    class Arguments:
        request_json = ObjectVal()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user_id = user.id
        request_json = args.get('request_json')
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'add_dict_to_grant'
        req['subject'] = request_json
        req['message'] = ''
        if DBSession.query(dbUserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            raise ResponseError(message="Request already exists")


        grant = DBSession.query(dbGrant).filter_by(id=request_json['grant_id']).first()
        grantadmins = grant.owners
        if not grantadmins:
            raise ResponseError(message="No administrators")

        for grantadmin in grantadmins:
            req['recipient_id'] = grantadmin
            req_id = create_one_userrequest(req, client_id)

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
        org_id = graphene.Int()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user_id = user.id
        org_id = args.get('org_id')
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'administrate_org'
        req['subject'] = {'org_id': org_id, 'user_id': user_id}
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
            req_id = create_one_userrequest(req, client_id)

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
        org_id = graphene.Int()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        client_id = info.context.get('client_id')
        client = DBSession.query(Client).filter_by(id=client_id).first()

        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        user_id = user.id
        org_id = args.get('org_id')
        req = dict()
        req['sender_id'] = user_id
        req['broadcast_uuid'] = str(uuid4())
        req['type'] = 'administrate_org'
        req['subject'] = {'org_id': org_id, 'user_id': user_id}
        req['message'] = ''
        if DBSession.query(dbUserRequest).filter_by(type=req['type'], subject=req['subject'],
                                                  message=req['message']).first():
            raise ResponseError(message="Request already exists")

        orgadmins = list()
        org = DBSession.query(dbOrganization).filter_by(id=org_id).first()
        if not org.additional_metadata:
            raise ResponseError(message="No administrators")

        orgadmins = org.additional_metadata.get('admins')

        if not orgadmins:
            raise ResponseError(message="No administrators")

        for orgadmin in org.additional_metadata['admins']:
            req['recipient_id'] = orgadmin
            req_id = create_one_userrequest(req, client_id)

        return ParticipateOrg(triumph=True)

class DeleteUserRequest(graphene.Mutation):
    """
    mutation {
        delete_userrequest(id: 7) {
            triumph
        }
    }

    """
    class Arguments:
        id = graphene.Int()

    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        userrequest_id = args.get('id')
        userrequest = DBSession.query(dbUserRequest).filter_by(id=userrequest_id).first()
        if userrequest:
            DBSession.delete(userrequest)
            return DeleteUserRequest(triumph=True)
        raise ResponseError(message="No such userrequest in the system")
