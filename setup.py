#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name="didww-aptly-ctl",
    version="0.3",
    packages=find_packages(exclude=["tests"]),
    license="MIT",
    author="Kirill Shestakov",
    author_email="kirill.sh@didww.com",
    description="Some scripts to automate work with Aptly API with convenient defaults.",
    install_requires=["aptly-api-client", "PyYAML", "requests"],
    python_requires=">=3",
    entry_points={
        "console_scripts":
            ["didww-aptly-ctl = didww_aptly_ctl.application:main"]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
    ],

)
