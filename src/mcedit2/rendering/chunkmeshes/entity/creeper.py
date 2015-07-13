"""
    creeper
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)


class ModelCreeper(object):
    textureWidth = 64
    textureHeight = 32

    modelTexture = "assets/minecraft/textures/entity/creeper/creeper.png"
    id = "Creeper"

    def __init__(self):
        headCenterHeight = 6
        head = ModelRenderer(self, 0, 0)
        head.addBox(-4.0, -8.0, -4.0, 8, 8, 8)
        head.setCenterPoint(0.0, headCenterHeight, 0.0)
        # creeperArmor = ModelRenderer(self, 32, 0)
        # creeperArmor.addBox(-4.0, -8.0, -4.0, 8, 8, 8)
        # creeperArmor.setCenterPoint(0.0, headCenterHeight, 0.0)
        body = ModelRenderer(self, 16, 16)
        body.addBox(-4.0, 0.0, -2.0, 8, 12, 4)
        body.setCenterPoint(0.0, headCenterHeight, 0.0)
        leg1 = ModelRenderer(self, 0, 16)
        leg1.addBox(-2.0, 0.0, -2.0, 4, 6, 4)
        leg1.setCenterPoint(-2.0, (12 + headCenterHeight), 4.0)
        leg2 = ModelRenderer(self, 0, 16)
        leg2.addBox(-2.0, 0.0, -2.0, 4, 6, 4)
        leg2.setCenterPoint(2.0, (12 + headCenterHeight), 4.0)
        leg3 = ModelRenderer(self, 0, 16)
        leg3.addBox(-2.0, 0.0, -2.0, 4, 6, 4)
        leg3.setCenterPoint(-2.0, (12 + headCenterHeight), -4.0)
        leg4 = ModelRenderer(self, 0, 16)
        leg4.addBox(-2.0, 0.0, -2.0, 4, 6, 4)
        leg4.setCenterPoint(2.0, (12 + headCenterHeight), -4.0)

        self.parts = [
            head, body, leg1, leg2, leg3, leg4
        ]
