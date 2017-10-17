
# Standard library imports.

import base64
import collections
import copy
import datetime
import editdistance
from errno import EEXIST
import getopt
import glob
import gzip
from hashlib import md5
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

import urllib.request
import urllib.parse

import zipfile

# External imports.

import cchardet as chardet
from celery.utils.log import get_task_logger

import hmmlearn.hmm

# Explicitly enabling GUI matplotlib backend, as other modules (e.g. lingvodoc.views.v2.phonology)
# explicitly disable it.
import matplotlib
matplotlib.use('TkAgg', warn = False)

import matplotlib.pyplot as pyplot
import matplotlib.widgets as widgets

import numpy
import numpy.fft
import numpy.linalg
import numpy.polynomial

from pathvalidate import sanitize_filename
 
from pyAudioAnalysis import audioBasicIO, audioSegmentation
from pyAudioAnalysis.audioFeatureExtraction import (mfccInitFilterBanks, stChromaFeatures,
    stChromaFeaturesInit, stEnergy, stEnergyEntropy, stMFCC, stSpectralCentroidAndSpread,
    stSpectralEntropy, stSpectralFlux, stSpectralRollOff, stZCR)

import pydub
import pydub.playback

import pympi

from pyramid.httpexceptions import HTTPInternalServerError, HTTPPreconditionFailed, HTTPOk
from pyramid.view import view_config

import scipy.fftpack
import scipy.io.wavfile as wavfile
import scipy.linalg

import sklearn.svm as svm

from sqlalchemy import and_, create_engine, func
from sqlalchemy.orm import aliased

from transaction import manager
import xlsxwriter

# Project imports.

import lingvodoc.cache.caching as caching
from lingvodoc.cache.caching import CACHE, initialize_cache, TaskStatus

from lingvodoc.models import (
    Client,
    DBSession,
    Dictionary,
    DictionaryPerspective,
    Entity,
    Field,
    LexicalEntry,
    PublishingEntity,
    TranslationGist,
    TranslationAtom
)

from lingvodoc.queue.celery import celery

from lingvodoc.views.v2.phonology import (AudioPraatLike, character_escape, compute_formants, cpu_time,
    entity_filename_date, get_sound_markup_bytes)

from lingvodoc.views.v2.utils import anonymous_userid, message, storage_file, unimplemented


# Setting up logging.
log = logging.getLogger(__name__)


def data_iteration_generator(path_list):
    """
    Iterates through sound/markup/transcription data files.
    """

    data_path_list = sorted(data_path
        for path in path_list
        for data_path in glob.glob(path))

    for data_path in data_path_list:

        # Computing MD5 hash of the data file.

        source_hash_state = md5()

        with open(data_path, 'rb') as data_file:
            bytes = data_file.read(65536)

            while bytes:
                source_hash_state.update(bytes)
                bytes = data_file.read(65536)

        source_hash = source_hash_state.hexdigest()

        # Processing data.

        with zipfile.ZipFile(data_path, 'r') as data_file:

            sound_dict = {}
            transcription_dict = {}
            markup_dict = {}

            max_data_index = -1
            skip_index_set = set()

            # Sorting data into sound recordings, transcriptions and markup.

            for zip_info in data_file.infolist():
                extension = path.splitext(zip_info.filename)[1].strip('.').lower()

                data_index = int(zip_info.filename.split('_')[0])
                max_data_index = max(data_index, max_data_index)

                if extension in ['wav', 'mp3', 'flac']:
                    sound_dict[data_index] = zip_info

                elif extension == 'txt':
                    transcription_dict[data_index] = zip_info

                elif extension == 'textgrid':
                    markup_dict[data_index] = zip_info
                
                else:
                    print('Unknown extension \'{0}\', file \'{1}\'.'.format(extension, zip_info.filename))
                    skip_index_set.add(data_index)

            # Checking that everything is as expected.

            for index in skip_index_set:

                sound_dict.pop(index, None)
                transcription_dict.pop(index, None)
                markup_dict.pop(index, None)

            expected_count = max_data_index + 1 - len(skip_index_set)

            if (len(sound_dict) != expected_count or
                len(transcription_dict) != expected_count or
                len(markup_dict) != expected_count):

                print('{0} sounds'.format(len(sound_dict)))
                print('{0} transcriptions'.format(len(transcription_dict)))
                print('{0} markups'.format(len(markup_dict)))
                print('maximum data item index: {0}'.format(max_data_index))

                raise NotImplementedError

            # Iterating through sound/markup/transcription data triples.

            for index in range(max_data_index + 1):

                if index in skip_index_set:
                    continue

                sound_name = sound_dict[index].filename
                sound_bytes = data_file.read(sound_dict[index])

                markup_name = markup_dict[index].filename
                markup_bytes = data_file.read(markup_dict[index])

                textgrid = pympi.Praat.TextGrid(xmax = 0)

                textgrid.from_file(
                    io.BytesIO(markup_bytes),
                    codec = chardet.detect(markup_bytes)['encoding'])

                yield (data_path, source_hash, index,
                    sound_name, sound_bytes, markup_name, textgrid,
                    transcription_dict[index].filename,
                    data_file.read(transcription_dict[index]).decode('utf-8'))


def data_iteration(data_path_list, process_f):
    """
    Processes sound/markup/transcription data files through iteration.
    """

    for args in data_iteration_generator(data_path_list):

        try:
            process_f(*args)

        except StopIteration:
            return


def main_listing(args):
    """
    Lists markups data.
    """

    data_list = []

    def process_f(
        source_path, source_hash, index,
        sound_filename, sound_bytes,
        textgrid_filename, textgrid,
        transcription_filename, transcription):
        """
        Processes sound/markup/transcription data triple.
        """

        data_list.append((transcription, textgrid))

    # Getting and then showing sound/markup/transcription data info.
    
    data_iteration(args[1:], process_f)

    for index, (transcription, textgrid) in enumerate(data_list):
        print('{0}: \'{1}\''.format(index, transcription))

        print('\n'.join('  tier {0} \'{1}\': {2}'.format(tier_number, tier_name,
            '|'.join(character_escape(text) for begin, end, text in
                textgrid.get_tier(tier_number).get_all_intervals()))
            for tier_number, tier_name in textgrid.get_tier_name_num()))


def main_coverage(args):
    """
    Trying to get data with good markup coverage.
    """

    def process_f(
        source_path, source_hash, index,
        sound_filename, sound_bytes,
        textgrid_filename, textgrid,
        transcription_filename, transcription):
        """
        Processes sound/markup/transcription data triple.
        """

        print('index: {0}\nsound file: {1}\nmarkup file: {2}\ntranscription file: {3}'.format(
            index, sound_filename, textgrid_filename, transcription_filename))

        print('transcription: \'{0}\''.format(transcription))
        print('markup:')

        def text_f(text):
            return character_escape(text) if len(text) > 0 else ' '

        print('\n'.join('  tier {0} \'{1}\': {2}'.format(tier_number, tier_name,
            '|'.join(text_f(text) for begin, end, text in
                textgrid.get_tier(tier_number).get_all_intervals()))
            for tier_number, tier_name in textgrid.get_tier_name_num()))

        # Detecting silent and non-silent portions of the sound recording.

        extension = path.splitext(sound_filename)[1]

        if len(extension) <= 0:
            extension = '.wav'

        with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

            temp_file.write(sound_bytes)
            temp_file.flush()

            (rate, data) = audioBasicIO.readAudioFile(temp_file.name)

        segment_list, non_silence_x, non_silence_y = \
            audioSegmentation.silenceRemoval(data, rate, 0.020, 0.020,
                smoothWindow = 0.1, Weight = 0.6)

        # Saving silence segmentation plot, see 'silenceRemoval' function from
        # 'pyAudioAnalysis.audioSegmentation'.

        pyplot.figure().set_size_inches(18, 11)
        pyplot.autoscale(tight = True)

        pyplot.subplot(2, 1, 1)
        pyplot.plot(numpy.arange(0, data.shape[0]) / rate, data)
        pyplot.title('Signal')

        for x1, x2 in segment_list:
            pyplot.axvline(x = x1, color = 'red')
            pyplot.axvline(x = x2, color = 'red')

        pyplot.subplot(2, 1, 2)
        pyplot.plot(non_silence_x, non_silence_y)
        pyplot.title('SVM Probability')

        for x1, x2 in segment_list:
            pyplot.axvline(x = x1, color = 'red')
            pyplot.axvline(x = x2, color = 'red')

        figure_path = path.join('segment',
            '{0}.png'.format(path.splitext(transcription_filename)[0].strip('.')))

        pyplot.savefig(figure_path, format = 'png',
            bbox_inches = 'tight', pad_inches = 0.5)

        # Showing detected non-silent segments, computing their total length.

        print('segments:')
        pprint.pprint(segment_list)

        non_silent_time = sum(end - begin for begin, end in segment_list)

        # Going through markup tiers, checking which non-silent portions don't have markup.

        for tier_number, tier_name in textgrid.get_tier_name_num():
            raw_interval_list = textgrid.get_tier(tier_number).get_all_intervals()

            text_interval_list = [(begin, end)
                for begin, end, text in raw_interval_list
                if len(character_escape(text).strip()) > 0]

            # If the tier has no markup, we skip it.

            if len(text_interval_list) <= 0:
                continue

            # Saving silence segmentation plot with highlighted non-empty markup intervals, see 'silenceRemoval'
            # function from 'pyAudioAnalysis.audioSegmentation'.

            pyplot.figure().set_size_inches(18, 11)
            pyplot.autoscale(tight = True)

            pyplot.subplot(2, 1, 1)
            pyplot.plot(numpy.arange(0, data.shape[0]) / rate, data)
            pyplot.title('Signal')

            for x1, x2 in text_interval_list:
                pyplot.axvspan(x1, x2, alpha = 0.25, color = 'green')

            for x1, x2 in segment_list:
                pyplot.axvline(x = x1, color = 'red')
                pyplot.axvline(x = x2, color = 'red')

            pyplot.subplot(2, 1, 2)
            pyplot.plot(non_silence_x, non_silence_y)
            pyplot.title('SVM Probability')

            for x1, x2 in segment_list:
                pyplot.axvline(x = x1, color = 'red')
                pyplot.axvline(x = x2, color = 'red')

            figure_path = path.join('segment',
                '{0}_{1}.png'.format(path.splitext(transcription_filename)[0].strip('.'), tier_name))

            pyplot.savefig(figure_path, format = 'png',
                bbox_inches = 'tight', pad_inches = 0.5)

            # Computing total unmarked non-silent time.

            unmarked_time = 0.0

            list_a = copy.deepcopy(segment_list)
            list_b = copy.deepcopy(text_interval_list)

            index_a = 0
            index_b = 0

            while True:

                # No non-silent intervals left, we stop the iteration.

                if index_a >= len(list_a):
                    break

                # No markup intervals left, processing any non-silent intervals left and then stopping the
                # iteration.

                elif index_b >= len(list_b):

                    for a1, a2 in list_a[index_a:]:
                        unmarked_time += a2 - a1

                    break

                a1, a2 = list_a[index_a]
                b1, b2 = list_b[index_b]

                # Interval [b1, b2] is inside the interval [a1, a2].

                if a1 <= b1 and a2 >= b2:

                    unmarked_time += b1 - a1
                    list_a[index_a] = [b2, a2]

                    index_b += 1

                # Interval [a1, a2] is inside the interval [b1, b2].

                elif b1 <= a1 and b2 >= a2:

                    index_a += 1

                # Interval [a1, a2] is strictly before the interval [b1, b2].

                elif a2 <= b1:

                    unmarked_time += a2 - a1
                    index_a += 1

                # Interval [b1, b2] is strictly before the interval [a1, a2].

                elif b2 <= a1:

                    index_b += 1

                # Interval [a1, a2] is before and intersects interval [b1, b2].

                elif a1 <= b1 and a2 <= b2:

                    unmarked_time += b1 - a1
                    index_a += 1

                # Interval [b1, b2] is before and intersects interval [a1, a2].

                elif b1 <= a1 and b2 <= a2:

                    list_a[index_a] = [b2, a2]
                    index_b += 1

                else:
                    print(list_a[index_a])
                    print(list_b[index_b])
                    raise NotImplementedError

            # Showing unmarked time information.

            print('Tier {0} \'{1}\', unmarked non-silent time: {2:.2f}s / {3:.2f}s, {4:.2f}s '
                '({5:.2f}% of non-silent time, {6:.2f}% of total time)'.format(
                tier_number, tier_name,
                unmarked_time, non_silent_time, data.shape[0] / float(rate),
                100.0 if non_silent_time <= 0 else 100.0 * unmarked_time / non_silent_time,
                100.0 * unmarked_time / data.shape[0] * float(rate)))

    # Ensuring that we have a directory for silence segmentation plots, analysing data.

    makedirs('segment', exist_ok = True)
    data_iteration(args, process_f)


