"""
    time_storagechain
"""
import logging
from timeit import timeit

from benchmarks import bench_temp_file
from mceditlib import nbt
from mceditlib.revisionhistory import RevisionHistory

log = logging.getLogger(__name__)

chain = RevisionHistory(bench_temp_file("AnvilWorld"))

chunkPositions = list(chain.getHead().chunkPositions(""))

from random import choice

def readChunk(rev, cx, cz):
    return nbt.load(buf=rev.readChunkBytes(cx, cz, ""))

def writeChunk(rev, cx, cz, tag):
    rev.writeChunkBytes(cx, cz, "", tag.save(compressed=False))

def addRevisions():
    for i in range(1000):
        rev = chain.createRevision()
        cx, cz = choice(chunkPositions)
        tag = readChunk(rev, cx, cz)
        tag["Level"]["touched"] = nbt.TAG_Byte(1)
        writeChunk(rev, cx, cz, tag)

def timeAccess():
    head = chain.getHead()
    for cx, cz in chunkPositions:
        tag = readChunk(head, cx, cz)


print "Empty: %0.1f ms" % (timeit(timeAccess, number=1)*1000)
print "addRevisions: %0.1f ms" % (timeit(addRevisions, number=1)*1000)
print "Full: %0.1f ms" % (timeit(timeAccess, number=1)*1000)
print "Save: %0.1f ms" % (timeit(chain.writeAllChanges, number=1)*1000)
