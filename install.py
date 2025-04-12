import subprocess
import sys
import os
import pkg_resources

BASE_PATH = os.path.dirname(os.path.realpath(__file__))
REQ_FILE = os.path.join(BASE_PATH, "requirements.txt")

def pip_install(*args):
    subprocess.run([sys.executable, "-m", "pip", "install", *args])

def is_package_installed(package):
    """Check if a package is already installed."""
    try:
        pkg_resources.require(package)
        return True
    except pkg_resources.DistributionNotFound:
        return False
    except pkg_resources.VersionConflict:
        return False

if os.path.exists(REQ_FILE):
    with open(REQ_FILE) as file:
        for package in file:
            package = package.strip()
            if package and not is_package_installed(package):
                pip_install(package)
