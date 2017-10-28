
# Standard library imports.

import base64
import collections
import copy
import datetime
from errno import EEXIST
import getopt
import glob
import gzip
import hashlib
import io
import itertools
import logging
import math
from os import makedirs, path
import pickle
import pprint
import random
import re
import shutil
import signal
import sndhdr
import string
import subprocess
import sys
import tempfile
from time import time
import traceback

from urllib.request import urlopen
import urllib.parse

import zipfile

# External imports.

import cchardet as chardet
from celery.utils.log import get_task_logger

import numpy
import numpy.fft
import numpy.linalg
import numpy.polynomial

from pathvalidate import sanitize_filename

import pydub
import pympi

from pyramid.httpexceptions import HTTPInternalServerError, HTTPPreconditionFailed, HTTPOk
from pyramid.request import Request
from pyramid.view import view_config

import scipy.linalg
import scipy.fftpack

import sklearn.svm as svm

from sqlalchemy import and_, create_engine, exists, func

from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import flag_modified

from transaction import manager
import xlsxwriter

# Project imports.

import lingvodoc.cache.caching as caching
from lingvodoc.cache.caching import CACHE, initialize_cache, TaskStatus

from lingvodoc.models import (
    BaseGroup,
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
from lingvodoc.scripts.markup_recognition import read_align_file

from lingvodoc.views.v2.phonology import (AudioPraatLike, character_escape, compute_formants, cpu_time,
    entity_filename_date, get_sound_markup_bytes)

from lingvodoc.views.v2.utils import (anonymous_userid, message, storage_file, storage_file_path,
    unimplemented)


# Setting up logging.
log = logging.getLogger(__name__)


@view_config(route_name = 'transcription_markup_data', renderer = 'json')
def transcription_markup_data(request):
    """
    Gets transcription/markup recognition training data --- transcriptions and corresponding sounds and
    markups --- for a specified perspective.
    """

    try:
        perspective_cid = request.params.get('perspective_client_id')
        perspective_oid = request.params.get('perspective_object_id')

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

        # Showing transcription/markup data gathering info.

        locale_id = int(request.cookies.get('locale_id') or 2)

        dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        perspective_name = perspective_translation_gist.get_translation(locale_id)

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        if user_id != 1:
            return {'error': 'not an administrator'}

        log.debug('transcription_markup_data {0}/{1}:'
            '\n  dictionary_name: \'{2}\'\n  perspective_name: \'{3}\''.format(
            perspective_cid, perspective_oid, dictionary_name, perspective_name))

        # Finding transcription field.

        field_data = DBSession.query(
            DictionaryPerspectiveToField, Field, TranslationAtom).filter(
                DictionaryPerspectiveToField.parent_client_id == perspective_cid,
                DictionaryPerspectiveToField.parent_object_id == perspective_oid,
                DictionaryPerspectiveToField.marked_for_deletion == False,
                Field.client_id == DictionaryPerspectiveToField.field_client_id,
                Field.object_id == DictionaryPerspectiveToField.field_object_id,
                Field.marked_for_deletion == False,
                TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                TranslationAtom.parent_object_id == Field.translation_gist_object_id,
                TranslationAtom.locale_id == 2,
                TranslationAtom.content.op('~*')('.*transcription.*'),
                translationatom.marked_for_deletion == False).order_by(
                    Field.client_id, Field.object_id).first()

        if not field_data:
            raise Exception('Missing transcription field.')

        transcription_field = field_data.Field

        log.debug('transcription field: {0}/{1} \'{2}\''.format(
            transcription_field.client_id, transcription_field.object_id,
            field._data.TranslationAtom.content))

        # Checking if we can find translation field.

        field_data = DBSession.query(
            DictionaryPerspectiveToField, Field, TranslationAtom).filter(
                DictionaryPerspectiveToField.parent_client_id == perspective_cid,
                DictionaryPerspectiveToField.parent_object_id == perspective_oid,
                DictionaryPerspectiveToField.marked_for_deletion == False,
                Field.client_id == DictionaryPerspectiveToField.field_client_id,
                Field.object_id == DictionaryPerspectiveToField.field_object_id,
                Field.marked_for_deletion == False,
                TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                TranslationAtom.parent_object_id == Field.translation_gist_object_id,
                TranslationAtom.locale_id == 2,
                TranslationAtom.content.op('~*')('.*translation.*'),
                translationatom.marked_for_deletion == False).order_by(
                    Field.client_id, Field.object_id).first()

        translation_field = field_data.Field if field_data else None

        log.debug('translation field: ' +
            ('None' if not field_data else '{0}/{1} \'{2}\''.format(
                translation_field.client_id, translation_field.object_id,
                field_data.TranslationAtom.content)))

        # Getting number of available sound/transcription/markup triples.

        Sound = aliased(Entity, name = 'Sound')
        Transcription = aliased(Entity, name = 'Transcription')
        Markup = aliased(Entity, name = 'Markup')
        Translation = aliased(Entity, name = 'Translation')

        PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')
        PublishingTranscription = aliased(PublishingEntity, name = 'PublishingTranscription')
        PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
        PublishingTranslation = aliased(PublishingEntity, name = 'PublishingTranslation')

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

        # Getting transcription data, if required.

        if transcription_field:

            data_query = (data_query
                
                .outerjoin(Transcription, and_(
                    Transcription.parent_client_id == LexicalEntry.client_id,
                    Transcription.parent_object_id == LexicalEntry.object_id,
                    Transcription.field_client_id == transcription_field.client_id,
                    Transcription.field_object_id == transcription_field.object_id,
                    Transcription.marked_for_deletion == False))

                .outerjoin(PublishingTranscription, and_(
                    PublishingTranscription.client_id == Transcription.client_id,
                    PublishingTranscription.object_id == Transcription.object_id,
                    PublishingTranscription.published == True,
                    PublishingTranscription.accepted == True))
                
                .add_columns(Transcription))

        # Getting translation data, if required.

        if translation_field:

            data_query = (data_query
                
                .outerjoin(Translation, and_(
                    Translation.parent_client_id == LexicalEntry.client_id,
                    Translation.parent_object_id == LexicalEntry.object_id,
                    Translation.field_client_id == translation_field.client_id,
                    Translation.field_object_id == translation_field.object_id,
                    Translation.marked_for_deletion == False))

                .outerjoin(PublishingTranslation, and_(
                    PublishingTranslation.client_id == Translation.client_id,
                    PublishingTranslation.object_id == Translation.object_id,
                    PublishingTranslation.published == True,
                    PublishingTranslation.accepted == True))
                
                .add_columns(
                    func.array_agg(Translation.content))
                
                .group_by(LexicalEntry, Markup, Sound, Transcription))

        # NOTE: somewhat changed data retrieval queries and did not test it, we should do it later, if we
        # will need transcription/sound/markup data again.

        return {'error': unimplemented()}

        total_count = data_query.count()
        log.debug('data triple count: {0}'.format(total_count))

        # Preparing for writing out sound/transcription/markup data archive.

        storage = request.registry.settings['storage']

        storage_dir = path.join(storage['path'], 'markup_recognition')
        makedirs(storage_dir, exist_ok = True)

        archive_name = sanitize_filename(
            '{0} - {1}.zip'.format(dictionary_name[:64], perspective_name[:64]))

        archive_path = path.join(storage_dir, archive_name)

        # If the archive already exists, we will overwrite it.

        if path.exists(archive_path):
            pass

        # Processing sound/transcription/markup data.

        triple_count = 0
        sound_name_set = set()

        with zipfile.ZipFile(archive_path, 'w') as archive_file:
            for index, row in enumerate(data_query.yield_per(100)):

                sound_url = row.Sound.content
                transcription = row.Transcription.content
                markup_url = row.Markup.content
                translation = row[4][0] if translation_field and len(row[4]) > 0 else None

                row_str = ('{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, '
                    'transcription-Entity {5}/{6}, markup-Entity {7}/{8})'.format(index,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Transcription.client_id, row.Transcription.object_id,
                        row.Markup.client_id, row.Markup.object_id))

                log.debug('{0}:\n  {1}\n  {2}\n  {3}\n  {4}'.format(
                    row_str, sound_url, transcription, markup_url, translation))

                # Getting sound and markup data.

                try:
                    sound_bytes, markup_bytes = get_sound_markup_bytes(
                        storage, sound_url, markup_url)

                # If we failed to get sound/markup data, we report why and go on to the next
                # sound/markup pair.

                except Exception as exception:

                    log.debug(
                        '{0}: exception\n{1}\n{2}'.format(
                        row_str, markup_url, sound_url))

                    traceback_string = ''.join(traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1]

                    log.debug(traceback_string)

                    continue

                # Archiving sound data, unless we already processed this sound entity, which can happen if
                # it has multiple markup entities.

                sound_name, sound_date = entity_filename_date(row.Sound, translation)

                sound_name = '{0}_'.format(triple_count) + sound_name
                sound_extension = path.splitext(sound_name)[1].strip().strip('.')

                if sound_name not in sound_name_set:

                    zip_info = zipfile.ZipInfo(sound_name, sound_date)
                    if sndhdr.test_wav(sound_bytes, io.BytesIO(sound_bytes)):

                        # Ensuring that the sound file has an extension. Files with unknown or missing
                        # extensions are presumed to be WAV files.

                        if (len(sound_extension) <= 0 or
                            not sound_extension.lower() in ['wav', 'mp3', 'flac']):

                            zip_info.filename += 'wav' if sound_name.endswith('.') else '.wav'

                        zip_info.compress_type = zipfile.ZIP_DEFLATED

                    sound_name_set.add(zip_info.filename)
                    archive_file.writestr(zip_info, sound_bytes)

                # Archiving transcription data.

                transcription_name, transcription_date = entity_filename_date(
                    row.Transcription, translation)

                transcription_name = '{0}_{1}.txt'.format(triple_count, transcription_name)

                archive_file.writestr(zipfile.ZipInfo(transcription_name, transcription_date),
                    transcription.encode('utf-8'), zipfile.ZIP_STORED)

                # Archiving markup data.

                markup_name, markup_date = entity_filename_date(row.Markup, translation)

                markup_name = '{0}_'.format(triple_count) + markup_name
                markup_extension = path.splitext(markup_name)[1].strip().strip('.')

                if (len(markup_extension) <= 0 or
                    markup_extension.lower() != 'textgrid'):

                    markup_name += 'textgrid' if markup_name.endswith('.') else '.textgrid'

                archive_file.writestr(zipfile.ZipInfo(markup_name, markup_date), markup_bytes,
                    zipfile.ZIP_DEFLATED)

                triple_count += 1

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('transcription_markup_data: exception')
        log.debug(traceback_string)

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}


