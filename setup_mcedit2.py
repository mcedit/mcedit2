"""
    setup-mcedit2
"""
from os import path

import sys
from setuptools import setup, find_packages
from Cython.Build import cythonize
import numpy

# Output annotated .html
import Cython.Compiler.Options
Cython.Compiler.Options.annotate = True


with file("version.txt") as f:
    version = f.read().strip()

install_requires = [
    "numpy",
]

include_dirs = [numpy.get_include()]

mcedit2_ext_modules = cythonize(
    [
        "src/mcedit2/rendering/blockmodels.pyx",
        "src/mcedit2/rendering/modelmesh.pyx",
    ],
    )

for m in mcedit2_ext_modules:
    m.include_dirs = include_dirs

sys.path.append(path.join(path.dirname(__file__), "src"))
from mcedit2.util.gen_ui import compile_ui
compile_ui()

setup(name='mcedit2',
      version=version,
      description="Interactive 3D World Editor for Minecraft Levels",
      # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
          "Development Status :: 2 - Pre-Alpha",
          "Environment :: Win32 (MS Windows)",
          "Environment :: X11 Applications :: Qt",
          "Environment :: MacOS X",
          "Intended Audience :: End Users/Desktop",
          "Natural Language :: English",
          "Operating System :: OS Independent",
          "Programming Language :: Python :: 2.7",
          "Topic :: Utilities",
          "License :: OSI Approved :: MIT License",
      ],
      keywords='minecraft',
      author='David Vierra',
      author_email='codewarrior0@gmail.com',
      url='https://github.com/mcedit/mcedit2',
      license='MIT License',
      packages=find_packages('src', include=["mcedit2*",]),
      package_dir={'': 'src'},
      ext_modules=mcedit2_ext_modules,
      include_dirs=include_dirs,
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      mcedit2=mcedit2.main:main
      """,
      )
