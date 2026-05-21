from setuptools import setup, find_packages

setup(
    name="xdl-download-manager",
    version="2.0.0",
    description="Open-source Internet Download Manager (IDM) alternative",
    author="BF667",
    license="Unlicense",
    packages=find_packages(),
    install_requires=[
        "PyQt5>=5.15",
        "yt-dlp>=2023.0",
        "requests>=2.28",
        "beautifulsoup4>=4.11",
        "tqdm>=4.64",
        "pyperclip>=1.8",
    ],
    entry_points={
        "console_scripts": [
            "xdl=main:main",
        ],
    },
    python_requires=">=3.8",
)