@view_config(route_name = 'markup_recognition', renderer = 'json')
def markup_recognition(request):
    """
    Performs automatic markup recognition of sound recordings of a specified perspective.

    Perspective is specified by URL parameters 'perspective_client_id' and 'perspective_object_id'.
    """

    task_status = None

    try:
        perspective_cid = request.params.get('perspective_client_id')
        perspective_oid = request.params.get('perspective_object_id')

        log.debug('markup_recognition {0}/{1}'.format(
            perspective_cid, perspective_oid))

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

        # Getting user and perspective info.

        locale_id = int(request.cookies.get('locale_id') or 2)

        dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        perspective_name = perspective_translation_gist.get_translation(locale_id)

        client_id = request.authenticated_userid

        if not client_id:
            return {'error': message('Unrecognized client.')}

        user = Client.get_user_by_client_id(client_id)

        if not user:
            return {'error': message('User authentification failure.')}

        # Checking if the user has sufficient permissions to perform automatic markup recognition.

        create_base_group = DBSession.query(BaseGroup).filter_by(
            subject = 'lexical_entries_and_entities', action = 'create').first()

        url = request.route_url('perspective_roles',
            client_id = dictionary.client_id,
            object_id = dictionary.object_id,
            perspective_client_id = perspective_cid,
            perspective_object_id = perspective_oid)

        subrequest = Request.blank(url)
        subrequest.method = 'GET'
        subrequest.headers = request.headers

        result = request.invoke_subrequest(subrequest)

        log.debug('AMR permissions: user {0}, perspective {1}/{2}: roles\n{3}'.format(
            user.id, perspective_cid, perspective_oid, pprint.pformat(result.json)))

        if user.id not in result.json['roles_users'][create_base_group.name] and \
            all(organization_id not in user.organizations
                for organization_id in result.json['roles_organizations'][create_base_group.name]):

            return {'error': 'Permissions to create markup entities are required.'}

        # Markup recognition task status setup.

        task_status = TaskStatus(user.id,
            'Automatic markup recognition', '{0}: {1}'.format(dictionary_name, perspective_name), 5)

        # Performing either synchronous or asynchronous sound/markup archive compilation.

        request.response.status = HTTPOk.code

        task_key = task_status.key

        cache_kwargs = request.registry.settings['cache_kwargs']
        sqlalchemy_url = request.registry.settings['sqlalchemy.url']
        storage = request.registry.settings['storage']

        return (std_markup_recognition if 'synchronous' in request.params else
            async_markup_recognition.delay)(
              task_key,
              client_id, perspective_cid, perspective_oid,
              locale_id, dictionary_name, perspective_name,
              cache_kwargs, storage, sqlalchemy_url,
              request.registry.settings)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('markup_recognition: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(5, 100, 'Finished (ERROR), external error')

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}


