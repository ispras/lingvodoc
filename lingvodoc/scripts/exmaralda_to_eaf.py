
# Standard library imports.

import ast
import collections
import getopt
import json
import logging
import os
import os.path
import pdb
import pprint
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import xml.etree.ElementTree as ElementTree
import zipfile

# External imports.

import pympi
import pyramid.paster as paster
import requests


# Setting up logging, if we are not being run as a script.

if __name__ != '__main__':

    log = logging.getLogger(__name__)
    log.debug('module init')


class Time(object):
    """
    Timeline value.
    """

    def __init__(
        self,
        id,
        index,
        value,
        before = None):

        self.id = id
        self.index = index
        self.value = value

        self.before = before
        self.after = None

        if self.before is not None:
            self.before.after = self

        self.start_dict = {}
        self.end_dict = {}


class Tier(object):
    """
    Markup tier.
    """

    def __init__(self, id, category, postfix):

        self.id = id
        self.category = category
        self.postfix = postfix

        self.event_list = []


class Event(object):
    """
    Markup event in one of the tiers.
    """

    def __init__(self, tier, start, end, content):

        self.tier = tier

        self.start = start
        self.end = end

        self.content = content

        self.index = (
            len(self.tier.event_list))

        self.previous = None
        self.next = None

        if self.tier.event_list:

            self.previous = self.tier.event_list[-1]
            self.previous.next = self

        self.tier.event_list.append(self)

        self.start.start_dict[tier.id] = self
        self.end.end_dict[tier.id] = self


