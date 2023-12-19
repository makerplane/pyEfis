#!/bin/sh

set -e
set -x

CTYPES_INIT=`python3 -c 'import ctypes; print(ctypes.__file__)'`
CTYPES_INIT_ORIG=${CTYPES_INIT}.orig
SITE_PY=`python3 -c 'import site; print(site.__file__)'`

# Restore patched files
[ -f "patched/ctypes/__init__.py.orig" ] && mv "patched/ctypes/__init__.py.orig" "${CTYPES_INIT}"

# Apply patches
echo "Patching ctypes..."
patch -s -b "${CTYPES_INIT}" "${SNAPCRAFT_PROJECT_DIR}/snap/local/patches/ctypes_init.diff"

# Save patches to allow rebuilding
mkdir -p patched/ctypes
[ -f "${CTYPES_INIT_ORIG}" ] && mv "${CTYPES_INIT_ORIG}" patched/ctypes

sed -i "${SITE_PY}" -e 's/^ENABLE_USER_SITE = None$/ENABLE_USER_SITE = False/'

