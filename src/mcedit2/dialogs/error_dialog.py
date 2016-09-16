"""
    error_dialog
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import traceback
import sys
import platform

from PySide import QtGui, QtCore

from mcedit2.ui.dialogs.error_dialog import Ui_errorDialog
from mcedit2.util import qglcontext
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.util.showprogress import MCEProgressDialog

log = logging.getLogger(__name__)

_errorShown = False


def showErrorDialog(text, tb=None, fatal=True):
    global _errorShown
    if tb is None:
        tb = sys.exc_info()
    _errorShown = True
    grabber = QtGui.QWidget.mouseGrabber()
    if grabber:
        grabber.releaseMouse()

        
    dialog = ErrorDialog(text, tb, fatal)
    dialog.exec_()
    _errorShown = False


class ErrorDialog(QtGui.QDialog, Ui_errorDialog):
    """
    A dialog for displaying an error traceback when something goes wrong.

    Used to report compile and run errors for plugin modules and classes, and
    to report errors in MCEdit itself during signal or event handlers.
    """
    def __init__(self, text, exc_info, fatal):
        super(ErrorDialog, self).__init__()
        self.setupUi(self)
        self.setModal(True)

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
        self.errorText = tbText

        self.tracebackView.setText(tbText)

        self.restartMCEditLabel.setVisible(fatal)

        self.restartMCEditButton.setVisible(fatal)
        self.restartMCEditButton.clicked.connect(self.restartMCEdit)

        self.quitMCEditButton.setVisible(fatal)
        self.quitMCEditButton.clicked.connect(self.quitMCEdit)

        try:
            import Pastebin
        except ImportError:
            self.copyToPastebinButton.setVisible(False)
        else:
            self.copyToPastebinButton.setVisible(True)
            self.copyToPastebinButton.clicked.connect(self.copyToPastebin)

        self.pastebinURLBox.setVisible(False)

    def show(self, *args, **kwargs):
        super(ErrorDialog, self).show(*args, **kwargs)
        centerWidgetInScreen(self)

    def copyToPastebin(self):
        import Pastebin
        api_dev_key = '0a9ae46e71b44c10184212e4674912c5'
        url = None

        progressText = self.tr("Uploading to pastebin...")
        dialog = MCEProgressDialog(progressText,
                                         None, 0, 0, self)
        dialog.setLabelText(progressText)
        dialog.setWindowTitle(progressText)
        dialog.setStatusTip(progressText)

        dialog.show()
        QtGui.qApp.processEvents()
        try:
            url = Pastebin.paste(api_dev_key, self.errorText,
                                 paste_expire_date="1M")
        except Exception as e:
            log.warn("Failed to upload to pastebin!", exc_info=1)
            self.copyToPastebinLabel.setText(self.tr("Failed to upload to pastebin: ") + str(e))
        finally:
            dialog.hide()

        if url:
            self.pastebinURLBox.setVisible(True)
            self.pastebinURLBox.setText(url)
            QtGui.QApplication.clipboard().setText(url)
            self.copyToPastebinLabel.setText(self.tr("Pastebin URL copied to clipboard!"))

    def restartMCEdit(self):
        QtCore.QProcess.startDetached(sys.executable, sys.argv)
        raise SystemExit

    def quitMCEdit(self):
        raise SystemExit