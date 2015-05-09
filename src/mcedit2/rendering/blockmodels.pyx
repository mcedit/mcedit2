#cython: boundscheck=False, profile=True
"""
    blockmodels
"""
from __future__ import absolute_import, print_function
import json
import logging
import math
import itertools
from PySide import QtGui

import numpy as np
cimport numpy as cnp

cnp.import_array()

from mcedit2.resourceloader import ResourceNotFound

from mceditlib.blocktypes import BlockType
from mceditlib.cachefunc import lru_cache
from mceditlib.geometry import Vector
from mceditlib.selection import FloatBox

from libc.stdlib cimport malloc, free
from libc.string cimport memset

log = logging.getLogger(__name__)


cdef struct ModelQuad:
    float[32] xyzuvstc
    char[4] cullface  # isCulled, dx, dy, dz
    char[4] quadface  # face, dx, dy, dz
    char biomeTintType

cdef struct ModelQuadList:
    int count
    ModelQuad *quads

cdef class FaceInfo(object):
    cdef:
        float x1, y1, z1, x2, y2, z2
        short face, cullface
        unicode texture
        short u1, v1, u2, v2
        char shade
        float ox, oy, oz
        cnp.ndarray elementMatrix, variantMatrix
        int textureRotation
        int variantXrot, variantYrot, variantZrot
        object tintcolor
        char biomeTintType

    def __init__(self, x1, y1, z1, x2, y2, z2, face,
                 texture, u1, v1, u2, v2, cullface,
                 shade, ox, oy, oz, elementMatrix, textureRotation,
                 variantXrot, variantYrot, variantZrot, variantMatrix, tintcolor, biomeTintType):
        self.x1, self.y1, self.z1 = x1, y1, z1
        self.x2, self.y2, self.z2 = x2, y2, z2
        self.face = face
        self.texture = texture
        self.u1, self.v1, self.u2, self.v2 = u1, v1, u2, v2
        self.cullface = cullface
        self.shade = shade
        self.ox = ox
        self.oy = oy
        self.oz = oz
        self.elementMatrix = elementMatrix
        self.textureRotation = textureRotation
        self.variantXrot = variantXrot
        self.variantYrot = variantYrot
        self.variantZrot = variantZrot
        self.variantMatrix = variantMatrix
        self.tintcolor = tintcolor
        self.biomeTintType = biomeTintType

UNKNOWN_MODEL = {
    u"parent": u"block/cube_all",
    u"textures": {
        u"all": u"MCEDIT_UNKNOWN"
    }
}

