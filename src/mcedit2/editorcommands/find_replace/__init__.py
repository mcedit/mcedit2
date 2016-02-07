"""
    replace
"""
from __future__ import absolute_import, division, print_function

import logging

from PySide import QtGui

from mcedit2.editorcommands.find_replace.command_text import FindReplaceCommandText
from mcedit2.editorcommands.find_replace.replace_blocks import FindReplaceBlocks
from mcedit2.editorcommands.find_replace.nbt import FindReplaceNBT
from mcedit2.ui.find_replace import Ui_findReplaceDialog
from mcedit2.util.load_ui import load_ui
from mcedit2.widgets.layout import Column

log = logging.getLogger(__name__)


class FindReplaceDialog(QtGui.QDialog, Ui_findReplaceDialog):
    def __init__(self, editorSession, *args, **kwargs):
        super(FindReplaceDialog, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.blocktypes = editorSession.worldEditor.blocktypes
        self.setupUi(self)

        self.findReplaceBlocks = FindReplaceBlocks(editorSession, self)
        self.replaceBlocksTab.setLayout(Column(self.findReplaceBlocks.widget, margin=0))

        self.findReplaceCommandText = FindReplaceCommandText(editorSession, self)
        self.commandBlocksTab.setLayout(Column(self.findReplaceCommandText.widget, margin=0))

        self.findReplaceNBT = FindReplaceNBT(editorSession, self)
        self.nbtTab.setLayout(Column(self.findReplaceNBT, margin=0))

        self.resultsWidgets = [
            # self.findReplaceBlocks.resultsDockWidget,
            self.findReplaceNBT.resultsDockWidget,
        ]

    def execFindBlocks(self):
        self.execTab(0)

    def execFindReplaceBlocks(self):
        self.execTab(1)

    def execFindReplaceItems(self):
        self.execTab(2)

    def execFindReplaceCommands(self):
        self.execTab(3)

    def execFindReplaceNBT(self):
        self.execTab(4)

    def execTab(self, tabIndex):
        self.tabWidget.setCurrentIndex(tabIndex)
        self.exec_()

    def exec_(self):
        self.findReplaceNBT.dialogOpened()
        # self.findReplaceBlocks.dialogOpened()
        super(FindReplaceDialog, self).exec_()



