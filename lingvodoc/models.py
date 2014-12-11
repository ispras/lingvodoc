from sqlalchemy.orm import relationship, backref
from pyramid.security import Everyone, Allow

from sqlalchemy import (
    Column,
    Index,
    Integer,
    Text,
    event,
    ForeignKey,
    ForeignKeyConstraint,
    Table
    )

from pyramid.security import (
    Everyone,
    Allow,
    Deny
    )

from sqlalchemy.ext.declarative import declarative_base

from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
    relationship,
    backref,
    query,
    )

from sqlalchemy.engine import (
    Engine
    )

from sqlalchemy.types import (
    Integer,
    Unicode,
    UnicodeText,
    Date,
    DateTime,
    Boolean,
    )


from zope.sqlalchemy import ZopeTransactionExtension

from passlib.hash import bcrypt

import datetime

DBSession = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


#@event.listens_for(Engine, "connect")
#def set_sqlite_pragma(dbapi_connection, connection_record):
#    cursor = dbapi_connection.cursor()
#    try:
#        cursor.execute("PRAGMA foreign_keys=ON")
#        cursor.close()
#    except:
#        print("It's not an sqlalchemy")

# Many to many users to groups association table
user_to_group_association = Table('user_to_group_association', Base.metadata,
                                  Column('user_id', Integer, ForeignKey('User.id')),
                                  Column('group_id', Integer, ForeignKey('Group.id'))
)


class Locale(Base):
    __tablename__ = 'Locale'
    id = Column(Integer, primary_key=True)
    shortcut = Column(Unicode(length=20))
    name = Column(UnicodeText)


# Base groups define available actions. Introduced for deduplication.
# The real groups are in 'Group' table because the is object of permission specified
class BaseGroup(Base):
    __tablename__ = 'BaseGroup'
    id = Column(Integer, primary_key=True)
    name = Column(UnicodeText)
    readable_name = Column(UnicodeText)
    groups = relationship('Group', backref=backref("BaseGroup"))


# Subject indicates the subject of permissions. Keyword "ANY" indicates any resource. May be empty for global resources.
# Used in ACL.
class Group(Base):
    __tablename__ = 'Group'
    id = Column(Integer, primary_key=True)
    base_group_id = Column(ForeignKey("BaseGroup.id"))
    subject = Column(UnicodeText)



class User(Base):
    __tablename__ = "User"
    id = Column(Integer, primary_key=True)
    login = Column(Unicode(length=30), unique=True)
    name = Column(UnicodeText)
    # this stands for name in English
    intl_name = Column(UnicodeText)
    default_locale_id = Column(ForeignKey("Locale.id"))
    birthday = Column(Date)
    signup_date = Column(DateTime)
    # it's responsible for "deleted user state". True for active, False for deactivated.
    is_active = Column(Boolean)
    clients = relationship("Client", backref=backref('User'))
    groups = relationship("Group", secondary=user_to_group_association, backref=backref("Users"))
    password = relationship("Passhash", uselist=False)
    email = relationship("Email")
    about = relationship("About")

    def check_password(self, passwd):
        return bcrypt.verify(passwd, self.password.hash)

#    photos = relationship("UserBlob")
#    organization = Column(Integer, ForeignKey('organization.id')
#   TODO: last_sync_datetime


class About(Base):
    __tablename__ = "About"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("User.id"), primary_key=True)

    content = Column(UnicodeText)
    locale_id = Column(ForeignKey("Locale.id"))


class Passhash(Base):
    __tablename__ = "Passhash"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User.id'))
    hash = Column(Unicode(length=61))

    def __init__(self, password):
        self.hash = bcrypt.encrypt(password)


class Email(Base):
    __tablename__ = "Email"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User.id'))
    email = Column(Unicode(length=50), unique=True)


class Client(Base):
    __tablename__ = "Client"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('User.id'))
    dictionaries = relationship("Dictionary", backref=backref("Client"))
    creation_time = Column(DateTime, default=datetime.datetime.utcnow)
    is_browser_client = Column(Boolean, default=True)


