from math import ceil, log

base = 36
digits = '0123456789abcdefghijklmnopqrstuvwxyz'

# Calculating lexgraph marker for decimal value
def get_lexgraph_marker(number):
    result = ''
    while number > 0:
        result = digits[number % base] + result
        number //= base
    return result or '0'

# Get list of lexgraph markers
def get_lexgraph_list(length):
    markers = []
    # First marker is '1'
    dimension = ceil(log(length + 1, base))
    for number in range(length):
        result = get_lexgraph_marker(number + 1)
        result = '0' * (dimension - len(result)) + result
        markers.append(result)
    return markers

def increased(marker, to_increase):
    new_value = digits[digits.index(marker[to_increase]) + 1]
    return marker[:to_increase] + new_value

def decreased(marker, to_decrease):
    new_value = digits[digits.index(marker[to_decrease]) - 1]
    return marker[:to_decrease] + new_value

def delta(larger, smaller):
    return int(larger, base) - int(smaller, base)

# Get lexgraph marker between two closest
def marker_between(marker_before='', marker_after=''):

    if marker_before and marker_after and marker_before >= marker_after:
        raise ValueError("first argument must be less than second one")
    if int(marker_after, base) == 0:
        raise ValueError("not possible be less than just '0'(s)")

    # Supplement marker_before by '0'(s) and marker_after by 'z'(s) to have equal lengths
    # Now marker can even consist just of '0'(s) or 'z'(s) if it was empty before
    marker1 = marker_before + '0' * (len(marker_after) - len(marker_before))
    marker2 = marker_after + 'z' * (len(marker_before) - len(marker_after))

    result = ''
    for pos in range(len(marker1)):
        if delta(marker2[pos], marker1[pos]) <= 1:
            result += marker1[pos]
            continue
        # under 'h' letter move down
        elif marker2[pos] > 'h':
            result += marker1[pos]
            return increased(result, pos)
        # above 'h' letter move up
        else:
            result += marker2[pos]
            return decreased(result, pos)
    return result + 'h'
