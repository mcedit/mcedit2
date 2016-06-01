"""
    schematic_worldview
"""
from __future__ import absolute_import, division, print_function, unicode_literals
from PySide import QtGui
import logging
from mcedit2.rendering.blockmodels import BlockModels
from mcedit2.rendering.textureatlas import TextureAtlas
from mcedit2.util import minecraftinstall
from mcedit2.util.screen import centerWidgetInScreen
from mcedit2.util.worldloader import WorldLoader
from mcedit2.worldview.camera import CameraWorldView, CameraPanMouseAction, \
    CameraStickyPanMouseAction
from mcedit2.worldview.viewaction import ViewAction

log = logging.getLogger(__name__)

minZoom = 0.1
maxZoom = 2.0

class SchematicZoomInAction(ViewAction):
    labelText = "Zoom Schematic View In"
    button = ViewAction.WHEEL_UP
    acceptsMouseWheel = True
    settingsKey = None

    def keyPressEvent(self, event):
        event.view.distance = min(maxZoom, max(minZoom, event.view.distance - 0.05))

class SchematicZoomOutAction(ViewAction):
    labelText = "Zoom Schematic View Out"
    button = ViewAction.WHEEL_DOWN
    acceptsMouseWheel = True
    settingsKey = None

    def keyPressEvent(self, event):
        event.view.distance = min(maxZoom, max(minZoom, event.view.distance + 0.05))


class SchematicWorldView(CameraWorldView):
    def __init__(self, dimension, textureAtlas):
        super(SchematicWorldView, self).__init__(dimension, textureAtlas)

        self.distance = 1.4
        self.centerPoint = dimension.bounds.center
        stickyPanAction = CameraStickyPanMouseAction()

        self.viewActions = [CameraPanMouseAction(stickyPanAction),
                            stickyPanAction,
                            SchematicZoomInAction(),
                            SchematicZoomOutAction()]

    _distance = 1.0

    @property
    def distance(self):
        return self._distance

    @distance.setter
    def distance(self, val):
        self._distance = val
        self._updateMatrices()
        self.update()

    def updateModelviewMatrix(self):
        cameraPos = self.centerPoint - self.cameraVector * self.dimension.bounds.size.length() * self.distance


        modelview = QtGui.QMatrix4x4()
        modelview.lookAt(QtGui.QVector3D(*cameraPos),
                         QtGui.QVector3D(*(cameraPos + self.cameraVector)),
                         QtGui.QVector3D(0, 1, 0))
        self.matrixState.modelview = modelview


_swv_app = None

def displaySchematic(schematic):
    global _swv_app
    if QtGui.qApp is None:
        _swv_app = QtGui.QApplication([])

    if hasattr(schematic, 'getDimension'):
        dim = schematic.getDimension()
    else:
        dim = schematic

    resourceLoader = minecraftinstall.getSelectedResourceLoader()  # xxx select using dim.blocktypes
    blockModels = BlockModels(schematic.blocktypes, resourceLoader)
    textureAtlas = TextureAtlas(schematic, resourceLoader, blockModels)

    _swv_view = SchematicWorldView(dim, textureAtlas)

    loader = WorldLoader(_swv_view.worldScene)
    loader.timer.timeout.connect(_swv_view.update)
    loader.startLoader()

    centerWidgetInScreen(_swv_view, resize=0.75)

    _swv_view.show()

    _swv_app.exec_()
