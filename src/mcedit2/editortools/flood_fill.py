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
from mcedit2.editortools.select import SelectionCursor
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Column, Row
from mceditlib import faces

log = logging.getLogger(__name__)

class FloodFillTool(EditorTool):
    name = "Flood Fill"
    iconName = "flood_fill"
    modifiesWorld = True

    def mousePress(self, event):
        pos = event.blockPosition
        if self.hoverCheckbox.isChecked():
            pos = pos + event.blockFace.vector

        command = FloodFillCommand(self.editorSession,
                                   pos,
                                   self.blockTypeWidget.block,
                                   self.indiscriminateCheckBox.isChecked(),
                                   self.getFloodDirs())
        self.editorSession.pushCommand(command)

    def mouseMove(self, event):
        self.mouseDrag(event)

    def mouseDrag(self, event):
        self.cursorNode.point = event.blockPosition
        self.cursorNode.face = event.blockFace

    def __init__(self, editorSession, *args, **kwargs):
        super(FloodFillTool, self).__init__(editorSession, *args, **kwargs)

        toolWidget = QtGui.QWidget()
        self.toolWidget = toolWidget

        self.cursorNode = SelectionCursor()

        self.floodXPosCheckbox = QtGui.QCheckBox(self.tr("X+"), checked=True)
        self.floodXNegCheckbox = QtGui.QCheckBox(self.tr("X-"), checked=True)
        self.floodYPosCheckbox = QtGui.QCheckBox(self.tr("Y+"), checked=True)
        self.floodYNegCheckbox = QtGui.QCheckBox(self.tr("Y-"), checked=True)
        self.floodZPosCheckbox = QtGui.QCheckBox(self.tr("Z+"), checked=True)
        self.floodZNegCheckbox = QtGui.QCheckBox(self.tr("Z-"), checked=True)
        
        floodDirsLayout = Column(Row(
            self.floodXPosCheckbox, 
            self.floodYPosCheckbox, 
            self.floodZPosCheckbox,
        ), Row(
            self.floodXNegCheckbox, 
            self.floodYNegCheckbox, 
            self.floodZNegCheckbox,
        ), )

        self.blockTypeWidget = BlockTypeButton()
        self.blockTypeWidget.block = self.editorSession.worldEditor.blocktypes["stone"]
        self.blockTypeWidget.editorSession = self.editorSession

        self.indiscriminateCheckBox = QtGui.QCheckBox("Ignore block meta")
        self.indiscriminateCheckBox.setChecked(False)

        self.hoverCheckbox = QtGui.QCheckBox("Hover")
        toolWidget.setLayout(Column(Row(QtGui.QLabel("Block:"),
                                        self.blockTypeWidget),
                                    Row(self.hoverCheckbox, self.indiscriminateCheckBox),
                                    floodDirsLayout,
                                    None))

    def getFloodDirs(self):
        return {f: c.isChecked() for f, c in
                ((faces.FaceXIncreasing, self.floodXPosCheckbox),
                 (faces.FaceYIncreasing, self.floodYPosCheckbox),
                 (faces.FaceZIncreasing, self.floodZPosCheckbox),
                 (faces.FaceXDecreasing, self.floodXNegCheckbox),
                 (faces.FaceYDecreasing, self.floodYNegCheckbox),
                 (faces.FaceZDecreasing, self.floodZNegCheckbox))}
    

class FloodFillCommand(SimplePerformCommand):
    def __init__(self, editorSession, point, blockInfo, indiscriminate, floodDirs):
        super(FloodFillCommand, self).__init__(editorSession)
        self.blockInfo = blockInfo
        self.point = point
        self.indiscriminate = indiscriminate
        self.floodDirs = floodDirs

    def perform(self):
        dim = self.editorSession.currentDimension
        point = self.point

        doomedBlock = dim.getBlockID(*point)
        doomedBlockData = dim.getBlockData(*point)
        checkData = (doomedBlock not in (8, 9, 10, 11))  # always ignore data when replacing water/lava xxx forge fluids?
        indiscriminate = self.indiscriminate
        floodDirs = self.floodDirs

        log.info("Flood fill: replacing %s with %s", (doomedBlock, doomedBlockData), self.blockInfo)

        if doomedBlock == self.blockInfo.ID:
            if indiscriminate or doomedBlockData == self.blockInfo.meta:
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
                    if not floodDirs[face]:
                        continue
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
