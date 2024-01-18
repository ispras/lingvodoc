
# Standard library imports.

import base64
import bisect
import collections
import configparser
import csv
import datetime
from errno import EEXIST
from hashlib import md5
import io
import itertools
import logging
import math

import os
from os import makedirs, path

import pprint
import re
from shutil import copyfileobj
import sndhdr
import string
import subprocess
import sys
import tempfile
import time
import traceback
import types
import unicodedata

import urllib.request
import urllib.parse

import warnings
import zipfile

# External imports.

import cchardet as chardet

# So that matplotlib does not require display stuff, in particular, tkinter. See e.g. https://
# stackoverflow.com/questions/4931376/generating-matplotlib-graphs-without-a-running-x-server.
import matplotlib
matplotlib.use('Agg', warn = False)

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

from sqlalchemy import and_, create_engine, func, tuple_
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
    DictionaryPerspectiveToField,
    Entity,
    Field,
    LexicalEntry,
    PublishingEntity,
    TranslationGist,
    TranslationAtom
)

from lingvodoc.queue.celery import celery
from lingvodoc.utils import sanitize_worksheet_name
from lingvodoc.views.v2.utils import anonymous_userid, as_storage_file, message, storage_file, unimplemented


# Setting up logging.
log = logging.getLogger(__name__)


def bessel_i0_approximation(x):
    """
    Computes approximate value of the Bessel function I_0 according to formulas in Praat source code, file
    num/Num.cpp:185, function NUMbessel_i0_f, which in turn cites Abramowicz & Stegun, "Handbook of
    Mathematical Functions, With Formulas, Graphs, and Mathematical Tables", p. 378.
    """

    if x < 0:
        return bessel_i0_approximation(-x)

    # Argument is in [0, 3.75), using formula 9.8.1.

    elif x < 3.75:

        t = x / 3.75
        t2 = t * t

        return 1.0 + t * (3.5156229 + t * (3.0899424 +
            t * (1.2067492 + t * (0.2659732 + t * (0.0360768 + t * 0.0045813)))));

    # Argument is in [3.75, +infinity), using formula 9.8.2.

    else:
        t = x / 3.75

        return math.exp(x) / math.sqrt(x) * (0.39894228 + t * (0.01328592 + t * (0.00225319 +
            t * (-0.00157565 + t * (0.00916281 + t * (-0.02057706 + t * (0.02635537 + t * (-0.01647633 +
            t * 0.00392377))))))))

    raise Exception('Unimplemented.')


#: Dictionary used for memoization of Kaiser window function computation.
kaiser_window_dict = dict()


def get_kaiser_window(half_window_size):
    """
    Computes (2N + 1)-sample Kaiser window, where N is a half window size in samples.

    Employs memoization.
    """

    if half_window_size in kaiser_window_dict:
        return kaiser_window_dict[half_window_size]

    # Computing a new window, saving it for reuse, and returning it.

    pi_alpha = 2 * math.pi ** 2 + 0.5

    window_list = [
        bessel_i0_approximation(pi_alpha * math.sqrt(1 - (i / half_window_size) ** 2))
            for i in range(-half_window_size, half_window_size + 1)]

    window_sum = sum(window_list)

    kaiser_window_dict[half_window_size] = (window_list, window_sum)
    return (window_list, window_sum)


#: Dictionary used for memoization of Gaussian window function computation.
gaussian_window_dict = dict()


def get_gaussian_window(window_size):
    """
    Computes (2N + 1)-sample Gaussian window, where N is a half window size in samples.

    Employs memoization.
    """

    if window_size in gaussian_window_dict:
        return gaussian_window_dict[window_size]

    # Computing a new window, saving it for reuse, and returning it.

    middle = float(window_size + 1) / 2
    edge = math.exp(-12)
    edge_one_minus = 1.0 - edge

    window_list = [
        (math.exp(-48 * ((i - middle) / (window_size + 1)) ** 2) - edge) / edge_one_minus
            for i in range(1, window_size + 1)]

    gaussian_window_dict[window_size] = window_list
    return window_list


def burg(sample_list, coefficient_number):
    """
    Computes Linear Prediction coefficients via Burg method from a list of samples.
    """

    p = sum(sample ** 2 for sample in sample_list)
    a0 = p / len(sample_list)

    b1 = sample_list[:len(sample_list) - 1]
    b2 = sample_list[1:]

    aa = [0.0 for i in range(coefficient_number)]
    coefficient_list = [0.0 for i in range(coefficient_number)]

    for i in range(coefficient_number):

        numerator = 0.0
        denominator = 0.0

        for j in range(len(sample_list) - i - 1):
            numerator += b1[j] * b2[j]
            denominator += b1[j] ** 2 + b2[j] **2

        coefficient_list[i] = 2.0 * numerator / denominator
        a0 *= 1.0 - coefficient_list[i] ** 2

        for j in range(i):
            coefficient_list[j] = aa[j] - coefficient_list[i] * aa[i - j - 1]

        if i < coefficient_number:

            for j in range(i + 1):
                aa[j] = coefficient_list[j]

            for j in range(len(sample_list) - i - 2):
                b1[j] -= aa[i] * b2[j]
                b2[j] = b2[j + 1] - aa[i] * b1[j + 1]

    return a0, coefficient_list


def compute_formants(sample_list, nyquist_frequency):
    """
    Computes formants of an audio sample.
    """

    sample_list = [sample * weight
        for sample, weight in zip(sample_list,
            get_gaussian_window(len(sample_list)))]

    # Computing Linear Prediction coefficients via Burg method, number of coefficients is twice the
    # number of formants we want to detect (hence 2 * 5 = 10).
    #
    # These coefficients a[0], a[1], ... a[10] are coefficients of a polynomial 1 - a[1] * x -
    # a[1] * x^2 - ... - a[10] * x^10 of degree 10 defined on [-1, 1], which is a so-called
    # characteristic polynomial, see https://en.wikipedia.org/wiki/Autoregressive_model. We then find
    # the roots of this polynomial.

    a0, coefficient_list = burg(sample_list, 10)

    polynomial = numpy.polynomial.Polynomial([1.0] + [-c for c in coefficient_list])
    root_list = polynomial.roots()

    # Finding better root approximations via Newton-Raphson iteration (see https://en.wikipedia.org/
    # wiki/Newton's_method).
    #
    # NOTE: profiling shows that instead of using numpy's polynomial evaluation a la 'polynomial(
    # root_list[0])' it is better to use our own Horner's method implementation.

    polynomial_list = [-c for c in reversed(coefficient_list)] + [1.0]
    derivative_list = [c * (10 - i) for i, c in enumerate(polynomial_list)]

    def evaluate(c_list, value):
        result = 0.0

        for c in c_list:
            result = result * value + c

        return result

    better_root_list = []
    better_root_index = 0

    # Processing all roots.

    while better_root_index < len(root_list):

        previous = root_list[better_root_index]
        previous_delta = abs(evaluate(polynomial_list, previous))

        current = previous - evaluate(polynomial_list, previous) / evaluate(derivative_list, previous)
        current_delta = abs(evaluate(polynomial_list, current))

        while current_delta < previous_delta:

            previous = current
            previous_delta = current_delta

            current = previous - evaluate(polynomial_list, previous) / evaluate(derivative_list, previous)
            current_delta = abs(evaluate(polynomial_list, current))

        # If it is a complex root, the next one is just its complex conjugate.

        better_root_list.append(previous)
        better_root_index += 1

        if abs(previous.imag) > 0:

            better_root_list.append(previous.conjugate())
            better_root_index += 1

    # Moving all roots into the unit circle. If a root is outside, we replace it with reciprocal of its
    # conjugate, reflecting it about the real line and projecting it inside the unit circle. Then we
    # find formants by looking at roots above the real line.

    formant_list = []

    for root in better_root_list:

        if abs(root) > 1.0:
            root = 1.0 / root.conjugate()

        if root.imag >= 0:
            frequency = abs(math.atan2(root.imag, root.real)) * nyquist_frequency / math.pi

            if frequency >= 50 and frequency <= nyquist_frequency - 50:
                formant_list.append(frequency)

    # Returning computed formants, from lowest to highest.

    while len(formant_list) < 5:
        formant_list.append(nyquist_frequency)

    formant_list.sort()

    return formant_list


