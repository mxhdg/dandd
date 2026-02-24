#!/usr/bin/env python3
"""Setup script for statling.

This setup.py is maintained for backwards compatibility.
Configuration is primarily in pyproject.toml.
"""

from pathlib import Path

from setuptools import find_packages, setup

# Read the README for long description
readme_file = Path(__file__).parent / "README.md"
if readme_file.exists():
    with open(readme_file, encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = ""

# Read version from __init__.py
init_file = Path(__file__).parent / "statling" / "__init__.py"
version = "0.1.0"
if init_file.exists():
    with open(init_file, encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                version = line.split("=")[1].strip().strip('"').strip("'")
                break

setup(
    name="statling",
    version=version,
    description="D&D 5e character sheet renderer from YAML to Markdown",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Heather",
    author_email="heather@example.com",
    url="https://github.com/mxhdg/dandd",
    project_urls={
        "Homepage": "https://github.com/mxhdg/dandd",
        "Repository": "https://github.com/mxhdg/dandd",
        "Issues": "https://github.com/mxhdg/dandd/issues",
    },
    packages=find_packages(exclude=["tests", "tests.*"]),
    package_data={
        "statling": ["templates/*.j2", "py.typed"],
    },
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "PyYAML>=6.0.1",
        "Jinja2>=3.1.3",
    ],
    extras_require={
        "dev": [
            "ruff>=0.1.0",
            "black>=24.0.0",
            "flake8>=7.0.0",
            "isort>=5.13.0",
            "mypy>=1.8.0",
            "pytest>=8.0.0",
            "pytest-cov>=4.1.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "statling=statling.render:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Topic :: Games/Entertainment :: Role-Playing",
        "Topic :: Text Processing :: Markup",
        "Typing :: Typed",
    ],
    keywords=[
        "dnd",
        "d&d",
        "dungeons-and-dragons",
        "character",
        "sheet",
        "yaml",
        "jinja2",
        "markdown",
        "rpg",
        "tabletop",
    ],
    license="MIT",
    zip_safe=False,
)
