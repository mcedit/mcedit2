#!/usr/bin/env python
"""
    main.py

    This is the main entry point of the MCEdit application.

    The order of every statement in this file is important, including import statements. If
    you do an "organize imports" on this file, I will kill you.
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import sys

import OpenGL

from mcedit2.sentry import get_sentry_client
from mcedit2.util import custom_traceback

import codecs

# Since the Windows console uses an encoding that can't represent all unicode
# characters, we set the error mode of the standard IO streams to "replace"
# so as not to get encoding errors when printing filenames.
from mcedit2.util.gen_ui import compile_ui


def writer(stream):
    oldwrite = stream.write
    def _write(a):
        if isinstance(a, str):
            stream.stream.write(a)
        else:
            oldwrite(a)

    return _write

ioencoding = sys.stdin.encoding or 'utf-8'

sys.stdout = codecs.getwriter(ioencoding)(sys.stdout, errors='ignore')
sys.stderr = codecs.getwriter(ioencoding)(sys.stderr, errors='ignore')

sys.stdout.write = writer(sys.stdout)
sys.stderr.write = writer(sys.stderr)

custom_traceback.install()

# IMPORTANT: Must set OpenGL.BLAH_BLAH **BEFORE** importing OpenGL.GL
if "-log" in sys.argv:
    sys.argv.remove('-log')
    OpenGL.FULL_LOGGING = True

if "-debug" not in sys.argv:
    OpenGL.ERROR_CHECKING = False
else:
    OpenGL.ERROR_LOGGING = True
    OpenGL.CONTEXT_CHECKING = True
    while "-debug" in sys.argv:
        sys.argv.remove('-debug')
    print("GL Errors enabled!")

import os

# ugly ugly hack. has_binding uses imp.find_module to find QtGui, but imp.find_module doesn't work for pyinstaller
# packed apps since pyi renames all the modules - QtGui becomes "PySide.QtGui.pyd" without any directory structure.
from qtconsole import qt_loaders
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
    class MCELogRecord(logging.LogRecord):
        """
        Override of LogRecord with 100% unicode-safe message formatting
        """
        def getMessage(self):
            """
            Return the message for this LogRecord.

            Return the message for this LogRecord after merging any user-supplied
            arguments with the message.
            """
            msg = self.msg
            if not isinstance(msg, basestring):
                try:
                    msg = str(self.msg)
                except UnicodeError:
                    msg = self.msg      #Defer encoding till later
            if self.args:
                try:
                    msg = msg % self.args
                except UnicodeDecodeError:
                    # 'msg' is unicode, but 'args' contains a str with non-ascii chars
                    # round-trip to str and decode with escapes to avoid encode errors
                    msg = msg.encode(b'ascii', b'backslashreplace')
                    msg = msg % self.args
                    msg = msg.decode(b'ascii', b'replace')
            return msg

    logging.LogRecord = MCELogRecord
    logging.captureWarnings(True)
    from mcedit2.util.directories import getUserFilesDirectory
    mceditUserData = getUserFilesDirectory()
    logfilename = os.path.join(mceditUserData, 'mcedit2.log')

    abslogfile = os.path.abspath(logfilename)
    if hasattr(sys, 'frozen'):
        log_debug("sys.frozen is set")

        if sys.platform == "darwin":
            log_debug("OS X found.")
            logfile = os.path.expanduser(b"~/Library/Logs/" + 'mcedit2.log')
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

@profiler.function("startup")
def startup():

    # Must call this before QApplication is created
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads, True)
    global editorApp
    setup_logging()
    get_sentry_client()
    compile_ui()
    sys.excepthook = excepthook

    from mcedit2 import __version__
    log.info("MCEdit2 version %s starting...", __version__)

    pyi_tmpdir = getattr(sys, "_MEIPASS", None)
    if pyi_tmpdir:
        os.chdir(pyi_tmpdir)

    import pygments.lexers
    if hasattr(pygments.lexers, 'newmod'):
        # pyinstaller hack - must call before importing from mcedit2
        pygments.lexers.PythonLexer = pygments.lexers.newmod.PythonLexer

    from mcedit2.editorapp import MCEditApp
    
    from mcedit2 import support_modules

    # TODO: get wchar_t argv from windows
    editorApp = MCEditApp(sys.argv)
    editorApp.startup()

    return editorApp

def excepthook(exc_type, exc_value, exc_tb):
    # When an error is caught during a Qt signal call, PySide calls PyErr_Print to
    # display the error traceback. PyErr_Print calls sys.excepthook to actually print the
    # exception, so we override it to send the error to the logging module and exit with an error,
    # since PySide foolishly tries to continue after catching the error.
    log.error("Unhandled Exception: \n\t%s", exc_value, exc_info=(exc_type, exc_value, exc_tb))
    # text = "An error has occured.\n\nUnhandled exception: %s" % exc_value
    # if getattr(sys, 'frozen', False):
    #     if editorApp:
    #         if editorApp.mainWindow:
    #             editorApp.mainWindow.hide()
    #     msg = QtGui.QMessageBox(editorApp.mainWindow or None if editorApp else None)
    #     msg.setIcon(QtGui.QMessageBox.Critical)
    #     msg.setText(text)
    #     msg.exec_()
    # sys.exit(-1)
    if isinstance(exc_value, KeyboardInterrupt):
        sys.exit(-1)

    from mcedit2.dialogs.error_dialog import showErrorDialog
    showErrorDialog("Unhandled Exception", (exc_type, exc_value, exc_tb), fatal=True)


def main():
    app = startup()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