def exb_to_eaf(
    exb_file,
    eaf_file_path,
    duration = None,
    reference_ext_set = None,
    __debug_flag__ = False):
    """
    Converts Exmaralda markup file from an INEL corpus to 5-tier compatible EAF file.
    """

    # Parsing Exmaralda markup, code in some measure inspired by
    # https://github.com/lingmod-tue/exmaralda-converter.

    tree = ElementTree.parse(exb_file)
    root = tree.getroot()

    # Checking referenced files.

    for reference_xml in root.iter('referenced-file'):

        reference_url = (
            reference_xml.get("url"))

        dirname, basename = (
            os.path.split(reference_url))

        if dirname:
            raise NotImplementedError

        name, ext = (
            os.path.splitext(basename))

        log.debug(
            '\nreference_url: {}'.format(
                reference_url))

        if (reference_ext_set and
            ext not in reference_ext_set):

            exb_path = (
                    
                exb_file.name if isinstance(exb_file, zipfile.ZipExtFile) else
                exb_file)

            log.warning(
                '\nmissing: {} -> {}'.format(
                    exb_path, reference_url))

    # Parsing timeline, collecting timeline points without assigned time values.

    timeline_id_dict = {}
    timeline_index_dict = {}

    timeline_list = []

    no_time_value_segment_list = []
    no_time_value_list = []

    before_point = None

    max_time_value = None

    # Ok, going through all timeline points.

    for time_xml in root.iter('tli'):

        time_value_str = time_xml.get('time')
        time_id = time_xml.get('id')

        if not time_id:
            raise NotImplementedError

        time_id = int(time_id[1:])

        if time_id in timeline_id_dict:
            raise NotImplementedError

        # Trying to getting time value, saving info if it's not present, saving ordering info.

        time_value = None

        if time_value_str:

            time_value = float(time_value_str)

            if (max_time_value is None or
                time_value > max_time_value):

                max_time_value = time_value

        time_point = (

            Time(
                time_id,
                len(timeline_list),
                time_value,
                before_point))

        timeline_id_dict[time_id] = time_point
        timeline_index_dict[time_id] = len(timeline_list)

        timeline_list.append(time_point)

        if time_value_str is None:

            no_time_value_list.append(time_point)

        elif no_time_value_list:

            no_time_value_segment_list.append(no_time_value_list)
            no_time_value_list = []

        before_point = time_point

    # Do we have a series of time points without time values at the end?

    if no_time_value_list:
        no_time_value_segment_list.append(no_time_value_list)

    # We add additional starting and ending time points, the latter with time value guessed based on overall
    # duration, if we were given one, and the former using the -1 index trick.

    log.debug(
        '\nduration: {}'.format(
            duration if duration is None else '{:f}'.format(duration)))

    extra_begin_flag = (

        duration is not None
        
        or

        no_time_value_segment_list and
        len(no_time_value_segment_list[0]) < len(timeline_list))

    # Additional ending time point, if required and if duration is available.

    if (timeline_list[-1].value is None and
        duration is not None):

        if (max_time_value is not None and
            duration < max_time_value):

            raise NotImplementedError

        time_id = (None, 'end')

        time_point = (

            Time(
                time_id,
                len(timeline_list),
                duration,
                before_point))

        if time_id in timeline_id_dict:
            raise NotImplementedError

        timeline_id_dict[time_id] = time_point
        timeline_index_dict[time_id] = len(timeline_list)

        timeline_list.append(time_point)

    # Additional starting time point, if required.

    if extra_begin_flag:

        time_id = (None, 'start')

        time_point = (

            Time(
                time_id,
                -1,
                0.0))

        time_point.after = timeline_list[0]
        timeline_list[0].before = time_point

        if time_id in timeline_id_dict:
            raise NotImplementedError

        timeline_id_dict[time_id] = time_point
        timeline_index_dict[time_id] = -1

        timeline_list.append(time_point)

    # Showing timeline info.

    if __debug_flag__:

        log.debug(
            '\nlen(timeline_list): {}'
            '\nlen(no_time_value_segment_list): {}'
            '\n{}\n{}'.format(
                len(timeline_list),
                len(no_time_value_list),
                pprint.pformat(
                    [(time_point.id, time_point.value)
                        for time_point in timeline_list],
                    width = 192),
                pprint.pformat(
                    [[time_point.id
                        for time_point in no_time_value_list]
                            for no_time_value_list in no_time_value_segment_list],
                    width = 192)))

    # Looking through tiers and their events.

    tier_dict = {}
    timeline_event_dict = collections.defaultdict(set)

    for tier_xml in root.iter('tier'):

        tier_id = tier_xml.get('id')
        tier_cat = tier_xml.get('category')
        tier_name = tier_xml.get('display-name')

        if tier_id.startswith(tier_cat):
            postfix = tier_id[len(tier_cat):]

        elif tier_name.startswith(tier_cat):
            postfix = tier_name[len(tier_cat):]

        else:

            log.debug(
                '\ntier_id: {}'
                '\ntier_cat: {}'
                '\ntier_name: {}'.format(
                    repr(tier_id),
                    repr(tier_cat),
                    repr(tier_name)))

            raise NotImplementedError

        tier = (
            Tier(tier_id, tier_cat, postfix))

        tier_dict[tier_id] = tier

        # Parsing events, tying then to tiers and timeline points.

        for event_xml in tier_xml.iter('event'):

            start = (
                timeline_id_dict[
                    int(event_xml.get('start')[1:])])

            end = (
                timeline_id_dict[
                    int(event_xml.get('end')[1:])])

            event = (
                Event(tier, start, end, event_xml.text))

            timeline_event_dict[start.id].add(end.id)

    # Guessing time values for timeline points with unspecified ones, if required.

    guess_info_list = []

    if no_time_value_segment_list:

        # Starting with checking that the timeline is a valid topological sorting of timeline points based
        # on start/end points of events and time values.

        for id_from, id_to_set in timeline_event_dict.items():
            for id_to in id_to_set:

                if timeline_index_dict[id_from] >= timeline_index_dict[id_to]:
                    raise NotImplementedError

        # Also using virtual edges from the timeline order of timeline points with specified time values.

        time_id_list = (

            [time_point.id
                for time_point in

                sorted(
                    [time_point
                        for time_point in timeline_list
                        if time_point.value],
                    key = lambda time_point: (time_point.value, time_point.index))])

        for time_id_a, time_id_b in zip(time_id_list[:-1], time_id_list[1:]):

            if timeline_index_dict[time_id_a] >= timeline_index_dict[time_id_b]:

                log.debug(
                    '\ntime_id: {}, {}'
                    '\nindex: {}, {}'.format(
                        time_id_a,
                        time_id_b,
                        timeline_index_dict[time_id_a],
                        timeline_index_dict[time_id_b]))

                raise NotImplementedError

        # Guessing time values for each timeline point in each timeline segment without such values, based
        # on relative transcription lengths.

        for no_time_value_list in no_time_value_segment_list:

            if (not no_time_value_list[0].before and
                not no_time_value_list[-1].after):

                # We have neither preceeding no succeeding time points, that means that we actually don't
                # have any time points with time values.
                #
                # So we are going to assign time values arbitrarily based on transcription lengths.

                duration_step = 0.075
                interval_count = len(no_time_value_list) - 1

                index_start = 0
                index_end = interval_count

                sum_list = [
                    0 for i in range(interval_count)]

                count_list = [
                    0 for i in range(interval_count)]
                
                for time_point in no_time_value_list[1:]:

                    for tier_id, event in time_point.end_dict.items():

                        if (tier_id.rsplit('-', 1)[0] not in ('tx', 'mb') or
                            event.start.index < index_start or
                            event.end.index > index_end):
                            continue

                        event_length = (
                            event.end.index - event.start.index)

                        event_value = (
                            len(event.content) / event_length)

                        index_from = (
                            event.start.index - index_start)

                        for i in range(event_length):

                            sum_list[index_from + i] += event_value
                            count_list[index_from + i] += 1

                # Setting time values proportionally to transcription length, with 1/N smoothing.

                weight_list = [
                    (sum / count if count else 0.0) + 1
                    for sum, count in zip(sum_list, count_list)]

                no_time_value_list[0].value = 0.0

                current_time = 0.0
                current_value = 0.0

                for weight, time_point in (
                    zip(weight_list, no_time_value_list[1:])):

                    time_point.value = (
                        current_time + weight * duration_step)

                    halfway_value = (
                        (current_time + time_point.value) / 2)

                    # Saving info of where we guessed time points.

                    if current_value is not None:

                        guess_info_list.append(
                            (current_value, halfway_value))

                    current_time = time_point.value
                    current_value = halfway_value

                guess_info_list.append(

                    (current_value,
                        no_time_value_list[-1].value))

                continue

            elif not no_time_value_list[0].before:

                # No preeceding time value, shouldn't happen because we can always introduce additional
                # starting point with time value 0.0s.

                raise NotImplementedError

            elif not no_time_value_list[-1].after:

                # No time value after, meaning we don't have externally supplied duration value.
                #
                # Probably should determine average transcription length duration rate and then divide this
                # tailing series of time intervals based on transcription lengths.

                raise NotImplementedError

            # We have both before and after time points with time values, we can just divide this time
            # interval.

            index_start = no_time_value_list[0].index - 1
            index_end = no_time_value_list[-1].index + 1

            no_time_value_list.append(
                no_time_value_list[-1].after)

            sum_list = [
                0 for time_point in no_time_value_list]

            count_list = [
                0 for time_point in no_time_value_list]

            # Looking at transriptions at each adjacent interval.

            for time_point in no_time_value_list:

                for tier_id, event in time_point.end_dict.items():

                    if (tier_id.rsplit('-', 1)[0] not in ('tx', 'mb') or
                        event.start.index < index_start or
                        event.end.index > index_end):
                        continue

                    event_length = (
                        event.end.index - event.start.index)

                    event_value = (
                        len(event.content) / event_length)

                    index_from = (
                        event.start.index - index_start)

                    for i in range(event_length):

                        sum_list[index_from + i] += event_value
                        count_list[index_from + i] += 1

            # Setting time values proportionally to transcription length, with 1/N smoothing.

            weight_list = [
                (sum / count if count else 0.0) + 1
                for sum, count in zip(sum_list, count_list)]

            weight_total = sum(weight_list)
            weight_current = 0.0

            start_time = (
                no_time_value_list[0].before.value)

            end_time = (
                no_time_value_list[-1].value)

            current_time = start_time
            current_value = None

            for weight, time_point in (
                zip(weight_list, no_time_value_list[:-1])):

                weight_current += weight

                time_point.value = (
                    start_time + (end_time - start_time) * weight_current / weight_total)

                # Saving info of where we guessed time points.

                halfway_value = (
                    (current_time + time_point.value) / 2)

                if current_value is not None:

                    guess_info_list.append(
                        (current_value, halfway_value))

                current_time = time_point.value
                current_value = halfway_value

            guess_info_list.append(

                (current_value,
                    (current_time + no_time_value_list[-1].value) / 2))

    # Compiling list of reference events in time order.

    ref_event_list = []

    for tier in tier_dict.values():

        if tier.category != 'ref':
            continue

        ref_event_list.extend(tier.event_list)

    ref_event_list.sort(
        key = lambda ref_event: (ref_event.start.value, ref_event.end.value))

    if __debug_flag__:

        log.debug(
            '\nref_event_list:\n' +
            pprint.pformat(
                [(event.start.value, event.end.value, event.content)
                    for event in ref_event_list],
                width = 192))

    # Checking time interval disjointness.

    base_event_list = ref_event_list
    ref_event_list = base_event_list[:1]

    event_index_a = 0
    event_index_b = 1

    while event_index_b < len(base_event_list):

        event_a = ref_event_list[-1]
        event_b = base_event_list[event_index_b]

        event_index_b += 1

        a_start, a_end = event_a.start.value, event_a.end.value
        b_start, b_end = event_b.start.value, event_b.end.value

        # Events are disjoint.

        if a_end <= b_start:

            ref_event_list.append(event_b)
            event_index_a = event_index_b

            continue

        # There is some overlap.

        a_half = (a_start + a_end) / 2
        b_half = (b_start + b_end) / 2

        large_enough_check = (
            a_start <= b_half <= a_end or
            b_start <= a_half <= b_end)

        if __debug_flag__:

            log.debug(
                '\noverlap {}, {}:'
                '\n{:.3f}, {:.3f}, {:.3f}, {}'
                '\n{:.3f}, {:.3f}, {:.3f}, {}'
                '\n{}'.format(
                    event_index_a,
                    event_index_b,
                    a_start,
                    a_half,
                    a_end,
                    repr(event_a.content),
                    b_start,
                    b_half,
                    b_end,
                    repr(event_b.content),
                    "large enough, skip 2nd" if large_enough_check else "small enough"))

        # Accepting next event if the overlap is not large enough.

        if not large_enough_check:

            ref_event_list.append(event_b)
            event_index_a = event_index_b

    if __debug_flag__:

        log.debug(
            '\nref_event_list:\n' +
            pprint.pformat(
                [(event.start.value, event.end.value, event.content)
                    for event in ref_event_list],
                width = 192))

    # Getting ready to export to EAF.

    eaf = pympi.Elan.Eaf()

    eaf.add_linguistic_type('text_top_level')
    eaf.add_linguistic_type('symbolic_association', 'Symbolic_Association', False)
    eaf.add_linguistic_type('word_translation_included_in', 'Included_In')

    eaf.add_linguistic_type('reference')
    eaf.add_linguistic_type('time guess mark')

    eaf.remove_linguistic_type('default-lt')

    eaf.add_tier('reference', 'reference')

    eaf.add_tier('text', 'text_top_level')
    eaf.add_tier('literary translation', 'symbolic_association', 'text')
    eaf.add_tier('translation', 'word_translation_included_in', 'text')
    eaf.add_tier('transcription', 'symbolic_association', 'translation')
    eaf.add_tier('word', 'symbolic_association', 'translation')

    eaf.add_tier('text translation english', 'symbolic_association', 'text')
    eaf.add_tier('text translation german', 'symbolic_association', 'text')
    eaf.add_tier('translation english', 'word_translation_included_in', 'text')
    eaf.add_tier('translation german', 'word_translation_included_in', 'text')

    eaf.add_tier('time guess mark', 'time guess mark')

    eaf.remove_tier('default')

    # Looking through reference events in order, getting required info for each of those.

    category_set = (
        set(['st', 'mb', 'gr', 'ge', 'gg', 'ltr', 'fg', 'fe']))

    for ref_event_index, ref_event in enumerate(ref_event_list):

        ref_postfix = (
            ref_event.tier.postfix)

        event_dict = {}

        for tier_id, event in ref_event.start.start_dict.items():

            category = event.tier.category

            if (category not in category_set or
                event.tier.postfix != ref_postfix):
                continue

            if category in event_dict:
                raise NotImplementedError

            event_dict[category] = event

        # Exporting to EAF, base events are reference and source text.
        #
        # NOTE: EAF times are in milliseconds and must be integral.

        ref_time = (
            round(ref_event.start.value * 1000))

        ref_bound = (
            ref_event.end.value)

        eaf.add_annotation(
            'reference',
            ref_time,
            round(ref_bound * 1000),
            ref_event.content)

        st_event = event_dict.get('st')

        if st_event:

            eaf.add_annotation(
                'text',
                round(st_event.start.value * 1000),
                round(st_event.end.value * 1000),
                st_event.content)

            text_time_half = (
                round((st_event.start.value + st_event.end.value) * 500))

        else:

            eaf.add_annotation(
                'text',
                ref_time,
                round(ref_event.end.value * 1000),
                '')

            text_time_half = (
                round((ref_event.start.value + ref_event.end.value) * 500))

        # Literary translation, english and german translations if present.

        if 'ltr' in event_dict:

            eaf.add_ref_annotation(
                'literary translation',
                'text',
                text_time_half,
                event_dict['ltr'].content)

        if 'fe' in event_dict:

            eaf.add_ref_annotation(
                'text translation english',
                'text',
                text_time_half,
                event_dict['fe'].content)

        if 'fg' in event_dict:

            eaf.add_ref_annotation(
                'text translation german',
                'text',
                text_time_half,
                event_dict['fg'].content)

        # We have a text event, we assume that there can be several of them inside the reference event, and
        # we process all of them trying to get all corresponding translations.

        if st_event:

            st_event = st_event.next

            ltr_tier_id = (
                event_dict['ltr'].tier.id if 'ltr' in event_dict else None)

            fe_tier_id = (
                event_dict['fe'].tier.id if 'fe' in event_dict else None)

            fg_tier_id = (
                event_dict['fg'].tier.id if 'fg' in event_dict else None)

            previous_st_time = None

            while (
                st_event and
                st_event.end.value <= ref_bound):

                # Another text event.

                st_time = (
                    round(st_event.start.value * 1000))

                if previous_st_time is not None:

                    gr_time = (
                        max(gr_time, previous_gr_time + 2))

                st_time_half = (

                    max(
                        round((st_event.start.value + st_event.end.value) * 500),
                        st_time + 1))

                eaf.add_annotation(
                    'text',
                    st_time,
                    max(
                        round(st_event.end.value * 1000),
                        st_time + 2),
                    st_event.content)

                # Translations, if present.

                ltr_event = (
                    st_event.start.start_dict.get(ltr_tier_id))

                if ltr_event:

                    eaf.add_ref_annotation(
                        'literary translation',
                        'text',
                        st_time_half,
                        ltr_event.content)

                fe_event = (
                    st_event.start.start_dict.get(fe_tier_id))

                if fe_event:

                    eaf.add_ref_annotation(
                        'text translation english',
                        'text',
                        st_time_half,
                        fe_event.content)

                fg_event = (
                    st_event.start.start_dict.get(fg_tier_id))

                if fg_event:

                    eaf.add_ref_annotation(
                        'text translation german',
                        'text',
                        st_time_half,
                        fg_event.content)

                # Next text event, if we have one.

                st_event = st_event.next

        # Now per-word data in the reference time interval.

        gr_event = event_dict.get('gr')

        if not gr_event:
            continue

        mb_tier_id = (
            event_dict['mb'].tier.id if 'mb' in event_dict else None)

        ge_tier_id = (
            event_dict['ge'].tier.id if 'ge' in event_dict else None)

        gg_tier_id = (
            event_dict['gg'].tier.id if 'gg' in event_dict else None)

        previous_gr_time = None

        while (
            gr_event and
            gr_event.start.value < ref_bound):

            # Translation and transcription, if it is present.

            gr_time = (
                round(gr_event.start.value * 1000))

            if previous_gr_time is not None:

                gr_time = (
                    max(gr_time, previous_gr_time + 2))

            previous_gr_time = gr_time

            gr_time_half = (

                max(
                    round((gr_event.start.value + gr_event.end.value) * 500),
                    gr_time + 1))

            eaf.add_annotation(
                'translation',
                gr_time,
                max(
                    round(gr_event.end.value * 1000),
                    gr_time + 2),
                gr_event.content)

            mb_event = (
                gr_event.start.start_dict.get(mb_tier_id))

            if mb_event:

                eaf.add_ref_annotation(
                    'transcription',
                    'translation',
                    gr_time_half,
                    mb_event.content)

            # Additional english and german translations, if they are present.

            ge_event = (
                gr_event.start.start_dict.get(ge_tier_id))

            if ge_event:

                eaf.add_annotation(
                    'translation english',
                    gr_time,
                    max(
                        round(ge_event.end.value * 1000),
                        gr_time + 1),
                    ge_event.content)

            gg_event = (
                gr_event.start.start_dict.get(gg_tier_id))

            if gg_event:

                eaf.add_annotation(
                    'translation german',
                    gr_time,
                    max(
                        round(gg_event.end.value * 1000),
                        gr_time + 1),
                    gg_event.content)

            # Next translation event, if we have one.

            gr_event = gr_event.next

    # Saving time interval guessing info.

    previous_guess_time = None

    for interval in guess_info_list:

        guess_time = round(interval[0] * 1000)

        if previous_guess_time is not None:

            guess_time = (
                max(guess_time, previous_guess_time + 1))

        previous_guess_time = guess_time

        eaf.add_annotation(
            'time guess mark',
            guess_time,
            max(
                round(interval[1] * 1000),
                guess_time + 1))

    # Saving EAF file.

    eaf.header['TIME_UNITS'] = 'milliseconds'

    eaf.to_file(eaf_file_path)


