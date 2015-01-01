"""
    blockmodels
"""
from __future__ import absolute_import, division, print_function
import json
import logging
import numpy
from mceditlib import faces
from mceditlib.geometry import BoundingBox, Vector, FloatBox

log = logging.getLogger(__name__)


class BlockModels(object):
    def _getBlockModel(self, modelName):
        model = self.modelJsons.get(modelName)
        if model is None:
            model = json.load(self.resourceLoader.openStream("models/%s.json" % modelName))
            self.modelJsons[modelName] = model
        return model

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

        self.modelJsons = {}
        self.modelQuads = {}
        self._textureNames = set()
        self.firstTextures = {}  # first texture found for each block - used for icons (xxx)
        self.cookedModels = {}  # nameAndState -> [face -> xyzuv, cullface]

        for block in blocktypes:
            name = block.internalName.replace(blocktypes.namePrefix, "")
            if name == "air":
                continue
            try:
                statesJson = json.load(resourceLoader.openStream("blockstates/%s.json" % block.resourcePath))
            except KeyError:
                log.warn("Could not get blockstates resource for %s, skipping...", block)
                continue
            variants = statesJson['variants']
            # variants is a dict with each key a blockstate, without the "[]" around them
            # for blocks without blockstates, the key is "normal"
            # the value for this key is either a dict describing which model to use
            # ... or a list of such models to be selected from randomly
            #
            # each model dict must have a 'model' key whose value is the name of a file under assets/minecraft/models
            # model dict may also have optional keys 'x', 'y', 'z' with a value in degrees, to rotate the model
            # around that axis
            # another optional key is 'uvlock', which needs investigating

            def matchVariantState(variantState, blockState):
                # if not all keys in variantState are found in blockState, return false
                if variantState == "all":
                    return True
                try:
                    blockState = blockState[1:-1]
                    vd = [s.split("=") for s in variantState.split(",")]
                    bd = {k: v for (k, v) in (s.split("=") for s in blockState.split(","))}
                    for k, v in vd:
                        if bd.get(k) != v:
                            return False
                    return True
                except:
                    log.info("MATCHING %s %s", variantState, blockState)
                    raise

            for variantBlockState in variants:
                if variantBlockState != "normal" and not matchVariantState(variantBlockState, block.blockState):
                    continue
                variantDict = variants[variantBlockState]
                if isinstance(variantDict, list):
                    variantDict = variantDict[0]  # do the random pick thing later, if at all
                modelName = variantDict['model']
                modelDict = self._getBlockModel("block/" + modelName)

                # model will either have an 'elements' key or a 'parent' key (maybe both).
                # 'parent' will be the name of a model
                # following 'parent' keys will eventually lead to a model with 'elements'
                #
                # 'elements' is a list of dicts each describing a cube that makes up the model.
                # each cube dict has 'from' and 'to' keys, which are lists of 3 float coordinates.
                #
                # the 'crossed squares' model demonstrates most of the keys found in a cube element
                #
                # {   "from": [ 0.8, 0, 8 ],
                # "to": [ 15.2, 16, 8 ],
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
                # the result of loading a model should be a list of quads, with four vertexes and four pairs of texture
                # coordinates each, plus a Face telling which adjacent block when present causes that quad to be
                # culled.

                textureVars = {}
                allElements = []

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
                    modelDict = self._getBlockModel(parentName)
                else:
                    raise ValueError("Parent loop detected in block model %s" % modelName)

                try:

                    allQuads = []

                    for element in allElements:
                        fromPoint = Vector(*element["from"])
                        toPoint = Vector(*element["to"])
                        fromPoint /= 16.
                        toPoint /= 16.

                        box = FloatBox(fromPoint, maximum=toPoint)
                        for face, info in element["faces"].iteritems():
                            texture = info["texture"]
                            lastvar = texture
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

                            self.firstTextures.setdefault(name, texture)
                            self._textureNames.add(texture)
                            allQuads.append((box, facesByCardinal[face], texture, info.get("uv", [ 0, 0, 16, 16 ]),
                                             info.get("cullface")))

                        # element["rotation"] xxxxxxxxxx
                    self.modelQuads[block.internalName + block.blockState] = allQuads

                except Exception as e:
                    log.error("Failed to parse variant of block %s\nelements:\n%s\ntextures:\n%s", name,
                              allElements, textureVars)
                    raise

        # for name in self.modelQuads:
        #    log.info("Quads for %s:\n%s\n", name, self.modelQuads[name])
        # raise SystemExit

    def getTextureNames(self):
        return iter(self._textureNames)

    def cookQuads(self, textureAtlas):
        cookedModels = {}
        for nameAndState, allQuads in self.modelQuads.iteritems():
            cookedQuads = []
            for (box, face, texture, uv, cullface) in allQuads:
                l, t, w, h = textureAtlas.texCoordsByName[texture]
                u1, v1, u2, v2 = uv # xxxx (u2-u1) / w etc scale to texture width
                u1 += l
                u2 += l
                v1 += t
                v2 += t
                uv = (u1, v1, u2, v2)

                xyzuv = getBlockFaceVertices(box, face, uv)
                if cullface:
                    cullface = facesByCardinal[cullface]
                cookedQuads.append((face, xyzuv, cullface))

            cookedModels[nameAndState] = cookedQuads

        self.cookedModels = cookedModels

facesByCardinal = dict(
    north=faces.FaceNorth,
    south=faces.FaceSouth,
    east=faces.FaceEast,
    west=faces.FaceWest,
    up=faces.FaceUp,
    down=faces.FaceDown,

)

# teutures = (u1, v1, u2, v1, u2, v2, u1, v2)

def getBlockFaceVertices(box, face, uv):
    x, y, z, = box.origin
    x2, y2, z2 = box.maximum
    u1, v1, u2, v2 = uv
    if face == faces.FaceXDecreasing:
        faceVertices = numpy.array(
            (x, y, z, u1, v1,
             x, y2, z, u1, v2,
             x, y2, z2, u2, v2,
             x, y, z2, u2, v1,
             ), dtype='f4')

    elif face == faces.FaceXIncreasing:
        faceVertices = numpy.array(
            (x2, y, z, u1, v1,
             x2, y2, z, u1, v2,
             x2, y2, z2, u2, v2,
             x2, y, z2, u2, v1,
             ), dtype='f4')

    elif face == faces.FaceYDecreasing:
        faceVertices = numpy.array(
            (x2, y, z2, u1, v1,
             x, y, z2, u1, v2,
             x, y, z, u2, v2,
             x2, y, z, u2, v1,
             ), dtype='f4')

    elif face == faces.FaceYIncreasing:
        faceVertices = numpy.array(
            (x2, y2, z, u1, v1,
             x, y2, z, u1, v2,
             x, y2, z2, u2, v2,
             x2, y2, z2, u2, v1,
             ), dtype='f4')

    elif face == faces.FaceZDecreasing:
        faceVertices = numpy.array(
            (x, y, z, u1, v1,
             x, y2, z, u1, v2,
             x2, y2, z, u2, v2,
             x2, y, z, u2, v1,
             ), dtype='f4')

    elif face == faces.FaceZIncreasing:
        faceVertices = numpy.array(
            (x2, y, z2, u1, v1,
             x2, y2, z2, u1, v2,
             x, y2, z2, u2, v2,
             x, y, z2, u2, v1
             ), dtype='f4')
    else:
        raise ValueError("Unknown face %s" % face)

    return faceVertices
