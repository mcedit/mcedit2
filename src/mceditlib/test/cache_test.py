"""
    cache_test
"""
from __future__ import absolute_import, division, print_function
from collections import deque
import logging
import pytest
from mceditlib.test.templevel import TempLevel

log = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)


@pytest.fixture(params=["AnvilWorld"])
def world(request):
    return TempLevel(request.param)


def testThrashing(world):
    if not hasattr(world, '_chunkDataCache'):
        return
    world.setCacheLimit(50)
    dim = world.getDimension()
    recent = deque(maxlen=10)
    for cx, cz in dim.chunkPositions():
        chunk = dim.getChunk(cx, cz)
        for lastChunkPos in recent:
            if lastChunkPos not in world._chunkDataCache:
                raise ValueError(
                    "Cache thrashing detected! %s no longer in cache. (cache has %d stored, %d hits %d misses)\n"
                    "Cache keys: %s" % (
                        lastChunkPos, len(world._chunkDataCache.cache), world._chunkDataCache.hits,
                        world._chunkDataCache.misses,
                        list(world._chunkDataCache)))
        recent.append((cx, cz, ""))


def testOldThrashing(world):
    if not hasattr(world, '_loadedChunkData'):
        return
    world.loadedChunkLimit = 50
    dim = world.getDimension()
    recent = deque(maxlen=10)
    for cx, cz in dim.chunkPositions():
        chunk = dim.getChunk(cx, cz)
        for lastChunkPos in recent:
            if lastChunkPos not in world._loadedChunkData:
                raise ValueError("Cache thrashing detected! %s no longer in cache. \n"
                                 "Cache keys: %s" % (
                                     lastChunkPos,
                                     world._loadedChunkData.keys()))
        recent.append((cx, cz, ""))

    log.info("Finished. %d in cache.", len(world._loadedChunkData))
