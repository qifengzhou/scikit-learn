#! /usr/bin/env python
#
# Copyright (C) 2007-2009 Cournapeau David <cournape@gmail.com>
#               2010 Fabian Pedregosa <fabian.pedregosa@inria.fr>
# License: 3-clause BSD

import sys
import os
import platform
import shutil
from distutils.command.clean import clean as Clean
from pkg_resources import parse_version
import traceback
try:
    import builtins
except ImportError:
    # Python 2 compat: just to be able to declare that Python >=3.5 is needed.
    import __builtin__ as builtins

# This is a bit (!) hackish: we are setting a global variable so that the
# main sklearn __init__ can detect if it is being loaded by the setup
# routine, to avoid attempting to load components that aren't built yet:
# the numpy distutils extensions that are used by scikit-learn to
# recursively build the compiled extensions in sub-packages is based on the
# Python import machinery.
builtins.__SKLEARN_SETUP__ = True


DISTNAME = 'scikit-learn'
DESCRIPTION = 'A set of python modules for machine learning and data mining'
with open('README.rst') as f:
    LONG_DESCRIPTION = f.read()
MAINTAINER = 'Andreas Mueller'
MAINTAINER_EMAIL = 'amueller@ais.uni-bonn.de'
URL = 'http://scikit-learn.org'
DOWNLOAD_URL = 'https://pypi.org/project/scikit-learn/#files'
LICENSE = 'new BSD'
PROJECT_URLS = {
    'Bug Tracker': 'https://github.com/scikit-learn/scikit-learn/issues',
    'Documentation': 'https://scikit-learn.org/stable/documentation.html',
    'Source Code': 'https://github.com/qifengzhou/scikit-learn'
}

# We can actually import a restricted version of sklearn that
# does not need the compiled code
import sklearn

VERSION = sklearn.__version__

if platform.python_implementation() == 'PyPy':
    SCIPY_MIN_VERSION = '1.1.0'
    NUMPY_MIN_VERSION = '1.14.0'
else:
    SCIPY_MIN_VERSION = '0.17.0'
    NUMPY_MIN_VERSION = '1.11.0'

JOBLIB_MIN_VERSION = '0.11'

# Optional setuptools features
# We need to import setuptools early, if we want setuptools features,
# as it monkey-patches the 'setup' function
# For some commands, use setuptools
SETUPTOOLS_COMMANDS = {
    'develop', 'release', 'bdist_egg', 'bdist_rpm',
    'bdist_wininst', 'install_egg_info', 'build_sphinx',
    'egg_info', 'easy_install', 'upload', 'bdist_wheel',
    '--single-version-externally-managed',
}
if SETUPTOOLS_COMMANDS.intersection(sys.argv):
    import setuptools

    extra_setuptools_args = dict(
        zip_safe=False,  # the package can run out of an .egg file
        include_package_data=True,
        extras_require={
            'alldeps': (
                'numpy >= {}'.format(NUMPY_MIN_VERSION),
                'scipy >= {}'.format(SCIPY_MIN_VERSION),
            ),
        },
    )
else:
    extra_setuptools_args = dict()


# Custom clean command to remove build artifacts

class CleanCommand(Clean):
    description = "Remove build artifacts from the source tree"

    def run(self):
        Clean.run(self)
        # Remove c files if we are not within a sdist package
        cwd = os.path.abspath(os.path.dirname(__file__))
        remove_c_files = not os.path.exists(os.path.join(cwd, 'PKG-INFO'))
        if remove_c_files:
            print('Will remove generated .c files')
        if os.path.exists('build'):
            shutil.rmtree('build')
        for dirpath, dirnames, filenames in os.walk('sklearn'):
            for filename in filenames:
                if any(filename.endswith(suffix) for suffix in
                       (".so", ".pyd", ".dll", ".pyc")):
                    os.unlink(os.path.join(dirpath, filename))
                    continue
                extension = os.path.splitext(filename)[1]
                if remove_c_files and extension in ['.c', '.cpp']:
                    pyx_file = str.replace(filename, extension, '.pyx')
                    if os.path.exists(os.path.join(dirpath, pyx_file)):
                        os.unlink(os.path.join(dirpath, filename))
            for dirname in dirnames:
                if dirname == '__pycache__':
                    shutil.rmtree(os.path.join(dirpath, dirname))


cmdclass = {'clean': CleanCommand}

# custom build_ext command to set OpenMP compile flags depending on os and
# compiler
# build_ext has to be imported after setuptools
try:
    from numpy.distutils.command.build_ext import build_ext  # noqa

    class build_ext_subclass(build_ext):
        def build_extensions(self):
            from sklearn._build_utils.openmp_helpers import get_openmp_flag

            if not os.getenv('SKLEARN_NO_OPENMP'):
                openmp_flag = get_openmp_flag(self.compiler)

                for e in self.extensions:
                    e.extra_compile_args += openmp_flag
                    e.extra_link_args += openmp_flag

            build_ext.build_extensions(self)

    cmdclass['build_ext'] = build_ext_subclass

