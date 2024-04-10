import bisect
import math
import numpy as np
from scipy.interpolate import CubicSpline

voiced_floor = 75
voiced_ceiling = 600

# OK
def get_jitter_local(me, tmin, tmax, pmin, pmax, maximumPeriodFactor):
    tmin, tmax = unidirectional_autowindow(me, tmin, tmax)
    first, last = bisect.bisect_right(me['t'], tmin), bisect.bisect_left(me['t'], tmax)
    numberOfPeriods = max(0, last - first)
    if numberOfPeriods < 2:
        return None
    dsum = 0.0
    for i in range(first + 1, last):
        p1 = me['t'][i] - me['t'][i - 1]
        p2 = me['t'][i + 1] - me['t'][i]
        intervalFactor = p1 / p2 if p1 > p2 else p2 / p1
        if pmin == pmax or (pmin <= p1 <= pmax and pmin <= p2 <= pmax and intervalFactor <= maximumPeriodFactor):
            dsum += abs(p1 - p2)
        else:
            numberOfPeriods -= 1
    if numberOfPeriods < 2:
        return None
    return (dsum / (numberOfPeriods - 1) /
            get_mean_period(me, tmin, tmax, pmin, pmax, maximumPeriodFactor))

# OK
def unidirectional_autowindow(me, tmin, tmax):
    if tmin >= tmax:
        tmin = me['xmin']
        tmax = me['xmax']
    return tmin, tmax

# OK
def get_mean_period(me, tmin, tmax, minimumPeriod, maximumPeriod, maximumPeriodFactor):
    tmin, tmax = unidirectional_autowindow(me, tmin, tmax)
    first, last = bisect.bisect_right(me['t'], tmin), bisect.bisect_left(me['t'], tmax)
    numberOfPeriods = 0
    dsum = 0.0
    for ipoint in range(first, last):
        if is_period(me, ipoint, minimumPeriod, maximumPeriod, maximumPeriodFactor):
            numberOfPeriods += 1
            dsum += me['t'][ipoint + 1] - me['t'][ipoint]
    return dsum / numberOfPeriods if numberOfPeriods > 0 else None

# OK
def is_period(me, ileft, minimumPeriod, maximumPeriod, maximumPeriodFactor):
    """
    This function answers the question: is the interval from point 'ileft' to point 'ileft+1' a period?
    """
    iright = ileft + 1

    # Period condition 1: both 'ileft' and 'iright' have to be within the point process.
    if ileft < 0 or iright >= me['nt']:
        return False

    # Period condition 2: the interval has to be within the boundaries, if specified.
    if minimumPeriod == maximumPeriod:  # special input setting (typically both zero)
        return True  # all intervals count as periods, irrespective of absolute size and relative size

    interval = me['t'][iright] - me['t'][ileft]
    if interval <= 0.0 or interval < minimumPeriod or interval > maximumPeriod:
        return False

    if maximumPeriodFactor is None or maximumPeriodFactor < 1.0:
        return True

    # Period condition 3: the interval cannot be too different from both of its neighbours, if any.
    if ileft <= 0:
        previousInterval = None
    else:
        previousInterval = me['t'][ileft] - me['t'][ileft - 1]

    if iright >= me['nt']:
        nextInterval = None
    else:
        nextInterval = me['t'][iright + 1] - me['t'][iright]

    if previousInterval is None or previousInterval <= 0.0:
        previousIntervalFactor = None
    else:
        previousIntervalFactor = interval / previousInterval

    if nextInterval is None or nextInterval <= 0.0:
        nextIntervalFactor = None
    else:
        nextIntervalFactor = interval / nextInterval

    if previousIntervalFactor is None and nextIntervalFactor is None:
        return True  # no neighbours: this is a period

    if previousIntervalFactor is not None and 0.0 < previousIntervalFactor < 1.0:
        previousIntervalFactor = 1.0 / previousIntervalFactor

    if nextIntervalFactor is not None and 0.0 < nextIntervalFactor < 1.0:
        nextIntervalFactor = 1.0 / nextIntervalFactor

    if (previousIntervalFactor is not None and previousIntervalFactor > maximumPeriodFactor and
            nextIntervalFactor is not None and nextIntervalFactor > maximumPeriodFactor):
        return False

    return True

