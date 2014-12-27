"""
    Block definitions for all known level formats
    Reader for block definitions stored in .yaml files (based on Minecraft X-Ray)
"""
from __future__ import absolute_import
from logging import getLogger
import os
import traceback
from os.path import join
from collections import defaultdict, namedtuple
import json

import numpy
import sys
from mceditlib.faces import faceNames

log = getLogger(__name__)

MCYDecreasing = 0
MCYIncreasing = 1
MCZDecreasing = 2 #south
MCZIncreasing = 3 #north
MCXDecreasing = 4 #west
MCXIncreasing = 5 #east


class BlockType(namedtuple("_BlockType", "ID blockData blocktypeSet")):
    """
    Value object representing an (id, data, blocktypeSet) tuple.
    Accessing its attributes will return the corresponding elements
    of its parent material's json arrays.

    """

    def __repr__(self):
        return "<BlockType {name} ({ID}:{data})>".format(
            name=self.englishName, ID=self.ID, data=self.blockData)

    def __str__(self):
        return "{name} [{internalName}] ({id}:{data})".format(
            name=self.englishName, internalName=self.internalName, id=self.ID, data=self.blockData)

    def __cmp__(self, other):
        if not isinstance(other, BlockType):
            return -1
        if None in (self, other):
            return -1

        key = lambda a: (a.internalName, a.blockData)
        return cmp(key(self), key(other))

    def __getattr__(self, attr):
        return self.blocktypeSet.getBlockTypeAttr(self, attr)


id_limit = 4096


def openResource(filename):
    path = join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        try:
            # py2exe, .egg
            import pkg_resources
            return pkg_resources.resource_stream(__name__, filename)
        except ImportError as e:
            log.exception("pkg_resources not available")

    return file(path)


