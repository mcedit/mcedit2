#cython: boundscheck=False
"""
    ${NAME}
"""
from __future__ import absolute_import, division, print_function
import logging

cimport numpy
import numpy as np

from mcedit2.rendering import renderstates
from mcedit2.rendering.scenegraph.vertex_array import VertexNode
from mcedit2.rendering.layers import Layer
from mcedit2.rendering.vertexarraybuffer import QuadVertexArrayBuffer
cimport mcedit2.rendering.blockmodels as blockmodels

from libc.stdlib cimport malloc, realloc, free
from libc.string cimport memcpy

log = logging.getLogger(__name__)


lPowerLevels = [p/15. * 0.6 + 0.4 for p in range(16)]

lRedstonePowerColors = [
    (p if p > 0.4 else 0.3, max(0.0, p * p * 0.7 - 0.5), max(0.0, p * p * 0.6 - 0.7))
    for p in lPowerLevels
]
cdef unsigned char redstonePowerColors[16 * 4]
for i, (r, g, b) in enumerate(lRedstonePowerColors):
    redstonePowerColors[i*4] = b * 255
    redstonePowerColors[i*4+1] = g * 255
    redstonePowerColors[i*4+2] = r * 255
    redstonePowerColors[i*4+3] = 255

cdef unsigned char * foliageBitsPine = [0x61, 0x99, 0x61, 0xFF];   # BGRA
cdef unsigned char * foliageBitsBirch = [0x55, 0xA7, 0x80, 0xFF];  # BGRA

