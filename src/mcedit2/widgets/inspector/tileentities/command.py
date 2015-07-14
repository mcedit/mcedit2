"""
    command
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from mcedit2.widgets.layout import Column, Row

log = logging.getLogger(__name__)


class CommandBlockEditorWidget(QtGui.QWidget):
    tileEntityID = "Control"
    def __init__(self, editorSession, tileEntityRef):
        super(CommandBlockEditorWidget, self).__init__()
        assert tileEntityRef.id == self.tileEntityID

        self.customNameLabel = QtGui.QLabel(self.tr("Custom Name: "))
        self.customNameField = QtGui.QLineEdit()

        self.trackOutputCheckbox = QtGui.QCheckBox(self.tr("Track Output"))
        self.successCountLabel = QtGui.QLabel(self.tr("Success Count: "))
        self.successCountSpinBox = QtGui.QSpinBox()


        self.commandTextEdit = QtGui.QTextEdit()
        self.commandTextEdit.setAcceptRichText(False)

        self.commandGroup = QtGui.QGroupBox(self.tr("Command Text:"))
        self.commandGroup.setLayout(Column(self.commandTextEdit))
        self.setLayout(Column(Row(self.customNameLabel, self.customNameField),
                              Row(self.trackOutputCheckbox, None,
                                  self.successCountLabel, self.successCountSpinBox),
                              self.commandGroup))

        self.tileEntityRef = tileEntityRef

        self.commandTextEdit.setText(tileEntityRef.Command)
        self.customNameField.setText(tileEntityRef.CustomName)
        self.trackOutputCheckbox.setChecked(tileEntityRef.TrackOutput != 0)
        self.successCountSpinBox.setValue(tileEntityRef.SuccessCount)


