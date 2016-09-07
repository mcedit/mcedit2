Plugin Tasks
============

A Minecraft world contains several different kinds of data. The blocks in the world
are fundamentally different from the monsters and animals that wander through it, and some
blocks contain data that is more complex than a single block ID. Blocks and entities are
organized into chunks, and there is additional data that applies to each entire chunk, and
there is also metadata that describes the world dimension that contains these chunks, and
that describes the save file as a whole. These tasks will guide you in editing each of
these different aspects of the save file.

World Dimensions
----------------

A Minecraft save file contains several world dimensions, which include the Overworld,
The Nether, The End, and any other dimensions added by game mods. MCEdit only allows the
user to view and edit one of the world's dimensions at any time, so plugins will often
be given a `dimension` object that refers to the world dimension that the user is
currently editing. All of the following tasks will refer to this `dimension` object.

Editing Blocks
--------------

Blocks are the defining element of a Minecraft dimension and are the simplest to deal with.
Blocks are stored in a three dimensional grid extending from the bottom of the world to the
build height - in other words, from `Y=0` to `Y=255`. Every position in the grid will have
a block. If a block appears to be empty, it will really contain the block `air`.

The position of a block is given by its X, Y, and Z coordinates. The type of the block
at that position is given by its identifier, which is a short string of text such as
`minecraft:air`, `minecraft:stone`, or `minecraft:stone[variant=diorite]`. Internally,
this identifier is stored as a pair of integers. When editing the world, you may use either
the string of text or the pair of integers to specify a block type, but it is recommended to
use the string of text, for both readability and for compatibility.

NOTE: When using block types added by mods, you *must* use the text identifier, because
the integer IDs will vary from world to world.

To change the block at a given position, call `dimension.setBlock`

.. automethod:: mceditlib.worldeditor.WorldEditorDimension.setBlock