class BlockTypeSet(object):
    defaultColor = (0xc9, 0x77, 0xf0, 0xff)

    def __init__(self, defaultName="Unused Block", idMapping=None):
        object.__init__(self)
        self.jsonDatas = []
        self.allBlocks = []
        self.json = defaultdict(dict)
        self.idMapping = {}  # internalName -> id

        self.defaults = {
            'englishName': defaultName,
            'opacity': 15,
            'brightness': 0,
            'internalName': 'UNKNOWN_NAME',
            'unlocalizedName': 'name.unknown',
            'opaqueCube': True,
            'renderType': 0,
        }

        self.aka = defaultdict(lambda: "")
        self.textureIconNames = defaultdict(lambda: ["missingno"] * 6)
        self.cubeBounds = numpy.zeros((id_limit, 16, 6), dtype='float32')
        self.cubeBounds[:] = 0., 0., 0., 1., 1., 1.

        self.brightness = numpy.zeros(id_limit, dtype='uint8')
        self.brightness[:] = self.defaults['brightness']
        self.opacity = numpy.zeros(id_limit, dtype='uint8')
        self.opacity[:] = self.defaults['opacity']
        self.mapColor = numpy.zeros((id_limit, 4), dtype='uint8')
        self.mapColor[:] = self.defaultColor
        self.renderType = numpy.zeros((id_limit, ), dtype='uint8')
        self.renderType[0] = -1
        self.renderColor = numpy.zeros((id_limit, 16, 3), dtype='uint8')
        self.renderColor[:] = 0xFF
        self.mapColor = numpy.zeros((id_limit, 16, 3), dtype='uint8')
        self.mapColor[:] = 0xFF

        self.opaqueCube = numpy.ones((id_limit, ), dtype='bool')
        self.opaqueCube[0] = 0

        self.name = "Unnamed Set"
        self.namePrefix = "minecraft:"

    def getBlockTypeAttr(self, block, attr):
    #        a = getattr(self, attr, None)
    #        if a is None:
        if attr == "textureIconNames":
            return self.textureIconNames[block.ID, block.blockData]
        if attr == "cubeBounds":
            return self.cubeBounds[block.ID, block.blockData]

        val = self.json[block.ID, block.blockData]
        base = self.json[block.ID, 0]
        retval = val.get(attr)
        if retval is None:
            retval = base.get(attr)
            if retval is None:
                retval = self.defaults[attr]

        return retval

    def __repr__(self):
        return "<BlockTypeSet ({0})>".format(self.name)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

    def __len__(self):
        return len(self.allBlocks)

    def __iter__(self):
        return iter(self.allBlocks)

    def __getitem__(self, key):
        """ Behavior changed. The only accepted string is the internalName field. Possible keys:

            Internal name
            Block ID
            Tuple of (Internal name, blockData)
            TUple of (ID, blockData)


                level.blocktypes["air"]  # also returns Air
                level.blocktypes["powered_rail"]  # returns Powered Rail

           """
        if isinstance(key, (tuple, list)):
            ID, blockData = key
        else:
            ID = key
            blockData = 0

        if isinstance(ID, basestring):
            if ID not in self.idMapping and not ID.startswith(self.namePrefix):
                ID = self.namePrefix + ID
            ID = self.idMapping[ID]

        return self.blockWithID(ID, blockData)


    def blocksMatching(self, name):
        name = name.lower()
        return [v for v in self.allBlocks if name in v.englishName.lower() or name in v.aka.lower()]

    def blockWithID(self, ID, data=0):
        return BlockType(ID, data, self)

    def addJsonBlocksFromFile(self, filename):
        f = openResource(filename)
        try:
            s = f.read()
            log.info(u"Loading block info from (%s) %s", len(s), f)
            self.addJsonBlocks(json.loads(s))

        except EnvironmentError as e:
            log.error(u"Exception while loading block info from %s: %s", f, e)
            traceback.print_exc()

    def addJsonBlocks(self, blockJson):
        self.jsonDatas.append(blockJson)
        for block in blockJson:
            try:
                self.addJsonBlock(block)
            except (KeyError, ValueError) as e:
                log.warn(u"Exception while parsing block: %r", e)
                traceback.print_exc()
                log.warn(u"Block dict: \n%s", block)

    def addJsonBlock(self, block):
        """
        Adds a block to this blockset using the keys and values in `block`.

        Required keys:
            internalName - String used by Minecraft to identify this block

        :type block: dict
        :return:
        :rtype:
        """
        ID = block.get("id")
        internalName = block.get("internalName")
        if ID is None and internalName is None:
            raise ValueError("Block definition must have either `id` or `internalName` attribute.")
        if ID is None:
            ID = self.idMapping[internalName]

        blockData = block.get("damage", 0)

        blockJson = self.json[ID, blockData]
        if blockData and len(blockJson) == 0:
            # initialize block subtype with base block attributes
            blockJson.update(self.json[ID, 0])

        blockJson.update(block)
        log.debug("Adding block: \n%s", json.dumps(blockJson, indent=2))

        if "id" not in block:
            ID = self.idMapping.get(internalName)
            if ID is None:
                # no ID mapping for this block - skip
                return
        else:
            ID = block["id"]  # really old blocks?

        self.allBlocks.append(BlockType(ID, blockData, self))

        for key in [
            'opaqueCube',
            'brightness',
            'opacity',
            'renderType',
        ]:  # does not have data axis
            if key in block:
                array = getattr(self, key)
                array[ID] = block[key]

        try:
            iconNames = self.textureIconNames[ID, blockData]
            for i, face in enumerate(faceNames):
                iconNames[i] = block.get("texture%s" % face, iconNames[i])

        except KeyError:
            pass

        bounds = [0., 0., 0., 1., 1., 1.]
        for idx, key in enumerate("minx miny minz maxx maxy maxz".split()):
            if key in block:
                bounds[idx] = block[key]
        self.cubeBounds[ID, blockData or slice(None)] = bounds

        color = block.get('renderColor')
        if color is not None:
            self.renderColor[ID, blockData or slice(None)] = ((color >> 16) & 0xff,
                                                              (color >> 8) & 0xff,
                                                              color & 0xff)

        color = block.get('materialMapColor')
        if color is not None:
            self.mapColor[ID, blockData or slice(None)] = ((color >> 16) & 0xff,
                                                           (color >> 8) & 0xff,
                                                           color & 0xff)



            # sides: 0: yMinus, 1: yPlus, 2: zMinus, 3: zPlus, 4: xMinus, 5: xPlus
            #[u'collidable',
            # u'color',
            # u'creativeTab',
            # u'englishName',
            # u'hasEntity',
            # u'materialAdventureExempt',
            # u'materialBlocksGrass',
            # u'materialBlocksMovement',
            # u'materialBurns',
            # u'materialLiquid',
            # u'materialMapColor',
            # u'materialMapColorIndex',
            # u'materialMobility',
            # u'materialOpaque',
            # u'materialReplacable',
            # u'materialSolid',
            # u'renderNormal',
            # u'renderPass',
            # u'texture',
            # u'useNeighborBrightness']


    def addYamlBlocksFromFile(self, f):
        return