def open_file(filepath, mode):
  """
  Opens file through the gzip module if its name end in '.gz', otherwise opens the file normally, creating
  directories for the file if required.
  """

  realpath = path.realpath(filepath)

  if 'a' in mode or 'w' in mode or 'x' in mode:
    makedirs(path.dirname(realpath), exist_ok = True)

  return (gzip.open if realpath.endswith('.gz') else open)(realpath, mode)


def interval_list_to_string(interval_list):
    """
    Produces string representation of Textgrid markup tier, escaping special Praat character sequences if
    necessary.
    """

    def text_f(text):
        return character_escape(text) if len(text) > 0 else ' '

    return '|'.join(text_f(text) for begin, end, text in filter(
        lambda interval: len(interval) >= 3, interval_list))


class Selection(object):
    """
    Interactive selection of sound recordings with good markup coverage.
    """

    def __init__(self):
        """
        Initializes sound recording selection data.
        """

        self.accept_set = set()
        self.check_set = set()

        self.skip_set = set()
        self.reject_set = set()

        self.segment_dict = dict()

        self.silent = False

    def print_data_info(self,
        source_path, source_hash, index,
        sound_filename, sound_bytes,
        textgrid_filename, textgrid,
        transcription_filename, transcription):
        """
        Prints sound/markup info.
        """

        print('\npath: {0}\nhash: {1}\nindex: {2}\n'
            'sound file: {3}\nmarkup file: {4}\ntranscription file: {5}'.format(
                source_path, source_hash, index, sound_filename, textgrid_filename, transcription_filename))

        print('transcription: \'{0}\''.format(transcription))
        print('markup:')

        print('\n'.join('  tier {0} \'{1}\': "{2}"'.format(tier_number, tier_name,
            interval_list_to_string(textgrid.get_tier(tier_number).get_all_intervals()))
            for tier_number, tier_name in textgrid.get_tier_name_num()))

    def sound_tier_generator(self, data_path_list):
        """
        Iterates over sound/markup data with separate markup tiers.
        """

        for data_tuple in data_iteration_generator(data_path_list):

            (source_path, source_hash, index,
                sound_filename, sound_bytes,
                textgrid_filename, textgrid,
                transcription_filename, transcription) = data_tuple

            # Getting sound data.

            extension = path.splitext(sound_filename)[1]

            if len(extension) <= 0:
                extension = '.wav'

            with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

                temp_file.write(sound_bytes)
                temp_file.flush()

                (sound_rate, sound_data) = audioBasicIO.readAudioFile(temp_file.name)

            # Showing sound data and intervals with non-empty markup.

            self.current_tier_dict = {}

            for tier_number, tier_name in textgrid.get_tier_name_num():

                interval_list = list(filter(
                    lambda interval: len(interval) >= 3,
                    textgrid.get_tier(tier_number).get_all_intervals()))

                text_interval_list = list(filter(
                    lambda interval: len(character_escape(interval[2]).strip()) > 0,
                    interval_list))

                # If the tier has no markup, we skip it.

                if len(text_interval_list) <= 0:
                    continue

                yield data_tuple, (sound_data, sound_rate), \
                    (tier_number, tier_name, interval_list, text_interval_list)

    def run(self, args):
        """
        Performs interactive selection of sound recordings with good enough markup coverage.
        """

        self.data_generator = self.sound_tier_generator(args)

        def show_next_data():
            """
            Shows next sound/markup data pair, or stops if there are no more left.
            """

            while True:

                # Iterating to not already processed sound/markup pair.

                try:
                    (self.current_data, (self.sound_data, self.sound_rate), self.current_tier) = \
                        next(self.data_generator)

                except StopIteration:

                    pyplot.close()
                    return

                (source_path, source_hash, index,
                    sound_filename, sound_bytes,
                    textgrid_filename, textgrid,
                    transcription_filename, transcription) = self.current_data

                (tier_number, tier_name, interval_list, text_interval_list) = self.current_tier

                # If this sound/markup data was already processed, we try to get the next one.

                self.current_data_tier = (source_hash, index, tier_number)
                self.selection = [None, 0.0]

                self.selection_begin = None
                self.selection_span = None
                self.selection_end = None

                tier_signature = tuple((begin, end)
                    for begin, end, text in text_interval_list)

                if self.current_data_tier in self.accept_set:

                    # Sound/markup was already accepted.

                    if not self.silent:
                        print('ALREADY accept tier {0} \'{1}\''.format(tier_number, tier_name))
                        self.print_data_info(*self.current_data)

                    self.current_tier_dict[tier_signature] = (tier_number, tier_name, 'accept')
                    continue

                elif self.current_data_tier in self.skip_set:

                    # Sound/markup was already skipped.

                    if not self.silent:
                        print('ALREADY skip tier {0} \'{1}\''.format(tier_number, tier_name))
                        self.print_data_info(*self.current_data)

                    self.current_tier_dict[tier_signature] = (tier_number, tier_name, 'skip')
                    continue

                self.print_data_info(*self.current_data)

                # If this markup tier is identical to one of the previous tier of this sound recording, we
                # accept or reject it automatically.

                if tier_signature in self.current_tier_dict:
                    (already_number, already_name, already_status) = self.current_tier_dict[tier_signature]

                    data_tier_set, action = \
                        (self.accept_set, 'ACCEPT') if already_status == 'accept' else \
                        (self.skip_set, 'SKIP')

                    data_tier_set.add(self.current_data_tier)

                    print('{0} tier {1} \'{2}\' as identical to tier {3} \'{4}\''.format(
                        action, tier_number, tier_name, already_number, already_name))

                    # Going on to the next sound/markup tier data.

                    continue

                # Ok, found unprocessed sound/markup pair.

                break

            # Preparing sound data.

            if len(self.sound_data.shape) > 1:
                self.sound_data = self.sound_data.mean(axis = 1)

            self.sound_segment = None

            # Plotting the sound/markup data.

            self.axes.clear()

            self.axes.plot(
                numpy.arange(0, self.sound_data.shape[0]) / self.sound_rate,
                self.sound_data)

            y_max = max((y if y >= 0 else -y) for y in self.sound_data)
            y_limit = min(35000, y_max * 1.1)

            self.axes.set_xlim(0.0, self.sound_data.shape[0] / float(self.sound_rate))
            self.axes.set_ylim(y_limit, -y_limit)

            for x1, x2, text in text_interval_list:
                self.axes.axvspan(x1, x2, alpha = 0.25, color = 'green')

            # Preparing the figure.

            self.axes.set_title('Tier {0} \'{1}\':\n\'{2}\''.format(
                tier_number, tier_name, interval_list_to_string(interval_list)),
                family = 'Gentium', fontsize = 20)

            self.cursor = widgets.Cursor(self.axes,
                horizOn = False, color = 'black', linewidth = 2)

            self.figure.canvas.draw()

        def data_accept(event):
            """
            Accepts current sound/markup pair as data item with good enough markup.
            """

            if self.selection[0] is not None and self.selection[1] is not None:
                raise NotImplementedError

            self.accept_set.add(self.current_data_tier)

            (tier_number, tier_name, interval_list, text_interval_list) = self.current_tier
            print('ACCEPT tier {0} \'{1}\''.format(tier_number, tier_name))

            tier_signature = tuple((begin, end)
                for begin, end, text in text_interval_list)

            self.current_tier_dict[tier_signature] = (tier_number, tier_name, 'accept')
            show_next_data()

        def data_skip(event):
            """
            Skips current sound/markup pair.
            """

            self.skip_set.add(self.current_data_tier)

            (tier_number, tier_name, interval_list, text_interval_list) = self.current_tier
            print('SKIP tier {0} \'{1}\''.format(tier_number, tier_name))

            tier_signature = tuple((begin, end)
                for begin, end, text in text_interval_list)

            self.current_tier_dict[tier_signature] = (tier_number, tier_name, 'skip')
            show_next_data()

        def stop(event):
            """
            Stops sound/markup selection process.
            """

            print('\nSTOP')
            pyplot.close()

        def on_key(event):
            """
            Processes key presses in Matplotlib GUI.
            """

            if event.key == 'a':
                data_accept(event)

            elif event.key == 'k':
                data_skip(event)

            elif event.key == 'escape':
                stop(event)

        def on_mouse(event):
            """
            Processes mouse button press event.
            """

            if event.inaxes != self.axes:
                return

            # Right button, disabling selection.

            if event.button > 1:
                self.selection = [None, 0.0]

                if self.selection_begin is not None:

                    self.selection_begin.remove()
                    self.selection_begin = None

                if self.selection_span is not None:

                    self.selection_span.remove()
                    self.selection_span = None

                    self.selection_end.remove()
                    self.selection_end = None

            # Left button, updating left selection boundary.

            elif self.selection[1] is not None and event.xdata is not None:

                self.selection = [max(event.xdata, 0), None]

                if self.selection_begin is not None:
                    self.selection_begin.remove()

                self.selection_begin = self.axes.axvline(
                    self.selection[0], color = 'red', linewidth = 2)

            # Left button, updating right selection boundary.

            elif self.selection[0] is not None and event.xdata is not None:

                self.selection[1] = event.xdata

                if self.selection_span is not None:

                    self.selection_span.remove()
                    self.selection_end.remove()

                self.selection_span = self.axes.axvspan(
                    self.selection[0], self.selection[1], alpha = 0.125, color = 'red')

                self.selection_end = self.axes.axvline(
                    self.selection[1], color = 'red', linewidth = 2)

        def center(event):
            """
            Centers axes on text markup.
            """

            text_interval_list = self.current_tier[3]

            text_min = min(begin for begin, end, text in text_interval_list)
            text_max = max(end for begin, end, text in text_interval_list)

            x_min = max(text_min - (text_max - text_min) * 0.2, 0.0)

            x_max = min(text_max + (text_max - text_min) * 0.2,
                self.sound_data.shape[0] / self.sound_rate)

            print(x_min, x_max)

            self.axes.set_xlim(x_min, x_max)

        def play(event):
            """
            Plays current sound recording or its selection portion.
            """

            # Getting sound data, if required.

            if self.sound_segment is None:

                self.sound_segment = pydub.AudioSegment(
                    self.sound_data.astype('int16').tobytes(),
                    sample_width = 2, frame_rate = int(self.sound_rate), channels = 1)

            # Playing either all or a portion of the current sound recording.

            if self.selection[0] is not None and self.selection[1] is not None:

                pydub.playback.play(self.sound_segment[
                    self.selection[0] : self.selection[1]])

            else:
                pydub.playback.play(self.sound_segment)

        # Setting up Matplotlib GUI.

        self.figure, self.axes = pyplot.subplots()
        pyplot.subplots_adjust(left = 0.05, right = 0.95, top = 0.8, bottom = 0.325)

        self.figure.canvas.mpl_connect('key_press_event', on_key)
        self.figure.canvas.mpl_connect('button_press_event', on_mouse)

        self.button_list = []

        for index, (handler, name) in enumerate([
            (data_accept, 'Accept (a)'),
            (data_skip, 'Skip (k)'),
            (stop, 'Stop (esc)'),
            (center, 'Center'),
            (play, 'Play')]):

            axes = pyplot.axes([0.05 + 0.11 * index, 0.05, 0.1, 0.075])
            button = widgets.Button(axes, name)

            button.on_clicked(handler)
            self.button_list.append((axes, button))

        show_next_data()
        pyplot.show()

        # Selection is finished, showing how many sound/pairs were selected and how many were not.

        print('\n{0} accepted, {1} skipped.\n'.format(
            len(self.accept_set), len(self.skip_set)))

        # Cleaning data so that we can be pickled.

        for attribute in ['data_generator',
            'current_data', 'current_tier', 'current_data_tier', 'current_tier_dict',
            'selection_begin', 'selection_span', 'selection_end',
            'sound_data', 'sound_segment',
            'axes', 'figure', 'cursor', 'button_list']:

            try:
                delattr(self, attribute)

            except AttributeError:
                pass

    @staticmethod
    def main_exclude(args):
        """
        Removes from selection data all sound/markup pairs from specified sources.
        """

        data_path = 'selection.gz'

        with open_file(data_path, 'rb') as selection_file:
            selection = pickle.load(selection_file)

        # Going through sound/markup data from specified sources.

        for current_data, (sound_data, sound_rate), current_tier in selection.sound_tier_generator(args):

            (source_path, source_hash, index,
                sound_filename, sound_bytes,
                textgrid_filename, textgrid,
                transcription_filename, transcription) = current_data

            (tier_number, tier_name, interval_list, text_interval_list) = current_tier

            current_data_tier = (source_hash, index, tier_number)

            # Removing sound/markup info.

            selection.accept_set.discard(current_data_tier)
            selection.check_set.discard(current_data_tier)

            selection.skip_set.discard(current_data_tier)
            selection.reject_set.discard(current_data_tier)

        # Saving modified selection data.

        with open_file(data_path, 'wb') as selection_file:
            pickle.dump(selection, selection_file)

    @staticmethod
    def main(args):
        """
        Loads interactive selection data, if it is present, and launches selection process.
        """

        command_dict = {
            'exclude': Selection.main_exclude}

        if args[0] in command_dict:
            return command_dict[args[0]](args[1:])

        # Processing command-line options.

        opt_list, arg_list = getopt.getopt(args, '', ['accept-source=', 'silent'])
        opt_dict = dict(opt_list)

        accept_set = set()

        if '--accept-source' in opt_dict:

            with open_file(opt_dict['--accept-source'], 'rb') as accept_file:
                accept_set = pickle.load(accept_file).accept_set

        # Loading already existing or creating new selection data.

        data_path = 'selection.gz'

        if path.exists(data_path):

            with open_file(data_path, 'rb') as selection_file:
                selection = pickle.load(selection_file)

        else:
            selection = Selection()

        # Performing selection, saving selection data.

        selection.accept_set.update(accept_set)
        selection.silent = '--silent' in opt_dict

        selection.run(args)

        with open_file(data_path, 'wb') as selection_file:
            pickle.dump(selection, selection_file)