# OK
def find_extremum_3(channel1_base, channel2_base, d, n, include_maxima, include_minima):
    channel1 = channel1_base[d:]
    channel2 = channel2_base[d:] if channel2_base is not None else None
    include_all = (include_maxima == include_minima)
    imin = imax = 0

    if n < 3:
        if n <= 0:
            return 0.0
        elif n == 1:
            return 1.0
        else:
            x1 = (channel1[0] + channel2[0]) / 2 if channel2 is not None else channel1[0]
            x2 = (channel1[1] + channel2[1]) / 2 if channel2 is not None else channel1[1]
            xleft = abs(x1) if include_all else x1 if include_maxima else -x1
            xright = abs(x2) if include_all else x2 if include_maxima else -x2
            return 1.0 if xleft > xright else 2.0 if xleft < xright else 1.5

    minimum = maximum = (channel1[0] + channel2[0]) / 2 if channel2 is not None else channel1[0]
    for i in range(1, n):
        value = (channel1[i] + channel2[i]) / 2 if channel2 is not None else channel1[i]
        if value < minimum:
            minimum = value
            imin = i
        if value > maximum:
            maximum = value
            imax = i

    if minimum == maximum:
        return 0.5 * (n + 1.0)

    if include_all:
        if abs(minimum) > abs(maximum):
            iextr = imin
        else:
            iextr = imax
    else:
        if include_maxima:
            iextr = imax
        else:
            iextr = imin

    if iextr == 0 or iextr == n:
        return iextr

    value_mid = (channel1[iextr] + channel2[iextr]) / 2 if channel2 is not None else channel1[iextr]
    value_left = (channel1[iextr - 1] + channel2[iextr - 1]) / 2 if channel2 is not None else channel1[iextr - 1]
    value_right = (channel1[iextr + 1] + channel2[iextr + 1]) / 2 if channel2 is not None else channel1[iextr + 1]
    return iextr + 0.5 * (value_right - value_left) / (2 * value_mid - value_left - value_right)

# OK
def sound_find_extremum(me, tmin, tmax, include_maxima, include_minima):
    assert tmin is not None
    assert tmax is not None
    imin = max(0, x_to_sampled_index(me, tmin, 'low'))
    imax = min(x_to_sampled_index(me, tmax, 'high'), me['nx'] - 1)
    iextremum = find_extremum_3(me['z'][0], me['z'][1] if me['ny'] > 1 else None, imin, imax - imin,
                                include_maxima, include_minima)
    if iextremum != 0.0:
        # Indexes 'imin' and 'iextremum' starts from zero
        return me['x1'] + (imin + iextremum) * me['dx']
    else:
        return 0.5 * (tmin + tmax)

# OK
def find_maximum_correlation(me, t1, windowLength, tmin2, tmax2):
    maximumCorrelation = -1.0  # smart 'impossible' starting value
    r1_best = r3_best = ir = None  # assignments not necessary, but extra safe
    r1 = r2 = r3 = 0.0
    halfWindowLength = 0.5 * windowLength
    ileft1 = x_to_sampled_index(me, t1 - halfWindowLength, 'nearest')
    iright1 = x_to_sampled_index(me, t1 + halfWindowLength, 'nearest')
    ileft2min = x_to_sampled_index(me, tmin2 - halfWindowLength, 'low')
    ileft2max = x_to_sampled_index(me, tmax2 - halfWindowLength, 'high')
    peak = 0.0  # default
    assert ileft2max >= ileft2min  # if the loop is never executed, the result will be garbage
    for ileft2 in range(ileft2min, ileft2max + 1):
        norm1 = norm2 = product = 0.0
        localPeak = 0.0
        for ichan in range(me['ny']):
            i2 = ileft2
            for i1 in range(ileft1, iright1 + 1):
                if i1 < 0 or i1 >= me['nx'] or i2 < 0 or i2 >= me['nx']:
                    continue
                amp1, amp2 = me['z'][ichan][i1], me['z'][ichan][i2]
                norm1 += amp1 ** 2
                norm2 += amp2 ** 2
                product += amp1 * amp2
                localPeak = max(localPeak, abs(amp2))
                i2 += 1

        r1, r2, r3 = r2, r3, 0.0 if product == 0.0 else product / np.sqrt(norm1 * norm2)
        if r2 > maximumCorrelation and r2 >= r1 and r2 >= r3:
            r1_best, maximumCorrelation, r3_best, ir = r1, r2, r3, ileft2 - 1
            peak = localPeak

    if maximumCorrelation > -1.0:  # was maximumCorrelation ever assigned to?...
        # ...then r1_best and r3_best and ir must also have been assigned to:
        assert r1_best is not None and r3_best is not None and ir is not None
        d2r = 2 * maximumCorrelation - r1_best - r3_best
        if d2r != 0.0:
            dr = 0.5 * (r3_best - r1_best)
            maximumCorrelation += 0.5 * dr * dr / d2r
            ir += dr / d2r
        tout = t1 + (ir - ileft1) * me['dx']
    return maximumCorrelation, peak, tout