def main_convert_exb(args):
    """
    Convertion of an Exmaralda markup file from an INEL corpus to 5-tier compatible EAF file.
    """

    exb_path = args[0]
    eaf_path = args[1]

    duration = (
        None if len(args) <= 2 else ast.literal_eval(args[2]))

    duration_str = (
        repr(None) if duration is None else '{:.3f}s'.format(duration))

    log.debug(
        '\nexb_path:\n{}'
        '\neaf_path:\n{}'
        '\nduration:\n{}'.format(
            exb_path,
            eaf_path,
            duration_str))

    exb_to_eaf(
        exb_path,
        eaf_path,
        duration)


ext_skip_set = set(['', '.coma', '.exs', '.pdf'])


def main_convert_corpus(args):
    """
    Converts INEL corpus from a .zip archive to collection of 5-tier compatible EAF files.
    """

    corpus_file_path = args[0]
    output_dir_path = args[1]

    __debug_flag__ = (
        len(args) > 2 and args[2] == '--debug')

    exb_eaf_list = []
    sound_dict = collections.defaultdict(set)
    duration_dict = {}

    with zipfile.ZipFile(corpus_file_path) as corpus_zip_file:

        for zip_info in corpus_zip_file.infolist():

            name, ext = os.path.splitext(zip_info.filename)

            # Saving .exb Exmaralda markup file info later convertion, as we prefer to process sounds first.

            if ext == '.exb':

                eaf_file_path = (
                    os.path.join(output_dir_path, name + '.eaf'))

                os.makedirs(
                    os.path.dirname(eaf_file_path),
                    exist_ok = True)

                if not os.path.exists(eaf_file_path):

                    exb_eaf_list.append(
                        (name, zip_info.filename, eaf_file_path))

                    log.debug(
                        '\n{} -> eaf delayed'.format(
                            zip_info.filename))

                else:

                    log.debug(
                        '\n{}: eaf exists'.format(
                            zip_info.filename))

            # Converting .wav file to FLAC, noting that we have a FLAC sound recording.

            elif ext == '.wav':

                flac_file_path = (
                    os.path.join(output_dir_path, name + '.flac'))

                if not os.path.exists(flac_file_path):

                    log.debug(
                        '\n{} -> flac'.format(
                            zip_info.filename))

                    with tempfile.NamedTemporaryFile() as temporary_file:

                        with corpus_zip_file.open(zip_info.filename) as wav_file:
                            shutil.copyfileobj(wav_file, temporary_file)

                        temporary_file.flush()

                        call_list = [
                            'ffmpeg',
                            '-f', 'wav',
                            '-i',
                            temporary_file.name,
                            '-f', 'flac',
                            flac_file_path]

                        log.debug(
                            '\n' + repr(call_list))

                        subprocess.check_call(
                            call_list)

                else:

                    log.debug(
                        '\n{}: flac exists'.format(
                            zip_info.filename))

                sound_dict[name].update(('.wav', '.flac'))

                # Saving sound recording duration, if required.

                if name not in duration_dict:

                    raise NotImplementedError

            # Noting that we have an MP3 sound recording.

            elif ext == '.mp3':

                log.debug(
                    '\n{}'.format(
                        zip_info.filename))

                sound_dict[name].add('.mp3')

                # Saving sound recording duration, if required.

                if name not in duration_dict:

                    with tempfile.NamedTemporaryFile() as temporary_file:

                        with corpus_zip_file.open(zip_info.filename) as mp3_file:
                            shutil.copyfileobj(mp3_file, temporary_file)

                        result = (

                            subprocess.check_output([
                                'ffprobe',
                                '-f', 'mp3',
                                '-i',
                                temporary_file.name,
                                '-show_entries',
                                'format=duration',
                                '-v',
                                'quiet',
                                '-of',
                                'csv=p=0']))

                        duration_dict[name] = float(result)

            # Extension we don't know what to do with.

            elif ext not in ext_skip_set:

                log.debug(
                    '\nzip_info.filename: {}'
                    '\nname: {}'
                    '\next: {}'.format(
                        zip_info.filename,
                        name,
                        ext))

                raise NotImplementedError

        # Converting .exb files to .eaf.

        for name, zip_filename, eaf_file_path in exb_eaf_list:

            duration = (
                duration_dict.get(name))

            duration_str = (
                repr(None) if duration is None else '{:.3f}s'.format(duration))

            log.debug(
                '\n{} [{}] -> eaf'.format(
                    zip_filename,
                    duration_str))

            with corpus_zip_file.open(zip_filename) as exb_file:

                exb_to_eaf(
                    exb_file,
                    eaf_file_path,
                    duration_dict.get(name),
                    sound_dict.get(name),
                    __debug_flag__)


