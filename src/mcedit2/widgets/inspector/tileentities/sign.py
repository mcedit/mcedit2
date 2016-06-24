"""
    sign
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from PySide import QtGui

log = logging.getLogger(__name__)


class SignEditorWidget(QtGui.QWidget):
    tileEntityID = "Sign"

    def __init__(self, editorSession, tileEntityRef):
        super(SignEditorWidget, self).__init__()
        assert tileEntityRef.id == self.tileEntityID

        self.editorSession = editorSession

        layout = QtGui.QFormLayout()

        self.tileEntityRef = tileEntityRef

        self.lineEdits = []
        for i in range(4):
            lineEdit = QtGui.QLineEdit()
            line = getattr(tileEntityRef, "Text%d" % (i+1), None)
            if line is not None:
                lineEdit.setText(line)

            layout.addRow(self.tr("Text %d") % (i+1), lineEdit)
            self.lineEdits.append(lineEdit)
            lineEdit.textChanged.connect(self.textDidChange)

        self.setLayout(layout)

    def textDidChange(self):
        with self.editorSession.beginSimpleCommand(self.tr("Edit sign text")):
            for i, lineEdit in self.enumerate(self.lineEdits):
                setattr(self.tileEntityRef, "Text%d" % (i+1), lineEdit.text())
