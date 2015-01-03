"""
    blockmodels
"""
from __future__ import absolute_import, division, print_function
import json
import logging
import math

import numpy
from mceditlib import faces
from mceditlib.geometry import Vector, FloatBox

log = logging.getLogger(__name__)


class BlockModels(object):
    def _getBlockModel(self, modelName):
        model = self.modelBlockJsons.get(modelName)
        if model is None:
            model = json.load(self.resourceLoader.openStream("models/%s.json" % modelName))
            self.modelBlockJsons[modelName] = model
        return model

    def _getBlockState(self, stateName):
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
        self.cookedModels = {}  # nameAndState -> [face -> xyzuv, cullface]

        for i, block in enumerate(blocktypes):
            if i % 100 == 0:
                log.info("Loading block models %s/%s", i, len(blocktypes))

            if block.renderType != 3:  # only rendertype 3 uses block models
                continue
            name = block.internalName.replace(blocktypes.namePrefix, "")
            try:
                statesJson = self._getBlockState(block.resourcePath)
            except KeyError:
                log.warn("Could not get blockstates resource for %s, skipping...", block)
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

                for element in allElements:
                    shade = element.get("shade", True)
                    fromPoint = Vector(*element["from"])
                    toPoint = Vector(*element["to"])
                    fromPoint /= 16.
                    toPoint /= 16.
                    box = FloatBox(fromPoint, maximum=toPoint)

                    for face, info in element["faces"].iteritems():
                        face = facesByCardinal[face]
                        texture = info["texture"]
                        cullface = info.get("cullface")

                        uv = info.get("uv", [0, 0, 16, 16])

                        lastvar = texture

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

                        self.firstTextures.setdefault(name, texture)
                        self._textureNames.add(texture)
                        allQuads.append((box, face,
                                         texture, uv, cullface,
                                         shade, element.get("rotation"), info.get("rotation"),
                                         variantXrot, variantYrot, variantZrot))




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
            for (box, face, texture, uv, cullface, shade, rotation, textureRotation,
                 variantXrot, variantYrot, variantZrot) in allQuads:

                l, t, w, h = textureAtlas.texCoordsByName[texture]
                u1, v1, u2, v2 = uv
                uw = (u2 - u1) / 16
                vh = (v2 - v1) / 16
                u1 += l
                u2 = u1 + uw * w

                # flip v axis - texcoords origin is top left but model uv origin is from bottom left
                v1 = t + h - v1
                v2 = v1 - vh * w

                uv = (u1, v1, u2, v2)

                xyzuvc = getBlockFaceVertices(box, face, uv, textureRotation)
                xyzuvc.shape = 4, 6

                if variantZrot:
                    face = rotateFace(face, 2, variantZrot)
                if variantXrot:
                    face = rotateFace(face, 0, variantXrot)
                if variantYrot:
                    face = rotateFace(face, 1, variantYrot)
                if cullface:
                    cullface = facesByCardinal[cullface]
                    if variantZrot:
                        cullface = rotateFace(cullface, 2, variantZrot)
                    if variantXrot:
                        cullface = rotateFace(cullface, 0, variantXrot)
                    if variantYrot:
                        cullface = rotateFace(cullface, 1, variantYrot)


                if rotation is not None:
                    origin = rotation["origin"]
                    axis = rotation["axis"]
                    angle = rotation["angle"]
                    rescale = rotation.get("rescale", False)
                    matrix = npRotate(axis, angle, rescale)
                    ox, oy, oz = origin
                    origin = ox/16., oy/16., oz/16.

                    xyzuvc[:, :3] -= origin
                    xyz = xyzuvc[:, :3].transpose()
                    xyzuvc[:, :3] = (matrix[:3, :3] * xyz).transpose()
                    xyzuvc[:, :3] += origin

                rotate = variantXrot or variantYrot or variantZrot
                if rotate:
                    matrix = numpy.matrix(numpy.identity(4))
                    if variantYrot:
                        matrix *= npRotate("y", -variantYrot)
                    if variantXrot:
                        matrix *= npRotate("x", -variantXrot)
                    if variantZrot:
                        matrix *= npRotate("z", -variantZrot)
                    xyzuvc[:, :3] -= 0.5, 0.5, 0.5
                    xyz = xyzuvc[:, :3].transpose()
                    xyzuvc[:, :3] = (matrix[:3, :3] * xyz).transpose()
                    xyzuvc[:, :3] += 0.5, 0.5, 0.5

                if shade:
                    xyzuvc.view('uint8')[:, 20:] = faceShades[face]
                else:
                    xyzuvc.view('uint8')[:, 20:] = 0xff



                cookedQuads.append((face, xyzuvc, cullface))

            cookedModels[nameAndState] = cookedQuads

        self.cookedModels = cookedModels

