
# Standard library imports.

import base64
import collections
import datetime
from errno import EEXIST
from hashlib import md5
import io
import itertools
import logging
import math
from os import makedirs, path
import pprint
import re
from shutil import copyfileobj
import sndhdr
import string
import tempfile
from time import time
import traceback

import urllib.request
import urllib.parse

import zipfile

# External imports.

import cchardet as chardet
from celery.utils.log import get_task_logger

# So that matplotlib does not require display stuff, in particular, tkinter. See e.g. https://
# stackoverflow.com/questions/4931376/generating-matplotlib-graphs-without-a-running-x-server.
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as pyplot
from mpl_toolkits.mplot3d import Axes3D

import numpy
import numpy.fft
import numpy.linalg
import numpy.polynomial

from pathvalidate import sanitize_filename

import pydub
from pydub.utils import ratio_to_db

import pympi

from pyramid.httpexceptions import HTTPInternalServerError, HTTPPreconditionFailed, HTTPOk
from pyramid.view import view_config

import scipy.linalg

from sqlalchemy import and_, create_engine, func
from sqlalchemy.orm import aliased

from transaction import manager
import xlsxwriter

# Project imports.

import lingvodoc.cache.caching as caching
from lingvodoc.cache.caching import CACHE, initialize_cache, TaskStatus

from lingvodoc.views.v2.phonology import (
    async_phonology,
    async_sound_and_markup,
    get_skip_list,
    get_tier_list,
    get_link_perspective_data,
    std_phonology,
    std_sound_and_markup)

from lingvodoc.schema.gql_holders import ResponseError
from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    DictionaryPerspectiveToField,
    Entity,
    Field,
    LexicalEntry,
    PublishingEntity,
    TranslationGist,
    TranslationAtom
)

from lingvodoc.queue.celery import celery
from lingvodoc.views.v2.utils import anonymous_userid, message, storage_file, unimplemented


# Setting up logging.
log = logging.getLogger(__name__)


# Trying to set up celery logging.
celery_log = get_task_logger(__name__)
celery_log.setLevel(logging.DEBUG)


def gql_phonology(request, locale_id, args):
    """
    Computes phonology of a specified perspective.
    """

    task_status = None

    try:
        log.debug(
            'phonology {0}/{1}: {2}, {3}, {4}, {5}, {6}, {7}, {8}, {9}, {10}, {11}, {12}, {13}'.format(
                args.perspective_cid, args.perspective_oid,
                args.group_by_description, args.vowel_selection,
                args.maybe_translation_field,
                args.only_first_translation, args.use_automatic_markup,
                args.maybe_tier_list,
                args.keep_list, args.join_list,
                args.chart_threshold,
                args.generate_csv,
                args.link_field_list,
                args.link_perspective_list))

        args.get_pd_names(locale_id)

        # Phonology task status setup.

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        task_status = TaskStatus(user_id, 'Phonology compilation',
            '{0}: {1}'.format(args.dictionary_name, args.perspective_name), 4)

        # Performing either synchronous or asynchronous phonology compilation.

        task_key = task_status.key

        cache_kwargs = request.registry.settings['cache_kwargs']
        sqlalchemy_url = request.registry.settings['sqlalchemy.url']
        storage = request.registry.settings['storage']

        return (std_phonology if args.synchronous else async_phonology.delay)(
            args, task_key, cache_kwargs, storage, sqlalchemy_url)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(4, 100, 'Finished (ERROR), external error')

        raise ResponseError(message = 'External error')


def gql_phonology_tier_list(perspective_cid, perspective_oid):
    """
    Gets a list of names of phonology markup tiers for specified perspective.
    """

    try_ok, result = get_tier_list(perspective_cid, perspective_oid)

    if not try_ok:

        traceback_string = result
        raise ResponseError(message = 'External error:\n' + traceback_string)

    return result


def gql_phonology_skip_list(perspective_cid, perspective_oid):
    """
    Gets a list of characters skipped during processing of vowel phonology, and a list of characters from
    markup intervals adjacent to intervals with vowel markup, for specified perspective.
    """

    try_ok, result = get_skip_list(perspective_cid, perspective_oid)

    if not try_ok:

        traceback_string = result
        raise ResponseError(message = 'External error:\n' + traceback_string)

    return result


def gql_phonology_link_perspective_data(perspective_id, field_id_list):
    """
    Gets info of perspectives holding data linked from a specified perspective through given link fields.
    """

    try_ok, result = get_link_perspective_data(perspective_id, field_id_list)

    if not try_ok:

        traceback_string = result
        raise ResponseError(message = 'External error:\n' + traceback_string)

    return result


def gql_sound_and_markup(request, locale_id, perspective_id, published_mode):
    """
    Tries to launch sound and markup compilation for a specified perspective.
    """

    task_status = None

    try:
        log.debug('sound_and_markup {0}/{1}: {2}'.format(
            perspective_id[0], perspective_id[1], published_mode))

        limit = (None if 'limit' not in request.params else
            int(request.params.get('limit')))

        # Getting perspective and perspective's dictionary info.

        # perspective = DBSession.query(DictionaryPerspective).filter_by(
        #     client_id = perspective_id[0], object_id = perspective_id[1]).first()
        perspective = CACHE.get(objects=
            {
                DictionaryPerspective : (perspective_id, )
            }
        )

        if not perspective:

            raise ResponseError(message =
                'Unknown perspective {0}/{1}.'.format(
                    perspective_id[0], perspective_id[1]))

        perspective_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = perspective.translation_gist_client_id,
            object_id = perspective.translation_gist_object_id).first()

        # dictionary = DBSession.query(Dictionary).filter_by(
        #     client_id = perspective.parent_client_id,
        #     object_id = perspective.parent_object_id).first()
        dictionary = CACHE.get(objects =
            {
                Dictionary : ((perspective.parent_client_id, perspective.parent_object_id), )
            }
        )


        if not dictionary:

            raise ResponseError(message =
                'Unknown dictionary {0}/{1}.'.format(
                    perspective.parent_client_id, perspective.parent_object_id))

        dictionary_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = dictionary.translation_gist_client_id,
            object_id = dictionary.translation_gist_object_id).first()

        # Sound/markup archiving task status setup.

        dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        perspective_name = perspective_translation_gist.get_translation(locale_id)

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        task_status = TaskStatus(user_id,
            'Sound/markup archive compilation',
            '{0}: {1}'.format(dictionary_name, perspective_name), 4)

        # Performing either synchronous or asynchronous sound/markup archive compilation.

        request.response.status = HTTPOk.code

        task_key = task_status.key

        cache_kwargs = request.registry.settings['cache_kwargs']
        sqlalchemy_url = request.registry.settings['sqlalchemy.url']
        storage = request.registry.settings['storage']

        return (std_sound_and_markup if 'synchronous' in request.params else async_sound_and_markup.delay)(
            task_key,
            perspective_id[0], perspective_id[1], published_mode, limit,
            dictionary_name, perspective_name,
            cache_kwargs, storage, sqlalchemy_url)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('sound_and_markup: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(4, 100, 'Finished (ERROR), external error')

        raise ResponseError(message = 'External error')
