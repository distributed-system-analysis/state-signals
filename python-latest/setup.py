from setuptools import setup
from pathlib import Path

setup(name='python3-state_signals',
    version='1.0.0',
    description='Package for easy management of state/event signal publishing, subscribing, and responding',
    url='https://github.com/distributed-system-analysis/state-signals/',
    author='Mustafa Eyceoz',
    author_email='meyceoz@redhat.com',
    license='GPL3',
    py_modules=['state_signals'],
    zip_safe=False)