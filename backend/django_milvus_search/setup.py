from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="django-milvus-search",
    version="1.0.0",
    author="AI Catalogue Team",
    author_email="team@aicatalogue.com",
    description="A comprehensive, highly maintainable Milvus vector search integration for Django applications",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/django-milvus-search",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Django",
        "Framework :: Django :: 4.0",
        "Framework :: Django :: 4.1",
        "Framework :: Django :: 4.2",
        "Topic :: Database",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-django>=4.5.0",
            "coverage>=6.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=0.950",
        ],
        "cache": [
            "redis>=4.0.0",
            "django-redis>=5.0.0",
        ],
    },
    include_package_data=True,
    zip_safe=False,
    keywords="django milvus vector search similarity ai ml machine-learning",
    project_urls={
        "Bug Reports": "https://github.com/your-org/django-milvus-search/issues",
        "Source": "https://github.com/your-org/django-milvus-search",
        "Documentation": "https://django-milvus-search.readthedocs.io/",
    },
)
