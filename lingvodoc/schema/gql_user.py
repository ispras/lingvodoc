import graphene
from sqlalchemy import and_
from lingvodoc.models import (
    User as dbUser,
    BaseGroup,
    Client,
    Email,
    Group,
    Passhash,
    DBSession
)
from lingvodoc.views.v2.utils import add_user_to_group

from lingvodoc.schema.gql_holders import (
    IdHolder,
    CreatedAt,
    AdditionalMetadata,
    Name,
    fetch_object
)

import datetime
from passlib.hash import bcrypt

class User(graphene.ObjectType):
    """
    created_at          | timestamp without time zone | NOT NULL
    id                  | bigint                      | NOT NULL DEFAULT nextval('user_id_seq'::regclass)
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

    dbType = dbUser
    dbObject = None

    class Meta:
        interfaces = (IdHolder, CreatedAt, AdditionalMetadata, Name)

    @fetch_object()
    def resolve_login(self, args, context, info):
        return self.dbObject.login

    @fetch_object()
    def resolve_name(self, args, context, info):
        return self.dbObject.name

    @fetch_object()
    def resolve_intl_name(self, args, context, info):
        return self.dbObject.intl_name

    @fetch_object()
    def resolve_default_locale_id(self, args, context, info):
        return self.dbObject.default_locale_id

    @fetch_object()
    def resolve_birthday(self, args, context, info):
        return self.dbObject.birthday

    @fetch_object()
    def resolve_is_active(self, args, context, info):
        return self.dbObject.is_active

    @fetch_object()
    def resolve_created_at(self, args, context, info):
        return self.dbObject.created_at

    @fetch_object()
    def resolve_additional_metadata(self, args, context, info):
        return self.dbObject.additional_metadata


class CreateUser(graphene.Mutation):
    """
    example:
    mutation:  {
        create_user( login: "new_usr", email: "new@mail.ru"), name: "Новое имя", birthday: [1, 1, 1970], password: "secret") {
            status
        }
    }
    """
    class Input:
        login = graphene.String()
        email = graphene.String()
        name = graphene.String()
        birthday = graphene.List(graphene.Int)
        password = graphene.String()


    field = graphene.Field(User)
    status = graphene.Boolean()


    @staticmethod
    def mutate(root, args, context, info):
        login = args.get('login')
        name = args.get('name')
        email = args.get('email')
        birthday = args.get('birthday')
        password = args.get('password')

        day = birthday[0]
        month = birthday[1]
        year = birthday[2]
        if day is None or month is None or year is None:
            return ResponseError(message="Error: day, month or year of the birth is missing")
        # birthday = datetime.datetime.strptime(day + month + year, "%d%m%Y").date()
        try:
            day = int(day)
            month = int(month)
            year = int(year)
            date_of_birthday = datetime.date(year, month, day)
        except ValueError:
            return ResponseError(message="Error: Invalid birthday")

        if DBSession.query(User).filter_by(login=login).first():
            return ResponseError(message="The user with this login is already registered")

        if DBSession.query(Email).filter_by(email=email).first():
            return ResponseError(message="The user with this email is already registered")

        dbentityobj = dbUser(login=login,
                             name=name,
                             created_at=datetime.datetime.utcnow(),
                             intl_name=login,
                             birthday=date_of_birthday,
                             is_active=True
                             )
        pwd = Passhash(password=password)
        email = Email(email=email)
        dbentityobj.password = pwd
        dbentityobj.email = email
        DBSession.add(dbentityobj)

        basegroups = []
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create dictionaries").first()]
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create languages").first()]
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create organizations").first()]
        basegroups += [DBSession.query(BaseGroup).filter_by(name="Can create translation strings").first()]
        groups = []
        for base in basegroups:
            groups += [DBSession.query(Group).filter_by(subject_override=True, base_group_id=base.id).first()]
        for group in groups:
            add_user_to_group(dbentityobj, group)
        DBSession.flush()

        user = User(login=dbentityobj.login, is_active=True)
        user.dbObject = dbentityobj
        return CreateUser(field=user, status=True)


"""
mutation  {
    update_user(user_id: 2, name: "Имя", about: "some about", birthday: [1, 1, 1980], email: "new@mail.ru" ){status}
}
resolve:
{
    "update_entity": {
        "status": true
    }
}
"""


class UpdateUser(graphene.Mutation):
    class Input:
        """
        user_id = graphene.Int()
        name = graphene.String()
        about = graphene.String()
        birthday = graphene.List(graphene.Int)
        email = graphene.String()
        """
        user_id = graphene.Int()
        new_password = graphene.String()
        old_password = graphene.String()
        name = graphene.String()
        default_locale_id = graphene.Int()
        birthday = graphene.String()
        email = graphene.String()
        about = graphene.String()

    field = graphene.Field(User)
    status = graphene.Boolean()

    @staticmethod
    def mutate(root, args, context, info):
        # client_id used in ACL func as arg
        client_id = context["client_id"]
        user_id = args.get('user_id')
        if client_id:
            client = DBSession.query(Client).filter_by(id=client_id).first()

            if not client:
                return ResponseError(message="Error: No such client in the system")

            user = DBSession.query(dbUser).filter_by(id=client.user_id).first()
            user_id = client.user_id
            if not user:
                return ResponseError(message="Error: No such user in the system")
        else:
            user = DBSession.query(dbUser).filter_by(id=user_id).first()
            if not user:
                return ResponseError(message="Error: No such user in the system")

        new_password = args.get('new_password')
        old_password = args.get('old_password')

        if new_password:
            if not old_password:
                return ResponseError(message="Error: Need old password to confirm")
            old_hash = DBSession.query(Passhash).filter_by(user_id=user_id).first()
            if old_hash:
                if not user.check_password(old_password):
                    return ResponseError(message="Error: Wrong password")
                else:
                    old_hash.hash = bcrypt.encrypt(new_password)
            else:
                return ResponseError(message="Error: User has no password")

        name = args.get('name')
        if name:
            user.name = name

        default_locale_id = args.get('default_locale_id')
        if default_locale_id:
            user.default_locale_id = default_locale_id

        birthday = args.get('birthday')
        if birthday:
            try:
                year, month, day = birthday.split('-')
                user.birthday = datetime.date(int(year), int(month), int(day))
            except ValueError:
                return ResponseError(message="Error: Invalid birthday")

        email = args.get('email')
        if email:
            if user.email:
                user.email.email = email
            else:
                new_email = Email(user=user, email=email)
                DBSession.add(new_email)
                DBSession.flush()

        about = args.get('about')
        if about:
            meta = dict()
            if user.additional_metadata:
                meta = user.additional_metadata
            meta['about'] = about
            user.additional_metadata = meta

        field = User(login=user.login)
        field.dbObject = user

        return UpdateUser(field=field, status=True)
