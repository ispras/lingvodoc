import json
import datetime
import graphene
from graphql.language.ast import ObjectValue, ListValue, IntValue
from graphql.language import ast
from graphene.types import Scalar
from graphene.types.json import JSONString as JSONtype
from graphene.types.generic import GenericScalar
from lingvodoc.models import (
    ObjectTOC,
    DBSession,
    Client,
    LexicalEntry,
    DictionaryPerspectiveToField,
    TranslationGist as dbTranslationGist,
    TranslationAtom as dbTranslationAtom
)
from lingvodoc.utils.verification import check_client_id
from lingvodoc.cache.caching import CACHE


# Object types
# TODO: delete comment lines

class ResponseError(Exception):
    """
    usage:
    (in resolve_***  functions)
    if not perm_check(client_id, "field"):
        return ResponseError(message = "Permission Denied")
    """
    def __init__(self, message, code=None, params=None, self_object=None):
        super().__init__(message)
        self.message = str(message)
        self.code = code
        self.params = params
        if self_object:
            self_object.ErrorHappened = True
        #DBSession.rollback()


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
            params=(client_id, action, subject, subject_id))

        self.client_id = client_id
        self.action = action
        self.subject = subject
        self.subject_id = subject_id


def acl_check_by_id(action, subject, id_key='id'):
    """
    Decorator enabling ACL-based permission checks, compatible with any functions/methods with signature
    'def f(arg1, args, context, *args)', e.g. resolve methods.
    Example:
        @acl_check_by_id('view', 'dictionary_role')
        def resolve_dictionary_role(self, args, context, info):
            ...
    With different identifier argument key, that is, assuming that subject identifier is  args.get(
    'different_id_key'):
     @client_id_check()
     @acl_check_by_id('create', 'perspective', id_key = "parent_id")
            ...
    """

    def decorator(resolve_f):
        def wrapper(self,info, **kwargs):

            if info.context.acl_check_if(action, subject, kwargs.get(id_key)):
                return resolve_f(self, info, **kwargs )

            else:
                raise PermissionException(info.context.client_id, action, subject, kwargs.get(id_key))

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
        def wrapper(self, *args, **kwargs):
            client_id = get_client_id_from_args(kwargs)
            info = args[0]
            authenticated = info.context.client_id
            if client_id:
                if not check_client_id(authenticated, client_id):
                    raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                                   authenticated)
            else:
                client = DBSession.query(Client).filter_by(id=authenticated).first()
                if not client:
                    raise KeyError("Invalid client id (not registered on server). Try to logout and then login.",
                                   authenticated)
            return resolve_f(self, args[0], **kwargs)

        return wrapper

    return decorator

class LingvodocObjectType(graphene.ObjectType):
    dbObject = None
    ErrorHappened = None

class LingvodocID(Scalar):
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
        if isinstance(ast, ListValue):
            if len(ast.values) != 2:
                return None
            result = list()
            for intvalue in ast.values:
                if isinstance(intvalue, IntValue):
                    result.append(int(intvalue.value))
                else:
                    return None
            return result
        else:
            return None


class Upload(graphene.types.Scalar):
    @staticmethod
    def serialize(value):
        return value

    @staticmethod
    def parse_literal(node):
        return node

    @staticmethod
    def parse_value(value):
        return value

# class LevelID(Scalar):
#     """
#     made specifically for returning language tree
#     """
#
#     @staticmethod
#     def identity(value):
#         return value
#
#     serialize = identity
#     parse_value = identity
#
#     @staticmethod
#     def parse_literal(ast):
#         if isinstance(ast, ListValue):
#             if len(ast.values) != 3:
#                 return None
#             result = list()
#             for intvalue in ast.values:
#                 if isinstance(intvalue, IntValue):
#                     result.append(int(intvalue.value))
#                 else:
#                     return None
#             return result
#         else:
#             return None


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
        # json.loads(value)
        return value


