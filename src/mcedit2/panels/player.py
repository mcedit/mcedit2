"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide import QtGui
from PySide.QtCore import Qt
from mcedit2.command import SimpleRevisionCommand
from mcedit2.nbt_treemodel import NBTTreeModel, NBTFilterProxyModel
from mcedit2.util.load_ui import load_ui
from mcedit2.util.resources import resourcePath
from mceditlib.exceptions import PlayerNotFound

log = logging.getLogger(__name__)


class PlayerPanel(QtGui.QWidget):
    name = "Edit Player"
    iconName = "edit_player"

    def __init__(self, editorSession, *args, **kwargs):
        """

        :type editorSession: mcedit2.editorsession.EditorSession
        :rtype: PlayerPanel
        """
        super(PlayerPanel, self).__init__(*args, **kwargs)
        self.editorSession = editorSession
        load_ui("panels/player.ui", baseinstance=self)

        self.movePlayerButton.clicked.connect(self.movePlayerToCamera)
        self.viewPlayerButton.clicked.connect(self.showPlayerView)

        for name in editorSession.worldEditor.listPlayers():  # xxx live update?
            if name == "":
                displayName = "[Single-player]"
            else:
                displayName = name
            self.playerListBox.addItem(displayName, name)

        self.playerListBox.currentIndexChanged[int].connect(self.setSelectedPlayer)

        self.selectedPlayer = None

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

    def setSelectedPlayer(self, index):
        name = self.playerListBox.itemData(index)
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
