"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging
import weakref
from contextlib import contextmanager

from OpenGL import GL
import numpy

from mcedit2.rendering import cubes
from mcedit2.rendering.depths import DepthOffsets
from mcedit2.util import profiler
from mcedit2.util.glutils import DisplayList

log = logging.getLogger(__name__)


class RenderNode(object):

    def __init__(self, sceneNode):
        super(RenderNode, self).__init__()
        self._parents = []
        self.children = []
        self.childrenBySceneNode = {}
        self.sceneNode = sceneNode
        self.displayList = DisplayList()          # Recompiled whenever this node's scenegraph node is dirty
                                                  # or node gains or loses children
        self.childNeedsRecompile = True

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.sceneNode)

    def addParent(self, obj):
        for parent in self._parents:
            if parent() is obj:
                return

        self._parents.append(weakref.ref(obj))

    def removeParent(self, obj):
        self._parents[:] = [p for p in self._parents
                            if p() is not obj and p() is not None]

    def addChild(self, node):
        self.children.append(node)
        self._addChild(node)

    def _addChild(self, node):
        self.childrenBySceneNode[node.sceneNode] = node
        node.addParent(self)
        self.displayList.invalidate()
        self.childNeedsRecompile = True
        self.notifyParents()

    def insertNode(self, index, node):
        self.children.insert(index, node)
        self._addChild(node)

    def removeChild(self, node):
        self.childrenBySceneNode.pop(node.sceneNode, None)
        self.children.remove(node)
        self.displayList.invalidate()
        node.removeParent(self)
        self.childNeedsRecompile = True
        self.notifyParents()

    def invalidate(self):
        self.displayList.invalidate()
        self.notifyParents()

    def notifyParents(self):
        for p in self._parents:
            parent = p()
            if parent:
                parent.childNeedsRecompile = True
                parent.notifyParents()

    def getList(self):
        return self.displayList.getList()

    def callList(self):
        rendernode_log("callList", self)
        self.displayList.call()

    def compile(self):
        rendernode_log("compile", self)
        if self.childNeedsRecompile:
            for node in self.children:
                if node.sceneNode.visible:
                    node.compile()
            self.childNeedsRecompile = False

        for state in self.sceneNode.states:
            state.compile()
        self.displayList.compile(self.draw)

    @contextmanager
    def enterStates(self):
        for state in self.sceneNode.states:
            state.enter()
        try:
            yield
        finally:
            for state in reversed(self.sceneNode.states):
                state.exit()

    def draw(self):
        rendernode_log("draw", self)
        with self.enterStates():
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

def createRenderNode(sceneNode):
    """
    Create and return a renderNode that renders the given sceneNode and all of its
    children.

    Calls updateRenderNode to recursively create child renderNodes for each descendent of
    sceneNode.

    :type sceneNode: Node
    :rtype: mcedit2.rendering.rendernode.RenderNode
    """
    try:
        renderNode = sceneNode.RenderNodeClass(sceneNode)
        updateRenderNode(renderNode)
        return renderNode
    except Exception:
        log.error("Failed to create render node for %s with class %s", sceneNode, sceneNode.RenderNodeClass)
        raise

logUpdateRenderNode = False

rendernode_file = None

def rendernode_log(msg, node, *a):
    if not logUpdateRenderNode:
        return

    global rendernode_file
    if rendernode_file is None:
        rendernode_file = open("rendernode.log", "w")

    if len(a):
        msg = msg % a

    msg = str(node) + ": " + msg

    rendernode_file.write(msg)
    rendernode_file.write("\n")


def updateRenderNode(renderNode):
    """
    Synchronize the state of a renderNode and its childre with its scene node.

    If the sceneNode that owns this renderNode is dirty, invalidates the renderNode.
    Then, updateChildren is called to add or remove renderNodes if the sceneNode had
    children added or removed.

    As an optimization, each sceneNode keeps track of whether one of its descendents
    was dirtied or had children added or removed. This allows us to skip the recursive
    updateRenderNode call if it is not needed.


    :type renderNode: mcedit2.rendering.rendernode.RenderNode
    """
    sceneNode = renderNode.sceneNode
    rendernode_log("updateRenderNode", sceneNode)

    if sceneNode.dirty:
        rendernode_log("dirty", sceneNode)
        renderNode.invalidate()
        sceneNode.dirty = False

    if sceneNode.childrenChanged:
        rendernode_log("childrenChanged", sceneNode)
        updateChildren(renderNode)
        sceneNode.childrenChanged = False

    if sceneNode.descendentNeedsUpdate:
        rendernode_log("descendentNeedsUpdate", sceneNode)
        for renderChild in renderNode.children:
            updateRenderNode(renderChild)
        sceneNode.descendentNeedsUpdate = False


def updateChildren(renderNode):
    """
    Compare the children of this renderNode to the children of its sceneNode. Create
    renderNodes for any new sceneNodes, and remove any renderNodes whose
    sceneNode is no longer a child of this node's sceneNode.

    :type renderNode: mcedit2.rendering.rendernode.RenderNode
    :return:
    :rtype:
    """
    sceneNode = renderNode.sceneNode
    orphans = []
    rendernode_log("childrenChanged", sceneNode)

    # Find renderNode children whose sceneNode is no longer this node's sceneNode
    for renderChild in renderNode.children:
        if not renderChild.sceneNode.hasParent(sceneNode):
            rendernode_log("orphaned", renderChild)
            orphans.append(renderChild)

    for node in orphans:
        renderNode.removeChild(node)
        node.destroy()

    # Find sceneNode children who do not have a renderNode as a child of this renderNode
    for index, sceneChild in enumerate(sceneNode.children):
        renderChild = renderNode.childrenBySceneNode.get(sceneChild)
        if renderChild is None:
            renderChild = createRenderNode(sceneChild)
            renderNode.insertNode(index, renderChild)
            sceneChild.dirty = False
            rendernode_log("new child", renderChild)


def renderScene(renderNode):
    with profiler.context("updateRenderNode"):
        updateRenderNode(renderNode)
    with profiler.context("renderNode.compile"):
        renderNode.compile()
    with profiler.context("renderNode.callList"):
        renderNode.callList()

    global rendernode_file, logUpdateRenderNode
    logUpdateRenderNode = False
    if rendernode_file:
        rendernode_file.close()
        rendernode_file = None