class PCBlockTypeSet(BlockTypeSet):
    def __init__(self):
        super(PCBlockTypeSet, self).__init__("Future Block!")

        self.idMapping.update(self.legacyIDs)

        self.name = "Minecraft"
        self.addJsonBlocksFromFile("minecraft_raw.json")
        self.addJsonBlocksFromFile("minecraft.json")

        # --- Static block defs ---

        self.Stone = self[1, 0]
        self.Grass = self[2, 0]
        self.Dirt = self[3, 0]
        self.Cobblestone = self[4, 0]
        self.WoodPlanks = self[5, 0]
        self.Sapling = self[6, 0]
        self.SpruceSapling = self[6, 1]
        self.BirchSapling = self[6, 2]
        self.Bedrock = self[7, 0]
        self.WaterActive = self[8, 0]
        self.Water = self[9, 0]
        self.LavaActive = self[10, 0]
        self.Lava = self[11, 0]
        self.Sand = self[12, 0]
        self.Gravel = self[13, 0]
        self.GoldOre = self[14, 0]
        self.IronOre = self[15, 0]
        self.CoalOre = self[16, 0]
        self.Wood = self[17, 0]
        self.Ironwood = self[17, 1]
        self.BirchWood = self[17, 2]
        self.Leaves = self[18, 0]
        self.PineLeaves = self[18, 1]
        self.BirchLeaves = self[18, 2]
        self.JungleLeaves = self[18, 3]
        self.LeavesPermanent = self[18, 4]
        self.PineLeavesPermanent = self[18, 5]
        self.BirchLeavesPermanent = self[18, 6]
        self.JungleLeavesPermanent = self[18, 7]
        self.LeavesDecaying = self[18, 8]
        self.PineLeavesDecaying = self[18, 9]
        self.BirchLeavesDecaying = self[18, 10]
        self.JungleLeavesDecaying = self[18, 11]
        self.Sponge = self[19, 0]
        self.Glass = self[20, 0]

        self.LapisLazuliOre = self[21, 0]
        self.LapisLazuliBlock = self[22, 0]
        self.Dispenser = self[23, 0]
        self.Sandstone = self[24, 0]
        self.NoteBlock = self[25, 0]
        self.Bed = self[26, 0]
        self.PoweredRail = self[27, 0]
        self.DetectorRail = self[28, 0]
        self.StickyPiston = self[29, 0]
        self.Web = self[30, 0]
        self.UnusedShrub = self[31, 0]
        self.TallGrass = self[31, 1]
        self.Shrub = self[31, 2]
        self.DesertShrub2 = self[32, 0]
        self.Piston = self[33, 0]
        self.PistonHead = self[34, 0]
        self.WhiteWool = self[35, 0]
        self.OrangeWool = self[35, 1]
        self.MagentaWool = self[35, 2]
        self.LightBlueWool = self[35, 3]
        self.YellowWool = self[35, 4]
        self.LightGreenWool = self[35, 5]
        self.PinkWool = self[35, 6]
        self.GrayWool = self[35, 7]
        self.LightGrayWool = self[35, 8]
        self.CyanWool = self[35, 9]
        self.PurpleWool = self[35, 10]
        self.BlueWool = self[35, 11]
        self.BrownWool = self[35, 12]
        self.DarkGreenWool = self[35, 13]
        self.RedWool = self[35, 14]
        self.BlackWool = self[35, 15]
        self.Block36 = self[36, 0]
        self.Flower = self[37, 0]
        self.Rose = self[38, 0]
        self.BrownMushroom = self[39, 0]
        self.RedMushroom = self[40, 0]
        self.BlockofGold = self[41, 0]
        self.BlockofIron = self[42, 0]
        self.DoubleStoneSlab = self[43, 0]
        self.DoubleSandstoneSlab = self[43, 1]
        self.DoubleWoodenSlab = self[43, 2]
        self.DoubleCobblestoneSlab = self[43, 3]
        self.DoubleBrickSlab = self[43, 4]
        self.DoubleStoneBrickSlab = self[43, 5]
        self.StoneSlab = self[44, 0]
        self.SandstoneSlab = self[44, 1]
        self.WoodenSlab = self[44, 2]
        self.CobblestoneSlab = self[44, 3]
        self.BrickSlab = self[44, 4]
        self.StoneBrickSlab = self[44, 5]
        self.Brick = self[45, 0]
        self.TNT = self[46, 0]
        self.Bookshelf = self[47, 0]
        self.MossStone = self[48, 0]
        self.Obsidian = self[49, 0]

        self.Torch = self[50, 0]
        self.Fire = self[51, 0]
        self.MonsterSpawner = self[52, 0]
        self.WoodenStairs = self[53, 0]
        self.Chest = self[54, 0]
        self.RedstoneWire = self[55, 0]
        self.DiamondOre = self[56, 0]
        self.BlockofDiamond = self[57, 0]
        self.CraftingTable = self[58, 0]
        self.Crops = self[59, 0]
        self.Farmland = self[60, 0]
        self.Furnace = self[61, 0]
        self.LitFurnace = self[62, 0]
        self.Sign = self[63, 0]
        self.WoodenDoor = self[64, 0]
        self.Ladder = self[65, 0]
        self.Rail = self[66, 0]
        self.StoneStairs = self[67, 0]
        self.WallSign = self[68, 0]
        self.Lever = self[69, 0]
        self.StoneFloorPlate = self[70, 0]
        self.IronDoor = self[71, 0]
        self.WoodFloorPlate = self[72, 0]
        self.RedstoneOre = self[73, 0]
        self.RedstoneOreGlowing = self[74, 0]
        self.RedstoneTorchOff = self[75, 0]
        self.RedstoneTorchOn = self[76, 0]
        self.Button = self[77, 0]
        self.SnowLayer = self[78, 0]
        self.Ice = self[79, 0]
        self.Snow = self[80, 0]

        self.Cactus = self[81, 0]
        self.Clay = self[82, 0]
        self.SugarCane = self[83, 0]
        self.Jukebox = self[84, 0]
        self.Fence = self[85, 0]
        self.Pumpkin = self[86, 0]
        self.Netherrack = self[87, 0]
        self.SoulSand = self[88, 0]
        self.Glowstone = self[89, 0]
        self.NetherPortal = self[90, 0]
        self.JackOLantern = self[91, 0]
        self.Cake = self[92, 0]
        self.RedstoneRepeaterOff = self[93, 0]
        self.RedstoneRepeaterOn = self[94, 0]
        self.AprilFoolsChest = self[95, 0]
        self.Trapdoor = self[96, 0]

        self.HiddenSilverfishStone = self[97, 0]
        self.HiddenSilverfishCobblestone = self[97, 1]
        self.HiddenSilverfishStoneBrick = self[97, 2]
        self.StoneBricks = self[98, 0]
        self.MossyStoneBricks = self[98, 1]
        self.CrackedStoneBricks = self[98, 2]
        self.HugeBrownMushroom = self[99, 0]
        self.HugeRedMushroom = self[100, 0]
        self.IronBars = self[101, 0]
        self.GlassPane = self[102, 0]
        self.Watermelon = self[103, 0]
        self.PumpkinStem = self[104, 0]
        self.MelonStem = self[105, 0]
        self.Vines = self[106, 0]
        self.FenceGate = self[107, 0]
        self.BrickStairs = self[108, 0]
        self.StoneBrickStairs = self[109, 0]
        self.Mycelium = self[110, 0]
        self.Lilypad = self[111, 0]
        self.NetherBrick = self[112, 0]
        self.NetherBrickFence = self[113, 0]
        self.NetherBrickStairs = self[114, 0]
        self.NetherWart = self[115, 0]

        self.WoodButton = self[143, 0]


    _legacyIDs = None

    @property
    def legacyIDs(self):
        if PCBlockTypeSet._legacyIDs is None:
            with openResource("legacy_ids.json") as f:
                _legacyIDs = json.load(f)
                PCBlockTypeSet._legacyIDs = {v: int(k) for k, v in _legacyIDs.iteritems()}

        return self._legacyIDs


