from pyramid.security import Allow, Authenticated, ALL_PERMISSIONS, Everyone

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
    query
)

from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
    event,
    ForeignKey,
    Table,
    UniqueConstraint,
    and_
)

from sqlalchemy.types import (
    UnicodeText,
    BigInteger,
    Integer,
    DateTime,
    TIMESTAMP,
    Boolean,
    Date
)

from sqlalchemy.ext.declarative import (
    declarative_base,
    declared_attr
)

from sqlalchemy.engine import (
    Engine
)

from zope.sqlalchemy import ZopeTransactionExtension

from passlib.hash import bcrypt

import datetime

import json

from sqlalchemy.inspection import inspect

from sqlalchemy.ext.compiler import compiles

import logging
ENGLISH_LOCALE = 2

log = logging.getLogger(__name__)

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class SLBigInteger(BigInteger):
    pass


@compiles(SLBigInteger, 'sqlite')
def bi_c(element, compiler, **kw):
    return "INTEGER"


@compiles(SLBigInteger)
def bi_c(element, compiler, **kw):
    return compiler.visit_BIGINT(element, **kw)


from collections import deque


# NOT DONE
# def new_recursive_content(self, publish):
#     vec = []
#     # This code may be much faster.
#     first_stack = deque()
#     second_stack = deque()
#     root = self
#     first_stack.append(root)
#     while len(first_stack) > 0:
#         current = first_stack.pop()
#         second_stack.append(current)
#         relationships = inspect(type(current)).relationships
#         for (name, relation) in relationships.items():
#             if relation.direction.name == "ONETOMANY" and hasattr(current, str(name)):
#                 child_list = getattr(current, str(name))
#                 for x in child_list:
#                     first_stack.append(x)
#
#     while len(second_stack) > 0:
#         node = second_stack.pop()
#         locale_id = None
#         additional_metadata = None
#         if hasattr(node, "additional_metadata"):
#             if node.additional_metadata:
#                 additional_metadata = json.loads(node.additional_metadata)
#         if hasattr(node, "locale_id"):
#             locale_id = node.locale_id
#         if hasattr(node, "content"):
#             content = node.content
#         if hasattr(node, "entity_type"):
#             entity_type = node.entity_type
#
#         vec.append({'level': node.__tablename__,
#                     'content': content,
#                     'object_id': node.object_id,
#                     'client_id': node.client_id,
#                     'parent_object_id': node.parent_object_id,
#                     'parent_client_id': node.parent_client_id,
#                     'entity_type': entity_type,
#                     'marked_for_deletion': node.marked_for_deletion,
#                     'locale_id': locale_id,
#                     'additional_metadata': additional_metadata})
#     return vec


def entity_content(xx, publish, root, delete_self=False):
    if delete_self and xx.self_client_id and xx.self_object_id:
        # from pdb import set_trace
        # set_trace()

        return None
    additional_metadata = None
    if hasattr(xx, "additional_metadata"):
        if xx.additional_metadata:
            additional_metadata = json.loads(xx.additional_metadata)  # TODO: check if json.loads json.dumps is excessive
    locale_id = None
    if hasattr(xx, "locale_id"):
        locale_id = xx.locale_id
    contains = list()
    tr_atom = DBSession.query(TranslationAtom).join(TranslationGist, and_(
        TranslationAtom.parent_client_id == TranslationGist.client_id,
        TranslationAtom.parent_object_id == TranslationGist.object_id)).join(Field, and_(
        TranslationGist.client_id == Field.data_type_translation_gist_client_id,
        TranslationGist.object_id == Field.data_type_translation_gist_object_id)).filter(
        Field.client_id == xx.field_client_id, Field.object_id == xx.field_object_id,
        TranslationAtom.locale_id == 2).first()
    if tr_atom.content.lower() == 'link' and root:
        lex_entry = DBSession.query(LexicalEntry).join(Entity, and_(
            Entity.link_client_id == LexicalEntry.client_id,
            Entity.link_object_id == LexicalEntry.object_id)).filter(
            Entity.client_id == xx.client_id, Entity.object_id == xx.object_id).first()
        contains = recursive_content(lex_entry, publish, False)
    # if 'ноготь_БИН.wav ' in xx.content:
    #     from pdb import set_trace
    #     set_trace()
    #     print('sound')

    # if tr_atom.content == 'sound':
        # from pdb import set_trace
        # set_trace()
        # print('sound')
    # if xx.entity:
    #     from pdb import set_trace
    #     set_trace()
    #     print('sound')

    contains += recursive_content(xx, publish, True)  # todo: check nested entities handling
    published = False
    if xx.publishingentity.published:
        published = True
    info = {'level': xx.__tablename__,
            'object_id': xx.object_id,
            'client_id': xx.client_id,
            'parent_object_id': xx.parent_object_id,
            'parent_client_id': xx.parent_client_id,
            'field_client_id': xx.field_client_id,
            'field_object_id': xx.field_object_id,
            'locale_id': locale_id,
            'additional_metadata': additional_metadata,
            'contains': contains,
            'published': published,
            'marked_for_deletion': xx.marked_for_deletion}
    if xx.link_client_id and xx.link_object_id:
        info['link_client_id'] = xx.link_client_id
        info['link_object_id'] = xx.link_object_id
    if xx.content:
        info['content'] = xx.content
    return info


