# -*- coding: utf-8 -*-
# The following file is for fixing the build environment on Mac OS 10.10 Yosemite. It may work
# Steal PySide stuff from MacPorts install locations since HomeBrew dropped support for Yosemite!
# Before running this script, install the following ports using MacPorts: (sudo port install FOO)
# py27-pyside-tools
# py27-pyside
from __future__ import print_function

__author__ = 'ethan'

import collections
import os
import shutil
import subprocess

PathSub_T = collections.namedtuple('PathSub_T', ['old_root', 'new_root'])

VENV_DIR = os.path.abspath(os.getenv('VIRTUAL_ENV', None))
assert os.path.isdir(VENV_DIR)  # Ensure the virtual env is functional


def steal_port(port_name, path_subs):
    print("Stealing {}".format(port_name))
    port_contents = [p.strip() for p in subprocess.check_output(['port', '-q', 'contents', port_name]).splitlines()]
    for port_content_path in port_contents:
        for path_sub in path_subs:  # type: PathSub_T
            if port_content_path.startswith(path_sub.old_root):
                new_content_path = port_content_path.replace(path_sub.old_root, path_sub.new_root, 1)

                if os.path.exists(new_content_path):
                    print(" --> Skipping re-copying {} -> {}".format(port_content_path, new_content_path))
                else:
                    if not os.path.isdir(os.path.dirname(new_content_path)):
                        os.makedirs(os.path.dirname(new_content_path))
                    print(" --> Copying {} -> {}".format(port_content_path, new_content_path))
                    shutil.copy(port_content_path, new_content_path)
                break
        else:
            print(" --> No steal rule for {}".format(port_content_path))
    print(" --> Done stealing {}".format(port_name))


def main():
    steal_port('py27-pyside-tools',
               [PathSub_T('/opt/local/Library/Frameworks/Python.framework/Versions/2.7', VENV_DIR),
                PathSub_T('/opt/local/bin', os.path.join(VENV_DIR, 'bin'))]
               )

    steal_port('py27-pyside',
               [PathSub_T('/opt/local/Library/Frameworks/Python.framework/Versions/2.7', VENV_DIR),
                PathSub_T('/opt/local/include', os.path.join(VENV_DIR, 'include')),
                PathSub_T('/opt/local/lib/', os.path.join(VENV_DIR, 'lib')),
                PathSub_T('/opt/local/share', os.path.join(VENV_DIR, 'share'))
                ]
               )


if __name__ == '__main__':
    main()