remove_list = 'ʲ\'ʹ:◌́`◌̈ːʷ◌̊•ˁˤ◌̥◌̞'
remove_set = set(remove_list)

#: Substituting ʚ -> ɞ because of correction, see "Obsolete and nonstandard symbols in the International
#  Phonetic Alphabet" on Wikipedia.
#
substitution_dict = {'á': 'a', 'í': 'i', 'ʥ': 'dʑ', 'ú': 'u', 'έ': 'ɛ', 'ʨ': 'tɕ', 'ö': 'o', 'ә': 'ə',
    'ɔ́': 'ɔ', 'а': 'a', 'ε': 'ɛ', 'ʚ': 'ɞ', 'т': 't', 'ä': 'a', 'ü': 'u', 'о': 'o', '(ʔ)': 'ʔ',
    'u()': 'u', 'n(?)': 'n', 'ɞ()': 'ɞ', 'æ()': 'æ', '(l)': 'l', 'ɔ()': 'ɔ', 'é': 'e', 'ɫ': 'l'}

allow_set = set('abdefghijklmnopqrstuvwxyzæðŋœɔɕəɛɞɣɨɪɵʃʊʑʔγθχʒɜʉβɐɲɦɒɸʁøɟçɮʂɬɭ')
vowel_set = set('aeiouæœɔəɛɞɨɪɵɜyʉɐɒø')


def process_markup(text):
    """
    Transforms interval markup into standard form.
    """

    text = character_escape(text).strip().strip(remove_list).lower()

    # It seems that sometimes .strip(remove_list) does not work, e.g. with 'd\'ʒ'.

    text = ''.join(character
        for character in text if character not in remove_set)

    # Performing substitution, if required.

    if text in substitution_dict:
        text = substitution_dict[text]

    # If we have several repetitions of the same symbol, we collapse it to a single instance of this
    # symbol.

    text = re.sub('(.)\\1*', '\\1', text)

    return text


