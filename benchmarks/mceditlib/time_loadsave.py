"""
    time_loadall
"""
from __future__ import absolute_import, division, print_function
import logging
import timeit
import gc

from benchmarks import bench_temp_level

log = logging.getLogger(__name__)

def loadall():
    ents = 0
    for cPos in pos[cStart:cEnd]:
        chunk = dim.getChunk(*cPos)
        ents += len(chunk.Entities) + len(chunk.TileEntities)
        # lc = len(editor._loadedChunks)
        # if lc > 20:
        #     refs = gc.get_referrers(chunk)
        #     print("Referrers:\n%s" % refs)
        #     print("WorldEditor: _loadedChunks: %d (_pending_removals: %d)" % (lc, len(editor._loadedChunks._pending_removals)))
    print("[Tile]Entities: ", ents)

def saveall():
    for cPos in pos[cStart:cEnd]:
        dim.getChunk(*cPos).dirty = True
    editor.saveChanges()

import sys
if len(sys.argv) > 1:
    filename = sys.argv[1]
else:
    filename = "AnvilWorld_1.8"

editor = bench_temp_level(filename)
dim = editor.getDimension()


cStart = 0
cEnd = 10000
chunkCount = cEnd - cStart

pos = list(dim.chunkPositions())

loadTime = timeit.timeit(loadall, number=1)
print("Loaded %d chunks in %.02fms (%f cps)" % (chunkCount, loadTime * 1000, chunkCount/loadTime))
print("Cache hits: %d, misses: %d, rejects: %d, max rejects: %d, queue: %d" % (
    editor._chunkDataCache.hits, editor._chunkDataCache.misses,
    editor._chunkDataCache.rejects, editor._chunkDataCache.max_rejects,
    len(editor._chunkDataCache.queue)))
print("WorldEditor: _loadedChunks: %d" % (len(editor._loadedChunks),))
#saveTime = timeit.timeit(saveall, number=1)
#print("Saved %d chunks in %.02fms (%f cps)" % (chunkCount, saveTime * 1000, chunkCount/saveTime))
