"""A setuptools based setup module."""

# Always prefer setuptools over distutils
from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / "README.rst").read_text(encoding="utf-8")

setup(
    name="pyEfis",
    version="0.1.0",
    description="An Electronic Flight Information System written in Python.",
    long_description=long_description,
    long_description_content_type="text/rst",
    url="https://github.com/makerplane/pyEfis",
    author="MakerPlane Open Source Aviation",
    author_email="contact@makerplane.org",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: X11 Applications :: Qt",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="aviation, makerplane, efis",
    package_data={
        "pyefis": ["config/*","config/includes/*", "config/buttons/*"],
    },
    packages=find_packages(exclude=["tests.*", "tests"]),
    python_requires=">=3.7, <4",
    install_requires=[
        "geomag==0.9.2015",
        "PyYAML==6.0",
        "pyavtools==0.1.0",
        "PyQt5==5.15.9",
        "pycond==20230212"
    ],
    extras_require={
        "build": ["build==0.10.0"],
    },
    entry_points={
        "console_scripts": [
            "pyefis=pyefis.main:main",
        ],
    },
    project_urls={
        "Homepage": "https://makerplane.org/",
        "Source": "https://github.com/makerplane/pyEfis",
    },
)
