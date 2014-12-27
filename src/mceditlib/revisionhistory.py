"""
    revisionhistory
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import collections
import json
import logging
import os
import shutil

from mceditlib.anvil.worldfolder import AnvilWorldFolder
from mceditlib.exceptions import ChunkNotPresent

log = logging.getLogger(__name__)
#
# RevisionHistory stores the edit history of a WorldFolder using a series of revision objects, each one storing the
# chunks and files changed or added in that revision along with a list of deleted chunks and files. Only the newest
# revision in the history may have new changes applied to it. Operations on a RevisionHistory:
#
#  createRevision:
# Creates a new revision at the head of the history. The previous head revision is marked read-only. If an earlier
# revision is given, removes all revisions after that revision and adds a revision after it as the new head.
#
#  closeRevision:
# Marks the head revision read-only. Client can use this to enforce that a new revision must be created with
# createRevision before further edits are made.
#
# writeAllChanges: Writes all changes since the last call to writeAllChanges, or since the beginning of the history
# if it hasn't been called. Rearranges the history to have the base world folder at the head of the history,
# or at the specified place in the history if a revision index is given. A partial revision holding the chunks and
# files that were overwritten by writeAllChanges is placed at the base world folder's previous position in the
# history to preserve the world folder's state at that place in the history.
#
#  getHead:
# Gets the newest revision in the history as a RevisionHistoryNode.
#
#  getRevision:
# Gets the revision at the requested index in the history as a RevisionHistoryNode
#
# RevisionHistoryNode reflects the state of the base WorldFolder at one place in its history. The node has all of
# the operations of a WorldFolder, including the chunk operations: listDimensions, containsChunk, chunkPositions,
# chunkCount, deleteChunk, readChunkBytes, writeChunkBytes; and the file operations: listFolder, containsFile,
# deleteFile, readFile, writeFile.
#
# It also has operations specific to the revision history: getChanges, getRevisionInfo, setRevisionInfo
#
#
# -- NOTES --
#
# How to preserve undo history after writing changes?
#
# Problem: the root folder now reflects all changes and cannot be the root folder any more, and must be
# moved to the head of the history. All chunks and files in the root folder that are overwritten will be lost
# from the history completely.
#
# Solution: While moving forward in the history, write each revision to the world folder, and save all files/chunks
# replaced by that revision into a new revision meant to reverse that revision's changes. The reverse revision
# will be placed before the written revision, replacing the world folder's previous place. The world folder will
# then replace the written revision. The reverse revision must also store delete commands for any files/chunks added
#  in the written revision. The reverse revision's previousNode should then point forward in the history,
# toward the world folder's new position. In fact, previousNode may not even be needed.


class RevisionChanges(object):
    def __init__(self):
        self.chunks = collections.defaultdict(set)  # dimName -> set[(cx, cz)]
        self.files = set()  # paths

    def __repr__(self):
        return "RevisionChanges(chunks=%r, files=%r)" % (self.chunks, self.files)

class UndoFolderExists(IOError):
    """
    Raised when initializing a RevisionHistory and an existing undo folder is found, but no resume mode is given.
    """

class RevisionHistory(object):
    """
    A history of partial world folders, used to implement disk-backed undo. Each partial folder represents a revision
    of the initial folder. Reading a file or chunk from the history will first read from the most recent world
    folder. If it is not found there, proceeds down the history until the requested data is found, and returns its
    most recent version. Writing a file or chunk will always write to the most recent revision.

    Chunks are read and written as NBT TAG_Compounds. Files are read and written as bytes.

    To begin using the RevisionHistory, call getHead() to get the head (latest) revision of the history as a
    RevisionHistoryNode. The RevisionHistory is created with the initial world folder as the head node. Call createRevision
    to create the first revision.

    To get a reference to an earlier revision, call getRevision with the index of the requested revision. For now,
    calling createRevision on an earlier revision will erase all subsequent revisions. In the future, this may be
    changed to implement a tree-shaped undo history.

    To write all changes from partial folders into the initial world folder, call writeAllChanges.

    When the RevisionHistory is deleted, all partial folders are removed from disk.
    """


    def __init__(self, filename, resume=None):
        """

        :param resume: Whether to resume editing if an undo folder already exists. Pass True to resume editing,
        False to delete the old world folder, or None to raise an exception if the folder exists.
        :type resume: bool | None
        :param filename: Path to the world folder to open
        :type filename: str | unicode
        :rtype: RevisionHistory
        """

        # Create undo folder in the folder containing the root folder.
        self.tempFolder = os.path.join(os.path.dirname(filename), "##%s.UNDO##" % os.path.basename(filename))
        if os.path.exists(self.tempFolder):
            if resume is True:
                raise NotImplementedError("Cannot resume from existing undo folder (yet)")
            elif resume is False:
                shutil.move(self.tempFolder, self.tempFolder + "__")
                shutil.rmtree(self.tempFolder + "__", ignore_errors=True)
            else:
                raise UndoFolderExists("Undo folder already exists for %s" % filename)
        os.makedirs(self.tempFolder)

        self.rootFolder = AnvilWorldFolder(filename)
        self.rootNode = RevisionHistoryNode(self, self.rootFolder, None)
        self.rootNode.differences = RevisionChanges()
        self.rootNodeIndex = 0
        self.orphanChainIndex = None
        self.IDcounter = 0
        self.nodes = [self.rootNode]

    def __repr__(self):
        return "RevisionHistory(%s)" % repr(self.rootFolder)

    def __del__(self):
        self.close()

    def close(self):
        """
        Close the RevisionHistory and release all resources, including all revisions. Operations on a closed RevisionHistory
        are undefined.
        :return:
        :rtype:
        """
        for node in self.nodes:
            node.worldFolder.close()
            self.nodes = []
        log.info("Removing undo folder %r", self.tempFolder)
        shutil.rmtree(self.tempFolder)
        self.readonly = True

    def _createRevisionFolder(self):
        ID = "%08d" % self.IDcounter
        self.IDcounter += 1

        filename = os.path.join(self.tempFolder, ID)
        return AnvilWorldFolder(filename, create=True)

    def createRevision(self, previousRevision=None):
        """
        Creates a new partial folder and appends it to the history. If revisionIndex is given, inserts the revision after
        that position and removes all later revisions. Inserting a revision before the position of any presave folders
        in the history after calling writeAllChanges will collapse those presave folders into the last presave folder
        in the new history.

        Subsequent writes are directed to this folder. This function must be called once before performing any edits,
        otherwise the world is read-only.

        :type previousRevision: int | RevisionHistoryNode
        :return: The newly created revision node.
        :rtype: RevisionHistoryNode
        """
        if isinstance(previousRevision, RevisionHistoryNode):
            if previousRevision is self.getHead():
                revisionIndex = len(self.nodes) - 1
            else:
                revisionIndex = self.nodes.index(previousRevision)

        elif previousRevision is None:
            revisionIndex = len(self.nodes) - 1
        else:
            revisionIndex = previousRevision

        if revisionIndex < self.rootNodeIndex:
            self.nodes[revisionIndex+1:] = []
            self.rootNodeIndex = revisionIndex
            self.orphanChainIndex = revisionIndex

            # Root folder is about to be orphaned. Revisions from revisionIndex on to the root folder won't show up
            #  in the history, but the world folder needs to stay as is. The node at revisionIndex will point
            # forward to the chain leading to the root folder, and the revision about to be created will point
            # backward to the node at revisionIndex. When the root folder is saved, it will need to move backwards
            # along its subchain until it reaches revisionIndex, deleting revisions as it goes instead of
            # reversing them, then move forward to the new revision.
            # Root folder won't be orphaned in more than one position in the history. When it needs to be moved
            # again because createRevision is called on a previous revision, the intervening revisions are made part
            #  of the new orphan chain and the newly created revision added as before. When it needs to be moved
            # because of a call to writeAllChanges, the orphan chain is collapsed onto the root folder before
            # writing changes as usual.

        newFolder = self._createRevisionFolder()

        previousNode = self.nodes[revisionIndex]
        previousNode.readonly = True

        newNode = RevisionHistoryNode(self, newFolder, previousNode)
        deadNodes = self.nodes[revisionIndex+1:]
        self.nodes = self.nodes[:revisionIndex+1]
        self.nodes.append(newNode)

        for node in deadNodes:
            if node.isPresave:
                node.previousNode = self.nodes[0]
                self.nodes[0] = node
            else:
                node.worldFolder.close()
                shutil.rmtree(node.worldFolder.filename, ignore_errors=True)
                node.invalid = True

        return newNode

    def closeRevision(self):
        self.getHead().readonly = True

    def getHead(self):
        return self.nodes[-1]

    def getRevision(self, idx):
        return self.nodes[idx]

    def getRevisionChanges(self, oldNode, newNode):
        """
        Return all changes that happened after oldNode up to and including those in newNode.

        Returns a RevisionChanges object that lists the chunks that changed by dimension name, and the files that
        changed. It does not distinguish between files/chunks that are newly created, modified or deleted.

        :param oldNode: Index of the node to find changes after, or the node itself.
        :type oldNode: int | RevisionHistoryNode
        :param newNode: Index of the node to find changes up to and including, or the node itself.
        :type newNode: int | RevisionHistoryNode
        :return:
        :rtype: RevisionChanges
        """
        changes = RevisionChanges()

        # The initial folder will provide the changes of the node it replaced in the history when writeAllChanges
        # was called.

        if isinstance(newNode, RevisionHistoryNode):
            newIndex = self.nodes.index(newNode)
        else:
            newIndex = newNode

        if isinstance(oldNode, RevisionHistoryNode):
            oldIndex = self.nodes.index(oldNode)
        else:
            oldIndex = oldNode

        if oldIndex > newIndex:
            oldIndex, newIndex = newIndex, oldIndex

        for node in self.nodes[oldIndex+1:newIndex+1]:
            nodeChanges = node.getChanges()
            for dimName, chunks in nodeChanges.chunks.iteritems():
                changes.chunks[dimName].update(chunks)
            changes.files.update(nodeChanges.files)

        return changes

    def writeAllChanges(self, requestedRevision=None):
        """
        Write all changes to the root world folder, preserving undo history. The previous head node is no longer
        valid after calling writeAllChanges. Specify a revision to only save changes up to and including that
        revision.
        :return:
        :rtype:
        """
        # XXXXX wait for async writes to complete here

        if isinstance(requestedRevision, RevisionHistoryNode):
            requestedIndex = self.nodes.index(requestedRevision)
        elif requestedRevision is None:
            requestedIndex = len(self.nodes) - 1
        else:
            requestedIndex = requestedRevision

        if self.orphanChainIndex is not None:
            # Root node is orphaned - collapse orphan chain into it in reverse order
            orphanNodes = []
            orphanChainNode = self.nodes[self.orphanChainIndex]
            while orphanChainNode is not self.rootNode:
                orphanNodes.append(orphanChainNode)
                orphanChainNode = orphanChainNode.parentNode

            for orphanChainNode in reversed(orphanNodes):
                copyToFolder(self.rootFolder, orphanChainNode)

            self.nodes[self.orphanChainIndex] = self.rootNode
            self.orphanChainIndex = None

        if requestedIndex == self.rootNodeIndex:
            return  # nothing to do
        elif requestedIndex < self.rootNodeIndex:
            direction = -1
            indexes = xrange(self.rootNodeIndex-1, requestedIndex-1, -1)
        else:
            direction = 1
            indexes = xrange(self.rootNodeIndex+1, requestedIndex+1)
        log.info("writeAllChanges: moving %s", "forwards" if direction == 1 else "backwards")

        for currentIndex in indexes:
            # Write all changes from each node into the initial folder. Save the previous
            # chunk and file data from the initial folder into a reverse revision.

            currentNode = self.nodes[currentIndex]

            reverseFolder = self._createRevisionFolder()
            reverseNode = RevisionHistoryNode(self, reverseFolder, self.nodes[currentIndex - direction])

            reverseNode.differences = self.rootNode.differences
            self.rootNode.differences = currentNode.getChanges()

            copyToFolder(self.rootFolder, currentNode, reverseNode)
            # xxx look ahead one or more nodes to skip some copies

            reverseNode.setRevisionInfo(self.rootNode.getRevisionInfo())
            reverseNode.readonly = True
            self.rootNode.setRevisionInfo(currentNode.getRevisionInfo())

            # Replace the previousNode with the reverse node, and the currentNode with the rootNode
            self.nodes[currentIndex - direction] = reverseNode
            self.nodes[currentIndex] = self.rootNode
            self.rootNodeIndex = currentIndex

            log.info("Root node now at index %d", currentIndex)

            assert currentNode is not self.rootNode, "Root node appears twice in nodes!"
            currentNode.worldFolder.close()
            currentNode.invalid = True
            shutil.rmtree(currentNode.worldFolder.filename, ignore_errors=True)


def copyToFolder(destFolder, sourceNode, presaveNode=None):
    if presaveNode:
        presaveFolder = presaveNode.worldFolder
    else:
        presaveNode = None

    sourceFolder = sourceNode.worldFolder

    # Remove deleted chunks
    for cx, cz, dimName in sourceNode.deadChunks:
        if destFolder.containsChunk(cx, cz, dimName):
            if presaveFolder and not presaveFolder.containsChunk(cx, cz, dimName):
                presaveFolder.writeChunkBytes(cx, cz, dimName, destFolder.readChunkBytes(cx, cz, dimName))
            destFolder.deleteChunk(cx, cz, dimName)

    # Write new and modified chunks
    for dimName in sourceFolder.listDimensions():
        for cx, cz in sourceFolder.chunkPositions(dimName):
            if presaveFolder and not presaveFolder.containsChunk(cx, cz, dimName):
                if destFolder.containsChunk(cx, cz, dimName):
                    presaveFolder.writeChunkBytes(cx, cz, dimName, destFolder.readChunkBytes(cx, cz, dimName))
                else:  # new chunk
                    presaveNode.deleteChunk(cx, cz, dimName)
            destFolder.writeChunkBytes(cx, cz, dimName, sourceFolder.readChunkBytes(cx, cz, dimName))

    # Remove deleted files
    for path in sourceNode.deadFiles:
        if destFolder.containsFile(path):
            if presaveFolder and not presaveFolder.containsFile(path):
                presaveFolder.writeFile(path, destFolder.readFile(path))
            destFolder.deleteFile(path)

    # Write new and modified files
    for path in sourceFolder.listAllFiles():
        if presaveFolder and not presaveFolder.containsFile(path):
            if destFolder.containsFile(path):
                presaveFolder.writeFile(path, destFolder.readFile(path))
            else:  # new file
                presaveNode.deleteFile(path)
        destFolder.writeFile(path, sourceFolder.readFile(path))

class RevisionHistoryNode(object):
    def __init__(self, history, worldFolder, parentNode):
        """

        :param history:
        :type history: RevisionHistory
        :param worldFolder:
        :type worldFolder: AnvilWorldFolder
        :param parentNode:
        :type parentNode: RevisionHistoryNode | None
        :return:
        :rtype:
        """
        self.history = history
        self.worldFolder = worldFolder
        self.parentNode = parentNode
        self.deadChunks = set()
        self.deadFiles = set()
        self.isPresave = False
        self.readonly = False
        self.differences = None
        self.invalid = False

    def __repr__(self):
        return "RevisionHistoryNode(readonly=%s, isPresave=%s, worldFolder=%s)" % (self.readonly, self.isPresave, repr(
            self.worldFolder))

    def getChanges(self):
        if self.differences:
            return self.differences

        changes = RevisionChanges()
        for dimName in self.worldFolder.listDimensions():
            changes.chunks[dimName] = set(self.worldFolder.chunkPositions(dimName))
        changes.files = set(self.worldFolder.listAllFiles())
        for cx, cz, dimName in self.deadChunks:
            changes.chunks[dimName].add((cx, cz))
        changes.files.update(self.deadFiles)

        return changes

    # --- Chunks ---

    def listDimensions(self):
        """
        List the names of all dimensions in this world.

        :return:
        :rtype: Iterator of [str]
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)

        dims = set()
        node = self
        while node:
            dims.update(node.worldFolder.listDimensions())
            node = node.parentNode

        return iter(dims)

    def containsChunk(self, cx, cz, dimName):
        """
        Return whether the given chunk is present in the given dimension

        :type cx: int
        :type cz: int
        :type dimName: str
        :return:
        :rtype: bool
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        node = self
        while node:
            if (cx, cz, dimName) in node.deadChunks:
                return False
            if node.worldFolder.containsChunk(cx, cz, dimName):
                return True

            node = node.parentNode
        return False

    def chunkPositions(self, dimName):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        node = self
        pos = set()
        while node:
            pos.update(node.worldFolder.chunkPositions(dimName))

            node = node.parentNode

        return pos

    def chunkCount(self, dimName):
        node = self
        count = 0
        while node:
            count += node.worldFolder.chunkCount(dimName)
            if node is self.history.rootNode:
                break

            node = node.parentNode
        return count

    def chunkPositionsThisRevision(self, dimName):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        return self.worldFolder.chunkPositions(dimName)

    def _deadChunksFile(self):
        return self.worldFolder.getFilePath("##MCEDIT.DEAD.CHUNKS##")

    def deleteChunk(self, cx, cz, dimName):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        if self.readonly:
            raise IOError("Storage node is read-only!")
        if self.worldFolder.containsChunk(cx, cz, dimName):
            self.worldFolder.deleteChunk(cx, cz, dimName)
        else:
            with file(self._deadChunksFile(), "w") as f:
                f.write("%d, %d, %s\n" % (cx, cz, dimName))
                f.close()
            self.deadChunks.add((cx, cz, dimName))

    def loadDeletedChunks(self):
        """
        A list of chunks deleted in this revision that MAY be present in previous revisions
        :return:
        :rtype:
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        with file(self._deadChunksFile()) as f:
            lines = f.read().split('\n')

        def _coords():
            for line in lines:
                cx, cz = line.split(", ")
                yield int(cx), int(cz)

        return _coords()

    def readChunkBytes(self, cx, cz, dimName):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        node = self
        while node:
            # Ask RevisionHistory for most recent node containing this chunk?
            if node.worldFolder.containsChunk(cx, cz, dimName):
                data = node.worldFolder.readChunkBytes(cx, cz, dimName)
                return data
            if node is self.history.rootNode:
                break

            node = node.parentNode

        raise ChunkNotPresent((cx, cz))

    def writeChunkBytes(self, cx, cz, dimName, data):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        if self.readonly:
            raise IOError("Storage node is read-only!")
        self.worldFolder.writeChunkBytes(cx, cz, dimName, data)

    # --- Regular files ---

    def containsFile(self, path):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        node = self
        while node:
            if path in node.deadFiles:
                return False
            if node.worldFolder.containsFile(path):
                return True
            if node is self.history.rootNode:
                break

            node = node.parentNode

        return False

    def _deadFilesFile(self):
        return self.worldFolder.getFilePath("##MCEDIT.DEAD.FILES##")

    def deleteFile(self, path):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        if self.readonly:
            raise IOError("Storage node is read-only!")
        if self.worldFolder.containsFile(path):
            self.worldFolder.deleteFile(path)
        else:
            with file(self._deadFilesFile(), "w") as f:
                f.write("%s\n" % path)
                f.close()
            self.deadFiles.add(path)

    def loadDeletedFiles(self):
        """
        A list of files deleted in this revision that MAY be present in previous revisions
        :return:
        :rtype:
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        with file(self._deadFilesFile()) as f:
            return f.read().split('\n')

    def readFile(self, path):
        """
        Read the specified file from the most recent revision containing that file.
        :param path:
        :type path:
        :return:
        :rtype:
        """
        # Ask RevisionHistory for most recent node containing this file?
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        node = self
        while node:
            if node.worldFolder.containsFile(path):
                data = node.worldFolder.readFile(path)
                if data is not None:
                    return data
                if node is self.history.rootNode:
                    break

            node = node.parentNode
        raise IOError("File not found")

    def writeFile(self, path, data):
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        if self.readonly:
            raise IOError("Storage node is read-only!")
        self.worldFolder.writeFile(path, data)

    def listFolder(self, path):
        """
        List the contents of the given folder, reading all previous revisions. Ignores the REVINFO file.

        rev1:
          level.dat
          some.file

        rev2
          level.dat_old

        rev3
          another.file
          -some.file

        rev4
          -another.file
          some.file

        @4 +some.file -another_file
          newFiles some.file
          files some.file
          deadFiles anotherFile
        @3 -some.file +another.file
          newFiles
          files some.file
          deadFiles anotherFile someFile
        @2 +level.dat_old
          newFiles level.dat_old
          files some.file level.dat_old
          deadFiles anotherFile someFile
        @1 +level.dat +some.file
          newFiles level.dat
          files level.dat level.dat_old some.file
          deadFiles anotherFile someFile

        expected:
          level.dat
          level.dat_old
          some.file

        :param path:
        :type path:
        :return:
        :rtype:
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        files = set()
        deadFiles = set()

        node = self
        while node:
            newFiles = set(node.worldFolder.listFolder(path))
            newFiles.discard(self.REVINFO_FILENAME)
            newFiles.difference_update(deadFiles)
            files.update(newFiles)
            deadFiles.update(node.deadFiles)
            if node is self.history.rootNode:
                break
            node = node.parentNode

        return files.difference(deadFiles)

    REVINFO_FILENAME = "##MCEDIT.REVINFO##"

    def getRevisionInfo(self):
        """
        Read revision info from a JSON-formatted file for the client's internal use.
        Returns None if no revision info is assigned.
        :return:
        :rtype: list | dict | str | unicode | int | None
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        if self is self.history.rootNode:
            filename = os.path.join(self.history.tempFolder, self.REVINFO_FILENAME)
            if not os.path.exists(filename):
                return None
            return json.load(open(filename, "rb"))
        else:
            if not self.worldFolder.containsFile(self.REVINFO_FILENAME):
                return None
            return json.loads(self.worldFolder.readFile(self.REVINFO_FILENAME))

    def setRevisionInfo(self, info):
        """
        Write revision info to a JSON-formatted file for the client's internal use
        :return:
        :rtype:
        """
        if self.invalid:
            raise RuntimeError("Accessing invalid node: %r" % self)
        if self is self.history.rootNode:
            # Write revision info to extra file in undo folder
            json.dump(info, open(os.path.join(self.history.tempFolder, self.REVINFO_FILENAME), "wb"))
        else:
            if self.readonly:
                raise IOError("Revision is read-only. Cannot set revision info.")
            self.worldFolder.writeFile(self.REVINFO_FILENAME, json.dumps(info))

