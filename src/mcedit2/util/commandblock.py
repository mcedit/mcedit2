# coding=utf-8
"""
    commandblock
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

from mceditlib.selection import BoundingBox

log = logging.getLogger(__name__)

"""
/achievement	    Gives or removes an achievement from a player.	Op	—	—	—	Players	—
/blockdata	        Modifies the data tag of a block.	Op	—	Blocks	—	—	—
/clear	            Clears items from player inventory.	Op	—	—	—	Players	—
    /clone	            Copies blocks from one place to another.	Op	—	Blocks	—	—	—
/defaultgamemode	Sets the default game mode.	Op	—	—	—	—	World
/difficulty	        Sets the difficulty level.	Op	—	—	—	Players	—
/effect	            Add or remove status effects.	Op	—	—	Entities	Players	—
/enchant	        Enchants a player item.	Op	—	—	—	Players	—
/entitydata	        Modifies the data tag of an entity.	Op	—	—	Entities	—	—
/execute	        Executes another command.	Op	—	—	—	—	—
/fill	            Fills a region with a specific block.	Op	—	Blocks	—	—	—
/gamemode	        Sets a player's game mode.	Op	—	—	—	Players	—
/gamerule	        Sets or queries a game rule value.	Op	—	—	—	—	World
/give	            Gives an item to a player.	Op	—	—	—	Players	—
/help	            Provides help for commands.	—	—	—	—	—	—
/kill	            Kills entities (players, mobs, items, etc.).	Op	—	—	Entities	Players	—
/list	            Lists players on the server.	Op	MP	—	—	Players	—
/me	                Displays a message about yourself.	—	—	—	—	Players	—
/particle	        Creates particles.	Op	—	—	—	Players	—
/playsound	        Plays a sound.	Op	—	—	—	Players	—
/replaceitem	    Replaces items in inventories.	Op	—	Blocks	Entities	Players	—
/say	            Displays a message to multiple players.	Op	—	—	—	—	—
/scoreboard	        Manages objectives, players, and teams.	Op	—	—	Entities	Players	—
/seed	            Displays the world seed.	Op	—	—	—	—	World
        /setblock	        Changes a block to another block.	Op	—	Blocks	—	—	—
/setworldspawn	    Sets the world spawn.	Op	—	—	—	—	World
/spawnpoint	        Sets the spawn point for a player.	Op	—	—	—	Players	—
/spreadplayers	    Teleports entities to random locations.	Op	—	—	Entities	Players	—
/stats	            Update objectives from command results.	Op	—	Blocks	Entities	Players	—
        /summon	            Summons an entity.	Op	—	—	Entities	—	—
/tell	            Displays a private message to other players.	—	—	—	—	Players	—
/tellraw	        Displays a JSON message to players.	Op	—	—	—	Players	—
/testfor	        Counts entities matching specified conditions.	Op	—	—	Entities	Players	—
        /testforblock	    Tests whether a block is in a location.	Op	—	Blocks	—	—	—
/testforblocks	    Tests whether the blocks in two regions match.	Op	—	Blocks	—	—	—
/time	            Changes or queries the world's game time.	Op	—	—	—	—	World
/title	            Manages screen titles.	Op	—	—	—	Players	—
/toggledownfall	    Toggles the weather.	Op	—	—	—	—	World
/tp	                Teleports entities.	Op	—	—	Entities	Players	—
/trigger	        Sets a trigger to be activated.	—	—	—	—	Players	—
/weather	        Sets the weather.	Op	—	—	—	—	World
/worldborder	    Manages the world border.	Op	—	—	—	—	World
/xp	                Adds or removes player experience.	Op	—	—	—	Players	—

The following commands are usable but with limited functionality (their output only
displays in the command block's Previous Output pane rather than being displayed in the
chat): /help, /seed, /list, /scoreboard objectives, /scoreboard players, and /scoreboard
teams list.

