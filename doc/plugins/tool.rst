Tool Plugins
============

Tool Plugins allow the creation of new editor tools, which give the user new ways to
interact with the world by clicking and dragging in the world viewport. Each tool plugin
may provide an "options widget" which is shown in the tool options panel while the tool
is selected. A tool plugin may implement mouse event handlers, which will recieve
3D coordinates in world space cooresponding to the mouse position.

A tool plugin may also provide a 3D mouse cursor in the form of a SceneNode. Alternately,
a 2D mouse cursor may be implemented by calling QCursor functions in your implementations
of `toolActive` and `toolInactive`

Mouse Handlers
--------------

These mouse handlers are called in response to user actions. A simple tool may only
implement `mousePress` or `mouseRelease`, while a tool that also allows dragging or
changes its cursor according to world position may also implement `mouseDrag` or
`mouseMove`.

.. automethod:: mcedit2.editortools.EditorTool.mousePress
.. automethod:: mcedit2.editortools.EditorTool.mouseMove
.. automethod:: mcedit2.editortools.EditorTool.mouseDrag
.. automethod:: mcedit2.editortools.EditorTool.mouseRelease

