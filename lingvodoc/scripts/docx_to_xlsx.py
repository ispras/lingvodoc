import docx
import sys
import os
import pyramid.paster as paster
import logging
import getopt


# Setting up logging, if we are not being run as a script.
if __name__ != '__main__':
    log = logging.getLogger(__name__)
    log.debug('module init')


def get_text(filename):
    doc = docx.Document(filename)
    full_text = ''
    left_words = ''
    right_words = ''

    for p, para in enumerate(doc.paragraphs):
        bold_words = ''

        for word in para.runs:
            if not (word.bold or word.font.cs_bold):
                break
            bold_words += word.text

        if bold_words:
            print(f'Left: {left_words}')
            print(f'Right: {right_words}')
            print('---')
            print(f'Bold: {bold_words}')
            is_left = True
            full_text = ''
            left_words = ''
            right_words = ''
        else:
            is_left = False

        full_text += para.text

        for w, word in enumerate(para.runs):
            if is_left and ('\u2013 ' not in word.text):
                left_words += word.text
            elif not is_left:
                if w == 0:
                    right_words += f'\n{word.text.lstrip()}'
                else:
                    right_words += word.text
            else:
                is_left = False
                dash_pos = word.text.index('\u2013 ')
                left_words += word.text[:dash_pos].rstrip()
                right_words += word.text[dash_pos+1:].lstrip()

        if p > 500:
            break

    return '\n'.join(full_text)
    #return '\n'.join(full_text[324:350])


def main_import(args):

    # Parsing command-line options.
    opt_list, arg_list = (
        getopt.gnu_getopt(args, '', [
            'docx-file=',
            'debug',
            'no-header',
            'separate-by-paragraphs']))

    opt_dict = dict(opt_list)
    if not (docx_path := opt_dict.get('--docx-file')):
        docx_path = arg_list[0]

    if os.path.isfile(docx_path):
        text_file = get_text(docx_path)
    else:
        log.error(
            f'\nSpecified path {docx_path} is not correct.')


if __name__ == "__main__":
    if (len(sys.argv) > 1 and
            sys.argv[1] == '-config'):

        # We have a configuration file; initializing logging.
        config_path = sys.argv[2]

        paster.setup_logging(config_path)
        log = logging.getLogger(__name__)

        arg_list = sys.argv[3:]
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
            '\nPlease specify arguments.')
    else:
        main_import(arg_list)
