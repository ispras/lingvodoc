
# Standard library imports.

import io
import logging
import math
import tempfile
import traceback

import urllib.request
import urllib.parse

# External imports.

import cchardet as chardet

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


def find_max_interval(sound, interval_list, type = 'rms'):
    """
    Accepts a sound recording and a list of intervals specified by boundaries in seconds, returns index of
    the interval with the highest sound intensity, relative intensity of this interval, index of the longest
    interval and the length of the longest interval.

    Intensity can be measured either as mean absolute intensity, or a root mean squared intesity, both in dB
    relative to full scale (dBFS). Choice of the intensity computation method is controlled by a third
    parameter with default value of 'rms' meaning root mean squared intensity. Other possible value is
    'mean_abs', meaning mean absolute intesity.
    """

    if not interval_list:
        return None

    # Setting intensity measure function.

    rms_f = lambda interval: interval.rms

    def mean_abs_f(interval):
        sample_list = interval.get_array_of_samples()
        return int(sum(abs(sample) for sample in sample_list) / len(sample_list))

    if type == 'rms':
        intensity_f = rms_f
    elif type == 'mean_abs':
        intensity_f = mean_abs_f
    else:
        raise ValueError()

    # Finding loudest and longest intervals.

    max_intensity = None
    max_intensity_index = None

    max_length = None
    max_length_index = None

    for index, (begin_sec, end_sec, _) in enumerate(interval_list):

        # Pydub's AudioSegment references sound locations in milliseconds, see
        # https://github.com/jiaaro/pydub/blob/master/API.markdown.

        interval = sound[begin_sec * 1000 : end_sec * 1000]
        intensity = ratio_to_db(intensity_f(interval), interval.max_possible_amplitude)
        length = end_sec - begin_sec

        if max_intensity == None or intensity > max_intensity:
            max_intensity = intensity
            max_intensity_index = index

        if max_length == None or length > max_length:
            max_length = length
            max_length_index = index

    return (max_intensity_index,
        float(max_intensity) / intensity_f(sound),
        max_length_index,
        max_length)


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


#: Dictionary used for memoization of window function computation.
window_dict = dict()


def get_window(half_window_size):
    """
    Computes (2N + 1)-sample Kaiser window, where N is a half window size in samples.

    Employs memoization.
    """

    if half_window_size in window_dict:
        return window_dict[half_window_size]

    # Computing a new window, saving it for reuse, and returning it.

    pi_alpha = 2 * math.pi ** 2 + 0.5

    window_list = [
        bessel_i0_approximation(pi_alpha * math.sqrt(1 - (i / half_window_size) ** 2))
            for i in range(-half_window_size, half_window_size + 1)]

    window_sum = sum(window_list)

    window_dict[half_window_size] = (window_list, window_sum)
    return (window_list, window_sum)


