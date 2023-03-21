from setuptools import setup, find_packages

setup(
    name='picoamp_control',  # Replace with your desired library name
    version='0.1.0',
    description='A library for a picoamperemeter',
    author='Martin Unland | Raffaela Busse',  
    author_email='martin.e@unland.eu',  
    url='https://github.com/martinunland/picoamp_control',  
    packages=find_packages(),
    install_requires=[
        # List the packages required for your library here, e.g.
         'pyvisa',
         'numpy'
    ],
    python_requires='>=3.6',
)
