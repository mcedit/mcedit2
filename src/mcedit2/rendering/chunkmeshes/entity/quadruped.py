"""
    pig
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import math
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)

class ModelQuadruped(object):
    textureWidth = 64
    textureHeight = 32

    def __init__(self, height, expandOffset=0.0):
        self.head = ModelRenderer(self, 0, 0)
        
        self.head.addBox(-4.0, -4.0, -8.0, 8, 8, 8, expandOffset)
        self.head.setCenterPoint(0.0, (18 - height), -6.0)
        self.body = ModelRenderer(self, 28, 8)
        self.body.addBox(-5.0, -10.0, -7.0, 10, 16, 8, expandOffset)
        self.body.setCenterPoint(0.0, (17 - height), 2.0)
        self.leg1 = ModelRenderer(self, 0, 16)
        self.leg1.addBox(-2.0, 0.0, -2.0, 4, height, 4, expandOffset)
        self.leg1.setCenterPoint(-3.0, (24 - height), 7.0)
        self.leg2 = ModelRenderer(self, 0, 16)
        self.leg2.addBox(-2.0, 0.0, -2.0, 4, height, 4, expandOffset)
        self.leg2.setCenterPoint(3.0, (24 - height), 7.0)
        self.leg3 = ModelRenderer(self, 0, 16)
        self.leg3.addBox(-2.0, 0.0, -2.0, 4, height, 4, expandOffset)
        self.leg3.setCenterPoint(-3.0, (24 - height), -5.0)
        self.leg4 = ModelRenderer(self, 0, 16)
        self.leg4.addBox(-2.0, 0.0, -2.0, 4, height, 4, expandOffset)
        self.leg4.setCenterPoint(3.0, (24 - height), -5.0)

        self.body.setRotation(math.pi/2., 0, 0)

    @property
    def parts(self):
        return [
            self.head,
            self.body,
            self.leg1,
            self.leg2,
            self.leg3,
            self.leg4,
        ]

class ModelPig(ModelQuadruped):
    id = "Pig"
    modelTexture = "assets/minecraft/textures/entity/pig/pig.png"

    def __init__(self, expandOffset=0.0):
        super(ModelPig, self).__init__(6)
        self.head.setTextureOffset(16, 16)
        self.head.addBox(-2.0, 0.0, -9.0, 4, 3, 1, expandOffset)


class ModelCow(ModelQuadruped):
    id = "Cow"
    modelTexture = "assets/minecraft/textures/entity/cow/cow.png"

    def __init__(self):
        super(ModelCow, self).__init__(12)

        self.head = ModelRenderer(self, 0, 0)
        self.head.addBox(-4.0, -4.0, -6.0, 8, 8, 6, 0.0)
        self.head.setCenterPoint(0.0, 4.0, -8.0)
        self.head.setTextureOffset(22, 0)
        self.head.addBox(-5.0, -5.0, -4.0, 1, 3, 1, 0.0)
        self.head.setTextureOffset(22, 0)
        self.head.addBox(4.0, -5.0, -4.0, 1, 3, 1, 0.0)
        self.body = ModelRenderer(self, 18, 4)
        self.body.addBox(-6.0, -10.0, -7.0, 12, 18, 10, 0.0)
        self.body.setCenterPoint(0.0, 5.0, 2.0)
        self.body.setTextureOffset(52, 0)
        self.body.addBox(-2.0, 2.0, -8.0, 4, 6, 1)

        self.body.setRotation(math.pi/2., 0, 0)

        self.leg1.cx -= 1
        self.leg2.cx += 1
        self.leg3.cx -= 1
        self.leg4.cx += 1
        self.leg3.cz -= 1
        self.leg4.cz += 1


class ModelSheepWool(ModelQuadruped):
    id = "MCEDIT_SheepWool"  # eww
    modelTexture = "assets/minecraft/textures/entity/sheep/sheep_fur.png"
    
    def __init__(self):
        super(ModelSheepWool, self).__init__(12)
        self.head = ModelRenderer(self, 0, 0)
        self.head.addBox(-3.0, -4.0, -4.0, 6, 6, 6, 0.6)
        self.head.setCenterPoint(0.0, 6.0, -8.0)
        self.body = ModelRenderer(self, 28, 8)
        self.body.addBox(-4.0, -10.0, -7.0, 8, 16, 6, 1.75)
        self.body.setCenterPoint(0.0, 5.0, 2.0)

        legExpand = 0.5
        self.leg1 = ModelRenderer(self, 0, 16)
        self.leg1.addBox(-2.0, 0.0, -2.0, 4, 6, 4, legExpand)
        self.leg1.setCenterPoint(-3.0, 12.0, 7.0)
        self.leg2 = ModelRenderer(self, 0, 16)
        self.leg2.addBox(-2.0, 0.0, -2.0, 4, 6, 4, legExpand)
        self.leg2.setCenterPoint(3.0, 12.0, 7.0)
        self.leg3 = ModelRenderer(self, 0, 16)
        self.leg3.addBox(-2.0, 0.0, -2.0, 4, 6, 4, legExpand)
        self.leg3.setCenterPoint(-3.0, 12.0, -5.0)
        self.leg4 = ModelRenderer(self, 0, 16)
        self.leg4.addBox(-2.0, 0.0, -2.0, 4, 6, 4, legExpand)
        self.leg4.setCenterPoint(3.0, 12.0, -5.0)

        self.body.setRotation(math.pi/2., 0, 0)


class ModelSheep(ModelQuadruped):
    id = "Sheep"
    modelTexture = "assets/minecraft/textures/entity/sheep/sheep.png"

    def __init__(self):
        super(ModelSheep, self).__init__(12)
        
        self.head = ModelRenderer(self, 0, 0)
        self.head.addBox(-3.0, -4.0, -6.0, 6, 6, 8, 0.0)
        self.head.setCenterPoint(0.0, 6.0, -8.0)
        self.body = ModelRenderer(self, 28, 8)
        self.body.addBox(-4.0, -10.0, -7.0, 8, 16, 6, 0.0)
        self.body.setCenterPoint(0.0, 5.0, 2.0)

        self.body.setRotation(math.pi/2., 0, 0)
