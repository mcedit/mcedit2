"""
    cache_test
"""
from __future__ import absolute_import, division, print_function
from collections import deque
import logging


def testThrashing(pc_world):
    if not hasattr(pc_world, '_chunkDataCache'):
        return
    pc_world.setCacheLimit(200)
    dim = pc_world.getDimension()
    recent = deque(maxlen=10)
    assert dim.chunkCount() > 200

    for cx, cz in dim.chunkPositions():
        _ = dim.getChunk(cx, cz)
        for lastChunkPos in recent:
            if lastChunkPos not in pc_world._chunkDataCache:
                raise ValueError(
                    "Cache thrashing detected! %s no longer in cache. (cache has %d stored, %d hits %d misses)\n"
                    "Cache keys: %s" % (
                        lastChunkPos, len(pc_world._chunkDataCache.cache), pc_world._chunkDataCache.hits,
                        pc_world._chunkDataCache.misses,
                        list(pc_world._chunkDataCache)))
        recent.append((cx, cz, ""))


def testOldThrashing(pc_world):
    if not hasattr(pc_world, '_loadedChunkData'):
        return
    pc_world.loadedChunkLimit = 50
    dim = pc_world.getDimension()
    recent = deque(maxlen=10)
    for cx, cz in dim.chunkPositions():
        chunk = dim.getChunk(cx, cz)
        for lastChunkPos in recent:
            if lastChunkPos not in pc_world._loadedChunkData:
                raise ValueError("Cache thrashing detected! %s no longer in cache. \n"
                                 "Cache keys: %s" % (
                                     lastChunkPos,
                                     pc_world._loadedChunkData.keys()))
        recent.append((cx, cz, ""))

    log.info("Finished. %d in cache.", len(pc_world._loadedChunkData))
