
# Standard library imports.

import collections
import datetime
import io
import logging
import math
import re
import string
import tempfile
import traceback

import urllib.request
import urllib.parse

# External imports.

import cchardet as chardet

import numpy
import numpy.fft
import numpy.linalg
import numpy.polynomial

import pydub
from pydub.utils import ratio_to_db

import pympi

from pyramid.httpexceptions import HTTPInternalServerError, HTTPPreconditionFailed
from pyramid.request import Request
from pyramid.response import FileIter, Response
from pyramid.view import view_config

import scipy.linalg

from sqlalchemy import (and_,)
from sqlalchemy.orm import aliased

import xlsxwriter

# Project imports.

from lingvodoc.cache.caching import CACHE, TaskStatus

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
)


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

    raise "Unimplemented."


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

        # Memoizing and returning first two formants.

        formant_list.sort()
        self.formant_list[step_index] = formant_list[:2]

        return formant_list[:2]

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

        f1_list = []
        f2_list = []

        for step_index in range(begin_step, end_step + 1):
            f1, f2 = self.get_formants(step_index)

            f1_list.append(f1)
            f2_list.append(f2)

        f1_list.sort()
        f2_list.sort()

        # Computing interval formant values as means (without highest and lowest values, if possible) and
        # medians of point formant values.

        step_count = end_step - begin_step + 1

        f1_mean = (
            sum(f1_list) / step_count if step_count <= 2 else
            sum(f1_list[1:-1]) / (step_count - 2))

        f2_mean = (
            sum(f2_list) / step_count if step_count <= 2 else
            sum(f2_list[1:-1]) / (step_count - 2))

        half_step_count = step_count // 2

        f1_median = (
            f1_list[half_step_count] if step_count & 1 == 1 else
            (f1_list[half_step_count - 1] + f1_list[half_step_count]) / 2)

        f2_median = (
            f2_list[half_step_count] if step_count & 1 == 1 else
            (f2_list[half_step_count - 1] + f2_list[half_step_count]) / 2)

        # Trying computation on just the middle third of the interval.

        third_step_count = step_count // 3

        f1_list = (
            f1_list[third_step_count : -third_step_count] if step_count % 3 < 2 else
            f1_list[third_step_count + 1 : -third_step_count - 1])

        f2_list = (
            f2_list[third_step_count : -third_step_count] if step_count % 3 < 2 else
            f2_list[third_step_count + 1 : -third_step_count - 1])

        return [f1_mean, f2_mean, f1_median, f2_median,
            sum(f1_list) / len(f1_list), sum(f2_list) / len(f2_list)]

        return f1_mean, f2_mean, f1_median, f2_median


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
vowel_set = set('AEIOUYaeiouyÄÆÉØäæéøŒœƆƏƐƗƜƟƱɄɅɐɑɒɔɘəɛɜɞɤɨɪɯɵɶʉʊʌʏ̞̈̽АОаоⱭⱯⱰꞫ')


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


def process_textgrid(textgrid, unusual_f, no_vowel_f, no_vowel_selected_f):
    """
    Processes TextGrid markup, checking for each tier if it should be analyzed.
    """

    tier_data_list = []
    vowel_flag = False

    for tier_number, tier_name in textgrid.get_tier_name_num():

        raw_interval_list = textgrid.get_tier(tier_number).get_all_intervals()
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


