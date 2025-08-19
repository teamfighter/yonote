from setuptools import setup, find_packages

setup(
    name="yonote-cli",
    version="0.1.0",
    description="Self-contained CLI for Yonote (import/export)",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["InquirerPy", "tqdm"],
    entry_points={
        "console_scripts": [
            "yonote=yonote_cli.__main__:main",
        ]
    },
)
