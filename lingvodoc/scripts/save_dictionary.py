# -*- coding: utf-8 -*-
import sqlite3
import base64
import requests
import json
import hashlib
import logging
from multiprocessing.util import register_after_fork
import os
import base64
import hashlib
import shutil
import transaction
import tempfile
from pydub import AudioSegment
from collections import defaultdict
from pathvalidate import sanitize_filename
from urllib import request

from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import create_engine
from sqlalchemy import and_
from lingvodoc.models import (
    Client,
    DBSession as SyncDBSession,
    UserBlobs,
    TranslationAtom,
    TranslationGist,
    Field,
    Entity,
    LexicalEntry,
    Dictionary,
    Language,
    User,
    DictionaryPerspectiveToField,
    DictionaryPerspective,
    BaseGroup,
    Group,
    PublishingEntity

)
from lingvodoc.cache.caching import TaskStatus, initialize_cache

from sqlalchemy.orm import (
    sessionmaker,
)

from sqlalchemy import tuple_, and_, or_
from lingvodoc.scripts import elan_parser
from pdb import set_trace
import io
import xlsxwriter
# from time import time
import datetime
import time
import traceback
from os import path, makedirs
from errno import EEXIST
from shutil import copyfileobj


EAF_TIERS = {
    "literary translation": "Translation of Paradigmatic forms",
    "text": "Transcription of Paradigmatic forms",
    "word": "Word",
    "transcription": "Transcription",
    "translation": "Translation"
}
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
field_ids_to_str = lambda x: str(x.field_client_id) + '_' + str(x.field_object_id)


def is_empty(row):
    for col in row:
        if col:
            return False
    return True


def find_lexical_entries_by_tags(tags, session, published):
    result = session.query(LexicalEntry) \
        .join(Entity) \
        .join(PublishingEntity) \
        .filter(Entity.content.in_(tags),
                PublishingEntity.accepted == True,
                Entity.field_client_id == 66,
                Entity.field_object_id == 25)
    if published is not None:
        result = result.filter(PublishingEntity.published == published)
    return result.all()


def find_all_tags(tag, session, published):
    tags = [tag]
    new_tags = [tag]
    while new_tags:
        lexical_entries = find_lexical_entries_by_tags(new_tags, session, published)
        new_tags = list()
        for lex in lexical_entries:
            entities = session.query(Entity)  \
                .join(PublishingEntity) \
                .filter(Entity.parent == lex,
                        PublishingEntity.accepted == True,
                        Entity.field_client_id == 66,
                        Entity.field_object_id == 25)
            if published is not None:
                entities = entities.filter(PublishingEntity.published == published)
            for entity in entities:
                if entity.content not in tags:
                    tags.append(entity.content)
                    new_tags.append(entity.content)
    return tags


def generate_massive_cell(tag, session, text_fields, published):
    result = list()
    tags = find_all_tags(tag, session, published)
    lexical_entries = find_lexical_entries_by_tags(tags, session, published)
    if published is not None:
        lexical_entries = lexical_entries.filter(PublishingEntity.published == published)
    for lex in lexical_entries:
        entities = session.query(Entity) \
            .filter(Entity.parent_client_id == lex.client_id,
                    Entity.parent_object_id == lex.object_id,
                    Entity.marked_for_deletion == False)
        subres = []
        for entity in entities:
            if (entity.field_client_id, entity.field_object_id) in text_fields and entity.content is not None:
                subres.append(entity.content)
        if len(subres) > 0:
            result.append("; ".join(subres))
    if len(result) > 0:
        return "\n".join(result)
    else:
        return ""


