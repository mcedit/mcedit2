MCEdit 2 Plugin Development
===========================

A plugin for MCEdit 2 is a Python module that defines one or more Plugin classes
and then registers them with MCEdit. These classes are instantiated once for each
Editor Session and called on by MCEdit in response to various user actions.

Plugin Classes
==============

.. toctree::
    plugins/command
    plugins/brush_shape
    plugins/brush_mode
    plugins/tool
    plugins/inspector
    plugins/tile_entity
    plugins/generate