"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import uuid
from PySide import QtGui
from PySide.QtCore import Qt
from mcedit2.command import SimpleRevisionCommand
from mcedit2.nbt_treemodel import NBTTreeModel, NBTFilterProxyModel
from mcedit2.util.load_ui import load_ui
from mcedit2.util.resources import resourcePath
from mceditlib.exceptions import PlayerNotFound
from mceditlib import nbt

log = logging.getLogger(__name__)


class PlayerPanel(QtGui.QWidget):
    def __init__(self, editorSession, *args, **kwargs):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: PlayerPanel
        """
        super(PlayerPanel, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        load_ui("panels/player.ui", baseinstance=self)
        self.treeWidgets = []

        self.movePlayerButton.clicked.connect(self.movePlayerToCamera)
        self.viewPlayerButton.clicked.connect(self.showPlayerView)

        playerUUIDs = list(editorSession.worldEditor.listPlayers())
        try:
            sp = editorSession.worldEditor.getPlayer("")
            singlePlayerUUID = sp.UUID
        except PlayerNotFound:
            singlePlayerUUID = None

        for UUID in playerUUIDs:  # xxx live update?
            if UUID == "":
                displayName = "[Single-player](%s)" % singlePlayerUUID
            else:
                displayName = UUID  # xxx mojang api here
                UUID = uuid.UUID(hex=UUID)
                if UUID == singlePlayerUUID:
                    continue  # Don't count single-player twice when it appears under playerData/
            self.playerListBox.addItem(displayName, UUID)

        self.playerListBox.currentIndexChanged[int].connect(self.setSelectedPlayerIndex)
        if len(playerUUIDs):
            self.setSelectedPlayerIndex(0)

        # for playerUUID in editorSession.worldEditor.listPlayers():
        #     self.setSelectedPlayer(playerUUID)
        #     break

        icon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/edit_player.png"))
        action = QtGui.QAction(icon, "Edit Player", self)
        action.setCheckable(True)
        action.triggered.connect(self.toggleView)
        self._toggleViewAction = action

    def toggleView(self):
        if self.isHidden():
            self.show()
            self._toggleViewAction.setChecked(True)
        else:
            self.hide()
            self._toggleViewAction.setChecked(False)

    def toggleViewAction(self):
        return self._toggleViewAction

    def setSelectedPlayerIndex(self, index):
        name = self.playerListBox.itemData(index)
        self.setSelectedPlayer(name)

    def setSelectedPlayer(self, name):
        try:
            self.selectedPlayer = player = self.editorSession.worldEditor.getPlayer(name)
        except PlayerNotFound:
            log.info("PlayerPanel: player %s not found!", name)
            self.treeView.setModel(None)
        else:
            model = NBTTreeModel(player.rootTag)
            proxyModel = NBTFilterProxyModel(self)
            proxyModel.setSourceModel(model)
            proxyModel.setDynamicSortFilter(True)

            self.treeView.setModel(proxyModel)
            self.treeView.sortByColumn(0, Qt.AscendingOrder)
            self.updatePlayerTab()

    def updatePlayerTab(self):
        treeWidget = self.playerAttributesWidget
        treeWidget.clear()
        self.treeWidgets[:] = []

        player = self.selectedPlayer
        rootTag = player.rootTag

        def addWidget(tagName, valueType=None, min=None, max=None):
            if valueType is None:
                valueType = int
            if tagName in rootTag:
                tag = rootTag[tagName]
                if tag.tagID == nbt.ID_BYTE:
                    tagMin = -(1 << 7)
                    tagMax = (1 << 7) - 1
                elif tag.tagID == nbt.ID_SHORT:
                    tagMin = -(1 << 15)
                    tagMax = (1 << 15) - 1
                elif tag.tagID == nbt.ID_INT:
                    tagMin = -(1 << 31)
                    tagMax = (1 << 31) - 1
                else:  # tag.tagID == nbt.ID_LONG, ID_FLOAT, ID_DOUBLE
                    # tagMin = -(1 << 63)  # xxxx 64-bit spinbox
                    # tagMax = (1 << 63) - 1
                    tagMin = -(1 << 31)
                    tagMax = (1 << 31) - 1

                if min is None:
                    min = tagMin
                if max is None:
                    max = tagMax

                item = QtGui.QTreeWidgetItem()
                item.setText(0, self.tr(tagName))
                treeWidget.addTopLevelItem(item)

                if valueType is int:
                    valueWidget = QtGui.QSpinBox()
                    valueWidget.setMinimum(min)
                    valueWidget.setMaximum(max)
                    valueWidget.setValue(rootTag[tagName].value)
                    valueWidget.changedHandler = self.treeWidgetChangedHandler(tagName)
                    valueWidget.valueChanged.connect(valueWidget.changedHandler)

                elif valueType is float:
                    valueWidget = QtGui.QDoubleSpinBox()
                    valueWidget.setMinimum(min)
                    valueWidget.setMaximum(max)
                    valueWidget.setValue(rootTag[tagName].value)
                    valueWidget.changedHandler = self.treeWidgetChangedHandler(tagName)
                    valueWidget.valueChanged.connect(valueWidget.changedHandler)

                elif valueType is bool:
                    valueWidget = QtGui.QCheckBox()
                    valueWidget.setChecked(rootTag[tagName].value)
                    valueWidget.changedHandler = self.treeWidgetChangedHandler(tagName)
                    valueWidget.toggled.connect(valueWidget.changedHandler)

                elif isinstance(valueType, list):  # Choice list
                    valueWidget = QtGui.QComboBox()
                    choiceValues = []
                    for choice in valueType:
                        value, name = choice
                        choiceValues.append(value)
                        valueWidget.addItem(name, value)

                    currentValue = rootTag[tagName].value
                    try:
                        currentIndex = choiceValues.index(currentValue)
                        valueWidget.setCurrentIndex(currentIndex)
                    except IndexError:
                        valueWidget.addItem("UNKNOWN VALUE %s" % currentValue, currentValue)

                    valueWidget.changedHandler = self.treeWidgetChoiceChangedHandler(tagName, valueType)
                    valueWidget.currentIndexChanged.connect(valueWidget.changedHandler)

                elif valueType is unicode:
                    valueWidget = QtGui.QPlainTextEdit()
                    valueWidget.setPlainText(rootTag[tagName].value)
                    valueWidget.changedHandler = self.treeWidgetChangedHandler(tagName)
                    valueWidget.textChanged.connect(valueWidget.changedHandler)

                else:
                    raise TypeError("Can't create attribute widgets for %s yet" % valueType)

                treeWidget.setItemWidget(item, 1, valueWidget)


                self.treeWidgets.append(valueWidget)  # QTreeWidget crashes if its itemWidget isn't retained by Python
                # treeWidget.setItemWidget(item, 0, QtGui.QLabel("BLAH"))

        addWidget("AbsorptionAmount")
        addWidget("Air")
        addWidget("DeathTime")
        addWidget("Dimension")
        addWidget("FallDistance", valueType=float)
        addWidget("Fire")
        addWidget("foodExhaustionLevel", valueType=float)
        addWidget("foodLevel")
        addWidget("foodSaturationLevel", valueType=float)
        addWidget("foodTickTimer")
        addWidget("HealF", valueType=float)
        addWidget("Health")
        addWidget("HurtByTimestamp")
        addWidget("HurtTime")
        addWidget("Invulnerable", bool)
        addWidget("OnGround", bool)
        addWidget("playerGameType", [(0, "Survival"), (1, "Creative"), (2, "Adventure")])
        addWidget("PortalCooldown")
        addWidget("Score")
        addWidget("SelectedItemSlot")  # xxx inventory
        addWidget("Sleeping", bool)
        addWidget("SleepTimer")
        addWidget("XpLevel")
        addWidget("XpP", float)
        addWidget("XpSeed")
        addWidget("XpTotal")





    def treeWidgetChangedHandler(self, name):
        def _changed(value):
            self.selectedPlayer.rootTag[name].value = value
        return _changed

    def treeWidgetChoiceChangedHandler(self, name, choices):
        def _changed(index):
            self.selectedPlayer.rootTag[name].value = choices[index][0]
        return _changed

    def movePlayerToCamera(self):
        view = self.editorSession.editorTab.currentView()
        if view.viewID == "Cam":
            command = SimpleRevisionCommand(self.editorSession, "Move Player")
            with command.begin():
                self.selectedPlayer.Position = view.centerPoint
                try:
                    self.selectedPlayer.Rotation = view.yawPitch
                except AttributeError:
                    pass

                self.selectedPlayer.dirty = True  # xxx do in AnvilPlayerRef
            self.editorSession.pushCommand(command)
        else:
            raise ValueError("Current view is not camera view.")


    def showPlayerView(self):
        self.editorSession.editorTab.showCameraView()
        view = self.editorSession.editorTab.cameraView
        view.setPerspective(False)
        view = self.editorSession.editorTab.currentView()
        view.centerPoint = self.selectedPlayer.Position
        view.yawPitch = self.selectedPlayer.Rotation
