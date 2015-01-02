"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from PySide.QtCore import Qt
from mcedit2.command import SimpleRevisionCommand
from mcedit2.editortools import EditorTool
from mcedit2.nbt_treemodel import NBTTreeModel, NBTFilterProxyModel
from mcedit2.util.load_ui import load_ui

log = logging.getLogger(__name__)


class PlayerTool(EditorTool):
    name = "Edit Player"
    iconName = "edit_player"

    def __init__(self, editorSession, *args, **kwargs):
        """

        :type editorSession: EditorSession
        """
        super(PlayerTool, self).__init__(editorSession, *args, **kwargs)

        self.toolWidget = load_ui("editortools/edit_player.ui")

        self.toolWidget.movePlayerButton.clicked.connect(self.movePlayerToCamera)
        self.toolWidget.viewPlayerButton.clicked.connect(self.showPlayerView)

        for name in editorSession.worldEditor.listPlayers():  # xxx live update?
            self.toolWidget.playerListBox.addItem(name)

        self.toolWidget.playerListBox.currentIndexChanged[str].connect(self.setSelectedPlayer)

        self.selectedPlayer = None

        for playerUUID in editorSession.worldEditor.listPlayers():
            self.setSelectedPlayer(playerUUID)
            break

    def setSelectedPlayer(self, name):
        self.selectedPlayer = player = self.editorSession.worldEditor.getPlayer(name)

        model = NBTTreeModel(player.rootTag)
        proxyModel = NBTFilterProxyModel(self)
        proxyModel.setSourceModel(model)
        proxyModel.setDynamicSortFilter(True)

        self.toolWidget.treeView.setModel(proxyModel)
        self.toolWidget.treeView.sortByColumn(0, Qt.AscendingOrder)

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
        view = self.editorSession.editorTab.currentView()
        view.centerPoint = self.selectedPlayer.Position
        view.yawPitch = self.selectedPlayer.Rotation
