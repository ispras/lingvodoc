import minio
import tempfile
import time
import os
import re

import graphene
import logging

from sqlalchemy import func, literal, tuple_, and_
from lingvodoc.queue.celery import celery
from lingvodoc.cache.caching import TaskStatus
from pyramid.security import authenticated_userid

from lingvodoc.models import (
    DBSession,
    TranslationAtom,
    TranslationGist,
    Field,
    Entity,
    Client,
    LexicalEntry,
    Dictionary,
    Language,
    DictionaryPerspectiveToField,
    DictionaryPerspective,
    PublishingEntity
)

from lingvodoc.schema.gql_holders import (
    fetch_object,
    client_id_check,
    del_object,
    acl_check_by_id,
    ResponseError,
    LingvodocID,
    ObjectVal
)

from sqlalchemy.orm import aliased
from pdb import set_trace as A

log = logging.getLogger(__name__)


class ListChanges(graphene.Mutation):

    class Arguments:
        pers_id = LingvodocID(required=True)
        # translation gist and/or atoms changes
        # language and/or its hierarchy changes
        # dictionary entry changes
        # dictionaryperspective changes
        # dictionaryperspectivetofield changes
        # lexicalentry changes
        # entity changes
        # publishingentity changes
        # fields changes
        # alembic_version changes (blocking parameter)
        # parser changes (blocking parameter)
        # parserresult changes
        # userblobs (with files)

        changes = graphene.List(ObjectVal, required=True)
        sync_stamp = graphene.String(required=True)  # belongs to perspective

    changes = graphene.List(ObjectVal)
    sync_stamp = graphene.String()  # belongs to perspective
    triumph = graphene.Boolean()

    @staticmethod
    @client_id_check()
    def mutate(root, info, **args):
        print('locking client')
        log.error('locking client')

        request = info.context.request
        DBSession.execute("LOCK TABLE client IN EXCLUSIVE MODE;")
        variables = {'auth': authenticated_userid(request)}
        client = DBSession.query(Client).filter_by(id=variables['auth']).first()
        if not client:
            raise ResponseError('try to login again')

        client_id = request.authenticated_userid
        user_id = Client.get_user_by_client_id(client_id).id

        is_admin = False
        if user_id == 1:
            is_admin = True

        task = TaskStatus(user_id, "Synchronisation with server", '', 5)
        task.set(1, 1, "Started", "")

        # Body


        task.set(5, 100, "Synchronisation complete (New data may be still downloading from server, look into the tasks)", "")
        return ListChanges(
            cahanges=proxy_changes,
            sync_stamp=proxy_sync_stamp,
            triumph=True)

def perspective_getter(perspective_cte, perspective_id):
    try:
        return (
            DBSession
                .query(
                    perspective_cte.c.perspective_title,
                    perspective_cte.c.dictionary_cid,
                    perspective_cte.c.dictionary_oid)

                .filter(
                    perspective_cte.c.perspective_cid == perspective_id[0],
                    perspective_cte.c.perspective_oid == perspective_id[1])

                .one())
    except:
        print(f'Skipped perspective: {perspective_id}')
        return None


def dictionary_getter(dictionary_cte, dictionary_id):
    try:
        return (
            DBSession
                .query(
                    dictionary_cte.c.dictionary_title,
                    dictionary_cte.c.language_cid,
                    dictionary_cte.c.language_oid)

                .filter(
                    dictionary_cte.c.dictionary_cid == dictionary_id[0],
                    dictionary_cte.c.dictionary_oid == dictionary_id[1])

                .one())
    except:
        print(f'Skipped dictionary: {dictionary_id}')
        return None


def language_getter(language_cte, language_id):
    try:
        return (
            DBSession
                .query(
                    language_cte.c.language_title)

                .filter(
                    language_cte.c.language_cid == language_id[0],
                    language_cte.c.language_oid == language_id[1])

                .one())
    except:
        print(f'Skipped language: {language_id}')
        return None


# Getting cte for languages, dictionaries, perspectives and fields

