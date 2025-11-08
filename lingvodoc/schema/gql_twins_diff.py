import collections
import re
import numpy as np
from difflib import Differ
from rapidfuzz.distance.JaroWinkler import distance as jw
from lingvodoc.schema.gql_parserresult import ValencyVerbCases as ReusedMethods
import xlsxwriter
import io
import logging
import lingvodoc.utils as utils

# Setting up logging.
log = logging.getLogger(__name__)

# Reusing the static method
save_xlsx_file = ReusedMethods.save_xlsx_file

from pdb import set_trace as A

# For debugging
line = '=' * 55
dash = '-' * 5

# Input texts
debug_vars = list()
debug_base = ((1,), "Я помню чудное мгновенье, передо мной явилась ты")
debug_vars.append(((2,), "Ещё нгновение чюдecное, впереди меня когда-то появилясь ты, я понмю"))


def diff_words(word1, word2):

    result = []
    from_chars = to_chars = ''

    def flush_result():
        nonlocal from_chars, to_chars
        if from_chars or to_chars:
            result.append((from_chars, to_chars))
            from_chars = to_chars = ''

    if word1.lower() == word2.lower():
        return None

    diff = Differ().compare
    delta = diff(word1.lower(), word2.lower())

    for (sign, _, char) in delta:
        if sign == '-':
            from_chars += char
        elif sign == '+':
            to_chars += char
        else:
            flush_result()

    flush_result()
    return result or None


def split_words(text):
    words = []
    for match in re.finditer(r'\w+', text):
        words.append((match.start(), match.group(0)))
    return words


def is_twin(word1, word2):
    edge = 0.25  # Jaro-Winkler edge
    same = jw(word1.lower(), word2.lower()) < edge
    return same


def get_dist(i1, i2, max_shape):
    skip = 4  # no more than four words between
    dist = abs(i1 - i2)

    # Returns extra-big distance if we are not neighbours yet,
    # a real distance if we are neighbours now and
    # None if we are not neighbours already
    return (
        dist if dist <= skip + 1 else
        max_shape if i2 < i1 else
        None)


def key2str(*key):
    return ','.join([str(k) for k in key])


def diff_sentences(
        text_base=debug_base,
        text_vars=tuple(debug_vars),
        twin_diffs=None,
        debug_flag=False):

    main_id, text = text_base
    main_id = key2str(*main_id)
    word_bases = split_words(text)

    # Output structures, initializing main sentence
    list_sentence = {}
    xlsx_table = {}

    def set_xlsx_cell(row, column, value):
        xlsx_row = xlsx_table.setdefault(
            row,
            [None] * (len(text_vars) + 1)
        )
        xlsx_row[column] = f'{value:<25}'

    main_sentence = collections.defaultdict(dict)

    if debug_flag:
        print(line)

    for t, (twin_id, text) in enumerate(text_vars):
        twin_id = key2str(*twin_id)
        word_vars = split_words(text)
        mains_num = len(word_bases)
        twins_num = len(word_vars)
        mtrx_shape = (mains_num, twins_num)
        word_match = np.zeros(mtrx_shape, dtype=int)
        max_shape = max(mtrx_shape)

        # Getting initial matrix of similarities
        for i1, (_, word1) in enumerate(word_bases):
            for i2, (_, word2) in enumerate(word_vars):
                word_match[i1, i2] = int(is_twin(word1, word2))

        # Positions of words which have no similarities by rows and by columns
        holes1 = set([i for i, row in enumerate(word_match) if not sum(row)])
        holes2 = set([j for j, col in enumerate(np.transpose(word_match)) if not sum(col)])

        # Initializing twin sentence
        twin_sentence = collections.defaultdict(dict)
        twin_equals = []

        for i1, (p1, word1) in enumerate(word_bases):
            twin_posn = -1
            twin_numb = max_shape
            twin_dist = max_shape
            twin_word = None

            for i2, (p2, word2) in enumerate(word_vars):
                # Number of holes before i2(!)
                delta1 = sum([(i < i2) for i in list(holes2)])
                # Number of holes before i1(!)
                delta2 = sum([(j < i1) for j in list(holes1)])

                cur_dist = get_dist(i1 + delta1, i2 + delta2, max_shape)

                # If we are neighbours now or will be in future and
                # current distance is less than a found one
                if cur_dist is not None and cur_dist < twin_dist:
                    if word_match[i1, i2]:
                        twin_dist = cur_dist
                        twin_numb = i2
                        twin_posn = p2
                        twin_word = word2
                # None or a bigger distance value
                elif cur_dist != max_shape:
                    break

            orig_numb, orig_posn, orig_word = i1, p1, word1
            main_key = key2str(orig_posn, len(orig_word))

            # If we have twins
            if twin_dist < max_shape:
                twin_key = key2str(twin_posn, len(twin_word))
                twin_diff = diff_words(orig_word, twin_word)

                if twin_dist or twin_diff:
                    main_sentence[main_key][twin_id] = (
                        twin_posn,
                        twin_word,
                        twin_dist,
                        twin_diff,
                        orig_word
                    )
                    twin_sentence[twin_key][main_id] = (
                        orig_posn,
                        orig_word,
                        twin_dist,
                        twin_diff,
                        twin_word
                    )

                    xlsx_value = twin_word
                    if twin_dist:
                        xlsx_value += f" <shifted by {twin_dist}>"
                    if twin_diff:
                        xlsx_value += f" <changed by {twin_diff}>"
                    # mark that xlsx row describes changes
                    set_xlsx_cell(orig_numb, 0, orig_word)
                    set_xlsx_cell(orig_numb, t+1, xlsx_value)

                else:
                    twin_equals.append(twin_key)
                    # store twin_word into xlsx row,
                    # but it may describe no changes,
                    # so we don't set xlsx_column'0 here
                    set_xlsx_cell(orig_numb, t+1, "<same>")

                # Collect diffs
                if twin_diffs is not None and twin_diff is not None:
                    for diff in twin_diff:
                        twin_diffs[diff].add((orig_word, twin_word))

                # If this is a real replacement
                if twin_dist > 0:
                    holes1.add(orig_numb)
                    holes2.add(twin_numb)

                if debug_flag:
                    dist = '>' if twin_dist else '='
                    diff_ = f'(+/-) {twin_diff}' if twin_diff else ''
                    print(f"{orig_numb:>2}: {orig_word:<12} ({dist}) {twin_numb:>2}: {twin_word:<12} {diff_}")
            else:
                main_sentence[main_key][twin_id] = None
                # mark that xlsx row describes changes
                set_xlsx_cell(orig_numb, 0, orig_word)
                set_xlsx_cell(orig_numb, t+1, "<none>")

                if debug_flag:
                    print(f"{orig_numb:>2}: {orig_word:<12} (-)  {dash}")

        # A new word, or it is too far from its twin
        for i2, (p2, word2) in enumerate(word_vars, mains_num):
            if (twin_key := key2str(p2, len(word2))) not in (list(twin_sentence) + twin_equals):
                twin_sentence[twin_key][main_id] = None
                # mark that xlsx row describes changes
                set_xlsx_cell(i2, 0, "<none>")
                set_xlsx_cell(i2, t+1, word2)

                if debug_flag:
                    print(f" {dash:<15} (+) {(i2 - mains_num):>2}: {word2:<12}")

        if debug_flag:
            print(f'\n{sorted(holes1)=} {sorted(holes2)=}\n')

        # If we found any change in twin sentence
        if len(twin_sentence):
            list_sentence[twin_id] = twin_sentence

    # If we found any change in main sentence
    if len(main_sentence):
        list_sentence[main_id] = main_sentence

    if debug_flag:
        print(line)
        print(list_sentence)

    return list_sentence, xlsx_table


