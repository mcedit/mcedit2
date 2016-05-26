"""
    simple_options
"""
from __future__ import absolute_import, division, print_function, unicode_literals

from PySide import QtGui

from mcedit2.plugins import registerPluginCommand, SimplePluginCommand
import logging

log = logging.getLogger(__name__)


@registerPluginCommand
class SimpleOptionsDemo(SimplePluginCommand):
    displayName = "Simple Options Demo"

    options = [
        {
            'type': 'int',
            'value': 50,
            'minimum': 0,
            'maximum': 100,
            'name': 'myIntOption',
            'text': 'Integer Option: ',
        },
        {
            'type': 'int',
            'value': 75,
            'name': 'myIntOption2',
            'text': 'Integer Option (No Min/Max): ',
        },
        {
            'type': 'float',
            'value': 1.5,
            'minimum': 0,
            'maximum': 100,
            'name': 'myFloatOption',
            'text': 'Float Option: ',
        },
        {
            'type': 'float',
            'value': 2.5,
            'name': 'myFloatOption2',
            'text': 'Float Option (No Min/Max): ',
        },
        {
            'type': 'bool',
            'name': 'myBoolOption',
            'text': 'Boolean Option: ',
        },
        {
            'type': 'text',
            'name': 'myTextOption',
            'text': 'Text Option (Placeholder): ',
            'placeholder': 'Placeholder Text',
        },
        {
            'type': 'text',
            'name': 'myTextOption2',
            'text': 'Text Option (Default Value): ',
            'value': 'Default Text Value',
        },
        {
            'type': 'choice',
            'name': 'myChoiceOption',
            'text': 'Choice Option: ',
            'choices': [
                ('Choice With Text Data', 'choice1'),
                ('Choice With Integer Data', 50),
                ('Choice With Float Data', 4.5),

            ]
        },
        {
            'type': 'blocktype',
            'name': 'myBlocktypeOption',
            'text': 'Blocktype Option: ',
            'value': 'minecraft:glass',
        }
    ]

    def perform(self, world, options):
        lines = []
        for key in [
            'myIntOption',
            'myIntOption2',
            'myFloatOption',
            'myFloatOption2',
            'myBoolOption',
            'myTextOption',
            'myTextOption2',
            'myChoiceOption',
            'myBlocktypeOption',
        ]:
            lines.append('%s: %s' % (key, options[key]))

        QtGui.QMessageBox.information(None, "Simple Options Demo Result",
                                      "Selected Options:\n\n" + '\n'.join(lines))
