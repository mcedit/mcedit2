"""
    shulker
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)


class ModelShulker(object):
    textureWidth = 64
    textureHeight = 64

    modelTexture = "assets/minecraft/textures/entity/shulker/endergolem.png"
    id = "Shulker"

    def __init__(self):
        self.part1 = ModelRenderer(self, 0, 0)
        self.part2 = ModelRenderer(self, 0, 28)
        self.part3 = ModelRenderer(self, 0, 52)

        self.part1.addBox(-8.0, -16.0, -8.0, 16, 12, 16)
        self.part1.setCenterPoint(0.0, 24.0, 0.0)

        self.part2.addBox(-8.0, -8.0, -8.0, 16, 8, 16)
        self.part2.setCenterPoint(0.0, 24.0, 0.0)

        self.part3.addBox(-3.0, 0.0, -3.0, 6, 6, 6)
        self.part3.setCenterPoint(0.0, 12.0, 0.0)

        self.parts = [
            self.part1, self.part2, self.part3
        ]