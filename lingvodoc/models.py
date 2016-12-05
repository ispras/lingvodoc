from pyramid.security import Allow, Authenticated, ALL_PERMISSIONS, Everyone

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
    query,
    aliased
)

from sqlalchemy.sql import text

from sqlalchemy import (
    Column,
    Index,
    ForeignKeyConstraint,
    event,
    ForeignKey,
    Table,
    UniqueConstraint,
    and_,
    tuple_
)

from sqlalchemy.types import (
    UnicodeText,
    VARCHAR,
    BigInteger,
    Integer,
    DateTime,
    TIMESTAMP,
    Boolean,
    Date,
    TypeDecorator
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

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

import uuid

RUSSIAN_LOCALE = 1
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

categories = {0: 'lingvodoc.ispras.ru/dictionary',
              1: 'lingvodoc.ispras.ru/corpora'}


from collections import deque


def entity_content(xx, publish, root, delete_self=False):
    publishing_entity = xx.publishingentity
    published = publishing_entity.published
    accepted = publishing_entity.accepted
    if publish and not published:
        return None

    if delete_self and xx.self_client_id and xx.self_object_id:
        # from pdb import set_trace
        # set_trace()

        return None
    additional_metadata = xx.additional_metadata
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
    contains += recursive_content(xx, publish, True)  # todo: check nested entities handling
    info = {'level': xx.__tablename__,
            'object_id': xx.object_id,
            'client_id': xx.client_id,
            'parent_object_id': xx.parent_object_id,
            'parent_client_id': xx.parent_client_id,
            'field_client_id': xx.field_client_id,
            'field_object_id': xx.field_object_id,
            'locale_id': locale_id,
            'data_type': xx.field.data_type,
            'additional_metadata': additional_metadata,
            'contains': contains,
            'published': published,
            'accepted': accepted,
            'marked_for_deletion': xx.marked_for_deletion,
            'created_at': str(xx.created_at),
            'entity_type':xx.field.get_translation(2)}
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
    for xx in self.entity:
        info = entity_content(xx, publish, root, delete_self)
        if not info:
            continue
        # if publish and not info['published']:
        #     continue
        vec.append(info)
    return vec



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


class AdditionalMetadataMixin(object):
    additional_metadata = Column(JSONB)


class TableNameMixin(object):
    """
    Look forward to:
    http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html
    It's used for automatically set tables names based on class names. Use it everywhere.
    """

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class EpochType(TypeDecorator):
    impl = TIMESTAMP

    def process_result_value(self, value, dialect):
        return int(value.timestamp())

    def process_bind_param(self, value, dialect):
        if type(value) == int:
            return datetime.datetime.fromtimestamp(value)
        return value

class EpochTypeForDate(TypeDecorator):
    impl = Date

    def process_result_value(self, value, dialect):
        if value:
            return str(value)
        else:
            return None

class UUIDType(TypeDecorator):
    impl = UUID(as_uuid=True)

    def process_result_value(self, value, dialect):
        if value:
            return str(value)
        else:
            return None

    def process_bind_param(self, value, dialect):
        if type(value) == str:
            return uuid.UUID(value)
        return value


class CreatedAtMixin(object):
    """
    It's used for automatically set created_at column.
    """
    created_at = Column(EpochType, default=datetime.datetime.utcnow(), nullable=False)


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


class ObjectTOC(Base, TableNameMixin):
    """
    This is base of translations
    """
    object_id = Column(SLBigInteger(), primary_key=True)
    client_id = Column(SLBigInteger(), primary_key=True)
    table_name = Column(UnicodeText, nullable=False)


class CompositeIdMixin(object):
    """
    It's used for automatically set client_id and object_id as composite primary key.
    """
    object_id = Column(SLBigInteger(), primary_key=True, autoincrement=True)
    client_id = Column(SLBigInteger(), primary_key=True)

    def __init__(self, **kwargs):
        if not kwargs.get("object_id", None):
            client_by_id = get_client_counter(kwargs['client_id'])
            kwargs["object_id"] = client_by_id.counter
        DBSession.add(ObjectTOC(client_id=kwargs['client_id'],
                                object_id=kwargs['object_id'],
                                table_name=self.__tablename__))
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

        main_locale = locale_id
        fallback_locale = ENGLISH_LOCALE if locale_id != str(ENGLISH_LOCALE) else RUSSIAN_LOCALE

        key = ':'.join([str(self.translation_gist_client_id),
                        str(self.translation_gist_object_id), str(main_locale)])
        translation = CACHE.get(key)
        if translation is not None:
            log.debug("Got cached")
            return translation
        log.debug("No cached value, getting from DB")
        translation = DBSession.query(TranslationAtom.content).filter_by(parent_client_id=self.translation_gist_client_id,
                                                                 parent_object_id=self.translation_gist_object_id,
                                                                 locale_id=main_locale).first()
        if not translation:
            log.debug("No value in DB, getting default value")
            key = ':'.join([str(self.translation_gist_client_id),
                            str(self.translation_gist_object_id), str(fallback_locale)])
            translation = CACHE.get(key)
            if translation is not None:
                log.debug("Got cached default value")
                return translation
            log.debug("No cached default value, getting from DB")
            translation = DBSession.query(TranslationAtom.content).filter_by(parent_client_id=self.translation_gist_client_id,
                                                                     parent_object_id=self.translation_gist_object_id,
                                                                     locale_id=fallback_locale).first()
        if translation:
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
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    type = Column(UnicodeText)


class TranslationAtom(CompositeIdMixin, Base, TableNameMixin, RelationshipMixin, CreatedAtMixin,
                      AdditionalMetadataMixin):
    """
    This is translations
    """
    __parentname__ = 'TranslationGist'
    locale_id = Column(SLBigInteger(), nullable=False)
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    content = Column(UnicodeText, nullable=False)


class Language(CompositeIdMixin, Base, TableNameMixin, CreatedAtMixin, TranslationMixin, RelationshipMixin,
               AdditionalMetadataMixin):
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

    @property
    def state(self):
        return DBSession.query(TranslationAtom.content).filter_by(
        parent_client_id=self.state_translation_gist_client_id,
        parent_object_id=self.state_translation_gist_object_id,
        locale_id=2).scalar()


class Dictionary(CompositeIdMixin,
                 Base,
                 TableNameMixin,
                 RelationshipMixin,
                 CreatedAtMixin,
                 TranslationMixin,
                 StateMixin,
                 AdditionalMetadataMixin):
    """
    This object presents logical dictionary that indicates separate language. Each dictionary can have many
    perspectives that indicate actual dicts: morphological, etymology etc. Despite the fact that Dictionary object
    indicates separate language (dialect) we want to provide our users an opportunity to have their own dictionaries
    for the same language so we use some grouping. This grouping is provided via Language objects.
    """
    __parentname__ = 'Language'
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    category = Column(Integer, default=0)
    domain = Column(Integer, default=0)

class DictionaryPerspective(CompositeIdMixin,
                            Base,
                            TableNameMixin,
                            RelationshipMixin,
                            CreatedAtMixin,
                            TranslationMixin,
                            StateMixin,
                            AdditionalMetadataMixin):
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
    marked_for_deletion = Column(Boolean, default=False)


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

    @property
    def data_type(self):
        return DBSession.query(TranslationAtom.content).filter_by(
        parent_client_id=self.data_type_translation_gist_client_id,
        parent_object_id=self.data_type_translation_gist_object_id,
        locale_id=2).scalar()


class Field(CompositeIdMixin,
            Base,
            TableNameMixin,
            CreatedAtMixin,
            TranslationMixin,
            DataTypeMixin,
            AdditionalMetadataMixin):
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
    marked_for_deletion = Column(Boolean, default=False, nullable=False)
    is_translatable = Column(Boolean, default=False, nullable=False)


class LexicalEntry(CompositeIdMixin,
                   Base,
                   TableNameMixin,
                   RelationshipMixin,
                   CreatedAtMixin,
                   AdditionalMetadataMixin):
    """
    Objects of this class are used for grouping objects as variations for single lexical entry. Using it we are grouping
    all the variations for a single "word" - each editor can have own version of this word. This class doesn't hold
    any viable data, it's used as a 'virtual' word. Also it contains redirects that occur after dicts merge.
    Parent: DictionaryPerspective.
    """
    __parentname__ = 'DictionaryPerspective'
    moved_to = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False)

    def track(self, publish, locale_id):
        metadata = self.additional_metadata if self.additional_metadata else None
        came_from = metadata.get('came_from') if metadata and 'came_from' in metadata else None

        lexes_composite_list = [(self.client_id, self.object_id, self.parent_client_id, self.parent_object_id,
                                 self.marked_for_deletion, metadata, came_from)]

        res_list = self.track_multiple(publish, lexes_composite_list, locale_id)

        return res_list[0] if res_list else {}

    @classmethod
    def track_multiple(cls, publish, lexs, locale_id):
        log.debug(lexs)
        ls = []
        for i, x in enumerate(lexs):
            ls.append({'traversal_lexical_order': i, 'client_id': x[0], 'object_id': x[1]})

        if not ls:
            return []

        temp_table_name = 'lexical_entries_temp_table' + str(uuid.uuid4()).replace("-", "")

        DBSession.execute('''create TEMPORARY TABLE %s (traversal_lexical_order INTEGER, client_id BIGINT, object_id BIGINT) on COMMIT DROP;''' % temp_table_name)

        DBSession.execute('''insert into %s (traversal_lexical_order, client_id, object_id) values (:traversal_lexical_order, :client_id, :object_id);''' % temp_table_name, ls)

        result = DBSession.execute(text('''
        WITH RECURSIVE cte_expr AS
        (SELECT
           entity.*,
           %s.traversal_lexical_order                                  AS traversal_lexical_order,
           1                                                                                   AS tree_level,
            row_number() over(partition by traversal_lexical_order order by Entity.created_at) as tree_numbering_scheme
         FROM entity
           INNER JOIN %s
             ON
               entity.parent_client_id = %s.client_id
               AND entity.parent_object_id = %s.object_id

         UNION ALL
         SELECT
           entity.*,
           cte_expr.traversal_lexical_order,
           tree_level + 1,
           cte_expr.tree_numbering_scheme
         FROM entity
           INNER JOIN cte_expr
             ON (cte_expr.client_id = entity.self_client_id AND cte_expr.object_id = entity.self_object_id)
         WHERE tree_level <= 10
        )

        SELECT
          cte_expr.*,
          COALESCE (data_type_atom.content, data_type_atom_fallback.content) as data_type,
          COALESCE (entity_type_atom.content, entity_type_atom_fallback.content) as entity_type,
          publishingentity.accepted,
          publishingentity.published
        FROM cte_expr
          LEFT JOIN publishingentity
            ON publishingentity.client_id = cte_expr.client_id AND publishingentity.object_id = cte_expr.object_id
          LEFT JOIN field
            ON cte_expr.field_client_id = field.client_id AND cte_expr.field_object_id = field.object_id
          LEFT JOIN translationgist AS field_translation_gist
            ON (field.translation_gist_client_id = field_translation_gist.client_id AND
                field.translation_gist_object_id = field_translation_gist.object_id)
          LEFT JOIN translationgist AS data_type_translation_gist
            ON (field.data_type_translation_gist_client_id = data_type_translation_gist.client_id AND
                field.data_type_translation_gist_object_id = data_type_translation_gist.object_id)
          LEFT JOIN translationatom AS entity_type_atom
            ON field_translation_gist.client_id = entity_type_atom.parent_client_id AND
               field_translation_gist.object_id = entity_type_atom.parent_object_id AND
               entity_type_atom.locale_id = :locale
          LEFT JOIN translationatom AS entity_type_atom_fallback
            ON field_translation_gist.client_id = entity_type_atom_fallback.parent_client_id AND
               field_translation_gist.object_id = entity_type_atom_fallback.parent_object_id AND
               entity_type_atom_fallback.locale_id = 1
          LEFT JOIN translationatom AS data_type_atom
            ON data_type_translation_gist.client_id = data_type_atom.parent_client_id AND
               data_type_translation_gist.object_id = data_type_atom.parent_object_id AND
               data_type_atom.locale_id = :locale
          LEFT JOIN translationatom AS data_type_atom_fallback
            ON data_type_translation_gist.client_id = data_type_atom_fallback.parent_client_id AND
               data_type_translation_gist.object_id = data_type_atom_fallback.parent_object_id AND
               data_type_atom_fallback.locale_id = 1

        ORDER BY traversal_lexical_order, tree_numbering_scheme, tree_level;
        ''' % (temp_table_name, temp_table_name, temp_table_name, temp_table_name)), {'locale': locale_id})

        entries = result.fetchall()

        def remove_keys(obj, rubbish):
            if isinstance(obj, dict):
                obj = {
                    key: remove_keys(value, rubbish)
                    for key, value in obj.items()
                    if key not in rubbish and value is not None}
            elif isinstance(obj, list):
                obj = [remove_keys(item, rubbish)
                       for item in obj
                       if item not in rubbish]
            return obj

        lexical_list = []
        for k in lexs:
            a = []
            entry = {
                'client_id': k[0],
                'object_id': k[1],
                'parent_client_id': k[2],
                'parent_object_id': k[3],
                'contains': a,
                'marked_for_deletion': k[4],
                'additional_metadata': k[5],
                'came_from': k[6],
                'level': 'lexicalentry',
                'published': False
            }

            prev_nodegroup = -1
            for i in entries:
                if i['parent_client_id'] != k[0] or i['parent_object_id'] != k[1]:
                    continue
                cur_nodegroup = i['tree_numbering_scheme'] if prev_nodegroup != i['tree_numbering_scheme'] else prev_nodegroup
                dictionary_form = dict(i)
                dictionary_form['created_at'] = str(i['created_at'])
                dictionary_form['level'] = 'entity'
                dictionary_form['contains'] = []
                if not dictionary_form.get('locale_id'):
                    dictionary_form['locale_id'] = 0
                if cur_nodegroup != prev_nodegroup:
                    prev_dictionary_form = dictionary_form
                else:
                    prev_dictionary_form['contains'].append(dictionary_form)
                    continue
                a.append(dictionary_form)
                prev_nodegroup = cur_nodegroup
            # TODO: published filtering
            # TODO: locale fallback
            lexical_list.append(entry)
        lexical_list = remove_keys(lexical_list, ['traversal_lexical_order', 'tree_level', 'tree_numbering_scheme'])
        log.debug(lexical_list)
        DBSession.execute('''drop TABLE %s''' % temp_table_name)

        return lexical_list