cdef class BlockModels(object):
    def _getBlockModel(self, modelName):
        if modelName == u"block/MCEDIT_UNKNOWN":
            return UNKNOWN_MODEL
        modelPath = "assets/minecraft/models/%s.json" % modelName

        return self._getBlockModelByPath(modelPath)

    def _getBlockModelByPath(self, modelPath):
        model = self.modelBlockJsons.get(modelPath)
        if model is None:
            model = json.load(self.resourceLoader.openStream(modelPath))
            self.modelBlockJsons[modelPath] = model
        return model

    def _getBlockState(self, stateName):
        if stateName == u"MCEDIT_UNKNOWN":
            return {
                u"variants": {
                    u"MCEDIT_UNKNOWN": {
                        u"model": u"MCEDIT_UNKNOWN",
                    }
                }
            }
        state = self.modelStateJsons.get(stateName)
        if state is None:
            state = json.load(self.resourceLoader.openStream("assets/minecraft/blockstates/%s.json" % stateName))
            self.modelStateJsons[stateName] = state
        return state

    def __init__(self, blocktypes, resourceLoader):
        """

        :param blocktypes:
        :type blocktypes: mceditlib.blocktypes.BlockTypeSet
        :param resourceLoader:
        :type resourceLoader: ResourceLoader
        :return:
        :rtype: BlockModels
        """
        self.resourceLoader = resourceLoader
        self.blocktypes = blocktypes

        self.grassImage = QtGui.QImage.fromData(resourceLoader.openStream("assets/minecraft/textures/colormap/grass.png").read())
        self.grassImage = self.grassImage.convertToFormat(QtGui.QImage.Format_ARGB32)
        self.grassImageX = self.grassImage.width()
        self.grassImageY = self.grassImage.height()

        self._grassImageBits = self.grassImage.bits()
        self.grassImageBits = self._grassImageBits

        self.foliageImage = QtGui.QImage.fromData(resourceLoader.openStream("assets/minecraft/textures/colormap/foliage.png").read())
        self.foliageImage = self.foliageImage.convertToFormat(QtGui.QImage.Format_ARGB32)
        self.foliageImageX = self.foliageImage.width()
        self.foliageImageY = self.foliageImage.height()

        self._foliageImageBits = self.foliageImage.bits()
        self.foliageImageBits = self._foliageImageBits

        self.modelBlockJsons = {}
        self.modelStateJsons = {}
        self.modelQuads = {}
        self._texturePaths = set()
        self.firstTextures = {}  # first texture found for each block - used for icons (xxx)
        self.cookedModels = {}  # nameAndState -> list[(xyzuvstc, cullface)]

        memset(self.cookedModelsByID, 0, sizeof(self.cookedModelsByID))
        self.cooked = False

        missingnoProxy = BlockType(-1, -1, blocktypes)
        missingnoProxy.internalName = u"MCEDIT_UNKNOWN"
        missingnoProxy.blockState = ""
        missingnoProxy.renderType = 3
        missingnoProxy.resourcePath = u"MCEDIT_UNKNOWN"
        missingnoProxy.resourceVariant = u"MCEDIT_UNKNOWN"
        missingnoProxy.color = 0xFFFFFF
        log.info("Loading block models...")

        cdef dict modelDict, textures, textureVars
        cdef list elements
        cdef int i
        cdef short variantXrot, variantYrot, variantZrot
        cdef char biomeTintType

        for i, block in enumerate(list(blocktypes) + [missingnoProxy]):
            if i % 100 == 0:
                log.info("Loading block models %s/%s", i, len(blocktypes))

            if block.renderType != 3:  # only rendertype 3 uses block models
                continue

            internalName = block.internalName
            blockState = block.blockState
            resourcePath = block.resourcePath
            modelDict = None

            if block.forcedModel is not None:  # user-configured block
                modelDict = self._getBlockModelByPath(block.forcedModel)

            elif resourcePath is not None:
                nameAndState = internalName + blockState
                try:
                    statesJson = self._getBlockState(resourcePath)
                except ResourceNotFound as e:
                    if block.internalName.startswith("minecraft:"):
                        log.warn("Could not get blockstates resource for %s, skipping... (%r)", block, e)
                    continue
                variants = statesJson['variants']
                # variants is a dict with each key a resourceVariant value (from the block's ModelResourceLocation)
                # the value for this key is either a dict describing which model to use
                # ... or a list of such models to be selected from randomly
                #
                # each model dict must have a 'model' key whose value is the name of a file under assets/minecraft/models
                # model dict may also have optional keys 'x', 'y', 'z' with a value in degrees, to rotate the model
                # around that axis
                # another optional key is 'uvlock', which needs investigating
                # variant dict for 'rail':

                # "variants": {
                #     "shape=north_south": { "model": "normal_rail_flat" },
                #     "shape=east_west": { "model": "normal_rail_flat", "y": 90 },
                #     "shape=ascending_east": { "model": "normal_rail_raised_ne", "y": 90 },
                #     "shape=ascending_west": { "model": "normal_rail_raised_sw", "y": 90 },
                #     "shape=ascending_north": { "model": "normal_rail_raised_ne" },
                #     "shape=ascending_south": { "model": "normal_rail_raised_sw" },
                #     "shape=south_east": { "model": "normal_rail_curved" },
                #     "shape=south_west": { "model": "normal_rail_curved", "y": 90 },
                #     "shape=north_west": { "model": "normal_rail_curved", "y": 180 },
                #     "shape=north_east": { "model": "normal_rail_curved", "y": 270 }
                # }

                resourceVariant = block.resourceVariant
                log.debug("Loading %s#%s for %s", resourcePath, resourceVariant, block)
                variantDict = variants[resourceVariant]
                if isinstance(variantDict, list):
                    variantDict = variantDict[0]  # do the random pick thing later, if at all
                modelName = variantDict['model']
                try:
                    modelDict = self._getBlockModel("block/" + modelName)
                except ResourceNotFound as e:
                    log.exception("Could not get model resource %s for block %s, skipping... (%r)", modelName, block, e)
                    continue
                except ValueError as e:
                    log.exception("Error parsing json for block/%s: %s", modelName, e)
                    continue
                variantXrot = variantDict.get("x", 0)
                variantYrot = variantDict.get("y", 0)
                variantZrot = variantDict.get("z", 0)

            if modelDict is None:
                log.debug("No model found for %s", internalName)
                continue

            # model will either have an 'elements' key or a 'parent' key (maybe both).
            # 'parent' will be the name of a model
            # following 'parent' keys will eventually lead to a model with 'elements'
            #
            # 'elements' is a list of dicts each describing a box that makes up the model.
            # each box dict has 'from' and 'to' keys, which are lists of 3 float coordinates.
            #
            # the 'crossed squares' model demonstrates most of the keys found in a box element
            #
            # {   "from": [ 0.8, 0, 8 ],
            #     "to": [ 15.2, 16, 8 ],
            #     "rotation": { "origin": [ 8, 8, 8 ], "axis": "y", "angle": 45, "rescale": true },
            #     "shade": false,
            #     "faces": {
            #         "north": { "uv": [ 0, 0, 16, 16 ], "texture": "#cross" },
            #         "south": { "uv": [ 0, 0, 16, 16 ], "texture": "#cross" }
            #     }
            # }
            #
            # model may also have a 'textures' dict which assigns a texture file to a texture variable,
            # or a texture variable to another texture variable.
            #
            # the result of loading a model should be a list of quads, each with four vertexes, four pairs of
            # texture coordinates, four RGBA values for shading, plus a Face telling which adjacent block when
            # present causes that quad to be culled.

            textureVars = {}
            allElements = []

            # grab textures and elements from this model, then get parent and merge its textures and elements
            # continue until no parent is found
            for i in range(30):
                textures = modelDict.get("textures")
                if textures is not None:
                    textureVars.update(textures)
                elements = modelDict.get("elements")
                if elements is not None:
                    allElements.extend(elements)
                parentName = modelDict.get("parent")
                if parentName is None:
                    break
                try:
                    modelDict = self._getBlockModel(parentName)
                except ValueError as e:
                    log.exception("Error parsing json for block/%s: %s", parentName, e)
                    raise
            else:
                raise ValueError("Parent loop detected in block model %s" % modelName)

            if block.forcedModelTextures:  # user-configured model textures
                for var, tex in block.forcedModelTextures.iteritems():
                    textureVars[var[1:]] = tex
            if block.forcedModelRotation:
                variantXrot = block.forcedModelRotation[0]
                variantYrot = block.forcedModelRotation[1]
                variantZrot = block.forcedModelRotation[2]

            if block.biomeTintType == "grass":
                biomeTintType = BIOME_GRASS
            elif block.biomeTintType == "foliage":
                biomeTintType = BIOME_FOLIAGE
            else:
                biomeTintType = BIOME_NONE

            try:
                # each element describes a box with up to six faces, each with a texture. convert the box into
                # quads.
                allQuads = []

                if internalName == "minecraft:redstone_wire":
                    blockColor = (0xff, 0x33, 0x00)
                else:
                    blockColor = block.color
                    r = (blockColor >> 16) & 0xff
                    g = (blockColor >> 8) & 0xff
                    b = blockColor & 0xff
                    blockColor = r, g, b

                variantMatrix = variantRotation(variantXrot, variantYrot, variantZrot)
                for element in allElements:
                    quads = self.buildBoxQuads(element, nameAndState, textureVars, variantXrot, variantYrot, variantZrot, variantMatrix, blockColor, biomeTintType)
                    allQuads.extend(quads)

                self.modelQuads[internalName + blockState] = allQuads

            except Exception as e:
                log.error("Failed to parse variant of block %s\nelements:\n%s\ntextures:\n%s", nameAndState,
                          allElements, textureVars)
                raise


    def buildBoxQuads(self, dict element, unicode nameAndState, dict textureVars,
                       short variantXrot, short variantYrot, short variantZrot,
                       cnp.ndarray variantMatrix, tuple blockColor, char biomeTintType):
        quads = []
        shade = element.get("shade", True)

        cdef float ox, oy, oz
        ox, oy, oz, elementMatrix = elementRotation(element.get("rotation"))
        cdef float x1, y1, z1, x2, y2, z2
        x1, y1, z1 = element["from"]
        x2, y2, z2 = element["to"]

        x1 /= 16.
        y1 /= 16.
        z1 /= 16.
        x2 /= 16.
        y2 /= 16.
        z2 /= 16.

        cdef short u1, v1, u2, v2
        cdef unicode texture, lasttexvar
        cdef short i
        cdef dict info

        for face, info in element["faces"].iteritems():
            assert info is not None

            face = facesByCardinal[face]
            texture = info["texture"]
            cullface = info.get("cullface")
            cullface = facesByCardinal[cullface] if cullface is not None else -1
            uv = info.get("uv")
            if uv is not None:
                u1, v1, u2, v2 = uv
            else:
                u1, v1, u2, v2 = 0, 0, 16, 16

            lasttexvar = texture

            tintindex = info.get("tintindex")
            if tintindex is not None:
                tintcolor = blockColor
            else:
                tintcolor = None

            # resolve texture variables
            for i in range(30):
                if texture is None:
                    raise ValueError("Texture variable %s is not assigned." % lasttexvar)
                elif texture[0] == u"#":
                    lasttexvar = texture
                    texture = textureVars.get(texture[1:], u"MCEDIT_UNKNOWN")
                else:
                    break
            else:
                raise ValueError("Texture variable loop detected!")

            if texture != u"MCEDIT_UNKNOWN" and not texture.endswith(".png"):
                texture = "assets/minecraft/textures/" + texture + ".png"
            self.firstTextures.setdefault(nameAndState, texture)
            self._texturePaths.add(texture)

            quads.append(FaceInfo(x1, y1, z1, x2, y2, z2, face,
                    texture, u1, v1, u2, v2, cullface,
                    shade, ox, oy, oz, elementMatrix, info.get("rotation", 0),
                    variantXrot, variantYrot, variantZrot, variantMatrix, tintcolor, biomeTintType))

        return quads

    def getTextureNames(self):
        return itertools.chain(iter(self._texturePaths),
                               ['assets/minecraft/textures/blocks/water_still.png',
                                'assets/minecraft/textures/blocks/lava_still.png'])

    def cookQuads(self, textureAtlas):
        if self.cooked:
            return

        log.info("Cooking quads for %d models...", len(self.modelQuads))
        cookedModels = {}
        cdef short ID, meta
        cdef int l, t, w, h
        cdef short u1, u2, v1, v2, tr, tg, tb
        cdef int uw, vh
        cdef short quadface, cullface,
        cdef unsigned char shade
        cdef ModelQuadList modelQuads
        cdef ModelQuadList unknownBlockModel
        cdef list allQuads
        UNKNOWN_BLOCK = u'MCEDIT_UNKNOWN'

        cdef size_t i, j;

        cdef dict texCoordsByName = textureAtlas.texCoordsByName
        cdef FaceInfo faceInfo
        cdef short * vec
        cdef unsigned char * rgba

        for nameAndState, allQuads in self.modelQuads.iteritems():
            if nameAndState != UNKNOWN_BLOCK:
                try:
                    ID, meta = self.blocktypes.IDsByState[nameAndState]
                except KeyError:
                    continue  # xxx stash models somewhere for user-configuration

            modelQuads.count = len(allQuads)
            modelQuads.quads = <ModelQuad *>malloc(modelQuads.count * sizeof(ModelQuad))

            for i, faceInfo in enumerate(allQuads):
                if faceInfo.texture not in texCoordsByName:
                    log.warn("Texture %s was not loaded, using 'UNKNOWN'", faceInfo.texture)
                    l, t, w, h = texCoordsByName[UNKNOWN_BLOCK]
                else:
                    l, t, w, h = texCoordsByName[faceInfo.texture]
                u1 = faceInfo.u1
                u2 = faceInfo.u2
                v1 = faceInfo.v1
                v2 = faceInfo.v2

                uw = (w * (u2 - u1)) / 16
                vh = (w * (v2 - v1)) / 16  # w is assumed to be the height of a single frame in an animation xxxxx read .mcmeta
                u1 += l
                u2 = u1 + uw

                # flip v axis - texcoords origin is top left but model uv origin is from bottom left
                v1 = t + h - v1
                v2 = v1 - vh

                quadface = faceInfo.face
                cullface = faceInfo.cullface
                getBlockFaceVertices(modelQuads.quads[i].xyzuvstc,
                                     faceInfo.x1, faceInfo.y1, faceInfo.z1,
                                     faceInfo.x2, faceInfo.y2, faceInfo.z2,
                                     quadface, u1, v1, u2, v2, faceInfo.textureRotation)

                if faceInfo.variantYrot:
                    quadface = rotateFace(quadface, 1, faceInfo.variantYrot)
                if faceInfo.variantZrot:
                    quadface = rotateFace(quadface, 2, faceInfo.variantZrot)
                if faceInfo.variantXrot:
                    quadface = rotateFace(quadface, 0, faceInfo.variantXrot)
                if cullface != -1:
                    if faceInfo.variantYrot:
                        cullface = rotateFace(cullface, 1, faceInfo.variantYrot)
                    if faceInfo.variantZrot:
                        cullface = rotateFace(cullface, 2, faceInfo.variantZrot)
                    if faceInfo.variantXrot:
                        cullface = rotateFace(cullface, 0, faceInfo.variantXrot)

                applyRotations(faceInfo.ox, faceInfo.oy, faceInfo.oz,
                               faceInfo.elementMatrix, faceInfo.variantMatrix,
                               modelQuads.quads[i].xyzuvstc)

                rgba = <unsigned char *>modelQuads.quads[i].xyzuvstc
                if faceInfo.shade:
                    shade = faceShades[quadface]
                    for j in range(4):
                        rgba[28 + 32*j + 0] = shade
                        rgba[28 + 32*j + 1] = shade
                        rgba[28 + 32*j + 2] = shade
                        rgba[28 + 32*j + 3] = 0xff

                else:
                    for j in range(4):
                        rgba[28 + 32*j + 0] = 0xff
                        rgba[28 + 32*j + 1] = 0xff
                        rgba[28 + 32*j + 2] = 0xff
                        rgba[28 + 32*j + 3] = 0xff

                modelQuads.quads[i].biomeTintType = 0
                if faceInfo.tintcolor is not None:
                    #log.info("Applying tint color for face %d of %s, biomeTint=%d", i, nameAndState, faceInfo.biomeTintType)
                    if faceInfo.biomeTintType is BIOME_NONE:
                        tr, tg, tb = faceInfo.tintcolor
                        for j in range(4):
                            rgba[28 + 32*j + 0] = (tr * rgba[28 + 32*j + 0]) >> 8
                            rgba[28 + 32*j + 1] = (tg * rgba[28 + 32*j + 1]) >> 8
                            rgba[28 + 32*j + 2] = (tb * rgba[28 + 32*j + 2]) >> 8
                    else:
                        modelQuads.quads[i].biomeTintType = faceInfo.biomeTintType

                #cookedQuads.append((xyzuvstc, cullface, face))
                if cullface != -1:
                    modelQuads.quads[i].cullface[0] = 1
                    vec = _faceVector(cullface)
                    modelQuads.quads[i].cullface[1] = vec[0]
                    modelQuads.quads[i].cullface[2] = vec[1]
                    modelQuads.quads[i].cullface[3] = vec[2]
                else:
                    modelQuads.quads[i].cullface[0] = 0
                    modelQuads.quads[i].cullface[1] = 0
                    modelQuads.quads[i].cullface[2] = 0
                    modelQuads.quads[i].cullface[3] = 0


                vec = _faceVector(quadface)
                modelQuads.quads[i].quadface[0] = int(quadface)
                modelQuads.quads[i].quadface[1] = vec[0]
                modelQuads.quads[i].quadface[2] = vec[1]
                modelQuads.quads[i].quadface[3] = vec[2]

            # cookedModels[nameAndState] = cookedQuads
            if nameAndState == UNKNOWN_BLOCK:
                unknownBlockModel = modelQuads
            else:
                self.cookedModelsByID[ID][meta] = modelQuads

        for ID in range(4096):
            for meta in range(16):
                if self.cookedModelsByID[ID][meta].count == 0:
                    self.cookedModelsByID[ID][meta] = unknownBlockModel

        self.cookedModels = cookedModels
        self.cooked = True

        self.cookFluidQuads()

    def cookFluidQuads(self):
        cdef ModelQuadList * modelQuads
        cdef float[:] quadVerts, modelQuadVerts
        cdef short * fv
        cdef short dx, dy, dz
        cdef cnp.ndarray varray = np.empty(shape=(4, 8), dtype='f4')

        for filled in range(9):
            box = FloatBox((0, 0, 0), (1, ((8 - filled) / 9.0) if filled < 8 else 1.0, 1))

            modelQuads = &self.fluidQuads[filled]
            modelQuads.count = 6
            modelQuads.quads = <ModelQuad *>malloc(6 * sizeof(ModelQuad))

            for face in range(6):
                modelQuads.quads[face].cullface[0] = 0

                fv = _faceVector(face)
                dx = fv[0]
                dy = fv[1]
                dz = fv[2]

                modelQuads.quads[face].quadface[0] = <int>face
                modelQuads.quads[face].quadface[1] = dx
                modelQuads.quads[face].quadface[2] = dy
                modelQuads.quads[face].quadface[3] = dz

                getBlockFaceVertices(<float *>varray.data,
                                     box.minx, box.miny, box.minz,
                                     box.maxx, box.maxy, box.maxz,
                                     face, 0, 0, 16, 16, 0)

                varray.view('uint8')[:, 28:] = faceShades[face]

                quadVerts = varray.ravel()
                modelQuadVerts = modelQuads.quads[face].xyzuvstc
                modelQuadVerts[:] = quadVerts[:]



