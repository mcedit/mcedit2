"""
    time_loadall
"""
from __future__ import absolute_import, division, print_function
import logging
import timeit
from mceditlib.test import templevel

log = logging.getLogger(__name__)

def loadall():
    ents = 0
    for cPos in dim.chunkPositions():
        chunk = dim.getChunk(*cPos)
        ents += len(chunk.Entities) + len(chunk.TileEntities)
    print("[Tile]Entities: ", ents)

def saveall():
    for cPos in dim.chunkPositions():
        dim.getChunk(*cPos).dirty = True
    editor.saveChanges()

editor = templevel.TempLevel("AnvilWorld_1.8")
dim = editor.getDimension()

print("Loaded %d chunks in %.02fms" % (dim.chunkCount(), timeit.timeit(loadall, number=1) * 1000))
print("Saved %d chunks in %.02fms" % (dim.chunkCount(), timeit.timeit(saveall, number=1) * 1000))
