The following files were obtained from the snapcraft example located here:
https://github.com/snapcraft-docs/python-ctypes-example

Files:
snap/local/patch-ctypes.sh
snap/local/patches/ctypes_init.diff

Theses are needed for python snaps to properly work on systems different than the
one they were built on.
For example, building on Ubuntu 23.10 and running the snap on 22.04

Without this the snap will only work on the system it was built on.
