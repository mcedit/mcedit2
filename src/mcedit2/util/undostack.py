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
        self.clearUndoBlock(False)
        super(MCEUndoStack, self).undo()

    def redo(self):
        self.clearUndoBlock(False)  # Shouldn't ever find a block
        super(MCEUndoStack, self).redo()

    def setUndoBlock(self, callback):
        """
        Set a function to be called before the next time undo, redo, or beginUndo is called. Some tools may need to
        call beginUndo, then interact with the user for a time before calling commitUndo, or they may need to use
        multiple undo revisions for a single operation with freedom given to the user between revisions. This
        ensures that the interactive operation will be completed or aborted before the next command begins its undo
        revision.

        User actions that only change the editor state will not call beginUndo, and their QUndoCommand may end up
        before the interrupted command in the history.

        :param callback: Function to call
        :type callback: callable
        """
        assert not self.undoBlock, "Cannot add multiple undo blocks (yet)"
        self.undoBlock = callback

    def removeUndoBlock(self, callback):
        if self.undoBlock:
            if callback != self.undoBlock:  # can't use 'is' for func ptrs, why?
                raise ValueError("Trying to remove an undoBlock that is not set, had %r and asked to remove %r",
                                 self.undoBlock, callback)
            self.undoBlock = None

    def clearUndoBlock(self, complete):
        """
        If an undo block is set, calls its callback and removes it.

        :param complete: Whether to complete or abort the command which set the undo block
        :type complete: bool
        :return:
        :rtype:
        """
        if self.undoBlock:
            callback = self.undoBlock
            self.undoBlock = None
            callback(complete)

