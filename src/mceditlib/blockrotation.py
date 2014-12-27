"""
   blockrotation.py

   Functions for adjusting blockdatas after rotating, rolling, flipping
   or mirroring a schematic file.

   Most of this file initializes the gigantic lookup tables that
   list the new blockdata for each blocktype and rotation type. A lot of this
   should be moved to the block definition file (minecraft.json) by naming
   the different blockdata values with directions and inferring the rotations
   from those. Only certain blocks (e.g. Doors and Vines) need special handling
   during rotation.

   Entities and TileEntities are rotated in schematic.py.
"""

from __future__ import absolute_import

from numpy import arange, zeros

from mceditlib import blocktypes

def genericVerticalFlip(cls):
    rotation = arange(16, dtype='uint8')
    if hasattr(cls, "Up") and hasattr(cls, "Down"):
        rotation[cls.Up] = cls.Down
        rotation[cls.Down] = cls.Up

    if hasattr(cls, "TopNorth") and hasattr(cls, "TopWest") and hasattr(cls, "TopSouth") and hasattr(cls, "TopEast"):
        rotation[cls.North] = cls.TopNorth
        rotation[cls.West] = cls.TopWest
        rotation[cls.South] = cls.TopSouth
        rotation[cls.East] = cls.TopEast
        rotation[cls.TopNorth] = cls.North
        rotation[cls.TopWest] = cls.West
        rotation[cls.TopSouth] = cls.South
        rotation[cls.TopEast] = cls.East

    return rotation


def genericRotation(cls):
    rotation = arange(16, dtype='uint8')
    rotation[cls.North] = cls.West
    rotation[cls.West] = cls.South
    rotation[cls.South] = cls.East
    rotation[cls.East] = cls.North
    if hasattr(cls, "TopNorth") and hasattr(cls, "TopWest") and hasattr(cls, "TopSouth") and hasattr(cls, "TopEast"):
        rotation[cls.TopNorth] = cls.TopWest
        rotation[cls.TopWest] = cls.TopSouth
        rotation[cls.TopSouth] = cls.TopEast
        rotation[cls.TopEast] = cls.TopNorth

    return rotation


def genericEastWestFlip(cls):
    rotation = arange(16, dtype='uint8')
    rotation[cls.West] = cls.East
    rotation[cls.East] = cls.West
    if hasattr(cls, "TopWest") and hasattr(cls, "TopEast"):
        rotation[cls.TopWest] = cls.TopEast
        rotation[cls.TopEast] = cls.TopWest

    return rotation


def genericNorthSouthFlip(cls):
    rotation = arange(16, dtype='uint8')
    rotation[cls.South] = cls.North
    rotation[cls.North] = cls.South
    if hasattr(cls, "TopNorth") and hasattr(cls, "TopSouth"):
        rotation[cls.TopSouth] = cls.TopNorth
        rotation[cls.TopNorth] = cls.TopSouth

    return rotation

rotationClasses = []


def genericFlipRotation(cls):
    cls.rotateLeft = genericRotation(cls)

    cls.flipVertical = genericVerticalFlip(cls)
    cls.flipEastWest = genericEastWestFlip(cls)
    cls.flipNorthSouth = genericNorthSouthFlip(cls)
    rotationClasses.append(cls)

