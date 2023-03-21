import graphene
from lingvodoc.schema.gql_holders import (
    IdHolder,
    Name,
    fetch_object,
    client_id_check, ResponseError, LingvodocID)
from lingvodoc.models import (
    DBSession,
    BaseGroup as dbBaseGroup,
    Group as dbGroup,
    User as dbUser,
    Client as dbClient)
from lingvodoc.schema.gql_holders import (
    LingvodocObjectType,
    CreatedAt,
)

from lingvodoc.schema.gql_user import User
from lingvodoc.utils.creation import add_user_to_group


class BaseGroup(LingvodocObjectType):  # tested
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL
     #dictionary_default  | boolean                     | NOT NULL
     #perspective_default | boolean                     | NOT NULL
     #name                | text                        | NOT NULL
     #subject             | text                        | NOT NULL
     #action              | text                        | NOT NULL

    query myQuery {
      all_basegroups {
        id
        created_at
        action
        name
        subject
        dictionary_default
        perspective_default
      }
    }

    """
    dbType = dbBaseGroup

    perspective_default = graphene.Boolean()
    dictionary_default = graphene.Boolean()
    subject = graphene.String()
    action = graphene.String()
    name = graphene.String()



    class Meta:
        interfaces = (IdHolder, CreatedAt, Name)

    @fetch_object("perspective_default")
    def resolve_perspective_default(self, info):
        return self.dbObject.perspective_default


    @fetch_object("dictionary_default")
    def resolve_dictionary_default(self, info):
        return self.dbObject.dictionary_default


    @fetch_object("subject")
    def resolve_subject(self, info):
        return self.dbObject.subject


    @fetch_object("action")
    def resolve_action(self, info):
        return self.dbObject.action



# Create
class CreateBasegroup(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        subject = graphene.String(required=True)
        action = graphene.String(required=True)

    # Result object

    triumph = graphene.Boolean()
    basegroup = graphene.Field(BaseGroup)
    """
    example:
    mutation awd{
        create_basegroup(name:"Can use master of etymologies" subject:"master of etymologies", action:"use"){
            basegroup{
                subject
                action
                id
            }
            triumph
        }
        
    }
    """

    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        name = args.get('name')
        subject = args.get('subject')
        action = args.get('action')
        client_id = info.context.get('client_id')
        user = dbClient.get_user_by_client_id(client_id)
        if user.id != "1":
            raise ResponseError(message="Permission Denied")
        name_exists = DBSession.query(dbBaseGroup).filter(dbBaseGroup.name==name).first()
        if name_exists:
            raise ResponseError(message="Basegroup with such name already exists")

        # new basegroup_creation
        # TODO: create function
        db_new_basegroup = dbBaseGroup(name=name, subject=subject, action=action)
        DBSession.add(db_new_basegroup)
        DBSession.flush()


        gql_basegoup = BaseGroup()
        gql_basegoup.dbObject = db_new_basegroup
        return CreateBasegroup(triumph=True, basegroup=gql_basegoup)


class AddUserToBasegroup(graphene.Mutation):
    class Arguments:
        user_id = graphene.Int(required=True)
        basegroup_name = graphene.String(required=True)

    # Result object

    triumph = graphene.Boolean()
    basegroup = graphene.Field(BaseGroup)
    user = graphene.Field(User)
    """
    example:
    mutation awd{
        create_basegroup(name:"Can use master of etymologies" subject:"master of etymologies", action:"use"){
            basegroup{
                subject
                action
                id
            }
            triumph
        }

    }
    """


    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        user_id = args.get('user_id')
        basegroup_name = args.get('basegroup_name')
        client_id = info.context.get('client_id')
        req_user = dbClient.get_user_by_client_id(client_id)
        if req_user.id != "1":
            raise ResponseError(message="Permission Denied")

        db_user = DBSession.query(dbUser).filter(dbUser.id==user_id).first()
        db_basegroup = DBSession.query(dbBaseGroup).filter(dbBaseGroup.name == basegroup_name).first()
        if not db_basegroup:
            raise ResponseError(message="Basegroup with such name doesn`t exists")

        db_group = DBSession.query(dbGroup).filter_by(base_group_id=db_basegroup.id).first()
        if not db_group:
            db_group = dbGroup(parent=db_basegroup)
            DBSession.add(db_group)
        add_user_to_group(db_user, db_group)

        gql_basegroup = BaseGroup()
        gql_basegroup.dbObject = db_basegroup

        gql_user = User()
        gql_user.dbObject = db_user

        return AddUserToBasegroup(triumph=True, basegroup=gql_basegroup, user=gql_user)

