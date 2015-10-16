"""
    time_selectionrender
"""
from __future__ import absolute_import, division, print_function
import logging
import timeit
from PySide import QtGui
from mcedit2.rendering.selection import SelectionScene
from mceditlib.selection import ShapeFuncSelection, SphereShape
from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

def main():
    app = QtGui.QApplication([])
    selection = ShapeFuncSelection(BoundingBox((0, 0, 0), (63, 63, 63)), SphereShape)
    scene = SelectionScene()
    def timeBuild():
        scene.selection = selection
        for _ in scene.loadSections():
            pass

    duration = timeit.timeit(timeBuild, number=1) * 1000
    print("timeBuild x1 in %0.2fms (%0.3fms per chunk)" % (duration, duration / selection.chunkCount))


if __name__ == '__main__':
    main()
