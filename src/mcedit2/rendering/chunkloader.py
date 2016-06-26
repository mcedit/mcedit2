"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from collections import deque, defaultdict
import logging
import time
import weakref

from PySide import QtCore
from mcedit2.util import profiler

from mcedit2.widgets.infopanel import InfoPanel
from mceditlib.exceptions import LevelFormatError

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class ChunkLoaderInfo(InfoPanel):
    def __init__(self):
        InfoPanel.__init__(self,
                           ['cps', 'client'],
                           ['chunkCompleted'],
                           )

    @property
    def client(self):
        if len(self.object.clients):
            return "Client: %s" % (self.object.clients[0])

class IChunkLoaderClient(object):
    def requestChunk(self):
        """
        Called on the first client in the clients list. When the first client returns None,
        is called on the second client, and so on.

        Return the coordinates of the chunk requested by the client. Each
        call to `requestChunk` should return a different set of coordinates.

        Return None to request no chunks.

        Returns
        -------

        chunkPos : (int, int) | None
        """
        pass

    def wantsChunk(self, (cx, cz)):
        """
        Called on each client after a chunk is requested, but before it is loaded.

        Return False to skip loading the chunk at the given position.
        If all clients return False, the chunk is not loaded.

        Returns
        -------

        wantsChunk : bool
        """

    def recieveChunk(self, chunk):
        """
        Called on each client after a chunk is loaded. Allows the chunk to be processed.

        May be implemented as a generator function or a function that returns an iterable - if
        `recieveChunk` returns an iterable, it will be exhausted. This allows potentially
        long-running operations on a single chunk to be split over multiple calls to
        ChunkLoader.next()

        Parameters
        ----------

        chunk : WorldEditorChunk
            The chunk returned by level.getChunk()

        Returns
        -------

        worker : Iterable | None
        """

    def chunkNotLoaded(self, (cx, cz), exc):
        """
        Called when a chunk fails to load due to an exception.

        Notifies each client of the chunk's position and the thrown exception.

        Parameters
        ----------
        (cx, cz) : (int, int)
            Position of the failed chunk.

        exc : The Exception object thrown by the world, usually IOError or LevelFormatError
        """

    def chunkNotPresent(self, (cx, cz)):
        """
        Called when a chunk fails to load because it is not present in the world.

        Notifies each client of the chunk's position.

        Parameters
        ----------
        (cx, cz) : (int, int)
            chunk position
        """

    def chunkInvalid(self, (cx, cz), deleted):
        """
        Called when the revision changes indicate a chunk is modified or deleted.

        Parameters
        ----------
        deleted : bool
            True if the chunk was deleted.

        Returns
        -------
        None

        """

