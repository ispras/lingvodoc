import json
import datetime
import graphene
from graphql.language.ast import ObjectValue
from graphql.language import ast
from graphene.types import Scalar
from graphene.types.json import JSONString as JSONtype
from graphene.types.generic import GenericScalar
from lingvodoc.models import (
    ObjectTOC,
    DBSession,
    Client
)
from lingvodoc.views.v2.utils import (
    check_client_id
)

# Object types

class ResponseError(Exception):
    """
    usage:
    (in resolve_***  functions)
    if not perm_check(client_id, "field"):
        return ResponseError(message = "Permission Denied")
    """
    def __init__(self, message, code=None, params=None):
        super().__init__(message)
        self.message = str(message)
        self.code = code
        self.params = params


class PermissionException(ResponseError):
    """
    Exception used to signal absense of permission.
    """

    def __init__(self, client_id, action, subject, subject_id):
        """
        Saves permission absense information.
        """

        super().__init__(
            'Client {0} doesn\'t have \'{1}\' permissions for \'{2}\' {3}.'.format(
                client_id, action, subject, subject_id),
            params = (client_id, action, subject, subject_id))

        self.client_id = client_id
        self.action = action
        self.subject = subject
        self.subject_id = subject_id


def acl_check_by_id(action, subject, id_key = 'id'):
    """
    Decorator enabling ACL-based permission checks, compatible with any functions/methods with signature
    'def f(arg1, args, context, *args)', e.g. resolve methods.
    Example:
        @acl_check_by_id('view', 'dictionary_role')
        def resolve_dictionary_role(self, args, context, info):
            ...
    With different identifier argument key, that is, assuming that subject identifier is  args.get(
    'different_id_key'):
        @acl_check_by_id('view', 'dictionary_role', 'different_id_key')
        def resolve_dictionary_role(self, args, context, info):
            ...
    """

    def decorator(resolve_f):

        def wrapper(self, args, context, *resolve_f_args):

            if context.acl_check_if(action, subject, args.get(id_key)):
                return resolve_f(self, args, context, *resolve_f_args)

            else:
                raise PermissionException(context.client_id, action, subject, args.get(id_key))

        return wrapper

    return decorator


def client_id_check():
    """
    client_id checks
    """
    def get_client_id_from_args(wrapper_args):
        if "id" in wrapper_args:
            if wrapper_args["id"]:
                return wrapper_args["id"][0]


    def decorator(resolve_f):
        def wrapper(self, args, context, *resolve_f_args):
            client_id = get_client_id_from_args(args)
            authenticated = context.client_id
            if client_id:
            #client = DBSession.query(Client).filter_by(id=context.client_id).first()
                if not check_client_id(authenticated, client_id):
                    raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                                       authenticated)
            else:
                client = DBSession.query(Client).filter_by(id=authenticated).first()
                if not client:
                    raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                                       authenticated)
            return resolve_f(self, args, context, *resolve_f_args)


        return wrapper

    return decorator

class ObjectVal(Scalar):
    """
    ObjectVal is GraphQL scalar value must be Object
    This class was obtained from from "GenericScalar" and restrict users to input string or float data
    """

    @staticmethod
    def identity(value):
        return value

    serialize = identity
    parse_value = identity

    @staticmethod
    def parse_literal(ast):
        if isinstance(ast, ObjectValue):
            return {field.name.value: GenericScalar.parse_literal(field.value) for field in ast.fields}
        else:
            return None


class JSONString(JSONtype):
    """
    graphene.types.json.JSONString replacement which has no JSON encoder and decoder
    """
    @staticmethod
    def serialize(dt):
        return dt

    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.StringValue):
            return json.loads(node.value)

    @staticmethod
    def parse_value(value):
        return value#json.loads(value)


class DateTime(Scalar): # TODO: change format
    """
    graphene.types.json.JSONString replacement having different time format
    """
    @staticmethod
    def serialize(dt):
        # need to add assert
        if type(dt) is datetime.datetime:
            return  dt.isoformat()
        else:
            dt = datetime.datetime.utcfromtimestamp(dt) # can return wrong time
        return dt.isoformat()

    @staticmethod
    def parse_literal(node):
        if isinstance(node, ast.StringValue):
            return datetime.datetime.strptime(
                node.value, "%Y-%m-%dT%H:%M:%S.%f")

    @staticmethod
    def parse_value(value):
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f")

