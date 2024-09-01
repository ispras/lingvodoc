import itertools
import json
import re

from sqlalchemy import func, literal

from lingvodoc.models import (
    DBSession as SyncDBSession,
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


def get_json_tree(only_in_toc=False, offset=0, limit=10, debug_flag=False):

    result_dict = {}
    result_json = None
    language_list = []
    cur_language_id = None
    cur_dictionary_id = None
    cur_perspective_id = None

    dictionary_title = None
    perspective_title = None

    # Getting set of cte
    (
        language_cte, dictionary_cte, perspective_cte, field_cte

    ) = get_cte_set(only_in_toc, offset, limit)

    # Getting perspective_id and etymology fields ids and names in cycle
    for (
        perspective_id,
        (xcript_fid, xcript_fname),
        (xlat_fid, xlat_fname)

    ) in fields_getter(field_cte):

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

            result_dict[language_id] = {}
            result_dict[language_id]['title'] = language_title

            # Logging processed languages
            language_list.append(language_title)

            cur_language_id = language_id

            if debug_flag:
                print(f"*** Language: {language_id} | {language_title}")

        # Once again check conditions for dictionary and perspective
        # and put the data into result_dict

        if dictionary_id != cur_dictionary_id:

            result_dict[language_id][dictionary_id] = {}
            result_dict[language_id][dictionary_id]['title'] = dictionary_title

            cur_dictionary_id = dictionary_id

            if debug_flag:
                print(f"** Dictionary: {dictionary_id} | {dictionary_title}")

        if perspective_id != cur_perspective_id:

            result_dict[language_id][dictionary_id][perspective_id] = {}
            result_dict[language_id][dictionary_id][perspective_id]['title'] = perspective_title
            result_dict[language_id][dictionary_id][perspective_id]['fields'] = [
                (xcript_fid, xcript_fname), (xlat_fid, xlat_fname)
            ]
            result_dict[language_id][dictionary_id][perspective_id]['entities'] = []

            cur_perspective_id = perspective_id

            if debug_flag:
                print(f"\n* Perspective: {perspective_id} | {perspective_title}")

        for (
            xcript_text,
            xlat_text,
            linked_group

        ) in entities_getter(perspective_id, xcript_fid, xlat_fid):

            result_dict[language_id][dictionary_id][perspective_id]['entities'].append(
                [xcript_text, xlat_text, linked_group]
            )

            if debug_flag:
                print(f"\n{xcript_fname}: {xcript_text}")
                print(f"{xlat_fname}: {xlat_text}")
                print(f"Cognate_groups: {str(linked_group)}")
    else:
        # On ending without any break
        result_json = json.dumps(result_dict)

    return result_json, language_list


def perspective_getter(perspective_cte, perspective_id):
    return (
        SyncDBSession
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
        SyncDBSession
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
        SyncDBSession
            .query(
                language_cte.c.language_title)

            .filter(
                language_cte.c.language_cid == language_id[0],
                language_cte.c.language_oid == language_id[1])

            .one())

# Getting cte for languages, dictionaries, perspectives and fields

def get_cte_set(only_in_toc, offset, limit):

    # Getting root languages

    language_init = (
        SyncDBSession
            .query(
                Language,
                literal(0).label('level'))

            .filter(
                Language.parent_client_id == None,
                Language.parent_object_id == None,
                Language.marked_for_deletion == False)

            .cte(recursive=True))

    prnLanguage = aliased(language_init)
    subLanguage = aliased(Language)

    # Recursively getting tree of languages

    language_step = language_init.union_all(
        SyncDBSession
            .query(
                subLanguage,
                (prnLanguage.c.level + 1).label("level"))

            .filter(
                subLanguage.parent_client_id == prnLanguage.c.client_id,
                subLanguage.parent_object_id == prnLanguage.c.object_id,
                subLanguage.marked_for_deletion == False))

    if_only_in_toc = [language_step.c.additional_metadata['toc_mark'] == 'true'] if only_in_toc else []

    get_translation_atom = [
        TranslationGist.marked_for_deletion == False,
        TranslationAtom.parent_id == TranslationGist.id,
        func.length(TranslationAtom.content) > 0,
        TranslationAtom.marked_for_deletion == False ]

    language_cte = (
        SyncDBSession
            .query(
                language_step.c.client_id.label('language_cid'),
                language_step.c.object_id.label('language_oid'),
                func.array_agg(TranslationAtom.content).label('language_title'),
                func.min(language_step.c.level).label('language_level'))

            .filter(
                language_step.c.translation_gist_client_id == TranslationGist.client_id,
                language_step.c.translation_gist_object_id == TranslationGist.object_id,
                *get_translation_atom, *if_only_in_toc)

            .group_by(
                'language_cid',
                'language_oid')

            .offset(offset)
            .limit(limit)
            .cte())

    # Getting dictionaries with self titles

    dictionary_cte = (
        SyncDBSession
            .query(
                Dictionary.parent_client_id.label('language_cid'),
                Dictionary.parent_object_id.label('language_oid'),
                Dictionary.client_id.label('dictionary_cid'),
                Dictionary.object_id.label('dictionary_oid'),
                func.array_agg(TranslationAtom.content).label('dictionary_title'),
                func.min(language_cte.c.language_level).label('language_level'))

            .filter(
                Dictionary.parent_client_id == language_cte.c.language_cid,
                Dictionary.parent_object_id == language_cte.c.language_oid,
                Dictionary.marked_for_deletion == False,
                Dictionary.translation_gist_id == TranslationGist.id,
                *get_translation_atom)

            .group_by(
                'language_cid',
                'language_oid',
                'dictionary_cid',
                'dictionary_oid')

            .cte())

    # Getting perspectives with self titles

    perspective_cte = (
        SyncDBSession
            .query(
                DictionaryPerspective.parent_client_id.label('dictionary_cid'),
                DictionaryPerspective.parent_object_id.label('dictionary_oid'),
                DictionaryPerspective.client_id.label('perspective_cid'),
                DictionaryPerspective.object_id.label('perspective_oid'),
                func.array_agg(TranslationAtom.content).label('perspective_title'),
                func.min(dictionary_cte.c.language_level).label('language_level'))

            .filter(
                DictionaryPerspective.parent_client_id == dictionary_cte.c.dictionary_cid,
                DictionaryPerspective.parent_object_id == dictionary_cte.c.dictionary_oid,
                DictionaryPerspective.marked_for_deletion == False,
                DictionaryPerspective.translation_gist_id == TranslationGist.id,
                *get_translation_atom)

            .group_by(
                'dictionary_cid',
                'dictionary_oid',
                'perspective_cid',
                'perspective_oid')

            .cte())

    # Getting fields with self title

    field_cte = (
        SyncDBSession
            .query(
                perspective_cte.c.perspective_cid,
                perspective_cte.c.perspective_oid,
                Field.client_id.label('field_cid'),
                Field.object_id.label('field_oid'),
                func.array_agg(func.lower(TranslationAtom.content)).label('field_title'),
                func.min(DictionaryPerspectiveToField.position).label('field_position'),
                func.min(perspective_cte.c.language_level).label('language_level'))

            .filter(
                DictionaryPerspectiveToField.parent_client_id == perspective_cte.c.perspective_cid,
                DictionaryPerspectiveToField.parent_object_id == perspective_cte.c.perspective_oid,
                DictionaryPerspectiveToField.marked_for_deletion == False,
                DictionaryPerspectiveToField.field_id == Field.id,
                Field.marked_for_deletion == False,
                Field.translation_gist_id == TranslationGist.id,
                *get_translation_atom, TranslationAtom.locale_id <= 2)

            .group_by(
                perspective_cte.c.perspective_cid,
                perspective_cte.c.perspective_oid,
                'field_cid', 'field_oid')

            .cte())

    return (
        language_cte,
        dictionary_cte,
        perspective_cte,
        field_cte)

# Getting perspectives with transcription, translation and cognates

def fields_getter(field_cte):

    def has_word(word, text):
        return bool(re.search(r'\b' + word + r'\b', text))

    # Group fields by perspective
    fields_by_perspective = itertools.groupby(
        SyncDBSession.query(field_cte).order_by(field_cte.c.language_level).yield_per(100),
        key=lambda x: (x[0], x[1]))

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
                        has_word("слово", title)):
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


def entities_getter(perspective_id, xcript_fid, xlat_fid):

    xcript_text = None
    xlat_text = None

    entities = (
        SyncDBSession
            .query(
                LexicalEntry.client_id,
                LexicalEntry.object_id,
                Entity.field_id,
                Entity.content)

            .filter(
                LexicalEntry.parent_id == perspective_id,
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
            SyncDBSession
                .execute(
                    f'select * from linked_group(66, 25, {lex_id[0]}, {lex_id[1]})')
                .fetchall())

        entities_by_field = itertools.groupby(entities_group, key = lambda x: (x[2], x[3]))

        for field_id, group in entities_by_field:

            field_text = [x[4] for x in group]

            if field_id == xcript_fid:
                xcript_text = field_text
            elif field_id == xlat_fid:
                xlat_text = field_text

        # Return current found lexical entry with perspective_id

        yield (
            xcript_text,
            xlat_text,
            linked_group)
