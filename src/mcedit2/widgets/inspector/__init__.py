"""
    inspector
"""
from __future__ import absolute_import, division, print_function
import logging
import traceback

from PySide import QtGui

from mcedit2.widgets.inspector.tileentities.chest import ChestEditorWidget, DispenserEditorWidget, HopperEditorWidget
from mcedit2.util.load_ui import load_ui
from mcedit2.widgets.inspector.tileentities.command import CommandBlockEditorWidget

log = logging.getLogger(__name__)

tileEntityEditorClasses = {
}

def registerBlockInspectorWidget(widgetClass):
    ID = widgetClass.tileEntityID
    tileEntityEditorClasses[ID] = widgetClass

def unregisterBlockInspectorWidget(widgetClass):
    dead = [k for k, v in tileEntityEditorClasses.iteritems() if v == widgetClass]
    for k in dead:
        tileEntityEditorClasses.pop(k, None)

registerBlockInspectorWidget(ChestEditorWidget)
registerBlockInspectorWidget(DispenserEditorWidget)
registerBlockInspectorWidget(HopperEditorWidget)

class InspectorWidget(QtGui.QWidget):
    def __init__(self, editorSession):
        """

        :param editorSession:
        :type editorSession: mcedit2.editorsession.EditorSession
        :return:
        :rtype:
        """
        super(InspectorWidget, self).__init__()
        load_ui("inspector.ui", baseinstance=self)
        self.editorSession = editorSession

        self.blockNBTEditor.editorSession = self.editorSession

        self.entityNBTEditor.editorSession = self.editorSession

        self.blockEditorWidget = None

        self.tileEntity = None
        self.entity = None

    def inspectBlock(self, pos):
        self.entity = None

        self.stackedWidget.setCurrentWidget(self.pageInspectBlock)
        x, y, z = pos
        self.blockXLabel.setText(str(x))
        self.blockYLabel.setText(str(y))
        self.blockZLabel.setText(str(z))

        if self.blockEditorWidget:
            self.blockTabWidget.removeTab(0)
            self.blockEditorWidget = None

        self.tileEntity = self.editorSession.currentDimension.getTileEntity(pos)

        if self.tileEntity is not None:
            editorClass = tileEntityEditorClasses.get(self.tileEntity.id)
            if editorClass is not None:
                try:
                    self.blockEditorWidget = editorClass(self.editorSession, self.tileEntity)
                except Exception as e:
                    self.blockEditorWidget = QtGui.QLabel("Failed to load TileEntity editor:\n%s\n%s" % (
                        e,
                        traceback.format_exc(),
                                                                                                        ))
                    self.blockEditorWidget.displayName = "Error"

                displayName = getattr(self.blockEditorWidget, 'displayName', self.tileEntity.id)

                self.blockTabWidget.insertTab(0, self.blockEditorWidget, displayName)
                self.blockTabWidget.setCurrentIndex(0)

            self.blockNBTEditor.setRootTagRef(self.tileEntity)
        else:
            self.blockNBTEditor.setRootTagRef(None)

        self.removeTileEntityButton.setEnabled(self.tileEntity is not None)

    def inspectEntity(self, entity):
        self.tileEntity = None

        self.entity = entity
        self.stackedWidget.setCurrentWidget(self.pageInspectEntity)
        self.entityIDLabel.setText(entity.id)
        try:
            self.entityUUIDLabel.setText(str(entity.UUID))
        except KeyError:
            self.entityUUIDLabel.setText(self.tr("(Not set)"))

        x, y, z = entity.Position
        self.entityXLabel.setText("%0.2f" % x)
        self.entityYLabel.setText("%0.2f" % y)
        self.entityZLabel.setText("%0.2f" % z)

        self.entityNBTEditor.setRootTagRef(entity)
