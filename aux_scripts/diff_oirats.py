import collections
import re
from string import punctuation as puncts
import numpy as np
from difflib import Differ
from rapidfuzz.distance.JaroWinkler import distance as jw
from pdb import set_trace as A

# For debugging
debug_flag = True
line = '=' * 55
dash = '-' * 5


def diff_words(word1, word2):
    if word1.lower() == word2.lower():
        return None

    result = []
    (sign_, _, char_) = '###'
    delta = diff(word1.lower(), word2.lower())

    for (sign, _, char) in delta:
        if sign_ == '-' and sign == '+':
            result.append(f'{char_} -> {char}')
        (sign_, char_) = (sign, char)

    return result or None


def split_words(text):
    parts = re.split(f'[{puncts}\\s]+', text)
    words = filter(lambda p: len(p), parts)

    return list(words)


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


if __name__ == "__main__":

    # Input texts
    text_vars = list()

    text_base = "Я помню чудное мгновенье, передо мной явилась ты"
    text_vars.append("Ещё мгновение чудное, впереди меня когда-то появилась ты, я помню")

    word_bases = split_words(text_base)

    # Output structures, initializing main sentence
    list_sentence = []
    main_sentence = collections.defaultdict(list)
    list_sentence.append(main_sentence)
    diff = Differ().compare

    if debug_flag:
        print(line)

    for n, text in enumerate(text_vars, 1):
        word_vars = split_words(text)
        mtrx_shape = (len(word_bases), len(word_vars))
        word_match = np.zeros(mtrx_shape, dtype=int)
        max_shape = max(mtrx_shape)

        # Getting initial matrix of similarities
        for i1, word1 in enumerate(word_bases):
            for i2, word2 in enumerate(word_vars):
                word_match[i1, i2] = int(twins(word1, word2))

        # Positions of words which have no similarities by rows and by columns
        holes1 = set([i for i, row in enumerate(word_match) if not sum(row)])
        holes2 = set([j for j, col in enumerate(np.transpose(word_match)) if not sum(col)])

        # Initializing twin sentence
        twin_sentence = {}
        list_sentence.append(twin_sentence)

        for i1, word1 in enumerate(word_bases):
            twin_posn = max_shape
            twin_dist = max_shape
            twin_word = None

            for i2, word2 in enumerate(word_vars):
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
                        twin_posn = i2
                        twin_word = word2
                elif cur_dist != max_shape:  # None or a bigger distance value
                    break

            # If we have twins
            if twin_dist < max_shape:
                twin_diff = diff_words(word1, twin_word)
                main_sentence[(i1, word1)].append((twin_posn, twin_word, twin_dist, twin_diff))
                twin_sentence[(twin_posn, twin_word)] = (i1, word1, twin_dist, twin_diff)

                if debug_flag:
                    dist = '>' if twin_dist else '='
                    diff_ = f'(+/-) {twin_diff}' if twin_diff else ''

                    print(f"{i1:>2}: {word1:<12} ({dist}) {twin_posn:>2}: {twin_word:<12} {diff_}")

                # If this is a real replacement
                if twin_dist > 0:
                    holes1.add(i1)
                    holes2.add(twin_posn)
            else:
                main_sentence[(i1, word1)].append(None)

                if debug_flag:
                    print(f"{i1:>2}: {word1:<12} (-)  {dash}")

        # A new word, or it is too far from its twin
        loners = [loner for loner in enumerate(word_vars) if loner not in twin_sentence]
        for (i, word) in loners:
            twin_sentence[(i, word)] = None

            if debug_flag:
                print(f" {dash:<15} (+) {i:>2}: {word:<12}")

        if debug_flag:
            print(f'\n{sorted(holes1)=} {sorted(holes2)=}\n')
            print(line)
