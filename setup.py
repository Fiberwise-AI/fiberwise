from setuptools import setup, find_packages

setup(
    name="fiberwise",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'click>=8.0.0',
        'watchdog>=3.0.0',
    ],
    entry_points={
        'console_scripts': [
            'fiber = fiberwise.main:cli',
        ],
    },
)
