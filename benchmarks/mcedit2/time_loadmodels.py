"""
    time_loadmodels
"""
from __future__ import absolute_import, division, print_function
import logging
import timeit
from mcedit2.rendering.blockmodels import BlockModels
from mcedit2.rendering.textureatlas import TextureAtlas
from mcedit2.rendering.worldscene import WorldScene
from mcedit2.resourceloader import ResourceLoader
from mcedit2.util import minecraftinstall
from mceditlib.worldeditor import WorldEditor

log = logging.getLogger(__name__)

class o(object):
    pass


def main():
    filename =  "C:\Users\Rio\AppData\Roaming\.minecraft\saves\New World1_8"
    worldEditor = WorldEditor(filename, readonly=True)
    dim = worldEditor.getDimension()
    positions = list(dim.chunkPositions())

    installs = minecraftinstall.GetInstalls()
    install = installs.getDefaultInstall()
    loader = install.getResourceLoader(install.findVersion1_8(), None)
    def loadModels():
        o.models = BlockModels(worldEditor.blocktypes, loader)
    def loadTextures():
        o.textureAtlas = TextureAtlas(worldEditor, loader, o.models, overrideMaxSize=2048)
        o.textureAtlas.load()
    def cookQuads():
        o.models.cookQuads(o.textureAtlas)
    def buildMeshes():
        o.worldScene = WorldScene(dim, o.textureAtlas)
        worker = o.worldScene.workOnChunk(dim.getChunk(*positions[0]))
        for i in worker:
            pass

    print("loadModels x1 in %0.2fms" % (timeit.timeit(loadModels, number=1) * 1000))
    print("loadTextures x1 in %0.2fms" % (timeit.timeit(loadTextures, number=1) * 1000))
    print("cookQuads x1 in %0.2fms" % (timeit.timeit(cookQuads, number=1) * 1000))
    print("buildMeshes x1 in %0.2fms" % (timeit.timeit(buildMeshes, number=1) * 1000))

if __name__ == "__main__":
    main()
