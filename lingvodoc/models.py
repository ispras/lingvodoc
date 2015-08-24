from pyramid.security import Allow, Authenticated,  ALL_PERMISSIONS


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
    event,
    ForeignKey,
    Table,
)

from sqlalchemy.types import (
    UnicodeText,
    BigInteger,
    DateTime,
    Boolean,
    Date,
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

from sqlalchemy.inspection import inspect

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


def recursive_content(self):
    vec = []
    for entry in dir(self):
        if entry in inspect(type(self)).relationships:
            i = inspect(self.__class__).relationships[entry]
            if i.direction.name == "ONETOMANY":
                x = getattr(self, str(entry))
                for xx in x:
                    vec += [xx.__tablename__, xx.content]
                    vec += recursive_content(xx)
    return vec


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except:
        print("It's not an sqlalchemy")


class TableNameMixin(object):
    """
    Look forward to:
    http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/mixins.html

    It's used for automatically set tables names based on class names. Use it everywhere.
    """
    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


class IdMixin(object):
    """
    It's used for automatically set id as primary key.
    """
    id = Column(BigInteger, primary_key=True)


class CompositeIdMixin(object):
    """
    It's used for automatically set client_id and object_id as composite primary key.
    """
    object_id = Column(BigInteger, primary_key=True)
    client_id = Column(BigInteger, primary_key=True)


class CompositeKeysHelper(object):
    """
    This class with one method is used to declare composite keys connections with composite primary and foreign keys.
    It's very important to use the following naming convention: each class using this mixin should have
    object_id and client_id composite keys as primary and parent_object_id with parent_client_id as composite
    foreign key.

    TODO: check if it even works (not sure)
    """
    # Seems to be working
    @classmethod
    def set_table_args_for_simple_fk_composite_key(cls, parent_name):
        return (ForeignKeyConstraint(['parent_object_id', 'parent_client_id'],
                                     [parent_name.lower()+'.object_id', parent_name.lower()+'.client_id']),)

    # This is used for classes that correspond to publishing words. Need to check if it even works.
    # Seems to be working
    @classmethod
    def set_table_args_for_publishing_fk_composite_key(cls, parent_name, entity_name):
        return (ForeignKeyConstraint(['parent_object_id', 'parent_client_id'],
                                     [parent_name.lower()+'.object_id', parent_name.lower()+'.client_id']),
                ForeignKeyConstraint(['entity_object_id', 'entity_client_id'],
                                     [entity_name.lower()+'.object_id', entity_name.lower()+'.client_id']))


class RelationshipMixin(object):
    """
    It's used for automatically set parent attribute as relationship.
    Each class using this mixin should have __parentname__ attribute
    """
    @declared_attr
    def parent(cls):
        return relationship(cls.__parentname__,
                            backref= backref(cls.__tablename__.lower())
                            )


class RelationshipPublishingMixin(RelationshipMixin):
    @declared_attr
    def entity(cls):
        return relationship(cls.__entityname__,
                            backref=backref(cls.__tablename__.lower()))


class Language(Base, TableNameMixin, CompositeIdMixin, RelationshipMixin):  # is there need for relationship?
    """
    This is grouping entity that isn't related with dictionaries directly. Locale can have pointer to language.
    """
    __parentname__ = 'Language'
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Language")
    translation_string = Column(UnicodeText(length=2**31))
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    marked_for_deletion = Column(Boolean, default=False)


class Locale(Base, TableNameMixin, IdMixin):
    """
    This entity specifies list of available translations (for words in dictionaries and for UI).
    Should be added as admin only.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Language")
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    shortcut = Column(UnicodeText)
    intl_name = Column(UnicodeText(length=2**31))


class UITranslationString(Base, TableNameMixin, IdMixin):
    """
    This table holds translation strings for UI. If couldn't be found by pair, should be searched by translation string.
    Should be used as admin only.
    """
    locale_id = Column(BigInteger)
    translation_string = Column(UnicodeText(length=2**31))
    translation = Column(UnicodeText(length=2**31))


class UserEntitiesTranslationString(Base, TableNameMixin, CompositeIdMixin):
    """
    This table holds translation strings for user-created entities such as dictionaries names, column names etc.
    Separate classes are needed not to allow users to interfere UI directly.
    Not intended to use for translations inside the dictionaries (these translations are hold inside entities tables).
    """
    locale_id = Column(BigInteger)
    translation_string = Column(UnicodeText(length=2**31))
    translation = Column(UnicodeText(length=2**31))


class Dictionary(Base, TableNameMixin, CompositeIdMixin):
    """
    This object presents logical dictionary that indicates separate language. Each dictionary can have many
    perspectives that indicate actual dicts: morphological, etymology etc. Despite the fact that Dictionary object
    indicates separate language (dialect) we want to provide our users an opportunity to have their own dictionaries
    for the same language so we use some grouping. This grouping is provided via Language objects.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Language")
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    state = Column(UnicodeText)
    name = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False)


