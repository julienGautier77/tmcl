# -*- coding: utf-8 -*-


"""
Interface Graphique pour le pilotage de deux moteurs tilt (TMCL/TMCM)
Thread secondaire pour afficher les positions
import files : moteurTMCL.py
python 3.X PyQt6
@author: Gautier julien loa
Created on Tue Jan 4 10:42:10 2018
Modified on Tue july 17  10:49:32 2018
"""

from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication, QToolButton
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QVBoxLayout, QHBoxLayout, QPushButton, QGridLayout, QDoubleSpinBox
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
import qdarkstyle
import pathlib
import time
import sys
import os
import moteurTMCL
from oneMotorTMCLGui import ONEMOTORGUI
import __init__
__version__=__init__.__version__

PY = sys.version_info[0]
if PY < 3:
    print('wrong version of python : Python 3.X must be used')


class TILTMOTORGUI(QWidget):
    """
    User interface Motor class :
    TILTMOTORGUI(rack, axisLat, axisVert, nomWin, nomTilt, unit)
    rack= identifiant du rack (groupe de racksTMCL.json) partagé par les 2 axes
    axisLat= numéro d'axe lat sur ce rack : 'axe0' à 'axe5'
    axisVert= numéro d'axe vert sur ce rack : 'axe0' à 'axe5'
    nomWin= windows name
    nomTilt= windows tilt name
    unit=0 step 1 micron 2 mm 3 ps 4 degres

    fichier de config des moteurs : 'configMoteurTMCL.json' (clé = "<rack>_<axe>")
    """

    def __init__(self, rack, axisLat, axisVert, nomWin='', nomTilt='', unit=1, jogValue=100, background='', parent=None, showUnit=False, invLat=False, invVert=False):

        super(TILTMOTORGUI, self).__init__()
        p = pathlib.Path(__file__)
        sepa = os.sep
        self.icon = str(p.parent) + sepa + 'icons' + sepa
        self.showUnit = showUnit
        self.inv = [invLat, invVert]
        self.iconFlecheHaut = self.icon + "flechehaut.png"
        self.iconFlecheHaut = pathlib.Path(self.iconFlecheHaut)
        self.iconFlecheHaut = pathlib.PurePosixPath(self.iconFlecheHaut)

        self.iconFlecheBas = self.icon + "flechebas.png"
        self.iconFlecheBas = pathlib.Path(self.iconFlecheBas)
        self.iconFlecheBas = pathlib.PurePosixPath(self.iconFlecheBas)

        self.iconFlecheDroite = self.icon + "flechedroite.png"
        self.iconFlecheDroite = pathlib.Path(self.iconFlecheDroite)
        self.iconFlecheDroite = pathlib.PurePosixPath(self.iconFlecheDroite)

        self.iconFlecheGauche = self.icon + "flechegauche.png"
        self.iconFlecheGauche = pathlib.Path(self.iconFlecheGauche)
        self.iconFlecheGauche = pathlib.PurePosixPath(self.iconFlecheGauche)
        self.isWinOpen = False
        if background != "":
            self.setStyleSheet("background-color:"+background)
        else:
            self.setStyleSheet(qdarkstyle.load_stylesheet_pyqt6())
        self.indexUnit = unit
        self.jogValue = jogValue
        self.nomTilt = nomTilt
        self.setWindowIcon(QIcon(self.icon+'LOA.png'))
        self.version = __version__
        self.rackId = rack
        self.axisLat = axisLat
        self.axisVert = axisVert
        self.motor = [f"{rack}_{axisLat}", f"{rack}_{axisVert}"]
        self.MOT = [0, 0]
        self.MOT[0] = moteurTMCL.MOTORTMCL(self.motor[0])
        self.MOT[1] = moteurTMCL.MOTORTMCL(self.motor[1])
        self.stepmotor = [0, 0]
        self.butePos = [0, 0]
        self.buteNeg = [0, 0]
        self.name = [0, 0]

        for zzi in range(0, 2):
            self.stepmotor[zzi] = float(moteurTMCL.confTMCL.value(self.motor[zzi]+"/stepmotor"))  # list of stepmotor values for unit conversion
            self.butePos[zzi] = float(moteurTMCL.confTMCL.value(self.motor[zzi]+"/buteePos"))
            self.buteNeg[zzi] = float(moteurTMCL.confTMCL.value(self.motor[zzi]+"/buteeneg"))
            self.name[zzi] = str(moteurTMCL.confTMCL.value(self.motor[zzi]+"/Name"))

        self.setWindowTitle(nomWin)

        self.threadLat = PositionThread(mot=self.MOT[0])  # thread pour afficher position Lat
        self.threadLat.POS.connect(self.PositionLat)

        time.sleep(0.1)

        self.threadVert = PositionThread(mot=self.MOT[1])  # thread pour afficher position Vert
        self.threadVert.POS.connect(self.PositionVert)

        self.latWidget = None
        self.vertWidget = None

        self.setup()
        self.unitTrans()

    def setup(self):

        vbox1 = QVBoxLayout()
        hbox1 = QHBoxLayout()
        nameBox = QLabel(self)
        nameBox.setText(self.nomTilt)
        nameBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nameBox.setStyleSheet('font: bold 14px;color: purple')
        vbox1.addWidget(nameBox)

        grid_layout = QGridLayout()
        grid_layout.setVerticalSpacing(0)
        grid_layout.setHorizontalSpacing(5)

        self.haut = QToolButton()
        self.haut.setStyleSheet("QToolButton:!pressed{border-image: url(%s);background-color: transparent ;border-color: gray;}""QToolButton:pressed{image: url(%s);background-color: gray ;border-color: gray}"%(self.iconFlecheHaut,self.iconFlecheHaut))
        self.haut.setMaximumHeight(15)
        self.haut.setMinimumWidth(15)
        self.haut.setMaximumWidth(15)
        self.haut.setMinimumHeight(15)
        self.haut.setAutoRepeat(True)

        self.bas = QToolButton()
        self.bas.setStyleSheet("QToolButton:!pressed{border-image: url(%s);background-color: transparent ;border-color: gray;}""QToolButton:pressed{image: url(%s);background-color: gray ;border-color: gray}"%(self.iconFlecheBas,self.iconFlecheBas))
        self.bas.setMaximumHeight(15)
        self.bas.setMinimumWidth(15)
        self.bas.setMaximumWidth(15)
        self.bas.setMinimumHeight(15)
        self.bas.setAutoRepeat(True)

        self.gauche = QToolButton()
        self.gauche.setStyleSheet("QToolButton:!pressed{border-image: url(%s);background-color: transparent ;border-color: gray;}""QToolButton:pressed{image: url(%s);background-color: gray ;border-color: gray}"%(self.iconFlecheGauche,self.iconFlecheGauche))
        self.gauche.setMaximumHeight(15)
        self.gauche.setMinimumWidth(15)
        self.gauche.setMaximumWidth(15)
        self.gauche.setMinimumHeight(15)
        self.droite = QToolButton()
        self.droite.setStyleSheet("QToolButton:!pressed{border-image: url(%s);background-color: transparent ;border-color: gray;}""QToolButton:pressed{image: url(%s);background-color: gray ;border-color: gray}"%(self.iconFlecheDroite,self.iconFlecheDroite))
        self.droite.setMaximumHeight(15)
        self.droite.setMinimumWidth(15)
        self.droite.setMaximumWidth(15)
        self.droite.setMinimumHeight(15)

        self.jogStep = QDoubleSpinBox()
        self.jogStep.setMaximum(1000000)
        self.jogStep.setStyleSheet("font: bold 8pt")
        self.jogStep.setValue(self.jogValue)
        self.jogStep.setMaximumWidth(70)
        self.jogStep.setMaximumHeight(20)

        center = QHBoxLayout()
        center.addWidget(self.jogStep)
        self.hautLayout = QHBoxLayout()
        self.hautLayout.addWidget(self.haut)
        self.basLayout = QHBoxLayout()
        self.basLayout.addWidget(self.bas)
        grid_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        grid_layout.addLayout(self.hautLayout, 0, 1)
        grid_layout.addLayout(self.basLayout, 2, 1)
        grid_layout.addWidget(self.gauche, 1, 0)
        grid_layout.addWidget(self.droite, 1, 2)
        grid_layout.addLayout(center, 1, 1)

        hbox1.addLayout(grid_layout)
        vbox1.addLayout(hbox1)

        posLAT = QPushButton('Lateral')
        posLAT.setStyleSheet("font: bold 6pt")
        posLAT.setMaximumHeight(12)
        posLAT.clicked.connect(self.openLatWidget)
        posVERT = QPushButton('Vertical')
        posVERT.setStyleSheet("font: bold 6pt")
        posVERT.setMaximumHeight(12)
        posVERT.clicked.connect(self.openVertWidget)
        hbox2 = QHBoxLayout()
        hbox2.addWidget(posLAT)
        hbox2.addWidget(posVERT)
        vbox1.addLayout(hbox2)

        self.position_Lat = QLabel('pos')
        self.position_Lat.setMaximumHeight(12)
        self.position_Lat.setStyleSheet("font: bold 6pt")
        self.position_Lat.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.position_Vert = QLabel('pos')
        self.position_Vert.setMaximumHeight(12)
        self.position_Vert.setStyleSheet("font: bold 6pt")
        self.position_Vert.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        hbox3 = QHBoxLayout()
        hbox3.addWidget(self.position_Lat)

        hbox3.addWidget(self.position_Vert)

        vbox1.addLayout(hbox3)

        hbox4 = QHBoxLayout()
        self.zeroButtonLat = QToolButton()
        self.zeroButtonLat.setText('Zero Lat')
        self.zeroButtonLat.setStyleSheet("font: bold 5pt")
        self.zeroButtonVert = QToolButton()
        self.zeroButtonVert.setText('Zero Vert')
        self.zeroButtonVert.setStyleSheet("font: bold 5pt")
        self.zeroButtonLat.setMaximumHeight(14)
        self.zeroButtonVert.setMaximumHeight(14)
        self.zeroButtonLat.setMaximumWidth(40)
        self.zeroButtonVert.setMaximumWidth(40)
        hbox4.addWidget(self.zeroButtonLat)
        hbox4.addWidget(self.zeroButtonVert)
        vbox1.addLayout(hbox4)

        self.stopButton = QPushButton('STOP')
        self.stopButton.setStyleSheet("background-color: red;font: bold 8pt")
        self.stopButton.setMaximumHeight(14)

        hbox5 = QHBoxLayout()
        hbox5.addWidget(self.stopButton)
        vbox1.addLayout(hbox5)
        vbox1.setContentsMargins(1, 1, 1, 1)

        self.setLayout(vbox1)
        self.actionButton()

    def startThread2(self):
        self.threadLat.ThreadINIT()
        self.threadLat.start()
        time.sleep(0.1)
        self.threadVert.ThreadINIT()
        self.threadVert.start()

    def actionButton(self):
        '''
           Definition des boutons
        '''
        self.haut.clicked.connect(self.hMove)  # jog haut
        self.haut.setAutoRepeat(False)
        self.bas.clicked.connect(self.bMove)  # jog bas
        self.bas.setAutoRepeat(False)
        self.gauche.clicked.connect(self.gMove)
        self.gauche.setAutoRepeat(False)
        self.droite.clicked.connect(self.dMove)
        self.droite.setAutoRepeat(False)

        self.zeroButtonLat.clicked.connect(self.ZeroLat)  # remet a zero l'affichage
        self.zeroButtonVert.clicked.connect(self.ZeroVert)
        self.stopButton.clicked.connect(self.StopMot)  # arret moteur

    def closeEvent(self, event):
        """
        When closing the window
        """
        self.fini()
        time.sleep(0.1)
        event.accept()

    def gMove(self):
        '''
        action bouton left -
        '''
        a = float(self.jogStep.value())
        a = float(a*self.unitChangeLat)
        b = self.MOT[0].position()
        if self.inv[0] is False:
            if b - a < self.buteNeg[0]:
                print("STOP : Butée Negative")
                self.MOT[0].stopMotor()
            else:
                self.MOT[0].rmove(-a)
        else:  # inv true on fait +
            if b + a > self.butePos[0]:
                print("STOP : Butée Pos")
                self.MOT[0].stopMotor()
            else:
                self.MOT[0].rmove(a)

    def dMove(self):
        '''
        action bouton right +
        '''
        a = float(self.jogStep.value())
        a = float(a*self.unitChangeLat)
        b = self.MOT[0].position()
        if self.inv[0] is False:
            if b + a > self.butePos[0]:
                print("STOP : Butée Positive")
                self.MOT[0].stopMotor()
            else:
                self.MOT[0].rmove(+a)
        else:  # on fait du moins
            if b - a < self.buteNeg[0]:
                print("STOP : Butée Negative")
                self.MOT[0].stopMotor()
            else:
                self.MOT[0].rmove(-a)

    def hMove(self):
        '''
        action bouton up +
        '''
        a = float(self.jogStep.value())
        a = float(a*self.unitChangeVert)
        b = self.MOT[1].position()
        if self.inv[1] is False:  # +
            if b + a > self.butePos[1]:
                print("STOP : Butée Positive")
                self.MOT[1].stopMotor()
            else:
                self.MOT[1].rmove(a)
        else:  # -
            if b - a < self.buteNeg[1]:
                print("STOP : Butée Negative")
                self.MOT[1].stopMotor()
            else:
                self.MOT[1].rmove(-a)

    def bMove(self):
        '''
        action bouton down
        '''
        a = float(self.jogStep.value())
        a = float(a*self.unitChangeVert)
        b = self.MOT[1].position()
        if self.inv[1] is False:  # -
            if b - a < self.buteNeg[1]:
                print("STOP : Butée Negative")
                self.MOT[1].stopMotor()
            else:
                self.MOT[1].rmove(-a)
        else:
            if b + a > self.butePos[1]:
                print("STOP : Butée Positive")
                self.MOT[1].stopMotor()
            else:
                self.MOT[1].rmove(a)

    def ZeroLat(self):  # remet le compteur a zero
        self.MOT[0].setzero()

    def ZeroVert(self):  # remet le compteur a zero
        self.MOT[1].setzero()

    def open_widget(self, fene):
        '''
        ouvre le widget complet du moteur (ou le remet au premier plan s'il est deja ouvert)
        '''
        if fene.isWinOpen == False:
            fene.show()
            fene.startThread2()
            fene.isWinOpen = True
        else:
            fene.raise_()
            fene.showNormal()

    def openLatWidget(self):
        if self.latWidget is None:
            self.latWidget = ONEMOTORGUI(mot=self.axisLat, rack=self.rackId, nomWin=self.nomTilt+' Lat', showRef=True, unit=self.indexUnit, jogValue=self.jogValue)
        self.open_widget(self.latWidget)

    def openVertWidget(self):
        if self.vertWidget is None:
            self.vertWidget = ONEMOTORGUI(mot=self.axisVert, rack=self.rackId, nomWin=self.nomTilt+' Vert', showRef=True, unit=self.indexUnit, jogValue=self.jogValue)
        self.open_widget(self.vertWidget)

    def unitTrans(self):
        '''
        Calcule les facteurs de conversion unité<->step pour les 2 axes
        '''
        if self.indexUnit == 0:  # step
            self.unitChangeLat = 1
            self.unitChangeVert = 1
            self.unitNameTrans = 'step'
        elif self.indexUnit == 1:  # micron
            self.unitChangeLat = float(1*self.stepmotor[0])
            self.unitChangeVert = float(1*self.stepmotor[1])
            self.unitNameTrans = 'um'
        elif self.indexUnit == 2:  # mm
            self.unitChangeLat = float(1000*self.stepmotor[0])
            self.unitChangeVert = float(1000*self.stepmotor[1])
            self.unitNameTrans = 'mm'
        elif self.indexUnit == 3:  # ps double passage : 1 micron=6fs
            self.unitChangeLat = float(1*self.stepmotor[0]/0.0066666666)
            self.unitChangeVert = float(1*self.stepmotor[1]/0.0066666666)
            self.unitNameTrans = 'ps'
        elif self.indexUnit == 4:  # degres
            self.unitChangeLat = 1*self.stepmotor[0]
            self.unitChangeVert = 1*self.stepmotor[1]
            self.unitNameTrans = '°'
        else:
            self.unitChangeLat = 1
            self.unitChangeVert = 1
            self.unitNameTrans = 'step'
        if self.unitChangeLat == 0:
            self.unitChangeLat = 1  # avoid /0
        if self.unitChangeVert == 0:
            self.unitChangeVert = 1  # avoid /0

        self.jogStep.setSuffix(" %s" % self.unitNameTrans)
        self.jogStep.setValue(self.jogValue)

    def StopMot(self):
        '''
        stop les moteurs
        '''
        for zzi in range(0, 2):
            self.MOT[zzi].stopMotor()

    def PositionLat(self, Posi):
        '''
        affichage de la position a l aide du second thread
        '''
        a = float(Posi)
        a = a / self.unitChangeLat  # valeur tenant compte du changement d'unite
        self.position_Lat.setText(str(round(a, 2)))
        self.position_Lat.setStyleSheet('font: bold 6pt;color:white')

    def PositionVert(self, Posi):
        '''
        affichage de la position a l aide du second thread
        '''
        a = float(Posi)
        a = a / self.unitChangeVert  # valeur tenant compte du changement d'unite
        self.position_Vert.setText(str(round(a, 2)))
        self.position_Vert.setStyleSheet('font: bold 6pt;color:white')

    def fini(self):
        '''
        a la fermeture de la fenetre on arrete le thread secondaire
        '''
        self.threadLat.stopThread()
        self.threadVert.stopThread()
        if self.latWidget is not None and self.latWidget.isWinOpen:
            self.latWidget.close()
        if self.vertWidget is not None and self.vertWidget.isWinOpen:
            self.vertWidget.close()
        self.isWinOpen = False
        time.sleep(0.1)

    def close(self):
        self.fini


class PositionThread(QtCore.QThread):
    '''
    Second thread to display the position
    '''
    import time
    POS = QtCore.pyqtSignal(float)  # signal of the second thread to main thread to display motors position

    def __init__(self, parent=None, mot='',):
        super(PositionThread, self).__init__(parent)
        self.MOT = mot
        self.parent = parent
        self.stop = False

    def run(self):
        while True:
            if self.stop is True:
                break
            else:
                Posi = self.MOT.position()
                time.sleep(0.1)
                try:
                    self.POS.emit(Posi)
                    time.sleep(0.01)
                except Exception as e:
                    print('error emit', e)

    def ThreadINIT(self):
        self.stop = False

    def stopThread(self):
        self.stop = True
        time.sleep(0.01)


if __name__ == '__main__':
    appli = QApplication(sys.argv)
    mot5 = TILTMOTORGUI(rack='rack1', axisLat='axe0', axisVert='axe5', nomWin='Tilt Turning Haut', nomTilt='tilt TB', background='')
    mot5.show()
    mot5.startThread2()
    appli.exec()