pc_blocktypes = PCBlockTypeSet()


class ClassicBlockTypeSet(BlockTypeSet):
    def __init__(self):
        super(ClassicBlockTypeSet, self).__init__("Not present in Classic")
        self.name = "Classic"
        self.addYamlBlocksFromFile("classic.yaml")

        # --- Classic static block defs ---
        self.Stone = self[1]
        self.Grass = self[2]
        self.Dirt = self[3]
        self.Cobblestone = self[4]
        self.WoodPlanks = self[5]
        self.Sapling = self[6]
        self.Bedrock = self[7]
        self.WaterActive = self[8]
        self.Water = self[9]
        self.LavaActive = self[10]
        self.Lava = self[11]
        self.Sand = self[12]
        self.Gravel = self[13]
        self.GoldOre = self[14]
        self.IronOre = self[15]
        self.CoalOre = self[16]
        self.Wood = self[17]
        self.Leaves = self[18]
        self.Sponge = self[19]
        self.Glass = self[20]

        self.RedWool = self[21]
        self.OrangeWool = self[22]
        self.YellowWool = self[23]
        self.LimeWool = self[24]
        self.GreenWool = self[25]
        self.AquaWool = self[26]
        self.CyanWool = self[27]
        self.BlueWool = self[28]
        self.PurpleWool = self[29]
        self.IndigoWool = self[30]
        self.VioletWool = self[31]
        self.MagentaWool = self[32]
        self.PinkWool = self[33]
        self.BlackWool = self[34]
        self.GrayWool = self[35]
        self.WhiteWool = self[36]

        self.Flower = self[37]
        self.Rose = self[38]
        self.BrownMushroom = self[39]
        self.RedMushroom = self[40]
        self.BlockofGold = self[41]
        self.BlockofIron = self[42]
        self.DoubleStoneSlab = self[43]
        self.StoneSlab = self[44]
        self.Brick = self[45]
        self.TNT = self[46]
        self.Bookshelf = self[47]
        self.MossStone = self[48]
        self.Obsidian = self[49]


