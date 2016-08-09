"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from PySide.QtCore import Qt
import time
import itertools
from mcedit2.util.worldloader import LoaderTimer
from mceditlib.util import exhaust
from mceditlib.util.progress import rescaleProgress

log = logging.getLogger(__name__)

timeBeforeDialog = 0.2


class MCEProgressDialog(QtGui.QProgressDialog):

    def __init__(self, *a):
        flags = Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint
        a = a + (flags,)
        super(MCEProgressDialog, self).__init__(*a)

    def close(self):
        pass

    def reject(self):
        pass

    def closeEvent(self, event):
        event.ignore()


_progressBarActive = False

def showProgress(text, *tasks, **kwargs):
    """
    Show a progress dialog for the given task(s). Each task should be an iterable,
    yielding progress info as (current, max) or (current, max, statusString) tuples.
    Return the last value yielded by the task.

    :param text:
    :type text:
    :param iter:
    :type iter:
    :param cancel:
    :type cancel:
    :return:
    :rtype:
    """
    global _progressBarActive

    if _progressBarActive:
        for task in tasks:
            exhaust(task)
        return

    progress = None
    cancel = kwargs.pop('cancel', None)
    start = time.time()
    shown = False
    try:
        with LoaderTimer.stopCtx():

            dialog = MCEProgressDialog(QtGui.qApp.mainWindow)
            if not cancel:
                dialog.setCancelButtonText(None)
            dialog.setWindowTitle(text)
            dialog.setWindowModality(Qt.WindowModal)
            log.info("Starting progress: %d tasks." % len(tasks))
            totalMaximum = len(tasks) * 100
            for i, task in enumerate(tasks):
                log.info("Task #%d", i)
                task = rescaleProgress(task, i*100, i*100+100)
                for progress in task:
                    if isinstance(progress, basestring):
                        current = 0
                        maximum = 0
                        status = progress
                    elif isinstance(progress, tuple):
                        if len(progress) > 2:
                            current, maximum, status = progress[:3]
                        else:
                            current, maximum = progress
                            status = ""
                    else:
                        current = 0
                        maximum = 0
                        status = ""

                    dialog.setValue(current)
                    if maximum == 0:
                        # Task progress is indeterminate
                        dialog.setMaximum(0)
                    else:
                        dialog.setMaximum(totalMaximum)
                    dialog.setLabelText(status)
                    if time.time() > start + timeBeforeDialog:
                        if not shown:
                            dialog.show()
                            shown = True
                        QtGui.QApplication.processEvents()

                    if dialog.wasCanceled():
                        return False

            return progress
    finally:
        dialog.reset()
        _progressBarActive = False

