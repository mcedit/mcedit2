Types of plugins
================

:doc:`plugins/command` are the simplest kind of plugin and the most similar to MCEdit 1
"filter" plugins. A command plugin adds a new menu item to the "Plugins" menu which
calls the plugin's code when selected. Command plugins are free to edit the world and to
display windows, dialog boxes, and other UI elements.

:doc:`plugins/tool` are a way to add new editor tools. Each editor tool will display a
panel of options while it is selected, and will respond to mouse actions within the world
view such as clicking and dragging. Tool plugins are free to edit the world and to display
windows, dialog boxes, and other UI elements. Before creating a Tool plugin, consider if
what you want to accomplish can be done using a :doc:`plugins/brush_mode` instead.

:doc:`plugins/brush_shape` are used to provide new shapes for use with the Brush and
Selection tool (and any other tools that may ask the user to choose a shape). Shape plugins
may not edit the world and may only return a SelectionBox object that defines the shape.

:doc:`plugins/brush_mode` are used to provide new actions for use with the Brush tool.
For instance, you could make a Brush Mode that sets the name of any entity within the
affected area to "Dinnerbone". Brush modes are expected to edit the world, and since the
:ref:`undo-history` is managed by the Brush tool, you do not need to manage it yourself.

:doc:`plugins/inspector` are used to create user interfaces for editing entities and
tile entities. Since inspectors for all of the base Minecraft entities are included with
MCEdit, this plugin type is intended for adding support for Minecraft mods. For instance,
a plugin for inspecting chests from the IronChests mod would inherit from the base Chest
inspector and change the number of slots in the chest.

:doc:`plugins/tile_entity` are a low-level plugin that does not directly interact with the
user. These plugins provide TileEntityRef classes that wrap the underlying NBT structures
for tile entities and may add meaning to numerical constants, validate tag types, or
expose ItemStacks that are stored in a nonstandard manner. These plugins are expected to
accompany the Inspector plugins for mod-added tile entities.

The future of :doc:`plugins/generate` is uncertain.

.. toctree::
   plugins/command
   plugins/tool
   plugins/brush_shape