def get_cte_set(only_in_toc, group, title, offset, limit, task_status):

    get_xlat_atoms = [
        TranslationAtom.parent_id == TranslationGist.id,
        func.length(TranslationAtom.content) > 0,
        TranslationAtom.marked_for_deletion == False]

    def get_language_ids(name):
        nonlocal get_xlat_atoms
        return (
            DBSession
                .query(
                    Language.client_id,
                    Language.object_id)
                .filter(
                    Language.translation_gist_id == TranslationGist.id,
                    *get_xlat_atoms,
                    func.lower(TranslationAtom.content) == name.lower().strip())
                .all())

    # Getting root languages

    language_init = (
        DBSession
            .query(
                Language,
                literal(0).label('level'))

            .filter(
                Language.marked_for_deletion == False))

    if not group and not title:
        language_init = language_init.filter(
            Language.parent_client_id == None,
            Language.parent_object_id == None)
    else:
        if group:
            if group_ids := get_language_ids(group):
                language_init = language_init.filter(
                    tuple_(Language.parent_client_id, Language.parent_object_id).in_(group_ids))
            else:
                if task_status:
                    task_status.set(2, 100, 'Finished (ERROR):\n' + 'No such language parent group in the database')
                return False
        if title:
            if title_ids := get_language_ids(title):
                language_init = language_init.filter(
                    tuple_(Language.client_id, Language.object_id).in_(title_ids))
            else:
                if task_status:
                    task_status.set(2, 100, 'Finished (ERROR):\n' + 'No such language group or title in the database')
                return False

    if not language_init.count():
        if task_status:
            task_status.set(2, 100, 'Finished (ERROR):\n' +
                'Seems like the parent group is not closest one for the target group or any of them is deleted')
        return False

    language_init = language_init.cte(recursive=True)

    prnLanguage = aliased(language_init)
    subLanguage = aliased(Language)

    # Recursively getting tree of languages

    if_only_in_toc = [subLanguage.additional_metadata['toc_mark'] == 'true'] if only_in_toc else []

    language_step = language_init.union_all(
        DBSession
            .query(
                subLanguage,
                (prnLanguage.c.level + 1).label("level"))

            .filter(
                subLanguage.parent_client_id == prnLanguage.c.client_id,
                subLanguage.parent_object_id == prnLanguage.c.object_id,
                subLanguage.marked_for_deletion == False,
                *if_only_in_toc))

    language_cte = (
        DBSession
            .query(
                language_step.c.client_id.label('language_cid'),
                language_step.c.object_id.label('language_oid'),
                func.array_agg(TranslationAtom.content).label('language_title'))

            .join(TranslationGist, and_(
                language_step.c.translation_gist_client_id == TranslationGist.client_id,
                language_step.c.translation_gist_object_id == TranslationGist.object_id,
                TranslationGist.marked_for_deletion == False))

            .outerjoin(TranslationAtom, and_(*get_xlat_atoms))

            .group_by(
                'language_cid',
                'language_oid')

            .cte())

    get_dicts_for_langs = [
        Dictionary.parent_client_id == language_step.c.client_id,
        Dictionary.parent_object_id == language_step.c.object_id,
        Dictionary.marked_for_deletion == False]

    # Getting dictionaries with self titles

    dictionary_cte = (
        DBSession
            .query(
                Dictionary.parent_client_id.label('language_cid'),
                Dictionary.parent_object_id.label('language_oid'),
                Dictionary.client_id.label('dictionary_cid'),
                Dictionary.object_id.label('dictionary_oid'),
                func.array_agg(TranslationAtom.content).label('dictionary_title'))

            .filter(*get_dicts_for_langs)

            .join(TranslationGist, and_(
                Dictionary.translation_gist_id == TranslationGist.id,
                TranslationGist.marked_for_deletion == False))

            .outerjoin(TranslationAtom, and_(*get_xlat_atoms))

            .group_by(
                'language_cid',
                'language_oid',
                'dictionary_cid',
                'dictionary_oid')

            .cte())

    get_pers_for_dicts = [
        DictionaryPerspective.parent_id == Dictionary.id,
        DictionaryPerspective.marked_for_deletion == False]

    # Getting perspectives with self titles

    perspective_limit = (
        DBSession
            .query(
                DictionaryPerspective.parent_client_id.label('dictionary_cid'),
                DictionaryPerspective.parent_object_id.label('dictionary_oid'),
                DictionaryPerspective.client_id.label('perspective_cid'),
                DictionaryPerspective.object_id.label('perspective_oid'),
                func.array_agg(TranslationAtom.content).label('perspective_title'),
                func.min(language_step.c.level).label('language_level'))

            .filter(
                *get_dicts_for_langs,
                *get_pers_for_dicts)

            .join(TranslationGist, and_(
                DictionaryPerspective.translation_gist_id == TranslationGist.id,
                TranslationGist.marked_for_deletion == False))

            .outerjoin(TranslationAtom, and_(*get_xlat_atoms))

            .group_by(
                'dictionary_cid',
                'dictionary_oid',
                'perspective_cid',
                'perspective_oid')

            .order_by(
                'language_level',
                DictionaryPerspective.client_id,
                DictionaryPerspective.object_id)

            .offset(offset)
            .limit(limit))

    perspective_count = perspective_limit.count()
    perspective_cte = perspective_limit.cte()

    # Getting fields with self title

    field_query = (
        DBSession
            .query(
                DictionaryPerspective.client_id,
                DictionaryPerspective.object_id,
                Field.client_id.label('field_cid'),
                Field.object_id.label('field_oid'),
                func.array_agg(func.lower(TranslationAtom.content)).label('field_title'),
                func.min(DictionaryPerspectiveToField.position).label('field_position'),
                func.min(perspective_cte.c.language_level).label('language_level'))

            .filter(
                DictionaryPerspective.client_id == perspective_cte.c.perspective_cid,
                DictionaryPerspective.object_id == perspective_cte.c.perspective_oid,
                DictionaryPerspectiveToField.parent_id == DictionaryPerspective.id,
                DictionaryPerspectiveToField.marked_for_deletion == False,
                DictionaryPerspectiveToField.field_id == Field.id,
                Field.marked_for_deletion == False,
                Field.translation_gist_id == TranslationGist.id,
                TranslationGist.marked_for_deletion == False,
                *get_xlat_atoms, TranslationAtom.locale_id <= 2)

            .group_by(
                DictionaryPerspective.client_id,
                DictionaryPerspective.object_id,
                'field_cid', 'field_oid')

            .order_by(
                'language_level',
                DictionaryPerspective.client_id,
                DictionaryPerspective.object_id)

            .yield_per(100))

    return (
        language_cte,
        dictionary_cte,
        perspective_count,
        perspective_cte,
        field_query)