# languages can be deleted only by administrator for now (hard to maintain synchronization if locales not fixed)
class Language(Base):
    __tablename__ = "Language"
    id = Column(Integer, primary_key=True)
    parent_id = Column(Integer, default=0)
    names = relationship("LanguageName", backref=backref("Language"))


class LanguageName(Base):
    __tablename__ = "LanguageName"
    id = Column(Integer, primary_key=True)
    language_id = Column(ForeignKey("Language.id"))
    locale_id = Column(ForeignKey("Locale.id"))

    readable_name = Column(UnicodeText)


class Dictionary(Base):
    __tablename__ = "Dictionary"
    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    #TODO: try to remember why have I done it like this, seems to be an error
    #client = relationship("Client")
    #TODO: check if I can use user login instead of id.
    lang = Column(ForeignKey("Language.id"))
    # state is meant to be ENUM type (may change in future): hidden, published, WiP.
    state = Column(UnicodeText)
    # name is meant to be used internally: it's some kind of ID that only editors will see
    name = Column(UnicodeText)
    # imported hash indicates source if dictionary is imported from external source.
    imported_hash = Column(Unicode(100))

    metawords = relationship("MetaWord")
    metastories = relationship("MetaStory")


class MetaWord(Base):
    __tablename__ = 'MetaWord'
    __table_args__ = (ForeignKeyConstraint(['dictionary_id', 'dictionary_client_id'],
                                           ['Dictionary.id', 'Dictionary.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    dictionary_client_id = Column(Integer)
    dictionary_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    entries = relationship('WordEntry', backref=backref('MetaWord'))
    transcriptions = relationship('WordTranscription', backref=backref('MetaWord'))
    translations = relationship('WordTranslation', backref=backref('MetaWord'))
    sounds = relationship('WordSound', backref=backref('MetaWord'))
    paradigms = relationship('MetaParadigm', backref=backref('MetaWord'))
    # TODO: it's temporary workaround
    etymology_tags = relationship('WordEtymologyTag', backref=backref('MetaWord'))

# NOTE: markups are connected with sounds, not with metawords
    #translations = relationship('MetaTranslation')
    #etymology_tags = relationship('EtymologyTag')

#class DictionariesACL(object):
#    def __init__(self, request):
#        assert request.matched_route.name == 'dictionaries.list'
#        self.__acl__ = [(Allow, Everyone, 'view')]
#        self.dictionaries = DBSession.query(Dictionary)


# NOTE: TODO: it's temporary object for demo-version; it should be done in other way.
class WordEtymologyTag(Base):
    __tablename__ = 'WordEtymologyTag'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordEntry(Base):
    __tablename__ = 'WordEntry'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


# This is one-to-one association. Represents words intended for publication. Can be edited on-site only.
class WordEntryDefault(Base):
    __tablename__ = 'WordEntryDefault'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),
                      ForeignKeyConstraint(['wordentry_id', 'wordentry_client_id'],
                                           ['WordEntry.id', 'WordEntry.client_id']),)
    id = Column(Integer, primary_key=True)
    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)
    wordentry_id = Column(Integer)
    wordentry_client_id = Column(Integer)
# TODO: not sure enough that it's right way to do it.

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordTranscription(Base):
    __tablename__ = 'WordTranscription'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordTranscriptionDefault(Base):
    __tablename__ = 'WordTranscriptionDefault'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),
                      ForeignKeyConstraint(['wordtranscription_id', 'wordtranscription_client_id'],
                                           ['WordTranscription.id', 'WordTranscription.client_id']),)
    id = Column(Integer, primary_key=True)
    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)
    wordtranscription_id = Column(Integer)
    wordtranscription_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordTranslation(Base):
    __tablename__ = 'WordTranslation'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)

    content = Column(UnicodeText)
    locale_id = Column(ForeignKey("Locale.id"))

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordTranslationDefault(Base):
    __tablename__ = 'WordTranslationDefault'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),
                      ForeignKeyConstraint(['wordtranslation_id', 'wordtranslation_client_id'],
                                           ['WordTranslation.id', 'WordTranslation.client_id']),)
    id = Column(Integer, primary_key=True)
    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)
    wordtranslation_id = Column(Integer)
    wordtranslation_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


