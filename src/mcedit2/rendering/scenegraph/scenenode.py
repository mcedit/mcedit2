"""
    scenegraph
"""
from __future__ import absolute_import, division, print_function
import logging
import weakref

from mcedit2.rendering.scenegraph import rendernode

log = logging.getLogger(__name__)


class Node(object):
    RenderNodeClass = rendernode.RenderNode

    def __init__(self):
        super(Node, self).__init__()
        self._children = []
        self._dirty = True
        self.childrenChanged = False
        self.descendentNeedsUpdate = False

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

    def childrenDidChange(self):
        node = self
        node.childrenChanged = True
        while node.parent:
            node = node.parent
            node.descendentNeedsUpdate = True

    def addChild(self, node):
        self._children.append(node)
        node.parent = self
        self.childrenDidChange()

    def insertChild(self, index, node):
        self._children.insert(index, node)
        node.parent = self
        self.childrenDidChange()

    def removeChild(self, node):
        self._children.remove(node)
        node.parent = None
        self.childrenDidChange()

    def clear(self):
        for c in self._children:
            c.parent = None
        self.childrenDidChange()
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
                node.descendentNeedsUpdate = True

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
    RenderNodeClass = rendernode.RenderNode

    def __init__(self):
        super(NamedChildrenNode, self).__init__()
        self._children = {}

    def addChild(self, name, node):
        oldNode = self._children.get(name)
        if oldNode:
            oldNode.parent = None
        self._children[name] = node
        node.parent = self
        self.childrenDidChange()

    insertChild = NotImplemented

    def removeChild(self, name):
        node = self._children.pop(name, None)
        if node:
            node.parent = None
            self.childrenDidChange()

    def getChild(self, name):
        return self._children.get(name)

    def clear(self):
        for node in self.children:
            node.parent = None
        self._children.clear()
        self.childrenDidChange()

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


