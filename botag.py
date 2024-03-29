import os
import re
from botools import *
import configparser
import keyboard
import argparse

_BOTH = 0
_CMD_ONLY = 1
_INI_ONLY = 2


class Settings(configparser.ConfigParser):

    configsList = {'section' : None,'varType' : 'str', 'location' : _INI_ONLY, 'shortCmd' : '','default' : None,'multi' : 0,'helpTxt' : ''}
    attribsList = { 
        'progFileTxt' : {'section' :'GENERAL', 'varType' : 'path','location' : _INI_ONLY} ,
        'noAction' : {'section' :'GENERAL', 'varType' : 'bool','location' : _BOTH,'shortCmd' : '-na', 'default' : 0, 'helpTxt' : "(True/False) : si True, exécute le programme sans effectuer aucun changement"} ,
        'makeDistCopy' : {'section' :'GENERAL', 'varType' : 'bool','location' : _BOTH,'shortCmd' : '-md', 'default' : True,'helpTxt' : "(True/False) : si True, effectue aussi les modifications sur les fichiers distants"} ,
        'autoCorrectFilename' : {'section' :'GENERAL', 'varType' : 'bool','location' : _BOTH,'shortCmd' : '-ac','helpTxt' : "Emplacement"} ,
        'excludedPaths' : {'section' :'GENERAL', 'varType' : 'path','location' : _INI_ONLY, 'multi' : 1, 'default' : '@'} ,
        'testEnv' : {'section' :'GENERAL', 'varType' : 'bool','location' : _BOTH,'shortCmd' : '-te', 'default' : True,'helpTxt' : "(True/False) si True, exécution en mode test, l'emplacement des différents chemins est modifié"} ,
        'changeLimit' : {'section' :'GENERAL', 'varType' : 'int','location' : _BOTH,'shortCmd' : '-cl', 'default' : 0,'helpTxt' : "Limite ne nombre de fichiers audio pouvant être modifié, 0 = aucune limite"} ,
        'syncPath' : {'section' :'SCANFILE', 'varType' : 'path','location' : _BOTH,'shortCmd' : '-sp','helpTxt' : "Emplacement du fichier ou du répertoire contenant les logs à analyser"} ,
        'syncSignature' : {'section' :'SCANFILE', 'varType' : 'str','location' : _BOTH,'shortCmd' : '-ss','helpTxt' : "signature permettant d'identifier les fichiers log"} ,
        'syncActionLine' : {'section' :'SCANFILE', 'varType' : 'str','location' : _INI_ONLY, 'multi' : 2} ,
        'scanDirectory' : {'section' :'SCANDIR', 'varType' : 'bool','location' :  _BOTH,'shortCmd' : '-sd','helpTxt' : "(True/False) si True, le répertoire racine va être parcouru pour vérifier les fichiers audio"} ,
        'scanAudioFilter' : {'section' :'SCANDIR', 'varType' : 'path','location' :  _BOTH,'shortCmd' : '-af', 'multi' : 1, 'default' : '','helpTxt' : "Filtre les fichiers audio sur leur nome, plusieurs valeurs possible "} ,
        'scanPathFilter' : {'section' :'SCANDIR', 'varType' : 'path','location' :  _BOTH,'shortCmd' : '-pf', 'multi' : 1, 'default' : '','helpTxt' : "Filtre les fichiers audio sur leur emplacement, plusieurs valeurs possible " } ,
        'allowedExtensions' : {'section' :'AUDIO', 'varType' : 'str','location' : _INI_ONLY, 'multi' : 1, 'default' : 'mp3'} ,
        'localRoot' : {'section' :'AUDIO', 'varType' : 'path','location' : _INI_ONLY} ,
        'distRoot' : {'section' :'AUDIO', 'varType' : 'path','location' : _INI_ONLY} ,
        'currentPath' : {'section' :'AUDIO', 'varType' : 'path','location' : _INI_ONLY, 'default' : 'current'} ,
        'audioSignature' : {'section' :'AUDIO', 'varType' : 'str','location' : _INI_ONLY} ,
        'logScreenLevel' : {'section' :'LOGS', 'varType' : 'int','location' : _BOTH,'shortCmd' : '-sl', 'default' : 2,'helpTxt' : "Filtre des messages à l'écran - 0:erreur 1:warning 2:info 3:détaillé 4:complet  -1 : rien du tout"} ,
        'logFileLevel' : {'section' :'LOGS', 'varType' : 'int','location' : _BOTH,'shortCmd' : '-fl', 'default' : 3,'helpTxt' : "Filtre des messages log -  0:erreur 1:warning 2:info 3:détaillé 4:complet  -1 : rien du tout"} ,
        'logPath' : {'section' :'LOGS', 'varType' : 'path','location' : _BOTH,'shortCmd' : '-lp', 'default' : 3,'helpTxt' : "Sélectionne le fichier log ou le répertoire contenant les logs"} ,
        'logMask' : {'section' :'LOGS', 'varType' : 'str','location' : _INI_ONLY, 'default' : 'TaggerID3Audio'} ,
        'logRotation' : {'section' :'LOGS', 'varType' : 'bool','location' : _INI_ONLY, 'default' : True} ,
        'logLimit' : {'section' :'LOGS', 'varType' : 'int','location' : _INI_ONLY, 'default' : 30} ,
    }
    def __init__(self):
        super().__init__()
        self.path = re.sub(r'py' , 'ini',__file__, re.IGNORECASE)
        self.read()
        self.initArgsParser()

    def initArgsParser(self):
        parser = argparse.ArgumentParser()
        for attrib in  list(self.attribsList.keys()):
            config = Settings.attribsList[attrib]
            for field in list(Settings.configsList.keys()):
                #initialise les champs manquants
                if not field in config: 
                    config[field] = Settings.configsList[field]
            if config['location'] in [_BOTH,_CMD_ONLY]:
                # configure l'argument de la ligne de commande si attribut est autorisé pour la ligne de commande
                parser.add_argument(config['shortCmd'], '--' + attrib, default=None,help=config['helpTxt'])            
        try:
            self.args = parser.parse_args()
        except:
            quit()
        

    def read(self):
        bot.Info("Chargement fichier de configuration : " + self.path)
        try :
            super().read(self.path, encoding='utf-8')
        except:
            print("Erreur fatale lors de la lecture du fichier de configuration " + self.path)
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()

    def unfoldValues(self,values,multi,varType):
        valuesList = []
        if multi > 0:
            values = values.split(',')
            for value in values:
                valuesList.append(self.formatOption(value,varType))
            return valuesList
        else:
            return self.formatOption(values,varType)
 
    def formatOption(self,value,varType):
        if varType == 'int':
            try:
                value = int(value)
            except:
                value = None
        elif varType == 'path':
            value = formatToUnixPath(value,removeQuotes=True)                
        elif varType == 'bool':
            if value.lower() == 'true': value = True
            elif value.lower() == 'false': value = False
            else : value = None
        return value

    def loadAttribs(self):
        for attrib in  list(self.attribsList.keys()):
            config = Settings.attribsList[attrib]
            if config['location'] in [_BOTH,_CMD_ONLY] and self.args.__dict__[attrib]:
                values = self.unfoldValues(self.args.__dict__[attrib],config['multi'],config['varType'])
            elif config['location'] in [_BOTH,_INI_ONLY]:
                if config['multi'] == 2:
                    linesList = []
                    for i in range(0,9):
                        line = super().get(config['section'],attrib + str(i),raw=True,fallback=config['default'])
                        if line:
                            linesList.append(self.unfoldValues(line, config['multi'], config['varType']))
                        else:
                            break
                    values = linesList
                else:
                        values = super().get(config['section'],attrib,raw=True,fallback=config['default'])   
                        values = self.unfoldValues(values, config['multi'], config['varType'])    
            else:
                values = None     
            if values is not None:
                setattr(self,attrib, values) 
            else:
                raise Exception(f'Option {attrib} manquante dans la configuration')                   
        self.root={'local' : self.localRoot,'distant' : self.distRoot}
        self.audioSignature += r'\.(' + '|'.join(self.allowedExtensions) + r')$'
        self.logSignature =  self.logMask.lower() + r".+\.log"

        #overwrite global for testing mode
        if self.testEnv :
            self.logPath = "C:/Users/yves/Python Sources/RB/Logs/"
            self.syncPath = "C:/Users/yves/Python Sources/RB/Diff/"
            self.root = {'local' : "C:/Users/yves/Python Sources/RB/SyncA/", 'distant' : "C:/Users/yves/Python Sources/RB/SyncB/"}
            self.progFileTxt = "C:/Users/yves/Python Sources/RB/source/emissions_radio-ballade.txt"

 
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
        with open(settings.progFileTxt,'r',-1,"utf-8") as scanLines:
            bot.Detail('**************************************************************************')
            bot.Info("OK : Lecture du fichier des émissions de Radio Ballade : "+  settings.progFileTxt)
            bot.Detail('**************************************************************************')
            for line in scanLines:
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

