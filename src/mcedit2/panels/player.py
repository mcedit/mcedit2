"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import uuid

from PySide import QtGui
from PySide.QtCore import Qt

from mcedit2.command import SimpleRevisionCommand
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.widgets.nbttree.nbttreemodel import NBTTreeModel, NBTTreeList
from mcedit2.util.load_ui import load_ui
from mcedit2.util.resources import resourcePath
from mcedit2.widgets.propertylist import PropertyListModel
from mceditlib.exceptions import PlayerNotFound
from mceditlib import nbt


log = logging.getLogger(__name__)

class PlayerPropertyChangeCommand(SimpleRevisionCommand):
    pass

class NBTDataChangeCommand(SimpleRevisionCommand):
    pass

class PlayerPanel(QtGui.QWidget):
    def __init__(self, editorSession, *args, **kwargs):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: PlayerPanel
        """
        super(PlayerPanel, self).__init__(QtGui.qApp.mainWindow, *args, f=Qt.Tool, **kwargs)

        self.editorSession = editorSession
        self.selectedUUID = None

        load_ui("panels/player.ui", baseinstance=self)

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

        icon = QtGui.QIcon(resourcePath("mcedit2/assets/mcedit2/icons/edit_player.png"))
        action = QtGui.QAction(icon, "Edit Player", self)
        action.setCheckable(True)
        action.triggered.connect(self.toggleView)
        self._toggleViewAction = action

        self.editorSession.revisionChanged.connect(self.revisionDidChange)
        self.initPropertiesWidget()

        centerWidgetInScreen(self)

    def initPropertiesWidget(self):
        model = PropertyListModel(self.selectedPlayer.rootTag)
        addWidget = model.addNBTProperty

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

        self.playerPropertiesWidget.setModel(model)
        model.propertyChanged.connect(self.propertyDidChange)

    def updateNBTTree(self):
        model = NBTTreeModel(self.selectedPlayer.rootTag)
        model.dataChanged.connect(self.nbtDataDidChange)
        self.treeView.setModel(model)

    def revisionDidChange(self):
        self.initPropertiesWidget()
        self.updateNBTTree()

    def nbtDataDidChange(self, index):
        model = self.treeView.model().sourceModel()  # xxx filter model this is confusing
        parent = model.parent(index)
        item = model.getItem(index)
        if parent is not None and isinstance(parent, NBTTreeList):
            name = str(parent.tag.index(item.tag))
        else:
            name = item.tag.name

        if self.selectedUUID != "":
            text = "Change player %s NBT tag %s" % (self.selectedUUID, name)
        else:
            text = "Change single-player NBT tag %s" % name

        command = NBTDataChangeCommand(self.editorSession, text)
        with command.begin():
            self.selectedPlayer.dirty = True
            self.editorSession.worldEditor.syncToDisk()
        self.editorSession.pushCommand(command)

    def propertyDidChange(self, name, value):
        if self.selectedUUID != "":
            text = "Change player %s property %s" % (self.selectedUUID, name)
        else:
            text = "Change single-player property %s" % name

        command = PlayerPropertyChangeCommand(self.editorSession, text)
        with command.begin():
            self.selectedPlayer.dirty = True
            self.editorSession.worldEditor.syncToDisk()
        self.editorSession.pushCommand(command)

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
        UUID = self.playerListBox.itemData(index)
        self.setSelectedPlayerUUID(UUID)

    def setSelectedPlayerUUID(self, UUID):
        try:
            self.selectedUUID = UUID
        except PlayerNotFound:
            log.info("PlayerPanel: player %s not found!", UUID)
            self.treeView.setModel(None)
        else:
            self.updateNBTTree()

    @property
    def selectedPlayer(self):
        return self.editorSession.worldEditor.getPlayer(self.selectedUUID)

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
        view.centerPoint = self.selectedPlayer.Position
        view.yawPitch = self.selectedPlayer.Rotation