class DateTime(Scalar):  # TODO: change format
    """
    graphene.types.json.JSONString replacement having different time format
    """
    @staticmethod
    def serialize(dt):
        # need to add assert
        if type(dt) is datetime.datetime:
            return dt.isoformat()
        else:
            dt = datetime.datetime.utcfromtimestamp(dt)  # can return wrong time
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

    # if hasattr(tmp_object, "translation_gist_object_id"):
    #     gist = DBSession.query(dbTranslationGist).filter_by(client_id=tmp_object.translation_gist_client_id,
    #                                                  object_id=tmp_object.translation_gist_object_id,
    #                                                         marked_for_deletion=False).first()
    #     atoms = DBSession.query(dbTranslationAtom).filter_by(parent=gist, marked_for_deletion=False).all()
    #     for dbtranslationatom in atoms:
    #         key = "translation:%s:%s:%s" % (
    #             str(dbtranslationatom.parent_client_id),
    #             str(dbtranslationatom.parent_object_id),
    #             str(dbtranslationatom.locale_id))
    #         CACHE.rem(key)
    #         dbtranslationatom.mark_deleted("Manually deleted")
    #     #gist.mark_deleted("Manually deleted")
    tmp_object.mark_deleted("Manually deleted")


def fetch_object(attrib_name=None, ACLSubject=None, ACLKey=None):
    """
    This magic decorator, which the resolve_* functions have, sets the dbObject atribute
    after execution of a request to a DB or force the function to return attribute by attrib_name.
    class must have dbType and dbObject attributes
    example:
    dbType = dbLanguage

    @fetch_object("marked_for_deletion")
    def resolve_marked_for_deletion(self, args, context, info):
        ...
    """
    def dec(func):
        def wrapper(*args, **kwargs):
            cls = args[0]
            context = args[1].context

            if ACLSubject and ACLKey == 'id':
                context.acl_check('view', ACLSubject, cls.id)
            if cls.ErrorHappened:
                return None
            if not cls.dbObject:
                if type(cls.id) is int:
                    # example: (id: 1)
                    id = cls.id
                    cls.dbObject = DBSession.query(cls.dbType).filter_by(id=id).first()
                    if cls.dbObject is None:
                        #cls.ErrorHappened = True
                        raise ResponseError(message="%s was not found" % cls.__class__, self_object=cls)
                elif type(cls.id) is list:
                    # example: (id: [2,3])
                    cls.dbObject = DBSession.query(cls.dbType).filter_by(client_id=cls.id[0],
                                                                         object_id=cls.id[1]).first()
                    if cls.dbObject is None:
                        #cls.ErrorHappened = True
                        raise ResponseError(message="%s was not found" % cls.__class__, self_object=cls)
            if ACLSubject and '_' in ACLKey:
                context.acl_check('view', ACLSubject,
                                  [getattr(cls.dbObject, ACLKey.replace('_', '_client_')),
                                   getattr(cls.dbObject, ACLKey.replace('_', '_object_'))])
            return func(*args, **kwargs)

        return wrapper

    return dec


# Common interfaces

class IdHolder(graphene.Interface):
    id = graphene.Int()

    @fetch_object("id")
    def resolve_id(self, info):
        return self.dbObject.id


class CompositeIdHolder(graphene.Interface):
    id = LingvodocID()
    # client_id = graphene.Int()
    # object_id = graphene.Int()

    @fetch_object("id")
    def resolve_id(self, info):
        return (self.dbObject.client_id, self.dbObject.object_id)

    # @fetch_object("client_id")
    # def resolve_client_id(self, info):
    #     return self.dbObject.client_id
    #
    # @fetch_object("object_id")
    # def resolve_object_id(self, info):
    #     return self.dbObject.object_id


class CreatedAt(graphene.Interface):
    created_at = graphene.Int() #DateTime()

    @fetch_object("created_at")
    def resolve_created_at(self, info):
        if type(self.dbObject.created_at) is int:
            return self.dbObject.created_at
        return self.dbObject.created_at.timestamp()


class Relationship(graphene.Interface):
    parent_id = LingvodocID()

    @fetch_object("parent_id")
    def resolve_parent_id(self, info):
        if self.dbObject.parent_client_id is None or self.dbObject.parent_object_id is None:
            return None
        return (self.dbObject.parent_client_id, self.dbObject.parent_object_id)

class SelfHolder(graphene.Interface):
    self_id = LingvodocID()

    @fetch_object("self_id")
    def resolve_self_id(self, info):
        if self.dbObject.self_client_id and self.dbObject.self_object_id:
            return (self.dbObject.self_client_id, self.dbObject.self_object_id)
        return None

class FieldHolder(graphene.Interface):
    field_id = LingvodocID()

    @fetch_object("field_id")
    def resolve_field_id(self, info):
        return (self.dbObject.field_client_id, self.dbObject.field_object_id)

