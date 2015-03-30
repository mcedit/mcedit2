"""
    scenegraph
"""
from __future__ import absolute_import, division, print_function
import logging
import weakref

from mcedit2.rendering import rendergraph


log = logging.getLogger(__name__)

from OpenGL import GL

class Node(object):
    RenderNodeClass = rendergraph.RenderNode

    def __init__(self):
        super(Node, self).__init__()
        self._children = []
        self._dirty = True
        self.childrenChanged = False
        self.descendentChildrenChanged = False

    def __repr__(self):
        return "%s(visible=%s, children=%d)" % (self.__class__.__name__, self.visible, len(self._children))

    _parent = None
    @property
    def parent(self):
        if self._parent is not None:
            return self._parent()

    @parent.setter
    def parent(self, value):
        if value is not None:
            self._parent = weakref.ref(value)
        else:
            self._parent = None

    def touchChildren(self):
        node = self
        node.childrenChanged = True
        while node.parent:
            node = node.parent
            node.descendentChildrenChanged = True

    def addChild(self, node):
        self._children.append(node)
        node.parent = self
        self.touchChildren()

    def insertChild(self, index, node):
        self._children.insert(index, node)
        node.parent = self
        self.touchChildren()

    def removeChild(self, node):
        self._children.remove(node)
        node.parent = None
        self.touchChildren()

    def clear(self):
        for c in self._children:
            c.parent = None
        self.touchChildren()
        self._children[:] = []

    def childCount(self):
        return len(self._children)

    @property
    def children(self):
        return iter(self._children)

    @property
    def dirty(self):
        return self._dirty

    @dirty.setter
    def dirty(self, value):
        self._dirty = value
        if value:
            node = self
            while node.parent:
                node = node.parent
                node.descendentChildrenChanged = True

    _visible = True
    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        if value is self._visible:
            return

        self._visible = value
        if self.parent:
            self.parent.dirty = True

class NamedChildrenNode(Node):
    RenderNodeClass = rendergraph.RenderNode

    def __init__(self):
        super(NamedChildrenNode, self).__init__()
        self._children = {}

    def addChild(self, name, node):
        oldNode = self._children.get(name)
        if oldNode:
            oldNode.parent = None
        self._children[name] = node
        node.parent = self
        self.touchChildren()

    insertChild = NotImplemented

    def removeChild(self, name):
        node = self._children.pop(name, None)
        if node:
            node.parent = None
            self.touchChildren()

    def getChild(self, name):
        return self._children.get(name)

    def clear(self):
        for node in self.children:
            node.parent = None
        self._children.clear()
        self.touchChildren()

    @property
    def children(self):
        return self._children.itervalues()


class RenderstateNode(Node):
    def __init__(self, nodeClass):
        super(RenderstateNode, self).__init__()
        self.RenderNodeClass = nodeClass

    def __repr__(self):
        return "RenderstateNode(nodeClass=%r, visible=%s, children=%d)" % (self.RenderNodeClass.__name__,
                                                                           self.visible, len(self._children))


class TextureAtlasNode(Node):
    RenderNodeClass = rendergraph.TextureAtlasRenderNode

    def __init__(self, textureAtlas):
        super(TextureAtlasNode, self).__init__()
        self.textureAtlas = textureAtlas


class TranslateNode(Node):
    RenderNodeClass = rendergraph.TranslateRenderNode

    def __init__(self, translateOffset=(0., 0., 0.)):
        super(TranslateNode, self).__init__()
        self._translateOffset = translateOffset

    @property
    def translateOffset(self):
        return self._translateOffset

    @translateOffset.setter
    def translateOffset(self, value):
        self._translateOffset = value
        self.dirty = True


class DepthMaskNode(Node):
    RenderNodeClass = rendergraph.DepthMaskRenderNode
    mask = False


class ClearNode(Node):
    RenderNodeClass = rendergraph.ClearRenderNode

    def __init__(self, clearColor=(0, 0, 0, 1)):
        super(ClearNode, self).__init__()
        self.clearColor = clearColor

class OrthoNode(Node):
    RenderNodeClass = rendergraph.OrthoRenderNode

    def __init__(self, size=(1, 1)):
        super(OrthoNode, self).__init__()
        self._size = size

    @property
    def size(self):
        return self._size

    @size.setter
    def size(self, value):
        self._size = value
        self.dirty = True


class VertexNode(Node):
    RenderNodeClass = rendergraph.VertexRenderNode

    def __init__(self, vertexArrays):
        """

        :type vertexArrays: VertexArrayBuffer
        """
        super(VertexNode, self).__init__()
        self.vertexArrays = vertexArrays


class MatrixRenderNode(rendergraph.RenderstateRenderNode):
    def enter(self):
        projection = self.sceneNode.projection
        if projection is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glPushMatrix()
            GL.glLoadMatrixd(projection.data())

        modelview = self.sceneNode.modelview
        if modelview is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glPushMatrix()
            GL.glLoadMatrixd(modelview.data())

    def exit(self):
        if self.sceneNode.projection is not None:
            GL.glMatrixMode(GL.GL_PROJECTION)
            GL.glPopMatrix()
        if self.sceneNode.modelview is not None:
            GL.glMatrixMode(GL.GL_MODELVIEW)
            GL.glPopMatrix()


class MatrixNode(Node):
    RenderNodeClass = MatrixRenderNode

    _projection = None
    @property
    def projection(self):
        """

        :return:
        :rtype: QMatrix4x4
        """
        return self._projection

    @projection.setter
    def projection(self, value):
        """

        :type value: QMatrix4x4
        """
        self._projection = value
        self.dirty = True

    _modelview = None
    @property
    def modelview(self):
        """

        :return:
        :rtype: QMatrix4x4
        """
        return self._modelview

    @modelview.setter
    def modelview(self, value):
        """

        :type value: QMatrix4x4
        """
        self._modelview = value
        self.dirty = True

class DepthOffsetNode(Node):
    RenderNodeClass = rendergraph.DepthOffsetRenderNode
    def __init__(self, depthOffset):
        super(DepthOffsetNode, self).__init__()
        self.depthOffset = depthOffset
