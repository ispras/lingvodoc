import graphene
from graphene.types.json import JSONString
#from graphene.types.datetime import DateTime
from lingvodoc.models import (
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    DictionaryPerspectiveToField as dbDictionaryPerspectiveToField,
    Field as dbField,
    Language as dbLanguage,
    TranslationAtom as dbTranslationAtom,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    User as dbUser,
    BaseGroup as dbBaseGroup,
    Group as dbGroup
)
from pyramid.request import Request

from sqlalchemy import (
    func,
    and_,
    or_,
    tuple_
)

import datetime
from graphene.types import Scalar
from graphql.language import ast

RUSSIAN_LOCALE = 1
ENGLISH_LOCALE = 2


def fetch_object(attrib_name=None):
    def dec(func):
        def wrapper(*args, **kwargs):
            cls = args[0]
            if attrib_name:
                if hasattr(cls, attrib_name):
                    return getattr(cls, attrib_name)
            if not cls.dbObject:
                if type(cls.id) is int:
                    id = cls.id
                    cls.dbObject = DBSession.query(cls.dbType).filter_by(id=id).one()
                elif type(cls.id) is list:
                    cls.dbObject = DBSession.query(cls.dbType).filter_by(client_id=cls.id[0], object_id=cls.id[1]).one()
            return func(*args, **kwargs)
        return wrapper
    return dec


class DateTime(Scalar): # TODO: choose format
    '''DateTime Scalar Description'''

    @staticmethod
    def serialize(dt):
        dt = datetime.datetime.utcfromtimestamp(dt) # wrong time
        return dt.isoformat()

    @staticmethod
    def parse_literal(node):
        print(2, node)
        if isinstance(node, ast.StringValue):
            return datetime.datetime.strptime(
                node.value, "%Y-%m-%dT%H:%M:%S.%f")

    @staticmethod
    def parse_value(value):
        print(3, value)
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")



class IdHolder(graphene.Interface):
    id = graphene.Int()
    fetch_object("id")
    def resolve_id(self, args, context, info):
        return self.dbObject.id

class CompositeIdHolder(graphene.Interface):
    id = graphene.List(graphene.Int)
    client_id = graphene.Int()
    object_id = graphene.Int()

    @fetch_object("id")
    def resolve_id(self, args, context, info):
        return [self.dbObject.client_id, self.dbObject.object_id]

    @fetch_object("client_id")
    def resolve_client_id(self, args, context, info):
        return self.dbObject.client_id

    @fetch_object("object_id")
    def resolve_object_id(self, args, context, info):
        return self.dbObject.object_id

class CreatedAt(graphene.Interface):
    created_at = DateTime()
    @fetch_object("created_at")
    def resolve_created_at(self, args, context, info):
        return self.dbObject.created_at

class Relationship(graphene.Interface):
    parent_id = graphene.List(graphene.Int)
    parent_client_id = graphene.List(graphene.Int)
    parent_object_id = graphene.List(graphene.Int)

    @fetch_object("parent_id")
    def resolve_parent_id(self, args, context, info):
        return self.dbObject.parent_id

    @fetch_object("parent_client_id")
    def resolve_parent_client_id(self, args, context, info):
        return self.dbObject.parent_client_id

    @fetch_object("parent_object_id")
    def resolve_parent_object_id(self, args, context, info):
        return self.dbObject.parent_object_id


class SelfHolder(graphene.Interface):
    self_id = graphene.List(graphene.Int)
    self_client_id = graphene.Int()
    self_object_id = graphene.Int()

    @fetch_object("self_id")
    def resolve_self_id(self, args, context, info):
        return self.dbObject.self_id

    @fetch_object("self_client_id")
    def resolve_self_client_id(self, args, context, info):
        return self.dbObject.self_client_id

    @fetch_object("self_object_id")
    def resolve_self_object_id(self, args, context, info):
        return self.dbObject.self_object_id

class FieldHolder(graphene.Interface):
    field_id = graphene.List(graphene.Int)
    field_client_id = graphene.Int()
    field_object_id = graphene.Int()

    @fetch_object("field_id")
    def resolve_field_id(self, args, context, info):
        return self.dbObject.field_id

    @fetch_object("field_client_id")
    def resolve_field_client_id(self, args, context, info):
        return self.dbObject.field_client_id

    @fetch_object("field_object_id")
    def resolve_field_object_id(self, args, context, info):
        return self.dbObject.field_object_id