cdef short FaceEast   = 0
cdef short FaceWest   = 1
cdef short FaceUp     = 2
cdef short FaceDown   = 3
cdef short FaceSouth  = 4
cdef short FaceNorth  = 5

cdef short FaceXIncreasing = FaceEast
cdef short FaceXDecreasing = FaceWest
cdef short FaceYIncreasing = FaceUp
cdef short FaceYDecreasing = FaceDown
cdef short FaceZIncreasing = FaceSouth
cdef short FaceZDecreasing = FaceNorth
MaxDirections = 6

cdef short[18] faceDirections  # cython doesn't work right if the following initializer if this is a 'char'

faceDirections[:] = [
    1,  0,  0,
    -1, 0,  0,
    0,  1,  0,
    0, -1,  0,
    0,  0,  1,
    0,  0, -1,
]

cdef short * _faceVector(char face):
    return faceDirections + face * 3

faceRotations = (
    (
        FaceYIncreasing,
        FaceZIncreasing,
        FaceYDecreasing,
        FaceZDecreasing,
    ),
    (
        FaceXIncreasing,
        FaceZIncreasing,
        FaceXDecreasing,
        FaceZDecreasing,
    ),
    (
        FaceXIncreasing,
        FaceYIncreasing,
        FaceXDecreasing,
        FaceYDecreasing,
    ),

)

