
from math import ceil, log
import pdb
import random
import sys
import time

base = 36
digits = '0123456789abcdefghijklmnopqrstuvwxyz'

# Three different ways to get index of a digit.

digit_index_dict = {
    digit: index
    for index, digit in enumerate(digits)}

ASCII_ZERO = ord('0')
LETTER_DIGIT_DELTA = ord('a') - ord('0') - 10

def digit_to_index(digit):
    index = ord(digit) - ASCII_ZERO
    return index if index < 10 else index - LETTER_DIGIT_DELTA

digit_index_tuple = (

    tuple(

        None if i < ord('0') else
            i - ord('0') if i < ord('a') else
            i - ord('a') + 10

        for i in range(ord('z') + 1)))

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
    new_value = digits[digit_index_dict[marker[to_increase]] + 1]
    return marker[:to_increase] + new_value

def decreased(marker, to_decrease):
    new_value = digits[digit_index_dict[marker[to_decrease]] - 1]
    return marker[:to_decrease] + new_value

increase_dict = {

    digit_before: digit_after
    for digit_before, digit_after in zip(digits[:-1], digits[1:])}

decrease_dict = {

    digit_after: digit_before
    for digit_before, digit_after in zip(digits[:-1], digits[1:])}

def delta(larger, smaller):
    return int(larger, base) - int(smaller, base)

# Get lexgraph marker between two closest
def marker_between(marker_before='', marker_after=''):

    if marker_before and marker_after and marker_before >= marker_after:
        raise ValueError("first argument must be less than second one")

    if marker_after and int(marker_after, base) == 0:
        raise ValueError("not possible be less than just '0'(s)")

    # Supplement marker_before by '0'(s) and marker_after by 'z'(s) to have equal lengths
    # Now marker can even consist just of '0'(s) or 'z'(s) if it was empty before
    marker1 = marker_before + '0' * (len(marker_after) - len(marker_before))
    marker2 = marker_after + 'z' * (len(marker_before) - len(marker_after))

    result = ''

    for m1, m2 in zip(marker1, marker2):

        if digit_index_dict[m2] - digit_index_dict[m1] <= 1:
            result += m1

        # under 'h' letter move down
        elif m2 > 'h':
            return result + increase_dict[m1]

        # above 'h' letter move up
        else:
            return result + decrease_dict[m2]

    return result + 'h'

def get_lexgraph_list_arith(
    how_many,
    prefix = '',
    marker_list = None):
    """
    Recursively populates list of lexicographically ordered markers, trying for an even spread.
    """

    if marker_list is None:

        marker_list = []

    if how_many <= 0:

        return marker_list

    # Only single digits.

    base_m1 = base - 1

    if how_many <= base_m1:

        threshold = base_m1

        how_many_x2 = how_many * 2
        base_m1_x2 = base_m1 * 2

        index = threshold // how_many_x2
        count = 1

        marker_list.append(prefix + digits[index + 1])

        while count < how_many:

            threshold += base_m1_x2

            index = threshold // how_many_x2
            count += 1

            marker_list.append(prefix + digits[index + 1])

        return marker_list

    # All 35 valid single digits with the rest recursively.

    how_many_after = how_many - base_m1

    how_many_per = how_many_after // base
    how_many_extra = how_many_after % base

    threshold = base // 2

    for i in range(base):

        current_prefix = (
            prefix + digits[i])

        if i > 0:

            marker_list.append(current_prefix)

        how_many_current = how_many_per

        if (i + 1) * how_many_extra >= threshold:

            how_many_current += 1
            threshold += base

        get_lexgraph_list_arith(
            how_many_current,
            current_prefix,
            marker_list)

    return marker_list