class ParentLink(graphene.Interface):
    link_id = graphene.List(graphene.Int)
    link_client_id = graphene.List(graphene.Int)
    link_object_id = graphene.List(graphene.Int)

    @fetch_object("link_id")
    def resolve_link_id(self, args, context, info):
        return self.dbObject.link_id

    @fetch_object("link_client_id")
    def resolve_link_client_id(self, args, context, info):
        return self.dbObject.link_client_id

    @fetch_object("link_object_id")
    def resolve_link_object_id(self, args, context, info):
        return self.dbObject.link_object_id

class MarkedForDeletion(graphene.Interface):
    marked_for_deletion = graphene.Boolean()

    @fetch_object("marked_for_deletion")
    def resolve_marked_for_deletion(self, args, context, info):
        return self.dbObject.marked_for_deletion

class AdditionalMetadata(graphene.Interface):
    additional_metadata = JSONString()

    @fetch_object("additional_metadata")
    def resolve_additional_metadata(self, args, context, info):
        return self.dbObject.additional_metadata


class Position(graphene.Interface):
    position = graphene.Int()

    @fetch_object("position")
    def resolve_position(self, args, context, info):
        return self.dbObject.position

class TranslationGistHolder(graphene.Interface):
    translation_gist_id = graphene.List(graphene.Int)
    translation_gist_client_id = graphene.Int()
    translation_gist_object_id = graphene.Int()

    @fetch_object("translation_gist_id")
    def resolve_translation_gist_id(self, args, context, info):
        return (self.dbObject.translation_gist_client_id, self.dbObject.translation_gist_object_id)

    @fetch_object("translation_gist_client_id")
    def resolve_translation_gist_client_id(self, args, context, info):
        return self.dbObject.translation_gist_client_id

    @fetch_object("translation_gist_object_id")
    def resolve_translation_gist_object_id(self, args, context, info):
        return self.dbObject.translation_gist_object_id

class UserId(graphene.Interface):
    user_id = graphene.Int()

    @fetch_object("user_id")
    def resolve_user_id(self, args, context, info):
        return self.dbObject.user_id

class StateHolder(graphene.Interface):
    state_translation_gist_id = graphene.List(graphene.Int)
    state_translation_gist_client_id = graphene.Int()
    state_translation_gist_object_id = graphene.Int()

    @fetch_object("state_translation_gist_id")
    def resolve_state_translation_gist_id(self, args, context, info):
        return (self.dbObject.state_translation_gist_client_id, self.dbObject.state_translation_gist_object_id)

    @fetch_object("state_translation_gist_client_id")
    def resolve_state_translation_gist_client_id(self, args, context, info):
        return self.dbObject.state_translation_gist_client_id

    @fetch_object("state_translation_gist_object_id")
    def resolve_state_translation_gist_object_id(self, args, context, info):
        return self.dbObject.state_translation_gist_object_id

class TableName(graphene.Interface):
    table_name = graphene.String()

    @fetch_object("table_name")
    def resolve_table_name(self, args, context, info):
        return self.dbObject.table_name

class Name(graphene.Interface):
    name = graphene.String()
    @fetch_object("name")
    def resolve_name(self, args, context, info):
        return self.dbObject.name

class LocaleId(graphene.Interface):
    locale_id = graphene.Int()

    @fetch_object("locale_id")
    def resolve_locale_id(self, args, context, info):
        return self.dbObject.locale_id

class Content(graphene.Interface):
    content = graphene.String()

    @fetch_object("content")
    def resolve_content(self, args, context, info):
        return self.dbObject.content

class TypeHolder(graphene.Interface):
    type = graphene.String()  # rename (?)
    @fetch_object("type")
    def resolve_type(self, args, context, info):
        return self.dbObject.type

class TranslationHolder(graphene.Interface):
    translation = graphene.String()
    @fetch_object("translation")
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id')) # TODO: fix it

# Organization
class About(graphene.Interface):
    about = graphene.String()
    @fetch_object("about")
    def resolve_about(self, args, context, info):
        return self.dbObject.about
# PublishedEntity
class Published(graphene.Interface):
    published = graphene.Boolean()

    @fetch_object("published")
    def resolve_about(self, args, context, info):
        return self.dbObject.published

class Accepted(graphene.Interface):
    accepted = graphene.Boolean()

    @fetch_object("accepted")
    def resolve_accepted(self, args, context, info):
        return self.dbObject.accepted
# userBlobs
class DataType(graphene.Interface):
    data_type = graphene.String()

    @fetch_object("data_type")
    def resolve_data_type(self, args, context, info):
        pass #return self.dbObject.data_type
# LexicalEntry
class MovedTo(graphene.Interface):
    moved_to = graphene.String()

    @fetch_object("moved_to")
    def resolve_moved_to(self, args, context, info):
        return self.dbObject.moved_to
# Field

