import graphene
from lingvodoc.schema.gql_holders import (CreatedAt,
    IdHolder,
    MarkedForDeletion,
    AdditionalMetadata,
    Name,
    About,
    del_object,
    acl_check_by_id,
    ResponseError,
    LingvodocID
)
from lingvodoc.models import (
    Organization as dbOrganization,
    Client,
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    DBSession
)
from lingvodoc.views.v2.utils import add_user_to_group

class Organization(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL DEFAULT nextval('organization_id_seq'::regclass)
     #marked_for_deletion | boolean                     | NOT NULL
     #name                | text                        |
     #about               | text                        |
     #additional_metadata | jsonb                       |
    """
    dbType = dbOrganization
    dbObject = None
    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                      MarkedForDeletion,
                      AdditionalMetadata,
                      Name,
                      About
                    )
    pass

class CreateOrganization(graphene.Mutation):
    """
    example:
    mutation  {
        create_organization(name: "new", about: "about") {
            organization {
                name
            }
            triumph
        }
    }

    (this example works)
    return:
    {
      "create_organization": {
        "field": {
          "name": "new"
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        name = graphene.String()
        about = graphene.String()

    organization = graphene.Field(Organization)
    triumph = graphene.Boolean()

    @staticmethod
    #@acl_check_by_id('create', 'organization')
    def mutate(root, info, **args):
        name = args.get('name')
        about = args.get('about')

        client_id = info.context["client_id"]
        client = DBSession.query(Client).filter_by(id=client_id).first()
        if not client:
            raise ResponseError(message="Invalid client id (not registered on server). Try to logout and then login.")
        user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not user:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")

        dborganization = dbOrganization(name=name,
                                    about=about)
        if user not in dborganization.users:
            dborganization.users.append(user)
        DBSession.add(dborganization)
        DBSession.flush()

        bases = DBSession.query(dbBaseGroup).filter_by(subject='organization')
        for base in bases:
            group = dbGroup(parent=base, subject_object_id=dborganization.id)
            add_user_to_group(user, group)
            DBSession.add(group)

        DBSession.flush()
        organization = Organization(name=dborganization.name, about = dborganization.about, id = dborganization.id)
        organization.dbObject = dborganization
        return CreateOrganization(organization=organization, triumph=True)

class UpdateOrganization(graphene.Mutation):
    """
    example:
    mutation  {
        update_organization(organization_id: 6, name: "new2") {
            field {
                name,
                id,
                about
            }
            triumph
        }
    }
    (this example works)
    return:
    {
      "update_organization": {
        "field": {
          "name": "new2",
          "id": 6,
          "about": "about"
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        organization_id = graphene.Int()
        add_users = LingvodocID()
        delete_users = graphene.List(graphene.Int)  # TODO: LingvodocID()? (no)
        name = graphene.String()
        about = graphene.String()

    organization = graphene.Field(Organization)
    triumph = graphene.Boolean()

    @staticmethod
    @acl_check_by_id('edit', 'organization')
    def mutate(root, info, **args):
        organization_id = args.get('organization_id')
        dborganization = DBSession.query(dbOrganization).filter_by(id=organization_id).first()

        client_id = info.context["client_id"]
        client = DBSession.query(Client).filter_by(id=client_id).first()
        if not client:
            raise ResponseError(message="Invalid client id (not registered on server). Try to logout and then login.")

        creator = DBSession.query(dbUser).filter_by(id=client.user_id).first()
        if not creator:
            raise ResponseError(message="This client id is orphaned. Try to logout and then login once more.")
        if dborganization:
            if not dborganization.marked_for_deletion:
                add_users = args.get('add_users')
                if add_users:
                    for user_id in add_users:
                        user = DBSession.query(dbUser).filter_by(id=user_id).first()
                        if user not in dborganization.users:
                            if not user in dborganization.users:
                                dborganization.users.append(user)
                            bases = DBSession.query(dbBaseGroup).filter_by(subject='organization')
                            for base in bases:
                                group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                                         subject_object_id=dborganization.id).first()
                                add_user_to_group(user, group)
                delete_users = args.get('delete_users')
                if delete_users:
                    for user_id in delete_users:
                        if user_id == creator.id:
                            raise ResponseError(message="You shouldn't delete yourself")
                        user = DBSession.query(dbUser).filter_by(id=user_id).first()
                        if user in dborganization.users:
                            dborganization.users.remove(user)
                            bases = DBSession.query(dbBaseGroup).filter_by(subject='organization')
                            for base in bases:
                                group = DBSession.query(dbGroup).filter_by(base_group_id=base.id,
                                                                         subject_object_id=dborganization.id).first()
                                group.users.remove(user)
                name = args.get('name')
                if name:
                    dborganization.name = name

                about = args.get('about')
                if about:
                    dborganization.about = about

                organization = Organization(name=dborganization.name, about=dborganization.about, id=dborganization.id)
                organization.dbObject = dborganization
        return UpdateOrganization(organization=organization, triumph=True)


class DeleteOrganization(graphene.Mutation):
    """
    example:
    mutation  {
        delete_organization(organization_id: 6) {
            field {
                name,
                id,
                about
            }
            triumph
        }
    }

    (this example works)
    return:
    {
      "delete_organization": {
        "field": {
          "name": "new2",
          "id": 6,
          "about": "about"
        },
        "triumph": true
      }
    }
    """

    class Arguments:
        organization_id = graphene.Int()

    organization = graphene.Field(Organization)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        organization_id = args.get('organization_id')
        dborganization = DBSession.query(dbOrganization).filter_by(id=organization_id).first()
        if dborganization:
            if not dborganization.marked_for_deletion:
                del_object(dborganization)
                organization = Organization(name=dborganization.name, about=dborganization.about, id=dborganization.id)
                organization.dbObject = dborganization
                return DeleteOrganization(organization=organization, triumph=True)
        raise ResponseError(message="No such organization in the system")