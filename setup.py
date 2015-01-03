from setuptools import setup
from Cython.Build import cythonize

import numpy

version = '0.1'

install_requires = [
    # -*- Extra requirements: -*-
    "numpy",
]

ext_modules = cythonize("src/mceditlib/nbt.pyx")

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
      ext_modules=ext_modules,
      include_dirs=numpy.get_include(),
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      )

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
      packages=["mcedit2"],
      package_dir={'': 'src'},
      include_dirs=numpy.get_include(),
      include_package_data=True,
      zip_safe=False,
      install_requires=install_requires,
      entry_points="""
      # -*- Entry points: -*-
      [console_scripts]
      mcedit2=mcedit2.main:main
      """,
      )
