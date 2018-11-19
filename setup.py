#!/usr/bin/env python3

from setuptools import setup, find_packages
from aptly_ctl import __version__
from os import path

this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="aptly-ctl",
    version=__version__,
    packages=find_packages(exclude=["tests"]),
    license="MIT",
    author="Kirill Shestakov",
    author_email="freyr.sh@gmail.com",
    description="Convenient command line Aptly API client",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cyril-s/aptly-ctl",
    install_requires=["aptly-api-client", "PyYAML", "requests", "fnvhash"],
    python_requires=">=3",
    entry_points={
        "console_scripts":
            ["aptly-ctl = aptly_ctl.application:main"]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3 :: Only",
        "Environment :: Console",
        "License :: OSI Approved :: MIT License",
    ]
)
