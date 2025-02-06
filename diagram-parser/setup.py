from setuptools import setup, find_packages

setup(
    name="questionnaire_parser",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "pydantic>=2.0.0",
        "networkx>=3.0",
        "matplotlib>=3.4.3",
    ],
    python_requires=">=3.9",
)