def main_markup(args):
    """
    Selection of good enough markup for markup recognition model training.
    """

    markup_path = 'markup.gz'
    selection_path = 'selection.gz'

    # If we already have markups from selected sound/markup pairs, we load them.

    if path.exists(markup_path):

        with open_file(markup_path, 'rb') as markup_file:
            markup_list = pickle.load(markup_file)

    # Otherwise we have to get them from selected sound/markup pairs.

    else:
        markup_list = []

        with open_file(selection_path, 'rb') as selection_file:
            selection = pickle.load(selection_file)

        for data_tuple, sound_tuple, tier_tuple in selection.sound_tier_generator(args):

            (source_path, source_hash, index,
                sound_filename, sound_bytes,
                textgrid_filename, textgrid,
                transcription_filename, transcription) = data_tuple

            (tier_number, tier_name, interval_list, text_interval_list) = tier_tuple

            # Gathering accepted markups.

            markup_signature = (source_hash, index, tier_number)
            if markup_signature in selection.accept_set:

                text_interval_list = [(begin, end, character_escape(text))
                    for begin, end, text in text_interval_list]

                markup_list.append((markup_signature, (tier_name, text_interval_list)))

        # Saving gathered markups for later re-use.

        with open_file(markup_path, 'wb') as markup_file:
            pickle.dump(markup_list, markup_file)

    # Processing selected markup pairs, computing phonetic symbols' statistics.

    accepted_list = []
    markup_dict = {}

    occurence_count = collections.Counter()
    markup_count = collections.Counter()

    symbol_dict = collections.defaultdict(list)

    for signature, (tier_name, text_interval_list) in markup_list:

        text_list = []
        rejected_flag = False

        for begin, end, text in text_interval_list:
            text = process_markup(text)

            # Unusual markup is rejected.

            if text in set(['oɔ', 'ɔo', 'oa', 'iʔ', 'a(ʔ)a', 'ei', 'ɔ(ʔ)ɔ', 'iu', 'ɛ(ʔ)', 'i(ʔ)', 'i (ʔ)',
                'u(ʔ)', 'uʔ', 'aʔ', 'ʔɛ', 'rʔ', 'ɛʃ', 'eɔ', 'ʔɔ', '\\s\\ɐ', '\\cx', 'ue', 'ua', 'ea', 'ou',
                'æu', 'wɸ', 'ɵu', 'uo', 'uɔ', 'æo', 'ch', 'je', 'сh', 'eu', 'eo', 'jo', 'ja', 'jɔʹ', 'ju',
                'ui', 'oi', 'jɔ', 'ai', 'ae', 'oj', 'aj', 'uj', 'oe', 'əi', 'rɔ', 'zʔ', 'ʔa', 'eʔ', 'ɔʔ',
                'ieʔ', 'c']):

                rejected_flag = True
                continue

            # Standard digraphs are accepted.

            elif text in set(['dʒ', 'dʃ', 'tʃ', 'dʑ', 'tɕ', 'ts']):

                text_list.append(text)
                continue

            # If the markup does not consists of a single character, or is an unknown character, we
            # terminate with error.

            if len(text) > 1:

                print(interval_list_to_string(text_interval_list))
                print(repr(text))
                print(repr(''.join('◌' + character for character in text)))

                raise NotImplementedError

            if text not in allow_set:

                print(interval_list_to_string(text_interval_list))
                print(repr(text))
                print(repr(''.join('◌' + character for character in text)))

                raise NotImplementedError

            text_list.append(text)

        # Saving accepted markup, if we have one.

        if rejected_flag:
            continue

        accepted_list.append(signature)
        markup_dict[signature] = text_list

        text_set = set(text_list)

        occurence_count.update(text_list)
        markup_count.update(text_set)

        for text in text_set:
            symbol_dict[text].append(signature)

    # Showing info of gathered markup.

    print('{0}/{1} ({2:.2f}%) markups accepted'.format(
       len(accepted_list), len(markup_list), 100.0 * len(accepted_list) / len(markup_list)))

    print('Occurence counts:')
    print(occurence_count)

    print('Markup counts:')
    print(markup_count)

    # Removing symbols with low occurence counts.

    occurence_list = occurence_count.most_common()

    for index in range(len(occurence_list)):

        least_common = list(filter(
            lambda symbol_count: symbol_count[1] > 0,
            occurence_count.most_common()))[-1]

        if least_common[1] >= 48:
            break

        # Updating symbol occurence counts.

        for signature in symbol_dict[least_common[0]]:

            if signature not in markup_dict:
                continue

            text_list = markup_dict.pop(signature)

            occurence_count.subtract(text_list)
            markup_count.subtract(set(text_list))

    print('{0} markups left after least common removal.'.format(len(markup_dict)))

    # Splitting markup into portions with as equal as possible symbol occurence counts.

    symbol_list = [symbol
        for symbol, count in occurence_count.most_common()
            if count > 0]

    symbol_list.reverse()

    signature_dict = collections.defaultdict(list)
    signature_set = set()

    for symbol in symbol_list:
        for signature in symbol_dict[symbol]:

            if signature not in markup_dict or signature in signature_set:
                continue

            signature_dict[symbol].append(signature)
            signature_set.add(signature)

    # Randomizing data order as much as we can.

    rng = random.Random(2)

    for symbol, signature_list in signature_dict.items():
        rng.shuffle(signature_list)

        signature_list.sort(
            key = lambda signature: collections.Counter(markup_dict[signature])[symbol],
            reverse = True)

    # Not optimized, but simple splitting.

    split_n = 8

    split_data_list = [[] for i in range(split_n)]
    split_count_list = [collections.Counter() for i in range(split_n)]

    for symbol in symbol_list:

        for signature in signature_dict[symbol]:

            # Getting the partition with the least number of the symbol's occurences.

            count, length, total, index = min(

                (split_count_list[index][symbol],
                    sum(split_count_list[index].values()),
                    len(split_data_list[index]),
                    index)

                    for index in range(split_n))

            split_data_list[index].append(signature)
            split_count_list[index].update(markup_dict[signature])

    # Saving list of accepted markups and data split.

    with open_file('accepted.gz', 'wb') as accepted_file:
        pickle.dump((accepted_list, split_data_list), accepted_file)


