"""Copyright (c) 2010-2012 David Rio Vierra

Permission to use, copy, modify, and/or distribute this software for any
purpose with or without fee is hereby granted, provided that the above
copyright notice and this permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

glutils.py

Pythonesque wrappers around certain OpenGL functions.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from OpenGL import GL
from OpenGL.GL.ARB import multitexture
from OpenGL.extensions import alternate
import numpy
from contextlib import contextmanager

import logging

import weakref
from OpenGL.GL import framebufferobjects as FBO
import sys


log = logging.getLogger(__name__)

class gl(object):
    @classmethod
    def ResetGL(cls):
        DisplayList.deallocAllLists()

    @classmethod
    @contextmanager
    def glPushMatrix(cls, matrixmode):
        try:
            GL.glMatrixMode(matrixmode)
            GL.glPushMatrix()
            yield
        finally:
            GL.glMatrixMode(matrixmode)
            GL.glPopMatrix()

    @classmethod
    @contextmanager
    def glPushAttrib(cls, *attribs):
        allAttribs = reduce(lambda a, b: a | b, attribs)
        try:
            GL.glPushAttrib(allAttribs)
            yield
        finally:
            GL.glPopAttrib()

    @classmethod
    @contextmanager
    def glBegin(cls, type):
        try:
            GL.glBegin(type)
            yield
        finally:
            GL.glEnd()

    @classmethod
    @contextmanager
    def glEnable(cls, *enables):
        try:
            GL.glPushAttrib(GL.GL_ENABLE_BIT)
            for e in enables:
                GL.glEnable(e)

            yield
        finally:
            GL.glPopAttrib()

    listCount = 0

    @classmethod
    def glGenLists(cls, n):
        cls.listCount += n
        return GL.glGenLists(n)

    @classmethod
    def glDeleteLists(cls, base, n):
        cls.listCount -= n
        return GL.glDeleteLists(base, n)

glActiveTexture = alternate(GL.glActiveTexture, multitexture.glActiveTextureARB)

allDisplayLists = []

class DisplayList(object):

    def __init__(self):
        self._list = None
        self.dirty = True

        def _delete(r):
            allDisplayLists.remove(r)
        allDisplayLists.append(weakref.ref(self, _delete))

    @classmethod
    def deallocAllLists(self):
        allLists = []
        for listref in allDisplayLists:
            list = listref()
            if list:
                list.dealloc()
                allLists.append(listref)

        allDisplayLists[:] = allLists

    def invalidate(self):
        self.dirty = True

    def dealloc(self):
        if self._list is not None:
            GL.glDeleteLists(self._list, 1)
            self._list = None
            self.dirty = True

    def compile(self, drawFunc):
        if not self.dirty and self._list is not None:
            return
        self._compile(drawFunc)

    def _compile(self, drawFunc):
        l = self.getList()[0]
        GL.glNewList(l, GL.GL_COMPILE)
        drawFunc()
        #try:
        GL.glEndList()
        #except GL.GLError:
        #    print "Error while compiling display list. Retrying display list code to pinpoint error"
        #    self.drawFunc()
        self.dirty = False

    def getList(self):
        if self._list is None:
            l = gl.glGenLists(1)
            self._list = numpy.array([l], 'uintc')
        return self._list

    def call(self):
        assert self._list is not None
        GL.glCallLists(self._list)


class Texture(object):
    allTextures = []
    defaultFilter = GL.GL_NEAREST

    def __init__(self, name=None, image=None, width=None, height=None, minFilter=None, magFilter=None, maxLOD=4):
        # maxLOD setting of 4 ensures 16x16 textures reduce to 1x1 and no smaller
        self.minFilter = minFilter or self.defaultFilter
        self.magFilter = magFilter or self.defaultFilter

        self._image = image
        self.width = width
        self.height = height
        self.name = name or "Unnamed"

        self.imageFormat = GL.GL_RGBA
        self.textureFormat = GL.GL_RGBA
        self.imageDtype = GL.GL_UNSIGNED_BYTE

        self._texID = None
        self.dirty = True
        self.maxLOD = maxLOD

    @property
    def image(self):
        return self._image

    @image.setter
    def image(self, value):
        self._image = value
        self.dirty = True

    def load(self):
        if self.image is None or not self.dirty:
            return
        assert self.width and self.height, "Invalid texture size."

        self.bind(load=False)
        log.debug("BINDING: %s", GL.glGetInteger(GL.GL_TEXTURE_BINDING_2D))
        GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, self.minFilter)
        GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, self.magFilter)

        log.debug("Update texture %s (%d)", self.name, self._texID)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, self.textureFormat,
                        self.width, self.height, 0, self.imageFormat,
                        self.imageDtype, self._image)
        self.dirty = False

    def dispose(self):
        if self._texID is not None:
            GL.glDeleteTextures(self._texID)
            self._texID = None

    def gen(self):
        if self._texID is None:
            self._texID = GL.glGenTextures(1)
            log.debug("Gen texture %s (%d)", self.name, self._texID)

            def _delete(r):
                Texture.allTextures.remove(r)
            self.allTextures.append(weakref.ref(self, _delete))

    def bind(self, load=True):
        self.gen()
        if load and self.dirty:
            raise ValueError("Binding dirty/unloaded texture! Implicit loads not allowed; should not load during displaylist compilation.")
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texID)

    def invalidate(self):
        self.dirty = True


# --- UNUSED FOR NOW? ---

class FramebufferTexture(Texture):
    def __init__(self, width, height, drawFunc):
        tex = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
        GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA8, width, height, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        self.enabled = False
        self._texID = tex
        if bool(FBO.glGenFramebuffers) and "Intel" not in GL.glGetString(GL.GL_VENDOR):
            buf = FBO.glGenFramebuffers(1)
            depthbuffer = FBO.glGenRenderbuffers(1)

            FBO.glBindFramebuffer(FBO.GL_FRAMEBUFFER, buf)

            FBO.glBindRenderbuffer(FBO.GL_RENDERBUFFER, depthbuffer)
            FBO.glRenderbufferStorage(FBO.GL_RENDERBUFFER, GL.GL_DEPTH_COMPONENT, width, height)

            FBO.glFramebufferRenderbuffer(FBO.GL_FRAMEBUFFER, FBO.GL_DEPTH_ATTACHMENT, FBO.GL_RENDERBUFFER, depthbuffer)
            FBO.glFramebufferTexture2D(FBO.GL_FRAMEBUFFER, FBO.GL_COLOR_ATTACHMENT0, GL.GL_TEXTURE_2D, tex, 0)

            status = FBO.glCheckFramebufferStatus(FBO.GL_FRAMEBUFFER)
            if status != FBO.GL_FRAMEBUFFER_COMPLETE:
                print ("glCheckFramebufferStatus: " + str(status))
                self.enabled = False
                return

            FBO.glBindFramebuffer(FBO.GL_FRAMEBUFFER, buf)

            with gl.glPushAttrib(GL.GL_VIEWPORT_BIT):
                GL.glViewport(0, 0, width, height)
                drawFunc()

            FBO.glBindFramebuffer(FBO.GL_FRAMEBUFFER, 0)
            FBO.glDeleteFramebuffers(1, [buf])
            FBO.glDeleteRenderbuffers(1, [depthbuffer])
            self.enabled = True
        else:
            GL.glReadBuffer(GL.GL_BACK)

            GL.glPushAttrib(GL.GL_VIEWPORT_BIT | GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT | GL.GL_STENCIL_TEST | GL.GL_STENCIL_BUFFER_BIT)
            GL.glDisable(GL.GL_STENCIL_TEST)

            GL.glViewport(0, 0, width, height)
            GL.glScissor(0, 0, width, height)
            with gl.glEnable(GL.GL_SCISSOR_TEST):
                drawFunc()

            GL.glBindTexture(GL.GL_TEXTURE_2D, tex)
            GL.glReadBuffer(GL.GL_BACK)
            GL.glCopyTexSubImage2D(GL.GL_TEXTURE_2D, 0, 0, 0, 0, 0, width, height)

            GL.glPopAttrib()



def debugDrawPoint(point):
    GL.glColor(1.0, 1.0, 0.0, 1.0)
    GL.glPointSize(9.0)
    with gl.glBegin(GL.GL_POINTS):
        GL.glVertex3f(*point)
