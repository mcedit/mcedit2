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
from mceditlib.util.progress import rescaleProgress

log = logging.getLogger(__name__)

timeBeforeDialog = 0.2

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
    progress = None
    cancel = kwargs.pop('cancel', None)
    with LoaderTimer.stopCtx():

        dialog = QtGui.QProgressDialog(QtGui.qApp.mainWindow)
        dialog.setWindowTitle(text)
        dialog.setWindowModality(Qt.WindowModal)
        #dialog.show()
        log.info("Starting progress: %d tasks." % len(tasks))
        maximum = len(tasks) * 100
        for i, task in enumerate(tasks):
            log.info("Task #%d", i)
            task = rescaleProgress(task, i*100, i*100+100)
            for progress in task:
                if isinstance(progress, basestring):
                    current = 0
                    status = progress
                elif isinstance(progress, tuple):
                    if len(progress) > 2:
                        current, _, status = progress[:3]
                    else:
                        current, _ = progress
                        status = ""
                else:
                    current = 1
                    status = ""

                dialog.setValue(current)
                dialog.setMaximum(maximum)
                dialog.setLabelText(status)
                #QtGui.QApplication.processEvents()
                if dialog.wasCanceled():
                    return False

        dialog.close()
        return progress

