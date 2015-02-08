"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from PySide.QtCore import Qt
from mcedit2.util.worldloader import LoaderTimer

log = logging.getLogger(__name__)

itersBeforeDialog = 8

def showProgress(text, iter, cancel=False):
    """
    Show a progress dialog for the given task. The task should be an iterable, yielding progress info as
    (current, max) or (current, max, statusString) tuples. Return the last value yielded by the task.
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
    i = 0
    with LoaderTimer.stopCtx():
        for progress in iter:
            i += 1
            if i > itersBeforeDialog:
                break
        else:
            return progress

        dialog = QtGui.QProgressDialog(QtGui.qApp.mainWindow)
        dialog.setWindowTitle(text)
        dialog.setWindowModality(Qt.WindowModal)
        dialog.show()


        for progress in iter:
            if isinstance(progress, basestring):
                max = current = 0
                status = progress
            elif isinstance(progress, (tuple, list)):
                if len(progress) > 2:
                    current, max, status = progress[:3]
                else:
                    current, max = progress
                    status = ""
            else:
                current = max = 1
                status = ""

            dialog.setValue(current)
            dialog.setMaximum(max)
            dialog.setLabelText(status)
            QtGui.QApplication.processEvents()
            if dialog.wasCanceled():
                return False

        dialog.close()
        return progress

