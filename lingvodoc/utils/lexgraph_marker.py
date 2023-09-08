from math import ceil, log
from os.path import commonprefix
import re

base = 35
digits = '0123456789abcdefghijklmnopqrstuvwxyz'
max_digit = digits[base - 1]

# Calculating lexgraph marker for decimal value
def get_lexgraph_marker(number):
    result = ''
    while number > 0:
        result = digits[number % base] + result
        number //= base
    return result or '0'

# Get list of lexgraph markers with string_number entries
def get_lexgraph_list(string_number):
    markers = []
    length = ceil(log(string_number, base))
    for number in range(string_number):
        result = get_lexgraph_marker(number)
        result = '0' * (length - len(result)) + result
        if int(result, base) == 0:
            result += 'z'
        markers.append(result)
    return markers

# Get lexgraph marker between two closest
def marker_between(marker_before, marker_after):

    if not marker_before and not marker_after:
        return None

    if not marker_before:
        marker = marker_after
        to_decrease = re.search(f'^[0]*', marker).span()[1]
        if to_decrease == len(marker):
            return None
        # Decrease the position what still is not minimal
        new_value = digits[digits.index(marker[to_decrease]) - 1]
        marker = marker[:to_decrease] + new_value
        if marker[-1] == '0':
            marker += 'z'
        return marker

    if not marker_after:
        marker = marker_before
        to_increase = re.search(f'[{max_digit}z]*$', marker).span()[0]
        if to_increase == 0:
            return marker + '0z'
        # Increase the position what still is not maximal
        new_value = digits[digits.index(marker[to_increase - 1]) + 1]
        return marker[:to_increase-1] + new_value + marker[to_increase:]

    if marker_before >= marker_after:
        return None