def write_xlsx(info, table, xlsx_diffs, debug_flag=False):

    workbook_stream = (
        io.BytesIO())

    workbook = (
        xlsxwriter.Workbook(
            workbook_stream, {'in_memory': True}))

    base = {'text_wrap': True, 'align': 'vcenter'}

    align = workbook.add_format(base)

    header = workbook.add_format({**base,
                                  'bold': True,
                                  'fg_color': '#D7E4BC',
                                  'border': 1})

    toc = workbook.add_format({**base,
                               'font_color': 'green'})

    def write_data(worksheet, content, with_toc=False):
        width = 30
        columns = content.pop(0)
        worksheet.set_column(0, 0, width // 3 if with_toc else width)
        worksheet.set_column(1, len(columns) - 1, width)
        worksheet.write_row(0, 0, columns, header)

        for row_count, cells in enumerate(content, start=1):
            height = (max(map(lambda c: len(c), cells)) // width + 1) * 17
            worksheet.set_row(row_count, height)
            for column_count, value in enumerate(cells):
                worksheet.write(row_count, column_count, value,
                                toc if with_toc and column_count == 0 else align)

            if debug_flag:
                log.debug(cells)

    config = [{
        'worksheet': workbook.add_worksheet(
            utils.sanitize_worksheet_name("By translation")),
        'content': table,
        'with_toc': False
    }, {
        'worksheet': workbook.add_worksheet(
            utils.sanitize_worksheet_name("By substance")),
        'content': xlsx_diffs,
        'with_toc': True
    }]

    for options in config:
        write_data(**options)

    workbook.close()

    xlsx_url = (
        save_xlsx_file(
            info,
            workbook_stream,
            debug_flag,
            title='twins_diff'))

    return xlsx_url


def DiffEntities(info, main_ids, twin_ids, entry_ids, field_names, debug_flag=False):
    from lingvodoc.models import DBSession, Entity as dbEntity

    twin_diffs = collections.defaultdict(set)

    def get_content(cid, oid):
        entity = DBSession.query(dbEntity).filter_by(client_id=cid, object_id=oid).first()
        return entity.content if entity else ""

    result = {}
    xlsx_table = [[f'{f:<25}' for f in field_names]]

    for main_id, twins, entry_id in zip(main_ids, twin_ids, entry_ids):
        if main_id is None:
            continue
        main_content = main_id, get_content(*main_id)

        twin_content = []
        for twin_id in twins:
            twin_content.append((twin_id, get_content(*twin_id)) if twin_id is not None else (twin_id, ""))

        diff, rows = diff_sentences(main_content, twin_content, twin_diffs)

        if diff:
            result[key2str(*(entry_id or (0, 0)))] = diff

        xlsx_table.extend(row for row in rows.values() if row[0] is not None)

    xlsx_diffs = [[f"{'Difference':<12}", f"{'Word1':<12}", f"{'Word2':<12}"]]

    for delta, word_set in twin_diffs.items():
        part1, part2 = delta
        delta = (
            f'{part1} -> {part2}' if len(part1) and len(part2) else
            f'+ {part2}' if not len(part1) else
            f'- {part1}'
        )

        xlsx_diffs.append([f"{delta:<12}"])
        for word1, word2 in word_set:
            xlsx_diffs.append([f"{'':<12}", f"{word1:<12}", f"{word2:<12}"])

    xlsx_url = write_xlsx(info, xlsx_table, xlsx_diffs)

    if debug_flag:
        for row in xlsx_table + [''] + xlsx_diffs:
            print(row)
        print(xlsx_url)

    return {
        'diffs': result,
        'xlsx_url': xlsx_url
    }


if __name__ == "__main__":
    diff_sentences(debug_flag=True)