class BlockModelMesh(object):
    renderstate = renderstates.RenderstateAlphaTest
    def __init__(self, sectionUpdate):
        """

        :param sectionUpdate:
        :type sectionUpdate: mcedit2.rendering.chunkupdate.SectionUpdate
        :return:
        :rtype:
        """
        self.sectionUpdate = sectionUpdate
        self.sceneNode = None
        self.layer = Layer.Blocks

    def createVertexArrays(self):
        DEF quadFloats = 32
        DEF vertexBytes = 32
        cdef numpy.ndarray[numpy.uint16_t, ndim=3] areaBlocks
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaBlockLight
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaSkyLight
        cdef numpy.ndarray[numpy.uint8_t, ndim=3] areaData
        cdef numpy.ndarray[numpy.uint8_t, ndim=2] areaBiomes
        cdef numpy.ndarray[numpy.uint8_t, ndim=1] renderType
        cdef numpy.ndarray[numpy.uint8_t, ndim=1] opaqueCube
        cdef numpy.ndarray[numpy.float32_t, ndim=1] biomeTemp
        cdef numpy.ndarray[numpy.float32_t, ndim=1] biomeRain

        cdef blockmodels.BlockModels blockModels

        cdef short cy = self.sectionUpdate.cy

        atlas = self.sectionUpdate.chunkUpdate.updateTask.textureAtlas
        blockModels = atlas.blockModels
        if not blockModels.cooked:
            log.warn("createVertexArrays: Block models not cooked, aborting.")
            return

        blocktypes = self.sectionUpdate.blocktypes
        areaBlocks = self.sectionUpdate.areaBlocks
        areaBlockLight = self.sectionUpdate.areaLights("BlockLight")
        areaSkyLight = self.sectionUpdate.areaLights("SkyLight")
        areaData = self.sectionUpdate.areaData
        areaBiomes = self.sectionUpdate.areaBiomes
        renderType = self.sectionUpdate.renderType
        opaqueCube = np.array(blocktypes.opaqueCube)
        biomeTemp = self.sectionUpdate.biomeTemp
        biomeRain = self.sectionUpdate.biomeRain


        #faceQuadVerts = []
        cdef unsigned short waterID = blocktypes["minecraft:water"].ID
        cdef unsigned short waterFlowID = blocktypes["minecraft:flowing_water"].ID
        cdef unsigned short lavaID = blocktypes["minecraft:lava"].ID
        cdef unsigned short lavaFlowID = blocktypes["minecraft:flowing_lava"].ID

        # glass, stained glass are special cased to return False for `shouldSideBeRendered`
        cdef unsigned short glassID = blocktypes["minecraft:glass"].ID
        cdef unsigned short stainedGlassID = blocktypes.get("minecraft:stained_glass", blocktypes["minecraft:glass"]).ID

        # more special cases...
        def getID(internalName):
            bt = blocktypes.get(internalName, None)
            if bt is None:
                return 0
            return bt.ID

        cdef unsigned short anvilID = getID("minecraft:anvil")
        cdef unsigned short carpetID = getID("minecraft:carpet")
        cdef unsigned short dragonEggID = getID("minecraft:dragon_egg")
        cdef unsigned short endPortalID = getID("minecraft:end_portal")
        cdef unsigned short fenceID = getID("minecraft:fence")
        cdef unsigned short fenceGateID = getID("minecraft:fence_gate")
        cdef unsigned short hopperID = getID("minecraft:hopper")
        cdef unsigned short leavesID = getID("minecraft:leaves")
        cdef unsigned short leaves2ID = getID("minecraft:leaves2")
        cdef unsigned short paneID = getID("minecraft:glass_pane")
        cdef unsigned short barsID = getID("minecraft:iron_bars")
        cdef unsigned short pistonHeadID = getID("minecraft:piston_head")
        cdef unsigned short netherPortalID = getID("minecraft:portal")
        cdef unsigned short pComparatorID = getID("minecraft:powered_comparator")
        cdef unsigned short upComparatorID = getID("minecraft:unpowered_comparator")
        cdef unsigned short pRepeaterID = getID("minecraft:powered_repeater")
        cdef unsigned short upRepeaterID = getID("minecraft:unpowered_repeater")
        cdef unsigned short stoneSlabID = getID("minecraft:stone_slab")
        cdef unsigned short stoneSlab2ID = getID("minecraft:stone_slab2")
        cdef unsigned short woodenSlabID = getID("minecraft:wooden_slab")

        cdef unsigned short grassID = getID("minecraft:grass")
        cdef unsigned short snowID = getID("minecraft:snow")
        cdef unsigned short snowLayerID = getID("minecraft:snow_layer")
        cdef unsigned short netherFenceID = getID("minecraft:nether_brick_fence")
        cdef unsigned short stainedGlassPaneID = getID("minecraft:stained_glass_pane")

        cdef unsigned short woodenDoorID = getID("minecraft:wooden_door")
        cdef unsigned short ironDoorID = getID("minecraft:iron_door")
        cdef unsigned short birchDoorID = getID("minecraft:birch_door")
        cdef unsigned short spruceDoorID = getID("minecraft:spruce_door")
        cdef unsigned short jungleDoorID = getID("minecraft:jungle_door")
        cdef unsigned short acaciaDoorID = getID("minecraft:acacia_door")
        cdef unsigned short darkOakDoorID = getID("minecraft:dark_oak_door")

        cdef unsigned short cobbleWallID = getID("minecraft:cobblestone_wall")


        cdef unsigned short redstoneWireID = getID("minecraft:redstone_wire")
        cdef list powerSources

        powerSources = [
            getID("minecraft:stone_pressure_plate"),
            getID("minecraft:wooden_pressure_plate"),
            getID("minecraft:light_weighted_pressure_plate"),
            getID("minecraft:heavy_weighted_pressure_plate"),
            getID("minecraft:stone_button"),
            getID("minecraft:wooden_button"),
            getID("minecraft:trapped_chest"),
            getID("minecraft:redstone_block"),
            getID("minecraft:daylight_detector"),
            getID("minecraft:daylight_detector_inverted"),
            getID("minecraft:lever"),
            getID("minecraft:detector_rail"),
            getID("minecraft:tripwire_hook"),
            getID("minecraft:redstone_torch"),
            getID("minecraft:unlit_redstone_torch"),
        ]
        powerSources = [p for p in powerSources if p != 0]

        #cdef char fancyGraphics = self.sectionUpdate.fancyGraphics
        cdef char fancyGraphics = True

        if fancyGraphics:
            opaqueCube[leavesID] = False
            opaqueCube[leaves2ID] = False


        waterTexTuple = self.sectionUpdate.chunkUpdate.textureAtlas.texCoordsByName["assets/minecraft/textures/blocks/water_still.png"]
        cdef float[4] waterTex
        waterTex[0] = waterTexTuple[0]
        waterTex[1] = waterTexTuple[1]
        waterTex[2] = waterTexTuple[2]
        waterTex[3] = waterTexTuple[3]
        lavaTexTuple = self.sectionUpdate.chunkUpdate.textureAtlas.texCoordsByName["assets/minecraft/textures/blocks/lava_still.png"]
        cdef float[4] lavaTex
        lavaTex[0] = lavaTexTuple[0]
        lavaTex[1] = lavaTexTuple[1]
        lavaTex[2] = lavaTexTuple[2]
        lavaTex[3] = lavaTexTuple[3]

        cdef float * fluidTex

        cdef unsigned short y, z, x, ID, meta
        cdef short dx, dy, dz,
        cdef unsigned short nx, ny, nz, nID, upID
        cdef unsigned char nMeta
        cdef blockmodels.ModelQuadList quads
        cdef blockmodels.ModelQuad quad

        cdef short rx, ry, rz
        cdef unsigned char bl, sl
        cdef unsigned char tintType
        cdef unsigned char biomeID
        cdef float temperature, rainfall
        cdef unsigned int imageX, imageY
        cdef size_t imageOffset

        cdef size_t buffer_ptr = 0
        cdef size_t buffer_size = 256
        cdef float * vertexBuffer = <float *>malloc(buffer_size * sizeof(float) * quadFloats)
        cdef float * xyzuvstc
        cdef numpy.ndarray vabuffer
        cdef unsigned char * vertexColor
        cdef unsigned short color
        cdef size_t vertex, channel
        cdef unsigned char * tintColor

        cdef char doCull = 0
        cdef char foundActualState
        cdef char redstonePower
        cdef char wallCount


        cdef blockmodels.ModelQuadListObj quadListObj

        if vertexBuffer == NULL:
            return
        for y in range(1, 17):
            ry = y - 1 + (cy << 4)
            for z in range(1, 17):
                rz = z - 1
                for x in range(1, 17):
                    rx = x - 1
                    ID = areaBlocks[y, z, x]
                    if ID == 0:
                        continue
                    meta = areaData[y, z, x]
                    actualState = None
                    redstonePower = 0

                    if renderType[ID] == 3:  # model blocks
                        # if this block has actualStates, get its actualState
                        # using its neighbors and look up that state's models
                        # in blockModels.... ... ...

                        # to get its actual state, we need to get its current state from
                        # its id and meta, parse the state into properties,
                        # change some property values into others according to
                        # actualState logic, then use the new state to look up the model
                        # ... ... ...
                        # all without doing a dict lookup for every block...
                        #
                        # absolutely disgusting

                        def parseProps(ID, meta):
                            state = blocktypes.statesByID.get((ID, meta))
                            if state is None:
                                state = blocktypes.defaultBlockstates.get(ID)
                            if state is None or '[' not in state:
                                return {}
                            state = state.split('[')[1]
                            props = state[:-1].split(",")
                            props = [p.split("=") for p in props]
                            return {k:v for k,v in props}

                        def combineProps(props):
                            props = [k + "=" + v for k, v in props.iteritems()]
                            return tuple(sorted(props))

                        if grassID and (ID == grassID):
                            if (areaBlocks[y+1, z, x] == snowID
                                or areaBlocks[y+1, z, x] == snowLayerID):
                                actualState = "minecraft:grass", ("snowy=true",)

                        if (fenceID and (ID == fenceID)
                            or netherFenceID and (ID == netherFenceID)):
                            props = []
                            for direction, dx, dz in [
                                ("north", 0, -1),
                                ("south", 0, 1),
                                ("west", -1, 0),
                                ("east", 1, 0),
                            ]:
                                nID = areaBlocks[y, z+dz, x+dx]
                                props.append(direction + "=" + ("true"
                                             if opaqueCube[nID]
                                                or fenceID and nID == fenceID
                                                or fenceGateID and nID == fenceGateID
                                                or netherFenceID and nID == netherFenceID
                                             else "false"))
                            actualState = blocktypes.namesByID[ID], tuple(sorted(props))

                        if (paneID and (ID == paneID)
                            or stainedGlassPaneID and (ID == stainedGlassPaneID)
                            or barsID and (ID == barsID)):
                            props = {}
                            if ID == stainedGlassPaneID:
                                props = parseProps(ID, meta)

                            for direction, dx, dz in [
                                ("north", 0, -1),
                                ("south", 0, 1),
                                ("west", -1, 0),
                                ("east", 1, 0),
                            ]:
                                nID = areaBlocks[y, z+dz, x+dx]
                                props[direction] = ("true"
                                             if opaqueCube[nID]
                                                or (paneID and nID == paneID)
                                                or (barsID and nID == barsID)
                                                or (stainedGlassPaneID and nID == stainedGlassPaneID)
                                                or (glassID and nID == glassID)
                                                or (stainedGlassID and nID == stainedGlassID)
                                             else "false")
                            actualState = blocktypes.namesByID[ID], combineProps(props)

                        if ((woodenDoorID and ID == woodenDoorID)
                            or (ironDoorID and ID == ironDoorID)
                            or (birchDoorID and ID == birchDoorID)
                            or (spruceDoorID and ID == spruceDoorID)
                            or (jungleDoorID and ID == jungleDoorID)
                            or (acaciaDoorID and ID == acaciaDoorID)
                            or (darkOakDoorID and ID == darkOakDoorID)
                            ):
                            props = parseProps(ID, meta)
                            if len(props):
                                if props['half'] == 'upper':
                                    nID = areaBlocks[y-1, z, x]
                                    if nID == ID:
                                        lowerProps = parseProps(areaBlocks[y-1, z, x], areaData[y-1, z, x])
                                        for p in ['facing', 'hinge', 'open']:
                                            props[p] = lowerProps[p]
                                        actualState = blocktypes.namesByID[ID], combineProps(props)
                        
                        if cobbleWallID and ID == cobbleWallID:
                            props = parseProps(ID, meta)
                            props['up'] = "true"
                            wallCount = 0
                            for direction, dx, dz in [
                                ("north", 0, -1),
                                ("south", 0, 1),
                                ("west", -1, 0),
                                ("east", 1, 0),
                            ]:
                                nID = areaBlocks[y, z+dz, x+dx]
                                if nID == ID:
                                    props[direction] = "true"
                                wallCount += 1
                                
                            if wallCount == 2 and (
                                (props['north'] == props['south'] == 'true')
                                or (props['east'] == props['west'] == 'true')
                            ):
                                if areaBlocks[y+1, z, x] == 0:
                                    props['up'] = 'false'
                            
                            actualState = blocktypes.namesByID[ID], combineProps(props)
                        
                        if redstoneWireID and ID == redstoneWireID:
                            props = parseProps(ID, meta)
                            def isConnectible(nID, nMeta, dx, dz):
                                if (nID == redstoneWireID
                                    or (upComparatorID and nID == upComparatorID)
                                    or (pComparatorID and nID == pComparatorID)
                                    or (nID in powerSources)
                                    ):
                                    return True
                                elif ((pRepeaterID and nID == pRepeaterID)
                                      or (upRepeaterID and nID == upRepeaterID)):
                                    nProps = parseProps(nID, nMeta)
                                    if (dz != 0 and nProps['facing'] in ('north', 'south')
                                        or dx != 0 and nProps['facing'] in ('east', 'west')):
                                        return True

                            if len(props):
                                for direction, dx, dz in [
                                    ("north", 0, -1),
                                    ("south", 0, 1),
                                    ("west", -1, 0),
                                    ("east", 1, 0),
                                ]:
                                    nID = areaBlocks[y, z+dz, x+dx]
                                    nMeta = areaData[y, z+dz, x+dx]
                                    if isConnectible(nID, nMeta, dx, dz):
                                        props[direction] = "side"

                                    elif opaqueCube[nID] > 0:  # xxx isFullOpaqueCube
                                        nID = areaBlocks[y+1, z+dz, x+dx]
                                        nMeta = areaData[y+1, z+dz, x+dx]
                                        if isConnectible(nID, nMeta, dx, dz):
                                            props[direction] = "up"
                                    else:
                                        nID = areaBlocks[y-1, z+dz, x+dx]
                                        nMeta = areaData[y-1, z+dz, x+dx]
                                        if isConnectible(nID, nMeta, dx, dz):
                                            props[direction] = "side"

                                redstonePower = int(props['power'])

                            actualState = "minecraft:redstone_wire", combineProps(props)

                        if actualState is None:
                            quads = blockModels.cookedModelsByID[ID][meta]
                        else:
                            quadListObj = blockModels.cookedModelsForState(actualState)
                            quads = quadListObj.quadList

                        if quads.count == 0:
                            continue

                        if areaBiomes is not None:
                            biomeID = areaBiomes[z, x]
                        else:
                            biomeID = 1

                        for i in range(quads.count):
                            doCull = 0
                            quad = quads.quads[i]
                            if quad.cullface[0]:
                                nx = x + quad.cullface[1]
                                ny = y + quad.cullface[2]
                                nz = z + quad.cullface[3]
                                nID = areaBlocks[ny, nz, nx]
                                if (ID == endPortalID
                                    and quad.cullface[2] == -1):
                                    doCull = 0
                                elif (ID == anvilID
                                      or ID == dragonEggID
                                      or ID == fenceID
                                      or ID == fenceGateID
                                      or ID == hopperID
                                      or ID == pistonHeadID
                                      ):
                                    doCull = 0
                                elif ID == carpetID and quad.cullface[2] == 1:
                                    doCull = 0
                                elif ((ID == glassID or ID == stainedGlassID)
                                      and ((glassID and nID == glassID)
                                           or (stainedGlassID and nID == stainedGlassID))
                                      ):
                                    doCull = 1
                                elif ((ID == paneID
                                       or ID == barsID)
                                      and (ID == nID and meta == areaData[ny, nz, nx])):
                                    doCull = 1
                                elif (ID == netherPortalID and False):  # hairy, do later
                                    doCull = 1
                                elif (ID == stoneSlabID
                                      or ID == stoneSlab2ID
                                      or ID == woodenSlabID):
                                    if ((stoneSlabID and nID == stoneSlabID)
                                        or (stoneSlab2ID and nID == stoneSlab2ID)
                                        or (woodenSlabID and nID == woodenSlabID)):
                                        if (meta & 0x8) == (areaData[ny, nz, nx] & 0x8):
                                            doCull = 1
                                    else:
                                        doCull = opaqueCube[nID]
                                else:
                                    doCull = opaqueCube[nID]

                                if doCull:
                                    continue

                            nx = x + quad.quadface[1]
                            ny = y + quad.quadface[2]
                            nz = z + quad.quadface[3]
                            bl = areaBlockLight[ny, nz, nx]  # xxx block.useNeighborLighting
                            sl = areaSkyLight[ny, nz, nx]

                            xyzuvstc = vertexBuffer + buffer_ptr * quadFloats
                            memcpy(xyzuvstc, quad.xyzuvstc, sizeof(float) * quadFloats)

                            temperature = biomeTemp[biomeID]
                            rainfall = biomeRain[biomeID]
                            temperature = min(max(temperature, 0.0), 1.0)
                            rainfall = min(max(rainfall, 0.0), 1.0)

                            rainfall *= temperature

                            if quad.biomeTintType:
                                if quad.biomeTintType == blockmodels.BIOME_GRASS:
                                    imageX = <unsigned int>((1.0 - temperature) * (blockModels.grassImageX - 1))
                                    imageY = <unsigned int>((1.0 - rainfall) * (blockModels.grassImageY - 1))
                                    imageOffset = imageX + blockModels.grassImageX * imageY
                                    tintColor = &blockModels.grassImageBits[imageOffset * 4]
                                if quad.biomeTintType == blockmodels.BIOME_FOLIAGE:
                                    imageX = <unsigned int>((1.0 - temperature) * (blockModels.foliageImageX - 1))
                                    imageY = <unsigned int>((1.0 - rainfall) * (blockModels.foliageImageY - 1))
                                    imageOffset = imageX + blockModels.foliageImageX * imageY
                                    tintColor = &blockModels.foliageImageBits[imageOffset * 4]
                                if quad.biomeTintType == blockmodels.BIOME_FOLIAGE_PINE:
                                    tintColor = foliageBitsPine
                                if quad.biomeTintType == blockmodels.BIOME_FOLIAGE_BIRCH:
                                    tintColor = foliageBitsBirch
                                if quad.biomeTintType == blockmodels.BIOME_REDSTONE:
                                    tintColor = &redstonePowerColors[redstonePower * 4]
                                    # print("REDSTONE TINT", redstonePower, tintColor[0], tintColor[1], tintColor[2])

                                vertexColor = <unsigned char *>xyzuvstc
                                for vertex in range(4):
                                    for channel in range(3):
                                        color = vertexColor[vertexBytes * vertex + vertexBytes - 4 + channel]
                                        # image format is ARGB8, but this is with respect to 4-byte words
                                        # when the words are little endian, the byte ordering becomes BGRA
                                        # what i REALLY SHOULD do is get the pixel as an int and bit shift the bytes out.
                                        color *= tintColor[2-channel]
                                        color >>= 8
                                        vertexColor[vertexBytes * vertex + vertexBytes - 4 + channel] = <unsigned char>color


                            xyzuvstc[0] += rx
                            xyzuvstc[1] += ry
                            xyzuvstc[2] += rz
                            xyzuvstc[5] += sl
                            xyzuvstc[6] += bl


                            xyzuvstc[8] += rx
                            xyzuvstc[9] += ry
                            xyzuvstc[10] += rz
                            xyzuvstc[13] += sl
                            xyzuvstc[14] += bl


                            xyzuvstc[16] += rx
                            xyzuvstc[17] += ry
                            xyzuvstc[18] += rz
                            xyzuvstc[21] += sl
                            xyzuvstc[22] += bl


                            xyzuvstc[24] += rx
                            xyzuvstc[25] += ry
                            xyzuvstc[26] += rz
                            xyzuvstc[29] += sl
                            xyzuvstc[30] += bl

                            buffer_ptr += 1

                            if buffer_ptr >= buffer_size:
                                buffer_size *= 2
                                vertexBuffer = <float *>realloc(vertexBuffer, buffer_size * sizeof(float) * quadFloats)

                    elif renderType[ID] == 1:
                        if ID == waterFlowID or ID == waterID:
                            fluidTex = waterTex
                        elif ID == lavaFlowID or ID == lavaID:
                            fluidTex = lavaTex
                        else:
                            continue
                        if meta > 8:
                            meta = 8  # "falling" water - always full cube

                        # upID = areaBlocks[y+1, z, x]
                        # if upID == waterID or upID == waterFlowID or upID == lavaID or upID == lavaFlowID:
                        #     quads = blockModels.fluidQuads[8]  # block above has fluid - fill this fluid block
                        # else:
                        quads = blockModels.fluidQuads[meta]

                        bl = areaBlockLight[y, z, x]  # xxx block.useNeighborLighting
                        sl = areaSkyLight[y, z, x]
                        for i in range(6):
                            quad = quads.quads[i]
                            nx = x + quad.quadface[1]
                            ny = y + quad.quadface[2]
                            nz = z + quad.quadface[3]
                            nID = areaBlocks[ny, nz, nx]
                            if opaqueCube[nID]:
                                continue
                            if nID == waterID or nID == waterFlowID or nID == lavaID or nID == lavaFlowID:
                                nMeta = areaData[ny, nz, nx]
                                if nMeta > 7 or 7 - (nMeta & 0x7) >= 7 - (meta & 0x7):
                                    continue  # cull face as the neighboring block is fuller

                            xyzuvstc = vertexBuffer + buffer_ptr * quadFloats
                            memcpy(xyzuvstc, quad.xyzuvstc, sizeof(float) * quadFloats)

                            xyzuvstc[0] += rx
                            xyzuvstc[1] += ry
                            xyzuvstc[2] += rz
                            xyzuvstc[3] += fluidTex[0]
                            xyzuvstc[4] += fluidTex[1]
                            xyzuvstc[5] += sl
                            xyzuvstc[6] += bl


                            xyzuvstc[8] += rx
                            xyzuvstc[9] += ry
                            xyzuvstc[10] += rz
                            xyzuvstc[11] += fluidTex[0]
                            xyzuvstc[12] += fluidTex[1]
                            xyzuvstc[13] += sl
                            xyzuvstc[14] += bl


                            xyzuvstc[16] += rx
                            xyzuvstc[17] += ry
                            xyzuvstc[18] += rz
                            xyzuvstc[19] += fluidTex[0]
                            xyzuvstc[20] += fluidTex[1]
                            xyzuvstc[21] += sl
                            xyzuvstc[22] += bl


                            xyzuvstc[24] += rx
                            xyzuvstc[25] += ry
                            xyzuvstc[26] += rz
                            xyzuvstc[27] += fluidTex[0]
                            xyzuvstc[28] += fluidTex[1]
                            xyzuvstc[29] += sl
                            xyzuvstc[30] += bl

                            buffer_ptr += 1

                            if buffer_ptr >= buffer_size:
                                buffer_size *= 2
                                vertexBuffer = <float *>realloc(vertexBuffer, buffer_size * sizeof(float) * quadFloats)

        if buffer_ptr:  # now buffer size
            vertexArray = QuadVertexArrayBuffer(buffer_ptr)
            vabuffer = vertexArray.buffer
            memcpy(vabuffer.data, vertexBuffer, buffer_ptr * sizeof(float) * quadFloats)
            self.sceneNode = VertexNode(vertexArray)
            self.sceneNode.name = "cy=%d" % self.sectionUpdate.cy
        free(vertexBuffer)
