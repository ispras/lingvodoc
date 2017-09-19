
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


class AudioPraatLike(object):
    """
    Allows computations of sound intensity and formants using algorithms mimicking as close as possible
    corresponding algorithms of the Praat [http://www.fon.hum.uva.nl/praat] software.
    """

    def __init__(self, source_sound):

        self.intensity_sound = source_sound

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
        Computes mean-energy intensity of an interval specified by beginning and end in seconds.
        """

        # Due to windowed nature of intensity computation, we can't compute it for points close to the
        # beginning and the end of the recording; such points are skipped.

        factor = self.intensity_sound.frame_rate / self.intensity_step_size

        begin_step = max(4, int(math.ceil(begin * factor)))
        end_step = min(self.intensity_step_count - 5, int(math.floor(end * factor)))

        energy_sum = sum(
            math.pow(10, 0.1 * self.get_intensity(step_index))
                for step_index in range(begin_step, end_step + 1))

        return 10 * math.log10(energy_sum / (end_step - begin_step + 1))

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

    def init_formant_fft(self):
        """
        Initializes formant computation data using FFT-based resampling computed via numpy.
        """

        sample_array = self.intensity_sound.get_array_of_samples()
        channel_count = self.intensity_sound.channels
        frame_count = int(self.intensity_sound.frame_count())

        padding = min(1000, frame_count // 16)
        source_count = frame_count + 2 * padding
        factor = float(self.formant_frame_rate) / self.intensity_sound.frame_rate

        resample_count = int(math.floor(factor * source_count))
        resample_padding = int(math.ceil(factor * padding))

        # Fourier transform is linear, so we first average over channels and then resample using FFT.

        source_list = numpy.empty(source_count)

        source_list[:padding] = 0.0
        source_list[-padding:] = 0.0

        if channel_count == 1:
            source_list[padding:-padding] = sample_array

        elif channel_count == 2:

            for i in range(frame_count):
                source_list[padding + i] = (sample_array[i * 2] + sample_array[i * 2 + 1]) / 2.0

        # General case.

        else:
            for i in range(frame_count):

                source_list[padding + i] = sum(
                    sample_array[i * channel_count + j]
                      for j in range(channel_count)) / channel_count

        sample_list = numpy.fft.irfft(numpy.fft.rfft(source_list), resample_count)

        # NOTE: we have to manually clear rfft's cache because otherwise it will grow indefinitely while
        # processing many series of different lengths.

        if len(numpy.fft.fftpack._real_fft_cache) >= 16:
            numpy.fft.fftpack._real_fft_cache = {}

        # Getting sound time series ready for formant analysis by pre-emphasising frequencies higher
        # than 50 Hz.

        factor = math.exp(-2.0 * math.pi * 50 / self.formant_frame_rate)

        self.formant_frame_count = len(sample_list)
        self.formant_sample_list = [sample_list[0]]

        for i in range(1, int(self.formant_frame_count)):

            self.formant_sample_list.append(
                sample_list[i] - factor * sample_list[i - 1])

        # Number of formant values and formant value cache.

        self.formant_step_count = int(
            math.floor((self.formant_frame_count - 1) // self.formant_step_size + 1))

        self.formant_list = [None for i in range(self.formant_step_count)]

    def get_formants(self, step_index):
        """
        Computes point formant values at the point specified by formant time step index.
        """

        # Initializing formant computation data, if required.

        if self.formant_list == None:
            self.init_formant_f()

        # Checking validity of supplied time step index.

        if step_index < 4 or step_index >= self.formant_step_count - 4:
            raise ValueError('step index {0} is out of bounds [4, {1})'.format(
                step_index, self.formant_step_count - 4))

        # Checking if we already computed required formant point value.

        if self.formant_list[step_index] != None:
            return self.formant_list[step_index]

        # No, we haven't, so we are going to compute it.

        window_list = get_gaussian_window(self.formant_window_size)
        sample_from = (step_index - 4) * self.formant_step_size

        sample_list = [
            self.formant_sample_list[sample_from + i] * window_list[i]
                for i in range(self.formant_window_size)]

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
        # wiki/Newton's_method.
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

        nyquist_frequency = self.formant_frame_rate * 0.5
        formant_list = []

        for root in better_root_list:

            if abs(root) > 1.0:
                root = 1.0 / root.conjugate()

            if root.imag >= 0:
                frequency = abs(math.atan2(root.imag, root.real)) * nyquist_frequency / math.pi

                if frequency >= 50 and frequency <= nyquist_frequency - 50:
                    formant_list.append(frequency)

        # Memoizing and returning first three formants.

        formant_list.sort()
        self.formant_list[step_index] = formant_list[:3]

        return formant_list[:3]

    def get_interval_formants(self, begin, end):
        """
        Computes first and second formants of an interval specified by beginning and end in seconds.
        """

        # Initializing formant computation data, if required.

        if self.formant_list == None:
            self.init_formant_f()

        # Due to windowed nature of formant value computation, we can't compute them for points close to
        # the beginning and the end of the recording; such points are skipped.

        factor = self.formant_frame_rate / self.formant_step_size

        begin_step = max(4, int(math.ceil(begin * factor)))
        end_step = min(self.formant_step_count - 5, int(math.floor(end * factor)))

        # Getting point formant values.

        f1_list, f2_list, f3_list = [], [], []

        for step_index in range(begin_step, end_step + 1):
            f1, f2, f3 = self.get_formants(step_index)

            f1_list.append(f1)
            f2_list.append(f2)
            f3_list.append(f3)

        f1_list.sort()
        f2_list.sort()
        f3_list.sort()

        # Computing interval formant values as means (without highest and lowest values, if possible).

        step_count = end_step - begin_step + 1

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

        intensity = sound.get_interval_intensity(begin_sec, end_sec)
        length = end_sec - begin_sec

        if max_intensity == None or intensity > max_intensity:
            max_intensity = intensity
            max_intensity_index = index

        if max_length == None or length > max_length:
            max_length = length
            max_length_index = index

    return (max_intensity_index, max_intensity, max_length_index, max_length)


#: Set of vowels used by computation of phonology of dictionary perspectives.
vowel_set = set('AEIOUYaeiouyÄÆÉØäæéøŒœƆƏƐƗƜƟƱɄɅɐɑɒɔɘəɛɜɞɤɨɪɯɵɶʉʊʌʏАОаоⱭⱯⱰꞫ')


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


def process_textgrid(textgrid, unusual_f, no_vowel_f, no_vowel_selected_f):
    """
    Processes TextGrid markup, checking for each tier if it should be analyzed.
    """

    tier_data_list = []
    vowel_flag = False

    for tier_number, tier_name in textgrid.get_tier_name_num():

        raw_interval_list = [(begin, end, character_escape(text))
            for begin, end, text in textgrid.get_tier(tier_number).get_all_intervals()]

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
            unusual_f(tier_number, tier_name, transcription, dict(unusual_markup_list))

        # If the markup does not have any vowels, we note it and also report it.

        if all(character not in vowel_set for character in transcription):

            tier_data_list.append((tier_number, tier_name, 'no_vowel'))
            no_vowel_f(tier_number, tier_name, transcription_list)

        # It is also possible that while full transcription has vowels, intervals selected for
        # analysis do not. In that case we also note it and report it.

        elif not any(character in vowel_set for character in selected):

            tier_data_list.append((tier_number, tier_name, 'no_vowel_selected'))
            no_vowel_selected_f(tier_number, tier_name, transcription_list, selected_list)

        # Otherwise we store tier data to be used during processing of the sound file.

        else:
            tier_data_list.append((tier_number, tier_name,
                (raw_interval_list, raw_interval_seq_list, interval_seq_list,
                    interval_idx_to_raw_idx, transcription)))

            vowel_flag = True

    return tier_data_list, vowel_flag


class Tier_Result(object):
    """
    Stores results of joint analysis of a single TextGrid tier and corresponding sound intervals.
    """

    def __init__(self,
        transcription,
        total_interval_length,
        mean_interval_length,
        translation_list,
        max_length_str,
        max_length_r_length,
        max_length_f_list,
        max_intensity_str,
        max_intensity_r_length,
        max_intensity_f_list,
        coincidence_str,
        interval_data_list):

        self.transcription = transcription

        self.total_interval_length = total_interval_length
        self.mean_interval_length = mean_interval_length

        self.translation_list = translation_list

        self.max_length_str = max_length_str
        self.max_length_r_length = max_length_r_length
        self.max_length_f_list = max_length_f_list

        self.max_intensity_str = max_intensity_str
        self.max_intensity_r_length = max_intensity_r_length
        self.max_intensity_f_list = max_intensity_f_list

        self.coincidence_str = coincidence_str

        self.interval_data_list = interval_data_list

    def format(self):
        """
        Generates more or less human-readable representation of analysis results.
        """

        interval_result_list = [

            ([interval_str,
                '{0:.2f}%'.format(r_length * 100),
                is_max_length, is_max_intensity], [f_list])

                for interval_str, r_length, f_list, is_max_length, is_max_intensity in
                    self.interval_data_list]

        return pprint.pformat(

            [[self.transcription,
                '{0:.3f}s'.format(self.total_interval_length),
                '{0:.3f}s'.format(self.mean_interval_length),
                self.translation_list,

                self.max_length_str,
                self.max_length_r_length,
                self.max_intensity_str,
                self.max_intensity_r_length,
                self.coincidence_str],

                self.max_length_f_list,
                self.max_intensity_f_list] + interval_result_list,

            width = 192)


def process_sound(tier_data_list, sound, translation_list = []):
    """
    Analyzes sound intervals corresponding to vowel-containing markup.
    """

    textgrid_result_list = []

    for tier_number, tier_name, tier_data in tier_data_list:

        if tier_data == 'no_vowel' or tier_data == 'no_vowel_selected':
            textgrid_result_list.append((tier_number, tier_name, tier_data))
            continue

        # Analyzing vowel sounds of each interval sequence.

        (raw_interval_list, raw_interval_seq_list,
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

            max_intensity_f_list = sound.get_interval_formants(*max_intensity_interval[:2])
            max_length_f_list = sound.get_interval_formants(*max_length_interval[:2])

            intensity_list = [
                sound.get_interval_intensity(begin_sec, end_sec)
                    for begin_sec, end_sec, text in interval_list]

            formant_list = [
                sound.get_interval_formants(begin_sec, end_sec)
                    for begin_sec, end_sec, text in interval_list]

            # Computing average sound interval length.

            total_interval_length = sum(end - begin
                for raw_index, (begin, end, text) in raw_interval_list)
            
            mean_interval_length = total_interval_length / len(raw_interval_list)

            # Preparing interval data.

            max_length_str = '{0} {1:.3f} [{2}]'.format(
                max_length_interval[2], max_length,
                len(''.join(text for index, (begin, end, text) in
                    raw_interval_list[:interval_idx_to_raw_idx[seq_index][max_length_index]])))

            max_intensity_str = '{0} {1:.3f} [{2}]'.format(
                max_intensity_interval[2],
                max_intensity,
                len(''.join(text for index, (begin, end, text) in
                    raw_interval_list[:interval_idx_to_raw_idx[seq_index][max_intensity_index]])))

            str_list = [
                    
                '{0} {1:.3f} {2:.3f} [{3}]'.format(
                    text, end_sec - begin_sec, intensity,
                    len(''.join(text for raw_index, (begin, end, text) in
                        raw_interval_list[:interval_idx_to_raw_idx[seq_index][index]])))

                    for index, (intensity, (begin_sec, end_sec, text)) in
                        enumerate(zip(intensity_list, interval_list))]

            # Compiling results.

            interval_data_list = [

                (interval_str,
                    (end - begin) / mean_interval_length,
                    list(map('{0:.3f}'.format, f_list)),
                    '+' if index == max_length_index else '-',
                    '+' if index == max_intensity_index else '-')

                    for index, (interval_str, f_list, (begin, end, text)) in
                        enumerate(zip(str_list, formant_list, interval_list))]

            textgrid_result_list[-1][2].append(Tier_Result(
                ''.join(text for index, (begin, end, text) in raw_interval_list),
                total_interval_length,
                mean_interval_length,
                translation_list,
                max_length_str,
                max_length / mean_interval_length,
                list(map('{0:.3f}'.format, max_length_f_list)),
                max_intensity_str,
                (max_intensity_interval[1] - max_intensity_interval[0]) / mean_interval_length,
                list(map('{0:.3f}'.format, max_intensity_f_list)),
                '+' if max_intensity_index == max_length_index else '-',
                interval_data_list))

    # Returning analysis results.

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


def compile_workbook(vowel_selection, result_list, result_group_set, workbook_stream):
    """
    Compiles analysis results into an Excel workbook.
    """

    workbook = xlsxwriter.Workbook(workbook_stream, {'in_memory': True})
    format_percent = workbook.add_format({'num_format': '0.00%'})

    group_string_dict = {group: repr(group)
        for group in result_group_set if group != None}

    group_sorted_list = sorted([(group_string, group)
        for group, group_string in group_string_dict.items() if group != None])

    group_list = [None] + list(
        map(lambda group_string_and_group: group_string_and_group[1], group_sorted_list))

    # Creating sets of worksheets for each result group, including the universal one.

    worksheet_dict = {}

    for group in group_list:
        group_name_string = '' if group == None else ' (group {0})'.format(group_string_dict[group])

        if vowel_selection:

            header_list = [
                'Longest (seconds) interval', 'Relative length',
                'F1 mean (Hz)', 'F2 mean (Hz)', 'F3 mean (Hz)', 'Table reference',
                'Highest intensity (dB) interval', 'Relative length',
                'F1 mean (Hz)', 'F2 mean (Hz)', 'F3 mean (Hz)', 'Table reference',
                'Coincidence']

        else:
            header_list = [
                'Interval', 'Relative length',
                'F1 mean (Hz)', 'F2 mean (Hz)', 'F3 mean (Hz)', 'Table reference',
                'Longest', 'Highest intensity']

        worksheet_results = workbook.add_worksheet('Results' + group_name_string)
        worksheet_results.write_row('A1', ['Transcription', 'Translation'] + header_list)

        # Formatting column widths.

        if vowel_selection:

            worksheet_results.set_column(0, 2, 26)
            worksheet_results.set_column(3, 3, 13, format_percent)
            worksheet_results.set_column(4, 7, 13)
            worksheet_results.set_column(8, 8, 26)
            worksheet_results.set_column(9, 9, 13, format_percent)
            worksheet_results.set_column(10, 14, 13)

        else:
            worksheet_results.set_column(0, 2, 26)
            worksheet_results.set_column(3, 3, 13, format_percent)
            worksheet_results.set_column(4, 9, 13)

        worksheet_dict[group] = (worksheet_results,
            workbook.add_worksheet('F-table' + group_name_string),
            workbook.add_worksheet('F-chart' + group_name_string),
            workbook.add_worksheet('F-table (3d)' + group_name_string))

    row_counter_dict = {group: 2 for group in result_group_set}
    sound_counter_dict = {group: 0 for group in result_group_set}

    vowel_formant_dict = {group: collections.defaultdict(list) for group in result_group_set}

    # Filling in analysis results.

    for textgrid_group_list, textgrid_result_list in result_list:
        for tier_number, tier_name, tier_result_list in textgrid_result_list:

            if tier_result_list == 'no_vowel' or tier_result_list == 'no_vowel_selected':
                continue

            for tier_result in tier_result_list:
                translation_list = tier_result.translation_list

                # Either only for longest interval and interval with highest intensity, or...

                if vowel_selection:

                    f_list_a = list(map(float, tier_result.max_length_f_list[:3]))
                    f_list_b = list(map(float, tier_result.max_intensity_f_list[:3]))

                    row_list = ([
                        tier_result.transcription,
                        translation_list[0] if translation_list else '',
                        tier_result.max_length_str,
                        round(tier_result.max_length_r_length, 4)] + f_list_a + [
                        ', '.join(formant_reference(*f_list_a[:2])),
                        tier_result.max_intensity_str,
                        round(tier_result.max_intensity_r_length, 4)] + f_list_b + [
                        ', '.join(formant_reference(*f_list_b[:2])),
                        tier_result.coincidence_str])

                    # Writing out interval data and any additional translations.

                    for group in textgrid_group_list:

                        worksheet_dict[group][0].write_row('A' + str(row_counter_dict[group]), row_list)
                        row_counter_dict[group] += 1

                        for translation in translation_list[1:]:

                            worksheet_dict[group][0].write('B' + str(row_counter_dict[group]), translation)
                            row_counter_dict[group] += 1

                    # Collecting vowel formant data.

                    text_a_list = tier_result.max_length_str.split()
                    text_b_list = tier_result.max_intensity_str.split()

                    vowel_a = ''.join(filter(lambda character: character in vowel_set, text_a_list[0]))
                    vowel_b = ''.join(filter(lambda character: character in vowel_set, text_b_list[0]))

                    for group in textgrid_group_list:

                        sound_counter_dict[group] += 1
                        vowel_formant_dict[group][vowel_a].append(tuple(f_list_a))

                    if text_b_list[2] != text_a_list[2]:
                        for group in textgrid_group_list:

                            sound_counter_dict[group] += 1
                            vowel_formant_dict[group][vowel_b].append(tuple(f_list_b))

                # ...for all intervals.

                else:
                    for index, (interval_str, interval_r_length, f_list, sign_longest, sign_highest) in \
                        enumerate(tier_result.interval_data_list):

                        text_list = interval_str.split()
                        vowel = ''.join(filter(lambda character: character in vowel_set, text_list[0]))

                        f_list = list(map(float, f_list[:3]))

                        row_list = ([
                            tier_result.transcription,
                            translation_list[index] if index < len(translation_list) else '',
                            interval_str,
                            round(interval_r_length, 4)] + f_list + [
                            ', '.join(formant_reference(*f_list[:2])),
                            sign_longest,
                            sign_highest])

                        # Writing out interval analysis data and any additional translations, collecting
                        # vowel formant data.

                        for group in textgrid_group_list:

                            worksheet_dict[group][0].write_row('A' + str(row_counter_dict[group]), row_list)
                            row_counter_dict[group] += 1

                            for translation in translation_list[len(tier_result.interval_data_list):]:

                                worksheet_dict[group][0].write(
                                    'B' + str(row_counter_dict[group]), translation)

                                row_counter_dict[group] += 1

                            sound_counter_dict[group] += 1
                            vowel_formant_dict[group][vowel].append(tuple(f_list))

    # And now we will produce 2d F1/F2 and 3d F1/F2/F3  scatter charts for all analysed and sufficiently
    # frequent vowels of all result groups.

    chart_stream_list = []
    for group in group_list:

        group_name_string = '' if group == None else ' (group {0})'.format(group_string_dict[group])
        worksheet_table_2d, worksheet_chart, worksheet_table_3d = worksheet_dict[group][1:4]

        vowel_formant_list = []

        for vowel, f_tuple_list in sorted(vowel_formant_dict[group].items()):
            f_tuple_list = list(set(f_tuple_list))

            if len(f_tuple_list) >= 8:
                vowel_formant_list.append((vowel,
                    list(map(lambda f_tuple: numpy.array(f_tuple[:2]), f_tuple_list)),
                    list(map(numpy.array, f_tuple_list))))

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

            mean_2d = sum(f_2d_list) / len(f_2d_list)
            sigma_2d = numpy.cov(numpy.array(f_2d_list).T)
            inverse_2d = numpy.linalg.inv(sigma_2d)

            mean_3d = sum(f_3d_list) / len(f_3d_list)
            sigma_3d = numpy.cov(numpy.array(f_3d_list).T)
            inverse_3d = numpy.linalg.inv(sigma_3d)

            distance_2d_list = []
            distance_3d_list = []

            # Calculation of squared Mahalanobis distance inspired by the StackOverflow answer
            # http://stackoverflow.com/q/27686240/2016856.

            for f_2d in f_2d_list:

                delta_2d = f_2d - mean_2d
                distance_2d_list.append((numpy.einsum('n,nk,k->', delta_2d, inverse_2d, delta_2d), f_2d))

            for f_3d in f_3d_list:

                delta_3d = f_3d - mean_3d
                distance_3d_list.append((numpy.einsum('n,nk,k->', delta_3d, inverse_3d, delta_3d), f_3d))

            distance_2d_list.sort()
            distance_3d_list.sort()

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

            for distance_squared, f_2d in distance_2d_list:
                if distance_squared <= 2:
                    filtered_2d_list.append(f_2d)
                else:
                    outlier_2d_list.append(f_2d)

            if len(filtered_2d_list) < (len(distance_2d_list) + 1) // 2:
                sorted_list = [f_2d for distance_squared, f_2d in distance_2d_list]

                filtered_2d_list = sorted_list[:(len(distance_2d_list) + 1) // 2]
                outlier_2d_list = sorted_list[(len(distance_2d_list) + 1) // 2:]

            chart_data_2d_list.append((
                len(filtered_2d_list), len(f_2d_list), vowel,
                filtered_2d_list, outlier_2d_list, mean_2d, ellipse_list))

            # The same for F1/F2/F3 3-vectors.

            filtered_3d_list = []
            outlier_3d_list = []

            for distance_squared, f_3d in distance_3d_list:
                if distance_squared <= 2:
                    filtered_3d_list.append(f_3d)
                else:
                    outlier_3d_list.append(f_3d)

            if len(filtered_3d_list) < (len(distance_3d_list) + 1) // 2:
                sorted_list = [f_3d for distance_squared, f_3d in distance_3d_list]

                filtered_3d_list = sorted_list[:(len(distance_3d_list) + 1) // 2]
                outlier_3d_list = sorted_list[(len(distance_3d_list) + 1) // 2:]

            chart_data_3d_list.append((
                len(filtered_3d_list), len(f_3d_list), vowel,
                filtered_3d_list, outlier_3d_list, mean_3d, sigma_3d, inverse_3d))

            # Updating F1/F2 maximum/minimum info.

            f1_list, f2_list = zip(*filtered_2d_list)

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

            f1_list, f2_list, f3_list = zip(*filtered_3d_list)

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

        if len(chart_data_2d_list) > 0:
            chart_dict_list = []

            column_list = list(string.ascii_uppercase) + [c1 + c2
                for c1 in string.ascii_uppercase
                for c2 in string.ascii_uppercase]

            shape_list = ['square', 'diamond', 'triangle', 'x', 'star', 'short_dash', 'long_dash', 'circle',
                'plus']

            color_list = ['black', 'blue', 'brown', 'green', 'navy', 'purple', 'red', 'orange', 'gray',
                'cyan', 'lime', 'magenta', 'silver', 'yellow']

            # It seems that we have to plot data in order of its size, from vowels with least number of
            # F1/F2 points to vowels with the most number of F1/F2 points, otherwise scatter chart fails to
            # generate properly.

            chart_data_2d_list.sort(reverse = True)

            max_f_2d_list_length = max(len(f_2d_list)
                for c, tc, v, f_2d_list, o_list, m, e_list in chart_data_2d_list)

            heading_list = []
            for c, tc, vowel, f_list, o_list, m, e_list in chart_data_2d_list:
                heading_list.extend(['{0} F1'.format(vowel), '{0} F2'.format(vowel)])

            worksheet_table_2d.write_row('A1', heading_list)
            worksheet_table_2d.write_row('A2', ['main part', ''] * len(chart_data_2d_list))

            # Removing outliers that outlie too much.

            f1_limit = max_2d_f1 + min_2d_f1 / 2
            f2_limit = max_2d_f2 + min_2d_f2 / 2

            for i in range(len(chart_data_2d_list)):
                chart_data_2d_list[i] = list(chart_data_2d_list[i])

                chart_data_2d_list[i][4] = list(filter(
                    lambda f_2d: f_2d[0] <= f1_limit and f_2d[1] <= f2_limit,
                    chart_data_2d_list[i][4]))

            max_outlier_list_length = max(len(outlier_list)
                for c, tc, v, f_list, outlier_list, m, e_list in chart_data_2d_list)

            # Writing out chart data and compiling chart data series info.

            for index, (count, total_count, vowel,
                f_2d_list, outlier_list, mean, ellipse_list) in enumerate(chart_data_2d_list):

                f1_list, f2_list = zip(*f_2d_list)

                f1_outlier_list, f2_outlier_list = zip(*outlier_list)
                x1_ellipse_list, x2_ellipse_list = zip(*ellipse_list)

                f1_column = column_list[index * 2]
                f2_column = column_list[index * 2 + 1]

                # Writing out formant data.

                worksheet_table_2d.write(f1_column + '3',
                    '{0}/{1} ({2:.1f}%) points'.format(
                        count, total_count, 100.0 * count / total_count))

                worksheet_table_2d.write_column(f1_column + '4',
                    list(f1_list) +
                    [''] * (max_f_2d_list_length - len(f1_list)) +
                    [vowel + ' outliers', '{0}/{1} ({2:.1f}%) points'.format(
                        len(outlier_list), total_count, 100.0 * len(outlier_list) / total_count)] +
                    list(f1_outlier_list) +
                    [''] * (max_outlier_list_length - len(f1_outlier_list)) +
                    [vowel + ' mean', mean[0], vowel + ' stdev ellipse'] +
                    list(x1_ellipse_list))

                worksheet_table_2d.write_column(f2_column + '4',
                    list(f2_list) +
                    [''] * (max_f_2d_list_length - len(f2_list)) +
                    ['', ''] + list(f2_outlier_list) +
                    [''] * (max_outlier_list_length - len(f2_outlier_list)) +
                    ['', mean[1], ''] + list(x2_ellipse_list))

                worksheet_table_2d.set_column(index * 2, index * 2 + 1, 11)

                # Compiling and saving chart data series info.

                group_name_string = '' if group == None else ' (group {0})'.format(group_string_dict[group])
                color = color_list[index % len(color_list)]

                chart_dict_list.append({
                    'name': vowel,
                    'categories': '=\'F-table{0}\'!${1}$4:${1}${2}'.format(
                        group_name_string, f2_column, len(f2_list) + 3),
                    'values': '=\'F-table{0}\'!${1}$4:${1}${2}'.format(
                        group_name_string, f1_column, len(f1_list) + 3),
                    'marker': {
                        'type': 'circle',
                        'size': 5,
                        'border': {'color': color},
                        'fill': {'color': color}}})

                # And additional outliers data series.

                chart_dict_list.append({
                    'name': vowel + ' outliers',
                    'categories': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                        group_name_string, f2_column,
                        max_f_2d_list_length + 6, max_f_2d_list_length + len(f2_outlier_list) + 5),
                    'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                        group_name_string, f1_column,
                        max_f_2d_list_length + 6, max_f_2d_list_length + len(f1_outlier_list) + 5),
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
                        group_name_string, f2_column, shift + 7, shift + 7),
                    'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                        group_name_string, f1_column, shift + 7, shift + 7),
                    'marker': {
                        'type': 'x',
                        'size': 12,
                        'border': {'color': color},
                        'fill': {'color': color}}})

                # Finally, one standard deviation ellipse data series.

                chart_dict_list.append({
                    'name': vowel + ' stdev ellipse',
                    'categories': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                        group_name_string, f2_column, shift + 9, shift + len(x2_ellipse_list) + 8),
                    'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                        group_name_string, f1_column, shift + 9, shift + len(x1_ellipse_list) + 8),
                    'marker': {
                        'type': 'none',
                        'size': 1,
                        'border': {'color': color},
                        'fill': {'color': color}},
                    'line': {'color': color, 'width': 0.5},
                    'smooth': True})

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

        if len(chart_data_3d_list) > 0:

            column_list = list(string.ascii_uppercase) + [c1 + c2
                for c1 in string.ascii_uppercase
                for c2 in string.ascii_uppercase]

            chart_data_3d_list.sort(reverse = True)

            max_f_3d_list_length = max(len(f_3d_list)
                for c, tc, v, f_3d_list, o_list, m, s_3d, i_3d in chart_data_3d_list)

            heading_list = []
            for c, tc, vowel, f_list, o_list, m, s_3d, i_3d in chart_data_3d_list:

                heading_list.extend([
                    '{0} F1'.format(vowel), '{0} F2'.format(vowel), '{0} F3'.format(vowel)])

            worksheet_table_3d.write_row('A1', heading_list)
            worksheet_table_3d.write_row('A2', ['main part', '', ''] * len(chart_data_3d_list))

            # Removing outliers that outlie too much.

            f1_limit = max_3d_f1 + min_3d_f1 / 2
            f2_limit = max_3d_f2 + min_3d_f2 / 2
            f3_limit = max_3d_f3 + min_3d_f3 / 2

            for i in range(len(chart_data_3d_list)):
                chart_data_3d_list[i] = list(chart_data_3d_list[i])

                chart_data_3d_list[i][4] = list(filter(
                    lambda f_3d: f_3d[0] <= f1_limit and f_3d[1] <= f2_limit and f_3d[2] <= f3_limit,
                    chart_data_3d_list[i][4]))

            max_outlier_list_length = max(len(outlier_list)
                for c, tc, v, f_list, outlier_list, m, s_3d, i_3d in chart_data_3d_list)

            # Writing out chart data.

            for index, (count, total_count, vowel, f_3d_list,
                outlier_list, mean, sigma_3d, inverse_3d) in enumerate(chart_data_3d_list):

                f1_list, f2_list, f3_list = zip(*f_3d_list)
                f1_outlier_list, f2_outlier_list, f3_outlier_list = zip(*outlier_list)

                f1_column = column_list[index * 3]
                f2_column = column_list[index * 3 + 1]
                f3_column = column_list[index * 3 + 2]

                # Writing out formant data.

                worksheet_table_3d.write(f1_column + '3',
                    '{0}/{1} ({2:.1f}%) points'.format(
                        count, total_count, 100.0 * count / total_count))

                worksheet_table_3d.write_column(f1_column + '4',
                    list(f1_list) +
                    [''] * (max_f_3d_list_length - len(f1_list)) +
                    [vowel + ' outliers', '{0}/{1} ({2:.1f}%) points'.format(
                        len(outlier_list), total_count, 100.0 * len(outlier_list) / total_count)] +
                    list(f1_outlier_list) +
                    [''] * (max_outlier_list_length - len(f1_outlier_list)) +
                    [vowel + ' mean', mean[0]])

                worksheet_table_3d.write_column(f2_column + '4',
                    list(f2_list) +
                    [''] * (max_f_3d_list_length - len(f2_list)) +
                    ['', ''] + list(f2_outlier_list) +
                    [''] * (max_outlier_list_length - len(f2_outlier_list)) +
                    ['', mean[1]])

                worksheet_table_3d.write_column(f3_column + '4',
                    list(f3_list) +
                    [''] * (max_f_3d_list_length - len(f3_list)) +
                    ['', ''] + list(f3_outlier_list) +
                    [''] * (max_outlier_list_length - len(f3_outlier_list)) +
                    ['', mean[2]])

                worksheet_table_3d.set_column(index * 3, index * 3 + 2, 11)

            # Creating 3d formant scatter charts, if we have any data.

            if chart_data_3d_list:

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

                color_list = ['black', 'blue', 'brown', 'green', 'navy', 'purple', 'red',
                    'orange', 'gray', 'cyan', 'lime', 'magenta', 'silver', 'yellow']

                # Graphing every vowel's data.

                for index, ((c, tc, vowel, f_3d_list, outlier_list, mean_3d, s_3d, inverse_3d),
                    color) in enumerate(zip(chart_data_3d_list, itertools.cycle(color_list))):

                    axes.scatter(
                        [f_3d[0] for f_3d in f_3d_list],
                        [f_3d[1] for f_3d in f_3d_list],
                        [f_3d[2] for f_3d in f_3d_list],
                        color = color, s = 4, depthshade = False, alpha = 0.5, zorder = 1000 + index)

                    f1_outlier_list, f2_outlier_list, f3_outlier_list = zip(*outlier_list)

                    axes.scatter(
                        f1_outlier_list, f2_outlier_list, f3_outlier_list,
                        color = color, s = 1.44, depthshade = False, alpha = 0.5, zorder = index)

                    # Using 'plot' and not 'scatter' so that z-ordering would work correctly and mean
                    # formant vector markers are in the forefront.

                    axes.plot([mean_3d[0]], [mean_3d[1]], [mean_3d[2]], '.',
                        marker = 'o', c = color, markersize = 7, zorder = 4000 + index)

                    plot_proxy = matplotlib.lines.Line2D(
                        [0], [0], linestyle = "none", c = color, marker = 'o')

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

                    u, s, rotation = numpy.linalg.svd(inverse_3d)
                    scale_x, scale_y, scale_z = 1.0 / numpy.sqrt(s)

                    x = scale_x * numpy.outer(numpy.cos(phi), numpy.sin(theta))
                    y = scale_y * numpy.outer(numpy.sin(phi), numpy.sin(theta))
                    z = scale_z * numpy.outer(numpy.ones_like(theta), numpy.cos(theta))

                    for i in range(len(x)):
                        for j in range(len(x)):

                            [x[i, j], y[i, j], z[i, j]] = (mean_3d +
                                numpy.dot([x[i, j], y[i, j], z[i, j]], rotation))

                    axes.plot_surface(x, y, z, rstride = 10, cstride = 10,
                        color = color, linewidth = 0.1, alpha = 0.044, shade = True, zorder = 2000 + index)

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

                for index, ((c, tc, vowel, f_3d_list, outlier_list, mean_3d, sigma_3d, i_3d),
                    color) in enumerate(zip(chart_data_3d_list, itertools.cycle(color_list))):

                    axes.scatter(mean_3d[0], mean_3d[1], z_level,
                        c = color, s = 36, marker = 'x', zorder = 5000 + index)

                    axes.plot(
                        [mean_3d[0], mean_3d[0]],
                        [mean_3d[1], mean_3d[1]],
                        [mean_3d[2], z_level],
                        '--', color = color, zorder = 3000 + index)

                    # Projection of an ellipsoid is an ellipse, for info on computation of ellipsoid
                    # projections see https://tcg.mae.cornell.edu/pubs/Pope_FDA_08.pdf.

                    projection = numpy.identity(3)
                    projection[2, 2] = 0

                    mean_3d_p = numpy.dot(projection, mean_3d)[:2]
                    transform = numpy.dot(projection, scipy.linalg.sqrtm(sigma_3d))[:2, :2]

                    phi = numpy.linspace(0, 2 * numpy.pi, 64)
                    x = numpy.cos(phi)
                    y = numpy.sin(phi)

                    for i in range(len(x)):
                        x[i], y[i] = mean_3d_p + numpy.dot([x[i], y[i]], transform)

                    axes.plot(x, y, zs = z_level, zdir = 'z', color = color, linewidth = 0.25,
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

                legend = axes.legend(legend_plot_list, legend_label_list,
                    markerscale = 1.25, numpoints = 1)

                pyplot.setp(legend.texts, family = 'Gentium')

                pyplot.tight_layout()
                figure.subplots_adjust(left = 0, right = 1, bottom = 0, top = 1)

                # Rendering charts to memory as PNG images.

                chart_stream = io.BytesIO()
                pyplot.savefig(chart_stream, format = 'png')

                chart_stream_list.append((chart_stream, group_name_string))

    # Finishing workbook compilation, returning some result counts.

    workbook.close()

    entity_counter_dict = {group: row_counter - 2
        for group, row_counter in row_counter_dict.items()}

    return (entity_counter_dict, sound_counter_dict, chart_stream_list)


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
        vowel_selection
    """

    task_status = None

    try:
        # Getting request parameters either from URL parameters...

        if 'url_parameters' in request.params:

            perspective_cid = int(request.params.get('perspective_client_id'))
            perspective_oid = int(request.params.get('perspective_object_id'))

            group_by_description = 'group_by_description' in request.params
            only_first_translation = 'only_first_translation' in request.params
            vowel_selection = 'vowel_selection' in request.params

            maybe_tier_list = None
            maybe_tier_set = None

        # ...or from JSON data.

        else:
            request_json = request.json

            perspective_cid = request_json.get('perspective_client_id')
            perspective_oid = request_json.get('perspective_object_id')

            group_by_description = request_json.get('group_by_description')
            only_first_translation = request_json.get('only_first_translation')
            vowel_selection = request_json.get('vowel_selection')

            maybe_tier_list = request_json.get('maybe_tier_list')
            maybe_tier_set = set(maybe_tier_list) if maybe_tier_list else None

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

        locale_id = int(request.cookies.get('locale_id') or 2)

        dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        perspective_name = perspective_translation_gist.get_translation(locale_id)

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        task_status = TaskStatus(user_id,
            'Phonology compilation', '{0}: {1}'.format(dictionary_name, perspective_name), 4)

        # Checking if we have limits on number of computed results.

        parameter_dict = \
            request.params if 'url_parameters' in request.params else request_json

        limit = (None if 'limit' not in parameter_dict else
            int(parameter_dict.get('limit')))

        limit_exception = (None if 'limit_exception' not in parameter_dict else
            int(parameter_dict.get('limit_exception')))

        limit_no_vowel = (None if 'limit_no_vowel' not in parameter_dict else
            int(parameter_dict.get('limit_no_vowel')))

        limit_result = (None if 'limit_result' not in parameter_dict else
            int(parameter_dict.get('limit_result')))

        # Performing either synchronous or asynchronous phonology compilation.

        request.response.status = HTTPOk.code

        task_key = task_status.key
        cache_kwargs = request.registry.settings["cache_kwargs"]
        sqlalchemy_url = request.registry.settings["sqlalchemy.url"]
        storage = request.registry.settings["storage"]

        return (std_phonology if 'synchronous' in request.params else async_phonology.delay)(
            task_key,
            perspective_cid, perspective_oid,
            dictionary_name, perspective_name,
            cache_kwargs, storage,
            group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
            limit, limit_exception, limit_no_vowel, limit_result,
            sqlalchemy_url)

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


