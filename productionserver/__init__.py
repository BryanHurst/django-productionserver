import os


__version__ = '1.0.0'

__include_files__ = [
    (os.path.join(os.path.dirname(__file__), 'management', 'commands', 'nginx'), 'nginx'),
]