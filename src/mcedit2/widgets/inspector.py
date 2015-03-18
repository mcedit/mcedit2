"""
    inspector
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui
from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)


class InspectorWidget(QtGui.QWidget):
    def __init__(self):
        super(InspectorWidget, self).__init__()
        load_ui("inspector.ui", baseinstance=self)
        # self.nbtEditor.editorSession = self.editorSession
        # self.nbtEditor.editMade.connect(self.editWasMade)
    #
    # def editWasMade(self):
    #     if self.currentEntity and self.currentEntity.chunk:
    #         self.currentEntity.chunk.dirty = True
