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
import numpy
from contextlib import contextmanager


import weakref
from OpenGL.GL import framebufferobjects as FBO
import sys


class gl(object):
    @classmethod
    def ResetGL(cls):
        DisplayList.destroyAllLists()

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
    def glPushClientAttrib(cls, *attribs):
        allAttribs = reduce(lambda a, b: a | b, attribs)
        try:
            GL.glPushClientAttrib(allAttribs)
            yield
        finally:
            GL.glPopClientAttrib()

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


    @classmethod
    @contextmanager
    def glEnableClientState(cls, *enables):
        try:
            GL.glPushClientAttrib(GL.GL_CLIENT_ALL_ATTRIB_BITS)
            for e in enables:
                GL.glEnableClientState(e)

            yield
        finally:
            GL.glPopClientAttrib()

    listCount = 0

    @classmethod
    def glGenLists(cls, n):
        cls.listCount += n
        return GL.glGenLists(n)

    @classmethod
    def glDeleteLists(cls, base, n):
        cls.listCount -= n
        return GL.glDeleteLists(base, n)

allDisplayLists = []

class DisplayList(object):

    def __init__(self, drawFunc=None):
        self.drawFunc = drawFunc
        self._list = None
        self.dirty = True

        def _delete(r):
            allDisplayLists.remove(r)
        allDisplayLists.append(weakref.ref(self, _delete))

    @classmethod
    def destroyAllLists(self):
        allLists = []
        for listref in allDisplayLists:
            list = listref()
            if list:
                list.destroy()
                allLists.append(listref)

        allDisplayLists[:] = allLists

    def invalidate(self):
        self.dirty = True

    def destroy(self):
        if self._list is not None:
            GL.glDeleteLists(self._list, 1)
            self._list = None
            self.dirty = True

    def compile(self, drawFunc):
        if not self.dirty and self._list is not None:
            return
        self._compile(drawFunc)

    def _compile(self, drawFunc):
        drawFunc = (drawFunc or self.drawFunc)
        if drawFunc is None:
            return

        if self._list is None:
            l = gl.glGenLists(1)
            self._list = numpy.array([l], 'uintc')

        l = self._list[0]
        GL.glNewList(l, GL.GL_COMPILE)
        drawFunc()
        #try:
        GL.glEndList()
        #except GL.GLError:
        #    print "Error while compiling display list. Retrying display list code to pinpoint error"
        #    self.drawFunc()
        self.dirty = False



    def getList(self, drawFunc=None):
        self.compile(drawFunc)
        return self._list

    if "-debuglists" in sys.argv:
        def call(self, drawFunc=None):
            drawFunc = (drawFunc or self.drawFunc)
            if drawFunc is None:
                return
            drawFunc()
    else:
        def call(self, drawFunc=None):
            self.compile(drawFunc)
            GL.glCallLists(self._list)


class Texture(object):
    allTextures = []
    defaultFilter = GL.GL_NEAREST

    def __init__(self, textureFunc=None, minFilter=None, magFilter=None, maxLOD=4):
        # maxLOD setting of 4 ensures 16x16 textures reduce to 1x1 and no smaller
        self.minFilter = minFilter or self.defaultFilter
        self.magFilter = magFilter or self.defaultFilter
        if textureFunc is None:
            textureFunc = lambda: None

        self.textureFunc = textureFunc
        self._texID = GL.glGenTextures(1)
        self.dirty = True
        self.maxLOD = maxLOD

    def load(self):
        if not self.dirty:
            return

        self.dirty = False

        def _delete(r):
            Texture.allTextures.remove(r)
        self.allTextures.append(weakref.ref(self, _delete))
        self.bind()

        GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, self.minFilter)
        GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, self.magFilter)

        self.textureFunc()

        if self.minFilter in (GL.GL_LINEAR_MIPMAP_LINEAR,
                              GL.GL_LINEAR_MIPMAP_NEAREST,
                              GL.GL_NEAREST_MIPMAP_LINEAR,
                              GL.GL_NEAREST_MIPMAP_NEAREST):

            if bool(GL.glGenerateMipmap):
                GL.glTexParameter(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAX_LOD, self.maxLOD)
                GL.glGenerateMipmap(GL.GL_TEXTURE_2D)

    def dispose(self):
        if self._texID is not None:
            GL.glDeleteTextures(self._texID)
            self._texID = None

    def bind(self):
        self.load()
        GL.glBindTexture(GL.GL_TEXTURE_2D, self._texID)

    def invalidate(self):
        self.dirty = True


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
