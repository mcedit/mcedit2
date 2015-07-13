"""
    spider
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import math
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)

class ModelSpider(object):
    textureWidth = 64
    textureHeight = 32

    id = "Spider"
    modelTexture = "assets/minecraft/textures/entity/spider/spider.png"

    def __init__(self):
        var1 = 0.0
        var2 = 15
        self.spiderHead = ModelRenderer(self, 32, 4)
        self.spiderHead.addBox(-4.0, -4.0, -8.0, 8, 8, 8, var1)
        self.spiderHead.setCenterPoint(0.0, var2, -3.0)
        self.spiderNeck = ModelRenderer(self, 0, 0)
        self.spiderNeck.addBox(-3.0, -3.0, -3.0, 6, 6, 6, var1)
        self.spiderNeck.setCenterPoint(0.0, var2, 0.0)
        self.spiderBody = ModelRenderer(self, 0, 12)
        self.spiderBody.addBox(-5.0, -4.0, -6.0, 10, 8, 12, var1)
        self.spiderBody.setCenterPoint(0.0, var2, 9.0)
        self.spiderLeg1 = ModelRenderer(self, 18, 0)
        self.spiderLeg1.addBox(-15.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg1.setCenterPoint(-4.0, var2, 2.0)
        self.spiderLeg2 = ModelRenderer(self, 18, 0)
        self.spiderLeg2.addBox(-1.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg2.setCenterPoint(4.0, var2, 2.0)
        self.spiderLeg3 = ModelRenderer(self, 18, 0)
        self.spiderLeg3.addBox(-15.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg3.setCenterPoint(-4.0, var2, 1.0)
        self.spiderLeg4 = ModelRenderer(self, 18, 0)
        self.spiderLeg4.addBox(-1.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg4.setCenterPoint(4.0, var2, 1.0)
        self.spiderLeg5 = ModelRenderer(self, 18, 0)
        self.spiderLeg5.addBox(-15.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg5.setCenterPoint(-4.0, var2, 0.0)
        self.spiderLeg6 = ModelRenderer(self, 18, 0)
        self.spiderLeg6.addBox(-1.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg6.setCenterPoint(4.0, var2, 0.0)
        self.spiderLeg7 = ModelRenderer(self, 18, 0)
        self.spiderLeg7.addBox(-15.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg7.setCenterPoint(-4.0, var2, -1.0)
        self.spiderLeg8 = ModelRenderer(self, 18, 0)
        self.spiderLeg8.addBox(-1.0, -1.0, -1.0, 16, 2, 2, var1)
        self.spiderLeg8.setCenterPoint(4.0, var2, -1.0)

        legYaw = 0.3926991
        legPitch = math.pi / 4
        self.spiderLeg1.setRotation(0, 2*legYaw, -legPitch)
        self.spiderLeg2.setRotation(0, -2*legYaw, legPitch)
        self.spiderLeg3.setRotation(0, legYaw, -legPitch*3/4.)
        self.spiderLeg4.setRotation(0, -legYaw, legPitch*3/4.)
        self.spiderLeg5.setRotation(0, -legYaw, -legPitch*3/4.)
        self.spiderLeg6.setRotation(0, legYaw, legPitch*3/4.)
        self.spiderLeg7.setRotation(0, -2*legYaw, -legPitch)
        self.spiderLeg8.setRotation(0, 2*legYaw, legPitch)

        self.parts = [
            self.spiderHead,
            self.spiderNeck,
            self.spiderBody,
            self.spiderLeg1,
            self.spiderLeg2,
            self.spiderLeg3,
            self.spiderLeg4,
            self.spiderLeg5,
            self.spiderLeg6,
            self.spiderLeg7,
            self.spiderLeg8,

        ]