class ParentLink(graphene.Interface):
    link_id = LingvodocID()

    @fetch_object("link_id")
    def resolve_link_id(self, info):
        if self.dbObject.link_client_id and self.dbObject.link_object_id:
            return (self.dbObject.link_client_id, self.dbObject.link_object_id)
        return None

class MarkedForDeletion(graphene.Interface):
    marked_for_deletion = graphene.Boolean()

    @fetch_object("marked_for_deletion")
    def resolve_marked_for_deletion(self, info):
        return self.dbObject.marked_for_deletion


class Position(graphene.Interface):
    position = graphene.Int()

    @fetch_object("position")
    def resolve_position(self, info):
        return self.dbObject.position


class TranslationGistHolder(graphene.Interface):
    translation_gist_id = LingvodocID()

    @fetch_object("translation_gist_id")
    def resolve_translation_gist_id(self, info):
        return (self.dbObject.translation_gist_client_id,
                self.dbObject.translation_gist_object_id)


class UserId(graphene.Interface):
    user_id = graphene.Int()

    @fetch_object("user_id")
    def resolve_user_id(self, info):
        return self.dbObject.user_id


class StateHolder(graphene.Interface):
    state_translation_gist_id = LingvodocID()

    @fetch_object("state_translation_gist_id")
    def resolve_state_translation_gist_id(self, info):
        return (self.dbObject.state_translation_gist_client_id,
                self.dbObject.state_translation_gist_object_id)

class TableName(graphene.Interface):
    table_name = graphene.String()

    @fetch_object("table_name")
    def resolve_table_name(self, info):
        return self.dbObject.table_name


class Name(graphene.Interface):
    name = graphene.String()

    @fetch_object("name")
    def resolve_name(self, info):
        return self.dbObject.name

class RealStoragePath(graphene.Interface):
    real_storage_path = graphene.String()

    @fetch_object("real_storage_path")
    def resolve_real_storage_path(self, info):
        return self.dbObject.real_storage_path

class LocaleId(graphene.Interface):
    locale_id = graphene.Int()

    @fetch_object("locale_id")
    def resolve_locale_id(self, info):
        return self.dbObject.locale_id


class Content(graphene.Interface):
    content = graphene.String()

    @fetch_object("content")
    def resolve_content(self, info):
        return self.dbObject.content


class TypeHolder(graphene.Interface):
    type = graphene.String()  # rename (?)

    @fetch_object("type")
    def resolve_type(self, info):
        return self.dbObject.type


class TranslationHolder(graphene.Interface):
    translation = graphene.String()


    @fetch_object("translation")
    def resolve_translation(self, info):
        context = info.context
        return str(self.dbObject.get_translation(context.get('locale_id'))) # TODO: fix it

# rare interfaces

# Organization interface


class About(graphene.Interface):

    about = graphene.String()

    @fetch_object("about")
    def resolve_about(self, info):
        return self.dbObject.about

# PublishedEntity interface


class Published(graphene.Interface):
    published = graphene.Boolean()

    @fetch_object("published")
    def resolve_published(self, info):
        if not self.publishingentity:
            self.publishingentity = self.dbObject.publishingentity
        return self.publishingentity.published


class Accepted(graphene.Interface):
    accepted = graphene.Boolean()

    @fetch_object("accepted")
    def resolve_accepted(self, info):
        if not self.publishingentity:
            self.publishingentity = self.dbObject.publishingentity
        return self.dbObject.publishingentity.accepted

# userBlobs interface


class DataType(graphene.Interface):  # TODO: check all data_type fields
    data_type = graphene.String()

    @fetch_object("data_type")
    def resolve_data_type(self, info):
        return self.dbObject.data_type

class FakeIds(graphene.Interface):
    fake_id = graphene.String()
    self_fake_id = graphene.String()


# LexicalEntry interface


class MovedTo(graphene.Interface):
    moved_to = graphene.String()

    @fetch_object("moved_to")
    def resolve_moved_to(self, info):
        return self.dbObject.moved_to

# Field interface


class DataTypeTranslationGistId(graphene.Interface):
    data_type_translation_gist_id = LingvodocID()


    @fetch_object("data_type_translation_gist_id")
    def resolve_data_type_translation_gist_id(self, info):
        return (self.dbObject.data_type_translation_gist_client_id,
                self.dbObject.data_type_translation_gist_object_id)
    #