class DictionaryPerspective(Base, TableNameMixin, CompositeIdMixin):
    """
    Perspective represents dictionary fields for current usage. For example each Dictionary object can have two
    DictionaryPerspective objects: one for morphological dictionary, one for etymology dictionary. Physically both
    perspectives will use the same database tables for storage but objects that apply to morphology will be have as a
    parent morphological perspective object and that objects that apply to etymology - etymology perspective.
    Each user that creates a language
    Parent: Dictionary.
    """

    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="Dictionary")
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    state = Column(UnicodeText)
    marked_for_deletion = Column(Boolean, default=False)
    name = Column(UnicodeText)  # ?


class DictionaryPerspectiveField(Base, TableNameMixin, CompositeIdMixin):  # client_id and object_id is primary?
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
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="DictionaryPerspective")
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    entity_type = Column(UnicodeText(length=2**31))
    level = Column(BigInteger)
    parent_entity = Column(UnicodeText(length=2**31))
    group = Column(UnicodeText(length=2**31))


class LexicalEntry(Base, TableNameMixin, CompositeIdMixin):  # TableNameMixin?
    """
    Objects of this class are used for grouping objects as variations for single lexical entry. Using it we are grouping
    all the variations for a single "word" - each editor can have own version of this word. This class doesn't hold
    any viable data, it's used as a 'virtual' word. Also it contains redirects that occur after dicts merge.
    Parent: DictionaryPerspective.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="DictionaryPerspective")
    parent_object_id = Column(BigInteger)
    parent_client_id = Column(BigInteger)
    moved_to = Column(UnicodeText)

    def track(self):
        vec = []
        vec += recursive_content(self)
        return vec


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
    data_type = Column(UnicodeText)
    content = Column(UnicodeText(length=2**31))
    additional_metadata = Column(UnicodeText(length=2**31))
    is_translatable = Column(Boolean, default=False)
    locale_id = Column(BigInteger)
    marked_for_deletion = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PublishingEntityMixin(object):
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
    entity_object_id = Column(BigInteger)
    entity_client_id = Column(BigInteger)
    entity_type = Column(UnicodeText)
    content = Column(UnicodeText(length=2**31))
    marked_for_deletion = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class LevelOneEntity(Base, TableNameMixin, EntityMixin, RelationshipMixin):
    """
    This type of entity is used for level-one word entries (e.g. transcription, translation, sounds,
    paradigm transcription, etc). The main convention for this type is to have word entry as a logical parent.
    Some entity types should provide special behaviour - for example sounds: as a content they should store path
    for the stored object (not the sound file itself). One more special type: translation should point locale_id.
    Parent: LexicalEntry.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="LexicalEntry")
    __parentname__ = 'LexicalEntry'


class LevelTwoEntity(Base, TableNameMixin, EntityMixin, RelationshipMixin):
    """
    This type of entity is used as level-two entity: logically it has as parent a level-one entity object. For
    now there is the only type of such entities - it's praat markup because it can not be separated from sound
    it belongs to. Each type of such entity most likely will have it's own behaviour. For now the markup should
    be stored separately and as content it should store path to the object.
    Parent: LevelOneEntity.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="LevelOneEntity")
    __parentname__ = 'LevelOneEntity'


class GroupingEntity(Base, TableNameMixin, EntityMixin, RelationshipMixin):
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
    __table_args__ = CompositeKeysHelper.set_table_args_for_simple_fk_composite_key(parent_name="LexicalEntry")
    __parentname__ = 'LexicalEntry'


class PublishLevelOneEntity(Base, TableNameMixin, PublishingEntityMixin, RelationshipPublishingMixin):
    """
    This type is needed for publisher view: publisher should be able to mark word variants for each of datatypes
    as 'correct' ones. For example, a word can have 5 correct translations, two sounds and one.
    Also publisher should be able to change perspective status: WIP, published.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_publishing_fk_composite_key(parent_name="LexicalEntry",
                                                                                         entity_name="LevelOneEntity")
    __parentname__ = 'LexicalEntry'
    __entityname__ = 'LevelOneEntity'


