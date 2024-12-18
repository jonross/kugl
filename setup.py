from setuptools import setup, find_packages

setup(
    name="kugel",  # Replace with your package name
    version="0.1.2",
    description="Explore Kubernetes resources using SQLite",
    author="Jon",
    author_email="kugel.devel@gmail.com",
    url="https://github.com/jonross/kugel",
    packages=find_packages(),  # Automatically finds `your_package_name/`
    include_package_data=True,
    install_requires=[
        "arrow==1.2.0",
        "funcy==1.17",
        "jmespath==1.0.1",
        "pydantic==2.6.1",
        "pytest-cov==4.1.0",
        "pytest==7.1.3",
        "pyyaml==6.0.1",
        "tabulate==0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "kugel = kugel.main:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",  # Minimum Python version
)

