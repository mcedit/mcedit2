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
from mceditlib.util.progress import rescaleProgress, enumProgress

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
# Problem: the root folder now reflects all changes and cannot be the tail node any more, and must be
# moved to the head of the history. All chunks and files in the root folder that are overwritten will be lost
# from the history completely.
#
# Solution: While moving forward in the history, write each revision to the world folder, and save all files/chunks
# replaced by that revision into a new revision meant to reverse that revision's changes. The reverse revision
# will be placed before the written revision, replacing the world folder's previous place. The world folder will
# then replace the written revision. The reverse revision must also store delete commands for any files/chunks added
#  in the written revision. The reverse revision's previousNode should then point forward in the history,
# toward the world folder's new position. In fact, previousNode may not even be needed.
#
#
# ---
# Each node has a 'parentNode' pointer which points to the node that its revision is
# based on. The pointer will point in one of three directions:
#
# Backward if the root node is earlier in the history
# Forward if `writeAllChanges` was previously called (this node is now a "revert" node)
# To an "orphaned" node not in the history if the root node is no longer in the history
# A node will be "orphaned" if, after `writeAllChanges` is called, a new revision is
# created before the root node's current position in the history.
#
# Initial State:
#
# root
# ^-head
#
# After adding several revisions with changes:
#
# root <- 1 <- 2 <- 3
#                   ^-head
#
# After calling writeAllChanges:
#
# 1' -> 2' -> 3' -> root
#                   ^-head
#
# After undoing twice:
#
# 1' -> 2' -> 3' -> root
#       ^-head
#
#
# Adding revisions to 2' will create an orphan chain starting with 2':
#
#       orphanChainIndex -> 2'
#
#       -> 3' -> root
#       |
# 1' -> 2' <- 4 <- 5
#                  ^-head
#
# Here, calling writeAllChanges must re-revert the changes in 3' and then 2' before
# applying the changes in 4 and 5. orphanChainIndex points to 2'. We walk this chain
# until it hits root and collect all nodes, including 2', and then apply them to root
# in reverse order. After collapsing the orphan chain, we should have this:
#
# 1' -> root <- 4 <- 5
#                    ^-head
#
# Then we can call the rest of writeAllChanges as usual:
#
# 1' -> 4' -> 5' -> root
#                   ^-head


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
        
        Parameters
        ----------
        
        resume : bool | None
            Whether to resume editing if an undo folder already exists. Pass True to resume editing,
            False to delete the old world folder, or None to raise an exception if the folder exists.
        filename : str | unicode
            Path to the world folder to open
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
            
            # The root folder is ahead of the requested revision. We want this newly
            # created revision to point to the current state of the world folder, but
            # we also don't want to modify the root folder right now.
            #
            # The node at `revisionIndex` captures the current state of the world folder,
            # since its chain of `previousNode` pointers will point along a list of
            # "reversion" revisions that eventually points to the root folder.
            # We allow it to keep this chain while all of the nodes in that chain
            # are removed from the revision history, and we store the index
            # of this node in `orphanChainIndex` so we can later collapse the orphaned
            # chain back onto the root folder during `writeAllChanges()`
            #
            # Oddly, `rootNodeIndex` now points to this node, which is not the original
            # root node. However, it is the "effective" root node because when `createRevision`
            # is called again with a revision that comes before the "root node", the
            # intervening revisions will be added onto the tail of the orphan chain
            # and the `orphanChainIndex` will be updated accordingly.
            #
            # This also means there is no possibility of having multiple orphaned chains.
            # Either the new revision is created after the "effective" root node and is
            # created normally, or it is created before this node and the orphan chain
            # is extended.
            
        newFolder = self._createRevisionFolder()

        previousNode = self.nodes[revisionIndex]
        previousNode.readonly = True

        newNode = RevisionHistoryNode(self, newFolder, previousNode)
        deadNodes = self.nodes[revisionIndex+1:]
        self.nodes = self.nodes[:revisionIndex+1]
        self.nodes.append(newNode)

        for node in deadNodes:
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
        for status in self.writeAllChangesIter(requestedRevision):
            pass

    def writeAllChangesIter(self, requestedRevision=None):
        """
        Write all changes to the root world folder, preserving undo history.
        
        If a revision is requested, the state of the world at that revision will be
        written, otherwise, the last node in the history is used.
        
        All nodes between the root node and the requested node, inclusive, are replaced
        with new nodes. The old nodes are no longer valid. The root node will be placed at
        the position in the nodes list previously occupied by the requested node.

        Parameters
        ----------
        
        requestedRevision: RevisionHistoryNode | int | None
            If given, this specifies the revision to write to the world folder, otherwise
            the most recent revision is written.
        
        Returns
        -------
        
        progress: Iterator[(current, max, status)]
            Progress information for the write-changes task.
            
        """
        # XXXXX wait for async writes to complete here
        # Progress counts:
        # 0-20:   Orphaned chains
        # 20-100: History nodes

        maxprogress = 100

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
            
            # Apply each orphaned node onto the root node.
            for progress, orphanChainNode in enumProgress(orphanNodes[::-1], 0, 20):
                yield (progress, maxprogress, "Collapsing orphaned chain")

                copyTask = copyToFolderIter(self.rootFolder, orphanChainNode)
                copyTask = rescaleProgress(copyTask, progress, progress + 20./len(orphanNodes))
                for current, _, status in copyTask:
                    yield current, maxprogress, status

            # Root node now replaces the orphan chain's tail in the history.
            # (the nodes ahead and behind of the root node should now point to this node)
            self.nodes[self.orphanChainIndex] = self.rootNode
            self.orphanChainIndex = None
            
        if requestedIndex == self.rootNodeIndex:
            return  # nothing to do
        elif requestedIndex < self.rootNodeIndex:
            # Nodes behind the root node in the history will be re-reverted and replaced
            # with plain nodes
            direction = -1
            indexes = xrange(self.rootNodeIndex-1, requestedIndex-1, -1)
        else:
            # Nodes ahead of the root node will be reverted and replaced with
            # "reversion" nodes.
            direction = 1
            indexes = xrange(self.rootNodeIndex+1, requestedIndex+1)
            
        log.info("writeAllChanges: moving %s", "forwards" if direction == 1 else "backwards")

        for progress, currentIndex in enumProgress(indexes, 20, 100):
            # Write all changes from each node into the initial folder. Save the previous
            # chunk and file data from the initial folder into a reverse revision.

            currentNode = self.nodes[currentIndex]

            reverseFolder = self._createRevisionFolder()
            reverseNode = RevisionHistoryNode(self, reverseFolder, self.nodes[currentIndex - direction])

            reverseNode.differences = self.rootNode.differences
            self.rootNode.differences = currentNode.getChanges()

            copyTask = copyToFolderIter(self.rootFolder, currentNode, reverseNode)
            copyTask = rescaleProgress(copyTask, progress, progress + 80. / len(indexes))
            for current, _, status in copyTask:
                yield current, maxprogress, status

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
    for status in copyToFolderIter(destFolder, sourceNode, presaveNode):
        pass


