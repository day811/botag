import os
import re
from botools import Engine, normalize_name, get_error_message, format_to_unixpath, RBException, STARS

import configparser
import keyboard
import argparse

BOTH = 0
CMD_ONLY = 1
INI_ONLY = 2
GENERAL = 'GENERAL'
SCANFILE = 'SCANFILE'
SCANDIR = 'SCANDIR'
AUDIO = 'AUDIO'
LOGS = 'LOGS'
SET_STR = 'str'
SET_PATH = 'path'
SET_BOOL = 'bool'
SET_INT = 'int'


class Setting():

    def __init__(self, section, vartype, location, shortcmd='', default=None, multi=0, helptxt=''):
        """Class des paramètres
        Args:
            section (str): nom de la section dans le fichier ini
            vartype (str): type de paramètres : String, path, integer, boolean
            location (int): visibilité du paramètres : fichier ini, ligne de commande ou les deux
            shortcmd (str, optional): nom de l'option raccourcie en ligne de commande. Defaut : ''.
            default (variant, optional): valeur par défaut du paramètre. Defaut None.
            multi (int, optional): si 1 la valeur est une liste, si 2 le paramètre est sur plusieurs lignes param[0-9]. Defaults to 0.
            helptxt (str, optional): texte d'aide pour la ligne de commande. Defaut ''.
        """
        self.section = section
        self.vartype = vartype
        self.location = location
        self.shortcmd = shortcmd
        self.default = default
        self.multi = multi
        self.helptxt = helptxt
        

