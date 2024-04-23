import numpy as np
from jitter import unidirectional_autowindow, get_window_points
from math import pi


class AmplitudeTier:
    def __init__(self, tmin, tmax):
        self.tmin = tmin
        self.tmax = tmax
        self.times = []
        self.values = []

    def addPoint(self, t, value):
        self.times.append(t)
        self.values.append(value)


def get_hann_windowed_rms(sound, tmid, widthLeft, widthRight):

    if (edges := get_window_samples(sound, tmid - widthLeft, tmid + widthRight)) is None:
        return None

    imin, imax = edges

    sumOfSquares = 0.0
    windowSumOfSquares = 0.0
    for i in range(imin, imax + 1):
        t = sound['x1'] + sound['dx'] * i
        width = widthLeft if t < tmid else widthRight
        windowPhase = (t - tmid) / width  # in [-1 .. 1]
        window = 0.5 + 0.5 * np.cos(pi * windowPhase)  # Hann
        if sound['ny'] == 1:
            windowedValue = sound['z'][0][i] * window
        else:
            windowedValue = 0.5 * (sound['z'][0][i] + sound['z'][1][i]) * window
        sumOfSquares += windowedValue ** 2
        windowSumOfSquares += window ** 2

    return np.sqrt(sumOfSquares / windowSumOfSquares)


def get_window_samples(sound, tmin, tmax):
    imin = np.ceil((tmin - sound['x1']) / sound['dx'])
    imax = np.floor((tmax - sound['x1']) / sound['dx'])
    imin = int(max(0.0, imin))
    imax = int(min(sound['nx'], imax))
    if imax - imin < 2:
        return None
    return imin, imax


def point_to_amplitude_period(pulse, sound, tmin, tmax, pmin, pmax, maximumPeriodFactor):
    try:
        tmin, tmax = unidirectional_autowindow(pulse, tmin, tmax)
        left, right = get_window_points(pulse, tmin, tmax)
        if right - left < 2:
            raise ValueError(f"Too few pulses between {tmin} and {tmax} seconds.")

        amplitude = AmplitudeTier(tmin, tmax)
        for i in range(1, right - left):
            p1 = pulse['t'][i] - pulse['t'][i - 1]
            p2 = pulse['t'][i + 1] - pulse['t'][i]
            intervalFactor = p1 / p2 if p1 > p2 else p2 / p1
            if pmin == pmax or (pmin <= p1 <= pmax and pmin <= p2 <= pmax and intervalFactor <= maximumPeriodFactor):
                peak = get_hann_windowed_rms(sound, pulse['t'][i], 0.2 * p1, 0.2 * p2)
                if peak is not None and peak > 0.0:
                    amplitude.addPoint(pulse.t[i], peak)

        return amplitude
    except Exception as e:
        raise ValueError(f"{pulse} & {sound}: not converted to AmplitudeTier.") from e


def PointProcess_Sound_getShimmer_local(pulse, thee, tmin, tmax, pmin, pmax, maximumPeriodFactor, maximumAmplitudeFactor):
    try:
        tmin, tmax = unidirectional_autowindow(pulse, tmin, tmax)
        peaks = point_to_amplitude_period(pulse, thee, tmin, tmax, pmin, pmax, maximumPeriodFactor)
        return AmplitudeTier_getShimmer_local(peaks, pmin, pmax, maximumAmplitudeFactor)
    except Exception as e:
        if "Too few pulses between" in str(e):
            return np.nan
        else:
            raise Exception(f"{pulse} & {thee}: shimmer (local) not computed.")


def AmplitudeTier_getShimmer_local(me, pmin, pmax, maximumAmplitudeFactor):
    numberOfPeaks = 0
    numerator = 0.0
    denominator = 0.0
    points = me.points
    for i in range(1, len(points)):
        p = points[i].number - points[i-1].number
        if pmin == pmax or (p >= pmin and p <= pmax):
            a1 = points[i-1].value
            a2 = points[i].value
            amplitudeFactor = a1 / a2 if a1 > a2 else a2 / a1
            if amplitudeFactor <= maximumAmplitudeFactor:
                numerator += abs(a1 - a2)
                numberOfPeaks += 1
    if numberOfPeaks < 1:
        return float('nan')
    numerator /= numberOfPeaks
    numberOfPeaks = 0
    for point in points:
        denominator += point.value
        numberOfPeaks += 1
    denominator /= numberOfPeaks
    if denominator == 0.0:
        return float('nan')
    return numerator / denominator
