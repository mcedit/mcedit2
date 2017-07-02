"""
    playermesh
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import os

import numpy
from OpenGL import GL

from mcedit2.rendering.chunkmeshes.entity.models import cookedModels
from mcedit2.rendering.chunkmeshes.entitymesh import entityModelNode
from mcedit2.rendering.scenegraph.misc import Enable
from mcedit2.rendering.scenegraph.scenenode import Node
from mcedit2.util import glutils
from mcedit2.util.load_png import loadPNGTexture, loadPNGFile
from mcedit2.util.player_server import PlayerDataCache
from mceditlib.nbt import NBTFormatError

log = logging.getLogger(__name__)


class PlayerNode(Node):
    def __init__(self, playerRef):
        super(PlayerNode, self).__init__()
        self.playerRef = playerRef
        self.entityNode = None

        def _callback(result, error):
            if result:
                self.texturePath = result['texturePath']
            else:
                self.texturePath = None
            if error:
                log.info("Error getting player info: %s", error)

        PlayerDataCache.getPlayerInfo(playerRef.UUID, _callback)

    _texturePath = None

    @property
    def texturePath(self):
        return self._texturePath

    @texturePath.setter
    def texturePath(self, value):
        self._texturePath = value
        if value is not None:
            log.info("Got texture path: %s", value)
            try:
                w, h, modelImage = loadPNGFile(value)
                modelImage = modelImage[::-1]
                # modelTex = loadPNGTexture(value)
                if h == 32:
                    w, h, modelImage = fixupTextureImage(modelImage)

                tex = glutils.Texture(name=os.path.basename(value), image=modelImage.ravel(),
                                      width=w, height=h)
            except Exception as e:
                log.warn("Error while loading player texture: %r", e)
                return

            if self.entityNode:
                self.removeChild(self.entityNode)

            self.entityNode = entityModelNode(self.playerRef, cookedModels['MCEDIT_Player'], tex)
            self.entityNode.addState(Enable(GL.GL_ALPHA_TEST))
            self.addChild(self.entityNode)
        else:
            log.info("Did not get texture path.")


def fixupTextureImage(modelImage):
    w = 64
    h = 64
    oh, ow, b = modelImage.shape
    
    newImage = numpy.zeros((h, w, b), dtype='uint8')
    newImage[:oh, :ow, :] = modelImage
    #newImage = newImage[::-1, :, :]

    def drawImage(x1, y1, x2, y2, sx1, sy1, sx2, sy2):
        def _slice(a, b):
            if a > b:
                return slice(a-1, b-1, -1)
            else:
                return slice(a, b)
        newImage[_slice(y1, y2), _slice(x1, x2)] = newImage[_slice(sy1, sy2), _slice(sx1, sx2)]

    drawImage(24, 48, 20, 52, 4, 16, 8, 20)
    drawImage(28, 48, 24, 52, 8, 16, 12, 20)
    drawImage(20, 52, 16, 64, 8, 20, 12, 32)
    drawImage(24, 52, 20, 64, 4, 20, 8, 32)
    drawImage(28, 52, 24, 64, 0, 20, 4, 32)
    drawImage(32, 52, 28, 64, 12, 20, 16, 32)
    drawImage(40, 48, 36, 52, 44, 16, 48, 20)
    drawImage(44, 48, 40, 52, 48, 16, 52, 20)
    drawImage(36, 52, 32, 64, 48, 20, 52, 32)
    drawImage(40, 52, 36, 64, 44, 20, 48, 32)
    drawImage(44, 52, 40, 64, 40, 20, 44, 32)
    drawImage(48, 52, 44, 64, 52, 20, 56, 32)

    #newImage = newImage[::-1, :, :]
    # }
    #
    # graphics.dispose();
    # this.imageData = ((DataBufferInt)bufferedimage.getRaster().getDataBuffer()).getData();
    # this.setAreaOpaque(0, 0, 32, 16);
    # this.setAreaTransparent(32, 0, 64, 32);
    # this.setAreaOpaque(0, 16, 64, 32);
    # this.setAreaTransparent(0, 32, 16, 48);
    # this.setAreaTransparent(16, 32, 40, 48);
    # this.setAreaTransparent(40, 32, 56, 48);
    # this.setAreaTransparent(0, 48, 16, 64);
    # this.setAreaOpaque(16, 48, 48, 64);
    # this.setAreaTransparent(48, 48, 64, 64);
    # return bufferedimage;
    
    return w, h, newImage

class PlayersNode(Node):
    def __init__(self, dimension):
        """

        Parameters
        ----------
        dimension : mceditlib.worldeditor.WorldEditorDimension
        """
        super(PlayersNode, self).__init__()

        playerNodes = []
        if not hasattr(dimension, 'worldEditor'):
            # gross, dimension may be a MaskLevel
            return

        for playerName in dimension.worldEditor.listPlayers():
            try:
                player = dimension.worldEditor.getPlayer(playerName)
            except NBTFormatError:
                continue
            if player.Dimension == dimension.dimNo:
                if player.UUID is None:
                    log.warning("Player %s has no UUID tags", playerName)
                else:
                    playerNodes.append(PlayerNode(player))

        for node in playerNodes:
            self.addChild(node)
