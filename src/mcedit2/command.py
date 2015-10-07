"""
    command
"""
from __future__ import absolute_import, division, print_function
import contextlib
import logging
from PySide import QtGui
from mcedit2.util.showprogress import showProgress

log = logging.getLogger(__name__)


class SimplePerformCommand(QtGui.QUndoCommand):
    performed = False

    def __init__(self, editorSession):
        super(SimplePerformCommand, self).__init__()
        self.editorSession = editorSession
        self.performed = False

    def undo(self):
        self.editorSession.undoBackward()

    def redo(self):
        if not self.performed:
            self.editorSession.beginUndo()
            self.perform()
            task = self.editorSession.commitUndoIter()
            showProgress(QtGui.qApp.tr("Writing undo history"), task)

        else:
            self.editorSession.undoForward()

    def perform(self):
        # implement me in subclass
        raise NotImplementedError


class SimpleRevisionCommand(QtGui.QUndoCommand):
    previousRevision = None  # int
    currentRevision = None  # int

    def __init__(self, editorSession, text, *args, **kwargs):
        super(SimpleRevisionCommand, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        self.setText(text)

    def undo(self):
        if self.previousRevision is not None:
            self.editorSession.gotoRevision(self.previousRevision)

    def redo(self):
        if self.currentRevision is not None:
            self.editorSession.gotoRevision(self.currentRevision)

    @contextlib.contextmanager
    def begin(self):
        self.previousRevision = self.editorSession.currentRevision
        self.editorSession.beginUndo()
        try:
            yield
        finally:
            task = self.editorSession.commitUndoIter()
            showProgress(QtGui.qApp.tr("Writing undo history"), task)

            self.currentRevision = self.editorSession.currentRevision
