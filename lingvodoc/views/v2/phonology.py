
# Standard library imports.

import io
import logging
import math
import re
import tempfile
import traceback

import urllib.request
import urllib.parse

# External imports.

import cchardet as chardet

import numpy
import numpy.polynomial

import pydub
from pydub.utils import ratio_to_db

import pympi

from pyramid.httpexceptions import HTTPPreconditionFailed
from pyramid.response import FileIter, Response
from pyramid.view import view_config

from sqlalchemy import (and_,)
from sqlalchemy.orm import aliased

import xlwt

# Project imports.

from lingvodoc.cache.caching import CACHE

from lingvodoc.models import (
    DBSession,
    Entity,
    LexicalEntry,
    PublishingEntity,
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

        for j in range(i - 1):
            coefficient_list[j] = aa[j] - coefficient_list[i] * aa[i - j - 1]

        if i < coefficient_number + 1:

            for j in range(i + 1):
                aa[j] = coefficient_list[j]

            for j in range(len(sample_list) - i - 2):
                b1[j] -= aa[i] * b2[j]
                b2[j] = b2[j + 1] - aa[i] * b1[j + 1];

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

        self.formant_sound = None

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

    def get_formants(self, step_index):
        """
        Computes point formant values at the point specified by formant time step index.
        """

        if step_index < 4 or step_index >= self.formant_step_count - 4:
            raise ValueError('step index {0} is out of bounds [4, {1})'.format(
                step_index, self.formant_step_count - 4))

        # Checking if we already computed required formant point value.

        if self.formant_list[step_index] != None:
            return self.formant_list[step_index]

        # No, we haven't, so we are going to compute it.

        window_list = get_gaussian_window(self.formant_window_size)
        sample_from = (step_index - 4) * self.formant_step_size

        sample_list = [self.formant_sample_list[sample_from + i] * window_list[i]
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

        derivative = polynomial.deriv()

        better_root_list = []
        better_root_index = 0

        # Finding better root approximations via Newton-Raphson iteration (see https://en.wikipedia.org/
        # wiki/Newton's_method.

        while better_root_index < len(root_list):

            previous = root_list[better_root_index]
            previous_delta = abs(polynomial(previous))

            current = previous - polynomial(previous) / derivative(previous)
            current_delta = abs(polynomial(current))

            while current_delta < previous_delta:

                previous = current
                previous_delta = current_delta

                current = previous - polynomial(previous) / derivative(previous)
                current_delta = abs(polynomial(current))

            # If it is a complex root, the next one is just its complex conjugate.

            better_root_list.append(previous)
            better_root_index += 1

            if abs(previous.imag) > 0:

                better_root_list.append(previous.conjugate())
                better_root_index += 1

            continue

        # Moving all roots into the unit circle. If a root is outside, we replace it with reciprocal of its
        # conjugate, reflecting it about the real line and projecting it inside the unit circle. Then we
        # find formants by looking at roots above the real line.

        nyquist_frequency = self.formant_sound.frame_rate * 0.5
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

        if self.formant_sound == None:

            self.formant_sound = self.intensity_sound.set_frame_rate(self.formant_frame_rate)

            self.formant_step_count = int(
                math.floor((self.formant_sound.frame_count() - 1) // self.formant_step_size + 1))

            self.formant_list = [None for i in range(self.formant_step_count)]

            # Getting sound time series ready for formant analysis by pre-emphasising frequencies higher
            # than 50 Hz.

            factor = math.exp(-2.0 * math.pi * 50 / self.formant_sound.frame_rate)
            sample_array = self.formant_sound.get_array_of_samples()

            channel_count = self.formant_sound.channels

            self.formant_sample_list = [
                sum(sample_array[j] for j in range(channel_count)) / channel_count]

            for i in range(1, int(self.formant_sound.frame_count())):

                self.formant_sample_list.append(sum(
                    sample_array[i * channel_count + j] -
                    factor * sample_array[(i - 1) * channel_count + j]
                        for j in range(channel_count)) / channel_count)

        # Due to windowed nature of formant value computation, we can't compute them for points close to
        # the beginning and the end of the recording; such points are skipped.

        factor = self.formant_sound.frame_rate / self.formant_step_size

        begin_step = max(4, int(math.ceil(begin * factor)))
        end_step = min(self.formant_step_count - 5, int(math.floor(end * factor)))

        # Computing interval formant values as means of point formant values.

        f1_sum, f2_sum = 0.0, 0.0

        for step_index in range(begin_step, end_step + 1):
            f1, f2 = self.get_formants(step_index)

            f1_sum += f1
            f2_sum += f2

        step_count = end_step - begin_step + 1
        return f1_sum / step_count, f2_sum / step_count


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
vowel_set = set('aeiouyæøœɐɑɒɔɘəɛɜɞɤɨɪɯɵɶʉʊʌʏ̈̽ао')


#: List of Unicode characters which can be used to write phonetic transcriptions.
#:
#: We have to define it through Unicode character codes because it contains combining characters, which mess
#: with syntax highlighting and probably could mess with Python source code parsing.
#:
phonetic_character_list = list(map(chr, [
    39, 46, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116,
    117, 118, 119, 120, 121, 122, 124, 161, 228, 230, 231, 232, 233, 234, 235, 240, 248, 259, 275, 283, 295,
    331, 339, 448, 449, 450, 451, 517, 592, 593, 594, 595, 596, 597, 598, 599, 600, 601, 602, 603, 604, 605,
    606, 607, 608, 609, 610, 611, 612, 613, 614, 615, 616, 618, 619, 620, 621, 622, 623, 624, 625, 626, 627,
    628, 629, 630, 632, 633, 634, 635, 637, 638, 640, 641, 642, 643, 644, 648, 649, 650, 651, 652, 653, 654,
    655, 656, 657, 658, 660, 661, 664, 665, 667, 668, 669, 670, 671, 673, 674, 675, 676, 677, 678, 679, 680,
    688, 690, 695, 700, 704, 712, 716, 720, 721, 724, 725, 726, 727, 734, 736, 737, 739, 740, 741, 742, 743,
    744, 745, 768, 769, 770, 771, 772, 774, 776, 778, 779, 780, 781, 783, 785, 792, 793, 794, 796, 797, 798,
    799, 800, 804, 805, 809, 810, 812, 814, 815, 816, 817, 820, 825, 826, 827, 828, 829, 865, 946, 952, 967,
    1072, 1086, 7498, 7542, 7569, 7587, 7609, 7615, 7869, 8201, 8214, 8255, 8319, 8599, 8600, 11377, 42779,
    42780]))


#: Regular expression defining acceptable phonetic transcription.
#:
#: Right now we use the simplest approach, just a sequence of acceptable symbols and whitespace. For lists
#: of phonetic symbols of various classes see https://en.wikipedia.org/wiki/International_Phonetic_Alphabet.
#:
transcription_re = re.compile(
    '[\s{0}]*'.format(''.join(phonetic_character_list)),
    re.DOTALL | re.IGNORECASE | re.VERBOSE)


@view_config(route_name="phonology", renderer='json')
def phonology(request):
    """
    Computes phonology of a specified perspective.

    Perspective is specified by request parameters 'perspective_client_id' and 'perspective_object_id',
    example of a request: /phonology?perspective_client_id=345&perspective_object_id=2.
    """

    perspective_cid = request.params.get('perspective_client_id')
    perspective_oid = request.params.get('perspective_object_id')

    # Checking if we have limits on number of computed results.

    limit = (None if 'limit' not in request.params else
        int(request.params.get('limit')))

    limit_exception = (None if 'limit_exception' not in request.params else
        int(request.params.get('limit_exception')))

    limit_no_vowel = (None if 'limit_no_vowel' not in request.params else
        int(request.params.get('limit_no_vowel')))

    limit_result = (None if 'limit_result' not in request.params else
        int(request.params.get('limit_result')))

    # TODO: get perspective's translation and language it belongs to.

    # We get lexical entries of this perspective with markup'ed sounds.

    Sound = aliased(Entity, name = "Sound")
    PublishingSound = aliased(PublishingEntity, name = "PublishingSound")

    query = DBSession.query(LexicalEntry, Entity, Sound, PublishingEntity, PublishingSound).filter(and_(
        LexicalEntry.parent_client_id == perspective_cid,
        LexicalEntry.parent_object_id == perspective_oid,
        LexicalEntry.marked_for_deletion == False,
        Entity.parent_client_id == LexicalEntry.client_id,
        Entity.parent_object_id == LexicalEntry.object_id,
        Entity.marked_for_deletion == False,
        Entity.additional_metadata.contains({"data_type": "praat markup"}),
        PublishingEntity.client_id == Entity.client_id,
        PublishingEntity.object_id == Entity.object_id,
        PublishingEntity.published == True,
        PublishingEntity.accepted == True,
        Sound.client_id == Entity.self_client_id,
        Sound.object_id == Entity.self_object_id,
        Sound.marked_for_deletion == False,
        PublishingSound.client_id == Sound.client_id,
        PublishingSound.object_id == Sound.object_id,
        PublishingSound.published == True,
        PublishingSound.accepted == True))

    # We process these lexical entries in batches. Just in case, it seems that perspectives rarely have more
    # then several hundred such lexical entries.

    exception_counter = 0
    no_vowel_counter = 0
    result_list = list()

    for index, row in enumerate(query.yield_per(100)):

        markup_url = row.Entity.content
        sound_url = row.Sound.content

        cache_key = 'phonology:{0}:{1}:{2}:{3}'.format(
            row.Sound.client_id, row.Sound.object_id,
            row.Entity.client_id, row.Entity.object_id)

        # Checking if we have cached result for this pair of sound/markup.

        cache_result = CACHE.get(cache_key)

        if cache_result == 'no_vowel':

            log.debug(
                '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}) '
                '[CACHE {7}]: no vowels\n{8}\n{9}'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Entity.client_id, row.Entity.object_id,
                cache_key, markup_url, sound_url))

            no_vowel_counter += 1

            if (limit_no_vowel and no_vowel_counter >= limit_no_vowel or
                limit and index + 1 >= limit):
                break

            continue

        # If we have cached exception, we do the same as with absence of vowels, show its info and
        # continue.

        elif isinstance(cache_result, tuple) and cache_result[0] == 'exception':
            exception, traceback_string = cache_result[1:3]

            log.debug(
                '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                '[CACHE {7}]: exception\n{8}\n{9}'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Entity.client_id, row.Entity.object_id,
                cache_key, markup_url, sound_url))

            log.debug(traceback_string)

            exception_counter += 1

            if (limit_exception and exception_counter >= limit_exception or
                limit and index + 1 >= limit):
                break

            continue

        # If we actually have the result, we use it and continue.

        elif cache_result:

            result_string = '\n'.join(
                'tier {0} \'{1}\': {2}'.format(tier_number, tier_name,
                    
                    tier_result_seq_list if not isinstance(tier_result_seq_list, list) else
                    tier_result_seq_list[0] if len(tier_result_seq_list) <= 1 else
                    ''.join('\n  {0}'.format(tier_result) for tier_result in tier_result_seq_list))

                    for tier_number, tier_name, tier_result_seq_list in cache_result)

            log.debug(
                '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}) '
                '[CACHE {7}]:\n{8}\n{9}\n{10}'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Entity.client_id, row.Entity.object_id,
                cache_key, markup_url, sound_url, result_string))

            result_list.append(cache_result)

            if (limit_result and len(result_list) >= limit_result or
                limit and index + 1 >= limit):
                break

            continue

        try:
            # Getting markup, checking for each tier if it needs to be processed.

            markup_bytes = urllib.request.urlopen(urllib.parse.quote(markup_url, safe = '/:')).read()

            textgrid = pympi.Praat.TextGrid(xmax = 0)
            textgrid.from_file(
                io.BytesIO(markup_bytes),
                codec = chardet.detect(markup_bytes)['encoding'])

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
                    log.debug(
                        '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                        'tier {7} \'{8}\' has interval(s) with unusual transcription text: '
                        '{9} / {10}'.format(
                        index,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Entity.client_id, row.Entity.object_id,
                        tier_number, tier_name, transcription, dict(unusual_markup_list)))

                # If the markup does not have any vowels, we note it and also report it.

                if all(character not in vowel_set for character in transcription):

                    tier_data_list.append((tier_number, tier_name, 'no_vowel'))

                    log.debug(
                        '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                        'tier {7} \'{8}\' doesn\'t have any vowel markup: {9}'.format(
                        index,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Entity.client_id, row.Entity.object_id,
                        tier_number, tier_name, transcription_list))

                # It is also possible that while full transcription has vowels, intervals selected for
                # analysis do not. In that case we also note it and report it.

                elif not any(character in vowel_set for character in selected):

                    tier_data_list.append((tier_number, tier_name, 'no_vowel_selected'))

                    log.debug(
                        '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                        'tier {7} \'{8}\' intervals to be processed don\'t have any vowel markup: '
                        'markup {9}, selected {10}'.format(
                        index,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Entity.client_id, row.Entity.object_id,
                        tier_number, tier_name,
                        transcription_list, selected_list))

                # Otherwise we store tier data to be used during processing of the sound file.

                else:
                    tier_data_list.append((tier_number, tier_name,
                        (raw_interval_list, raw_interval_seq_list, interval_seq_list,
                            interval_idx_to_raw_idx, transcription)))

                    vowel_flag = True

            # If there are no tiers with vowel markup, we skip this sound-markup file altogether.

            if not vowel_flag:

                CACHE.set(cache_key, 'no_vowel')
                no_vowel_counter += 1

                if (limit_no_vowel and no_vowel_counter >= limit_no_vowel or
                    limit and index + 1 >= limit):
                    break

                continue

            # Otherwise we retrieve the sound file and analyse each vowel-containing markup.
            # Partially inspired by source code at scripts/convert_five_tiers.py:307.

            sound = None
            with tempfile.NamedTemporaryFile() as temp_file:

                sound_file = urllib.request.urlopen(urllib.parse.quote(sound_url, safe = '/:'))
                temp_file.write(sound_file.read())
                temp_file.flush()

                sound = AudioPraatLike(pydub.AudioSegment.from_wav(temp_file.name))

            tier_result_list = []

            for tier_number, tier_name, tier_data in tier_data_list:

                if tier_data == 'no_vowel' or tier_data == 'no_vowel_selected':
                    tier_result_list.append((tier_number, tier_name, tier_data))
                    continue

                # Analyzing vowel sounds of each interval sequence.

                (raw_interval_list, raw_interval_seq_list, interval_seq_list, interval_idx_to_raw_idx,
                    transcription) = tier_data

                tier_result_list.append((tier_number, tier_name, []))

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

                    tier_result_list[-1][2].append([
                        ''.join(text for index, (begin, end, text) in raw_interval_list),
                        max_length_str,
                        '{0:.3f}'.format(max_length_f1_f2[0]),
                        '{0:.3f}'.format(max_length_f1_f2[1]),
                        max_intensity_str,
                        '{0:.3f}'.format(max_intensity_f1_f2[0]),
                        '{0:.3f}'.format(max_intensity_f1_f2[1]),
                        '+' if max_intensity_index == max_length_index else '-'])

            # Saving result.

            result_list.append(tier_result_list)
            CACHE.set(cache_key, tier_result_list)

            result_string = '\n'.join(
                'tier {0} \'{1}\': {2}'.format(tier_number, tier_name,
                    
                    tier_result_seq_list if not isinstance(tier_result_seq_list, list) else
                    tier_result_seq_list[0] if len(tier_result_seq_list) <= 1 else
                    ''.join('\n  {0}'.format(tier_result) for tier_result in tier_result_seq_list))

                    for tier_number, tier_name, tier_result_seq_list in tier_result_list)

            log.debug(
                '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}):'
                '\n{7}\n{8}\n{9}'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Entity.client_id, row.Entity.object_id,
                markup_url, sound_url, result_string))

            # Stopping earlier, if required.

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
                '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                'exception\n{7}\n{8}'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Entity.client_id, row.Entity.object_id,
                markup_url, sound_url))

            # if we encountered an exception, we show its info and remember not to try offending
            # sound/markup pair again.

            traceback_string = ''.join(traceback.format_exception(
                exception, exception, exception.__traceback__))[:-1]

            log.debug(traceback_string)

            CACHE.set(cache_key, ('exception', exception,
                traceback_string.replace('Traceback', 'CACHEd traceback')))

            exception_counter += 1

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

        return {
            "error": "no markups for this query",
            "exception_counter": exception_counter,
            "no_vowel_counter": no_vowel_counter}

    # Otherwise we create and then serve Excel file.

    excel_book = xlwt.Workbook(encoding = "utf-8")
    sheet = excel_book.add_sheet("Sheet 1")

    sheet.write(0, 0, 'Transcription')
    sheet.write(0, 1, 'Longest (seconds) interval')
    sheet.write(0, 2, 'F1 (Hz)')
    sheet.write(0, 3, 'F2 (Hz)')
    sheet.write(0, 4, 'Highest intensity (dB) interval')
    sheet.write(0, 5, 'F1 (Hz)')
    sheet.write(0, 6, 'F2 (Hz)')
    sheet.write(0, 7, 'Coincidence')

    row_counter = 1

    for tier_result_list in result_list:
        for tier_number, tier_name, tier_result_seq_list in tier_result_list:

            if tier_result_seq_list == 'no_vowel':
                continue

            for tier_data in tier_result_seq_list:
                for index, tier_data_str in enumerate(tier_data):
                    sheet.write(row_counter, index, tier_data_str)

                row_counter += 1

    # Formatting column widths.

    sheet.col(0).width = 24 * 256
    sheet.col(1).width = 24 * 256
    sheet.col(2).width = 12 * 256
    sheet.col(3).width = 12 * 256
    sheet.col(4).width = 24 * 256
    sheet.col(5).width = 12 * 256
    sheet.col(6).width = 12 * 256
    sheet.col(7).width = 12 * 256

    excel_stream = io.BytesIO()
    excel_book.save(excel_stream)
    excel_stream.seek(0)

    # See http://stackoverflow.com/questions/2937465/what-is-correct-content-type-for-excel-files for Excel
    # content-type.

    response = Response(content_type = 'application/vnd.ms-excel')

    response.app_iter = FileIter(excel_stream)
    response.headers['Content-Disposition'] = "attachment; filename=phonology.xls"

    return response


# A little bit of local testing.

if __name__ == '__main__':

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

