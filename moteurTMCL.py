# -*- coding: utf-8 -*-
"""
Created on Wed Feb 28 11:43:51 2018
Pilotage des controleurs TMCL TMCM via USB
Pyserial
python 3.X pyQT5
@author: Gautier julien loa
"""


#%% Imports
import serial
from PyQt6.QtWidgets import QMessageBox

from PyQt6 import QtCore
import time
import atexit
import jsonSettings


#%% connexion des ports (chaque moteur est identifié par son rack + son numéro d'axe (0-6) ;
#%% chaque rack a une seule adresse, définie une fois dans racksTMCL.json :
#%% port local : '/dev/ttyACM0' ; port distant (RaspberryPi + ser2net/socat) : 'socket://IP:port')

confTMCL=jsonSettings.openConfig('fichiersConfig/configMoteurTMCL.json') # motor configuration files
racksTMCL=jsonSettings.openConfig('fichiersConfig/racksTMCL.json') # rack -> adresse (IP ou port USB)

def getRackAddress(rackId):
    """
    Retourne l'adresse (port USB local ou socket://IP:port) du rack
    """
    return racksTMCL.value(rackId+'/address')

serialPorts={} # port -> connexion pyserial ouverte (locale ou socket://)
portMutex={} # port -> QMutex dédié à ce port

def closeAllPorts():
    """
    Ferme proprement toutes les connexions ouvertes (appelé à la fermeture du programme,
    avant le démontage des modules, pour éviter les exceptions de finalisation tardive)
    """
    for mys in serialPorts.values():
        try:
            if mys.is_open:
                mys.close()
        except Exception:
            pass

atexit.register(closeAllPorts)

def connectPort(port):
    """
    ouverture (ou réouverture) du port d'un moteur : chemin série local ('/dev/ttyACM0')
    ou url socket série distante ('socket://IP:port', ex. RaspberryPi + ser2net/socat)
    """
    mys=serialPorts.get(port)
    if mys is None:
        mys=serial.serial_for_url(port, do_not_open=True)
        serialPorts[port]=mys
    try:
        mys.baudrate=9600
        mys.timeout=1
        if mys.is_open==False:
            mys.open()
        else:
            mys.close()
            time.sleep(0.1)
            mys.open()
        print ('TMCM connected on port :',port)
    except Exception as e:
        print('TMCM on port',port,'not connected :',e)
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setText("Error connexion TMCL")
        msg.setInformativeText(f"Error connexion TMCL port {port} please chek connexion or restart computeur")
        msg.setWindowTitle("Warning ...")
        msg.setWindowFlags(QtCore.Qt.WindowType.WindowStaysOnTopHint)
        msg.exec()
    return mys

def getConnection(port):
    """
    Retourne la connexion série ouverte pour ce port (l'ouvre si besoin)
    """
    mys=serialPorts.get(port)
    if mys is None or mys.is_open==False:
        mys=connectPort(port)
    mutex=portMutex.setdefault(port, QtCore.QMutex())
    return mys, mutex


#%% fonction for send and receive data
def sendCommand(instruction, instr_type, mii, values_list, port):
    """
    Envoyer une commande au controleur
    'ROR':1, 'ROL':2, 'MST':3, 'MVP':4, 'SAP':5, 'GAP':6,
            'STAP':7, 'RSAP':8, 'SGP':9, 'GGP':10, 'RFS':13, 'SIO':14, 'GIO':15, 'WAIT':27, 'STOP':28,
                'SCO':30, 'GCO':31, 'CCO':32, 'VER':136, 'RST':255}
    """

    if len(values_list) > 4:
        print ("Command error: "+str(values_list).encode('hex'))

    cmd = bytearray([0x01, instruction, instr_type, mii, 0x00, 0x00, 0x00, 0x00, 0x00])
    values_list.reverse()
    ii = 7
    for vii in values_list:
        cmd[ii] =( vii)
        ii = ii-1

        cmd[8] = sum(cmd[0:8])&0xff

    mys, mutex = getConnection(port)
    mutex.lock()
    mys.write(cmd)
    time.sleep(0.02)
    out = mys.read(9)
    time.sleep(0.02)
    mutex.unlock()
    return bytearray(out)


def Format(value):
    """
    Met au format hex la valuer de la commande"
    """
    return [(value>>24), ((value>>16)&0xff), ((value>>8)&0xff), (value&0xff)]