class IsTranslatable(graphene.Interface):
    is_translatable = graphene.Boolean()

    @fetch_object("is_translatable")
    def resolve_is_translatable(self, info):
        return self.dbObject.is_translatable


class MergeMetadata(graphene.ObjectType):
    min_created_at = graphene.Int()
    original_client_id = graphene.Int()
    merge_tree = graphene.List(LingvodocID)


class Metadata(graphene.ObjectType):
    """
    graphene object that have all metadata attributes
    if new attributes of metadata are added, then this class has to be updated
    """
    hash = graphene.String()
    origin_id = LingvodocID()
    blobs = graphene.List(LingvodocID)
    merged_by = LingvodocID()
    data_type = graphene.String()
    blob_description = graphene.String()
    merge = graphene.Field(MergeMetadata)  # TODO: MergeMetadata
    original_filename = graphene.String()
    location = ObjectVal()
    client_id = graphene.Int()
    authors = graphene.String()
    row_id = graphene.Int()
    merged_to = LingvodocID()
    is_protected = graphene.Boolean()
    previous_objects = graphene.List(LingvodocID)
    younger_siblings = graphene.List(LingvodocID)
    starling_fields = graphene.List(graphene.String)
    participant = graphene.List(LingvodocID)
    link_perspective_id = LingvodocID()
    tag_list = graphene.List(graphene.String)



# class LevelAndId(graphene.ObjectType):
#     """
#     graphene object that have all metadata attributes
#     if new attributes of metadata are added, then this class has to be updated
#     """
#     parent_id = LingvodocID()
#     language_id = LingvodocID()


# def get_value_by_key(db_object, additional_metadata_string, metadata_key):
#     """
#
#     :param db_object: self.dbObject with metadata or None
#     :param additional_metadata_string: self.additional_metadata_string dictionary or None
#     :param metadata_key: metadata first-level key
#     :return: value by metadata_key or None if params are not set
#     """
#     if additional_metadata_string:
#         if metadata_key in additional_metadata_string:
#             return additional_metadata_string[metadata_key]
#     if db_object:
#         meta = db_object.additional_metadata
#         if meta:
#             if metadata_key in meta:
#                 return meta[metadata_key]



class AdditionalMetadata(graphene.Interface):
    """
    Interface allowing to work with metadata as with the dictionary

    example:
    additional_metadata{
      hash
     }
    """

    additional_metadata = graphene.Field(Metadata)

    @fetch_object()
    def resolve_additional_metadata(self, info):
        db_object = self.dbObject

        # initializes dict with None, for keys nonexistent in dbObject.additional_metadata
        # list of keys is taken from Metadata attributes

        def default_value(i):
            if type(getattr(Metadata, i)) == graphene.List:
                return []
            return None

        metadata_dict = {i: default_value(i) for i in Metadata().__class__.__dict__ if not i.startswith("_")}

        if db_object.additional_metadata:
            new_meta = {key: db_object.additional_metadata[key] for key in db_object.additional_metadata if key in metadata_dict}
            metadata_dict.update(new_meta)

        if "participant" in metadata_dict:
            if metadata_dict["participant"]:
                old_id_meta = metadata_dict["participant"]
                metadata_dict["participant"] = [[x["client_id"], x["object_id"]] for x in old_id_meta]
        if "blobs" in metadata_dict:
            if metadata_dict["blobs"]:
                old_id_meta = metadata_dict["blobs"]
                metadata_dict["blobs"] = [[x["client_id"], x["object_id"]] for x in old_id_meta]
        metadata_object = Metadata(**metadata_dict)
        return metadata_object

#  end of metadata section


class CommonFieldsComposite(MarkedForDeletion, AdditionalMetadata, CreatedAt, CompositeIdHolder, Relationship,
                            TranslationGistHolder, TranslationHolder):
    """
    used in Dictionary, DictionaryPerspective and Language classes as Interfaces because function
    tree = graphene.List(CommonFieldsComposite, ) does not support listing
    """
    pass#fieldType = graphene.String()  # depricated? -> data_typeString()


class UserAndOrganizationsRoles(graphene.ObjectType):
    roles_users = graphene.List(ObjectVal)
    roles_organizations = graphene.List(ObjectVal)

    def resolve_roles_users(self, info):
        return self.roles_users

    def resolve_roles_organizations(self, info):
        return self.roles_organizations
