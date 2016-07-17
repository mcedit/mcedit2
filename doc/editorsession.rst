
EditorSession
=============

An EditorSession contains the entire state and behavior of the world editor for a single
 world. It contains references to the current selection, undo history, the UI widgets,
 and the WorldEditor instance underlying the session.

.. attribute:: currentDimension
    :type: WorldEditorDimension

    The dimension currently displayed in the editor window.

.. attribute:: currentSelection
    :type: SelectionBox | None

    The current selection made by the user with the Select tool. Unlike MCEdit 1.0,
    a selection is not always a rectangular box. Shaped and disjoint selections are
    possible now.

.. _session-undo-history:

Undo History
============

The session's undo history is managed as a stack of QUndoCommands. The revision system
provided by :ref:`worldeditor` is used to manage changes to the world's data. Simple
access to the revision system is provided by the `beginSimpleCommand` method of the
`EditorSession`

.. automethod:: mcedit2.editorsession.EditorSession.beginSimpleCommand

This method returns an object to be used in a `with` statement. Any changes to the
WorldEditor within the `with` statement's block are captured by a new revision in the
revision system, and a new entry is added to the session's undo history. For example::

    def changeOneBlock():
        with editorSession.beginSimpleCommand("Change One Block"):
            editorSession.currentDimension.setBlock(1, 2, 3, "minecraft:dirt")

