"""
    count_blocks
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

from mcedit2.plugins import registerPluginCommand, CommandPlugin

log = logging.getLogger(__name__)


@registerPluginCommand
class CountBlocksPlugin(CommandPlugin):
    def __init__(self, editorSession):
        super(CountBlocksPlugin, self).__init__(editorSession)

        self.addMenuItem(self.tr("Count Blocks") , self.countBlocks)

    def countBlocks(self):
        selection = self.editorSession.currentSelection
        if selection is None:
            QtGui.QMessageBox.warning(
                None, self.tr("No selection"),
                self.tr("You must select an area before using this command"))

        else:
            QtGui.QMessageBox.information(
                None, self.tr("Count Blocks"),
                self.tr("Selection is present. TODO: Count some blocks.")
            )