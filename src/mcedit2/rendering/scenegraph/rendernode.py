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
from mcedit2.util import glutils
from mcedit2.util.glutils import DisplayList, gl

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

class BindTextureRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_ENABLE_BIT | GL.GL_TEXTURE_BIT)
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        scale = self.sceneNode.scale
        if scale is not None:
            GL.glScale(*scale)
        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        self.sceneNode.texture.bind()

    def exit(self):
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPopMatrix()
        GL.glPopAttrib()



class TextureAtlasRenderNode(RenderstateRenderNode):
    def enter(self):
        if self.sceneNode.textureAtlas is None:
            return

        GL.glColor(1., 1., 1., 1.)
        textureAtlas = self.sceneNode.textureAtlas
        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_TEXTURE_2D)
        textureAtlas.bindTerrain()

        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glScale(1. / textureAtlas.width, 1. / textureAtlas.height, 1.)

        glutils.glActiveTexture(GL.GL_TEXTURE1)
        GL.glEnable(GL.GL_TEXTURE_2D)
        textureAtlas.bindLight()

        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glScale(1. / 16, 1. / 16, 1.)

        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glEnable(GL.GL_CULL_FACE)

    def exit(self):
        if self.sceneNode.textureAtlas is None:
            return

        GL.glDisable(GL.GL_CULL_FACE)
        glutils.glActiveTexture(GL.GL_TEXTURE1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, 0)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPopMatrix()

        glutils.glActiveTexture(GL.GL_TEXTURE0)
        GL.glDisable(GL.GL_TEXTURE_2D)
        GL.glMatrixMode(GL.GL_TEXTURE)
        GL.glPopMatrix()


class TranslateRenderNode(RenderstateRenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: TranslateNode
        """
        super(TranslateRenderNode, self).__init__(sceneNode)

    def __repr__(self):
        return "TranslateRenderNode(%s)" % (self.sceneNode.translateOffset,)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glTranslate(*self.sceneNode.translateOffset)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()

class RotateRenderNode(RenderstateRenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: TranslateNode
        """
        super(RotateRenderNode, self).__init__(sceneNode)

    def __repr__(self):
        return "RotateRenderNode(%s, %s)" % (self.sceneNode.degrees,self.sceneNode.axis)

    def enter(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPushMatrix()
        GL.glRotate(self.sceneNode.degrees, *self.sceneNode.axis)

    def exit(self):
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glPopMatrix()


class PolygonModeRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_POLYGON_BIT)
        GL.glPolygonMode(self.sceneNode.face, self.sceneNode.mode)

    def exit(self):
        GL.glPopAttrib()


class VertexRenderNode(RenderNode):
    def __init__(self, sceneNode):
        """

        :type sceneNode: VertexNode
        """
        super(VertexRenderNode, self).__init__(sceneNode)

        self.didDraw = False

    def invalidate(self):
        if self.didDraw:
            assert False
        super(VertexRenderNode, self).invalidate()


    def drawSelf(self):
        self.didDraw = True
        bare = []
        withTex = []
        withLights = []
        for array in self.sceneNode.vertexArrays:
            if array.lights:
                withLights.append(array)
            elif array.textures:
                withTex.append(array)
            else:
                bare.append(array)

        with gl.glPushAttrib(GL.GL_ENABLE_BIT):
            GL.glDisable(GL.GL_TEXTURE_2D)
            self.drawArrays(bare, False, False)
            GL.glEnable(GL.GL_TEXTURE_2D)
            self.drawArrays(withTex, True, False)
            self.drawArrays(withLights, True, True)

    def drawArrays(self, vertexArrays, textures, lights):
        if textures:
            GL.glClientActiveTexture(GL.GL_TEXTURE0)
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        if lights:
            GL.glClientActiveTexture(GL.GL_TEXTURE1)
            GL.glEnableClientState(GL.GL_TEXTURE_COORD_ARRAY)
        else:
            GL.glMultiTexCoord2d(GL.GL_TEXTURE1, 15, 15)

        GL.glEnableClientState(GL.GL_COLOR_ARRAY)

        for array in vertexArrays:
            if 0 == len(array.buffer):
                continue
            stride = 4 * array.elements

            buf = array.buffer.ravel()

            GL.glVertexPointer(3, GL.GL_FLOAT, stride, buf)
            if textures:
                GL.glClientActiveTexture(GL.GL_TEXTURE0)
                GL.glTexCoordPointer(2, GL.GL_FLOAT, stride, (buf[array.texOffset:]))
            if lights:
                GL.glClientActiveTexture(GL.GL_TEXTURE1)
                GL.glTexCoordPointer(2, GL.GL_FLOAT, stride, (buf[array.lightOffset:]))
            GL.glColorPointer(4, GL.GL_UNSIGNED_BYTE, stride, (buf.view(dtype=numpy.uint8)[array.rgbaOffset*4:]))

            vertexCount = int(array.buffer.size / array.elements)
            GL.glDrawArrays(array.gl_type, 0, vertexCount)

        GL.glDisableClientState(GL.GL_COLOR_ARRAY)

        if lights:
            GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)

        if textures:
            GL.glClientActiveTexture(GL.GL_TEXTURE0)
            GL.glDisableClientState(GL.GL_TEXTURE_COORD_ARRAY)

class OrthoRenderNode(RenderstateRenderNode):
    def enter(self):
        w, h = self.sceneNode.size
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPushMatrix()
        GL.glLoadIdentity()
        GL.glOrtho(0., w, 0., h, -200, 200)

    def exit(self):
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glPopMatrix()


class ClearRenderNode(RenderNode):
    def drawSelf(self):
        color = self.sceneNode.clearColor
        if color is None:
            GL.glClear(GL.GL_DEPTH_BUFFER_BIT)
        else:
            GL.glClearColor(*color)
            GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

class DepthMaskRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT)
        GL.glDepthMask(self.sceneNode.mask)

    def exit(self):
        GL.glPopAttrib()

class DepthFuncRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_DEPTH_BUFFER_BIT)
        GL.glDepthFunc(self.sceneNode.func)

    def exit(self):
        GL.glPopAttrib()

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


class DepthOffsetRenderNode(RenderstateRenderNode):
    def enter(self):
        GL.glPushAttrib(GL.GL_POLYGON_BIT)
        GL.glPolygonOffset(self.sceneNode.depthOffset, self.sceneNode.depthOffset)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)

    def exit(self):
        GL.glPopAttrib()

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

