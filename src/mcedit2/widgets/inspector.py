"""
    inspector
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui
from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)


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
        self.blockNBTEditor.editMade.connect(self.editWasMade)

        self.entityNBTEditor.editorSession = self.editorSession
        self.entityNBTEditor.editMade.connect(self.editWasMade)

        self.tileEntity = None
        self.entity = None


    def editWasMade(self):
        if self.currentEntity and self.currentEntity.chunk:
            self.currentEntity.chunk.dirty = True

    def inspectBlock(self, pos):
        self.stackedWidget.setCurrentWidget(self.pageInspectBlock)
        x, y, z = pos
        self.blockXLabel.setText(str(x))
        self.blockYLabel.setText(str(y))
        self.blockZLabel.setText(str(z))
        self.tileEntity = self.editorSession.currentDimension.getTileEntity(pos)
        if self.tileEntity is not None:
            self.blockNBTEditor.setRootTag(self.tileEntity.raw_tag())
        else:
            self.blockNBTEditor.setRootTag(None)
        self.removeTileEntityButton.setEnabled(self.tileEntity is not None)

    def inspectEntity(self, entity):
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

        self.entityNBTEditor.setRootTag(entity.raw_tag())