class PublishLevelTwoEntity(Base, TableNameMixin, PublishingEntityMixin, RelationshipPublishingMixin):
    """
    The same for markups.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_publishing_fk_composite_key(parent_name="LexicalEntry",
                                                                                         entity_name="LevelTwoEntity")
    __parentname__ = 'LexicalEntry'
    __entityname__ = 'LevelTwoEntity'


class PublishGroupingEntity(Base, TableNameMixin, PublishingEntityMixin, RelationshipPublishingMixin):
    """
    The same for etymology tags.
    """
    __table_args__ = CompositeKeysHelper.set_table_args_for_publishing_fk_composite_key(parent_name="LexicalEntry",
                                                                                         entity_name="GroupingEntity")
    __parentname__ = 'LexicalEntry'
    __entityname__ = 'GroupingEntity'


user_to_group_association = Table('user_to_group_association', Base.metadata,
                                  Column('user_id', BigInteger, ForeignKey('user.id')),
                                  Column('group_id', BigInteger, ForeignKey('group.id'))
)


user_to_organization_association = Table('user_to_organization_association', Base.metadata,
                                  Column('user_id', BigInteger, ForeignKey('user.id')),
                                  Column('organization_id', BigInteger, ForeignKey('organization.id'))
)


class User(Base, TableNameMixin, IdMixin):
    login = Column(UnicodeText(length=30), unique=True)
    name = Column(UnicodeText)
    # this stands for name in English
    intl_name = Column(UnicodeText)
    default_locale_id = Column(ForeignKey("locale.id"))
    birthday = Column(Date)
    signup_date = Column(DateTime)
    # it's responsible for "deleted user state". True for active, False for deactivated.
    is_active = Column(Boolean)
    password = relationship("Passhash", uselist=False)

    def check_password(self, passwd):
        return bcrypt.verify(passwd, self.password.hash)

    # TODO: last_sync_datetime


class BaseGroup(Base, TableNameMixin, IdMixin):
    name = Column(UnicodeText)
    readable_name = Column(UnicodeText)
    # groups = relationship('Group', backref=backref("BaseGroup"))


class Group(Base, TableNameMixin, IdMixin, RelationshipMixin):
    __parentname__ = 'BaseGroup'
    base_group_id = Column(ForeignKey("basegroup.id"))
    subject = Column(UnicodeText)
    users = relationship("User", secondary=user_to_group_association, backref=backref("groups"))


class Organization(Base, TableNameMixin, IdMixin, RelationshipMixin):
    name = Column(UnicodeText)
    users = relationship("User", secondary=user_to_organization_association, backref=backref("organizations"))
    about = Column(UnicodeText)
    # locale_id = Column(ForeignKey("locale.id"))


class About(Base, TableNameMixin, IdMixin):
    user_id = Column(BigInteger, ForeignKey("user.id"), primary_key=True)
    user = relationship("User", backref='about')
    content = Column(UnicodeText)
    locale_id = Column(ForeignKey("locale.id"))


class Passhash(Base, TableNameMixin, IdMixin):
    user_id = Column(BigInteger, ForeignKey('user.id'))
    hash = Column(UnicodeText(length=61))

    def __init__(self, password):
        self.hash = bcrypt.encrypt(password)


class Email(Base, TableNameMixin, IdMixin):
    user_id = Column(BigInteger, ForeignKey('user.id'))
    email = Column(UnicodeText(length=50), unique=True)
    user = relationship("User", backref='email')


class Client(Base, TableNameMixin, IdMixin):
    user_id = Column(BigInteger, ForeignKey('user.id'))
    dictionaries = relationship("Dictionary", backref=backref("client"))
    languages = relationship("Language", backref=backref("client"))
    perspectives = relationship("Perspective", backref=backref("client"))
    creation_time = Column(DateTime, default=datetime.datetime.utcnow)
    is_browser_client = Column(Boolean, default=True)
    user = relationship("User", backref='clients')


# class RootFactory(object):
#     def __init__(self,request):
#         self.request = request
#     # TODO: do it, if we go this way
#     # also do many containers for many objects


class PerspAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = [(Allow, 'admin',  ALL_PERMISSIONS)]
        obj_id = int(self.request.matchdict['perspective_object_id'])
        cli_id = int(self.request.matchdict['perspective_client_id'])
        persp = DBSession.query(DictionaryPerspective).filter_by(object_id=obj_id, client_id=cli_id).first()
        object_id = persp.parent_object_id
        client_id = persp.parent_client_id
        groups = DBSession.query(Group)
        for group in groups:  # add different strategies
            name = 'dictionary' + str(object_id) + '_' + str(client_id)
            if name in group.subject:
                perm = group.BaseGroup.name
                acls += [(Allow, group.subject, perm)]
            name = 'perspective' + str(obj_id) + '_' + str(cli_id)
            if name in group.subject:
                perm = group.parent.name
                acls += [(Allow, group.subject, perm)]


class DictAcl(object):
    def __init__(self, request):
        self.request = request

    def __acl__(self):
        acls = [(Allow, 'admin',  ALL_PERMISSIONS)]
        obj_id = int(self.request.matchdict['object_id'])
        cli_id = int(self.request.matchdict['client_id'])
        groups = DBSession.query(Group)
        for group in groups:
            name = 'dictionary' + str(obj_id) + '_' + str(cli_id)
            if name in group.subject:
                perm = group.parent.name
                acls += [(Allow, group.subject, perm)]