def recursive_content(self, publish, root=True, delete_self=False):  # TODO: completely redo
    """
    :param publish:
    :param root: The value is True if we want to get underlying lexical entries.
    :return:
    """
    vec = list()
    # This code may IS much faster.
    # m = filter(lambda x: x[1].direction.name == "ONETOMANY" and hasattr(self, str(x[0])),
    #            inspect(type(self)).relationships.items())
    # for (name, relationship) in m:
    #     entry_content = getattr(self, str(name))
    #     for xx in entry_content:
    for xx in self.entity:
        info = entity_content(xx, publish, root, delete_self)
        # print(type(info))
        # print(info)
        if not info:
            continue
        if publish and not info['published']:
            continue
        # if info['contains']:
        #     log.debug(info['contains'])
        #     ents = list(info['contains'])
        #     # TODO: check published handling
        vec.append(info)
    return vec


# def recursive_content(self, publish):  # TODO: completely redo
#     import pdb
#     pdb.set_trace()
#     vec = []
#     # This code may IS much faster.
#     m = inspect(type(self)).relationships
#     for (name, relationship) in m.items():
#         if relationship.direction.name == "ONETOMANY" and hasattr(self, str(name)):
#             x = getattr(self, str(name))
#             for xx in x:
#                 additional_metadata = None
#                 if hasattr(xx, "additional_metadata"):
#                     if xx.additional_metadata:
#                         additional_metadata = json.loads(xx.additional_metadata)
#                 locale_id = None
#                 if hasattr(xx, "locale_id"):
#                     locale_id = xx.locale_id
#                 info = {'level': xx.__tablename__,
#                         'content': xx.content,
#                         'object_id': xx.object_id,
#                         'client_id': xx.client_id,
#                         'parent_object_id': xx.parent_object_id,
#                         'parent_client_id': xx.parent_client_id,
#                         # 'entity_type': xx.entity_type,
#                         # 'marked_for_deletion': xx.marked_for_deletion,
#                         'locale_id': locale_id,
#                         'additional_metadata': additional_metadata,
#                         'contains': recursive_content(xx, publish) or None}
#                 published = False
#                 if info['contains']:
#                     log.debug(info['contains'])
#                     ents = []
#                     for ent in info['contains']:
#                         ents += [ent]
#                         # log.debug('CONTAINS', ent)
#                     for ent in ents:
#                         try:
#                             if 'publish' in ent['level']:
#                                 if not ent['marked_for_deletion']:
#                                     published = True
#                                     if not publish:
#                                         break
#                                 if publish:
#                                     info['contains'].remove(ent)
#                         except TypeError:
#                             log.debug('IDK: %s' % str(ent))
#                 if publish:
#                     if not published:
#                         if 'publish' in info['level']:
#                             res = dict()
#                             res['level'] = info['level']
#                             res['marked_for_deletion'] = info['marked_for_deletion']
#                             info = res
#                         else:
#                             continue
#                 info['published'] = published
#                 vec += [info]
#     return vec


# TODO: make this part detecting the engine automatically or from config (need to get after engine_from_config)
# DANGER: This pragma should be turned off for all the bases except sqlite3: it produces unpredictable bugs
# In this variant it leads to overhead on each connection establishment.

