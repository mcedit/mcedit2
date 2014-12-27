"""
    rendertypes
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from pprint import pprint

log = logging.getLogger(__name__)


def main():
    s = """var5 == 0 ? this.renderStandardBlock(par1Block, par2, par3, par4) : (var5 == 4 ? this.renderBlockFluids(par1Block, par2, par3, par4) : (var5 == 31 ? this.renderBlockLog(par1Block, par2, par3, par4) : (var5 == 1 ? this.renderCrossedSquares(par1Block, par2, par3, par4) : (var5 == 2 ? this.renderBlockTorch(par1Block, par2, par3, par4) : (var5 == 20 ? this.renderBlockVine(par1Block, par2, par3, par4) : (var5 == 11 ? this.renderBlockFence((BlockFence)par1Block, par2, par3, par4) : (var5 == 39 ? this.renderBlockQuartz(par1Block, par2, par3, par4) : (var5 == 5 ? this.renderBlockRedstoneWire(par1Block, par2, par3, par4) : (var5 == 13 ? this.renderBlockCactus(par1Block, par2, par3, par4) : (var5 == 9 ? this.renderBlockMinecartTrack((BlockRailBase)par1Block, par2, par3, par4) : (var5 == 19 ? this.renderBlockStem(par1Block, par2, par3, par4) : (var5 == 23 ? this.renderBlockLilyPad(par1Block, par2, par3, par4) : (var5 == 6 ? this.renderBlockCrops(par1Block, par2, par3, par4) : (var5 == 3 ? this.renderBlockFire((BlockFire)par1Block, par2, par3, par4) : (var5 == 8 ? this.renderBlockLadder(par1Block, par2, par3, par4) : (var5 == 7 ? this.renderBlockDoor(par1Block, par2, par3, par4) : (var5 == 10 ? this.renderBlockStairs((BlockStairs)par1Block, par2, par3, par4) : (var5 == 27 ? this.renderBlockDragonEgg((BlockDragonEgg)par1Block, par2, par3, par4) : (var5 == 32 ? this.renderBlockWall((BlockWall)par1Block, par2, par3, par4) : (var5 == 12 ? this.renderBlockLever(par1Block, par2, par3, par4) : (var5 == 29 ? this.renderBlockTripWireSource(par1Block, par2, par3, par4) : (var5 == 30 ? this.renderBlockTripWire(par1Block, par2, par3, par4) : (var5 == 14 ? this.renderBlockBed(par1Block, par2, par3, par4) : (var5 == 15 ? this.renderBlockRepeater((BlockRedstoneRepeater)par1Block, par2, par3, par4) : (var5 == 36 ? this.renderBlockRedstoneLogic((BlockRedstoneLogic)par1Block, par2, par3, par4) : (var5 == 37 ? this.renderBlockComparator((BlockComparator)par1Block, par2, par3, par4) : (var5 == 16 ? this.renderPistonBase(par1Block, par2, par3, par4, false) : (var5 == 17 ? this.renderPistonExtension(par1Block, par2, par3, par4, true) : (var5 == 18 ? this.renderBlockPane((BlockPane)par1Block, par2, par3, par4) : (var5 == 21 ? this.renderBlockFenceGate((BlockFenceGate)par1Block, par2, par3, par4) : (var5 == 24 ? this.renderBlockCauldron((BlockCauldron)par1Block, par2, par3, par4) : (var5 == 33 ? this.renderBlockFlowerpot((BlockFlowerPot)par1Block, par2, par3, par4) : (var5 == 35 ? this.renderBlockAnvil((BlockAnvil)par1Block, par2, par3, par4) : (var5 == 25 ? this.renderBlockBrewingStand((BlockBrewingStand)par1Block, par2, par3, par4) : (var5 == 26 ? this.renderBlockEndPortalFrame((BlockEndPortalFrame)par1Block, par2, par3, par4) : (var5 == 28 ? this.renderBlockCocoa((BlockCocoa)par1Block, par2, par3, par4) : (var5 == 34 ? this.renderBlockBeacon((BlockBeacon)par1Block, par2, par3, par4) : (var5 == 38 ? this.renderBlockHopper((BlockHopper)par1Block, par2, par3, par4) : false))))))))))))))))))))))))))))))))))))));
    """

    s = s.replace("var5 == ", "").replace(" ? this.", ": ").replace("render", "").replace("Block", "")

    parts = s.split(") : (")
    pprint(parts)
    parts = [p.split("(")[0].split(": ") for p in parts]
    parts = [(int(num), name) for num, name in parts]
    pprint(sorted(parts))

if __name__ == "__main__":
    main()

renderTypes = dict([(0, u'Standard'),
                    (1, u'CrossedSquares'),
                    (2, u'Torch'),
                    (3, u'Fire'),
                    (4, u'Fluids'),
                    (5, u'RedstoneWire'),
                    (6, u'Crops'),
                    (7, u'Door'),
                    (8, u'Ladder'),
                    (9, u'MinecartTrack'),
                    (10, u'Stairs'),
                    (11, u'Fence'),
                    (12, u'Lever'),
                    (13, u'Cactus'),
                    (14, u'Bed'),
                    (15, u'Repeater'),
                    (16, u'PistonBase'),
                    (17, u'PistonExtension'),
                    (18, u'Pane'),
                    (19, u'Stem'),
                    (20, u'Vine'),
                    (21, u'FenceGate'),
                    (23, u'LilyPad'),
                    (24, u'Cauldron'),
                    (25, u'BrewingStand'),
                    (26, u'EndPortalFrame'),
                    (27, u'DragonEgg'),
                    (28, u'Cocoa'),
                    (29, u'TripWireSource'),
                    (30, u'TripWire'),
                    (31, u'Log'),
                    (32, u'Wall'),
                    (33, u'Flowerpot'),
                    (34, u'Beacon'),
                    (35, u'Anvil'),
                    (36, u'RedstoneLogic'),
                    (37, u'Comparator'),
                    (38, u'Hopper'),
                    (39, u'Quartz')])