def process_sound(tier_data_list, sound, translation = None):
    """
    Analyzes sound intervals corresponding to vowel-containing markup.
    """

    textgrid_result_list = []

    for tier_number, tier_name, tier_data in tier_data_list:

        if tier_data == 'no_vowel' or tier_data == 'no_vowel_selected':
            textgrid_result_list.append((tier_number, tier_name, tier_data))
            continue

        # Analyzing vowel sounds of each interval sequence.

        (raw_interval_list, raw_interval_seq_list, interval_seq_list, interval_idx_to_raw_idx,
            transcription) = tier_data

        textgrid_result_list.append((tier_number, tier_name, []))

        for seq_index, (raw_interval_list, interval_list) in enumerate(zip(
            raw_interval_seq_list, interval_seq_list)):

            if len(interval_list) <= 0:
                continue

            (max_intensity_index, max_intensity, max_length_index, max_length) = \
                find_max_interval_praat(sound, interval_list)

            max_intensity_interval = interval_list[max_intensity_index]
            max_length_interval = interval_list[max_length_index]

            max_intensity_f1_f2 = sound.get_interval_formants(*max_intensity_interval[:2])
            max_length_f1_f2 = sound.get_interval_formants(*max_length_interval[:2])

            # Compiling results.

            max_length_str = '{0} {1:.3f} [{2}]'.format(
                max_length_interval[2], max_length,
                len(''.join(text for index, (begin, end, text) in
                    raw_interval_list[:interval_idx_to_raw_idx[seq_index][max_length_index]])))

            max_intensity_str = '{0} {1:.3f} [{2}]'.format(
                max_intensity_interval[2],
                max_intensity,
                len(''.join(text for index, (begin, end, text) in
                    raw_interval_list[:interval_idx_to_raw_idx[seq_index][max_intensity_index]])))

            textgrid_result_list[-1][2].append([
                ''.join(text for index, (begin, end, text) in raw_interval_list),
                translation,
                max_length_str,
                '{0:.3f}'.format(max_length_f1_f2[0]),
                '{0:.3f}'.format(max_length_f1_f2[1]),
                '{0:.3f}'.format(max_length_f1_f2[2]),
                '{0:.3f}'.format(max_length_f1_f2[3]),
                '{0:.3f}'.format(max_length_f1_f2[4]),
                '{0:.3f}'.format(max_length_f1_f2[5]),
                max_intensity_str,
                '{0:.3f}'.format(max_intensity_f1_f2[0]),
                '{0:.3f}'.format(max_intensity_f1_f2[1]),
                '{0:.3f}'.format(max_intensity_f1_f2[2]),
                '{0:.3f}'.format(max_intensity_f1_f2[3]),
                '{0:.3f}'.format(max_intensity_f1_f2[4]),
                '{0:.3f}'.format(max_intensity_f1_f2[5]),
                '+' if max_intensity_index == max_length_index else '-'])

    return textgrid_result_list


def format_textgrid_result(group_list, textgrid_result_list):
    """
    A little helper function for formatting sound/markup analysis results.
    """

    return '\n'.join(
        ['groups: {0}'.format(group_list)] +
        ['tier {0} \'{1}\': {2}'.format(tier_number, tier_name,
            
            tier_result_list if not isinstance(tier_result_list, list) else
            tier_result_list[0] if len(tier_result_list) <= 1 else
            ''.join('\n  {0}'.format(tier_result) for tier_result in tier_result_list))

            for tier_number, tier_name, tier_result_list in textgrid_result_list])


