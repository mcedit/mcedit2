"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import uuid
import os

from PySide import QtGui
from PySide.QtCore import Qt
import itertools

from mcedit2.command import SimpleRevisionCommand
from mceditlib.util.lazyprop import weakrefprop
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.widgets.inventory import InventoryView, InventoryItemModel, InventoryEditor
from mcedit2.widgets.layout import Row
from mcedit2.widgets.nbttree.nbttreemodel import NBTTreeModel
from mcedit2.util.load_ui import load_ui
from mcedit2.util.resources import resourcePath
from mcedit2.widgets.propertylist import PropertyListModel
from mceditlib.exceptions import PlayerNotFound


log = logging.getLogger(__name__)

def playerSlotLayout():
    layout = [(x, 0, 100+x) for x in range(4)]  # equipment
    layout += [(x, y+1, x+9*y+9) for x, y in itertools.product(range(9), range(3))]  # inventory
    layout += [(x, 4, x) for x in range(9)]  # hotbar
    return layout

PLAYER_SLOT_LAYOUT = playerSlotLayout()

class PlayerPropertyChangeCommand(SimpleRevisionCommand):
    pass

class PlayerPanel(QtGui.QWidget):
    def __init__(self, editorSession):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: PlayerPanel
        """
        super(PlayerPanel, self).__init__(QtGui.qApp.mainWindow, f=Qt.Tool)

        self.editorSession = editorSession
        self.selectedUUID = None

        load_ui("panels/player.ui", baseinstance=self)

        self.inventoryEditor = InventoryEditor(PLAYER_SLOT_LAYOUT)
        self.inventoryGroupBox.setLayout(Row(self.inventoryEditor))

        self.movePlayerButton.clicked.connect(self.movePlayerToCamera)
        self.viewPlayerButton.clicked.connect(self.showPlayerView)
        playerUUIDs = list(editorSession.worldEditor.listPlayers())
        try:
            sp = editorSession.worldEditor.getPlayer("")
            singlePlayerUUID = sp.UUID
        except PlayerNotFound:
            log.info("No single-player.")
            singlePlayerUUID = None
        except KeyError:
            log.info("Failed to get single-player UUID.")
            singlePlayerUUID = None

        if "" in playerUUIDs:
            # Move singleplayer to beginning of list
            playerUUIDs.remove("")
            playerUUIDs.insert(0, "")

        for UUID in playerUUIDs:  # xxx live update?
            if UUID == "":
                displayName = "[Single-player](%s)" % singlePlayerUUID
            else:
                displayName = UUID  # xxx mojang api here
                try:
                    UUID = uuid.UUID(hex=UUID)
                    if UUID == singlePlayerUUID:
                        displayName = "[Multiplayer](%s)" % singlePlayerUUID
                except ValueError:  # badly formed uuid?
                    log.warn("Could not get a UUID from %s", UUID)
                    continue

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

        self.nbtEditor.editorSession = self.editorSession

        centerWidgetInScreen(self)

    editorSession = weakrefprop()

    def initPropertiesWidget(self):
        if self.selectedPlayer is None:
            self.playerPropertiesWidget.setModel(None)
            return

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
        self.nbtEditor.undoCommandPrefixText = ("Player %s: " % self.selectedUUID) if self.selectedUUID else "Single-player: "
        self.nbtEditor.setRootTagRef(self.selectedPlayer, os.name == 'posix')   # Workround for bug 53

    def updateInventory(self):
        self.inventoryEditor.editorSession = self.editorSession
        self.inventoryEditor.inventoryRef = self.selectedPlayer.Inventory

    def revisionDidChange(self):
        self.initPropertiesWidget()
        self.updateNBTTree()

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
            
    def closeEvent(self, event):
        self.toggleView()

    def toggleViewAction(self):
        return self._toggleViewAction

    def setSelectedPlayerIndex(self, index):
        UUID = self.playerListBox.itemData(index)
        self.setSelectedPlayerUUID(UUID)

    def setSelectedPlayerUUID(self, UUID):
        self.selectedUUID = UUID
        self.updateNBTTree()
        self.updateInventory()

    @property
    def selectedPlayer(self):
        try:
            return self.editorSession.worldEditor.getPlayer(self.selectedUUID)
        except PlayerNotFound:
            log.info("PlayerPanel: player %s not found!", self.selectedUUID)

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