try:
    settings = Settings()
except Exception as e:
    print(getErrorMmessage())
    quit()
else:
    settings.loadAttribs()

with  bot:
    
    
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
                bot.manageAudioSet(fileID)
                if bot.changeCount >= settings.changeLimit and settings.changeLimit > 0:
                    bot.Info('Le nombre de changements effectués a atteint la limite , relancer pour continuer')
                    break
        else:
            bot.Info('************************************************************')
            bot.Info("Aucun fichier audio sélectionné : consulter les logs si ERREUR/WARNING")
            bot.Detail('************************************************************')
        bot.Info()

    bot.Info("Fin du taggage synchronisé de Radio Ballade")
    bot.Info()
    if bot.countAttention > 0 :
        print("***********************************************************************")
        print(f"    {bot.countAttention} WARNINGS(S) détecté(s)")
        print(bot.getlevelMessage(1))                
#        print("***********************************************************************")
    if bot.countError > 0 :
        print("***********************************************************************")
        print(f"    {bot.countError} ERREUR(S) détectée(s)")
        print(bot.getlevelMessage(0))                
        print("***********************************************************************")
    if settings.logRotation:
        bot.Info("Démarrage du nettoyage des fichiers log supérieurs à " + str(settings.logLimit) + " jours")
        bot.rotate()



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