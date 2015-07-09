"""
    error_dialog
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import traceback
import sys
import platform

from PySide import QtGui
from mcedit2.util import qglcontext

from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)

def showErrorDialog(text, tb, fatal):
    dialog = ErrorDialog(text, tb, fatal)
    dialog.exec_()

class ErrorDialog(QtGui.QDialog):
    """
    A dialog for displaying an error traceback when something goes wrong.

    Used to report compile and run errors for plugin modules and classes, and might be
    used to report errors in MCEdit itself during signal or event handlers.
    """
    def __init__(self, text, exc_info, fatal):
        super(ErrorDialog, self).__init__()
        load_ui("error_dialog.ui", baseinstance=self)

        exc_type, exc_value, exc_tb = exc_info

        self.errorDescriptionLabel.setText(text)
        tbText = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

        contextInfo = qglcontext.getContextInfo() or ""

        from mcedit2 import __version__
        tbText = "MCEdit version: %s\n" \
                 "Python version: %s\n" \
                 "Platform: %s\n" \
                 "System version: %s\n" \
                 "Processor: %s\n" \
                 "\n" \
                 "%s\n" \
                 "------\n\n" \
                 "%s\n\n" \
                 "%s" % (__version__, sys.version, sys.platform,
                         platform.platform(), platform.processor(),
                         contextInfo, text, tbText)
        self.tracebackView.setText(tbText)

        self.restartMCEditLabel.setVisible(fatal)

