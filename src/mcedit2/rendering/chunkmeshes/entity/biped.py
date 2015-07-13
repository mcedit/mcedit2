"""
    biped
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)

class ModelBiped(object):
    textureWidth = 64
    textureHeight = 32

    def __init__(self, expandOffset=0.0, headOffset=0.0):
        self.bipedHead = ModelRenderer(self, 0, 0)
        self.bipedHead.addBox(-4.0, -8.0, -4.0, 8, 8, 8, expandOffset)
        self.bipedHead.setCenterPoint(0.0, 0.0 + headOffset, 0.0)
        self.bipedHeadwear = ModelRenderer(self, 32, 0)
        self.bipedHeadwear.addBox(-4.0, -8.0, -4.0, 8, 8, 8, expandOffset + 0.5)
        self.bipedHeadwear.setCenterPoint(0.0, 0.0 + headOffset, 0.0)
        self.bipedBody = ModelRenderer(self, 16, 16)
        self.bipedBody.addBox(-4.0, 0.0, -2.0, 8, 12, 4, expandOffset)
        self.bipedBody.setCenterPoint(0.0, 0.0 + headOffset, 0.0)
        self.bipedRightArm = ModelRenderer(self, 40, 16)
        self.bipedRightArm.addBox(-3.0, -2.0, -2.0, 4, 12, 4, expandOffset)
        self.bipedRightArm.setCenterPoint(-5.0, 2.0 + headOffset, 0.0)
        self.bipedLeftArm = ModelRenderer(self, 40, 16)
        self.bipedLeftArm.mirror = True
        self.bipedLeftArm.addBox(-1.0, -2.0, -2.0, 4, 12, 4, expandOffset)
        self.bipedLeftArm.setCenterPoint(5.0, 2.0 + headOffset, 0.0)
        self.bipedRightLeg = ModelRenderer(self, 0, 16)
        self.bipedRightLeg.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset)
        self.bipedRightLeg.setCenterPoint(-1.9, 12.0 + headOffset, 0.0)
        self.bipedLeftLeg = ModelRenderer(self, 0, 16)
        self.bipedLeftLeg.mirror = True
        self.bipedLeftLeg.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset)
        self.bipedLeftLeg.setCenterPoint(1.9, 12.0 + headOffset, 0.0)


    @property
    def parts(self):
        return [
            self.bipedHead,
            self.bipedHeadwear,
            self.bipedBody,
            self.bipedRightArm,
            self.bipedLeftArm,
            self.bipedRightLeg,
            self.bipedLeftLeg
        ]


class ModelZombie(ModelBiped):
    textureWidth = 64
    textureHeight = 64

    modelTexture = "assets/minecraft/textures/entity/zombie/zombie.png"
    id = "Zombie"


class ModelPigZombie(ModelBiped):
    textureWidth = 64
    textureHeight = 64

    modelTexture = "assets/minecraft/textures/entity/zombie_pigman.png"
    id = "PigZombie"


class ModelSkeleton(ModelBiped):
    modelTexture = "assets/minecraft/textures/entity/skeleton/skeleton.png"
    id = "Skeleton"

    def __init__(self, expandOffset=1.0, headOffset=0.0):
        super(ModelSkeleton, self).__init__(expandOffset, headOffset)

        self.bipedRightArm = ModelRenderer(self, 40, 16)
        self.bipedRightArm.addBox(-1.0, -2.0, -1.0, 2, 12, 2, expandOffset)
        self.bipedRightArm.setCenterPoint(-5.0, 2.0, 0.0)
        self.bipedLeftArm = ModelRenderer(self, 40, 16)
        self.bipedLeftArm.mirror = True
        self.bipedLeftArm.addBox(-1.0, -2.0, -1.0, 2, 12, 2, expandOffset)
        self.bipedLeftArm.setCenterPoint(5.0, 2.0, 0.0)
        self.bipedRightLeg = ModelRenderer(self, 0, 16)
        self.bipedRightLeg.addBox(-1.0, 0.0, -1.0, 2, 12, 2, expandOffset)
        self.bipedRightLeg.setCenterPoint(-2.0, 12.0, 0.0)
        self.bipedLeftLeg = ModelRenderer(self, 0, 16)
        self.bipedLeftLeg.mirror = True
        self.bipedLeftLeg.addBox(-1.0, 0.0, -1.0, 2, 12, 2, expandOffset)
        self.bipedLeftLeg.setCenterPoint(2.0, 12.0, 0.0)