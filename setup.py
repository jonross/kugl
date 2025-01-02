from pathlib import Path
from setuptools import setup, find_packages

setup(
    name="kugl",  # Replace with your package name
    version="0.3.0",
    description="Explore Kubernetes resources using SQLite",
    author="Jon Ross",
    author_email="kugl.devel@gmail.com",
    url="https://github.com/jonross/kugl",
    packages=find_packages(),  # Automatically finds `your_package_name/`
    include_package_data=True,
    install_requires=(Path(__file__).parent / "reqs_public.txt").read_text().splitlines(),
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