class Entity(CompositeIdMixin,
             Base,
             TableNameMixin,
             CreatedAtMixin,
             RelationshipMixin,
             SelfMixin,
             FieldMixin,
             ParentLinkMixin,
             AdditionalMetadataMixin):
    __parentname__ = "LexicalEntry"

    content = Column(UnicodeText)
    locale_id = Column(SLBigInteger())
    marked_for_deletion = Column(Boolean, default=False, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        publishingentity = PublishingEntity(client_id=self.client_id, object_id=self.object_id,
                                            created_at=self.created_at)
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
    accepted = Column(Boolean, default=False, nullable=False)
    parent = relationship('Entity', backref=backref("publishingentity", uselist=False))


user_to_group_association = Table('user_to_group_association', Base.metadata,
                                  Column('user_id', SLBigInteger(), ForeignKey('user.id')),
                                  Column('group_id', UUIDType, ForeignKey('group.id'))
                                  )

organization_to_group_association = Table('organization_to_group_association', Base.metadata,
                                          Column('organization_id', SLBigInteger(), ForeignKey('organization.id')),
                                          Column('group_id', UUIDType, ForeignKey('group.id'))
                                          )

user_to_organization_association = Table('user_to_organization_association', Base.metadata,
                                         Column('user_id', SLBigInteger(), ForeignKey('user.id')),
                                         Column('organization_id', SLBigInteger(), ForeignKey('organization.id'))
                                         )


class User(Base, TableNameMixin, IdMixin, CreatedAtMixin, AdditionalMetadataMixin):
    login = Column(UnicodeText, unique=True, nullable=False)
    name = Column(UnicodeText)
    # this stands for name in English
    intl_name = Column(UnicodeText, nullable=False)
    default_locale_id = Column(ForeignKey("locale.id"), default=2, nullable=False)
    birthday = Column(EpochTypeForDate)
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


class Group(Base, TableNameMixin, CreatedAtMixin):
    __parentname__ = 'BaseGroup'
    # old_id = Column(SLBigInteger(), autoincrement=True)
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
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


class Client(Base, TableNameMixin, IdMixin, CreatedAtMixin, AdditionalMetadataMixin):
    user_id = Column(SLBigInteger(), ForeignKey('user.id'), nullable=False)
    # creation_time = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    is_browser_client = Column(Boolean, default=True, nullable=False)
    user = relationship("User", backref='clients')
    counter = Column(SLBigInteger(), default=1, nullable=False)

    @classmethod
    def get_user_by_client_id(cls, client_id):
        if client_id:
            client = DBSession.query(Client).filter(Client.id == client_id).first()
            if client:
                return client.user
            else:
                return None
        else:
            return None


class UserBlobs(CompositeIdMixin, Base, TableNameMixin, CreatedAtMixin, AdditionalMetadataMixin):  # TODO: decide what is nullable
    name = Column(UnicodeText, nullable=False)
    # content holds url for the object
    content = Column(UnicodeText, nullable=False)
    real_storage_path = Column(UnicodeText, nullable=False)
    data_type = Column(UnicodeText, nullable=False)
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
                if persp.state == 'Published' or persp.state == 'Limited access':
                    acls += [(Allow, Everyone, 'view'), (Allow, Everyone, 'preview')]
        elif subject in ['dictionary', 'other dictionary subjects']:
            dicty = DBSession.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).first()
            if dicty:
                if dicty.state == 'Published' or dicty.state == 'Limited access':
                    acls += [(Allow, Everyone, 'view'), (Allow, Everyone, 'preview')]
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
    log.debug("ACLS: %s", acls)  # todo: caching
    # log.error("ACLS: %s", acls)
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
    log.debug("ACLS: %s", acls)  # todo: caching
    # log.error("ACLS: %s", acls)
    return acls


