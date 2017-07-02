"""
    blocks
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtCore, QtGui

from mcedit2.command import SimpleRevisionCommand
from mcedit2.ui.find_replace_blocks import Ui_FindReplaceBlocks
from mcedit2.util.resources import resourcePath
from mcedit2.util.showprogress import showProgress
from mcedit2.widgets.blockpicker import BlockTypeButton
from mcedit2.widgets.layout import Row

log = logging.getLogger(__name__)


class FindReplaceBlocksWidget(QtGui.QWidget, Ui_FindReplaceBlocks):
    def __init__(self):
        super(FindReplaceBlocksWidget, self).__init__()
        self.setupUi(self)


class FindReplaceBlocks(QtCore.QObject):
    def __init__(self, editorSession, dialog, *args, **kwargs):
        super(FindReplaceBlocks, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.dialog = dialog

        self.widget = FindReplaceBlocksWidget()

        self.widget.replacementList.editorSession = editorSession
        self.widget.blocksReplaceButton.clicked.connect(self.doReplace)
        self.widget.blocksReplaceButton.setEnabled(not self.editorSession.readonly)

    def doReplace(self):
        replacements = self.widget.replacementList.getReplacements()
        command = SimpleRevisionCommand(self.editorSession, "Replace")
        if self.widget.replaceBlocksInSelectionCheckbox.isChecked():
            selection = self.editorSession.currentSelection
        else:
            selection = self.editorSession.currentDimension.bounds
        with command.begin():
            task = self.editorSession.currentDimension.fillBlocksIter(selection, replacements)
            showProgress("Replacing...", task)
        self.editorSession.pushCommand(command)