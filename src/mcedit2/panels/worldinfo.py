"""
    worldinfo
"""
from __future__ import absolute_import
import logging
from contextlib import contextmanager

from PySide import QtGui
from PySide.QtCore import Qt

from mcedit2.command import SimpleRevisionCommand
from mcedit2.ui.panels.worldinfo import Ui_worldInfoWidget
from mcedit2.util.resources import resourcePath
from mcedit2.util.screen import centerWidgetInScreen

log = logging.getLogger(__name__)


class WorldInfoPanel(QtGui.QWidget, Ui_worldInfoWidget):

    editsDisabled = False

    def __init__(self, editorSession):
        super(WorldInfoPanel, self).__init__(QtGui.qApp.mainWindow, f=Qt.Tool)
        self.setupUi(self)

        self.editorSession = editorSession
        self.worldMeta = self.editorSession.worldEditor.adapter.metadata

        callIcon = QtGui.QIcon(resourcePath('mcedit2/assets/mcedit2/icons/edit_worldinfo.png'))
        callButton = QtGui.QAction(callIcon, self.tr('World Info'), self)
        callButton.setCheckable(True)
        callButton.triggered.connect(self.toggleView)
        self._toggleViewAction = callButton

        self.worldNBTEditor.editorSession = self.editorSession
        self.editorSession.revisionChanged.connect(self.revisionDidChange)

        self.gamemodes = [self.tr('Survival'), self.tr('Creative'), self.tr('Adventure'), self.tr('Spectator')]
        self.difficulties = [self.tr('Peaceful'), self.tr('Easy'), self.tr('Normal'), self.tr('Hard')]
        self.generatorTypes = [
            (self.tr('Default'), 'default'),
            (self.tr('Flat'), 'flat'),
            (self.tr('Large Biomes'), 'largeBiomes'),
            (self.tr('Amplified'), 'amplified'),
            (self.tr('Customized'), 'customized'),
            (self.tr('Debug All Block States'), 'debug_all_block_states'),
        ]

        self.defaultGamemodeCombo.addItems(self.gamemodes)
        self.defaultGamemodeCombo.currentIndexChanged.connect(self.defaultGamemodeChanged)

        self.worldDifficultyCombo.addItems(self.difficulties)
        self.worldDifficultyCombo.currentIndexChanged.connect(self.worldDifficultyChanged)

        for name, data in self.generatorTypes:
            self.generatorTypeCombo.addItem(name, data)

        self.generatorTypeCombo.currentIndexChanged.connect(self.generatorTypeChanged)

        # Since QComboBox emits editTextChanged after every keystroke,
        # we connect to its QLineEdit's editingFinished to only get signaled
        # after the line edit loses focus (or the user presses return)
        self.generatorTypeCombo.lineEdit().editingFinished.connect(self.generatorTypeChanged)

        self.worldNameLineEdit.editingFinished.connect(self.worldNameChanged)
        self.generatorSeedLineEdit.editingFinished.connect(self.seedChanged)
        self.generatorOptionsLineEdit.editingFinished.connect(self.generatorOptionsChanged)

        self.spawnX.editingFinished.connect(self.spawnChanged)
        self.spawnY.editingFinished.connect(self.spawnChanged)
        self.spawnZ.editingFinished.connect(self.spawnChanged)

        self.timeDays.editingFinished.connect(self.timeChanged)
        self.timeSlider.sliderReleased.connect(self.timeChanged)

        self.dawnButton.setIcon(QtGui.QIcon(resourcePath('mcedit2/assets/mcedit2/clock/dawn.png')))
        self.dawnButton.pressed.connect(self.setTimeDawn)
        self.noonButton.setIcon(QtGui.QIcon(resourcePath('mcedit2/assets/mcedit2/clock/noon.png')))
        self.noonButton.pressed.connect(self.setTimeNoon)
        self.eveningButton.setIcon(QtGui.QIcon(resourcePath('mcedit2/assets/mcedit2/clock/evening.png')))
        self.eveningButton.pressed.connect(self.setTimeEvening)
        self.nightButton.setIcon(QtGui.QIcon(resourcePath('mcedit2/assets/mcedit2/clock/night.png')))
        self.nightButton.pressed.connect(self.setTimeNight)

        self.lockedDifficultyBool.stateChanged.connect(self.lockedDifficultyChanged)
        self.commandsBool.stateChanged.connect(self.allowCommandsChanged)
        self.hardcoreBool.stateChanged.connect(self.hardcoreChanged)

        self.updatePanel()
        self.updateNBTTree()

        centerWidgetInScreen(self)

    def updatePanel(self):
        with self.disableEdits():
            self._updatePanel()

    def _updatePanel(self):
        self.defaultGamemodeCombo.setCurrentIndex(self.worldMeta.GameType)
        self.worldDifficultyCombo.setCurrentIndex(self.worldMeta.Difficulty)

        generatorIndex = self.generatorTypeCombo.findData(self.worldMeta.generatorName)
        if generatorIndex == -1:
            generatorIndex = self.generatorTypeCombo.findText(self.worldMeta.generatorName)
            if generatorIndex == -1:
                self.generatorTypeCombo.addItem(self.worldMeta.generatorName)
                generatorIndex = self.generatorTypeCombo.count()-1

        self.generatorTypeCombo.setCurrentIndex(generatorIndex)

        self.worldNameLineEdit.setText(self.worldMeta.LevelName)
        self.worldNameLineEdit.setText(self.worldMeta.LevelName)
        self.generatorSeedLineEdit.setText(str(self.worldMeta.RandomSeed))
        self.generatorOptionsLineEdit.setText(self.worldMeta.generatorOptions)

        sx, sy, sz = self.worldMeta.Spawn
        self.spawnX.setValue(sx)
        self.spawnY.setValue(sy)
        self.spawnZ.setValue(sz)

        time = self.worldMeta.DayTime + 30000  # On time = 0, it's day 1, 6:00. Day 0, 0:00 is -30000
        day = time / 24000
        hourminute = (time % 24000)

        self.timeDays.setValue(day)
        h, m = (hourminute / 1000), ((hourminute % 1000) / (1000.0/60.0))
        self.timeLabel.setText('{h:02d}:{m:02d}'.format(h=int(h), m=int(m)))
        self.timeSlider.setValue(hourminute)

        self.lockedDifficultyBool.setChecked(bool(self.worldMeta.DifficultyLocked))
        self.commandsBool.setChecked(bool(self.worldMeta.allowCommands))
        self.hardcoreBool.setChecked(bool(self.worldMeta.hardcore))

    @contextmanager
    def disableEdits(self):
        self.editsDisabled = True
        yield
        self.editsDisabled = False

    def updateNBTTree(self):
        self.worldNBTEditor.undoCommandPrefixText = self.tr('World Metadata: ')
        self.worldNBTEditor.setRootTagRef(self.worldMeta)

    def revisionDidChange(self):
        self.worldMeta = self.editorSession.worldEditor.adapter.metadata
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

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Level Name'))
        with command.begin():
            self.worldMeta.LevelName = self.worldNameLineEdit.text()
        self.editorSession.pushCommand(command)

    def seedChanged(self):
        if self.editsDisabled or self.worldMeta.RandomSeed == long(self.generatorSeedLineEdit.text()):
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Generator Random Seed'))
        with command.begin():
            self.worldMeta.RandomSeed = long(self.generatorSeedLineEdit.text())
        self.editorSession.pushCommand(command)

    def generatorOptionsChanged(self):
        if self.editsDisabled or self.worldMeta.generatorOptions == self.generatorOptionsLineEdit.text():
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Generator Options'))
        with command.begin():
            self.worldMeta.generatorOptions = self.generatorOptionsLineEdit.text()
        self.editorSession.pushCommand(command)

    def defaultGamemodeChanged(self):
        gamemodeIndex = self.defaultGamemodeCombo.currentIndex()
        if self.editsDisabled or self.worldMeta.GameType == gamemodeIndex:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Default Gamemode'))
        with command.begin():
            self.worldMeta.GameType = gamemodeIndex
        self.editorSession.pushCommand(command)

    def worldDifficultyChanged(self):
        difficultyIndex = self.worldDifficultyCombo.currentIndex()
        if self.editsDisabled or self.worldMeta.Difficulty == difficultyIndex:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Difficulty'))
        with command.begin():
            self.worldMeta.Difficulty = difficultyIndex
        self.editorSession.pushCommand(command)

    def generatorTypeChanged(self):
        generatorName = self.generatorTypeCombo.currentText()
        generatorIndex = self.generatorTypeCombo.findText(generatorName)
        if generatorIndex != -1:
            itemData = self.generatorTypeCombo.itemData(-1)
            if itemData:
                generatorName = itemData

        if self.editsDisabled or self.worldMeta.generatorName == generatorName:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Generation Type'))
        with command.begin():
            self.worldMeta.generatorName = generatorName
        self.editorSession.pushCommand(command)

    def spawnChanged(self):
        spawn = self.spawnX.value(), self.spawnY.value(), self.spawnZ.value()
        if self.editsDisabled or spawn == self.worldMeta.Spawn:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Spawn Coordinates'))
        with command.begin():
            self.worldMeta.Spawn = spawn
        self.editorSession.pushCommand(command)

    def timeChanged(self):
        days, time = self.timeDays.value(), self.timeSlider.value()
        time = max((days * 24000 + time) - 30000, 0)
        if self.editsDisabled or self.worldMeta.DayTime == time:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change DayTime'))
        with command.begin():
            self.worldMeta.DayTime = time
        self.editorSession.pushCommand(command)

    def setTimeDawn(self):
        self.timeSlider.setValue(6000)
        self.timeChanged()

    def setTimeNoon(self):
        self.timeSlider.setValue(12000)
        self.timeChanged()

    def setTimeEvening(self):
        self.timeSlider.setValue(18000)
        self.timeChanged()

    def setTimeNight(self):
        self.timeSlider.setValue(0)
        self.timeChanged()

    def hardcoreChanged(self):
        if self.editsDisabled:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Hardcore'))
        with command.begin():
            self.worldMeta.hardcore = self.hardcoreBool.isChecked()
        self.editorSession.pushCommand(command)

    def lockedDifficultyChanged(self):
        if self.editsDisabled:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Locked Difficulty'))
        with command.begin():
            self.worldMeta.DifficultyLocked = self.lockedDifficultyBool.isChecked()
        self.editorSession.pushCommand(command)

    def allowCommandsChanged(self):
        if self.editsDisabled:
            return

        command = WorldMetaEditCommand(self.editorSession, self.tr('Change Allow Commands'))
        with command.begin():
            self.worldMeta.allowCommands = self.commandsBool.isChecked()
        self.editorSession.pushCommand(command)

class WorldMetaEditCommand(SimpleRevisionCommand):
    pass
