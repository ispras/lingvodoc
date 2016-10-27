import os
import tgt


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
            print('first exception')
            print(e)
            textgrid = tgt.io.read_textgrid(textGrid_file, encoding='utf-16')
            elan = tgt.io.export_to_elan(textgrid)
        except Exception as e:
            print('second exception')
            print(e)
            return 'error'
    return elan


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


def elan_to_elan(filename, user_config=None, converter_config=None):
    content = _export_to_elan(filename)
    return content


rules = [ConvertRule('Praat','Elan', ['TextGrid'], ['eaf'], praat_to_elan),
         ConvertRule('Elan','Elan', ['eaf'], ['eaf'], elan_to_elan)]