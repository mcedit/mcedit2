Plugin basics
=============

Plugin Structure
----------------

A plugin is defined to be a Python module. A module can take several forms. The simplest
is a single python file, such as `my_plugin.py` that contains plugin class definitions.

For larger plugins, or plugins that include other support files, you may choose to create
a Python package, which is a folder that contains (at the very least) an `__init__.py`
file. For example::

    my_plugin/
        __init__.py
        helpers.py
        header_image.png
        footer_image.png

TBD: In the future, it will be possible to package your plugin as a zip file for easy
installation.

.. _undo-history

Undo History
------------

NOTE: The following mainly applies to the full-featured `CommandPlugin`. Plugins derived from
`SimpleCommandPlugin` or `BrushMode` will automatically manage the undo history for you.

Plugins that edit the world must make it possible for these edits to be undone. This is
done by enclosing your editing commands within a call to `editorSession.beginSimpleCommand`.
This creates a new entry in the undo history and tells the editorSession to begin recording
undo information. If this function is not called, the world will be in read-only mode and
editing will not be possible. For example::

    def changeOneBlock():
        with editorSession.beginSimpleCommand("Change One Block"):
            editorSession.currentDimension.setBlock(1, 2, 3, "minecraft:dirt")



Registering Plugin Classes
--------------------------

When defining a plugin class, you must also call a function to register it with MCEdit's
plugin handling system. This is usually as simple as placing a decorator such as
`@registerCommandPlugin` before the class definition. See the examples for each of the
:doc:`plugin_types`.