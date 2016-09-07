"""
    world_editing_demo
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from PySide import QtGui

from mcedit2.plugins import registerPluginCommand, SimpleCommandPlugin
import logging

log = logging.getLogger(__name__)


@registerPluginCommand
class WorldEditingDemo(SimpleCommandPlugin):
    displayName = "World Editing Demo"

    options = [
        {
            'type': 'blocktype',
            'name': 'replaceWith',
            'text': 'Replace all Stone blocks with this: ',
            'value': 'minecraft:glass',
        },
        
        {
            'type': 'float',
            'value': 10,
            'min': 0,
            'max': 200,
            'name': 'pigHealth',
            'text': 'Change the health of all Pigs to this: ',
        },
        {
            'type': 'text',
            'name': 'zombieName',
            'text': 'Change the name of all Zombies to this: ',
            'placeholder': 'Dinnerbone',
        },
    ]

    def perform(self, dimension, selection, options):
        stone = dimension.blocktypes['minecraft:stone']
        replaceWith = options['replaceWith']
        
        for x, y, z in selection.positions:
            if dimension.getBlock(x, y, z) == stone:
                dimension.setBlock(x, y, z, replaceWith)
                
        for entity in dimension.getEntities(selection, id='Pig'):
            entity.Health = options['pigHealth']
            
        for entity in dimension.getEntities(selection, id='Zombie'):
            entity.Name = options['zombieName']