def main_upload_corpus(args):
    """
    Converts INEL corpus from a .zip archive to collection of 5-tier compatible EAF files and uploads it to
    a specified Lingvodoc server.
    """

    corpus_file_path = args[0]
    output_dir_path = args[1]

    # Command-line options.

    opt_list, arg_list = (

        getopt.gnu_getopt(args[2:], '', [
            'cookies-dict=',
            'debug',
            'dialect-coma=',
            'graphql-url=',
            'language-id=',
            'language-name=',
            'limit=',]))

    opt_dict = dict(opt_list)

    cookies_dict = (
        ast.literal_eval(opt_dict['--cookies-dict']))

    dialect_flag = (
        '--dialect-coma' in opt_dict)

    language_id = (
        ast.literal_eval(opt_dict['--language-id']))
    
    language_name = (
        opt_dict['--language-name'])

    limit = (
        ast.literal_eval(opt_dict['--limit']) if '--limit' in opt_dict else
        None)

    # Loading dialect info, if required.

    if '--dialect-coma' in opt_dict:

        dialect_dict = {}

        dialect_str_map = {
            'Chaya': 'Lower-Chaya',
            'Baikha': 'Northern',
            'Ket': 'Ket',
            'Narym': 'Narym',
            'Narym/Tym': 'Narym',
            'Ob': 'Ob',
            'Taz': 'Northern',
            'Tym': 'Tym',
            'Upper Tolka': 'Northern'}

        dialect_id_map = {
            'Lower-Chaya': [3602, 5],
            'Ket': [302, 4],
            'Narym': [33, 87],
            'Northern': [2045, 2048],
            'Tym': [3619, 5],
            'Ob': [2111, 84]}

        log.debug(
            '\ndialect_str_map:\n' +
            pprint.pformat(dialect_str_map))

        tree = (
            ElementTree.parse(opt_dict['--dialect-coma']))

        root = (
            tree.getroot())

        mismatch_list = []

        # Looking through all communication infos.

        for communication_xml in root.iter('Communication'):

            description_xml = (
                communication_xml.find('Description'))

            genre_str = None
            dialect_str = None
            speaker_str = None

            for key_xml in description_xml.iter('Key'):

                key_name = (
                    key_xml.get('Name'))
                
                if key_name == '1 Genre':

                    if genre_str is not None:
                        raise NotImplementedError

                    genre_str = key_xml.text
                
                elif key_name == '3b Dialect':

                    if dialect_str is not None:
                        raise NotImplementedError

                    dialect_str = key_xml.text

                elif key_name == '4 Speakers':

                    if speaker_str is not None:
                        raise NotImplementedError

                    speaker_str = key_xml.text

            if (genre_str is None or
                dialect_str is None or
                speaker_str is None):

                raise NotImplementedError

            speaker_str_a = (
                re.sub(r',\s+', '_', speaker_str))

            # Finding .exb file entry, to get speaker info consistent with our .eaf files.

            speaker_str_b = None

            for transcription_xml in communication_xml.iter('Transcription'):

                filename = (
                    transcription_xml.find('Filename').text)

                name, ext = (
                    os.path.splitext(filename))

                if ext == '.exb':

                    match = (

                        re.fullmatch(
                            r'(.*?)_\d+[^_]*?_.*?(?:_' + genre_str + ')?',
                            name))

                    speaker_str_b = match.group(1)
                    break

            if speaker_str_b is None:
                raise NotImplementedError

            if speaker_str_b != speaker_str_a:

                mismatch_list.append(
                    (filename, speaker_str_b, speaker_str_a))

            if speaker_str_b in dialect_str:
                raise NotImplementedError

            dialect_dict[speaker_str_b] = (
                dialect_id_map[dialect_str_map[dialect_str]])

        log.debug(
            '\ndialect_dict:\n' +
            pprint.pformat(dialect_dict, width = 192))
    
    # __VARIANT__

