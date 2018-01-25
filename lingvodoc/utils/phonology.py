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
from lingvodoc.views.v2.phonology import std_phonology, async_phonology

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

def gql_phonology(request, group_by_description, only_first_translation, perspective_cid, perspective_oid,
              synchronous, vowel_selection, maybe_tier_list, maybe_tier_set=None, limit=None,
              limit_exception=None, limit_no_vowel=None, limit_result=None, locale_id=2, maybe_translation_field=None):
    """
    Computes phonology of a specified perspective.
    Perspective is specified by JSON request parameters 'perspective_client_id' and 'perspective_object_id'.
    Can also get parameter data from URL parameters, if URL parameter 'url_parameters' is present.
    Parameters:
        group_by_description
        limit
        limit_exception
        limit_no_vowel
        limit_result
        only_first_translation
        perspective_client_id
        perspective_object_id
        synchronous
        vowel_selection
    """

    task_status = None

    try:
        #request_json = request.json

        # Indicating that we are starting to process phonology request.

        log.debug('phonology {0}/{1}: {2}, {3}, {4}, {5}'.format(
            perspective_cid, perspective_oid,
            group_by_description, vowel_selection, only_first_translation,
            maybe_tier_list))

        # Getting perspective and perspective's dictionary info.

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = perspective_cid, object_id = perspective_oid).first()

        perspective_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = perspective.translation_gist_client_id,
            object_id = perspective.translation_gist_object_id).first()

        dictionary = DBSession.query(Dictionary).filter_by(
            client_id = perspective.parent_client_id,
            object_id = perspective.parent_object_id).first()

        dictionary_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = dictionary.translation_gist_client_id,
            object_id = dictionary.translation_gist_object_id).first()

        # Phonology task status setup.

        dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        perspective_name = perspective_translation_gist.get_translation(locale_id)

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        task_status = TaskStatus(user_id,
            'Phonology compilation', '{0}: {1}'.format(dictionary_name, perspective_name), 4)

        # Checking if we have limits on number of computed results.

        # Performing either synchronous or asynchronous phonology compilation.

        task_key = task_status.key
        cache_kwargs = request.registry.settings["cache_kwargs"]
        sqlalchemy_url = request.registry.settings["sqlalchemy.url"]
        storage = request.registry.settings["storage"]

        return (std_phonology if synchronous else async_phonology.delay)(
            task_key,
            perspective_cid=perspective_cid, perspective_oid=perspective_oid,
            dictionary_name=dictionary_name, perspective_name=perspective_name,
            cache_kwargs=cache_kwargs, storage=storage,
            group_by_description=group_by_description, vowel_selection=vowel_selection, only_first_translation=only_first_translation, maybe_tier_set=maybe_tier_set,
            limit=limit, limit_exception=limit_exception, limit_no_vowel=limit_no_vowel, limit_result=limit_result,
            sqlalchemy_url=sqlalchemy_url,
            use_automatic_markup=None,
        maybe_translation_field=maybe_translation_field)


    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(4, 100, 'Finished (ERROR), external error')

        raise ResponseError(message="External error")



def gql_phonology_tier_list(perspective_cid, perspective_oid):
    """
    Gets a list of names of phonology markup tiers for a specified perspective.
    """

    try:

        log.debug('phonology_tier_list {0}/{1}'.format(
            perspective_cid, perspective_oid))

        # We are going to look through all perspective's accessible markup/sound pairs.

        Markup = aliased(Entity, name = 'Markup')
        Sound = aliased(Entity, name = 'Sound')

        PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
        PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')

        data_query = DBSession.query(
            LexicalEntry, Markup, Sound).filter(
                LexicalEntry.parent_client_id == perspective_cid,
                LexicalEntry.parent_object_id == perspective_oid,
                LexicalEntry.marked_for_deletion == False,
                Markup.parent_client_id == LexicalEntry.client_id,
                Markup.parent_object_id == LexicalEntry.object_id,
                Markup.marked_for_deletion == False,
                Markup.additional_metadata.contains({'data_type': 'praat markup'}),
                PublishingMarkup.client_id == Markup.client_id,
                PublishingMarkup.object_id == Markup.object_id,
                PublishingMarkup.published == True,
                PublishingMarkup.accepted == True,
                Sound.client_id == Markup.self_client_id,
                Sound.object_id == Markup.self_object_id,
                Sound.marked_for_deletion == False,
                PublishingSound.client_id == Sound.client_id,
                PublishingSound.object_id == Sound.object_id,
                PublishingSound.published == True,
                PublishingSound.accepted == True)

        # Processing sound/markup pairs.

        tier_count = collections.Counter()
        total_count = 0

        for index, row in enumerate(data_query.yield_per(100)):
            markup_url = row.Markup.content

            row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Markup.client_id, row.Markup.object_id)

            log.debug('{0}: {1}'.format(row_str, markup_url))

            # Checking if we have cached tier list for this pair of sound/markup.

            cache_key = 'phonology_tier_list:{0}:{1}:{2}:{3}'.format(
                row.Sound.client_id, row.Sound.object_id,
                row.Markup.client_id, row.Markup.object_id)

            cache_result = caching.CACHE.get(cache_key)

            if cache_result:

                tier_count.update(cache_result)
                total_count += 1

                log.debug('{0} [CACHE {1}]: {2}'.format(row_str, cache_key, list(sorted(cache_result))))
                continue

            # Trying to download and parse markup and get its tiers.

            try:
                with urllib.request.urlopen(urllib.parse.quote(markup_url, safe = '/:')) as markup_stream:
                    markup_bytes = markup_stream.read()

                try:
                    textgrid = pympi.Praat.TextGrid(xmax = 0)

                    textgrid.from_file(
                        io.BytesIO(markup_bytes),
                        codec = chardet.detect(markup_bytes)['encoding'])

                except:
                    # If we failed to parse TextGrid markup, we assume that sound and markup files were
                    # accidentally swapped and try again.

                    markup_url = row.Sound.content

                    with urllib.request.urlopen(urllib.parse.quote(markup_url, safe = '/:')) as markup_stream:
                        markup_bytes = markup_stream.read()

                    textgrid = pympi.Praat.TextGrid(xmax = 0)

                    textgrid.from_file(
                        io.BytesIO(markup_bytes),
                        codec = chardet.detect(markup_bytes)['encoding'])

                markup_tier_set = set(tier_name
                    for tier_number, tier_name in textgrid.get_tier_name_num())

                caching.CACHE.set(cache_key, markup_tier_set)

                tier_count.update(markup_tier_set)
                total_count += 1

                log.debug('{0}: {1}'.format(row_str, list(sorted(markup_tier_set))))

            # Markup processing error, we report it and go on.

            except Exception as exception:

                traceback_string = ''.join(traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1]

                log.debug('{0}: exception'.format(row_str))
                log.debug(traceback_string)

        # Logging and returning list of all tier names we encountered.

        tier_list = list(sorted(tier_count.items(),
            key = lambda tier_count: (tier_count[0].lower(), tier_count[0])))

        log.debug('phonology_tier_list {0}/{1}: {2}, {3}'.format(
            perspective_cid, perspective_oid, total_count, tier_list))

        return {'tier_count': dict(tier_count), 'total_count': total_count}

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology_tier_list: exception')
        log.debug(traceback_string)

        raise ResponseError(message="External error")
