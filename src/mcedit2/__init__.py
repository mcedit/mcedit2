import subprocess
import logging
import sys

log = logging.getLogger(__name__)


def get_git_version():
    """
    Get the version from git.
    """

    return subprocess.check_output('git describe --tags'.split()).strip()


def get_version():
    if not getattr(sys, 'frozen', False):
        try:
            return get_git_version()
        except Exception as e:
            log.info("Failed to get git version")
    try:
        from _version import __version__ as v
        return v
    except Exception as e:
        ret = "HOMEBAKED"
        log.info("Failed to get version from version file, using %s", ret)
        return ret

__version__ = get_version()
