# -*- coding: utf-8 -*-
"""
Petit outil pour gérer les racks TMCL (racksTMCL.json) et configurer un axe
dans configMoteurTMCL.json : on choisit un rack (adresse IP ou port série
définie une seule fois par rack), le numéro d'axe (0-5, 6 axes possibles par
rack), le type (bibliothèque motorPresetsTMCL.json) et un nom d'affichage.
La clé JSON du moteur est générée automatiquement ("<rack>_axe<N>") ;
l'entrée est créée (ou écrasée si cet axe est déjà configuré).

@author: Gautier julien loa
"""

import sys
import os
import pathlib
import time

from PyQt6.QtWidgets import (
    QApplication, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QSpinBox, QComboBox, QPushButton, QMessageBox,
)

import qdarkstyle
import jsonSettings

try:
    import serial.tools.list_ports
    HAS_SERIAL_TOOLS = True
except Exception:
    HAS_SERIAL_TOOLS = False


class ADDRACKDIALOG(QDialog):
    """Petite fenêtre pour définir un nouveau rack (nom + adresse)"""

    def __init__(self, racks, parent=None):
        super(ADDRACKDIALOG, self).__init__(parent)
        self.racks = racks
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        self.setWindowTitle("Nouveau rack")
        self.setMinimumWidth(380)

        mainLayout = QVBoxLayout()
        formLayout = QFormLayout()

        self.nameEdit = QLineEdit()
        self.nameEdit.setPlaceholderText("ex: rack2")
        formLayout.addRow("Nom du rack :", self.nameEdit)

        addressLayout = QHBoxLayout()
        self.addressCombo = QComboBox()
        self.addressCombo.setEditable(True)
        self.addressCombo.setPlaceholderText("/dev/ttyACM0 ou socket://IP:4000")
        self.refreshButton = QPushButton("🔄")
        self.refreshButton.setMaximumWidth(40)
        self.refreshButton.clicked.connect(self.refreshPorts)
        addressLayout.addWidget(self.addressCombo)
        addressLayout.addWidget(self.refreshButton)
        formLayout.addRow("Adresse :", addressLayout)

        self.descEdit = QLineEdit()
        self.descEdit.setPlaceholderText("ex: Raspberry Pi tmcl-rack2 (optionnel)")
        formLayout.addRow("Description :", self.descEdit)

        mainLayout.addLayout(formLayout)

        buttonLayout = QHBoxLayout()
        self.cancelButton = QPushButton("❌ Annuler")
        self.cancelButton.clicked.connect(self.reject)
        self.okButton = QPushButton("✅ Créer")
        self.okButton.clicked.connect(self.createRack)
        buttonLayout.addWidget(self.cancelButton)
        buttonLayout.addWidget(self.okButton)
        mainLayout.addLayout(buttonLayout)

        self.setLayout(mainLayout)
        self.refreshPorts()

    def refreshPorts(self):
        current = self.addressCombo.currentText()
        self.addressCombo.clear()
        ports = []
        if HAS_SERIAL_TOOLS:
            try:
                ports = [pi.device for pi in serial.tools.list_ports.comports()]
            except Exception:
                ports = []
        self.addressCombo.addItems(ports)
        if current:
            self.addressCombo.setCurrentText(current)

    def createRack(self):
        name = self.nameEdit.text().strip()
        address = self.addressCombo.currentText().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir un nom pour ce rack.")
            return
        if not address:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir une adresse (port ou socket://IP:port).")
            return
        if name in self.racks.childGroups():
            QMessageBox.warning(self, "Erreur", f"Un rack nommé '{name}' existe déjà.")
            return
        self.racks.setValue(name+"/address", address)
        self.racks.setValue(name+"/description", self.descEdit.text().strip())
        self.racks.sync()
        self.newRackName = name
        self.accept()


class ADDMOTORWIDGET(QWidget):

    def __init__(self, parent=None):
        super(ADDMOTORWIDGET, self).__init__(parent)
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        self.setWindowTitle("Ajouter un moteur TMCL")
        self.setMinimumWidth(420)

        p = pathlib.Path(__file__)
        self.configPath = str(p.parent / "fichiersConfig") + os.sep
        self.confMotors = jsonSettings.openConfig(self.configPath+'configMoteurTMCL.json')
        self.presets = jsonSettings.openConfig(self.configPath+'motorPresetsTMCL.json')
        self.racks = jsonSettings.openConfig(self.configPath+'racksTMCL.json')
        self.presetNames = sorted(self.presets.childGroups())

        self.setup()

    def setup(self):
        mainLayout = QVBoxLayout()
        mainLayout.setSpacing(12)
        mainLayout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("➕ Nouveau moteur TMCL")
        title.setStyleSheet("font: bold 14pt; color: #4a9eff;")
        mainLayout.addWidget(title)

        formLayout = QFormLayout()

        self.typeCombo = QComboBox()
        self.typeCombo.addItem("-- Choisir un type --")
        self.typeCombo.addItems(self.presetNames)
        formLayout.addRow("Type :", self.typeCombo)

        rackLayout = QHBoxLayout()
        self.rackCombo = QComboBox()
        self.newRackButton = QPushButton("➕ Nouveau rack")
        self.newRackButton.clicked.connect(self.openAddRackDialog)
        rackLayout.addWidget(self.rackCombo)
        rackLayout.addWidget(self.newRackButton)
        formLayout.addRow("Rack :", rackLayout)

        self.axisSpin = QSpinBox()
        self.axisSpin.setRange(0, 5)
        formLayout.addRow("Numéro d'axe (0-5) :", self.axisSpin)

        self.nameEdit = QLineEdit()
        self.nameEdit.setPlaceholderText("ex: tilt lat")
        formLayout.addRow("Nom d'affichage :", self.nameEdit)

        mainLayout.addLayout(formLayout)

        self.infoLabel = QLabel("")
        self.infoLabel.setStyleSheet("color: #888; font-size: 9pt;")
        self.infoLabel.setWordWrap(True)
        mainLayout.addWidget(self.infoLabel)
        self.typeCombo.currentTextChanged.connect(self.updateInfo)

        mainLayout.addStretch()

        self.addButton = QPushButton("➕ Ajouter le moteur")
        self.addButton.setMinimumHeight(35)
        self.addButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.addButton.clicked.connect(self.addMotor)
        mainLayout.addWidget(self.addButton)

        self.setLayout(mainLayout)
        self.refreshRacks()

    def refreshRacks(self, selectName=None):
        current = selectName or self.rackCombo.currentText()
        self.rackCombo.clear()
        rackNames = sorted(self.racks.childGroups())
        if not rackNames:
            self.rackCombo.addItem("-- Aucun rack, cliquez sur Nouveau rack --")
        else:
            for name in rackNames:
                address = self.racks.value(name+"/address", "")
                self.rackCombo.addItem(f"{name} ({address})", userData=name)
        if current:
            idx = self.rackCombo.findData(current)
            if idx >= 0:
                self.rackCombo.setCurrentIndex(idx)

    def openAddRackDialog(self):
        dlg = ADDRACKDIALOG(self.racks, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.refreshRacks(selectName=dlg.newRackName)

    def updateInfo(self, name):
        if name not in self.presetNames:
            self.infoLabel.setText("")
            return
        vals = {k: self.presets.value(name+"/"+k) for k in
                ("Cmax", "Cstandby", "Vmax", "AccMax", "PulseDiv", "RampDiv", "stepResolution", "stepmotor")}
        self.infoLabel.setText(
            f"Cmax:{vals['Cmax']} Cstandby:{vals['Cstandby']} Vmax:{vals['Vmax']} "
            f"AccMax:{vals['AccMax']} PulseDiv:{vals['PulseDiv']} RampDiv:{vals['RampDiv']} "
            f"stepResolution:{vals['stepResolution']} stepmotor:{vals['stepmotor']}"
        )

    def addMotor(self):
        typeName = self.typeCombo.currentText()
        axis = self.axisSpin.value()
        rack = self.rackCombo.currentData()
        displayName = self.nameEdit.text().strip()

        if typeName not in self.presetNames:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir un type de moteur.")
            return
        if not rack:
            QMessageBox.warning(self, "Erreur", "Veuillez choisir (ou créer) un rack.")
            return
        if not displayName:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir un nom d'affichage pour ce moteur.")
            return

        axisId = f"axe{axis}"
        key = f"{rack}_{axisId}"

        if key in self.confMotors.childGroups():
            reply = QMessageBox.question(
                self, "Axe déjà configuré",
                f"L'axe {axis} du rack '{rack}' est déjà configuré (nom actuel : "
                f"'{self.confMotors.value(key+'/Name')}'). Voulez-vous l'écraser avec ces valeurs ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        for k in ("Cmax", "Cstandby", "Vmax", "AccMax", "PulseDiv", "RampDiv", "stepResolution", "stepmotor"):
            self.confMotors.setValue(key+"/"+k, self.presets.value(typeName+"/"+k))

        self.confMotors.setValue(key+"/Name", displayName)
        self.confMotors.setValue(key+"/numMoteur", axis)
        self.confMotors.setValue(key+"/rack", rack)
        self.confMotors.setValue(key+"/moteurType", "TMCL")
        self.confMotors.setValue(key+"/version", "1.0")
        self.confMotors.setValue(key+"/alimSeuil", 200)
        self.confMotors.setValue(key+"/rightSwitchEnable", False)
        self.confMotors.setValue(key+"/leftSwitchEnable", False)
        self.confMotors.setValue(key+"/buteePos", 500000000000000)
        self.confMotors.setValue(key+"/buteeneg", -50000000000000)
        self.confMotors.setValue(key+"/date", time.strftime("%A %d %B %Y %H:%M:%S"))
        for i in range(1, 7):
            self.confMotors.setValue(f"{key}/ref{i}Name", f"ref{i}")
            self.confMotors.setValue(f"{key}/ref{i}Pos", 0)

        self.confMotors.sync()

        QMessageBox.information(self, "Succès", f"✅ Moteur '{displayName}' ajouté ({key}, type {typeName}) !")
        self.nameEdit.clear()


if __name__ == '__main__':
    appli = QApplication(sys.argv)
    w = ADDMOTORWIDGET()
    w.show()
    appli.exec()
