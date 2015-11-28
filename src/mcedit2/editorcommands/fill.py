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

_fillWidget = None

# xxxx why?
def getFillWidget(editorSession):
    global _fillWidget
    if _fillWidget is None:
        _fillWidget = FillCommandWidget(editorSession)
    _fillWidget.editorSession = editorSession
    return _fillWidget


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