def compile_workbook(client_id, object_id, workbook_stream, session, locale_id, published):
    """
    Compiles analysis results into an Excel workbook.
    """

    workbook = xlsxwriter.Workbook(workbook_stream, {'in_memory': True})

    dictionary = session.query(Dictionary).filter_by(client_id=client_id, object_id=object_id,
                                                     marked_for_deletion=False).one()

    text_fields = session.query(Field.client_id, Field.object_id) \
        .filter_by(data_type_translation_gist_client_id=1,
                   data_type_translation_gist_object_id=47).all()
    perspectives = session.query(DictionaryPerspective).filter_by(parent_client_id=client_id,
                                                                  parent_object_id=object_id,
                                                                  marked_for_deletion=False).all()
    for perspective in perspectives:
        perspective_name = perspective.get_translation(client_id, session)
        worksheet = workbook.add_worksheet(name=perspective_name)
        fields = session.query(DictionaryPerspectiveToField).filter_by(parent_client_id=perspective.client_id,
                                                                       parent_object_id=perspective.object_id,
                                                                       marked_for_deletion=False,
                                                                       ).filter(
            tuple_(DictionaryPerspectiveToField.field_client_id, DictionaryPerspectiveToField.field_object_id).in_(
                text_fields)
        ).order_by(DictionaryPerspectiveToField.position).all()
        etymology_field = session.query(DictionaryPerspectiveToField).filter_by(parent_client_id=perspective.client_id,
                                                                                parent_object_id=perspective.object_id,
                                                                                marked_for_deletion=False,
                                                                                field_client_id=66,
                                                                                field_object_id=25
                                                                                ).first()

        field_to_column = {field_ids_to_str(field): counter for counter, field in
                           enumerate(fields)}
        row = 1
        column = 0
        for field in fields:
            worksheet.write(0, column, field.field.get_translation(locale_id, session))
            column += 1

        if etymology_field:
            worksheet.write(0, column, etymology_field.field.get_translation(locale_id, session))

        lexical_entries = session.query(LexicalEntry).join(Entity).join(PublishingEntity) \
            .filter(LexicalEntry.parent_client_id == perspective.client_id,
                    LexicalEntry.parent_object_id == perspective.object_id,
                    LexicalEntry.marked_for_deletion == False,
                    Entity.marked_for_deletion == False,
                    PublishingEntity.accepted == True)
        if published is not None:
            lexical_entries = lexical_entries.filter(PublishingEntity.published == published)
        for lex in lexical_entries:
            row_to_write = ["" for field in fields]
            entities = session.query(Entity).join(PublishingEntity) \
                .filter(Entity.parent_client_id == lex.client_id,
                        Entity.parent_object_id == lex.object_id,
                        Entity.marked_for_deletion == False,
                        PublishingEntity.accepted == True)
            if published is not None:
                entities = entities.filter(PublishingEntity.published == published)
            for entity in entities:
                ent_field_ids = field_ids_to_str(entity)
                if ent_field_ids in field_to_column:
                    if row_to_write[field_to_column[ent_field_ids]] == "":
                        row_to_write[field_to_column[ent_field_ids]] = entity.content
                    else:
                        row_to_write[field_to_column[ent_field_ids]] += "\n" + entity.content
                if etymology_field and len(row_to_write) == len(fields) and ent_field_ids == "66_25":
                    row_to_write.append(generate_massive_cell(entity.content, session, text_fields, published))
            if not is_empty(row_to_write):
                worksheet.write_row(row, 0, row_to_write)
                row += 1
    return


def save(
        client_id,
        object_id,
        storage,
        sqlalchemy_url,
        task_key,
        cache_kwargs,
        dict_name,
        locale_id,
        published
):  # :(

    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)

    engine = create_engine(sqlalchemy_url)
    register_after_fork(engine, engine.dispose)
    log = logging.getLogger(__name__)
    Session = sessionmaker(bind=engine)
    session = Session()
    task_status.set(3, 20, 'Running async process')

    workbook_stream = io.BytesIO()

    try:
        compile_workbook(client_id, object_id, workbook_stream, session, locale_id, published)

        workbook_stream.seek(0)

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('compile_workbook: exception')
        log.debug(traceback_string)

        # If we failed to create an Excel file, we terminate with error.

        task_status.set(4, 100,
                        'Finished (ERROR), result compilation error')

        return {'error': 'result compilation error'}

    # Name(s) of the resulting file(s) includes dictionary name, perspective name and current date.

    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    result_filename = '{0} - {1:04d}.{2:02d}.{3:02d}'.format(
        dict_name[:64],
        current_datetime.year,
        current_datetime.month,
        current_datetime.day)

    table_filename = sanitize_filename(result_filename + '.xlsx')

    cur_time = time.time()
    storage_dir = path.join(storage['path'], 'save_dictionary', str(cur_time))
    makedirs(storage_dir, exist_ok=True)

    # Storing file with the results.

    storage_path = path.join(storage_dir, table_filename)
    directory = path.dirname(storage_path)

    try:
        makedirs(directory)

    except OSError as exception:
        if exception.errno != EEXIST:
            raise

    # If the name of the result file is too long, we try again with a shorter name.

    try:
        with open(storage_path, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    except OSError as os_error:

        if os_error.errno != 36:
            raise

        result_filename = '{0} - {1:04d}.{2:02d}.{3:02d}'.format(
            dict_name[:32],
            current_datetime.year,
            current_datetime.month,
            current_datetime.day)

        table_filename = sanitize_filename(result_filename + '.xlsx')
        storage_path = path.join(storage_dir, table_filename)

        with open(storage_path, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    # Successfully compiled phonology, finishing and returning links to files with results.

    url_list = [

        ''.join([
            storage['prefix'],
            storage['static_route'],
            'save_dictionary', '/',
            str(cur_time), '/',
            filename])

        for filename in [table_filename]]

    task_status.set(4, 100, 'Finished', result_link_list=url_list)

    session.commit()
    engine.dispose()
    return


def save_dictionary(
        client_id,
        object_id,
        storage,
        sqlalchemy_url,
        task_key,
        cache_kwargs,
        dict_name,
        locale_id,
        published
):
    save(
        client_id,
        object_id,
        storage,
        sqlalchemy_url,
        task_key,
        cache_kwargs,
        dict_name,
        locale_id,
        published
    )
