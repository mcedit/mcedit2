"""
    setup_mceditlib
"""

from setuptools import setup
from Cython.Build import cythonize

# Output annotated .html
import Cython.Compiler.Options
Cython.Compiler.Options.annotate = True

import numpy

with file("version.txt") as f:
    version = f.read().strip()

install_requires = [
    "numpy",
]

include_dirs = [numpy.get_include()]

mceditlib_ext_modules = cythonize([
    "src/mceditlib/nbt.pyx",
    "src/mceditlib/relight/with_cython.pyx"
])

for m in mceditlib_ext_modules:
    m.include_dirs = include_dirs

setup(name='mceditlib',
      version=version,
      description="Python library for editing Minecraft levels",
      # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: Console",
          "Intended Audience :: Developers",
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
      packages=["mceditlib"],
      package_dir={'': 'src'},
      ext_modules=mceditlib_ext_modules,
      include_dirs=include_dirs,
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      )
