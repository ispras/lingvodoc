import collections
import re
from string import punctuation as puncts
import numpy as np
from difflib import Differ
from rapidfuzz.distance.JaroWinkler import distance as jw
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


def twins(word1, word2):
    edge = 0.25  # Jaro-Winkler edge
    same = jw(word1.lower(), word2.lower()) < edge

    return same


def neighbor(i1, i2, max_shape):
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


def str2key(string):
    return string.split(',')


def get_diff(text_base=debug_base, text_vars=tuple(debug_vars), debug_flag=False):

    main_id, text = text_base
    main_id = key2str(*main_id)
    word_bases = split_words(text)

    # Output structures, initializing main sentence
    list_sentence = {}
    main_sentence = collections.defaultdict(dict)
    list_sentence[main_id] = main_sentence

    if debug_flag:
        print(line)

    for (twin_id, text) in text_vars:
        twin_id = key2str(*twin_id)
        word_vars = split_words(text)
        mtrx_shape = (len(word_bases), len(word_vars))
        word_match = np.zeros(mtrx_shape, dtype=int)
        max_shape = max(mtrx_shape)

        # Getting initial matrix of similarities
        for i1, (_, word1) in enumerate(word_bases):
            for i2, (_, word2) in enumerate(word_vars):
                word_match[i1, i2] = int(twins(word1, word2))

        # Positions of words which have no similarities by rows and by columns
        holes1 = set([i for i, row in enumerate(word_match) if not sum(row)])
        holes2 = set([j for j, col in enumerate(np.transpose(word_match)) if not sum(col)])

        # Initializing twin sentence
        twin_sentence = {}
        list_sentence[twin_id] = twin_sentence

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

                cur_dist = neighbor(i1 + delta1, i2 + delta2, max_shape)

                # If we are neighbours now or will be in future and
                # current distance is less than a found one
                if cur_dist is not None and cur_dist < twin_dist:
                    if word_match[i1, i2]:
                        twin_dist = cur_dist
                        twin_numb = i2
                        twin_posn = p2
                        twin_word = word2
                elif cur_dist != max_shape:  # None or a bigger distance value
                    break

            main_key = key2str(p1, len(word1 or ""))
            twin_key = key2str(twin_posn, len(twin_word or ""))

            # If we have twins
            if twin_dist < max_shape:
                twin_diff = diff_words(word1, twin_word)

                main_sentence[main_key][twin_id] = (twin_posn, twin_word, twin_dist, twin_diff)
                twin_sentence[twin_key] = (p1, word1, twin_dist, twin_diff)

                # If this is a real replacement
                if twin_dist > 0:
                    holes1.add(i1)
                    holes2.add(twin_numb)

                if debug_flag:
                    dist = '>' if twin_dist else '='
                    diff_ = f'(+/-) {twin_diff}' if twin_diff else ''
                    print(f"{i1:>2}: {word1:<12} ({dist}) {twin_numb:>2}: {twin_word:<12} {diff_}")
            else:
                main_sentence[main_key][twin_id] = None

                if debug_flag:
                    print(f"{i1:>2}: {word1:<12} (-)  {dash}")

        # A new word, or it is too far from its twin
        for i, (p, word) in enumerate(word_vars):
            if twin_key := key2str(p, len(word or "")) not in twin_sentence:
                twin_sentence[twin_key] = None

                if debug_flag:
                    print(f" {dash:<15} (+) {i:>2}: {word:<12}")

        if debug_flag:
            print(line)
            print(f'\n{sorted(holes1)=} {sorted(holes2)=}\n')
            print(list_sentence)

    return list_sentence


if __name__ == "__main__":
    get_diff(debug_flag=True)
