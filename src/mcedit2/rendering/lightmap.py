"""
    lightmap
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
import numpy

log = logging.getLogger(__name__)

lightBrightnessTable = range(16)

def generateLightBrightnessTable(minLight = 0.0):
    for index in range(16):
        darkness = 1.0 - index / 15.0
        lightBrightnessTable[index] = (1.0 - darkness) / (darkness * 3.0 + 1.0) * (1.0 - minLight) + minLight

generateLightBrightnessTable()

def generateLightmap(darkness, theEnd = False, gamma = 0.5):

    """
    :type gamma: Brightness setting in the Minecraft Video Options. Usual values are 0.0 to 1.0
    """
    lightmapColors = numpy.zeros((16, 16, 4), 'uint8')

    torchFlickerX = 0.0

    for x, y in numpy.ndindex(16, 16):
        var4 = darkness * 0.95 + 0.05
        skyLight = lightBrightnessTable[y] * var4
        blockLight = lightBrightnessTable[x] * (torchFlickerX * 0.1 + 1.5)

#        if (var2.lightningFlash > 0)
#            skyLight = var2.provider.lightBrightnessTable[index / 16]

        skyRed = skyLight * (darkness * 0.65 + 0.35)
        skyGreen = skyLight * (darkness * 0.65 + 0.35)
        blockGreen = blockLight * ((blockLight * 0.6 + 0.4) * 0.6 + 0.4)
        blockBlue = blockLight * (blockLight * blockLight * 0.6 + 0.4)
        red = skyRed + blockLight
        green = skyGreen + blockGreen
        blue = skyLight + blockBlue
        red = red * 0.96 + 0.03
        green = green * 0.96 + 0.03
        blue = blue * 0.96 + 0.03

#        if (this.field_82831_U > 0.0): #boss glow?
#            gamma = this.field_82832_V + (this.field_82831_U - this.field_82832_V) * ticks
#            red = red * (1.0 - gamma) + red * 0.7 * gamma
#            green = green * (1.0 - gamma) + green * 0.6 * gamma
#            blue = blue * (1.0 - gamma) + blue * 0.6 * gamma

        if theEnd:
            red = 0.22 + blockLight * 0.75
            green = 0.28 + blockGreen * 0.75
            blue = 0.25 + blockBlue * 0.75

#        if (this.mc.thePlayer.isPotionActive(Potion.nightVision))
#            gamma = this.func_82830_a(this.mc.thePlayer, ticks)
#            var17 = 1.0 / red
#
#            if (var17 > 1.0 / green)
#                var17 = 1.0 / green
#
#            if (var17 > 1.0 / blue)
#                var17 = 1.0 / blue
#
#            red = red * (1.0 - gamma) + red * var17 * gamma
#            green = green * (1.0 - gamma) + green * var17 * gamma
#            blue = blue * (1.0 - gamma) + blue * var17 * gamma

        if red > 1.0:
            red = 1.0

        if green > 1.0:
            green = 1.0

        if blue > 1.0:
            blue = 1.0

        redG = 1.0 - red
        greenG = 1.0 - green
        blueG = 1.0 - blue
        redG = 1.0 - redG * redG * redG * redG
        greenG = 1.0 - greenG * greenG * greenG * greenG
        blueG = 1.0 - blueG * blueG * blueG * blueG
        red = red * (1.0 - gamma) + redG * gamma
        green = green * (1.0 - gamma) + greenG * gamma
        blue = blue * (1.0 - gamma) + blueG * gamma
        red = red * 0.96 + 0.03
        green = green * 0.96 + 0.03
        blue = blue * 0.96 + 0.03

        if red > 1.0:
            red = 1.0

        if green > 1.0:
            green = 1.0

        if blue > 1.0:
            blue = 1.0

        if red < 0.0:
            red = 0.0

        if green < 0.0:
            green = 0.0

        if blue < 0.0:
            blue = 0.0

        alphaB = 255
        redB = int(red * 255.0)
        greenB = int(green * 255.0)
        blueB = int(blue * 255.0)
        slot = lightmapColors[x, y]
        slot[:] = (redB, greenB, blueB, alphaB)

    return lightmapColors


def main():
    colors = generateLightmap(1.0)
    numpy.set_printoptions(edgeitems=100)
    print (colors)

if __name__ == "__main__":
    main()
