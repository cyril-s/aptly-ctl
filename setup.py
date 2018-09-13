#!/usr/bin/env python3

from setuptools import setup, find_packages
from aptly_ctl import __version__

setup(
    name="aptly-ctl",
    version=__version__,
    packages=find_packages(exclude=["tests"]),
    license="MIT",
    author="Kirill Shestakov",
    author_email="freyr.sh@gmail.com",
    description="Convenient command line Aptly API client",
    install_requires=["aptly-api-client", "PyYAML", "requests"],
    tests_require=["pytest"],
    python_requires=">=3",
    entry_points={
        "console_scripts":
            ["aptly-ctl = aptly_ctl.application:main"]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
    ],

)
