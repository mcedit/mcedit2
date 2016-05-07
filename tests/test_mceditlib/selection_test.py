"""
    selection_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

def test_difference():
    box1 = BoundingBox((0, 0, 0), (10, 10, 10))
    box2 = BoundingBox((0, 5, 0), (10, 10, 10))

    diff = box1 - box2

    mask = diff.box_mask(box1)
    assert not mask[5:, :, :].any()
