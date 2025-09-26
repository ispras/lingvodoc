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


def transposition(case1, case2):
    i1, word1 = case1
    i2, word2 = case2

    edge = 0.25  # Jaro-Winkler edge
    skip = 4  # no more words between
    same = jw(word1.lower(), word2.lower()) < edge
    near = abs(i1 - i2) < (skip + 2)

    return same and near


# Create an instance of HtmlDiff
# differ = HtmlDiff()
text_vars = list()
text_dist = list()

text_base = "Я   чудное   мгновенье пока ещё помню... передо мной явилась ты!"
text_vars.append("Припоминаю я чудесное мгновение, впереди меня ты появилась.")

delimiter = '=' * 40
print(delimiter)

word_bases = split_words(text_base)

for n, text in enumerate(text_vars, 1):
    word_vars = split_words(text)
    word_match = np.zeros((len(word_bases), len(word_vars)), dtype=int)
    text_dist.append(word_match)

    for i1, word1 in enumerate(word_bases):
        for i2, word2 in enumerate(word_vars):
            if transposition((i1, word1), (i2, word2)):
                word_match[i1, i2] = 1
                print(f"{i1 + 1:>2}: {word1:<12} (>) {i2 + 1:>2}: {word2}")

        if not sum(word_match[i1]):
            print(f"{i1 + 1:>2}: {word1:<12} (-)")

    col_sums = np.sum(word_match, axis=0)
    for i2, word2 in enumerate(word_vars):
        if not col_sums[i2]:
            print(f"{'(+)':>20} {i2 + 1:>2}: {word2}")

    print(delimiter)
    print(word_match)
    print(delimiter)

'''
html_output = differ.make_file(list1, list2, "Benchmark", "Version")

with open('diff.html', 'w') as html_file:
    html_file.write(html_output)

print("file://" + os.path.abspath('diff.html'))
#webbrowser.open("file://" + html_file_path)
'''