classic_blocktypes = ClassicBlockTypeSet()


class IndevBlockTypeSet(BlockTypeSet):
    def __init__(self):
        super(IndevBlockTypeSet, self).__init__("Not present in Indev")
        self.name = "Indev"
        self.addYamlBlocksFromFile("indev.yaml")

        # --- Indev static block defs ---
        self.Stone = self[1]
        self.Grass = self[2]
        self.Dirt = self[3]
        self.Cobblestone = self[4]
        self.WoodPlanks = self[5]
        self.Sapling = self[6]
        self.Bedrock = self[7]
        self.WaterActive = self[8]
        self.Water = self[9]
        self.LavaActive = self[10]
        self.Lava = self[11]
        self.Sand = self[12]
        self.Gravel = self[13]
        self.GoldOre = self[14]
        self.IronOre = self[15]
        self.CoalOre = self[16]
        self.Wood = self[17]
        self.Leaves = self[18]
        self.Sponge = self[19]
        self.Glass = self[20]

        self.RedWool = self[21]
        self.OrangeWool = self[22]
        self.YellowWool = self[23]
        self.LimeWool = self[24]
        self.GreenWool = self[25]
        self.AquaWool = self[26]
        self.CyanWool = self[27]
        self.BlueWool = self[28]
        self.PurpleWool = self[29]
        self.IndigoWool = self[30]
        self.VioletWool = self[31]
        self.MagentaWool = self[32]
        self.PinkWool = self[33]
        self.BlackWool = self[34]
        self.GrayWool = self[35]
        self.WhiteWool = self[36]

        self.Flower = self[37]
        self.Rose = self[38]
        self.BrownMushroom = self[39]
        self.RedMushroom = self[40]
        self.BlockofGold = self[41]
        self.BlockofIron = self[42]
        self.DoubleStoneSlab = self[43]
        self.StoneSlab = self[44]
        self.Brick = self[45]
        self.TNT = self[46]
        self.Bookshelf = self[47]
        self.MossStone = self[48]
        self.Obsidian = self[49]

        self.Torch = self[50, 0]
        self.Fire = self[51, 0]
        self.InfiniteWater = self[52, 0]
        self.InfiniteLava = self[53, 0]
        self.Chest = self[54, 0]
        self.Cog = self[55, 0]
        self.DiamondOre = self[56, 0]
        self.BlockofDiamond = self[57, 0]
        self.CraftingTable = self[58, 0]
        self.Crops = self[59, 0]
        self.Farmland = self[60, 0]
        self.Furnace = self[61, 0]
        self.LitFurnace = self[62, 0]