# Functions

def del_object(tmp_object):
    tmp_object.marked_for_deletion = True
    tmp_objecttoc = DBSession.query(ObjectTOC).filter_by(client_id=tmp_object.client_id,
                                                     object_id=tmp_object.object_id).one()
    tmp_objecttoc.marked_for_deletion = True

def fetch_object(attrib_name=None):
    """
    This magic decorator, which the resolve_* functions have, sets the dbObject atribute
    after execution of a request to a DB or force the function to return attribute by attrib_name.
    class must have dbType and dbObject attributes
    example:
    dbType = dbLanguage
    dbObject = None

    @fetch_object("marked_for_deletion")
    def resolve_marked_for_deletion(self, args, context, info):
        ...
    """
    def dec(func):
        def wrapper(*args, **kwargs):
            cls = args[0]
            if attrib_name:
                if hasattr(cls, attrib_name):
                    return getattr(cls, attrib_name)
            if not cls.dbObject:
                if type(cls.id) is int:
                    # example: (id: 1)
                    id = cls.id
                    cls.dbObject = DBSession.query(cls.dbType).filter_by(id=id).one()
                elif type(cls.id) is list:
                    # example: (id: [2,3])
                    cls.dbObject = DBSession.query(cls.dbType).filter_by(client_id=cls.id[0],
                                                                         object_id=cls.id[1]).one()
            return func(*args, **kwargs)
        return wrapper
    return dec


# Common interfaces

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
        return (self.dbObject.client_id, self.dbObject.object_id)

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
        return (self.dbObject.parent_client_id, self.dbObject.parent_object_id)

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
        return (self.dbObject.self_client_id, self.dbObject.self_object_id)

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
        return (self.dbObject.field_client_id, self.dbObject.field_object_id)

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
        return (self.dbObject.link_client_id, self.dbObject.link_object_id)

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
        return (self.dbObject.translation_gist_client_id,
                self.dbObject.translation_gist_object_id)

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
        return (self.dbObject.state_translation_gist_client_id,
                self.dbObject.state_translation_gist_object_id)

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

# rare interfaces

# Organization interface
class About(graphene.Interface):
    about = graphene.String()
    @fetch_object("about")
    def resolve_about(self, args, context, info):
        return self.dbObject.about

# PublishedEntity interface
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

# userBlobs interface
class DataType(graphene.Interface):   #TODO: check all data_type fields
    data_type = graphene.String()

    @fetch_object("data_type")
    def resolve_data_type(self, args, context, info):
        pass #return self.dbObject.data_type

# LexicalEntry interface
class MovedTo(graphene.Interface):
    moved_to = graphene.String()

    @fetch_object("moved_to")
    def resolve_moved_to(self, args, context, info):
        return self.dbObject.moved_to

# Field interface
class DataTypeTranslationGistId(graphene.Interface):
    data_type_translation_gist_id = graphene.List(graphene.Int)
    data_type = graphene.String()

    @fetch_object("data_type")
    def resolve_data_type(self, args, context, info):
        return self.dbObject.data_type

    @fetch_object("data_type_translation_gist_id")
    def resolve_data_type_translation_gist_id(self, args, context, info):
        return (self.dbObject.data_type_translation_gist_client_id,
                self.dbObject.data_type_translation_gist_object_id)

    @fetch_object("data_type_translation_gist_client_id")
    def resolve_data_type_translation_gist_client_id(self, args, context, info):
        return self.dbObject.data_type_translation_gist_client_id

    @fetch_object("data_type_translation_gist_object_id")
    def resolve_data_type_translation_gist_object_id(self, args, context, info):
        return self.dbObject.data_type_translation_gist_object_id

# Metadata section

class IsTranslatable(graphene.Interface):
    is_translatable = graphene.Boolean()

    @fetch_object("is_translatable")
    def resolve_is_translatable(self, args, context, info):
        return self.dbObject.is_translatable