def std_phonology(
    task_key,
    perspective_cid, perspective_oid,
    dictionary_name, perspective_name,
    cache_kwargs, storage,
    group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
    limit, limit_exception, limit_no_vowel, limit_result,
    sqlalchemy_url):
    """
    Synchronous phonology compilation, useful for debugging.
    """

    task_status = TaskStatus.get_from_cache(task_key)

    try:
        return perform_phonology(
            perspective_cid, perspective_oid,
            dictionary_name, perspective_name,
            group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
            limit, limit_exception, limit_no_vowel, limit_result,
            task_status, storage)

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
def async_phonology(
    task_key,
    perspective_cid, perspective_oid,
    dictionary_name, perspective_name,
    cache_kwargs, storage,
    group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
    limit, limit_exception, limit_no_vowel, limit_result,
    sqlalchemy_url):
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

            return perform_phonology(
                perspective_cid, perspective_oid,
                dictionary_name, perspective_name,
                group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
                limit, limit_exception, limit_no_vowel, limit_result,
                task_status, storage)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('phonology: exception')
            log.debug(traceback_string)

            if task_status is not None:
                task_status.set(4, 100, 'Finished (ERROR), external error')

            return {'error': 'external error'}


def perform_phonology(
    perspective_cid, perspective_oid,
    dictionary_name, perspective_name,
    group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
    limit, limit_exception, limit_no_vowel, limit_result,
    task_status, storage):
    """
    Performs phonology compilation.
    """

    log.debug('phonology {0}/{1}:'
        '\n  dictionary_name: \'{2}\'\n  perspective_name: \'{3}\''
        '\n  group_by_description: {4}\n  vowel_selection: {5}\n  only_first_translation: {6}'
        '\n  maybe_tier_set: {7}'
        '\n  limit: {8}\n  limit_exception: {9}\n  limit_no_vowel: {10}\n  limit_result: {11}'.format(
        perspective_cid, perspective_oid,
        dictionary_name, perspective_name,
        group_by_description, vowel_selection, only_first_translation, maybe_tier_set,
        limit, limit_exception, limit_no_vowel, limit_result))

    task_status.set(1, 0, 'Preparing')

    # Setting up result filteting based on allowed tiers, if required.

    if maybe_tier_set:

        def result_filter(textgrid_result_list):

            return [(tier_number, tier_name, tier_data)
                for tier_number, tier_name, tier_data in textgrid_result_list
                    if tier_name in maybe_tier_set]

    else:

        def result_filter(textgrid_result_list):
            return textgrid_result_list

    # Getting translation field data, for SQLAlchemy regular expression conditionals see
    # https://stackoverflow.com/a/34989788/2016856.

    field_data = DBSession.query(
        DictionaryPerspectiveToField, Field, TranslationAtom).filter(
            DictionaryPerspectiveToField.parent_client_id == perspective_cid,
            DictionaryPerspectiveToField.parent_object_id == perspective_oid,
            DictionaryPerspectiveToField.marked_for_deletion == False,
            Field.client_id == DictionaryPerspectiveToField.field_client_id,
            Field.object_id == DictionaryPerspectiveToField.field_object_id,
            TranslationAtom.parent_client_id == Field.translation_gist_client_id,
            TranslationAtom.parent_object_id == Field.translation_gist_object_id,
            TranslationAtom.locale_id == 2,
            TranslationAtom.content.op('~*')('.*translation.*')).first()

    if not field_data:
        raise Exception('Missing translation field.')

    field = field_data.Field
    log.debug('field: {0}/{1}'.format(field.client_id, field.object_id))

    # Before everything else we should count how many sound/markup pairs we are to process.

    Markup = aliased(Entity, name = 'Markup')
    Sound = aliased(Entity, name = 'Sound')
    Translation = aliased(Entity, name = 'Translation')

    PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
    PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')
    PublishingTranslation = aliased(PublishingEntity, name = 'PublishingTranslation')

    data_query = DBSession.query(
        LexicalEntry, Markup, Sound, func.array_agg(Translation.content)).filter(
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
            PublishingSound.accepted == True,
            Translation.parent_client_id == LexicalEntry.client_id,
            Translation.parent_object_id == LexicalEntry.object_id,
            Translation.marked_for_deletion == False,
            Translation.field_client_id == field.client_id,
            Translation.field_object_id == field.object_id,
            PublishingTranslation.client_id == Translation.client_id,
            PublishingTranslation.object_id == Translation.object_id,
            PublishingTranslation.published == True,
            PublishingTranslation.accepted == True).group_by(
                LexicalEntry.client_id, LexicalEntry.object_id,
                Markup.client_id, Markup.object_id,
                Sound.client_id, Sound.object_id)

    total_count = data_query.count()
    task_status.set(2, 1, 'Analyzing sound and markup')

    # We get lexical entries of the perspective with markup'ed sounds, and possibly with translations, and
    # process these lexical entries in batches.
    #
    # In batches because just in case, it seems that perspectives rarely have more then several hundred
    # such lexical entries, but we are being cautious.

    exception_counter = 0
    no_vowel_counter = 0

    result_list = list()
    result_group_set = set()

    for index, row in enumerate(data_query.yield_per(100)):

        markup_url = row.Markup.content
        sound_url = row.Sound.content

        row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(
            index,
            row.LexicalEntry.client_id, row.LexicalEntry.object_id,
            row.Sound.client_id, row.Sound.object_id,
            row.Markup.client_id, row.Markup.object_id)

        cache_key = 'phonology:{0}:{1}:{2}:{3}'.format(
            row.Sound.client_id, row.Sound.object_id,
            row.Markup.client_id, row.Markup.object_id)

        # Processing grouping, if required.

        group_list = [None]

        if group_by_description and 'blob_description' in row.Markup.additional_metadata:
            group_list.append(row.Markup.additional_metadata['blob_description'])

            log.debug(message('\n  blob description: {0}/{1}'.format(
                row.Markup.additional_metadata['blob_description'],
                row.Sound.additional_metadata['blob_description'])))

        # Checking if we have cached result for this pair of sound/markup.
        #
        # NOTE: We reference CACHE indirectly, as caching.CACHE, so that when we are inside a celery task
        # and CACHE is re-initialized, we would get newly initialized CACHE, and not the value which was
        # imported ealier.

        cache_result = caching.CACHE.get(cache_key)

        try:
            if cache_result == 'no_vowel':

                log.debug('{0} [CACHE {1}]: no vowels\n{2}\n{3}'.format(
                    row_str, cache_key, markup_url, sound_url))

                no_vowel_counter += 1

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    'Analyzing sound and markup')

                if (limit_no_vowel and no_vowel_counter >= limit_no_vowel or
                    limit and index + 1 >= limit):
                    break

                continue

            # If we have cached exception, we do the same as with absence of vowels, show its info and
            # continue.

            elif isinstance(cache_result, tuple) and cache_result[0] == 'exception':
                exception, traceback_string = cache_result[1:3]

                log.debug(
                    '{0} [CACHE {1}]: exception\n{2}\n{3}'.format(
                    row_str, cache_key, markup_url, sound_url))

                log.debug(traceback_string)

                exception_counter += 1

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    'Analyzing sound and markup')

                if (limit_exception and exception_counter >= limit_exception or
                    limit and index + 1 >= limit):
                    break

                continue

            # If we actually have the result, we use it and continue.

            elif cache_result:

                textgrid_result_list = cache_result
                filtered_result_list = result_filter(textgrid_result_list)

                log.debug(
                    '{0} [CACHE {1}]:\n{2}\n{3}\n{4}'.format(
                    row_str, cache_key, markup_url, sound_url,
                    format_textgrid_result(group_list, textgrid_result_list)))

                if maybe_tier_set:

                    log.debug('filtered result:\n{0}'.format(
                        format_textgrid_result(group_list, filtered_result_list)))

                # Acquiring another result, updating progress status, stopping earlier, if required.

                result_list.append((group_list, filtered_result_list))
                result_group_set.update(group_list)

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    'Analyzing sound and markup')

                if (limit_result and len(result_list) >= limit_result or
                    limit and index + 1 >= limit):
                    break

                continue

        # If we have an exception while processing cache results, we stop and terminate with error.

        except:
            task_status.set(4, 100,
                'Finished (ERROR), cache processing error')

            return {
                'error': 'cache processing error',
                'exception_counter': exception_counter,
                'no_vowel_counter': no_vowel_counter,
                'result_counter': len(result_list)}

        try:
            # Getting markup, checking for each tier if it needs to be processed.

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

                markup_url, sound_url = sound_url, markup_url

                with urllib.request.urlopen(urllib.parse.quote(markup_url, safe = '/:')) as markup_stream:
                    markup_bytes = markup_stream.read()

                textgrid = pympi.Praat.TextGrid(xmax = 0)

                textgrid.from_file(
                    io.BytesIO(markup_bytes),
                    codec = chardet.detect(markup_bytes)['encoding'])

            # Some helper functionis.

            def unusual_f(tier_number, tier_name, transcription, unusual_markup_dict):

                log.debug(
                    '{0}: tier {1} \'{2}\' has interval(s) with unusual transcription text: '
                    '{3} / {4}'.format(
                    row_str, tier_number, tier_name, transcription, unusual_markup_dict))

            def no_vowel_f(tier_number, tier_name, transcription_list):

                log.debug(
                    '{0}: tier {1} \'{2}\' doesn\'t have any vowel markup: {3}'.format(
                    row_str, tier_number, tier_name, transcription_list))

            def no_vowel_selected_f(tier_number, tier_name, transcription_list, selected_list):

                log.debug(
                    '{0}: tier {1} \'{2}\' intervals to be processed don\'t have any vowel markup: '
                    'markup {3}, selected {4}'.format(
                    row_str, tier_number, tier_name, transcription_list, selected_list))

            tier_data_list, vowel_flag = process_textgrid(
                textgrid, unusual_f, no_vowel_f, no_vowel_selected_f)

            # If there are no tiers with vowel markup, we skip this sound-markup pair altogether.

            if not vowel_flag:

                caching.CACHE.set(cache_key, 'no_vowel')
                no_vowel_counter += 1

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    'Analyzing sound and markup')

                if (limit_no_vowel and no_vowel_counter >= limit_no_vowel or
                    limit and index + 1 >= limit):
                    break

                continue

            # Otherwise we retrieve the sound file and analyze each vowel-containing markup.
            # Partially inspired by source code at scripts/convert_five_tiers.py:307.

            sound = None
            with tempfile.NamedTemporaryFile() as temp_file:

                with urllib.request.urlopen(urllib.parse.quote(sound_url, safe = '/:')) as sound_stream:
                    temp_file.write(sound_stream.read())
                    temp_file.flush()

                sound = AudioPraatLike(pydub.AudioSegment.from_wav(temp_file.name))

            textgrid_result_list = process_sound(tier_data_list, sound,
                row[3][:1] if only_first_translation else row[3])

            # Saving analysis results.

            filtered_result_list = result_filter(textgrid_result_list)

            result_list.append((group_list, filtered_result_list))
            result_group_set.update(group_list)

            caching.CACHE.set(cache_key, textgrid_result_list)

            # Showing results for this sound/markup pair, stopping earlier, if required.

            log.debug(
                '{0}:\n{1}\n{2}\n{3}'.format(
                row_str, markup_url, sound_url,
                format_textgrid_result(group_list, textgrid_result_list)))

            if maybe_tier_set:

                log.debug('filtered result:\n{0}'.format(
                    format_textgrid_result(group_list, filtered_result_list)))

            task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                'Analyzing sound and markup')

            if (limit_result and len(result_list) >= limit_result or
                limit and index + 1 >= limit):
                break

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
                '{0}: exception\n{1}\n{2}'.format(
                row_str, markup_url, sound_url))

            # if we encountered an exception, we show its info and remember not to try offending
            # sound/markup pair again.

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug(traceback_string)

            caching.CACHE.set(cache_key, ('exception', exception,
                traceback_string.replace('Traceback', 'CACHEd traceback')))

            exception_counter += 1

            task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                'Analyzing sound and markup')

            if (limit_exception and exception_counter >= limit_exception or
                limit and index + 1 >= limit):
                break

    log.debug('phonology {0}/{1}: {2} result{3}, {4} no vowels, {5} exceptions'.format(
        perspective_cid, perspective_oid,
        len(result_list), '' if len(result_list) == 1 else 's',
        no_vowel_counter, exception_counter))

    # If we have no results, we indicate the situation and also show number of failures and number of
    # markups with no vowels.

    if not result_list:

        task_status.set(4, 100,
            'Finished, no results produced')

        return {
            'error': 'no markups for this query',
            'exception_counter': exception_counter,
            'no_vowel_counter': no_vowel_counter}

    # Otherwise we create an Excel file with results.

    task_status.set(3, 99, 'Compiling results')
    workbook_stream = io.BytesIO()

    try:
        entry_count_dict, sound_count_dict, chart_stream_list = compile_workbook(
            vowel_selection, result_list, result_group_set, workbook_stream)

        workbook_stream.seek(0)

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
            'exception_counter': exception_counter,
            'no_vowel_counter': no_vowel_counter,
            'result_counter': len(result_list)}

    # Name(s) of the resulting file(s) includes dictionary name, perspective name and current date.

    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    result_filename = '{0} - {1} - {2:04d}.{3:02d}.{4:02d}'.format(
        dictionary_name[:64], perspective_name[:64],
        current_datetime.year,
        current_datetime.month,
        current_datetime.day)

    table_filename = sanitize_filename(result_filename + '.xlsx')

    cur_time = time()
    storage_dir = path.join(storage["path"], "phonology", str(cur_time))
    makedirs(storage_dir, exist_ok = True)

    # Storing file with the results.

    storage_path = path.join(storage_dir, table_filename)
    directory = path.dirname(storage_path)

    try:
        makedirs(directory)

    except OSError as exception:
        if exception.errno != EEXIST:
            raise

    workbook_stream.seek(0)

    # If the name of the result file is too long, we try again with a shorter name.

    try:
        with open(storage_path, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    except OSError as os_error:

        if os_error.errno != 36:
            raise

        result_filename = '{0} - {1} - {2:04d}.{3:02d}.{4:02d}'.format(
            dictionary_name[:32], perspective_name[:32],
            current_datetime.year,
            current_datetime.month,
            current_datetime.day)

        table_filename = sanitize_filename(result_filename + '.xlsx')
        storage_path = path.join(storage_dir, table_filename)

        with open(storage_path, 'wb+') as workbook_file:
            copyfileobj(workbook_stream, workbook_file)

    # Storing 3d F1/F2/F3 scatter charts, if we have any.

    chart_filename_list = []

    for chart_stream, group_string in chart_stream_list:

        filename = sanitize_filename(result_filename + group_string + '.png')
        storage_path = path.join(storage_dir, filename)

        chart_stream.seek(0)

        with open(storage_path, 'wb+') as chart_file:
            copyfileobj(chart_stream, chart_file)

        chart_filename_list.append(filename)

    # Successfully compiled phonology, finishing and returning links to files with results.

    url_list = [

        "".join([
            storage["prefix"],
            storage["static_route"],
            "phonology", '/',
            str(cur_time), '/',
            filename])

        for filename in [table_filename] + chart_filename_list]

    task_status.set(4, 100, 'Finished', result_link_list = url_list)


@view_config(route_name = 'phonology_tier_list', renderer = 'json')
def phonology_tier_list(request):
    """
    Gets a list of names of phonology markup tiers for a specified perspective.
    """

    try:
        perspective_cid = request.params.get('perspective_client_id')
        perspective_oid = request.params.get('perspective_object_id')

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

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}