def compile_workbook(result_list, result_group_set, workbook_stream):
    """
    Compiles analysis results into an Excel workbook.
    """

    workbook = xlsxwriter.Workbook(workbook_stream, {'in_memory': True})

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

        worksheet_results = workbook.add_worksheet('Results' + group_name_string)
        worksheet_results.write_row('A1', [
            'Transcription',
            'Translation',
            'Longest (seconds) interval',
            'F1 mean (Hz)', 'F2 mean (Hz)',
        #   'F1 median (Hz)', 'F2 median (Hz)',
        #   'F1 third (Hz)', 'F2 third (Hz)',
            'Highest intensity (dB) interval',
            'F1 mean (Hz)', 'F2 mean (Hz)',
        #   'F1 median (Hz)', 'F2 median (Hz)',
        #   'F1 third (Hz)', 'F2 third (Hz)',
            'Coincidence'])

        # Formatting column widths.

        worksheet_results.set_column(0, 2, 26)
        worksheet_results.set_column(3, 4, 13)
        worksheet_results.set_column(5, 5, 26)
        worksheet_results.set_column(6, 8, 13)

        worksheet_dict[group] = (worksheet_results,
            workbook.add_worksheet('F-table' + group_name_string),
            workbook.add_worksheet('F-chart' + group_name_string))

    row_counter_dict = {group: 2 for group in result_group_set}
    sound_counter_dict = {group: 0 for group in result_group_set}

    vowel_formant_dict = {group: collections.defaultdict(list) for group in result_group_set}

    # Filling in analysis results.

    for textgrid_group_list, textgrid_result_list in result_list:
        for tier_number, tier_name, tier_result in textgrid_result_list:

            if tier_result == 'no_vowel' or tier_result == 'no_vowel_selected':
                continue

            for tier_data in tier_result:

                row_list = (tier_data[:3] +
                    list(map(float, tier_data[3:5])) + [tier_data[9]] +
                    list(map(float, tier_data[10:12])) + [tier_data[16]])

                for group in textgrid_group_list:
                    worksheet_dict[group][0].write_row('A' + str(row_counter_dict[group]), row_list)

                    row_counter_dict[group] += 1
                    sound_counter_dict[group] += 1

                # Collecting vowel formant data.

                text_a, f1_f2_list_a = tier_data[2], tier_data[3:5]
                text_b, f1_f2_list_b = tier_data[9], tier_data[10:12]

                text_a_list = text_a.split()
                text_b_list = text_b.split()

                vowel_a = ''.join(filter(lambda character: character in vowel_set, text_a_list[0]))
                vowel_b = ''.join(filter(lambda character: character in vowel_set, text_b_list[0]))

                for group in textgrid_group_list:
                    vowel_formant_dict[group][vowel_a].append(tuple(map(float, f1_f2_list_a)))

                if text_b_list[2] != text_a_list[2]:
                    for group in textgrid_group_list:

                        sound_counter_dict[group] += 1
                        vowel_formant_dict[group][vowel_b].append(tuple(map(float, f1_f2_list_b)))

    # And now we will produce F1/F2 scatter charts for all sufficiently frequent analysed vowels of all
    # result groups.

    for group in group_list:
        worksheet_table, worksheet_chart = worksheet_dict[group][1:3]

        vowel_formant_list = []

        for vowel, f1_f2_list in sorted(vowel_formant_dict[group].items()):
            f1_f2_list = list(set(f1_f2_list))

            if len(f1_f2_list) >= 8:
                vowel_formant_list.append((vowel, list(map(numpy.array, f1_f2_list))))

        # Compiling data of formant value series by filtering F1/F2 2-vectors by Mahalonobis distance.

        chart_data_list = []

        min_f1, max_f1 = None, None
        min_f2, max_f2 = None, None

        for index, (vowel, f1_f2_list) in enumerate(vowel_formant_list):

            mean = sum(f1_f2_list) / len(f1_f2_list)
            sigma = numpy.cov(numpy.array(f1_f2_list).T)
            inverse = numpy.linalg.inv(sigma)

            distance_list = []
            for f1_f2 in f1_f2_list:

                # Calculation of squared Mahalanobis distance inspired by the StackOverflow answer
                # http://stackoverflow.com/q/27686240/2016856.

                delta = f1_f2 - mean
                distance_list.append((numpy.einsum('n,nk,k->', delta, inverse, delta), f1_f2))

            distance_list.sort()

            # Trying to produce one standard deviation ellipse.

            sigma_one_two = scipy.linalg.sqrtm(sigma)
            ellipse_list = []

            for i in range(64 + 1):
                phi = 2 * math.pi * i / 64

                ellipse_list.append(
                    mean + numpy.dot(numpy.array([math.cos(phi), math.sin(phi)]), sigma_one_two))

            # Splitting F1/F2 vectors into these that are close enough to the mean and the outliers.

            filtered_list = []
            outlier_list = []

            for distance_squared, f1_f2 in distance_list:
                if distance_squared <= 2:
                    filtered_list.append(f1_f2)
                else:
                    outlier_list.append(f1_f2)

            if len(filtered_list) < len(distance_list) // 2:
                f1_f2_list = [f1_f2 for distance_squared, f1_f2 in distance_list]

                filtered_list = f1_f2_list[:len(distance_list) // 2]
                outlier_list = f1_f2_list[len(distance_list) // 2:]

            chart_data_list.append((
                len(filtered_list), len(f1_f2_list), vowel,
                filtered_list, outlier_list, mean, ellipse_list))

            # Updating F1/F2 maximum/minimum info.

            f1_list, f2_list = zip(*filtered_list)

            min_f1_list, max_f1_list = min(f1_list), max(f1_list)

            if min_f1 == None or min_f1_list < min_f1:
                min_f1 = min_f1_list

            if max_f1 == None or max_f1_list > max_f1:
                max_f1 = max_f1_list

            min_f2_list, max_f2_list = min(f2_list), max(f2_list)

            if min_f2 == None or min_f2_list < min_f2:
                min_f2 = min_f2_list

            if max_f2 == None or max_f2_list > max_f2:
                max_f2 = max_f2_list

        # Compiling info of the formant scatter chart data series, unless we actually don't have any.

        if len(chart_data_list) <= 0:
            continue

        chart_dict_list = []

        column_list = list(string.ascii_uppercase) + [c1 + c2
            for c1 in string.ascii_uppercase
            for c2 in string.ascii_uppercase]

        shape_list = ['square', 'diamond', 'triangle', 'x', 'star', 'short_dash', 'long_dash', 'circle',
            'plus']

        color_list = ['black', 'blue', 'brown', 'green', 'navy', 'purple', 'red', 'orange', 'gray', 'cyan',
            'lime', 'magenta', 'silver', 'yellow']

        # It seems that we have to plot data in order of its size, from vowels with least number of F1/F2 points
        # to vowels with the most number of F1/F2 points, otherwise scatter chart fails to generate properly.

        chart_data_list.sort(reverse = True)

        max_f1_f2_list_length = max(len(f1_f2_list)
            for count, total_count, vowel, f1_f2_list, outlier_list, mean, ellipse_list in chart_data_list)

        heading_list = []
        for count, total_count, vowel, f1_f2_list, outlier_list, mean, ellipse_list in chart_data_list:
            heading_list.extend(['{0} F1'.format(vowel), '{0} F2'.format(vowel)])

        worksheet_table.write_row('A1', heading_list)
        worksheet_table.write_row('A2', ['main part', ''] * len(chart_data_list))

        # Removing outliers that outlie too much.

        f1_limit = max_f1 + min_f1 / 2
        f2_limit = max_f2 + min_f2 / 2

        for i in range(len(chart_data_list)):
            chart_data_list[i] = list(chart_data_list[i])

            chart_data_list[i][4] = list(filter(
                lambda f1_f2: f1_f2[0] <= f1_limit and f1_f2[1] <= f2_limit,
                chart_data_list[i][4]))

        max_outlier_list_length = max(len(outlier_list)
            for count, total_count, vowel, f1_f2_list, outlier_list, mean, ellipse_list in chart_data_list)

        # Writing out chart data and compiling chart data series info.

        for index, (count, total_count, vowel,
            f1_f2_list, outlier_list, mean, ellipse_list) in enumerate(chart_data_list):

            f1_list, f2_list = zip(*f1_f2_list)

            f1_outlier_list, f2_outlier_list = zip(*outlier_list)
            x1_ellipse_list, x2_ellipse_list = zip(*ellipse_list)

            f1_column = column_list[index * 2]
            f2_column = column_list[index * 2 + 1]

            # Writing out formant data.

            worksheet_table.write(f1_column + '3',
                '{0}/{1} ({2:.1f}%) points'.format(
                    count, total_count, 100.0 * count / total_count))

            worksheet_table.write_column(f1_column + '4',
                list(f1_list) +
                [''] * (max_f1_f2_list_length - len(f1_list)) +
                [vowel + ' outliers', '{0}/{1} ({2:.1f}%) points'.format(
                    len(outlier_list), total_count, 100.0 * len(outlier_list) / total_count)] +
                list(f1_outlier_list) +
                [''] * (max_outlier_list_length - len(f1_outlier_list)) +
                [vowel + ' mean', mean[0], vowel + ' stdev ellipse'] +
                list(x1_ellipse_list))

            worksheet_table.write_column(f2_column + '4',
                list(f2_list) +
                [''] * (max_f1_f2_list_length - len(f2_list)) +
                ['', ''] + list(f2_outlier_list) +
                [''] * (max_outlier_list_length - len(f2_outlier_list)) +
                ['', mean[1], ''] + list(x2_ellipse_list))

            worksheet_table.set_column(index * 2, index * 2 + 1, 11)

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
                    max_f1_f2_list_length + 6, max_f1_f2_list_length + len(f2_outlier_list) + 5),
                'values': '=\'F-table{0}\'!${1}${2}:${1}${3}'.format(
                    group_name_string, f1_column,
                    max_f1_f2_list_length + 6, max_f1_f2_list_length + len(f1_outlier_list) + 5),
                'marker': {
                    'type': 'circle',
                    'size': 2,
                    'border': {'color': color},
                    'fill': {'color': color}}})

            # Mean data point.

            shift = max_f1_f2_list_length + max_outlier_list_length

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

    workbook.close()

    entity_counter_dict = {group: row_counter - 2
        for group, row_counter in row_counter_dict.items()}

    return (entity_counter_dict, sound_counter_dict)