indev_blocktypes = IndevBlockTypeSet()


class PocketBlockTypeSet(BlockTypeSet):
    def __init__(self):
        super(PocketBlockTypeSet, self).__init__()
        self.name = "Pocket"
        self.addYamlBlocksFromFile("pocket.yaml")

        # --- Pocket static block defs ---

        self.Air = self[0, 0]
        self.Stone = self[1, 0]
        self.Grass = self[2, 0]
        self.Dirt = self[3, 0]
        self.Cobblestone = self[4, 0]
        self.WoodPlanks = self[5, 0]
        self.Sapling = self[6, 0]
        self.SpruceSapling = self[6, 1]
        self.BirchSapling = self[6, 2]
        self.Bedrock = self[7, 0]
        self.Wateractive = self[8, 0]
        self.Water = self[9, 0]
        self.Lavaactive = self[10, 0]
        self.Lava = self[11, 0]
        self.Sand = self[12, 0]
        self.Gravel = self[13, 0]
        self.GoldOre = self[14, 0]
        self.IronOre = self[15, 0]
        self.CoalOre = self[16, 0]
        self.Wood = self[17, 0]
        self.PineWood = self[17, 1]
        self.BirchWood = self[17, 2]
        self.Leaves = self[18, 0]
        self.Glass = self[20, 0]

        self.LapisLazuliOre = self[21, 0]
        self.LapisLazuliBlock = self[22, 0]
        self.Sandstone = self[24, 0]
        self.Bed = self[26, 0]
        self.Web = self[30, 0]
        self.UnusedShrub = self[31, 0]
        self.TallGrass = self[31, 1]
        self.Shrub = self[31, 2]
        self.WhiteWool = self[35, 0]
        self.OrangeWool = self[35, 1]
        self.MagentaWool = self[35, 2]
        self.LightBlueWool = self[35, 3]
        self.YellowWool = self[35, 4]
        self.LightGreenWool = self[35, 5]
        self.PinkWool = self[35, 6]
        self.GrayWool = self[35, 7]
        self.LightGrayWool = self[35, 8]
        self.CyanWool = self[35, 9]
        self.PurpleWool = self[35, 10]
        self.BlueWool = self[35, 11]
        self.BrownWool = self[35, 12]
        self.DarkGreenWool = self[35, 13]
        self.RedWool = self[35, 14]
        self.BlackWool = self[35, 15]
        self.Flower = self[37, 0]
        self.Rose = self[38, 0]
        self.BrownMushroom = self[39, 0]
        self.RedMushroom = self[40, 0]
        self.BlockofGold = self[41, 0]
        self.BlockofIron = self[42, 0]
        self.DoubleStoneSlab = self[43, 0]
        self.DoubleSandstoneSlab = self[43, 1]
        self.DoubleWoodenSlab = self[43, 2]
        self.DoubleCobblestoneSlab = self[43, 3]
        self.DoubleBrickSlab = self[43, 4]
        self.StoneSlab = self[44, 0]
        self.SandstoneSlab = self[44, 1]
        self.WoodenSlab = self[44, 2]
        self.CobblestoneSlab = self[44, 3]
        self.BrickSlab = self[44, 4]
        self.Brick = self[45, 0]
        self.TNT = self[46, 0]
        self.Bookshelf = self[47, 0]
        self.MossStone = self[48, 0]
        self.Obsidian = self[49, 0]

        self.Torch = self[50, 0]
        self.Fire = self[51, 0]
        self.WoodenStairs = self[53, 0]
        self.Chest = self[54, 0]
        self.DiamondOre = self[56, 0]
        self.BlockofDiamond = self[57, 0]
        self.CraftingTable = self[58, 0]
        self.Crops = self[59, 0]
        self.Farmland = self[60, 0]
        self.Furnace = self[61, 0]
        self.LitFurnace = self[62, 0]
        self.WoodenDoor = self[64, 0]
        self.Ladder = self[65, 0]
        self.StoneStairs = self[67, 0]
        self.IronDoor = self[71, 0]
        self.RedstoneOre = self[73, 0]
        self.RedstoneOreGlowing = self[74, 0]
        self.SnowLayer = self[78, 0]
        self.Ice = self[79, 0]

        self.Snow = self[80, 0]
        self.Cactus = self[81, 0]
        self.Clay = self[82, 0]
        self.SugarCane = self[83, 0]
        self.Fence = self[85, 0]
        self.Glowstone = self[89, 0]
        self.InvisibleBedrock = self[95, 0]
        self.Trapdoor = self[96, 0]

        self.StoneBricks = self[98, 0]
        self.GlassPane = self[102, 0]
        self.Watermelon = self[103, 0]
        self.MelonStem = self[105, 0]
        self.FenceGate = self[107, 0]
        self.BrickStairs = self[108, 0]

        self.GlowingObsidian = self[246, 0]
        self.NetherReactor = self[247, 0]
        self.NetherReactorUsed = self[247, 1]


