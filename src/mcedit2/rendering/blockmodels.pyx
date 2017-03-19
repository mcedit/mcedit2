#cython: boundscheck=False
"""
    blockmodels
"""
from __future__ import absolute_import, print_function
from collections import defaultdict
import json
import logging
import math
import itertools
from PySide import QtGui

import numpy as np
cimport numpy as cnp
from mcedit2.util import resources

cnp.import_array()

from mcedit2.resourceloader import ResourceNotFound

from mceditlib.blocktypes import BlockType
from mceditlib.cachefunc import lru_cache
from mceditlib.geometry import Vector
from mceditlib.selection import FloatBox
from mceditlib.blocktypes import splitInternalName

from libc.stdlib cimport malloc, free
from libc.string cimport memset

log = logging.getLogger(__name__)

DEF MAX_TEXTURE_RECURSIONS = 200

cdef struct ModelQuad:
    float[32] xyzuvstc
    char[4] cullface  # isCulled, dx, dy, dz
    char[4] quadface  # face, dx, dy, dz
    char biomeTintType

cdef struct ModelQuadList:
    int count
    ModelQuad *quads

cdef class ModelQuadListObj(object):
    pass  # defined in blockmodels.pxd


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
        int variantXrot, variantYrot
        object tintcolor
        char biomeTintType

    def __init__(self, x1, y1, z1, x2, y2, z2, face,
                 texture, u1, v1, u2, v2, cullface,
                 shade, ox, oy, oz, elementMatrix, textureRotation,
                 variantXrot, variantYrot, variantMatrix, tintcolor, biomeTintType):
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
        self.variantMatrix = variantMatrix
        self.tintcolor = tintcolor
        self.biomeTintType = biomeTintType