#
#class Torch:
#    blocktypes = [
#        pc_blocktypes.Torch.ID,
#        pc_blocktypes.RedstoneTorchOn.ID,
#        pc_blocktypes.RedstoneTorchOff.ID,
#    ]
#
#    South = 1
#    North = 2
#    West = 3
#    East = 4
#
#genericFlipRotation(Torch)
#
#
#class Ladder:
#    blocktypes = [pc_blocktypes.Ladder.ID]
#
#    East = 2
#    West = 3
#    North = 4
#    South = 5
#genericFlipRotation(Ladder)
#
#
#class Stair:
#    blocktypes = [b.ID for b in pc_blocktypes.AllStairs]
#
#    South = 0
#    North = 1
#    West = 2
#    East = 3
#    TopSouth = 4
#    TopNorth = 5
#    TopWest = 6
#    TopEast = 7
#genericFlipRotation(Stair)
#
#
#class HalfSlab:
#    blocktypes = [pc_blocktypes.StoneSlab.ID]
#
#    StoneSlab = 0
#    SandstoneSlab = 1
#    WoodenSlab = 2
#    CobblestoneSlab = 3
#    BrickSlab = 4
#    StoneBrickSlab = 5
#    TopStoneSlab = 8
#    TopSandstoneSlab = 9
#    TopWoodenSlab = 10
#    TopCobblestoneSlab = 11
#    TopBrickSlab = 12
#    TopStoneBrickSlab = 13
#
#HalfSlab.flipVertical =  arange(16, dtype='uint8')
#HalfSlab.flipVertical[HalfSlab.StoneSlab] = HalfSlab.TopStoneSlab
#HalfSlab.flipVertical[HalfSlab.SandstoneSlab] = HalfSlab.TopSandstoneSlab
#HalfSlab.flipVertical[HalfSlab.WoodenSlab] = HalfSlab.TopWoodenSlab
#HalfSlab.flipVertical[HalfSlab.CobblestoneSlab] = HalfSlab.TopCobblestoneSlab
#HalfSlab.flipVertical[HalfSlab.BrickSlab] = HalfSlab.TopBrickSlab
#HalfSlab.flipVertical[HalfSlab.StoneBrickSlab] = HalfSlab.TopStoneBrickSlab
#HalfSlab.flipVertical[HalfSlab.TopStoneSlab] = HalfSlab.StoneSlab
#HalfSlab.flipVertical[HalfSlab.TopSandstoneSlab] = HalfSlab.SandstoneSlab
#HalfSlab.flipVertical[HalfSlab.TopWoodenSlab] = HalfSlab.WoodenSlab
#HalfSlab.flipVertical[HalfSlab.TopCobblestoneSlab] = HalfSlab.CobblestoneSlab
#HalfSlab.flipVertical[HalfSlab.TopBrickSlab] = HalfSlab.BrickSlab
#HalfSlab.flipVertical[HalfSlab.TopStoneBrickSlab] = HalfSlab.StoneBrickSlab
#rotationClasses.append(HalfSlab)
#
#
#class WallSign:
#    blocktypes = [pc_blocktypes.WallSign.ID]
#
#    East = 2
#    West = 3
#    North = 4
#    South = 5
#genericFlipRotation(WallSign)
#
#
#class FurnaceDispenserChest:
#    blocktypes = [
#        pc_blocktypes.Furnace.ID,
#        pc_blocktypes.LitFurnace.ID,
#        pc_blocktypes.Dispenser.ID,
#        pc_blocktypes.Chest.ID,
#    ]
#    East = 2
#    West = 3
#    North = 4
#    South = 5
#genericFlipRotation(FurnaceDispenserChest)
#
#
#class Pumpkin:
#    blocktypes = [
#        pc_blocktypes.Pumpkin.ID,
#        pc_blocktypes.JackOLantern.ID,
#    ]
#
#    East = 0
#    South = 1
#    West = 2
#    North = 3
#genericFlipRotation(Pumpkin)
#
#
#class Rail:
#    blocktypes = [pc_blocktypes.Rail.ID]
#
#    EastWest = 0
#    NorthSouth = 1
#    South = 2
#    North = 3
#    East = 4
#    West = 5
#
#    Northeast = 6
#    Southeast = 7
#    Southwest = 8
#    Northwest = 9
#
#
#def generic8wayRotation(cls):
#
#    cls.rotateLeft = genericRotation(cls)
#    cls.rotateLeft[cls.Northeast] = cls.Northwest
#    cls.rotateLeft[cls.Southeast] = cls.Northeast
#    cls.rotateLeft[cls.Southwest] = cls.Southeast
#    cls.rotateLeft[cls.Northwest] = cls.Southwest
#
#    cls.flipEastWest = genericEastWestFlip(cls)
#    cls.flipEastWest[cls.Northeast] = cls.Northwest
#    cls.flipEastWest[cls.Northwest] = cls.Northeast
#    cls.flipEastWest[cls.Southwest] = cls.Southeast
#    cls.flipEastWest[cls.Southeast] = cls.Southwest
#
#    cls.flipNorthSouth = genericNorthSouthFlip(cls)
#    cls.flipNorthSouth[cls.Northeast] = cls.Southeast
#    cls.flipNorthSouth[cls.Southeast] = cls.Northeast
#    cls.flipNorthSouth[cls.Southwest] = cls.Northwest
#    cls.flipNorthSouth[cls.Northwest] = cls.Southwest
#    rotationClasses.append(cls)
#
#generic8wayRotation(Rail)
#Rail.rotateLeft[Rail.NorthSouth] = Rail.EastWest
#Rail.rotateLeft[Rail.EastWest] = Rail.NorthSouth
#
#
#def applyBit(apply):
#    def _applyBit(class_or_array):
#        if hasattr(class_or_array, "rotateLeft"):
#            for a in (class_or_array.flipEastWest,
#                      class_or_array.flipNorthSouth,
#                      class_or_array.rotateLeft):
#                apply(a)
#        else:
#            array = class_or_array
#            apply(array)
#
#    return _applyBit
#
#
#@applyBit
#def applyBit8(array):
#    array[8:16] = array[0:8] | 0x8
#
#
#@applyBit
#def applyBit4(array):
#    array[4:8] = array[0:4] | 0x4
#    array[12:16] = array[8:12] | 0x4
#
#
#@applyBit
#def applyBits48(array):
#    array[4:8] = array[0:4] | 0x4
#    array[8:16] = array[0:8] | 0x8
#
#applyThrownBit = applyBit8
#
#
#class PoweredDetectorRail(Rail):
#    blocktypes = [pc_blocktypes.PoweredRail.ID, pc_blocktypes.DetectorRail.ID]
#PoweredDetectorRail.rotateLeft = genericRotation(PoweredDetectorRail)
#
#PoweredDetectorRail.rotateLeft[PoweredDetectorRail.NorthSouth] = PoweredDetectorRail.EastWest
#PoweredDetectorRail.rotateLeft[PoweredDetectorRail.EastWest] = PoweredDetectorRail.NorthSouth
#
#PoweredDetectorRail.flipEastWest = genericEastWestFlip(PoweredDetectorRail)
#PoweredDetectorRail.flipNorthSouth = genericNorthSouthFlip(PoweredDetectorRail)
#applyThrownBit(PoweredDetectorRail)
#rotationClasses.append(PoweredDetectorRail)
#
#
#class Lever:
#    blocktypes = [pc_blocktypes.Lever.ID]
#    ThrownBit = 0x8
#    South = 1
#    North = 2
#    West = 3
#    East = 4
#    EastWest = 5
#    NorthSouth = 6
#Lever.rotateLeft = genericRotation(Lever)
#Lever.rotateLeft[Lever.NorthSouth] = Lever.EastWest
#Lever.rotateLeft[Lever.EastWest] = Lever.NorthSouth
#Lever.flipEastWest = genericEastWestFlip(Lever)
#Lever.flipNorthSouth = genericNorthSouthFlip(Lever)
#applyThrownBit(Lever)
#rotationClasses.append(Lever)
#
#
#class Button:
#    blocktypes = [pc_blocktypes.Button.ID, pc_blocktypes.WoodButton.ID]
#    PressedBit = 0x8
#    South = 1
#    North = 2
#    West = 3
#    East = 4
#Button.rotateLeft = genericRotation(Button)
#Button.flipEastWest = genericEastWestFlip(Button)
#Button.flipNorthSouth = genericNorthSouthFlip(Button)
#applyThrownBit(Button)
#rotationClasses.append(Button)
#
#
#class SignPost:
#    blocktypes = [pc_blocktypes.Sign.ID]
#    #west is 0, increasing clockwise
#
#    rotateLeft = arange(16, dtype='uint8')
#    rotateLeft -= 4
#    rotateLeft &= 0xf
#
#    flipEastWest = arange(16, dtype='uint8')
#    flipNorthSouth = arange(16, dtype='uint8')
#    pass
#
#rotationClasses.append(SignPost)
#
#
#class Bed:
#    blocktypes = [pc_blocktypes.Bed.ID]
#    West = 0
#    North = 1
#    East = 2
#    South = 3
#
#genericFlipRotation(Bed)
#applyBit8(Bed)
#applyBit4(Bed)
#
#
#class Door:
#    blocktypes = [
#        pc_blocktypes.IronDoor.ID,
#        pc_blocktypes.WoodenDoor.ID,
#    ]
#    TopHalfBit = 0x8
#    SwungCCWBit = 0x4
#
#    Northeast = 0
#    Southeast = 1
#    Southwest = 2
#    Northwest = 3
#
#    rotateLeft = arange(16, dtype='uint8')
#
#Door.rotateLeft[Door.Northeast] = Door.Northwest
#Door.rotateLeft[Door.Southeast] = Door.Northeast
#Door.rotateLeft[Door.Southwest] = Door.Southeast
#Door.rotateLeft[Door.Northwest] = Door.Southwest
#
#applyBit4(Door.rotateLeft)
#
##when flipping horizontally, swing the doors so they at least look the same
#
#Door.flipEastWest = arange(16, dtype='uint8')
#Door.flipEastWest[Door.Northeast] = Door.Northwest
#Door.flipEastWest[Door.Northwest] = Door.Northeast
#Door.flipEastWest[Door.Southwest] = Door.Southeast
#Door.flipEastWest[Door.Southeast] = Door.Southwest
#Door.flipEastWest[4:8] = Door.flipEastWest[0:4]
#Door.flipEastWest[0:4] = Door.flipEastWest[4:8] | 0x4
#Door.flipEastWest[8:16] = Door.flipEastWest[0:8] | 0x8
#
#Door.flipNorthSouth = arange(16, dtype='uint8')
#Door.flipNorthSouth[Door.Northeast] = Door.Southeast
#Door.flipNorthSouth[Door.Northwest] = Door.Southwest
#Door.flipNorthSouth[Door.Southwest] = Door.Northwest
#Door.flipNorthSouth[Door.Southeast] = Door.Northeast
#Door.flipNorthSouth[4:8] = Door.flipNorthSouth[0:4]
#Door.flipNorthSouth[0:4] = Door.flipNorthSouth[4:8] | 0x4
#Door.flipNorthSouth[8:16] = Door.flipNorthSouth[0:8] | 0x8
#
#rotationClasses.append(Door)
#
#
#class RedstoneRepeater:
#    blocktypes = [
#        pc_blocktypes.RedstoneRepeaterOff.ID,
#        pc_blocktypes.RedstoneRepeaterOn.ID,
#
#    ]
#
#    East = 0
#    South = 1
#    West = 2
#    North = 3
#
#genericFlipRotation(RedstoneRepeater)
#
##high bits of the repeater indicate repeater delay, and should be preserved
#applyBits48(RedstoneRepeater)
#
#
#class Trapdoor:
#    blocktypes = [pc_blocktypes.Trapdoor.ID]
#
#    West = 0
#    East = 1
#    South = 2
#    North = 3
#
#genericFlipRotation(Trapdoor)
#applyOpenedBit = applyBit4
#applyOpenedBit(Trapdoor)
#
#
#class PistonBody:
#    blocktypes = [pc_blocktypes.StickyPiston.ID, pc_blocktypes.Piston.ID]
#
#    Down = 0
#    Up = 1
#    East = 2
#    West = 3
#    North = 4
#    South = 5
#
#genericFlipRotation(PistonBody)
#applyPistonBit = applyBit8
#applyPistonBit(PistonBody)
#
#
#class PistonHead(PistonBody):
#    blocktypes = [pc_blocktypes.PistonHead.ID]
#rotationClasses.append(PistonHead)
#
#
##Mushroom types:
##Value     Description     Textures
##0     Fleshy piece     Pores on all sides
##1     Corner piece     Cap texture on top, directions 1 (cloud direction) and 2 (sunrise)
##2     Side piece     Cap texture on top and direction 2 (sunrise)
##3     Corner piece     Cap texture on top, directions 2 (sunrise) and 3 (cloud origin)
##4     Side piece     Cap texture on top and direction 1 (cloud direction)
##5     Top piece     Cap texture on top
##6     Side piece     Cap texture on top and direction 3 (cloud origin)
##7     Corner piece     Cap texture on top, directions 0 (sunset) and 1 (cloud direction)
##8     Side piece     Cap texture on top and direction 0 (sunset)
##9     Corner piece     Cap texture on top, directions 3 (cloud origin) and 0 (sunset)
##10     Stem piece     Stem texture on all four sides, pores on top and bottom
#
#
#class HugeMushroom:
#    blocktypes = [pc_blocktypes.HugeRedMushroom.ID, pc_blocktypes.HugeBrownMushroom.ID]
#    Northeast = 1
#    East = 2
#    Southeast = 3
#    South = 6
#    Southwest = 9
#    West = 8
#    Northwest = 7
#    North = 4
#
#generic8wayRotation(HugeMushroom)
#
#
#class Vines:
#    blocktypes = [pc_blocktypes.Vines.ID]
#
#    WestBit = 1
#    NorthBit = 2
#    EastBit = 4
#    SouthBit = 8
#
#    rotateLeft = arange(16, dtype='uint8')
#    flipEastWest = arange(16, dtype='uint8')
#    flipNorthSouth = arange(16, dtype='uint8')
#
#
##Hmm... Since each bit is a direction, we can rotate by shifting!
#Vines.rotateLeft = 0xf & ((Vines.rotateLeft >> 1) | (Vines.rotateLeft << 3))
## Wherever each bit is set, clear it and set the opposite bit
#EastWestBits = (Vines.EastBit | Vines.WestBit)
#Vines.flipEastWest[(Vines.flipEastWest & EastWestBits) > 0] ^= EastWestBits
#
#NorthSouthBits = (Vines.NorthBit | Vines.SouthBit)
#Vines.flipNorthSouth[(Vines.flipNorthSouth & NorthSouthBits) > 0] ^= NorthSouthBits
#
#rotationClasses.append(Vines)


