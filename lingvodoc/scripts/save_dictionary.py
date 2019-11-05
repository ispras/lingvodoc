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
import pprint
import shutil
import transaction
import tempfile
from pydub import AudioSegment
from collections import defaultdict
from pathvalidate import sanitize_filename
from urllib import request

import sqlalchemy
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import and_, create_engine, func

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
from lingvodoc.utils import explain_analyze

from sqlalchemy.orm import (
    aliased, sessionmaker,
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
import uuid


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


def find_lexical_entries_by_tags(tags, session, published):
    result = session.query(LexicalEntry) \
        .join(Entity) \
        .join(PublishingEntity) \
        .filter(
            LexicalEntry.marked_for_deletion == False,
            Entity.content.in_(tags),
            Entity.marked_for_deletion == False,
            Entity.field_client_id == 66,
            Entity.field_object_id == 25,
            PublishingEntity.accepted == True)
    if published is not None:
        result = result.filter(PublishingEntity.published == published)
    return result.all()


def find_all_tags(tag, session, published):
    tags = {tag}
    new_tags = {tag}
    while new_tags:
        lexical_entries = find_lexical_entries_by_tags(new_tags, session, published)
        new_tags = set()
        for lex in lexical_entries:
            entities = session.query(Entity)  \
                .join(PublishingEntity) \
                .filter(
                    Entity.marked_for_deletion == False,
                    Entity.parent == lex,
                    Entity.field_client_id == 66,
                    Entity.field_object_id == 25,
                    PublishingEntity.accepted == True)
            if published is not None:
                entities = entities.filter(PublishingEntity.published == published)
            for entity in entities:
                if entity.content not in tags:
                    tags.add(entity.content)
                    new_tags.add(entity.content)
    return tags


def find_group_by_tags(
    session,
    entry_id_set,
    tag_set,
    tag_list,
    field_client_id,
    field_object_id,
    published = None):
    """
    Optimized retrieval of a group of lexical entries linked by a set of tags from a specified field.
    """

    # While we have tags we don't have all lexical entries for,
    # we get these all entries of these tags...

    while tag_list:

        entry_id_query = (

            session.query(
                LexicalEntry.client_id,
                LexicalEntry.object_id)

            .filter(
                LexicalEntry.marked_for_deletion == False,
                Entity.parent_client_id == LexicalEntry.client_id,
                Entity.parent_object_id == LexicalEntry.object_id,
                Entity.field_client_id == field_client_id,
                Entity.field_object_id == field_object_id,
                Entity.marked_for_deletion == False,
                Entity.content.in_(tag_list),
                PublishingEntity.client_id == Entity.client_id,
                PublishingEntity.object_id == Entity.object_id,
                PublishingEntity.accepted == True))

        if published is not None:

            entry_id_query = entry_id_query.filter(
                PublishingEntity.published == published)

        entry_id_list = []

        for entry_id in entry_id_query.distinct():

            if entry_id not in entry_id_set:

                entry_id_set.add(entry_id)
                entry_id_list.append(entry_id)

        if not entry_id_list:
            break

        # And then get all tags for entries we haven't already done it for.

        tag_query = (

            session.query(
                Entity.content)

            .filter(
                tuple_(Entity.parent_client_id, Entity.parent_object_id)
                    .in_(entry_id_list),
                Entity.field_client_id == field_client_id,
                Entity.field_object_id == field_object_id,
                Entity.marked_for_deletion == False,
                PublishingEntity.client_id == Entity.client_id,
                PublishingEntity.object_id == Entity.object_id,
                PublishingEntity.accepted == True))

        if published is not None:

            tag_query = tag_query.filter(
                PublishingEntity.published == published)

        tag_list = []

        for tag in tag_query.distinct():

            if tag not in tag_set:

                tag_set.add(tag)
                tag_list.append(tag)

    # Showing what we've found.

    log.debug(
        '\nfind_group_by_tags({0}, {1}):'
        '\nlen(tag_set): {2}'
        '\nlen(entry_id_set): {3}'.format(
        field_client_id,
        field_object_id,
        len(tag_set),
        len(entry_id_set)))

    return entry_id_set, tag_set


def generate_massive_cell_simple(
    tag,
    session,
    text_fields,
    published):
    """
    Gathers info of etymologically linked lexical entries via standard simple method.
    """

    result_list = []

    # Current standard method.

    tags = find_all_tags(tag, session, published)
    lexical_entries = find_lexical_entries_by_tags(tags, session, published)

    for lex in lexical_entries:
        entities = session.query(Entity).join(PublishingEntity) \
            .filter(Entity.parent_client_id == lex.client_id,
                    Entity.parent_object_id == lex.object_id,
                    PublishingEntity.accepted == True,
                    Entity.marked_for_deletion == False)
        if published is not None:
            entities = entities.filter(PublishingEntity.published == published)
        subres = []
        for entity in entities:
            if (entity.field_client_id, entity.field_object_id) in text_fields and entity.content is not None:
                subres.append(entity.content)
        if len(subres) > 0:
            result_list.append("; ".join(subres))

    return "\n".join(result_list)


def generate_massive_cell_optimized(
    tag,
    session,
    text_fields,
    published):
    """
    Optimized gathering of etymologically linked lexical entries info.
    """

    entry_id_set, tag_set = (

        find_group_by_tags(
            session, set(), {tag}, [tag], 66, 25, published))

    query = (
            
        session

            .query()
            
            .filter(
                Entity.marked_for_deletion == False,
                tuple_(Entity.parent_client_id, Entity.parent_object_id)
                    .in_(entry_id_set),
                tuple_(Entity.field_client_id, Entity.field_object_id)
                    .in_(text_fields),
                Entity.content != None,
                PublishingEntity.client_id == Entity.client_id,
                PublishingEntity.object_id == Entity.object_id,
                PublishingEntity.accepted == True)

            .add_columns(
                func.string_agg(Entity.content, '; ')
                .label('content'))
            
            .group_by(
                Entity.parent_client_id, Entity.parent_object_id))

    if published is not None:

        query = query.filter(
            PublishingEntity.published == published)

    return '\n'.join(
        row[0] for row in query)


def generate_massive_cell_cte(
    tag,
    session,
    text_fields,
    published):
    """
    Gathering of etymologically linked lexical entries info using recursive CTE.

    Takes much more time then the back-and-forth implementation in generate_massive_cell_optimized() due to
    inefficiences stemming from the recursive CTE query restrictions.
    """

    entry_id_query = (
            
        session.query(
            LexicalEntry.client_id,
            LexicalEntry.object_id)

        .filter(
            LexicalEntry.marked_for_deletion == False,
            Entity.parent_client_id == LexicalEntry.client_id,
            Entity.parent_object_id == LexicalEntry.object_id,
            Entity.field_client_id == 66,
            Entity.field_object_id == 25,
            Entity.marked_for_deletion == False,
            Entity.content == tag,
            PublishingEntity.client_id == Entity.client_id,
            PublishingEntity.object_id == Entity.object_id,
            PublishingEntity.accepted == True))

    if published is not None:

        entry_id_query = entry_id_query.filter(
            PublishingEntity.published == published)

    # See https://stackoverflow.com/questions/53186429/sqlalchemy-simple-recursive-cte-query for Sqlalchemy
    # resursive CTE example.

    cte_query = entry_id_query.cte(
        recursive = True, name = 'entry_id')

    E_entry = aliased(Entity, name = 'E1')
    E_tag = aliased(Entity, name = 'E2')

    P_entry = aliased(PublishingEntity, name = 'P1')
    P_tag = aliased(PublishingEntity, name = 'P2')

    recursive_query = (

        session.query(
            LexicalEntry.client_id,
            LexicalEntry.object_id)
        
        .filter(
            LexicalEntry.marked_for_deletion == False,
            E_entry.parent_client_id == LexicalEntry.client_id,
            E_entry.parent_object_id == LexicalEntry.object_id,
            E_entry.field_client_id == 66,
            E_entry.field_object_id == 25,
            E_entry.marked_for_deletion == False,
            P_entry.client_id == E_entry.client_id,
            P_entry.object_id == E_entry.object_id,
            P_entry.accepted == True,
            E_entry.content == E_tag.content,
            E_tag.parent_client_id == cte_query.c.client_id,
            E_tag.parent_object_id == cte_query.c.object_id,
            E_tag.field_client_id == 66,
            E_tag.field_object_id == 25,
            E_tag.marked_for_deletion == False,
            P_tag.client_id == E_tag.client_id,
            P_tag.object_id == E_tag.object_id,
            P_tag.accepted == True))

    if published is not None:

        recursive_query = (
                
            recursive_query.filter(
                P_entry.published == published,
                P_tag.published == published))

    cte_query = cte_query.union(
        recursive_query.distinct())

    # Query for required cell data.

    content_query = (
            
        session

            .query()
            
            .filter(
                Entity.marked_for_deletion == False,
                tuple_(Entity.parent_client_id, Entity.parent_object_id)
                    .in_(session.query(cte_query)),
                tuple_(Entity.field_client_id, Entity.field_object_id)
                    .in_(text_fields),
                Entity.content != None,
                PublishingEntity.client_id == Entity.client_id,
                PublishingEntity.object_id == Entity.object_id,
                PublishingEntity.accepted == True)

            .add_columns(
                func.string_agg(Entity.content, '; ')
                .label('content'))
            
            .group_by(
                Entity.parent_client_id, Entity.parent_object_id))

    if published is not None:

        content_query = content_query.filter(
            PublishingEntity.published == published)

    log.debug(
        '\ncontent_query:\n' +
        str(content_query))

    return '\n'.join(
        row[0] for row in content_query)


def generate_massive_cell_temp_table(
    tag,
    session,
    text_field_id_table_name,
    published,
    __debug_flag__ = False):
    """
    Gathering of etymologically linked lexical entries info using temporary tables.
    """

    uuid_str = str(uuid.uuid4()).replace('-', '_')

    entry_id_table_name = 'entry_id_table_' + uuid_str
    tag_table_name = 'tag_table_' + uuid_str

    tag_list_name = 'tag_list_' + uuid_str
    tag_list_prev_name = 'tag_list_prev_' + uuid_str

    published_str = (
        '' if published is None else
        ' and P.published = ' + str(published).lower())

    # Temporary table for lexical entry ids.

    sql_str = ('''

        create temporary table
        
        {entry_id_table_name} (
          client_id BIGINT,
          object_id BIGINT,
          primary key (client_id, object_id))

        on commit drop;

        insert into {entry_id_table_name}

        select
          L.client_id,
          L.object_id

        from
          lexicalentry L,
          public.entity E,
          publishingentity P

        where
          L.marked_for_deletion = false and
          E.parent_client_id = L.client_id and
          E.parent_object_id = L.object_id and
          E.field_client_id = 66 and
          E.field_object_id = 25 and
          E.marked_for_deletion = false and
          E.content = :tag and
          P.client_id = E.client_id and
          P.object_id = E.object_id and
          P.accepted = true{0}

        on conflict do nothing;

        '''.format(
            published_str,
            entry_id_table_name = entry_id_table_name))

    session.execute(
        sql_str, {'tag': tag})

    # Temporary table for tags.

    sql_str = ('''

        create temporary table

        {tag_table_name} (
          tag TEXT primary key)

        on commit drop;

        insert into {tag_table_name}
          values (:tag);

        create temporary table
        
        {tag_list_name}
        
        on commit drop as
        with

        tag_cte as (

          insert into {tag_table_name}
          select distinct E.content

          from
            public.entity E,
            publishingentity P

          where
            (E.parent_client_id, E.parent_object_id) in (
              select * from {entry_id_table_name}) and
            E.field_client_id = 66 and
            E.field_object_id = 25 and
            E.marked_for_deletion = false and
            P.client_id = E.client_id and
            P.object_id = E.object_id and
            P.accepted = true{0}

          on conflict do nothing
          returning *)
        
        select * from tag_cte;

        '''.format(
            published_str,
            entry_id_table_name = entry_id_table_name,
            tag_table_name = tag_table_name,
            tag_list_name = tag_list_name))

    session.execute(
        sql_str, {'tag': tag})

    # While we have tags we don't have all lexical entries for, we get these all new entries of these tags
    # and then all new tags of this new entries.

    exists_str = '''

        select exists (
          select 1 from {tag_list_name});
          
        '''.format(
            tag_list_name = tag_list_name)

    while session.execute(exists_str).scalar():

        sql_str = ('''

            alter table {tag_list_name}
              rename to {tag_list_prev_name};

            create temporary table
            
            {tag_list_name}
            
            on commit drop as
            with

            entry_id_cte as (

              insert into {entry_id_table_name}

              select distinct
                L.client_id,
                L.object_id

              from
                lexicalentry L,
                public.entity E,
                publishingentity P

              where
                L.marked_for_deletion = false and
                E.parent_client_id = L.client_id and
                E.parent_object_id = L.object_id and
                E.field_client_id = 66 and
                E.field_object_id = 25 and
                E.marked_for_deletion = false and
                E.content in (
                  select * from {tag_list_prev_name}) and
                P.client_id = E.client_id and
                P.object_id = E.object_id and
                P.accepted = true{0}

              on conflict do nothing
              returning *),

            tag_cte as (

              insert into {tag_table_name}
              select distinct E.content

              from
                public.entity E,
                publishingentity P

              where
                (E.parent_client_id, E.parent_object_id) in (
                  select * from entry_id_cte) and
                E.field_client_id = 66 and
                E.field_object_id = 25 and
                E.marked_for_deletion = false and
                P.client_id = E.client_id and
                P.object_id = E.object_id and
                P.accepted = true{0}

              on conflict do nothing
              returning *)
            
            select * from tag_cte;

            drop table {tag_list_prev_name};

            '''.format(
                published_str,
                entry_id_table_name = entry_id_table_name,
                tag_table_name = tag_table_name,
                tag_list_name = tag_list_name,
                tag_list_prev_name = tag_list_prev_name))

        session.execute(
            sql_str)

    # And now we get required info of the linked lexical entries.

    query = (
            
        session

            .query()
            
            .filter(
                Entity.marked_for_deletion == False,

                tuple_(
                    Entity.parent_client_id, Entity.parent_object_id)

                    .in_(sqlalchemy.text(
                        'select * from ' + entry_id_table_name)),

                tuple_(
                    Entity.field_client_id, Entity.field_object_id)

                    .in_(sqlalchemy.text(
                        'select * from ' + text_field_id_table_name)),

                Entity.content != None,
                PublishingEntity.client_id == Entity.client_id,
                PublishingEntity.object_id == Entity.object_id,
                PublishingEntity.accepted == True)

            .add_columns(
                func.string_agg(Entity.content, '; ')
                .label('content'))
            
            .group_by(
                Entity.parent_client_id, Entity.parent_object_id))

    if published is not None:

        query = query.filter(
            PublishingEntity.published == published)

    if __debug_flag__:

        # Showing PostgreSQL's explain analyze, if required.

        row_list = (
            self.session.execute(
                explain_analyze(query)).fetchall())

        log.debug(''.join(
            '\n' + row[0] for row in row_list))

    return '\n'.join(
        row[0] for row in query)


def generate_massive_cell_plpgsql(
    tag,
    session,
    published):
    """
    Gathering of etymologically linked lexical entries info using stored PL/pgSQL procedure.
    """

    row_list = (
            
        session.execute(
            'select etymology_text(:tag, :publish)',
            {'tag': tag, 'publish': published}).fetchall())

    return '\n'.join(
        row[0] for row in row_list)


class Save_Context(object):
    """
    Holds data of the saving of dictionary/dictionaries into an XLSX workbook.

    Also used in advanced_search.
    """

    def __init__(
        self,
        locale_id,
        session,
        __debug_flag__ = False):

        self.locale_id = locale_id
        self.session = session

        self.stream = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.stream, {'in_memory': True})

        # Getting up-to-date text field info.

        self.session.execute(
            'refresh materialized view text_field_id_view;')

        self.etymology_dict = {}

        if __debug_flag__:

            # Simple text field ids query.

            self.text_field_query = session.query(
                Field.client_id, Field.object_id).filter_by(
                data_type_translation_gist_client_id = 1,
                data_type_translation_gist_object_id = 47,
                marked_for_deletion = False)

            # Simple list of text field ids.

            self.text_fields = self.text_field_query.all()

            # Temporary table with text field ids.

            self.text_field_id_table_name = (
                'text_field_id_table_' +
                str(uuid.uuid4()).replace('-', '_'))

            self.session.execute('''

                create temporary table {text_field_id_table_name} (
                  client_id BIGINT,
                  object_id BIGINT,
                  primary key (client_id, object_id))
                on commit drop;

                insert into {text_field_id_table_name}
                select client_id, object_id
                from field
                where
                data_type_translation_gist_client_id = 1 and
                data_type_translation_gist_object_id = 47 and
                marked_for_deletion = false;

                '''.format(
                    text_field_id_table_name = self.text_field_id_table_name))

    def ready_perspective(
        self,
        perspective,
        dictionary = None,
        list_flag = False,
        __debug_flag__ = False):
        """
        Prepares for saving data of lexical entries of another perspective.
        """

        perspective_name = perspective.get_translation(self.locale_id, self.session)

        for c in '\x00*/:?[\\]':
            perspective_name = perspective_name.replace(c, '')

        id_str = '_{0}_{1}'.format(
            perspective.client_id, perspective.object_id)

        worksheet_name = (
            perspective_name[:31 - len(id_str)] + id_str)

        self.worksheet = (
            self.workbook.add_worksheet(name = worksheet_name))

        # Listing dictionary and perspective names, if required.

        self.row = 0

        if list_flag:

            if dictionary:

                self.worksheet.write(self.row, 0,
                    dictionary.get_translation(self.locale_id, self.session))

                self.row += 1

            self.worksheet.write(self.row, 0,
                perspective.get_translation(self.locale_id, self.session))

            self.row += 1

        # Getting field data.

        field_query = (
                
            self.session
                .query(DictionaryPerspectiveToField)

                .filter_by(
                    parent_client_id=perspective.client_id,
                    parent_object_id=perspective.object_id,
                    marked_for_deletion=False)
                
                .filter(tuple_(
                    DictionaryPerspectiveToField.field_client_id,
                    DictionaryPerspectiveToField.field_object_id)
                        .in_(sqlalchemy.text('select * from text_field_id_view')))

                .order_by(DictionaryPerspectiveToField.position))

        if __debug_flag__:

            # Showing PostgreSQL's explain analyze, if required.

            row_list = (
                self.session.execute(
                    explain_analyze(field_query)).fetchall())

            log.debug(''.join(
                '\n' + row[0] for row in row_list))

        self.fields = field_query.all()

        # Etymology field.

        self.etymology_field = (
            self.session.query(DictionaryPerspectiveToField).filter_by(
                parent_client_id=perspective.client_id,
                parent_object_id=perspective.object_id,
                marked_for_deletion=False,
                field_client_id=66,
                field_object_id=25).first())

        self.field_to_column = {
            field_ids_to_str(field): counter
            for counter, field in enumerate(self.fields)}

        # Listing fields.

        column = 0

        for field in self.fields:

            self.worksheet.write(self.row, column,
                field.field.get_translation(self.locale_id, self.session))

            column += 1

        if self.etymology_field:

            self.worksheet.write(self.row, column,
                self.etymology_field.field.get_translation(self.locale_id, self.session))

        self.row += 1

    def get_etymology_text(
        self,
        tag,
        published):
        """
        Gets info of etymologycally linked lexical entries, caches results.
        """

        row_list = (

            self.session.execute(
                'select * from etymology_group_text(:tag, :publish)',
                {'tag': tag, 'publish': published}).fetchall())

        entry_id_list = []
        text_list = []

        for client_id, object_id, text in row_list:

            entry_id_list.append((client_id, object_id))
            text_list.append(text)

        etymology_text = '\n'.join(text_list)

        for entry_id in entry_id_list:
            self.etymology_dict[entry_id] = etymology_text

        return etymology_text

    def save_lexical_entry(
        self,
        entry,
        published = None,
        accepted = True):
        """
        Save data of a lexical entry of the current perspective.
        """

        row_to_write = ["" for field in self.fields]

        entities = (
            self.session.query(Entity).filter(
                Entity.parent_client_id == entry.client_id,
                Entity.parent_object_id == entry.object_id,
                Entity.marked_for_deletion == False))

        if published is not None or accepted is not None:

            entities = entities.join(PublishingEntity)

            if published is not None:
                entities = entities.filter(PublishingEntity.published == published)

            if accepted is not None:
                entities = entities.filter(PublishingEntity.accepted == accepted)

        for entity in entities:
            ent_field_ids = field_ids_to_str(entity)

            if ent_field_ids in self.field_to_column:

                if row_to_write[self.field_to_column[ent_field_ids]] == "":
                    row_to_write[self.field_to_column[ent_field_ids]] = entity.content

                else:
                    row_to_write[self.field_to_column[ent_field_ids]] += "\n" + entity.content

            elif (
                ent_field_ids == "66_25" and
                self.etymology_field and
                len(row_to_write) == len(self.fields)):

                entry_id = (entry.client_id, entry.object_id)

                if entry_id in self.etymology_dict:

                    row_to_write.append(
                        self.etymology_dict[entry_id])

                else:

                    row_to_write.append(
                        self.get_etymology_text(
                            entity.content, published))

        if any(row_to_write):

            self.worksheet.write_row(self.row, 0, row_to_write)
            self.row += 1