class DataTypeTranslationGistId(graphene.Interface):
    data_type_translation_gist_id = graphene.List(graphene.Int)
    data_type = graphene.String()

    @fetch_object("data_type")
    def resolve_data_type(self, args, context, info):
        return self.dbObject.data_type

    @fetch_object("data_type_translation_gist_id")
    def resolve_data_type_translation_gist_id(self, args, context, info):
        return (self.dbObject.data_type_translation_gist_client_id, self.dbObject.data_type_translation_gist_object_id)

    @fetch_object("data_type_translation_gist_client_id")
    def resolve_data_type_translation_gist_client_id(self, args, context, info):
        return self.dbObject.data_type_translation_gist_client_id

    @fetch_object("data_type_translation_gist_object_id")
    def resolve_data_type_translation_gist_object_id(self, args, context, info):
        return self.dbObject.data_type_translation_gist_object_id

class CommonFieldsComposite( MarkedForDeletion, AdditionalMetadata, CreatedAt, CompositeIdHolder, Relationship, TranslationGistHolder):
    fieldType = graphene.String()

class IsTranslatable(graphene.Interface):
    is_translatable = graphene.Boolean()

    @fetch_object("is_translatable")
    def resolve_is_translatable(self, args, context, info):
        return self.dbObject.is_translatable
# class SingleID(graphene.Interface):
#     id = graphene.Int()

# class TranslationgistHoler(graphene.Interface):
#     id = graphene.List(graphene.Int)
#     additional_metadata = JSONString()
#     created_at = DateTime()
#     marked_for_deletion = graphene.Boolean()




class BaseGroup(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL
     #dictionary_default  | boolean                     | NOT NULL
     #perspective_default | boolean                     | NOT NULL
     #name                | text                        | NOT NULL
     #subject             | text                        | NOT NULL
     #action              | text                        | NOT NULL
    """
    perspective_default = graphene.Boolean()
    dictionary_default = graphene.Boolean()
    subject = graphene.String()
    action = graphene.String()
    class Meta:
        interfaces = (IdHolder, CreatedAt, Name)
    pass





class DictionaryPerspectiveToField(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #self_client_id      | bigint                      |
     #self_object_id      | bigint                      |
     #field_client_id     | bigint                      | NOT NULL
     #field_object_id     | bigint                      | NOT NULL
     #link_client_id      | bigint                      |
     #link_object_id      | bigint                      |
     #marked_for_deletion | boolean                     | NOT NULL
     #position            | integer                     | NOT NULL
    """
    dbObject = None
    dbType = dbDictionaryPerspectiveToField
    class Meta:
        interfaces = (CreatedAt,
                      CompositeIdHolder,
                      Relationship,
                      SelfHolder,
                      FieldHolder,
                      ParentLink,
                      MarkedForDeletion,
                      Position)
    pass

class Email(graphene.ObjectType):
    """
     #created_at | timestamp without time zone | NOT NULL
     #id         | bigint                      | NOT NULL DEFAULT nextval('email_id_seq'::regclass)
     #user_id    | bigint                      | NOT NULL
     #email      | text                        |
    """
    email = graphene.String()

    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                      UserId
                    )
    pass

class Grant(graphene.ObjectType):
    """
     #id                                | bigint                      | NOT NULL DEFAULT nextval('grant_id_seq'::regclass)
     #translation_gist_client_id        | bigint                      | NOT NULL
     #translation_gist_object_id        | bigint                      | NOT NULL
     #issuer_translation_gist_client_id | bigint                      | NOT NULL
     #issuer_translation_gist_object_id | bigint                      | NOT NULL
     #begin                             | date                        |
     #end                               | date                        |
     #created_at                        | timestamp without time zone | NOT NULL
     #issuer_url                        | character varying(2048)     | NOT NULL
     #grant_url                         | character varying(2048)     | NOT NULL
     #grant_number                      | character varying(1000)     | NOT NULL
     #owners                            | jsonb                       |
     #additional_metadata               | jsonb                       |
    """
    issuer_translation_gist_id = graphene.Int()
    begin = DateTime()
    end = DateTime()
    issuer_url = graphene.String()
    grant_url = graphene.String()
    grant_number = graphene.String()
    owners = JSONString()

    class Meta:
        interfaces = (CreatedAt,
                      TranslationGistHolder,
                      IdHolder,
                      AdditionalMetadata
                    )
    pass