def std_markup_recognition(
    task_key,
    client_id, perspective_cid, perspective_oid,
    locale_id, dictionary_name, perspective_name,
    cache_kwargs, storage, sqlalchemy_url, settings):
    """
    Synchronous automatic markup recognition, used for debugging.
    """

    task_status = TaskStatus.get_from_cache(task_key)

    try:
        return perform_markup_recognition(
            client_id, perspective_cid, perspective_oid,
            locale_id, dictionary_name, perspective_name,
            task_status, storage, settings)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('markup_recognition: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(5, 100, 'Finished (ERROR), external error')

        return {'error': 'external error'}


@celery.task
def async_markup_recognition(
    task_key,
    client_id, perspective_cid, perspective_oid,
    locale_id, dictionary_name, perspective_name,
    cache_kwargs, storage, sqlalchemy_url, settings):
    """
    Asynchronous automatic markup recognition.
    """

    # This is a no-op with current settings, we use it to enable logging inside celery tasks, because
    # somehow this does it, and otherwise we couldn't set it up.

    logging.debug('async_markup_recognition')

    # Ok, and now we go on with task execution.

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)
    initialize_cache(cache_kwargs)

    task_status = TaskStatus.get_from_cache(task_key)

    with manager:
        try:

            return perform_markup_recognition(
                client_id, perspective_cid, perspective_oid,
                locale_id, dictionary_name, perspective_name,
                task_status, storage, settings)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('markup_recognition: exception')
            log.debug(traceback_string)

            if task_status is not None:
                task_status.set(5, 100, 'Finished (ERROR), external error')

            return {'error': 'external error'}


