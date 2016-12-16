from pyramid.view import view_config

from sqlalchemy import (
    and_,
)

from sqlalchemy.orm import aliased

from lingvodoc.models import (
    DBSession,
    Entity,
)

from pyramid.httpexceptions import (
    HTTPOk
)

import pympi

import pydub

import tempfile
import urllib.request
import urllib.parse

import logging
log = logging.getLogger(__name__)


def find_max_db_segment(wav_url, segment_list, type = 'rms'):
    """
    Accepts URL to a WAV file and a list of segments specified by boundaries in seconds, returns indices of
    the loudest segment and the longest segment.

    Loudness can be measured either by mean of the absolute intensity, or a root mean squared intesity.
    Choice of the loudness computation method is controlled by a third parameter with default value of
    'rms' meaning root mean squared intensity. Other possible value is 'mean_abs', meaning mean of the
    absolute intesity.
    """

    if not segment_list:
        return None

    # Setting loudness measure function.

    rms_f = lambda segment: segment.rms

    def mean_abs_f(segment):
        sample_list = segment.get_array_of_samples()
        return int(sum(abs(sample) for sample in sample_list) / len(sample_list))

    if type == 'rms':
        loudness_f = rms_f
    elif type == 'mean_abs':
        loudness_f = mean_abs_f
    else:
        raise ValueError()

    # Finding loudest and longest segments.

    max_loudness = None
    max_loudness_index = None

    max_length = None
    max_length_index = None

    # Partially inspired by source code at scripts/convert_five_tiers.py:307.

    with tempfile.NamedTemporaryFile() as temp_file:

        sound_file = urllib.request.urlopen(wav_url)
        temp_file.write(sound_file.read())
        temp_file.flush()

        sound = pydub.AudioSegment.from_wav(temp_file.name)

        for index, (begin_sec, end_sec) in enumerate(segment_list):

            # Pydub's AudioSegment references sound locations in milliseconds, see
            # https://github.com/jiaaro/pydub/blob/master/API.markdown.

            loudness = loudness_f(sound[begin_sec * 1000 : end_sec * 1000])
            length = end_sec - begin_sec

            if max_loudness == None or loudness > max_loudness:
                max_loudness = loudness
                max_loudness_index = index

            if max_length == None or length > max_length:
                max_length = length
                max_length_index = index

    return (max_loudness_index, max_length_index)


@view_config(route_name="phonology", renderer='json')
def phonology(request):

    # TODO:
    # receive perspective ids (client_id and object_id) as GET parameters (look around the code, it's standard pattern)
    # get its translation and language it belongs to
    # filter only entities that belong to this perspective. Should look like this (didn't test)
    # DBSession.query(Entity, Sound).filter(
    #   Entity.additional_metadata.contains({"data_type": "praat markup"})).join(
    #       Sound, and_(Sound.client_id == Entity.self_client_id, Sound.object_id == Entity.self_object_id).join(
    #       LexicalEntry, Entity.parent == LexicalEntry).join(
    #       DictionaryPerspective, LexicalEntry.parent == DictionaryPerspective).filter(_and(DictionaryPerspective.client_id==client_id, DictionaryPerspective.object_id==object_id))
    #
    #

    # here we get markups with corresponding sounds
    Sound = aliased(Entity, name="Sound")
    pairs = DBSession.query(Entity, Sound).filter(
        Entity.additional_metadata.contains({"data_type": "praat markup"})
    ).join(Sound, and_(
        Sound.client_id == Entity.self_client_id,
        Sound.object_id == Entity.self_object_id)
           )

    wrong_counter = 0

    # batch fetch (will be fetched ~26000 anyway, just RAM optimization)
    for i in pairs.yield_per(200):
        markup = i.Entity
        sound = i.Sound

        try:
            markup_file, headers = urllib.request.urlretrieve(urllib.parse.quote(markup.content, safe='/:'))
            # IMPORTANT NOTE: in sounds downloading need to fix the same way (most of the links are unicode)

            textgrid = pympi.TextGrid(file_path=markup_file)
            # TODO: fix reading problems
            first_tier = textgrid.get_tier(0)

            # 1. Get intervals list with symbols
            # 2. Check the intervals where the following symbols present:  i y ɨ ʉ ɯ u ɪ ʏ ɪ̈ ʊ̈ ɯ̽ ʊ e ø ɘ ɵ ɤ o ə ɛ œ ɜ ɞ ʌ ɔ æ ɐ a ɶ ɑ ɒ
            # 3. a) If any of the symbols present in any markup interval, get the intervals for these matches and goto 4.
            #    b) Else (none of the symbols are found in markup), continue the cycle (skip this markup-sound pair)
            # 4. Download the sound and find_max_db_segment with these intervals
            # 5. Form the table row:
            #   transcription (concat the symbols in all intervals without whitespaces) - e.g. "pilka"
            #   symbol with the max length, its length in seconds, its position in transcription - e.g. "i 0.072 [2]"
            #   symbol with max intensity, its intensity, its position - e.g. "i -0.68 [2]"
            #   mark "+" or "-" for if max length and max intensity symbol is the same interval (i [2] in this case)
            # 6. Output is an Excel file (do save them when you test) or {"error": "no markups for this query"} .


        except Exception as e:
            urllib.request.urlcleanup()
            wrong_counter = wrong_counter + 1
            # log.error(str(e))

        urllib.request.urlcleanup()
        if wrong_counter % 1000 == 0:
            log.error(counter)


    return {"wrong_markups_count": wrong_counter}



# A little bit of testing.
if __name__ == '__main__':

    wav_url = 'http://www.wav-sounds.com/answering_machine/rappin.wav'
    print('rms', find_max_db_segment(wav_url, [(0.1, 0.3), (0.4, 0.5)]))
    print('mean_abs', find_max_db_segment(wav_url, [(0.1, 0.3), (0.4, 0.5)], 'mean_abs'))

    wav_url = 'http://www.wav-sounds.com/movie/terminator.wav'
    print('rms', find_max_db_segment(wav_url, [(0.1, 0.3), (0.4, 0.5)]))
    print('mean_abs', find_max_db_segment(wav_url, [(0.1, 0.3), (0.4, 0.5)], 'mean_abs'))

