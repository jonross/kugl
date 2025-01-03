from pathlib import Path
from setuptools import setup, find_packages
from textwrap import dedent

setup(
    name="kugl",
    version="0.3.2",
    description="Explore Kubernetes resources using SQLite",
    long_description=dedent("""
    PyPI readme goes here.
    
    For documentation please visit the [GitHub repository](https://github.com/jonross/kugl).
    """),
    long_description_content_type="text/markdown",
    author="Jon Ross",
    author_email="kugl.devel@gmail.com",
    url="https://github.com/jonross/kugl",
    packages=find_packages(),
    include_package_data=True,
    install_requires=(Path(__file__).parent / "reqs_public.txt").read_text().strip().splitlines(),
    entry_points={
        "console_scripts": [
            "kugl = kugl.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",  # Minimum Python version
)