# Getting perspectives with transcription, translation and cognates

def fields_getter(field_query):

    def has_word(word, text):
        return bool(re.search(r'\b' + word + r'\b', text))

    # Group fields by perspective
    fields_by_perspective = itertools.groupby(field_query, key=lambda x: (x[0], x[1]))

    for perspective_id, fields_group in fields_by_perspective:

        # Sorting fields by position
        fields_list = sorted(list(fields_group), key=lambda x: x[5])

        xcript_fid, xlat_fid, xcript_fname, xlat_fname = [None] * 4
        with_cognates = False

        for _, _, field_cid, field_oid, title, _, _ in fields_list:

            title = "; ".join(title)

            if xcript_fid is None and not has_word("affix", title):
                if (has_word("transcription", title) or
                        has_word("word", title) or
                        has_word("транскрипция", title) or
                        has_word("слово", title) or
                        has_word("лексема", title) or
                        has_word("праформа", title)):
                    xcript_fid = (field_cid, field_oid)
                    xcript_fname = title

            if xlat_fid is None and not has_word("affix", title):
                if (has_word("translation", title) or
                        has_word("meaning", title) or
                        has_word("перевод", title) or
                        has_word("значение", title)):
                    xlat_fid = (field_cid, field_oid)
                    xlat_fname = title

            if ((field_cid, field_oid) == (66, 25)):
                with_cognates = True

            if xcript_fid and xlat_fid and with_cognates:
                break

        if xcript_fid and xlat_fid and with_cognates:
            yield (
                perspective_id,
                (xcript_fid, xcript_fname),
                (xlat_fid, xlat_fname))
        else:
            yield None


def entities_getter(perspective_id, xcript_fid, xlat_fid, get_linked_group=True, group_field_id=(66, 25)):

    xcript_text = None
    xlat_text = None

    entities = (
        DBSession
            .query(
                LexicalEntry.client_id,
                LexicalEntry.object_id,
                Entity.field_id,
                Entity.content)

            .filter(
                LexicalEntry.parent_id == perspective_id,
                LexicalEntry.marked_for_deletion == False,
                Entity.parent_id == LexicalEntry.id,
                Entity.field_id.in_([xcript_fid, xlat_fid]),
                Entity.marked_for_deletion == False,
                Entity.client_id == PublishingEntity.client_id,
                Entity.object_id == PublishingEntity.object_id,
                PublishingEntity.published == True,
                PublishingEntity.accepted == True)

            .yield_per(100))

    entities_by_lex = itertools.groupby(entities, key=lambda x: (x[0], x[1]))

    for lex_id, entities_group in entities_by_lex:

        entities_by_field = itertools.groupby(entities_group, key = lambda x: (x[2], x[3]))

        for field_id, group in entities_by_field:

            field_text = [x[4] for x in group]

            if field_id == xcript_fid:
                xcript_text = field_text
            elif field_id == xlat_fid:
                xlat_text = field_text

        linked_group = []

        if get_linked_group:

            linked_group = (
                DBSession
                    .execute(
                        f'select * from linked_group'
                        f'({group_field_id[0]}, {group_field_id[1]}, {lex_id[0]}, {lex_id[1]})'
                    )
                    .fetchall())

            # Preparing of linked_group for json-serialization
            linked_group = list(map(lambda x: tuple(x), linked_group))

        # Return current found lexical entry with perspective_id

        yield (
            lex_id,
            xcript_text,
            xlat_text,
            linked_group)