#   # Selkup dialects' data partition info.

#   dialect_dict = {

#       (304, 2): [ # Selkup Ket
#           ('BAG', '1964'),
#           ('KMS', '1963'),
#           ('SVG', '1964'),
#           ('PES', '1964'),
#           ('SyVI', '1964'),
#           ('ZIF', '1963')],

#       (33, 87): [ # Selkup Narym
#           ('IAI', '1968')],

#       'Tym': [ # Selkup Tym
#           ('KFN', '1965'),
#           ('SG', '196X'),
#           ('YIF', '1968')],

#       (2045, 2048): [ # Selkup Northern
#           ('AR', '1965'),
#           ('DN', '196X'),
#           ('KAI', '1965'),
#           ('KGE', '1965'),
#           ('KIA', '1965'),
#           ('KMG', '1976'),
#           ('KMI', '1976'),
#           ('KNK', '1965'),
#           ('KNM', '196X'),
#           ('KNS', '1966'),
#           ('KPG', '1969'),
#           ('KPM', '1977'),
#           ('KR', '1969'),
#           ('KTP', '196X'),
#           ('KVS', '1965'),
#           ('KuLP', '1976'),
#           ('KuMI', '196X'),
#           ('MMS', '196X'),
#           ('MNA', '1965'),
#           ('NAI', '1965'),
#           ('NEP', '1965'),
#           ('NN1', '1976'),
#           ('NN2', '196X'),
#           ('NST', '1965'),
#           ('NVA', '1965'),
#           ('PL', '1965'),
#           ('SAG', '1965'),
#           ('SAI', '1965'),
#           ('SAIAI', '1965'),
#           ('SAIAn', '1965'),
#           ('SMI', '1965'),
#           ('SMV', '196X'),
#           ('TAV', '1965'),
#           ('TVP', '1965')]}