# OK
def pitch_to_point(sound, pitch):
    try:
        point = []
        t = pitch['xmin']
        added_right = -1e308
        global_peak = np.max(np.abs(sound['z']))  # with interpolation?

        get_value_at_time = CubicSpline(
            [pitch['x1'] + pitch['dx'] * n for n in range(pitch['nx'])],
            [frame['candidates'][0]['frequency'] for frame in pitch['frames']])

        # Cycle over all voiced intervals
        edges = [0, 0]
        while get_voiced_interval_after(pitch, t, edges):
            t_left, t_right = edges
            assert t_right > t

            # Go to the middle of the voice stretch
            t_middle = (t_left + t_right) / 2
            f0_middle = get_value_at_time(t_middle)

            # Our first point is near this middle
            if f0_middle is None:
                raise ValueError(
                    f"Sound_Pitch_to_PointProcess_cc: tleft {t_left}, tright {t_right}, f0middle {f0_middle}")

            t_max = sound_find_extremum(
                        sound,
                        t_middle - 0.5 / f0_middle,
                        t_middle + 0.5 / f0_middle,
                        True, True)

            assert t_max is not None
            point.append(t_max)

            t_save = t_max
            while True:
                f0 = get_value_at_time(t_max)
                if f0 is None:
                    break
                correlation, peak, t_max = find_maximum_correlation(
                                                sound,
                                                t_max,
                                                1.0 / f0,
                                                t_max - 1.25 / f0,
                                                t_max - 0.8 / f0)
                if correlation == -1.0:
                    t_max -= 1.0 / f0
                if t_max < t_left:
                    if correlation > 0.7 and peak > 0.023333 * global_peak and t_max - added_right > 0.8 / f0:
                        point.append(t_max)
                    break
                if correlation > 0.3 and (peak == 0.0 or peak > 0.01 * global_peak):
                    if t_max - added_right > 0.8 / f0:
                        point.append(t_max)

            t_max = t_save
            while True:
                f0 = get_value_at_time(t_max)
                if f0 is None:
                    break
                correlation, peak, t_max = find_maximum_correlation(
                                                sound,
                                                t_max,
                                                1.0 / f0,
                                                t_max + 0.8 / f0,
                                                t_max + 1.25 / f0)
                if correlation == -1.0:
                    t_max += 1.0 / f0
                if t_max > t_right:
                    if correlation > 0.7 and peak > 0.023333 * global_peak:
                        point.append(t_max)
                        added_right = t_max
                    break
                if correlation > 0.3 and (peak == 0.0 or peak > 0.01 * global_peak):
                    point.append(t_max)
                    added_right = t_max

            t = t_right

        return point
    except Exception as e:
        raise ValueError(f"{sound} & {pitch}: not converted to PointProcess (cc).") from e

# OK
def sampled_index_to_x(me, index):
    # Index starts from zero
    return me['x1'] + index * me['dx']

# OK
def x_to_sampled_index(me, x, to_int=None):
    # Index starts from zero
    index = (x - me['x1']) / me['dx']
    if to_int == 'nearest':
        return round(index)
    elif to_int == 'low':
        return math.floor(index)
    elif to_int == 'high':
        return math.ceil(index)
    else:
        return index

# OK
def get_voiced_interval_after(me, after, edges):
    # Index starts from zero
    ileft = math.ceil((after - me['x1']) / me['dx'])
    if ileft >= me['nx']:
        return False   # offright
    if ileft < 0:
        ileft = 0   # offleft

    # Search for first voiced frame
    while ileft < me['nx']:
        if voiced_floor < me['frames'][ileft]['candidates'][0] < voiced_ceiling:
            break
        ileft += 1
    if ileft >= me['nx']:
        return False   # offright

    # Search for last voiced frame
    iright = ileft
    while iright < me['nx']:
        if not voiced_floor < me['frames'][iright]['candidates'][0] < voiced_ceiling:
            break
        iright += 1
    iright -= 1

    edges[0] = sampled_index_to_x(me, ileft) - 0.5 * me['dx']   # the whole frame is considered voiced
    edges[1] = sampled_index_to_x(me, iright) + 0.5 * me['dx']

    if edges[0] >= me['xmax'] - 0.5 * me['dx']:
        return False

    edges[0] = max(edges[0], me['xmin'])
    edges[1] = min(edges[1], me['xmax'])

    if edges[1] <= after:
        return False

    return True