class metadata(graphene.ObjectType):
    """
    graphene object that have all metadata attributes
    if new attributes of metadata are added, then this class has to be updated
    """
    hash = GenericScalar()
    origin_client_id = GenericScalar()
    origin_object_id = GenericScalar()
    info = GenericScalar()
    merged_by = GenericScalar()
    data_type = GenericScalar()
    blob_description = GenericScalar()
    merge = GenericScalar()
    original_filename = GenericScalar()
    location = GenericScalar()
    client_id = GenericScalar()
    authors = GenericScalar()
    row_id = GenericScalar()
    merged_to = GenericScalar()


    def resolve_hash(self, args, context, info):
        return self.hash

    def resolve_origin_client_id(self, args, context, info):
        return self.origin_client_id

    def resolve_origin_object_id(self, args, context, info):
        return self.origin_object_id

    def resolve_info(self, args, context, info):
        return self.info

    def resolve_merged_by(self, args, context, info):
        return self.merged_by

    def resolve_data_type(self, args, context, info):
        return self.data_type

    def resolve_blob_description(self, args, context, info):
        return self.blob_description

    def resolve_merge(self, args, context, info):
        return self.merge

    def resolve_original_filename(self, args, context, info):
        return self.original_filename

    def resolve_location(self, args, context, info):
        return self.location

    def resolve_client_id(self, args, context, info):
        return self.client_id

    def resolve_authors(self, args, context, info):
        return self.authors

    def resolve_row_id(self, args, context, info):
        return self.row_id

    def resolve_merged_to(self, args, context, info):
        return self.merged_to


def get_value_by_key(db_object, additional_metadata_string, metadata_key):
    """

    :param db_object: self.dbObject with metadata or None
    :param additional_metadata_string: self.additional_metadata_string dictionary or None
    :param metadata_key: metadata first-level key
    :return: value by metadata_key or None if params are not set
    """
    if additional_metadata_string:
        if metadata_key in additional_metadata_string:
            return additional_metadata_string[metadata_key]
    if db_object:
        meta = db_object.additional_metadata
        if meta:
            if metadata_key in meta:
                return meta[metadata_key]


class AdditionalMetadata(graphene.Interface):
    """
    Interface allowing to work with metadata as with the dictionary

    example:
    additional_metadata{
      hash
     }
    """

    # additional_metadata_string is attribute which needs to be set to have an opportunity to receive metadata without appeal to a DB

    additional_metadata_string = JSONString()

    # additional_metadata_string is necessary for obtaining result

    additional_metadata = graphene.Field(metadata)


    @fetch_object()
    def resolve_additional_metadata(self, args, context, info):
        db_object = self.dbObject
        additional_metadata_string = None
        if hasattr(self, "additional_metadata_string"):
            additional_metadata_string = self.additional_metadata_string

        # returns an object with the fields to which we can get access in the request

        metadata_object = metadata(hash=get_value_by_key(db_object, additional_metadata_string,"hash"), # TODO: refactor
                                    origin_client_id=get_value_by_key(db_object, additional_metadata_string, "origin_client_id"),
                                    origin_object_id=get_value_by_key(db_object, additional_metadata_string,"origin_object_id"),
                                    info=get_value_by_key(db_object, additional_metadata_string,"info"),
                                    merged_by = get_value_by_key(db_object, additional_metadata_string,"merged_by"),
                                    data_type = get_value_by_key(db_object, additional_metadata_string,"data_type"),
                                    blob_description = get_value_by_key(db_object, additional_metadata_string,"blob_description"),
                                    merge = get_value_by_key(db_object, additional_metadata_string,"merge"),
                                    original_filename = get_value_by_key(db_object, additional_metadata_string,"original_filename"),
                                    location = get_value_by_key(db_object, additional_metadata_string,"location"),
                                    client_id = get_value_by_key(db_object, additional_metadata_string,"client_id"),
                                    authors = get_value_by_key(db_object, additional_metadata_string,"authors"),
                                    row_id = get_value_by_key(db_object, additional_metadata_string,"row_id"),
                                    merged_to = get_value_by_key(db_object, additional_metadata_string,"merged_to")
                                   )
        return metadata_object

#  end of metadata section

class CommonFieldsComposite( MarkedForDeletion, AdditionalMetadata, CreatedAt, CompositeIdHolder, Relationship, TranslationGistHolder):
    """
    used in Dictionary, DictionaryPerspective and Language classes as Interfaces because function
    tree = graphene.List(CommonFieldsComposite, ) does not support listing
    """
    fieldType = graphene.String()  # depricated? -> data_typeString()
