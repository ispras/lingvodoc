import bisect


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
