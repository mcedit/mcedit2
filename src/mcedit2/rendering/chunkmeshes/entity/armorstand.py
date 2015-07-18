"""
    armorstand
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering.chunkmeshes.entity.biped import ModelBiped
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)

class ModelArmorStandArmor(ModelBiped):
    pass

SLOT_BOOTS = 1
SLOT_LEGS = 2
SLOT_CHEST = 3
SLOT_HEAD = 4

class ModelArmorStand(ModelArmorStandArmor):
    textureWidth = 64
    textureHeight = 64

    modelTexture = "assets/minecraft/textures/entity/armorstand/wood.png"
    id = "ArmorStand"
    
    def __init__(self, expandOffset=0.0):
        self.bipedHead = ModelRenderer(self, 0, 0)
        self.bipedHead.addBox(-1.0, -7.0, -1.0, 2, 7, 2, expandOffset)
        self.bipedHead.setCenterPoint(0.0, 0.0, 0.0)
        self.bipedBody = ModelRenderer(self, 0, 26)
        self.bipedBody.addBox(-6.0, 0.0, -1.5, 12, 3, 3, expandOffset)
        self.bipedBody.setCenterPoint(0.0, 0.0, 0.0)
        self.bipedRightArm = ModelRenderer(self, 24, 0)
        self.bipedRightArm.addBox(-2.0, -2.0, -1.0, 2, 12, 2, expandOffset)
        self.bipedRightArm.setCenterPoint(-5.0, 2.0, 0.0)
        self.bipedLeftArm = ModelRenderer(self, 32, 16)
        self.bipedLeftArm.mirror = True
        self.bipedLeftArm.addBox(0.0, -2.0, -1.0, 2, 12, 2, expandOffset)
        self.bipedLeftArm.setCenterPoint(5.0, 2.0, 0.0)
        self.bipedRightLeg = ModelRenderer(self, 8, 0)
        self.bipedRightLeg.addBox(-1.0, 0.0, -1.0, 2, 11, 2, expandOffset)
        self.bipedRightLeg.setCenterPoint(-1.9, 12.0, 0.0)
        self.bipedLeftLeg = ModelRenderer(self, 40, 16)
        self.bipedLeftLeg.mirror = True
        self.bipedLeftLeg.addBox(-1.0, 0.0, -1.0, 2, 11, 2, expandOffset)
        self.bipedLeftLeg.setCenterPoint(1.9, 12.0, 0.0)
        self.standRightSide = ModelRenderer(self, 16, 0)
        self.standRightSide.addBox(-3.0, 3.0, -1.0, 2, 7, 2, expandOffset)
        self.standRightSide.setCenterPoint(0.0, 0.0, 0.0)
        self.standRightSide.showModel = True
        self.standLeftSide = ModelRenderer(self, 48, 16)
        self.standLeftSide.addBox(1.0, 3.0, -1.0, 2, 7, 2, expandOffset)
        self.standLeftSide.setCenterPoint(0.0, 0.0, 0.0)
        self.standWaist = ModelRenderer(self, 0, 48)
        self.standWaist.addBox(-4.0, 10.0, -1.0, 8, 2, 2, expandOffset)
        self.standWaist.setCenterPoint(0.0, 0.0, 0.0)
        self.standBase = ModelRenderer(self, 0, 32)
        self.standBase.addBox(-6.0, 11.0, -6.0, 12, 1, 12, expandOffset)
        self.standBase.setCenterPoint(0.0, 12.0, 0.0)

    @property
    def parts(self):
        return [
            self.bipedHead,
            self.bipedBody,
            self.bipedRightArm,
            self.bipedLeftArm,
            self.bipedRightLeg,
            self.bipedLeftLeg,
            self.standRightSide,
            self.standLeftSide,
            self.standWaist,
            self.standBase
        ]