facesByCardinal = dict(
    east=FaceEast,
    west=FaceWest,
    up=FaceUp,
    down=FaceDown,
    south=FaceSouth,
    north=FaceNorth,
)

cdef short[6] faceShades
faceShades[:] = [
    0xCC,
    0xCC,
    0xFF,
    0x77,
    0x99,
    0x99,
]



cdef short rotateFace(short face, short axis, int degrees):
    rots = faceRotations[axis]
    try:
        idx = rots.index(face)
    except ValueError:
        return face

    while degrees > 0:
        idx += 1
        degrees -= 90
    idx %= 4
    return rots[idx]

cdef void applyRotations(float ox, float oy, float oz,
                         cnp.ndarray[ndim=2, dtype=double] elementMatrix,
                         cnp.ndarray[ndim=2, dtype=double] variantMatrix,
                         float * xyzuvstc):
    cdef int i
    cdef float x, y, z, nx, ny, nz
    if elementMatrix is not None:
        for i in range(4):
            x = xyzuvstc[i*8 + 0] - ox
            y = xyzuvstc[i*8 + 1] - oy
            z = xyzuvstc[i*8 + 2] - oz
            nx = x * elementMatrix[0, 0] + y * elementMatrix[1, 0] + z * elementMatrix[2, 0]
            ny = x * elementMatrix[0, 1] + y * elementMatrix[1, 1] + z * elementMatrix[2, 1]
            nz = x * elementMatrix[0, 2] + y * elementMatrix[1, 2] + z * elementMatrix[2, 2]
            xyzuvstc[i*8 + 0] = nx + ox
            xyzuvstc[i*8 + 1] = ny + oy
            xyzuvstc[i*8 + 2] = nz + oz

    if variantMatrix is not None:
        for i in range(4):
            x = xyzuvstc[i*8 + 0] - 0.5
            y = xyzuvstc[i*8 + 1] - 0.5
            z = xyzuvstc[i*8 + 2] - 0.5
            nx = x * variantMatrix[0, 0] + y * variantMatrix[1, 0] + z * variantMatrix[2, 0]
            ny = x * variantMatrix[0, 1] + y * variantMatrix[1, 1] + z * variantMatrix[2, 1]
            nz = x * variantMatrix[0, 2] + y * variantMatrix[1, 2] + z * variantMatrix[2, 2]
            xyzuvstc[i*8 + 0] = nx + 0.5
            xyzuvstc[i*8 + 1] = ny + 0.5
            xyzuvstc[i*8 + 2] = nz + 0.5