def main_data(args):
    """
    Computes training data for modelling of dependency between sound recordings and phonetic markups from
    selected sound recordings and accepted markup.
    """

    opt_list, arg_list = getopt.getopt(args, '', ['limit='])
    opt_dict = dict(opt_list)

    limit = int(opt_dict['--limit']) if '--limit' in opt_dict else None

    # Loading source data.

    selection_path = 'selection.gz'
    accepted_path = 'accepted.gz'

    with open_file(selection_path, 'rb') as selection_file:
        selection = pickle.load(selection_file)

    with open_file(accepted_path, 'rb') as accepted_file:
        accepted_set = set(pickle.load(accepted_file))

    # Trying to load already computed feature/label data.

    data_path = 'data.gz'

    if path.exists(data_path):

        with open_file(data_path, 'rb') as data_file:
            data_dict, label_set = pickle.load(data_file)

    else:
        data_dict = {}
        label_set = set()

    # Setting up signal handling for iteration stopping.

    run_flag = True

    def handler(signal, frame):
        """
        Processes stopping signal, drops run flag.
        """

        nonlocal run_flag
        run_flag = False

    signal.signal(signal.SIGINT, handler)

    # Computing features of accepted sound/markup pairs.

    window_width_s = 0.050
    step_width_s = window_width_s / 8

    for data_index, (data_tuple, sound_tuple, tier_tuple) in enumerate(
        selection.sound_tier_generator(arg_list, silent = True)):

        if (not run_flag or
            limit is not None and data_index >= limit):
            break

        (source_path, source_hash, index,
            sound_filename, sound_bytes,
            textgrid_filename, textgrid,
            transcription_filename, transcription) = data_tuple

        (tier_number, tier_name, interval_list, text_interval_list) = tier_tuple

        # If we have an invalid markup, or if this sound/markup pair is already processed, we go on.

        markup_signature = (source_hash, index, tier_number)

        if markup_signature not in accepted_set or markup_signature in data_dict:
            continue

        # Getting sound data.

        extension = path.splitext(sound_filename)[1]

        if len(extension) <= 0:
            extension = '.wav'

        with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

            temp_file.write(sound_bytes)
            temp_file.flush()

            sound = AudioPraatLike(pydub.AudioSegment.from_file(temp_file.name))
            (sound_rate, sound_data) = audioBasicIO.readAudioFile(temp_file.name)

        # Computing formant features ensuring accurate window alignment.

        start_cpu_time = cpu_time()

        sound.init_formant_fft(padding_length = window_width_s / 2)

        half_w_size = int(math.floor(window_width_s / 2 * sound.intensity_sound.frame_rate))
        formant_half_w_size = int(math.floor(window_width_s / 2 * sound.formant_frame_rate))

        step_count = int(math.floor(sound.intensity_sound.duration_seconds / step_width_s))

        start_time = (sound.padding_length
            if sound.padding_length <= window_width_s / 2 else
            window_width_s / 2)

        # Merging channels of, adding padding to and otherwise preparing the source sound data for
        # pyAudioAnalysis features.

        if len(sound_data.shape) > 1:
            sound_data = numpy.mean(sound_data, axis = 1)

        sound_padding = int(math.floor(window_width_s / 2 * sound_rate))

        sound_data = numpy.concatenate([
            numpy.zeros(sound_padding), sound_data, numpy.zeros(sound_padding)])

        sound_data = sound_data - sound_data.mean()
        sound_data = sound_data / numpy.abs(sound_data).max()

        [fbank, freqs] = mfccInitFilterBanks(sound_rate, half_w_size)
        nChroma, nFreqsPerChroma = stChromaFeaturesInit(half_w_size, sound_rate)

        numOfTimeSpectralFeatures = 8
        nceps = 13
        numOfChromaFeatures = 13
        totalNumOfFeatures = numOfTimeSpectralFeatures + nceps + numOfChromaFeatures

        formant_number = 4
        nyquist_frequency = sound.formant_frame_rate / 2

        feature_list = []
        for index in range(step_count):

            step_time = start_time + index * step_width_s

            window_center = int(math.floor(step_time * sound.intensity_sound.frame_rate))
            formant_w_center = int(math.floor(step_time * sound.formant_frame_rate))

            # Computing pyAudioAnalysis features with proper window computation, see function
            # stFeatureExtration in pyAudioAnalysis.audioFeatureExtraction.

            window = sound_data[window_center - half_w_size : window_center + half_w_size + 1]
            window_fft = abs(scipy.fftpack.fft(window))[0 : half_w_size] / half_w_size

            if index == 0:
                window_fft_before = window_fft.copy()

            feature_array = numpy.zeros((totalNumOfFeatures + formant_number, 1))

            feature_array[0] = stZCR(window)

            feature_array[1] = stEnergy(window)
            feature_array[2] = stEnergyEntropy(window)

            [feature_array[3], feature_array[4]] = stSpectralCentroidAndSpread(window_fft, sound_rate)
            feature_array[5] = stSpectralEntropy(window_fft)
            feature_array[6] = stSpectralFlux(window_fft, window_fft_before)
            feature_array[7] = stSpectralRollOff(window_fft, 0.90, sound_rate)

            feature_array[numOfTimeSpectralFeatures : numOfTimeSpectralFeatures + nceps, 0] = \
                stMFCC(window_fft, fbank, nceps).copy()

            chromaNames, chromaF = stChromaFeatures(window_fft, sound_rate, nChroma, nFreqsPerChroma)

            feature_array[numOfTimeSpectralFeatures + nceps :
                numOfTimeSpectralFeatures + nceps + numOfChromaFeatures - 1] = chromaF

            feature_array[numOfTimeSpectralFeatures + nceps + numOfChromaFeatures - 1] = chromaF.std()

            # Computing formants.

            sample_list = sound.formant_sample_list[
                formant_w_center - formant_half_w_size : formant_w_center + formant_half_w_size + 1]

            formant_list = compute_formants(
                sample_list, nyquist_frequency)

            # If we have less then required number of formants, we take the formant Nyquist frequency as the
            # missing values.

            if len(formant_list) >= formant_number:
                formant_array = numpy.array(formant_list[:formant_number])

            else:
                formant_array = numpy.empty(formant_number)

                formant_array[:len(formant_list)] = formant_list
                formant_array[len(formant_list):] = nyquist_frequency

            # Ok, we have another feature vector.

            feature_array[-formant_number:] = formant_array.reshape(formant_number, 1)
            feature_list.append(feature_array)
            
            window_fft_before = window_fft.copy()

        # And now gathering raw features and computing their windowed means and standard deviations as final
        # features, and at the same time computing sequence of labels from the markup.

        source_array = numpy.concatenate(feature_list, 1)

        feature_count, source_length = source_array.shape
        feature_array = numpy.zeros((feature_count * 2, source_length - 8))

        interval_list = [(begin, end, process_markup(text))
            for begin, end, text in interval_list]

        label_list = []

        for index in range(source_length - 8):

            feature_array[ : feature_count, index] = \
                numpy.mean(source_array[:, index : index + 9], axis = 1)

            feature_array[feature_count :, index] = \
                numpy.std(source_array[:, index : index + 9], axis = 1)

            # Finding label for the current position, ineffective but simple.

            step_time = start_time + (index + 4) * step_width_s
            label = ''

            for begin, end, text in interval_list:
                if step_time >= begin and step_time < end:

                    label = text
                    break

            label_list.append(label)
            label_set.add(label)

        # Saving another feature array and label sequence, showing their info.

        data_dict[markup_signature] = (feature_array, label_list)
        elapsed_cpu_time = cpu_time(start_cpu_time)

        sound_shape = sound_data.shape

        if len(sound_shape) == 1:
            sound_shape = sound_shape[0]

        print(
            '({0}) {1:.3f}s of sound + {2:.3f}s x2 of padding, "{3}" markup, {4} at {5} Hz formant data, '
            '{6} at {7} Hz sound data, {8} features, {9} labels, '
            '{10:.3f}s CPU time, {11:.3f}s per thread.'.format(
                data_index,
                sound.intensity_sound.duration_seconds, sound.padding_length,
                interval_list_to_string(interval_list),
                len(sound.formant_sample_list), sound.formant_frame_rate,
                sound_shape, sound_rate,
                feature_array.shape, len(label_list),
                elapsed_cpu_time, elapsed_cpu_time / 8))

        sys.stdout.flush()

    # Showing overall data info and saving the data.

    print('{0} feature array and label sequence pairs, {1} distinct labels: {2}'.format(
        len(data_dict), len(label_set), list(sorted(label_set))))

    with open_file(data_path, 'wb') as data_file:
        pickle.dump((data_dict, label_set), data_file)


def main_model_hmm(args):
    """
    Models dependency between sound recordings and phonetic markups via HMM (hidden Markov model), using
    prepared training data.
    """

    data_path = 'data.gz'

    with open_file(data_path, 'rb') as data_file:
        data_dict, label_set = pickle.load(data_file)

    data_list = [data_item
        for signature, data_item in sorted(data_dict.items())]

    label_list = list(sorted(label_set))
    label_dict = {label: index for index, label in enumerate(label_list)}

    # Computing parameters of Gaussian HMM model, see function 'trainHMM_computeStatistics' from
    # pyAudioAnalysis.audioSegmentation for reference.

    feature_count = data_list[0][0].shape[0]
    label_count = len(label_set)

    start_count = numpy.zeros(label_count, numpy.int)
    transition_count = numpy.zeros((label_count, label_count), numpy.int)

    mean_sum = numpy.zeros((label_count, feature_count))
    emission_count = numpy.zeros(label_count, numpy.int)

    for feature_array, label_sequence in data_list:
        start_count[label_dict[label_sequence[0]]] += 1

        for label_a, label_b in zip(label_sequence[:-1], label_sequence[1:]):
            transition_count[label_dict[label_a], label_dict[label_b]] += 1

        for index, label in enumerate(label_sequence):
            label_index = label_dict[label]

            mean_sum[label_index, :] += feature_array[:, index]
            emission_count[label_index] += 1

    def normalize(count_array):
        """
        Normalizes counts into probabilities with smoothing.
        """

        total = float(count_array.sum())
        addition = min(label_count, max(total, 1.0) / label_count)

        return (count_array + numpy.full(label_count, addition / label_count)) / (total + addition)

    # Computing starting and transition probabilities.

    start_p = normalize(start_count)
    transition_p = numpy.empty_like(transition_count, numpy.float64)

    for i in range(label_count):
        transition_p[i, :] = normalize(transition_count[i, :])

        if any(transition_p[i, :] <= 0):
            raise NotImplementedError

    print('{0} feature array / label sequence pairs, {1} unique labels, {2} transitions, '
        '{3} feature vector emissions.\n'
        'Start probabilities:\n{4}'.format(
            len(data_list), len(label_list), transition_count.sum(), emission_count.sum(),
            ', '.join('\'{0}\': {1:.4f}'.format(label, p) for label, p in zip(label_list, start_p))))

    # Computing means and then standard deviations of feature emission distributions.

    mean_array = numpy.empty_like(mean_sum)

    for i in range(label_count):
        mean_array[i, :] = mean_sum[i, :] / emission_count[i]

        for value in mean_array[i, :]:
            if numpy.abs(value) <= 0:
                raise NotImplementedError

    stdev_sum = numpy.zeros((label_count, feature_count))

    for feature_array, label_sequence in data_list:
        for index, label in enumerate(label_sequence):

            label_index = label_dict[label]
            stdev_sum[label_index] += numpy.square(feature_array[:, index] - mean_array[label_index])

    stdev_array = numpy.empty_like(stdev_sum)

    for i in range(label_count):
        stdev_array[i, :] = numpy.sqrt(stdev_sum[i, :] / emission_count[i])

    # Computing total log-likelihood.

    start_ll = (numpy.log2(start_p) * start_count).sum()
    transition_ll = (numpy.log2(transition_p) * transition_count).sum()

    emission_ll = 0.0
    factor = -numpy.log2(numpy.e) / 2

    for feature_array, label_sequence in data_list:
        for index, label in enumerate(label_sequence):

            label_index = label_dict[label]

            emission_ll += factor * numpy.square(
                (feature_array[:, index] - mean_array[label_index]) / stdev_array[label_index]).sum()

    emission_ll -= \
        emission_count.sum() * numpy.log2(2 * numpy.pi) * float(feature_count) / 2 + \
        numpy.sum(numpy.log2(stdev_array).sum(axis = 1) * emission_count)

    print('Start log-likehood: {0:.3f}, transition log-likehood: {1:.3f}, emission log-likehood: {2:.3f}\n'
        'Total log-likehood: {3:.3f}'.format(
        start_ll, transition_ll, emission_ll,
        start_ll + transition_ll + emission_ll))

    # Checking how the model represents training data.

    model = hmmlearn.hmm.GaussianHMM(label_count, 'diag')

    model.startprob_ = start_p
    model.transmat_ = transition_p
    model.means_ = mean_array
    model.covars_ = stdev_array

    match_count = 0
    for feature_array, label_sequence in data_list:

        if set(label_sequence) == set(label_list[index]
            for index in model.predict(feature_array.T)):

            match_count += 1

    print('Training data label set match: {0}/{1} ({2:.2f}%)'.format(
        match_count, len(data_list), 100.0 * match_count / len(data_list)))