def masterRotationTable(attrname):
    # compute a blocktypes.id_limitx16 table mapping each possible blocktype/data combination to
    # the resulting data when the block is rotated
    table = zeros((blocktypes.id_limit, 16), dtype='uint8')
    table[:] = arange(16, dtype='uint8')
    for cls in rotationClasses:
        if hasattr(cls, attrname):
            blocktable = getattr(cls, attrname)
            for blocktype in cls.blocktypes:
                table[blocktype] = blocktable

    return table


def rotationTypeTable():
    table = {}
    for cls in rotationClasses:
        for b in cls.blocktypes:
            table[b] = cls

    return table


class BlockRotation:
    rotateLeft = masterRotationTable("rotateLeft")
    flipEastWest = masterRotationTable("flipEastWest")
    flipNorthSouth = masterRotationTable("flipNorthSouth")
    flipVertical = masterRotationTable("flipVertical")
    typeTable = rotationTypeTable()


def SameRotationType(blocktype1, blocktype2):
    #use different default values for typeTable.get() to make it return false when neither blocktype is present
    return BlockRotation.typeTable.get(blocktype1.ID) == BlockRotation.typeTable.get(blocktype2.ID, BlockRotation)


def FlipVertical(blocks, data):
    data[:] = BlockRotation.flipVertical[blocks, data]


def FlipNorthSouth(blocks, data):
    data[:] = BlockRotation.flipNorthSouth[blocks, data]


def FlipEastWest(blocks, data):
    data[:] = BlockRotation.flipEastWest[blocks, data]


def RotateLeft(blocks, data):
    data[:] = BlockRotation.rotateLeft[blocks, data]
