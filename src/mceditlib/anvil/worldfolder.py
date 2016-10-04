"""
    worldfolder
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from collections import defaultdict
import logging
from mceditlib.exceptions import ChunkNotPresent

log = logging.getLogger(__name__)

from mceditlib.pc.regionfile import RegionFile
import os


class AnvilWorldFolder(object):
    def __init__(self, filename, create=False, readonly=False):
        '''

        :type filename: str or unicode
        :type create: bool
        '''
        if not os.path.exists(filename):
            if create:
                os.mkdir(filename)
            else:
                raise IOError("World not found")

        elif not os.path.isdir(filename):
            raise IOError("AnvilWorldFolder: Not a folder: %s" % filename)

        self.filename = filename
        self.readonly = readonly
        self.regionFiles = {}
        self._dimensionNames = set(self._findDimensions())
        self._regionPositionsByDim = defaultdict(set)
        self._regionPositionsByDim.update({dimName: set(self._listRegionFiles(dimName))
                                           for dimName in self._dimensionNames})


    def __repr__(self):
        return "AnvilWorldFolder(%s)" % repr(self.filename)

    # --- File paths ---

    def getFilePath(self, path):
        path = path.replace("/", os.path.sep)
        path = path.lstrip(os.path.sep)
        return os.path.join(self.filename, path)

    def getFolderPath(self, path):
        path = self.getFilePath(path)
        if not os.path.exists(path):
            os.makedirs(path)

        return path

    # --- Ordinary files ---

    def containsFile(self, path):
        return os.path.exists(self.getFilePath(path))

    def deleteFile(self, path):
        return os.unlink(self.getFilePath(path))

    def readFile(self, path):
        with open(self.getFilePath(path), "rb") as f:
            return f.read()

    def writeFile(self, path, data):
        path = self.getFilePath(path)
        dirpath = os.path.dirname(path)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
        with open(path, "wb") as f:
            f.write(data)

    def listFolder(self, path):
        """
        Returns the path of each file or folder in the given folder. All paths returned
        are relative to the world folder and use '/' as the path separator.

        :param path: Folder to list
        :type path: unicode
        :return: List of file/folder paths
        :rtype: Iterator[unicode]
        """
        for filename in os.listdir(self.getFolderPath(path)):
            yield "%s/%s" % (path, filename)

    def listAllFiles(self):
        for root, dirs, files in os.walk(self.filename):
            root = root.replace(self.filename, "").replace(os.path.sep, "/")
            for filename in files:
                if filename.endswith(".mca") or filename.endswith(".mcr") or filename.startswith("##MCEDIT"):
                    continue
                else:
                    yield "%s/%s" % (root, filename)

    # --- Region files and dimensions ---

    def _findDimensions(self):
        yield ""
        worldDirs = os.listdir(self.filename)
        for dirname in worldDirs:
            if dirname.startswith("##"):
                continue
            try:
                if os.path.exists(os.path.join(self.filename, dirname, "region")):
                    log.debug("Found dimension {0}".format(dirname))
                    yield dirname
            except Exception as e:
                log.info(u"Error detecting dimension {0}: {1}".format(dirname, e))
                continue

    def listDimensions(self):
        return iter(self._dimensionNames)


    def getRegionFolderPath(self, dimName):
        if dimName == "":
            return self.getFolderPath("region")
        else:
            return self.getFolderPath("%s/region" % dimName)

    def _listRegionFiles(self, dimName):
        regionDir = self.getRegionFolderPath(dimName)

        regionFiles = os.listdir(regionDir)
        for filename in regionFiles:
            bits = filename.split('.')
            if len(bits) < 4 or bits[0] != 'r' or bits[3] != "mca":
                log.info("Unexpected file in region folder: %s", filename)
                continue

            try:
                rx, rz = map(int, bits[1:3])
            except ValueError:
                log.info("Unexpected file in region folder: %s", filename)
                continue

            yield rx, rz

    def getRegionFilename(self, rx, rz, dimName):
        return os.path.join(self.getRegionFolderPath(dimName), "r.%s.%s.%s" % (rx, rz, "mca"))

    def getRegionFile(self, rx, rz, dimName):
        """

        :type rx: int or dtype
        :type rz: int or dtype
        :type dimName: unicode or str
        :return:
        :rtype: RegionFile
        """
        regionFile = self.regionFiles.get((rx, rz, dimName))
        if regionFile:
            return regionFile
        path = self.getRegionFilename(rx, rz, dimName)
        if not os.path.exists(path):
            self._dimensionNames.add(dimName)
            self._regionPositionsByDim[dimName].add((rx, rz))
        try:
            regionFile = RegionFile(path, self.readonly)
        except Exception:
            log.exception("Failed to open region file.")
            return None
        self.regionFiles[rx, rz, dimName] = regionFile
        return regionFile

    def getRegionForChunk(self, cx, cz, dimName):
        rx = cx >> 5
        rz = cz >> 5
        return self.getRegionFile(rx, rz, dimName)

    def close(self):
        self.regionFiles = {}

    # --- Chunks and chunk listing ---

    def chunkCount(self, dimName):
        """

        :param dimName: Name of dimension
        :type dimName: unicode or str
        :return: Number of chunks in given dimension
        :rtype: int
        """
        count = 0
        for rx, rz in self._regionPositionsByDim[dimName]:
            regionFile = self.getRegionFile(rx, rz, dimName)
            if regionFile is None:
                continue

            count += regionFile.chunkCount
        return count

    def chunkPositions(self, dimName):
        """
        Iterate over chunk positions
        :type dimName: unicode or str
        :return: iterator
        :rtype: iterator [(int, int)]
        """
        for rx, rz in set(self._regionPositionsByDim[dimName]):
            regionFile = self.getRegionFile(rx, rz, dimName)
            if regionFile is None:
                continue

            if regionFile.chunkCount:
                for cx, cz in regionFile.chunkPositions():
                    cx += rx << 5
                    cz += rz << 5
                    yield (cx, cz)
            else:
                filename = regionFile.path
                log.info(u"Removing empty region file {0}".format(filename))
                self._regionPositionsByDim[dimName].remove((rx, rz))
                del self.regionFiles[rx, rz, dimName]
                os.unlink(regionFile.path)

    def containsChunk(self, cx, cz, dimName):
        rx = cx >> 5
        rz = cz >> 5
        if (rx, rz) not in self._regionPositionsByDim[dimName]:
            return False

        return self.getRegionForChunk(cx, cz, dimName).containsChunk(cx, cz)

    def deleteChunk(self, cx, cz, dimName):
        rx = cx >> 5
        rz = cz >> 5
        rf = self.getRegionFile(rx, rz, dimName)
        if rf:
            rf.deleteChunk(cx & 0x1f, cz & 0x1f)
            if rf.chunkCount == 0:
                del self.regionFiles[rx, rz, dimName]
                os.unlink(rf.path)

    def readChunkBytes(self, cx, cz, dimName):
        if not self.containsChunk(cx, cz, dimName):
            raise ChunkNotPresent((cx, cz))
        return self.getRegionForChunk(cx, cz, dimName).readChunkBytes(cx, cz)

    def writeChunkBytes(self, cx, cz, dimName, data):
        self.getRegionForChunk(cx, cz, dimName).writeChunkBytes(cx, cz, data)

    def copyChunkFrom(self, sourceFolder, cx, cz, dimName):
        """
        Copy chunk from another source folder without decompression
        :param sourceFolder:
        :type sourceFolder: AnvilWorldFolder
        :param cx:
        :type cx: int
        :param cz:
        :type cz: int
        :param dimName:
        :type dimName: unicode
        :return:
        :rtype:
        """
        data, fmt = sourceFolder.getRegionForChunk(cx, cz, dimName).readChunkCompressed(cx, cz)
        self.getRegionForChunk(cx, cz, dimName).writeChunkCompressed(cx, cz, data, fmt)
