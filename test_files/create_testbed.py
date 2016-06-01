"""
    create_testbed
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

import numpy

from mcedit2.worldview.schematic_worldview import displaySchematic
from mceditlib.schematic import SchematicFileAdapter, createSchematic
from mceditlib.worldeditor import WorldEditor

log = logging.getLogger(__name__)

def main():
    blockWidth = 64
    blockCount = 256*16

    width = blockWidth * 3 + 1
    rows = blockCount // blockWidth + 1
    length = rows * 3 + 1
    height = 3

    world = createSchematic((width, height, length))
    dim = world.getDimension()

    allBlocks = [world.blocktypes[a, b] for a in range(256) for b in range(16)]

    w, l = numpy.indices((width, length))

    dim.setBlocks(w, 1, l, "minecraft:stone")

    for i, block in enumerate(allBlocks):
        col = (i % blockWidth) * 3 + 1
        row = (i // blockWidth) * 3
        dim.setBlocks([col, col+1, col, col+1], 2, [row, row, row+1, row+1], block)

    world.saveToFile("testbed.schematic")
    displaySchematic(dim)

if __name__ == '__main__':
    main()