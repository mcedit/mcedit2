"""
    select
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import itertools
import logging

from PySide import QtGui
from PySide.QtCore import Qt

from mcedit2.editortools import EditorTool
from mcedit2.widgets.nbttree.nbttreemodel import NBTTreeModel, NBTFilterProxyModel
from mcedit2.util.bresenham import bresenham
from mcedit2.util.load_ui import load_ui


log = logging.getLogger(__name__)


class SelectEntityCommand(QtGui.QUndoCommand):
    def __init__(self, tool, ray, *args, **kwargs):
        QtGui.QUndoCommand.__init__(self, *args, **kwargs)
        self.setText("Select Entity")
        self.ray = ray
        self.tool = tool

    def undo(self):
        self.tool.setSelectionRay(self.ray)

    def redo(self):
        self.previousRay = self.tool.selectionRay
        self.tool.setSelectionRay(self.ray)


class EntityTool(EditorTool):
    name = "Edit Entity"
    iconName = "edit_entity"
    selectionRay = None

    def __init__(self, editorSession, *args, **kwargs):
        """
        :type editorSession: EditorSession
        """
        super(EntityTool, self).__init__(editorSession, *args, **kwargs)
        self.createToolWidget()

    def createToolWidget(self):
        self.toolWidget = load_ui("editortools/select_entity.ui")
        self.toolWidget.entityListBox.currentIndexChanged.connect(self.setSelectedEntity)

    def mousePress(self, event):
        command = SelectEntityCommand(self, event.ray)
        self.editorSession.pushCommand(command)

    def setSelectionRay(self, ray):
        self.selectionRay = ray
        editorSession = self.editorSession
        entities = entitiesOnRay(editorSession.currentDimension, ray)

        entityListBox = self.toolWidget.entityListBox
        entityListBox.clear()
        self.selectedEntities = list(entities)
        if len(self.selectedEntities):
            for e in self.selectedEntities:
                pos = e.Position
                entityListBox.addItem("%s at %0.2f, %0.2f, %0.2f" % (e.id, pos[0], pos[1], pos[2]), None)

            self.setSelectedEntity(0)

    def setSelectedEntity(self, index):
        if len(self.selectedEntities):
            model = NBTTreeModel(self.selectedEntities[index].raw_tag())
            proxyModel = NBTFilterProxyModel(self)
            proxyModel.setSourceModel(model)
            proxyModel.setDynamicSortFilter(True)

            self.toolWidget.treeView.setModel(proxyModel)
            self.toolWidget.treeView.sortByColumn(0, Qt.AscendingOrder)
        else:
            self.toolWidget.treeView.setModel(None)


def entitiesOnRay(dimension, ray, rayWidth=2.0, maxDistance = 1000):
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
            evec = position - pos
            dist = ray_dir.cross(evec).length()
            return dist < rayWidth


    sr = RaySelection()

    return itertools.chain(dimension.getEntities(sr), dimension.getTileEntities(sr))













