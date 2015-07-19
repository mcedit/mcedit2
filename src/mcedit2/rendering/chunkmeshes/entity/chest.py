"""
    chest
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)


class ModelChest(object):
    textureWidth = 64
    textureHeight = 64

    tileEntityID = "Chest"

    modelTexture = "assets/minecraft/textures/entity/chest/normal.png"

    def __init__(self):
        self.chestLid = ModelRenderer(self, 0, 0)
        self.chestLid.addBox(0.0, -5.0, -14.0, 14, 5, 14, 0.0)
        self.chestLid.setCenterPoint(1., 7., 15.)

        self.chestKnob = ModelRenderer(self, 0, 0)
        self.chestKnob.addBox(-1.0, -2.0, -15.0, 2, 4, 1, 0.0)
        self.chestKnob.setCenterPoint(8., 7., 15.)

        self.chestBelow = ModelRenderer(self, 0, 19)
        self.chestBelow.addBox(0.0, 0.0, 0.0, 14, 10, 14, 0.0)
        self.chestBelow.setCenterPoint(1., 6., 1.)


        self.parts = [
            self.chestLid,
            self.chestKnob,
            self.chestBelow,
        ]

class ModelLargeChest(object):
    textureWidth = 128
    textureHeight = 64

    modelTexture = "assets/minecraft/textures/entity/chest/normal_double.png"
    tileEntityID = "MCEDIT_LargeChest"  # gross

    def __init__(self):
        
        self.chestLid = ModelRenderer(self, 0, 0)
        self.chestLid.addBox(0.0, -5.0, -14.0, 30, 5, 14, 0.0)
        self.chestLid.setCenterPoint(1., 7., 15.)
        self.chestKnob = ModelRenderer(self, 0, 0)
        self.chestKnob.addBox(-1.0, -2.0, -15.0, 2, 4, 1, 0.0)
        self.chestKnob.setCenterPoint(16., 7., 15.)
        self.chestBelow = ModelRenderer(self, 0, 19)
        self.chestBelow.addBox(0.0, 0.0, 0.0, 30, 10, 14, 0.0)
        self.chestBelow.setCenterPoint(1., 6., 1.)

        self.parts = [
            self.chestLid,
            self.chestKnob,
            self.chestBelow,
        ]