import os
import re
from botools import *
import configparser
import keyboard
import argparse




class Settings(configparser.ConfigParser):

    def __init__(self):
        super().__init__()
        self.path = re.sub('py' , 'ini',__file__, re.IGNORECASE)
        parser = argparse.ArgumentParser()
        parser.add_argument('-s','--scanDirectory',default=None)
        parser.add_argument('-l','--changeLimit',default=None,type=int)
        parser.add_argument('-a','--scanAudioFilter',default=None, type = str)
        parser.add_argument('-p','--scanPathFilter',default=None)
        parser.add_argument('-n','--noAction',default=None)
        self.args = parser.parse_args()
        self.read()
        self.loadConfig()


    def read(self):
        bot.Info("Chargement fichier de configuration : " + self.path)
        try :
            super().read(self.path, encoding='utf-8')
        except:
            bot.Error("Erreur fatale lors de la lecture du fichier de configuration " + self.path)
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()

    def loadConfig(self):

        try:
            self.progFileTxt = self.getOption('GENERAL','progFileTxt','path')
            self.testEnv = self.getOption('GENERAL','testEnv','bool', False)

            self.noAction = self.args.noAction
            if self.noAction:
                self.noAction = self.noAction.lower() != "false"
            else:
                self.noAction = self.getOption('GENERAL','noAction','bool', True)

            self.makeDistCopy = self.getOption('GENERAL','makeDistCopy','bool', True)
            self.autoCorrectFilename = self.getOption('GENERAL','autoCorrectFilename','bool', False)
            self.excludedPaths = self.getOption('GENERAL','excludedPaths','path',multi=True)

            self.changeLimit = self.args.changeLimit
            if not self.changeLimit:
                self.changeLimit = self.getOption('GENERAL','changeLimit', 'int', 0)

            self.syncPath = self.getOption('SCANFILE','syncPath','path')
            self.syncSignature = self.getOption('SCANFILE','syncSignature', raw=True)
            self.syncActionLine = self.getOption('SCANFILE','actionLine',multi=True)

            self.scanDirectory = self.args.scanDirectory
            if self.scanDirectory:
                self.scanDirectory = self.scanDirectory.lower() == "true"
            else:
                self.scanDirectory = self.getOption('SCANDIR','scanDirectory','bool', False)

            self.scanAudioFilter = self.args.scanAudioFilter
            if  self.scanAudioFilter:
                self.scanAudioFilter = re.sub("'|\"",'',self.scanAudioFilter).split(',') 
            else:
                self.scanAudioFilter = self.getOption('SCANDIR','scanAudioFilter',default='', raw=True,multi = True)

            self.scanPathFilter = self.args.scanPathFilter
            if  self.scanPathFilter:
                self.scanPathFilter = self.scanPathFilter.split(',') 
            else:
                self.scanPathFilter = self.getOption('SCANDIR','scanPathFilter',default='', raw=True,multi = True)


            self.allowedExtensions = self.getOption('AUDIO','allowedExtensions','str', 'mp3',multi=True)
            self.root={'local' : self.getOption('AUDIO','localRoot','path'),'distant' : self.getOption('AUDIO','distRoot','path')}
            self.currentPath = self.getOption('AUDIO','currentPath','path',"current/")
            self.audioSignature = self.getOption('AUDIO','audioSignature', raw=True)

            self.logScreenLevel = self.getOption('LOG','screenLevel', 'int', 2)
            self.logFileLevel = self.getOption('LOG','fileLevel', 'int', 3)
            self.logRotation = self.getOption('LOG','rotation','bool', True)
            self.logLimit = self.getOption('LOG','limit', 'int', 30)
            self.logPath = self.getOption('LOG','logPath','path')
            self.logMask = self.getOption('LOG','mask')

        except FileNotFoundError as e:
            print(e)
            bot.Error("Erreur fatale, un paramètre obligatoire est manquant")
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()

        self.logSignature =  self.logMask.lower() + r".+\.log"
        for index,value  in enumerate(self.syncActionLine):
            self.syncActionLine[index] = value.split(";")

        #self.excludedPaths = ["sem#40","notag"]

        #overwrite global for testing mode
        if self.testEnv :
            self.logPath = "C:/Users/yves/Python Sources/RB/Logs/"
            self.syncPath = "C:/Users/yves/Python Sources/RB/Diff/"
            self.root = {'local' : "C:/Users/yves/Python Sources/RB/SyncA/", 'distant' : "C:/Users/yves/Python Sources/RB/SyncB/"}
            self.progFileTxt = "C:/Users/yves/Python Sources/RB/source/emissions_radio-ballade.txt"


    def getOption(self,section,option,varType='str',default=None,multi=False,sep=',',raw=False):
        if varType == 'path':
            raw = True
        values = super().get(section,option,raw=True,fallback=default)
        if values is None:
            bot.Error("Erreur fatale, Option manquante/erronée "+ section + "/" + option)
            raise IndexError("Option manquante/erronée "+ section + "/" + option)
        if multi:
            values = values.split(sep)
        else:
            values = [values]
        for i,value in enumerate(values):
            if varType == 'path':
                values[i] =  value.replace("\\","/")
            elif varType == 'int':
                if value.isdigit():
                    values[i] = int(value)
                elif default is not None:
                    values[i] = default
                else:
                    bot.Error("Erreur fatale section:"+ section + " option:" + option + ", nombre non valide " + value)
                    raise IndexError("Option manquante/erronée "+ section + "/" + option)
            elif varType == 'bool':
                if value.lower() == 'true':
                    values[i] = True
                else:
                    values[i] = False

        # print('')
        if multi:
            return values
        else:
            return values[0]
 
