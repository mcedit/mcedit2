"""
    fill
"""
from __future__ import absolute_import, division, print_function
from PySide import QtGui
import logging
from mcedit2.command import SimpleRevisionCommand
from mcedit2.ui.fill import Ui_fillDialog
from mcedit2.util.showprogress import showProgress

log = logging.getLogger(__name__)

class FillCommandWidget(QtGui.QDialog, Ui_fillDialog):
    def __init__(self, editorSession):
        super(FillCommandWidget, self).__init__()
        self.setupUi(self)
        self.adjustSize()
        self.blockTypeInput.editorSession = editorSession
        self.blockTypeInput.block = "minecraft:stone"

# Cache the FillCommandWidget on the session. Gross.
def getFillWidget(editorSession):
    widget = getattr(editorSession, '_fillWidget', None)
    
    if widget is None:
        widget = editorSession._fillWidget = FillCommandWidget(editorSession)
    return widget


def fillCommand(editorSession):
    """

    :type editorSession: mcedit2.editorsession.EditorSession
    """
    box = editorSession.currentSelection
    if box is None or box.volume == 0:
        return

    widget = getFillWidget(editorSession)
    if widget.exec_():
        command = SimpleRevisionCommand(editorSession, "Fill")
        with command.begin():
            task = editorSession.currentDimension.fillBlocksIter(box, widget.blockTypeInput.block)
            showProgress("Filling...", task)
        editorSession.pushCommand(command)