class ChunkLoader(QtCore.QObject):
    chunkCompleted = QtCore.Signal()
    allChunksDone = QtCore.Signal()

    def __init__(self, dimension, *args, **kwargs):
        """
        A ChunkLoader manages a list of clients who want to access chunks from `dimension`.
        Each client may request a chunk to load, receive chunks as they are loaded,
         be notified of chunks loaded by any client's request, and be notified when
         a chunk is modified. See the IChunkLoaderClient class for details.

        ChunkLoader is intended for clients who only need to view, display, or read chunks, such as WorldViews.
        For editing chunks, use a subclass of Operation and/or use ComposeOperations to combine them.

        To use a ChunkLoader, create a ChunkLoader instance, add one or more IChunkLoaderClient-compatible
        objects using `addClient`, and then repeatedly call `next` (or simply iterate the ChunkLoader)
        to load and process chunks. `StopIteration` will be raised when all clients return None when
        requestChunk is called.

        Parameters
        ----------

        dimension : WorldEditorDimension
            The dimension to load chunks from.
        """
        QtCore.QObject.__init__(self, *args, **kwargs)

        self.clients = []
        self.dimension = dimension
        self.chunkWorker = None
        self.chunkSamples = deque(maxlen=30)
        self.invalidChunks = defaultdict(set)
        for i in range(self.chunkSamples.maxlen):
            self.chunkSamples.append(0.0)

        log.debug("ChunkLoader created for %r", dimension)

    @property
    def cps(self):
        chunkSamples = self.chunkSamples
        duration = sum(chunkSamples)
        if duration and len(chunkSamples):
            chunkTime = duration / len(chunkSamples)
            cps = 1.0 / chunkTime
            return cps
        else:
            return 0.0

    def addClient(self, client, index=-1):
        """
        Parameters
        ----------

        client : IChunkLoaderClient
        """
        self.clients.insert(index, weakref.ref(client))
        log.info("Added: client %s",  client)

    def removeClient(self, client):
        """
        Parameters
        ----------

        client : IChunkLoaderClient
        """
        try:
            self.clients[:] = [c for c in self.clients if c() is not client]
            log.info("Removed: client %s",  client)
        except ValueError:
            pass

    def removeAllClients(self):
        self.clients[:] = []

    def __iter__(self):
        return self

    def next(self):
        if self.chunkWorker is None:
            self.chunkWorker = self._loadChunks()
        try:
            return self.chunkWorker.next()
        except StopIteration:
            self.chunkWorker = None
            raise

    def revisionDidChange(self, revisionChanges):
        dimName = self.dimension.dimName
        for cx, cz in revisionChanges.chunks[dimName]:
            self.invalidChunks[dimName].add((cx, cz))

    def _loadChunks(self):
        """
        Generator function, returns an iterator. On each iteration, requests a chunk position from a client, then loads
        that chunk and delivers it to each client. Returns (raises StopIteration) when the client list is empty or when
        no client requests a chunk.

        Used to implement ChunkLoader.next
        """
        log.debug("Starting chunk loader")
        while True:
            if 0 == len(self.clients):
                log.debug("ChunkLoader: No clients!")
                return

            invalidChunks = self.invalidChunks.pop(self.dimension.dimName, [])
            for c in invalidChunks:
                deleted = not self.dimension.containsChunk(*c)
                for ref in self.clients:
                    client = ref()
                    if client:
                        client.chunkInvalid(c, deleted)

            for ref in self.clients:
                client = ref()
                if client is None:
                    continue
                c = client.requestChunk()
                if c is not None:
                    log.debug("Client %s: %s", client, c)
                    for _ in self._loadChunk(c):
                        yield
                    break
                else:
                    log.debug("Client %s: No requests", client)
            else:
                log.debug("No requests.")
                self.allChunksDone.emit()
                return
            yield

    def _loadChunk(self, cPos):

        if not self.dimension.containsChunk(*cPos):
            for ref in self.clients:
                client = ref()
                if client is None:
                    continue
                if hasattr(client, 'chunkNotPresent'):
                    client.chunkNotPresent(cPos)
            return

        if not any([ref().wantsChunk(cPos)
                    for ref in self.clients
                    if ref() is not None]):
            log.debug("Chunk %s is unwanted.", cPos)
            return

        chunkStartTime = time.time()
        try:
            with profiler.context("getChunk"):
                chunk = self.dimension.getChunk(*cPos)
        except (EnvironmentError, LevelFormatError) as e:
            #log.exception(e)
            log.debug("Chunk %s had an error: %r!", cPos, e)
            for ref in self.clients:
                client = ref()
                if client is None:
                    continue
                if hasattr(client, 'chunkNotLoaded'):
                    client.chunkNotLoaded(cPos, e)
        else:
            for ref in self.clients:
                client = ref()
                if client is None:
                    continue
                log.debug("Chunk %s -> %s", cPos, client)
                iterator = profiler.iterate(client.recieveChunk(chunk), "Client %s" % type(client).__name__)

                if iterator:
                    for _ in iterator:
                        yield

        self.chunkSamples.append(time.time() - chunkStartTime)
        self.chunkCompleted.emit()

    def discardChunks(self, chunks):
        for cx, cz in chunks:
            self.discardChunk(cx, cz)

    def discardChunk(self, cx, cz):
        for ref in self.clients:
            client = ref()
            if client is not None:
                client.discardChunk(cx, cz)


