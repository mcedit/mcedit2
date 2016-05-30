"""
    structure_test
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mceditlib.selection import BoundingBox
from mceditlib.structure import exportStructure

log = logging.getLogger(__name__)

def testStructureExport(pc_world, tmpdir):
    selection = BoundingBox((-6, 62, 44), size=(32, 32, 32))
    structurePath = tmpdir.join("structure_out.nbt").strpath
    exportStructure(structurePath, pc_world.getDimension(), selection)