UNKNOWN_MODEL = {
    u"parent": u"block/cube_all",
    u"textures": {
        u"all": u"MCEDIT_UNKNOWN"
    }
}
"""
Some blocks have blockStates not represented in the world file.
These will have additional blockStates with corresponding resourceVariants that do not
have a unique ID/meta combination.

To make these additional block states renderable, we will need to have a function
`getActualBlockState` to get the state, and another function to get the resourceVariant
for that state. We will also need to load the model specified by the resourceVariant
into BlockModels.

Since BlockModels only stores models in an ID/meta lookup table, these "extra" models
will need to be stored differently. Storing all of the models in a dict keyed to the
blockstate would be expensive, as we'd need up to 4k dict lookups per section.

One possible solution is to assign an internal numeric ID to each
internalName+blockState combination, and use a table to map ID/meta to our own internal
ID, and use a dict to map the internalName+blockState to our internal ID. This skips
the dict lookup for states that actually are represented as ID/meta, so only states
that are returned by `getActualBlockState` will be looked up textually.


"""
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

    def _getBlockState(self, stateName, fallback=False):
        if stateName == u"MCEDIT_UNKNOWN":
            return {
                u"variants": {
                    u"MCEDIT_UNKNOWN": {
                        u"model": u"MCEDIT_UNKNOWN",
                    }
                }
            }
        state = self.modelStateJsons.get((stateName, fallback))
        if state is None:
            state = json.load(self.resourceLoader.openStream("assets/minecraft/blockstates/%s.json" % stateName, fallback))
            self.modelStateJsons[stateName, fallback] = state
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
        self.quadsByResourcePathVariant = {}
        self.blockStatesByResourcePathVariant = defaultdict(list)
        self.cookedModelsByBlockState = {}

        self._texturePaths = set()
        self.firstTextures = {}  # first texture found for each block - used for icons (xxx)
        self.cookedModels = {}  # nameAndState -> list[(xyzuvstc, cullface)]

        memset(self.cookedModelsByID, 0, sizeof(self.cookedModelsByID))
        self.cooked = False

        missingnoProxy = BlockType(-1, -1, blocktypes)
        missingnoProxy.internalName = missingnoProxy.nameAndState = u"MCEDIT_UNKNOWN"
        missingnoProxy.blockState = ""

        missingnoProxy.renderType = 3
        missingnoProxy.resourcePath = u"MCEDIT_UNKNOWN"
        missingnoProxy.resourceVariant = u"MCEDIT_UNKNOWN"
        missingnoProxy.color = 0xFFFFFF
        log.info("Loading block models...")

        cdef dict modelDict, textures, textureVars
        cdef list elements
        cdef int i
        cdef short variantXrot, variantYrot
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
                if modelDict is None:
                    log.debug("No model found for %s", internalName)
                    continue

                # jam the custom models into quadsByResourcePathVariant and blockStatesByResourcePathVariant
                resourcePath = "MCEDIT_CUSTOM_" + internalName
                resourceVariant = "MCEDIT_CUSTOM_" + blockState
                self.blockStatesByResourcePathVariant[resourcePath, resourceVariant].append((internalName, blockState))
                if block.forcedModelRotation:
                    variantXrot = block.forcedModelRotation[0]
                    variantYrot = block.forcedModelRotation[1]

                parts = [(modelDict, variantXrot, variantYrot)]

            elif resourcePath is not None:
                resourceVariant = block.resourceVariant
                self.blockStatesByResourcePathVariant[resourcePath, resourceVariant].append((internalName, blockState))
                parts = self.loadResourceVariant(resourcePath, resourceVariant)
                
            if parts is None or len(parts) == 0:
                continue

            self.loadModelParts(block, resourcePath, resourceVariant, parts)

        hiddenModels = json.load(file(resources.resourcePath("mcedit2/rendering/hiddenstates_1_11.json"), "rb"))
        log.info("Loading %s hidden blockState models...", len(hiddenModels))
        hiddensLoaded = 0
        for i, hidden in enumerate(hiddenModels):
            if i % 500 == 0:
                log.debug("Loading hidden blockState models %s/%s", i, len(hiddenModels))

            nameAndState = hidden['blockState']
            resourcePath = hidden['resourcePath']
            resourceVariant = hidden['resourceVariant']
            if nameAndState in self.blockStatesByResourcePathVariant[resourcePath, resourceVariant]:
                log.debug("Model for state %s previously loaded", nameAndState)
                continue

            internalName, blockState = splitInternalName(nameAndState)
            block = blocktypes.get(internalName, None)
            if block is None:
                log.debug("No block found for block %s", internalName)
                continue

            self.blockStatesByResourcePathVariant[resourcePath, resourceVariant].append((internalName, blockState))

            if (resourcePath, resourceVariant) in self.quadsByResourcePathVariant:
                log.debug("Model for variant %s#%s previously loaded", resourcePath, resourceVariant)
                continue

            parts = self.loadResourceVariant(resourcePath, resourceVariant)
            if parts is None:
                log.debug("No blockstates file found for %s: %s#%s", nameAndState, resourcePath, resourceVariant)
                continue

            self.loadModelParts(block, resourcePath, resourceVariant, parts)
            hiddensLoaded += 1

        log.info("Found %s additional models for hidden states", hiddensLoaded)

    def loadModelParts(self, block, resourcePath, resourceVariant, parts):
        quads = []
        for modelDict, variantXrot, variantYrot in parts:
            res = self._loadModel(block, resourcePath, resourceVariant, modelDict, variantXrot, variantYrot)
            quads.extend(res)

        self.quadsByResourcePathVariant[resourcePath, resourceVariant] = quads

    def _loadModel(self, block, resourcePath, resourceVariant, modelDict, variantXrot, variantYrot):

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

        # grab textures and elements from this model, then get parent and merge its textures and elements
        # continue until no parent is found
        rawTextureVars = {}
        allElements = []

        for i in range(MAX_TEXTURE_RECURSIONS):
            textures = modelDict.get("textures")
            if textures is not None:
                rawTextureVars.update(textures)
            elements = modelDict.get("elements")
            if elements is not None:
                allElements.extend(elements)
            parentName = modelDict.get("parent")
            if parentName is None:
                break
            try:
                modelDict = self._getBlockModel(parentName)
            except Exception as e:
                log.exception("Error parsing json for block/%s: %s", parentName, e)
                return
        else:
            log.error("Parent loop detected in block model for %s" % block.nameAndState)
            return

        if block.forcedModelTextures:  # user-configured model textures
            for var, tex in block.forcedModelTextures.iteritems():
                rawTextureVars[var[1:]] = tex

        # pre-resolve texture vars

        textureVars = {}
        for k, v in rawTextureVars.iteritems():
            while v is not None and v.startswith("#"):
                v = rawTextureVars.get(v[1:])
            if v:
                textureVars[k] = v


        if block.biomeTintType == "grass":
            biomeTintType = BIOME_GRASS
        elif block.biomeTintType == "foliage":
            biomeTintType = BIOME_FOLIAGE
        elif block.biomeTintType == "foliagePine":
            biomeTintType = BIOME_FOLIAGE_PINE
        elif block.biomeTintType == "foliageBirch":
            biomeTintType = BIOME_FOLIAGE_BIRCH
        else:
            biomeTintType = BIOME_NONE

        # each element describes a box with up to six faces, each with a texture. convert the box into
        # quads.
        allQuads = []

        try:

            if block.internalName == "minecraft:redstone_wire":
                blockColor = (0xff, 0xff, 0xff)
                biomeTintType = BIOME_REDSTONE
            else:
                blockColor = block.color
                r = (blockColor >> 16) & 0xff
                g = (blockColor >> 8) & 0xff
                b = blockColor & 0xff
                blockColor = r, g, b

            variantMatrix = variantRotation(variantXrot, variantYrot)
            for element in allElements:
                quads = self.buildBoxQuads(element, block.nameAndState, textureVars,
                                           variantXrot, variantYrot,
                                           variantMatrix, blockColor, biomeTintType)
                if quads:
                    allQuads.extend(quads)


        except Exception as e:
            log.error("Failed to parse variant of block %s\nelements:\n%s\ntextures:\n%s",
                      block.nameAndState, allElements, rawTextureVars)

        return allQuads

    def loadResourceVariant(self, resourcePath, resourceVariant):
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
        if (resourcePath, resourceVariant) in self.quadsByResourcePathVariant:
            log.debug("Model %s#%s already loaded", resourcePath, resourceVariant)
            return None

        log.debug("Loading %s#%s", resourcePath, resourceVariant)
        try:
            statesJson = self._getBlockState(resourcePath)
        except ResourceNotFound as e:
            # if block.internalName.startswith("minecraft:"):
            #     log.warn("Could not get blockstates resource for %s, skipping... (%r)", block, e)
            log.warn("Could not get blockstates resource for %s#%s, skipping... (%r)", resourcePath, resourceVariant, e)
            return None

        variants = statesJson.get('variants')
        if variants is not None:
            variantDict = variants.get(resourceVariant)
            if variantDict is None:
                log.warn("Could not get variant key for %s#%s, skipping...", resourcePath, resourceVariant)
                return None

            if isinstance(variantDict, list):
                if len(variantDict):
                    variantDict = variantDict[0]  # do the random pick thing later, if at all
                else:
                    log.warn("Variant key for %s#%s contains no variants, skipping...", resourcePath, resourceVariant)
                    return None
            
            modelName = variantDict.get('model')

            if modelName is None:
                log.warn("No 'model' key found for variant %s in 'variants' key of states file %s, skipping...", resourceVariant, resourcePath)
                return None

            try:
                modelDict = self._getBlockModel("block/" + modelName)
            except ResourceNotFound as e:
                log.exception("Could not get model resource %s, skipping... (%r)", modelName, e)
                return None
            except ValueError as e:
                log.exception("Error parsing json for block/%s: %s", modelName, e)
                return None
            variantXrot = variantDict.get("x", 0)
            variantYrot = variantDict.get("y", 0)
            return [(modelDict, variantXrot, variantYrot)]

        multipart = statesJson.get('multipart')

        def matchWhen(when, variantMap):
            ok = True
            for key, val in when.iteritems():
                if key == 'OR':
                    ok = False
                    for when2 in val:
                        ok |= matchWhen(when2, variantMap)
                elif key == 'AND':
                    for when2 in val:
                        ok &= matchWhen(when2, variantMap)
                else:
                    varVal = variantMap.get(key)

                    if varVal is None:
                        ok = False

                    if str(varVal).lower() != str(val).lower():
                        # Gross, values in multipart may be raw values but values in resourceVariant are strings...
                        ok = False

            return ok

        if multipart is not None:
            # Multipart looks like this:
            # [
            # {   "when": {"north": false, "east": false, "south": false, "west": false, "up": false},
            #     "apply": [
            #         { "model": "fire_floor0" },
            #         { "model": "fire_floor1" }
            #     ]
            # },
            # {   "when": {"OR": [{"north": true}, {"north": false, "east": false, "south": false, "west": false, "up": false}]},
            #     "apply": [
            #         { "model": "fire_side0" },
            #         { "model": "fire_side1" },
            #         { "model": "fire_side_alt0" },
            #         { "model": "fire_side_alt1" }
            #     ]
            # }
            # ]
            variantMap = dict(pair.split('=') for pair in resourceVariant.split(','))
            ret = []

            for part in multipart:
                ok = True
                when = part.get('when')
                if when is not None:
                    ok = matchWhen(when, variantMap)

                if ok:
                    apply = part.get('apply')
                    if apply is not None:
                        if not isinstance(apply, list):
                            apply = [apply]
                            
                        for model in apply:
                            modelName = model.get('model')
                            if modelName is None:
                                continue
                            try:
                                modelDict = self._getBlockModel("block/" + modelName)
                            except ResourceNotFound as e:
                                log.exception("Could not get model resource %s, skipping... (%r)", modelName, e)
                                continue
                            except ValueError as e:
                                log.exception("Error parsing json for block/%s: %s", modelName, e)
                                continue

                            variantXrot = model.get('x', 0)
                            variantYrot = model.get('y', 0)
                            ret.append((modelDict, variantXrot, variantYrot))
            
            return ret

    def buildBoxQuads(self, dict element, unicode nameAndState, dict textureVars,
                       short variantXrot, short variantYrot,
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
            for i in range(MAX_TEXTURE_RECURSIONS):
                if texture is None:
                    log.error("Texture variable %s is not assigned." % lasttexvar)
                    return None
                elif texture[0] == u"#":
                    lasttexvar = texture
                    texture = textureVars.get(texture[1:], u"MCEDIT_UNKNOWN")
                else:
                    break
            else:
                log.error("Texture variable loop detected!")
                return None

            if texture != u"MCEDIT_UNKNOWN" and not texture.endswith(".png"):
                texture = "assets/minecraft/textures/" + texture + ".png"
            self.firstTextures.setdefault(nameAndState, texture)
            self._texturePaths.add(texture)

            quads.append(FaceInfo(x1, y1, z1, x2, y2, z2, face,
                    texture, u1, v1, u2, v2, cullface,
                    shade, ox, oy, oz, elementMatrix, info.get("rotation", 0),
                    variantXrot, variantYrot, variantMatrix, tintcolor, biomeTintType))

        return quads

    def getTextureNames(self):
        return itertools.chain(iter(self._texturePaths),
                               ['assets/minecraft/textures/blocks/water_still.png',
                                'assets/minecraft/textures/blocks/lava_still.png'])

    def cookQuads(self, textureAtlas):
        cdef short ID, meta
        cdef int l, t, w, h
        cdef short u1, u2, v1, v2, tr, tg, tb
        cdef int uw, vh
        cdef short quadface, cullface
        cdef unsigned char shade
        cdef ModelQuadList modelQuads
        cdef ModelQuadList unknownBlockModel
        cdef ModelQuadListObj modelQuadsObj = None
        cdef list allQuads
        cdef size_t i, j

        cdef dict texCoordsByName = textureAtlas.texCoordsByName
        cdef FaceInfo faceInfo
        cdef short * vec
        cdef unsigned char * rgba

        if self.cooked:
            return

        log.info("Cooking quads for %d models...", len(self.quadsByResourcePathVariant))
        cookedModels = {}
        UNKNOWN_BLOCK = u'MCEDIT_UNKNOWN'

        for (path, variant), allQuads in self.quadsByResourcePathVariant.iteritems():

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

                # u1..u2 is on the scale 0..16, convert it to l..l+w
                # v1..v2 is also 0..16, but should be flipped to t+h..t
                # u /= 16.
                # u *= w
                # u += l
                # v /= 16.
                # v = -v
                # v *= h
                # v += h
                # v += t

                # TODO: read texture .mcmeta files
                # use top square of texture for now.
                h = w

                u1 = <short>(l + (u1 * w) / 16.)
                u2 = <short>(l + (u2 * w) / 16.)

                v1 = <short>(t + h + (v1 * -h) / 16.)
                v2 = <short>(t + h + (v2 * -h) / 16.)

                quadface = faceInfo.face
                cullface = faceInfo.cullface
                getBlockFaceVertices(modelQuads.quads[i].xyzuvstc,
                                     faceInfo.x1, faceInfo.y1, faceInfo.z1,
                                     faceInfo.x2, faceInfo.y2, faceInfo.z2,
                                     quadface, u1, v1, u2, v2, faceInfo.textureRotation)

                quadface = rotateFaceByVariant(quadface,
                                               faceInfo.variantXrot,
                                               faceInfo.variantYrot)
                if cullface != -1:
                    cullface = rotateFaceByVariant(cullface,
                                                   faceInfo.variantXrot,
                                                   faceInfo.variantYrot)

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

            for internalName, blockState in self.blockStatesByResourcePathVariant[path, variant]:
                if internalName != UNKNOWN_BLOCK:
                    modelQuadsObj = ModelQuadListObj()
                    modelQuadsObj.quadList = modelQuads

                    stateProps = sorted(blockState[1:-1].split(","))
                    self.cookedModelsByBlockState[internalName, tuple(stateProps)] = modelQuadsObj

                    try:
                        ID, meta = self.blocktypes.IDsByState[internalName + blockState]
                    except KeyError:
                        continue
                    
                # cookedModels[nameAndState] = cookedQuads
                if path == UNKNOWN_BLOCK:
                    unknownBlockModel = modelQuads
                else:
                    self.cookedModelsByID[ID][meta] = modelQuads

        for ID in range(4096):
            for meta in range(16):
                if self.cookedModelsByID[ID][meta].count == 0:
                    self.cookedModelsByID[ID][meta] = unknownBlockModel

        self.cookedModels = cookedModels
        self.cooked = True

        # import pprint; pprint.pprint((self.cookedModelsByBlockState)); raise SystemExit
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

    cdef cookedModelsForState(self, tuple nameAndState):
        quads = self.cookedModelsByBlockState.get(nameAndState)
        if quads is not None:
            return quads

        return _nullQuads
        #name, state = nameAndState


_nullQuads = ModelQuadListObj()

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
        FaceNorth,
        FaceDown,
        FaceSouth,
        FaceUp,
    ),
    (
        FaceNorth,
        FaceEast,
        FaceSouth,
        FaceWest,
    ),
    # (
    #     FaceXIncreasing,
    #     FaceYIncreasing,
    #     FaceXDecreasing,
    #     FaceYDecreasing,
    # ),

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

cdef short rotateFaceByVariant(short face, short variantXrot, short variantYrot):
    if variantXrot:
        face = rotateFace(face, 0, variantXrot)
    if variantYrot:
        face = rotateFace(face, 1, variantYrot)
    return face


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

    matrix = npRotate(axis, -angle, rescale)
    ox, oy, oz = origin
    return ox / 16., oy / 16., oz / 16., matrix[:3, :3]

cdef variantRotation(variantXrot, variantYrot):
    if variantXrot or variantYrot:
        matrix = np.matrix(np.identity(4))
        if variantXrot:
            matrix *= npRotate("x", variantXrot)
        if variantYrot:
            matrix *= npRotate("y", variantYrot)
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