# path to the sound is determined by it's IDs.
class WordSound(Base):
    __tablename__ = 'WordSound'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    mime = Column(UnicodeText)
    name = Column(UnicodeText)

    markups = relationship('WordMarkup', backref=backref('WordSound'))

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordSoundDefault(Base):
    __tablename__ = 'WordSoundDefault'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),
                      ForeignKeyConstraint(['wordsound_id', 'wordsound_client_id'],
                                           ['WordSound.id', 'WordSound.client_id']),)
    id = Column(Integer, primary_key=True)
    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)
    wordsound_id = Column(Integer)
    wordsound_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordMarkup(Base):
    __tablename__ = 'WordMarkup'
    __table_args__ = (ForeignKeyConstraint(['wordsound_id', 'wordsound_client_id'],
                                           ['WordSound.id', 'WordSound.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    wordsound_id = Column(Integer)
    wordsound_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class WordMarkupDefault(Base):
    __tablename__ = 'WordMarkupDefault'
    __table_args__ = (ForeignKeyConstraint(['wordsound_id', 'wordsound_client_id'],
                                           ['WordSound.id', 'WordSound.client_id']),
                      ForeignKeyConstraint(['wordmarkup_id', 'wordmarkup_client_id'],
                                           ['WordMarkup.id', 'WordMarkup.client_id']),)
    id = Column(Integer, primary_key=True)
    wordsound_id = Column(Integer)
    wordsound_client_id = Column(Integer)
    wordmarkup_id = Column(Integer)
    wordmarkup_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class MetaParadigm(Base):
    __tablename__ = 'MetaParadigm'
    __table_args__ = (ForeignKeyConstraint(['metaword_id', 'metaword_client_id'],
                                           ['MetaWord.id', 'MetaWord.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaword_id = Column(Integer)
    metaword_client_id = Column(Integer)

    entries = relationship('ParadigmEntry', backref=backref('MetaParadigm'))
    transcriptions = relationship('ParadigmTranscription', backref=backref('MetaParadigm'))
    translations = relationship('ParadigmTranslation', backref=backref('MetaParadigm'))
    sounds = relationship('ParadigmSound', backref=backref('MetaParadigm'))

    marked_to_delete = Column(Boolean)


class ParadigmEntry(Base):
    __tablename__ = 'ParadigmEntry'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


# This is one-to-one association. Represents words intended for publication. Can be edited on-site only.
class ParadigmEntryDefault(Base):
    __tablename__ = 'ParadigmEntryDefault'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),
                      ForeignKeyConstraint(['paradigmentry_id', 'paradigmentry_client_id'],
                                           ['ParadigmEntry.id', 'ParadigmEntry.client_id']),)
    id = Column(Integer, primary_key=True)
    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)
    paradigmentry_id = Column(Integer)
    paradigmentry_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmTranscription(Base):
    __tablename__ = 'ParadigmTranscription'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmTranscriptionDefault(Base):
    __tablename__ = 'ParadigmTranscriptionDefault'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),
                      ForeignKeyConstraint(['paradigmtranscription_id', 'paradigmtranscription_client_id'],
                                           ['ParadigmTranscription.id', 'ParadigmTranscription.client_id']),)
    id = Column(Integer, primary_key=True)
    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)
    paradigmtranscription_id = Column(Integer)
    paradigmtranscription_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmTranslation(Base):
    __tablename__ = 'ParadigmTranslation'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)

    content = Column(UnicodeText)
    locale_id = Column(ForeignKey("Locale.id"))

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmTranslationDefault(Base):
    __tablename__ = 'ParadigmTranslationDefault'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),
                      ForeignKeyConstraint(['paradigmtranslation_id', 'paradigmtranslation_client_id'],
                                           ['ParadigmTranslation.id', 'ParadigmTranslation.client_id']),)
    id = Column(Integer, primary_key=True)
    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)
    paradigmtranslation_id = Column(Integer)
    paradigmtranslation_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmSound(Base):
    __tablename__ = 'ParadigmSound'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    mime = Column(UnicodeText)
    name = Column(UnicodeText)

    markups = relationship('ParadigmMarkup', backref=backref('ParadigmSound'))

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmSoundDefault(Base):
    __tablename__ = 'ParadigmSoundDefault'
    __table_args__ = (ForeignKeyConstraint(['metaparadigm_id', 'metaparadigm_client_id'],
                                           ['MetaParadigm.id', 'MetaParadigm.client_id']),
                      ForeignKeyConstraint(['paradigmsound_id', 'paradigmsound_client_id'],
                                           ['ParadigmSound.id', 'ParadigmSound.client_id']),)
    id = Column(Integer, primary_key=True)
    metaparadigm_id = Column(Integer)
    metaparadigm_client_id = Column(Integer)
    paradigmsound_id = Column(Integer)
    paradigmsound_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmMarkup(Base):
    __tablename__ = 'ParadigmMarkup'
    __table_args__ = (ForeignKeyConstraint(['paradigmsound_id', 'paradigmsound_client_id'],
                                           ['ParadigmSound.id', 'ParadigmSound.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    paradigmsound_id = Column(Integer)
    paradigmsound_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class ParadigmMarkupDefault(Base):
    __tablename__ = 'ParadigmMarkupDefault'
    __table_args__ = (ForeignKeyConstraint(['paradigmsound_id', 'paradigmsound_client_id'],
                                           ['ParadigmSound.id', 'ParadigmSound.client_id']),
                      ForeignKeyConstraint(['paradigmmarkup_id', 'paradigmmarkup_client_id'],
                                           ['ParadigmMarkup.id', 'ParadigmMarkup.client_id']),)
    id = Column(Integer, primary_key=True)
    paradigmsound_id = Column(Integer)
    paradigmsound_client_id = Column(Integer)
    paradigmmarkup_id = Column(Integer)
    paradigmmarkup_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class MetaStory(Base):
    __tablename__ = 'MetaStory'
    __table_args__ = (ForeignKeyConstraint(['dictionary_id', 'dictionary_client_id'],
                                           ['Dictionary.id', 'Dictionary.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    dictionary_id = Column(Integer)
    dictionary_client_id = Column(Integer)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


class StoryText(Base):
    __tablename__ = 'StoryText'
    __table_args__ = (ForeignKeyConstraint(['metastory_id', 'metastory_client_id'],
                                           ['MetaStory.id', 'MetaStory.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metastory_id = Column(Integer)
    metastory_client_id = Column(Integer)

    content = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


# Due to previous naming principles it should be the same as StoryDefault.
class StoryLegend(Base):
    __tablename__ = 'StoryLegend'
    __table_args__ = (ForeignKeyConstraint(['metastory_id', 'metastory_client_id'],
                                           ['MetaStory.id', 'MetaStory.client_id']),
                      ForeignKeyConstraint(['storytext_id', 'storytext_client_id'],
                                           ['StoryText.id', 'StoryText.client_id']),)
    id = Column(Integer, primary_key=True)
    metastory_id = Column(Integer)
    metastory_client_id = Column(Integer)
    storytext_id = Column(Integer)
    storytext_client_id = Column(Integer)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


# this is for files (audio/video/other). No defaults are intended to be in use.
class StoryObject(Base):
    __tablename__ = 'StoryObject'
    __table_args__ = (ForeignKeyConstraint(['metastory_id', 'metastory_client_id'],
                                           ['MetaStory.id', 'MetaStory.client_id']),)
    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey('Client.id'), primary_key=True)
    client = relationship("Client")

    metastory_id = Column(Integer)
    metastory_client_id = Column(Integer)

    type = Column(UnicodeText)

    marked_to_delete = Column(Boolean)

    creation_time = Column(DateTime, default=datetime.datetime.utcnow)


#Index('my_index', MyModel.name, unique=True, mysql_length=255)