#   if dialect_flag:

#       speaker_dialect_dict = {}

#       for dialect_id, key_str_list in dialect_dict.items():
#           for speaker_str, date_str in key_str_list:

#               if speaker_str in speaker_dialect_dict:
#                   raise NotImplementedError

#               speaker_dialect_dict[speaker_str] = (dialect_id, date_str)

    # Going through INEL corpus data.

    exb_eaf_list = []
    sound_dict = collections.defaultdict(dict)
    duration_dict = {}

    upload_list = []

    with zipfile.ZipFile(corpus_file_path) as corpus_zip_file:

        info_list = (
            corpus_zip_file.infolist())

        if limit is not None:

            info_list = info_list[:limit]

        for zip_info in info_list:

            name, ext = os.path.splitext(zip_info.filename)

            # Saving .exb Exmaralda markup file info later convertion, as we prefer to process sounds first.

            if ext == '.exb':

                eaf_file_path = (
                    os.path.join(output_dir_path, name + '.eaf'))

                os.makedirs(
                    os.path.dirname(eaf_file_path),
                    exist_ok = True)

                if not os.path.exists(eaf_file_path):

                    exb_eaf_list.append(
                        (name, zip_info.filename, eaf_file_path))

                    log.debug(
                        '\n{} -> eaf delayed'.format(
                            zip_info.filename))

                else:

                    log.debug(
                        '\n{}: eaf exists'.format(
                            zip_info.filename))

                upload_list.append((eaf_file_path, name))

            # Converting .wav file to FLAC, noting that we have a FLAC sound recording.

            elif ext == '.wav':

                flac_file_path = (
                    os.path.join(output_dir_path, name + '.flac'))

                if not os.path.exists(flac_file_path):

                    log.debug(
                        '\n{} -> flac'.format(
                            zip_info.filename))

                    with tempfile.NamedTemporaryFile() as temporary_file:

                        with corpus_zip_file.open(zip_info.filename) as wav_file:
                            shutil.copyfileobj(wav_file, temporary_file)

                        temporary_file.flush()

                        call_list = [
                            'ffmpeg',
                            '-f', 'wav',
                            '-i',
                            temporary_file.name,
                            '-f', 'flac',
                            flac_file_path]

                        log.debug(
                            '\n' + repr(call_list))

                        subprocess.check_call(
                            call_list)

                else:

                    log.debug(
                        '\n{}: flac exists'.format(
                            zip_info.filename))

                sound_dict[name]['.wav'] = zip_info
                sound_dict[name]['.flac'] = flac_file_path

                # Saving sound recording duration, if required.

                if name not in duration_dict:

                    raise NotImplementedError

            # Noting that we have an MP3 sound recording.

            elif ext == '.mp3':

                log.debug(
                    '\n{}'.format(
                        zip_info.filename))

                sound_dict[name]['.mp3'] = zip_info

                # Saving sound recording duration, if required.

                if name not in duration_dict:

                    with tempfile.NamedTemporaryFile() as temporary_file:

                        with corpus_zip_file.open(zip_info.filename) as mp3_file:
                            shutil.copyfileobj(mp3_file, temporary_file)

                        result = (

                            subprocess.check_output([
                                'ffprobe',
                                '-f', 'mp3',
                                '-i',
                                temporary_file.name,
                                '-show_entries',
                                'format=duration',
                                '-v',
                                'quiet',
                                '-of',
                                'csv=p=0']))

                        duration_dict[name] = float(result)

            # Extension we don't know what to do with.

            elif ext not in ext_skip_set:

                log.debug(
                    '\nzip_info.filename: {}'
                    '\nname: {}'
                    '\next: {}'.format(
                        zip_info.filename,
                        name,
                        ext))

                raise NotImplementedError

        # Converting .exb files to .eaf.

        for name, zip_filename, eaf_file_path in exb_eaf_list:

            duration = (
                duration_dict.get(name))

            duration_str = (
                repr(None) if duration is None else '{:.3f}s'.format(duration))

            log.debug(
                '\n{} [{}] -> eaf'.format(
                    zip_filename,
                    duration_str))

            with corpus_zip_file.open(zip_filename) as exb_file:

                exb_to_eaf(
                    exb_file,
                    eaf_file_path,
                    duration_dict.get(name),
                    sound_dict.get(name).keys(),
                    __debug_flag__)

        # Getting ready to upload .eaf files with audio, starting by grouping by speaker.

        upload_list.sort(
            key = lambda upload: upload[1])

        log.debug(
            '\nupload_list:\n' +
            pprint.pformat(upload_list, width = 192))

        log.debug(
            '\nsound_dict:\n' +
            pprint.pformat(sound_dict, width = 192))

        speaker_dict = collections.OrderedDict()

        for eaf_file_path, name in upload_list:

            dirname, base_name = os.path.split(name)
            type_name, dir_name = os.path.split(dirname)

            log.debug(
                '\n{}\n{}\n{}'.format(
                    repr(eaf_file_path),
                    repr(name),
                    [type_name, dir_name, base_name]))

            match = (

                re.fullmatch(
                    r'(.*?)_(\d+[^_]*?)_(.*?)(?:_' + type_name + ')?',
                    base_name))

            speaker_str, date_str, title_str = match.groups()

            if speaker_str not in speaker_dict:
                speaker_dict[speaker_str] = []

            speaker_dict[speaker_str].append(
                    
                (eaf_file_path, name,
                    type_name, dir_name, base_name,
                    speaker_str, date_str, title_str))

        # __VARIANT__

