import itertools
import json
import shutil
import minio
import tempfile
import time
import os
import re

from sqlalchemy import func, literal, tuple_, create_engine
from lingvodoc.queue.celery import celery
from lingvodoc.cache.caching import initialize_cache, TaskStatus

from lingvodoc.models import (
    DBSession,
    TranslationAtom,
    TranslationGist,
    Field,
    Entity,
    LexicalEntry,
    Dictionary,
    Language,
    DictionaryPerspectiveToField,
    DictionaryPerspective,
    PublishingEntity
)

from sqlalchemy.orm import aliased
from pdb import set_trace as A


@celery.task
def async_get_json_tree(
        task_key,
        sqlalchemy_url,
        cache_kwargs,
        storage,
        only_in_toc=False,
        group=None,
        title=None,
        offset=0,
        limit=10,
        debug_flag=False):

    result_dict = {}
    language_list = []
    cur_language_id = None
    cur_dictionary_id = None
    cur_perspective_id = None

    dictionary_title = None
    perspective_title = None

    # Ok, and now we go on with task execution.
    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind=engine)
    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)

    if task_status:
        task_status.set(1, 10, 'Getting required data from database...')

    # Getting set of cte
    if cte_set := get_cte_set(only_in_toc, group, title, offset, limit, task_status):
        language_cte, dictionary_cte, perspective_count, perspective_cte, field_query = cte_set
    else:
        if task_status:
            task_status.set(1, 100, "Finished (ERROR): it's something wrong with queries, please ask administrator")
        return False

    def id2str(id):
        return f'{id[0],id[1]}'

    # Getting perspective_id and etymology fields ids and names in cycle
    j = 0
    for i, current_perspective in enumerate(fields_getter(field_query)):

        if current_perspective is None:
            j += 1

        if task_status:
            task_status.set(
                2, 10 + i * 95 // perspective_count,
                f'So far {i}/{j} of {perspective_count} perspectives are processed / are not suitable')

        if current_perspective is None:
            continue

        (
            perspective_id,
            (xcript_fid, xcript_fname),
            (xlat_fid, xlat_fname)

        ) = current_perspective

        # Init dictionary_id and language_id
        dictionary_id = cur_dictionary_id
        language_id = cur_language_id

        # Getting next perspective_title and dictionary_id
        if perspective_id != cur_perspective_id:
            (
                perspective_title,
                dictionary_cid,
                dictionary_oid

            ) = perspective_getter(perspective_cte, perspective_id)

            dictionary_id = (dictionary_cid, dictionary_oid)

        # Getting next dictionary_title and language_id
        if dictionary_id != cur_dictionary_id:
            (
                dictionary_title,
                language_cid,
                language_oid

            ) = dictionary_getter(dictionary_cte, dictionary_id)

            language_id = (language_cid, language_oid)

        # Getting next language_title
        if language_id != cur_language_id:
            (
                language_title,

            ) = language_getter(language_cte, language_id)

            lang_slot = result_dict[id2str(language_id)] = {}
            lang_slot['title'] = language_title

            # Logging processed languages
            language_list.append(language_title)

            cur_language_id = language_id

            if debug_flag:
                print(f"*** Language: {language_id} | {language_title}")

        # Once again check conditions for dictionary and perspective
        # and put the data into result_dict

        if dictionary_id != cur_dictionary_id:

            dict_slot = lang_slot[id2str(dictionary_id)] = {}
            dict_slot['title'] = dictionary_title

            cur_dictionary_id = dictionary_id

            if debug_flag:
                print(f"** Dictionary: {dictionary_id} | {dictionary_title}")

        if perspective_id != cur_perspective_id:

            pers_slot = dict_slot[id2str(perspective_id)] = {}
            pers_slot['title'] = perspective_title
            pers_slot['fields'] = [
                (xcript_fid, xcript_fname), (xlat_fid, xlat_fname)
            ]
            pers_slot['entities'] = {}

            cur_perspective_id = perspective_id

            if debug_flag:
                print(f"* Perspective: {perspective_id} | {perspective_title}\n")

        for (
            lex_id,
            xcript_text,
            xlat_text,
            linked_group

        ) in entities_getter(perspective_id, xcript_fid, xlat_fid):

            pers_slot['entities'][id2str(lex_id)] = (
                xcript_text, xlat_text, linked_group
            )

            if debug_flag:
                print(f"{xcript_fname}: {xcript_text}")
                print(f"{xlat_fname}: {xlat_text}")
                print(f"Cognate_groups: {str(linked_group)}\n")

    if task_status:
        task_status.set(3, 95, 'Writing result file...')

    file_name = (
        f'cognates'
        f'{"_" + group if group else ""}'
        f'{"_" + title if title else ""}'
        f'_{offset + 1}to{offset + limit}'
        f'{"_onlyInToc" if only_in_toc else ""}.json')

    try:
        json_url = write_json_file(json.dumps(result_dict), file_name, storage, debug_flag)
    except Exception as e:
        if task_status:
            task_status.set(3, 100, "Finished (ERROR):\n" + "Result file can't be stored\n" + str(e))
        return False

    language_list = '\n'.join(str(title) for title in language_list)

    if task_status:
        task_status.set(3, 100, 'Finished. Processed languages:\n' + language_list, json_url)

    return True