class ACLMixin(object):
    @classmethod
    def get_subject(cls):
        return cls.subject

    def __acl__(self):
        object_id = self.request.matchdict.get(self.object_id, None)
        client_id = self.request.matchdict.get(self.client_id, None)
        return acl_by_groups(object_id, client_id, self.subject)

    def __init__(self, request):
        self.request = request


class SimpleAclMixin(object):
    def get_subject(self):
        return self.subject

    def __acl__(self):
        id = self.request.matchdict.get(self.id, None)
        return acl_by_groups_single_id(id, self.subject)

    def __init__(self, request):
        self.request = request


class LanguageAcl(ACLMixin):
    subject = 'language'
    client_id = 'client_id'
    object_id = 'object_id'


class AdminAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = [(Allow, 'Admin', ALL_PERMISSIONS)]
        return acls


class PerspectiveAcl(ACLMixin):
    subject = 'perspective'
    client_id = 'perspective_client_id'
    object_id = 'perspective_object_id'


class PerspectiveCreateAcl(ACLMixin):
    subject = 'perspective'
    client_id = 'dictionary_client_id'
    object_id = 'dictionary_object_id'


class OrganizationAcl(ACLMixin):
    subject = 'organization'
    id = 'organization_id'


class DictionaryAcl(ACLMixin):
    subject = 'dictionary'
    client_id = 'client_id'
    object_id = 'object_id'