The following commands use the command block's name (defaults to @) in their
output: /me, /say, and /tell.
"""

class ParseError(ValueError):
    """
    Raised when parsing command text fails (due to wrong number of arguments, for example)
    """

def ParseCommand(commandText):
    if commandText[0] == "/":
        commandText = commandText[1:]

    name, args = commandText.split(None, 1)
    name = name.lower()
    cmdClass = _commandClasses.get(name)
    if cmdClass is None:
        return UnknownCommand(name, args)
    else:
        return cmdClass(args)


def parseCoord(text):
    rel = False
    if text[0] == '~':
        rel = True
        text = text[1:]
    if len(text):
        try:
            c = int(text)
        except ValueError:
            c = float(text)
    else:
        c = 0
    return c, rel


def formatCoords(cmd):
    return formatCoordTuple(cmd.x, cmd.relX,
                            cmd.y, cmd.relY,
                            cmd.z, cmd.relZ)

def formatCoordTuple(x, relX, y, relY, z, relZ):
    text = ""
    if x is not None:
        if relX:
            text += "~"
        if x or not relX:
            text += str(x)
        text += " "

        if y is not None:
            if relY:
                text += "~"
            if y or not relY:
                text += str(y)
            text += " "

            if z is not None:
                if relZ:
                    text += "~"
                if z or not relZ:
                    text += str(z)
    return text

def formatDetectCoords(cmd):
    text = ""
    if cmd.relDX:
        text += "~"
    if cmd.dx or not cmd.relDX:
        text += str(cmd.dx)
    text += " "

    if cmd.relDY:
        text += "~"
    if cmd.dy or not cmd.relDY:
        text += str(cmd.dy)
    text += " "
    if cmd.relDZ:
        text += "~"
    if cmd.dz or not cmd.relDZ:
        text += str(cmd.dz)

    return text

def formatRepr(cmd, attrs):
    args = ", ".join("%s=%s" % (a, getattr(cmd, a)) for a in attrs)
    return "%s(%s)" % (cmd.__class__.__name__, args)


class UnknownCommand(object):
    def __init__(self, name, args):
        self.name = name
        self.args = args

    def __str__(self):
        return "/%s %s" % (self.name, self.args)


def argsplit(args, numargs, required=0):
    """
    Like str.split(), but always returns a list of length `numargs`
    """

    args = args.split(None, numargs-1)
    if len(args) < required:
        raise ParseError("Not enough arguments to command.")
    if len(args) < numargs:
        args = args + [""] * (numargs - len(args))
    return args

class TargetSelector(object):
    playerName = None
    targetVariable = None
    targetArgs = ()

    def __str__(self):
        if self.playerName is not None:
            return self.playerName
        else:
            selectorArgs = []
            implicitArgs = []
            for key, value in self.targetArgs:
                if key == 'x' and len(implicitArgs) == 0:
                    implicitArgs.append(value)
                elif key == 'y' and len(implicitArgs) == 1:
                    implicitArgs.append(value)
                elif key == 'z' and len(implicitArgs) == 2:
                    implicitArgs.append(value)
                elif key == 'r' and len(implicitArgs) == 3:
                    implicitArgs.append(value)
                else:
                    selectorArgs.append(key + "=" + value)

            selectorText = ",".join(implicitArgs + selectorArgs)

            return "@%s[%s]" % (self.targetVariable, selectorText)


    def __init__(self, selectorText):
        if selectorText[0] == "@":
            if len(selectorText) < 2:
                raise ParseError("Target selector has @ without target variable.")

            targetVariable = selectorText[1]
            targetArgText = selectorText[2:]

            if targetArgText[0] != '[' and targetArgText[-1] != ']':
                raise ParseError("Selector arguments must be enclosed in [].")

            targetArgText = targetArgText[1:-1]
            targetArgs = targetArgText.split(",")

            parsedArgs = []
            implicitKeys = list('xyzr')

            for arg in targetArgs:
                if '=' not in arg:
                    if len(implicitKeys):
                        key = implicitKeys.pop(0)
                        value = arg
                    else:
                        raise ParseError("Selector argument must be in the form key=value.")
                else:
                    key, value = arg.split('=', 1)

                parsedArgs.append((key, value))

            self.targetVariable = targetVariable
            self.targetArgs = parsedArgs

        else:
            # No '@', so this is a player selector
            self.playerName = selectorText

    int_keys = {'x', 'y', 'z', 'r', 'rm', 'c', 'l', 'lm', 'dx', 'dy', 'dz',
                'rx', 'rxm', 'ry', 'rym'}

    def getArg(self, arg):
        for key, value in self.targetArgs:
            if key == arg:
                if key in self.int_keys or key.startswith("score_"):
                    value = int(value)
                    return value
        return None

    def setArg(self, arg, value):
        value = str(value)
        self.targetArgs = [(k, v) for k, v in self.targetArgs if k != arg]
        self.targetArgs.append((arg, value))

def resolvePosition(point, x, relX, y, relY, z, relZ):
    if relX:
        x = point[0] + x
    if relY:
        y = point[1] + y
    if relZ:
        z = point[2] + z

    return x, y, z

class PositionalCommand(object):
    x = y = z = 0
    relX = relY = relZ = False
    
    def resolvePosition(self, point):
        return resolvePosition(point, self.x, self.relX, self.y, self.relY, self.z, self.relZ)
        
class CloneCommand(object):
    name = "clone"
    maskMode = "replace"
    cloneMode = "normal"
    tileName = None

    def resolveS1(self, point):
        return resolvePosition(point, 
                               self.sx1, self.relSX1, 
                               self.sy1, self.relSY1, 
                               self.sz1, self.relSZ1)

    def resolveS2(self, point):
        return resolvePosition(point, 
                               self.sx2, self.relSX2, 
                               self.sy2, self.relSY2, 
                               self.sz2, self.relSZ2)

    def resolveDestination(self, point):
        return resolvePosition(point,
                               self.dx, self.relDX,
                               self.dy, self.relDY,
                               self.dz, self.relDZ)

    def resolveSourceBounds(self, point):
        sourceP1 = self.resolveS1(point)
        sourceP2 = self.resolveS2(point)
        return BoundingBox(sourceP1, (1, 1, 1)).union(BoundingBox(sourceP2, (1, 1, 1)))

    def __str__(self):
        args = formatCoordTuple(self.sx1, self.relSX1,
                                self.sy1, self.relSY1,
                                self.sz1, self.relSZ1)
        args += " "
        args += formatCoordTuple(self.sx2, self.relSX2,
                                 self.sy2, self.relSY2,
                                 self.sz2, self.relSZ2)
        args += " "
        args += formatCoordTuple(self.dx, self.relDX,
                                 self.dy, self.relDY,
                                 self.dz, self.relDZ)

        if self.maskMode != CloneCommand.maskMode:
            args += " " + self.maskMode
        if self.cloneMode != CloneCommand.cloneMode:
            args += " " + self.cloneMode
        if self.tileName:
            args += " " + self.tileName

        return "/%s %s" % (self.name, args)
    
    def __init__(self, args):
        sx1, sy1, sz1, sx2, sy2, sz2, dx, dy, dz, rest = argsplit(args, 10, required=9)

        self.sx1, self.relSX1 = parseCoord(sx1)
        self.sy1, self.relSY1 = parseCoord(sy1)
        self.sz1, self.relSZ1 = parseCoord(sz1)
        self.sx2, self.relSX2 = parseCoord(sx2)
        self.sy2, self.relSY2 = parseCoord(sy2)
        self.sz2, self.relSZ2 = parseCoord(sz2)
        self.dx, self.relDX = parseCoord(dx)
        self.dy, self.relDY = parseCoord(dy)
        self.dz, self.relDZ = parseCoord(dz)

        maskMode, rest = argsplit(args, 2)
        if maskMode in ("filtered", "masked", "replace"):
            self.maskMode = maskMode
            cloneMode, rest = argsplit(args, 2)
        else:
            cloneMode = maskMode

        if cloneMode in ("force", "move", "normal"):
            self.cloneMode = cloneMode
            tileName = rest
        else:
            tileName = cloneMode

        self.tileName = tileName

        if self.maskMode == "filtered":
            if not self.tileName:
                raise ParseError("Filtered clone command must have tileName as the last argument.")




class ExecuteCommand(PositionalCommand):
    name = "execute"
    subcommand = None
    targetSelector = None
    
    dx = dy = dz = None
    relDX = relDY = relDZ = False

    def __str__(self):
        args = str(self.targetSelector)
        args += " " + formatCoords(self)
        if None not in (self.dx, self.dy, self.dz):
            args += " " + formatDetectCoords(self)
            args += " " + self.blockID
            args += " " + self.blockData

        args += " " + str(self.subcommand)

        return "/%s %s" % (self.name, args)

    def __init__(self, args):
        selectorText, x, y, z, rest = argsplit(args, 5, required=4)
        self.targetSelector = TargetSelector(selectorText)
    
        # x, y, z are relative to the entity that is targeted.
        self.x, self.relX = parseCoord(x)
        self.y, self.relY = parseCoord(y)
        self.z, self.relZ = parseCoord(z)

        if rest.startswith("detect"):
            _detect, dx, dy, dz, blockID, blockData, rest = argsplit(rest, 7)
            
            # dx, dy, dz are relative to the x, y, z computed from the entity
            self.dx, self.relDX = parseCoord(dx)
            self.dy, self.relDY = parseCoord(dy)
            self.dz, self.relDZ = parseCoord(dz)

            self.blockID = blockID
            self.blockData = blockData

        commandText = rest

        self.subcommand = ParseCommand(commandText)
            

class SetBlockCommand(PositionalCommand):
    name = "setblock"
    dataValue = -1
    tileName = None
    oldBlockHandling = "replace"

    def __str__(self):
        args = formatCoords(self)
        args += " " + self.tileName
        if self.dataValue != -1:
            args += " " + str(self.dataValue)
        if self.oldBlockHandling != "replace":
            args += " " + str(self.dataValue)
        if self.dataTag:
            args += " " + self.dataTag

        return "/%s %s" % (self.name, args)

    def __init__(self, args):
        x, y, z, tileName, rest = argsplit(args, 5)

        self.x, self.relX = parseCoord(x)
        self.y, self.relY = parseCoord(y)
        self.z, self.relZ = parseCoord(z)
        self.tileName = tileName

        dataValue, rest = argsplit(rest, 2)
        try:
            dataValue = int(dataValue)
        except ValueError:
            oldBlockHandling = dataValue
            dataValue = -1
        else:
            oldBlockHandling, rest = argsplit(rest, 2)

        if oldBlockHandling not in ("destroy", "keep", "replace"):
            dataTag = oldBlockHandling + rest
            oldBlockHandling = "replace"
        else:
            dataTag = rest


        self.dataValue = dataValue
        self.oldBlockHandling = oldBlockHandling
        self.dataTag = dataTag


class TestForBlockCommand(PositionalCommand):
    name = "testforblock"
    dataTag = ""

    def __repr__(self):
        attrs = "x y z relX relY relZ tileName dataValue dataTag".split()
        return formatRepr(self, attrs)

    def __str__(self):
        args = formatCoords(self)
        args += " " + self.tileName
        if self.dataValue != -1:
            args += " " + str(self.dataValue)
        if self.dataTag:
            args += " " + self.dataTag

        return "/%s %s" % (self.name, args)

    def __init__(self, args):
        x, y, z, tileName, rest = argsplit(args, 5)
        self.x, self.relX = parseCoord(x)
        self.y, self.relY = parseCoord(y)
        self.z, self.relZ = parseCoord(z)
        self.tileName = tileName

        dataValue, dataTag = argsplit(args, 2)
        try:
            dataValue = int(dataValue)
        except ValueError:
            dataTag = dataValue
            dataValue = -1

        self.dataValue = dataValue
        self.dataTag = dataTag


class SummonCommand(PositionalCommand):
    name = "summon"
    entityName = NotImplemented

    def __repr__(self):
        attrs = "entityName x y z relX relY relZ dataTagText".split()
        return formatRepr(self, attrs)

    def __str__(self):
        args = self.entityName + " "
        args += formatCoords(self)

        args += " " + self.dataTagText
        return "/%s %s" % (self.name, args)

    def __init__(self, args):
        self.entityName, args = args.split(None, 1)
        try:
            dataTagStart = args.index("{")
        except ValueError:
            pos = args
            self.dataTagText = ""
        else:
            pos, self.dataTagText = args[:dataTagStart], args[dataTagStart:]

        x, y, z = pos.split(None, 2)
        if len(x):
            x, self.relX = parseCoord(x)
        else:
            x = None
        if len(y):
            y, self.relY = parseCoord(y)
        else:
            y = None
        if len(z):
            z, self.relZ = parseCoord(z)
        else:
            z = None

        self.x = x
        self.y = y
        self.z = z


_commandClasses = {}


def addCommandClass(cls):
    _commandClasses[cls.name] = cls

_cc = [SummonCommand, TestForBlockCommand, SetBlockCommand, ExecuteCommand, CloneCommand]

for cc in _cc:
    addCommandClass(cc)

del _cc


def main():
    testCommands = [
        r'/summon Zombie 2.5 63 -626.5 {Health:18,HealF:18,IsVillager:0,Attributes:[{Name:"generic.followRange",Base:6},{Name:"generic.movementSpeed",Base:0.2},{Name:"generic.knockbackResistance",Base:1.0}],Equipment:[{id:283},{},{},{},{id:332, Age:5980}],PersistenceRequired:1}',
        r'/setblock ~ ~3 ~ air',
        r'/execute @e[type=ArmorStand,x=-1562,y=13,z=-117,r=1] ~ ~59 ~ /clone ~-5 ~-7 ~-8 ~5 ~-7 ~8 ~-5 ~-32 ~-8',
        r'/clone ~-5 ~-4 ~-8 ~5 ~-4 ~8 ~-5 ~-54 ~-8'
    ]
    for cmdText in testCommands:
        testReencode(cmdText)
        testReencodeWithDataTag(cmdText)

def testReencode(cmdText):
    cmd = ParseCommand(cmdText)
    assert not isinstance(cmd, UnknownCommand), "Command \"%s...\" is an UnknownCommand" % cmdText[:20]
    newCmdText = str(cmd)
    #assert cmdText == newCmdText, "Expected: \n%s\nFound: \n%s" % (cmdText, newCmdText)

    newNewCmdText = str(ParseCommand(newCmdText))
    assert newCmdText == newNewCmdText, "Expected: \n%s\nFound: \n%s" % (newCmdText, newNewCmdText)

def testReencodeWithDataTag(cmdText):
    cmd = ParseCommand(cmdText)
    assert not isinstance(cmd, UnknownCommand)
    if not hasattr(cmd, 'dataTagText'):
        return

    from mceditlib.util import demjson
    dataTag = demjson.decode(cmd.dataTagText, sort_keys='preserve')
    encoded = demjson.encode(dataTag, encode_quoted_property_names=False, sort_keys='preserve')
    cmd.dataTagText = encoded
    newCmdText = str(cmd)
    assert str(ParseCommand(newCmdText)) == str(cmd)

if __name__ == '__main__':
    main()
"""
/summon Zombie ~3 ~ ~3 {"Attributes":[{"Base":6,"Name":"generic.followRange"},{"Base":0.2,"Name":"generic.movementSpeed"},{"Base":1.0,"Name":"generic.knockbackResistance"}],"Equipment":[{"id":283},{},{},{},{"Age":5980,"id":332}],"HealF":18,"Health":18,"IsVillager":0,"PersistenceRequired":1}
"""