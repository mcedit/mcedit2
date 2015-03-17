"""
    flood_fill
"""
from __future__ import absolute_import, division, print_function
from PySide import QtGui
import logging
import collections
import time
from mcedit2.editortools import EditorTool
from mcedit2.command import SimplePerformCommand
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Column, Row
from mceditlib import faces

log = logging.getLogger(__name__)

class FloodFillTool(EditorTool):
    name = "Flood Fill"
    iconName = "flood_fill"

    def mousePress(self, event):
        command = FloodFillCommand(self.editorSession, event.blockPosition, self.blockTypeWidget.block)
        self.editorSession.pushCommand(command)

    def __init__(self, editorSession, *args, **kwargs):
        super(FloodFillTool, self).__init__(editorSession, *args, **kwargs)

        toolWidget = QtGui.QWidget()
        self.toolWidget = toolWidget

        self.blockTypeWidget = BlockTypeButton()
        self.blockTypeWidget.block = self.editorSession.worldEditor.blocktypes["stone"]
        self.blockTypeWidget.textureAtlas = self.editorSession.textureAtlas

        toolWidget.setLayout(Column(Row(QtGui.QLabel("Block:"),
                                        self.blockTypeWidget),
                                    None))



class FloodFillCommand(SimplePerformCommand):
    def __init__(self, editorSession, point, blockInfo):
        super(FloodFillCommand, self).__init__(editorSession)
        self.blockInfo = blockInfo
        self.point = point
        self.indiscriminate = False  # xxx

    def perform(self):

        dim = self.editorSession.currentDimension
        point = self.point

        doomedBlock = dim.getBlockID(*point)
        doomedBlockData = dim.getBlockData(*point)
        checkData = (doomedBlock not in (8, 9, 10, 11))
        indiscriminate = self.indiscriminate

        if doomedBlock == self.blockInfo.ID:
            return
        if indiscriminate:
            checkData = False
            if doomedBlock == 2:  # grass
                doomedBlock = 3  # dirt

        x, y, z = point
        dim.setBlockID(x, y, z, self.blockInfo.ID)
        dim.setBlockData(x, y, z, self.blockInfo.meta)

        def processCoords(coords):
            newcoords = collections.deque()

            for (x, y, z) in coords:
                for face, offsets in faces.faceDirections:
                    dx, dy, dz = offsets
                    p = (x + dx, y + dy, z + dz)

                    nx, ny, nz = p
                    b = dim.getBlockID(nx, ny, nz)
                    if indiscriminate:
                        if b == 2:
                            b = 3
                    if b == doomedBlock:
                        if checkData:
                            if dim.getBlockData(nx, ny, nz) != doomedBlockData:
                                continue

                        dim.setBlockID(nx, ny, nz, self.blockInfo.ID)
                        dim.setBlockData(nx, ny, nz, self.blockInfo.meta)
                        newcoords.append(p)

            return newcoords

        def spread(coords):
            start = time.time()
            num = 0
            while len(coords):
                num += len(coords)
                coords = processCoords(coords)
                d = time.time() - start
                progress = "Did {0} coords in {1}".format(num, d)
                log.debug(progress)
                yield progress


        showProgress("Flood fill...", spread([point]), cancel=True)
