"""
    models
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import collections
import logging
import math
import numpy
from mcedit2.rendering.chunkmeshes.entity.armorstand import ModelArmorStand
from mcedit2.rendering.chunkmeshes.entity.biped import ModelZombie, ModelSkeleton, \
    ModelPigZombie
from mcedit2.rendering.chunkmeshes.entity.chest import ModelChest, ModelLargeChest
from mcedit2.rendering.chunkmeshes.entity.creeper import ModelCreeper
from mcedit2.rendering.chunkmeshes.entity.player import ModelPlayer
from mcedit2.rendering.chunkmeshes.entity.quadruped import ModelPig, ModelCow, ModelSheep, \
    ModelSheepWool
from mcedit2.rendering.chunkmeshes.entity.shulker import ModelShulker
from mcedit2.rendering.chunkmeshes.entity.spider import ModelSpider
from mcedit2.rendering.chunkmeshes.entity.villager import ModelVillager

log = logging.getLogger(__name__)


def makeQuad(c1, c2, c3, c4, u1, v1, u2, v2):
    return [
        c1 + (u2, v1),
        c2 + (u1, v1),
        c3 + (u1, v2),
        c4 + (u2, v2),
    ]


def makeBoxQuads(box):
    u, v = box.u, box.v
    x, y, z = box.x, box.y, box.z
    x2, y2, z2 = box.x2, box.y2, box.z2
    expandOffset = box.expandOffset
    x -= expandOffset
    y -= expandOffset
    z -= expandOffset
    x2 += expandOffset
    y2 += expandOffset
    z2 += expandOffset

    if box.mirror:
        x, x2 = x2, x


    xyz =       x, y, z
    x2yz =      x2, y, z
    xy2z =      x, y2, z
    xyz2 =      x, y, z2
    x2y2z =     x2, y2, z
    x2yz2 =     x2, y, z2
    xy2z2 =     x, y2, z2
    x2y2z2 =    x2, y2, z2
    dx, dy, dz = box.dx, box.dy, box.dz

    quadArgs = [
        (x2yz2, x2yz, x2y2z, x2y2z2,
         u + dz + dx,        v + dz, u + dz + dx + dz,       v + dz + dy),

        (xyz, xyz2, xy2z2, xy2z,
         u,                  v + dz, u + dz,                 v + dz + dy),

        (x2yz2, xyz2, xyz, x2yz,
         u + dz,             v,      u + dz + dx,            v + dz),

        (x2y2z, xy2z, xy2z2, x2y2z2,
         u + dz + dx,        v + dz, u + dz + dx + dx,       v),

        (x2yz, xyz, xy2z, x2y2z,
         u + dz,             v + dz, u + dz + dx,            v + dz + dy),

        (xyz2, x2yz2, x2y2z2, xy2z2,
         u + dz + dx + dz,   v + dz, u + dz + dx + dz + dx,  v + dz + dy),
    ]
    quads = []
    for a in quadArgs:
        quad = makeQuad(*a)
        if box.mirror:
            quad = reversed(quad)
        quads.extend(quad)

    return quads


# xxx dup from blockmodels.pyx
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

    s = math.sin(angle)
    c = math.cos(angle)
    rotate = numpy.matrix([[x*x*(1-c)+c,    x*y*(1-c)-z*s,  x*z*(1-c)+y*s,  0],
                           [y*x*(1-c)+z*s,  y*y*(1-c)+c,    y*z*(1-c)-x*s,  0],
                           [x*z*(1-c)-y*s,  y*z*(1-c)+x*s,  z*z*(1-c)+c,    0],
                           [0,              0,              0,              1]])
    # xxx rescale
    return rotate

CookedModel = collections.namedtuple('CookedModel', 'vertices texWidth texHeight modelTexture')

def cookEntityModel(model):
    allVerts = []
    for part in model.parts:
        partVerts = []
        for box in part.boxes:
            partVerts.extend(makeBoxQuads(box))

        cx, cy, cz = part.cx, part.cy, part.cz
        rx, ry, rz = part.rx, part.ry, part.rz
        partMatrix = numpy.identity(4)
        if ry:
            partMatrix = npRotate("y", ry) * partMatrix
        if rx:
            partMatrix = npRotate("x", rx) * partMatrix
        if rz:
            partMatrix = npRotate("z", rz) * partMatrix

        for x, y, z, u, v in partVerts:
            coord = numpy.matrix([x, y, z, 0]).T
            x, y, z = numpy.array(partMatrix * coord)[:3, 0]

            allVerts.append((x+cx, y+cy, z+cz, u, v))

    return CookedModel(allVerts, model.textureWidth, model.textureHeight, model.modelTexture)

cookedModels = {}
models = {}

cookedTileEntityModels = {}
tileEntityModels = {}


def addModel(model):
    if hasattr(model, 'id'):
        cookedModels[model.id] = cookEntityModel(model)
        models[model.id] = model
    else:
        cookedTileEntityModels[model.tileEntityID] = cookEntityModel(model)
        tileEntityModels[model.tileEntityID] = model


def getModelTexture(entityRef):
    model = models.get(entityRef.id)
    if model is None:
        return None
    if hasattr(model, b"textureForEntity"):
        return model.textureForEntity(entityRef)
    return model.modelTexture

def getTexture(entityID):
    model = models.get(entityID)
    return model.modelTexture

addModel(ModelPlayer())
addModel(ModelCreeper())
addModel(ModelZombie())
addModel(ModelSkeleton())
addModel(ModelPigZombie())
addModel(ModelSpider())
addModel(ModelPig())
addModel(ModelCow())
addModel(ModelSheep())
addModel(ModelSheepWool())
addModel(ModelVillager())
addModel(ModelArmorStand())
addModel(ModelChest())
addModel(ModelLargeChest())
addModel(ModelShulker())

if __name__ == '__main__':
    from pprint import pprint
    pprint(cookedModels["Sheep"])