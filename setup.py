from setuptools import find_packages, setup

setup(
    name="web_data_collection",
    packages=find_packages(),
    install_requires=[
        "litellm",
        "crawl4ai",
        "sentence-transformers",
        "mistralai",
        "htmldate",
        "requests",
        "pandas",
        "pydantic",
    ],
    author="Thomas Berkane",
    description="Automated web data collection using LLMs",
)