def perform_markup_recognition(
    client_id,
    perspective_cid, perspective_oid,
    locale_id,
    dictionary_name, perspective_name,
    task_status, storage, settings):
    """
    Performs automatic markup recognition.
    """

    log.debug('markup_recognition {0} {1}/{2}:'
        '\n  locale_id: {3}\n  dictionary_name: \'{4}\'\n  perspective_name: \'{5}\''.format(
        client_id,
        perspective_cid, perspective_oid,
        locale_id,
        dictionary_name, perspective_name))

    task_status.set(1, 0, 'Preparing for markup recognition')

    # Checking if we can find sound field.

    sound_field_data = DBSession.query(
        DictionaryPerspectiveToField, Field).filter(
            DictionaryPerspectiveToField.parent_client_id == perspective_cid,
            DictionaryPerspectiveToField.parent_object_id == perspective_oid,
            DictionaryPerspectiveToField.field_client_id == Field.client_id,
            DictionaryPerspectiveToField.field_object_id == Field.object_id,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.data_type_translation_gist_client_id == TranslationAtom.parent_client_id,
            Field.data_type_translation_gist_object_id == TranslationAtom.parent_object_id,
            Field.marked_for_deletion == False,
            TranslationAtom.locale_id == 2,
            TranslationAtom.content == 'Sound',
            TranslationAtom.marked_for_deletion == False).first()

    if sound_field_data == None:
        return {'error': 'Missing sound field.'}

    sound_field = sound_field_data.Field

    log.debug('sound field: {0}/{1}'.format(
        sound_field.client_id, sound_field.object_id))

    # Trying to get markup field.

    markup_field_data = DBSession.query(
        DictionaryPerspectiveToField, Field).filter(
            DictionaryPerspectiveToField.parent_client_id == perspective_cid,
            DictionaryPerspectiveToField.parent_object_id == perspective_oid,
            DictionaryPerspectiveToField.field_client_id == Field.client_id,
            DictionaryPerspectiveToField.field_object_id == Field.object_id,
            DictionaryPerspectiveToField.self_client_id ==
                sound_field_data.DictionaryPerspectiveToField.client_id,
            DictionaryPerspectiveToField.self_object_id ==
                sound_field_data.DictionaryPerspectiveToField.object_id,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.data_type_translation_gist_client_id == TranslationAtom.parent_client_id,
            Field.data_type_translation_gist_object_id == TranslationAtom.parent_object_id,
            Field.marked_for_deletion == False,
            TranslationAtom.locale_id == 2,
            TranslationAtom.content == 'Markup',
            TranslationAtom.marked_for_deletion == False).first()

    if markup_field_data == None:
        return {'error': 'Missing markup field.'}

    markup_field = markup_field_data.Field

    log.debug('markup field: {0}/{1}'.format(
        markup_field.client_id, markup_field.object_id))

    # And now we have to go through sound recordings which have no attached markups.

    Sound = aliased(Entity, name = 'Sound')
    Markup = aliased(Entity, name = 'Markup')

    data_query = DBSession.query(
        LexicalEntry, Sound).filter(

            LexicalEntry.parent_client_id == perspective_cid,
            LexicalEntry.parent_object_id == perspective_oid,
            LexicalEntry.marked_for_deletion == False,
            Sound.parent_client_id == LexicalEntry.client_id,
            Sound.parent_object_id == LexicalEntry.object_id,
            Sound.field_client_id == sound_field.client_id,
            Sound.field_object_id == sound_field.object_id,
            Sound.marked_for_deletion == False,

            ~exists().where(and_(
                LexicalEntry.parent_client_id == perspective_cid,
                LexicalEntry.parent_object_id == perspective_oid,
                LexicalEntry.marked_for_deletion == False,
                Markup.parent_client_id == LexicalEntry.client_id,
                Markup.parent_object_id == LexicalEntry.object_id,
                Markup.field_client_id == markup_field.client_id,
                Markup.field_object_id == markup_field.object_id,
                Markup.self_client_id == Sound.client_id,
                Markup.self_object_id == Sound.object_id,
                Markup.marked_for_deletion == False,
                Markup.additional_metadata.contains({'data_type': 'praat markup'}))))

    # If we have no such recodings, we do nothing.

    data_count = data_query.count()
    log.debug('{0} sound recordings without markup'.format(data_count))

    if data_count <= 0:

        task_status.set(5, 100, 'No sound recordings without markup')
        return {'how_many': 0}

    # Processing markupless sound recordings.

    task_status.set(2, 0, 'Preparing sound recordings for decoding')

    storage_dir_path = path.join(storage['path'], 'markup_recognition')
    makedirs(storage_dir_path, exist_ok = True)

    with tempfile.TemporaryDirectory(dir = storage_dir_path) as temporary_dir_path:
        log.debug('temporary directory: {0}'.format(temporary_dir_path))

        sound_dir_path = path.join(temporary_dir_path, 'sound')
        data_dir_path = path.join(temporary_dir_path, 'data')

        makedirs(sound_dir_path, exist_ok = True)
        makedirs(data_dir_path, exist_ok = True)

        # Preparing data for decoding of sound recordings.

        entry_sound_dict = {}

        with open(path.join(data_dir_path, 'wav.scp'), 'wb') as wav_file, \
            open(path.join(data_dir_path, 'utt2spk'), 'wb') as utt_file:

            for index, (entry, sound) in enumerate(data_query.yield_per(100)):
                entry_sound_dict[index] = (entry, sound)

                # Getting sound recording data.

                sound_url = sound.content

                try:
                    input_path = storage_file_path(storage, sound_url)
                    output_path = path.join(sound_dir_path, 's{0:06d}.wav'.format(index))

                    if input_path is not None:

                        # Processing locally accessible sound recording.

                        call_list = ['sox',
                            input_path, '-b', '16', '-r', '16k', '-c', '1', '-G', output_path]

                        log.debug(call_list)
                        subprocess.check_call(call_list)

                    else:
                        extension = path.splitext(
                            urllib.parse.urlparse(sound_url).path)[1]

                        if len(extension) <= 0:
                            extension = '.wav'

                        # Downloading and transforming sound recording.

                        with tempfile.NamedTemporaryFile(suffix = extension) as temp_file, \
                            urlopen(urllib.parse.quote(sound_url, safe = '/:')) as sound_stream:

                            temp_file.write(sound_stream.read())
                            temp_file.flush()

                            call_list = ['sox',
                                temp_file.name, '-b', '16', '-r', '16k', '-c', '1', '-G', output_path]

                            log.debug(call_list)
                            subprocess.check_call(call_list)

                    # Another sound recording is ready.

                    wav_file.write('s{0:06d} {1}\n'.format(index, output_path).encode('utf-8'))
                    utt_file.write('s{0:06d} s{0:06d}\n'.format(index).encode('utf-8'))

                    log.debug('{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}):\n  {5}'.format(
                        index, entry.client_id, entry.object_id, sound.client_id, sound.object_id,
                        sound_url))

                    task_status.set(2, int(math.floor((index + 1) * 100 / data_count)),
                        'Preparing sound recordings for decoding')

                # If we failed to get sound data, we report why and go on to the next sound recording.

                except Exception as exception:

                    log.debug('{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}): exception\n  {5}'.format(
                        index, entry.client_id, entry.object_id, sound.client_id, sound.object_id,
                        sound_url))

                    traceback_string = ''.join(traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1]

                    log.debug(traceback_string)

                    task_status.set(2, int(math.floor((index + 1) * 100 / data_count)),
                        'Preparing sound recordings for decoding')

                    continue

        # Ok, and now we should perform markup recognition.

        kaldi_dir_path = settings['amr']['kaldi']
        model_dir_path = settings['amr']['model']

        log.debug('\n  Kaldi root directory: {0}\n  Kaldi AMR model directory: {1}'.format(
            kaldi_dir_path, model_dir_path))

        task_status.set(3, 0, 'Decoding sound recordings')

        call_list = [
            path.join(model_dir_path, 'markup_recognition.sh'),
            kaldi_dir_path, model_dir_path, temporary_dir_path]

        log.debug(call_list)
        subprocess.check_call(call_list)

        # Getting resulting markups.
        
        align_file_path = path.join(
            temporary_dir_path, 'decode', 'align.1.txt')

        align_dict = read_align_file(align_file_path)

        log.debug('\n  Alignment file: {0}, processing {1} alignments.'.format(
            align_file_path, len(align_dict)))

        task_status.set(4, 0, 'Saving generated markup')

        markup_entity_count = 0

        for index, (transcription_list, interval_list) in sorted(align_dict.items()):

            textgrid = pympi.Praat.TextGrid(
                xmin = 0, xmax = interval_list[-1][1], codec = 'utf-8')

            amr_tier = textgrid.add_tier('amr_20171016')

            for interval in interval_list:
                amr_tier.add_interval(*interval)

            # Creating markup entity.

            entry, sound = entry_sound_dict[index]

            entity_kwargs = {
                'additional_metadata': {'amr': 20171016, 'data_type': 'praat markup'},
                'client_id': client_id,
                'field_client_id': markup_field.client_id,
                'field_object_id': markup_field.object_id,
                'locale_id': locale_id,
                'parent_client_id': entry.client_id,
                'parent_object_id': entry.object_id,
                'self_client_id': sound.client_id,
                'self_object_id': sound.object_id}

            entity = Entity(**entity_kwargs)

            if sound.publishingentity.accepted:
                entity.publishingentity.accepted = True

            # Saving TextGrid we created to the storage, see function 'create_object' in
            # lingvodoc.views.v2.utils for reference.

            if storage['type'] == 'openstack':
                return {'error': unimplemented()}

            markup_file_name = sanitize_filename(
                path.splitext(path.basename(urllib.parse.urlparse(sound.content).path))[0] + '.TextGrid')

            markup_dir_path = path.join(storage['path'], entity.__tablename__, 'markup',
                str(entity.client_id), str(entity.object_id))

            makedirs(markup_dir_path, exist_ok = True)

            markup_file_path = path.join(markup_dir_path, markup_file_name)
            textgrid.to_file(markup_file_path)

            # Updating markup entity, finishing its creation.

            markup_file_url = ''.join([
                storage['prefix'],
                storage['static_route'],
                entity.__tablename__, '/markup/',
                str(entity.client_id), '/',
                str(entity.object_id), '/',
                markup_file_name])

            entity.content = markup_file_url

            with open(markup_file_path, 'rb') as markup_file:
                hash = hashlib.sha224(markup_file.read()).hexdigest()

            entity.additional_metadata['hash'] = hash
            flag_modified(entity, 'additional_metadata')

            DBSession.add(entity)

            # Logging creation of a new markup entity.

            markup_entity_count += 1

            log.debug('{0} (markup-Entity {1}/{2}):\n  {3}\n  {4}'.format(
                index, entity.client_id, entity.object_id, markup_file_path, markup_file_url))

            task_status.set(4, int(math.floor((index + 1) * 100 / len(align_dict))),
                'Saving generated markup')

    # Returning number of newly created markup entities.

    log.debug('markup_recognition {0} {1}/{2}: {3} new markup entities'.format(
        client_id, perspective_cid, perspective_oid, markup_entity_count))

    task_status.set(5, 100, 'Finished')

    return {'how_many': markup_entity_count}

