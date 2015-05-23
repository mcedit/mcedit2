"""
    qglcontext
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from OpenGL import GL
from PySide import QtOpenGL, QtGui
import logging

log = logging.getLogger(__name__)


def validateQGLContext():
    oglFormat = QtOpenGL.QGLFormat()
    oglFormat.setVersion(1, 3)
    QtOpenGL.QGLFormat.setDefaultFormat(oglFormat)
    context = QtOpenGL.QGLContext(oglFormat)
    context.makeCurrent()
    versionFlags = QtOpenGL.QGLFormat.openGLVersionFlags()
    log.info("OpenGL Version Info:")
    for flag in (
            QtOpenGL.QGLFormat.OpenGL_Version_1_1,
            QtOpenGL.QGLFormat.OpenGL_Version_1_2,
            QtOpenGL.QGLFormat.OpenGL_Version_1_3,
            QtOpenGL.QGLFormat.OpenGL_Version_1_4,
            QtOpenGL.QGLFormat.OpenGL_Version_1_5,
            QtOpenGL.QGLFormat.OpenGL_Version_2_0,
            QtOpenGL.QGLFormat.OpenGL_Version_3_0,
            QtOpenGL.QGLFormat.OpenGL_Version_3_1,
            QtOpenGL.QGLFormat.OpenGL_Version_3_2,
            QtOpenGL.QGLFormat.OpenGL_Version_3_3,
            QtOpenGL.QGLFormat.OpenGL_Version_4_0,
    ):
        if flag & versionFlags:
            log.info(str(flag))

    actualFormat = context.format()
    """:type : QtOpenGL.QGLFormat"""

    if (not versionFlags & QtOpenGL.QGLFormat.OpenGL_Version_1_3
        or (actualFormat.majorVersion(), actualFormat.minorVersion()) < (1, 3)):
        msgBox = QtGui.QMessageBox()
        msgBox.setWindowTitle(QtGui.qApp.tr("OpenGL Error"))
        msgBox.setStandardButtons(QtGui.QMessageBox.Close)
        msgBox.setText(QtGui.qApp.tr("OpenGL 1.3 or greater is required. MCEdit was unable to start up OpenGL."))
        msgBox.setInformativeText(
            QtGui.qApp.tr("Could not create a usable OpenGL context. Verify that your "
                          "graphics drivers are installed correctly.")
        )

        detailedText = "Obtained a GL context with this format:\n"
        detailedText += "Version: %s.%s\n" % (actualFormat.majorVersion(), actualFormat.minorVersion())
        detailedText += "Depth buffer: %s, %s\n" % (actualFormat.depth(), actualFormat.depthBufferSize())
        detailedText += "Double buffer: %s\n" % (actualFormat.doubleBuffer(), )
        detailedText += "Direct render: %s\n" % (actualFormat.directRendering(), )
        detailedText += "\n"
        detailedText += "Driver info:\n"
        detailedText += "GL_VERSION: %s\n" % GL.glGetString(GL.GL_VERSION)
        detailedText += "GL_VENDOR: %s\n" % GL.glGetString(GL.GL_VENDOR)
        detailedText += "GL_RENDERER: %s\n" % GL.glGetString(GL.GL_RENDERER)

        msgBox.setDetailedText(detailedText)

        msgBox.setIcon(QtGui.QMessageBox.Critical)

        msgBox.setMinimumWidth(300)
        msgBox.setSizeGripEnabled(True)
        msgBox.exec_()

        raise SystemExit

    return context