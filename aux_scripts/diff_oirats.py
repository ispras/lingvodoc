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


def transpos(word1, word2):
    edge = 0.25  # Jaro-Winkler edge
    same = jw(word1.lower(), word2.lower()) < edge

    return same


def neighbor(i1, i2, delta):
    skip = 4  # no more words between
    near = abs(i1 - i2) < (skip + delta + 2)

    return near


text_vars = list()
text_dist = list()

text_base = "Я помню чудное мгновенье, передо мной явилась ты"
text_vars.append("Я   чудное   мгновенье пока ещё помню... передо мной явилась ты!")
text_vars.append("Припоминаю я чудесное мгновение, впереди меня ты появилась.")
text_vars.append("Чудо помню мгновенное, ты появилась предо мною.")
text_vars.append("Как гений чистой красоты, явилась ты передо мной, помню я")

word_bases = split_words(text_base)

for n, text in enumerate(text_vars, 1):
    word_vars = split_words(text)
    mtrx_shape = (len(word_bases), len(word_vars))
    word_match = np.zeros(mtrx_shape, dtype=int)
    # text_dist.append(word_match)
    max_shape = max(mtrx_shape)
    twin_psns = [max_shape * 2] * len(word_bases)

    for i1, word1 in enumerate(word_bases):
        for i2, word2 in enumerate(word_vars):
            word_match[i1, i2] = int(transpos(word1, word2))

    # Positions of words which have no twin
    orphans = (
        [i for i, row in enumerate(word_match) if not sum(row)] +
        [j for j, col in enumerate(np.transpose(word_match)) if not sum(col)]
    )

    print(delimiter)

    for i1, word1 in enumerate(word_bases):
        for i2, word2 in enumerate(word_vars):

            # Number of orphans between i1 and i2
            delta = sum([(i1 < i < i2 or i2 < i < i1) for i in orphans])

            if word_match[i1, i2] and neighbor(i1, i2, delta):
                if abs(i1 - i2) < abs(i1 - twin_psns[i1]):
                    twin_psns[i1] = i2
                else:
                    break

        # If we found a twin
        if twin_psns[i1] < max_shape:
            print(f"{i1 + 1:>2}: {word1:<12} (>) {twin_psns[i1] + 1:>2}: {word_vars[twin_psns[i1]]}")
        else:
            print(f"{i1 + 1:>2}: {word1:<12} (-)")

    for i2, word2 in enumerate(word_vars):
        # A new word, or it is too far from its twin
        if i2 not in twin_psns:
            print(f"{'(+)':>20} {i2 + 1:>2}: {word2}")

    '''
    print(delimiter)
    print(word_match)
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