except ImportError:
    # Numpy should not be a dependency just to be able to introspect
    # that python 3.5 is required.
    pass


# Optional wheelhouse-uploader features
# To automate release of binary packages for scikit-learn we need a tool
# to download the packages generated by travis and appveyor workers (with
# version number matching the current release) and upload them all at once
# to PyPI at release time.
# The URL of the artifact repositories are configured in the setup.cfg file.

WHEELHOUSE_UPLOADER_COMMANDS = {'fetch_artifacts', 'upload_all'}
if WHEELHOUSE_UPLOADER_COMMANDS.intersection(sys.argv):
    import wheelhouse_uploader.cmd

    cmdclass.update(vars(wheelhouse_uploader.cmd))


def configuration(parent_package='', top_path=None):
    if os.path.exists('MANIFEST'):
        os.remove('MANIFEST')

    from numpy.distutils.misc_util import Configuration

    config = Configuration(None, parent_package, top_path)

    # Avoid non-useful msg:
    # "Ignoring attempt to set 'name' (from ... "
    config.set_options(ignore_setup_xxx_py=True,
                       assume_default_configuration=True,
                       delegate_options_to_subpackages=True,
                       quiet=True)

    config.add_subpackage('sklearn')

    return config


def get_numpy_status():
    """
    Returns a dictionary containing a boolean specifying whether NumPy
    is up-to-date, along with the version string (empty string if
    not installed).
    """
    numpy_status = {}
    try:
        import numpy
        numpy_version = numpy.__version__
        numpy_status['up_to_date'] = parse_version(
            numpy_version) >= parse_version(NUMPY_MIN_VERSION)
        numpy_status['version'] = numpy_version
    except ImportError:
        traceback.print_exc()
        numpy_status['up_to_date'] = False
        numpy_status['version'] = ""
    return numpy_status


def setup_package():
    metadata = dict(name=DISTNAME,
                    maintainer=MAINTAINER,
                    maintainer_email=MAINTAINER_EMAIL,
                    description=DESCRIPTION,
                    license=LICENSE,
                    url=URL,
                    download_url=DOWNLOAD_URL,
                    project_urls=PROJECT_URLS,
                    version=VERSION,
                    long_description=LONG_DESCRIPTION,
                    classifiers=['Intended Audience :: Science/Research',
                                 'Intended Audience :: Developers',
                                 'License :: OSI Approved',
                                 'Programming Language :: C',
                                 'Programming Language :: Python',
                                 'Topic :: Software Development',
                                 'Topic :: Scientific/Engineering',
                                 'Operating System :: Microsoft :: Windows',
                                 'Operating System :: POSIX',
                                 'Operating System :: Unix',
                                 'Operating System :: MacOS',
                                 'Programming Language :: Python :: 3',
                                 'Programming Language :: Python :: 3.5',
                                 'Programming Language :: Python :: 3.6',
                                 'Programming Language :: Python :: 3.7',
                                 ('Programming Language :: Python :: '
                                  'Implementation :: CPython'),
                                 ('Programming Language :: Python :: '
                                  'Implementation :: PyPy')
                                 ],
                    cmdclass=cmdclass,
                    python_requires=">=3.5",
                    install_requires=[
                        'numpy>={}'.format(NUMPY_MIN_VERSION),
                        'scipy>={}'.format(SCIPY_MIN_VERSION),
                        'joblib>={}'.format(JOBLIB_MIN_VERSION)
                    ],
                    **extra_setuptools_args)

    if len(sys.argv) == 1 or (
            len(sys.argv) >= 2 and ('--help' in sys.argv[1:] or
                                    sys.argv[1] in ('--help-commands',
                                                    'egg_info',
                                                    '--version',
                                                    'clean'))):
        # For these actions, NumPy is not required
        #
        # They are required to succeed without Numpy for example when
        # pip is used to install Scikit-learn when Numpy is not yet present in
        # the system.
        try:
            from setuptools import setup
        except ImportError:
            from distutils.core import setup

        metadata['version'] = VERSION
    else:
        if sys.version_info < (3, 5):
            raise RuntimeError(
                "Scikit-learn requires Python 3.5 or later. The current"
                " Python version is %s installed in %s."
                % (platform.python_version(), sys.executable))

        numpy_status = get_numpy_status()
        numpy_req_str = "scikit-learn requires NumPy >= {}.\n".format(
            NUMPY_MIN_VERSION)

        instructions = ("Installation instructions are available on the "
                        "scikit-learn website: "
                        "http://scikit-learn.org/stable/install.html\n")

        if numpy_status['up_to_date'] is False:
            if numpy_status['version']:
                raise ImportError("Your installation of Numerical Python "
                                  "(NumPy) {} is out-of-date.\n{}{}"
                                  .format(numpy_status['version'],
                                          numpy_req_str, instructions))
            else:
                raise ImportError("Numerical Python (NumPy) is not "
                                  "installed.\n{}{}"
                                  .format(numpy_req_str, instructions))

        from numpy.distutils.core import setup

        metadata['configuration'] = configuration

    setup(**metadata)


if __name__ == "__main__":
    setup_package()