class Settings(configparser.ConfigParser):

    params=dict[str,Setting] = {
        'progFileTxt' :  Setting(GENERAL, SET_PATH, INI_ONLY),
        'noAction' : Setting(GENERAL, SET_BOOL, BOTH, shortcmd='-na', default=True, 
                helptxt="(True/False) : si True, exécute le programme sans effectuer aucun changement"),
        'makeDistCopy' :  Setting(GENERAL, SET_BOOL,BOTH, shortcmd='-md', default=True, 
                helptxt="(True/False) : si True, effectue aussi les modifications sur les fichiers distants"),
        'autoCorrectFilename' :  Setting(GENERAL, SET_BOOL,BOTH, shortcmd='-ac', default=False, 
                helptxt="(True/False) : si True, corrige le nom des fichiers si erreur de nommage"),
        'excludedPaths' : Setting(GENERAL, SET_PATH,INI_ONLY, multi=True),
        'testEnv' : Setting(GENERAL, SET_BOOL,BOTH, shortcmd='-te', default=True, 
                helptxt="(True/False) si True, exécution en mode test, l'emplacement des différents chemins est modifié"),
        'changeLimit' : Setting(GENERAL, SET_INT,BOTH, shortcmd='-cl', default=0, 
                helptxt="Limite ne nombre de fichiers audio pouvant être modifié, 0=aucune limite"),
        'syncPath' : Setting(SCANFILE, SET_PATH,BOTH, shortcmd='-sp', default=0, 
                helptxt="Emplacement du fichier ou du répertoire contenant les logs à analyser"),
        'syncSignature' : Setting(SCANFILE, SET_PATH, BOTH, shortcmd='-sp', default=0, 
                helptxt="Expression régulière signature permettant d'identifier les fichiers log"),
        'syncActionLine' : Setting(SCANFILE, SET_PATH, INI_ONLY, multi=2),
        'scanDirectory' : Setting(SCANDIR, SET_BOOL, BOTH, shortcmd='-sd', default=True, 
                helptxt="(True/False) si True, le répertoire racine va être parcouru pour vérifier les fichiers audio"),
        'scanAudioFilter' : Setting(SCANDIR, SET_PATH, BOTH, shortcmd='-af', default='', multi=1,
                helptxt="Filtre les fichiers audio sur leur nome, plusieurs valeurs possible"),
        'scanPathFilter' : Setting(SCANDIR, SET_PATH, BOTH, shortcmd='-pf', default='', multi=1,
                helptxt="Filtre les fichiers audio sur leur emplacement, plusieurs valeurs possible"),
        'allowedExtensions' : Setting(SCANDIR, SET_STR, INI_ONLY, shortcmd='-sd', default='mp3', multi="1") ,
        'localRoot' : Setting(AUDIO, SET_PATH, INI_ONLY),
        'distRoot' : Setting(AUDIO, SET_PATH, INI_ONLY),
        'currentPath' : Setting(AUDIO, SET_PATH, INI_ONLY, default='current\\'),
        'audioSignature' : Setting(AUDIO, SET_STR, INI_ONLY),
        'logScreenLevel' : Setting(LOGS, SET_INT, BOTH, shortcmd='-sl', default=2,
                helptxt="Filtre des messages à l'écran - 0:erreur 1:warning 2:info 3:détaillé 4:complet  -1 : rien du tout"),
        'logFileLevel' : Setting(LOGS, SET_INT, BOTH, shortcmd='-fl', default=3, 
                helptxt="Filtre des messages log -  0:erreur 1:warning 2:info 3:détaillé 4:complet  -1 : rien du tout"),
        'logPath' : Setting(LOGS, SET_PATH, BOTH, shortcmd='-pf', default='', multi=1,
                helptxt="Filtre les fichiers audio sur leur emplacement, plusieurs valeurs possible"),
        'logMask' : Setting(LOGS, SET_STR, INI_ONLY, default='TaggerID3Audio'),
        'logRotation' : Setting(LOGS, SET_BOOL, INI_ONLY, default=True),
        'logLimit' : Setting(LOGS, SET_INT, INI_ONLY, default=30),
    }
    
    def __init__(self):
        super().__init__()
        self.path = __file__.lower().replace('py', 'ini')
        self.read_ini()
        self.initArgsParser()

    def initArgsParser(self):
        parser = argparse.ArgumentParser()
        for attrib in  list(self.params.keys()):
            setting = Settings.params[attrib]
            if setting.location in [BOTH, CMD_ONLY]:
                # configure l'argument de la ligne de commande si attribut est autorisé pour la ligne de commande
                parser.add_argument(setting.shortcmd, '--' + attrib, default=None, help=setting.helptxt)            
        try:
            self.args = parser.parse_args()
        except parser.error:
            quit()

    def read_ini(self):
        bot.info("Chargement fichier de configuration : " + self.path)
        try :
            super().read(self.path, encoding='utf-8')
        except configparser.Error:
            print(f"Erreur fatale lors de la lecture du fichier de configuration {self.path}")
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()

    def unfoldValues(self, values, multi, var_type):
        """ Return formatted strings or list of formatted string from coma separated string  

        Args:
            values (str): Given String with coma separated datas
            multi (int): list if true/1, string if no/0
            var_type (str): format to apply

        Returns:
            value: list or str
        """

        values_list = []
        if multi > 0:
            values = values.split(',')
            for value in values:
                values_list.append(self.formatOption(value, var_type))
            return values_list
        else:
            return self.formatOption(values, var_type)
 
    def formatOption(self, value, var_type):
        if var_type == 'int':
            try:
                value = int(value)
            except ValueError:
                value = None
        elif var_type == 'path':
            value = format_to_unixpath(value, remove_quotes=True)                
        elif var_type == 'bool':
            if value.lower() == 'true': value = True
            elif value.lower() == 'false': value = False
            else : value = None
        return value
   
    def load_multi(self, attrib, setting : Setting):
        if setting.multi == 2:
            lines_list = []
            for i in range(0, 9):
                line = super().get(setting.section, attrib + str(i), raw=True, fallback=setting.default)
                if line:
                    lines_list.append(self.unfoldValues(line,  setting.multi, setting.varType))
                else:
                    break
            values = lines_list
        else:
            values = super().get(setting.section, attrib, raw=True, fallback=setting.default)   
            values = self.unfoldValues(values, setting.multi, setting.varType)    
        return values
    
    def load_attribs(self):

        for attrib in  list(self.params.keys()):
            setting = Settings.params[attrib]
            if setting.location in [BOTH, CMD_ONLY] and self.args.__dict__[attrib]:
                # if cli parameters is present and allowed in CLI mode
                values = self.unfoldValues(self.args.__dict__[attrib], setting.multi, setting.varType)
            elif setting.location in [BOTH, INI_ONLY]:
                # load possibly multiline
                values = self.load_multi(attrib, setting)
            else:
                values = None     
            if values is not None:
                setattr(self, attrib, values) 
            else:
                raise RBException(f'Option {attrib} manquante dans la configuration')                   
        self.root={'local' : self.localRoot, 'distant' : self.distRoot}
        self.audioSignature += r'\.(' + '|'.join(self.allowedExtensions) + r')$'
        self.logSignature =  self.logMask.lower() + r".+\.log"

        #overwrite global for testing mode
        if self.testEnv :
            self.logPath = "C:/Users/yves/Python Sources/RB/Logs/"
            self.syncPath = "C:/Users/yves/Python Sources/RB/Diff/"
            self.root = {'local' : "C:/Users/yves/Python Sources/RB/SyncA/", 'distant' : "C:/Users/yves/Python Sources/RB/SyncB/"}
            self.progFileTxt = "C:/Users/yves/Python Sources/RB/source/emissions_radio-ballade.txt"

 
