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

Alternately, you may pass a BlockType instance. A BlockType instance may be obtained
by presenting a block type input to the user (e.g. using an option with `type="blocktype"`
in a `SimpleCommandPlugin` or by constructing a `BlockTypeButton` yourself). BlockTypes
may also be found by looking up a textual or numeric ID in the dimension's `blocktypes`.
To wit::

    stone = dimension.blocktypes['minecraft:stone']
    granite = dimension.blocktypes['minecraft:stone[variant=granite]']
    cobblestone = dimension.blocktypes[1]  # don't do this!
    podzol = dimension.blocktypes[3, 2]    # don't do this either!

    dimension.setBlock(0, 0, 0, granite)   # etc.

To discover which block is at a given position, call `dimension.getBlock`, which will return
a `BlockType` instance.

.. automethod:: mceditlib.worldeditor.WorldEditorDimension.getBlock

To change the block at a given position, call `dimension.setBlock`

.. automethod:: mceditlib.worldeditor.WorldEditorDimension.setBlock

Array-based, high performance variants of these two methods are available. When given
parallel arrays of x, y, z coordinates, `dimension.getBlocks` will return an array of the
same size containing the block IDs at those coordinates. If requested, it will also return
the block metadata values, light values, and/or biome values for those coordinates at the
same time.

Likewise, `dimension.setBlocks` may be given parallel arrays of x, y, z coordinates along
with arrays of any of the following: block IDs, block metadata values, light values,
biome values. To set all coordinates to the same value, you may pass a single value
instead of an array.

.. automethod:: mceditlib.worldeditor.WorldEditorDimension.getBlocks
.. automethod:: mceditlib.worldeditor.WorldEditorDimension.setBlocks

Editing Entities
----------------

Entities are the free-roaming elements of a Minecraft world. They are not bound to the
block grid, they may be present at any position in the world, and may even overlap. Animals,
monsters, items, and experience orbs are examples of entities.

Since entities may be at any position, you cannot specify an entity with a single x, y, z
coordinate triple. Instead, you may create a BoundingBox (or any other SelectionBox object)
and ask MCEdit to find all of the entities within it. You may even ask it to find only
the entities which have specific attributes, such as `id="Pig"` to find only Pigs, or
`name="Notch"` to find entities named "Notch". This is all done by calling
`dimension.getEntities`

.. automethod:: mceditlib.worldeditor.WorldEditorDimension.getEntities

It is important to know that this function only returns an iterator over the found entities.
If you assign one of these entities to another variable (or put it into a container such
as a `list` or `dict`) then that entity will keep its containing chunk loaded, which may
possibly lead to out-of-memory errors. Thus, it is best to simply modify the entities
in-place while iterating through them rather than hold references to them.

The entities are returned as instances of `EntityRef`. An `EntityRef` is a wrapper around
the underlying NBT Compound Tag that contains the entity's data. The `EntityRef` allows you
to change the values of the entity's attributes without having to deal with the individual
tags and tag types that represent those attributes.

In other words, instead of writing::

    entity["Name"] = nbt.TAG_String("codewarrior0")

You only have to write::

    entity.Name = "codewarrior0"

However, it may occasionally be useful to access the entity's NBT tags directly. This can
be done using the `entity.raw_tag` attribute. After modifying the `raw_tag`, you must always
mark the entity as dirty by doing `entity.dirty = True` to ensure your changes are saved::

    import nbt
    tag = entity.raw_tag()
    tag["Name"] = nbt.TAG_String("codewarrior0")
    entity.dirty = True


Creating entities
-----------------

TODO: Describe creating entities, either by calling `dimension.worldEditor.EntityRef.create(entityID)` or
by crafting the entity's tag by hand.
