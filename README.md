# MCEdit 2.0

MCEdit 2.0 is the next version of MCEdit, the World Editor for Minecraft. MCEdit allows you to edit every aspect of
a Minecraft world, and to import and export .schematic files created by many programs including WorldEdit and the
original MCEdit 1.x. It is free to use and licensed under the BSD license.

MCEdit 2.0's development is still in a pre-alpha stage and is not usable. To download MCEdit 2.0 anyway, head over to 
http://www.mcedit.net/

The rest of this file is of interest to programmers only.

# Getting Started

This guide is written with Windows developers in mind. Linux / OS X developers can read how to install below. 
Windows developers are assumed to be using a unix shell such as the _GIT Bash_ included with the Windows distribution 
of Git.

- Install [Python for Windows v2.7.9](http://www.python.org/downloads/). Edit your PATH environment variable (or your 
.bashrc) to have both the `python27` and `python27\scripts` folders. (by default, `c:\python27;c:\python27\scripts;`)
- Install [Microsoft Visual C++ Compiler for Python 2.7](http://www.microsoft.com/en-us/download/details.aspx?id=44266). 
This is not needed if you already have MSVC 2008 (Visual Studio 9.0) or the Windows SDK 7.0 
installed, but you probably don't so install it anyway.
- Install virtualenv: `pip install virtualenv` (pip is now included with recent versions of Python)
- Open a bash shell and `cd` to the folder containing the MCEdit sources.
- Create a virtualenv using `virtualenv ENV`
- Activate the virtualenv using `. ENV/scripts/activate`

Now, install the required libraries. 

On Windows, `easy_install` is able to install binary installer packages into a virtualenv. Download each of the following and run `easy_install <module>.exe` while the virtualenv is active. Binary packages for the following are available at Chris Gohlke's page. Download the versions for Python 2.7, and make sure to download the `win32` versions if you installed the 32-bit Python (the default) or the `win-amd64` versions for 64-bit Python.

- [pyside](http://www.lfd.uci.edu/~gohlke/pythonlibs#pyside) 
- [pyopengl](http://www.lfd.uci.edu/~gohlke/pythonlibs#pyopengl) (be sure to grab `PyOpenGL-accelerate` too.)
- [pywin32](http://www.lfd.uci.edu/~gohlke/pythonlibs#pywin32) (for registry access)
- [cython](http://www.lfd.uci.edu/~gohlke/pythonlibs#cython) (for building `nbt.pyd`)
- [ipython](http://www.lfd.uci.edu/~gohlke/pythonlibs#ipython) (for debugging)
- [pygments](http://www.lfd.uci.edu/~gohlke/pythonlibs#pygments) (required by IPython) 
- [pyzmq](http://www.lfd.uci.edu/~gohlke/pythonlibs#pyzmq) (required by IPython)
- [numpy](http://www.lfd.uci.edu/~gohlke/pythonlibs#numpy) **

Also use _pip_ to install this library:

- `pip install arrow` - a date/time class with nice text formatting.

**Note that Gohlke's numpy builds use the Intel Math Kernel Library (MKL) which requires a license to use. If you 
have not purchased an MKL license (it's expensive) then you ***DO NOT HAVE PERMISSION TO DISTRIBUTE APPS*** built 
with it. I didn't notice any better performance with MKL regardless.

An alternative is to install the official builds of numpy from the [SourceForge Downloads](http://sourceforge.net/projects/numpy/files/NumPy/)
but 64-bit builds are not provided. If you need a 64-bit build of numpy that does not include MKL, you will need to 
build it yourself. Also, the official builds are packed into a "superpack" installer which easy_install chokes on. 
Just open the installer in an archiving program like [7-zip](http://www.7-zip.org/) and extract the SSE3 installer, 
then `easy_install` it.

Another alternative to downloading all of the above is to download all the packages 
[from my dropbox folder](https://www.dropbox.com/sh/fw8u5f050r1m6lp/AABAYXOEAzmV_nfH0Qj9hUOwa?dl=0). Note that the 
64-bit numpy package is one I built myself, with several facilities (LAPACK, BLAS etc) disabled because I couldn't 
be bothered to find out why MSVC 64-bit chokes on them. MCEdit seems to run fine without them. Install 
`python-2.7.9.msi` first, then install [MSVC++ for Python](http://www.microsoft.com/en-us/download/details.aspx?id=44266), 
then virtualenv, and create and activate a virtualenv as above. Install each of the .exe files using `easy_install` 
and make sure to `pip install arrow` too.

Once all of the requirements are met, install MCEdit itself into the virtualenv. This will build `nbt.pyd`, ensure 
both `mcedit2` and `mceditlib` are on the pythonpath, and also create an `mcedit2` script making it easy to launch 
the app. 

`python setup.py develop`

All that's left is to see if the app launches.

`mcedit2`

As a bonus, you can use the `-debug` flag to enable the Debug menu and a few extra widgets.

`mcedit2 -debug`

## Linux/OS X (not tested fully)

Make sure to delete pywin32 from the requirements list because that is a windows only library. 


    cd (Your mcedit2 location)
    virtualenv ENV
    . ENV/bin/activate
    pip install -r requirements.txt
    python setup.py develop
    mcedit2

If you get a `Library not loaded: libpyside-python2.7.1.2.dylib` error, try running `pyside_postinstall.py -install` to fix this. 

If after that, you get a `Library not loaded: /usr/local/lib/QtGui.framework/Versions/4/QtGui` error after that, try installing `qt` using a package manager like Homebrew or apt-get. 

Example: `brew install qt`

_Note: This information is not fully tested and might not work for you_

# Troubleshooting

- `python setup.py develop` or `build` produces the error `cannot find vcvarsall.bat` or similar.
Old version of setuptools don't know about MSVC++ for Python 2.7. Run `pip install --upgrade setuptools` to upgrade.

- When running mcedit2, `ImportError: cannot import name nbt` is produced.
The extension module `nbt.pyd` failed to build. Run `python setup.py develop` to rebuild it and look for any errors.
 The most likely error is the `vcvarsall.bat` error above.
 
- When running mcedit2, `ImportError: %1 is not a valid Win32 application` is produced.
This happens when switching between 32-bit and 64-bit Pythons on Windows. The `nbt.pyx` must be rebuilt after 
switching, so run `python setup.py develop` again.
