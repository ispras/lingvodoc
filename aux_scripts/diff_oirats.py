import re
from string import punctuation as puncts
import numpy as np
from rapidfuzz.distance.JaroWinkler import distance as jw
from pdb import set_trace as A

'''
cases = []

sentence = {
    'numbs': [],
    'words': [],
    'links': []
}

links = {
    'numbs': [],
    'words': [],
    'diffs': []
}

def compile_diffs(main_numb, main_word, numbs, words, diffs):
    if

'''

def split_words(text):
    parts = re.split(f'[{puncts}\\s]+', text)
    words = filter(lambda p: len(p), parts)

    return list(words)


def reversion(word1, word2):
    edge = 0.25  # Jaro-Winkler edge
    same = jw(word1.lower(), word2.lower()) < edge

    return same


def neighbor(i1, i2, max_shape, delta=0):
    skip = 4  # no more words between
    dist = abs(i1 - i2) - 1 - delta
    # Returns extra-big distance if we are not neighbours yet,
    # a real distance if we are neighbours now and
    # None if we are not neighbours already
    return (
        dist if dist <= skip else
        max_shape if i2 < i1 else
        None)


def print_result(twin_psns):
    for twin1, twin2 in twin_psns.items():
        if twin1 is not None:
            (i1, word1) = twin1
            # If we found twins
            if twin2 is not None:
                (i2, word2) = twin2
                print(f"{i1:>2}: {word1:<12} (>) {i2:>2}: {word2}")
            else:
                print(f"{i1:>2}: {word1:<12} (-)")
        else:
            # A new word, or it is too far from its twin
            for (i2, word2) in twin2:
                print(f"{'(+)':>20} {i2:>2}: {word2}")


text_vars = list()
text_dist = list()

text_base = "Я помню чудное мгновенье, передо мной явилась ты"
text_vars.append("Я   чудное   мгновенье пока ещё помню... передо мной явилась ты!")
text_vars.append("Припоминаю я чудесное мгновение, впереди меня ты появилась.")
text_vars.append("Чудо помню мгновенное, ты появилась предо мною, потом забыл я.")
text_vars.append("Как гений чистой красоты, явилась ты, помню я, передо мной")

word_bases = split_words(text_base)

delimiter = '=' * 40
print(delimiter)

for n, text in enumerate(text_vars, 1):
    word_vars = split_words(text)
    mtrx_shape = (len(word_bases), len(word_vars))
    word_match = np.zeros(mtrx_shape, dtype=int)
    # text_dist.append(word_match)
    max_shape = max(mtrx_shape)

    # Getting initial matrix of similarities
    for i1, word1 in enumerate(word_bases):
        for i2, word2 in enumerate(word_vars):
            word_match[i1, i2] = int(reversion(word1, word2))

    # Positions of words which have no similarities by rows and by columns
    orphans1 = set([i for i, row in enumerate(word_match) if not sum(row)])
    orphans2 = set([j for j, col in enumerate(np.transpose(word_match)) if not sum(col)])
    twin_dict = {}

    for step in "getting_orphans", "getting_twins":

        # Updating orphans sets if some similarities actually are not neighbours
        if step == "getting_twins":
            orphans1.update([i for (i, _), twin in twin_dict.items() if twin is None])
            # Reinitializing twin_dict with found loners
            twin_dict = {
                None: [loner for loner in enumerate(word_vars) if loner not in twin_dict.values()]
            }
            orphans2.update([j for (j, _) in twin_dict[None]])

        for i1, word1 in enumerate(word_bases):
            twin_dist = max_shape
            twin_dict[(i1, word1)] = None

            for i2, word2 in enumerate(word_vars):
                # Number of orphans between i1 and i2
                delta = sum([(i1 < i < i2 or i2 < i < i1) for i in list(orphans1) + list(orphans2)])
                cur_dist = neighbor(i1, i2, max_shape, delta)

                # If we are neighbours now or will be in future and
                # current distance is less than a found one
                if cur_dist is not None and cur_dist < twin_dist:
                    if word_match[i1, i2]:
                        twin_dist = cur_dist
                        twin_dict[(i1, word1)] = (i2, word2)
                elif cur_dist != max_shape:
                    break

    print_result(twin_dict)
    print(f'\n{sorted(orphans1)=} {sorted(orphans2)=}\n')
    #print(word_match)
    print(delimiter)
