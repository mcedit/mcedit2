Plugin basics
=============

Plugins that edit the world must make it possible for these edits to be undone. This is
done by enclosing your editing commands within a call to `editorSession.beginSimpleCommand`.
This creates a new entry in the undo history and tells the editorSession to begin recording
undo information. If this function is not called, the world will be in read-only mode and
editing will not be possible. For example::

    def changeOneBlock():
        with editorSession.beginSimpleCommand("Change One Block"):
            editorSession.currentDimension.setBlock(1, 2, 3, "minecraft:dirt")



