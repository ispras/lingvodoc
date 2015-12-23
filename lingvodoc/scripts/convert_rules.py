import os
import tgt
import pympi
from pympi import Eaf
from re import split, search


class ConvertRule:
    def __init__(self, in_type, out_type, in_extensions, out_extensions, convert_method, converter_config=None, max_out_size = 1, max_in_size = 1):
        self.in_type = in_type
        self.out_type = out_type
        self.max_out_size = max_out_size  # in MB
        self.max_in_size = max_in_size  # in MB
        self.in_extensions = in_extensions
        self.out_extensions = out_extensions
        self.converter_config = converter_config
        self.convert = convert_method


def _export_to_elan(textGrid_file):
    if os.stat(textGrid_file).st_size == 0:
        return 'error'
    try:
        textgrid = tgt.io.read_textgrid(textGrid_file, encoding='utf-8')
        elan = tgt.io.export_to_elan(textgrid)
    except Exception as e:
        try:
            print(e)
            textgrid = tgt.io.read_textgrid(textGrid_file, encoding='utf-16')
            elan = tgt.io.export_to_elan(textgrid)
        except Exception as e:
            print(e)
            return 'error'
    return elan


def _weird_float_to_int(number):
    from math import modf
    a = modf(number)
    a0 = a[0]
    a1 = a[1]
    b = (a1 * 60 + a0 * 100) * 1000
    return int(b)


def _txt_to_elan(txt_file):
    # textgrid = tgt.TextGrid()
    import time
    import random
    import string
    elan = Eaf()
    new_lines = list()
    print('I\'m here!', txt_file)
    with open(txt_file, 'r') as f:
        for line in f:
            new_lines += split('([0-9]+\.[0-9]+)', line)
    # print(new_lines)
    my_format = dict()
    key = -0.1
    building_line = ''
    counter = 0
    # for line in new_lines:
    #     new_key = search('([0-9]+\.[0-9]+)', line)
    #     if new_key:
    #         new_key = line
    #         # my_format[key] = building_line
    #         if key != - 0.1:
    #
    #             new_key = float(new_key)
    #             if new_key == key:
    #                 new_key += 0.005
    #             # textgrid.add_tier().add_annotation()
    #             tmp_key_1 = _weird_float_to_int(key)
    #             tmp_key_2 = _weird_float_to_int(new_key)
    #             elan.add_tier('ts%s' % counter)
    #             elan.add_annotation('ts%s' % counter, tmp_key_1, tmp_key_2, building_line)
    #             key = new_key
    #             counter += 1
    #             building_line = ''
    #         else:
    #             key = float(new_key)
    #
    #     else:
    #         building_line += line
    counter = 3
    elan.add_linguistic_type('original')
    elan.add_linguistic_type('translation')
    elan.add_tier('original', ling='original')
    elan.add_tier('translation', ling='translaiton')
    key = float(new_lines[counter])
    counter += 1
    orig = new_lines[counter]
    counter += 1
    tran = new_lines[counter]
    counter += 2
    le =  len(new_lines)
    print( le)
    while counter + 3 < le:
        new_key = new_lines[counter]
        new_key = float(new_key)
        if new_key == key:
            new_key += 0.005
        tmp_key_1 = _weird_float_to_int(float(key))
        tmp_key_2 = _weird_float_to_int(float(new_key))
        if tmp_key_2 - 1 <= tmp_key_1:
            print(tmp_key_2, tmp_key_1)

        elan.add_annotation('original', tmp_key_1, tmp_key_2, orig)

        elan.add_ref_annotation('translation', 'original', int(tmp_key_2 - 1),  tran)
        key = new_key
        counter += 1
        orig = new_lines[counter]
        counter += 1
        tran = new_lines[counter]
        counter += 1
        while (new_lines[counter] == '' or new_lines[counter] == '\n') and counter < le:
            counter += 1
            # print(counter)

    new_key = new_lines[counter]
    new_key = float(new_key)
    if new_key == key:
        new_key += 0.005

    tmp_key_1 = _weird_float_to_int(float(key))
    tmp_key_2 = _weird_float_to_int(float(new_key))
    if tmp_key_2 - 1 <= tmp_key_1:
        print(tmp_key_2, tmp_key_1)
    elan.add_annotation('original', tmp_key_1, tmp_key_2, orig)

    elan.add_ref_annotation('translation', 'original', int(tmp_key_2 - 1),  tran)
    key = new_key
    counter += 1
    orig = new_lines[counter]
    counter += 1
    tran = new_lines[counter]

    tmp_key_1 = _weird_float_to_int(float(key))
    tmp_key_2 = _weird_float_to_int(float(21.00))
    if tmp_key_2 - 1 <= tmp_key_1:
        print(tmp_key_2, tmp_key_1)
    elan.add_annotation('original', tmp_key_1, tmp_key_2, orig)

    elan.add_ref_annotation('translation', 'original', int(tmp_key_2 - 1),  tran)


    # elan = tgt.io.export_to_elan(textgrid)
    filename = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
                                              for c in range(10))
    elan.remove_tier('default')
    elan.to_file(filename)
    f = open('text.eaf', 'r')
    a = f.read()
    f.close()
    # filename = time.ctime() + ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits)
    #                                           for c in range(10))
    # txtgrd.to_file(filename)
    # elan = _export_to_elan(filename)
    os.remove(filename)
    # print(elan.tiers)
    return a


def _import_from_elan(elan_file):
    if os.stat(elan_file).st_size == 0:
        return 'error'
    try:
        textgrid = tgt.io.read_eaf(elan_file)
        content = tgt.io.export_to_long_textgrid(textgrid)
    except Exception as e:
            print(e)
            return 'error'
    return content


# def _is_empty(tier):
#     """ Checks whether all intervals are marked as ""
#     """
#     for int in tier:
#         if int.text != "":
#             return False
#     return True


def praat_to_elan(filename, user_config=None, converter_config=None):
    content = _export_to_elan(filename)
    return content


def txt_to_elan(filename, user_config=None, converter_config=None):
    content = _txt_to_elan(filename)
    return content


rules = [ConvertRule('Praat','Elan', ['.TextGrid'], ['eaf'], praat_to_elan), ConvertRule('txt','Elan', ['.txt'], ['eaf'], txt_to_elan)]