def perspective_getter(perspective_cte, perspective_id):
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


def dictionary_getter(dictionary_cte, dictionary_id):
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


def language_getter(language_cte, language_id):
    return (
        DBSession
            .query(
                language_cte.c.language_title)

            .filter(
                language_cte.c.language_cid == language_id[0],
                language_cte.c.language_oid == language_id[1])

            .one())


# Getting cte for languages, dictionaries, perspectives and fields

def get_cte_set(only_in_toc, group, title, offset, limit, task_status):

    get_xlat_atoms = [
        TranslationGist.marked_for_deletion == False,
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

            .filter(
                language_step.c.translation_gist_client_id == TranslationGist.client_id,
                language_step.c.translation_gist_object_id == TranslationGist.object_id,
                *get_xlat_atoms)

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

            .filter(
                *get_dicts_for_langs,
                Dictionary.translation_gist_id == TranslationGist.id,
                *get_xlat_atoms)

            .group_by(
                'language_cid',
                'language_oid',
                'dictionary_cid',
                'dictionary_oid')

            .cte())

    get_pers_for_dicts = [
        DictionaryPerspective.parent_id == Dictionary.id,
        DictionaryPerspective.marked_for_deletion == False]

    # Get perspectives count

    perspective_limit = (
        DBSession
            .query(
                DictionaryPerspective.client_id,
                DictionaryPerspective.object_id,
                language_step.c.level)

            .filter(
                *get_dicts_for_langs,
                *get_pers_for_dicts)

            .order_by(
                language_step.c.level,
                DictionaryPerspective.client_id,
                DictionaryPerspective.object_id
            )

            .offset(offset)
            .limit(limit))

    perspective_count = perspective_limit.count()
    perspective_limit = perspective_limit.cte()

    # Getting perspectives with self titles

    perspective_cte = (
        DBSession
            .query(
                DictionaryPerspective.parent_client_id.label('dictionary_cid'),
                DictionaryPerspective.parent_object_id.label('dictionary_oid'),
                DictionaryPerspective.client_id.label('perspective_cid'),
                DictionaryPerspective.object_id.label('perspective_oid'),
                func.array_agg(TranslationAtom.content).label('perspective_title'))

            .filter(
                *get_dicts_for_langs,
                *get_pers_for_dicts,
                DictionaryPerspective.translation_gist_id == TranslationGist.id,
                *get_xlat_atoms)

            .group_by(
                'dictionary_cid',
                'dictionary_oid',
                'perspective_cid',
                'perspective_oid')

            .cte())

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
                func.min(language_step.c.level).label('language_level'))

            .filter(
                *get_dicts_for_langs,
                *get_pers_for_dicts,
                DictionaryPerspective.client_id == perspective_limit.c.client_id,
                DictionaryPerspective.object_id == perspective_limit.c.object_id,
                DictionaryPerspectiveToField.parent_id == DictionaryPerspective.id,
                DictionaryPerspectiveToField.marked_for_deletion == False,
                DictionaryPerspectiveToField.field_id == Field.id,
                Field.marked_for_deletion == False,
                Field.translation_gist_id == TranslationGist.id,
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


def entities_getter(perspective_id, xcript_fid, xlat_fid):

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

        linked_group = (
            DBSession
                .execute(
                    f'select * from linked_group(66, 25, {lex_id[0]}, {lex_id[1]})')
                .fetchall())

        # Preparing of linked_group for json-serialization
        linked_group = list(map(lambda x: tuple(x), linked_group))

        entities_by_field = itertools.groupby(entities_group, key = lambda x: (x[2], x[3]))

        for field_id, group in entities_by_field:

            field_text = [x[4] for x in group]

            if field_id == xcript_fid:
                xcript_text = field_text
            elif field_id == xlat_fid:
                xlat_text = field_text

        # Return current found lexical entry with perspective_id

        yield (
            lex_id,
            xcript_text,
            xlat_text,
            linked_group)


def write_json_file(result_json, file_name, storage, debug_flag):

    with tempfile.TemporaryDirectory() as tmp_dir_path:
        tmp_json_file_path = (
            os.path.join(tmp_dir_path, 'cognates_summary.json'))

        with open(tmp_json_file_path, 'w') as tmp_json_file:
            tmp_json_file.write(result_json)

        # Saving local copies, if required.
        if debug_flag:
            shutil.copyfile(
                tmp_json_file_path,
                file_name)

        # Saving processed files.
        storage_temporary = storage['temporary']
        host = storage_temporary['host']
        bucket = storage_temporary['bucket']

        minio_client = (
            minio.Minio(
                host,
                access_key=storage_temporary['access_key'],
                secret_key=storage_temporary['secret_key'],
                secure=True))

        current_time = time.time()

        object_name = (
                storage_temporary['prefix'] +
                '/'.join((
                    'cognates_summary',
                    f'{current_time:.6f}',
                    file_name)))

        minio_client.fput_object(
            bucket,
            object_name,
            tmp_json_file_path)

    url = (
        '/'.join((
            'https:/',
            host,
            bucket,
            object_name)))

    return url