def marker_between_arith(
    marker_before = '',
    marker_after = ''):
    """
    Generate a marker between two others, as short as possible and, secondly, as close to the middle as
    possible.
    """

    if marker_before and marker_after and marker_before >= marker_after:
        raise ValueError("first argument must be less than second one")

    len_before = len(marker_before)
    len_after = len(marker_after)

    # Going through digits, computing shorted between that is also slosest to (before + after) // 2.

    value_list = []

    carry = (
        0 if marker_after else base)

    i = 0

    while True:

        value_before = (
            digit_index_dict[marker_before[i]] if i < len_before else 0)

        value_after = (

            carry +
            (digit_index_dict[marker_after[i]] if i < len_after else 0))

        if value_after - value_before > 1:

            value_list.append((value_before + value_after) // 2)
            break

        value_list.append(value_before)

        carry = (
            0 if value_after == value_before else base)

        i += 1

    # Normalizing by carrying up if required.

    for i in range(len(value_list) - 1, 0, -1):

        if value_list[i] >= base:

            value_list[i] -= base
            value_list[i - 1] += 1

    return ''.join(digits[i] for i in value_list)

def main_list(
    args,
    arith_flag = False,
    assert_flag = False):
    """
    Shows how generation of a list of markers works.
    """

    n_length = int(args[0])

    lexgraph_f = (
        get_lexgraph_list_arith if arith_flag else
        get_lexgraph_list)

    marker_list = (
        lexgraph_f(n_length))

    len_list = tuple(map(len, marker_list))

    avg_len_start = sum(len_list) / n_length
    min_len_start = min(len_list)
    max_len_start = max(len_list)

    print(marker_list)
    print(f'min/avg/max len: {min_len_start:.3f} / {avg_len_start:.3f} / {max_len_start:.3f}')

    if assert_flag:

        assert marker_list == sorted(marker_list)
        assert len(marker_list) == n_length

def main_between(
    args,
    arith_flag = False,
    assert_flag = False):
    """
    Shows how between marker computation works.
    """

    marker_before = args[0]
    marker_after = args[1]

    between_f = (
        marker_between_arith if arith_flag else
        marker_between)

    between = (

        between_f(
            marker_before,
            marker_after))

    print(f'{repr(marker_before)}, {repr(marker_after)} -> {repr(between)}')

    if assert_flag:

        assert marker_before < between
        assert marker_after > between

def main_test(
    args,
    arith_flag = False,
    assert_flag = False,
    verbose_flag = False):
    """
    Tests marker implementation via multiple random swaps.
    """

    n_length = int(args[0])
    n_swaps = int(args[1])

    seed = (

        int(
            args[2] if len(args) > 2 else
            time.time() * 1e6 % 1e6))

    print(f'seed: {seed}')

    rng = (
        random.Random(seed))

    if arith_flag:

        lexgraph_f = get_lexgraph_list_arith
        between_f = marker_between_arith

    else:

        lexgraph_f = get_lexgraph_list
        between_f = marker_between

    marker_list = (
        lexgraph_f(n_length))

    if assert_flag:

        assert marker_list == sorted(marker_list)
        assert len(marker_list) == n_length

    len_list = tuple(map(len, marker_list))

    avg_len_start = sum(len_list) / n_length
    min_len_start = min(len_list)
    max_len_start = max(len_list)

    time_start = time.time()

    print(marker_list)
    print(f'min/avg/max len: {min_len_start:.3f} / {avg_len_start:.3f} / {max_len_start:.3f}')

    for i in range(n_swaps):

        index_from = rng.randrange(0, n_length)
        index_to = rng.randrange(0, n_length)

        marker_list.pop(index_from)

        marker_before = (
            '' if index_to <= 0 else marker_list[index_to - 1])

        marker_after = (
            '' if index_to >= n_length - 1 else marker_list[index_to])

        between = (

            between_f(
                marker_before,
                marker_after))

        marker_list.insert(index_to, between)

        if assert_flag:

            assert marker_list == sorted(marker_list)

        if verbose_flag:

            print(
                f'{repr(marker_before)} ({index_to - 1}), '
                f'{repr(marker_after)} ({index_to}) -> '
                f'{repr(between)}')

            print(marker_list)

    time_elapsed = (
        time.time() - time_start)

    len_list = tuple(map(len, marker_list))

    avg_len_end = sum(len_list) / n_length
    min_len_end = min(len_list)
    max_len_end = max(len_list)

    avg_len_delta = (
        avg_len_end - avg_len_start)

    min_len_delta = (
        min_len_end - min_len_start)

    max_len_delta = (
        max_len_end - max_len_start)

    print(f'{time_elapsed:.6f}s')

    print(marker_list)

    print(
        'min/avg/max len:\n'
        f'{min_len_end:.3f} / {avg_len_end:.3f} / {max_len_end:.3f}\n'
        f'{min_len_delta:+.3f} / {avg_len_delta:+.3f} / {max_len_delta:+.3f}\n'
        f'{min_len_delta / n_swaps:+.6f} / '
        f'{avg_len_delta / n_swaps:+.6f} / '
        f'{max_len_delta / n_swaps:+.6f} per swap')

    print(f'seed: {seed}')

if __name__ == '__main__':

    args = sys.argv[1:]

    arith_flag = False
    assert_flag = False
    verbose_flag = False

    if '--arith' in args:

        args.remove('--arith')
        arith_flag = True

    if '--assert' in args:

        args.remove('--assert')
        assert_flag = True

    if '--verbose' in args:

        args.remove('--verbose')
        verbose_flag = True

    if args[0] == 'list':

        main_list(
            args[1:],
            arith_flag,
            assert_flag)

    elif args[0] == 'between':

        main_between(
            args[1:],
            arith_flag,
            assert_flag)

    elif args[0] == 'test':

        main_test(
            args[1:],
            arith_flag,
            assert_flag,
            verbose_flag)

