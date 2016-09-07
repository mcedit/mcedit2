Command Plugins
===============

A command plugin will add a new menu command to the application's Plugins menu, and
call a specified function when the menu command is selected. This is the simplest and
most straightforward type of plugin, and is the most similar to MCEdit 1.0's "filter"
plugins.

To define a command plugin, create a class that inherits from CommandPlugin. Implement
the `__init__` function to call `self.addMenuItem` for each user-selectable command, and
also implement the functions that correspond to each menu item.

A basic command plugin::

    from mcedit2.plugins import registerPluginCommand, CommandPlugin
    from PySide import QtGui

    @registerPluginCommand
    class ExampleCommand(CommandPlugin):
        def __init__(self, editorSession):
            super(ExampleCommand, self).__init__(editorSession)
            self.addMenuItem("Example Command", self.perform)

        def perform():
            dimension = self.editorSession.currentDimension
            chunkCount = dimension.chunkCount()

            QtGui.QMessageBox.information(None,         # messagebox parent (None for app-modal)
                "Example Command",                      # messagebox title
                "The Example Command was successful. "  # messagebox text
                "The current dimension contains "
                "%d chunks") % chunkCount)

You can do nearly anything you want in the `perform()` function. The currently edited
dimension can be accessed as `self.editorSession.currentDimension`. See
:doc:`plugin_tasks` for an overview of the dimension object. If you need to modify the
world, be sure to read :ref:`undo-history` first.

Simple Commands
===============

MCEdit 1.0's "filter" plugins all follow the same pattern: They prompt the user for some
inputs, and then call a `perform()` function which is given the current world, the current
selection, and the inputs provided by the user. `SimpleCommandPlugin` fills the same
role in MCEdit 2.0.

This class automatically adds a menu item to the Plugins menu. When the item is chosen,
it opens a dialog box with a list of options defined by the class; when the user presses
"OK", it calls a `perform()` function with those same arguments. The options to present
are defined by a Python data structure, making it possible to create a simple
UI for your plugin without having to learn any of Qt's UI widgets.

`SimpleCommandPlugin` also manages the undo history automatically. There is no need to
call `beginCommand()` here, and to do so is an error.

A minimal SimpleCommandPlugin::

    from mcedit2.plugins import registerPluginCommand, SimpleCommandPlugin

    @registerPluginCommand
    class SimpleOptionsDemo(SimpleCommandPlugin):
        displayName = "Simple Options Demo"

        options = [
            {
                'type': 'int',
                'value': 0,
                'min': 0,
                'max': 100,
                'name': 'myIntOption',
                'text': 'Integer Option: ',
            },
        ]

        def perform(self, dimension, selection, options):
            print("Option value: %d" % options['myIntOption'])
            print("Selection volume: %s" % selection.volume)
            print("Chunks in dimension: %d" % dimension.chunkCount())

This plugin will display a dialog with a single integer input, and print the value
from that input to the console along with info about the current selection and dimension.

Simple Command Inputs
---------------------

Each element in the plugin's `options` list is a `dict` that defines a single input. All
 option elements must have at least these keys:

- `type`: Defines which kind of input to create.
- `name`: The internal name for this input. You will use this to access the input's value,
          and MCEdit will use it to automatically save the last used value.
- `text`: The caption to display alongside this input. Should describe what the input does.
- `value`: An initial value to show in the input. Optional.

Further keys are available depending on the type of input.

Input Types
___________

- `type="int"`: A numeric input for integer values, within the range +/- two billion or so. If
         both the `min` and `max` keys are given, also creates a slider for selecting
         a value from within this range

  - `min`: Minimum allowed value. Optional.
  - `max`: Maximum allowed value. Optional.

- `type="float"`: Identical to the `int` input, but provides a floating point value (within the
           range allowed by double-precision floating point). If
           both the `min` and `max` keys are given, also creates a slider for selecting
           a value from within this range

  - `min`: Minimum allowed value. Optional.
  - `max`: Maximum allowed value. Optional.

- `type="bool"`: A checkbox that can be either on or off.

- `type="text"`: A text field that can input a single line of text.

  - `placeholder`: Displays this text in a light grey color if the text field is empty. Optional.

- `type="choice"`: A pop-up menu that offers multiple choices for the user to select from.
            Each choice is associated with a value that you define in the element's `choices`
            list. This is the value you will receive as this option's value in
            the `perform()` function.

  - `choices`: A list of tuples of the form `(text, value)`.

- `type="blocktype"`: A button that allows the user to select a Minecraft block type.
            The option's value will be a single BlockType instance that can be used with
            `dimension.setBlock`.

  - `value`: The block type that will initially be selected. This should be a block's
            internal name, such as `minecraft:grass`.

For examples of all possible simple command inputs, see the `simple_options.py` file in
the `plugins` folder included with MCEdit.