# -*- coding: utf-8 -*-
"""
Created on Mon Apr  1 11:16:50 2019

@author: sallejaune
"""

#%%Import
from PyQt6 import QtCore
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QWidget,QMessageBox,QLineEdit,QTextEdit,QDialog,QGroupBox
from PyQt6.QtWidgets import QVBoxLayout,QHBoxLayout,QPushButton,QGridLayout,QDoubleSpinBox,QCheckBox
from PyQt6.QtWidgets import QComboBox,QLabel
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import QRect, Qt

import sys,time,os
import qdarkstyle
import pathlib
from collections import deque
from datetime import datetime
import __init__

import jsonSettings
import moteurTMCL

__version__=__init__.__version__



class ONEMOTORGUI(QWidget) :
    """
    User interface Motor class for TMCL/TMCM motors :
    ONEMOTORGUI(mot='axe0', rack='rack1', nomWin=..., nomTilt=..., )
    mot = numéro d'axe sur le rack : 'axe0' à 'axe5' (6 axes possibles par rack)
    rack = identifiant du rack (groupe de racksTMCL.json, définit l'adresse IP/USB)
    nonWin= windows name

    showRef =True show refrence widget
    unit : 0: step 1: um 2: mm 3: ps 4: °

    fichier de config des moteurs : 'configMoteurTMCL.json' (clé = "<rack>_<mot>")
    """

    def __init__(self, mot='',rack='',nomWin='TMCL Control',showRef=False,unit=2,jogValue=1,parent=None):

        super(ONEMOTORGUI, self).__init__(parent)

        p = pathlib.Path(__file__)
        sepa=os.sep
        self.icon=str(p.parent) + sepa + 'icons' +sepa
        self.axisId=str(mot)
        self.rackId=str(rack)
        self.motor=[f"{rack}_{mot}"]
        self.motorTypeName=['TMCL']
        self.motorType=[0]
        self.MOT=[0]
        self.configMotName=[0]
        self.conf=[0]
        self.configPath=str(p.parent / "fichiersConfig")+sepa
        self.isWinOpen=False
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        self.refShowId=showRef
        self.indexUnit=unit
        self.jogValue=jogValue
        self.setWindowIcon(QIcon(self.icon+'LOA.png'))
        self.setWindowOpacity(0.96)
        # log
        self.actionLog=deque(maxlen=20)
        self.logWindow=None
        self.alimOff=False
        self.butNegSoft=False # butée logicielle négative atteinte
        self.butPosSoft=False # butée logicielle positive atteinte
        self.butNegHard=False # switch matériel gauche déclenché
        self.butPosHard=False # switch matériel droit déclenché
        for zi in range (0,1): #  list configuration et motor
            self.configMotName[zi]=self.configPath+'configMoteurTMCL.json'
            import moteurTMCL as TMCL
            self.motorType[zi]=TMCL
            self.MOT[zi]=self.motorType[zi].MOTORTMCL(self.motor[zi])
            self.conf[zi]=jsonSettings.openConfig(self.configMotName[zi]) # fichier config motor (json)

        self.stepmotor=[0,0,0]
        self.butePos=[0,0,0]
        self.buteNeg=[0,0,0]
        self.name=[0,0,0]
        
        for zzi in range(0,1):
            
            self.stepmotor[zzi]=float(self.conf[zzi].value(self.motor[zzi]+"/stepmotor")) #list of stepmotor values for unit conversion
            self.butePos[zzi]=float(self.conf[zzi].value(self.motor[zzi]+"/buteePos")) # list 
            self.buteNeg[zzi]=float(self.conf[zzi].value(self.motor[zzi]+"/buteeneg"))
            self.name[zzi]=str(self.conf[zzi].value(self.motor[zzi]+"/Name"))

        self.nomWin=nomWin
        self.version=str(self.conf[0].value(self.motor[0]+"/version",""))
        self.updateWindowTitle()
        
        self.thread=PositionThread(self,mot=self.MOT[0],motorType=self.motorType[0]) # thread for displaying position
        self.thread.POS.connect(self.Position)

        
        
        ## initialisation of the jog value 
        if self.indexUnit==0: #  step
            self.unitChange=1
            self.unitName='step'
            
        if self.indexUnit==1: # micron
            self.unitChange=float((1*self.stepmotor[0])) 
            self.unitName='um'
        if self.indexUnit==2: #  mm 
            self.unitChange=float((1000*self.stepmotor[0]))
            self.unitName='mm'
        if self.indexUnit==3: #  ps  double passage : 1 microns=6fs
            self.unitChange=float(1*self.stepmotor[0]/0.0066666666) 
            self.unitName='ps'
        if self.indexUnit==4: #  en degres
            self.unitChange=1 *self.stepmotor[0]
            self.unitName='°'
        self.configWidget=ConfigMotorWidget(motor=self.MOT[0],parent=self) # Widget de configuration
        self.setup()
        self.unit()
        self.jogStep.setValue(self.jogValue)
        self.addLog("Initialisation", f"Moteur {self.name[0]} ({self.motorTypeName[0]})")

    def updateWindowTitle(self):
        self.setWindowTitle(self.nomWin+' : '+ self.motor[0]+' - '+self.name[0]+'             V.'+self.version)

    def startThread2(self):
        self.thread.ThreadINIT()
        self.thread.start()
        time.sleep(0.1)
        self.statusTimer=QtCore.QTimer(self)
        self.statusTimer.timeout.connect(self.checkStatus)
        self.statusTimer.start(5000)
        self.checkStatus()

    def checkStatus(self):
        '''
        Vérifie toutes les 5s la tension d'alimentation (GIO port 8, banque 1)
        et l'état des switchs de fin de course activés (GAP axis param 10/11)
        N'affiche quelque chose dans self.enPosition que si l'alim est coupée
        '''
        try:
            volt=self.MOT[0].getSupplyVoltage()
        except Exception as e:
            self.addLog("ERROR", f"Erreur lecture tension alim: {e}")
        else:
            seuil=float(self.conf[0].value(self.motor[0]+"/alimSeuil", 200))
            if volt<seuil:
                self.alimOff=True
                self.enPosition.setText("ALIM OFF")
                self.enPosition.setStyleSheet("font: bold 15pt; color: red")
            else:
                self.alimOff=False

        if bool(self.conf[0].value(self.motor[0]+"/rightSwitchEnable", False)):
            try:
                self.butPosHard=self.MOT[0].getRightSwitchStatus()
            except Exception as e:
                self.addLog("ERROR", f"Erreur lecture switch droit: {e}")
        else:
            self.butPosHard=False
        if bool(self.conf[0].value(self.motor[0]+"/leftSwitchEnable", False)):
            try:
                self.butNegHard=self.MOT[0].getLeftSwitchStatus()
            except Exception as e:
                self.addLog("ERROR", f"Erreur lecture switch gauche: {e}")
        else:
            self.butNegHard=False
        self.refreshLimitChecks()

    def refreshLimitChecks(self):
        '''
        Coche But Neg/Pos si la butée logicielle est atteinte OU si le switch matériel est déclenché
        '''
        self.butNegButt.setChecked(self.butNegSoft or self.butNegHard)
        self.butPosButt.setChecked(self.butPosSoft or self.butPosHard)


    def setup(self):
        
        vbox1=QVBoxLayout() 
        hboxTitre=QHBoxLayout()
        self.nom=QLabel(self.name[0])
        self.nom.setStyleSheet("font: bold 20pt;color:yellow")
        hboxTitre.addWidget(self.nom)
        
        self.enPosition=QLineEdit()
        #self.enPosition.setMaximumWidth(50)
        self.enPosition.setStyleSheet("font: bold 15pt")
        self.enPosition.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        hboxTitre.addWidget(self.enPosition)
        self.butNegButt=QCheckBox('But Neg',self)
        hboxTitre.addWidget(self.butNegButt)
       
        self.butPosButt=QCheckBox('But Pos',self)
        hboxTitre.addWidget(self.butPosButt)
        vbox1.addLayout(hboxTitre)
        #vbox1.addSpacing(10)
        
        
        hbox0=QHBoxLayout()
        self.position=QLabel('1234567')
        self.position.setMaximumWidth(300)
        self.position.setStyleSheet("font: bold 40pt" )
        
        self.unitBouton=QComboBox()
        self.unitBouton.addItem('Step')
        self.unitBouton.addItem('um')
        self.unitBouton.addItem('mm')
        self.unitBouton.addItem('ps')
        self.unitBouton.addItem('°')
        self.unitBouton.setMaximumWidth(100)
        self.unitBouton.setMinimumWidth(100)
        self.unitBouton.setStyleSheet("font: bold 12pt")
        self.unitBouton.setCurrentIndex(self.indexUnit)
        
        
        self.zeroButton=QPushButton('Zero')
        self.zeroButton.setMaximumWidth(50)
        
        hbox0.addWidget(self.position)
        hbox0.addWidget(self.unitBouton)
        hbox0.addWidget(self.zeroButton)
        vbox1.addLayout(hbox0)
        #vbox1.addSpacing(10)
        
        hboxAbs=QHBoxLayout()
        absolueLabel=QLabel('Absolue mouvement')
