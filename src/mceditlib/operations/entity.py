"""
    entity
"""
from __future__ import absolute_import, division, print_function
import logging
from mceditlib.operations import Operation

log = logging.getLogger(__name__)

class RemoveEntitiesOperation(Operation):
    def __init__(self, dimension, selection, removeItems=True):
        super(RemoveEntitiesOperation, self).__init__(dimension, selection)
        self.removeItems = removeItems

    def operateOnChunk(self, chunk):
        """

        :type chunk: WorldEditorChunk
        """
        ents = []
        for ref in chunk.Entities:
            if not self.removeItems:
                if ref.id == 'Item' or ref.id == 'TConstruct.FancyItem':
                    continue
            if ref.Position in self.selection:
                ents.append(ref)

        chunk.removeEntities(ents)