class DictionaryRolesAcl(ACLMixin):
    subject = 'dictionary_role'
    client_id = 'client_id'
    object_id = 'object_id'


class PerspectiveRolesAcl(ACLMixin):
    subject = 'perspective_role'
    client_id = 'perspective_client_id'
    object_id = 'perspective_object_id'


class CreateLexicalEntriesEntitiesAcl(ACLMixin):
    subject = 'lexical_entries_and_entities'
    client_id = 'perspective_client_id'
    object_id = 'perspective_object_id'


class LexicalEntriesEntitiesAcl(ACLMixin):
    subject = 'lexical_entries_and_entities'
    client_id = 'perspective_client_id'
    object_id = 'perspective_object_id'


class TranslationAcl(ACLMixin):
    subject = 'translations'
    client_id = 'client_id'
    object_id = 'object_id'


class AuthenticatedAcl(ACLMixin):
    subject = 'no op subject'

    def __acl__(self):
        return [(Allow, Authenticated, ALL_PERMISSIONS)]


class RootAcl(ACLMixin):
    subject = 'no op subject'

    def __acl__(self):
        return []


class PerspectiveEntityAcl(ACLMixin):
    subject = 'lexical_entries_and_entities'

    def __acl__(self):
        object_id = self.request.matchdict.get('object_id', None)
        client_id = self.request.matchdict.get('client_id', None)
        levoneent = DBSession.query(Entity).filter_by(client_id=client_id, object_id=object_id).first()
        perspective = levoneent.parent.parent
        return acl_by_groups(perspective.object_id, perspective.client_id, self.subject)


class PerspectivePublishAcl(ACLMixin):
    subject = 'approve_entities'
    client_id = 'perspective_client_id'
    object_id = 'perspective_object_id'


class LexicalViewAcl(ACLMixin):
    subject = 'lexical_entries_and_entities'

    def __acl__(self):
        acls = []
        object_id = self.request.matchdict['object_id']
        client_id = self.request.matchdict['client_id']

        lex = DBSession.query(LexicalEntry).filter_by(client_id=client_id, object_id=object_id).first()
        parent = lex.parent
        return acls + acl_by_groups(parent.object_id, parent.client_id, self.subject)


class ApproveAllAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        return [(Allow, Everyone, ALL_PERMISSIONS)]