def main_model(args):
    """
    Models dependency between sound recordings and phonetic markups using prepared training data.
    """

    data_path = 'data.gz'

    with open_file(data_path, 'rb') as data_file:
        data_dict, label_set = pickle.load(data_file)

    data_list = [data_item
        for signature, data_item in sorted(data_dict.items())]

    label_list = list(sorted(label_set))
    label_dict = {label: index for index, label in enumerate(label_list)}

    # Shrinking data by removing intermediate feature vectors.

    data_list = [
        (feature_array[:, ::4], label_sequence[::4])
            for feature_array, label_sequence in data_list]

    label_set = set()

    label_set.update(*(label_sequence
        for feature_array, label_sequence in data_list))

    label_dict = {label: index for index, label in enumerate(label_list)}

    # Splitting feature matrices and label sequences.

    rng = random.Random(2)
    rng.shuffle(data_list)

    x_list = [feature_array[:, index]
        for feature_array, label_sequence in data_list
        for index in range(len(label_sequence))]

    y_list = [label_dict[label]
        for feature_array, label_sequence in data_list
        for label in label_sequence]

    print(len(x_list))
    print(len(y_list))

    # Modelling feature-label dependency via logistic regression.

    how_many = 16384

    import sklearn

    model = sklearn.linear_model.LogisticRegression()

    print(set(y_list[:how_many]))
    print(len(set(y_list[:how_many])))

    from sklearn.model_selection import cross_val_score, cross_validate, KFold

    k_fold = KFold(n_splits = 4, shuffle = False)

    result = cross_validate(model, x_list[:how_many], y_list[:how_many],
        scoring = 'accuracy', cv = k_fold, n_jobs = 4)

    for key, value in sorted(result.items()):
        print('{0}: {1}'.format(key, value))

    print('{0:.3f}s'.format(result['fit_time'].sum()))

    print(result['train_score'].mean())
    print(result['test_score'].mean())