@view_config(route_name="phonology", renderer='json')
def phonology(request):
    """
    Computes phonology of a specified perspective.

    Perspective is specified by request parameters 'perspective_client_id' and 'perspective_object_id',
    example of a request: /phonology?perspective_client_id=345&perspective_object_id=2.
    """

    perspective_cid = request.params.get('perspective_client_id')
    perspective_oid = request.params.get('perspective_object_id')

    group_by_description = request.params.get('group_by_description')

    # Phonology task status setup.

    locale_id = int(request.cookies.get('locale_id') or 2)

    client_id = request.authenticated_userid
    user_id = 0 if not client_id else Client.get_user_by_client_id(client_id).id

    perspective = DBSession.query(DictionaryPerspective).filter_by(
        client_id = perspective_cid, object_id = perspective_oid).first()

    perspective_translation_gist = DBSession.query(TranslationGist).filter_by(
        client_id = perspective.translation_gist_client_id,
        object_id = perspective.translation_gist_object_id).first()

    task_status = TaskStatus(user_id,
        "Phonology compilation", perspective_translation_gist.get_translation(locale_id), 4)

    task_status.set(1, 0, "Preparing")

    # We also get perspective's dictionary data.

    dictionary = DBSession.query(Dictionary).filter_by(
        client_id = perspective.parent_client_id,
        object_id = perspective.parent_object_id).first()

    dictionary_translation_gist = DBSession.query(TranslationGist).filter_by(
        client_id = dictionary.translation_gist_client_id,
        object_id = dictionary.translation_gist_object_id).first()

    # Getting 'Translation' field ids.

    subrequest = Request.blank('/translation_search')

    subrequest.method = 'POST'
    subrequest.headers = {}
    subrequest.json = {'searchstring': 'Translation'}

    if request.headers.get('Cookie'):
        subrequest.headers = {'Cookie': request.headers['Cookie']}

    response = request.invoke_subrequest(subrequest)

    field_translation_gist_client_id = None
    field_translation_gist_object_id = None

    # Looking through all translations we've got, getting field translation data.

    for gist_data in response.json:

        if gist_data['type'] != 'Field':
            continue

        for atom_data in gist_data['contains']:
            if atom_data['locale_id'] == 2 and atom_data['content'] == 'Translation':

                field_translation_gist_client_id = gist_data['client_id']
                field_translation_gist_object_id = gist_data['object_id']
                break

    if not field_translation_gist_client_id or not field_translation_gist_object_id:
        raise Exception('Missing \'Translation\' field data.')

    # Finding required field by its translation.

    field = DBSession.query(Field).filter_by(
        translation_gist_client_id = field_translation_gist_client_id,
        translation_gist_object_id = field_translation_gist_object_id).first()

    if not field:
        raise Exception('Missing \'Translation\' field.')

    # Checking if we have limits on number of computed results.

    limit = (None if 'limit' not in request.params else
        int(request.params.get('limit')))

    limit_exception = (None if 'limit_exception' not in request.params else
        int(request.params.get('limit_exception')))

    limit_no_vowel = (None if 'limit_no_vowel' not in request.params else
        int(request.params.get('limit_no_vowel')))

    limit_result = (None if 'limit_result' not in request.params else
        int(request.params.get('limit_result')))

    # Before everything else we should count how many sound/markup pairs we are to process.

    Markup = aliased(Entity, name = "Markup")
    Sound = aliased(Entity, name = "Sound")
    Translation = aliased(Entity, name = "Translation")
    PublishingSound = aliased(PublishingEntity, name = "PublishingSound")

    count_query = DBSession.query(
        LexicalEntry, Markup, Sound, PublishingEntity, PublishingSound).filter(and_(
            LexicalEntry.parent_client_id == perspective_cid,
            LexicalEntry.parent_object_id == perspective_oid,
            LexicalEntry.marked_for_deletion == False,
            Markup.parent_client_id == LexicalEntry.client_id,
            Markup.parent_object_id == LexicalEntry.object_id,
            Markup.marked_for_deletion == False,
            Markup.additional_metadata.contains({"data_type": "praat markup"}),
            PublishingEntity.client_id == Markup.client_id,
            PublishingEntity.object_id == Markup.object_id,
            PublishingEntity.published == True,
            PublishingEntity.accepted == True,
            Sound.client_id == Markup.self_client_id,
            Sound.object_id == Markup.self_object_id,
            Sound.marked_for_deletion == False,
            PublishingSound.client_id == Sound.client_id,
            PublishingSound.object_id == Sound.object_id,
            PublishingSound.published == True,
            PublishingSound.accepted == True))

    total_count = count_query.count()
    task_status.set(2, 1, "Analyzing sound and markup")

    # We get lexical entries of the perspective with markup'ed sounds, and possibly with translations.

    data_query = count_query.outerjoin(Translation, and_(
        LexicalEntry.client_id == Translation.parent_client_id,
        LexicalEntry.object_id == Translation.parent_object_id)).filter(and_(
            Translation.field_client_id == field.client_id,
            Translation.field_object_id == field.object_id)).add_entity(Translation)

    exception_counter = 0
    no_vowel_counter = 0

    result_list = list()
    result_group_set = set()

    # We process these lexical entries in batches. Just in case, it seems that perspectives rarely have more
    # then several hundred such lexical entries.

    for index, row in enumerate(data_query.yield_per(100)):

        markup_url = row.Markup.content
        sound_url = row.Sound.content

        row_str = '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6})'.format(index,
            row.LexicalEntry.client_id, row.LexicalEntry.object_id,
            row.Sound.client_id, row.Sound.object_id,
            row.Markup.client_id, row.Markup.object_id)

        cache_key = 'phonology:{0}:{1}:{2}:{3}'.format(
            row.Sound.client_id, row.Sound.object_id,
            row.Markup.client_id, row.Markup.object_id)

        # Checking if we have cached result for this pair of sound/markup.

        cache_result = CACHE.get(cache_key)

        try:
            if cache_result == 'no_vowel':

                log.debug('{0} [CACHE {1}]: no vowels\n{2}\n{3}'.format(
                    row_str, cache_key, markup_url, sound_url))

                no_vowel_counter += 1

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    "Analyzing sound and markup")

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
                    "Analyzing sound and markup")

                if (limit_exception and exception_counter >= limit_exception or
                    limit and index + 1 >= limit):
                    break

                continue

            # If we actually have the result, we use it and continue.

            elif cache_result:
                group_list, textgrid_result_list = cache_result

                log.debug(
                    '{0} [CACHE {1}]:\n{2}\n{3}\n{4}'.format(
                    row_str, cache_key, markup_url, sound_url,
                    format_textgrid_result(group_list, textgrid_result_list)))

                result_list.append(cache_result)
                result_group_set.update(group_list)

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    "Analyzing sound and markup")

                if (limit_result and len(result_list) >= limit_result or
                    limit and index + 1 >= limit):
                    break

                continue

        # If we have an exception while processing cache results, we stop and terminate with error.

        except:
            request.response.status = HTTPInternalServerError.code

            task_status.set(4, 100,
                "Finished (ERROR), cache processing error")

            return {
                "error": "cache processing error",
                "exception_counter": exception_counter,
                "no_vowel_counter": no_vowel_counter,
                "result_counter": len(result_list)}

        try:
            # Getting markup, checking for each tier if it needs to be processed.

            markup_bytes = urllib.request.urlopen(urllib.parse.quote(markup_url, safe = '/:')).read()

            textgrid = pympi.Praat.TextGrid(xmax = 0)
            textgrid.from_file(
                io.BytesIO(markup_bytes),
                codec = chardet.detect(markup_bytes)['encoding'])

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

                CACHE.set(cache_key, 'no_vowel')
                no_vowel_counter += 1

                task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                    "Analyzing sound and markup")

                if (limit_no_vowel and no_vowel_counter >= limit_no_vowel or
                    limit and index + 1 >= limit):
                    break

                continue

            # Otherwise we retrieve the sound file and analyze each vowel-containing markup.
            # Partially inspired by source code at scripts/convert_five_tiers.py:307.

            sound = None
            with tempfile.NamedTemporaryFile() as temp_file:

                sound_file = urllib.request.urlopen(urllib.parse.quote(sound_url, safe = '/:'))
                temp_file.write(sound_file.read())
                temp_file.flush()

                sound = AudioPraatLike(pydub.AudioSegment.from_wav(temp_file.name))

            textgrid_result_list = process_sound(tier_data_list, sound,
                row.Translation.content if row.Translation else None)

            # Saving analysis results.

            group_list = [None]

            if group_by_description == 'true' and 'blob_description' in row.Markup.additional_metadata:
                group_list.append(row.Markup.additional_metadata['blob_description'])

                print(row.Markup.additional_metadata['blob_description'])
                print(row.Sound.additional_metadata['blob_description'])

            result_list.append((group_list, textgrid_result_list))
            result_group_set.update(group_list)

            CACHE.set(cache_key, (group_list, textgrid_result_list))

            # Showing results for this sound/markup pair, stopping earlier, if required.

            log.debug(
                '{0}:\n{1}\n{2}\n{3}'.format(
                row_str, markup_url, sound_url,
                format_textgrid_result(group_list, textgrid_result_list)))

            task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                "Analyzing sound and markup")

            if (limit_result and len(result_list) >= limit_result or
                limit and index + 1 >= limit):
                break

        except Exception as exception:

            #
            # NOTE
            #
            # Exceptional situations encountered so far:
            #
            #   1. TextGrid file actually contains sound, and wav file actually contains textgrid markup.
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

            CACHE.set(cache_key, ('exception', exception,
                traceback_string.replace('Traceback', 'CACHEd traceback')))

            exception_counter += 1

            task_status.set(2, 1 + int(math.floor((index + 1) * 99 / total_count)),
                "Analyzing sound and markup")

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
        request.response.status = HTTPPreconditionFailed.code

        task_status.set(4, 100,
            "Finished, no results produced")

        return {
            "error": "no markups for this query",
            "exception_counter": exception_counter,
            "no_vowel_counter": no_vowel_counter}

    # Otherwise we create and then serve Excel file.

    task_status.set(3, 99, "Compiling results")
    workbook_stream = io.BytesIO()

    try:
        entry_count_dict, sound_count_dict = compile_workbook(
            result_list, result_group_set, workbook_stream)

        workbook_stream.seek(0)

    except Exception as exception:

        traceback_string = ''.join(traceback.format_exception(
            exception, exception, exception.__traceback__))[:-1]

        log.debug('compile_workbook: exception')
        log.debug(traceback_string)

        # If we failed to create an Excel file, we terminate with error.

        request.response.status = HTTPInternalServerError.code

        task_status.set(4, 100,
            "Finished (ERROR), result compilation error")

        return {
            "error": "result compilation error",
            "exception_counter": exception_counter,
            "no_vowel_counter": no_vowel_counter,
            "result_counter": len(result_list)}

    # Name of the resulting file includes dictionary name, perspective name and current date.

    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    result_filename = '{0} - {1} - {2:04d}.{3:02d}.{4:02d}.xlsx'.format(
        dictionary_translation_gist.get_translation(2),
        perspective_translation_gist.get_translation(2),
        current_datetime.year,
        current_datetime.month,
        current_datetime.day)

    # See http://stackoverflow.com/questions/2937465/what-is-correct-content-type-for-excel-files for Excel
    # content-type.

    task_status.set(4, 100, "Finished")

    response = Response(content_type =
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    response.app_iter = FileIter(workbook_stream)
    response.headers['Content-Disposition'] = 'attachment; filename="{0}"'.format(result_filename)

    return response


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

    data_dir_list = list(map(os.path.realpath, sys.argv[1].split(',')))

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
        for wav_path in sorted(glob.glob(os.path.join(data_dir, 'phonology:*.wav'))):

            match = re.match('phonology:(\d+):(\d+):(\d+):(\d+)_.*', os.path.basename(wav_path))
            id_tuple = tuple(map(int, match.groups()))

            wav_dict[id_tuple] = wav_path

        # Analyzing markup files one by one.

        result_list = []
        result_limit = None if len(sys.argv) < 3 else int(sys.argv[2])

        for index, textgrid_path in enumerate(sorted(
            glob.glob(os.path.join(data_dir, 'phonology:*.TextGrid')))):

            # Getting sound-markup pair data.

            match = re.match('phonology:(\d+):(\d+):(\d+):(\d+)_(.*)', os.path.basename(textgrid_path))
            id_tuple = tuple(map(int, match.groups()[:4]))
            textgrid_name = match.group(5)

            wav_path = wav_dict[id_tuple]
            match = re.match('phonology:(\d+):(\d+):(\d+):(\d+)_(.*)', os.path.basename(wav_path))
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

        with open(os.path.join(data_dir, 'result.xlsx'), 'wb') as result_file:
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


# A little bit of local testing.

if __name__ == '__main__':
    test_profile()

