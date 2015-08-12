from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
    query,
)

from sqlalchemy import (
    Column,
    ForeignKeyConstraint,
)

from sqlalchemy.types import (
    UnicodeText,
    BigInteger,
    DateTime,
    Boolean,
)

from sqlalchemy.ext.declarative import (
    declarative_base,
    declared_attr
)

from zope.sqlalchemy import ZopeTransactionExtension

from passlib.hash import bcrypt

import datetime

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

class TableNameMixin(object):
    """
    Look forward to:
    http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html

    It's used for automatically set tables names based on class names. Use it everywhere.
    """
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class CompositeKeysHelper(object):
    """
    This class with one method is used to declare composite keys connections with composite primary and foreign keys.
    It's very important to use the following naming convention: each class using this mixin should have
    object_id and client_id composite keys as primary and parent_object_id with parent_client_id as composite
    foreign key.

    TODO: check if it even works (not sure)
    """

    @classmethod
    def set_table_args_for_simple_fk_composite_key(cls, parent_name):
        return (ForeignKeyConstraint(['parent_object_id', 'parent_client_id'],
                                     [parent_name.lower()+'.object_id', parent_name.lower()+'.client_id']),)

    # This is used for classes that correspond to publishing words. Need to check if it even works.
    @classmethod
    def set_table_args_for_publishing_fk_composite_key(cls, parent_name, entity_name):
        return (ForeignKeyConstraint(['parent_object_id', 'parent_client_id'],
                                     [parent_name.lower()+'.object_id', parent_name.lower()+'.client_id']),
                ForeignKeyConstraint(['entity_object_id', 'entity_client_id'],
                                     [entity_name.lower()+'.object_id', entity_name.lower()+'.client_id']))



class Language(Base, TableNameMixin):
    """
    This is grouping entity that isn't related with dictionaries directly. Locale can have pointer to language.
    """
    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)
    translation_string = Column(UnicodeText(length=2**31))

    
class Locale(Base):
    """
    This entity specifies list of available translations (for words in dictionaries and for UI).
    Should be added as admin only.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Language")
    id = Column(BigInteger, primary_key=True)
    language_object_id = Column(BigInteger)
    language_client_id = Column(BigInteger)
    shortcut = Column(UnicodeText)
    intl_name = Column(UnicodeText(length=2**31))


class UITranslationString(Base):
    """
    This table holds translation strings for UI. If couldn't be found by pair, should be searched by translation string.
    Should be used as admin only.
    """
    id = Column(BigInteger, primary_key=True)
    locale_id = Column(BigInteger)
    translation_string = Column(UnicodeText(length=2**31))
    translation = Column(UnicodeText(length=2**31))


class UserEntitiesTranslationString(Base):
    """
    This table holds translation strings for user-created entities such as dictionaries names, column names etc.
    Separate classes are needed not to allow users to interfere UI directly.
    Not intended to use for translations inside the dictionaries (these translations are hold inside entities tables).
    """
    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)

    locale_id = Column(BigInteger)
    translation_string = Column(UnicodeText(length=2**31))
    translation = Column(UnicodeText(length=2**31))


class Dictionary(Base):
    """
    This object presents logical dictionary that indicates separate language. Each dictionary can have many
    perspectives that indicate actual dicts: morphological, etymology etc. Despite the fact that Dictionary object
    indicates separate language (dialect) we want to provide our users an opportunity to have their own dictionaries
    for the same language so we use some grouping. This grouping is provided via Language objects.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Language")
    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)


class DictionaryPerspective(Base):
    """
    Perspective represents dictionary fields for current usage. For example each Dictionary object can have two
    DictionaryPerspective objects: one for morphological dictionary, one for etymology dictionary. Physically both
    perspectives will use the same database tables for storage but objects that apply to morphology will be have as a
    parent morphological perspective object and that objects that apply to etymology - etymology perspective.
    Each user that creates a language
    Parent: Dictionary.
    """

    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Dictionary")
    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    state = Column(UnicodeText)


