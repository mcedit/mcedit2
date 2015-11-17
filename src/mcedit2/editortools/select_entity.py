"""
    select
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.editortools import EditorTool
from mcedit2.util.bresenham import bresenham
from mcedit2.util.load_ui import load_ui


log = logging.getLogger(__name__)


class SelectEntityCommand(QtGui.QUndoCommand):
    def __init__(self, tool, ray, *args, **kwargs):
        QtGui.QUndoCommand.__init__(self, *args, **kwargs)
        self.setText("Inspect Entity")
        self.ray = ray
        self.tool = tool

    def undo(self):
        self.tool.setSelectionRay(self.ray)

    def redo(self):
        self.previousRay = self.tool.selectionRay
        self.tool.setSelectionRay(self.ray)


class SelectEntityTool(EditorTool):
    name = "Inspect Entity"
    iconName = "edit_entity"
    selectionRay = None
    currentEntity = None
    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(SelectEntityTool, self).__init__(editorSession, *args, **kwargs)

        self.toolWidget = load_ui("editortools/select_entity.ui")
        self.toolWidget.tableWidget.cellClicked.connect(self.cellWasClicked)
        self.toolWidget.tableWidget.setColumnCount(2)
        self.toolWidget.tableWidget.setHorizontalHeaderLabels(["ID", "Position"])
        self.selectedEntities = []

    def mousePress(self, event):
        command = SelectEntityCommand(self, event.ray)
        self.editorSession.pushCommand(command)

    def setSelectionRay(self, ray):
        self.selectionRay = ray
        editorSession = self.editorSession
        entities = entitiesOnRay(editorSession.currentDimension, ray)

        tableWidget = self.toolWidget.tableWidget
        tableWidget.clear()
        self.selectedEntities = list(entities)
        if len(self.selectedEntities):
            tableWidget.setRowCount(len(self.selectedEntities))
            for row, e in enumerate(self.selectedEntities):
                pos = e.Position
                tableWidget.setItem(row, 0, QtGui.QTableWidgetItem(e.id))
                tableWidget.setItem(row, 1, QtGui.QTableWidgetItem("%0.2f, %0.2f, %0.2f" % (pos[0], pos[1], pos[2])))

            self.cellWasClicked(0, 0)

    def cellWasClicked(self, row, column):
        if len(self.selectedEntities):
            self.currentEntity = self.selectedEntities[row]
            self.editorSession.inspectEntity(self.currentEntity)
        else:
            self.editorSession.inspectEntity(None)

def entitiesOnRay(dimension, ray, rayWidth=0.75, maxDistance = 1000):
    pos, vec = ray

    endpos = pos + vec.normalize() * maxDistance

    ray_dir = vec.normalize()

    # Visit each chunk along the ray
    def chunks(pos, endpos):
        last_cpos = None
        for x, y, z in bresenham(pos, endpos):
            cpos = int(x) >> 4, int(z) >> 4
            if cpos != last_cpos:
                yield cpos
                last_cpos = cpos

    class RaySelection(object):
        positions = list(chunks(pos, endpos))
        def chunkPositions(self):
            return self.positions

        def __contains__(self, position):
            evec = (position + (0.5, 0.5, 0.5)) - pos
            dist = ray_dir.cross(evec).length()
            return dist < rayWidth

    sr = RaySelection()

    return dimension.getEntities(sr)