# is_sqlite = False
# @event.listens_for(Engine, "connect")
# def set_sqlite_pragma(dbapi_connection, connection_record):
#     if dbapi_connection.__class__.__module__ == "sqlite3":
#         cursor = dbapi_connection.cursor()
#         try:
#             cursor.execute("PRAGMA foreign_keys=ON")
#             cursor.close()
#             is_sqlite = True
#         except:
#             print("It's not an sqlalchemy")


def table_args_method(self, table_args):
    table_args.update(super(type(self), self).__table_args__)
    return table_args


class PrimeTableArgs(object):
    @declared_attr
    def __table_args__(cls):
        return tuple()


class TableNameMixin(object):
    """
    Look forward to:
    http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html
    It's used for automatically set tables names based on class names. Use it everywhere.
    """

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class CreatedAtMixin(object):
    """
    It's used for automatically set created_at column.
    """
    created_at = Column(TIMESTAMP, default=datetime.datetime.utcnow(), nullable=False)


class IdMixin(object):
    """
    It's used for automatically set id as primary key.
    """
    id = Column(SLBigInteger(), primary_key=True, autoincrement=True)
    # __table_args__ = (
    #     dict(
    #         sqlite_autoincrement=True))
    # __remove_this_table_args__ = (
    #     dict(
    #         sqlite_autoincrement=True))


def get_client_counter(check_id):
    DBSession.query(Client).filter_by(id=check_id).update(values={"counter": Client.counter + 1}, synchronize_session='fetch')
    DBSession.flush()
    return DBSession.query(Client).filter_by(id=check_id).with_for_update(of=Client).first()


class CompositeIdMixin(object):
    """
    It's used for automatically set client_id and object_id as composite primary key.
    """
    object_id = Column(SLBigInteger(), primary_key=True, autoincrement=True)
    client_id = Column(SLBigInteger(), primary_key=True)  # SLBigInteger() ? look sqlite sequences

    def __init__(self, **kwargs):
        kwargs.pop("object_id", None)
        client_by_id = get_client_counter(kwargs['client_id'])
        kwargs["object_id"] = client_by_id.counter
        # self.object_id = client_by_id.counter
        # client_by_id.counter = Client.counter + 1

        super().__init__(**kwargs)


class CompositeKeysHelper(object):
    """
    This class with one method is used to declare composite keys connections with composite primary and foreign keys.
    It's very important to use the following naming convention: each class using this mixin should have
    object_id and client_id composite keys as primary and parent_object_id with parent_client_id as composite
    foreign key.
    """
    # Seems to be working
    @classmethod
    def set_table_args_for_simple_fk_composite_key(cls, parent_name):
        return (ForeignKeyConstraint(['parent_object_id', 'parent_client_id'],
                                     [parent_name.lower() + '.object_id', parent_name.lower() + '.client_id']),)


class RelationshipMixin(PrimeTableArgs):
    """
    It's used for automatically set parent attribute as relationship.
    Each class using this mixin should have __parentname__ attribute
    """

    @declared_attr
    def __table_args__(cls):
        return CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(
            parent_name=cls.__parentname__) + super().__table_args__

    @declared_attr
    def parent(cls):
        if cls.__parentname__.lower() == cls.__tablename__.lower():
            return relationship(cls.__parentname__,
                                backref=backref(cls.__tablename__.lower()), remote_side=[cls.client_id, cls.object_id],
                                foreign_keys=[cls.parent_client_id,
                                              cls.parent_object_id])
        else:
            return relationship(cls.__parentname__,
                                backref=backref(cls.__tablename__.lower()),
                                foreign_keys=[cls.parent_client_id,
                                              cls.parent_object_id])

    parent_object_id = Column(SLBigInteger())  # , nullable=False
    parent_client_id = Column(SLBigInteger())  # , nullable=False


