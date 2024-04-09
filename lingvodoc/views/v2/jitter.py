import bisect
import math

voiced_floor = 75
voiced_ceiling = 600

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


def unidirectional_autowindow(me, tmin, tmax):
    if tmin >= tmax:
        tmin = me['xmin']
        tmax = me['xmax']
    return tmin, tmax


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

    # Period condition 3: the interval cannot be too different from both of its neigbours, if any.
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


import numpy as np
from scipy.signal import find_peaks

# TODO: implement
def get_value_at_time(pitch, t):
    value = voiced_floor
    return value

def pitch_to_point(sound, pitch):
    try:
        point = []
        t = pitch['xmin']
        added_right = -1e308
        global_peak = np.max(np.abs(sound['z']))

        # Cycle over all voiced intervals
        edges = [0, 0]
        while get_voiced_interval_after(pitch, t, edges):
            t_left, t_right = edges
            assert t_right > t

            # Go to the middle of the voice stretch
            t_middle = (t_left + t_right) / 2
            f0_middle = get_value_at_time(pitch, t_middle)

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
                f0 = get_value_at_time(pitch, t_max)
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
                f0 = get_value_at_time(pitch, t_max)
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


def sampled_index_to_x(me, index):
    return me['x1'] + (index - 1) * me['dx']


def get_voiced_interval_after(me, after, edges):
    ileft = math.ceil((after - me['x1']) / me['dx'] + 1.0)
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
