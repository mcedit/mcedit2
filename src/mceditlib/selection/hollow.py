"""
    hollow
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mceditlib.selection import SelectionBox

log = logging.getLogger(__name__)


class HollowSelection(SelectionBox):
    def __init__(self, base):
        super(HollowSelection, self).__init__()

        self.base = base
        self.mincx = base.mincx
        self.mincy = base.mincy
        self.mincz = base.mincz
        self.maxcx = base.maxcx
        self.maxcy = base.maxcy
        self.maxcz = base.maxcz

    def box_mask(self, box):

        bigBox = box.expand(1)

        mask = self.base.box_mask(bigBox)

        # Find exposed faces

        exposedY = mask[:-1] != mask[1:]
        exposedZ = mask[:, :-1] != mask[:, 1:]
        exposedX = mask[:, :, :-1] != mask[:, :, 1:]

        # Any block with exposed faces is rendered

        exposed = exposedY[:-1, 1:-1, 1:-1]
        exposed |= exposedY[1:, 1:-1, 1:-1]
        exposed |= exposedZ[1:-1, :-1, 1:-1]
        exposed |= exposedZ[1:-1, 1:, 1:-1]
        exposed |= exposedX[1:-1, 1:-1, :-1]
        exposed |= exposedX[1:-1, 1:-1, 1:]

        mask = mask[1:-1,1:-1,1:-1]
        result = mask & exposed
        log.info("%d blocks in mask, %d present after hollow", mask.sum(), result.sum())

        return result