#       # Checking consistency of speaker separation by dialects, if required.

#       if dialect_flag:

#           inconsistency_flag = False

#           for speaker_str, speaker_info_list in speaker_dict.items():

#               if speaker_str not in speaker_dialect_dict:
#                   continue

#               dialect_id, dialect_date_str = speaker_dialect_dict[speaker_str]

#               in_list = []
#               out_list = []

#               for speaker_info in speaker_info_list:

#                   _, name, type_name, dir_name, base_name, speaker_str, date_str, title_str = (
#                       speaker_info)

#                   ((in_list if date_str == dialect_date_str else out_list)
#                       .append(base_name))

#               if not in_list or out_list:

#                   log.debug(
#                       '\ninconsistency'
#                       '\nspeaker: {}, {}'
#                       '\n{}\n{}'.format(
#                           speaker_str,
#                           dialect_date_str,
#                           in_list, out_list))

#           if inconsistency_flag:
#               raise NotImplementedError

#       raise NotImplementedError

        # Going by speakers, creating corpora and uploading data.

        log.debug(
            '\nspeaker_dict:\n' +
            pprint.pformat(speaker_dict, width = 192))

        for speaker_str, speaker_info_list in speaker_dict.items():

            # Creating corpus for speaker's data.

            query_str = '''

                mutation create_dictionary(
                  $category: Int!,
                  $parent_id: LingvodocID!,
                  $translation_atoms: [ObjectVal]!,
                  $perspectives: [ObjectVal]!,
                  $additional_metadata: ObjectVal)
                {
                  create_dictionary(
                    category: $category,
                    parent_id: $parent_id,
                    translation_atoms: $translation_atoms,
                    perspectives: $perspectives,
                    additional_metadata: $additional_metadata)
                  {
                    dictionary
                    {
                      id
                      perspectives
                      {
                        id
                      }
                    }
                  }
                }

                '''

            variable_dict = {
                    
                'category': 1,

                'parent_id': language_id,

                'translation_atoms': [{
                    'content': 'INEL {} 1.0 {} corpus'.format(
                        language_name,
                        speaker_str),
                    'locale_id': 2}],

                'perspectives': [{
                    'fake_id': 0,
                    'fields': [
                        {'fake_id': '6f355d7a-e68d-44ab-9cf6-36f78e8f1b34',
                            'field_id': [66, 12],
                            'link_id': None,
                            'self_id': None},
                        {'fake_id': '4e299305-94fd-4939-bc35-61cfda5b4fce',
                            'field_id': [66, 23],
                            'link_id': None,
                            'self_id': '6f355d7a-e68d-44ab-9cf6-36f78e8f1b34'},
                        {'fake_id': '51fbe0b6-2cea-4d40-a994-f6bb6f501d48',
                            'field_id': [66, 23],
                            'link_id': None,
                            'self_id': None},
                        {'fake_id': '0ba8e515-e9d5-42c5-a25c-c616297b5b60',
                            'field_id': [674, 5],
                            'link_id': None,
                            'self_id': None}],
                    'translation_atoms': [{
                        'content': speaker_str, 'locale_id': 2}]}],

                'additional_metadata': {
                    'authors': [],
                    'bibliographicDataOfTheSource': '',
                    'bibliographicDataOfTheTranslation': '',
                    'genre': '',
                    'humanSettlement': [],
                    'kind': 'Expedition',
                    'license': 'cc-by-nc-sa-4.0',
                    'quantitativeCharacteristic': '',
                    'timeOfWriting': '',
                    'titleOfTheWork': '',
                    'translator': '',
                    'years': []}}

            if (dialect_flag and
                speaker_str in dialect_dict):

                variable_dict['parent_id'] = (
                    dialect_dict[speaker_str])

            log.debug(
                '\nquery_str:\n{}\nvariable_dict:\n{}'.format(
                    textwrap.dedent(query_str).strip(),
                    pprint.pformat(variable_dict, width = 192)))

            result = (

                requests.post(
                    opt_dict['--graphql-url'],
                    cookies = cookies_dict,
                    json = {'query': query_str, 'variables': variable_dict}))

            log.debug(
                '\nresult.text:\n' +
                repr(result.text))

            result_dict = (
                result.json()['data']['create_dictionary'])

            log.debug(
                '\nresult_dict:\n' +
                pprint.pformat(result_dict, width = 192))

            corpus_id = (
                result_dict['dictionary']['perspectives'][0]['id'])

            # Now uploading each markup with possibly attached audio.

            for speaker_info in speaker_info_list:

                eaf_file_path, name, type_name, dir_name, base_name, speaker_str, date_str, title_str = (
                    speaker_info)

                # Creating a lexical entry.

                query_str = '''

                    mutation create_lexicalentry(
                      $perspective_id: LingvodocID!)
                    {
                      create_lexicalentry(
                        perspective_id: $perspective_id)
                      {
                        lexicalentry
                        {
                          id
                        }
                      }
                    }

                    '''

                variable_dict = (
                    {'perspective_id': corpus_id})

                log.debug(
                    '\nquery_str:\n{}\nvariable_dict:\n{}'.format(
                        textwrap.dedent(query_str).strip(),
                        pprint.pformat(variable_dict, width = 192)))

                result = (

                    requests.post(
                        opt_dict['--graphql-url'],
                        cookies = cookies_dict,
                        json = {
                            'query': query_str,
                            'variables': variable_dict}))

                log.debug(
                    '\nresult.text:\n' +
                    repr(result.text))

                result_dict = (
                    result.json()['data']['create_lexicalentry'])

                entry_id = (
                    result_dict['lexicalentry']['id'])

                log.debug(
                    '\nresult_dict:\n' +
                    pprint.pformat(result_dict, width = 192))

                # If we have audio, upload it first.

                sound_entity_id = None
                audio_info_dict = sound_dict.get(name)

                if audio_info_dict:

                    if '.flac' in audio_info_dict:

                        audio_file = (

                            open(
                                audio_info_dict['.flac'], 'rb'))

                        audio_file_name = base_name + '.flac'
                        audio_file_ct = 'audio/flac'

                    else:

                        if ('.wav' in audio_info_dict or
                            '.mp3' not in audio_info_dict):

                            raise NotImplementedError

                        audio_file = (

                            corpus_zip_file.open(
                                audio_info_dict['.mp3'].filename, 'r'))

                        audio_file_name = base_name + '.mp3'
                        audio_file_ct = 'audio/mp3'

                    query_str = '''

                        mutation createEntity(
                          $parent_id: LingvodocID!,
                          $field_id: LingvodocID!,
                          $file_content: Upload)
                        {
                          create_entity(
                            parent_id: $parent_id,
                            field_id: $field_id,
                            file_content: $file_content)
                          {
                            entity
                            {
                              id
                            }
                          }
                        }
                        '''

                    variable_dict = {
                        'parent_id': entry_id,
                        'field_id': [66, 12],
                        'file_content': None}

                    operations_str = (
                            
                        json.dumps({
                            'query': re.sub(r'\s+', ' ', query_str).strip(),
                            'variables': variable_dict}))

                    # See https://stackoverflow.com/a/12385661/2016856 for example of None for multipart
                    # file name.

                    file_list = [
                        ('operations', (None, operations_str)),
                        ('map', (None, json.dumps({'0': ['variables.file_content']}))),
                        ('0', (audio_file_name, audio_file, audio_file_ct))]

                    log.debug(
                        '\nquery_str:\n{}'
                        '\nvariable_dict:\n{}'
                        '\nfile_list:\n{}'.format(
                            textwrap.dedent(query_str).strip(),
                            pprint.pformat(variable_dict, width = 192),
                            pprint.pformat(file_list, width = 192)))

                    result = (
                            
                        requests.post(
                            opt_dict['--graphql-url'],
                            cookies = cookies_dict,
                            files = file_list))

                    log.debug(
                        '\nresult.text:\n' +
                        repr(result.text))

                    result_dict = (
                        result.json()['data']['create_entity'])

                    sound_entity_id = (
                        result_dict['entity']['id'])

                    log.debug(
                        '\nresult_dict:\n' +
                        pprint.pformat(result_dict, width = 192))

                    audio_file.close()

                # And now we will upload markup.

                markup_file = (

                    open(
                        eaf_file_path, 'rb'))

                markup_file_name = base_name + '.eaf'
                markup_file_ct = 'application/octet-stream'

                query_str = '''

                    mutation createEntity(
                      $parent_id: LingvodocID!,
                      $field_id: LingvodocID!,
                      $self_id: LingvodocID,
                      $file_content: Upload)
                    {
                      create_entity(
                        parent_id: $parent_id,
                        field_id: $field_id,
                        self_id: $self_id,
                        file_content: $file_content)
                      {
                        entity
                        {
                          id
                        }
                      }
                    }
                    '''

                variable_dict = {
                    'parent_id': entry_id,
                    'field_id': [66, 23],
                    'self_id': sound_entity_id,
                    'file_content': None}

                operations_str = (
                        
                    json.dumps({
                        'query': re.sub(r'\s+', ' ', query_str).strip(),
                        'variables': variable_dict}))

                file_list = [
                    ('operations', (None, operations_str)),
                    ('map', (None, json.dumps({'0': ['variables.file_content']}))),
                    ('0', (markup_file_name, markup_file, markup_file_ct))]

                log.debug(
                    '\nquery_str:\n{}'
                    '\nvariable_dict:\n{}'
                    '\nfile_list:\n{}'.format(
                        textwrap.dedent(query_str).strip(),
                        pprint.pformat(variable_dict, width = 192),
                        pprint.pformat(file_list, width = 192)))

                result = (
                        
                    requests.post(
                        opt_dict['--graphql-url'],
                        cookies = cookies_dict,
                        files = file_list))

                log.debug(
                    '\nresult.text:\n' +
                    repr(result.text))

                result_dict = (
                    result.json()['data']['create_entity'])

                log.debug(
                    '\nresult_dict:\n' +
                    pprint.pformat(result_dict, width = 192))

                markup_file.close()


