"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import weakref
from PySide import QtCore
from mcedit2.util import profiler

log = logging.getLogger(__name__)

_loaderTimers = []

class LoaderTimer(QtCore.QTimer):
    def __init__(self, *args, **kwargs):
        super(LoaderTimer, self).__init__(*args, **kwargs)
        _loaderTimers.append(weakref.ref(self))

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
    def __init__(self, scene):
        """
        A timer for loading a world separately from the main ChunkLoader. Loads every chunk in the world.

        :type scene: WorldScene
        """
        self.scene = scene
        self.timer = LoaderTimer(timeout=self.loadChunk)
        self.timer.setInterval(0)
        self.chunkIter = self.work()

    def loadChunk(self):
        try:
            self.chunkIter.next()
        except StopIteration:
            self.timer.stop()

    @profiler.iterator
    def work(self):
        yield
        for cPos in self.scene.dimension.chunkPositions():
            for _ in self.scene.workOnChunk(self.scene.dimension.getChunk(*cPos)):
                yield _