class Group(graphene.ObjectType):
    """
     #created_at        | timestamp without time zone | NOT NULL
     #id                | uuid                        | NOT NULL
     #old_id            | bigint                      |
     #base_group_id     | bigint                      | NOT NULL
     #subject_client_id | bigint                      |
     #subject_object_id | bigint                      |
     #subject_override  | boolean                     |
    """
    old_id = graphene.String() # uuid
    base_group_id = graphene.Int()
    subject_id = graphene.List(graphene.Int)
    subject_override = graphene.Boolean()

    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                    )
    pass


class Organization(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #id                  | bigint                      | NOT NULL DEFAULT nextval('organization_id_seq'::regclass)
     #marked_for_deletion | boolean                     | NOT NULL
     #name                | text                        |
     #about               | text                        |
     #additional_metadata | jsonb                       |
    """
    class Meta:
        interfaces = (CreatedAt,
                      IdHolder,
                      MarkedForDeletion,
                      AdditionalMetadata,
                      Name,
                      About
                    )
    pass


"""
organization_to_group_association = Table('organization_to_group_association', Base.metadata,
                                          Column('organization_id', SLBigInteger(), ForeignKey('organization.id')),
                                          Column('group_id', UUIDType, ForeignKey('group.id'))
                                          )
"""



class ObjectTOC(graphene.ObjectType):
    """
    #object_id           | bigint  | NOT NULL
    #client_id           | bigint  | NOT NULL
    #table_name          | text    | NOT NULL
    #marked_for_deletion | boolean | NOT NULL
    """
    class Meta:
        interfaces = (CompositeIdHolder,
                      MarkedForDeletion,
                      TableName,
                    )
    pass


class PublishingEntity(graphene.ObjectType):
    """
     #created_at | timestamp without time zone | NOT NULL
     #object_id  | bigint                      | NOT NULL
     #client_id  | bigint                      | NOT NULL
     #published  | boolean                     | NOT NULL
     #accepted   | boolean                     | NOT NULL
    """
    class Meta:
        interfaces = (CreatedAt,
                      CompositeIdHolder,
                      Published,
                      Accepted
                    )
    pass


class TranslationAtom(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #locale_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #content             | text                        | NOT NULL
     #additional_metadata | jsonb                       |
    """
    class Meta:
        interfaces = (CompositeIdHolder, Relationship, AdditionalMetadata, CreatedAt, MarkedForDeletion,  Content, LocaleId)
    pass

class TranslationGist(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #marked_for_deletion | boolean                     | NOT NULL
     #type                | text                        |
    """
    class Meta:
        interfaces = (CompositeIdHolder,
                      CreatedAt,
                      MarkedForDeletion,
                      TypeHolder

                      )


class UserBlobs(graphene.ObjectType):
    """
    #created_at          | timestamp without time zone | NOT NULL
    #object_id           | bigint                      | NOT NULL
    #client_id           | bigint                      | NOT NULL
    #marked_for_deletion | boolean                     | NOT NULL
    #user_id             | bigint                      |
    #name                | text                        | NOT NULL
    #content             | text                        | NOT NULL
    #real_storage_path   | text                        | NOT NULL
    #data_type           | text                        | NOT NULL
    #additional_metadata | jsonb                       |
    """
    real_storage_path = graphene.String()

    class Meta:
        interfaces = (CompositeIdHolder, AdditionalMetadata, CreatedAt, MarkedForDeletion, UserId, Content, DataType)
    pass

class UserRequest(graphene.ObjectType):
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
class Field(graphene.ObjectType):
    """
     #created_at                           | timestamp without time zone | NOT NULL
     #object_id                            | bigint                      | NOT NULL
     #client_id                            | bigint                      | NOT NULL
     #translation_gist_client_id           | bigint                      | NOT NULL
     #translation_gist_object_id           | bigint                      | NOT NULL
     #data_type_translation_gist_client_id | bigint                      | NOT NULL
     #data_type_translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion                  | boolean                     | NOT NULL
     #is_translatable                      | boolean                     | NOT NULL
     #additional_metadata                  | jsonb                       |
     + .translation
    """

    data_type = graphene.String()
    translation = graphene.String()
    dbType = dbField
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder,
                      TranslationGistHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      MarkedForDeletion,
                      DataTypeTranslationGistId,
                      IsTranslatable,
                      #TranslationHolder
                      )

    #@fetch_object("data_type")
    #def resolve_data_type(self, args, context, info):
    #    pass#print (self.dbObject.data_type)
    #    #return self.dbObject.data_type

    @fetch_object("translation")
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))



class ResponseError(Exception):
    def __init__(self, message, code=None, params=None):
        super().__init__(message)
        self.message = str(message)
        self.code = code
        self.params = params


from graphql.execution import ExecutionResult
from lingvodoc import models
from lingvodoc.models import user_to_group_association
def perm_check(a, b):

    return True

class CreateField(graphene.Mutation):
    class Input:
        translation_gist_id = graphene.List(graphene.Int)
        data_type_translation_gist_id = graphene.List(graphene.Int)


    marked_for_deletion = graphene.Boolean()
    field = graphene.Field(Field)
    status_code = graphene.Boolean()
    errors = graphene.List(graphene.String)
    id = graphene.List(graphene.Int)

    @staticmethod
    def mutate(root, args, context, info):
        #subject = 'language'
        client_id = context["client_id"]
        if client_id:
            data_type_translation_gist_id = args.get('data_type_translation_gist_id')
            translation_gist_id = args.get('translation_gist_id')
            dbfield = dbField(client_id=client_id,
                          object_id=None,
                          data_type_translation_gist_client_id=data_type_translation_gist_id[0],
                          data_type_translation_gist_object_id=data_type_translation_gist_id[1],
                          translation_gist_client_id=translation_gist_id[0],
                          translation_gist_object_id=translation_gist_id[1],
                          marked_for_deletion=False
                          )
            # if args.get('is_translatable', None):
            #     field.is_translatable = bool(args['is_translatable'])
            DBSession.add(dbfield)
            DBSession.flush()
            field = Field(id = [dbfield.client_id, dbfield.object_id])
            field.dbObject = dbfield
            return CreateField(field=field)







            """
            groups = DBSession.query(dbGroup).filter_by(subject_override=True).join(dbBaseGroup).filter_by(subject=subject).all()
            print(groups)
            create_base_group = DBSession.query(dbBaseGroup).filter_by(
                subject = 'language', action = 'edit').first()
            #print(create_base_group)

            user_create = DBSession.query(user_to_group_association, dbGroup).filter(and_(
            user_to_group_association.c.user_id == user_id,
            user_to_group_association.c.group_id == dbGroup.id,
            dbGroup.base_group_id == create_base_group.id,
            dbGroup.subject_client_id == 205,
            dbGroup.subject_object_id == 1)).limit(1).count() > 0
            print("!", user_create)
            """
            #print(models.acl_by_groups())
            #client_id = context.authenticated_userid
            #client_id = context["request"].authenticated_userid
            #if not perm_check(client_id, "field"):
            #    return ResponseError(message = "Permission Denied (Field)")

            #print(context)

            #id = args.get('id')
            #field = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
            #context["error"] = ["123"]


class UpdateField(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    marked_for_deletion = graphene.Boolean()
    person = graphene.Field(Field)

    @staticmethod
    def mutate(root, args, context, info):
        #client_id = context.authenticated_userid
        client_id = context["request"].authenticated_userid
        id = args.get('id')
        field = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
        person = Field(id = id)
        marked_for_deletion = True
        return CreateField(person=person, marked_for_deletion=marked_for_deletion)


class DeleteField(graphene.Mutation):
    class Input:
        id = graphene.List(graphene.Int)

    marked_for_deletion = graphene.Boolean()
    field = graphene.Field(Field)

    @staticmethod
    def mutate(root, args, context, info):
        #client_id = context.authenticated_userid
        client_id = context["client_id"]
        id = args.get('id')
        field = DBSession.query(dbField).filter(and_(dbField.client_id == id[0], dbField.object_id == id[1])).one()
        field.marked_for_deletion = True
        field = Field(id = id)
        return CreateField(field=field)

class MyMutations(graphene.ObjectType):
    create_field = CreateField.Field()
    update_field = UpdateField.Field()
    delete_field = DeleteField.Field()


class Entity(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #self_client_id      | bigint                      |
     #self_object_id      | bigint                      |
     #field_client_id     | bigint                      | NOT NULL
     #field_object_id     | bigint                      | NOT NULL
     #link_client_id      | bigint                      |
     #link_object_id      | bigint                      |
     #locale_id           | bigint                      |
     #marked_for_deletion | boolean                     | NOT NULL
     #content             | text                        |
     #additional_metadata | jsonb                       |


    """
     # TODO: Accepted, entity_type
    content = graphene.String()
    data_type = graphene.String()

    dbType = dbEntity
    dbObject = None
    class Meta:
        interfaces = (CompositeIdHolder,
                      AdditionalMetadata,
                      CreatedAt,
                      MarkedForDeletion,
                      Relationship,
                      SelfHolder,
                      FieldHolder,
                      ParentLink,
                      Content,
                      TranslationHolder,
                      LocaleId
                      )


    @fetch_object('data_type')
    def resolve_data_type(self, args, context, info):
        return self.dbObject.field.data_type



class LexicalEntry(graphene.ObjectType):
    """
     #created_at          | timestamp without time zone | NOT NULL
     #object_id           | bigint                      | NOT NULL
     #client_id           | bigint                      | NOT NULL
     #parent_object_id    | bigint                      |
     #parent_client_id    | bigint                      |
     #marked_for_deletion | boolean                     | NOT NULL
     #moved_to            | text                        |
     #additional_metadata | jsonb                       |
    """
    entities = graphene.List(Entity)

    dbType = dbLexicalEntry
    dbObject = None

    class Meta:
        interfaces = (CompositeIdHolder, AdditionalMetadata, CreatedAt, MarkedForDeletion, Relationship, MovedTo)
        #only_fields = ['id', 'additional_metadata', 'created_at', "marked_for_deletion"]

    @fetch_object('entities')
    def resolve_entities(self, args, context, info):
        result = list()
        for db_entity in self.dbObject.entity:
            gr_entity_object = Entity(id=[db_entity.client_id, db_entity.object_id])
            gr_entity_object.dbObject = db_entity
            result.append(gr_entity_object)
        return result[:2]



# class Holder2(graphene.Interface):
#     additional_metadata = JSONString()
#     created_at = DateTime()
#     marked_for_deletion = graphene.Boolean()
#
# class PairID2(graphene.Interface):
#     id = graphene.List(graphene.Int)

#
#
# class MetaMRO(type):
#     def mro(cls):
#         return (cls, graphene.Interface, Holder,PairID, object)


#class CompositeIdHolder, AdditionalMetadata, CreatedAt, MarkedForDeletion(Holder, PairID, metaclass = MetaMRO): pass


# from graphene.types.field import Field as grField
# from graphene.types.union import Union
#
# class MyUnion(Union):
#     class Meta:
#         types = (PairID, Holder)

# class Thing(graphene.Union(PairID, Holder)):
#     '''Thing union description'''
#     my_attr = True

class Dictionary(graphene.ObjectType):
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
    """
    dbType = dbDictionary
    dbObject = None
    category = graphene.Int()
    domain = graphene.Int()
    # parent_object_id
    # translation_gist_client_id
    # state_translation_gist_client_id
    status = graphene.String()

    translation = graphene.String()
    dataType = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder)

    def resolve_dataType(self, args, context, info):
        return 'dictionary'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        # return dbdict.get_translation(2)
        return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('status')
    def resolve_status(self, args, context, info):
        atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=self.dbObject.state_translation_gist_client_id,
                                                          parent_object_id=self.dbObject.state_translation_gist_object_id,
                                                          locale_id=int(context.get('locale_id'))).first()
        if atom:
            return atom.content
        else:
            return None

    @fetch_object()
    def resolve_created_at(self, args, context, info):
        return self.dbObject.created_at




class Language(graphene.ObjectType):
    """
     #created_at                 | timestamp without time zone | NOT NULL
     #object_id                  | bigint                      | NOT NULL
     #client_id                  | bigint                      | NOT NULL
     #parent_object_id           | bigint                      |
     #parent_client_id           | bigint                      |
     #translation_gist_client_id | bigint                      | NOT NULL
     #translation_gist_object_id | bigint                      | NOT NULL
     #marked_for_deletion        | boolean                     | NOT NULL
     #additional_metadata        | jsonb                       |
     + translation
    """
    dbType = dbLanguage
    dbObject = None

    dataType = graphene.String()

    class Meta:
        interfaces = (CommonFieldsComposite, TranslationHolder)
    @fetch_object()
    def resolve_dictionaries(self, args, context, info):
        result = list()
        for dictionary in DBSession.query(dbDictionary).filter(and_(dbDictionary.parent_object_id == self.dbObject.object_id,
                                                         dbDictionary.parent_client_id == self.dbObject.client_id)):
            result.append(Dictionary(id=[dictionary.client_id, dictionary.object_id]))
        return result

    def resolve_dataType(self, args, context, info):
        return 'language'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))

    #@fetch_object()
    #def resolve_created_at(self, args, context, info):
    #    return self.dbObject.created_at


class DictionaryPerspective(graphene.ObjectType):
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
     #is_template                      | boolean                     | NOT NULL
     #import_source                    | text                        |
     #import_hash                      | text                        |
     #additional_metadata              | jsonb                       |
     + .translation
     + status
     + tree
    """
    data_type = graphene.String()

    is_template = graphene.Boolean()
    status = graphene.String()
    import_source = graphene.String()
    import_hash = graphene.String()

    tree = graphene.List(CommonFieldsComposite, )  # TODO: check it
    fields = graphene.List(Field)
    lexicalEntries = graphene.List(LexicalEntry, offset = graphene.Int(), count = graphene.Int(), mode = graphene.String())
    #stats = graphene.String() # ?


    dbType = dbPerspective
    dbObject = None

    class Meta:
        interfaces = (CommonFieldsComposite, StateHolder, TranslationHolder)


    @fetch_object()
    def resolve_additional_metadata(self, args, context, info):
        return self.dbObject.additional_metadata

    @fetch_object('data_type')
    def resolve_data_type(self, args, context, info):
        return 'perspective'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object('status')
    def resolve_status(self, args, context, info):
        atom = DBSession.query(dbTranslationAtom).filter_by(parent_client_id=self.dbObject.state_translation_gist_client_id,
                                                          parent_object_id=self.dbObject.state_translation_gist_object_id,
                                                          locale_id=int(context.get('locale_id'))).first()
        if atom:
            return atom.content
        else:
            return None

    @fetch_object() # TODO: ?
    def resolve_tree(self, args, context, info):
        # print(self.dbObject)
        # print(DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one())

        result = list()
        iteritem = self.dbObject
        while iteritem:
            #print(type(iteritem))
            id = [iteritem.client_id, iteritem.object_id]
            if type(iteritem) == dbPerspective:
                result.append(DictionaryPerspective(id=id))
            if type(iteritem) == dbDictionary:
                result.append(Dictionary(id=id))
            if type(iteritem) == dbLanguage:
                result.append(Language(id=id))
            iteritem = iteritem.parent

        return result

    @fetch_object() # TODO: ?
    def resolve_fields(self, args, context, info):
        print(context.get("locale_id"))
        locale_id = context.get("locale_id")
        dbFields = self.dbObject.dictionaryperspectivetofield
        result = list()
        for dbfield in dbFields:
            gr_field_obj = DictionaryPerspectiveToField(id=[dbfield.client_id, dbfield.object_id])
            gr_field_obj.dbObject = dbfield
            result.append(gr_field_obj)
        return result

    def resolve_lexicalEntries(self, args, context, info):
        result = list()
        request = context.get('request')

        #dbPersp = DBSession.query(dbPerspective).filter_by(client_id=self.id[0], object_id=self.id[1]).one()
        lexes = DBSession.query(dbLexicalEntry).filter_by(parent=self.dbObject)

        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes.all()]
        # for lex in lexes:
        #     dbentities = DBSession.query(dbEntity).filter_by(parent=lex).all()
        #     entities = [Entity(id=[ent.client_id, ent.object_id]) for ent in dbentities]
        #     result.append(LexicalEntry(id=[lex.client_id, lex.object_id], entities = entities))


        sub_result = dbLexicalEntry.track_multiple(lexes_composite_list,
                                             int(request.cookies.get('locale_id') or 2),
                                             publish=None, accept=True)
        for entry in sub_result:
            entities = []
            for ent in entry['contains']:
                del ent["contains"]
                del ent["level"]
                del ent["accepted"]
                del ent["entity_type"]
                del ent["published"]
                if "link_client_id" in ent and "link_object_id" in ent:
                    ent["link_id"] = (ent["link_client_id"], ent["link_object_id"])
                if not "content" in ent:
                    ent["content"] = None
                gr_entity_object = Entity(id=[ent['client_id'],
                                       ent['object_id']],
                                       #link_id = (ent["link_client_id"], ent["link_object_id"]),
                                       parent_id = (ent["parent_client_id"], ent["parent_object_id"]),

                                   #content=ent.get('content'),
                                   #fieldType=ent['data_type'],
                                   ** ent)
                #print(ent)
                entities.append(gr_entity_object)
            #del entry["entries"]
            del entry["published"]
            del entry["contains"]
            del entry["level"]
            gr_lexicalentry_object = LexicalEntry(id=[entry['client_id'], entry['object_id']], entities=entities, **entry)

            result.append(gr_lexicalentry_object)


        return result






"""
user_to_group_association = Table('user_to_group_association', Base.metadata,
                                  Column('user_id', SLBigInteger(), ForeignKey('user.id')),
                                  Column('group_id', UUIDType, ForeignKey('group.id'))
                                  )

user_to_organization_association = Table('user_to_organization_association', Base.metadata,
                                         Column('user_id', SLBigInteger(), ForeignKey('user.id')),
                                         Column('organization_id', SLBigInteger(), ForeignKey('organization.id'))
                                         )

"""

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





class Query(graphene.ObjectType):

    client = graphene.String()
    dictionaries = graphene.List(Dictionary, published=graphene.Boolean())
    dictionary = graphene.Field(Dictionary, id=graphene.List(graphene.Int))
    perspective = graphene.Field(DictionaryPerspective, id=graphene.List(graphene.Int))
    entity = graphene.Field(Entity, id=graphene.List(graphene.Int))
    language = graphene.Field(Language, id=graphene.List(graphene.Int))
    user = graphene.Field(User, id=graphene.Int())
    field = graphene.Field(Field, id=graphene.List(graphene.Int))

    def resolve_dictionaries(self, args, context, info):
        dbdicts = list()
        request = context.get('request')
        if args.get('published'):

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Published'}
            headers = dict()
            if request.headers.get('Cookie'):
                headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)

            if 'error' not in resp.json:
                state_translation_gist_object_id, state_translation_gist_client_id = resp.json['object_id'], resp.json[
                    'client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            subreq = Request.blank('/translation_service_search')
            subreq.method = 'POST'
            subreq.headers = request.headers
            subreq.json = {'searchstring': 'Limited access'}  # todo: fix
            headers = dict()
            if request.headers.get('Cookie'):
                headers = {'Cookie': request.headers['Cookie']}
            subreq.headers = headers
            resp = request.invoke_subrequest(subreq)

            if 'error' not in resp.json:
                limited_object_id, limited_client_id = resp.json['object_id'], resp.json['client_id']
            else:
                raise KeyError("Something wrong with the base", resp.json['error'])

            dbdicts = DBSession.query(dbDictionary).filter(or_(and_(dbDictionary.state_translation_gist_object_id == state_translation_gist_object_id,
                                                                    dbDictionary.state_translation_gist_client_id == state_translation_gist_client_id),
                                 and_(dbDictionary.state_translation_gist_object_id == limited_object_id,
                                      dbDictionary.state_translation_gist_client_id == limited_client_id))).\
                join(dbPerspective) \
                .filter(or_(and_(dbPerspective.state_translation_gist_object_id == state_translation_gist_object_id,
                             dbPerspective.state_translation_gist_client_id == state_translation_gist_client_id),
                        and_(dbPerspective.state_translation_gist_object_id == limited_object_id,
                             dbPerspective.state_translation_gist_client_id == limited_client_id))).all()

        else:
            dbdicts = DBSession.query(dbDictionary).all()

        dictionaries_list = [Dictionary(id=[dbdict.client_id, dbdict.object_id]) for dbdict in dbdicts]
        return dictionaries_list

    def resolve_dictionary(self, args, context, info):
        id = args.get('id')
        return Dictionary(id=id)

    def resolve_perspective(self, args, context, info):
        id = args.get('id')
        return DictionaryPerspective(id=id)

    def resolve_language(self, args, context, info):
        id = args.get('id')
        return Language(id=id)

    def resolve_entity(self, args, context, info):
        id = args.get('id')
        return Entity(id=id)

    def resolve_user(self, args, context, info):
        id = args.get('id')
        return User(id=id)

    def resolve_datetime(self, args, context, info):
        id = args.get('id')
        return DateTime(id=id)


    def resolve_basegroup(self, args, context, info):
        id = args.get('id')
        return BaseGroup(id=id)

    def resolve_client(self, args, context, info):
        return context.get('client')

    def resolve_dictionaryperspectivetofield(self, args, context, info):
        id = args.get('id')
        return DictionaryPerspectiveToField(id=id)

    def resolve_email(self, args, context, info):
        id = args.get('id')
        return Email(id=id)

    def resolve_grant(self, args, context, info):
        id = args.get('id')
        return Grant(id=id)

    def resolve_group(self, args, context, info):
        id = args.get('id')
        return Group(id=id)

    def resolve_organization(self, args, context, info):
        id = args.get('id')
        return Organization(id=id)

    # def resolve_passhash(self, args, context, info):
    #     id = args.get('id')
    #     return Passhash(id=id)

    def resolve_objecttoc(self, args, context, info):
        id = args.get('id')
        return ObjectTOC(id=id)

    def resolve_publishingentity(self, args, context, info):
        id = args.get('id')
        return PublishingEntity(id=id)

    def resolve_translationatom(self, args, context, info):
        id = args.get('id')
        return TranslationAtom(id=id)

    def resolve_translationgist(self, args, context, info):
        id = args.get('id')
        return TranslationGist(id=id)

    def resolve_userblobs(self, args, context, info):
        id = args.get('id')
        return UserBlobs(id=id)

    def resolve_field(self, args, context, info):
        print(context)
        client_id = context.get("client_id")
        print(client_id)
        id = args.get('id')
        return Field(id=id)

    def resolve_lexicalentry(self, args, context, info):
        id = args.get('id')
        return LexicalEntry(id=id)



schema = graphene.Schema(query=Query, auto_camelcase=False, mutation=MyMutations)

