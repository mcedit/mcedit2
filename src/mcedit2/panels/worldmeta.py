"""
    player
"""
from __future__ import absolute_import
import logging
from contextlib import contextmanager

from PySide import QtGui
from PySide.QtCore import Qt

from mcedit2.util.resources import resourcePath
from mcedit2.util.load_ui import load_ui
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.widgets.nbttree.nbteditor import NBTDataChangeCommand

log = logging.getLogger(__name__)


class WorldMetaPanel(QtGui.QWidget):
    GENERATOR_TYPES = ["default", "flat", "largeBiomes", "amplified", "customized", 'debug_all_block_states']
    GAMEMODES = ["Survival", "Creative", "Adventure", "Spectator"]
    DIFFICULTIES = ["Peaceful", "Easy", "Normal", "Hard"]

    editsDisabled = False

    def __init__(self, editorSession):
        super(WorldMetaPanel, self).__init__(QtGui.qApp.mainWindow, f=Qt.Tool)
        self.editorSession = editorSession
        self.worldMeta = editorSession.worldEditor.adapter.metadata
        callIcon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/edit_metadata.png"))
        callButton = QtGui.QAction(callIcon, "Edit World Metadata", self)
        callButton.setCheckable(True)
        callButton.triggered.connect(self.toggleView)
        self._toggleViewAction = callButton

        load_ui("panels/worldmeta.ui", baseinstance=self)

        self.worldNBTEditor.editorSession = self.editorSession
        self.editorSession.revisionChanged.connect(self.revisionDidChange)

        self.updateNBTTree()
        self.setupPanel()
        self.updatePanel()

        centerWidgetInScreen(self)

    def updatePanel(self):
        self.defaultGamemodeCombo.setCurrentIndex(self.worldMeta.GameType)
        self.worldDifficultyCombo.setCurrentIndex(self.worldMeta.Difficulty)
        self.generationTypeCombo.setCurrentIndex(self.GENERATOR_TYPES.index(self.worldMeta.generatorName))

        self.worldNameLineEdit.setText(self.worldMeta.LevelName)
        self.worldNameLineEdit.setText(self.worldMeta.LevelName)
        self.generatorSeedLineEdit.setText(unicode(str(self.worldMeta.RandomSeed), encoding='utf-8'))
        self.generatorOptionsLineEdit.setText(self.worldMeta.generatorOptions)

        self.spawnX.setValue(self.worldMeta.SpawnX)
        self.spawnY.setValue(self.worldMeta.SpawnY)
        self.spawnZ.setValue(self.worldMeta.SpawnZ)

        time = self.worldMeta.DayTime + 30000  # On time = 0, it's day 1, 6:00. Day 0, 0:00 is -30000
        day = time / 24000
        hour = (time % 24000) / 1000
        minute = int((time % 1000) / (1000.0 / 60.0))

        self.timeDays.setValue(day)
        self.timeHours.setValue(hour)
        self.timeMinutes.setValue(minute)

        self.lockedDifficultyBool.setChecked(bool(self.worldMeta.DifficultyLocked))
        self.commandsBool.setChecked(bool(self.worldMeta.allowCommands))
        self.hardcoreBool.setChecked(bool(self.worldMeta.hardcore))

    def setupPanel(self):
        self.defaultGamemodeCombo.clear
        self.defaultGamemodeCombo.addItems(self.GAMEMODES)
        self.defaultGamemodeCombo.currentIndexChanged.connect(self.defaultGamemodeChanged)

        self.worldDifficultyCombo.clear
        self.worldDifficultyCombo.addItems(self.DIFFICULTIES)
        self.worldDifficultyCombo.currentIndexChanged.connect(self.worldDifficultyChanged)

        self.generationTypeCombo.clear
        self.generationTypeCombo.addItems(self.GENERATOR_TYPES)
        self.generationTypeCombo.currentIndexChanged.connect(self.generationTypeChanged)

        self.worldNameLineEdit.editingFinished.connect(self.worldNameChanged)
        self.generatorSeedLineEdit.editingFinished.connect(self.seedChanged)
        self.generatorOptionsLineEdit.editingFinished.connect(self.generatorOptionsChanged)

        self.spawnX.editingFinished.connect(self.spawnXChanged)
        self.spawnY.editingFinished.connect(self.spawnYChanged)
        self.spawnZ.editingFinished.connect(self.spawnZChanged)

        self.timeDays.editingFinished.connect(self.timeChanged)
        self.timeHours.editingFinished.connect(self.timeChanged)
        self.timeMinutes.editingFinished.connect(self.timeChanged)

        self.lockedDifficultyBool.stateChanged.connect(self.lockedDifficultyChanged)
        self.commandsBool.stateChanged.connect(self.allowCommandsChanged)
        self.hardcoreBool.stateChanged.connect(self.hardcoreChanged)

    @contextmanager  # xxx copied from inventory.py
    def disableEdits(self):
        self.editsDisabled = True
        yield
        self.editsDisabled = False

    def updateNBTTree(self):
        self.worldNBTEditor.undoCommandPrefixText = "World Metadata: "
        self.worldNBTEditor.setRootTagRef(self.worldMeta)

    def revisionDidChange(self):
        self.updateNBTTree()
        self.updatePanel()

    def toggleView(self):
        if self.isHidden():
            self.show()
            self._toggleViewAction.setChecked(True)
        else:
            self.hide()
            self._toggleViewAction.setChecked(False)

    def closeEvent(self, event):
        self.toggleView()

    _toggleViewAction = None

    def toggleViewAction(self):
        return self._toggleViewAction

    # -- Listeners to change NBT tags on editing (does it really need a function per tag?)

    def worldNameChanged(self):
        if self.editsDisabled or self.worldMeta.LevelName == self.worldNameLineEdit.text():
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Level Name"))
        with command.begin():
            self.worldMeta.LevelName = self.worldNameLineEdit.text()
        self.editorSession.pushCommand(command)

    def seedChanged(self):
        if self.editsDisabled or self.worldMeta.RandomSeed == long(self.generatorSeedLineEdit.text()):
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Generator Random Seed"))
        with command.begin():
            self.worldMeta.RandomSeed = long(self.generatorSeedLineEdit.text())
        self.editorSession.pushCommand(command)

    def generatorOptionsChanged(self):
        if self.editsDisabled or self.worldMeta.generatorOptions == self.generatorOptionsLineEdit.text():
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Generator Options"))
        with command.begin():
            self.worldMeta.generatorOptions = self.generatorOptionsLineEdit.text()
        self.editorSession.pushCommand(command)

    def defaultGamemodeChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Default Gamemode"))
        with command.begin():
            self.worldMeta.GameType = self.defaultGamemodeCombo.currentIndex()
        self.editorSession.pushCommand(command)

    def worldDifficultyChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Difficulty"))
        with command.begin():
            self.worldMeta.Difficulty = self.worldDifficultyCombo.currentIndex()
        self.editorSession.pushCommand(command)

    def generationTypeChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Generation Type"))
        with command.begin():
            self.worldMeta.generatorName = self.GENERATOR_TYPES[self.generationTypeCombo.currentIndex()]
        self.editorSession.pushCommand(command)

    def spawnXChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Spawn X"))
        with command.begin():
            self.worldMeta.SpawnX = self.spawnX.value()
        self.editorSession.pushCommand(command)

    def spawnYChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Spawn Y"))
        with command.begin():
            self.worldMeta.SpawnY = self.spawnY.value()
        self.editorSession.pushCommand(command)

    def spawnZChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Spawn Z"))
        with command.begin():
            self.worldMeta.SpawnZ = self.spawnZ.value()
        self.editorSession.pushCommand(command)

    def timeChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change DayTime"))
        with command.begin():
            days, hours, minutes = self.timeDays.value(), self.timeHours.value(), self.timeMinutes.value()
            time = max((days * 24000 + hours * 1000 + int(minutes * (1000.0 / 60.0))) - 30000, 0)
            self.worldMeta.DayTime = time
        self.editorSession.pushCommand(command)

    def hardcoreChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Hardcore"))
        with command.begin():
            self.worldMeta.hardcore = self.hardcoreBool.isChecked()
        self.editorSession.pushCommand(command)

    def lockedDifficultyChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Locked Difficulty"))
        with command.begin():
            self.worldMeta.DifficultyLocked = self.lockedDifficultyBool.isChecked()
        self.editorSession.pushCommand(command)

    def allowCommandsChanged(self):
        if self.editsDisabled:  # xxx copied from inventory.py
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr("Change Allow Commands"))
        with command.begin():
            self.worldMeta.allowCommands = self.commandsBool.isChecked()
        self.editorSession.pushCommand(command)

class WorldMetaEditCommand(NBTDataChangeCommand):
    pass
