
# Standard library imports.

import collections
import copy
import itertools
import json
import logging
import math
import pprint
import traceback

# External imports.

import pylev
from pyramid.response import Response
from pyramid.request import Request
from pyramid.view import view_config

from sqlalchemy import and_, BigInteger, cast, extract, func, tuple_, create_engine
from sqlalchemy.orm import aliased

from pyramid.view import view_config

from sqlalchemy.orm.attributes import flag_modified

from transaction import manager

# Lingvodoc imports.

from lingvodoc.cache.caching import initialize_cache, TaskStatus

import lingvodoc.merge_perspectives as merge_perspectives
from lingvodoc.merge_perspectives import mergeDicts
from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    ENGLISH_LOCALE,
    Entity,
    Field,
    LexicalEntry,
    PublishingEntity,
    RUSSIAN_LOCALE,
    TranslationAtom,
    TranslationGist,
    User,
    Group,
    BaseGroup,
    DictionaryPerspective,
    ObjectTOC
)

from lingvodoc.views.v2.merge import (
    merge_bulk_async_try,
    merge_bulk_task_try,
    merge_bulk_try,
    merge_suggestions_compute
)

from lingvodoc.views.v2.utils import message, unimplemented
from lingvodoc.utils.creation import add_user_to_group
from lingvodoc.schema.gql_holders import ResponseError

from lingvodoc.views.v2.utils import (
    message,
    remove_deleted,
    unimplemented
)

from lingvodoc.queue.celery import celery


log = logging.getLogger(__name__)


def merge_suggestions(request,
                      perspective_client_id, perspective_object_id,
                      algorithm,
                      entity_type_primary = 'Transcription', entity_type_secondary = 'Translation',
                      threshold = 0.1, levenshtein = 1,
                      field_selection_list = None, locale_id = 2):
    """
    Finds groups of mergeable lexical entries according to specified criteria.
    """

    if algorithm not in {'simple', 'fields'}:
        raise ResponseError('Unknown entity matching algorithm \'{0}\'.'.format(algorithm))

    # Computing merge suggestions.

    entry_data_list, match_result_list, user_has_permissions = merge_suggestions_compute(
        request,
        perspective_client_id, perspective_object_id,
        algorithm,
        entity_type_primary, entity_type_secondary,
        threshold, levenshtein,
        field_selection_list, locale_id)

    if not match_result_list:

        return {
            'match_result': [],
            'user_has_permissions': user_has_permissions}

    # Returning match data together with data of matching lexical entries.

    return {

        'match_result': [
            {"lexical_entries": [list(id_a), list(id_b)],
             "confidence": confidence}
            for id_a, id_b, confidence in match_result_list],

        'user_has_permissions': user_has_permissions}


def merge_bulk(request, publish_any, group_list):
    """
    Merges multiple groups of lexical entries, provided that each group is a subset of a single perspective,
    returns client/object ids of new lexical entries, a new entry for each merged group.
    """

    def error_f(error_message):
        raise ResponseError(message = error_message)

    try_ok, merge_context = merge_bulk_try(
        request, publish_any, group_list, error_f)

    # Returning identifiers of new lexical entries.

    return merge_context.result_list


@celery.task
def merge_bulk_task(task_key, cache_kwargs, sqlalchemy_url, merge_context):
    """
    Performs asynchronous merge.
    """

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)

    initialize_cache(cache_kwargs)
    task_status = TaskStatus.get_from_cache(task_key)

    with manager:
        try_ok, traceback_string = merge_bulk_task_try(task_status, merge_context)

    if not try_ok:
        raise ResponseError(message='\n' + traceback_string)


def merge_bulk_async(request, publish_any, group_list):
    """
    Launches asynchronous background merge task, see 'merge_bulk' procedure.
    """

    try_ok, task_status = merge_bulk_async_try(request,
        request.json['publish_any'],
        request.json['group_list'])

    # If something was not as expected, we report it.

    if not try_ok:

        traceback_string = result
        raise ResponseError(message='\n' + traceback_string)

    # Launched asynchronous merge task successfully.

    task_status = result
    return task_status.key if task_status is not None else ''

