"""
    undostack
"""
from __future__ import absolute_import, division, print_function
import logging
from PySide import QtGui

log = logging.getLogger(__name__)

class MCEUndoStack(QtGui.QUndoStack):
    undoBlock = None

    def undo(self):
        self.clearUndoBlock()
        super(MCEUndoStack, self).undo()

    def redo(self):
        self.clearUndoBlock()  # Shouldn't ever find a block
        super(MCEUndoStack, self).redo()

    def push(self, *args, **kwargs):
        self.clearUndoBlock()
        super(MCEUndoStack, self).push(*args, **kwargs)

    def clearUndoBlock(self):
        """
        If an undo block is set, calls its callback and removes it.

        :return:
        :rtype:
        """
        if self.undoBlock:
            callback = self.undoBlock
            self.undoBlock = None
            callback()

