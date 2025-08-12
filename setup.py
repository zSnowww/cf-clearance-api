#!/usr/bin/env python3
"""Setup configuration for CF-Clearance-Scraper."""

from __future__ import annotations

from pathlib import Path
from setuptools import setup, find_packages

# Leer README
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

# Leer requirements
requirements_path = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_path.exists():
    with requirements_path.open(encoding="utf-8") as f:
        requirements = [
            line.strip() 
            for line in f 
            if line.strip() and not line.startswith("#")
        ]

setup(
    name="cf-clearance-scraper",
    version="1.0.0",
    description="Scraper para obtener cookies de clearance de Cloudflare",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="CF-Clearance-Scraper Team",
    python_requires=">=3.10",
    packages=find_packages(),
    install_requires=requirements,
    extras_require={
        "api": [
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0", 
            "pydantic>=2.5.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "mypy>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "cf-clearance-cli=cf_clearance_scraper.cli.main:run_cli",
            "cf-clearance-api=api_server:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="cloudflare scraping cookies clearance",
    project_urls={
        "Source": "https://github.com/Xewdy444/CF-Clearance-Scraper",
        "Bug Reports": "https://github.com/Xewdy444/CF-Clearance-Scraper/issues",
    },
) 