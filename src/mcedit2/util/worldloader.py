"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import contextlib
import logging
import weakref
from PySide import QtCore
import time
from mcedit2.util import profiler

log = logging.getLogger(__name__)

_loaderTimers = []

class LoaderTimer(QtCore.QTimer):
    def __init__(self, *args, **kwargs):
        super(LoaderTimer, self).__init__(*args, **kwargs)
        _loaderTimers.append(weakref.ref(self))

    @classmethod
    @contextlib.contextmanager
    def stopCtx(cls):
        cls.stopAll()
        yield
        cls.startAll()

    @staticmethod
    def stopAll():
        for ref in _loaderTimers:
            timer = ref()
            if timer:
                timer.stop()
        _loaderTimers[:] = [ref for ref in _loaderTimers if ref() is not None]

    @staticmethod
    def startAll():
        for ref in _loaderTimers:
            timer = ref()
            if timer:
                timer.start()
        _loaderTimers[:] = [ref for ref in _loaderTimers if ref() is not None]


class WorldLoader(object):
    def __init__(self, scene, chunkPositions=None):
        """
        A timer for loading a world separately from the main ChunkLoader. If
        chunkPositions is given, loads only those chunks, otherwise loads every
        chunk in the world.

        :type scene: WorldScene
        """
        self.scene = scene
        self.timer = LoaderTimer(timeout=self.loadChunk)
        self.timer.setInterval(0)
        self.chunkPositions = chunkPositions
        self.chunkIter = self.work()

    def startLoader(self, duration=0.12):
        self.timer.start()
        start = time.time()
        while time.time() < start + duration:
            self.loadChunk()

    def loadChunk(self):
        try:
            self.chunkIter.next()
        except StopIteration:
            self.timer.stop()

    @profiler.iterator
    def work(self):
        yield
        if self.chunkPositions is not None:
            chunkPositions = self.chunkPositions
        else:
            chunkPositions = self.scene.dimension.chunkPositions()
        for cPos in chunkPositions:
            if self.scene.dimension.containsChunk(*cPos):
                for _ in self.scene.workOnChunk(self.scene.dimension.getChunk(*cPos)):
                    yield _
