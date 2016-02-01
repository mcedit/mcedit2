"""
    progress
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

log = logging.getLogger(__name__)


def rescaleProgress(iterable, start, end):
    """
    Given an iterable that yields (current, maximum, status) tuples, rescales current and maximum
    to fit within the range [start, end]. `current` is assumed to start at zero.

    Use rescaleProgress to combine multiple progress-yielding iterables by assigning
    a different range to each iterable.

    :param iterable:
    :param start:
    :param end:
    :return:
    """
    d = end - start
    status = ""

    for progress in iterable:
        if isinstance(progress, tuple):
            current, maximum = progress[:2]
            if len(progress) > 2:
                status = progress[2]

            if maximum:
                offset = current * d / maximum
            else:
                offset = 0

            yield start + offset, end, status
        else:
            yield progress


def enumProgress(collection, start, end=None):
    """
    Iterate through a collection, yielding (progress, value) tuples. `progress` is the value
    between `start` and `end` proportional to the progress through the collection.

    Use enumProgress to report the progress of iterating through a collection, scaled
    to a fixed amount of progress.

    :param collection:
    :param progress:
    :return:
    """
    if end is None:
        end = start
        start = 0

    if len(collection) == 0:
        return

    progFraction = (end - start) / len(collection)
    for i, value in enumerate(collection):
        yield start + i * progFraction, value