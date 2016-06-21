"""
    rotation
"""
from __future__ import absolute_import, division, print_function, unicode_literals
import logging
from collections import defaultdict

import numpy

from mceditlib.blocktypes import parseBlockstate, joinBlockstate, PCBlockTypeSet

log = logging.getLogger(__name__)


def blankRotationTable():
    table = numpy.indices((32768, 16))

    # Roll array so table[x, y] returns [x, y]
    table = numpy.rollaxis(numpy.rollaxis(table, 1), 2, 1)
    return table


class BlockRotations(object):
    mappings = {
        'y': {
            'north': 'west',
            'west': 'south',
            'south': 'east',
            'east': 'north',
            'down_x': 'down_z',
            'down_z': 'down_x',
            'up_x': 'up_z',
            'up_z': 'up_x',
            
        },
        'x': {
            'up': 'south',
            'south': 'down',
            'down': 'north',
            'north': 'up',
        },
        'z': {
            'up': 'west',
            'west': 'down',
            'down': 'east',
            'east': 'up',
        }
    }

    axisMappings = {
        'y': {
            'x': 'z',
            'z': 'x',
        },
        'x': {
            'y': 'z',
            'z': 'y',
        },
        'z': {
            'x': 'y',
            'y': 'x',
        },

    }

    railShapes = {
        'ascending_north': 'ascending_west',
        'ascending_west': 'ascending_south',
        'ascending_south': 'ascending_east',
        'ascending_east': 'ascending_north',
        'east_west': 'north_south',
        'north_east': 'north_west',
        'north_west': 'south_west',
        'south_west': 'south_east',
        'south_east': 'north_east',

    }
    
    halfFacingMappings = {
        'y': {},
        'x': {
            ('top', 'south'): ('bottom', 'south'),
            ('bottom', 'south'): ('bottom', 'north'),
            ('bottom', 'north'): ('top', 'north'),
            ('top', 'north'): ('top', 'south'), 
        },
        'z': {
            ('top', 'west'): ('bottom', 'west'),
            ('bottom', 'west'): ('bottom', 'east'),
            ('bottom', 'east'): ('top', 'east'),
            ('top', 'east'): ('top', 'west'), 
        }
    }

    def __init__(self, blocktypes):
        self.blocktypes = blocktypes

        self.blocksByInternalName = defaultdict(list)

        for block in self.blocktypes:
            self.blocksByInternalName[block.internalName].append(block)

        self.rotateY90 = self.buildTable(axis='y')
        self.rotateX90 = self.buildTable(axis='x')
        self.rotateZ90 = self.buildTable(axis='z')
        self.rotateX180 = self.buildTable(axis='x', aboutFace=True)
        self.rotateZ180 = self.buildTable(axis='z', aboutFace=True)

    def buildTable(self, axis, aboutFace=False):
        mapping = self.mappings[axis]
        axisMapping = self.axisMappings[axis]
        halfFacingMap = self.halfFacingMappings[axis]
        
        if aboutFace:
            mapping90 = mapping
            mapping = {k: mapping90[v] for k, v in mapping90.iteritems()}
            if axis in 'xz':
                mapping['down_x'] = 'up_x'
                mapping['down_z'] = 'up_z'
                mapping['up_x'] = 'down_x'
                mapping['up_z'] = 'down_z'

            halfFacingMap90 = halfFacingMap
            halfFacingMap = {k: halfFacingMap90[v] for k, v in halfFacingMap90.iteritems()}

        table = blankRotationTable()

        rotIncrement = 8 if aboutFace else 4

        for block in self.blocktypes:
            oldState = state = block.stateDict
            if not len(state):
                continue
            
            # First pass: facing=north and similar
            newState = {}
            for k, v in state.items():
                n = mapping.get(v)
                if n:
                    newState[k] = n
                else:
                    newState[k] = v

            state = newState
            newState = dict(state)

            # Second pass: north=true and similar
            for k, v in mapping.items():
                if k in state:
                    if state[k] == 'true':
                        newState[k] = 'false'
                        newState[v] = 'true'

            state = newState

            if axis == 'y':
                # For signs and banners: rotation=10 and similar

                if 'rotation' in state:
                    rotation = (int(state['rotation']) + rotIncrement) % 16
                    state['rotation'] = unicode(rotation)

                # For rails, powered rails, etc: shape=north_east

                if 'shape' in state:
                    shape = state['shape']

                    newShape = self.railShapes.get(shape)
                    if newShape:
                        state['shape'] = newShape

            # For logs and such: axis=x and similar

            if not aboutFace and 'axis' in state:
                axis = state['axis']
                axis = axisMapping.get(axis, axis)
                state['axis'] = axis

            # For slabs: if x or z axis and 180-degree rotation, flip "half"

            if axis in 'xz' and aboutFace:
                if 'half' in state:
                    if state['half'] == 'bottom':
                        state['half'] = 'top'
                    elif state['half'] == 'top':
                        state['half'] = 'bottom'

            # For stairs, x or z axis: flip "half" upward or flip east/west to roll

            if 'half' in oldState and 'facing' in oldState:
                newHalfFacing = halfFacingMap.get((oldState['half'], oldState['facing']))
                if newHalfFacing:
                    state['half'], state['facing'] = newHalfFacing

            #print("Changed %s \nto %s" % (stateString, newStateString))

            newBlock = self.matchingState(block.internalName, state)
            if newBlock is block:
                pass
            # elif newBlock is None:
                # newStateString = joinBlockstate(state)
                # print("no mapping for %s%s" % (block.internalName, newStateString))
            elif newBlock is not None:
                # print("Changed %s \nto %s" % (block, newBlock))
                table[block.ID, block.meta] = [newBlock.ID, newBlock.meta]

        return table

    def matchingState(self, internalName, stateDict):
        """
        Find the first block with the given name whose state matches all of the keys
        and values in stateDict.

        Parameters
        ----------
        internalName : unicode
            block's internal name
        stateDict : dict
            the keys and values that the returned state must match

        Returns
        -------

        block: BlockType

        """
        for b in self.blocksByInternalName[internalName]:
            bsd = b.stateDict
            for k, v in stateDict.iteritems():
                if bsd.get(k) != v:
                    break
            else:
                return b

        return None


def xxxtest_yAxisTable():
    from . import PCBlockTypeSet
    blocktypes = PCBlockTypeSet()
    table = yAxisTable(blocktypes)

    assert (table != blankRotationTable()).any(), "Table is blank"

    changed = False
    changedNames = set()
    for i in range(32768):
        for j in range(16):
            e = table[i,j]
            if e[0] != i or e[1] != j:
                changed = True
                name = blocktypes[i, j].internalName
                if name not in changedNames:
                    # print("%s is changed" % name)
                    changedNames.add(name)

    assert changed, "Table is unchanged"

def main():
    from timeit import timeit
    blocktypes = PCBlockTypeSet()

    secs = timeit(lambda: BlockRotations(blocktypes), number=1)
    print("Time: %0.3f" % secs)

    assert secs < 0.1

if __name__ == '__main__':
    main()