def copyToFolderIter(destFolder, sourceNode, reversionNode=None):
    # Progress counts:
    # 0-10:   deleted chunks
    # 10-80:  new/modified chunks
    # 80-90:  deleted files
    # 90-100: new/modified files

    if reversionNode:
        reversionFolder = reversionNode.worldFolder
    else:
        reversionFolder = None

    sourceFolder = sourceNode.worldFolder

    maxprogress = 100

    # Remove deleted chunks
    for deadProgress, (cx, cz, dimName) in enumProgress(sourceNode.deadChunks, 0, 10):
        yield deadProgress, maxprogress, "Removing deleted chunks"

        if destFolder.containsChunk(cx, cz, dimName):
            if reversionFolder and not reversionFolder.containsChunk(cx, cz, dimName):
                reversionFolder.writeChunkBytes(cx, cz, dimName, destFolder.readChunkBytes(cx, cz, dimName))
            destFolder.deleteChunk(cx, cz, dimName)

    # Write new and modified chunks
    dims = list(sourceFolder.listDimensions())
    dimProgress = 70. / len(dims)

    for i, dimName in enumerate(dims):
        progress = 10 + i * dimProgress

        cPos = list(sourceFolder.chunkPositions(dimName))
        for chunkProgress, (cx, cz) in enumProgress(cPos, progress, progress + dimProgress):
            yield chunkProgress, maxprogress, "Writing new and modified chunks"

            if reversionFolder and not reversionFolder.containsChunk(cx, cz, dimName):
                if destFolder.containsChunk(cx, cz, dimName):
                    reversionFolder.writeChunkBytes(cx, cz, dimName, destFolder.readChunkBytes(cx, cz, dimName))
                else:  # new chunk
                    reversionNode.deleteChunk(cx, cz, dimName)
            destFolder.writeChunkBytes(cx, cz, dimName, sourceFolder.readChunkBytes(cx, cz, dimName))

    # Remove deleted files
    for delProgress, path in enumProgress(sourceNode.deadFiles, 80, 10):
        yield delProgress, maxprogress, "Removing deleted files"

        if destFolder.containsFile(path):
            if reversionFolder and not reversionFolder.containsFile(path):
                reversionFolder.writeFile(path, destFolder.readFile(path))
            destFolder.deleteFile(path)

    # Write new and modified files

    files = list(sourceFolder.listAllFiles())
    for delProgress, path in enumProgress(files, 90, 10):
        yield delProgress, maxprogress, "Writing new and modified files"

        if reversionFolder and not reversionFolder.containsFile(path):
            if destFolder.containsFile(path):
                reversionFolder.writeFile(path, destFolder.readFile(path))
            else:  # new file
                reversionNode.deleteFile(path)
        destFolder.writeFile(path, sourceFolder.readFile(path))

    yield maxprogress, maxprogress, "Done"

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
        self.readonly = False
        self.differences = None
        self.invalid = False

    def __repr__(self):
        return "RevisionHistoryNode(readonly=%s, worldFolder=%s)" % (self.readonly, repr(
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
        dead = set()

        #
        # If a node is found in deadChunks:
        #   if found again in a later revision, it is alive
        #   if found again in this revision, it is still alive
        #   otherwise, it is dead
        #
        # `pos` contains all chunks found in this and later revisions.
        # Thus, `pos` should be subtracted from `deadChunks` before adding `deadChunks` to `dead`

        while node:
            nodepos = set(node.worldFolder.chunkPositions(dimName))
            pos.update(nodepos)

            nodedead = set((cx, cz) for cx, cz, deadDim in node.deadChunks if deadDim == dimName)
            nodedead.difference_update(pos)
            dead.update(nodedead)

            node = node.parentNode

        return pos - dead

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
            with open(self._deadChunksFile(), "w") as f:
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
        with open(self._deadChunksFile()) as f:
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
            if (cx, cz, dimName) in node.deadChunks:
                raise ChunkNotPresent((cx, cz), "Chunk was deleted")
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
            with open(self._deadFilesFile(), "w") as f:
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
        with open(self._deadFilesFile()) as f:
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
            if path in node.deadFiles:
                raise IOError("File not found (deleted)")
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
        List the contents of the given folder, reading all previous revisions.
        Ignores the REVINFO file.

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


        Returns the path of each file or folder in the given folder. All paths returned
        are relative to the world folder.

        :param path: Folder to list
        :type path: unicode
        :return: List of file/folder paths
        :rtype: Iterator[unicode]
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