cdef elementRotation(dict rotation):
    if rotation is None:
        return 0, 0, 0, None

    origin = rotation["origin"]
    axis = rotation["axis"]
    angle = rotation["angle"]
    rescale = rotation.get("rescale", False)

    matrix = npRotate(axis, angle, rescale)
    ox, oy, oz = origin
    return ox / 16., oy / 16., oz / 16., matrix[:3, :3]

cdef variantRotation(variantXrot, variantYrot, variantZrot):
    if variantXrot or variantYrot or variantZrot:
        matrix = np.matrix(np.identity(4))
        if variantYrot:
            matrix *= npRotate("y", variantYrot)
        if variantXrot:
            matrix *= npRotate("x", variantXrot)
        if variantZrot:
            matrix *= npRotate("z", variantZrot)
        return matrix[:3, :3]

@lru_cache()
def npRotate(axis, angle, rescale=False):
    # ( xx(1-c)+c	xy(1-c)-zs  xz(1-c)+ys	 0  )
    # | yx(1-c)+zs	yy(1-c)+c   yz(1-c)-xs	 0  |
    # | xz(1-c)-ys	yz(1-c)+xs  zz(1-c)+c	 0  |
    # (	 0	        0		    0	         1  )
    # axis:
    # "x": (1, 0, 0)
    # "y": (0, 1, 0)
    # "z": (0, 0, 1)
    x = y = z = 0
    if axis == "x":
        x = 1
    elif axis == "y":
        y = 1
    elif axis == "z":
        z = 1
    else:
        raise ValueError("Unknown axis: %r" % axis)

    s = math.sin(math.radians(angle))
    c = math.cos(math.radians(angle))
    rotate = np.matrix([[x*x*(1-c)+c,    x*y*(1-c)-z*s,  x*z*(1-c)+y*s,  0],
                           [y*x*(1-c)+z*s,  y*y*(1-c)+c,    y*z*(1-c)-x*s,  0],
                           [x*z*(1-c)-y*s,  y*z*(1-c)+x*s,  z*z*(1-c)+c,    0],
                           [0,              0,              0,              1]])
    # xxx rescale
    return rotate



