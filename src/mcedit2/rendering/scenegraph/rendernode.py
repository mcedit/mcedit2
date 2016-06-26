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

DEBUG_NO_DISPLAYLISTS = False

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

    if DEBUG_NO_DISPLAYLISTS:
        def callList(self):
            with self.enterStates():
                self.drawSelf()
                self.debugDrawChildren()
    else:
        def callList(self):
            self.displayList.call()

    def compile(self):
        if self.childNeedsRecompile:
            for node in self.children:
                node.compile()
            self.childNeedsRecompile = False

        for state in self.sceneNode.states:
            state.compile()

        if not DEBUG_NO_DISPLAYLISTS:
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
        with self.enterStates():
            self.drawSelf()
            self.callChildren()

    def callChildren(self):
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

    def debugDrawChildren(self):
        if len(self.children):
            for node in self.children:
                node.callList()


    def drawSelf(self):
        pass

    def dealloc(self):
        for child in self.children:
            child.dealloc()
        self.displayList.dealloc()

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


def updateRenderNode(renderNode):
    """
    Synchronize the state of a renderNode and its children with its scene node.

    If the sceneNode that owns this renderNode is dirty, invalidates the renderNode.
    Then, updateChildren is called to add or remove renderNodes if the sceneNode had
    children added or removed.

    As an optimization, each sceneNode keeps track of whether one of its descendents
    was dirtied or had children added or removed. This allows us to skip the recursive
    updateRenderNode call if it is not needed.


    :type renderNode: mcedit2.rendering.rendernode.RenderNode
    """
    sceneNode = renderNode.sceneNode

    if sceneNode.dirty:
        renderNode.invalidate()
        sceneNode.dirty = False

    if sceneNode.childrenChanged:
        updateChildren(renderNode)
        sceneNode.childrenChanged = False

    if sceneNode.descendentNeedsUpdate:
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

    # Find renderNode children whose sceneNode is no longer this node's sceneNode
    for renderChild in renderNode.children:
        if not renderChild.sceneNode.hasParent(sceneNode):
            orphans.append(renderChild)

    for node in orphans:
        renderNode.removeChild(node)
        node.dealloc()

    # Find sceneNode children who do not have a renderNode as a child of this renderNode
    for index, sceneChild in enumerate(sceneNode.children):
        renderChild = renderNode.childrenBySceneNode.get(sceneChild)
        if renderChild is None:
            # A previously rendered sceneNode that was removed from the graph
            # may be added back in, and will think its children don't need
            # to have renderNodes recreated.
            # Force createRenderNode to recurse into the sceneNode and check for
            # missing children.
            sceneChild.childrenChanged = True

            renderNode.insertNode(index, createRenderNode(sceneChild))
            sceneChild.dirty = False



def printStats(renderNode):
    listCount = 0
    singleChildNodes = set()
    stack = [renderNode]
    seen = set()
    while len(stack):
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)

        listCount += 1
        if len(node.children) == 1:
            singleChildNodes.add(node)
        stack.extend(node.children)

    print("List count:", listCount)
    print("Nodes with single children: ")
    from pprint import pprint
    pprint(sorted(singleChildNodes))

def renderScene(renderNode):
    with profiler.context("updateRenderNode"):
        updateRenderNode(renderNode)
    with profiler.context("renderNode.compile"):
        renderNode.compile()
    with profiler.context("renderNode.callList"):
        renderNode.callList()

