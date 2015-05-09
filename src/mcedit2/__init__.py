import subprocess
import logging

log = logging.getLogger(__name__)

__version__ = "HOMEBAKED"

def get_git_version():
    """
    Get the version from git.
    """

    return subprocess.check_output('git describe --tags'.split()).strip()


try:
    __version__ = get_git_version()
except Exception as e:
    log.info("Failed to get git version")
    try:
        from _version import __version__
    except Exception as e:
        log.info("Failed to get version from version file, using %s", __version__)
