"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging
import weakref

from OpenGL import GL
import numpy

from mcedit2.rendering import cubes
from mcedit2.rendering.depths import DepthOffset
from mcedit2.util import profiler
from mcedit2.util.glutils import DisplayList

log = logging.getLogger(__name__)


class RenderNode(object):

    def __init__(self, sceneNode):
        super(RenderNode, self).__init__()
        self.children = []
        self.childrenBySceneNode = {}
        self.sceneNode = sceneNode
        self.displayList = DisplayList()          # Recompiled whenever this node's scenegraph node is dirty
                                                  # or node gains or loses children
        self.childNeedsRecompile = True

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.sceneNode)

    _parent = None
    @property
    def parent(self):
        if self._parent:
            return self._parent()

    @parent.setter
    def parent(self, value):
        if value is not None:
            self._parent = weakref.ref(value)
        else:
            self._parent = None

    def addChild(self, node):
        self.children.append(node)
        self._addChild(node)

    def _addChild(self, node):
        self.childrenBySceneNode[node.sceneNode] = node
        node.parent = self
        self.displayList.invalidate()
        self.childNeedsRecompile = True
        if self.parent:
            self.parent.touch()

    def insertNode(self, index, node):
        self.children.insert(index, node)
        self._addChild(node)

    def removeChild(self, node):
        self.childrenBySceneNode.pop(node.sceneNode, None)
        self.children.remove(node)
        self.displayList.invalidate()
        node.parent = None
        self.childNeedsRecompile = True
        if self.parent:
            self.parent.touch()

    def invalidate(self):
        self.displayList.invalidate()
        self.touch()

    def touch(self):
        node = self
        while node:
            node.childNeedsRecompile = True
            node = node.parent

    def getList(self):
        return self.displayList.getList()

    def callList(self):
        self.displayList.call()

    def compile(self):
        if self.childNeedsRecompile:
            for node in self.children:
                if node.sceneNode.visible:
                    node.compile()
            self.childNeedsRecompile = False

        self.displayList.compile(self.draw)

    def draw(self):
        self.drawSelf()
        self.drawChildren()

    def drawChildren(self):
        if len(self.children):
            lists = [node.getList()
                     for node in self.children
                     if node.sceneNode.visible]
            if len(lists):
                lists = numpy.hstack(tuple(lists))
                try:
                    GL.glCallLists(lists)
                except GL.error as e:
                    log.exception("Error calling child lists: %s", e)
                    raise

    def drawSelf(self):
        pass

    def destroy(self):
        for child in self.children:
            child.destroy()
        self.displayList.destroy()

class RenderstateRenderNode(RenderNode):
    def draw(self):
        self.enter()
        self.drawChildren()
        self.exit()

    def enter(self):
        raise NotImplementedError

    def exit(self):
        raise NotImplementedError

"""
UNUSED??

class BoxRenderNode(RenderNode):
    def drawSelf(self):
        box = self.sceneNode.box
        color = self.sceneNode.color
        GL.glPolygonOffset(DepthOffset.Selection, DepthOffset.Selection)
        cubes.drawConstructionCube(box, color)

class BoxFaceRenderNode(RenderNode):
    def drawBoxFace(self, box, face, color=(0.9, 0.6, 0.2, 0.5)):
        GL.glEnable(GL.GL_BLEND)
        GL.glColor(*color)
        cubes.drawFace(box, face)

        GL.glColor(0.9, 0.6, 0.2, 0.8)
        GL.glLineWidth(2.0)
        cubes.drawFace(box, face, elementType=GL.GL_LINE_STRIP)
        GL.glDisable(GL.GL_BLEND)
"""

def updateRenderNode(renderNode):
    """

    :type renderNode: mcedit2.rendering.rendernode.RenderNode
    """
    sceneNode = renderNode.sceneNode

    if sceneNode.dirty:
        renderNode.invalidate()
        sceneNode.dirty = False
    if sceneNode.descendentChildrenChanged or sceneNode.childrenChanged:
        updateChildren(renderNode)
        sceneNode.descendentChildrenChanged = False
        sceneNode.childrenChanged = False


def createRenderNode(sceneNode):
    """

    :type sceneNode: Node
    :rtype: mcedit2.rendering.rendernode.RenderNode
    """
    renderNode = sceneNode.RenderNodeClass(sceneNode)
    updateChildren(renderNode)
    return renderNode


def updateChildren(renderNode):
    """

    :type renderNode: mcedit2.rendering.rendernode.RenderNode
    :return:
    :rtype:
    """
    sceneNode = renderNode.sceneNode
    deadChildren = []
    for renderChild in renderNode.children:
        if renderChild.sceneNode.parent is None:
            deadChildren.append(renderChild)

    for dc in deadChildren:
        renderNode.removeChild(dc)
        dc.destroy()

    for index, sceneChild in enumerate(sceneNode.children):
        renderChild = renderNode.childrenBySceneNode.get(sceneChild)
        if renderChild is None:
            renderNode.insertNode(index, createRenderNode(sceneChild))
            sceneChild.dirty = False
        else:
            updateRenderNode(renderChild)


def renderScene(renderNode):
    with profiler.context("updateRenderNode"):
        updateRenderNode(renderNode)
    with profiler.context("renderNode.compile"):
        renderNode.compile()
    with profiler.context("renderNode.callList"):
        renderNode.callList()

