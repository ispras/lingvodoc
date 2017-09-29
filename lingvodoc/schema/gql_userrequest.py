import graphene

from lingvodoc.models import (
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Client,
    Group as dbGroup,
    Grant as dbGrant,
    Organization as dbOrganization,
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
    class Arguments:
        grant_id = graphene.Int()

    #userrequest = graphene.Field(UserRequest)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
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
    class Arguments:
        request_json = ObjectVal()

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
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
    class Arguments:
        org_id = graphene.Int()

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
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
    class Arguments:
        org_id = graphene.Int()

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
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