cdef void getBlockFaceVertices(float[] xyzuvstc,
                               float x1, float y1, float z1,
                               float x2, float y2, float z2,
                               short face,
                               short u1, short v1, short u2, short v2, int textureRotation):
    cdef int roll = 0

    cdef float[8] tc
    if textureRotation:
        roll = textureRotation / 90
        roll %= 4
        roll *= 2
        roll = 8 - roll

    tc[(0+roll)%8] = u1
    tc[(1+roll)%8] = v1
    tc[(2+roll)%8] = u1
    tc[(3+roll)%8] = v2
    tc[(4+roll)%8] = u2
    tc[(5+roll)%8] = v2
    tc[(6+roll)%8] = u2
    tc[(7+roll)%8] = v1

    if face == FaceXDecreasing:
        xyzuvstc[:] = [x1, y2, z1, tc[0], tc[1], 0.5, 0.5, 0.0,
                       x1, y1, z1, tc[2], tc[3], 0.5, 0.5, 0.0,
                       x1, y1, z2, tc[4], tc[5], 0.5, 0.5, 0.0,
                       x1, y2, z2, tc[6], tc[7], 0.5, 0.5, 0.0,
        ]

    elif face == FaceXIncreasing:
        xyzuvstc[:] = [x2, y2, z2, tc[0], tc[1], 0.5, 0.5, 0.0,
                       x2, y1, z2, tc[2], tc[3], 0.5, 0.5, 0.0,
                       x2, y1, z1, tc[4], tc[5], 0.5, 0.5, 0.0,
                       x2, y2, z1, tc[6], tc[7], 0.5, 0.5, 0.0,
        ]

    elif face == FaceYDecreasing:
        xyzuvstc[:] = [x1, y1, z2, tc[0], tc[1], 0.5, 0.5, 0.0,
                       x1, y1, z1, tc[2], tc[3], 0.5, 0.5, 0.0,
                       x2, y1, z1, tc[4], tc[5], 0.5, 0.5, 0.0,
                       x2, y1, z2, tc[6], tc[7], 0.5, 0.5, 0.0,
        ]

    elif face == FaceYIncreasing:
        xyzuvstc[:] = [x1, y2, z1, tc[0], tc[1], 0.5, 0.5, 0.0,
                       x1, y2, z2, tc[2], tc[3], 0.5, 0.5, 0.0,
                       x2, y2, z2, tc[4], tc[5], 0.5, 0.5, 0.0,
                       x2, y2, z1, tc[6], tc[7], 0.5, 0.5, 0.0,
        ]

    elif face == FaceZDecreasing:
        xyzuvstc[:] = [x2, y2, z1, tc[0], tc[1], 0.5, 0.5, 0.0,
                       x2, y1, z1, tc[2], tc[3], 0.5, 0.5, 0.0,
                       x1, y1, z1, tc[4], tc[5], 0.5, 0.5, 0.0,
                       x1, y2, z1, tc[6], tc[7], 0.5, 0.5, 0.0,
        ]

    elif face == FaceZIncreasing:
        xyzuvstc[:] = [x1, y2, z2, tc[0], tc[1], 0.5, 0.5, 0.0,
                       x1, y1, z2, tc[2], tc[3], 0.5, 0.5, 0.0,
                       x2, y1, z2, tc[4], tc[5], 0.5, 0.5, 0.0,
                       x2, y2, z2, tc[6], tc[7], 0.5, 0.5, 0.0,
        ]
    else:
        raise ValueError("Unknown face %s" % face)

