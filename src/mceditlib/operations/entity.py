"""
    entity
"""
from __future__ import absolute_import, division, print_function
import logging
from mceditlib.operations import Operation

log = logging.getLogger(__name__)

class RemoveEntitiesOperation(Operation):
    def __init__(self, dimension, selection):
        super(RemoveEntitiesOperation, self).__init__(dimension, selection)

    def operateOnChunk(self, chunk):
        """

        :type chunk: WorldEditorChunk
        """
        ents = []
        for ref in chunk.Entities:
            if ref.Position in self.selection:
                ents.append(ref)

        chunk.removeEntities(ents)
