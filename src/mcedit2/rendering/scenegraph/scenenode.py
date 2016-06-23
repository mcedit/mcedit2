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

    def __init__(self, name=None):
        super(Node, self).__init__()
        self._children = []
        self._dirty = True
        self._parents = []
        self.states = []
        self.name = name
        self.childrenChanged = False
        self.descendentNeedsUpdate = False

    def __repr__(self):
        return "%s(%r, visible=%s, children=%d, states=%s)" % (
            self.__class__.__name__, self.name, self.visible, len(self._children), self.states
        )

    def nested_repr(self):
        lines = []
        lines.extend(self._nested_repr(0))
        return "\n".join(lines)

    def _nested_repr(self, indent=0):
        yield indent * " " + repr(self)
        for c in self.children:
            for line in c._nested_repr(indent + 2):
                yield line

    def addState(self, obj):
        self.states.append(obj)
        obj.addParent(self)

    def removeState(self, obj):
        self.states.remove(obj)
        obj.removeParent(self)

    def addParent(self, obj):
        for parent in self._parents:
            if parent() is obj:
                return

        self._parents.append(weakref.ref(obj))

    def removeParent(self, obj):
        self._parents[:] = [p for p in self._parents
                            if p() is not obj and p() is not None]

    def hasParent(self, obj):
        for p in self._parents:
            if p() is obj:
                return True

        return False

    def childrenDidChange(self):
        node = self
        node.childrenChanged = True
        self.notifyParents()

    def notifyParents(self):
        for p in self._parents:
            parent = p()
            if parent:
                parent.descendentNeedsUpdate = True
                parent.notifyParents()

    def addChild(self, node):
        self._children.append(node)
        node.addParent(self)
        self.childrenDidChange()

    def insertChild(self, index, node):
        self._children.insert(index, node)
        node.addParent(self)
        self.childrenDidChange()

    def removeChild(self, node):
        self._children.remove(node)
        node.removeParent(self)
        self.childrenDidChange()

    def clear(self):
        for c in self._children:
            c.removeParent(self)
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
            self.notifyParents()

    _visible = True
    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        if value is self._visible:
            return

        self._visible = value
        for p in self._parents:
            parent = p()
            if parent:
                parent.dirty = True

class NamedChildrenNode(Node):
    RenderNodeClass = rendernode.RenderNode

    def __init__(self):
        super(NamedChildrenNode, self).__init__()
        self._children = {}

    def addChild(self, name, node):
        oldNode = self._children.get(name)
        if oldNode:
            oldNode.removeParent(self)
        self._children[name] = node
        node.addParent(self)
        self.childrenDidChange()

    insertChild = NotImplemented

    def removeChild(self, name):
        node = self._children.pop(name, None)
        if node:
            node.removeParent(self)
            self.childrenDidChange()

    def getChild(self, name):
        return self._children.get(name)

    def clear(self):
        for node in self.children:
            node.removeParent(self)
        self._children.clear()
        self.childrenDidChange()

    @property
    def children(self):
        return self._children.itervalues()
