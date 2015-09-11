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

    :param iterable:
    :param start:
    :param end:
    :return:
    """
    d = end - start

    for current, maximum, status in iterable:
        yield start + current * d / maximum, end, status


def enumProgress(collection, start, end=None):
    """
    Iterate through a collection, yielding (progress, value) tuples. `progress` is the value
    between `start` and `end` proportional to the progress through the collection.

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