"""
    main.py
"""
#!/usr/bin/env python
from __future__ import absolute_import, division, print_function, unicode_literals
import sys
import traceback

import OpenGL

from mcedit2.util import custom_traceback


custom_traceback.install()

# IMPORTANT: Must set OpenGL.BLAH_BLAH **BEFORE** importing OpenGL.GL
if "-log" in sys.argv:
    sys.argv.remove('-log')
    OpenGL.FULL_LOGGING = True

if "-debug" not in sys.argv:
    OpenGL.ERROR_CHECKING = False

import os
# ugly ugly hack. has_binding uses imp.find_module to find QtGui, but imp.find_module doesn't work for pyinstaller
# packed apps since pyi renames all the modules - QtGui becomes "PySide.QtGui.pyd" without any directory structure.
from IPython.external import qt_loaders
qt_loaders.has_binding = lambda p: p == "pyside"

from PySide import QtGui, QtCore
from mcedit2.util.bugfixes import QObject_tr_unicode_literals_fix
from mcedit2.util import profiler

import logging
log = logging.getLogger(__name__)

QObject_tr_unicode_literals_fix()

log_debug = print
# log_debug = lambda *a, **kw: None

def setup_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    log_debug("Logging level set")

    from mcedit2.util.directories import getUserFilesDirectory
    mceditUserData = getUserFilesDirectory()
    logfilename = os.path.join(mceditUserData, 'mcedit.log')

    abslogfile = os.path.abspath(logfilename)
    if hasattr(sys, 'frozen'):
        log_debug("sys.frozen is set")

        if sys.platform == "darwin":
            log_debug("OS X found.")
            logfile = os.path.expanduser("~/Library/Logs/" + logfilename)
        else:
            logfile = abslogfile
    else:
        logfile = abslogfile

    fmt = logging.Formatter(
        '[%(levelname)s][%(filename)s:%(lineno)d]:%(message)s'
    )
    log_debug("Logging to %s" % logfile)

    logfileHandler = logging.FileHandler(logfile, mode="w")
    logfileHandler.setLevel(logging.INFO)
    logfileHandler.setFormatter(fmt)
    root_logger.addHandler(logfileHandler)

    closeStdouterr = False
    if closeStdouterr:
        sys.stdout = logfileHandler.stream
        sys.stderr = logfileHandler.stream

    else:
        log_debug("Setting up console handler")

        consoleHandler = logging.StreamHandler()
        consoleHandler.setLevel(logging.WARN)

        if "-v" in sys.argv:
            sys.argv.remove("-v")
            consoleHandler.setLevel(logging.INFO)
        if "-vv" in sys.argv:
            sys.argv.remove("-vv")
            consoleHandler.setLevel(logging.DEBUG)
            logfileHandler.setLevel(logging.DEBUG)

        consoleHandler.setFormatter(fmt)
        root_logger.addHandler(consoleHandler)


editorApp = None
DEBUG = False
if "-debug" in sys.argv:
    sys.argv.remove("-debug")
    DEBUG = True


@profiler.function("startup")
def startup():
    global editorApp
    sys.excepthook = excepthook
    setup_logging()

    import pygments.lexers
    if hasattr(pygments.lexers, 'newmod'):
        # pyinstaller hack - must call before importing from mcedit2
        pygments.lexers.PythonLexer = pygments.lexers.newmod.PythonLexer

    from mcedit2.editorapp import MCEditApp

    editorApp = MCEditApp(sys.argv, DEBUG)

    return editorApp

def excepthook(exc_type, exc_value, exc_tb):
    # When an error is caught during a Qt signal call, PySide calls PyErr_Print to
    # display the error traceback. PyErr_Print calls sys.excepthook to actually print the
    # exception, so we override it to send the error to the logging module.
    log.error("Unhandled Exception: \n\t%s", exc_value, exc_info=(exc_type, exc_value, exc_tb))
    #def showError():
    text = "An error has occured.\n\nUnhandled exception: %s" % exc_value
    if getattr(sys, 'frozen', False):
        if editorApp:
            if editorApp.mainWindow:
                editorApp.mainWindow.hide()
        msg = QtGui.QMessageBox(editorApp.mainWindow or None if editorApp else None)
        msg.setIcon(QtGui.QMessageBox.Critical)
        msg.setText(text)
        msg.exec_()
    QtCore.qFatal(text)

    #QtCore.QTimer.singleShot(0, showError)

def main():
    try:
        app = startup()
        sys.exit(app.exec_())
    except Exception as e:
        if not getattr(sys, 'frozen', False) and '-debug' in sys.argv:
            # Interactively inspect program state after a crash, if running from source and with the -debug flag set
            traceback.print_exc()
            import IPython; IPython.embed()
        else:
            raise


if __name__ == "__main__":
    main()
