"""
    RegionFile class.

    Reads and writes chunks to *.mcr* (Minecraft Region)
    and *.mca* (Minecraft Anvil Region) files
"""
from __future__ import absolute_import, division
import logging
import os
import struct
import zlib
import time

import numpy

from mceditlib import nbt
from mceditlib.exceptions import ChunkNotPresent, RegionFormatError

REGION_DEBUG = 5
logging.addLevelName("REGION_DEBUG", REGION_DEBUG)

log = logging.getLogger(__name__)

# Disable region debugging today.
log.setLevel(logging.DEBUG)

def region_debug(msg, *args, **kwargs):
    return log.log(REGION_DEBUG, msg, *args, **kwargs)

__author__ = 'Rio'


def deflate(data):
    return zlib.compress(data, 2)


def inflate(data):
    return zlib.decompress(data)

class RegionFile(object):
    SECTOR_BYTES = 4096
    CHUNK_HEADER_SIZE = 5
    VERSION_GZIP = 1
    VERSION_DEFLATE = 2

    def __init__(self, path, readonly=False):
        self.path = path
        newFile = False
        if not os.path.exists(path):
            if readonly:
                raise IOError("Region file not found: %r" % path)
            open(path, "w").close()
            newFile = True

        filesize = os.path.getsize(path)
        mode = "rb" if readonly else "rb+"
        with open(self.path, mode) as f:

            if newFile:
                filesize = self.SECTOR_BYTES * 2
                f.truncate(filesize)
                self.offsets = numpy.zeros(self.SECTOR_BYTES//4, dtype='>u4')
                self.modTimes = numpy.zeros(self.SECTOR_BYTES//4, dtype='>u4')
            else:

                if not readonly:
                    # Increase file size if not a multiple of sector size
                    if filesize & 0xfff:
                        filesize = (filesize | 0xfff) + 1
                        f.truncate(filesize)

                    # Increase file size if empty (new regionfile)
                    if filesize == 0:
                        filesize = self.SECTOR_BYTES * 2
                        f.truncate(filesize)

                f.seek(0)
                offsetsData = f.read(self.SECTOR_BYTES)
                modTimesData = f.read(self.SECTOR_BYTES)

                self.offsets = numpy.fromstring(offsetsData, dtype='>u4')
                self.modTimes = numpy.fromstring(modTimesData, dtype='>u4')

            self.freeSectors = [True] * (filesize // self.SECTOR_BYTES)
            self.freeSectors[0:2] = False, False

            if not newFile:
                needsRepair = False

                # Populate freeSectors table
                for offset in self.offsets:
                    sector = offset >> 8
                    count = offset & 0xff

                    for i in xrange(sector, sector + count):
                        if i >= len(self.freeSectors):
                            log.warn("Region file offset table points to sector %d (past the end of the file)", i)
                            needsRepair = True
                            break
                        if self.freeSectors[i] is False:
                            needsRepair = True
                        self.freeSectors[i] = False

                if needsRepair:
                    self.repair()

                region_debug("Found region file %s with %d/%d sectors used and %d chunks present",
                          os.path.basename(path), self.usedSectors, self.sectorCount, self.chunkCount)
            else:
                region_debug("Created new region file %s", os.path.basename(path))

    def __repr__(self):
        return "%s(\"%s\")" % (self.__class__.__name__, self.path)

    @property
    def usedSectors(self):
        return len(self.freeSectors) - sum(self.freeSectors)

    @property
    def sectorCount(self):
        return len(self.freeSectors)

    @property
    def chunkCount(self):
        return numpy.sum(self.offsets > 0)

    def chunkPositions(self):
        for index, offset in enumerate(self.offsets):
            if offset:
                cx = index & 0x1f
                cz = index >> 5
                yield (cx, cz)

    def repair(self):
        """
        Fix the following problems with the region file:
         - remove offset table entries pointing past the end of the file
         - remove entries that overlap other entries
         - relocate offsets for chunks whose xPos,yPos don't match
        """

        lostAndFound = {}
        _freeSectors = [True] * len(self.freeSectors)
        _freeSectors[0] = _freeSectors[1] = False
        deleted = 0
        recovered = 0
        log.info("Beginning repairs on {file} ({chunks} chunks)".format(file=os.path.basename(self.path), chunks=sum(self.offsets > 0)))
        for index, offset in enumerate(self.offsets):
            if offset:
                cx = index & 0x1f
                cz = index >> 5
                sectorStart = offset >> 8
                sectorCount = offset & 0xff
                try:

                    if sectorStart + sectorCount > len(self.freeSectors):
                        raise RegionFormatError("Offset {start}:{end} ({offset}) at index {index} pointed outside of "
                                                "the file".format(start=sectorStart, end=sectorStart + sectorCount, index=index, offset=offset))

                    data = self.readChunkBytes(cx, cz)
                    chunkTag = nbt.load(buf=data)
                    lev = chunkTag["Level"]
                    xPos = lev["xPos"].value & 0x1f
                    zPos = lev["zPos"].value & 0x1f
                    overlaps = False

                    for i in xrange(sectorStart, sectorStart + sectorCount):
                        if _freeSectors[i] is False:
                            overlaps = True
                        _freeSectors[i] = False

                    if xPos != cx or zPos != cz:
                        lostAndFound[xPos, zPos] = data
                        raise RegionFormatError("Chunk {found} was found in the slot reserved for {expected}".format(found=(xPos, zPos), expected=(cx, cz)))

                    if overlaps:
                        raise RegionFormatError("Chunk {found} (in slot {expected}) has overlapping sectors with another chunk!".format(found=(xPos, zPos), expected=(cx, cz)))

                except Exception as e:
                    log.info("Unexpected chunk data at sector {sector} ({exc})".format(sector=sectorStart, exc=e))
                    self._setOffset(cx, cz, 0)
                    deleted += 1

        for cPos, foundData in lostAndFound.iteritems():
            cx, cz = cPos
            if self._getOffset(cx, cz) == 0:
                log.info("Found chunk {found} and its slot is empty, recovering it".format(found=cPos))
                self.writeChunkBytes(cx, cz, foundData)
                recovered += 1

        log.info("Repair complete. Removed {0} chunks, recovered {1} chunks, net {2}".format(deleted, recovered, recovered - deleted))

    def readChunkCompressed(self, cx, cz):
        """
        Read a chunk and return its compression type and the compressed data as a (data, fmt) tuple
        """
        cx &= 0x1f
        cz &= 0x1f
        offset = self._getOffset(cx, cz)
        if offset == 0:
            raise ChunkNotPresent((cx, cz))

        sectorStart = offset >> 8
        numSectors = offset & 0xff
        if numSectors == 0:
            raise ChunkNotPresent((cx, cz))

        if sectorStart + numSectors > len(self.freeSectors):
            raise ChunkNotPresent((cx, cz))

        with open(self.path, "rb") as f:
            f.seek(sectorStart * self.SECTOR_BYTES)
            data = f.read(numSectors * self.SECTOR_BYTES)
        if len(data) < 5:
            raise RegionFormatError("Chunk %s data is only %d bytes long (expected 5)" % ((cx, cz), len(data)))

        # region_debug("REGION LOAD {0},{1} sector {2}".format(cx, cz, sectorStart))

        length = struct.unpack_from(">I", data)[0]
        fmt = struct.unpack_from("B", data, 4)[0]
        data = data[5:length + 5]
        return data, fmt

    def readChunkBytes(self, cx, cz):
        """

        :param cx:
        :type cx:
        :param cz:
        :type cz:
        :return:
        :rtype: bytes
        """
        data, fmt = self.readChunkCompressed(cx, cz)
        if data is None:
            return None
        if fmt == self.VERSION_GZIP:
            return nbt.gunzip(data)
        if fmt == self.VERSION_DEFLATE:
            return inflate(data)

        raise RegionFormatError("Unknown compress format: {0}".format(fmt))

    def writeChunkBytes(self, cx, cz, uncompressedData):
        data = deflate(uncompressedData)
        self.writeChunkCompressed(cx, cz, data, self.VERSION_DEFLATE)

    def writeChunkCompressed(self, cx, cz, data, format):
        cx &= 0x1f
        cz &= 0x1f
        offset = self._getOffset(cx, cz)
        sectorNumber = offset >> 8
        sectorsAllocated = offset & 0xff
        sectorsNeeded = (len(data) + self.CHUNK_HEADER_SIZE) // self.SECTOR_BYTES + 1
        if sectorsNeeded >= 256:
            err = RegionFormatError("Cannot save chunk %s with compressed length %s (exceeds 1 megabyte)" %
                                    ((cx, cz), len(data)))
            err.chunkPosition = cx, cz

        if sectorNumber != 0 and sectorsAllocated >= sectorsNeeded:
            region_debug("REGION SAVE {0},{1} rewriting {2}b".format(cx, cz, len(data)))
            self.writeSector(sectorNumber, data, format)
        else:
            # we need to allocate new sectors

            # mark the sectors previously used for this chunk as free
            for i in xrange(sectorNumber, sectorNumber + sectorsAllocated):
                self.freeSectors[i] = True

            runLength = 0
            runStart = 0
            try:
                runStart = self.freeSectors.index(True)

                for i in range(runStart, len(self.freeSectors)):
                    if runLength:
                        if self.freeSectors[i]:
                            runLength += 1
                        else:
                            runLength = 0
                    elif self.freeSectors[i]:
                        runStart = i
                        runLength = 1

                    if runLength >= sectorsNeeded:
                        break
            except ValueError:
                pass

            # we found a free space large enough
            if runLength >= sectorsNeeded:
                region_debug("REGION SAVE {0},{1}, reusing {2}b".format(cx, cz, len(data)))
                sectorNumber = runStart
                self._setOffset(cx, cz, sectorNumber << 8 | sectorsNeeded)
                self.writeSector(sectorNumber, data, format)
                self.freeSectors[sectorNumber:sectorNumber + sectorsNeeded] = [False] * sectorsNeeded

            else:
                # no free space large enough found -- we need to grow the
                # file

                region_debug("REGION SAVE {0},{1}, growing by {2}b".format(cx, cz, len(data)))

                with open(self.path, "rb+") as f:
                    f.seek(0, 2)
                    filesize = f.tell()

                    sectorNumber = len(self.freeSectors)

                    assert sectorNumber * self.SECTOR_BYTES == filesize

                    filesize += sectorsNeeded * self.SECTOR_BYTES
                    f.truncate(filesize)

                self.freeSectors += [False] * sectorsNeeded

                self._setOffset(cx, cz, sectorNumber << 8 | sectorsNeeded)
                self.writeSector(sectorNumber, data, format)

        self.setTimestamp(cx, cz)

    def writeSector(self, sectorNumber, data, format):
        with open(self.path, "rb+") as f:
            region_debug("REGION: Writing sector {0}".format(sectorNumber))

            f.seek(sectorNumber * self.SECTOR_BYTES)
            f.write(struct.pack(">I", len(data) + 1))  # // chunk length
            f.write(struct.pack("B", format))  # // chunk version number
            f.write(data)  # // chunk data
            # f.flush()

    def containsChunk(self, cx, cz):
        return self._getOffset(cx, cz) != 0

    def _getOffset(self, cx, cz):
        cx &= 0x1f
        cz &= 0x1f
        return self.offsets[cx + cz * 32]

    def _setOffset(self, cx, cz, offset):
        cx &= 0x1f
        cz &= 0x1f
        self.offsets[cx + cz * 32] = offset
        with open(self.path, "rb+") as f:
            f.seek(0)
            f.write(self.offsets.tostring())

    def deleteChunk(self, cx, cz):
        offset = self._getOffset(cx, cz)
        sectorNumber = offset >> 8
        sectorsAllocated = offset & 0xff
        for i in range(sectorNumber, sectorNumber + sectorsAllocated):
            self.freeSectors[i] = True

        self._setOffset(cx, cz, 0)

    def getTimestamp(self, cx, cz):
        cx &= 0x1f
        cz &= 0x1f
        return self.modTimes[cx + cz * 32]

    def setTimestamp(self, cx, cz, timestamp=None):
        if timestamp is None:
            timestamp = time.time()

        cx &= 0x1f
        cz &= 0x1f
        self.modTimes[cx + cz * 32] = timestamp
        with open(self.path, "rb+") as f:
            f.seek(self.SECTOR_BYTES)
            f.write(self.modTimes.tostring())
