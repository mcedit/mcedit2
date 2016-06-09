"""
    player
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mcedit2.rendering.chunkmeshes.entity.biped import ModelBiped
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)


class ModelPlayer(ModelBiped):
    id = "MCEDIT_Player"
    textureWidth = 64
    textureHeight = 64
    modelTexture = None

    def __init__(self, expandOffset=0.0, headOffset=0.0, smallArms=False):
        super(ModelPlayer, self).__init__(expandOffset, headOffset)
        
        self.smallArms = smallArms
        self.bipedCape = ModelRenderer(self, 0, 0)
        # self.bipedCape.setTextureSize(64, 32)
        self.bipedCape.addBox(-5.0, 0.0, -1.0, 10, 16, 1, expandOffset)

        if smallArms:
            self.bipedLeftArm = ModelRenderer(self, 32, 48)
            self.bipedLeftArm.addBox(-1.0, -2.0, -2.0, 3, 12, 4, expandOffset)
            self.bipedLeftArm.setCenterPoint(5.0, 2.5, 0.0)
            self.bipedRightArm = ModelRenderer(self, 40, 16)
            self.bipedRightArm.addBox(-2.0, -2.0, -2.0, 3, 12, 4, expandOffset)
            self.bipedRightArm.setCenterPoint(-5.0, 2.5, 0.0)
            self.bipedLeftArmwear = ModelRenderer(self, 48, 48)
            self.bipedLeftArmwear.addBox(-1.0, -2.0, -2.0, 3, 12, 4, expandOffset + 0.25)
            self.bipedLeftArmwear.setCenterPoint(5.0, 2.5, 0.0)
            self.bipedRightArmwear = ModelRenderer(self, 40, 32)
            self.bipedRightArmwear.addBox(-2.0, -2.0, -2.0, 3, 12, 4, expandOffset + 0.25)
            self.bipedRightArmwear.setCenterPoint(-5.0, 2.5, 10.0)
        
        else:
            self.bipedLeftArm = ModelRenderer(self, 32, 48)
            self.bipedLeftArm.addBox(-1.0, -2.0, -2.0, 4, 12, 4, expandOffset)
            self.bipedLeftArm.setCenterPoint(5.0, 2.0, 0.0)
            self.bipedLeftArmwear = ModelRenderer(self, 48, 48)
            self.bipedLeftArmwear.addBox(-1.0, -2.0, -2.0, 4, 12, 4, expandOffset + 0.25)
            self.bipedLeftArmwear.setCenterPoint(5.0, 2.0, 0.0)
            self.bipedRightArmwear = ModelRenderer(self, 40, 32)
            self.bipedRightArmwear.addBox(-3.0, -2.0, -2.0, 4, 12, 4, expandOffset + 0.25)
            self.bipedRightArmwear.setCenterPoint(-5.0, 2.0, 10.0)
        
        self.bipedLeftLeg = ModelRenderer(self, 16, 48)
        self.bipedLeftLeg.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset)
        self.bipedLeftLeg.setCenterPoint(1.9, 12.0, 0.0)
        self.bipedLeftLegwear = ModelRenderer(self, 0, 48)
        self.bipedLeftLegwear.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset + 0.25)
        self.bipedLeftLegwear.setCenterPoint(1.9, 12.0, 0.0)
        self.bipedRightLegwear = ModelRenderer(self, 0, 32)
        self.bipedRightLegwear.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset + 0.25)
        self.bipedRightLegwear.setCenterPoint(-1.9, 12.0, 0.0)
        self.bipedBodyWear = ModelRenderer(self, 16, 32)
        self.bipedBodyWear.addBox(-4.0, 0.0, -2.0, 8, 12, 4, expandOffset + 0.25)
        self.bipedBodyWear.setCenterPoint(0.0, 0.0, 0.0)

    @property
    def parts(self):
        return [
            self.bipedHead,
            self.bipedHeadwear,
            self.bipedBody,
            self.bipedBodyWear,
            self.bipedRightArm,
            self.bipedRightArmwear,
            self.bipedLeftArm,
            self.bipedLeftArmwear,
            self.bipedRightLeg,
            self.bipedRightLegwear,
            self.bipedLeftLeg,
            self.bipedLeftLegwear,
        ]