#        absolueLabel.setStyleSheet("background-color: green")
        self.MoveStep=QDoubleSpinBox()
        self.MoveStep.setMaximum(1000000)
        self.MoveStep.setMinimum(-1000000)
        #self.MoveStep.setStyleSheet("background-color: green")
        
        self.absMvtButton=QPushButton()
        self.absMvtButton.setStyleSheet(f"QPushButton:!pressed{{border-image: url({self.icon}playGreen.png);background-color: transparent;border-color: green;}}QPushButton:pressed{{image: url({self.icon}playGreen.png) ;background-color: transparent;border-color: blue}}")
        self.absMvtButton.setMinimumHeight(50)
        self.absMvtButton.setMaximumHeight(50)
        self.absMvtButton.setMinimumWidth(50)
        self.absMvtButton.setMaximumWidth(50)
        #self.absMvtButton.setStyleSheet("background-color: green")
        hboxAbs.addWidget(absolueLabel)
        hboxAbs.addWidget(self.MoveStep)
        hboxAbs.addWidget(self.absMvtButton)
        vbox1.addLayout(hboxAbs)
        vbox1.addSpacing(10)
        hbox1=QHBoxLayout()
        self.moins=QPushButton()
        self.moins.setStyleSheet(f"QPushButton:!pressed{{border-image: url({self.icon}moinsBleu.png);background-color: transparent ;border-color: green;}}QPushButton:pressed{{image: url({self.icon}moinsBleu.png);background-color: transparent;border-color: blue}}")
        
        self.moins.setMinimumHeight(70)
        self.moins.setMaximumHeight(70)
        self.moins.setMinimumWidth(70)
        self.moins.setMaximumWidth(70)
        
        #self.moins.setStyleSheet("border-radius:20px")
        hbox1.addWidget(self.moins)
        
        self.jogStep=QDoubleSpinBox()
        self.jogStep.setMaximum(10000)
        self.jogStep.setMaximumWidth(130)
        self.jogStep.setStyleSheet("font: bold 12pt")
        self.jogStep.setValue(self.jogValue)
  
        hbox1.addWidget(self.jogStep)
         
        
        self.plus=QPushButton()
        self.plus.setStyleSheet(f"QPushButton:!pressed{{border-image: url({self.icon}plusBleu.png) ;background-color: transparent;border-color: green;}}QPushButton:pressed{{image: url({self.icon}plusBleu.png) ;background-color: transparent;border-color: blue}}")
        self.plus.setMinimumHeight(70)
        self.plus.setMaximumHeight(70)
        self.plus.setMinimumWidth(70)
        self.plus.setMaximumWidth(70)
        #self.plus.setStyleSheet("border-radius:20px")
        hbox1.addWidget(self.plus)
        
        vbox1.addLayout(hbox1)
        #vbox1.addStretch(10)
        vbox1.addSpacing(10)
        
        hbox2=QHBoxLayout()
        self.stopButton=QPushButton()
        self.stopButton.setStyleSheet(f"QPushButton:!pressed{{border-image: url({self.icon}close.png);background-color: transparent;border-color: green;}}QPushButton:pressed{{image: url({self.icon}close.png) ;background-color: transparent;border-color: blue}}")
        #self.stopButton.setStyleSheet("border-radius:20px;background-color: red")
        self.stopButton.setMaximumHeight(70)
        self.stopButton.setMaximumWidth(70)
        self.stopButton.setMinimumHeight(70)
        self.stopButton.setMinimumWidth(70)
        hbox2.addWidget(self.stopButton)
        vbox2=QVBoxLayout()
        
        self.showRef=QPushButton('Show Ref')
        self.showRef.setMaximumWidth(90)
        vbox2.addWidget(self.showRef)
        self.configButton=QPushButton('⚙️ Config')
        self.configButton.setMaximumWidth(90)
        self.configButton.setToolTip('Configurer butées et step')
        vbox2.addWidget(self.configButton)
        hbox2.addLayout(vbox2)
        
        vbox1.addLayout(hbox2)
        vbox1.addSpacing(10)
        
        self.REF1 = REF1M(num=1)
        self.REF2 = REF1M(num=2)
        self.REF3 = REF1M(num=3)
        self.REF4 = REF1M(num=4)
        self.REF5 = REF1M(num=5)
        self.REF6 = REF1M(num=6)
        
        grid_layoutRef = QGridLayout()
        grid_layoutRef.setVerticalSpacing(4)
        grid_layoutRef.setHorizontalSpacing(4)
        grid_layoutRef.addWidget(self.REF1,0,0)
        grid_layoutRef.addWidget(self.REF2,0,1)
        grid_layoutRef.addWidget(self.REF3,1,0)
        grid_layoutRef.addWidget(self.REF4,1,1)
        grid_layoutRef.addWidget(self.REF5,2,0)
        grid_layoutRef.addWidget(self.REF6,2,1)
        
        self.widget6REF=QWidget()
        self.widget6REF.setLayout(grid_layoutRef)
        vbox1.addWidget(self.widget6REF)
       # vbox1.setContentsMargins(0,0,0,0)
        self.setLayout(vbox1)
        
        
        self.absRef=[self.REF1.ABSref,self.REF2.ABSref,self.REF3.ABSref,self.REF4.ABSref,self.REF5.ABSref,self.REF6.ABSref] 
        self.posText=[self.REF1.posText,self.REF2.posText,self.REF3.posText,self.REF4.posText,self.REF5.posText,self.REF6.posText]
        self.POS=[self.REF1.Pos,self.REF2.Pos,self.REF3.Pos,self.REF4.Pos,self.REF5.Pos,self.REF6.Pos]
        self.Take=[self.REF1.take,self.REF2.take,self.REF3.take,self.REF4.take,self.REF5.take,self.REF6.take]
        
        self.actionButton()
        self.jogStep.setFocus()
        self.refShow()
      
    def actionButton(self):
        '''
           buttons action setup 
        '''
        
        self.unitBouton.currentIndexChanged.connect(self.unit) #  unit change
        self.absMvtButton.clicked.connect(self.MOVE)
        self.plus.clicked.connect(self.pMove) # jog + foc
        self.plus.setAutoRepeat(False)
        self.moins.clicked.connect(self.mMove)# jog - fo
        self.moins.setAutoRepeat(False)
        self.configButton.clicked.connect(lambda:self.open_widget(self.configWidget))
        self.zeroButton.clicked.connect(self.Zero) # reset display to 0
       
        #self.refZeroButton.clicked.connect(self.RefMark) # todo
        
        self.stopButton.clicked.connect(self.StopMot)#stop motors
        self.showRef.clicked.connect(self.refShow) # show references widgets
        iii=1
        for saveNameButton in self.posText: # reference name
            nbRef=str(iii)
            saveNameButton.textChanged.connect(self.savName)
            saveNameButton.setText(str(self.conf[0].value(self.motor[0]+"/ref"+nbRef+"Name"))) # print  ref name
            iii+=1        
        for posButton in self.POS: # button GO
            posButton.clicked.connect(self.ref)    # go to reference value
        eee=1   
        for absButton in self.absRef: 
            nbRef=str(eee)
            absButton.setValue(float(self.conf[0].value(self.motor[0]+"/ref"+nbRef+"Pos"))/self.unitChange) # save reference value
            absButton.editingFinished.connect(self.savRef) # sauv value
            eee+=1
       
        for takeButton in self.Take:
            takeButton.clicked.connect(self.take) # take the value 
        
        
    def open_widget(self,fene):
        
        """ open new widget 
        """
        
        if fene.isWinOpen is False:
            #New widget"
            fene.show()
            fene.isWinOpen = True
    
        else:
            #fene.activateWindow()
            fene.raise_()
            fene.showNormal()
             
    def refShow(self):
        
        if self.refShowId is True:
            #self.resize(368, 345)
            self.widget6REF.show()
            self.refShowId=False
            self.showRef.setText('Hide Ref')
            self.setFixedSize(430,800)
             
        else:
            #print(self.geometry())
            
            self.widget6REF.hide()
            self.refShowId=True
            #self.setGeometry(QRect(107, 75, 429, 315))
            #self.setMaximumSize(368, 345)
            self.showRef.setText('Show Ref')
