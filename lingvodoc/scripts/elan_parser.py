# -*- coding: utf-8 -*-

import bisect
import re
import pympi

import collections
try: from xml.etree import cElementTree as ElementTree
except ImportError: from xml.etree import ElementTree

def hyphen_to_dash(string_with_hyphen):
    if not string_with_hyphen:
        return string_with_hyphen
    restricted_symbs = ["\xad",  # Soft hyphen
                        "\xAF",  # Spacing macron
                        "\x96", # en dash
                        "\u2013",
                        "\x97", # em dash
                        "\u2014"
                        ]
    for symbol in restricted_symbs:
        string_with_hyphen = string_with_hyphen.replace(symbol, "-")
    return string_with_hyphen

class Word:
    def __init__(self, index=None, text=None, tier=None, time=None):
        self.index = index
        self.text = self.strip(text)
        self.tier = tier
        self.time = time

    def __repr__(self):
        return f'<{repr(self.index)}, {repr(self.text)}, {repr(self.tier)}, {self.time}>'

    def strip(self, string):
        if type(string) is str:
            return hyphen_to_dash(string.strip())
        return string

    def get_tuple(self):
        return((self.index, self.text, self.tier, self.time))

class Elan:
    def __init__(self, eaf_path):

        self.result = collections.OrderedDict()
        self.word_tier = {}
        self.tiers = []
        self.top_tiers = set()
        self.tier_refs = collections.defaultdict(set)
        self.word = {}
        self.main_tier_elements = []
        self.reader = ElementTree.parse(eaf_path)
        self.xml_obj = self.reader.getroot()
        self.eafob = pympi.Elan.Eaf(eaf_path)



    def get_annotation_data_for_tier(self, id_tier):
        a = self.eafob.tiers[id_tier][0]
        return [(self.eafob.timeslots[a[b][0]], self.eafob.timeslots[a[b][1]], a[b][2])
                for b in a]

    def get_annotation_data_between_times(self, id_tier, start, end):
        tier_data = self.eafob.tiers[id_tier][0]
        anns = ((self.eafob.timeslots[tier_data[a][0]], self.eafob.timeslots[tier_data[a][1]], a)
                for a in tier_data)
        sorted_words = sorted([a for a in anns if a[0] >= start and a[1] <= end],  key=lambda time_tup: time_tup[1] )
        return [x for x in sorted_words]
        #sorted([a[2] for a in anns if a[1] >= start and a[0] <= end],  key=lambda time_tup: time_tup[0] )


    def parse(self, debug_flag=False):

        # Choosing top-level text tier as first top-level tier referring to 'literary translation' and
        # 'translation' tiers.

        for element in self.xml_obj:
            if element.tag == 'TIER':
                tier_id = element.attrib['TIER_ID']
                if 'PARENT_REF' in element.attrib:
                    tier_ref = element.attrib['PARENT_REF']
                    self.tier_refs[tier_ref].add(tier_id)
                else:
                    self.top_tiers.add(tier_id)
                self.tiers.append(tier_id)

        self.top_level_tier = None

        for tier_id in self.tier_refs:
            if self.tier_refs[tier_id].issuperset(('literary translation', 'translation')):
                self.top_level_tier = tier_id

        if self.top_level_tier is None:
            raise NotImplementedError

        translation_list = None

        def find_by_time_slot(time_from, time_to):

            nonlocal translation_list

            if translation_list is None:

                translation_list = (

                    sorted(

                        [(self.eafob.timeslots[data[0]], 
                            self.eafob.timeslots[data[1]],
                            data[2],
                            id)

                            for id, data in self.eafob.tiers['translation'][0].items()],

                        key = lambda item: item[0]))

            index = (

                bisect.bisect_left(
                    translation_list,
                    (time_from, time_to)))

            while index < len(translation_list):

                translation = translation_list[index]

                if time_from >= translation[0] and time_to <= translation[1]:
                    return translation[3]

                elif time_from > translation[1]:
                    break

            return None

        for element in self.xml_obj:

            if element.tag != 'TIER':
                continue

            tier_id = element.attrib['TIER_ID']
            tier_parent_ref = element.attrib.get('PARENT_REF')

            for elem1 in element:

                if elem1.tag != 'ANNOTATION':
                    continue

                for elem2 in elem1:

                    annotation_id = elem2.attrib["ANNOTATION_ID"]

                    # Get text value and tier id of current element
                    self.word[annotation_id] = [x for x in elem2][0].text
                    self.word_tier[annotation_id] = tier_id

                    # Collect annotation ids for 'translation' tier
                    if tier_id == "translation":
                        self.main_tier_elements.append(annotation_id)

                    # Collect annotation ids to dictionary by parent annotation id ('text' or 'translation')
                    if elem2.tag == 'REF_ANNOTATION':
                        annot_ref = elem2.attrib['ANNOTATION_REF']
                        if not annot_ref in self.result:
                            self.result[annot_ref] = []
                        self.result[annot_ref].append(annotation_id)

                    # If we have an improperly linked 'transcription' or 'word' sub-tier of 'translation'
                    # tier, with 'Included In' type instead of 'Symbolic Association', we still try to get
                    # its contents.

                    elif (
                        elem2.tag == 'ALIGNABLE_ANNOTATION' and
                        (tier_id.lower() == 'transcription' or tier_id.lower() == 'word') and
                        tier_parent_ref.lower() == 'translation'):

                        time_from = self.eafob.timeslots[elem2.attrib['TIME_SLOT_REF1']]
                        time_to = self.eafob.timeslots[elem2.attrib['TIME_SLOT_REF2']]

                        annot_ref = (
                            find_by_time_slot(time_from, time_to))

                        if annot_ref:

                            if not annot_ref in self.result:
                                self.result[annot_ref] = []

                            self.result[annot_ref].append(annotation_id)

                    if debug_flag:
                        print(f'*** {self.word_tier[annotation_id]}: {self.word[annotation_id]}')

    def get_word_text(self, word):
        return list(word)[0].text

    def get_word_aid(self, word):
        return word.attrib['ANNOTATION_ID']

    def preview(self):
        preview_dict = collections.defaultdict(list)

        text_an = min(
                self.eafob.get_annotation_data_for_tier(self.top_level_tier),
                key = lambda time_tup: time_tup[0])

        for top_tier in 'text', 'translation':
            for i in self.get_annotation_data_between_times(top_tier, text_an[0], text_an[1]):
                preview_dict[top_tier].append(self.word[i[2]])
                if i[2] in self.result:
                    for j in self.result[i[2]]:
                        preview_dict[self.word_tier[j]].append(self.word[j])

        return preview_dict

    def proc(self, debug_flag=False):

        # Get sub-tiers of 'translation' tier
        res = {}
        for aid in self.main_tier_elements:
            res[aid] = []
            if aid in self.result:
                for next_id in self.result[aid]:
                    res[aid].append(next_id)
            #else: 1st paradigm has 1 column

        perspectives = []

        # Sort top_level_tier ('text') annotation ids chronologically
        ans = sorted(
                self.eafob.get_annotation_data_for_tier(self.top_level_tier),
                key = lambda time_tup: time_tup[0])

        for text_an in ans:
            complex_list = []
            raw_dict = collections.OrderedDict()
            cur_tier = "translation"
            for data in self.get_annotation_data_between_times(cur_tier, text_an[0], text_an[1]):
                time_tup = (data[0], data[1])
                translation_data = data[2]

                # Dictionary of Words with real tier names

                if raw_list := [Word(i, self.word[i], self.word_tier[i], (time_tup[0], time_tup[1])) for i in res[translation_data]]:
                    raw_dict[Word(translation_data, self.word[translation_data], cur_tier, (time_tup[0], time_tup[1]))] = raw_list

                transcription_data = ""
                word_data = ""

                if res[translation_data]:
                    transcription_data = res[translation_data][0]
                if len(res[translation_data]) > 1:
                    word_data = res[translation_data][1]

                tr_text = hyphen_to_dash(self.word[translation_data])

                if type(tr_text) is str:
                    mark = re.search('[-.][\dA-Z]+', tr_text)
                    if (mark and not re.search("[-]INF", tr_text)
                             and not re.search("[-]SG.NOM", tr_text)
                             and not re.search("[-]NOM", tr_text)):

                        tag = re.search("[1-3][Dd][Uu]|[1-3][Pp][Ll]|[1-3][Ss][Gg]", tr_text)

                        if tag and tr_text != tag.group(0) or not tag:
                            mixed_list = []
                            if word_data:
                                mixed_list.append([Word(word_data,
                                                             self.word[word_data],
                                                             "Word of Paradigmatic forms",
                                                             (time_tup[0], time_tup[1])) ])
                            if transcription_data:
                                mixed_list.append([Word(transcription_data,
                                                             self.word[transcription_data], "text",
                                                             (time_tup[0], time_tup[1])) ])
                            if translation_data:
                                mixed_list.append([Word(translation_data,
                                                             self.word[translation_data],
                                                             "literary translation",
                                                             (time_tup[0], time_tup[1])) ])

                            # 'perspectives' list additional element
                            #  if found mark:
                            #
                            # [ [Word_aliased_word],
                            #   [Word_aliased_transcription],
                            #   [Word_aliased_translation] ]
                            #
                            perspectives.append(mixed_list)

            # 'perspectives' list regular element:
            #
            # [ [Word(s)_text],
            #   [Word_literary_translation],
            #   [Word_other_text],
            #   { Word_translation: [
            #       Word_transcription,
            #       Word_word
            #   ] }
            # ]
            #
            complex_list.append([
                Word(i[2], self.word[i[2]], 'text', (i[0], i[1]))
                for i in self.get_annotation_data_between_times(self.top_level_tier, text_an[0], text_an[1])])

            for cur_tier in "literary translation", "other text":
                for i in self.get_annotation_data_between_times(self.top_level_tier, text_an[0], text_an[1]):
                    if i[2] in self.result:
                        for j in self.result[i[2]]:
                            if self.word_tier[j] == cur_tier:
                                complex_list.append([Word(j, self.word[j], cur_tier, (i[0], i[1]))]) #time from text

            # 'raw_dict' goes at the end of 'complex_list'
            if raw_dict:
                complex_list.append(raw_dict)

            perspectives.append(complex_list)

        return perspectives