class TranslationMixin(PrimeTableArgs):
    translation_gist_client_id = Column(SLBigInteger(), nullable=False)
    translation_gist_object_id = Column(SLBigInteger(), nullable=False)

    @declared_attr
    def __table_args__(cls):
        return (ForeignKeyConstraint(['translation_gist_object_id', 'translation_gist_client_id'],
                                     ['TranslationGist'.lower() + '.object_id',
                                      'TranslationGist'.lower() + '.client_id']),) + super().__table_args__

    def get_translation(self, locale_id):
        from lingvodoc.cache.caching import CACHE

        key = ':'.join([str(self.translation_gist_client_id),
                        str(self.translation_gist_object_id), str(locale_id)])
        translation = CACHE.get(key)
        if translation is not None:
            log.debug("Got cached")
            return translation
        log.debug("No cached value, getting from DB")
        translation = DBSession.query(TranslationAtom).filter_by(parent_client_id=self.translation_gist_client_id,
                                                                 parent_object_id=self.translation_gist_object_id,
                                                                 locale_id=locale_id).first()
        if translation is None:
            log.debug("No value in DB, getting default value")
            key = ':'.join([str(self.translation_gist_client_id),
                            str(self.translation_gist_object_id), str(ENGLISH_LOCALE)])
            translation = CACHE.get(key)
            if translation is not None:
                log.debug("Got cached default value")
                return translation
            log.debug("No cached default value, getting from DB")
            translation = DBSession.query(TranslationAtom).filter_by(parent_client_id=self.translation_gist_client_id,
                                                                     parent_object_id=self.translation_gist_object_id,
                                                                     locale_id=ENGLISH_LOCALE).first()
        if translation is not None:
            log.debug("Got results. Putting the value in the cache")
            CACHE.set(key, translation.content)
            return translation.content
        log.warn("'translationgist' exists but there is no default (english) translation. "
                 "translation_gist_client_id={0}, translation_gist_object_id={1}"
                 .format(self.translation_gist_client_id, self.translation_gist_object_id))
        return "Translation N/A"


class TranslationGist(CompositeIdMixin, Base, TableNameMixin, CreatedAtMixin):
    """
    This is base of translations
    """
    type = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False, nullable=False)


class TranslationAtom(CompositeIdMixin, Base, TableNameMixin, RelationshipMixin, CreatedAtMixin):
    """
    This is translations
    """
    __parentname__ = 'TranslationGist'
    content = Column(UnicodeText, nullable=False)
    locale_id = Column(SLBigInteger(), nullable=False)
    marked_for_deletion = Column(Boolean, default=False, nullable=False)


class Language(CompositeIdMixin, Base, TableNameMixin, CreatedAtMixin, TranslationMixin, RelationshipMixin):
    """
    This is grouping entity that isn't related with dictionaries directly. Locale can have pointer to language.
    """
    __parentname__ = 'Language'
    marked_for_deletion = Column(Boolean, default=False, nullable=False)


class Locale(Base, TableNameMixin, IdMixin, RelationshipMixin, CreatedAtMixin):
    """
    This entity specifies list of available translations (for words in dictionaries and for UI).
    Should be added as admin only.
    """
    __parentname__ = 'Language'
    shortcut = Column(UnicodeText, nullable=False)
    intl_name = Column(UnicodeText, nullable=False)


class StateMixin(PrimeTableArgs):
    @declared_attr
    def __table_args__(cls):
        return (ForeignKeyConstraint(['state_translation_gist_client_id',
                                      'state_translation_gist_object_id'],
                                     ['TranslationGist'.lower() + '.client_id',
                                      'TranslationGist'.lower() + '.object_id']),) + super().__table_args__

    state_translation_gist_client_id = Column(SLBigInteger(), nullable=False)
    state_translation_gist_object_id = Column(SLBigInteger(), nullable=False)


class Dictionary(CompositeIdMixin,
                 Base,
                 TableNameMixin,
                 RelationshipMixin,
                 CreatedAtMixin,
                 TranslationMixin,
                 StateMixin):
    """
    This object presents logical dictionary that indicates separate language. Each dictionary can have many
    perspectives that indicate actual dicts: morphological, etymology etc. Despite the fact that Dictionary object
    indicates separate language (dialect) we want to provide our users an opportunity to have their own dictionaries
    for the same language so we use some grouping. This grouping is provided via Language objects.
    """
    __parentname__ = 'Language'
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    additional_metadata = Column(UnicodeText)
    category = Column(UnicodeText)


class DictionaryPerspective(CompositeIdMixin,
                            Base,
                            TableNameMixin,
                            RelationshipMixin,
                            CreatedAtMixin,
                            TranslationMixin,
                            StateMixin):
    """
    Perspective represents dictionary fields for current usage. For example each Dictionary object can have two
    DictionaryPerspective objects: one for morphological dictionary, one for etymology dictionary. Physically both
    perspectives will use the same database tables for storage but objects that apply to morphology will be have as a
    parent morphological perspective object and that objects that apply to etymology - etymology perspective.
    Each user that creates a language
    Parent: Dictionary.
    """
    __parentname__ = 'Dictionary'
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)
    import_source = Column(UnicodeText)
    import_hash = Column(UnicodeText)
    additional_metadata = Column(UnicodeText)