class AudioPraatLike(pydub.AudioSegment):
    """
    Extends pydub.AudioSegment to allow computations of intensity and, possibly in the future, formants
    using algorithms mimicking as close as possible corresponding algorithms of the Praat [http://www.fon.
    hum.uva.nl/praat] software.
    """

    def __init__(self, data=None, *args, **kwargs):
        super().__init__(data, *args, **kwargs)

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

        self.step_size = int(math.floor(0.0125 * self.frame_rate))
        self.half_window_size = 4 * self.step_size
        self.window_size = 2 * self.half_window_size + 1

        self.step_count = int(math.floor((self.frame_count() - 1) // self.step_size + 1))
        self.intensity_list = [None for i in range(self.step_count)]

    def get_intensity(self, step_index):
        """
        Computes intensity at the point specified by time step index.
        """

        if step_index < 4 or step_index > self.step_count - 4:
            raise ValueError('step index {0} is out of bounds [4, {1}]'.format(
                step_index, self.step_count - 4))

        window_list, window_sum = get_window(self.half_window_size)

        sample_array = self.get_array_of_samples()
        sample_sum = 0.0

        sample_from = (step_index - 4) * self.step_size * self.channels

        # We sum squared normalized amplitudes of all samples of all channels in the window.

        for i in range(self.window_size):
            for j in range(self.channels):
                sample = sample_array[sample_from + i * self.channels + j] / self.max_possible_amplitude
                sample_sum += sample ** 2 * window_list[i]

        # Multiplication by 2.5e9 is taken directly from Praat source code, where it is performed via
        # division by 4e-10.

        intensity = sample_sum / (self.channels * window_sum) * 2.5e9
        return -300 if intensity < 1e-30 else 10 * math.log10(intensity);

    def get_interval_intensity(self, begin, end):
        """
        Computes mean-energy intensity of the interval specified by beginning and end in seconds.
        """

        begin_step = int(math.ceil(begin * self.frame_rate / self.step_size))
        end_step = int(math.floor(end * self.frame_rate / self.step_size))

        energy_sum = sum(
            math.pow(10, 0.1 * self.get_intensity(step_index))
                for step_index in range(begin_step, end_step + 1))

        return 10 * math.log10(energy_sum / (end_step - begin_step + 1))


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

        try:
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

            elif cache_result:

                # If we actually have the result, we use it and continue.

                result_string = '\n'.join(
                    'tier {0} \'{1}\': {2}'.format(tier_number, tier_name, tier_result)
                        for tier_number, tier_name, tier_result in cache_result)

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
                interval_list = []
                long_text_flag = False

                interval_idx_to_raw_idx = dict()

                # Compiling transcription, checking if we have unusual markup.

                # TODO: split sound and markup on intervals with empty markup into separate interval
                # sequences and treat each such sequence as a separate word.

                for raw_index, interval in enumerate(raw_interval_list):

                    if len(interval[2]) <= 2 \
                            and len(interval[2].strip()) \
                            and any(character in vowel_set for character in interval[2]):

                        interval_list.append(interval)
                        interval_idx_to_raw_idx[len(interval_list)-1] = raw_index

                    elif len(interval[2]) > 2:
                        long_text_flag = True

                transcription = ''.join(text for begin, end, text in raw_interval_list)

                # If we have intervals with non-singleton markup, we report them.

                if long_text_flag:
                    log.debug(
                        '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                        'tier {7} \'{8}\' has interval(s) with unusually long text: {9}'.format(
                        index,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Entity.client_id, row.Entity.object_id,
                        tier_number, tier_name,
                        list(map(lambda interval: interval[2], raw_interval_list))))

                # If the markup does not have any vowels, we note it and also report it.

                if all(character not in vowel_set for character in transcription):

                    tier_data_list.append((tier_number, tier_name, 'no_vowel'))

                    log.debug(
                        '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                        'tier {7} \'{8}\' doesn\'t have any vowel markup'.format(
                        index,
                        row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                        row.Sound.client_id, row.Sound.object_id,
                        row.Entity.client_id, row.Entity.object_id,
                        tier_number, tier_name))

                # Otherwise we store tier data to be used during processing of the sound file.

                else:
                    tier_data_list.append((tier_number, tier_name,
                        (raw_interval_list, interval_list, interval_idx_to_raw_idx, transcription)))

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

                sound = AudioPraatLike.from_wav(temp_file.name)

            tier_result_list = list()

            for tier_number, tier_name, tier_data in tier_data_list:

                if tier_data == 'no_vowel':
                    tier_result_list.append((tier_number, tier_name, 'no_vowel'))
                    continue

                # Analyzing vowel sounds.

                raw_interval_list, interval_list, interval_idx_to_raw_idx, transcription = tier_data

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

                tier_result_list.append((tier_number, tier_name,
                    (transcription, max_length_str, max_intensity_str,
                        '+' if max_intensity_index == max_length_index else '-')))

            # Saving result.

            result_list.append(tier_result_list)
            CACHE.set(cache_key, tier_result_list)

            result_string = '\n'.join(
                'tier {0} \'{1}\': {2}'.format(tier_number, tier_name, tier_result)
                    for tier_number, tier_name, tier_result in tier_result_list)

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

            log.debug(
                '{0} (LexicalEntry {1}/{2}, sound-Entity {3}/{4}, markup-Entity {5}/{6}): '
                'exception\n{7}\n{8}'.format(
                index,
                row.LexicalEntry.client_id, row.LexicalEntry.object_id,
                row.Sound.client_id, row.Sound.object_id,
                row.Entity.client_id, row.Entity.object_id,
                markup_url, sound_url))

            # If we encountered an exception, we show its info.

            log.debug(''.join(traceback.format_exception(
                Exception, exception, exception.__traceback__))[:-1])

            exception_counter += 1

            if (limit_exception and exception_counter >= limit_exception or
                limit and index + 1 >= limit):
                break

    log.debug('phonology {0}/{1}: {2} results, {3} no vowels, {4} exceptions'.format(
        perspective_cid, perspective_oid, len(result_list), no_vowel_counter, exception_counter))

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
    sheet.write(0, 1, 'Longest (seconds) segment')
    sheet.write(0, 2, 'Highest intensity (dB) segment')
    sheet.write(0, 3, 'Coincidence')

    row_counter = 1

    for tier_result_list in result_list:
        for tier_number, tier_name, tier_data in tier_result_list:

            if tier_data == 'no_vowel':
                continue

            transcription, max_length_str, max_intensity_str, check_str = tier_data

            sheet.write(row_counter, 0, transcription)
            sheet.write(row_counter, 1, max_length_str)
            sheet.write(row_counter, 2, max_intensity_str)
            sheet.write(row_counter, 3, check_str)

            row_counter += 1

    # Formatting column widths.

    sheet.col(0).width = 24 * 256
    sheet.col(1).width = 24 * 256
    sheet.col(2).width = 24 * 256
    sheet.col(3).width = 12 * 256

    excel_stream = io.BytesIO()
    excel_book.save(excel_stream)
    excel_stream.seek(0)

    # See http://stackoverflow.com/questions/2937465/what-is-correct-content-type-for-excel-files for Excel
    # content-type.

    response = Response(content_type = 'application/vnd.ms-excel')

    response.app_iter = FileIter(excel_stream)
    response.headers['Content-Disposition'] = "attachment; filename=phonology.xls"

    return response

