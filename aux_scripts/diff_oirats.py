from difflib import HtmlDiff
import webbrowser
import os, re
from string import punctuation as puncts
import numpy as np
from rapidfuzz.distance.JaroWinkler import distance as jw
from pdb import set_trace as A


def split_words(text):
    parts = re.split(f'[{puncts}\s]+', text)
    words = filter(lambda p: len(p), parts)

    return list(words)


def transposition(word1, word2):
    edge = 0.25  # Jaro-Winkler edge
    same = jw(word1.lower(), word2.lower()) < edge

    return same


def neighbor(i1, i2, delta):
    skip = 4  # no more words between
    near = abs(i1 - i2) < (skip + delta + 2)

    return near

# Create an instance of HtmlDiff
# differ = HtmlDiff()
text_vars = list()
text_dist = list()

text_base = "Я помню чудное мгновенье, передо мной явилась ты"
text_vars.append("Я   чудное   мгновенье пока ещё помню... передо мной явилась ты!")
text_vars.append("Припоминаю я чудесное мгновение, впереди меня ты появилась.")
text_vars.append("Чудо помню мгновенное, ты появилась предо мною.")
text_vars.append("Как гений чистой красоты, явилась ты передо мной, помню я")

delimiter = '=' * 40
print(delimiter)

word_bases = split_words(text_base)

for n, text in enumerate(text_vars, 1):
    word_vars = split_words(text)
    word_match = np.zeros((len(word_bases), len(word_vars)), dtype=int)
    text_dist.append(word_match)

    for i1, word1 in enumerate(word_bases):
        for i2, word2 in enumerate(word_vars):
            word_match[i1, i2] = int(transposition(word1, word2))

    max_shape = max(word_match.shape)
    # Which words have no pair (positions)
    orphans = [i for i, row in enumerate(word_match) if not sum(row)]

    for i1, word1 in enumerate(word_bases):
        pair_pos = max_shape
        for i2, word2 in enumerate(word_vars):
            # Number of orphans between i1 and i2
            delta = sum([(i1 < i < i2 or i2 < i < i1) for i in orphans])

            if (word_match[i1, i2] and
                neighbor(i1, i2, delta) and
                abs(i1 - i2) < abs(i1 - pair_pos)):

                pair_pos = i2

        # If we found any pair
        if pair_pos != max_shape:
            print(f"{i1 + 1:>2}: {word1:<12} (>) {pair_pos + 1:>2}: {word_vars[pair_pos]}")
            continue

        print(f"{i1 + 1:>2}: {word1:<12} (-)")

    col_sums = np.sum(word_match, axis=0)
    for i2, word2 in enumerate(word_vars):
        if not col_sums[i2]:
            print(f"{'(+)':>20} {i2 + 1:>2}: {word2}")

    '''
    print(delimiter)
    print(word_match)
    '''

    print(delimiter)

'''
html_output = differ.make_file(list1, list2, "Benchmark", "Version")

with open('diff.html', 'w') as html_file:
    html_file.write(html_output)

print("file://" + os.path.abspath('diff.html'))
#webbrowser.open("file://" + html_file_path)
'''