class SelfMixin(PrimeTableArgs):
    @declared_attr
    def __table_args__(cls):
        return (
            ForeignKeyConstraint(['self_client_id', 'self_object_id'],
                                 [cls.__tablename__.lower() + '.client_id',
                                  cls.__tablename__.lower() + '.object_id']),) + super().__table_args__
    self_client_id = Column(SLBigInteger())
    self_object_id = Column(SLBigInteger())

    @declared_attr
    def upper_level(cls):
        return relationship(cls,
                                    backref=backref(cls.__tablename__.lower()),
                                    remote_side=[cls.client_id,
                                                 cls.object_id])


class FieldMixin(PrimeTableArgs):
    @declared_attr
    def __table_args__(cls):
        return (
            ForeignKeyConstraint(['field_client_id', 'field_object_id'],
                                 ['field' + '.client_id',
                                  'field' + '.object_id']),) + super().__table_args__
    field_client_id = Column(SLBigInteger(), nullable=False)
    field_object_id = Column(SLBigInteger(), nullable=False)

    @declared_attr
    def field(cls):
        return relationship('Field',
                         backref=backref(cls.__tablename__.lower()))


class ParentLinkMixin(PrimeTableArgs):
    @declared_attr
    def __table_args__(cls):
        return (
            ForeignKeyConstraint(['link_client_id', 'link_object_id'],
                                 [cls.__parentname__.lower() + '.client_id',
                                  cls.__parentname__.lower() + '.object_id']),
        ) + super().__table_args__
    link_client_id = Column(SLBigInteger())
    link_object_id = Column(SLBigInteger())

    @declared_attr
    def link(cls):
        return relationship(cls.__parentname__,
                        backref=backref('linked_from'.lower()),
                        foreign_keys=[cls.link_client_id,
                                      cls.link_object_id])


class DictionaryPerspectiveToField(CompositeIdMixin,
                                   Base,
                                   TableNameMixin,
                                   CreatedAtMixin,
                                   RelationshipMixin,
                                   SelfMixin,
                                   FieldMixin,
                                   ParentLinkMixin
                                   ):
    """
    """
    __parentname__ = 'DictionaryPerspective'
    position = Column(Integer, nullable=False)


class DataTypeMixin(PrimeTableArgs):
    """
     Used only by Field. This mixin is needed, because super() can not be used in __table_args__ in
     Field class definition. Sqlalchemy looks through __table_args__ before class is fully initialized,
     so super() does not exist yet.
    """

    @declared_attr
    def __table_args__(cls):
        return (ForeignKeyConstraint(['data_type_translation_gist_client_id',
                                      'data_type_translation_gist_object_id'],
                                     ['TranslationGist'.lower() + '.client_id',
                                      'TranslationGist'.lower() + '.object_id']),) + super().__table_args__
    data_type_translation_gist_client_id = Column(SLBigInteger(), nullable=False)
    data_type_translation_gist_object_id = Column(SLBigInteger(), nullable=False)


class Field(CompositeIdMixin,
            Base,
            TableNameMixin,
            CreatedAtMixin,
            TranslationMixin,
            DataTypeMixin):
    """
    With this objects we specify allowed fields for dictionary perspective. This class is used for three purposes:
        1. To control final web-page view. With it we know which fields belong to perspective (and what we should
          show on dictionary page.
        2. Also we can know what entities should be grouped under the buttons (for example paradigms). Also we can
          control connections between level-one and level-two entities. And we can control grouping entities (if we
          want to have not only etymology connections).
        3. With it we can restrict to use any entity types except listed here (security concerns).
    Parent: DictionaryPerspective.
    """
    # data_type = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    is_translatable = Column(Boolean, default=False, nullable=False)