class AudioPraatLike(object):
    """
    Allows computations of sound intensity and formants using algorithms mimicking as close as possible
    corresponding algorithms of the Praat [http://www.fon.hum.uva.nl/praat] software.
    """

    def __init__(
        self,
        source_sound,
        args = None,
        vowel_range_list = None):

        self.intensity_sound = source_sound
        self.args = args
        self.vowel_range_list = vowel_range_list

        #
        # Praat's intensity window size is computed as 3.2/minimum_pitch (see http://www.fon.hum.uva.nl/
        # praat/manual/Sound__To_Intensity___.html), where standard minimum_pitch in Praat 6.0.04 in Ubuntu
        # 16.04 is set to 75 Hz, corresponding to 3.2/75 ≈ 0.04267 s.
        #
        # We set intensity window size to 0.05, corresponding to Praat's minimum pitch of 3.2/0.05 = 64 Hz.
        #
        # Intensity series time step is set to 0.8/minimum_pitch, which with minimum pitch of 64 Hz is
        # 0.8/64 = 0.0125.
        #
        # Both window size and time step are rounded down to include an whole number of samples. Praat uses
        # Kaiser window, and actual window size is twice 3.2/minimum_pitch., i.e., 6.4/minimum_pitch (see
        # Praat source code, file fon/Sound_to_Intensity.cpp:36, function Sound_to_Intensity_), rounded to
        # the odd number of samples. We use window of the size of 2N + 1 samples, where N is a half window
        # size, computed as 4 times the number of samples in the time step.
        #

        self.intensity_step_size = int(math.floor(0.0125 * self.intensity_sound.frame_rate))
        self.intensity_half_window_size = 4 * self.intensity_step_size
        self.intensity_window_size = 2 * self.intensity_half_window_size + 1

        self.intensity_step_count = int(
            math.floor((self.intensity_sound.frame_count() - 1) // self.intensity_step_size + 1))

        self.intensity_list = [None for i in range(self.intensity_step_count)]

        self.fast_track_flag = (
            args and args.use_fast_track)

        self.fast_track_plot_flag = False

        # Standard formant computation algorithm.

        if not self.fast_track_flag:

            #
            # Praat's formant window size is 0.05 seconds, and formant time step is 8 times less, i.e.
            # 0.05 / 8 = 0.00625 seconds.
            #
            # Computation of formants is performed on the sound recording resampled to twice the maximum formant
            # frequency (see http://www.fon.hum.uva.nl/praat/manual/Sound__To_Formant__burg____.html). Standard
            # maximum formant frequency is 5500 Hz, so standard resampling frequency is 11000 Hz.
            #
            # We set resampling frequency to 11025 Hz, which is a divisor of common sound recording frequencies
            # 44100 Hz and 22050 Hz; doing so allows us to minimize resampling errors when using pydub's simple
            # linear interpolation resampling.
            #

            self.formant_frame_rate = 11025

            self.formant_step_size = int(math.floor(0.00625 * self.formant_frame_rate))

            self.formant_half_window_size = 4 * self.formant_step_size
            self.formant_window_size = 2 * self.formant_half_window_size + 1

            self.formant_step_shift = 4

        # Fast Track formant computation algorithm.

        else:

            self.formant_frequency_min = 4700
            self.formant_frequency_max = 7550

            self.formant_frequency_step_n = 20

            self.dct_coef_n = 5

            step_n_m1 = (
                self.formant_frequency_step_n - 1)

            frequency_delta = (
                self.formant_frequency_max - self.formant_frequency_min)

            self.formant_frame_rate_list = []

            self.formant_step_size_list = []
            self.formant_half_window_size_list = []
            self.formant_window_size_list = []

            self.formant_step_shift_list = []
            self.formant_step_count_list = []

            # Derived parameters for each maximum formant frequency.

            for i in range(self.formant_frequency_step_n):

                formant_frame_rate = (
                    2 * int(self.formant_frequency_min + frequency_delta * i / step_n_m1))

                self.formant_frame_rate_list.append(formant_frame_rate)

                formant_step_size = (
                    int(math.floor(0.002 * formant_frame_rate)))

                formant_half_window_size = (
                    int(math.floor(0.025 * formant_frame_rate)))

                self.formant_step_size_list.append(formant_step_size)
                self.formant_half_window_size_list.append(formant_half_window_size)
                self.formant_window_size_list.append(2 * formant_half_window_size + 1)

                formant_step_shift = (
                    (formant_half_window_size + formant_step_size - 1) // formant_step_size)

                self.formant_step_shift_list.append(formant_step_shift)

        self.formant_list = None

        # Setting up formant data initialization. By default we use initialization with FFT-based resampling
        # computed via numpy.

        self.init_formant_f = self.init_formant_fft

    def get_intensity(self, step_index):
        """
        Computes intensity at the point specified by intensity time step index.
        """

        if step_index < 4 or step_index >= self.intensity_step_count - 4:
            raise ValueError('step index {0} is out of bounds [4, {1})'.format(
                step_index, self.intensity_step_count - 4))

        # Checking if we already computed required intensity value.

        if self.intensity_list[step_index] != None:
            return self.intensity_list[step_index]

        # No, we haven't, so we are going to compute it.

        window_list, window_sum = get_kaiser_window(self.intensity_half_window_size)

        sample_array = self.intensity_sound.get_array_of_samples()
        sample_sum = 0.0

        channel_count = self.intensity_sound.channels
        amplitude_limit = self.intensity_sound.max_possible_amplitude

        # We sum squared normalized amplitudes of all samples of all channels in the window.

        sample_from = (step_index - 4) * self.intensity_step_size * channel_count

        for i in range(self.intensity_window_size):
            for j in range(channel_count):
                sample = sample_array[sample_from + i * channel_count + j] / amplitude_limit
                sample_sum += sample ** 2 * window_list[i]

        # Multiplication by 2.5e9 is taken directly from Praat source code, where it is performed via
        # division by 4e-10.

        intensity_ratio = sample_sum / (channel_count * window_sum) * 2.5e9
        intensity = -300 if intensity_ratio < 1e-30 else 10 * math.log10(intensity_ratio)

        # Saving computed intensity value for reuse, and returning it.

        self.intensity_list[step_index] = intensity
        return intensity

    def get_interval_intensity(self, begin, end):
        """
        Computes mean-energy intensity, intensity maximum and intensity minimum of an interval specified by
        beginning and end in seconds.
        """

        # Due to windowed nature of intensity computation, we can't compute it for points close to the
        # beginning and the end of the recording; such points are skipped.

        factor = self.intensity_sound.frame_rate / self.intensity_step_size

        begin_step = max(4, int(math.ceil(begin * factor)))
        end_step = min(self.intensity_step_count - 5, int(math.floor(end * factor)))

        # Checking if we actually have any points.

        if end_step < begin_step:
            return 0.0, 0.0, 0.0

        # Computing intensity point values, getting minimum and maximum like in Praat, with additional
        # parabolic interpolation.

        intensity_list = [
            self.get_intensity(step_index)
            for step_index in range(begin_step, end_step + 1)]

        intensity_min = (
            min(intensity_list[0], intensity_list[-1]))

        intensity_max = (
            max(intensity_list[0], intensity_list[-1]))

        if self.args and self.args.__debug_flag__:

            intensity_list_str = (

                ', '.join(
                    f'{value:.3f}'
                    for value in intensity_list))

            log.debug(
                f'\nintensity_list ({len(intensity_list)}):\n[{intensity_list_str}]'
                f'\nintensity_min: {intensity_min:.3f}'
                f'\nintensity_max: {intensity_max:.3f}')

        for i in range(len(intensity_list) - 2):

            v1, v2, v3 = (
                intensity_list[i : i + 3])

            intensity_min = (
                min(intensity_min, v2))

            intensity_max = (
                max(intensity_max, v2))

            # Extremum of parabolic interpolation, see e.g.
            # http://www.ebyte.it/library/codesnippets/P3Interpolation.html.
            #
            # Using parabola's extremum only if it's non-degenerate and the extremum lies in the [i, i+2]
            # interval of v1, v2, v3 values.

            d1 = 0.5 * (v3 - v1)
            d2 = v1 + v3 - 2 * v2

            if (math.fabs(d2) > 0 and
                math.fabs(d1d2 := d1 / d2) < 1):

                vX = v2 - 0.5 * d1 * d1d2

                intensity_min = (
                    min(intensity_min, vX))

                intensity_max = (
                    max(intensity_max, vX))

        if self.args and self.args.__debug_flag__:

            log.debug(
                f'\nintensity_min: {intensity_min:.3f}'
                f'\nintensity_max: {intensity_max:.3f}')

        # Interval intensity as mean-energy intensity like in Praat.

        energy_sum = (

            sum(
                math.pow(10, 0.1 * intensity)
                for intensity in intensity_list))

        return (
            10 * math.log10(energy_sum / (end_step - begin_step + 1)),
            intensity_min,
            intensity_max)

    def init_formant_pydub(self):
        """
        Initializes formant computation data using pydub's simple linear resampling.
        """

        self.formant_sound = self.intensity_sound.set_frame_rate(self.formant_frame_rate)
        self.formant_frame_count = int(self.formant_sound.frame_count())

        # Getting sound time series ready for formant analysis by pre-emphasising frequencies higher
        # than 50 Hz.

        factor = math.exp(-2.0 * math.pi * 50 / self.formant_sound.frame_rate)
        sample_array = self.formant_sound.get_array_of_samples()

        channel_count = self.formant_sound.channels

        self.formant_sample_list = [
            sum(sample_array[j] for j in range(channel_count)) / channel_count]

        for i in range(1, int(self.formant_sound.frame_count())):

            # During pre-emphasis we also average all channels.

            self.formant_sample_list.append(sum(
                sample_array[i * channel_count + j] -
                factor * sample_array[(i - 1) * channel_count + j]
                    for j in range(channel_count)) / channel_count)

        # Number of formant values and formant value cache.

        self.formant_step_count = int(
            math.floor((self.formant_sound.frame_count() - 1) // self.formant_step_size + 1))

        self.formant_list = [None for i in range(self.formant_step_count)]

    def init_formant_fft(self, padding_length = None):
        """
        Initializes formant computation data using FFT-based resampling computed via numpy.
        """

        sample_array = self.intensity_sound.get_array_of_samples()
        channel_count = self.intensity_sound.channels

        frame_count = int(self.intensity_sound.frame_count())
        frame_rate = self.intensity_sound.frame_rate

        if padding_length is None:

            padding = min(1000, frame_count // 16)

        else:

            padding = (

                max(
                    min(1000, frame_count // 16),
                    int(math.floor(padding_length * frame_rate))))

        source_count = (
            frame_count + 2 * padding)

        self.padding = padding

        self.padding_length = (
            float(padding) / frame_rate)

        if not self.fast_track_flag:

            factor_rate = (
                float(self.formant_frame_rate) / frame_rate)

            resample_count = (
                int(math.floor(factor_rate * source_count)))

        # Fourier transform is linear, so we can average over channels before using FFT.

        source_list = numpy.empty(source_count)

        source_list[:padding] = 0.0
        source_list[-padding:] = 0.0

        if channel_count == 1:

            source_list[padding:-padding] = sample_array

        elif channel_count == 2:

            for i in range(frame_count):

                source_list[padding + i] = (
                    (sample_array[i * 2] + sample_array[i * 2 + 1]) / 2.0)

        else:

            # General case.

            for i in range(frame_count):

                source_list[padding + i] = (

                    sum(
                        sample_array[i * channel_count + j]
                        for j in range(channel_count))

                        / channel_count)

        # If we are using samples only from vowel intervals.

        if self.args and self.args.interval_only:

            if self.fast_track_flag:
                raise NotImplementedError

            self.formant_frame_count = resample_count

            self.formant_step_count = (

                int(math.floor(
                    (self.formant_frame_count - 1) // self.formant_step_size + 1)))

            sample_interval_list = []

            factor_step = (
                self.formant_frame_rate / self.formant_step_size)

            # Looking for boundaries of vowel-containing intervals.

            for begin, end in self.vowel_range_list:

                begin_step = (

                    max(4,
                        int(math.ceil((begin + self.padding_length) * factor_step))))

                end_step = (

                    min(
                        self.formant_step_count - 5,
                        int(math.floor((end + self.padding_length) * factor_step))))

                # Boundaries in both resampled and source sound time series.

                formant_sample_from = (
                    (begin_step - 4) * self.formant_step_size)

                formant_sample_to = (
                    (end_step - 4) * self.formant_step_size + self.formant_window_size)

                source_sample_from = (
                    int(math.floor(formant_sample_from / factor_rate)))

                source_sample_to = (
                    int(math.floor(formant_sample_to / factor_rate)))

                # Merging intervals, if required.

                if (sample_interval_list and
                    source_sample_from <= sample_interval_list[-1][7]):

                    sample_interval_list[-1][1] = end
                    sample_interval_list[-1][3] = end_step
                    sample_interval_list[-1][5] = formant_sample_to
                    sample_interval_list[-1][7] = source_sample_to

                else:

                    sample_interval_list.append([
                        begin, end,
                        begin_step, end_step,
                        formant_sample_from, formant_sample_to,
                        source_sample_from, source_sample_to])

            log.debug(
                '\nsample_interval_list:\n' +
                pprint.pformat(
                    sample_interval_list, width = 144))

            # Preparing data for formant analysis in each interval.

            self.formant_sample_list = [
                None for i in range(resample_count)]

            factor_filter = (
                math.exp(-2.0 * math.pi * 50 / self.formant_frame_rate))

            for _, _, _, _, formant_from, formant_to, source_from, source_to in sample_interval_list:

                formant_count = (
                    formant_to - formant_from)

                sample_list = (

                    numpy.fft.irfft(
                        numpy.fft.rfft(source_list[source_from : source_to]),
                        formant_count))

                # Pre-emphasizing frequencies higher than 50 Hz, see Praat source code.

                self.formant_sample_list[formant_from] = (
                    sample_list[0] * (1 - factor_filter))

                for i in range(1, formant_count):

                    self.formant_sample_list[formant_from + i] = (
                        sample_list[i] - factor_filter * sample_list[i - 1])

        # Using full length of the sound, standard formant computation algorithm.

        elif not self.fast_track_flag:

            sample_list = numpy.fft.irfft(numpy.fft.rfft(source_list), resample_count)

            # Getting sound time series ready for formant analysis by pre-emphasising frequencies higher
            # than 50 Hz, see Praat source code.

            factor_filter = (
                math.exp(-2.0 * math.pi * 50 / self.formant_frame_rate))

            formant_frame_count = len(sample_list)
            formant_sample_list = [sample_list[0]]

            for i in range(1, int(formant_frame_count)):

                formant_sample_list.append(
                    sample_list[i] - factor_filter * sample_list[i - 1])

            self.formant_sample_list = formant_sample_list

            # Number of formant values.

            self.formant_step_count = int(
                math.floor((formant_frame_count - 1) // self.formant_step_size + 1))

        # Full length of the sound, Fast Track formant computation algorithm.

        else:

            source_fft_list = (
                numpy.fft.rfft(source_list))

            self.formant_sample_list_list = []
            self.formant_list_list = []

            for i in range(self.formant_frequency_step_n):

                formant_frame_rate = self.formant_frame_rate_list[i]

                factor_rate = (
                    float(formant_frame_rate) / frame_rate)

                resample_count = (
                    int(math.floor(factor_rate * source_count)))

                sample_list = numpy.fft.irfft(source_fft_list, resample_count)   

                # Getting sound time series ready for formant analysis by pre-emphasising frequencies higher
                # than 50 Hz, see Praat source code.

                factor_filter = (
                    math.exp(-2.0 * math.pi * 50 / formant_frame_rate))

                formant_frame_count = len(sample_list)
                formant_sample_list = [sample_list[0]]

                for j in range(1, int(formant_frame_count)):

                    formant_sample_list.append(
                        sample_list[j] - factor_filter * sample_list[j - 1])

                self.formant_sample_list_list.append(formant_sample_list)

                # Number of formant values.

                formant_step_count = (

                    int(math.floor(
                        (formant_frame_count - 1) // self.formant_step_size_list[i] + 1)))

                self.formant_step_count_list.append(formant_step_count)

                self.formant_list_list.append(
                    [None for j in range(formant_step_count)])

        # Formant value time series.

        if not self.fast_track_flag:

            self.formant_list = [None for i in range(self.formant_step_count)]

        else:

            self.formant_list = []

    def get_formants(self, step_index):
        """
        Computes point formant values at the point specified by formant time step index.
        """

        # Initializing formant computation data, if required.

        if self.formant_list is None:
            self.init_formant_f()

        # Checking validity of supplied time step index.

        if (step_index < self.formant_step_shift or
            step_index >= self.formant_step_count - self.formant_step_shift):

            raise (

                ValueError(
                    'step index {} is out of bounds [{}, {})'.format(
                        step_index,
                        self.formant_step_shift,
                        self.formant_step_count - self.formant_step_shift)))

        # Checking if we already computed required formant point value.

        if self.formant_list[step_index] != None:
            return self.formant_list[step_index]

        # No, we haven't, so we are going to compute it.

        sample_from = (
            step_index * self.formant_step_size - self.formant_half_window_size)

        sample_list = [
            self.formant_sample_list[sample_from + i]
                for i in range(self.formant_window_size)]

        formant_list = (

            compute_formants(
                sample_list, self.formant_frame_rate * 0.5))

        self.formant_list[step_index] = formant_list[:3]

        return formant_list[:3]

    def get_formants_fast_track(self, ft_index, step_index):
        """
        Computes point formant values at the point specified by formant time step index for Fast Track
        formant computation.
        """

        # Initializing formant computation data, if required.

        if self.formant_list is None:
            self.init_formant_f()

        # Checking validity of supplied time step index.

        formant_step_shift = self.formant_step_shift_list[ft_index]
        formant_step_count = self.formant_step_count_list[ft_index]

        if (step_index < formant_step_shift or
            step_index >= formant_step_count - formant_step_shift):

            raise (

                ValueError(
                    'step index {} is out of bounds [{}, {})'.format(
                        step_index,
                        formant_step_shift,
                        formant_step_count - formant_step_shift)))

        # Checking if we already computed required formant point value.

        formant_list_list = (
            self.formant_list_list[ft_index])

        if formant_list_list[step_index] != None:
            return formant_list_list[step_index]

        # No, we haven't, so we are going to compute it.

        formant_step_size = self.formant_step_size_list[ft_index]

        formant_half_window_size = self.formant_half_window_size_list[ft_index]
        formant_window_size = self.formant_window_size_list[ft_index]

        formant_sample_list = self.formant_sample_list_list[ft_index]

        sample_from = (
            step_index * formant_step_size - formant_half_window_size)

        sample_list = [
            formant_sample_list[sample_from + i]
                for i in range(formant_window_size)]

        formant_list = (

            compute_formants(
                sample_list, self.formant_frame_rate_list[ft_index] * 0.5))

        formant_list_list[step_index] = formant_list[:3]

        return formant_list[:3]

    def get_interval_formants(self, begin, end):
        """
        Computes first and second formants of an interval specified by beginning and end in seconds.
        """

        # Initializing formant computation data, if required.

        if self.formant_list is None:
            self.init_formant_f()

        f1_list, f2_list, f3_list = [], [], []

        # Standard formant computation algorithm.

        if not self.fast_track_flag:

            # Due to windowed nature of formant value computation, we can't compute them for points close to
            # the beginning and the end of the recording; such points are skipped.

            factor = (
                self.formant_frame_rate / self.formant_step_size)

            begin_step = (

                max(
                    self.formant_step_shift,
                    int(math.ceil((begin + self.padding_length) * factor))))

            end_step = (

                min(
                    self.formant_step_count - 1 - self.formant_step_shift,
                    int(math.floor((end + self.padding_length) * factor))))

            # Getting point formant values.

            for step_index in range(begin_step, end_step + 1):

                f1, f2, f3 = self.get_formants(step_index)

                f1_list.append(f1)
                f2_list.append(f2)
                f3_list.append(f3)

            f1_list.sort()
            f2_list.sort()
            f3_list.sort()

        # Fast Track formant computation algorithm.

        else:

            best_index = None

            best_f_list_list = None
            best_mae = None

            for i in range(self.formant_frequency_step_n):

                formant_frame_rate = self.formant_frame_rate_list[i]

                formant_step_size = self.formant_step_size_list[i]
                formant_step_shift = self.formant_step_shift_list[i]

                formant_step_count = self.formant_step_count_list[i]

                factor = (
                    formant_frame_rate / formant_step_size)

                begin_step = (

                    max(
                        formant_step_shift,
                        int(math.ceil((begin + self.padding_length) * factor))))

                end_step = (

                    min(
                        formant_step_count - 1 - formant_step_shift,
                        int(math.floor((end + self.padding_length) * factor))))

                # Getting point formant values.

                ft_f1_list = []
                ft_f2_list = []
                ft_f3_list = []

                for step_index in range(begin_step, end_step + 1):

                    f1, f2, f3 = self.get_formants_fast_track(i, step_index)

                    ft_f1_list.append(f1)
                    ft_f2_list.append(f2)
                    ft_f3_list.append(f3)

                f_list_list = [ft_f1_list, ft_f2_list, ft_f3_list]

                # Computing linear regression on cosine predictors.

                N = len(ft_f1_list)

                cosine_list_list = [
                    [1.0 for j in range(N)]]

                for j in range(1, self.dct_coef_n + 1):

                    cosine_list_list.append([
                        math.cos((k + 0.5) * j * math.pi / N)
                        for k in range(N)])

                cosine_array = (
                    numpy.array(cosine_list_list).transpose())

                fitted_list_list = []
                mae_list = []

                for ft_list in f_list_list:

                    result = (
                        numpy.linalg.lstsq(
                            cosine_array, ft_list, rcond = None))

                    coef_array = result[0]

                    fitted_list = (

                        numpy.sum(
                            coef_array[j] * cosine_array[:,j]
                            for j in range(self.dct_coef_n + 1)))

                    fitted_list_list.append(fitted_list)

                    mae = (

                        sum(
                            abs(ft_list[j] - fitted_list[j])
                            for j in range(N))

                            / N)

                    mae_list.append(mae)

                mae_total = sum(mae_list)

                if best_mae is None or mae_total < best_mae:

                    best_index = i

                    best_f_list_list = f_list_list
                    best_mae = mae_total

                log.debug(
                    '\n{} Hz: {:.2f} + {:.2f} + {:.2f} -> {:.2f} MAE'.format(
                        int(formant_frame_rate / 2),
                        mae_list[0], mae_list[1], mae_list[2],
                        mae_total))

                # Plotting formants, if required.

                if (self.args and self.args.__debug_flag__ and
                    self.fast_track_plot_flag):

                    figure = pyplot.figure()
                    figure.set_size_inches(16, 10)

                    axes = figure.add_subplot(111)

                    x_list = [0.5 + j for j in range(N)]

                    axes.plot(x_list, ft_f1_list, 'b.')
                    axes.plot(x_list, ft_f2_list, 'g.')
                    axes.plot(x_list, ft_f3_list, 'r.')

                    axes.plot(x_list, fitted_list_list[0], 'b-x')
                    axes.plot(x_list, fitted_list_list[1], 'g-x')
                    axes.plot(x_list, fitted_list_list[2], 'r-x')

                    axes.set_title(
                        '{} Hz: {:.2f} + {:.2f} + {:.2f} -> {:.2f} MAE'.format(
                            int(formant_frame_rate / 2),
                            mae_list[0], mae_list[1], mae_list[2],
                            mae_total))

                    axes.autoscale()

                    axes.set_xlim(0, len(ft_f1_list))
                    axes.set_ylim(ymin = 0)

                    y_max = max(ft_f3_list) * 1.05

                    if y_max > axes.get_ylim()[1]:
                        axes.set_ylim(ymax = y_max)

                    pyplot.tight_layout()
                    pyplot.savefig('fast_track_plot_{:02d}.png'.format(i))

            # Using set of formants with the least MAE.

            log.debug(
                '\nbest: {} Hz, {:.2f} MAE'.format(
                    int(self.formant_frame_rate_list[best_index] / 2),
                    best_mae))

            f1_list, f2_list, f3_list = best_f_list_list

            f1_list.sort()
            f2_list.sort()
            f3_list.sort()

        # Computing interval formant values as means (without highest and lowest values, if possible).

        step_count = len(f1_list)

        f1_mean = (
            sum(f1_list) / step_count if step_count <= 2 else
            sum(f1_list[1:-1]) / (step_count - 2))

        f2_mean = (
            sum(f2_list) / step_count if step_count <= 2 else
            sum(f2_list[1:-1]) / (step_count - 2))

        f3_mean = (
            sum(f3_list) / step_count if step_count <= 2 else
            sum(f3_list[1:-1]) / (step_count - 2))

        # Computing medians of point formant values.

        half_step_count = step_count // 2

        f1_median = (
            f1_list[half_step_count] if step_count & 1 == 1 else
            (f1_list[half_step_count - 1] + f1_list[half_step_count]) / 2)

        f2_median = (
            f2_list[half_step_count] if step_count & 1 == 1 else
            (f2_list[half_step_count - 1] + f2_list[half_step_count]) / 2)

        f3_median = (
            f3_list[half_step_count] if step_count & 1 == 1 else
            (f3_list[half_step_count - 1] + f3_list[half_step_count]) / 2)

        # Trying computation on just the middle third of the interval.

        third_step_count = step_count // 3

        f1_list = (
            f1_list[third_step_count : -third_step_count] if step_count % 3 < 2 else
            f1_list[third_step_count + 1 : -third_step_count - 1])

        f2_list = (
            f2_list[third_step_count : -third_step_count] if step_count % 3 < 2 else
            f2_list[third_step_count + 1 : -third_step_count - 1])

        f3_list = (
            f3_list[third_step_count : -third_step_count] if step_count % 3 < 2 else
            f3_list[third_step_count + 1 : -third_step_count - 1])

        return [f1_mean, f2_mean, f3_mean,
            f1_median, f2_median, f3_median,
            sum(f1_list) / len(f1_list), sum(f2_list) / len(f2_list), sum(f3_list) / len(f3_list)]


def find_max_interval_praat(sound, interval_list):
    """
    Given a sound recording and a list of intervals specified by boundaries in seconds, returns index of the
    interval with the highest sound intensity, intensity of this interval, index of the longest interval and
    the length of the longest interval.

    Intensity is computed as closely as possible to the intensity computed by Praat software.
    """

    max_intensity = None
    max_intensity_index = None

    max_length = None
    max_length_index = None

    # Finding interval with highest intensity and the longest interval.

    for index, (begin_sec, end_sec, _) in enumerate(interval_list):

        intensity = (
            sound.get_interval_intensity(begin_sec, end_sec)[0])

        length = (
            end_sec - begin_sec)

        if max_intensity == None or intensity > max_intensity:

            max_intensity = intensity
            max_intensity_index = index

        if max_length == None or length > max_length:

            max_length = length
            max_length_index = index

    return (
        max_intensity_index,
        max_intensity,
        max_length_index,
        max_length)


#: Set of vowels used by computation of phonology of dictionary perspectives.
vowel_set = set('AEIOUYaeiouyÄÆÉØäæéøŒœƆƏƐƗƜƟƱɄɅɐɑɒɔɘəɛɜɞɤɨɪɯɵɶʉʊʌʏАОаоⱭⱯⱰꞫ')


#: Set of consonants, as opposed to vowels and modifiers.
consonant_set = set('bcdfhjklmnpqrstvxzðħŋǀǁǂǃɓɕɖɗɟɠɡɢɣɦɬɭɮɰɱɲɳɴɸɹɺɻɽɾʀʁʂʃʄʈʋʎʐʑʒʔʕʘʙʛʜʝʟʡʢʼˀ˔˞βθχᶑⱱ')


#: List of Unicode characters which can be used to write phonetic transcriptions.
#:
#: We have to define it through Unicode character codes because it contains combining characters, which mess
#: with syntax highlighting and probably could mess with Python source code parsing.
#:
phonetic_character_list = list(map(chr, [
    39, 40, 41, 45, 46, 58, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84,
    85, 86, 87, 88, 89, 90, 94, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112,
    113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 124, 161, 196, 198, 199, 200, 201, 202, 203, 208, 216,
    228, 230, 231, 232, 233, 234, 235, 240, 248, 258, 259, 274, 275, 282, 283, 294, 295, 330, 331, 338, 339,
    385, 390, 393, 394, 399, 400, 403, 404, 407, 412, 413, 415, 422, 425, 430, 433, 434, 439, 448, 449, 450,
    451, 516, 517, 580, 581, 592, 593, 594, 595, 596, 597, 598, 599, 600, 601, 602, 603, 604, 605, 606, 607,
    608, 609, 610, 611, 612, 613, 614, 615, 616, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627, 628, 629,
    630, 632, 633, 634, 635, 637, 638, 640, 641, 642, 643, 644, 648, 649, 650, 651, 652, 653, 654, 655, 656,
    657, 658, 660, 661, 664, 665, 667, 668, 669, 670, 671, 673, 674, 675, 676, 677, 678, 679, 680, 688, 690,
    695, 700, 704, 705, 712, 716, 720, 721, 724, 725, 726, 727, 734, 736, 737, 739, 740, 741, 742, 743, 744,
    745, 768, 769, 770, 771, 772, 774, 776, 778, 779, 780, 781, 783, 785, 792, 793, 794, 796, 797, 798, 799,
    800, 804, 805, 809, 810, 812, 814, 815, 816, 817, 820, 825, 826, 827, 828, 829, 865, 914, 920, 935, 946,
    952, 967, 1040, 1054, 1072, 1086, 7498, 7542, 7569, 7587, 7609, 7615, 7868, 7869, 8201, 8214, 8255,
    8319, 8599, 8600, 11362, 11364, 11373, 11374, 11375, 11376, 11377, 42779, 42780, 42893, 42922, 42923,
    42924, 42925, 42928, 42930]))


#: Regular expression defining acceptable phonetic transcription.
#:
#: Right now we use the simplest approach, just a sequence of acceptable symbols and whitespace. For lists
#: of phonetic symbols of various classes see https://en.wikipedia.org/wiki/International_Phonetic_Alphabet.
#:
transcription_re = re.compile(
    '[\s\\\\{0}]*'.format(''.join(phonetic_character_list)),
    re.DOTALL | re.IGNORECASE | re.VERBOSE)


#: Praat character escape sequences, extracted from Praat sources via main_praat_escape().
character_escape_list = [
    ('\\  ', 32), ('\\! ', 33), ('\\!d', 161), ('\\# ', 35), ('\\$ ', 36), ('\\% ', 37), ('\\& ', 38),
    ('\\( ', 40), ('\\) ', 41), ('\\* ', 42), ('\\+ ', 43), ('\\+-', 177), ('\\+v', 799), ('\\, ', 44),
    ('\\- ', 45), ('\\--', 8211), ('\\->', 8594), ('\\-^', 772), ('\\-h', 173), ('\\-m', 8722),
    ('\\-v', 800), ('\\. ', 46), ('\\..', 8943), ('\\.3', 8756), ('\\.c', 183), ('\\.f', 721), ('\\/ ', 47),
    ('\\/d', 8725), ('\\0 ', 48), ('\\0^', 778), ('\\0v', 805), ('\\1 ', 49), ('\\2 ', 50), ('\\3 ', 51),
    ('\\3v', 825), ('\\4 ', 52), ('\\5 ', 53), ('\\6 ', 54), ('\\7 ', 55), ('\\8 ', 56), ('\\9 ', 57),
    ('\\9+', 1506), ('\\9-', 674), ('\\9e', 661), ('\\: ', 58), ('\\:-', 247), ('\\:^', 776), ('\\:f', 720),
    ('\\:v', 804), ('\\; ', 59), ('\\< ', 60), ('\\<-', 8592), ('\\<<', 171), ('\\<=', 8656),
    ('\\<>', 8596), ('\\<_', 8804), ('\\= ', 61), ('\\=/', 8800), ('\\=3', 8801), ('\\=>', 8658),
    ('\\=~', 8773), ('\\> ', 62), ('\\>>', 187), ('\\>_', 8805), ('\\? ', 63), ('\\?+', 1488),
    ('\\?-', 673), ('\\?d', 191), ('\\?g', 660), ('\\@ ', 64), ('\\A ', 65), ('\\A;', 260), ('\\A^', 194),
    ('\\A`', 192), ('\\Ae', 198), ('\\Al', 913), ('\\Ao', 197), ('\\At', 8704), ('\\A~', 195), ('\\B ', 66),
    ('\\B+', 1489), ('\\Be', 914), ('\\C ', 67), ('\\C%', 1509), ('\\C+', 1510), ('\\C,', 199),
    ('\\C<', 268), ('\\Ci', 935), ('\\D ', 68), ('\\D+', 1491), ('\\D-', 272), ('\\D<', 270), ('\\De', 916),
    ('\\Dv', 827), ('\\E ', 69), ('\\E;', 280), ('\\E<', 282), ('\\E^', 202), ('\\E`', 200), ('\\Ep', 917),
    ('\\Er', 8707), ('\\Et', 919), ('\\F ', 70), ('\\FI', 64257), ('\\FL', 64258), ('\\Fi', 934),
    ('\\G ', 71), ('\\G+', 1490), ('\\G<', 486), ('\\G^', 667), ('\\Ga', 915), ('\\H ', 72), ('\\H+', 1492),
    ('\\I ', 73), ('\\I^', 206), ('\\I`', 204), ('\\Io', 921), ('\\J ', 74), ('\\J+', 1497), ('\\K ', 75),
    ('\\K%', 1498), ('\\K+', 1499), ('\\Ka', 922), ('\\L ', 76), ('\\L+', 1500), ('\\L/', 321),
    ('\\La', 923), ('\\Lp', 163), ('\\M ', 77), ('\\M%', 1501), ('\\M+', 1502), ('\\Mu', 924), ('\\N ', 78),
    ('\\N%', 1503), ('\\N+', 1504), ('\\N<', 327), ('\\N^', 774), ('\\Nu', 925), ('\\Nv', 810),
    ('\\N~', 209), ('\\O ', 79), ('\\O.', 664), ('\\O/', 216), ('\\O:', 336), ('\\O^', 212), ('\\O`', 210),
    ('\\Oe', 630), ('\\Om', 937), ('\\On', 927), ('\\O|', 8709), ('\\O~', 213), ('\\P ', 80),
    ('\\P%', 1507), ('\\P+', 1508), ('\\Pi', 928), ('\\Ps', 936), ('\\Q ', 81), ('\\Q+', 1511),
    ('\\R ', 82), ('\\R+', 1512), ('\\R<', 344), ('\\Ro', 929), ('\\S ', 83), ('\\S+', 1505), ('\\S<', 352),
    ('\\SS', 167), ('\\Si', 931), ('\\T ', 84), ('\\T(', 792), ('\\T)', 793), ('\\T+', 1514), ('\\T<', 356),
    ('\\TM', 8482), ('\\T^', 797), ('\\Ta', 932), ('\\Te', 920), ('\\Th', 222), ('\\Tt', 8869),
    ('\\Tv', 798), ('\\U ', 85), ('\\U:', 368), ('\\U^', 219), ('\\U`', 217), ('\\Uo', 366), ('\\Up', 933),
    ('\\Uv', 826), ('\\V ', 86), ('\\V+', 1493), ('\\Vr', 8730), ('\\W ', 87), ('\\W+', 1513), ('\\X ', 88),
    ('\\X+', 1495), ('\\Xi', 926), ('\\Y ', 89), ('\\Y+', 1496), ('\\Y=', 165), ('\\Z ', 90), ('\\Z!', 379),
    ('\\Z+', 1494), ('\\Z<', 381), ('\\Ze', 918), ('\\[ ', 91), ('\\[f', 91), ('\\] ', 93), ('\\]f', 93),
    ('\\^ ', 94), ('\\^#', 8657), ('\\^9', 705), ('\\^?', 704), ('\\^G', 7597), ('\\^H', 689),
    ('\\^M', 7514), ('\\^N', 7505), ('\\^Y', 7587), ('\\^^', 770), ('\\^f', 7584), ('\\^g', 736),
    ('\\^h', 688), ('\\^j', 690), ('\\^l', 737), ('\\^m', 7504), ('\\^n', 8319), ('\\^s', 738),
    ('\\^w', 695), ('\\^x', 739), ('\\^y', 696), ('\\^|', 8593), ('\\_ ', 95), ('\\_#', 8659),
    ('\\_u', 8255), ('\\_|', 8595), ('\\` ', 8216), ('\\`^', 768), ('\\a ', 97), ('\\a;', 261),
    ('\\a^', 226), ('\\a_', 170), ('\\a`', 224), ('\\ab', 594), ('\\ae', 230), ('\\al', 945),
    ('\\an', 8743), ('\\ao', 229), ('\\ap', 700), ('\\as', 593), ('\\at', 592), ('\\ay', 594),
    ('\\a~', 227), ('\\b ', 98), ('\\b^', 595), ('\\bc', 665), ('\\be', 946), ('\\bf', 946), ('\\bs', 92),
    ('\\bu', 8226), ('\\c ', 99), ('\\c,', 231), ('\\c/', 162), ('\\c<', 269), ('\\c=', 8834),
    ('\\cE', 1461), ('\\cc', 597), ('\\cf', 967), ('\\ci', 967), ('\\cl', 9827), ('\\cn', 794),
    ('\\co', 169), ('\\ct', 596), ('\\cu', 164), ('\\cv', 796), ('\\d ', 100), ('\\d-', 273), ('\\d.', 598),
    ('\\d<', 271), ('\\d^', 599), ('\\dd', 8706), ('\\de', 948), ('\\dg', 176), ('\\dh', 240),
    ('\\di', 9830), ('\\dq', 1468), ('\\e ', 101), ('\\e-', 600), ('\\e;', 281), ('\\e<', 283),
    ('\\e=', 8712), ('\\e^', 234), ('\\e`', 232), ('\\ef', 603), ('\\ep', 949), ('\\eq', 8660),
    ('\\er', 604), ('\\et', 951), ('\\eu', 8364), ('\\f ', 102), ('\\f.', 637), ('\\f2', 981),
    ('\\f5', 10048), ('\\fd', 402), ('\\ff', 632), ('\\fh', 638), ('\\fi', 966), ('\\g ', 103),
    ('\\g<', 487), ('\\g^', 608), ('\\ga', 947), ('\\gc', 610), ('\\gf', 611), ('\\gs', 609), ('\\h ', 104),
    ('\\h-', 295), ('\\hI', 1460), ('\\hO', 1465), ('\\h^', 614), ('\\hc', 668), ('\\he', 9829),
    ('\\hj', 615), ('\\hr', 734), ('\\hs', 650), ('\\ht', 613), ('\\i ', 105), ('\\i-', 616), ('\\i^', 238),
    ('\\i`', 236), ('\\ic', 618), ('\\id', 639), ('\\in', 8747), ('\\io', 953), ('\\ir', 645),
    ('\\j ', 106), ('\\j-', 607), ('\\j^', 644), ('\\jc', 669), ('\\k ', 107), ('\\ka', 954), ('\\kb', 606),
    ('\\l ', 108), ('\\l-', 620), ('\\l.', 621), ('\\l/', 322), ('\\la', 955), ('\\lc', 671), ('\\li', 865),
    ('\\lz', 622), ('\\l~', 619), ('\\m ', 109), ('\\mj', 625), ('\\ml', 624), ('\\mt', 623), ('\\mu', 956),
    ('\\n ', 110), ('\\n.', 627), ('\\n<', 328), ('\\nc', 628), ('\\ng', 331), ('\\ni', 8745),
    ('\\nj', 626), ('\\no', 172), ('\\nu', 957), ('\\nv', 815), ('\\n~', 241), ('\\o ', 111),
    ('\\o+', 8853), ('\\o-', 629), ('\\o/', 248), ('\\o2', 982), ('\\o:', 337), ('\\o^', 244),
    ('\\o_', 186), ('\\o`', 242), ('\\oc', 8733), ('\\oe', 339), ('\\om', 969), ('\\on', 959),
    ('\\oo', 8734), ('\\or', 8744), ('\\ox', 8855), ('\\o~', 245), ('\\p ', 112), ('\\pA', 1463),
    ('\\pf', 9758), ('\\pi', 960), ('\\ps', 968), ('\\q ', 113), ('\\qA', 1464), ('\\qU', 1467),
    ('\\r ', 114), ('\\r.', 635), ('\\r<', 345), ('\\rc', 640), ('\\re', 174), ('\\rh', 612), ('\\ri', 641),
    ('\\rl', 634), ('\\ro', 961), ('\\rt', 633), ('\\s ', 115), ('\\s.', 642), ('\\s2', 962), ('\\s<', 353),
    ('\\sE', 1462), ('\\sU', 64309), ('\\sh', 643), ('\\si', 963), ('\\sp', 9824), ('\\sr', 602),
    ('\\ss', 223), ('\\su', 8721), ('\\sw', 601), ('\\t ', 116), ('\\t.', 648), ('\\t2', 977),
    ('\\t<', 357), ('\\tS', 679), ('\\ta', 964), ('\\te', 952), ('\\tf', 952), ('\\th', 254),
    ('\\tm', 8482), ('\\ts', 678), ('\\u ', 117), ('\\u-', 649), ('\\u:', 369), ('\\u^', 251),
    ('\\u`', 249), ('\\uo', 367), ('\\up', 965), ('\\uu', 8746), ('\\v ', 118), ('\\vO', 64331),
    ('\\v^', 780), ('\\vs', 651), ('\\vt', 652), ('\\w ', 119), ('\\wt', 653), ('\\x ', 120), ('\\xi', 958),
    ('\\xx', 215), ('\\y ', 121), ('\\yc', 655), ('\\yt', 654), ('\\z ', 122), ('\\z!', 380), ('\\z.', 656),
    ('\\z<', 382), ('\\zc', 657), ('\\ze', 950), ('\\zh', 658), ('\\{ ', 123), ('\\| ', 124), ('\\|-', 450),
    ('\\|1', 448), ('\\|2', 449), ('\\|f', 124), ('\\|v', 809), ('\\||', 182), ('\\} ', 125), ('\\~ ', 126),
    ('\\~<', 820), ('\\~^', 771), ('\\~v', 816), ('\\~~', 8776)]


#: Substitutions of Praat character escape sequences.
character_escape_dict = {escape_string: chr(character_code)
    for escape_string, character_code in character_escape_list}


#: Substitutions of various Unicode symbols by Praat character escape sequences.
escape_character_dict = {chr(character_code): escape_string
    for escape_string, character_code in character_escape_list}


#: Regular expression for substitution of Praat character escape sequences, based on info in http://
#: stackoverflow.com/questions/6116978/python-replace-multiple-strings and https://gist.github.com/bgusach/
#: a967e0587d6e01e889fd1d776c5f3729.
character_escape_re = re.compile('|'.join(
    map(re.escape, sorted(character_escape_dict.keys(), key = len, reverse = True))))


#: Regular expression for substitution of various Unicode symbols by Praat character escape sequences.
escape_character_re = re.compile('|'.join(
    map(re.escape, sorted(escape_character_dict.keys(), key = len, reverse = True))))


def character_escape(string):
    """
    Substitutes Praat charater escape sequences by corresponding Unicode characters.
    """

    return character_escape_re.sub(lambda match: character_escape_dict[match.group(0)], string)


def escape_character(string):
    """
    Substitutes various Unicode characters by corresponding Praat charater escape sequences.
    """

    return escape_character_re.sub(lambda match: escape_character_dict[match.group(0)], string)


def process_textgrid(
    textgrid,
    unusual_f = None,
    no_vowel_f = None,
    no_vowel_selected_f = None,
    interval_only = False):
    """
    Processes TextGrid markup, checking for each tier if it should be analyzed.
    """

    tier_data_list = []
    vowel_flag = False
    vowel_range_list = None

    if interval_only:
        vowel_range_list = []

    for tier_number, tier_name in textgrid.get_tier_name_num():

        try:

            raw_interval_list = [(begin, end, character_escape(text))
                for begin, end, text in textgrid.get_tier(tier_number).get_all_intervals()]

        except ValueError:

            continue

        raw_interval_seq_list = [[]]

        # Splitting interval sequence on empty intervals.

        for raw_index, interval in enumerate(raw_interval_list):

            if len(interval[2].strip()) <= 0:
                if len(raw_interval_seq_list[-1]) > 0:
                    raw_interval_seq_list.append([])

            else:
                raw_interval_seq_list[-1].append((raw_index, interval))

        if len(raw_interval_seq_list[-1]) <= 0:
            del raw_interval_seq_list[-1]

        # Selecting interval sequences for analysis, checking if we have unusual markup.

        interval_seq_list = []
        interval_idx_to_raw_idx = dict()

        unusual_markup_flag = False
        unusual_markup_list = []

        for raw_interval_seq in raw_interval_seq_list:

            interval_seq_list.append([])
            interval_idx_to_raw_idx[len(interval_seq_list) - 1] = {}

            for partial_raw_index, (raw_index, interval) in enumerate(raw_interval_seq):

                interval_text = interval[2].strip()

                # Accepting interval if its text contains at least one vowel, and is short enough or
                # is a valid phonetic transcription.

                transcription_check = re.fullmatch(transcription_re, interval_text)

                if (len(interval_text) > 0 and
                    any(character in vowel_set for character in interval_text) and
                    (len(interval_text) <= 2 or transcription_check)):

                    interval_seq_list[-1].append(interval)

                    sequence_index = len(interval_seq_list) - 1
                    interval_index = len(interval_seq_list[-1]) - 1

                    interval_idx_to_raw_idx[(sequence_index, interval_index)] = raw_index
                    interval_idx_to_raw_idx[sequence_index][interval_index] = partial_raw_index

                    # If we are to limit processing to only selected intervals, we should update selected
                    # ranges.

                    if interval_only:

                        interval_range = tuple(interval[:2])

                        if len(vowel_range_list) <= 0:
                            vowel_range_list.append(interval_range)

                        else:

                            index = (

                                bisect.bisect_left(
                                    vowel_range_list, interval_range))

                            # Can we merge with preceeding?
                                
                            if (index >= 1 and
                                vowel_range_list[index - 1][1] >= interval_range[0]):

                                index -= 1

                                vowel_range_list[index] = (
                                    (vowel_range_list[index][0], interval_range[1]))

                                # Maybe we should also merge with succeeding?

                                if (index + 1 < len(vowel_range_list) and
                                    vowel_range_list[index][1] >= vowel_range_list[index + 1][0]):

                                    vowel_range_list[index] = (
                                        (vowel_range_list[index][0], vowel_range_list[index + 1][1]))

                                    vowel_range_list.pop(index + 1)

                            # Can we merge with succeeding?

                            elif (
                                index < len(vowel_range_list) and
                                vowel_range_list[index][0] <= interval_range[1]):

                                vowel_range_list[index] = (
                                    (interval_range[0], vowel_range_list[index][1]))

                            # No merge, just insert.

                            else:
                                vowel_range_list.insert(index, interval_range)

                # Noting if the interval contains unusual (i.e. non-transcription) markup.

                elif not transcription_check:

                    unusual_markup_flag = True
                    unusual_markup_list.append((raw_index, interval))

        transcription_list = [text for begin, end, text in raw_interval_list]
        transcription = ''.join(transcription_list)

        selected_list = [text
            for interval_list in interval_seq_list
                for begin, end, text in interval_list]

        selected = ''.join(selected_list)

        # If we have intervals with unusual markup, we report them.

        if unusual_markup_flag:

            if unusual_f is not None:
                unusual_f(tier_number, tier_name, transcription, dict(unusual_markup_list))

        # If the markup does not have any vowels, we note it and also report it.

        if all(character not in vowel_set for character in transcription):

            tier_data_list.append((tier_number, tier_name, 'no_vowel'))

            if no_vowel_f is not None:
                no_vowel_f(tier_number, tier_name, transcription_list)

        # It is also possible that while full transcription has vowels, intervals selected for
        # analysis do not. In that case we also note it and report it.

        elif not any(character in vowel_set for character in selected):

            tier_data_list.append((tier_number, tier_name, 'no_vowel_selected'))

            if no_vowel_selected_f is not None:
                no_vowel_selected_f(tier_number, tier_name, transcription_list, selected_list)

        # Otherwise we store tier data to be used during processing of the sound file.

        else:

            interval_tuple = (   
                raw_interval_list,
                raw_interval_seq_list,
                interval_seq_list,
                interval_idx_to_raw_idx,
                transcription)

            tier_data_list.append((
                tier_number,
                tier_name,
                interval_tuple))

            vowel_flag = True

    return (
        tier_data_list,
        vowel_flag,
        vowel_range_list)


class Tier_Result(object):
    """
    Stores results of joint analysis of a single TextGrid tier and corresponding sound intervals.
    """

    def __init__(self,
        transcription,
        total_interval_length,
        mean_interval_length,
        max_length_str,
        max_length_r_length,
        max_length_i_list,
        max_length_f_list,
        max_length_source_index,
        max_intensity_str,
        max_intensity_r_length,
        max_intensity_i_list,
        max_intensity_f_list,
        max_intensity_source_index,
        coincidence_str,
        interval_data_list,
        source_interval_list):

        self.transcription = transcription

        self.total_interval_length = total_interval_length
        self.mean_interval_length = mean_interval_length

        self.max_length_str = max_length_str
        self.max_length_r_length = max_length_r_length
        self.max_length_i_list = max_length_i_list
        self.max_length_f_list = max_length_f_list
        self.max_length_source_index = max_length_source_index

        self.max_intensity_str = max_intensity_str
        self.max_intensity_r_length = max_intensity_r_length
        self.max_intensity_i_list = max_intensity_i_list
        self.max_intensity_f_list = max_intensity_f_list
        self.max_intensity_source_index = max_intensity_source_index

        self.coincidence_str = coincidence_str

        self.interval_data_list = interval_data_list
        self.source_interval_list = source_interval_list

    def format(self):
        """
        Generates more or less human-readable representation of analysis results.
        """

        interval_result_list = [

            ([interval_str,
                '{0:.2f}%'.format(r_length * 100),
                is_max_length, is_max_intensity, source_index],
                i_list,
                f_list)

                for interval_str, r_length, i_list, f_list, is_max_length, is_max_intensity, source_index in
                    self.interval_data_list]

        return pprint.pformat(

            [[self.transcription,
                '{0:.3f}s'.format(self.total_interval_length),
                '{0:.3f}s'.format(self.mean_interval_length),

                self.max_length_str,
                self.max_length_r_length,
                self.max_intensity_str,
                self.max_intensity_r_length,
                self.coincidence_str],

                self.max_length_i_list,
                self.max_length_f_list,
                self.max_intensity_i_list,
                self.max_intensity_f_list] + interval_result_list,

            width = 192)


def before_after_text(index, interval_list, join_set = None):
    """
    Extracts any preceeding or following markup to be joined to an interval's text.
    """

    before_text, after_text = '', ''

    # Checking if we have some preceeding or following markup to join with.

    if join_set:

        if index > 0:

            before_text = ''.join(character
                for character in interval_list[index - 1][2]
                if character in join_set)

        if index < len(interval_list) - 1:

            after_text = ''.join(character
                for character in interval_list[index + 1][2]
                if character in join_set)

    return before_text, after_text


def process_sound(tier_data_list, sound):
    """
    Analyzes sound intervals corresponding to vowel-containing markup.
    """

    textgrid_result_list = []

    for tier_number, tier_name, tier_data in tier_data_list:

        if tier_data == 'no_vowel' or tier_data == 'no_vowel_selected':
            textgrid_result_list.append((tier_number, tier_name, tier_data))
            continue

        # Analyzing vowel sounds of each interval sequence.

        (source_interval_list, raw_interval_seq_list,
            interval_seq_list, interval_idx_to_raw_idx,
            transcription) = tier_data

        textgrid_result_list.append((tier_number, tier_name, []))

        for seq_index, (raw_interval_list, interval_list) in enumerate(zip(
            raw_interval_seq_list, interval_seq_list)):

            if len(interval_list) <= 0:
                continue

            # Looking in particular at longest interval and interval with highest intensity, and at all
            # intervals in general.

            (max_intensity_index, max_intensity, max_length_index, max_length) = \
                find_max_interval_praat(sound, interval_list)

            max_intensity_interval = interval_list[max_intensity_index]
            max_length_interval = interval_list[max_length_index]

            max_intensity_i_list = (
                sound.get_interval_intensity(*max_intensity_interval[:2]))

            max_length_i_list = (
                sound.get_interval_intensity(*max_length_interval[:2]))

            max_intensity_f_list = (
                sound.get_interval_formants(*max_intensity_interval[:2]))

            max_length_f_list = (
                sound.get_interval_formants(*max_length_interval[:2]))

            intensity_list = [
                sound.get_interval_intensity(begin_sec, end_sec)
                    for begin_sec, end_sec, text in interval_list]

            formant_list = [
                sound.get_interval_formants(begin_sec, end_sec)
                    for begin_sec, end_sec, text in interval_list]

            # Computing average sound interval length.

            total_interval_length = (

                sum(
                    end - begin
                    for raw_index, (begin, end, text) in raw_interval_list))

            mean_interval_length = (
                total_interval_length / len(raw_interval_list))

            # Preparing data of maximum length and maximum intensity intervals.

            max_length_source_index = interval_idx_to_raw_idx[(seq_index, max_length_index)]

            max_length_str = '{0} {1:.3f} [{2}]'.format(
                max_length_interval[2].strip(),
                max_length,
                len(''.join(text for index, (begin, end, text) in
                    raw_interval_list[:interval_idx_to_raw_idx[seq_index][max_length_index]])))

            max_intensity_source_index = interval_idx_to_raw_idx[(seq_index, max_intensity_index)]

            max_intensity_str = '{0} {1:.3f} [{2}]'.format(
                max_intensity_interval[2].strip(),
                max_intensity,
                len(''.join(text for index, (begin, end, text) in
                    raw_interval_list[:interval_idx_to_raw_idx[seq_index][max_intensity_index]])))

            # Preparing data of all other intervals.

            str_list = [

                '{0} {1:.3f} {2:.3f} [{3}]'.format(
                    text.strip(),
                    end_sec - begin_sec, intensity,
                    len(''.join(text for raw_index, (begin, end, text) in
                        raw_interval_list[:interval_idx_to_raw_idx[seq_index][index]])))

                    for index, ((intensity, _, _), (begin_sec, end_sec, text)) in
                        enumerate(zip(intensity_list, interval_list))]

            source_index_list = [
                interval_idx_to_raw_idx[(seq_index, index)]
                    for index in range(len(interval_list))]

            # Compiling results.

            interval_data_list = [

                (interval_str,
                    (end - begin) / mean_interval_length,
                    [f'{i_min:.3f}', f'{i_max:.3f}', f'{i_max - i_min:.3f}'],
                    list(map('{0:.3f}'.format, f_list)),
                    '+' if index == max_length_index else '-',
                    '+' if index == max_intensity_index else '-',
                    source_index)

                    for (
                        index,
                            (interval_str, (_, i_min, i_max), f_list, (begin, end, text), source_index)) in

                        enumerate(
                            zip(
                                str_list, intensity_list, formant_list, interval_list, source_index_list))]

            textgrid_result_list[-1][2].append(

                Tier_Result(
                    ''.join(text for index, (begin, end, text) in raw_interval_list),
                    total_interval_length,
                    mean_interval_length,
                    max_length_str,
                    max_length / mean_interval_length,
                    list(map('{0:.3f}'.format, max_length_i_list)),
                    list(map('{0:.3f}'.format, max_length_f_list)),
                    max_length_source_index,
                    max_intensity_str,
                    (max_intensity_interval[1] - max_intensity_interval[0]) / mean_interval_length,
                    list(map('{0:.3f}'.format, max_intensity_i_list)),
                    list(map('{0:.3f}'.format, max_intensity_f_list)),
                    max_intensity_source_index,
                    '+' if max_intensity_index == max_length_index else '-',
                    interval_data_list,
                    source_interval_list))

    # Returning analysis results.

    return textgrid_result_list


def process_sound_markup(
    log_str,
    sound_entity_id,
    sound_url,
    markup_entity_id,
    markup_url,
    storage,
    __debug_flag__ = False):
    """
    Extracts phonology data from a pair of sound recording and its markup, using cache in a manner
    compatible with phonological analysis.
    """

    log.debug(
        '{0}\nsound_url: {1}\nmarkup_url: {2}'.format(
        log_str, sound_url, markup_url))

    # Checking if we have already cached sound/markup analysis result.

    cache_key = 'phonology:{0}:{1}:{2}:{3}'.format(
        sound_entity_id[0], sound_entity_id[1],
        markup_entity_id[0], markup_entity_id[1])

    cache_result = caching.CACHE.get(cache_key)

    if cache_result == 'no_vowel':

        log.debug('{0} [CACHE {1}]: no vowel'.format(
            log_str, cache_key))

        return None

    # Cached exception result.

    elif (isinstance(cache_result, tuple) and
        cache_result[0] == 'exception'):

        exception, traceback_string = cache_result[1:3]

        log.debug(
            '{0} [CACHE {1}]: exception'.format(
            log_str, cache_key))

        log.debug(traceback_string)

        return None

    # We have a cached analysis result.

    elif cache_result:

        textgrid_result_list = cache_result

        log.debug(
            '{0} [CACHE {1}]:\n{2}'.format(
            log_str, cache_key,
            format_textgrid_result(
                [None], textgrid_result_list)))

    # Ok, we don't have a cached result, so we are going to perform sound/markup analysis.

    else:

        try:

            storage_f = (
                as_storage_file if __debug_flag__ else storage_file)

            sound_bytes = None

            # Getting markup, checking if we have a tier that needs to be processed.

            with storage_f(storage, markup_url) as markup_stream:
                markup_bytes = markup_stream.read()

            try:

                textgrid = pympi.Praat.TextGrid(xmax = 0)

                if __debug_flag__:

                    with open('__markup__.TextGrid', 'wb') as markup_file:
                        markup_file.write(markup_bytes)

                # Textgrid package decodes files line by line, and that means that for UTF-16 / UTF-32
                # endianness specified by the BOM at the start of the file may be lost.

                textgrid.from_file(

                    io.BytesIO(
                        markup_bytes
                            .decode(chardet.detect(markup_bytes)['encoding'])
                            .encode('utf-8')),

                    codec = 'utf-8')

            except:

                # If we failed to parse TextGrid markup, we assume that sound and markup files
                # were accidentally swapped and try again.

                sound_bytes = markup_bytes
                markup_url, sound_url = sound_url, markup_url

                with storage_f(storage, markup_url) as markup_stream:
                    markup_bytes = markup_stream.read()

                textgrid = pympi.Praat.TextGrid(xmax = 0)

                textgrid.from_file(

                    io.BytesIO(
                        markup_bytes
                            .decode(chardet.detect(markup_bytes)['encoding'])
                            .encode('utf-8')),

                    codec = 'utf-8')

            # Processing markup, getting info we need.

            tier_data_list, vowel_flag, vowel_range_list = process_textgrid(textgrid)

            log.debug(
                '{0}:\ntier_data_list:\n{1}\nvowel_flag: {2}'.format(
                log_str,
                pprint.pformat(tier_data_list, width = 144),
                vowel_flag))

            if not vowel_flag:

                log.debug('{0}: no vowel'.format(log_str))
                caching.CACHE.set(cache_key, 'no_vowel')

                return None

            # Ok, we have usable markup, and now we retrieve the sound file to analyze it.

            extension = path.splitext(
                urllib.parse.urlparse(sound_url).path)[1]

            sound = None
            with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

                if sound_bytes is None:

                    with storage_f(storage, sound_url) as sound_stream:
                        sound_bytes = sound_stream.read()

                temp_file.write(sound_bytes)
                temp_file.flush()

                sound = AudioPraatLike(pydub.AudioSegment.from_file(temp_file.name))

            # Analysing sound, showing and caching analysis results.

            textgrid_result_list = process_sound(
                tier_data_list, sound)

            log.debug(
                '{0}:\n{1}'.format(
                log_str,
                format_textgrid_result(
                    [None], textgrid_result_list)))

            caching.CACHE.set(cache_key, textgrid_result_list)

        # We have exception during sound/markup analysis, we save its info in the cache.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('{0}: exception'.format(log_str))
            log.debug(traceback_string)

            caching.CACHE.set(cache_key, ('exception', exception,
                traceback_string.replace('Traceback', 'CACHEd traceback'), log_str))

            return None

    # Ok, we have our result.

    return textgrid_result_list


def format_textgrid_result(group_list, textgrid_result_list):
    """
    A little helper function for formatting sound/markup analysis results.
    """

    return '\n'.join(
        ['groups: {0}'.format(group_list)] +
        ['tier {0} \'{1}\': {2}'.format(tier_number, tier_name,

            tier_result_list if not isinstance(tier_result_list, list) else
            tier_result_list[0].format() if len(tier_result_list) <= 1 else
            ''.join('\n{0}'.format(tier_result.format()) for tier_result in tier_result_list))

            for tier_number, tier_name, tier_result_list in textgrid_result_list])


#: Formant reference table.
formant_reference_table = [
    ('y', 235, 2100),
    ('i', 240, 2400),
    ('u', 250, 595),
    ('ɯ', 300, 1390),
    ('o', 360, 640),
    ('ø', 370, 1900),
    ('e', 390, 2300),
    ('ɤ', 460, 1310),
    ('ɔ', 500, 700),
    ('œ', 585, 1710),
    ('ʌ', 600, 1170),
    ('ɛ', 610, 1900),
    ('ɒ', 700, 760),
    ('ɑ', 750, 940),
    ('ɶ', 820, 1530),
    ('a', 850, 1610)]


def formant_reference(f1, f2):
    """
    Gets vowels which are a close enough match for given first formants according to the formant reference
    table.
    """

    vowel_list = []
    for vowel, v_f1, v_f2 in formant_reference_table:

        if (f1 >= v_f1 - 100 and f1 <= v_f1 + 100 and
            f2 >= v_f2 - 100 and f2 <= v_f2 + 100):

            vowel_list.append(vowel)

    return vowel_list


def sigma_inverse(sigma):
    """
    Inverts covariance matrix, suitably modifying it, if it's singular.
    """

    for i in range(len(sigma)):
        if numpy.isnan(sigma[i, i]):
            sigma[i, i] = 625.0

    sigma[numpy.isnan(sigma)] = 0.0

    w, v = numpy.linalg.eigh(sigma)
    w_max = max(w)

    # Checking if covariance matrix is singular (i.e., one of axes of its corresponding ellipsoid is too
    # small, i.e. corresponding eigenvalue is too small), fixing it if it is.

    singular_flag = False

    for i in range(len(w)):
        if abs(w[i]) <= 625.0:

            w[i] = max(w_max / 256, 625.0)
            singular_flag = True

    if singular_flag:

        sx = numpy.matmul(numpy.matmul(v, numpy.diag(w)), v.T)
        sigma = (sx + sx.T) / 2

    inverse = numpy.linalg.inv(sigma)

    return sigma, inverse


def chart_data(f_2d_tt_list, f_3d_tt_list):
    """
    Generates formant chart data given formant series.
    """

    f_2d_list = [f_2d for f_2d, tt in f_2d_tt_list]
    f_3d_list = [f_3d for f_3d, tt in f_3d_tt_list]

    # Computing means and standard deviation matrices.

    mean_2d = sum(f_2d_list) / len(f_2d_list)

    sigma_2d = \
        numpy.cov(numpy.array(f_2d_list).T) if len(f_2d_list) > 1 else \
        numpy.array([[625.0, 0.0], [0.0, 625.0]])

    sigma_2d, inverse_2d = sigma_inverse(sigma_2d)

    mean_3d = sum(f_3d_list) / len(f_3d_list)

    sigma_3d = \
        numpy.cov(numpy.array(f_3d_list).T) if len(f_3d_list) > 1 else \
        numpy.array([[625.0, 0.0, 0.0], [0.0, 625.0, 0.0], [0.0, 0.0, 625.0]])

    sigma_3d, inverse_3d = sigma_inverse(sigma_3d)

    # Calculation of squared Mahalanobis distance inspired by the StackOverflow answer
    # http://stackoverflow.com/q/27686240/2016856.

    distance_2d_list = []
    distance_3d_list = []

    for f_2d, tt in f_2d_tt_list:

        delta_2d = (
            f_2d - mean_2d)

        distance_2d = (
            numpy.einsum('n,nk,k->', delta_2d, inverse_2d, delta_2d))

        distance_2d_list.append(
            (distance_2d, f_2d, tt))

    for f_3d, tt in f_3d_tt_list:

        delta_3d = (
            f_3d - mean_3d)

        distance_3d = (
            numpy.einsum('n,nk,k->', delta_3d, inverse_3d, delta_3d))

        distance_3d_list.append(
            (distance_3d, f_3d, tt))

    distance_2d_list.sort(key = lambda dft: dft[0])
    distance_3d_list.sort(key = lambda dft: dft[0])

    # Trying to produce one standard deviation ellipse for F1/F2 2-vectors.

    sigma_one_two = scipy.linalg.sqrtm(sigma_2d)
    ellipse_list = []

    for i in range(64 + 1):
        phi = 2 * math.pi * i / 64

        ellipse_list.append(
            mean_2d + numpy.dot(numpy.array([math.cos(phi), math.sin(phi)]), sigma_one_two))

    # Splitting F1/F2 2-vectors into these that are close enough to the mean, and the outliers.

    filtered_2d_list = []
    outlier_2d_list = []

    for distance_squared, f_2d, tt in distance_2d_list:

        if distance_squared <= 2:
            filtered_2d_list.append((f_2d, tt))

        else:
            outlier_2d_list.append((f_2d, tt))

    if len(filtered_2d_list) < (len(distance_2d_list) + 1) // 2:

        sorted_list = [

            (f_2d, tt)
            for distance_squared, f_2d, tt in distance_2d_list]

        filtered_2d_list = (
            sorted_list[:(len(distance_2d_list) + 1) // 2])

        outlier_2d_list = (
            sorted_list[(len(distance_2d_list) + 1) // 2:])

    # The same for F1/F2/F3 3-vectors.

    filtered_3d_list = []
    outlier_3d_list = []

    for distance_squared, f_3d, tt in distance_3d_list:

        if distance_squared <= 2:
            filtered_3d_list.append((f_3d, tt))

        else:
            outlier_3d_list.append((f_3d, tt))

    if len(filtered_3d_list) < (len(distance_3d_list) + 1) // 2:

        sorted_list = [
                
            (f_3d, tt)
            for distance_squared, f_3d, tt in distance_3d_list]

        filtered_3d_list = (
            sorted_list[:(len(distance_3d_list) + 1) // 2])

        outlier_3d_list = (
            sorted_list[(len(distance_3d_list) + 1) // 2:])

    # Returning computed chart data.

    return (
        filtered_2d_list, outlier_2d_list, mean_2d, ellipse_list,
        filtered_3d_list, outlier_3d_list, mean_3d, sigma_3d, inverse_3d)


chart_color_list = [
    'black', 'blue', 'brown', 'green', 'navy', 'purple', 'red', 'orange', 'gray', 'cyan', 'lime', 'magenta',
    'silver', 'yellow']


def chart_definition_list(
    chart_data_2d_list,
    worksheet_table_2d,
    min_2d_f1,
    max_2d_f1,
    min_2d_f2,
    max_2d_f2,
    group_name_string = '',
    row_index = 0):
    """
    Compiles definitions of chart series given chart series data and where to write it out to.
    """

    column_list = list(string.ascii_uppercase) + [c1 + c2
        for c1 in string.ascii_uppercase
        for c2 in string.ascii_uppercase]

    shape_list = ['square', 'diamond', 'triangle', 'x', 'star', 'short_dash', 'long_dash', 'circle',
        'plus']

    chart_dict_list = []

    # Starting with data column headers.

    max_f_2d_list_length = (

        max(
            len(f_2d_list)
            for c, tc, v, f_2d_list, o_list, m, e_list in chart_data_2d_list))

    heading_list = []

    for c, tc, vowel, f_list, o_list, m, e_list in chart_data_2d_list:

        heading_list.extend([
            '{0} F1'.format(vowel),
            '{0} F2'.format(vowel),
            '',
            ''])

    worksheet_table_2d.write_row(
        'A{0}'.format(row_index + 1), heading_list)

    worksheet_table_2d.write_row(
        'A{0}'.format(row_index + 2), ['main part', '', '', ''] * len(chart_data_2d_list))

    # Removing outliers that outlie too much.

    f1_limit = max_2d_f1 + min_2d_f1 / 2
    f2_limit = max_2d_f2 + min_2d_f2 / 2

    for i in range(len(chart_data_2d_list)):

        chart_data_2d_list[i] = list(chart_data_2d_list[i])

        chart_data_2d_list[i][4] = (
                
            list(
                filter(
                    lambda f_2d_tt:
                        f_2d_tt[0][0] <= f1_limit and
                        f_2d_tt[0][1] <= f2_limit,
                    chart_data_2d_list[i][4])))

    max_outlier_list_length = (

        max(
            len(outlier_list)
            for c, tc, v, f_list, outlier_list, m, e_list in chart_data_2d_list))

    # Writing out chart data and compiling chart data series info.

    for index, (count, total_count, vowel,
        f_2d_tt_list, outlier_list, mean, ellipse_list) in enumerate(chart_data_2d_list):

        f_2d_list = [f_2d for f_2d, tt in f_2d_tt_list]
        tt_list = [tt for f_2d, tt in f_2d_tt_list]

        f1_list, f2_list = zip(*f_2d_list)
        xc_list, xl_list = zip(*tt_list)

        f1_outlier_list, f2_outlier_list = [], []
        xc_outlier_list, xl_outlier_list = [], []

        if outlier_list:

            f_2d_list = [f_2d for f_2d, tt in outlier_list]
            tt_list = [tt for f_2d, tt in outlier_list]

            f1_outlier_list, f2_outlier_list = zip(*f_2d_list)
            xc_outlier_list, xl_outlier_list = zip(*tt_list)

        x1_ellipse_list, x2_ellipse_list = zip(*ellipse_list)

        f1_column = column_list[index * 4]
        f2_column = column_list[index * 4 + 1]

        xc_column = column_list[index * 4 + 2]
        xl_column = column_list[index * 4 + 3]

        # Writing out formant data.

        worksheet_table_2d.write(
            f1_column + str(row_index + 3),
            '{0}/{1} ({2:.1f}%) points'.format(
                count, total_count, 100.0 * count / total_count))

        worksheet_table_2d.write_column(
            f1_column + str(row_index + 4),
            list(f1_list) +
                [''] * (max_f_2d_list_length - len(f1_list)) +
                [vowel + ' outliers', '{0}/{1} ({2:.1f}%) points'.format(
                    len(outlier_list), total_count, 100.0 * len(outlier_list) / total_count)] +
                list(f1_outlier_list) +
                [''] * (max_outlier_list_length - len(f1_outlier_list)) +
                [vowel + ' mean', mean[0], vowel + ' stdev ellipse'] +
                list(x1_ellipse_list))

        worksheet_table_2d.write_column(
            f2_column + str(row_index + 4),
            list(f2_list) +
                [''] * (max_f_2d_list_length - len(f2_list)) +
                ['', ''] + list(f2_outlier_list) +
                [''] * (max_outlier_list_length - len(f2_outlier_list)) +
                ['', mean[1], ''] + list(x2_ellipse_list))

        worksheet_table_2d.write_column(
            xc_column + str(row_index + 4),
            list(xc_list) +
                [''] * (max_f_2d_list_length - len(xc_list)) +
                ['', ''] + list(xc_outlier_list) +
                [''] * (max_outlier_list_length - len(xc_outlier_list)))

        worksheet_table_2d.write_column(
            xl_column + str(row_index + 4),
            list(xl_list) +
                [''] * (max_f_2d_list_length - len(xl_list)) +
                ['', ''] + list(xl_outlier_list) +
                [''] * (max_outlier_list_length - len(xl_outlier_list)))

        worksheet_table_2d.set_column(index * 4, index * 4 + 1, 11)
        worksheet_table_2d.set_column(index * 4 + 2, index * 4 + 3, 15)

        # Compiling and saving chart data series info.

        color = (
            chart_color_list[index % len(chart_color_list)])

        chart_dict_list.append({
            'name': vowel,
            'categories': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f2_column,
                row_index + 4,
                row_index + len(f2_list) + 3),
            'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f1_column,
                row_index + 4,
                row_index + len(f1_list) + 3),
            'marker': {
                'type': 'circle',
                'size': 5,
                'border': {'color': color},
                'fill': {'color': color}}})

        # And additional outliers data series.

        chart_dict_list.append({
            'name': vowel + ' outliers',
            'categories': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f2_column,
                row_index + max_f_2d_list_length + 6,
                row_index + max_f_2d_list_length + len(f2_outlier_list) + 5),
            'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f1_column,
                row_index + max_f_2d_list_length + 6,
                row_index + max_f_2d_list_length + len(f1_outlier_list) + 5),
            'marker': {
                'type': 'circle',
                'size': 2,
                'border': {'color': color},
                'fill': {'color': color}}})

        # Mean data point.

        shift = max_f_2d_list_length + max_outlier_list_length

        chart_dict_list.append({
            'name': vowel + ' mean',
            'categories': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f2_column,
                row_index + shift + 7,
                row_index + shift + 7),
            'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f1_column,
                row_index + shift + 7,
                row_index + shift + 7),
            'marker': {
                'type': 'x',
                'size': 12,
                'border': {'color': color},
                'fill': {'color': color}}})

        # Finally, one standard deviation ellipse data series.

        chart_dict_list.append({
            'name': vowel + ' stdev ellipse',
            'categories': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f2_column,
                row_index + shift + 9,
                row_index + shift + len(x2_ellipse_list) + 8),
            'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                group_name_string,
                f1_column,
                row_index + shift + 9,
                row_index + shift + len(x1_ellipse_list) + 8),
            'marker': {'type': 'none'},
            'line': {'color': color, 'width': 0.5},
            'smooth': True})

    # Returning compiled chart series definitions.

    return chart_dict_list, row_index + shift + len(x1_ellipse_list) + 9


def get_vowel_class(index, interval_list, keep_set = None, join_set = None):
    """
    Extracts vowel class label given vowel's interval index and markup interval info.
    """

    interval_text = ''.join(character
        for character in interval_list[index][2]
        if character in vowel_set or keep_set and character in keep_set)

    before_text, after_text = before_after_text(index, interval_list, join_set)

    return before_text + interval_text + after_text


def compile_workbook(
    args,
    source_entry_id_set,
    result_dict,
    result_group_set,
    workbook_stream,
    csv_stream = None):
    """
    Compiles analysis results into an Excel workbook, and, if required, a CSV file.
    """

    workbook = (
        xlsxwriter.Workbook(workbook_stream, {'in_memory': True}))

    format_percent = (
        workbook.add_format({'num_format': '0.00%'}))

    if csv_stream:
        csv_writer = csv.writer(csv_stream)

    group_string_dict = {group: repr(group)
        for group in result_group_set if group != None}

    group_sorted_list = sorted([(group_string, group)
        for group, group_string in group_string_dict.items() if group != None])

    group_list = [None] + list(
        map(lambda group_string_and_group: group_string_and_group[1], group_sorted_list))

    # Determining what fields our results would have.

    if args.vowel_selection:

        header_list = [

            'Longest (seconds) interval',
            'Relative length',
            'Intensity minimum (dB)', 'Intensity maximum (dB)', 'Intensity range (dB)',
            'F1 mean (Hz)', 'F2 mean (Hz)', 'F3 mean (Hz)',
            'Table reference',

            'Highest intensity (dB) interval',
            'Relative length',
            'Intensity minimum (dB)', 'Intensity maximum (dB)', 'Intensity range (dB)',
            'F1 mean (Hz)', 'F2 mean (Hz)', 'F3 mean (Hz)',
            'Table reference',

            'Coincidence']

    else:

        header_list = [

            'Interval',
            'Relative length',
            'Intensity minimum (dB)', 'Intensity maximum (dB)', 'Intensity range (dB)',
            'F1 mean (Hz)', 'F2 mean (Hz)', 'F3 mean (Hz)',
            'Table reference',
            'Longest',
            'Highest intensity']

    # Creating sets of worksheets for each result group, including the universal one.

    worksheet_dict = {}

    for group in group_list:
        group_name_string = '' if group == None else ' (group {0})'.format(group_string_dict[group])

        worksheet_results = workbook.add_worksheet(
            sanitize_worksheet_name('Results' + group_name_string))

        worksheet_results.write_row('A1', ['Transcription', 'Translation'] + header_list)

        # Formatting column widths.

        if args.vowel_selection:

            worksheet_results.set_column(0, 2, 20)
            worksheet_results.set_column(3, 3, 8, format_percent)
            worksheet_results.set_column(4, 6, 8)
            worksheet_results.set_column(7, 9, 10)
            worksheet_results.set_column(10, 10, 4)
            worksheet_results.set_column(11, 11, 20)
            worksheet_results.set_column(12, 12, 8, format_percent)
            worksheet_results.set_column(13, 15, 8)
            worksheet_results.set_column(16, 18, 10)
            worksheet_results.set_column(19, 20, 4)

        else:

            worksheet_results.set_column(0, 2, 20)
            worksheet_results.set_column(3, 3, 8, format_percent)
            worksheet_results.set_column(4, 6, 8)
            worksheet_results.set_column(7, 9, 10)
            worksheet_results.set_column(10, 12, 4)

        worksheet_dict[group] = (

            worksheet_results,

            workbook.add_worksheet(
                sanitize_worksheet_name('F-table' + group_name_string)),

            workbook.add_worksheet(
                sanitize_worksheet_name('F-chart' + group_name_string)),

            workbook.add_worksheet(
                sanitize_worksheet_name('F-table (3d)' + group_name_string)))

    # Writing out header for CSV file, if required.

    if csv_stream:

        csv_writer.writerow([
            'Lexical entry client id', 'Lexical entry object id',
            'Sound entity client id', 'Sound entity object id',
            'Markup entity client id', 'Markup entity object id',
            'Tier number', 'Tier name',
            'Transcription',
            'Translation entity client id', 'Translation entity object id',
            'Translation'] + header_list)

    row_counter_dict = {group: 2 for group in result_group_set}
    sound_counter_dict = {group: 0 for group in result_group_set}

    vowel_formant_dict = {group: collections.defaultdict(list) for group in result_group_set}
    already_set = set()

    def fill_analysis_results(entry_id):
        """
        Writes out to the Excel file resuls of formant analysis of sound/markup pairs of the specified
        lexical entry.
        """

        already_set.add(entry_id)
        result_list, text_list, link_set = result_dict[entry_id]

        text_list_str = (
            ', '.join(text[2] for text in text_list)
            if text_list else None)

        text = text_list[0] if text_list else None
        text_str = text[2] if text else ''
        text_index = 0

        def next_text():
            """
            Gets next text from the text list.
            """

            nonlocal text
            nonlocal text_str
            nonlocal text_index

            text_index += 1

            text = text_list[text_index] \
                if text_index < len(text_list) else None

            text_str = text[2] if text else ''

            return text

        # Going through all formant data extracted from sound and markup.

        for (sound_cid, sound_oid, markup_cid, markup_oid,
            textgrid_group_list, textgrid_result_list) in result_list:

            id_list = [entry_id[0], entry_id[1],
                sound_cid, sound_oid, markup_cid, markup_oid]

            for tier_number, tier_name, tier_result_list in textgrid_result_list:

                if tier_result_list == 'no_vowel' or tier_result_list == 'no_vowel_selected':
                    continue

                for tier_result in tier_result_list:

                    # Either only for longest interval and interval with highest intensity, or...

                    if args.vowel_selection:

                        i_list_a = (
                            list(map(float, tier_result.max_length_i_list)))

                        i_list_b = (
                            list(map(float, tier_result.max_intensity_i_list)))

                        f_list_a = (
                            list(map(float, tier_result.max_length_f_list[:3])))

                        f_list_b = (
                            list(map(float, tier_result.max_intensity_f_list[:3])))

                        text_a_list = tier_result.max_length_str.split()
                        text_b_list = tier_result.max_intensity_str.split()

                        vowel_a = (

                            get_vowel_class(
                                tier_result.max_length_source_index,
                                tier_result.source_interval_list,
                                args.keep_set,
                                args.join_set))

                        vowel_b = (

                            get_vowel_class(
                                tier_result.max_intensity_source_index,
                                tier_result.source_interval_list,
                                args.keep_set,
                                args.join_set))

                        # Writing out interval data and any additional texts.

                        row_list = (

                            [tier_result.transcription,
                                text_str,
                                ' '.join([vowel_a] + text_a_list[1:]),
                                round(tier_result.max_length_r_length, 4)] +

                            i_list_a +
                            f_list_a +

                            [', '.join(formant_reference(*f_list_a[:2])),
                                ' '.join([vowel_b] + text_b_list[1:]),
                                round(tier_result.max_intensity_r_length, 4)] +

                            i_list_b +
                            f_list_b +

                            [', '.join(formant_reference(*f_list_b[:2])),
                                tier_result.coincidence_str])

                        for group in textgrid_group_list:

                            worksheet_dict[group][0].write_row(
                                'A' + str(row_counter_dict[group]), row_list)

                            row_counter_dict[group] += 1

                        # Saving to CSV file, if required.

                        if csv_stream:

                            csv_writer.writerow(
                                id_list +
                                [tier_number, tier_name, tier_result.transcription] +
                                (text if text else ['', '', '']) +
                                row_list[2:])

                        next_text()

                        # Collecting vowel formant data.

                        for group in textgrid_group_list:

                            f_list_a.extend([
                                tier_result.transcription, text_list_str])

                            sound_counter_dict[group] += 1
                            vowel_formant_dict[group][vowel_a].append(f_list_a)

                        if text_b_list[2] != text_a_list[2]:
                            for group in textgrid_group_list:

                                f_list_b.extend([
                                    tier_result.transcription, text_list_str])

                                sound_counter_dict[group] += 1
                                vowel_formant_dict[group][vowel_b].append(f_list_b)

                    # ...for all intervals.

                    else:

                        for index, (interval_str, interval_r_length,
                            i_list, f_list, sign_longest, sign_highest, source_index) in (

                            enumerate(tier_result.interval_data_list)):

                            vowel = (

                                get_vowel_class(
                                    source_index,
                                    tier_result.source_interval_list,
                                    args.keep_set,
                                    args.join_set))

                            i_list = list(map(float, i_list))
                            f_list = list(map(float, f_list[:3]))

                            row_list = (

                                [tier_result.transcription,
                                    text_str,
                                    ' '.join([vowel] + interval_str.split()[1:]),
                                    round(interval_r_length, 4)] +

                                i_list +
                                f_list +

                                [', '.join(formant_reference(*f_list[:2])),
                                    sign_longest,
                                    sign_highest])

                            # Writing out interval analysis data and any additional translations, collecting
                            # vowel formant data.

                            for group in textgrid_group_list:

                                worksheet_dict[group][0].write_row(
                                    'A' + str(row_counter_dict[group]), row_list)

                                row_counter_dict[group] += 1

                                f_list.extend([
                                    tier_result.transcription, text_list_str])

                                sound_counter_dict[group] += 1
                                vowel_formant_dict[group][vowel].append(f_list)

                            if csv_stream:

                                csv_writer.writerow(
                                    id_list +
                                    [tier_number, tier_name, tier_result.transcription] +
                                    (text if text else ['', '', '']) +
                                    row_list[2:])

                            next_text()

            # Writing out any additional translations not written out during writing out of data of vowel
            # intervals of all markup tiers.

            while text:

                for group in textgrid_group_list:

                    worksheet_dict[group][0].write('B' + str(row_counter_dict[group]), text[2])
                    row_counter_dict[group] += 1

                if csv_stream:
                    csv_writer.writerow(id_list + ['', '', ''] + text)

                next_text()

    # Filling in analysis results.

    for source_entry_id in sorted(source_entry_id_set):
        fill_analysis_results(source_entry_id)

        for link_entry_id in sorted(result_dict[source_entry_id][2]):
            fill_analysis_results(link_entry_id)

    # And now we will produce 2d F1/F2 and 3d F1/F2/F3 scatter charts for all analysed and sufficiently
    # frequent vowels of all result groups.

    chart_stream_list = []

    for group in group_list:

        group_name_string = (
            '' if group == None else
            f' (group {group_string_dict[group]})')

        worksheet_table_2d, worksheet_chart, worksheet_table_3d = (
            worksheet_dict[group][1:4])

        vowel_formant_list = []

        for vowel, f_list_list_raw in sorted(vowel_formant_dict[group].items()):

            f_list_list = []
            f_tuple_set = set()

            for f_list in f_list_list_raw:

                f_tuple = tuple(f_list[:3])

                if f_tuple not in f_tuple_set:

                    f_list_list.append(f_list)
                    f_tuple_set.add(f_tuple)

            if len(f_list_list) >= args.chart_threshold:

                vowel_formant_list.append((
                    vowel,
                    list(map(lambda f_list: (numpy.array(f_list[:2]), f_list[3:]), f_list_list)),
                    list(map(lambda f_list: (numpy.array(f_list[:3]), f_list[3:]), f_list_list))))

        # Compiling data of formant value series by filtering F1/F2 2-vectors and F1/F2/F3 3-vectors by
        # Mahalonobis distance.

        chart_data_2d_list = []
        chart_data_3d_list = []

        min_2d_f1, max_2d_f1 = None, None
        min_2d_f2, max_2d_f2 = None, None

        min_3d_f1, max_3d_f1 = None, None
        min_3d_f2, max_3d_f2 = None, None
        min_3d_f3, max_3d_f3 = None, None

        for index, (vowel, f_2d_list, f_3d_list) in enumerate(vowel_formant_list):

            # Getting formant chart data.

            (filtered_2d_list, outlier_2d_list, mean_2d, ellipse_list,
                filtered_3d_list, outlier_3d_list, mean_3d, sigma_3d, inverse_3d) = (

                chart_data(f_2d_list, f_3d_list))

            chart_data_2d_list.append((
                len(filtered_2d_list), len(f_2d_list), vowel,
                filtered_2d_list, outlier_2d_list, mean_2d, ellipse_list))

            chart_data_3d_list.append((
                len(filtered_3d_list), len(f_3d_list), vowel,
                filtered_3d_list, outlier_3d_list, mean_3d, sigma_3d, inverse_3d))

            # Updating F1/F2 maximum/minimum info.

            f1_list, f2_list = (
                zip(*[f_2d for f_2d, tt in filtered_2d_list]))

            min_f1_list, max_f1_list = min(f1_list), max(f1_list)
            min_f2_list, max_f2_list = min(f2_list), max(f2_list)

            if min_2d_f1 == None or min_f1_list < min_2d_f1:
                min_2d_f1 = min_f1_list

            if max_2d_f1 == None or max_f1_list > max_2d_f1:
                max_2d_f1 = max_f1_list

            if min_2d_f2 == None or min_f2_list < min_2d_f2:
                min_2d_f2 = min_f2_list

            if max_2d_f2 == None or max_f2_list > max_2d_f2:
                max_2d_f2 = max_f2_list

            # Updating F1/F2/F3 maximum/minimum info.

            f1_list, f2_list, f3_list = (
                zip(*[f_3d for f_3d, tt in filtered_3d_list]))

            min_f1_list, max_f1_list = min(f1_list), max(f1_list)
            min_f2_list, max_f2_list = min(f2_list), max(f2_list)
            min_f3_list, max_f3_list = min(f3_list), max(f3_list)

            if min_3d_f1 == None or min_f1_list < min_3d_f1:
                min_3d_f1 = min_f1_list

            if max_3d_f1 == None or max_f1_list > max_3d_f1:
                max_3d_f1 = max_f1_list

            if min_3d_f2 == None or min_f2_list < min_3d_f2:
                min_3d_f2 = min_f2_list

            if max_3d_f2 == None or max_f2_list > max_3d_f2:
                max_3d_f2 = max_f2_list

            if min_3d_f3 == None or min_f3_list < min_3d_f3:
                min_3d_f3 = min_f3_list

            if max_3d_f3 == None or max_f3_list > max_3d_f3:
                max_3d_f3 = max_f3_list

        # Compiling info of the formant scatter chart data series, unless we actually don't have any.

        if chart_data_2d_list:

            chart_dict_list = []

            # It seems that we have to plot data in order of its size, from vowels with least number of
            # F1/F2 points to vowels with the most number of F1/F2 points, otherwise scatter chart fails to
            # generate properly.

            chart_data_2d_list.sort(
                reverse = True)

            chart_dict_list, table_2d_row_index = (
                    
                chart_definition_list(
                    chart_data_2d_list, worksheet_table_2d,
                    min_2d_f1, max_2d_f1, min_2d_f2, max_2d_f2,
                    '' if group == None else ' (group {0})'.format(group_string_dict[group])))

            # Generating formant chart, if we have any data.

            if chart_dict_list:

                chart = workbook.add_chart({'type': 'scatter'})

                chart.set_x_axis({
                    'major_gridlines': {'visible': True},
                    'name': 'F2 (Hz)',
                    'reverse': True})

                chart.set_y_axis({
                    'major_gridlines': {'visible': True},
                    'name': 'F1 (Hz)',
                    'reverse': True})

                chart.set_legend({'position': 'top'})

                for chart_dict in chart_dict_list:
                    chart.add_series(chart_dict)

                chart.set_style(11)
                chart.set_size({'width': 1024, 'height': 768})

                worksheet_chart.insert_chart('A1', chart)

        # Compiling info for F1/F2/F3 3-vector scatter charts, if we have any data.

        if chart_data_3d_list:

            column_list = (

                list(string.ascii_uppercase) +

                [c1 + c2
                    for c1 in string.ascii_uppercase
                    for c2 in string.ascii_uppercase])

            # Sorting 3d data in the same order as 2d data if required, ensuring same colors for same vowels
            # in both 2d and 3d charts.

            if chart_data_2d_list:

                vowel_order_dict = {
                    vowel: index
                    for index, (_, _, vowel, _, _, _, _) in enumerate(chart_data_2d_list)}

                chart_data_3d_list.sort(
                    key = lambda data: vowel_order_dict[data[2]])

            else:

                chart_data_3d_list.sort(
                    reverse = True)

            max_f_3d_list_length = (

                max(
                    len(f_3d_list)
                    for c, tc, v, f_3d_list, o_list, m, s_3d, i_3d in chart_data_3d_list))

            heading_list = []

            for c, tc, vowel, f_list, o_list, m, s_3d, i_3d in chart_data_3d_list:

                heading_list.extend([
                    '{0} F1'.format(vowel),
                    '{0} F2'.format(vowel),
                    '{0} F3'.format(vowel),
                    '',
                    ''])

            worksheet_table_3d.write_row(
                'A1',
                heading_list)

            worksheet_table_3d.write_row(
                'A2',
                ['main part', '', '', '', ''] * len(chart_data_3d_list))

            # Removing outliers that outlie too much.

            f1_limit = max_3d_f1 + min_3d_f1 / 2
            f2_limit = max_3d_f2 + min_3d_f2 / 2
            f3_limit = max_3d_f3 + min_3d_f3 / 2

            for i in range(len(chart_data_3d_list)):

                chart_data_3d_list[i] = (
                    list(chart_data_3d_list[i]))

                chart_data_3d_list[i][4] = (
                        
                    list(
                        filter(
                            lambda f_3d_tt:
                                f_3d_tt[0][0] <= f1_limit and
                                f_3d_tt[0][1] <= f2_limit and
                                f_3d_tt[0][2] <= f3_limit,
                            chart_data_3d_list[i][4])))

            max_outlier_list_length = (

                max(
                    len(outlier_list)
                    for c, tc, v, f_list, outlier_list, m, s_3d, i_3d in chart_data_3d_list))

            # Writing out chart data.

            for (
                index,
                (count, total_count, vowel, f_3d_tt_list, outlier_list, mean, sigma_3d, inverse_3d)) in (

                enumerate(chart_data_3d_list)):

                f_3d_list = [f_3d for f_3d, tt in f_3d_tt_list]
                tt_list = [tt for f_3d, tt in f_3d_tt_list]

                f1_list, f2_list, f3_list = zip(*f_3d_list)
                xc_list, xl_list = zip(*tt_list)

                f1_outlier_list, f2_outlier_list, f3_outlier_list = [], [], []
                xc_outlier_list, xl_outlier_list = [], []

                if outlier_list:

                    f_3d_list = [
                        f_3d for f_3d, tt in outlier_list]

                    tt_list = [
                        tt for f_3d, tt in outlier_list]

                    f1_outlier_list, f2_outlier_list, f3_outlier_list = (
                        zip(*f_3d_list))

                    xc_outlier_list, xl_outlier_list = (
                        zip(*tt_list))
                
                f1_column = column_list[index * 5]
                f2_column = column_list[index * 5 + 1]
                f3_column = column_list[index * 5 + 2]

                xc_column = column_list[index * 5 + 3]
                xl_column = column_list[index * 5 + 4]

                # Writing out formant data.

                worksheet_table_3d.write(
                    f1_column + '3',
                    '{0}/{1} ({2:.1f}%) points'.format(
                        count, total_count, 100.0 * count / total_count))

                worksheet_table_3d.write_column(
                    f1_column + '4',
                    list(f1_list) +
                        [''] * (max_f_3d_list_length - len(f1_list)) +
                        [vowel + ' outliers', '{0}/{1} ({2:.1f}%) points'.format(
                            len(outlier_list), total_count, 100.0 * len(outlier_list) / total_count)] +
                        list(f1_outlier_list) +
                        [''] * (max_outlier_list_length - len(f1_outlier_list)) +
                        [vowel + ' mean', mean[0]])

                worksheet_table_3d.write_column(
                    f2_column + '4',
                    list(f2_list) +
                        [''] * (max_f_3d_list_length - len(f2_list)) +
                        ['', ''] + list(f2_outlier_list) +
                        [''] * (max_outlier_list_length - len(f2_outlier_list)) +
                        ['', mean[1]])

                worksheet_table_3d.write_column(
                    f3_column + '4',
                    list(f3_list) +
                        [''] * (max_f_3d_list_length - len(f3_list)) +
                        ['', ''] + list(f3_outlier_list) +
                        [''] * (max_outlier_list_length - len(f3_outlier_list)) +
                        ['', mean[2]])

                worksheet_table_3d.write_column(
                    xc_column + '4',
                    list(xc_list) +
                        [''] * (max_f_3d_list_length - len(xc_list)) +
                        ['', ''] + list(xc_outlier_list) +
                        [''] * (max_outlier_list_length - len(xc_outlier_list)))

                worksheet_table_3d.write_column(
                    xl_column + '4',
                    list(xl_list) +
                        [''] * (max_f_3d_list_length - len(xl_list)) +
                        ['', ''] + list(xl_outlier_list) +
                        [''] * (max_outlier_list_length - len(xl_outlier_list)))

                worksheet_table_3d.set_column(index * 5, index * 5 + 2, 11)
                worksheet_table_3d.set_column(index * 5 + 3, index * 5 + 4, 15)

            # Creating 3d formant scatter charts.

            figure = pyplot.figure()
            figure.set_size_inches(16, 10)

            axes = figure.add_subplot(111, projection = '3d')

            axes.autoscale(tight = True)
            axes.autoscale_view(tight = True)

            axes.invert_xaxis()
            axes.view_init(elev = 30, azim = -165)

            x_min, x_max = min_3d_f1, max_3d_f1
            y_min, y_max = min_3d_f2, max_3d_f2
            z_min, z_max = min_3d_f3, max_3d_f3

            legend_plot_list = []
            legend_label_list = []

            # Graphing every vowel's data.

            for (
                index, (
                    (c, tc, vowel, f_3d_tt_list, outlier_list, mean_3d, s_3d, inverse_3d),
                    color)) in (

                enumerate(
                    zip(
                        chart_data_3d_list,
                        itertools.cycle(chart_color_list)))):

                axes.scatter(
                    [f_3d[0] for f_3d, tt in f_3d_tt_list],
                    [f_3d[1] for f_3d, tt in f_3d_tt_list],
                    [f_3d[2] for f_3d, tt in f_3d_tt_list],
                    color = color,
                    s = 4,
                    depthshade = False,
                    alpha = 0.5,
                    zorder = 1000 + index)

                if outlier_list:

                    axes.scatter(
                        [f_3d[0] for f_3d, tt in outlier_list],
                        [f_3d[1] for f_3d, tt in outlier_list],
                        [f_3d[2] for f_3d, tt in outlier_list],
                        color = color,
                        s = 1.44,
                        depthshade = False,
                        alpha = 0.5,
                        zorder = index)

                # Using 'plot' and not 'scatter' so that z-ordering would work correctly and mean
                # formant vector markers are in the forefront.

                axes.plot(
                    [mean_3d[0]],
                    [mean_3d[1]],
                    [mean_3d[2]],
                    '.',
                    marker = 'o',
                    c = color,
                    markersize = 7,
                    zorder = 4000 + index)

                plot_proxy = (

                    matplotlib.lines.Line2D(
                        [0], [0],
                        linestyle = "none",
                        c = color,
                        marker = 'o'))

                legend_plot_list.append(plot_proxy)
                legend_label_list.append(vowel)

                # Plotting one standard deviation ellipsoids for F1/F2/F3 3-vectors.
                #
                # See https://stackoverflow.com/questions/7819498/plotting-ellipsoid-with-matplotlib and
                # https://stackoverflow.com/questions/41955492/how-to-plot-efficiently-a-large-number-
                # of-3d-ellipsoids-with-matplotlib-axes3d for examples of parametrization with spherical
                # coordinates.

                phi = numpy.linspace(0, 2 * numpy.pi, 100)
                theta = numpy.linspace(0, numpy.pi, 100)

                # Getting scaling and rotation matrices from ellipsoid definition matrix Sigma^{-1}
                # by decomposing it via singular value decomposition.

                u, s, rotation = (
                    numpy.linalg.svd(inverse_3d))

                scale_x, scale_y, scale_z = (
                    1.0 / numpy.sqrt(s))

                x = scale_x * numpy.outer(numpy.cos(phi), numpy.sin(theta))
                y = scale_y * numpy.outer(numpy.sin(phi), numpy.sin(theta))
                z = scale_z * numpy.outer(numpy.ones_like(theta), numpy.cos(theta))

                for i in range(len(x)):
                    for j in range(len(x)):

                        x[i, j], y[i, j], z[i, j] = (

                            mean_3d +

                            numpy.dot(
                                (x[i, j], y[i, j], z[i, j]),
                                rotation))

                axes.plot_surface(
                    x,
                    y,
                    z,
                    rstride = 10,
                    cstride = 10,
                    color = color,
                    linewidth = 0.1,
                    alpha = 0.044,
                    shade = True,
                    zorder = 2000 + index)

                # And again, updating plot's minimums and maximums.

                ellipsoid_x_min = min(x.flat)
                ellipsoid_x_max = max(x.flat)

                if ellipsoid_x_min < x_min:
                    x_min = ellipsoid_x_min - (ellipsoid_x_max - ellipsoid_x_min) / 16

                if ellipsoid_x_max > x_max:
                    x_max = ellipsoid_x_max + (ellipsoid_x_max - ellipsoid_x_min) / 16

                ellipsoid_y_min = min(y.flat)
                ellipsoid_y_max = max(y.flat)

                if ellipsoid_y_min < y_min:
                    y_min = ellipsoid_y_min - (ellipsoid_y_max - ellipsoid_y_min) / 16

                if ellipsoid_y_max > y_max:
                    y_max = ellipsoid_y_max + (ellipsoid_y_max - ellipsoid_y_min) / 16

                ellipsoid_z_min = min(z.flat)
                ellipsoid_z_max = max(z.flat)

                if ellipsoid_z_min < z_min:
                    z_min = ellipsoid_z_min - (ellipsoid_z_max - ellipsoid_z_min) / 16

                if ellipsoid_z_max > z_max:
                    z_max = ellipsoid_z_max + (ellipsoid_z_max - ellipsoid_z_min) / 16

            # And now plotting projections of mean F1/F2/F3 vectors, with vertial projection lines, and
            # outlines of standard deviation ellipsoids.
            #
            # Separate cycle due to need for establishing a Z coordinate lower bound.

            z_min_current, z_max_current = axes.get_zlim3d()
            z_level = z_min_current - (z_max - z_min_current) / 4

            for (
                index, (
                    (c, tc, vowel, f_3d_tt_list, outlier_list, mean_3d, sigma_3d, i_3d),
                    color)) in (

                enumerate(
                    zip(
                        chart_data_3d_list,
                        itertools.cycle(chart_color_list)))):

                axes.scatter(
                    mean_3d[0],
                    mean_3d[1],
                    z_level,
                    c = color,
                    s = 36,
                    marker = 'x',
                    zorder = 5000 + index)

                axes.plot(
                    [mean_3d[0], mean_3d[0]],
                    [mean_3d[1], mean_3d[1]],
                    [mean_3d[2], z_level],
                    '--',
                    color = color,
                    zorder = 3000 + index)

                # Projection of an ellipsoid is an ellipse, for info on computation of ellipsoid
                # projections see https://tcg.mae.cornell.edu/pubs/Pope_FDA_08.pdf.

                projection = numpy.identity(3)
                projection[2, 2] = 0

                mean_3d_p = (

                    numpy.dot(
                        projection,
                        mean_3d)

                        [:2])

                transform = (

                    numpy.dot(
                        projection,
                        scipy.linalg.sqrtm(sigma_3d))

                        [:2, :2])

                phi = numpy.linspace(0, 2 * numpy.pi, 64)

                x = numpy.cos(phi)
                y = numpy.sin(phi)

                for i in range(len(x)):

                    x[i], y[i] = (

                        mean_3d_p +

                        numpy.dot(
                            (x[i], y[i]),
                            transform))

                axes.plot(
                    x, y,
                    zs = z_level,
                    zdir = 'z',
                    color = color,
                    linewidth = 0.25,
                    zorder = 6000 + index)

            # Minimizing whitespace. Please remember that x-axis is inverted.

            axes.set_xlim(x_max, x_min)
            axes.set_ylim(y_min, y_max)
            axes.set_zlim(z_level, z_max)

            # Additional newlines for adjusting label positions, see https://stackoverflow.com/a/
            # 5526717/2016856.

            axes.set_xlabel('\nF1 (Hz)')
            axes.set_ylabel('\nF2 (Hz)')
            axes.set_zlabel('\nF3 (Hz)')

            # Legend with manually selected font appropriate for various phonetic Unicode characters.

            legend = (

                axes.legend(
                    legend_plot_list,
                    legend_label_list,
                    markerscale = 1.25,
                    numpoints = 1))

            pyplot.setp(
                legend.texts,
                family = 'Gentium')

            pyplot.tight_layout()

            figure.subplots_adjust(
                left = 0,
                right = 1,
                bottom = 0,
                top = 1)

            # Rendering charts to memory as PNG images.

            chart_stream = io.BytesIO()

            pyplot.savefig(
                chart_stream,
                format = 'png')

            chart_stream_list.append(
                (chart_stream, group_name_string))

    # Finishing workbook compilation, returning some result counts.

    workbook.close()

    entity_counter_dict = {
        group: row_counter - 2
        for group, row_counter in row_counter_dict.items()}

    return (
        entity_counter_dict,
        sound_counter_dict,
        chart_stream_list)


class Phonology_Parameters(object):
    """
    Stores phonology computation parameters.
    """

    def parse_keep_join_list(self, keep_list, join_list):
        """
        Checks if we are given a list of characters specified by their code points to keep in the vowel
        interval markup, and a list of characters to join into the vowel markup from adjacent intervals.
        """

        if isinstance(keep_list, str):
            keep_list = keep_list.split(',')

        if isinstance(join_list, str):
            join_list = join_list.split(',')

        if keep_list:

           keep_list = [
                (chr(codepoint) if isinstance(codepoint, int) else chr(int(codepoint_str, base = 0)))
                for codepoint in keep_list]

        if join_list:

           join_list = [
                (chr(codepoint) if isinstance(codepoint, int) else chr(int(codepoint_str, base = 0)))
                for codepoint in join_list]

        self.keep_list = keep_list
        self.join_list = join_list

        self.keep_set = set(keep_list) if keep_list else set()
        self.join_set = set(join_list) if join_list else set()

    @staticmethod
    def from_request(request):
        """
        Creates new phonology parameters object, extracts parameters from HTTP request.
        """

        parameters = Phonology_Parameters()
        parameters.get_from_request(request)

        return parameters

    def get_from_request(self, request):
        """
        Extracts phonology parameters from HTTP request.
        """

        # Getting request parameters either from URL parameters...

        if 'url_parameters' in request.params:

            self.perspective_cid = int(request.params.get('perspective_client_id'))
            self.perspective_oid = int(request.params.get('perspective_object_id'))

            self.group_by_description = 'group_by_description' in request.params

            self.maybe_translation_field = None
            self.only_first_translation = 'only_first_translation' in request.params

            self.use_automatic_markup = 'use_automatic_markup' in request.params
            self.vowel_selection = 'vowel_selection' in request.params

            self.maybe_tier_list = None
            self.maybe_tier_set = None

            self.parse_keep_join_list(
                request.params.get('keep_list'), request.params.get('join_list'))

            self.chart_threshold = (int(request.params['chart_threshold'])
                if 'chart_threshold' in request.params else 8)

            self.generate_csv = 'generate_csv' in request.params

            # Getting info of link fields and linked perspectives.

            self.link_field_list = []

            for field_str, perspective_list_str in map(
                lambda field_perspective_list_str: field_perspective_list_str.split(':'),
                request.params['link_field_list'].split(';')
                    if 'link_field_list' in request.params else []):

                field_id = tuple(map(int, field_str.split(',')))

                perspective_id_list = [
                    tuple(map(int, perspective_str.split(',')))
                    for perspective_str in perspective_list_str.split('|')]
                    
                self.link_field_list.append((field_id, perspective_id_list))

            self.link_perspective_list = []

            for perspective_str, field_str in map(
                lambda perspective_field_str: perspective_field_str.split(':'),
                request.params['link_perspective_list'].split(';')
                    if 'link_perspective_list' in request.params else []):

                perspective_id = tuple(map(int, perspective_str.split(',')))
                field_id = tuple(map(int, field_str.split(',')))

                self.link_perspective_list.append((perspective_id, field_id))

            self.link_field_dict = dict(self.link_field_list)
            self.link_perspective_dict = dict(self.link_perspective_list)

            self.use_fast_track = 'use_fast_track' in request.params

            self.no_cache = 'no_cache' in request.params
            self.interval_only = 'interval_only' in request.params

            self.synchronous = 'synchronous' in request.params

        # ...or from JSON data.

        else:
            request_json = request.json

            self.perspective_cid = request_json.get('perspective_client_id')
            self.perspective_oid = request_json.get('perspective_object_id')

            self.group_by_description = request_json.get('group_by_description')

            self.maybe_translation_field = request_json.get('maybe_translation_field')
            self.only_first_translation = request_json.get('only_first_translation')

            self.use_automatic_markup = request_json.get('use_automatic_markup')
            self.vowel_selection = request_json.get('vowel_selection')

            self.maybe_tier_list = request_json.get('maybe_tier_list')
            self.maybe_tier_set = set(self.maybe_tier_list) if self.maybe_tier_list else None

            self.parse_keep_join_list(
                request_json.get('keep_list'), request_json.get('join_list'))

            self.chart_threshold = request_json.get('chart_threshold', 8)
            self.generate_csv = request_json.get('generate_csv')

            # Getting info of link fields and linked perspectives.

            self.link_field_list = request_json.get('link_field_list', [])
            self.link_perspective_list = request_json.get('link_perspective_list', [])

            self.link_field_dict = {
                tuple(field_id): list(map(tuple, perspective_id_list))
                    for field_id, perspective_id_list in self.link_field_list}

            self.link_perspective_dict = {
                tuple(perspective_id): tuple(field_id)
                    for perspective_id, field_id in self.link_perspective_list}

            self.use_fast_track = request_json.get('use_fast_track')

            self.no_cache = request_json.get('no_cache')
            self.interval_only = request_json.get('interval_only')

            self.synchronous = request_json.get('synchronous')

        # Checking if we have limits on number of computed results.

        parameter_dict = \
            request.params if 'url_parameters' in request.params else request_json
        '''
        self.limit = (None if 'limit' not in parameter_dict else
            int(parameter_dict.get('limit')))
        '''
        self.limit = 100

        self.limit_exception = (None if 'limit_exception' not in parameter_dict else
            int(parameter_dict.get('limit_exception')))

        self.limit_no_vowel = (None if 'limit_no_vowel' not in parameter_dict else
            int(parameter_dict.get('limit_no_vowel')))

        self.limit_result = (None if 'limit_result' not in parameter_dict else
            int(parameter_dict.get('limit_result')))

        # Getting perspective and perspective's dictionary names.

        self.get_pd_names(int(request.cookies.get('locale_id') or 2))

    def get_pd_names(self, locale_id):
        """
        Queries names of phonology perspective and its dictionary.
        """

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = self.perspective_cid, object_id = self.perspective_oid).first()

        perspective_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = perspective.translation_gist_client_id,
            object_id = perspective.translation_gist_object_id).first()

        dictionary = DBSession.query(Dictionary).filter_by(
            client_id = perspective.parent_client_id,
            object_id = perspective.parent_object_id).first()

        dictionary_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = dictionary.translation_gist_client_id,
            object_id = dictionary.translation_gist_object_id).first()

        self.dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        self.perspective_name = perspective_translation_gist.get_translation(locale_id)

    @staticmethod
    def from_graphql(args):
        """
        Creates new phonology parameters object, extracts parameters from GraphQL phonology mutation
        arguments.
        """

        parameters = Phonology_Parameters()
        parameters.get_from_graphql(args)

        return parameters

    def get_from_graphql(self, args):
        """
        Extracts phonology parameters from GraphQL phonology mutation arguments.
        """

        self.perspective_cid, self.perspective_oid = args['perspective_id']

        self.group_by_description = args['group_by_description']

        self.maybe_translation_field = args.get('maybe_translation_field')
        self.only_first_translation = args['only_first_translation']

        self.use_automatic_markup = args.get('use_automatic_markup', False)
        self.vowel_selection = args['vowel_selection']

        self.maybe_tier_list = args.get('maybe_tier_list')
        self.maybe_tier_set = set(self.maybe_tier_list) if self.maybe_tier_list else None

        self.parse_keep_join_list(
            args.get('keep_list'), args.get('join_list'))

        self.chart_threshold = args.get('chart_threshold', 8)
        self.generate_csv = args.get('generate_csv', False)

        # Getting info of link fields and linked perspectives.

        self.link_field_list = args.get('link_field_list', [])
        self.link_perspective_list = args.get('link_perspective_list', [])

        self.link_field_dict = {
            tuple(field_id): list(map(tuple, perspective_id_list))
                for field_id, perspective_id_list in self.link_field_list}

        self.link_perspective_dict = {
            tuple(perspective_id): tuple(field_id)
                for perspective_id, field_id in self.link_perspective_list}

        self.use_fast_track = args.get('use_fast_track')

        self.synchronous = args.get('synchronous')

        self.limit = 100 #args.get('limit')
        self.limit_exception = args.get('limit_exception')
        self.limit_no_vowel = args.get('limit_no_vowel')
        self.limit_result = args.get('limit_result')

        self.no_cache = args.get('no_cache')
        self.interval_only = args.get('interval_only')


@view_config(route_name = 'phonology', renderer = 'json')
def phonology(request):
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
        use_automatic_markup
        vowel_selection
    """

    task_status = None

    try:

        args = (
            Phonology_Parameters.from_request(request))

        args.__debug_flag__ = False

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

        # Phonology task status setup.

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        task_status = TaskStatus(user_id, 'Phonology compilation',
            '{0}: {1}'.format(args.dictionary_name, args.perspective_name), 4)

        # Performing either synchronous or asynchronous phonology compilation.

        request.response.status = HTTPOk.code

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

        request.response.status = HTTPInternalServerError.code

        if task_status is not None:
            task_status.set(4, 100, 'Finished (ERROR), external error')

        return {'error': 'external error'}


def std_phonology(args, task_key, cache_kwargs, storage, sqlalchemy_url):
    """
    Synchronous phonology compilation, useful for debugging.
    """

    task_status = TaskStatus.get_from_cache(task_key)

    try:
        return perform_phonology(args, task_status, storage)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(4, 100, 'Finished (ERROR), external error')

        return {'error': 'external error'}


@celery.task
def async_phonology(args, task_key, cache_kwargs, storage, sqlalchemy_url):
    """
    Asynchronous phonology compilation.
    """

    # This is a no-op with current settings, we use it to enable logging inside celery tasks, because
    # somehow this does it, and otherwise we couldn't set it up.

    logging.debug('async_phonology')

    # Ok, and now we go on with task execution.

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)
    initialize_cache(cache_kwargs)

    task_status = TaskStatus.get_from_cache(task_key)

    with manager:

        try:
            return perform_phonology(args, task_status, storage)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('phonology: exception')
            log.debug(traceback_string)

            if task_status is not None:
                task_status.set(4, 100, 'Finished (ERROR), external error')

            return {'error': 'external error'}


def analyze_sound_markup(
    args,
    task_status,
    storage,
    result_filter,
    state,
    complete_already,
    complete_range,
    index,
    row,
    row_str,
    text_list,
    fails_stream):
    """
    Performs phonological analysis of a single sound/markup pair.
    """

    markup_url = row.Markup.content
    sound_url = row.Sound.content
    err_msg = ""
    warn_msg = ""

    cache_key = (

        'phonology:{}:{}:{}:{}{}'.format(
            row.Sound.client_id, row.Sound.object_id,
            row.Markup.client_id, row.Markup.object_id,
            '+ft' if args and args.use_fast_track else ''))

    # Processing grouping, if required.

    group_list = [None]

    if args.group_by_description and 'blob_description' in row.Markup.additional_metadata:
        group_list.append(row.Markup.additional_metadata['blob_description'])

        log.debug(message('\n  blob description: {0}/{1}'.format(
            row.Markup.additional_metadata['blob_description'],
            row.Sound.additional_metadata.get('blob_description'))))

    # Checking if we have cached result for this pair of sound/markup.
    #
    # NOTE: We reference CACHE indirectly, as caching.CACHE, so that when we are inside a celery task
    # and CACHE is re-initialized, we would get newly initialized CACHE, and not the value which was
    # imported ealier.

    if not args.no_cache:

        cache_result = caching.CACHE.get(cache_key)

        try:
            if cache_result == 'no_vowel':

                log.debug('{0} [CACHE {1}]: no vowels\n{2}\n{3}\n{4}'.format(
                    row_str, cache_key, markup_url, sound_url, text_list))

                state.no_vowel_counter += 1

                task_status.set(2, 1 + int(math.floor(
                    complete_already + complete_range * (index + 1) / state.total_count)),
                    'Analyzing sound and markup')

                return (
                    args.limit_no_vowel and state.no_vowel_counter >= args.limit_no_vowel or
                    args.limit and index + 1 >= args.limit), None

            # If we have cached exception, we do the same as with absence of vowels, show its info and
            # continue.

            elif isinstance(cache_result, tuple) and cache_result[0] == 'warning':
                msg = cache_result[1]

                fails_stream.write(f"\nWARNING: {msg}"
                   f"{cache_key} (sound:markup ids)\n"
                   f"sound_url: {sound_url}\n"
                   f"markup_url: {markup_url}\n"
                   f"-----\n")

                task_status.set(2, 1 + int(math.floor(
                    complete_already + complete_range * (index + 1) / state.total_count)),
                    'Analyzing sound and markup')

                return False, None

            elif isinstance(cache_result, tuple) and cache_result[0] == 'exception':
                exception, traceback_string, msg = cache_result[1:4]

                log.debug(
                    '{0} [CACHE {1}]: exception\n{2}\n{3}\n{4}'.format(
                    row_str, cache_key, markup_url, sound_url, text_list))

                log.debug(
                    '\n' + traceback_string)

                fails_stream.write(f"\nERROR: {msg}"
                   f"{cache_key} (sound:markup ids)\n"
                   f"sound_url: {sound_url}\n"
                   f"markup_url: {markup_url}\n\n"
                   f"{traceback_string}\n"
                   f"-----\n")

                state.exception_counter += 1

                task_status.set(2, 1 + int(math.floor(
                    complete_already + complete_range * (index + 1) / state.total_count)),
                    'Analyzing sound and markup')

                return (
                    args.limit_exception and state.exception_counter >= args.limit_exception or
                    args.limit and index + 1 >= args.limit), None

            # If we actually have the result, we use it and continue.

            elif cache_result:

                textgrid_result_list = cache_result

                filtered_result_list = \
                    result_filter(textgrid_result_list) \
                        if result_filter else textgrid_result_list

                log.debug(
                    '{0} [CACHE {1}]:\n{2}\n{3}\n{4}\n{5}'.format(
                    row_str, cache_key, markup_url, sound_url, text_list,
                    format_textgrid_result(group_list, textgrid_result_list)))

                if result_filter and args.maybe_tier_set:

                    log.debug('filtered result:\n{0}'.format(
                        format_textgrid_result(group_list, filtered_result_list)))

                # Ok, another result, updating progress status, stopping earlier, if required.

                task_status.set(2, 1 + int(math.floor(
                    complete_already + complete_range * (index + 1) / state.total_count)),
                    'Analyzing sound and markup')

                return False, (group_list, filtered_result_list)

        # If we have an exception while processing cache results, we stop and terminate with error.

        except:
            return False, 'cache_error'

    try:

        storage_f = (
            as_storage_file if args.__debug_flag__ else storage_file)

        # Getting markup, checking for each tier if it needs to be processed.

        with storage_f(storage, markup_url) as markup_stream:
            markup_bytes = markup_stream.read()

        try:
            textgrid = pympi.Praat.TextGrid(xmax = 0)

            if args.__debug_flag__:

                with open('__markup__.TextGrid', 'wb') as markup_file:
                    markup_file.write(markup_bytes)

            # Textgrid package decodes files line by line, and that means that for UTF-16 / UTF-32
            # endianness specified by the BOM at the start of the file may be lost.

            textgrid.from_file(

                io.BytesIO(
                    markup_bytes
                        .decode(chardet.detect(markup_bytes)['encoding'])
                        .encode('utf-8')),

                codec = 'utf-8')

        except:

            try:
                # If we failed to parse TextGrid markup, we assume that sound and markup files were
                # accidentally swapped and try again.

                markup_url, sound_url = sound_url, markup_url

                with storage_f(storage, markup_url) as markup_stream:
                    markup_bytes = markup_stream.read()

                textgrid = pympi.Praat.TextGrid(xmax = 0)

                textgrid.from_file(

                    io.BytesIO(
                        markup_bytes
                            .decode(chardet.detect(markup_bytes)['encoding'])
                            .encode('utf-8')),

                    codec = 'utf-8')

                # Parsed sound as markup and markup as sound and succeeded.
                warn_msg += "Sound-markup swap occurred.\n"

            except Exception as e:

                err_msg += "Sound-markup swap failed.\n"
                raise e

        # Some helper functions.

        def unusual_f(tier_number, tier_name, transcription, unusual_markup_dict):

            nonlocal warn_msg

            log.debug(
                '{0}: tier {1} \'{2}\' has interval(s) with unusual transcription text: '
                '{3} / {4}'.format(
                row_str, tier_number, tier_name, transcription, unusual_markup_dict))

            warn_msg += (f"Tier {tier_number} '{tier_name}' has interval(s) with unusual transcription text: "
                         f"{transcription} / {unusual_markup_dict}\n")

        def no_vowel_f(tier_number, tier_name, transcription_list):

            log.debug(
                '{0}: tier {1} \'{2}\' doesn\'t have any vowel markup: {3}'.format(
                row_str, tier_number, tier_name, transcription_list))

        def no_vowel_selected_f(tier_number, tier_name, transcription_list, selected_list):

            log.debug(
                '{0}: tier {1} \'{2}\' intervals to be processed don\'t have any vowel markup: '
                'markup {3}, selected {4}'.format(
                row_str, tier_number, tier_name, transcription_list, selected_list))

        tier_data_list, vowel_flag, vowel_range_list = (

            process_textgrid(
                textgrid,
                unusual_f,
                no_vowel_f,
                no_vowel_selected_f,
                args.interval_only))

        if warn_msg:
            fails_stream.write(f"\nWARNING: {warn_msg}"
                               f"{cache_key} (sound:markup ids)\n"
                               f"sound_url: {sound_url}\n"
                               f"markup_url: {markup_url}\n"
                               f"-----\n")
            caching.CACHE.set(cache_key, ('warning', warn_msg))

        # If there are no tiers with vowel markup, we skip this sound-markup pair altogether.

        if not vowel_flag:

            caching.CACHE.set(cache_key, 'no_vowel')
            state.no_vowel_counter += 1

            task_status.set(2, 1 + int(math.floor(
                complete_already + complete_range * (index + 1) / state.total_count)),
                'Analyzing sound and markup')

            return (
                args.limit_no_vowel and state.no_vowel_counter >= args.limit_no_vowel or
                args.limit and index + 1 >= args.limit), None

        if args.interval_only:

            log.debug(
                '\nvowel_range_list:\n' +
                pprint.pformat(vowel_range_list, width = 108))

        # Otherwise we retrieve the sound file and analyze each vowel-containing markup.
        # Partially inspired by source code at scripts/convert_five_tiers.py:307.

        extension = path.splitext(
            urllib.parse.urlparse(sound_url).path)[1]

        sound = None
        with tempfile.NamedTemporaryFile(suffix = extension) as temp_file:

            with storage_f(storage, sound_url) as sound_stream:
                temp_file.write(sound_stream.read())
                temp_file.flush()

            sound = (

                AudioPraatLike(
                    pydub.AudioSegment.from_file(temp_file.name),
                    args,
                    vowel_range_list if args.interval_only else None))

        textgrid_result_list = (
            process_sound(tier_data_list, sound))

        caching.CACHE.set(cache_key, textgrid_result_list)

        # Showing analysis results.

        filtered_result_list = \
            result_filter(textgrid_result_list) \
                if result_filter else textgrid_result_list

        log.debug(
            '{0}:\n{1}\n{2}\n{3}\n{4}'.format(
            row_str, markup_url, sound_url, text_list,
            format_textgrid_result(group_list, textgrid_result_list)))

        if result_filter and args.maybe_tier_set:

            log.debug('filtered result:\n{0}'.format(
                format_textgrid_result(group_list, filtered_result_list)))

        # Updating progress status, returning analysis results.

        task_status.set(2, 1 + int(math.floor(
            complete_already + complete_range * (index + 1) / state.total_count)),
            'Analyzing sound and markup')

        return False, (group_list, filtered_result_list)

    except Exception as exception:

        #
        # NOTE
        #
        # Exceptional situations encountered so far:
        #
        #   1. TextGrid file actually contains sound, and wav file actually contains textgrid
        #     markup.
        #
        #     Perspective 330/4, LexicalEntry 330/7, sound-Entity 330/2328, markup-Entity 330/6934
        #
        #   2. Markup for one of the intervals contains a newline "\n", and pympi fails to parse it.
        #     Praat parses such files without problems.
        #
        #     Perspective 330/4, LexicalEntry 330/20, sound-Entity 330/6297, markup-Entity 330/6967
        #

        log.debug(
            '{0}: exception\n{1}\n{2}\n{3}'.format(
            row_str, markup_url, sound_url, text_list))

        # if we encountered an exception, we show its info and remember not to try offending
        # sound/markup pair again.

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug(traceback_string)

        err_msg += "Sound-markup analysis general exception.\n"
        fails_stream.write(f"\nERROR: {err_msg}"
                           f"{cache_key} (sound:markup ids)\n"
                           f"sound_url: {sound_url}\n"
                           f"markup_url: {markup_url}\n\n"
                           f"{traceback_string}\n"
                           f"-----\n")

        caching.CACHE.set(cache_key, ('exception', exception,
            traceback_string.replace('Traceback', 'CACHEd traceback'), err_msg))

        state.exception_counter += 1

        task_status.set(2, 1 + int(math.floor(
            complete_already + complete_range * (index + 1) / state.total_count)),
            'Analyzing sound and markup')

        return (
            args.limit_exception and state.exception_counter >= args.limit_exception or
            args.limit and index + 1 >= args.limit), None


def perform_phonology(args, task_status, storage):
    """
    Performs phonology compilation.
    """

    fails_stream = io.StringIO()

    log.debug('phonology {}/{}:'
        '\n  dictionary_name: \'{}\'\n  perspective_name: \'{}\''
        '\n  group_by_description: {}'
        '\n  maybe_translation_field: {}\n  only_first_translation: {}'
        '\n  use_automatic_markup: {}\n  vowel_selection: {}'
        '\n  maybe_tier_set: {}'
        '\n  keep_set: {}\n  join_set: {}'
        '\n  chart_threshold: {}'
        '\n  generate_csv: {}'
        '\n  link_field_dict: {}'
        '\n  link_perspective_dict: {}'
        '\n  use_fast_track: {}'
        '\n  limit: {}\n  limit_exception: {}'
        '\n  limit_no_vowel: {}\n  limit_result: {}'.format(
        args.perspective_cid, args.perspective_oid,
        args.dictionary_name, args.perspective_name,
        args.group_by_description,
        args.maybe_translation_field, args.only_first_translation,
        args.use_automatic_markup, args.vowel_selection,
        args.maybe_tier_set,
        args.keep_set, args.join_set,
        args.chart_threshold,
        args.generate_csv,
        args.link_field_dict,
        args.link_perspective_dict,
        args.use_fast_track,
        args.limit, args.limit_exception,
        args.limit_no_vowel, args.limit_result))

    time_begin = time.time()

    task_status.set(1, 0, 'Preparing')

    # Setting up result filteting based on allowed tiers, if required.

    if args.maybe_tier_set:

        def result_filter(textgrid_result_list):

            return [(tier_number, tier_name, tier_data)
                for tier_number, tier_name, tier_data in textgrid_result_list
                    if tier_name in args.maybe_tier_set]

    else:

        def result_filter(textgrid_result_list):
            return textgrid_result_list

    # If we have no explicitly specified text field, we try to find one ourselves.
    # For SQLAlchemy regular expression conditionals see https://stackoverflow.com/a/34989788/2016856.

    if not args.maybe_translation_field:

        field_data = DBSession.query(
            DictionaryPerspectiveToField, Field, TranslationAtom).filter(
                DictionaryPerspectiveToField.parent_client_id == args.perspective_cid,
                DictionaryPerspectiveToField.parent_object_id == args.perspective_oid,
                DictionaryPerspectiveToField.marked_for_deletion == False,
                Field.client_id == DictionaryPerspectiveToField.field_client_id,
                Field.object_id == DictionaryPerspectiveToField.field_object_id,
                Field.marked_for_deletion == False,
                TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                TranslationAtom.parent_object_id == Field.translation_gist_object_id,
                TranslationAtom.locale_id == 2,
                TranslationAtom.content.op('~*')('.*translation.*'),
                TranslationAtom.marked_for_deletion == False).order_by(
                    Field.client_id, Field.object_id).first()

    # Otherwise we get info of the specified field.

    else:
        field_client_id, field_object_id = args.maybe_translation_field

        field_data = DBSession.query(
            Field, TranslationAtom).filter(
                Field.client_id == field_client_id,
                Field.object_id == field_object_id,
                TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                TranslationAtom.parent_object_id == Field.translation_gist_object_id,
                TranslationAtom.locale_id == 2,
                TranslationAtom.marked_for_deletion == False).first()

    text_field = field_data.Field if field_data else None

    log.debug('text field: ' +
        ('None' if not field_data else '{0}/{1} \'{2}\''.format(
            text_field.client_id, text_field.object_id,
            field_data.TranslationAtom.content)))

    # Preparing to get sound/markup data.

    Markup = aliased(Entity, name = 'Markup')
    Sound = aliased(Entity, name = 'Sound')
    Text = aliased(Entity, name = 'Text')

    PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
    PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')
    PublishingText = aliased(PublishingEntity, name = 'PublishingText')

    data_query = DBSession.query(
        LexicalEntry, Markup, Sound).filter(
            LexicalEntry.parent_client_id == args.perspective_cid,
            LexicalEntry.parent_object_id == args.perspective_oid,
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

    # Getting text field data, if required.

    if text_field:

        data_query = (data_query

            .outerjoin(Text, and_(
                Text.parent_client_id == LexicalEntry.client_id,
                Text.parent_object_id == LexicalEntry.object_id,
                Text.field_client_id == text_field.client_id,
                Text.field_object_id == text_field.object_id,
                Text.marked_for_deletion == False))

            .outerjoin(PublishingText, and_(
                PublishingText.client_id == Text.client_id,
                PublishingText.object_id == Text.object_id,
                PublishingText.published == True,
                PublishingText.accepted == True))

            .add_columns(func.jsonb_agg(func.jsonb_build_array(
                Text.client_id, Text.object_id, Text.content)))

            .group_by(LexicalEntry, Markup, Sound))

    # Before everything else we should count how many sound/markup pairs we are to process.

    total_count = data_query.count()
    task_status.set(2, 1, 'Analyzing sound and markup')

    log.debug('phonology {0}/{1}: {2} sound/markup pairs'.format(
        args.perspective_cid, args.perspective_oid, total_count))

    # We get lexical entries of the perspective with markup'ed sounds, and possibly with accompaning texts,
    # and process these lexical entries in batches.
    #
    # In batches because just in case, it seems that perspectives rarely have more then several hundred
    # such lexical entries, but we are being cautious.

    state = types.SimpleNamespace(
        total_count = total_count,
        exception_counter = 0,
        no_vowel_counter = 0)

    # Results are grouped by lexical entries, each lexical entry has a list of markup analysis results,
    # possibly a list of associated text values (by default, translations of this lexical entry), and
    # a set of ids of linked lexical entries.
    #
    # Ids of lexical entries of the source perspective are also recorded separately.

    source_entry_id_set = set()

    result_dict = collections.defaultdict(
        lambda: [[], None, set()])

    result_group_set = set()

    # Skipping automatic markup, if required.

    for index, row in enumerate(row
        for row in data_query.yield_per(100)
        if args.use_automatic_markup or 'amr' not in row.Markup.additional_metadata):

        text_list = ([] if not text_field else
            [text for text in row[3] if text])

        if args.only_first_translation:
            text_list = text_list[:1]

        # Performing phonological analysis of this sound/markup pair.

        row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}{7})'.format(
            index,
            row.LexicalEntry.client_id, row.LexicalEntry.object_id,
            row.Sound.client_id, row.Sound.object_id,
            row.Markup.client_id, row.Markup.object_id,
            '' if 'amr' not in row.Markup.additional_metadata else
                ' [auto/{0}]'.format(row.Markup.additional_metadata['amr']))

        break_flag, result = (

            analyze_sound_markup(
                args, task_status, storage,
                result_filter,
                state, 0.0, 99.0 / (1 + len(args.link_field_dict)),
                index, row, row_str,
                text_list,
                fails_stream))

        # If we had cache processing error, we terminate.

        if result == 'cache_error':

            task_status.set(4, 100,
                'Finished (ERROR), cache processing error')

            return {
                'error': 'cache processing error',
                'exception_counter': state.exception_counter,
                'no_vowel_counter': state.no_vowel_counter,
                'result_counter': len(result_list)}

        # Otherwise we process sound/markup analysis results, if we have them.

        elif result:

            entry_id = (row.LexicalEntry.client_id, row.LexicalEntry.object_id)
            group_list, filtered_result_list = result

            source_entry_id_set.add(entry_id)

            result_dict[entry_id][0].append((
                row.Sound.client_id, row.Sound.object_id,
                row.Markup.client_id, row.Markup.object_id,
                group_list, filtered_result_list))

            if result_dict[entry_id][1] is None:
                result_dict[entry_id][1] = text_list

            result_group_set.update(group_list)

            # Stopping earlier, if required.

            if (args.limit_result and len(result_dict) >= args.limit_result or
                args.limit and index + 1 >= args.limit):
                break

        # Stopping iteration over sound/markup pairs early, if required.

        if break_flag:
            break

    log.debug(
        'phonology {}/{}: {} result{}, {} no vowels, {} exceptions, {:.3f}s elapsed time'.format(
            args.perspective_cid,
            args.perspective_oid,
            len(result_dict),
            '' if len(result_dict) == 1 else 's',
            state.no_vowel_counter,
            state.exception_counter,
            time.time() - time_begin))

    # We also process data linked through specified link fields, if we have any.

    perspective_field_dict = {}

    # Query for lexical entries of the source perspective with sound/markup data.

    source_entry_query = DBSession.query(
        LexicalEntry,
        func.count(Markup.client_id),
        func.count(Sound.client_id)).filter(
            LexicalEntry.parent_client_id == args.perspective_cid,
            LexicalEntry.parent_object_id == args.perspective_oid,
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
            PublishingSound.accepted == True).group_by(
                LexicalEntry.client_id, LexicalEntry.object_id).subquery()

    for field_index, (field_id, perspective_id_list) in \
        enumerate(args.link_field_dict.items()):

        # Query for link entities of the specified link field of the specified perspective.

        link_entity_query = DBSession.query(
            LexicalEntry.client_id.label('entry_client_id'),
            LexicalEntry.object_id.label('entry_object_id'),
            Entity).filter(
                LexicalEntry.parent_client_id == args.perspective_cid,
                LexicalEntry.parent_object_id == args.perspective_oid,
                LexicalEntry.marked_for_deletion == False,
                Entity.parent_client_id == LexicalEntry.client_id,
                Entity.parent_object_id == LexicalEntry.object_id,
                Entity.field_client_id == field_id[0],
                Entity.field_object_id == field_id[1],
                Entity.marked_for_deletion == False,
                PublishingEntity.client_id == Entity.client_id,
                PublishingEntity.object_id == Entity.object_id,
                PublishingEntity.published == True,
                PublishingEntity.accepted == True).subquery()

        for perspective_index, perspective_id in \
            enumerate(perspective_id_list):

            # Query for linked sound/markup entities in the linked perspective.

            data_query = DBSession.query(
                LexicalEntry,
                Markup,
                Sound,
                source_entry_query.c.client_id.label('source_client_id'),
                source_entry_query.c.object_id.label('source_object_id'),
                link_entity_query.c.client_id.label('link_client_id'),
                link_entity_query.c.object_id.label('link_object_id')).filter(
                    source_entry_query.c.client_id == link_entity_query.c.entry_client_id,
                    source_entry_query.c.object_id == link_entity_query.c.entry_object_id,
                    link_entity_query.c.link_client_id == LexicalEntry.client_id,
                    link_entity_query.c.link_object_id == LexicalEntry.object_id,
                    LexicalEntry.parent_client_id == perspective_id[0],
                    LexicalEntry.parent_object_id == perspective_id[1],
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

            # Checking if we have a text field for this perspective.

            if perspective_id in perspective_field_dict:
                text_field = perspective_field_dict[perspective_id]

            else:

                # Ok, we don't yet have a text field, but maybe we have an identifier to find the field by?
                
                if perspective_id in args.link_perspective_dict:
                    text_field_id = args.link_perspective_dict[perspective_id]

                    text_field_data = DBSession.query(
                        Field, TranslationAtom).filter(
                            Field.client_id == text_field_id[0],
                            Field.object_id == text_field_id[1],
                            TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                            TranslationAtom.parent_object_id == Field.translation_gist_object_id,
                            TranslationAtom.locale_id == 2,
                            TranslationAtom.marked_for_deletion == False).first()

                # Otherwise we just try to find anything suitable.

                else:

                    text_field_data = DBSession.query(
                        DictionaryPerspectiveToField, Field, TranslationAtom).filter(
                            DictionaryPerspectiveToField.parent_client_id == perspective_id[0],
                            DictionaryPerspectiveToField.parent_object_id == perspective_id[1],
                            DictionaryPerspectiveToField.marked_for_deletion == False,
                            Field.client_id == DictionaryPerspectiveToField.field_client_id,
                            Field.object_id == DictionaryPerspectiveToField.field_object_id,
                            Field.marked_for_deletion == False,
                            TranslationAtom.parent_client_id == Field.translation_gist_client_id,
                            TranslationAtom.parent_object_id == Field.translation_gist_object_id,
                            TranslationAtom.locale_id == 2,
                            TranslationAtom.content.op('~*')('.*translation.*'),
                            TranslationAtom.marked_for_deletion == False).order_by(
                                Field.client_id, Field.object_id).first()

                # Showing and saving text field info.

                text_field = text_field_data.Field if text_field_data else None
                perspective_field_dict[perspective_id] = text_field

                log.debug(
                    'perspective {0}/{1} text field: '.format(*perspective_id) +
                    ('None' if not text_field_data else '{0}/{1} \'{2}\''.format(
                        text_field.client_id, text_field.object_id,
                        text_field_data.TranslationAtom.content)))

            # Getting text field data, if we have a suitable text field.

            if text_field:

                data_query = (data_query

                    .outerjoin(Text, and_(
                        Text.parent_client_id == LexicalEntry.client_id,
                        Text.parent_object_id == LexicalEntry.object_id,
                        Text.field_client_id == text_field.client_id,
                        Text.field_object_id == text_field.object_id,
                        Text.marked_for_deletion == False))

                    .outerjoin(PublishingText, and_(
                        PublishingText.client_id == Text.client_id,
                        PublishingText.object_id == Text.object_id,
                        PublishingText.published == True,
                        PublishingText.accepted == True))

                    .add_columns(func.jsonb_agg(func.jsonb_build_array(
                        Text.client_id, Text.object_id, Text.content)))

                    .group_by(
                        LexicalEntry,
                        Markup,
                        Sound,
                        source_entry_query.c.client_id,
                        source_entry_query.c.object_id,
                        link_entity_query.c.client_id,
                        link_entity_query.c.object_id))

            # Checking how many sound/markup pairs we are to process.

            link_perspective_count = data_query.count()
            perspective_result_count = 0

            log.debug(
                'phonology {0}/{1}, link field {2}/{3}, perspective {4}/{5}: {6} sound/markup pairs'.format(
                    args.perspective_cid, args.perspective_oid,
                    field_id[0], field_id[1],
                    perspective_id[0], perspective_id[1],
                    link_perspective_count))

            state.total_count = link_perspective_count
            state.exception_counter = 0
            state.no_vowel_counter = 0

            # Skipping automatic markup, if required.

            for index, row in enumerate(row
                for row in data_query.yield_per(100)
                if args.use_automatic_markup or 'amr' not in row.Markup.additional_metadata):

                text_list = ([] if not text_field else
                    [text for text in row[7] if text])

                if args.only_first_translation:
                    text_list = text_list[:1]

                # Performing phonological analysis of this sound/markup pair.

                row_str = (
                    'link field {0}/{1}, perspective {2}/{3}: {4}\n'
                    'source-Entry {5}/{6}, link-Entity {7}/{8}, target-Entry {9}/{10}, '
                    'sound-Entity {11}/{12}, markup-Entity {13}/{14}{15}'.format(
                        field_id[0], field_id[1],
                        perspective_id[0], perspective_id[1], index,
                        row.source_client_id, row.source_object_id,
                        row.link_client_id, row.link_object_id,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Markup.client_id, row.Markup.object_id,
                        '' if 'amr' not in row.Markup.additional_metadata else
                            ' [auto/{0}]'.format(row.Markup.additional_metadata['amr'])))

                field_complete_step = 99.0 / (1 + len(args.link_field_dict))
                perspective_complete_step = field_complete_step / len(perspective_id_list)

                break_flag, result = analyze_sound_markup(
                    args, task_status, storage,
                    None, state,
                    field_complete_step * (field_index + 1) +
                        perspective_complete_step * perspective_index,
                    perspective_complete_step,
                    index, row, row_str,
                    text_list,
                    fails_stream)

                # If we had cache processing error, we terminate.

                if result == 'cache_error':

                    task_status.set(4, 100,
                        'Finished (ERROR), cache processing error')

                    return {
                        'error': 'cache processing error',
                        'exception_counter': state.exception_counter,
                        'no_vowel_counter': state.no_vowel_counter,
                        'result_counter': perspective_result_count}

                # Otherwise we process sound/markup analysis results, if we have them.

                elif result:

                    source_id = (row.source_client_id, row.source_object_id)
                    entry_id = (row.LexicalEntry.client_id, row.LexicalEntry.object_id)

                    group_list, filtered_result_list = result

                    result_dict[entry_id][0].append((
                        row.Sound.client_id, row.Sound.object_id,
                        row.Markup.client_id, row.Markup.object_id,
                        group_list, filtered_result_list))

                    if result_dict[entry_id][1] is None:
                        result_dict[entry_id][1] = text_list

                    result_dict[source_id][2].add(entry_id)

                    result_group_set.update(group_list)

                    perspective_result_count += 1

                    # Stopping earlier, if required.

                    if (args.limit_result and perspective_result_count >= args.limit_result or
                        args.limit and index + 1 >= args.limit):
                        break

                # Stopping iteration over sound/markup pairs early, if required.

                if break_flag:
                    break

            log.debug(
                'phonology {}/{}, link field {}/{}, perspective {}/{}: '
                '{} result{}, {} no vowels, {} exceptions'.format(
                    args.perspective_cid, args.perspective_oid,
                    field_id[0], field_id[1],
                    perspective_id[0], perspective_id[1],
                    perspective_result_count, '' if perspective_result_count == 1 else 's',
                    state.no_vowel_counter, state.exception_counter))

    # If we have no results, we indicate the situation and also show number of failures and number of
    # markups with no vowels.

    if not source_entry_id_set:

        task_status.set(4, 100,
            'Finished, no results produced')

        return {'error': 'no markups for this query'}

    # Otherwise we create an Excel file with results.

    task_status.set(3, 99, 'Compiling results')

    workbook_stream = io.BytesIO()

    csv_stream = io.BytesIO() if args.generate_csv else None
    csv_wrapper = io.TextIOWrapper(csv_stream, encoding = 'utf-8') if args.generate_csv else None

    try:

        entry_count_dict, sound_count_dict, chart_stream_list = (

            compile_workbook(
                args,
                source_entry_id_set,
                result_dict,
                result_group_set,
                workbook_stream,
                csv_wrapper))

        # Getting ready to write out Excel and, if required, CSV file data.

        workbook_stream.seek(0)

        if csv_stream:
            csv_wrapper.flush()
            csv_stream.seek(0)

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('compile_workbook: exception')
        log.debug(traceback_string)

        # If we failed to create an Excel file, we terminate with error.

        task_status.set(4, 100,
            'Finished (ERROR), result compilation error')

        return {
            'error': 'result compilation error',
            'result_counter': len(result_dict)}

    # Name(s) of the resulting file(s) includes dictionary name, perspective name and current date.

    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    result_filename = '{0} - {1} - {2:04d}.{3:02d}.{4:02d}'.format(
        args.dictionary_name[:64], args.perspective_name[:64],
        current_datetime.year,
        current_datetime.month,
        current_datetime.day)

    xlsx_filename = sanitize_filename(result_filename + '.xlsx')
    csv_filename = sanitize_filename(result_filename + '.csv')

    cur_time = time.time()
    storage_dir = path.join(storage['path'], 'phonology', str(cur_time))

    xlsx_path = path.join(storage_dir, xlsx_filename)
    csv_path = path.join(storage_dir, csv_filename)

    makedirs(path.dirname(xlsx_path), exist_ok = True)

    # If the name of the result file is too long, we try again with a shorter name.

    try:
        with open(xlsx_path, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    except OSError as os_error:

        if os_error.errno != 36:
            raise

        result_filename = '{0} - {1} - {2:04d}.{3:02d}.{4:02d}'.format(
            args.dictionary_name[:32], args.perspective_name[:32],
            current_datetime.year,
            current_datetime.month,
            current_datetime.day)

        xlsx_filename = sanitize_filename(result_filename + '.xlsx')
        csv_filename = sanitize_filename(result_filename + '.csv')

        xlsx_path = path.join(storage_dir, xlsx_filename)
        csv_path = path.join(storage_dir, csv_filename)

        workbook_stream.seek(0)

        with open(xlsx_path, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    if args.__debug_flag__:

        workbook_stream.seek(0)

        with open(xlsx_filename, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    # Writing out data in a CSV file, if required.

    if csv_stream:

        with open(csv_path, 'wb+') as csv_file:
            copyfileobj(csv_stream, csv_file)

    # Storing 3d F1/F2/F3 scatter charts, if we have any.

    chart_filename_list = []

    for chart_stream, group_string in chart_stream_list:

        chart_filename = sanitize_filename(result_filename + group_string + '.png')
        chart_path = path.join(storage_dir, chart_filename)

        chart_stream.seek(0)

        with open(chart_path, 'wb+') as chart_file:
            copyfileobj(chart_stream, chart_file)

        chart_filename_list.append(chart_filename)

        if args.__debug_flag__:

            chart_stream.seek(0)

            with open(chart_filename, 'wb+') as chart_file:
                copyfileobj(chart_stream, chart_file)

    # Successfully compiled phonology, finishing and returning links to files with results.

    filename_list = [xlsx_filename] + \
        ([csv_filename] if args.generate_csv else []) + \
        chart_filename_list

    url_list = [

        ''.join([
            storage['prefix'],
            storage['static_route'],
            'phonology', '/',
            str(cur_time), '/',
            filename])

        for filename in filename_list]

    fails_stream.seek(0)
    print(fails_stream.read())
    fails_stream.close()

    task_status.set(4, 100, 'Finished', result_link_list = url_list)


class Sound_Markup_Iterator(object):
    """
    Iterates over sound/markup pairs of a specified perspective while keeping state.
    """

    def __init__(self, perspective_id, cache_key_str):
        """
        Initialization of iteration parameters.
        """

        self.perspective_id = perspective_id
        self.cache_key_str = cache_key_str

    def run(self):
        """
        Iteratively processes sound/markup pairs of the perspective.
        """

        Markup = aliased(Entity, name = 'Markup')
        Sound = aliased(Entity, name = 'Sound')

        PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
        PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')

        data_query = DBSession.query(
            LexicalEntry, Markup, Sound).filter(
                LexicalEntry.parent_client_id == self.perspective_id[0],
                LexicalEntry.parent_object_id == self.perspective_id[1],
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

        self.markup_count = 0

        for index, row in enumerate(data_query.yield_per(100)):

            self.markup_count += 1
            markup_url = row.Markup.content

            row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Markup.client_id, row.Markup.object_id)

            log.debug('{0}: {1}'.format(row_str, markup_url))

            # Checking if we have cached tier list for this pair of sound/markup.

            cache_key = '{0}:{1}:{2}:{3}:{4}'.format(
                self.cache_key_str,
                row.Sound.client_id, row.Sound.object_id,
                row.Markup.client_id, row.Markup.object_id)

            cache_result = caching.CACHE.get(cache_key)
            if cache_result is not None:

                self.process_cache(row_str, cache_key, cache_result)
                continue

            # Trying to download and parse markup and get its tiers.

            try:

                with urllib.request.urlopen(
                    urllib.parse.quote(markup_url, safe = '/:')) as markup_stream:

                    markup_bytes = markup_stream.read()

                try:

                    textgrid = pympi.Praat.TextGrid(xmax = 0)

                    # Textgrid package decodes files line by line, and that means that for UTF-16 / UTF-32
                    # endianness specified by the BOM at the start of the file may be lost.

                    textgrid.from_file(

                        io.BytesIO(
                            markup_bytes
                                .decode(chardet.detect(markup_bytes)['encoding'])
                                .encode('utf-8')),

                        codec = 'utf-8')

                except:

                    # If we failed to parse TextGrid markup, we assume that sound and markup files were
                    # accidentally swapped and try again.

                    markup_url = row.Sound.content

                    with urllib.request.urlopen(
                        urllib.parse.quote(markup_url, safe = '/:')) as markup_stream:

                        markup_bytes = markup_stream.read()

                    textgrid = pympi.Praat.TextGrid(xmax = 0)

                    textgrid.from_file(

                        io.BytesIO(
                            markup_bytes
                                .decode(chardet.detect(markup_bytes)['encoding'])
                                .encode('utf-8')),

                        codec = 'utf-8')

                result = self.process_sound_markup(row_str, textgrid)
                caching.CACHE.set(cache_key, result)

            # Markup processing error, we report it and go on.

            except Exception as exception:

                traceback_string = ''.join(traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1]

                log.debug('{0}: exception'.format(row_str))
                log.debug(traceback_string)


class Tier_List_Iterator(Sound_Markup_Iterator):
    """
    Iterates over sound/markup pairs of a specified perspective, compiles list of markup tier names.
    """

    def __init__(self, perspective_id):
        """
        Initializes state of markup tier name compilation.
        """

        super().__init__(perspective_id, 'phonology_tier_list')

        self.tier_count = collections.Counter()
        self.total_count = 0

    def process_sound_markup(self, row_str, textgrid):
        """
        Processes another markup.
        """

        markup_tier_set = set(tier_name
            for tier_number, tier_name in textgrid.get_tier_name_num())

        self.tier_count.update(markup_tier_set)
        self.total_count += 1

        log.debug('{0}: {1}'.format(row_str,
            list(sorted(markup_tier_set))))

        return markup_tier_set

    def process_cache(self, row_str, cache_key, markup_tier_set):
        """
        Processes cached result.
        """

        self.tier_count.update(markup_tier_set)
        self.total_count += 1

        log.debug('{0} [CACHE {1}]: {2}'.format(row_str, cache_key,
            list(sorted(markup_tier_set))))


def get_tier_list(perspective_cid, perspective_oid):
    """
    Helper function, gets a list of names of phonology markup tiers for specified perspective.
    """

    try:
        log.debug('phonology_tier_list {0}/{1}'.format(
            perspective_cid, perspective_oid))

        iterator = Tier_List_Iterator((perspective_cid, perspective_oid))
        iterator.run()

        # Logging and returning list of all tier names we encountered.

        tier_list = list(sorted(iterator.tier_count.items(),
            key = lambda tier_count: (tier_count[0].lower(), tier_count[0])))

        log.debug('phonology_tier_list {0}/{1}: {2}, {3}'.format(
            perspective_cid, perspective_oid, iterator.total_count, tier_list))

        return True, {
            'tier_count': dict(iterator.tier_count),
            'total_count': iterator.total_count}

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology_tier_list: exception')
        log.debug(traceback_string)

        return False, traceback_string


@view_config(route_name = 'phonology_tier_list', renderer = 'json')
def phonology_tier_list(request):
    """
    Gets a list of names of phonology markup tiers for specified perspective.
    """

    perspective_cid = request.params.get('perspective_client_id')
    perspective_oid = request.params.get('perspective_object_id')

    try_ok, result = get_tier_list(perspective_cid, perspective_oid)

    if not try_ok:

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}

    return result


class Skip_List_Iterator(Sound_Markup_Iterator):
    """
    Iterates over sound/markup pairs of a specified perspective, compiles list of characters skipped during
    processing of vowel phonology for this perspective, and a list of characters from intervals adjacent to
    intervals with vowel markup.
    """

    def __init__(self, perspective_id):
        """
        Initializes state of markup tier name compilation.
        """

        super().__init__(perspective_id, 'phonology_skip_list')

        self.skip_count = collections.Counter()
        self.total_skip_count = 0

        self.neighbour_count = collections.Counter()
        self.total_neighbour_count = 0

    def process_sound_markup(self, row_str, textgrid):
        """
        Processes another markup.
        """

        skip_set = set()
        neighbour_set = set()

        # Looking through all intervals of all tiers of the current markup.

        for tier_number, tier_name in textgrid.get_tier_name_num():

            interval_list = [(begin, end, character_escape(text).strip())
                for begin, end, text in textgrid.get_tier(tier_number).get_all_intervals()]

            for index, (begin, end, text) in enumerate(interval_list):
                transcription_check = re.fullmatch(transcription_re, text)

                if (len(text) > 0 and
                    any(character in vowel_set for character in text) and
                    (len(text) <= 2 or transcription_check)):

                    # If we have an interval with vowel markup, we update sets of skipped and adjacent
                    # characters of this markup.

                    skip_set.update(set(character
                        for character in text
                        if character not in vowel_set))

                    if index > 0:

                        neighbour_set.update(set(character
                            for character in interval_list[index - 1][2]
                            if character not in vowel_set))

                    if index < len(interval_list) - 1:

                        neighbour_set.update(set(character
                            for character in interval_list[index + 1][2]
                            if character not in vowel_set))

        # Updating data of skipped and adjacent characters.

        self.skip_count.update(skip_set)
        self.total_skip_count += 1

        self.neighbour_count.update(neighbour_set)
        self.total_neighbour_count += 1

        log.debug('{0}: {1}, {2}'.format(row_str,
            list(sorted(skip_set)), list(sorted(neighbour_set))))

        return skip_set, neighbour_set

    def process_cache(self, row_str, cache_key, cache_result):
        """
        Processes cached result.
        """

        skip_set, neighbour_set = cache_result

        self.skip_count.update(skip_set)
        self.total_skip_count += len(neighbour_set)

        self.neighbour_count.update(neighbour_set)
        self.total_neighbour_count += 1

        log.debug('{0} [CACHE {1}]: {2}, {3}'.format(row_str, cache_key,
            list(sorted(skip_set)), list(sorted(neighbour_set))))


def get_skip_list(perspective_cid, perspective_oid):
    """
    Helper function, gets a list of characters skipped during processing of vowel phonology, and a list of
    characters from markup intervals adjacent to intervals with vowel markup, for specified perspective.
    """

    try:
        log.debug('phonology_skip_list {0}/{1}'.format(
            perspective_cid, perspective_oid))

        iterator = Skip_List_Iterator((perspective_cid, perspective_oid))
        iterator.run()

        def info_list(character_count):
            """
            Compiles info of a set of unicode characters given their counts in the form of a dictionary-like
            object.
            """

            return list(sorted(

                (ord(character), count,
                    character if unicodedata.combining(character) == 0 else u'◌' + character,
                    unicodedata.name(character).title())

                    for character, count in character_count.items()
                    if not character.isspace()))

        skip_list = info_list(iterator.skip_count)
        neighbour_list = info_list(iterator.neighbour_count)

        def info_to_str(info_list, total_count):
            """
            Builds string representation of a character info list.
            """

            return ''.join(
                '\n  \'{0}\' U+{1:04x} {2}: {3}/{4} ({5:.2f}%)'.format(
                    string, point, name, count, total_count, 100.0 * count / total_count)
                for point, count, string, name in info_list)

        # Logging lists of all skipped and adjacent characters we encountered.

        log.debug(
            'phonology_skip_list {0}/{1}: {2} sound/markup pairs'.format(
            perspective_cid, perspective_oid, iterator.markup_count))

        log.debug(
            'phonology_skip_list {0}/{1}: {2} skipped character instances, {3} unique{4}'.format(
                perspective_cid, perspective_oid,
                iterator.total_skip_count, len(skip_list),
                info_to_str(skip_list, iterator.total_skip_count)))

        log.debug(
            'phonology_skip_list {0}/{1}: {2} adjacent character instances, {3} unique{4}'.format(
                perspective_cid, perspective_oid,
                iterator.total_neighbour_count, len(neighbour_list),
                info_to_str(neighbour_list, iterator.total_neighbour_count)))

        # Returning skipped and adjacent character data.

        return True, {
            'markup_count': iterator.markup_count,
            'neighbour_list': neighbour_list,
            'skip_list': skip_list,
            'total_neighbour_count': iterator.total_neighbour_count,
            'total_skip_count': iterator.total_skip_count}

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology_skip_list: exception')
        log.debug(traceback_string)

        return False, traceback_string


@view_config(route_name = 'phonology_skip_list', renderer = 'json')
def phonology_skip_list(request):
    """
    Gets a list of characters skipped during processing of vowel phonology, and a list of characters from
    markup intervals adjacent to intervals with vowel markup, for specified perspective.
    """

    perspective_cid = request.params.get('perspective_client_id')
    perspective_oid = request.params.get('perspective_object_id')

    try_ok, result = get_skip_list(perspective_cid, perspective_oid)

    if not try_ok:

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}

    return result


def get_link_perspective_data(perspective_id, field_id_list):
    """
    Gets info of perspectives holding data linked from a specified perspective through link entities of the
    specified fields.
    """

    try:
        perspective_client_id, perspective_object_id = perspective_id

        log.debug('phonology_link_perspective_data {0}/{1}: {2}'.format(
            perspective_client_id, perspective_object_id, field_id_list))

        Markup = aliased(Entity, name = 'Markup')
        Sound = aliased(Entity, name = 'Sound')

        PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
        PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')

        # Query for lexical entries of the specified perspective with sound/markup data.

        source_entry_query = DBSession.query(
            LexicalEntry,
            func.count(Markup.client_id),
            func.count(Sound.client_id)).filter(
                LexicalEntry.parent_client_id == perspective_client_id,
                LexicalEntry.parent_object_id == perspective_object_id,
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
                PublishingSound.accepted == True).group_by(
                    LexicalEntry.client_id, LexicalEntry.object_id).subquery()

        # Getting list of perspectives for each field.

        perspective_id_set = set()
        perspective_id_dict = collections.defaultdict(list)

        for field_id in field_id_list:
            field_client_id, field_object_id = field_id

            link_entity_query = DBSession.query(
                LexicalEntry.client_id.label('entry_client_id'),
                LexicalEntry.object_id.label('entry_object_id'),
                Entity).filter(
                    LexicalEntry.parent_client_id == perspective_client_id,
                    LexicalEntry.parent_object_id == perspective_object_id,
                    LexicalEntry.marked_for_deletion == False,
                    Entity.parent_client_id == LexicalEntry.client_id,
                    Entity.parent_object_id == LexicalEntry.object_id,
                    Entity.field_client_id == field_client_id,
                    Entity.field_object_id == field_object_id,
                    Entity.marked_for_deletion == False,
                    PublishingEntity.client_id == Entity.client_id,
                    PublishingEntity.object_id == Entity.object_id,
                    PublishingEntity.published == True,
                    PublishingEntity.accepted == True).subquery()

            # Getting ids of perspectives containing data referenced through this field.

            data_query = DBSession.query(
                LexicalEntry.parent_client_id, LexicalEntry.parent_object_id).filter(
                    source_entry_query.c.client_id == link_entity_query.c.entry_client_id,
                    source_entry_query.c.object_id == link_entity_query.c.entry_object_id,
                    link_entity_query.c.link_client_id == LexicalEntry.client_id,
                    link_entity_query.c.link_object_id == LexicalEntry.object_id)

            perspective_id_list = [tuple(row)
                for row in data_query.distinct()]

            perspective_id_set.update(perspective_id_list)
            perspective_id_dict[tuple(field_id)] = perspective_id_list

        # Returning perspective ids we've found.

        return True, {

            'field_data_list': [
                (field_id, perspective_id_dict[tuple(field_id)])
                    for field_id in field_id_list],

            'perspective_id_list': list(sorted(perspective_id_set))}

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('phonology_link_perspective_data: exception')
        log.debug(traceback_string)

        return False, traceback_string


@view_config(route_name = 'sound_and_markup', renderer = 'json')
def sound_and_markup(request):
    """
    Compiles archive of sound recordings and corresponding markups for a specified perspective.

    Perspective is specified by URL parameters 'perspective_client_id' and 'perspective_object_id'.

    Parameters:
        perspective_client_id
        perspective_object_id
        published_mode
    """

    task_status = None

    try:
        perspective_cid = request.params.get('perspective_client_id')
        perspective_oid = request.params.get('perspective_object_id')

        published_mode = request.params.get('published_mode')

        '''
        limit = (None if 'limit' not in request.params else
            int(request.params.get('limit')))
        '''
        limit = 100

        log.debug('sound_and_markup {0}/{1}: {2}'.format(
            perspective_cid, perspective_oid, published_mode))

        # Getting perspective and perspective's dictionary info.

        perspective = DBSession.query(DictionaryPerspective).filter_by(
            client_id = perspective_cid, object_id = perspective_oid).first()

        if not perspective:
            return {'error': 'Unknown perspective {0}/{1}.'.format(
                perspective_cid, perspective_oid)}

        perspective_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = perspective.translation_gist_client_id,
            object_id = perspective.translation_gist_object_id).first()

        dictionary = DBSession.query(Dictionary).filter_by(
            client_id = perspective.parent_client_id,
            object_id = perspective.parent_object_id).first()

        if not dictionary:
            return {'error': 'Unknown dictionary {0}/{1}.'.format(
                perspective.parent_client_id, perspective.parent_object_id)}

        dictionary_translation_gist = DBSession.query(TranslationGist).filter_by(
            client_id = dictionary.translation_gist_client_id,
            object_id = dictionary.translation_gist_object_id).first()

        # Sound/markup archiving task status setup.

        locale_id = int(request.cookies.get('locale_id') or 2)

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
            perspective_cid, perspective_oid, published_mode, limit,
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

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}


def std_sound_and_markup(
    task_key,
    perspective_cid, perspective_oid, published_mode, limit,
    dictionary_name, perspective_name,
    cache_kwargs, storage, sqlalchemy_url):
    """
    Synchronous sound/markup archive dictionary compilation, used for debugging.
    """

    task_status = TaskStatus.get_from_cache(task_key)

    try:
        return perform_sound_and_markup(
            perspective_cid, perspective_oid, published_mode, limit,
            dictionary_name, perspective_name,
            task_status, storage)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('sound_and_markup: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(4, 100, 'Finished (ERROR), external error')

        return {'error': 'external error'}


@celery.task
def async_sound_and_markup(
    task_key,
    perspective_cid, perspective_oid, published_mode, limit,
    dictionary_name, perspective_name,
    cache_kwargs, storage, sqlalchemy_url):
    """
    Asynchronous sound/markup archive dictionary compilation.
    """

    # This is a no-op with current settings, we use it to enable logging inside celery tasks, because
    # somehow this does it, and otherwise we couldn't set it up.

    logging.debug('async_sound_and_markup')

    # Ok, and now we go on with task execution.

    engine = create_engine(sqlalchemy_url)
    DBSession.configure(bind = engine)
    initialize_cache(cache_kwargs)

    task_status = TaskStatus.get_from_cache(task_key)

    with manager:
        try:

            return perform_sound_and_markup(
                perspective_cid, perspective_oid, published_mode, limit,
                dictionary_name, perspective_name,
                task_status, storage)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('sound_and_markup: exception')
            log.debug(traceback_string)

            if task_status is not None:
                task_status.set(4, 100, 'Finished (ERROR), external error')

            return {'error': 'external error'}


def entity_filename_date(entity, translation):
    """
    Produces archive filename and archive timestamp for a sound or markup file from its entity.
    """

    url_path = urllib.parse.urlparse(entity.content).path

    filename = path.basename(url_path)
    extension = path.splitext(url_path)[1]

    name = sanitize_filename('{0}_{1}_{2}'.format(
        entity.client_id, entity.object_id,
        '{0}{1}'.format(translation[:32], extension[:32]) if translation else filename))

    date = datetime.datetime.utcfromtimestamp(entity.created_at)
    return name, (date.year, date.month, date.day, date.hour, date.minute, date.second)


def get_sound_markup_bytes(storage, sound_url, markup_url):
    """
    Tries to get sound and markup file data, checks if sound and markup files were swapped.
    """

    with storage_file(storage, sound_url) as sound_stream:
        sound_bytes = sound_stream.read()

    with storage_file(storage, markup_url) as markup_stream:
        markup_bytes = markup_stream.read()

    # Checking if we have a valid TextGrid markup.

    try:

        textgrid = pympi.Praat.TextGrid(xmax = 0)

        # Textgrid package decodes files line by line, and that means that for UTF-16 / UTF-32
        # endianness specified by the BOM at the start of the file may be lost.

        textgrid.from_file(

            io.BytesIO(
                markup_bytes
                    .decode(chardet.detect(markup_bytes)['encoding'])
                    .encode('utf-8')),

            codec = 'utf-8')

        return sound_bytes, markup_bytes

    except:

        # If we failed to parse TextGrid markup, we assume that sound and markup files were
        # accidentally swapped and try again.

        textgrid = pympi.Praat.TextGrid(xmax = 0)

        textgrid.from_file(

            io.BytesIO(
                markup_bytes
                    .decode(chardet.detect(markup_bytes)['encoding'])
                    .encode('utf-8')),

            codec = 'utf-8')

        return markup_bytes, sound_bytes


def perform_sound_and_markup(
    perspective_cid, perspective_oid, published_mode, limit,
    dictionary_name, perspective_name,
    task_status, storage):
    """
    Performs sound/markup archive compilation/update.
    """

    log.debug('sound_and_markup {0}/{1}:'
        '\n  published_mode: \'{2}\'\n  dictionary_name: \'{3}\'\n  perspective_name: \'{4}\''.format(
        perspective_cid, perspective_oid, published_mode,
        dictionary_name, perspective_name))

    task_status.set(1, 0, 'Preparing')

    # Checking if we can find translation field.

    field_data = DBSession.query(
        Field, TranslationAtom).filter(
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
            TranslationAtom.marked_for_deletion == False).order_by(
                Field.client_id, Field.object_id).first()

    translation_field = field_data.Field if field_data else None

    log.debug('translation field: ' +
        ('None' if not field_data else '{0}/{1} \'{2}\''.format(
            translation_field.client_id, translation_field.object_id,
            field_data.TranslationAtom.content)))

    # Looking up sound fields.

    FieldTranslationAtom = aliased(TranslationAtom, name = 'FieldTranslationAtom')

    field_data_list = DBSession.query(
        Field, TranslationAtom, FieldTranslationAtom).filter(
            DictionaryPerspectiveToField.parent_client_id == perspective_cid,
            DictionaryPerspectiveToField.parent_object_id == perspective_oid,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.client_id == DictionaryPerspectiveToField.field_client_id,
            Field.object_id == DictionaryPerspectiveToField.field_object_id,
            Field.marked_for_deletion == False,
            TranslationAtom.parent_client_id == Field.data_type_translation_gist_client_id,
            TranslationAtom.parent_object_id == Field.data_type_translation_gist_object_id,
            TranslationAtom.locale_id == 2,
            TranslationAtom.content.op('~*')('.*sound.*'),
            TranslationAtom.marked_for_deletion == False,
            FieldTranslationAtom.parent_client_id == Field.translation_gist_client_id,
            FieldTranslationAtom.parent_object_id == Field.translation_gist_object_id,
            FieldTranslationAtom.locale_id == 2,
            FieldTranslationAtom.marked_for_deletion == False).all()

    sound_field_list = [field_data.Field
        for field_data in field_data_list]

    sound_field_id_list = [(field.client_id, field.object_id)
        for field in sound_field_list]

    # Logging sound fields we've found.

    if len(field_data_list) <= 0:
        sound_field_str = ' []'

    elif len(field_data_list) == 1:

        sound_field_str = ' {0}/{1} \'{2}\''.format(
            sound_field_list[0].client_id, sound_field_list[0].object_id,
            field_data_list[0].FieldTranslationAtom.content)

    else:
        sound_field_str = '\n' + ''.join(

            '  {0}/{1} \'{2}\'\n'.format(
                field_data.Field.client_id, field_data.Field.object_id,
                field_data.FieldTranslationAtom.content)

            for field_data in field_data_list)

    log.debug('sound fields ({0}):'.format(len(sound_field_list)) + sound_field_str)

    # Getting ready to gather list of currently available sound/markup pairs.

    Markup = aliased(Entity, name = 'Markup')
    Sound = aliased(Entity, name = 'Sound')
    Translation = aliased(Entity, name = 'Translation')

    PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
    PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')
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
            PublishingMarkup.accepted == True,
            Sound.client_id == Markup.self_client_id,
            Sound.object_id == Markup.self_object_id,
            Sound.marked_for_deletion == False,
            PublishingSound.client_id == Sound.client_id,
            PublishingSound.object_id == Sound.object_id,
            PublishingSound.accepted == True)

    # And we also prepare to gather sounds unpaired with markup.

    sound_query = DBSession.query(
        LexicalEntry, Sound).filter(
            LexicalEntry.parent_client_id == perspective_cid,
            LexicalEntry.parent_object_id == perspective_oid,
            LexicalEntry.marked_for_deletion == False,
            Sound.parent_client_id == LexicalEntry.client_id,
            Sound.parent_object_id == LexicalEntry.object_id,
            Sound.marked_for_deletion == False,
            tuple_(Sound.field_client_id, Sound.field_object_id).in_(sound_field_id_list),
            PublishingSound.client_id == Sound.client_id,
            PublishingSound.object_id == Sound.object_id,
            PublishingSound.accepted == True)

    # Filtering by publishing status, if required.

    translation_condition = and_(
        PublishingTranslation.client_id == Translation.client_id,
        PublishingTranslation.object_id == Translation.object_id,
        PublishingTranslation.accepted == True)

    if published_mode == 'published':

        data_query = data_query.filter(
            PublishingMarkup.published == True,
            PublishingSound.published == True)

        sound_query = sound_query.filter(
            PublishingSound.published == True)

        translation_condition = and_(
            translation_condition,
            PublishingTranslation.published == True)

    # Getting translation data, if required.

    if translation_field:

        data_query = (data_query

            .outerjoin(Translation, and_(
                Translation.parent_client_id == LexicalEntry.client_id,
                Translation.parent_object_id == LexicalEntry.object_id,
                Translation.field_client_id == translation_field.client_id,
                Translation.field_object_id == translation_field.object_id,
                Translation.marked_for_deletion == False))

            .outerjoin(PublishingTranslation, translation_condition)

            .add_columns(
                func.array_agg(Translation.content))

            .group_by(LexicalEntry, Markup, Sound))

        # Unpaired sounds we also try to match with translations.

        sound_query = (sound_query

            .outerjoin(Translation, and_(
                Translation.parent_client_id == LexicalEntry.client_id,
                Translation.parent_object_id == LexicalEntry.object_id,
                Translation.field_client_id == translation_field.client_id,
                Translation.field_object_id == translation_field.object_id,
                Translation.marked_for_deletion == False))

            .outerjoin(PublishingTranslation, translation_condition)

            .add_columns(
                func.array_agg(Translation.content))

            .group_by(LexicalEntry, Sound))

    # Preparing for writing out sound/markup archive.

    storage_dir = path.join(storage['path'], 'sound_and_markup')
    makedirs(storage_dir, exist_ok = True)

    archive_name = sanitize_filename(
        '{0} - {1}.zip'.format(dictionary_name[:64], perspective_name[:64]))

    archive_path = path.join(storage_dir, archive_name)
    log.debug('archive path: {0}'.format(archive_path))

    if not path.exists(archive_path):

        # Ok, we are to simply generate new archive.

        total_count = data_query.count()
        sound_count = sound_query.count()

        sound_name_set = set()
        markup_count = 0

        no_markup_count = 0

        with zipfile.ZipFile(archive_path, 'w') as archive_file:

            # Starting with sound/markup pairs.

            task_status.set(2, 1, 'Processing sound and markup files')

            for index, row in enumerate(data_query.yield_per(100)):

                sound_url = row.Sound.content
                markup_url = row.Markup.content
                translation = row[3][0] if translation_field and len(row[3]) > 0 else None

                row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(
                    index,
                    row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                    row.Sound.client_id, row.Sound.object_id,
                    row.Markup.client_id, row.Markup.object_id)

                log.debug('{0}: \'{1}\'\n{2}\n{3}'.format(
                    row_str, translation, sound_url, markup_url))

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

                    task_status.set(2, int(math.floor(1 + (index + 1) * 49.5 / total_count)),
                        'Archiving sound and markup')

                    continue

                # Archiving sound data, unless we already processed this sound entity, which can happen if
                # it has multiple markup entities.

                sound_name, sound_date = entity_filename_date(row.Sound, translation)

                if sound_name not in sound_name_set:
                    sound_name_set.add(sound_name)

                    zip_info = zipfile.ZipInfo(sound_name, sound_date)

                    if sndhdr.test_wav(sound_bytes, io.BytesIO(sound_bytes)):
                        zip_info.compress_type = zipfile.ZIP_DEFLATED

                    archive_file.writestr(zip_info, sound_bytes)

                # Archiving markup data.

                markup_name, markup_date = entity_filename_date(row.Markup, translation)

                markup_name = '{0}_{1}_{2}'.format(
                    row.Sound.client_id, row.Sound.object_id, markup_name)

                archive_file.writestr(zipfile.ZipInfo(markup_name, markup_date), markup_bytes,
                    zipfile.ZIP_DEFLATED)

                markup_count += 1

                # Another sound/markup pair is processed successfully.

                task_status.set(2, int(math.floor(1 + (index + 1) * 49.5 / total_count)),
                    'Archiving sound and markup')

                if limit and index + 1 >= limit:
                    break

            # Also processing sounds without markup.

            task_status.set(3, 1, 'Processing sounds without markup')

            for index, row in enumerate(sound_query.yield_per(100)):

                sound_url = row.Sound.content
                translation = row[2][0] if translation_field and len(row[2]) > 0 else None

                sound_name, sound_date = entity_filename_date(row.Sound, translation)

                if sound_name in sound_name_set:
                    continue

                row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4})'.format(index,
                    row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                    row.Sound.client_id, row.Sound.object_id)

                log.debug('{0}: \'{1}\'\n{2}'.format(
                    row_str, translation, sound_url))

                # Getting sound data.

                try:

                    with storage_file(storage, sound_url) as sound_stream:
                        sound_bytes = sound_stream.read()

                except Exception as exception:

                    log.debug('{0}: exception\n{1}'.format(
                        row_str, sound_url))

                    traceback_string = ''.join(traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1]

                    log.debug(traceback_string)

                    task_status.set(3, int(math.floor(50.5 + (index + 1) * 49.5 / sound_count)),
                        'Archiving sounds without markup')

                    continue

                # Archiving sound data.

                zip_info = zipfile.ZipInfo('no_markup_sounds/' + sound_name, sound_date)

                if sndhdr.test_wav(sound_bytes, io.BytesIO(sound_bytes)):
                    zip_info.compress_type = zipfile.ZIP_DEFLATED

                archive_file.writestr(zip_info, sound_bytes)
                no_markup_count += 1

                task_status.set(3, int(math.floor(50.5 + (index + 1) * 49.5 / sound_count)),
                    'Archiving sounds without markup')

                if limit and index + 1 >= limit:
                    break

    else:

        # Updating existing archive, we start with gathering info of sound and markup files which should end
        # up in the archive.

        update_list = []
        update_set = set()

        for index, row in enumerate(data_query.yield_per(100)):

            translation = row[3][0] if translation_field and len(row[3]) > 0 else None

            sound_name, sound_date = entity_filename_date(row.Sound, translation)
            markup_name, markup_date = entity_filename_date(row.Markup, translation)

            markup_name = '{0}_{1}_{2}'.format(
                row.Sound.client_id, row.Sound.object_id, markup_name)

            # Saving sound/markup data for later use.

            update_list.append((index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Markup.client_id, row.Markup.object_id,
                row.Sound.content, row.Markup.content, translation,
                sound_name, sound_date, markup_name, markup_date))

            update_set.add(sound_name)
            update_set.add(markup_name)

            if limit and index + 1 >= limit:
                break

        # The same for unpaired sound files.

        sound_update_list = []
        sound_update_set = set()

        for index, row in enumerate(sound_query.yield_per(100)):

            translation = row[2][0] if translation_field and len(row[2]) > 0 else None
            sound_name, sound_date = entity_filename_date(row.Sound, translation)

            if sound_name in update_set:
                continue

            sound_update_list.append((index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Sound.content, translation,
                sound_name, sound_date))

            sound_update_set.add(sound_name)

            if limit and index + 1 >= limit:
                break

        # Checking what files are already in the archive, which archive entries should be deleted and which
        # files should be added to the archive.

        with zipfile.ZipFile(archive_path, 'r') as archive_file:
            zip_info_list = archive_file.infolist()

        already_set = set()
        sound_already_set = set()

        no_markup_str = 'no_markup_sounds/'
        no_markup_len = len(no_markup_str)

        for zip_info in zip_info_list:

            if zip_info.filename.startswith(no_markup_str):
                sound_already_set.add(zip_info.filename[no_markup_len:])

            else:
                already_set.add(zip_info.filename)

        delete_set = already_set - update_set
        add_set = update_set - already_set

        sound_delete_set = sound_already_set - sound_update_set
        sound_add_set = sound_update_set - sound_already_set

        # Doing something only if we need to delete or add some files.

        if (len(delete_set) + len(sound_delete_set) > 0 or
            len(add_set) + len(sound_add_set) > 0):

            if len(delete_set) + len(sound_delete_set) > 0:

                archive_mode = 'w'

                add_set = update_set
                sound_add_set = sound_update_set

            else:

                archive_mode = 'a'

            # Either appending to the archive, or overwriting it, depending on whether we need to delete
            # files from the archive.

            with zipfile.ZipFile(archive_path, archive_mode) as archive_file:

                sound_name_set = set()
                markup_count = 0

                no_markup_count = 0

                task_status.set(2, 1, 'Processing sound and markup files')

                for (index,
                    lexicalentry_cid, lexicalentry_oid,
                    sound_cid, sound_oid,
                    markup_cid, markup_oid,
                    sound_url, markup_url, translation,
                    sound_name, sound_date, markup_name, markup_date) in update_list:

                    # Skipping all already present sound/markup pairs.

                    if sound_name not in add_set and markup_name not in add_set:
                        continue

                    row_str = ('{0} (LexicalEntry {1}/{2}, '
                        'sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(index,
                        lexicalentry_cid, lexicalentry_oid, sound_cid, sound_oid, markup_cid, markup_oid))

                    log.debug('{0}: \'{1}\'\n{2}\n{3}'.format(
                        row_str, translation, sound_url, markup_url))

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

                        task_status.set(2, int(math.floor(1 + (index + 1) * 49.5 / len(update_list))),
                            'Archiving sound and markup')

                        continue

                    # Archiving sound data, unless we already have it in the archive or we already processed
                    # this sound entity, which can happen if it has multiple markup entities.

                    if sound_name in add_set and sound_name not in sound_name_set:
                        sound_name_set.add(sound_name)

                        zip_info = zipfile.ZipInfo(sound_name, sound_date)

                        if sndhdr.test_wav(sound_bytes, io.BytesIO(sound_bytes)):
                            zip_info.compress_type = zipfile.ZIP_DEFLATED

                        archive_file.writestr(zip_info, sound_bytes)

                    # Archiving markup data if we don't have it in the archive already.

                    if markup_name in add_set:

                        archive_file.writestr(zipfile.ZipInfo(markup_name, markup_date), markup_bytes,
                            zipfile.ZIP_DEFLATED)

                        markup_count += 1

                    # Another sound/markup pair is processed successfully.

                    task_status.set(2, int(math.floor(1 + (index + 1) * 49.5 / len(update_list))),
                        'Archiving sound and markup')

                    if limit and index + 1 >= limit:
                        break

                # And now unpaired sound files.

                task_status.set(3, 1, 'Processing sounds without markup')

                for (index,
                    lexicalentry_cid, lexicalentry_oid,
                    sound_cid, sound_oid,
                    sound_url, translation,
                    sound_name, sound_date) in sound_update_list:

                    if sound_name not in sound_add_set:
                        continue

                    row_str = ('{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4})'.format(index,
                        lexicalentry_cid, lexicalentry_oid, sound_cid, sound_oid))

                    log.debug('{0}: \'{1}\'\n{2}'.format(
                        row_str, translation, sound_url))

                    # Getting sound data.

                    try:

                        with storage_file(storage, sound_url) as sound_stream:
                            sound_bytes = sound_stream.read()

                    except Exception as exception:

                        log.debug('{0}: exception\n{1}'.format(
                            row_str, sound_url))

                        traceback_string = ''.join(traceback.format_exception(
                            exception, exception, exception.__traceback__))[:-1]

                        log.debug(traceback_string)

                        task_status.set(3,
                            int(math.floor(50.5 + (index + 1) * 49.5 / len(sound_update_list))),
                            'Archiving sounds without markup')

                        continue

                    # Archiving sound data.

                    zip_info = zipfile.ZipInfo('no_markup_sounds/' + sound_name, sound_date)

                    if sndhdr.test_wav(sound_bytes, io.BytesIO(sound_bytes)):
                        zip_info.compress_type = zipfile.ZIP_DEFLATED

                    archive_file.writestr(zip_info, sound_bytes)
                    no_markup_count += 1

                    task_status.set(3,
                        int(math.floor(50.5 + (index + 1) * 49.5 / len(sound_update_list))),
                        'Archiving sounds without markup')

                    if limit and index + 1 >= limit:
                        break

        # We don't have to delete any files, and we don't have to add any files, we leave the archive
        # unchanged and indicate that it is fully ready.

        else:

            sound_name_set = set()
            markup_count = 0

            no_markup_count = 0

            task_status.set(2, 100, 'Archiving sound and markup')

    # Successfully compiled sound/markup archive, finishing and returning link to the archive.

    archive_url = ''.join([
        storage['prefix'],
        storage['static_route'],
        'sound_and_markup', '/', archive_name])

    task_status.set(4, 100, 'Finished', result_link = archive_url)

    return {
        'sound_count': len(sound_name_set),
        'markup_count': markup_count,
        'no_markup_count': no_markup_count}


def cpu_time(reference_cpu_time = 0.0):
    """
    Returns current or elapsed value of CPU time used by the process,
    including both user and system CPU time of both the process itself and
    its children.
    """

    return sum(os.times()[:4]) - reference_cpu_time


def main_cache_delete_exceptions(args):
    """
    Removes cached phonology exceptions from the redis cache.
    """

    parser = configparser.ConfigParser()
    parser.read(args[0])

    caching.initialize_cache({
        k: v for k, v in parser.items('cache:redis:args')})

    cache_key_list = (

        subprocess
            .check_output(['redis-cli', '--scan', '--pattern', 'phonology:*'])
            .decode('utf-8')
            .split())

    count = 0

    for cache_key in cache_key_list:

        cache_result = caching.CACHE.get(cache_key)

        if (isinstance(cache_result, tuple) and
            cache_result[0] == 'exception'):

            print(cache_result[1])

            caching.CACHE.rem(cache_key)
            count += 1

            print(cache_key)

    print('{} cached exceptions removed'.format(count))


def main_test_alpha(args):
    """
    Tests that intensity and formant computation works.
    """

    markup_bytes = open('корень_БИН_(1_раз).TextGrid', 'rb').read()

    textgrid = pympi.Praat.TextGrid(xmax = 0)

    # Textgrid package decodes files line by line, and that means that for UTF-16 / UTF-32
    # endianness specified by the BOM at the start of the file may be lost.

    textgrid.from_file(

        io.BytesIO(
            markup_bytes
                .decode(chardet.detect(markup_bytes)['encoding'])
                .encode('utf-8')),

        codec = 'utf-8')

    raw_interval_list = textgrid.get_tier(1).get_all_intervals()
    interval_list = []
    long_text_flag = False

    interval_idx_to_raw_idx = dict()

    # Compiling transcription, checking if we have unusual markup.

    for raw_index, interval in enumerate(raw_interval_list):

        if len(interval[2]) <= 2 and \
            len(interval[2].strip()) and \
            any(character in vowel_set for character in interval[2]):

            interval_list.append(interval)
            interval_idx_to_raw_idx[len(interval_list)-1] = raw_index

        elif len(interval[2]) > 2:
            long_text_flag = True

    transcription = ''.join(text for begin, end, text in raw_interval_list)

    # Otherwise we retrieve the sound file and analyse each vowel-containing markup.

    sound = AudioPraatLike(pydub.AudioSegment.from_wav('корень_БИН_(1_раз).wav'))

    (max_intensity_index, max_intensity, max_length_index, max_length) = \
        find_max_interval_praat(sound, interval_list)

    max_intensity_interval = interval_list[max_intensity_index]
    max_length_interval = interval_list[max_length_index]

    # Compiling results.

    max_length_str = '{0} {1:.3f} [{2}]'.format(
        max_length_interval[2], max_length,
        len(''.join(text for begin, end, text in
            raw_interval_list[:interval_idx_to_raw_idx[max_length_index]])))

    max_intensity_str = '{0} {1:.3f} [{2}]'.format(
        max_intensity_interval[2],
        max_intensity,
        len(''.join(text for begin, end, text in
            raw_interval_list[:interval_idx_to_raw_idx[max_intensity_index]])))

    print((transcription, max_length_str, max_intensity_str,
        '+' if max_intensity_index == max_length_index else '-'))

    # Getting formants.

    begin, end = raw_interval_list[interval_idx_to_raw_idx[max_length_index]][:2]
    print(raw_interval_list[interval_idx_to_raw_idx[max_length_index]])
    print(sound.get_interval_formants(begin, end))

    begin, end = raw_interval_list[interval_idx_to_raw_idx[max_intensity_index]][:2]
    print(raw_interval_list[interval_idx_to_raw_idx[max_intensity_index]])
    print(sound.get_interval_formants(begin, end))


def main_test_profile(args):
    """
    Tests large amount of intensity/formant computation for profiling.
    """

    data_dir_list = list(map(path.realpath, sys.argv[1].split(',')))

    total_pair_count = 0
    total_result_count = 0
    total_entry_count = 0
    total_sound_count = 0

    total_elapsed_cpu_time = 0.0

    for data_dir in data_dir_list:
        print('Data directory: {0}'.format(data_dir))

        start_cpu_time = cpu_time()

        # Gathering available sound files.

        wav_dict = {}
        for wav_path in sorted(glob.glob(path.join(data_dir, 'phonology:*.wav'))):

            match = re.match('phonology:(\d+):(\d+):(\d+):(\d+)_.*', path.basename(wav_path))
            id_tuple = tuple(map(int, match.groups()))

            wav_dict[id_tuple] = wav_path

        # Analyzing markup files one by one.

        result_list = []
        result_limit = None if len(sys.argv) < 3 else int(sys.argv[2])

        for index, textgrid_path in enumerate(sorted(
            glob.glob(path.join(data_dir, 'phonology:*.TextGrid')))):

            # Getting sound-markup pair data.

            match = re.match('phonology:(\d+):(\d+):(\d+):(\d+)_(.*)', path.basename(textgrid_path))
            id_tuple = tuple(map(int, match.groups()[:4]))
            textgrid_name = match.group(5)

            wav_path = wav_dict[id_tuple]
            match = re.match('phonology:(\d+):(\d+):(\d+):(\d+)_(.*)', path.basename(wav_path))
            wav_name = match.group(5)

            phonology_str = '[{0}] phonology:{1}:{2}:{3}:{4}'.format(index, *id_tuple)

            print('{0}: {1}, {2}'.format(
                phonology_str, textgrid_name, wav_name))
            sys.stdout.flush()

            # Getting markup.

            try:

                markup_bytes = open(textgrid_path, 'rb').read()

                textgrid = pympi.Praat.TextGrid(xmax = 0)

                # Textgrid package decodes files line by line, and that means that for UTF-16 / UTF-32
                # endianness specified by the BOM at the start of the file may be lost.

                textgrid.from_file(

                    io.BytesIO(
                        markup_bytes
                            .decode(chardet.detect(markup_bytes)['encoding'])
                            .encode('utf-8')),

                    codec = 'utf-8')

            except Exception as exception:

                print(''.join(traceback.format_exception(
                    exception, exception, exception.__traceback__))[:-1])

                continue

            # Checking for each tier if it needs to be processed.

            def unusual_f(tier_number, tier_name, transcription, unusual_markup_dict):
                print('tier {0} \'{1}\' has interval(s) with unusual transcription text: {2} / {3}'.format(
                    tier_number, tier_name, transcription, unusual_markup_dict))

            def no_vowel_f(tier_number, tier_name, transcription_list):
                print('tier {0} \'{1}\' doesn\'t have any vowel markup: {2}'.format(
                    tier_number, tier_name, transcription_list))

            def no_vowel_selected_f(tier_number, tier_name, transcription_list, selected_list):

                print(
                    'tier {0} \'{1}\' intervals to be processed don\'t have any vowel markup: '
                    'markup {2}, selected {3}'.format(
                    tier_number, tier_name, transcription_list, selected_list))

            tier_data_list, vowel_flag = process_textgrid(
                textgrid, unusual_f, no_vowel_f, no_vowel_selected_f)

            # If there are no tiers with vowel markup, we skip this sound-markup pair altogether.

            if not vowel_flag:
                continue

            # We analyze each vowel-containing markup.

            sound = AudioPraatLike(pydub.AudioSegment.from_wav(wav_path))

            textgrid_result_list = process_sound(tier_data_list, sound)
            result_list.append(textgrid_result_list)

            result_string = '\n'.join(
                'tier {0} \'{1}\': {2}'.format(tier_number, tier_name,

                    tier_result_list if not isinstance(tier_result_list, list) else
                    tier_result_list[0] if len(tier_result_list) <= 1 else
                    ''.join('\n  {0}'.format(tier_result) for tier_result in tier_result_list))

                    for tier_number, tier_name, tier_result_list in textgrid_result_list)

            print('result:\n{0}'.format(result_string))
            sys.stdout.flush()

            # Stopping earlier, if required.

            if result_limit and len(result_list) >= result_limit:
                break

        # Compiling Excel workbook with analysis results.

        workbook_stream = io.BytesIO()
        entry_count, sound_count = compile_workbook(result_list, workbook_stream)

        with open(path.join(data_dir, 'result.xlsx'), 'wb') as result_file:
            result_file.write(workbook_stream.getvalue())

        # Showing result counts and elapsed CPU time.

        print('{0} result{1}, {2} entr{3}, {4} sound{5} ({6} markup/sound pair{7} processed)'.format(
            len(result_list), '' if len(result_list) == 1 else 's',
            entry_count, 'y' if entry_count == 1 else 'ies',
            sound_count, '' if sound_count == 1 else 's',
            index + 1, '' if index == 0 else 's'))

        elapsed_cpu_time = cpu_time(start_cpu_time)

        print(
            'elapsed CPU time: {0:.3f}s, {1:.3f}s / result, {2:.3f}s / entry, {3:.3f}s / sound, '
            '{4:.3f}s / pair'.format(
            elapsed_cpu_time,
            elapsed_cpu_time / len(result_list),
            elapsed_cpu_time / entry_count,
            elapsed_cpu_time / sound_count,
            elapsed_cpu_time / (index + 1)))

        # Updating total results.

        total_pair_count += index + 1
        total_result_count += len(result_list)
        total_entry_count += entry_count
        total_sound_count += sound_count

        total_elapsed_cpu_time += elapsed_cpu_time

    # Reporting total result and CPU time statistics.

    print(
        '{0} data directories, {1} result{2}, {3} entr{4}, {5} sound{6} '
        '({7} markup/sound pair{8} processed)'.format(
        len(data_dir_list),
        total_result_count, '' if total_result_count == 1 else 's',
        total_entry_count, 'y' if total_entry_count == 1 else 'ies',
        total_sound_count, '' if total_sound_count == 1 else 's',
        total_pair_count, '' if total_pair_count == 1 else 's'))

    print(
        'total elapsed CPU time: {0:.3f}s, {1:.3f}s / result, {2:.3f}s / entry, {3:.3f}s / sound, '
        '{4:.3f}s / pair'.format(
        total_elapsed_cpu_time,
        total_elapsed_cpu_time / total_result_count,
        total_elapsed_cpu_time / total_entry_count,
        total_elapsed_cpu_time / total_sound_count,
        total_elapsed_cpu_time / total_pair_count))


def main_praat_escape(args):
    """
    Extracts data of valid character escape sequences from Praat sources (at the moment source files
    kar/UnicodeData.h, kar/longchar.cpp), constructs regular expression replacer, checks that it works.
    """

    character_dict = {}
    unicode_re = re.compile('\\s*#define (UNICODE_\\S*?)\\s+(\\S*)\\s*')

    with open(sys.argv[1], 'r', encoding = 'utf-8') as unicode_data_file:
        for line in unicode_data_file:

            match = unicode_re.fullmatch(line)

            if match:
                character_dict[match.group(1)] = chr(int(match.group(2), 0))

    # Parsing escape sequence substitution data.

    replace_dict = {}
    longchar_re = re.compile('\\s*{\\s*\'(.)\'\\s*,\\s*\'(.)\',.*?(UNICODE_\\S*?)\\s*}\\s*,')

    with open(sys.argv[2], 'r', encoding = 'utf-8') as longchar_file:
        for line in longchar_file:

            match = longchar_re.match(line)

            if match:
                replace_dict['\\' + match.group(1) + match.group(2)] = character_dict[match.group(3)]

    # Multireplacement via regular expressions along the lines of http://stackoverflow.com/questions/
    # 6116978/python-replace-multiple-strings and https://gist.github.com/bgusach/
    # a967e0587d6e01e889fd1d776c5f3729.

    print(len(character_dict))
    print(list(sorted(character_dict.items()))[:4])

    print(len(replace_dict))
    print(list(sorted(replace_dict.items()))[:4])

    substitution_list = sorted(replace_dict.keys(), key = len, reverse = True)
    substitution_re = re.compile('|'.join(map(re.escape, substitution_list)))

    print(len(substitution_list))
    print(len('|'.join(map(re.escape, substitution_list))))

    # Testing substitution.

    print(substitution_re.sub(
        lambda match: replace_dict[match.group(0)],
        'b\\^j\\ae\\tf\\i-'))

    replace_list = list(
        sorted((escape_string, ord(character))
            for escape_string, character in replace_dict.items()))

    # Showing escape substitution data.

    print('[')
    current_line = '   '

    for index, (escape_string, character_code) in enumerate(replace_list):

        current_string = ' ({0}, {1}){2}'.format(
            repr(escape_string), character_code, ',' if index < len(replace_list) - 1 else ']')

        if len(current_line + current_string) <= 108:
            current_line += current_string
            continue

        print(current_line)
        current_line = '   ' + current_string

    print(current_line)


# Some additional local computations.

command_dict = {
    'cache_delete_exceptions': main_cache_delete_exceptions,
    'praat_escape': main_praat_escape,
    'test_alpha': main_test_alpha,
    'test_profile': main_test_profile}

if __name__ == '__main__':

    if len(sys.argv) > 1:

        if sys.argv[1] in command_dict:
            command_dict[sys.argv[1]](sys.argv[2:])

        else:
            print('Unknown command \'{0}\'.'.format(sys.argv[1]))

    else:
        print('Please specify command to execute.')