def main_model_crf(args):
    """
    Models dependency between sound recordings and phonetic markups via CRF (conditional random field),
    using prepared training data.
    """

    data_path = 'data.gz'

    with open_file(data_path, 'rb') as data_file:
        data_dict, label_set = pickle.load(data_file)

    data_list = [data_item
        for signature, data_item in sorted(data_dict.items())]

    label_list = list(sorted(label_set))
    label_dict = {label: index for index, label in enumerate(label_list)}

    # Shrinking data by removing intermediate feature vectors.

    data_list = [
        (feature_array[:, ::4], label_sequence[::4])
            for feature_array, label_sequence in data_list]

    label_set = set()

    label_set.update(*(label_sequence
        for feature_array, label_sequence in data_list))

    label_dict = {label: index for index, label in enumerate(label_list)}

    # Showing training data info.

    print('{0} training sequences, {1} samples total, {2} unique labels.'.format(
        len(data_list),
        sum(len(label_sequence)
            for feature_array, label_sequence in data_list),
        len(label_set)))

    rng = random.Random(2)
    rng.shuffle(data_list)

    how_many = len(data_list)

    # Trying using CRFsuite directly.

    def crfsuite_output(data_list, data_file_path):
        """
        Outputs sound labelling data in the CRFsuite format.
        """

        with open(data_file_path, 'wb') as data_file:

            for index, (feature_array, label_sequence) in enumerate(data_list[:how_many]):

                if index > 0:
                    data_file.write(b'\n')

                for index_a, label in enumerate(label_sequence):

                    feature_string = '\t'.join(
                            'f{0:02}:{1:.9f}'.format(index_b, feature_array[index_b, index_a])
                            for index_b in range(feature_array.shape[0]))

                    marker_string = \
                        '\t__BOS__' if index_a == 0 else \
                        '\t__EOS__' if index_a == len(label_sequence) - 1 else ''

                    data_file.write('{0}\t{1}{2}\n'.format(
                        label if len(label) > 0 else '_', feature_string, marker_string).encode('utf-8'))

    crfsuite_output(data_list[: -how_many // 4], 'crfsuite_train')
    crfsuite_output(data_list[-how_many // 4 :], 'crfsuite_test')


def main_kaldi_data(args):
    """
    Prepares data for automatic markup recognition via Kaldi ASR toolkit.
    """

    opt_list, arg_list = getopt.getopt(args, '', ['limit='])
    opt_dict = dict(opt_list)

    limit = int(opt_dict['--limit']) if '--limit' in opt_dict else None

    # Setting up working directories.

    root_dir_path = path.realpath(arg_list[-1])

    steps_dir_path = path.join(root_dir_path, 'steps')
    utils_dir_path = path.join(root_dir_path, 'utils')

    print('Root directory: {0}'.format(root_dir_path))

    # Loading source data.

    selection_path = 'selection.gz'
    accepted_path = 'accepted.gz'

    with open_file(selection_path, 'rb') as selection_file:
        selection = pickle.load(selection_file)

    with open_file(accepted_path, 'rb') as accepted_file:
        accepted_list, split_data_list = pickle.load(accepted_file)

    split_data_set = set(split_data_list[0])
    split_data_set.update(*split_data_list[1:])

    # Placing properly formatted sound/markup data where it needs to go.

    wav_dir_path = path.join(root_dir_path, 'sound')
    makedirs(wav_dir_path, exist_ok = True)

    markup_dict = {}

    phone_set = set()
    word_set = set()

    # Processing all available sound/markup pairs.

    for data_index, (data_tuple, sound_tuple, tier_tuple) in enumerate(
        selection.sound_tier_generator(arg_list[:-1])):

        if limit is not None and len(markup_list) >= limit:
            break

        (source_path, source_hash, index,
            sound_filename, sound_bytes,
            textgrid_filename, textgrid,
            transcription_filename, transcription) = data_tuple

        (tier_number, tier_name, interval_list, text_interval_list) = tier_tuple

        # If we have an invalid markup, we go on.

        markup_signature = (source_hash, index, tier_number)

        if markup_signature not in split_data_set:
            continue

        interval_list = [(begin, end, process_markup(text))
            for begin, end, text in interval_list]

        extension = path.splitext(sound_filename)[1]

        if len(extension) <= 0:
            extension = '.wav'

        with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

            temp_file.write(sound_bytes)
            temp_file.flush()

            # Placing sound data, resampled to one 16 bit channel at 16 kHz and, where it needs to go.

            subprocess.check_call(['sox',
                temp_file.name, '-b', '16', '-r', '16k', '-c', '1', '-G',
                path.join(wav_dir_path, 's{0:06d}.wav'.format(data_index))])

            sys.stdout.write('{0} "{1}"\n'.format(data_index, interval_list_to_string(interval_list)))
            sys.stdout.flush()

            markup_dict[markup_signature] = (data_index, interval_list)

    # Saving markup data of exported sound recordings, reporting export.

    with open_file('source.gz', 'wb') as source_file:

        pickle.dump({data_index: interval_list
            for data_index, interval_list in markup_dict.values()}, source_file)

    print('Exported {0} sound recordings'.format(len(markup_dict)))

    def word_list(interval_list):
        """
        Transforms markup into word list.
        """

        word_list = []
        current_list = []

        for begin, end, text in interval_list:

            if len(text) <= 0:

                # Another word ends.

                if len(current_list) > 0:

                    word_list.append(''.join(current_list))

                    word_set.add(tuple(current_list))
                    phone_set.update(current_list)

                    current_list = []

                continue

            else:
                current_list.append(text)

        # Checking if we have a word finished by interval list finish.

        if len(current_list) > 0:

            word_list.append(''.join(current_list))

            word_set.add(tuple(current_list))
            phone_set.update(current_list)

        return word_list

    def write_out_data(signature_list, dir_name, dir_path):
        """
        Writes out sound/markup data.
        """

        makedirs(dir_path, exist_ok = True)

        data_list = sorted(markup_dict[signature]
            for signature in signature_list)

        # Writing out data.

        with open(path.join(dir_path, 'text'), 'wb') as text_file, \
            open(path.join(dir_path, 'wav.scp'), 'wb') as wav_file, \
            open(path.join(dir_path, 'utt2spk'), 'wb') as utt_file:

            for index, interval_list in data_list:

                text_file.write('s{0:06d} {1}\n'.format(
                    index, ' '.join(word_list(interval_list))).encode('utf-8'))

                wav_file.write('s{0:06d} sound/s{0:06d}.wav\n'.format(index).encode('utf-8'))
                utt_file.write('s{0:06d} s{0:06d}\n'.format(index).encode('utf-8'))

                print('{0} {1}: {2}'.format(dir_name, index, word_list(interval_list)))

        print('Dataset \'{0}\': {1} sound recordings.'.format(
            dir_name, len(data_list)))

        # Producing 'spk2utt' file.

        print(['utils/utt2spk_to_spk2utt.pl',
            'data/{0}/utt2spk'.format(dir_name), '>',
            'data/{0}/spk2utt'.format(dir_name)])

        with open(path.join(dir_path, 'spk2utt'), 'wb') as spk_file:

            subprocess.check_call([
                path.join(utils_dir_path, 'utt2spk_to_spk2utt.pl'),
                path.join(dir_path, 'utt2spk')],
                stdout = spk_file)

    # Getting ready to write sound/markup dataset and cross-validation training/testing dataset pairs.

    data_dir_path = path.join(root_dir_path, 'data')

    for index_a, signature_list_a in enumerate(split_data_list):

        train_name = 'train_{0}'.format(index_a)
        test_name = 'test_{0}'.format(index_a)

        train_dir_path = path.join(data_dir_path, train_name)
        test_dir_path = path.join(data_dir_path, test_name)

        makedirs(train_dir_path, exist_ok = True)
        makedirs(test_dir_path, exist_ok = True)

        # Writing out another training/testing dataset pair.

        train_list = [signature
            for index_b, signature_list_b in enumerate(split_data_list) if index_b != index_a
            for signature in signature_list_b]

        write_out_data(train_list, train_name, train_dir_path)
        write_out_data(signature_list_a, test_name, test_dir_path)

    # And now saving the whole sound/markup dataset for final training.

    train_dir_path = path.join(data_dir_path, 'train')
    makedirs(train_dir_path, exist_ok = True)

    train_list = [signature
        for signature_list in split_data_list
        for signature in signature_list]

    write_out_data(train_list, 'train', train_dir_path)

    # Preparing language data.

    print('{0} unique words, {1} unique phones.'.format(
        len(word_set), len(phone_set)))

    dict_dir_path = path.join(data_dir_path, 'local', 'dict')
    makedirs(dict_dir_path, exist_ok = True)

    with open(path.join(dict_dir_path, 'nonsilence_phones.txt'), 'wb') as phone_file:
        for phone in sorted(phone_set):

            if len(phone) > 0:
                phone_file.write('{0}\n'.format(phone).encode('utf-8'))

    with open(path.join(dict_dir_path, 'silence_phones.txt'), 'wb') as silence_file:
        silence_file.write(b'SIL\n')

    with open(path.join(dict_dir_path, 'optional_silence.txt'), 'wb') as optional_file:
        optional_file.write(b'SIL\n')

    with open(path.join(dict_dir_path, 'lexicon.txt'), 'wb') as lexicon_file:
        lexicon_file.write(b'<SIL> SIL\n')

        for word_tuple in sorted(word_set):
            lexicon_file.write('{0} {1}\n'.format(
                ''.join(word_tuple), ' '.join(word_tuple)).encode('utf-8'))


def main_kaldi_model(args):
    """
    Trains models for automatic markup recognition via Kaldi ASR toolkit.
    """

    raise NotImplementedError


def read_align_file(align_file_path, align_dict = None):
    """
    Reads decoded alignments from specified file, parses them into transcription and markup interval lists.
    """

    if align_dict is None:
        align_dict = {}

    with open(align_file_path, 'rb') as align_file:

        interval_list = None

        for line in align_file:
            line_list = line.decode('utf-8').split()

            if len(line_list) <= 0:
                continue

            # Parsing alignment intervals.

            if line_list[1] == '[':

                if line_list[-1] != ']':
                    raise NotImplementedError

                interval_list = []
                total_count = 0

                for interval_sequence in \
                    line.decode('utf-8')[len(line_list[0]) :].strip()[1:-1].split('] ['):

                    interval_count = len(interval_sequence.strip().split())

                    interval_list.append((total_count * 0.01, (total_count + interval_count) * 0.01))
                    total_count += interval_count
                
                continue

            # Parsing phonetic symbols.

            markup_list = []

            for text, (begin, end) in zip(line_list[1:], interval_list):
                text = text if text != 'SIL' else ' '

                if len(markup_list) <= 0 or text != ' ' or markup_list[-1][2] != ' ':
                    markup_list.append((begin, end, text))

                # Concatenating silence intervals together.

                else:
                    begin_before, end_before = markup_list[-1][:2]
                    markup_list[-1] = (begin_before, end, ' ')

            transcription_list = [text
                for begin, end, text in markup_list]

            align_dict[int(line_list[0][1:])] = (transcription_list, markup_list)

    # Returning what we have read.

    return align_dict


class Levenshtein_State(object):
    """
    State of Levenshtein distance computation, with number of insertions, deletions, substitutions, total
    distance and sets of indices of equal and unequal substitutions.
    """

    def __init__(self, del_n):
        """
        Initial state with a given number of deletions.
        """

        self.ins_n = 0
        self.del_n = del_n
        self.sub_n = 0

        self.total = del_n

        self.equal_sub = {}
        self.not_equal_sub = {}


def levenshtein(source_list, result_list):
    """
    Computes Levenshtein distance between source and decoded transcriptions, keeping insertion, deletion,
    substitution statistics and substitution indices.

    See https://en.wikipedia.org/wiki/Levenshtein_distance#Iterative_with_full_matrix and function
    'LevenshteinEditDistance' in file src/util/edit-distance-inl.h of Kaldi distribution for reference.

    Not terribly efficient, prioritizing correctness over efficiency.
    """

    previous_list = [Levenshtein_State(i)
        for i in range(len(source_list) + 1)]

    current_list = [None
        for i in range(len(source_list) + 1)]

    # Two-row Levenshtein matrix iteration.

    for i in range(1, len(result_list) + 1):

        current_list[0] = copy.deepcopy(previous_list[0])
        current_list[0].ins_n += 1
        current_list[0].total += 1

        for j in range(1, len(source_list) + 1):

            ins_n = previous_list[j].total + 1
            del_n = current_list[j - 1].total + 1
            sub_n = previous_list[j - 1].total

            if result_list[i - 1] != source_list[j - 1]:
                sub_n += 1

            # We prefer substitutions.

            if sub_n <= ins_n and sub_n <= del_n:

                current_list[j] = copy.deepcopy(previous_list[j - 1])

                if result_list[i - 1] == source_list[j - 1]:
                    current_list[j].equal_sub[j - 1] = i - 1

                else:
                    current_list[j].sub_n += 1
                    current_list[j].not_equal_sub[j - 1] = i - 1

                current_list[j].total = sub_n

            # Insertions and deletions are processed in standard manner, deletions of phonetical symbols
            # are currently preferred.

            elif del_n <= ins_n:

                current_list[j] = copy.deepcopy(current_list[j - 1])
                current_list[j].total = del_n
                current_list[j].del_n += 1

            else:

                current_list[j] = copy.deepcopy(previous_list[j])
                current_list[j].total = ins_n
                current_list[j].ins_n += 1

        # Row switch at the end of the iteration.

        previous_list = current_list

        current_list = [None
            for i in range(len(source_list) + 1)]

    # Final result.

    return previous_list[-1]


def main_measure(args):
    """
    Gathering results of Kaldi-based markup recognition testing, computing modelling quality measures.
    """

    opt_list, arg_list = getopt.getopt(args, '', ['kaldi-data-output=', 'source='])
    opt_dict = dict(opt_list)

    # Loading source markup data.

    source_dict = {}

    if '--kaldi-data-output' in opt_dict:

        with open(opt_dict.get('--kaldi-data-output', 'kaldi_data.output'), 'rb') as source_file:

            for line in source_file:
                match = re.match('(\\d+) "(.*)"', line.decode('utf-8'))

                if not match:
                    continue

                source_dict[int(match.group(1))] = \
                    (match.group(2), re.sub(' \\||\\| ', '', match.group(2)).split('|'), None)

    # We have full markup data.

    else:

        with open_file(opt_dict.get('--source', 'source.gz'), 'rb') as source_file:
            markup_dict = pickle.load(source_file)

        source_dict = {
            
            index: (interval_list_to_string(interval_list),
                [text for begin, end, text in interval_list if text != ''],
                interval_list)

                for index, interval_list in markup_dict.items()}

    # Going through all testing result sources.

    sys.stdout.write('\n')
    result_dict = {}

    for arg in arg_list:

        result_dir_path = path.realpath(arg)
        print('Result data path: {0}'.format(result_dir_path))

        for result_file_path in glob.glob(path.join(result_dir_path, 'align.?.txt')):
            read_align_file(result_file_path, result_dict)

    print('\n{0} testing results.'.format(len(result_dict)))

    # Showing source and testing results, measuring their inconsistency.

    edit_total = 0

    ins_total = 0
    del_total = 0
    sub_total = 0

    match_total = 0

    source_total = 0
    result_total = 0

    occurence_dict = collections.Counter()
    substitution_dict = collections.defaultdict(collections.Counter)

    # Markup interval begin/end error statistics.

    delta_begin_list = []
    delta_end_list = []

    relative_begin_list = []
    relative_end_list = []

    sub_delta_begin_list = []
    sub_delta_end_list = []

    sub_relative_begin_list = []
    sub_relative_end_list = []

    # Comparing all testing results to original markups.

    for index, (result_list, interval_list) in sorted(result_dict.items()):

        source_str, source_list, maybe_markup_list = source_dict[index]

        sys.stdout.write('\n>> "{0}"\n<< "{1}"\n'.format(
            source_str, '|'.join(result_list)))

        result_list = [symbol
            for symbol in result_list if symbol != ' ']

        source_total += len(source_list)
        result_total += len(result_list)

        occurence_dict.update(source_list)

        # Computing edit distance and number of matching symbols.

        l_state = levenshtein(source_list, result_list)
        edit_total += l_state.total

        ins_total += l_state.ins_n
        del_total += l_state.del_n
        sub_total += l_state.sub_n

        for i_from, i_to in l_state.not_equal_sub.items():
            substitution_dict[source_list[i_from]][result_list[i_to]] += 1

        # Counting set-like, i.e. unordered, phonetical symbol matchings.

        source_count = collections.Counter(source_list)
        result_count = collections.Counter(result_list)

        match_count = 0

        for symbol in set(source_list) | set(result_list):
            match_count += min(source_count[symbol], result_count[symbol])

        match_total += match_count

        # How about markup interval border alignments?

        if maybe_markup_list is not None:

            interval_list = [(begin, end, text)
                for begin, end, text in interval_list
                    if text != ' ']

            markup_list = [(begin, end, text)
                for begin, end, text in maybe_markup_list
                    if text != '']

            # Interval border statistics for matched symbols.

            for i_from, i_to in l_state.equal_sub.items():

                begin_a, end_a, text_a = markup_list[i_from]
                begin_b, end_b, text_b = interval_list[i_to]

                length = end_a - begin_a

                if text_a != text_b or length <= 0:
                    raise NotImplementedError

                delta_begin = abs(begin_a - begin_b)
                delta_end = abs(end_a - end_b)

                delta_begin_list.append(delta_begin * 1000)
                delta_end_list.append(delta_end * 1000)

                relative_begin_list.append(delta_begin / length)
                relative_end_list.append(delta_end / length)

            # And now interval border statistics for substitutions.

            for i_from, i_to in l_state.not_equal_sub.items():

                begin_a, end_a, text_a = markup_list[i_from]
                begin_b, end_b, text_b = interval_list[i_to]

                length = end_a - begin_a

                if length <= 0:
                    raise NotImplementedError

                delta_begin = abs(begin_a - begin_b)
                delta_end = abs(end_a - end_b)

                sub_delta_begin_list.append(delta_begin * 1000)
                sub_delta_end_list.append(delta_end * 1000)

                sub_relative_begin_list.append(delta_begin / length)
                sub_relative_end_list.append(delta_end / length)

        # Showing computed quality metrics.

        print('Phone edit distance: {0}/{1} ({2:.2f}%), '
            '{3} insertions ({4:.2f}%), {5} deletions ({6:.2f}%), {7} substitutions ({8:.2f}%)\n'
            'Phone set precision: {9}/{10} ({11})\n'
            'Phone set recall: {12}/{13} ({14:.2f}%)'.format(
                l_state.total, len(source_list), 100.0 * l_state.total / len(source_list),
                l_state.ins_n, 100.0 * l_state.ins_n / len(source_list),
                l_state.del_n, 100.0 * l_state.del_n / len(source_list),
                l_state.sub_n, 100.0 * l_state.sub_n / len(source_list),
                match_count, len(result_list), 'inf' if len(result_list) <= 0 else
                    '{0:.2f}%'.format(100.0 * match_count / len(result_list)),
                match_count, len(source_list), 100.0 * match_count / len(source_list)))

    # Showing overall transcription quality metrics.

    print('\nOverall phone error rate: {0}/{1} ({2:.2f}%)\n'
        '  {3} insertions ({4:.2f}%), {5} deletions ({6:.2f}%), {7} substitutions ({8:.2f}%)\n\n'
        'Total phone set precision: {9}/{10} ({11:.2f}%)\n'
        'Total phone set recall: {12}/{13} ({14:.2f}%)'.format(
            edit_total, source_total, 100.0 * edit_total / source_total,
            ins_total, 100.0 * ins_total / source_total,
            del_total, 100.0 * del_total / source_total,
            sub_total, 100.0 * sub_total / source_total,
            match_total, result_total, 100.0 * match_total / result_total,
            match_total, source_total, 100.0 * match_total / source_total))

    # Computing and showing markup interval alignment statistics.

    print('\nInterval border alignment errors:')

    delta_list = delta_begin_list + delta_end_list

    print('\n  absolute, ms:'
        '\n    start and end: {0:.2f} min, {1:.2f} max, {2:.2f} median, {3:.2f} mean, {4:.2f} stdev'
        '\n    start only: {5:.2f} min, {6:.2f} max, {7:.2f} median, {8:.2f} mean, {9:.2f} stdev'
        '\n    end only: {10:.2f} min, {11:.2f} max, {12:.2f} median, {13:.2f} mean, {14:.2f} stdev'.format(
            min(delta_list), max(delta_list), numpy.median(delta_list),
            numpy.mean(delta_list), numpy.std(delta_list),
            min(delta_begin_list), max(delta_begin_list), numpy.median(delta_begin_list),
            numpy.mean(delta_begin_list), numpy.std(delta_begin_list),
            min(delta_end_list), max(delta_end_list), numpy.median(delta_end_list),
            numpy.mean(delta_end_list), numpy.std(delta_end_list)))

    relative_list = relative_begin_list + relative_end_list

    print('\n  relative:'
        '\n    start and end: {0:.2f} min, {1:.2f} max, {2:.2f} median, {3:.2f} mean, {4:.2f} stdev'
        '\n    start only: {5:.2f} min, {6:.2f} max, {7:.2f} median, {8:.2f} mean, {9:.2f} stdev'
        '\n    end only: {10:.2f} min, {11:.2f} max, {12:.2f} median, {13:.2f} mean, {14:.2f} stdev'.format(
            min(relative_list), max(relative_list), numpy.median(relative_list),
            numpy.mean(relative_list), numpy.std(relative_list),
            min(relative_begin_list), max(relative_begin_list), numpy.median(relative_begin_list),
            numpy.mean(relative_begin_list), numpy.std(relative_begin_list),
            min(relative_end_list), max(relative_end_list), numpy.median(relative_end_list),
            numpy.mean(relative_end_list), numpy.std(relative_end_list)))

    # The same, now together with intervals matched with symbol substitutions.

    print('\nIncluding matched intervals with symbol substitution:')

    total_delta_begin_list = delta_begin_list + sub_delta_begin_list
    total_delta_end_list = delta_end_list + sub_delta_end_list

    total_delta_list = total_delta_begin_list + total_delta_end_list

    print('\n  absolute, ms:'
        '\n    start and end: {0:.2f} min, {1:.2f} max, {2:.2f} median, {3:.2f} mean, {4:.2f} stdev'
        '\n    start only: {5:.2f} min, {6:.2f} max, {7:.2f} median, {8:.2f} mean, {9:.2f} stdev'
        '\n    end only: {10:.2f} min, {11:.2f} max, {12:.2f} median, {13:.2f} mean, {14:.2f} stdev'.format(
            min(total_delta_list), max(total_delta_list), numpy.median(total_delta_list),
            numpy.mean(total_delta_list), numpy.std(total_delta_list),
            min(total_delta_begin_list), max(total_delta_begin_list), numpy.median(total_delta_begin_list),
            numpy.mean(total_delta_begin_list), numpy.std(total_delta_begin_list),
            min(total_delta_end_list), max(total_delta_end_list), numpy.median(total_delta_end_list),
            numpy.mean(total_delta_end_list), numpy.std(total_delta_end_list)))

    total_relative_begin_list = relative_begin_list + sub_relative_begin_list
    total_relative_end_list = relative_end_list + sub_relative_end_list

    total_relative_list = total_relative_begin_list + total_relative_end_list

    print('\n  relative:'
        '\n    start and end: {0:.2f} min, {1:.2f} max, {2:.2f} median, {3:.2f} mean, {4:.2f} stdev'
        '\n    start only: {5:.2f} min, {6:.2f} max, {7:.2f} median, {8:.2f} mean, {9:.2f} stdev'
        '\n    end only: {10:.2f} min, {11:.2f} max, {12:.2f} median, {13:.2f} mean, {14:.2f} stdev'.format(
            min(total_relative_list), max(total_relative_list),
            numpy.median(total_relative_list),
            numpy.mean(total_relative_list), numpy.std(total_relative_list),
            min(total_relative_begin_list), max(total_relative_begin_list),
            numpy.median(total_relative_begin_list),
            numpy.mean(total_relative_begin_list), numpy.std(total_relative_begin_list),
            min(total_relative_end_list), max(total_relative_end_list),
            numpy.median(total_relative_end_list),
            numpy.mean(total_relative_end_list), numpy.std(total_relative_end_list)))

    # Plotting error distibutions, if required.

    if False:

        mean, std = numpy.mean(total_relative_list), numpy.std(total_relative_list)

        pyplot.hist(total_relative_list, 256, normed = 1, facecolor = 'green', alpha = 0.5)
        pyplot.axvline(x = mean, color = 'red', linewidth = 2)

        for i in range(1, 3 + 1):
            pyplot.axvline(x = mean + i * std, color = 'red')

        pyplot.show()

    # Showing symbol substitutions.

    print('\nAdditional symbol statistics:')

    symbol_list = []

    for symbol_from, count_dict in sorted(substitution_dict.items()):

        occurence_count = occurence_dict[symbol_from]
        sub_count = sum(count_dict.values())

        print('\n\'{0}\':'
            ' {1} occurences ({2:.2f}% of all symbols),'
            ' {3} ({4:.2f}%) were substituted.'
            '\n\n\'{0}\' substitutions:'.format(
            symbol_from, occurence_dict[symbol_from],
            100.0 * occurence_dict[symbol_from] / source_total,
            sub_count, 100.0 * sub_count / occurence_dict[symbol_from]))

        sub_list = list(sorted(count_dict.items(),
            key = lambda symbol_count: (symbol_count[1], symbol_count[0]),
            reverse = True))

        symbol_list.append((symbol_from, occurence_count, sub_count, sub_list[0]))

        for symbol_to, count in sub_list:

            print('  \'{0}\': {1} ({2:.2f}%)'.format(
                symbol_to, count, 100.0 * count / sub_count))

    # Additional symbol statistics.

    print('\nSymbols in order of occurence frequency:')

    for symbol, occurence_count, substitution_count, most_frequent in sorted(
        symbol_list, key = lambda x: x[1], reverse = True):

        print('  \'{0}\': {1} ({2:.2f}%) occurences, {3} ({4:.2f}%) were substituted'.format(symbol,
            occurence_count, 100.0 * occurence_count / source_total,
            substitution_count, 100.0 * substitution_count / occurence_count))

    print('\nSymbols in order of substitution frequency:')

    for symbol, occurence_count, substitution_count, (mf_symbol, mf_count) in sorted(
        symbol_list, key = lambda x: float(x[2]) / x[1], reverse = True):

        print('  \'{0}\': {1} ({2:.2f}%) substitutions, '
            'most {{{3}/{1}, {4:.2f}%}} into \'{5}\''.format(symbol,
            substitution_count, 100.0 * substitution_count / occurence_count,
            mf_count, 100.0 * mf_count / substitution_count, mf_symbol))

    print('\nMost frequent substitutions:')

    for symbol, occurence_count, substitution_count, (mf_symbol, mf_count) in sorted(symbol_list):

        print('  \'{0}\': \'{1}\' ({2:.2f}%)'.format(
            symbol, mf_symbol, 100.0 * mf_count / substitution_count))

    sys.stdout.write('\n')


def main(args):
    """
    Various stuff related to automatic markup recognition.
    """

command_dict = {
    'coverage': main_coverage,
    'data': main_data,
    'kaldi_data': main_kaldi_data,
    'kaldi_model': main_kaldi_model,
    'listing': main_listing,
    'markup': main_markup,
    'measure': main_measure,
    'model': main_model,
    'model_crf': main_model_crf,
    'model_hmm': main_model_hmm,
    'selection': Selection.main}


if __name__ == '__main__':

    if sys.argv[1] in command_dict:
        command_dict[sys.argv[1]](sys.argv[2:])

    else:
        main(sys.argv)