class DictionaryPerspectiveField(Base):
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
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="DictionaryPerspective")
    object_id = Column(BigInteger)
    client_id = Column(BigInteger)
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    entity_type = Column(UnicodeText(length=2**31))
    level = Column(BigInteger)
    parent_entity = Column(UnicodeText(length=2**31))
    group = Column(UnicodeText(length=2**31))


class LexicalEntry(Base):
    """
    Objects of this class are used for grouping objects as variations for single lexical entry. Using it we are grouping
    all the variations for a single "word" - each editor can have own version of this word. This class doesn't hold
    any viable data, it's used as a 'virtual' word. Also it contains redirects that occur after dicts merge.
    Parent: DictionaryPerspective.
    """
    __table_attrs__ = CompositeKeyConstraint.set_table_args(parent_name="DictionaryPerspective")
    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)




class EntityMixin(object):
    """
    Look forward to:
    http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html

    This mixin groups common fields and operations for *Entity classes.
    It makes sense to include __acl__ rules right here for code deduplication.
    """

    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    entity_type = Column(UnicodeText)
    content = Column(UnicodeText(length=2**31))
    additional_metadata = Column(UnicodeText(length=2**31))
    is_translatable = Column(Boolean, default=False)
    locale_id = Column(BigInteger)
    marked_for_deletion = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)



class LevelOneEntity(Base, TableNameMixin, EntityMixin):
    """
    This type of entity is used for level-one word entries (e.g. transcription, translation, sounds,
    paradigm transcription, etc). The main convention for this type is to have word entry as a logical parent.
    Some entity types should provide special behaviour - for example sounds: as a content they should store path
    for the stored object (not the sound file itself). One more special type: translation should point locale_id.
    Parent: LexicalEntry.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="LexicalEntry")



class LevelTwoEntity(Base, TableNameMixin, EntityMixin):
    """
    This type of entity is used as level-two entity: logically it has as parent a level-one entity object. For
    now there is the only type of such entities - it's praat markup because it can not be separated from sound
    it belongs to. Each type of such entity most likely will have it's own behaviour. For now the markup should
    be stored separately and as content it should store path to the object.
    Parent: LevelOneEntity.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="LevelOneEntity")



class GroupingEntity(Base, TableNameMixin, EntityMixin):
    """
    This type of entity is used for grouping word entries (e.g. etymology tags). With it we can group bunch of
    LexicalEntries as connected with each other.
    Main points for usage:
        1. If you are trying to connect two LexicalEntries you should check if there is already a connection
           for one of LexicalEntries.
          1a. If you found only one GroupingEntity (for one word only), you should create one more object for
              GroupingEntity with the same content as the found one.
          1b. If you found no GroupingEntities (both of words are not connected with any others), you should
              generate an unique string for a content field. Unix epoch + words concat are good enough in most
              cases.
          1c. If you found that one (or both) of the words has many GroupingEntries connected and the content field
              differs, you should create all the GroupingEntries for each different content fields for both words.
        2. We shall provide an ability to define "content" field explicitly. If it is provided, we shall accept it
           and check the 1c case after it. It will be an often case during dictionaries conversion.

    Note: (1c) case will be rather frequent when desktop clients will appear. But moreover it will be a result of
          Dialeqt desktop databases conversion.

    Parent: LexicalEntry.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="LexicalEntry")



class PublishLevelOneEntity(Base, TableNameMixin):
    """
    This type is needed for publisher view: publisher should be able to mark word variants for each of datatypes
    as 'correct' ones. For example, a word can have 5 correct translations, two sounds and one.
    Also publisher should be able to change perspective status: WIP, published.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_publishing_fk_composite_key(parent_name="LexicalEntry",
                                                                                         entity_name="LevelOneEntity")

class PublishLevelTwoEntity(Base, TableNameMixin):
    """
    The same for markups.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_publishing_fk_composite_key(parent_name="LexicalEntry",
                                                                                         entity_name="LevelTwoEntity")

class PublishGroupingEntity(Base, TableNameMixin):
    """
    The same for etymology tags.
    """
    __table_attrs__ = CompositeKeysHelper.set_table_args_for_publishing_fk_composite_key(parent_name="LexicalEntry",
                                                                                         entity_name="GroupingEntity")

