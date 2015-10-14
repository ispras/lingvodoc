import re
import difflib
from nltk.metrics import edit_distance


braces = re.compile(r"\([^()]*\)")
punct = re.compile(r"[\.,;]")
def getWordParts(w):
    while True:
        (w, n) = braces.subn("", w)
        if n == 0: break
    return list(set(map(lambda x: x.strip(), punct.split(w))))


def flattenDict(d):
    return [(ent, trans, origent[2]) for origent in d for ent in getWordParts(origent[0]) for trans in getWordParts(origent[1])]


def additional_checks(w1, w2, levenstein = 1):
    r = edit_distance(w1, w2)
    return r <= levenstein


def mergeDicts(x, y, threshold = 0.0, levenstein = 1):
    xs = iter(sorted(flattenDict(x), key = lambda x: (x[0], x[2])))
    ys = iter(sorted(flattenDict(y), key = lambda x: (x[0], x[2])))
    def nxt(it):
        try:
            return next(it)
        except:
            return None

    xcnt = dict()
    ycnt = dict()

    def nxtx():
        x = nxt(xs)
        if x is not None:
            xcnt[x[2]] = xcnt.get(x[2], 0) + 1
        return x

    def nxty():
        y = nxt(ys)
        if y is not None:
            ycnt[y[2]] = ycnt.get(y[2], 0) + 1
        return y

    x = nxtx()
    y = nxty()
    while x[0] == "": x = nxtx()
    while y[0] == "": y = nxty()

    matchcnts = dict()
    while x is not None and y is not None:
        if x[0] == y[0]:
            mx = list()
            x1 = x
            while x[0] == x1[0]:
                mx.append(x)
                x = nxtx()
                if x is None: break
            my = list()
            y1 = y
            while y[0] == y1[0]:
                my.append(y)
                y = nxty()
                if y is None: break
            prev_x = x1[2]
            prev_y = y1[2]
            my_dict = list(map(lambda x: {'tuple': x, 'marker': False}, my))
            for ax in mx:
                ax_marker = False
                if ax[2] != prev_x:
                    my_dict = list(map(lambda x: {'tuple': x, 'marker': False}, my))
                prev_x = ax[2]
                for ay in my_dict:
                    if ay['tuple'][2] != prev_y:
                        ax_marker = False
                    prev_y = ay['tuple'][2]
                    if ax[2] == ay['tuple'][2]: continue
                    if matchcnts.get((ay['tuple'][2], ax[2])) is not None: continue
                    if (additional_checks(ax[1], ay['tuple'][1], levenstein)):
                        m = (ax[2], ay['tuple'][2])
                        if not ax_marker:
                            matchcnts[m] = matchcnts.get(m, 0) + 1
                            ax_marker = True
                        if not ay['marker']:
                            matchcnts[m] = matchcnts.get(m, 0) + 1
                            ay['marker'] = True
        elif x[0] < y[0]:
            x = nxtx()
        elif x[0] > y[0]:
            y = nxty()
        else:
            assert False, "WTF"
    results = [(k[0], k[1], v / (xcnt[k[0]] + ycnt[k[1]])) for (k, v) in matchcnts.items()]
    return list(filter(lambda x: x[2] >= threshold, results))

