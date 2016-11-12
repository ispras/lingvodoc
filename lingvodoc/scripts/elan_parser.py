# -*- coding: utf-8 -*-
import pympi

import collections
try: from xml.etree import cElementTree as ElementTree
except ImportError: from xml.etree import ElementTree


class Word:
    def __init__(self, index=None, text=None, tier=None, time=None):
        self.index = index
        self.text = text
        self.tier = tier
        self.time = time

    def _print(self):
        return((self.index, self.text, self.tier, self.time))

class Elan:
    def __init__(self, eaf_path):
        self.main_tier_name = None

        self.result = collections.OrderedDict()
        self.word_tier = {}
        self.tiers = []
        #self.tier_names = {}
        self.tier_refs = collections.defaultdict(list)
        self.word = {}
        self.main_tier_elements = []
        self.noref_tiers = []
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
        sorted_words = sorted([a for a in anns if a[0] >= start and a[1] <= end],  key=lambda t: t[1] )
        return [x for x in sorted_words]
        #sorted([a[2] for a in anns if a[1] >= start and a[0] <= end],  key=lambda t: t[0] )


    def parse(self):
        d = collections.defaultdict(dict)
        for element in self.xml_obj:
            if element.tag == 'TIER':
                tier_id = element.attrib['TIER_ID']
                if self.main_tier_name is None:
                    self.main_tier_name = tier_id
                if 'PARENT_REF' in element.attrib:
                    tier_ref = element.attrib['PARENT_REF']
                    self.tier_refs[tier_ref].append(tier_id)
                self.tiers.append(tier_id)
                for elem1 in element:
                    if elem1.tag == 'ANNOTATION':
                        for elem2 in elem1:
                            self.word_tier[elem2.attrib["ANNOTATION_ID"]] = tier_id
                            if tier_id == "translation":
                                self.main_tier_elements.append(elem2.attrib["ANNOTATION_ID"])
                            self.word[elem2.attrib["ANNOTATION_ID"]] = [x for x in elem2][0].text
                            if elem2.tag == 'REF_ANNOTATION':
                                annot_ref = elem2.attrib['ANNOTATION_REF']
                                if not annot_ref in self.result:
                                    self.result[annot_ref] = []
                                self.result[annot_ref].append(elem2.attrib["ANNOTATION_ID"])

        return self.main_tier_name

    def get_word_text(self, word):
        return list(word)[0].text

    def get_word_aid(self, word):
        return word.attrib['ANNOTATION_ID']



    def proc(self):
        # print(self.result)
        for tier in self.tiers:
            tier_data = self.get_annotation_data_for_tier(tier)

            if tier_data:
                self.noref_tiers.append(tier)
                # print(tier_data)
                # print(tier)
        res = {}
        for aid in self.main_tier_elements:
            res[aid] = []
            if aid in self.result:
                for next_id in self.result[aid]:
                    res[aid].append(next_id)
            else:
                pass # 1st paradigm has 1 column

            # print(self.word[aid])
            # while next_id in self.result:
            #     print(self.result[next_id])
            #     next_id = self.result[next_id][0]
            #
            #     print(self.word[next_id])
            #     res[aid].append(next_id)
        #print(res["a1"])


        perspectives = []
        ans = sorted(self.eafob.get_annotation_data_for_tier("text"), key=lambda t: t[0]) # text
        for x in ans:
            next = []
            for cur_tier in ["text", "translation", "literary translation"]:
                perspectives2 = collections.OrderedDict()
                if cur_tier == "translation":
                    for k in self.get_annotation_data_between_times(cur_tier, x[0], x[1]):
                        t = (k[0], k[1])
                        z = k[2]
                        new_list = [Word(i, self.word[i], self.word_tier[i], (t[0], t[1])) for i in res[z]]
                        if new_list:
                            perspectives2[Word(z, self.word[z], cur_tier, (t[0], t[1]))] = new_list
                    next.append(perspectives2)
                    #print(perspectives2)
                else:
                    # next.append([Word(i[2] , self.word[i[2]], cur_tier, (i[0], i[1]))])
                    if cur_tier == "text":
                        next.append([Word(i[2] , self.word[i[2]], cur_tier, (i[0], i[1])) for i in self.get_annotation_data_between_times("text", x[0], x[1])])
                    elif cur_tier == "literary translation":
                        for i in self.get_annotation_data_between_times("text", x[0], x[1]):
                            if i[2] in self.result:
                                for j in self.result[i[2]]:
                                    next.append([Word(j , self.word[j], cur_tier, (i[0], i[1])) ]) #time from text

            perspectives.append(next)
        # for x in res:
        #     print( self.word[x], [ self.word[i] for i in res[x]])
        final_dicts = perspectives
        # for x in final_dicts:
        #     print("=========")
        #     for y in x:
        #         if type(y) == list:
        #             for j in y:
        #                 print(j._print())
        #             #print(y)
        #         else:
        #             for j in y:
        #                 print(j._print(), y[j][0]._print(), y[j][1]._print())
        return perspectives
            # return perspectives