def loadRadioPrograms():

    # chaque émissions à une ligne dans le fichier
    # ligne : nomprog,currentStauts,Alias1,Alias2....
    #   nomProg : nom de l'émission
    #   currentStatus : génération fichier current/previous (0: non   1: Oui)
    #   un ou plusieurs alias

    # les noms d'artistes/alias sont normalisés (uniquement alphanum en minuscule et sans accent) pour servir d'index
    # un alias normalisé ne peut remplacer le nom principal normalisé

    ProgDict={}
    try:
        with open(settings.progFileTxt,'r',-1,"utf-8") as pft:
            bot.Detail('**************************************************************************')
            bot.Info("Lecture du fichier des émissions de Radio Ballade : "+  settings.progFileTxt)
            bot.Detail('**************************************************************************')
            for line in pft:
                elements = line.split(",")
                if not line.startswith('#') and len(elements) > 1 :
                    nomProg = elements[0]
                    currentStatus = int(elements[1])==1 # make boolean from 0/1 values

                    # entre le nom en minuscules uniquement alphanum sans accent comme entrée dans le dictionnaire
                    ProgDict[normalizeName(nomProg)]=(nomProg,currentStatus)
                    bot.Verbose("Entrée nom/défaut émission RB : " + normalizeName(nomProg) + " => " + nomProg + " , "+ str(currentStatus))
                    # entre les alias si ils existent
                    for i in range(2,len(elements)):
                        newIndex = normalizeName(elements[i])
                        # don't overwrite existing values
                        if newIndex not in ProgDict:
                            ProgDict[newIndex]=(nomProg,currentStatus)
                            bot.Verbose("Entrée      alias émission RB : " + newIndex + " => " + nomProg + " , "+ str(currentStatus))
            bot.Detail()
    except:
        bot.Error("Lecture impossible du fichier des émissions de Radio Ballade : " + settings.progFileTxt )
        input("Tapez une touche pour terminer ou fermez cette fenêtre")
        exit()
        return False

    else:
        return ProgDict

# MAIN PROGRAM
with  bot:
    
    settings = Settings()
    
    bot.start(settings)

    bot.Info("Démmarage du taggage synchronisé de Radio Ballade")
    if settings.noAction:
        bot.Info("Exécution en mode NoAction : aucun changement effectué")
    bot.Info()

    # lecture du fichier des émissions RB
    bot.RBProgs = loadRadioPrograms()
    
    with bot.scan() as files:
        bot.Info()
        if files:
            bot.Info('************************************************************')
            bot.Info("Traitement des actions pour " + str(len(files)) + " fichier(s)")
            bot.Detail('************************************************************')
            
            for fileID in files:
                bot.Info()
                bot.launchActions(fileID)
                if bot.changeCount >= settings.changeLimit and settings.changeLimit > 0:
                    bot.Info('Le nombre de changements effectués a atteint la limite , relancer pour continuer')
                    break
        else:
            bot.Info('************************************************************')
            bot.Info("Aucune fichier audio sélectionné : consulter les logs si ERREUR/WARNING")
            bot.Detail('************************************************************')
        bot.Info()

    bot.Info("Fin du taggage synchronisé de Radio Ballade")
    bot.Info()
    if settings.logRotation:
        bot.Info("Démarrage du nettoyage des fichiers log supérieurs à " + str(settings.logLimit) + " jours")
        bot.rotate()

    if bot.countAttention > 0 :
        print("***********************************************************************")
        print(f"    {bot.countAttention} WARNINGS(S) détecté(s)")
        print("***********************************************************************")
    if bot.countError > 0 :
        print("***********************************************************************")
        print(f"    {bot.countError} ERREUR(S) détectée(s)")
        print("***********************************************************************")


print("Fin du traitement. Appuyer sur L pour voir le log complet")
print('Fichier log :' + bot.logFilename + "\n")
print("Appuyer sur n'importe quelle touche pour terminer")
while True:
    key = keyboard.read_key()
    if key.lower() == 'l':

        cmd = 'start "" "'+ bot.logFilename +'"' 
        os.system(cmd)
    else:
        exit()