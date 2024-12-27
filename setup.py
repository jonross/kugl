from setuptools import setup, find_packages

setup(
    name="kugel",  # Replace with your package name
    version="0.2.3",
    description="Explore Kubernetes resources using SQLite",
    author="Jon Ross",
    author_email="kugel.devel@gmail.com",
    url="https://github.com/jonross/kugel",
    packages=find_packages(),  # Automatically finds `your_package_name/`
    include_package_data=True,
    install_requires=[
        "arrow>=1.0.1,<=1.3.0",
        "funcy>=1.13,<=1.18",
        "jmespath>=0.9.5,<=1.0.1",
        "pydantic>=2.0.2,<=2.9.2",
        "pyyaml>=5.3,<=6.0.2",
        "tabulate>=0.8.7,<=0.9.0",
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