pocket_blocktypes = PocketBlockTypeSet()

_indices = numpy.rollaxis(numpy.indices((id_limit, 16)), 0, 3)


def _filterTable(filters, unavailable, default=(0, 0)):
    # a filter table is a id_limit table of (ID, data) pairs.
    table = numpy.zeros((id_limit, 16, 2), dtype='uint8')
    table[:] = _indices
    for u in unavailable:
        try:
            if u[1] == 0:
                u = u[0]
        except TypeError:
            pass
        table[u] = default
    for f, t in filters:
        try:
            if f[1] == 0:
                f = f[0]
        except TypeError:
            pass
        table[f] = t
    return table


nullConversion = lambda b, d: (b, d)


def filterConversion(table):
    def convert(blocks, data):
        if data is None:
            data = 0
        t = table[blocks, data]
        return t[..., 0], t[..., 1]

    return convert


def guessFilterTable(matsFrom, matsTo):
    """ Returns a pair (filters, unavailable)
    filters is a list of (from, to) pairs;  from and to are (ID, data) pairs
    unavailable is a list of (ID, data) pairs in matsFrom not found in matsTo.

    Searches the 'englishName' and 'aka' fields to find matches.
    """
    filters = []
    unavailable = []
    toByName = dict(((b.englishName, b) for b in sorted(matsTo.allBlocks, reverse=True)))
    for fromBlock in matsFrom.allBlocks:
        block = toByName.get(fromBlock.englishName)
        if block is None:
            for b in matsTo.allBlocks:
                if b.englishName.startswith(fromBlock.englishName):
                    block = b
                    break
        if block is None:
            for b in matsTo.allBlocks:
                if fromBlock.englishName in b.englishName:
                    block = b
                    break
        if block is None:
            for b in matsTo.allBlocks:
                if fromBlock.englishName in b.aka:
                    block = b
                    break
        if block is None:
            if "Indigo Wool" == fromBlock.englishName:
                block = toByName.get("Purple Wool")
            elif "Violet Wool" == fromBlock.englishName:
                block = toByName.get("Purple Wool")

        if block:
            if block != fromBlock:
                filters.append(((fromBlock.ID, fromBlock.blockData), (block.ID, block.blockData)))
        else:
            unavailable.append((fromBlock.ID, fromBlock.blockData))

    return filters, unavailable


allMaterials = (pc_blocktypes, classic_blocktypes, pocket_blocktypes, indev_blocktypes)

_conversionFuncs = {}


def conversionFunc(destMats, sourceMats):
    if destMats is sourceMats:
        return nullConversion
    func = _conversionFuncs.get((destMats, sourceMats))
    if func:
        return func

    filters, unavailable = guessFilterTable(sourceMats, destMats)
    log.debug("From: %s", sourceMats)
    log.debug("To: %s", destMats)
    log.debug("%s %s %s", sourceMats.name, "=>", destMats.name)
    for a, b in [(sourceMats.blockWithID(*a), destMats.blockWithID(*b)) for a, b in filters]:
        log.debug("{0:20} => \"{1}\"".format('"' + a.englishName + '"', b.englishName))

    log.debug("")
    import pprint

    log.debug("Missing blocks: %s",
              pprint.pformat([sourceMats.blockWithID(*a).englishName for a in sorted(unavailable)]))

    table = _filterTable(filters, unavailable, (35, 0))
    func = filterConversion(table)
    _conversionFuncs[(destMats, sourceMats)] = func
    return func


def convertBlocks(destMats, sourceMats, blocks, blockData):
    if sourceMats == destMats:
        return blocks, blockData

    return conversionFunc(destMats, sourceMats)(blocks, blockData)


blocktypes_named = dict((i.name, i) for i in allMaterials)
blocktypes_named["Alpha"] = pc_blocktypes
