"""
    command_text
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtCore, QtGui

from mcedit2.ui.find_replace_commands import Ui_findCommandsWidget

log = logging.getLogger(__name__)


class FindReplaceCommandWidget(QtGui.QWidget, Ui_findCommandsWidget):
    def __init__(self):
        super(FindReplaceCommandWidget, self).__init__()
        self.setupUi(self)


class FindReplaceCommandText(QtCore.QObject):
    def __init__(self, editorSession, dialog, *args, **kwargs):
        super(FindReplaceCommandText, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.dialog = dialog
        self.widget = FindReplaceCommandWidget()