def load_radioprograms():

    # chaque émissions à une ligne dans le fichier
    # ligne : nomprog, currentStauts, Alias1, Alias2....
    #   nomProg : nom de l'émission
    #   currentStatus : génération fichier current/previous (0: non   1: Oui)
    #   un ou plusieurs alias

    # les noms d'artistes/alias sont normalisés (uniquement alphanum en minuscule et sans accent) pour servir d'index
    # un alias normalisé ne peut remplacer le nom principal normalisé

    prog_dict={}
    try:
        with open(settings.progFileTxt, 'r', -1, "utf-8") as scanLines:
            bot.detail(STARS)
            bot.info(f"OK : Lecture du fichier des émissions de Radio Ballade : {settings.progFileTxt}")
            bot.detail(STARS)
            for line in scanLines:
                elements = line.split(",")
                if not line.startswith('#') and len(elements) > 1 :
                    nom_programme = elements[0]
                    current_status = int(elements[1])==1 # make boolean from 0/1 values

                    # entre le nom en minuscules uniquement alphanum sans accent comme entrée dans le dictionnaire
                    prog_dict[normalize_name(nom_programme)]=(nom_programme, current_status)
                    bot.verbose(f"Entrée nom/défaut émission RB : {normalize_name(nom_programme)} => {nom_programme}, {str(current_status)}")
                    # entre les alias si ils existent
                    for i in range(2, len(elements)):
                        new_index = normalize_name(elements[i])
                        # don't overwrite existing values
                        if new_index not in prog_dict:
                            prog_dict[new_index] = (nom_programme, current_status)
                            bot.verbose(f"Entrée      alias émission RB : {normalize_name(nom_programme)} => {nom_programme}, {str(current_status)}")
            bot.detail()
    except OSError as e:
        bot.error(f"Lecture impossible du fichier des émissions de Radio Ballade : {settings.progFileTxt}")
        bot.error(f"Détail : {e}")
        input("Tapez une touche pour terminer ou fermez cette fenêtre")
        exit()
        return False

    else:
        return prog_dict

# MAIN PROGRAM

try:
    bot = Engine(1, 3)
    settings = Settings()
except RBException as e:
    print(get_error_message())
    quit()
else:
    settings.load_attribs()

with  bot:
    
    bot.start(settings)
    bot.info("Démmarage du taggage synchronisé de Radio Ballade")
    if settings.noAction:
        bot.info("Exécution en mode NoAction : aucun changement effectué")
    bot.info()

    # lecture du fichier des émissions RB
    bot.RBProgs = load_radioprograms()
    
    with bot.scan() as files:
        bot.info()
        if files:
            bot.info(STARS)
            bot.info(f"Traitement des actions pour {str(len(files))} fichier(s)")
            bot.detail(STARS)
            
            for fileID in files:
                bot.info()
                bot.manageAudioSet(fileID)
                if bot.change_count >= settings.changeLimit and settings.changeLimit > 0:
                    bot.info('Le nombre de changements effectués a atteint la limite , relancer pour continuer')
                    break
        else:
            bot.info(STARS)
            bot.info("Aucun fichier audio sélectionné : consulter les logs si ERREUR/WARNING")
            bot.detail(STARS)
        bot.info()

    bot.info("Fin du taggage synchronisé de Radio Ballade")
    bot.info()
    if bot.count_attention > 0 :
        print(STARS)
        print(f"    {bot.count_attention} WARNINGS(S) détecté(s)")
        print(bot.get_levelmessage(1))                
    if bot.count_error > 0 :
        print(STARS)
        print(f"    {bot.count_error} ERREUR(S) détectée(s)")
        print(bot.get_levelmessage(0))                
        print(STARS)
    if settings.logRotation:
        bot.info(f"Démarrage du nettoyage des fichiers log supérieurs à {str(settings.logLimit)} jours")
        bot.rotate()

print("Fin du traitement. Appuyer sur L pour voir le log complet")
print(f'Fichier log : {bot.log_filename}\n')
print("Appuyer sur n'importe quelle touche pour terminer")
while True:
    key = keyboard.read_key()
    if key.lower() == 'l':
        cmd = 'start "" "'+ bot.log_filename +'"' 
        os.system(cmd)
    else:
        exit()