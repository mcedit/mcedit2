WorldEditor
===========

A `WorldEditor` object is used to edit all parts of a Minecraft world. It contains a
:ref:`WorldEditorMetadata` object containing info about the world's name, seed, and other
data found in the `level.dat` file, and a collection of :ref:`WorldEditorDimension`s
 which provides access to the chunks, blocks, and entities in each dimension.

`WorldEditor` also provides a revisioning system used to implement MCEdit's undo history.
When editing a world opened in MCEdit, you should use the :ref:`session-undo-history`


.. method:: mceditlib.worldeditor.getDimension

.. _world-editor-dimension

WorldEditorDimension
====================

All blocks, chunks, and entities in a world are contained in a `WorldEditorDimension`.
A world may have one or more dimensions. One of these dimensions is always the
"overworld" or default dimension and may be obtained by calling `WorldEditor.getDimension()`
with no arguments.