class ElanCheck:

    def __init__(self, eaf_path):
        self.top_tier_list = []
        self.tier_refs = collections.defaultdict(set)
        self.reader = ElementTree.parse(eaf_path)
        self.xml_obj = self.reader.getroot()
        self.edge_dict = collections.defaultdict(set)
        self.lingv_type = {}

    def parse(self):
        for element in self.xml_obj:
            if element.tag == 'TIER':
                tier_id = element.attrib['TIER_ID']
                if 'PARENT_REF' in element.attrib:
                    tier_ref = element.attrib['PARENT_REF']
                    self.edge_dict[tier_ref].add((
                        tier_id,
                        element.attrib["LINGUISTIC_TYPE_REF"]))
                    self.tier_refs[tier_ref].add(tier_id)
                else:
                    self.top_tier_list.append(tier_id)
            elif element.tag == "LINGUISTIC_TYPE":
                at = element.attrib
                if "CONSTRAINTS" in at:
                    ling_type = at["CONSTRAINTS"]
                    id = at["LINGUISTIC_TYPE_ID"]
                    is_time_alignable = at["TIME_ALIGNABLE"]
                    self.lingv_type[id] = (ling_type, is_time_alignable)

    def check(self):
        """
        Accepting EAF if we have a top-level tier with required sub-tiers.
        """

        # We got to have a translation tier with two dependent transcription and word tiers.

        if ('translation' not in self.tier_refs or
            not self.tier_refs['translation'].issuperset(('transcription', 'word'))):

            return False

        # And then we have to have a top level tier referencing two translation tiers.

        for tier_id in self.top_tier_list:

            if self.tier_refs[tier_id].issuperset(('literary translation', 'translation')):
                return True

        return False

