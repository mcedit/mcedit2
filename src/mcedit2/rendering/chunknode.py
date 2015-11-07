"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging

from mcedit2.rendering.scenegraph import scenenode
from mcedit2.rendering.scenegraph.matrix import Translate
from mcedit2.rendering.scenegraph.scenenode import NamedChildrenNode

log = logging.getLogger(__name__)


class ChunkNode(scenenode.Node):
    def __init__(self, chunkPosition):
        """

        :param chunkPosition:
        :type chunkPosition: (int, int)
        :return:
        :rtype:
        """
        super(ChunkNode, self).__init__()
        self.chunkPosition = chunkPosition
        cx, cz = chunkPosition
        self.translate = Translate()
        self.translate.translateOffset = (cx << 4, 0, cz << 4)
        self.addState(self.translate)
        self.name = str(chunkPosition)


class ChunkGroupNode(NamedChildrenNode):
    """
    Stores chunks in a group of subnodes, each storing 4x4 chunks. Reduces the number of chunk nodes whose parent
     node must be redrawn when a chunk is added or removed.
    """
    def __init__(self):
        super(ChunkGroupNode, self).__init__()

    def getChunkArea(self, cx, cz, create=True):
        ax = cx >> 4
        az = cz >> 4
        area = self.getChild((ax, az))
        if area is None and create:
            area = NamedChildrenNode()
            area.name = "(ax=%s,az=%s)" % (ax, az)
            self.addChild((ax, az), area)
        return area

    def dropChunkArea(self, cx, cz):
        ax = cx >> 4
        az = cz >> 4
        self.removeChild((ax, az))

    def containsChunkNode(self, (cx, cz)):
        area = self.getChunkArea(cx, cz)
        if area is not None:
            return area.getChild((cx, cz)) is not None
        return False

    def getChunkNode(self, (cx, cz)):
        return self.getChunkArea(cx, cz).getChild((cx, cz))

    def addChunkNode(self, chunkNode):
        self.getChunkArea(*chunkNode.chunkPosition).addChild(chunkNode.chunkPosition, chunkNode)

    def discardChunkNode(self, cx, cz):
        area = self.getChunkArea(cx, cz, create=False)
        if area:
            area.removeChild((cx, cz))
            if 0 == len(area._children):
                self.dropChunkArea(cx, cz)
    #
    # def invalidateChunkNode(self, cx, cz, invalidLayers=None):
    #     if invalidLayers is None:
    #         invalidLayers = set(layers.Layer.AllLayers)
    #     area = self.getChunkArea(cx, cz, create=False)
    #     if area:
    #         node = area.getChild((cx, cz))
    #         if node:
    #             node.invalidLayers = invalidLayers

    def chunkPositions(self):
        for area in self._children.itervalues():
            for name in area._children:
                yield name

    def clear(self):
        super(ChunkGroupNode, self).clear()

    def setLayerVisible(self, layerName, visible):
        for area in self._children.itervalues():
            for chunkNode in area._children.itervalues():
                for node in chunkNode.children:
                    if node.layerName == layerName:
                        node.visible = visible
