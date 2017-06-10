import graphene
from graphene.types.json import JSONString
#from graphene.types.datetime import DateTime
from lingvodoc.models import (
    DBSession,
    Dictionary as dbDictionary,
    DictionaryPerspective as dbPerspective,
    DictionaryPerspectiveToField as dbField,
    Language as dbLanguage,
    TranslationAtom as dbTranslationAtom,
    Entity as dbEntity,
    LexicalEntry as dbLexicalEntry,
    User as dbUser
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

class Holder(graphene.Interface):
    id = graphene.List(graphene.Int)
    translation = graphene.String()
    dataType = graphene.String()

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


class BaseGroup(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     id                  | bigint                      | NOT NULL
     dictionary_default  | boolean                     | NOT NULL
     perspective_default | boolean                     | NOT NULL
     name                | text                        | NOT NULL
     subject             | text                        | NOT NULL
     action              | text                        | NOT NULL
    """
    pass


class Client(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     id                  | bigint                      | NOT NULL DEFAULT nextval('client_id_seq'::regclass)
     user_id             | bigint                      | NOT NULL
     is_browser_client   | boolean                     | NOT NULL
     counter             | bigint                      | NOT NULL
     additional_metadata | jsonb                       |
    """
    pass


class DictionaryPerspectiveToField(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     object_id           | bigint                      | NOT NULL
     client_id           | bigint                      | NOT NULL
     parent_object_id    | bigint                      |
     parent_client_id    | bigint                      |
     self_client_id      | bigint                      |
     self_object_id      | bigint                      |
     field_client_id     | bigint                      | NOT NULL
     field_object_id     | bigint                      | NOT NULL
     link_client_id      | bigint                      |
     link_object_id      | bigint                      |
     marked_for_deletion | boolean                     | NOT NULL
     position            | integer                     | NOT NULL
    """
    pass

class Email(graphene.ObjectType):
    """
     created_at | timestamp without time zone | NOT NULL
     id         | bigint                      | NOT NULL DEFAULT nextval('email_id_seq'::regclass)
     user_id    | bigint                      | NOT NULL
     email      | text                        |
    """
    pass

class Grant(graphene.ObjectType):
    """
     id                                | bigint                      | NOT NULL DEFAULT nextval('grant_id_seq'::regclass)
     translation_gist_client_id        | bigint                      | NOT NULL
     translation_gist_object_id        | bigint                      | NOT NULL
     issuer_translation_gist_client_id | bigint                      | NOT NULL
     issuer_translation_gist_object_id | bigint                      | NOT NULL
     begin                             | date                        |
     end                               | date                        |
     created_at                        | timestamp without time zone | NOT NULL
     issuer_url                        | character varying(2048)     | NOT NULL
     grant_url                         | character varying(2048)     | NOT NULL
     grant_number                      | character varying(1000)     | NOT NULL
     owners                            | jsonb                       |
     additional_metadata               | jsonb                       |
    """

    pass


class Group(graphene.ObjectType):
    """
     created_at        | timestamp without time zone | NOT NULL
     id                | uuid                        | NOT NULL
     old_id            | bigint                      |
     base_group_id     | bigint                      | NOT NULL
     subject_client_id | bigint                      |
     subject_object_id | bigint                      |
     subject_override  | boolean                     |
    """
    pass


class Organization(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     id                  | bigint                      | NOT NULL DEFAULT nextval('organization_id_seq'::regclass)
     marked_for_deletion | boolean                     | NOT NULL
     name                | text                        |
     about               | text                        |
     additional_metadata | jsonb                       |
    """
    pass


"""
organization_to_group_association = Table('organization_to_group_association', Base.metadata,
                                          Column('organization_id', SLBigInteger(), ForeignKey('organization.id')),
                                          Column('group_id', UUIDType, ForeignKey('group.id'))
                                          )
"""
class Passhash(graphene.ObjectType):
    """
     id         | bigint                      | NOT NULL DEFAULT nextval('passhash_id_seq'::regclass)
     user_id    | bigint                      | NOT NULL
     hash       | text                        | NOT NULL
        """
    pass


class ObjectTOC(graphene.ObjectType):
    """
    object_id           | bigint  | NOT NULL
    client_id           | bigint  | NOT NULL
    table_name          | text    | NOT NULL
    marked_for_deletion | boolean | NOT NULL
    """
    pass


class PublishingEntity(graphene.ObjectType):
    """
     created_at | timestamp without time zone | NOT NULL
     object_id  | bigint                      | NOT NULL
     client_id  | bigint                      | NOT NULL
     published  | boolean                     | NOT NULL
     accepted   | boolean                     | NOT NULL
    """
    pass


class TranslationAtom(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     object_id           | bigint                      | NOT NULL
     client_id           | bigint                      | NOT NULL
     parent_object_id    | bigint                      |
     parent_client_id    | bigint                      |
     locale_id           | bigint                      | NOT NULL
     marked_for_deletion | boolean                     | NOT NULL
     content             | text                        | NOT NULL
     additional_metadata | jsonb                       |
    """
    pass

class TranslationGist(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     object_id           | bigint                      | NOT NULL
     client_id           | bigint                      | NOT NULL
     marked_for_deletion | boolean                     | NOT NULL
     type                | text                        |
    """
    pass


class UserBlobs(graphene.ObjectType):
    """
    created_at          | timestamp without time zone | NOT NULL
    object_id           | bigint                      | NOT NULL
    client_id           | bigint                      | NOT NULL
    marked_for_deletion | boolean                     | NOT NULL
    user_id             | bigint                      |
    name                | text                        | NOT NULL
    content             | text                        | NOT NULL
    real_storage_path   | text                        | NOT NULL
    data_type           | text                        | NOT NULL
    additional_metadata | jsonb                       |
    """
    pass

class UserRequest(graphene.ObjectType):
    """
     id                  | bigint                      | NOT NULL DEFAULT nextval('userrequest_id_seq'::regclass)
     sender_id           | bigint                      | NOT NULL
     recipient_id        | bigint                      | NOT NULL
     created_at          | timestamp without time zone | NOT NULL
     broadcast_uuid      | character varying(36)       | NOT NULL
     type                | character varying(1000)     | NOT NULL
     message             | character varying(1000)     |
     subject             | jsonb                       |
     additional_metadata | jsonb                       |
    """
    pass

class Field(graphene.ObjectType):
    """
     created_at                           | timestamp without time zone | NOT NULL
     object_id                            | bigint                      | NOT NULL
     client_id                            | bigint                      | NOT NULL
     translation_gist_client_id           | bigint                      | NOT NULL
     translation_gist_object_id           | bigint                      | NOT NULL
     data_type_translation_gist_client_id | bigint                      | NOT NULL
     data_type_translation_gist_object_id | bigint                      | NOT NULL
     marked_for_deletion                  | boolean                     | NOT NULL
     is_translatable                      | boolean                     | NOT NULL
     additional_metadata                  | jsonb                       |
    """
    dbType = dbField
    dbObject = None
    class Meta:
        interfaces = (Holder, )

    def resolve_dataType(self):
        return 'field'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.field.get_translation(context.get('locale_id'))

class Entity(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     object_id           | bigint                      | NOT NULL
     client_id           | bigint                      | NOT NULL
     parent_object_id    | bigint                      |
     parent_client_id    | bigint                      |
     self_client_id      | bigint                      |
     self_object_id      | bigint                      |
     field_client_id     | bigint                      | NOT NULL
     field_object_id     | bigint                      | NOT NULL
     link_client_id      | bigint                      |
     link_object_id      | bigint                      |
     locale_id           | bigint                      |
     marked_for_deletion | boolean                     | NOT NULL
     content             | text                        |
     additional_metadata | jsonb                       |
    """
    id = graphene.List(graphene.Int)
    content = graphene.String()
    fieldType = graphene.String()

    dbType = dbEntity
    dbObject = None

    @fetch_object('content')
    def resolve_content(self, args, context, info):
        return self.dbObject.content

    @fetch_object('fieldType')
    def resolve_fieldType(self, args, context, info):
        return self.dbObject.field.data_type


class LexicalEntry(graphene.ObjectType):
    """
     created_at          | timestamp without time zone | NOT NULL
     object_id           | bigint                      | NOT NULL
     client_id           | bigint                      | NOT NULL
     parent_object_id    | bigint                      |
     parent_client_id    | bigint                      |
     marked_for_deletion | boolean                     | NOT NULL
     moved_to            | text                        |
     additional_metadata | jsonb                       |
    """
    id = graphene.List(graphene.Int)
    entities = graphene.List(Entity)
    created_at = DateTime()

    dbType = dbLexicalEntry
    dbObject = None

    @fetch_object('entities')
    def resolve_entities(self, args, context, info):
        result = list()
        for entity in self.dbObject.entity:
            result.append(Entity(id=[entity.client_id, entity.object_id]))
        return result[:2]

    @fetch_object()
    def resolve_created_at(self, args, context, info):
        return self.dbObject.created_at

class DictionaryPerspective(graphene.ObjectType):
    """
     created_at                       | timestamp without time zone | NOT NULL
     object_id                        | bigint                      | NOT NULL
     client_id                        | bigint                      | NOT NULL
     parent_object_id                 | bigint                      |
     parent_client_id                 | bigint                      |
     translation_gist_client_id       | bigint                      | NOT NULL
     translation_gist_object_id       | bigint                      | NOT NULL
     state_translation_gist_client_id | bigint                      | NOT NULL
     state_translation_gist_object_id | bigint                      | NOT NULL
     marked_for_deletion              | boolean                     | NOT NULL
     is_template                      | boolean                     | NOT NULL
     import_source                    | text                        |
     import_hash                      | text                        |
     additional_metadata              | jsonb                       |
    """
    class Meta:
        interfaces = (Holder, )


    status = graphene.String()
    tree = graphene.List(Holder)
    fields = graphene.List(Field)
    lexicalEntries = graphene.List(LexicalEntry, offset = graphene.Int(), count = graphene.Int(), mode = graphene.String())
    stats = graphene.String()

    dbType = dbPerspective
    dbObject = None

    def resolve_dataType(self, args, context, info):
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
        result = list()
        iteritem = self.dbObject
        while iteritem:
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
        dbFields = self.dbObject.dictionaryperspectivetofield
        result = list()
        for dbfield in dbFields:
            result.append(Field(id=[dbfield.client_id, dbfield.object_id]))
        return result

    @fetch_object() # TODO: ?
    def resolve_lexicalEntries(self, args, context, info):
        result = list()
        request = context.get('request')
        # lexes = DBSession.query(dbLexicalEntry).filter_by(parent=self.dbObject)
        #
        # lexes_composite_list = [(lex.created_at,
        #                          lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
        #                          lex.marked_for_deletion, lex.additional_metadata,
        #                          lex.additional_metadata.get('came_from')
        #                          if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
        #                         for lex in lexes.all()]
        # for lex in lexes:
        #     dbentities = DBSession.query(dbEntity).filter_by(parent=lex).all()
        #     entities = [Entity(id=[ent.client_id, ent.object_id]) for ent in dbentities]
        #     result.append(LexicalEntry(id=[lex.client_id, lex.object_id], entities = entities))

        lex = DBSession.query(dbLexicalEntry).filter_by(parent=self.dbObject).first()
        lexes_composite_list = [lex]
        lexes_composite_list = [(lex.created_at,
                                 lex.client_id, lex.object_id, lex.parent_client_id, lex.parent_object_id,
                                 lex.marked_for_deletion, lex.additional_metadata,
                                 lex.additional_metadata.get('came_from')
                                 if lex.additional_metadata and 'came_from' in lex.additional_metadata else None)
                                for lex in lexes_composite_list]
        sub_result = dbLexicalEntry.track_multiple(lexes_composite_list,
                                             int(request.cookies.get('locale_id') or 2),
                                             publish=None, accept=True)

        # sub_result = dbLexicalEntry.track_multiple(lexes_composite_list,
        #                                      int(request.cookies.get('locale_id') or 2),
        #                                      publish=None, accept=True)
        for entry in sub_result:
            entities = [Entity(id=[ent['client_id'], ent['object_id']],  fieldType=ent['data_type']) for ent in entry['contains']]

            result.append(LexicalEntry(id=[entry['client_id'], entry['object_id']], entities=entities))


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
    # class Meta:
    #     interfaces = (Holder, )
    # class
    login = graphene.String()
    name = graphene.String()
    intl_name = graphene.String()
    default_locale_id = graphene.Int()
    birthday = graphene.String() # TODO: DateTime class
    is_active = graphene.Boolean() #boolean
    id = graphene.Int()
    created_at = DateTime()

    dbType = dbUser
    dbObject = None

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



class Language(graphene.ObjectType):
    """
     created_at                 | timestamp without time zone | NOT NULL
     object_id                  | bigint                      | NOT NULL
     client_id                  | bigint                      | NOT NULL
     parent_object_id           | bigint                      |
     parent_client_id           | bigint                      |
     translation_gist_client_id | bigint                      | NOT NULL
     translation_gist_object_id | bigint                      | NOT NULL
     marked_for_deletion        | boolean                     | NOT NULL
     additional_metadata        | jsonb                       |
    """
    dbType = dbLanguage
    dbObject = None
    created_at = DateTime()


    class Meta:
        interfaces = (Holder, )

    def resolve_dataType(self, args, context, info):
        return 'language'

    @fetch_object('translation')
    def resolve_translation(self, args, context, info):
        return self.dbObject.get_translation(context.get('locale_id'))

    @fetch_object()
    def resolve_created_at(self, args, context, info):
        return self.dbObject.created_at



class Dictionary(graphene.ObjectType):
    """
     created_at                       | timestamp without time zone | NOT NULL
     object_id                        | bigint                      | NOT NULL
     client_id                        | bigint                      | NOT NULL
     parent_object_id                 | bigint                      |
     parent_client_id                 | bigint                      |
     translation_gist_client_id       | bigint                      | NOT NULL
     translation_gist_object_id       | bigint                      | NOT NULL
     state_translation_gist_client_id | bigint                      | NOT NULL
     state_translation_gist_object_id | bigint                      | NOT NULL
     marked_for_deletion              | boolean                     | NOT NULL
     category                         | bigint                      |
     domain                           | bigint                      |
     additional_metadata              | jsonb                       |
    """
    dbType = dbDictionary
    dbObject = None
    category = graphene.Int()
    domain = graphene.Int()
    # parent_object_id
    # translation_gist_client_id
    # state_translation_gist_client_id
    created_at = DateTime()
    status = graphene.String()
    marked_for_deletion = graphene.Boolean()
    additional_metadata = JSONString()

    class Meta:
        interfaces = (Holder, )


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


class Query(graphene.ObjectType):

    client = graphene.String()
    dictionaries = graphene.List(Dictionary, published=graphene.Boolean())
    dictionary = graphene.Field(Dictionary, id=graphene.List(graphene.Int))
    perspective = graphene.Field(DictionaryPerspective, id=graphene.List(graphene.Int))
    entity = graphene.Field(Entity, id=graphene.List(graphene.Int))
    language = graphene.Field(Language, id=graphene.List(graphene.Int))
    user = graphene.Field(User, id=graphene.Int())
    def resolve_client(self, args, context, info):
        return context.get('client')

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

schema = graphene.Schema(query=Query, auto_camelcase=False)