def compile_workbook(context, client_id, object_id, session, locale_id, published):
    """
    Compiles analysis results into an Excel workbook.
    """

    dictionary = session.query(Dictionary).filter_by(client_id=client_id, object_id=object_id,
                                                     marked_for_deletion=False).one()

    perspectives = session.query(DictionaryPerspective).filter_by(parent_client_id=client_id,
                                                                  parent_object_id=object_id,
                                                                  marked_for_deletion=False).all()

    for perspective in perspectives:

        context.ready_perspective(perspective)

        lexical_entries = session.query(LexicalEntry).join(Entity).join(PublishingEntity) \
            .filter(LexicalEntry.parent_client_id == perspective.client_id,
                    LexicalEntry.parent_object_id == perspective.object_id,
                    LexicalEntry.marked_for_deletion == False,
                    Entity.marked_for_deletion == False,
                    PublishingEntity.accepted == True)
        if published is not None:
            lexical_entries = lexical_entries.filter(PublishingEntity.published == published)

        for lex in lexical_entries:
            context.save_lexical_entry(lex, published)

    context.workbook.close()


# @profile()
def save(
    client_id,
    object_id,
    storage,
    sqlalchemy_url,
    task_key,
    cache_kwargs,
    dict_name,
    locale_id,
    published,
    __debug_flag__ = False
):  # :(

    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key) if task_key else None

    engine = create_engine(sqlalchemy_url)
    register_after_fork(engine, engine.dispose)
    log = logging.getLogger(__name__)
    Session = sessionmaker(bind=engine)
    session = Session()

    if task_status:
        task_status.set(3, 20, 'Running async process')

    save_context = Save_Context(
        locale_id, session, __debug_flag__)

    try:
        compile_workbook(save_context, client_id, object_id, session, locale_id, published)

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('compile_workbook: exception')
        log.debug(traceback_string)

        # If we failed to create an Excel file, we terminate with error.

        if task_status:
            task_status.set(4, 100, 'Finished (ERROR), result compilation error')

        return {'error': 'result compilation error'}

    # Name(s) of the resulting file(s) includes dictionary name, perspective name and current date.

    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    result_filename = '{0} - {1:04d}.{2:02d}.{3:02d}'.format(
        dict_name[:64],
        current_datetime.year,
        current_datetime.month,
        current_datetime.day)

    table_filename = sanitize_filename(result_filename + '.xlsx')

    # cur_time = time.time()
    dictionary = session.query(Dictionary).filter_by(client_id=client_id, object_id=object_id).one()
    dict_status_atom = session.query(TranslationAtom).filter_by(
        parent_client_id=dictionary.state_translation_gist_client_id,
        parent_object_id=dictionary.state_translation_gist_object_id,
        locale_id=2).first()
    if not dict_status_atom:
        dict_status = 'translation_failure'
    else:
        dict_status = dict_status_atom.content

    if published is None:
        cur_folder = 'edit'
    elif published is True:
        cur_folder = 'view'
    else:
        cur_folder = 'should_be_impossible'

    storage_dir = path.join(storage['path'], 'save_dictionary', dict_status, cur_folder)
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

            save_context.stream.seek(0)
            copyfileobj(save_context.stream, workbook_file)

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

            save_context.stream.seek(0)
            copyfileobj(save_context.stream, workbook_file)

    if __debug_flag__:

        with open(table_filename, 'wb') as xlsx_file:

            save_context.stream.seek(0)
            copyfileobj(save_context.stream, xlsx_file)

    # Successfully saved dictionary, finishing and returning links to files with results.

    url_list = [

        ''.join([
            storage['prefix'],
            storage['static_route'],
            'save_dictionary', '/',
            dict_status, '/',
            cur_folder, '/',
            filename])

        for filename in [table_filename]]

    if task_status:
        task_status.set(4, 100, 'Finished', result_link_list=url_list)

    session.commit()
    engine.dispose()


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
