Types of plugins
================

:doc:`plugins/command` are the simplest kind of plugin and the most similar to MCEdit 1
"filter" plugins. A command plugin adds a new menu item to the "Plugins" menu which
calls the plugin's code when selected. Command plugins are free to edit the world and to
display windows, dialog boxes, and other UI elements.

:doc:`plugins/tool` are a way to add new editor tools. Each editor tool will display a
panel of options while it is selected, and will respond to mouse actions within the world
view such as clicking and dragging. Tool plugins are free to edit the world and to display
windows, dialog boxes, and other UI elements.

:doc:`plugins/brush_shape` are used to provide new shapes for use with the Brush and
Selection tool (and any other tools that may ask the user to choose a shape). Shape plugins
may not edit the world and may only return a SelectionBox object that defines the shape.


.. toctree::
   plugins/command
   plugins/tool
   plugins/brush_shape