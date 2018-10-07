from sqlalchemy import func, and_

from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    LexicalEntry,
    TranslationGist
)


def gc_message(timestamp, reason, initiator):
    """
    This function generates a message for additional metadata to track reason of garbage collection.
    :param timestamp: time of gc-loop start
    :param reason: text reason for deletion
    :param initiator: object that initially became a reason for deletion (it can be some of parents objects of self)
    :return:
    """
    return {"garbage_collector":
                {"deleted_at": int(timestamp.timestamp()),
                 "reason": reason,
                 "initiator":
                     {"client_id": initiator.client_id,
                      "object_id": initiator.object_id,
                      "tablename": initiator.__tablename__}
                 }
            }


def get_empty_perspectives():
    """
    This function detects perspectives that don't have any lexical entries
    :return: list
    """

    # NOTE: don't listen to PyCharm; here we must use '==' comparison instead of 'is'
    perspectives = DBSession.query(DictionaryPerspective).outerjoin(LexicalEntry)\
        .filter(DictionaryPerspective.lexicalentry == None)

    # # double check
    # for i in perspectives:
    #     lexes = DBSession.query(LexicalEntry).filter(and_(LexicalEntry.parent_client_id==i.client_id, LexicalEntry.parent_object_id==i.object_id)).count()
    #     if lexes != 0:
    #         print("ASSERT!")
    #         print(i.client_id, i.object_id)

    return perspectives


def get_empty_dictionaries():
    """
    This function detects dictionaries that don't have any perspectives
    :return: list
    """
    dictionaries = DBSession.query(Dictionary).outerjoin(DictionaryPerspective)\
        .filter(Dictionary.dictionaryperspective == None)
    return dictionaries


def get_useless_dictionaries():
    """
    This function detects dictionaries that have all the perspectives empty
    :return: tuple
    """
    empty_perspectives = set(get_empty_perspectives())
    empty_dictionaries = get_empty_dictionaries()

    all_dictionaries = DBSession.query(Dictionary).outerjoin(DictionaryPerspective)\
        .filter(Dictionary.dictionaryperspective != None)
    useful_dictionaries = []
    no_content_dictionaries = []
    for dictionary in all_dictionaries:
        for perspective in dictionary.dictionaryperspective:
            if perspective not in empty_perspectives:
                useful_dictionaries.append(dictionary)
                continue
            no_content_dictionaries.append(dictionary)

    return empty_dictionaries, no_content_dictionaries, useful_dictionaries


def get_empty_lexical_entries():
    """
    This function detects lexical entries that don't have any entities
    :return: list
    """
    le = DBSession.query(LexicalEntry).filter(LexicalEntry == None)
    return le


def get_orphaned_translations():
    """
    TODO:
    This function detects translation gists that have only deleted parents
    :return: list
    """
    return
