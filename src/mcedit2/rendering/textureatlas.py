"""
    textureatlas
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import itertools

from OpenGL import GL
import numpy

from mcedit2.util.load_png import loadPNGData
from mcedit2.rendering.lightmap import generateLightmap
from mcedit2.resourceloader import ResourceLoader, ResourceNotFound
from mcedit2.util import glutils
from mcedit2.util.resources import resourcePath
from mceditlib import util


log = logging.getLogger(__name__)


class TextureSlot(object):
    def __init__(self, left, top, right, bottom):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.textures = []

    @property
    def width(self):
        return self.right - self.left

    @property
    def height(self):
        return self.bottom - self.top

    def addTexture(self, name, w, h, d):
        if w > self.width or h > self.height:
            return False

        self.textures.append((name, self.left, self.top, w, h, d))
        if self.width > self.height:
            self.left += w
        else:
            self.top += h

        return True


def allTextureNames(blocktypes):
    for b in blocktypes:
        yield b.internalName


class TextureAtlas(object):

    def __init__(self, world, resourceLoader, blockModels, maxLOD=0, overrideMaxSize=None):
        """
        Important members:

            textureData: RGBA Texture Data as a numpy array.

            texCoordsByName: Dictionary of texture coordinates. Usable for textures loaded using the extraTextures argument
                or from block definitions.
                Maps "texture_name" -> (left, top, right, bottom)


        :param world:
        :type world: mceditlib.worldeditor.WorldEditor
        :param resourceLoader:
        :type resourceLoader: mcedit2.resourceloader.ResourceLoader
        :param blockModels:
        :type blockModels: mcedit2.rendering.blockmodels.BlockModels
        :param maxLOD: Adds wrapped borders to each texture to allow mipmapping at this level of detail
        :type maxLOD: int
        :param overrideMaxSize: Override the maximum texture size - ONLY use for testing TextureAtlas without creating a GL context.
        :type overrideMaxSize: int or None
        :return:
        :rtype: TextureAtlas
        """
        self.overrideMaxSize = overrideMaxSize
        self.blockModels = blockModels
        self.blocktypes = world.blocktypes
        self._filename = world.filename
        self._resourceLoader = resourceLoader
        self._lightTexture = None
        self._terrainTexture = None
        self._maxLOD = maxLOD


        names = set()
        self._rawTextures = rawTextures = []
        assert "MCEDIT_UNKNOWN" in blockModels.getTextureNames()
        for filename in blockModels.getTextureNames():
            if filename in names:
                continue
            try:
                f = self._openImageStream(filename)
                rawTextures.append((filename,) + loadPNGData(f.read()))
                names.add(filename)
                log.debug("Loaded texture %s", filename)
            except ResourceNotFound as e:
                log.error("Could not load texture %s: %r", filename, e)
            except Exception as e:
                log.exception("%s while loading texture '%s', skipping...", e, filename)

        rawSize = sum(a.nbytes for (n, w, h, a) in rawTextures)

        log.info("Preloaded %d textures for world %s (%i kB)",
                 len(self._rawTextures), util.displayName(self._filename), rawSize/1024)



    def load(self):
        if self._terrainTexture:
            return

        if self.overrideMaxSize is None:
            maxSize = getGLMaximumTextureSize()
        else:
            maxSize = self.overrideMaxSize

        maxLOD = min(4, self._maxLOD)
        if not bool(GL.glGenerateMipmap):
            maxLOD = 0
        if maxLOD:
            borderSize = 1 << (maxLOD - 1)
        else:
            borderSize = 0

        slots = []
        atlasWidth = 0
        atlasHeight = 0
        self._rawTextures.sort(key=lambda (_, w, h, __): max(w, h), reverse=True)

        for path, w, h, data in self._rawTextures:
            w += borderSize * 2
            h += borderSize * 2
            for slot in slots:
                if slot.addTexture(path, w, h, data):
                    log.debug("Slotting %s into an existing slot", path)
                    break
            else:
                if atlasHeight < 24 * atlasWidth and atlasHeight + h < maxSize:
                    # Prefer to lay out textures vertically, since animations are vertical strips
                    slots.append(TextureSlot(0, atlasHeight, max(atlasWidth, w), atlasHeight + h))
                    atlasWidth = max(atlasWidth, w)
                    atlasHeight = atlasHeight + h
                else:
                    slots.append(TextureSlot(atlasWidth, 0, atlasWidth + w, max(atlasHeight, h)))
                    atlasWidth = atlasWidth + w
                    atlasHeight = max(atlasHeight, h)

                if atlasWidth > maxSize or atlasHeight > maxSize:
                    raise ValueError("Building texture atlas: Textures too large for maximum texture size. (Needed "
                                     "%s, only got %s", (atlasWidth, atlasHeight), (maxSize, maxSize))

                if not slots[-1].addTexture(path, w, h, data):
                    raise ValueError("Building texture atlas: Internal error.")

                log.debug("Slotting %s into a newly created slot", path)

        self.textureData = texData = numpy.zeros((atlasHeight, atlasWidth, 4), dtype='uint8')
        self.textureData[:] = [0xff, 0x0, 0xff, 0xff]
        self.texCoordsByName = {}
        b = borderSize
        for slot in slots:
            for name, left, top, width, height, data in slot.textures:
                log.debug("Texture %s at (%d,%d,%d,%d)", name, left, top, width, height)
                texDataView = texData[top:top + height, left:left + width]
                if b:
                    texDataView[b:-b, b:-b] = data

                    # Wrap texture edges to avoid antialiasing bugs at edges of blocks
                    texDataView[-b:, b:-b] = data[:b]
                    texDataView[:b, b:-b] = data[-b:]

                    texDataView[:, -b:] = texDataView[:, b:2 * b]
                    texDataView[:, :b] = texDataView[:, -b * 2:-b]
                else:
                    texDataView[:] = data
                self.texCoordsByName[name] = left + b, top + b, width - 2 * b, height - 2 * b

        def _load():
            GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, atlasWidth, atlasHeight, 0, GL.GL_RGBA,
                            GL.GL_UNSIGNED_BYTE, self.textureData.ravel())

        if self.overrideMaxSize is None:
            if maxLOD:
                minFilter = GL.GL_NEAREST_MIPMAP_LINEAR
            else:
                minFilter = None
            self._terrainTexture = glutils.Texture(_load, minFilter=minFilter, maxLOD=maxLOD)
            self._terrainTexture.load()
        else:
            self._terrainTexture = object()

        self.width = atlasWidth
        self.height = atlasHeight

        totalSize = atlasWidth * atlasHeight * 4
        usedSize = sum(sum(width * height for _, _, _, width, height, _ in slot.textures) for slot in slots) * 4
        log.info("Terrain atlas created for world %s (%d/%d kB)", util.displayName(self._filename), usedSize / 1024,
                 totalSize / 1024)
        self.blockModels.cookQuads(self)

        #file("terrain-%sw-%sh.raw" % (atlasWidth, atlasHeight), "wb").write(texData.tostring())
        #raise SystemExit

    def _openImageStream(self, name):
        if name == "MCEDIT_UNKNOWN":
            block_unknown = resourcePath("mcedit2/assets/mcedit2/block_unknown.png")
            return file(block_unknown, "rb")
        return self._resourceLoader.openStream(name)

    def bindTerrain(self):
        self._terrainTexture.bind()

    _dayTime = 1.0

    @property
    def dayTime(self):
        return self._dayTime

    @dayTime.setter
    def dayTime(self, value):
        self._dayTime = value
        del self._lightTexture

    _minBrightness = 0.0

    @property
    def minBrightness(self):
        return self._minBrightness

    @minBrightness.setter
    def minBrightness(self, value):
        self._minBrightness = value
        del self._lightTexture

    def bindLight(self):
        if self._lightTexture is None:
            self._lightTexture = _makeLightTexture(self.dayTime, self.minBrightness)

        self._lightTexture.bind()

    def dispose(self):
        if self._terrainTexture:
            self._terrainTexture.dispose()
        if self._lightTexture:
            self._lightTexture.dispose()


def _makeLightTexture(dayTime=1.0, minBrightness=1.0):
    def _loadLightTexture():
        pixels = generateLightmap(dayTime)
        pixels.clip(int(minBrightness * 255), 255, pixels)
        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, 16, 16, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, pixels.ravel())

    return glutils.Texture(_loadLightTexture)

_maxSize = None

def getGLMaximumTextureSize():
    global _maxSize
    if _maxSize == None:
        _maxSize = _getMaxSize()
    return _maxSize

def _getMaxSize():
    size = 16384
    while size > 0:
        size /= 2
        GL.glTexImage2D(GL.GL_PROXY_TEXTURE_2D, 0, GL.GL_RGBA, size, size, 0, GL.GL_RGBA, GL.GL_UNSIGNED_BYTE, None)
        maxsize = GL.glGetTexLevelParameteriv(GL.GL_PROXY_TEXTURE_2D, 0, GL.GL_TEXTURE_WIDTH)

        if maxsize:
            return maxsize

    return -1


def test_TextureAtlas():
    rl = ResourceLoader()


