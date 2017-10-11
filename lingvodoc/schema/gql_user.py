import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Client,
    Email as dbEmail,
    Group as dbGroup,
    Passhash,
    DBSession
)
from lingvodoc.views.v2.utils import add_user_to_group

from lingvodoc.schema.gql_holders import (
    IdHolder,
    CreatedAt,
    AdditionalMetadata,
    Name,
    fetch_object,
    client_id_check,
    acl_check_by_id,
    ResponseError
)

import datetime
from passlib.hash import bcrypt

class User(graphene.ObjectType):
    """
    created_at          | timestamp without time zone | NOT NULL
    id                  | bigint                      | NOT NULL DEFAULpserve --daemon ./postgres.ini startT nextval('user_id_seq'::regclass)
    default_locale_id   | bigint                      | NOT NULL
    birthday            | date                        |
    is_active           | boolean                     | NOT NULL
    login               | text                        | NOT NULL
    intl_name           | text                        | NOT NULL
    name                | text                        |
    additional_metadata | jsonb                       |
    """
    login = graphene.String()
    intl_name = graphene.String()
    default_locale_id = graphene.Int()
    birthday = graphene.String() # TODO: DateTime class
    is_active = graphene.Boolean() #boolean
    email = graphene.String()

    dbType = dbUser
    dbObject = None

    class Meta:
        interfaces = (IdHolder, CreatedAt, AdditionalMetadata, Name)
    @fetch_object("email")
    def resolve_email(self):
        return self.dbObject.email.email

    @fetch_object("login")
    def resolve_login(self, info):
        return self.dbObject.login

    @fetch_object("name")
    def resolve_name(self, info):
        return self.dbObject.name

    @fetch_object("intl_name")
    def resolve_intl_name(self, info):
        return self.dbObject.intl_name

    @fetch_object("default_locale_id")
    def resolve_default_locale_id(self, info):
        return self.dbObject.default_locale_id

    @fetch_object("birthday")
    def resolve_birthday(self, info):
        return self.dbObject.birthday

    @fetch_object("is_active")
    def resolve_is_active(self, info):
        return self.dbObject.is_active

    @fetch_object("created_at")
    def resolve_created_at(self, info):
        return self.dbObject.created_at

    @fetch_object("additional_metadata")
    def resolve_additional_metadata(self, info):
        return self.dbObject.additional_metadata


class CreateUser(graphene.Mutation):
    """
    example:
    mutation {
        create_user( login: "new", email: "n@mail.ru", name: "Новое имя", birthday: [1, 1, 1970], password: "secret") {
             field {
                login
                id
            }
            triumph
        }
    }

    (this example works)
    returns:

    {
      "create_user": {
        "field": {
          "login": "new",
          "id": 70
        },
        "triumph": true
      }
    }
    """
    class Arguments:
        login = graphene.String()
        email = graphene.String()
        name = graphene.String()
        birthday = graphene.Int()
        password = graphene.String()

    user = graphene.Field(User)
    triumph = graphene.Boolean()

    @staticmethod
    def mutate(root, info, **args):
        login = args.get('login')
        name = args.get('name')
        email = args.get('email')
        birthday = args.get('birthday')
        password = args.get('password')

        if not birthday:
            return ResponseError(message="Error: day, month or year of the birth is missing")

        if DBSession.query(dbUser).filter_by(login=login).first():
            return ResponseError(message="The user with this login is already registered")

        if DBSession.query(dbEmail).filter_by(email=email).first():
            return ResponseError(message="The user with this email is already registered")

        dbuser = dbUser(login=login,
                             name=name,
                             created_at=datetime.datetime.utcnow(),
                             intl_name=login,
                             birthday=birthday,
                             is_active=True
                             )
        pwd = Passhash(password=password)
        email = dbEmail(email=email)
        dbuser.password = pwd
        dbuser.email = email
        DBSession.add(dbuser)

        basegroups = []
        basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can create dictionaries").first()]
        basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can create languages").first()]
        basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can create organizations").first()]
        basegroups += [DBSession.query(dbBaseGroup).filter_by(name="Can create translation strings").first()]
        groups = []
        for base in basegroups:
            groups += [DBSession.query(dbGroup).filter_by(subject_override=True, base_group_id=base.id).first()]
        for group in groups:
            add_user_to_group(dbuser, group)
        DBSession.flush()

        user = User(login=dbuser.login, id = dbuser.id, is_active=True)
        user.dbObject = dbuser
        return CreateUser(user=user, triumph=True)

class UpdateUser(graphene.Mutation):
    """
    example:
    mutation {
        update_user(user_id: 70, name: "Измененное имя") {
             field {
                name
                id
                login
            }
            triumph
        }
    }
        (this example works)
    returns:

    {
      "update_user": {
        "field": {
          "name": "Измененное имя",
          "id": 70,
          "login": "new"
        },
        "triumph": true
      }
    }
    """
    class Arguments:
        #id = graphene.List(graphene.Int)
        client_id = graphene.Int()
        user_id = graphene.Int()
        new_password = graphene.String()
        old_password = graphene.String()
        name = graphene.String()
        default_locale_id = graphene.Int()
        birthday = graphene.String()
        email = graphene.String()
        about = graphene.String()

    user = graphene.Field(User)
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    @acl_check_by_id('edit', 'edit_user')
    def mutate(root, info, **args):
        #id = args.get('id')
        client_id = args.get('client_id')
        user_id = args.get('user_id')

        if client_id:
            client = DBSession.query(Client).filter_by(id=client_id).first()
            dbuser = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            user_id = client.user_id
            if not dbuser:
                return ResponseError(message="Error: No such user in the system")
        else:
            dbuser = DBSession.query(dbUser).filter_by(id=user_id).first()
            if not dbuser:
                return ResponseError(message="Error: No such user in the system")

        new_password = args.get('new_password')
        old_password = args.get('old_password')
        if new_password:
            if not old_password:
                return ResponseError(message="Error: Need old password to confirm")
            old_hash = DBSession.query(Passhash).filter_by(user_id=user_id).first()
            if old_hash:
                if not dbuser.check_password(old_password):
                    return ResponseError(message="Error: Wrong password")
                else:
                    old_hash.hash = bcrypt.encrypt(new_password)
            else:
                return ResponseError(message="Error: User has no password")

        name = args.get('name')
        if name:
            dbuser.name = name

        default_locale_id = args.get('default_locale_id')
        if default_locale_id:
            dbuser.default_locale_id = default_locale_id

        birthday = args.get('birthday')
        if birthday:
            year, month, day = birthday.split('-')
            dbuser.birthday = datetime.date(int(year), int(month), int(day))

        email = args.get('email')
        if email:
            if dbuser.email:
                dbuser.email.email = email
            else:
                new_email = dbEmail(user=dbuser, email=email)
                DBSession.add(new_email)
                DBSession.flush()

        about = args.get('about')
        if about:
            meta = dict()
            if dbuser.additional_metadata:
                meta = dbuser.additional_metadata
            meta['about'] = about
            dbuser.additional_metadata = meta

        user = User(login=dbuser.login, id=dbuser.id, name=dbuser.name)
        user.dbObject = dbuser
        return UpdateUser(user=user, triumph=True)
