# coding=utf-8
"""
    commandblock
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging

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
    text = ""
    if cmd.x is not None:
        if cmd.relX:
            text += "~"
        text += str(cmd.x) + " "
    if cmd.y is not None:
        if cmd.relY:
            text += "~"
        text += str(cmd.y) + " "
    if cmd.z is not None:
        if cmd.relZ:
            text += "~"
        text += str(cmd.z)
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


def argsplit(args, numargs):
    """
    Like str.split(), but always returns a list of length `numargs`
    """

    args = args.split(None, numargs-1)
    if len(args) < numargs:
        args = args + [""] * (numargs - len(args))
    return args


class SetBlockCommand(object):
    name = "setblock"
    relX = relY = relZ = False
    x = y = z = 0
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


class TestForBlockCommand(object):
    name = "testforblock"
    relX = relY = relZ = False
    x = y = z = 0
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
        x, y, z, tileName, rest = args.split(None, 4)
        self.x, self.relX = parseCoord(x)
        self.y, self.relY = parseCoord(y)
        self.z, self.relZ = parseCoord(z)
        self.tileName = tileName

        dataValue, dataTag = rest.split(None, 1)
        try:
            dataValue = int(dataValue)
        except ValueError:
            dataTag = dataValue
            dataValue = -1

        self.dataValue = dataValue
        self.dataTag = dataTag


class SummonCommand(object):
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

_cc = [SummonCommand, TestForBlockCommand, SetBlockCommand]

for cc in _cc:
    addCommandClass(cc)

del _cc


def main():
    testCommands = [
        r'/summon Zombie 2.5 63 -626.5 {Health:18,HealF:18,IsVillager:0,Attributes:[{Name:"generic.followRange",Base:6},{Name:"generic.movementSpeed",Base:0.2},{Name:"generic.knockbackResistance",Base:1.0}],Equipment:[{id:283},{},{},{},{id:332, Age:5980}],PersistenceRequired:1}',
        r'/setblock ~ ~3 ~ air',
    ]
    for cmdText in testCommands:
        testReencode(cmdText)
        testReencodeWithDataTag(cmdText)

def testReencode(cmdText):
    cmd = ParseCommand(cmdText)
    assert not isinstance(cmd, UnknownCommand)
    newCmdText = str(cmd)
    newNewCmdText = str(ParseCommand(newCmdText))
    assert newNewCmdText == newCmdText, "Expected: \n%s\nFound: \n%s" % (newCmdText, newNewCmdText)

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