#%% initialisation of all the motor

def ini(motor=0):
    """ intitialisation of one motor
    """
    Vmax=int(confTMCL.value(motor+'/Vmax'))#1142
    Cmax=int(confTMCL.value(motor+'/Cmax'))
    Cstby=int(confTMCL.value(motor+'/Cstandby'))
    pulseD=int(confTMCL.value(motor+'/PulseDiv'))
    rampD=int(confTMCL.value(motor+'/RampDiv'))
    Amax=int(confTMCL.value(motor+'/AccMax'))
    stepResol=int(confTMCL.value(motor+'/stepResolution')) # step resolution (0-8)
    Mot=int(confTMCL.value(motor+'/numMoteur'))
    port=getRackAddress(confTMCL.value(motor+'/rack'))

    cmd=5 # Set Axis parameter
    Type=6 # max current
    value = Format(Cmax)
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=7 # standby current
    value = Format(Cstby)
    out = sendCommand(cmd,Type,Mot,value,port)

    rightSwEnable=bool(confTMCL.value(motor+'/rightSwitchEnable', False))
    leftSwEnable=bool(confTMCL.value(motor+'/leftSwitchEnable', False))

    cmd=5 # Set Axis parameter
    Type=4 # Max speed
    value =Format(Vmax)
    #print value
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=5 # Max acceleration
    value =Format(Amax)
    #print value
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=154 # pulse divisor 154
    value =Format(pulseD)
    #print value
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=153 # ramp divisor 153
    value =Format(rampD)
    #print value
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=12 # right limit switch disable
    value =Format(0 if rightSwEnable else 1)
    #print value
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=13 # left limit switch disable
    value =Format(0 if leftSwEnable else 1)
    #print value
    out = sendCommand(cmd,Type,Mot,value,port)

    cmd=5 # Set Axis parameter
    Type=140 # set step resolution
    value=Format(stepResol) # entre 0 et 8 = entre 1 et 256
    out = sendCommand(cmd,Type,Mot,value,port)
    #print (" motor TMCL inititalisation :  ",motor)

def iniTot():
    """ initialisation of all the motor present in the config.ini file
    """
    print('intialisation of all TMCL motors')
    groups=confTMCL.childGroups()
    for vi in groups:
        time.sleep(0.05)
        ini(vi)
    print('initialisation TMCL :OK')

# iniTot() # initialisation de tous les moteurs

