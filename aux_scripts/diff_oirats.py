import re
from string import punctuation as puncts
import numpy as np
from rapidfuzz.distance.JaroWinkler import distance as jw
from pdb import set_trace as A
delimiter = '=' * 40


def split_words(text):
    parts = re.split(f'[{puncts}\s]+', text)
    words = filter(lambda p: len(p), parts)

    return list(words)


def reversion(word1, word2):
    edge = 0.25  # Jaro-Winkler edge
    same = jw(word1.lower(), word2.lower()) < edge

    return same


def neighbor(i1, i2, max_shape, delta=0):
    skip = 4  # no more words between
    dist = abs(i1 - i2) - delta
    # Returns extra-big distance if we are not neighbours yet,
    # a real distance if we are neighbours now and
    # None if we are not neighbours already
    return (
        dist if dist < skip + 2 else
        max_shape if i2 < i1 else
        None)


text_vars = list()
text_dist = list()

text_base = "Я помню чудное мгновенье, передо мной явилась ты"
text_vars.append("Я   чудное   мгновенье пока ещё помню... передо мной явилась ты!")
text_vars.append("Припоминаю я чудесное мгновение, впереди меня ты появилась.")
text_vars.append("Чудо помню мгновенное, ты появилась предо мною, потом забыл я.")
text_vars.append("Как гений чистой красоты, явилась ты передо мной, помню я")

word_bases = split_words(text_base)

for n, text in enumerate(text_vars, 1):
    word_vars = split_words(text)
    mtrx_shape = (len(word_bases), len(word_vars))
    word_match = np.zeros(mtrx_shape, dtype=int)
    # text_dist.append(word_match)
    max_shape = max(mtrx_shape)
    twin_psns = [None] * len(word_bases)

    for i1, word1 in enumerate(word_bases):
        for i2, word2 in enumerate(word_vars):
            word_match[i1, i2] = int(reversion(word1, word2))

    # Positions of words which have no twin
    orphans = (
        [i for i, row in enumerate(word_match) if not sum(row)] +
        [j for j, col in enumerate(np.transpose(word_match)) if not sum(col)]
    )

    print(delimiter)

    for i1, word1 in enumerate(word_bases):
        twin_dist = max_shape

        for i2, word2 in enumerate(word_vars):
            # Number of orphans between i1 and i2
            delta = sum([(i1 < i < i2 or i2 < i < i1) for i in orphans])
            cur_dist = neighbor(i1, i2, max_shape, delta)

            if cur_dist is not None and cur_dist < twin_dist:
                if word_match[i1, i2]:
                    twin_dist = cur_dist
                    twin_psns[i1] = i2
            elif cur_dist != max_shape:
                break

        # If we found a twin
        if twin_psns[i1] is not None:
            print(f"{i1 + 1:>2}: {word1:<12} (>) {twin_psns[i1] + 1:>2}: {word_vars[twin_psns[i1]]}")
        else:
            print(f"{i1 + 1:>2}: {word1:<12} (-)")
            if i1 not in orphans:
                orphans.append(i1)

    for i2, word2 in enumerate(word_vars):
        # A new word, or it is too far from its twin
        if i2 not in twin_psns:
            print(f"{'(+)':>20} {i2 + 1:>2}: {word2}")
            if i2 not in orphans:
                orphans.append(i2)

'''
    print(delimiter)
    print(word_match)
    print(f'{orphans=}')
'''

print(delimiter)

'''
from difflib import HtmlDiff
import os
differ = HtmlDiff()
html_output = differ.make_file(list1, list2, "Benchmark", "Version")

with open('diff.html', 'w') as html_file:
    html_file.write(html_output)

print("file://" + os.path.abspath('diff.html'))
#webbrowser.open("file://" + html_file_path)
'''
