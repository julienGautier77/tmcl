# -*- coding: utf-8 -*-
"""
JSON-backed config store exposing the same "group/key" API as QSettings,
so motor config files can use a .json file instead of a .ini file without
changing the code that reads/writes them (moteurTMCL.py, oneMotorTMCLGui.py,
scanMotor.py, ...).

@author: Gautier julien loa
"""

import json
import os


class JsonSettings():
    """
    Minimal QSettings-like wrapper backed by a JSON file.
    Keys use the same "group/param" convention as the .ini config files :
    conf.value('axe05/stepmotor'), conf.setValue('axe05/stepmotor', 1000).
    """

    def __init__(self, filename):
        self.filename = filename
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        else:
            self._data = {}

    def value(self, key, defaultValue=None):
        group, _, param = key.partition('/')
        return self._data.get(group, {}).get(param, defaultValue)

    def setValue(self, key, val):
        group, _, param = key.partition('/')
        self._data.setdefault(group, {})[param] = val

    def sync(self):
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self._data, f, indent=4, ensure_ascii=False, sort_keys=True)
            f.write('\n')

    def childGroups(self):
        return list(self._data.keys())


def openConfig(filename):
    """
    Return a QSettings-like config store for filename.
    .json files are read/written as plain JSON ; any other extension
    keeps using Qt's QSettings ini format (existing motor config files).
    """
    if str(filename).lower().endswith('.json'):
        return JsonSettings(filename)
    from PyQt6 import QtCore
    return QtCore.QSettings(filename, QtCore.QSettings.Format.IniFormat)