#            print(self.sizeHint())
#            self.minimumSizeHint()
#            print(self.sizeHint())
#            self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
            #self.setMaximumSize(300,300)
            self.setFixedSize(430,380)
           
            #self.updateGeometry()
    
    def MOVE(self):
        '''
        absolue mouvment
        '''
        
        a = float(self.MoveStep.value())
        a = float(a*self.unitChange) # changement d unite
        if a<self.buteNeg[0] :
            print( "STOP : Butée Négative")
            self.butNegSoft=True
            self.refreshLimitChecks()
            self.MOT[0].stopMotor()
            self.addLog("STOP", "Butée négative atteinte")
        elif a>self.butePos[0] :
            print( "STOP : Butée Positive")
            self.butPosSoft=True
            self.refreshLimitChecks()
            self.MOT[0].stopMotor()
            self.addLog("STOP", "Butée positive atteinte")
        else :
            self.MOT[0].move(a)
            self.butNegSoft=False
            self.butPosSoft=False
            self.refreshLimitChecks()
            self.addLog("absolue move", f"{self.MoveStep.value():.2f} {self.unitName}")

    def pMove(self):
        '''
        action jog + foc
        '''
        a = float(self.jogStep.value())
        a = float(a*self.unitChange)
        b = self.MOT[0].position()

        if b+a > self.butePos[0] :
            print( "STOP :  Positive switch")
            self.MOT[0].stopMotor()
            self.butPosSoft=True
            self.refreshLimitChecks()
            self.addLog("STOP", "Butée positive atteinte")
        else :
            self.MOT[0].rmove(a)
            self.butNegSoft=False
            self.butPosSoft=False
            self.refreshLimitChecks()
            self.addLog("rmove", f"+{self.jogStep.value():.2f} {self.unitName}")
    def mMove(self):
        '''
        action jog - foc
        '''
        a = float(self.jogStep.value())
        a = float(a*self.unitChange)
        b = self.MOT[0].position()
        if b-a<self.buteNeg[0] :
            print( "STOP : negative switch")
            self.MOT[0].stopMotor()
            self.butNegSoft=True
            self.refreshLimitChecks()
            self.addLog("STOP", "Butée négative atteinte")
        else :
            self.MOT[0].rmove(-a)
            self.butNegSoft=False
            self.butPosSoft=False
            self.refreshLimitChecks()
            self.addLog("rmove", f"-{self.jogStep.value():.2f} {self.unitName}")

    def Zero(self): #  zero
        self.MOT[0].setzero()
        self.addLog("Set Zero", "")

    def RefMark(self): # 
        """
            todo ....
        """
        #self.motorType.refMark(self.motor)
   
    def unit(self):
        '''
        unit change mot foc
        '''
        self.indexUnit=self.unitBouton.currentIndex()
        valueJog=self.jogStep.value()*self.unitChange
        
        if self.indexUnit==0: #  step
            self.unitChange=1
            self.unitName='step'
            
        if self.indexUnit==1: # micron
            self.unitChange=float((1*self.stepmotor[0])) 
            self.unitName='um'
        if self.indexUnit==2: #  mm 
            self.unitChange=float((1000*self.stepmotor[0]))
            self.unitName='mm'
        if self.indexUnit==3: #  ps  double passage : 1 microns=6fs
            self.unitChange=float(1*self.stepmotor[0]/0.0066666666) 
            self.unitName='ps'
        if self.indexUnit==4: #  en degres
            self.unitChange=1 *self.stepmotor[0]
            self.unitName='°'    
            
        if self.unitChange==0:
            self.unitChange=1 #avoid /0 
            
        self.jogStep.setSuffix(" %s" % self.unitName)
        self.jogStep.setValue(valueJog/self.unitChange)
        self.MoveStep.setSuffix(" %s" % self.unitName)

        eee=1
        for absButton in self.absRef: 
            nbRef=str(eee)
            absButton.setValue(float(self.conf[0].value(self.motor[0]+"/ref"+nbRef+"Pos"))/self.unitChange)
            absButton.setSuffix(" %s" % self.unitName)
            eee+=1
        
        
        
    def StopMot(self):
        '''
        stop all motors
        '''
        self.REF1.show()
        for zzi in range(0,1):
            self.MOT[zzi].stopMotor();
            self.addLog("STOP moteur", "Arrêt du moteur demandé")

    def Position(self,Posi):
        ''' 
        Position  display with the second thread
        '''
        a=float(Posi)
        b=a # value in step
        a=a/self.unitChange # value with unit changed

        self.position.setText(str(round(a,2)))
        self.position.setStyleSheet('font: bold 40pt;color:white')

        if self.alimOff:
            return # "ALIM OFF" reste affiché tant que l'alim n'est pas revenue

        self.enPosition.setStyleSheet("font: bold 15pt")
        positionConnue=0 #
        precis=5
        for nbRefInt in range(1,7):
            nbRef=str(nbRefInt)
            if float(self.conf[0].value(self.motor[0]+"/ref"+nbRef+"Pos"))-precis<b< float(self.conf[0].value(self.motor[0]+"/ref"+nbRef+"Pos"))+precis:
                self.enPosition.setText(str(self.conf[0].value(self.motor[0]+"/ref"+nbRef+"Name")))
                positionConnue=1
        if positionConnue==0:
            self.enPosition.setText('?' )

    def take (self) :
        ''' 
        take and save the reference
        '''
        sender=QtCore.QObject.sender(self) # take the name of  the button 
        
        nbRef=str(sender.objectName()[0])
        
        reply=QMessageBox.question(None,'Save Position ?',"Do you want to save this position ?",QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
               tpos=float(self.MOT[0].position())
               
               self.conf[0].setValue(self.motor[0]+"/ref"+nbRef+"Pos",tpos)
               self.conf[0].sync()
               
               self.absRef[int(nbRef)-1].setValue(tpos/self.unitChange)
               print ("Position saved",tpos)
               self.addLog("Reference value", f"saved ref{nbRef} : {tpos/self.unitChange:.2f} {self.unitName}")
               
#
    def ref(self):  
        '''
        Move the motor to the reference value in step : GO button
        Fait bouger le moteur a la valeur de reference en step : bouton Go 
        '''
        sender=QtCore.QObject.sender(self)
        reply=QMessageBox.question(None,'Go to this Position ?',"Do you want to GO to this position ?",QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            nbRef=str(sender.objectName()[0])
            for i in range (0,1):
                
                vref=int(self.conf[i].value(self.motor[i]+"/ref"+nbRef+"Pos"))
                if vref<self.buteNeg[i] :
                    print( "STOP : negative switch")
                    self.butNegSoft=True
                    self.refreshLimitChecks()
                    self.MOT[i].stopMotor()
                elif vref>self.butePos[i] :
                    print( "STOP : positive switch")
                    self.butPosSoft=True
                    self.refreshLimitChecks()
                    self.MOT[i].stopMotor()
                else :
                    self.MOT[i].move(vref)
                    self.butNegSoft=False
                    self.butPosSoft=False
                    self.refreshLimitChecks()
                    self.addLog("Reference", f"move to ref{nbRef}")
#
    def savName(self) :
        '''
        Save reference name
        '''
        sender=QtCore.QObject.sender(self)
        nbRef=sender.objectName()[0] #PosTExt1
        vname=self.posText[int(nbRef)-1].text()
        for i in range (0,1):
            self.conf[i].setValue(self.motor[i]+"/ref"+nbRef+"Name",str(vname))
            self.conf[i].sync()
#
    def savRef (self) :
        '''
        save reference  value
        '''
        sender=QtCore.QObject.sender(self)
        nbRef=sender.objectName()[0] # nom du button ABSref1
        
        vref=int(self.absRef[int(nbRef)-1].value())*self.unitChange
        self.conf[0].setValue(self.motor[0]+"/ref"+nbRef+"Pos",vref) # on sauvegarde en step dans le fichier ini
        self.conf[0].sync()

    def addLog(self, action, details=""):
        """Ajoute une action au log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.actionLog.append({'timestamp': timestamp, 'action': action, 'details': details})
        self.refreshLog()

    def showLog(self):
        """Affiche la fenêtre de log"""
        if self.logWindow is None or not self.logWindow.isVisible():
            self.logWindow = LogWindow(parent=self)
            self.logWindow.setLogs(list(self.actionLog))
            self.logWindow.show()
        else:
            self.logWindow.raise_()
            self.logWindow.activateWindow()

    def refreshLog(self):
        """Rafraîchit l'affichage du log"""
        if self.logWindow and self.logWindow.isVisible():
            self.logWindow.setLogs(list(self.actionLog))

    def clearLogs(self):
        """Efface tous les logs"""
        self.actionLog.clear()
        self.addLog("Historique effacé", "")

    def closeEvent(self, event):
        """
        When closing the window
        """
        self.fini()
        time.sleep(0.1)
        event.accept()

    def fini(self):
        '''
        a the end we close all the thread
        '''
        self.thread.stopThread()
        self.statusTimer.stop()
        self.isWinOpen=False
        time.sleep(0.1)
        if self.configWidget.isWinOpen==True:
            self.configWidget.close()

class REF1M(QWidget):
    
    def __init__(self,num=0, parent=None):
        super(REF1M, self).__init__()
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        icon=str(pathlib.Path(__file__).parent) + os.sep + 'icons' + os.sep
        self.wid=QWidget()
        self.id=num
        self.vboxPos=QVBoxLayout()
        
        self.posText=QLineEdit('ref')
        self.posText.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        self.posText.setStyleSheet("font: bold 15pt")
        self.posText.setObjectName('%s'%self.id)
#        self.posText.setMaximumWidth(80)
        self.vboxPos.addWidget(self.posText)
        
        self.take=QPushButton()
        self.take.setObjectName('%s'%self.id)
        self.take.setStyleSheet(f"QPushButton:!pressed{{border-image: url({icon}disquette.png);background-color: rgb(0, 0, 0) ;border-color: green;}}QPushButton:pressed{{image: url({icon}disquette.png);background-color: rgb(0, 0, 0) ;border-color: blue}}")
        self.take.setMaximumWidth(30)
        self.take.setMinimumWidth(30)
        self.take.setMinimumHeight(30)
        self.take.setMaximumHeight(30)
        self.takeLayout=QHBoxLayout()
        self.takeLayout.addWidget(self.take)
        self.Pos=QPushButton()
        self.Pos.setStyleSheet(f"QPushButton:!pressed{{border-image: url({icon}playGreen.png);background-color: rgb(0, 0, 0) ;border-color: green;}}QPushButton:pressed{{image: url({icon}playGreen.png);background-color: rgb(0, 0, 0) ;border-color: blue}}")
        self.Pos.setMinimumHeight(40)
        self.Pos.setMaximumHeight(40)
        self.Pos.setMinimumWidth(40)
        self.Pos.setMaximumWidth(40)
        self.PosLayout=QHBoxLayout()
        self.PosLayout.addWidget(self.Pos)
        self.Pos.setObjectName('%s'%self.id)
        #○self.Pos.setStyleSheet("background-color: rgb(85, 170, 255)")
        Labelref=QLabel('Pos :')
        Labelref.setMaximumWidth(30)
        Labelref.setStyleSheet("font: 9pt" )
        self.ABSref=QDoubleSpinBox()
        self.ABSref.setMaximum(500000000)
        self.ABSref.setMinimum(-500000000)
        self.ABSref.setValue(123456)
        self.ABSref.setMaximumWidth(80)
        self.ABSref.setObjectName('%s'%self.id)
        self.ABSref.setStyleSheet("font: 9pt" )
        
        grid_layoutPos = QGridLayout()
        grid_layoutPos.setVerticalSpacing(5)
        grid_layoutPos.setHorizontalSpacing(10)
        grid_layoutPos.setAlignment(QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter)
        grid_layoutPos.addLayout(self.takeLayout,0,0)
        grid_layoutPos.addLayout(self.PosLayout,0,1)
        grid_layoutPos.addWidget(Labelref,1,0)
        grid_layoutPos.addWidget(self.ABSref,1,1)
        
        
        self.vboxPos.addLayout(grid_layoutPos)
        self.wid.setStyleSheet("background-color: rgb(60, 77, 87);border-radius:10px")
       
        self.wid.setLayout(self.vboxPos)
        mainVert=QVBoxLayout()
        mainVert.addWidget(self.wid)
        mainVert.setContentsMargins(0,0,0,0)
        self.setLayout(mainVert)


class PositionThread(QtCore.QThread):
    '''
    Secon thread  to display the position
    '''
    import time #?
    POS=QtCore.pyqtSignal(float) # signal of the second thread to main thread  to display motors position
    def __init__(self,parent=None,mot='',motorType=''):
        super(PositionThread,self).__init__(parent)
        self.MOT=mot
        self.motorType=motorType
        self.parent=parent
        self.stop=False
    def run(self):
        while True:
            if self.stop==True:
                break
            else:
                Posi=(self.MOT.position())
                time.sleep(0.5)

                try :
                    self.POS.emit(Posi)

                    time.sleep(0.1)

                except:
                    print('error emit')

    def ThreadINIT(self):
        self.stop=False   
                        
    def stopThread(self):
        self.stop=True
        time.sleep(0.1)
        self.terminate()


class LogWindow(QDialog):
    """
    Fenêtre de visualisation des logs
    Affiche les dernières actions du moteur
    """

    def __init__(self, parent=None):
        super(LogWindow, self).__init__(parent)
        self.setWindowTitle("📋 Historique des Actions")
        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        layout = QVBoxLayout()

        title = QLabel("Dernières actions (max 20)")
        title.setStyleSheet("font: bold 12pt; color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        self.logText = QTextEdit()
        self.logText.setReadOnly(True)
        self.logText.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #00ff00;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                border: 2px solid #4a9eff;
                border-radius: 5px;
                padding: 10px;
            }
        """)
        layout.addWidget(self.logText)

        buttonLayout = QHBoxLayout()

        self.refreshButton = QPushButton("🔄 Actualiser")
        self.refreshButton.setMaximumWidth(120)
        self.refreshButton.clicked.connect(self.refresh)

        self.clearButton = QPushButton("🗑️ Effacer")
        self.clearButton.setMaximumWidth(120)
        self.clearButton.clicked.connect(self.clearLogs)

        self.closeButton = QPushButton("✖ Fermer")
        self.closeButton.setMaximumWidth(120)
        self.closeButton.clicked.connect(self.close)

        buttonLayout.addWidget(self.refreshButton)
        buttonLayout.addWidget(self.clearButton)
        buttonLayout.addStretch()
        buttonLayout.addWidget(self.closeButton)

        layout.addLayout(buttonLayout)
        self.setLayout(layout)

    def setLogs(self, logs):
        """Affiche les logs"""
        self.logText.clear()

        if not logs:
            self.logText.setHtml('<span style="color: #ff6b6b;">Aucune action enregistrée</span>')
            return

        html = ""
        for log in logs:
            timestamp = log['timestamp']
            action = log['action']
            details = log.get('details', '')

            if 'absolue move' in action.lower() or 'rmove' in action.lower():
                color = "#4a9eff"
                icon = "→"
            elif 'stop' in action.lower():
                color = "#ff6b6b"
                icon = "⏹"
            elif 'zero' in action.lower():
                color = "#ffd43b"
                icon = "⓪"
            elif 'ref' in action.lower():
                color = "#51cf66"
                icon = "📍"
            elif 'config' in action.lower():
                color = "#51cf66"
                icon = "⚙️"
            else:
                color = "#aaaaaa"
                icon = "•"

            html += f'<span style="color: #888;">[{timestamp}]</span> '
            html += f'<span style="color: {color}; font-weight: bold;">{icon} {action}</span>'
            if details:
                html += f' <span style="color: #ccc;">  {details}</span>'
            html += '<br>'

        self.logText.setHtml(html)
        scrollbar = self.logText.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def refresh(self):
        if self.parent():
            self.parent().refreshLog()

    def clearLogs(self):
        reply = QMessageBox.question(
            self,
            'Effacer les logs ?',
            "Voulez-vous effacer tout l'historique ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            if self.parent():
                self.parent().clearLogs()
            self.logText.setHtml('<span style="color: #ff6b6b;">Logs effacés</span>')


class ConfigMotorWidget(QWidget):
    """Widget de configuration des butées et du step, sauvegardé dans le fichier JSON du moteur"""

    def __init__(self, motor, parent=None):
        super(ConfigMotorWidget, self).__init__()
        self.motor = motor
        self.parent = parent
        self.isWinOpen = False

        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        self.setWindowTitle(f"Configuration Moteur - {self.parent.name[0]}")
        self.setMinimumWidth(450)

        self.paramsWidget = MotorParamsWidget(parent=self.parent)

        self.setup()
        self.loadCurrentValues()

    def setup(self):
        mainLayout = QVBoxLayout()
        mainLayout.setSpacing(12)
        mainLayout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("⚙️ Motor Configuration")
        title.setStyleSheet("font: bold 14pt; color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mainLayout.addWidget(title)

        groupStyle = """
            QGroupBox {
                font: bold 11pt;
                color: #aaaaaa;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """

        infoGroup = QGroupBox("Informations")
        infoGroup.setStyleSheet(groupStyle)
        infoLayout = QVBoxLayout()
        nameLayout = QHBoxLayout()
        nameLabel = QLabel("Nom:")
        nameLabel.setMinimumWidth(100)
        self.nameLineEdit = QLineEdit()
        self.nameLineEdit.setStyleSheet("font: bold 11pt;")
        nameLayout.addWidget(nameLabel)
        nameLayout.addWidget(self.nameLineEdit)
        infoLayout.addLayout(nameLayout)
        numMoteur = self.parent.conf[0].value(self.parent.motor[0]+"/numMoteur", "?")
        rack = self.parent.conf[0].value(self.parent.motor[0]+"/rack", "?")
        rackAddress = moteurTMCL.getRackAddress(rack) if rack != "?" else "?"
        self.axisLabel = QLabel(f"Type: TMCL - Axe: {numMoteur} - Rack: {rack} ({rackAddress}) - Fichier: {os.path.basename(self.parent.configMotName[0])}")
        infoLayout.addWidget(self.axisLabel)
        infoGroup.setLayout(infoLayout)
        mainLayout.addWidget(infoGroup)

        stepGroup = QGroupBox("Step Value")
        stepGroup.setStyleSheet(groupStyle)
        stepLayout = QVBoxLayout()
        stepHelpLabel = QLabel("1 step = ? microns")
        stepHelpLabel.setStyleSheet("color: #888; font-size: 9pt;")
        stepLayout.addWidget(stepHelpLabel)
        stepInputLayout = QHBoxLayout()
        stepLabel = QLabel("Step (µm):")
        stepLabel.setMinimumWidth(100)
        self.stepSpinBox = QDoubleSpinBox()
        self.stepSpinBox.setDecimals(6)
        self.stepSpinBox.setRange(0.000001, 1000.0)
        self.stepSpinBox.setValue(1.0)
        self.stepSpinBox.setSuffix(" µm")
        self.stepSpinBox.setMinimumWidth(150)
        stepInputLayout.addWidget(stepLabel)
        stepInputLayout.addWidget(self.stepSpinBox)
        stepInputLayout.addStretch()
        stepLayout.addLayout(stepInputLayout)
        stepGroup.setLayout(stepLayout)
        mainLayout.addWidget(stepGroup)

        buteesGroup = QGroupBox("Software Limits")
        buteesGroup.setStyleSheet(groupStyle)
        buteesLayout = QVBoxLayout()

        butNegLayout = QHBoxLayout()
        butNegLabel = QLabel("Switch - (step):")
        butNegLabel.setMinimumWidth(100)
        self.butNegSpinBox = QDoubleSpinBox()
        self.butNegSpinBox.setDecimals(2)
        self.butNegSpinBox.setRange(-1e15, 1e15)
        self.butNegSpinBox.setValue(0)
        self.butNegSpinBox.setSuffix(" step")
        self.butNegSpinBox.setMinimumWidth(150)
        butNegLayout.addWidget(butNegLabel)
        butNegLayout.addWidget(self.butNegSpinBox)
        butNegLayout.addStretch()
        buteesLayout.addLayout(butNegLayout)

        butPosLayout = QHBoxLayout()
        butPosLabel = QLabel("Switch + (step):")
        butPosLabel.setMinimumWidth(100)
        self.butPosSpinBox = QDoubleSpinBox()
        self.butPosSpinBox.setDecimals(2)
        self.butPosSpinBox.setRange(-1e15, 1e15)
        self.butPosSpinBox.setValue(100000)
        self.butPosSpinBox.setSuffix(" step")
        self.butPosSpinBox.setMinimumWidth(150)
        butPosLayout.addWidget(butPosLabel)
        butPosLayout.addWidget(self.butPosSpinBox)
        butPosLayout.addStretch()
        buteesLayout.addLayout(butPosLayout)

        buteesGroup.setLayout(buteesLayout)
        mainLayout.addWidget(buteesGroup)

        mainLayout.addStretch()

        buttonLayout = QGridLayout()
        buttonLayout.setSpacing(8)

        self.logButton = QPushButton("📋 Historique")
        self.logButton.setMinimumHeight(35)
        self.logButton.setStyleSheet("padding: 8px; font: 10pt; color: #4a9eff;")
        self.logButton.clicked.connect(self.parent.showLog)

        self.paramsButton = QPushButton("🔧 Paramètres moteur")
        self.paramsButton.setMinimumHeight(35)
        self.paramsButton.setStyleSheet("padding: 8px; font: 10pt; color: #4a9eff;")
        self.paramsButton.clicked.connect(lambda:self.parent.open_widget(self.paramsWidget))

        self.resetButton = QPushButton("🔄 Recharger")
        self.resetButton.setMinimumHeight(35)
        self.resetButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.resetButton.clicked.connect(self.loadCurrentValues)

        self.cancelButton = QPushButton("❌ Annuler")
        self.cancelButton.setMinimumHeight(35)
        self.cancelButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.cancelButton.clicked.connect(self.close)

        self.saveButton = QPushButton("💾 Sauvegarder")
        self.saveButton.setMinimumHeight(35)
        self.saveButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.saveButton.clicked.connect(self.saveConfiguration)

        buttonLayout.addWidget(self.logButton, 0, 0)
        buttonLayout.addWidget(self.paramsButton, 0, 1)
        buttonLayout.addWidget(self.resetButton, 1, 0)
        buttonLayout.addWidget(self.cancelButton, 1, 1)
        buttonLayout.addWidget(self.saveButton, 2, 0, 1, 2)

        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)

    def loadCurrentValues(self):
        try:
            self.nameLineEdit.setText(self.parent.name[0])
            current_step = float(self.parent.stepmotor[0])
            self.stepSpinBox.setValue(current_step)
            self.butNegSpinBox.setValue(float(self.parent.buteNeg[0]))
            self.butPosSpinBox.setValue(float(self.parent.butePos[0]))
            self.parent.addLog("Config", "Valeurs actuelles chargées")
        except Exception as e:
            self.parent.addLog("ERROR Config", f"Erreur chargement: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur:\n{e}")

    def saveConfiguration(self):
        reply = QMessageBox.question(
            self,
            'Sauvegarder la configuration ?',
            "⚠️ Attention! Modifier ces valeurs peut affecter le comportement du moteur.\n\n"
            "Voulez-vous vraiment sauvegarder ces paramètres ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                new_name = self.nameLineEdit.text().strip()
                new_step = float(self.stepSpinBox.value())
                new_but_neg = float(self.butNegSpinBox.value())
                new_but_pos = float(self.butPosSpinBox.value())

                if not new_name:
                    QMessageBox.warning(self, "Erreur",
                                      "Le nom ne peut pas être vide!")
                    return
                if new_but_neg >= new_but_pos:
                    QMessageBox.warning(self, "Erreur",
                                      "La butée négative doit être inférieure à la butée positive!")
                    return
                if new_step <= 0:
                    QMessageBox.warning(self, "Erreur",
                                      "Le step doit être supérieur à 0!")
                    return

                motor0 = self.parent.motor[0]
                conf0 = self.parent.conf[0]
                conf0.setValue(motor0+"/Name", new_name)
                conf0.setValue(motor0+"/stepmotor", new_step)
                conf0.setValue(motor0+"/buteePos", new_but_pos)
                conf0.setValue(motor0+"/buteeneg", new_but_neg)
                conf0.sync()

                self.parent.name[0] = new_name
                self.parent.nom.setText(new_name)
                self.parent.updateWindowTitle()
                self.setWindowTitle(f"Configuration Moteur - {new_name}")
                self.parent.stepmotor[0] = new_step
                self.parent.buteNeg[0] = new_but_neg
                self.parent.butePos[0] = new_but_pos
                self.parent.unit()

                self.parent.addLog("Config",
                    f"⚙️ Sauvegardé - Nom: {new_name}, Step: {new_step:.6f} µm, Butées: [{new_but_neg}, {new_but_pos}]")

                QMessageBox.information(self, "Succès", "✅ Configuration sauvegardée!")
                self.close()

            except Exception as e:
                self.parent.addLog("ERROR Config", f"Erreur: {e}")
                QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def closeEvent(self, event):
        self.isWinOpen = False
        event.accept()


class MotorParamsWidget(QWidget):
    """Widget de configuration avancée des paramètres moteur TMCL (courant, vitesse, accélération, microstep, switchs)"""

    MICROSTEP_VALUES = [1,2,4,8,16,32,64,128,256]

    def __init__(self, parent=None):
        super(MotorParamsWidget, self).__init__()
        self.parent = parent
        self.isWinOpen = False

        self.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyqt6'))
        self.setWindowTitle(f"Paramètres Moteur - {self.parent.name[0]}")
        self.setMinimumWidth(400)

        presetsPath=self.parent.configPath+'motorPresetsTMCL.json'
        self.presets=jsonSettings.openConfig(presetsPath)
        self.presetNames=sorted(self.presets.childGroups())

        self.setup()
        self.loadCurrentValues()

    def setup(self):
        mainLayout = QVBoxLayout()
        mainLayout.setSpacing(12)
        mainLayout.setContentsMargins(15, 15, 15, 15)

        title = QLabel("🔧 Motor Parameters (TMCL)")
        title.setStyleSheet("font: bold 14pt; color: #4a9eff;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mainLayout.addWidget(title)

        groupStyle = """
            QGroupBox {
                font: bold 11pt;
                color: #aaaaaa;
                border: 2px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
        """

        presetGroup = QGroupBox("Bibliothèque de moteurs")
        presetGroup.setStyleSheet(groupStyle)
        presetGroupLayout = QVBoxLayout()

        presetLayout = QHBoxLayout()
        self.presetCombo = QComboBox()
        self.presetCombo.addItem("-- Sélectionner un type de moteur --")
        self.presetCombo.addItems(self.presetNames)
        self.presetCombo.setMinimumWidth(200)
        self.loadPresetButton = QPushButton("📥 Charger")
        self.loadPresetButton.setStyleSheet("padding: 6px; font: 10pt;")
        self.loadPresetButton.clicked.connect(self.loadPreset)
        presetLayout.addWidget(self.presetCombo)
        presetLayout.addWidget(self.loadPresetButton)
        presetGroupLayout.addLayout(presetLayout)

        savePresetLayout = QHBoxLayout()
        self.presetNameEdit = QLineEdit()
        self.presetNameEdit.setPlaceholderText("Nom du type de moteur")
        self.savePresetButton = QPushButton("💾 Sauvegarder nouveau type moteur")
        self.savePresetButton.setStyleSheet("padding: 6px; font: 10pt;")
        self.savePresetButton.clicked.connect(self.savePreset)
        savePresetLayout.addWidget(self.presetNameEdit)
        savePresetLayout.addWidget(self.savePresetButton)
        presetGroupLayout.addLayout(savePresetLayout)

        presetGroup.setLayout(presetGroupLayout)
        mainLayout.addWidget(presetGroup)

        currentGroup = QGroupBox("Courant")
        currentGroup.setStyleSheet(groupStyle)
        currentLayout = QVBoxLayout()

        cmaxLayout = QHBoxLayout()
        cmaxLabel = QLabel("Courant max :")
        cmaxLabel.setMinimumWidth(140)
        self.cmaxSpinBox = QDoubleSpinBox()
        self.cmaxSpinBox.setDecimals(0)
        self.cmaxSpinBox.setRange(0, 255)
        self.cmaxSpinBox.setMinimumWidth(120)
        cmaxLayout.addWidget(cmaxLabel)
        cmaxLayout.addWidget(self.cmaxSpinBox)
        cmaxLayout.addStretch()
        currentLayout.addLayout(cmaxLayout)

        cstandbyLayout = QHBoxLayout()
        cstandbyLabel = QLabel("Courant standby :")
        cstandbyLabel.setMinimumWidth(140)
        self.cstandbySpinBox = QDoubleSpinBox()
        self.cstandbySpinBox.setDecimals(0)
        self.cstandbySpinBox.setRange(0, 255)
        self.cstandbySpinBox.setMinimumWidth(120)
        cstandbyLayout.addWidget(cstandbyLabel)
        cstandbyLayout.addWidget(self.cstandbySpinBox)
        cstandbyLayout.addStretch()
        currentLayout.addLayout(cstandbyLayout)

        currentGroup.setLayout(currentLayout)
        mainLayout.addWidget(currentGroup)

        motionGroup = QGroupBox("Vitesse / Accélération")
        motionGroup.setStyleSheet(groupStyle)
        motionLayout = QVBoxLayout()

        vmaxLayout = QHBoxLayout()
        vmaxLabel = QLabel("Vitesse max :")
        vmaxLabel.setMinimumWidth(140)
        self.vmaxSpinBox = QDoubleSpinBox()
        self.vmaxSpinBox.setDecimals(0)
        self.vmaxSpinBox.setRange(0, 2047)
        self.vmaxSpinBox.setMinimumWidth(120)
        vmaxLayout.addWidget(vmaxLabel)
        vmaxLayout.addWidget(self.vmaxSpinBox)
        vmaxLayout.addStretch()
        motionLayout.addLayout(vmaxLayout)

        amaxLayout = QHBoxLayout()
        amaxLabel = QLabel("Accélération max :")
        amaxLabel.setMinimumWidth(140)
        self.amaxSpinBox = QDoubleSpinBox()
        self.amaxSpinBox.setDecimals(0)
        self.amaxSpinBox.setRange(0, 2047)
        self.amaxSpinBox.setMinimumWidth(120)
        amaxLayout.addWidget(amaxLabel)
        amaxLayout.addWidget(self.amaxSpinBox)
        amaxLayout.addStretch()
        motionLayout.addLayout(amaxLayout)

        pulseLayout = QHBoxLayout()
        pulseLabel = QLabel("Pulse divisor :")
        pulseLabel.setMinimumWidth(140)
        self.pulseDivSpinBox = QDoubleSpinBox()
        self.pulseDivSpinBox.setDecimals(0)
        self.pulseDivSpinBox.setRange(0, 13)
        self.pulseDivSpinBox.setMinimumWidth(120)
        pulseLayout.addWidget(pulseLabel)
        pulseLayout.addWidget(self.pulseDivSpinBox)
        pulseLayout.addStretch()
        motionLayout.addLayout(pulseLayout)

        rampLayout = QHBoxLayout()
        rampLabel = QLabel("Ramp divisor :")
        rampLabel.setMinimumWidth(140)
        self.rampDivSpinBox = QDoubleSpinBox()
        self.rampDivSpinBox.setDecimals(0)
        self.rampDivSpinBox.setRange(0, 13)
        self.rampDivSpinBox.setMinimumWidth(120)
        rampLayout.addWidget(rampLabel)
        rampLayout.addWidget(self.rampDivSpinBox)
        rampLayout.addStretch()
        motionLayout.addLayout(rampLayout)

        microstepLayout = QHBoxLayout()
        microstepLabel = QLabel("Microstep :")
        microstepLabel.setMinimumWidth(140)
        self.microstepCombo = QComboBox()
        for vi in self.MICROSTEP_VALUES:
            self.microstepCombo.addItem(f"{vi} microstep(s)")
        self.microstepCombo.setMinimumWidth(120)
        microstepLayout.addWidget(microstepLabel)
        microstepLayout.addWidget(self.microstepCombo)
        microstepLayout.addStretch()
        motionLayout.addLayout(microstepLayout)

        motionGroup.setLayout(motionLayout)
        mainLayout.addWidget(motionGroup)

        calibGroup = QGroupBox("Calibration")
        calibGroup.setStyleSheet(groupStyle)
        calibLayout = QHBoxLayout()
        stepmotorLabel = QLabel("Step motor :")
        stepmotorLabel.setMinimumWidth(140)
        self.stepmotorSpinBox = QDoubleSpinBox()
        self.stepmotorSpinBox.setDecimals(6)
        self.stepmotorSpinBox.setRange(0.000001, 1000000)
        self.stepmotorSpinBox.setMinimumWidth(120)
        calibLayout.addWidget(stepmotorLabel)
        calibLayout.addWidget(self.stepmotorSpinBox)
        calibLayout.addStretch()
        calibGroup.setLayout(calibLayout)
        mainLayout.addWidget(calibGroup)

        switchGroup = QGroupBox("Switchs de fin de course")
        switchGroup.setStyleSheet(groupStyle)
        switchLayout = QVBoxLayout()
        self.rightSwitchCheck = QCheckBox("Switch droit activé")
        self.leftSwitchCheck = QCheckBox("Switch gauche activé")
        switchLayout.addWidget(self.rightSwitchCheck)
        switchLayout.addWidget(self.leftSwitchCheck)
        switchGroup.setLayout(switchLayout)
        mainLayout.addWidget(switchGroup)

        mainLayout.addStretch()

        buttonLayout = QGridLayout()
        buttonLayout.setSpacing(8)

        self.resetButton = QPushButton("🔄 Recharger")
        self.resetButton.setMinimumHeight(35)
        self.resetButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.resetButton.clicked.connect(self.loadCurrentValues)

        self.cancelButton = QPushButton("❌ Annuler")
        self.cancelButton.setMinimumHeight(35)
        self.cancelButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.cancelButton.clicked.connect(self.close)

        self.saveButton = QPushButton("💾 Sauvegarder et appliquer")
        self.saveButton.setMinimumHeight(35)
        self.saveButton.setStyleSheet("padding: 8px; font: 10pt;")
        self.saveButton.clicked.connect(self.saveParameters)

        buttonLayout.addWidget(self.resetButton, 0, 0)
        buttonLayout.addWidget(self.cancelButton, 0, 1)
        buttonLayout.addWidget(self.saveButton, 1, 0, 1, 2)

        mainLayout.addLayout(buttonLayout)
        self.setLayout(mainLayout)

    def loadCurrentValues(self):
        try:
            conf0 = self.parent.conf[0]
            motor0 = self.parent.motor[0]
            self.cmaxSpinBox.setValue(float(conf0.value(motor0+"/Cmax", 0)))
            self.cstandbySpinBox.setValue(float(conf0.value(motor0+"/Cstandby", 0)))
            self.vmaxSpinBox.setValue(float(conf0.value(motor0+"/Vmax", 0)))
            self.amaxSpinBox.setValue(float(conf0.value(motor0+"/AccMax", 0)))
            self.pulseDivSpinBox.setValue(float(conf0.value(motor0+"/PulseDiv", 0)))
            self.rampDivSpinBox.setValue(float(conf0.value(motor0+"/RampDiv", 0)))
            stepRes = int(conf0.value(motor0+"/stepResolution", 0))
            self.microstepCombo.setCurrentIndex(max(0, min(stepRes, len(self.MICROSTEP_VALUES)-1)))
            self.stepmotorSpinBox.setValue(float(conf0.value(motor0+"/stepmotor", 1)))
            self.rightSwitchCheck.setChecked(bool(conf0.value(motor0+"/rightSwitchEnable", False)))
            self.leftSwitchCheck.setChecked(bool(conf0.value(motor0+"/leftSwitchEnable", False)))
            self.parent.addLog("Config", "Paramètres moteur actuels chargés")
        except Exception as e:
            self.parent.addLog("ERROR Config", f"Erreur chargement paramètres: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur:\n{e}")

    def loadPreset(self):
        """Pré-remplit les champs avec les valeurs de la bibliothèque, sans rien appliquer/sauvegarder"""
        name = self.presetCombo.currentText()
        if name not in self.presetNames:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un type de moteur dans la liste.")
            return
        try:
            self.cmaxSpinBox.setValue(float(self.presets.value(name+"/Cmax", 0)))
            self.cstandbySpinBox.setValue(float(self.presets.value(name+"/Cstandby", 0)))
            self.vmaxSpinBox.setValue(float(self.presets.value(name+"/Vmax", 0)))
            self.amaxSpinBox.setValue(float(self.presets.value(name+"/AccMax", 0)))
            self.pulseDivSpinBox.setValue(float(self.presets.value(name+"/PulseDiv", 0)))
            self.rampDivSpinBox.setValue(float(self.presets.value(name+"/RampDiv", 0)))
            stepRes = int(self.presets.value(name+"/stepResolution", 0))
            self.microstepCombo.setCurrentIndex(max(0, min(stepRes, len(self.MICROSTEP_VALUES)-1)))
            self.stepmotorSpinBox.setValue(float(self.presets.value(name+"/stepmotor", 1)))
            self.presetNameEdit.setText(name)
            self.parent.addLog("Config", f"Preset '{name}' chargé (à confirmer avec Sauvegarder)")
        except Exception as e:
            self.parent.addLog("ERROR Config", f"Erreur chargement preset: {e}")
            QMessageBox.warning(self, "Erreur", f"Erreur:\n{e}")

    def savePreset(self):
        """Sauvegarde les valeurs actuelles du formulaire comme (nouveau) type de moteur dans la bibliothèque"""
        name = self.presetNameEdit.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Veuillez saisir un nom pour ce type de moteur.")
            return
        if name in self.presetNames:
            reply = QMessageBox.question(
                self,
                'Écraser le type existant ?',
                f"Le type de moteur '{name}' existe déjà dans la bibliothèque.\n\n"
                "Voulez-vous écraser ses valeurs avec les valeurs actuelles du formulaire ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        try:
            self.presets.setValue(name+"/Cmax", int(self.cmaxSpinBox.value()))
            self.presets.setValue(name+"/Cstandby", int(self.cstandbySpinBox.value()))
            self.presets.setValue(name+"/Vmax", int(self.vmaxSpinBox.value()))
            self.presets.setValue(name+"/AccMax", int(self.amaxSpinBox.value()))
            self.presets.setValue(name+"/PulseDiv", int(self.pulseDivSpinBox.value()))
            self.presets.setValue(name+"/RampDiv", int(self.rampDivSpinBox.value()))
            self.presets.setValue(name+"/stepResolution", self.microstepCombo.currentIndex())
            self.presets.setValue(name+"/stepmotor", float(self.stepmotorSpinBox.value()))
            self.presets.sync()

            if name not in self.presetNames:
                self.presetNames = sorted(self.presetNames+[name])
                self.presetCombo.clear()
                self.presetCombo.addItem("-- Sélectionner un type de moteur --")
                self.presetCombo.addItems(self.presetNames)
            self.presetCombo.setCurrentText(name)

            self.parent.addLog("Config", f"Type de moteur '{name}' sauvegardé dans la bibliothèque")
            QMessageBox.information(self, "Succès", f"✅ Type de moteur '{name}' sauvegardé!")
        except Exception as e:
            self.parent.addLog("ERROR Config", f"Erreur sauvegarde type moteur: {e}")
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def saveParameters(self):
        reply = QMessageBox.question(
            self,
            'Sauvegarder les paramètres moteur ?',
            "⚠️ Attention! Ces paramètres sont envoyés directement au contrôleur moteur.\n\n"
            "Voulez-vous vraiment sauvegarder et appliquer ces paramètres ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                new_cmax = int(self.cmaxSpinBox.value())
                new_cstandby = int(self.cstandbySpinBox.value())
                new_vmax = int(self.vmaxSpinBox.value())
                new_amax = int(self.amaxSpinBox.value())
                new_pulseDiv = int(self.pulseDivSpinBox.value())
                new_rampDiv = int(self.rampDivSpinBox.value())
                new_stepRes = self.microstepCombo.currentIndex()
                new_stepmotor = float(self.stepmotorSpinBox.value())
                new_rightEnable = self.rightSwitchCheck.isChecked()
                new_leftEnable = self.leftSwitchCheck.isChecked()

                if new_stepmotor <= 0:
                    QMessageBox.warning(self, "Erreur",
                                      "Le step motor doit être supérieur à 0!")
                    return

                motor0 = self.parent.motor[0]
                conf0 = self.parent.conf[0]
                conf0.setValue(motor0+"/Cmax", new_cmax)
                conf0.setValue(motor0+"/Cstandby", new_cstandby)
                conf0.setValue(motor0+"/Vmax", new_vmax)
                conf0.setValue(motor0+"/AccMax", new_amax)
                conf0.setValue(motor0+"/PulseDiv", new_pulseDiv)
                conf0.setValue(motor0+"/RampDiv", new_rampDiv)
                conf0.setValue(motor0+"/stepResolution", new_stepRes)
                conf0.setValue(motor0+"/stepmotor", new_stepmotor)
                conf0.setValue(motor0+"/rightSwitchEnable", new_rightEnable)
                conf0.setValue(motor0+"/leftSwitchEnable", new_leftEnable)
                conf0.sync()

                MOT = self.parent.MOT[0]
                MOT.setCurrent(new_cmax)
                MOT.setStandbyCurrent(new_cstandby)
                MOT.setSpeed(new_vmax)
                MOT.setAcceleration(new_amax)
                MOT.setPulseDiv(new_pulseDiv)
                MOT.setRampDiv(new_rampDiv)
                MOT.setMicrostepResolution(new_stepRes)
                MOT.setRightSwitchEnable(new_rightEnable)
                MOT.setLeftSwitchEnable(new_leftEnable)

                self.parent.stepmotor[0] = new_stepmotor
                self.parent.unit()

                self.parent.addLog("Config",
                    f"🔧 Paramètres moteur appliqués - Cmax:{new_cmax} Cstandby:{new_cstandby} "
                    f"Vmax:{new_vmax} Amax:{new_amax} PulseDiv:{new_pulseDiv} RampDiv:{new_rampDiv} "
                    f"Microstep:{self.MICROSTEP_VALUES[new_stepRes]} Stepmotor:{new_stepmotor} "
                    f"SwitchD:{new_rightEnable} SwitchG:{new_leftEnable}")

                QMessageBox.information(self, "Succès", "✅ Paramètres moteur sauvegardés et appliqués!")
                self.close()

            except Exception as e:
                self.parent.addLog("ERROR Config", f"Erreur paramètres moteur: {e}")
                QMessageBox.critical(self, "Erreur", f"Erreur:\n{e}")

    def closeEvent(self, event):
        self.isWinOpen = False
        event.accept()


if __name__ =='__main__':
    
    appli=QApplication(sys.argv)
    
        
    mot5=ONEMOTORGUI( mot='axe5',rack='rack1',showRef=False,unit=1,jogValue=1)
    mot5.show()
    mot5.startThread2()
    appli.exec()