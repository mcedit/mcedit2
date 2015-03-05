#cython: boundscheck=False, profile=True
"""
    blockmodels
"""
from __future__ import absolute_import, print_function
import json
import logging
import math
import itertools

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

    def __init__(self, x1, y1, z1, x2, y2, z2, face,
                 texture, u1, v1, u2, v2, cullface,
                 shade, ox, oy, oz, elementMatrix, textureRotation,
                 variantXrot, variantYrot, variantZrot, variantMatrix, tintcolor):
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



cdef class BlockModels(object):

    def _getBlockModel(self, modelName):
        if modelName == u"block/MCEDIT_UNKNOWN":
            return {
                u"parent": u"block/cube_all",
                u"textures": {
                    u"all": u"MCEDIT_UNKNOWN"
                }
            }
        model = self.modelBlockJsons.get(modelName)
        if model is None:
            model = json.load(self.resourceLoader.openStream("models/%s.json" % modelName))
            self.modelBlockJsons[modelName] = model
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
            state = json.load(self.resourceLoader.openStream("blockstates/%s.json" % stateName))
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

        self.modelBlockJsons = {}
        self.modelStateJsons = {}
        self.modelQuads = {}
        self._textureNames = set()
        self.firstTextures = {}  # first texture found for each block - used for icons (xxx)
        self.cookedModels = {}  # nameAndState -> list[(xyzuvstc, cullface)]
        #self.cookedModelsByID = numpy.zeros((256*16, 16), dtype=list)  # (id, meta) -> list[(xyzuvstc, cullface)]
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

        for i, block in enumerate(list(blocktypes) + [missingnoProxy]):
            if i % 100 == 0:
                log.info("Loading block models %s/%s", i, len(blocktypes))

            if block.renderType != 3:  # only rendertype 3 uses block models
                continue
            nameAndState = block.internalName + block.blockState
            try:
                statesJson = self._getBlockState(block.resourcePath)
            except ResourceNotFound as e:
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

            variantBlockState = block.resourceVariant
            log.debug("Loading %s#%s for %s", block.resourcePath, block.resourceVariant, block)
            variantDict = variants[variantBlockState]
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

            try:
                # each element describes a box with up to six faces, each with a texture. convert the box into
                # quads.
                allQuads = []

                if block.internalName == "minecraft:redstone_wire":
                    blockColor = (0xff, 0x33, 0x00)
                else:
                    blockColor = block.color
                    r = (blockColor >> 16) & 0xff
                    g = (blockColor >> 8) & 0xff
                    b = blockColor & 0xff
                    blockColor = r, g, b

                variantMatrix = variantRotation(variantXrot, variantYrot, variantZrot)
                for element in allElements:
                    quads = self.buildBoxQuads(element, nameAndState, textureVars, variantXrot, variantYrot, variantZrot, variantMatrix, blockColor)
                    allQuads.extend(quads)



                self.modelQuads[block.internalName + block.blockState] = allQuads

            except Exception as e:
                log.error("Failed to parse variant of block %s\nelements:\n%s\ntextures:\n%s", nameAndState,
                          allElements, textureVars)
                raise


    def buildBoxQuads(self, element, nameAndState, textureVars, variantXrot, variantYrot, variantZrot, variantMatrix, blockColor):
        quads = []
        shade = element.get("shade", True)
        fromPoint = Vector(*element["from"])
        toPoint = Vector(*element["to"])
        fromPoint /= 16.
        toPoint /= 16.
        box = FloatBox(fromPoint, maximum=toPoint)
        ox, oy, oz, elementMatrix = elementRotation(element.get("rotation"))
        cdef float x1, y1, z1
        x1, y1, z1 = box.origin
        cdef float x2, y2, z2
        x2, y2, z2 = box.maximum
        cdef short u1, v1, u2, v2

        for face, info in element["faces"].iteritems():
            face = facesByCardinal[face]
            texture = info["texture"]
            cullface = info.get("cullface")

            u1, v1, u2, v2 = info.get("uv", [0, 0, 16, 16])

            lastvar = texture

            tintindex = info.get("tintindex")
            if tintindex is not None:
                tintcolor = blockColor
            else:
                tintcolor = None

            # resolve texture variables
            for i in range(30):
                if texture is None:
                    raise ValueError("Texture variable %s is not assigned." % lastvar)
                elif texture[0] == "#":
                    lastvar = texture
                    texture = textureVars[texture[1:]]
                else:
                    break
            else:
                raise ValueError("Texture variable loop detected!")

            self.firstTextures.setdefault(nameAndState, texture)
            self._textureNames.add(texture)

            quads.append(FaceInfo(x1, y1, z1, x2, y2, z2, face,
                    texture, u1, v1, u2, v2, facesByCardinal[cullface] if cullface is not None else -1,
                    shade, ox, oy, oz, elementMatrix, info.get("rotation", 0),
                    variantXrot, variantYrot, variantZrot, variantMatrix, tintcolor))

        return quads

    def getTextureNames(self):
        return itertools.chain(iter(self._textureNames), ['blocks/water_still', 'blocks/lava_still'])

    def cookQuads(self, textureAtlas):
        if self.cooked:
            return

        log.info("Cooking quads for %d models...", len(self.modelQuads))
        cookedModels = {}
        cdef short ID, meta
        cdef int l, t, w, h
        cdef short u1, u2, v1, v2
        cdef int uw, vh
        cdef short quadface, cullface, shade
        cdef ModelQuadList modelQuads
        cdef ModelQuadList unknownBlockModel
        UNKNOWN_BLOCK = u'MCEDIT_UNKNOWN'

        cdef float[:] modelxyzuvstc, quadxyzuvstc
        cdef size_t i;

        cdef dict texCoordsByName = textureAtlas.texCoordsByName
        cdef FaceInfo faceInfo
        cdef short * vec

        cdef cnp.ndarray xyzuvstc = np.empty(shape=(4, 8), dtype='f4')

        for nameAndState, allQuads in self.modelQuads.iteritems():
            if nameAndState != UNKNOWN_BLOCK:
                try:
                    ID, meta = self.blocktypes.IDsByState[nameAndState]
                except KeyError:
                    continue  # xxx stash models somewhere for user-configuration

            modelQuads.count = len(allQuads)
            modelQuads.quads = <ModelQuad *>malloc(modelQuads.count * sizeof(ModelQuad))

            for i, faceInfo in enumerate(allQuads):

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
                getBlockFaceVertices(<float *>xyzuvstc.data,
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

                applyRotations(faceInfo.ox, faceInfo.oy, faceInfo.oz, faceInfo.elementMatrix, faceInfo.variantMatrix, xyzuvstc)

                rgba = xyzuvstc.view('uint8')[:, 28:]
                if faceInfo.shade:
                    rgba[:] = faceShades[quadface]
                else:
                    rgba[:] = 0xff

                if faceInfo.tintcolor is not None:
                    tintcolor = faceInfo.tintcolor
                    rgba[..., 0] = (tintcolor[0] * int(rgba[0, 0])) >> 8
                    rgba[..., 1] = (tintcolor[1] * int(rgba[0, 1])) >> 8
                    rgba[..., 2] = (tintcolor[2] * int(rgba[0, 2])) >> 8


                #cookedQuads.append((xyzuvstc, cullface, face))
                quadxyzuvstc = modelQuads.quads[i].xyzuvstc
                modelxyzuvstc = xyzuvstc.ravel()
                quadxyzuvstc[:] = modelxyzuvstc[:]
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
        idx -= 1
        degrees -= 90
    idx %= 4
    return rots[idx]

cdef applyRotations(float ox, float oy, float oz,
                    cnp.ndarray[ndim=2,dtype=double] elementMatrix,
                    cnp.ndarray[ndim=2,dtype=double] variantMatrix,
                    cnp.ndarray[ndim=2,dtype=float] xyzuvstc):
    cdef int i
    cdef float x, y, z, nx, ny, nz
    if elementMatrix is not None:
        for i in range(4):
            x = xyzuvstc[i, 0] - ox
            y = xyzuvstc[i, 1] - oy
            z = xyzuvstc[i, 2] - oz
            nx = x * elementMatrix[0, 0] + y * elementMatrix[1, 0] + z * elementMatrix[2, 0]
            ny = x * elementMatrix[0, 1] + y * elementMatrix[1, 1] + z * elementMatrix[2, 1]
            nz = x * elementMatrix[0, 2] + y * elementMatrix[1, 2] + z * elementMatrix[2, 2]
            xyzuvstc[i, 0] = nx + ox
            xyzuvstc[i, 1] = ny + oy
            xyzuvstc[i, 2] = nz + oz

    if variantMatrix is not None:
        for i in range(4):
            x = xyzuvstc[i, 0] - 0.5
            y = xyzuvstc[i, 1] - 0.5
            z = xyzuvstc[i, 2] - 0.5
            nx = x * variantMatrix[0, 0] + y * variantMatrix[1, 0] + z * variantMatrix[2, 0]
            ny = x * variantMatrix[0, 1] + y * variantMatrix[1, 1] + z * variantMatrix[2, 1]
            nz = x * variantMatrix[0, 2] + y * variantMatrix[1, 2] + z * variantMatrix[2, 2]
            xyzuvstc[i, 0] = nx + 0.5
            xyzuvstc[i, 1] = ny + 0.5
            xyzuvstc[i, 2] = nz + 0.5

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
            matrix *= npRotate("y", -variantYrot)
        if variantXrot:
            matrix *= npRotate("x", -variantXrot)
        if variantZrot:
            matrix *= npRotate("z", -variantZrot)
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



cdef getBlockFaceVertices(float[] xyzuvstc,
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

