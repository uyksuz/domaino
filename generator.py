import itertools
import string

CHARSET = string.ascii_lowercase
LENGTHS = [3, 4, 5, 6]


def total_count(length):
    return len(CHARSET) ** length


def get_slice(length, offset, count):
    gen = itertools.islice(
        itertools.product(CHARSET, repeat=length),
        offset,
        offset + count
    )
    return [''.join(combo) + '.com' for combo in gen]
