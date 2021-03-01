#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys

from setuptools import find_packages, setup

SOURCE_DIR = "mx-file-util"

if sys.version_info < (3, 6):
    sys.stderr.write("ERROR:  requires at least Python Version 3.6\n")
    sys.exit(1)

if os.path.exists("README.md"):
    with open("README.md") as fh:
        readme = fh.read()
else:
    readme = ""

if os.path.exists("HISTORY.md"):
    with open("HISTORY.md") as fh:
        history = fh.read().replace(".. :changelog:", "")
else:
    history = ""


# Setup package using PIP
if __name__ == "__main__":
    setup(
        name="godaddy_dns_migrator",
        version="0.1.0",
        description="Migrate DNS settings from GoDaddy to GCP DNS Zone managed via Terraform",
        long_description=f"{readme}\n\n{history}",
        url="https://github.com/JohnMcSpedon/GoDaddy_DNS_migrator",
        author="John McSpedon",
        license="MIT",
        install_requires=["requests"],
        packages=find_packages(exclude=["tests*"]),
    )
