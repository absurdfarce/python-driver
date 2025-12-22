# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys

from setuptools import setup, Extension

from cassandra import __version__

# ========================== General purpose vals to describe our current platform ==========================
is_windows = sys.platform.startswith('win32')
is_macos = sys.platform.startswith('darwin')
is_pypy = "PyPy" in sys.version
is_supported_platform = sys.platform != "cli" and not sys.platform.startswith("java")
is_supported_arch = sys.byteorder != "big"


platform_unsupported_msg = \
"""
===============================================================================
The optional C extensions are not supported on this platform.
===============================================================================
"""

arch_unsupported_msg = \
"""
===============================================================================
The optional C extensions are not supported on big-endian systems.
===============================================================================
"""

pypy_unsupported_msg = \
"""
=================================================================================
Some optional C extensions are not supported in PyPy. Only murmur3 will be built.
=================================================================================
"""

windows_compmile_error = \
"""
===============================================================================
WARNING: could not compile %s.

The C extensions are not required for the driver to run, but they add support
for token-aware routing with the Murmur3Partitioner.

On Windows, make sure Visual Studio or an SDK is installed, and your environment
is configured to build for the appropriate architecture (matching your Python runtime).
This is often a matter of using vcvarsall.bat from your install directory, or running
from a command prompt in the Visual Studio Tools Start Menu.
===============================================================================
"""

non_windows_compile_error = \
"""
===============================================================================
WARNING: could not compile %s.

The C extensions are not required for the driver to run, but they add support
for libev and token-aware routing with the Murmur3Partitioner.

Linux users should ensure that GCC and the Python headers are available.

On Ubuntu and Debian, this can be accomplished by running:

    $ sudo apt-get install build-essential python-dev

On RedHat and RedHat-based systems like CentOS and Fedora:

    $ sudo yum install gcc python-devel

On OSX, homebrew installations of Python should provide the necessary headers.

libev Support
-------------
For libev support, you will also need to install libev and its headers.

On Debian/Ubuntu:

    $ sudo apt-get install libev4 libev-dev

On RHEL/CentOS/Fedora:

    $ sudo yum install libev libev-devel

On OSX, via homebrew:

    $ brew install libev

===============================================================================
"""

# ========================== A few upfront checks ==========================
if is_pypy:
    sys.stderr.write(pypy_unsupported_msg)
if not is_supported_platform:
    sys.stderr.write(platform_unsupported_msg)
elif not is_supported_arch:
    sys.stderr.write(arch_unsupported_msg)

# ========================== Extensions ==========================
murmur3_ext = Extension('cassandra.cmurmur3',
                        sources=['cassandra/cmurmur3.c'])

def eval_env_var_as_array(varname):
    val = os.environ.get(varname)
    return None if not val else [v.strip() for v in val.split(',')]

DEFAULT_LIBEV_INCLUDES = ['/usr/include/libev', '/usr/local/include', '/opt/local/include', '/usr/include']
DEFAULT_LIBEV_LIBDIRS = ['/usr/local/lib', '/opt/local/lib', '/usr/lib64']
libev_includes = eval_env_var_as_array('CASS_DRIVER_LIBEV_INCLUDES') or DEFAULT_LIBEV_INCLUDES
libev_libdirs = eval_env_var_as_array('CASS_DRIVER_LIBEV_LIBS') or DEFAULT_LIBEV_LIBDIRS
if is_macos:
    libev_includes.extend(['/opt/homebrew/include', os.path.expanduser('~/homebrew/include')])
    libev_libdirs.extend(['/opt/homebrew/lib'])
libev_ext = Extension('cassandra.io.libevwrapper',
                      sources=['cassandra/io/libevwrapper.c'],
                      include_dirs=libev_includes,
                      libraries=['ev'],
                      library_dirs=libev_libdirs)

try_extensions = "--no-extensions" not in sys.argv and is_supported_platform and is_supported_arch and not os.environ.get('CASS_DRIVER_NO_EXTENSIONS')
try_murmur3 = try_extensions and "--no-murmur3" not in sys.argv
try_libev = try_extensions and "--no-libev" not in sys.argv and not is_pypy and not os.environ.get('CASS_DRIVER_NO_LIBEV')
try_cython = try_extensions and "--no-cython" not in sys.argv and not is_pypy and not os.environ.get('CASS_DRIVER_NO_CYTHON')

build_concurrency = int(os.environ.get('CASS_DRIVER_BUILD_CONCURRENCY', '0'))

def build_extension_list():

    rv = []

    if try_murmur3:
        sys.stderr.write("Appending murmur extension %s" % murmur3_ext)
        rv.append(murmur3_ext)

    if try_libev:
        sys.stderr.write("Appending libev extension %s" % libev_ext)
        rv.append(libev_ext)

    if try_cython:
        sys.stderr.write("Trying Cython builds in order to append Cython extensions")
        try:
            from Cython.Build import cythonize
            cython_candidates = ['cluster', 'concurrent', 'connection', 'cqltypes', 'metadata',
                                 'pool', 'protocol', 'query', 'util']
            compile_args = [] if is_windows else ['-Wno-unused-function']
            rv.extend(cythonize(
                    [Extension('cassandra.%s' % m, ['cassandra/%s.py' % m],
                                extra_compile_args=compile_args)
                        for m in cython_candidates],
                    nthreads=build_concurrency,
                    exclude_failures=True))

            rv.extend(cythonize(Extension("*", ["cassandra/*.pyx"], extra_compile_args=compile_args),
                                          nthreads=build_concurrency))
        except Exception:
            sys.stderr.write("Failed to cythonize one or more modules. These will not be compiled as extensions (optional).\n")
    
    return rv

# ========================== And finally setup() itself ==========================
setup(
    version = __version__,
    ext_modules = build_extension_list()
)