class LexicalEntry(CompositeIdMixin,
                   Base,
                   TableNameMixin,
                   RelationshipMixin,
                   CreatedAtMixin):
    """
    Objects of this class are used for grouping objects as variations for single lexical entry. Using it we are grouping
    all the variations for a single "word" - each editor can have own version of this word. This class doesn't hold
    any viable data, it's used as a 'virtual' word. Also it contains redirects that occur after dicts merge.
    Parent: DictionaryPerspective.
    """
    __parentname__ = 'DictionaryPerspective'
    moved_to = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False)
    additional_metadata = Column(UnicodeText)

    def track(self, publish):
        vec = []
        vec += recursive_content(self, publish, True, True)
        published = False
        if vec:
            ents = list(vec)
            for ent in ents:
                try:
                    if 'publish' in ent['level']:
                        if not ent['marked_for_deletion']:
                            published = True
                            if not publish:
                                break
                        if publish:
                            vec.remove(ent)
                except:
                    log.debug('IDK: %s' % ent)
        came_from = None
        meta = None
        if self.additional_metadata:
            meta = json.loads(self.additional_metadata)
        if meta:
            if 'came_from' in meta:
                came_from = meta['came_from']
        response = {"level": self.__tablename__,
                    "client_id": self.client_id, "object_id": self.object_id, "contains": vec, "published": published,
                    "parent_client_id": self.parent_client_id,
                    "parent_object_id": self.parent_object_id,
                    "marked_for_deletion": self.marked_for_deletion,
                    "came_from": came_from}
        return response


