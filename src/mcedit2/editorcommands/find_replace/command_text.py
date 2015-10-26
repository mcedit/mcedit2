"""
    command_text
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtCore

from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)


class FindReplaceCommandText(QtCore.QObject):
    def __init__(self, editorSession, dialog, *args, **kwargs):
        super(FindReplaceCommandText, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.dialog = dialog

        self.widget = load_ui("find_replace_commands.ui")
