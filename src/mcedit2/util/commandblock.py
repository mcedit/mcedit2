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


class UnknownCommand(object):
    def __init__(self, name, args):
        self.name = name
        self.args = args


class SummonCommand(object):
    name = "summon"
    entityName = NotImplemented
    relX = relY = relZ = False
    x = y = z = 0

    def __repr__(self):
        attrs = "entityName x y z dataTagText".split()
        args = ", ".join("%s=%s" % (a, getattr(self, a)) for a in attrs)
        return "SummonCommand(%s)" % args
    
    def __str__(self):
        args = self.entityName + " "
        if self.x is not None:
            if self.relX:
                args += "~"
            args += str(self.x) + " "
        if self.y is not None:
            if self.relY:
                args += "~"
            args += str(self.y) + " "
        if self.z is not None:
            if self.relZ:
                args += "~"
            args += str(self.z) + " "

        args += self.dataTagText
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
            if x[0] == '~':
                self.relX = True
                x = x[1:]
            try:
                x = int(x)
            except ValueError:
                x = float(x)
        else:
            x = None
        if len(y):
            if y[0] == '~':
                self.relY = True
                y = y[1:]
            try:
                y = int(y)
            except ValueError:
                y = float(y)
        else:
            y = None
        if len(z):
            if z[0] == '~':
                self.relZ = True
                z = z[1:]
            try:
                z = int(z)
            except ValueError:
                z = float(z)
        else:
            z = None

        self.x = x
        self.y = y
        self.z = z


_commandClasses = {}


def addCommandClass(cls):
    _commandClasses[cls.name] = cls

_cc = [SummonCommand]

for cc in _cc:
    addCommandClass(cc)

del _cc

if __name__ == '__main__':
    cmdText = r'/summon Zombie 2.5 63 -626.5 {Health:18,HealF:18,IsVillager:0,Attributes:[{Name:"generic.followRange",Base:6},{Name:"generic.movementSpeed",Base:0.2},{Name:"generic.knockbackResistance",Base:1.0}],Equipment:[{id:283},{},{},{},{id:332, Age:5980}],PersistenceRequired:1}'
    print("Command: ")
    print(cmdText)
    cmd = ParseCommand(cmdText)
    print("Parsed: ", repr(cmd))
    from mceditlib.util import demjson
    dataTag = demjson.decode(cmd.dataTagText, sort_keys='preserve')
    from pprint import pprint
    print("DataTag: ")
    pprint(dataTag)
    print("Encoded: ")
    encoded = demjson.encode(dataTag, encode_quoted_property_names=False, sort_keys='preserve')
    print(encoded)
    print("Command: ")
    cmd.dataTagText = encoded
    newCmdText = str(cmd)
    print(newCmdText)
    assert str(ParseCommand(newCmdText)) == str(cmd)

"""
/summon Zombie ~3 ~ ~3 {"Attributes":[{"Base":6,"Name":"generic.followRange"},{"Base":0.2,"Name":"generic.movementSpeed"},{"Base":1.0,"Name":"generic.knockbackResistance"}],"Equipment":[{"id":283},{},{},{},{"Age":5980,"id":332}],"HealF":18,"Health":18,"IsVillager":0,"PersistenceRequired":1}
"""