class ElanCheck:
    def __init__(self, eaf_path):
        self.tier_refs = collections.defaultdict(list)
        self.reader = ElementTree.parse(eaf_path)
        self.xml_obj = self.reader.getroot()
        self.edges = set()
        self.num_words = {}
        self.word_number = 1
        self.lingv_type = {}



    def parse(self):
        for element in self.xml_obj:
            if element.tag == 'TIER':
                tier_id = element.attrib['TIER_ID']
                if 'PARENT_REF' in element.attrib:
                    tier_ref = element.attrib['PARENT_REF']
                    self.edges.add((self.get_word_number(tier_ref), self.get_word_number(tier_id), element.attrib["LINGUISTIC_TYPE_REF"], tier_id))
                    self.tier_refs[tier_ref].append(tier_id)
            elif element.tag == "LINGUISTIC_TYPE":
                at = element.attrib
                if "CONSTRAINTS" in at:
                    ling_type = at["CONSTRAINTS"]
                    id = at["LINGUISTIC_TYPE_ID"]
                    is_time_alignable = at["TIME_ALIGNABLE"]
                    self.lingv_type[id] = (ling_type, is_time_alignable)


    def get_word_number(self, word):
        if not word in self.num_words:
            number = self.word_number
            self.num_words[word] = number
            self.word_number += 1
        else:
            number = self.num_words[word]
        return number

    def check(self):
        # graph_structure = {(1, 2, ('Symbolic_Association', 'false'), 'literary translation'),
        #                     (1, 3, ('Included_In', 'true'), 'translation'),
        #                     (3, 5, ('Symbolic_Association', 'false'), 'word'),
        #                     (3, 4, ('Symbolic_Association', 'false'), 'transcription')
        # }
        # new_graph = set([(x[0], x[1], self.lingv_type[x[2]], x[3]) for x in self.edges])

        graph_structure = {(('Symbolic_Association', 'false'), 'literary translation'),
                            (('Included_In', 'true'), 'translation'),
                            (('Symbolic_Association', 'false'), 'word'),
                            (('Symbolic_Association', 'false'), 'transcription')
        }
        new_graph = set([( self.lingv_type[x[2]], x[3]) for x in self.edges])
        if new_graph != graph_structure:
            return False
        return True

# def main():
#     elan_check = ElanCheck("/home/igor/objects/bible.eaf")
#     elan_check.parse()
#     check = elan_check.check()
#     print(check)
#
#
#     converter = Elan("/home/igor/objects/bible.eaf")
#     #converter = Elan("/home/igor/ELAN_4.9.4/katushka3.eaf")
#     main_tier = converter.parse()
#     print("!!!!!!")
#     # print(main_tier)
#     # print(converter.tiers[0])
#     print("!!!!!!")
#     final_dicts = converter.proc()
#
#     for x in final_dicts:
#         print("=========")
#         for y in x:
#             if type(y) == list:
#                 for j in y:
#                     print(j._print())
#                 #print(y)
#             else:
#                 for j in y:
#                     print(j._print())
#                     for k in y[j]:
#                         print(k._print())
#                     #print(j._print(), y[j][0]._print(), y[j][1]._print())
#                 #print(j._print() , y[j][0]._print() )
#
#
#
#
#
# if __name__ == "__main__":
#     main()
#