faceRotations = (
    (
        faces.FaceYIncreasing,
        faces.FaceZIncreasing,
        faces.FaceYDecreasing,
        faces.FaceZDecreasing,
    ),
    (
        faces.FaceXIncreasing,
        faces.FaceZDecreasing,
        faces.FaceXDecreasing,
        faces.FaceZIncreasing,
    ),
    (
        faces.FaceXIncreasing,
        faces.FaceYIncreasing,
        faces.FaceXDecreasing,
        faces.FaceYDecreasing,
    ),

)

def rotateFace(face, axis, degrees):
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
    rotate = numpy.matrix([[x*x*(1-c)+c,    x*y*(1-c)-z*s,  x*z*(1-c)+y*s,  0],
                           [y*x*(1-c)+z*s,  y*y*(1-c)+c,    y*z*(1-c)-x*s,  0],
                           [x*z*(1-c)-y*s,  y*z*(1-c)+x*s,  z*z*(1-c)+c,    0],
                           [0,              0,              0,              1]])
    # xxx rescale
    return rotate


facesByCardinal = dict(
    north=faces.FaceNorth,
    south=faces.FaceSouth,
    east=faces.FaceEast,
    west=faces.FaceWest,
    up=faces.FaceUp,
    down=faces.FaceDown,

)

faceShades = {
    faces.FaceNorth: 0x99,
    faces.FaceSouth: 0x99,
    faces.FaceEast: 0xCC,
    faces.FaceWest: 0xCC,
    faces.FaceUp: 0xFF,
    faces.FaceDown: 0x77,
}


def getBlockFaceVertices(box, face, uv, textureRotation):
    x1, y1, z1, = box.origin
    x2, y2, z2 = box.maximum
    u1, v1, u2, v2 = uv
    tc = [
        (u1, v1),
        (u1, v2),
        (u2, v2),
        (u2, v1),
    ]
    if textureRotation:
        while textureRotation > 0:
            tc = tc[1:] + tc[:1]
            textureRotation -= 90

    tc = numpy.array(tc)

    if face == faces.FaceXDecreasing:
        faceVertices = numpy.array(
            (x1, y2, z1, 0.0, 0.0, 0.0,
             x1, y1, z1, 0.0, 0.0, 0.0,
             x1, y1, z2, 0.0, 0.0, 0.0,
             x1, y2, z2, 0.0, 0.0, 0.0,
             ), dtype='f4')

    elif face == faces.FaceXIncreasing:
        faceVertices = numpy.array(
            (x2, y2, z2, 0.0, 0.0, 0.0,
             x2, y1, z2, 0.0, 0.0, 0.0,
             x2, y1, z1, 0.0, 0.0, 0.0,
             x2, y2, z1, 0.0, 0.0, 0.0,
             ), dtype='f4')

    elif face == faces.FaceYDecreasing:
        faceVertices = numpy.array(
            (x1, y1, z2, 0.0, 0.0, 0.0,
             x1, y1, z1, 0.0, 0.0, 0.0,
             x2, y1, z1, 0.0, 0.0, 0.0,
             x2, y1, z2, 0.0, 0.0, 0.0,
             ), dtype='f4')

    elif face == faces.FaceYIncreasing:
        faceVertices = numpy.array(
            (x1, y2, z1, 0.0, 0.0, 0.0,
             x1, y2, z2, 0.0, 0.0, 0.0,
             x2, y2, z2, 0.0, 0.0, 0.0,
             x2, y2, z1, 0.0, 0.0, 0.0,
             ), dtype='f4')

    elif face == faces.FaceZDecreasing:
        faceVertices = numpy.array(
            (x2, y2, z1, 0.0, 0.0, 0.0,
             x2, y1, z1, 0.0, 0.0, 0.0,
             x1, y1, z1, 0.0, 0.0, 0.0,
             x1, y2, z1, 0.0, 0.0, 0.0,
             ), dtype='f4')

    elif face == faces.FaceZIncreasing:
        faceVertices = numpy.array(
            (x1, y2, z2, 0.0, 0.0, 0.0,
             x1, y1, z2, 0.0, 0.0, 0.0,
             x2, y1, z2, 0.0, 0.0, 0.0,
             x2, y2, z2, 0.0, 0.0, 0.0,
             ), dtype='f4')
    else:
        raise ValueError("Unknown face %s" % face)

    faceVertices.shape = 4, 6
    faceVertices[:, 3:5] = tc

    return faceVertices
