
class Operation(object):

    def __init__(self, dimension, selection):
        """
        A function that operates on every chunk within a selection. Can be composed with other operations.

        :param selection: Area to operate within
        :type selection: mceditlib.selection.SelectionBox
        :param dimension: World dimension to operate on
        :type dimension: mceditlib.worldeditor.WorldEditorDimension
        """
        self.dimension = dimension
        self.selection = selection
        self.chunksDone = 0

    chunkIterator = None

    def __iter__(self):
        return self

    def next(self):
        """
        Iterating an Operation will call the function. Each iteration will complete a single chunk
        :return:
        :rtype:
        """
        if self.chunkIterator is None:
            self.chunkIterator = self.dimension.getChunks(self.selection.chunkPositions())
        try:
            chunk = self.chunkIterator.next()
        except StopIteration:
            self.done()
            raise
        else:
            self.operateOnChunk(chunk)
            self.chunksDone += 1
            return self.chunksDone, self.selection.chunkCount

    def done(self):
        """
        Called after all chunks have been iterated.
        :return:
        :rtype:
        """
        pass

    def operateOnChunk(self, chunk):
        """
        Operate on a single chunk.

        :param chunk:
        :type chunk: WorldEditorChunk
        :return:
        :rtype:
        """
        raise NotImplementedError


class ComposeOperations(Operation):
    def __init__(self, left, right):
        """
        Compose two operations together. For each chunk, the left operation is called first, then the right.
        Can be composed further.

        :param left:
        :type left: Operation
        :param right:
        :type right: Operation
        :return:
        :rtype:
        """
        if left.selection != right.selection:
            raise ValueError("Operations must have the same selection")
        if left.dimension != right.dimension:
            raise ValueError("Operations must operate on the same world dimension")
        super(ComposeOperations, self).__init__(left.dimension, left.selection)
        self.left = left
        self.right = right

    def operateOnChunk(self, chunk):
        self.left.operateOnChunk(chunk)
        self.right.operateOnChunk(chunk)

    def done(self):
        self.left.done()
        self.right.done()
