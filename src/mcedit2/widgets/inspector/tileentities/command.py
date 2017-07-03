"""
    command
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui

from mcedit2.util.commandblock import ParseCommand
from mcedit2.widgets.layout import Column, Row

log = logging.getLogger(__name__)


class CommandBlockEditorWidget(QtGui.QWidget):
    tileEntityID = "Control"

    def __init__(self, editorSession, tileEntityRef):
        super(CommandBlockEditorWidget, self).__init__()
        assert tileEntityRef.id == self.tileEntityID

        self.editorSession = editorSession

        self.customNameLabel = QtGui.QLabel(self.tr("Custom Name: "))
        self.customNameField = QtGui.QLineEdit()

        self.trackOutputCheckbox = QtGui.QCheckBox(self.tr("Track Output"))
        self.successCountLabel = QtGui.QLabel(self.tr("Success Count: "))
        self.successCountSpinBox = QtGui.QSpinBox()

        self.gotoCommandButton = QtGui.QPushButton(self.tr("Go To Command"), clicked=self.gotoCommand)
        self.gotoTargetButton = QtGui.QPushButton(self.tr("Go To Target"), clicked=self.gotoTarget)
        self.gotoIndirectTargetButton = QtGui.QPushButton(self.tr("Go To Indirect Target"), clicked=self.gotoIndirectTarget)

        self.commandTextEdit = QtGui.QTextEdit()
        self.commandTextEdit.setAcceptRichText(False)

        self.commandGroup = QtGui.QGroupBox(self.tr("Command Text:"))
        self.commandGroup.setLayout(Column(self.commandTextEdit))
        self.setLayout(Column(Row(self.customNameLabel, self.customNameField),
                              Row(self.trackOutputCheckbox, None,
                                  self.successCountLabel, self.successCountSpinBox),
                              Row(self.gotoCommandButton, self.gotoTargetButton, self.gotoIndirectTargetButton),
                              self.commandGroup))

        self.tileEntityRef = tileEntityRef

        self.commandTextEdit.setText(tileEntityRef.Command)
        self.customNameField.setText(tileEntityRef.CustomName)
        self.trackOutputCheckbox.setChecked(tileEntityRef.TrackOutput != 0)
        self.successCountSpinBox.setValue(tileEntityRef.SuccessCount)

        enabled = not editorSession.readonly

        self.trackOutputCheckbox.setEnabled(enabled)
        self.successCountSpinBox.setEnabled(enabled)
        self.commandTextEdit.setEnabled(enabled)
        self.customNameField.setEnabled(enabled)

        try:
            self.parsedCommand = ParseCommand(tileEntityRef.Command)
        except Exception:
            log.warn("Failed to parse command block.", exc_info=1)
            self.parsedCommand = None

            self.gotoTargetButton.setEnabled(False)
            self.gotoIndirectTarget.setEnabled(False)

        self.adjustSize()

    def gotoCommand(self):
        self.editorSession.zoomToPoint(self.tileEntityRef.Position)

    def gotoTarget(self):
        if self.parsedCommand.name == "setblock":
            targetPos = self.parsedCommand.resolvePosition(self.tileEntityRef.Position)
            self.editorSession.zoomToPoint(targetPos)
        elif self.parsedCommand.name == "execute":
            selector = self.parsedCommand.targetSelector
            if selector.playerName is not None:
                return

            x, y, z = [selector.getArg(a) for a in 'xyz']

            if None in (x, y, z):
                log.warn("No selector coordinates for command %s", self.parsedCommand)
                return
            self.editorSession.zoomToPoint((x, y, z))

    def gotoIndirectTarget(self):
        if self.parsedCommand.name == "execute":
            targetPos = self.parsedCommand.resolvePosition(self.tileEntityRef.Position)
            subcommand = self.parsedCommand.subcommand

            if hasattr(subcommand, 'resolvePosition'):
                indirectPos = subcommand.resolvePosition(targetPos)
                self.editorSession.zoomToPoint(indirectPos)

            if hasattr(subcommand, 'resolveBoundingBox'):
                sourceBounds = subcommand.resolveBoundingBox(targetPos)
                self.editorSession.zoomToPoint(sourceBounds.center)