# If we are being run as a script.

if __name__ == '__main__':

    if (len(sys.argv) > 1 and
        sys.argv[1] == '-config'):

        # We have a configuration file; initializing DB, if required, and logging.

        config_path = sys.argv[2]

        if sys.argv[3] != '-no-db':

            pyramid_env = paster.bootstrap(config_path)
            arg_list = sys.argv[3:]

        else:
            arg_list = sys.argv[4:]

        paster.setup_logging(config_path)
        log = logging.getLogger(__name__)

    else:

        # No config file, so just logging to stdout.

        arg_list = sys.argv[1:]

        log_root = logging.getLogger()
        log_root.setLevel(logging.DEBUG)

        log_handler = logging.StreamHandler(sys.stdout)
        log_handler.setLevel(logging.DEBUG)

        log_formatter = (
                
            logging.Formatter(
                '%(asctime)s %(levelname)-5.5s [%(name)s][%(threadName)s] '
                '%(pathname)s:%(lineno)d: %(message)s'))

        log_handler.setFormatter(log_formatter)
        log_root.addHandler(log_handler)

        log = logging.getLogger(__name__)

    # Doing what we need.

    if len(arg_list) <= 0:

        log.info(
            '\nPlease specify a command to execute.')

    elif arg_list[0] == 'convert_exb':

        main_convert_exb(arg_list[1:])

    elif arg_list[0] == 'convert_corpus':

        main_convert_corpus(arg_list[1:])

    elif arg_list[0] == 'upload_corpus':

        main_upload_corpus(arg_list[1:])

    else:

        log.warn(
            '\nUnknown command \'{0}\'.'.format(arg_list[0]))