#%% class TMCL motor
class MOTORTMCL():

    def __init__(self, mot1='',parent=None):
        #super(MOTORTMCL, self).__init__()
        self.moteurname=mot1
        self.numMoteur=int(confTMCL.value(self.moteurname+'/numMoteur'))
        self.rack=confTMCL.value(self.moteurname+'/rack')
        self.port=getRackAddress(self.rack)
        ini(motor=self.moteurname)
    def position(self):
        """
        position du motor"
        """
        cmd=6
        Type=1
        value=[0]

        out2 = sendCommand(cmd,Type,self.numMoteur,value,self.port)
        #out2 = receiveData()
        try:
            pos= int(out2[4]<<24) + int(out2[5]<<16) + int(out2[6]<<8) + int(out2[7])
        except:
            pos=0
        if  pos> 0x80000000: pos = pos - 0xffffffff
        return int(pos)

    def getSupplyVoltage(self):
        """
        Tension d'alimentation moteur mesurée (GIO port 8, banque 1 = analogique)
        Retourne la valeur en dixièmes de volt (ex: 240 = 24.0V, ~5-7 si alim coupée)
        """
        cmd=15 # GIO
        Type=8 # port 8 = tension moteur (analogique)
        bank=1 # banque analogique
        value=[0]
        out2 = sendCommand(cmd,Type,bank,value,self.port)
        try:
            volt= int(out2[4]<<24) + int(out2[5]<<16) + int(out2[6]<<8) + int(out2[7])
        except:
            volt=0
        return volt

    def getRightSwitchStatus(self):
        """
        Etat du switch de fin de course droit (GAP axis param 10)
        """
        cmd=6 # GAP
        Type=10 # right limit switch status
        value=[0]
        out2 = sendCommand(cmd,Type,self.numMoteur,value,self.port)
        try:
            state= int(out2[4]<<24) + int(out2[5]<<16) + int(out2[6]<<8) + int(out2[7])
        except:
            state=0
        return bool(state)

    def getLeftSwitchStatus(self):
        """
        Etat du switch de fin de course gauche (GAP axis param 11)
        """
        cmd=6 # GAP
        Type=11 # left limit switch status
        value=[0]
        out2 = sendCommand(cmd,Type,self.numMoteur,value,self.port)
        try:
            state= int(out2[4]<<24) + int(out2[5]<<16) + int(out2[6]<<8) + int(out2[7])
        except:
            state=0
        return bool(state)

    def move(self,pos=0,vitesse=10000):
        cmd=4 #(MVP Move to position"#
        Type=0 # Abolute
        pos=int(pos)
        print (self.moteurname, "move to",pos)
        if pos >2000000000 or pos<-2000000000 :
            print ( "number of step to high")
        else :
            if pos < 0: pos = pos+0xffffffff
            value = Format(pos)
            out = sendCommand(cmd,Type,self.numMoteur,value,self.port)

    def rmove(self,pos=0,vitesse=10000):
        cmd = 4
        Type = 1
        pos=int(pos)
        if pos >2000000000 or pos<-2000000000 :
            print ("number of step to high")
        else :
            print (self.moteurname, "relative move of ",pos )
            if pos < 0: pos = pos+0xffffffff
            value = Format(pos)
            out = sendCommand(cmd,Type,self.numMoteur,value,self.port)


    def stopMotor(self):
        cmd = 3 # "Motor stop"
        Type = 0
        value =Format(0)
        out = sendCommand(cmd,Type,self.numMoteur,value,self.port)
        print (self.moteurname,"stopped")

    def setzero(self):
        print ("motor",self.moteurname,"set to Zero")
        cmd= 5 #set Axis Parameter
        Type= 1 # Set Actual Postion Bizarre ....
        value = [0]
        out = sendCommand(1,0,self.numMoteur,[0],self.port) #velocity =0s
        out = sendCommand(cmd,Type,self.numMoteur,value,self.port)

    def setAxisParam(self,paramType,value):
        """
        Set Axis Parameter (SAP) générique
        """
        cmd=5
        out = sendCommand(cmd,paramType,self.numMoteur,Format(int(value)),self.port)

    def setCurrent(self,cmax):
        self.setAxisParam(6,cmax) # max current

    def setStandbyCurrent(self,cstandby):
        self.setAxisParam(7,cstandby) # standby current

    def setSpeed(self,vmax):
        self.setAxisParam(4,vmax) # max speed

    def setAcceleration(self,amax):
        self.setAxisParam(5,amax) # max acceleration

    def setPulseDiv(self,pulseDiv):
        self.setAxisParam(154,pulseDiv)

    def setRampDiv(self,rampDiv):
        self.setAxisParam(153,rampDiv)

    def setMicrostepResolution(self,stepResolution):
        self.setAxisParam(140,stepResolution) # 0-8 => 1-256 microsteps

    def setRightSwitchEnable(self,enable):
        self.setAxisParam(12,0 if enable else 1) # right limit switch disable

    def setLeftSwitchEnable(self,enable):
        self.setAxisParam(13,0 if enable else 1) # left limit switch disable


if __name__ == "__main__":
    print("test")


#%% not used:


##def sendCommand(cmd,Type,motor,value):
##    adr = 1
##    tmp = struct.pack('BBBBi', adr, cmd, Type, motor, value)
##    checksum=sum(struct.unpack('BBBBBBBB',tmp))
##    TxBuffer=struct.pack('>BBBBiB',adr,cmd,Type,motor,value,checksum)
##    print TxBuffer
##    return mys.write(TxBuffer)

#def receiveData():
#    RxBuffer = mys.read(9)
#    if RxBuffer.__len__() == 9:
#        data = struct.unpack('>BBBBiB', RxBuffer)
#
#        return data
#    else:
#        print ("error recieve data TMCL")

#def allPosition():
#groups=confTMCL.childGroups()
#M={}
#for vi in groups:
#    time.sleep(0.05)
#    M[str(vi)]=position(vi)
#foldername=time.strftime("%Y_%m_%d")
#if not os.path.isdir(foldername):
#        os.mkdir(foldername)
#fichier=open(foldername+'/'+'sauvPosition.txt','a')
#fichier.write(time.strftime("%A %d %B %Y %H:%M:%S"))
#fichier.write(repr(M))
#fichier.write("\n")
#fichier.close()
#return M