@view_config(route_name = 'sound_and_markup', renderer = 'json')
def sound_and_markup(request):
    """
    Gets a list of names of phonology markup tiers for a specified perspective.

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

        log.debug('sound_and_markup {0}/{1}: {2}'.format(
            perspective_cid, perspective_oid, published_mode))

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

        # Sound/markup archiving task status setup.

        locale_id = int(request.cookies.get('locale_id') or 2)

        dictionary_name = dictionary_translation_gist.get_translation(locale_id)
        perspective_name = perspective_translation_gist.get_translation(locale_id)

        client_id = request.authenticated_userid

        user_id = (
            Client.get_user_by_client_id(client_id).id
                if client_id else anonymous_userid(request))

        task_status = TaskStatus(user_id,
            'Sound/markup archive compilation', '{0}: {1}'.format(dictionary_name, perspective_name), 3)

        # Performing either synchronous or asynchronous sound/markup archive compilation.

        request.response.status = HTTPOk.code

        task_key = task_status.key
        cache_kwargs = request.registry.settings["cache_kwargs"]
        sqlalchemy_url = request.registry.settings["sqlalchemy.url"]
        storage = request.registry.settings["storage"]

        return (std_sound_and_markup if 'synchronous' in request.params else async_sound_and_markup.delay)(
            task_key,
            perspective_cid, perspective_oid, published_mode,
            dictionary_name, perspective_name,
            cache_kwargs, storage, sqlalchemy_url)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('sound_and_markup: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(3, 100, 'Finished (ERROR), external error')

        request.response.status = HTTPInternalServerError.code
        return {'error': 'external error'}


def std_sound_and_markup(
    task_key,
    perspective_cid, perspective_oid, published_mode,
    dictionary_name, perspective_name,
    cache_kwargs, storage, sqlalchemy_url):
    """
    Synchronous sound/markup archive dictionary compilation, used for debugging.
    """

    task_status = TaskStatus.get_from_cache(task_key)

    try:
        return perform_sound_and_markup(
            perspective_cid, perspective_oid, published_mode,
            dictionary_name, perspective_name,
            task_status, storage)

    # Some unknown external exception.

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('sound_and_markup: exception')
        log.debug(traceback_string)

        if task_status is not None:
            task_status.set(3, 100, 'Finished (ERROR), external error')

        return {'error': 'external error'}


@celery.task
def async_sound_and_markup(
    task_key,
    perspective_cid, perspective_oid, published_mode,
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
                perspective_cid, perspective_oid, published_mode,
                dictionary_name, perspective_name,
                task_status, storage)

        # Some unknown external exception.

        except Exception as exception:

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug('sound_and_markup: exception')
            log.debug(traceback_string)

            if task_status is not None:
                task_status.set(3, 100, 'Finished (ERROR), external error')

            return {'error': 'external error'}


def perform_sound_and_markup(
    perspective_cid, perspective_oid, published_mode,
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

    data_type_query = DBSession.query(Field) \
        .join(TranslationGist,
              and_(Field.translation_gist_object_id == TranslationGist.object_id,
                   Field.translation_gist_client_id == TranslationGist.client_id)) \
        .join(TranslationGist.translationatom)

    field = data_type_query.filter(
        TranslationAtom.locale_id == 2,
        TranslationAtom.content == 'Translation').one()

    log.debug('translation field: ' + 
        ('None' if not field else '{0}/{1}'.format(field.client_id, field.object_id)))

    # Getting ready to gather list of currently available sound/markup pairs.

    Markup = aliased(Entity, name = 'Markup')
    Sound = aliased(Entity, name = 'Sound')
    Translation = aliased(Entity, name = 'Translation')

    PublishingMarkup = aliased(PublishingEntity, name = 'PublishingMarkup')
    PublishingSound = aliased(PublishingEntity, name = 'PublishingSound')
    PublishingTranslation = aliased(PublishingEntity, name = 'PublishingTranslation')

    if not field:

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

        # Filtering by publishing status, if required.

        if published_mode == 'published':

            data_query = data_query.filter(
                PublishingMarkup.published == True,
                PublishingSound.published == True)

    # Also gathering translations, if we have the translation field.

    else:
        data_query = DBSession.query(
            LexicalEntry, Markup, Sound, func.array_agg(Translation.content)).filter(
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
                PublishingSound.accepted == True,
                Translation.parent_client_id == LexicalEntry.client_id,
                Translation.parent_object_id == LexicalEntry.object_id,
                Translation.marked_for_deletion == False,
                Translation.field_client_id == field.client_id,
                Translation.field_object_id == field.object_id,
                PublishingTranslation.client_id == Translation.client_id,
                PublishingTranslation.object_id == Translation.object_id,
                PublishingTranslation.accepted == True)

        # Filtering by publishing status, if required.

        if published_mode == 'published':

            data_query = data_query.filter(
                PublishingMarkup.published == True,
                PublishingSound.published == True,
                PublishingTranslation.published == True)

        data_query = data_query.group_by(
            LexicalEntry.client_id, LexicalEntry.object_id,
            Markup.client_id, Markup.object_id,
            Sound.client_id, Sound.object_id)

    # Preparing for writing out sound/markup archive.

    storage_dir = path.join(storage['path'], 'sound_and_markup')
    makedirs(storage_dir, exist_ok = True)

    archive_name = sanitize_filename(
        '{0} - {1}.zip'.format(dictionary_name, perspective_name))

    archive_path = path.join(storage_dir, archive_name)

    def entity_filename_date(entity, translation):
        """
        Produces archive filename and archive timestamp for a sound or markup file from its entity.
        """

        url_path = urllib.parse.urlparse(entity.content).path

        filename = path.basename(url_path)
        extension = path.splitext(url_path)[1]

        name = sanitize_filename('{0}_{1}_{2}'.format(
            entity.client_id, entity.object_id,
            '{0}{1}'.format(translation, extension) if translation else filename))

        date = datetime.datetime.utcfromtimestamp(entity.created_at)
        return name, (date.year, date.month, date.day, date.hour, date.minute, date.second)

    def get_sound_markup_bytes(sound_url, markup_url):
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

            textgrid.from_file(
                io.BytesIO(markup_bytes),
                codec = chardet.detect(markup_bytes)['encoding'])

            return sound_bytes, markup_bytes

        except:

            # If we failed to parse TextGrid markup, we assume that sound and markup files were
            # accidentally swapped and try again.

            textgrid = pympi.Praat.TextGrid(xmax = 0)

            textgrid.from_file(
                io.BytesIO(sound_bytes),
                codec = chardet.detect(sound_bytes)['encoding'])

            return markup_bytes, sound_bytes

    if not path.exists(archive_path):

        # Ok, we are to simply generate new archive.

        total_count = data_query.count()
        task_status.set(2, 1, 'Processing sound and markup files')

        sound_name_set = set()

        with zipfile.ZipFile(archive_path, 'w') as archive_file:
            for index, row in enumerate(data_query.yield_per(100)):

                sound_url = row.Sound.content
                markup_url = row.Markup.content
                translation = row[3][0] if field and len(row[3]) > 0 else None

                row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(
                    index,
                    row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                    row.Sound.client_id, row.Sound.object_id,
                    row.Markup.client_id, row.Markup.object_id)

                log.debug('{0}: \'{1}\'\n{2}\n{3}'.format(
                    row_str, translation, sound_url, markup_url))

                # Getting sound and markup data.

                try:
                    sound_bytes, markup_bytes = get_sound_markup_bytes(sound_url, markup_url)

                # If we failed to get sound/markup data, we report why and go on to the next
                # sound/markup pair.

                except Exception as exception:

                    log.debug(
                        '{0}: exception\n{1}\n{2}'.format(
                        row_str, markup_url, sound_url))

                    traceback_string = ''.join(traceback.format_exception(
                        exception, exception, exception.__traceback__))[:-1]

                    log.debug(traceback_string)

                    task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
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

                # Another sound/markup pair is processed successfully.

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    'Archiving sound and markup')

    else:
        # Updating existing archive, we start with gathering info of sound and markup files which should end
        # up in the archive.

        update_list = []
        update_set = set()

        for index, row in enumerate(data_query.yield_per(100)):

            translation = row[3][0] if field and len(row[3]) > 0 else None

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

        # Checking what files are already in the archive, which archive entries should be deleted and which
        # files should be added to the archive.

        with zipfile.ZipFile(archive_path, 'r') as archive_file:
            zip_info_list = archive_file.infolist()

        already_set = set(zip_info.filename
            for zip_info in zip_info_list)

        delete_set = already_set - update_set
        add_set = update_set - already_set

        # If none of the files in the archive should be deleted and we have some new files, we just add them
        # to the archive.

        if len(delete_set) <= 0 and len(add_set) > 0:
            with zipfile.ZipFile(archive_path, 'a') as archive_file:

                sound_name_set = set()
                add_count = 0

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
                        sound_bytes, markup_bytes = get_sound_markup_bytes(sound_url, markup_url)

                    # If we failed to get sound/markup data, we report why and go on to the next
                    # sound/markup pair.

                    except Exception as exception:

                        log.debug(
                            '{0}: exception\n{1}\n{2}'.format(
                            row_str, markup_url, sound_url))

                        traceback_string = ''.join(traceback.format_exception(
                            exception, exception, exception.__traceback__))[:-1]

                        log.debug(traceback_string)

                        task_status.set(2, 1 + int(math.floor((index + 1) * 99 / len(update_list))),
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

                    # Another sound/markup pair is processed successfully.

                    task_status.set(2, 1 + int(math.floor((index + 1) * 99 / len(update_list))),
                        'Archiving sound and markup')

        # If we have to delete some files from the archive, we just overwrite it completely.

        elif len(delete_set) > 0:
            with zipfile.ZipFile(archive_path, 'w') as archive_file:

                sound_name_set = set()

                for (index,
                    lexicalentry_cid, lexicalentry_oid,
                    sound_cid, sound_oid,
                    markup_cid, markup_oid,
                    sound_url, markup_url, translation,
                    sound_name, sound_date, markup_name, markup_date) in update_list:

                    row_str = ('{0} (LexicalEntry {1}/{2}, '
                        'sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(index,
                        lexicalentry_cid, lexicalentry_oid, sound_cid, sound_oid, markup_cid, markup_oid))

                    log.debug('{0}: \'{1}\'\n{2}\n{3}'.format(
                        row_str, translation, sound_url, markup_url))

                    # Getting sound and markup data.

                    try:
                        sound_bytes, markup_bytes = get_sound_markup_bytes(sound_url, markup_url)

                    # If we failed to get sound/markup data, we report why and go on to the next
                    # sound/markup pair.

                    except Exception as exception:

                        log.debug(
                            '{0}: exception\n{1}\n{2}'.format(
                            row_str, markup_url, sound_url))

                        traceback_string = ''.join(traceback.format_exception(
                            exception, exception, exception.__traceback__))[:-1]

                        log.debug(traceback_string)

                        task_status.set(2, 1 + int(math.floor((index + 1) * 99 / len(update_list))),
                            'Archiving sound and markup')

                        continue

                    # Archiving sound data, unless we already processed this sound entity, which can happen
                    # if it has multiple markup entities.

                    if sound_name not in sound_name_set:
                        sound_name_set.add(sound_name)

                        zip_info = zipfile.ZipInfo(sound_name, sound_date)
                        if sndhdr.test_wav(sound_bytes, io.BytesIO(sound_bytes)):
                            zip_info.compress_type = zipfile.ZIP_DEFLATED

                        archive_file.writestr(zip_info, sound_bytes)

                    # Archiving markup data.

                    archive_file.writestr(zipfile.ZipInfo(markup_name, markup_date), markup_bytes,
                        zipfile.ZIP_DEFLATED)

                    # Another sound/markup pair is processed successfully.

                    task_status.set(2, 1 + int(math.floor((index + 1) * 99 / len(update_list))),
                        'Archiving sound and markup')

        # We don't have to delete any files, and we don't have to add any files, we leave the archive
        # unchanged and indicate that it is fully ready.

        else:
            task_status.set(2, 100, 'Archiving sound and markup')

    # Successfully compiled sound/markup archive, finishing and returning link to the archive.

    archive_url = ''.join([
        storage['prefix'],
        storage['static_route'],
        'sound_and_markup', '/', archive_name])

    task_status.set(3, 100, 'Finished', result_link = archive_url)


def cpu_time(reference_cpu_time = 0.0):
    """
    Returns current or elapsed value of CPU time used by the process,
    including both user and system CPU time of both the process itself and
    its children.
    """

    return sum(os.times()[:4]) - reference_cpu_time


def test_alpha():
    """
    Tests that intensity and formant computation works.
    """

    markup_bytes = open('корень_БИН_(1_раз).TextGrid', 'rb').read()

    textgrid = pympi.Praat.TextGrid(xmax = 0)
    textgrid.from_file(
        io.BytesIO(markup_bytes),
        codec = chardet.detect(markup_bytes)['encoding'])

    raw_interval_list = textgrid.get_tier(1).get_all_intervals()
    interval_list = []
    long_text_flag = False

    interval_idx_to_raw_idx = dict()

    # Compiling transcription, checking if we have unusual markup.

    for raw_index, interval in enumerate(raw_interval_list):

        if len(interval[2]) <= 2 \
                and len(interval[2].strip()) \
                and any(character in vowel_set for character in interval[2]):

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


def test_profile():
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
                textgrid.from_file(
                    io.BytesIO(markup_bytes),
                    codec = chardet.detect(markup_bytes)['encoding'])

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


def main_praat_escape():
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

if __name__ == '__main__':
    main_praat_escape()