class Entity(CompositeIdMixin,
             Base,
             TableNameMixin,
             CreatedAtMixin,
             RelationshipMixin,
             SelfMixin,
             FieldMixin,
             ParentLinkMixin):
    __parentname__ = "LexicalEntry"

    content = Column(UnicodeText)
    additional_metadata = Column(UnicodeText)
    locale_id = Column(SLBigInteger())
    marked_for_deletion = Column(Boolean, default=False, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        publishingentity = PublishingEntity(client_id=self.client_id, object_id=self.object_id)
        DBSession.add(publishingentity)
        self.publishingentity = publishingentity

    def track(self, publish):
        return entity_content(self, publish, False)


class PublishingEntity(Base, TableNameMixin, CreatedAtMixin):
    __parentname__ = 'Entity'
    __table_args__ = ((ForeignKeyConstraint(['client_id', 'object_id'],
                                            [__parentname__.lower() + '.client_id',
                                             __parentname__.lower() + '.object_id']),)
                      )

    object_id = Column(SLBigInteger(), primary_key=True)
    client_id = Column(SLBigInteger(), primary_key=True)
    published = Column(Boolean, default=False, nullable=False)
    # approved = Column(Boolean, default=False, nullable=False)
    parent = relationship('Entity', backref=backref("publishingentity", uselist=False))


user_to_group_association = Table('user_to_group_association', Base.metadata,
                                  Column('user_id', BigInteger, ForeignKey('user.id')),
                                  Column('group_id', BigInteger, ForeignKey('group.id'))
                                  )

organization_to_group_association = Table('organization_to_group_association', Base.metadata,
                                          Column('organization_id', BigInteger, ForeignKey('organization.id')),
                                          Column('group_id', BigInteger, ForeignKey('group.id'))
                                          )

user_to_organization_association = Table('user_to_organization_association', Base.metadata,
                                         Column('user_id', BigInteger, ForeignKey('user.id')),
                                         Column('organization_id', BigInteger, ForeignKey('organization.id'))
                                         )


class User(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    login = Column(UnicodeText, unique=True, nullable=False)
    name = Column(UnicodeText)
    # this stands for name in English
    intl_name = Column(UnicodeText, nullable=False)
    additional_metadata = Column(UnicodeText)
    default_locale_id = Column(ForeignKey("locale.id"), default=2, nullable=False)
    birthday = Column(Date)
    # signup_date = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    # it's responsible for "deleted user state". True for active, False for deactivated.
    is_active = Column(Boolean, default=True, nullable=False)
    password = relationship("Passhash", uselist=False)
    # dictionaries = relationship("Dictionary",
    #                             secondary=user_to_dictionary_association, backref=backref("participated"))

    def check_password(self, passwd):
        return bcrypt.verify(passwd, self.password.hash)

        # TODO: last_sync_datetime


class BaseGroup(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    name = Column(UnicodeText, nullable=False)  # readable name
    groups = relationship('Group', backref=backref("BaseGroup"))
    subject = Column(UnicodeText, nullable=False)
    action = Column(UnicodeText, nullable=False)
    dictionary_default = Column(Boolean, default=False, nullable=False)
    perspective_default = Column(Boolean, default=False, nullable=False)


class Group(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    __parentname__ = 'BaseGroup'
    base_group_id = Column(ForeignKey("basegroup.id"), nullable=False)
    subject_client_id = Column(SLBigInteger())
    subject_object_id = Column(SLBigInteger())
    subject_override = Column(Boolean, default=False)
    users = relationship("User",
                         secondary=user_to_group_association,
                         backref=backref("groups"))
    organizations = relationship("Organization",
                                 secondary=organization_to_group_association,
                                 backref=backref("groups"))
    parent = relationship(__parentname__, backref=backref('group'))


class Organization(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    name = Column(UnicodeText)
    users = relationship("User",
                         secondary=user_to_organization_association,
                         backref=backref("organizations"))
    about = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    # locale_id = Column(ForeignKey("locale.id"))


class Passhash(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    user_id = Column(SLBigInteger(), ForeignKey('user.id'), nullable=False)
    hash = Column(UnicodeText, nullable=False)

    def __init__(self, password):
        self.hash = bcrypt.encrypt(password)


class Email(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    user_id = Column(SLBigInteger(), ForeignKey('user.id'), nullable=False)
    email = Column(UnicodeText, unique=True)
    user = relationship("User", backref=backref('email', uselist=False))


class Client(Base, TableNameMixin, IdMixin, CreatedAtMixin):
    user_id = Column(SLBigInteger(), ForeignKey('user.id'), nullable=False)
    # creation_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_browser_client = Column(Boolean, default=True, nullable=False)
    user = relationship("User", backref='clients')
    counter = Column(SLBigInteger(), default=1, nullable=False)


class UserBlobs(CompositeIdMixin, Base, TableNameMixin, CreatedAtMixin):  # TODO: decide what is nullable
    name = Column(UnicodeText, nullable=False)
    # content holds url for the object
    content = Column(UnicodeText, nullable=False)
    real_storage_path = Column(UnicodeText, nullable=False)
    data_type = Column(UnicodeText, nullable=False)
    additional_metadata = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False)
    # created_at = Column(DateTime, default=datetime.datetime.utcnow)
    user_id = Column(SLBigInteger(), ForeignKey('user.id'))
    user = relationship("User", backref='userblobs')


def acl_by_groups(object_id, client_id, subject):
    acls = []  # DANGER if acls do not work -- uncomment string below
    # acls += [(Allow, Everyone, ALL_PERMISSIONS)]
    groups = DBSession.query(Group).filter_by(subject_override=True).join(BaseGroup).filter_by(subject=subject).all()
    if client_id and object_id:
        if subject in ['perspective', 'approve_entities', 'lexical_entries_and_entities', 'other perspective subjects']:
            persp = DBSession.query(DictionaryPerspective).filter_by(client_id=client_id, object_id=object_id).first()
            if persp:
                if persp.state == 'Published':
                    acls += [(Allow, Everyone, 'view')]
        elif subject in ['dictionary', 'other dictionary subjects']:
            dict = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
            if dict:
                if dict.state == 'Published':
                    acls += [(Allow, Everyone, 'view')]
    groups += DBSession.query(Group).filter_by(subject_client_id=client_id, subject_object_id=object_id). \
        join(BaseGroup).filter_by(subject=subject).all()
    for group in groups:
        base_group = group.parent
        if group.subject_override:
            group_name = base_group.action + ":" + base_group.subject + ":" + str(group.subject_override)
        else:
            group_name = base_group.action + ":" + base_group.subject \
                         + ":" + str(group.subject_client_id) + ":" + str(group.subject_object_id)
        acls += [(Allow, group_name, base_group.action)]
    log.debug("ACLS: %s", acls)
    return acls


def acl_by_groups_single_id(object_id, subject):
    acls = []  # DANGER if acls do not work -- uncomment string below
    # acls += [(Allow, Everyone, ALL_PERMISSIONS)]
    groups = DBSession.query(Group).filter_by(subject_override=True).join(BaseGroup).filter_by(subject=subject).all()
    groups += DBSession.query(Group).filter_by(subject_client_id=None, subject_object_id=object_id). \
        join(BaseGroup).filter_by(subject=subject).all()
    for group in groups:
        base_group = group.parent
        if group.subject_override:
            group_name = base_group.action + ":" + base_group.subject + ":" + str(group.subject_override)
        else:
            group_name = base_group.action + ":" + base_group.subject \
                         + ":" + str(group.subject_object_id)
        acls += [(Allow, group_name, base_group.action)]
    log.debug("ACLS: %s", acls)
    return acls


class LanguageAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'language')


class AdminAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = [(Allow, 'Admin', ALL_PERMISSIONS)]
        return acls


class PerspectiveAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        client_id = None
        try:
            client_id = self.request.matchdict['perspective_client_id']
        except:
            pass
        object_id = None
        try:
            object_id = self.request.matchdict['perspective_object_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'perspective')


class PerspectiveCreateAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        client_id = None
        try:
            client_id = self.request.matchdict['dictionary_client_id']
        except:
            pass
        object_id = None
        try:
            object_id = self.request.matchdict['dictionary_object_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'perspective')


class OrganizationAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        organization_id = None
        try:
            organization_id = self.request.matchdict['organization_id']
        except:
            pass
        return acls + acl_by_groups_single_id(organization_id, 'organization')


class DictionaryAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'dictionary')


class DictionaryIdsWithPrefixAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['dictionary_perspective_object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['dictionary_perspective_client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'dictionary')


class DictionaryRolesAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'dictionary_role')


class PerspectiveRolesAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['perspective_object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['perspective_client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'perspective_role')


class CreateLexicalEntriesEntitiesAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['perspective_object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['perspective_client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'lexical_entries_and_entities')


class LexicalEntriesEntitiesAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['perspective_object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['perspective_client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'lexical_entries_and_entities')


# class PerspectiveEntityOneAcl(object):
#     def __init__(self, request):
#         self.request = request
# #
#     def __acl__(self):
#         acls = []
#         object_id = None
#         try:
#             object_id = self.request.matchdict['object_id']
#         except:
#             pass
#         client_id = None
#         try:
#             client_id = self.request.matchdict['client_id']
#         except:
#             pass
#         levoneent = DBSession.query(LevelOneEntity).filter_by(client_id=client_id, object_id=object_id).first()
#         perspective = levoneent.parent.parent
#         return acls + acl_by_groups(perspective.object_id, perspective.client_id, 'lexical_entries_and_entities')
#
#
# class PerspectiveEntityTwoAcl(object):
#     def __init__(self, request):
#         self.request = request
#
#     def __acl__(self):
#         acls = []
#         object_id = None
#         try:
#             object_id = self.request.matchdict['object_id']
#         except:
#             pass
#         client_id = None
#         try:
#             client_id = self.request.matchdict['client_id']
#         except:
#             pass
#         levoneent = DBSession.query(LevelTwoEntity).filter_by(client_id=client_id, object_id=object_id).first()
#         perspective = levoneent.parent.parent.parent
#         return acls + acl_by_groups(perspective.object_id, perspective.client_id, 'lexical_entries_and_entities')


# class PerspectiveEntityGroupAcl(object):
#     def __init__(self, request):
#         self.request = request
#
#     def __acl__(self):
#         acls = []
#         object_id=None
#         try:
#             object_id = self.request.matchdict['object_id']
#         except:
#             pass
#         client_id=None
#         try:
#             client_id = self.request.matchdict['client_id']
#         except:
#             pass
#         group_ent = DBSession.query(GroupingEntity).filter_by(client_id=client_id, object_id=object_id).first()
#         perspective = group_ent.parent.parent
#         return acls + acl_by_groups(perspective.object_id, perspective.client_id, 'lexical_entries_and_entities')


class PerspectivePublishAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['perspective_object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['perspective_client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'approve_entities')


class PerspectiveLexicalViewAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['perspective_object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['perspective_client_id']
        except:
            pass
        return acls + acl_by_groups(object_id, client_id, 'lexical_entries_and_entities')


class LexicalViewAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = []
        object_id = None
        try:
            object_id = self.request.matchdict['object_id']
        except:
            pass
        client_id = None
        try:
            client_id = self.request.matchdict['client_id']
        except:
            pass
        lex = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
        parent = lex.parent
        return acls + acl_by_groups(parent.object_id, parent.client_id, 'lexical_entries_and_entities')


class ApproveAllAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        return [(Allow, Everyone, ALL_PERMISSIONS)]
