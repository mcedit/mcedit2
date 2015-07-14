"""
    villager
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from mcedit2.rendering.chunkmeshes.entity.modelrenderer import ModelRenderer

log = logging.getLogger(__name__)


class ModelVillager(object):
    textureWidth = 64
    textureHeight = 64
    modelTexture = "assets/minecraft/textures/entity/villager/villager.png"

    id = "Villager"

    def textureForEntity(self, entityRef):
        prof = entityRef.Profession
        profNames = {
            0: "farmer",
            1: "librarian",
            2: "priest",
            3: "smith",
            4: "butcher",
        }
        profName = profNames.get(prof, "villager")
        return "assets/minecraft/textures/entity/villager/%s.png" % profName

    def __init__(self, expandOffset=0., heightOffset=0.):

        self.villagerHead = ModelRenderer(self)
        self.villagerHead.setCenterPoint(0.0, 0.0 + heightOffset, 0.0)
        self.villagerHead.setTextureOffset(0, 0)
        self.villagerHead.addBox(-4.0, -10.0, -4.0, 8, 10, 8, expandOffset)
        self.villagerNose = ModelRenderer(self)
        self.villagerNose.setCenterPoint(0.0, heightOffset - 2.0, 0.0)
        self.villagerNose.setTextureOffset(24, 0)
        self.villagerNose.addBox(-1.0, -1.0, -6.0, 2, 4, 2, expandOffset)
        #self.villagerHead.addChild(self.villagerNose)
        self.villagerBody = ModelRenderer(self)
        self.villagerBody.setCenterPoint(0.0, 0.0 + heightOffset, 0.0)
        self.villagerBody.setTextureOffset(16, 20)
        self.villagerBody.addBox(-4.0, 0.0, -3.0, 8, 12, 6, expandOffset)
        self.villagerBody.setTextureOffset(0, 38)
        self.villagerBody.addBox(-4.0, 0.0, -3.0, 8, 18, 6, expandOffset + 0.5)
        self.villagerArms = ModelRenderer(self)
        self.villagerArms.setCenterPoint(0.0, 0.0 + heightOffset + 2.0, 0.0)
        self.villagerArms.setTextureOffset(44, 22)
        self.villagerArms.addBox(-8.0, -2.0, -2.0, 4, 8, 4, expandOffset)
        self.villagerArms.setTextureOffset(44, 22)
        self.villagerArms.addBox(4.0, -2.0, -2.0, 4, 8, 4, expandOffset)
        self.villagerArms.setTextureOffset(40, 38)
        self.villagerArms.addBox(-4.0, 2.0, -2.0, 8, 4, 4, expandOffset)
        self.rightVillagerLeg = (ModelRenderer(self, 0, 22))
        self.rightVillagerLeg.setCenterPoint(-2.0, 12.0 + heightOffset, 0.0)
        self.rightVillagerLeg.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset)
        self.leftVillagerLeg = (ModelRenderer(self, 0, 22))
        self.leftVillagerLeg.mirror = True
        self.leftVillagerLeg.setCenterPoint(2.0, 12.0 + heightOffset, 0.0)
        self.leftVillagerLeg.addBox(-2.0, 0.0, -2.0, 4, 12, 4, expandOffset)

    @property
    def parts(self):
        return [
            self.villagerHead,
            self.villagerNose,
            self.villagerBody,
            self.villagerArms,
            self.rightVillagerLeg,
            self.leftVillagerLeg,
        ]