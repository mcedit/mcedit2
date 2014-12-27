"""
    command
"""
from __future__ import absolute_import, division, print_function
import contextlib
import logging
from PySide import QtGui

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
            self.editorSession.commitUndo()
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
        self.editorSession.gotoRevision(self.previousRevision)

    def redo(self):
        self.editorSession.gotoRevision(self.currentRevision)
        pass

    @contextlib.contextmanager
    def begin(self):
        self.previousRevision = self.editorSession.currentRevision
        self.editorSession.beginUndo()
        yield
        self.editorSession.commitUndo()
        self.currentRevision = self.editorSession.currentRevision
