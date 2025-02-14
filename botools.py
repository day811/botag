import os
import shutil
from typing import Any
import unicodedata
import subprocess
import mutagen
from mutagen import MutagenError
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from datetime import datetime , timedelta
import re ,  sys, traceback
from botag import bot

# CONSTANTS

settings = None
STARS = '************************************************************'
ARTIST = 'artist'
YEAR = 'date'
TRACK = 'tracknumber'
LENGTH = 'length'
RAW_TITLE = 'rawtitle'
NORM_FILNAME = 'normfilename'
TITLE = 'title'
MODEL = 'model'
SHORT_MODEL = 'shortMod'
CURRENT = 'current'
PREVIOUS = 'previous'
LOCAL = 'local'
DISTANT = 'distant'
SOURCE = 'source'
ID = 'id'
FILENAME = 'filename'
RELPATH = 'relpath'
EXT = 'extension'
PHY_MODELS = { SOURCE : '', CURRENT : "C#", PREVIOUS : "P#"}
CURRENT_PREVIOUS = [CURRENT, PREVIOUS]
ALL_ROOTS = [LOCAL, DISTANT]
SMALLER = 1
BIGGER = 2
EQUAL = 3
SIMILAR = 4

ALL_KEYS = {FILENAME : ['F:', FILENAME], ARTIST : ['A:', 'Artiste'], YEAR: ['Y:','Année'], TRACK: ['P:','Piste'],
            TITLE: ['T:', 'Titre'], LENGTH: ['L:','Longuer'], RAW_TITLE: ['C','Titre court'],
            MODEL : ['',''], ID : ['',''], NORM_FILNAME : None, EXT : ['Ex','Extension']}
READ_FILE_KEYS = [ARTIST, YEAR, TRACK, TITLE, LENGTH]
SAVE_FILE_KEYS = [ARTIST, YEAR, TRACK, TITLE]
READ_FILENAME_KEYS = [ARTIST, YEAR, TRACK, RAW_TITLE, EXT]
TITLE_SUM_KEYS = {
    SOURCE : [YEAR, TRACK, LENGTH, RAW_TITLE],
    CURRENT : [SHORT_MODEL, YEAR, TRACK, LENGTH, RAW_TITLE],
    PREVIOUS : [SHORT_MODEL, YEAR, TRACK, LENGTH, RAW_TITLE],
    }
CALC_FILENAME={
    SOURCE : [ARTIST, YEAR, TRACK, RAW_TITLE],
    CURRENT : [ARTIST, MODEL],
    PREVIOUS : [ARTIST, MODEL]
}
EXCLUDE_FROM_TITLE = ['0000', '00', '', None]
ID_KEYS = [YEAR, TRACK, RAW_TITLE]

# FUNCTIONS

def get_error_message():
    exc_type, exc_value, exc_tb = sys.exc_info()
    stack_summary = traceback.extract_tb(exc_tb)
    end = stack_summary[-1]

    err_type = type(exc_type).__name__
    err_msg = str(exc_value)
    message = f"{err_type} dans {end.filename} / {end.name} en line {end.lineno} \nwith the error message: {err_msg}.\n"
    message += f"Message d'erreur : {err_msg} / Code reponsable: {end.line!r}"
    return message

def format_to_unixpath(path: str, is_dir=False, reverse = False, remove_quotes = False):
    path = path.replace('\n','')
    if remove_quotes:
        path = path.replace('"|\'','')
        
    from_sep = "\\"
    to_sep = "/"
    if reverse:
        from_sep = '/'
        to_sep = r'\\'
    new_path =  path.replace(from_sep, to_sep)
    if is_dir and not new_path.endswith(to_sep) : 
        new_path += to_sep
    return new_path

def normalize_name(a) -> str:
    """ retoune une chaine de caractères uniquement alphanumérique en minuscule et sans accent ni espace."""
    return re.sub(r'[\W_]+', '', remove_accents(a.lower()))

def remove_accents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')

def str_compare(a, b) -> int:
    if a == b: 
        return EQUAL
    if (normalize_name(a) == normalize_name(b)):
        return SIMILAR
    if a > b:
        return BIGGER
    else:
        return SMALLER

def split_filepath(full_pathname):
    global settings
    path_tab = full_pathname.rsplit('/', maxsplit=1)
    path = path_tab[0]+'/'
    filename = path_tab[1]
    find = '(' + '|'.join(settings.root[x] for x in settings.root)+ r')(.*)'
    match = re.search(find, path, re.I)
    if match:
        relpath = match.group(2)
        return relpath, filename
    else:
        return None, None

def format_lasting(lasting):
    """ convert time in sec into time mmm:ss """
    length = float(lasting)
    minutes = "{:02d}".format(int(length // 60))
    seconds = "{:02d}".format(int(round(length % 60)))
    return  ":".join([minutes, seconds]) 

def format_field(func):
    """ formatte les clés (tag) """
    def inner(*args, **kwargs):
        value = func(*args, **kwargs)
        key = args[1]
        make_filter = False
        if 'makeFilter' in  kwargs:
            make_filter = kwargs['makeFilter']
        if key == YEAR:
            return "{:04.0f}".format(int(value))
        elif key == TRACK:
            if value == '': 
                value = "0"
            return "{:02.0f}".format(int(value))
        elif key == LENGTH:
            if make_filter: wrapper = [r'\(', r'\)']
            else: wrapper = ['(',')']
            return value.join(wrapper)
        return value
    return inner

# ExceptionS
    
class BTException(Exception):
    def __init__(self, message) -> None:
        super().__init__(message)

class BTFileNotFound(BTException):
    def __init__(self, filepath) -> None:
        message = f'Fichier audio {filepath} inexistant'
        super().__init__(message)

class BTArtistNotFound(BTException):
    def __init__(self, artist) -> None:
        message = f"L'artiste : {artist} n'existe pas"
        super().__init__(message)

class BTTagError(BTException):
    def __init__(self, model, root) -> None:
        filename = bot.audio.get_full_filepath(model, root)
        message = f'lors de l\'écriture des tags dans {filename}'
        super().__init__(message)

class BTCopyError(BTException):
    def __init__(self, from_file, to_file) -> None:
        message = f'lors de la copie du fichier {from_file} vers {to_file}'
        super().__init__(message)

class BTMoveError(BTException):
    def __init__(self, from_file, to_file, e) -> None:
        message = f'lors du déplacement du fichier {from_file} vers {to_file}\nDétail : {e}'
        super().__init__(message)

# Classes

class Logger():
    
    def __init__(self, screen_level, file_level) -> None:

        self.wrapper = None
        self.log_filename = None
        self.screen_level = screen_level
        self.file_level = file_level
        self.count_attention = 0
        self.count_error = 0
        self.count_line = 0
        self.history = []
        self.time_stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.change_count = 0
 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
        return False
    
    def open(self):

        try:
            self.wrapper = open(self.log_filename ,"w", encoding="utf-8")
        except OSError as e :
            print(f"Création impossible du fichier des logs : {self.log_filename}" )
            print(f"Détail : {e}")
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()
        else:
            return True        

    def write_logs(self):

        self.wrapper.write("\tCréation du fichier log " + self.log_filename+ '\n')
        for message in self.history:
            if message[0] <= self.file_level: 
                self.wrapper.write("{:05.0f}".format(message[2]) + f' : {message[1]}' )
        if self.count_attention + self.count_error >0:
            self.wrapper.write("\nLISTES DES ERREURS / ATTENTIONS\n")
            self.wrapper.write(self.get_levelmessage(1))
            self.wrapper.write(self.get_levelmessage(0))
        self.history = None
    
    def close(self):
        
        """ Compute some counts and close the logfile
        """
        
        if self.history is not None and self.log_filename is not None:
            if self.count_error:
                self.log_filename += '_[ERREUR]'
            elif self.count_attention:
                self.log_filename += '_[ATTENTION]'
            self.log_filename +='.log'
            if self.open():
                self.write_logs()
                self.wrapper.close()
    
    def get_levelmessage(self, level):
        res = ''
        for message in bot.history:
            if message[0] == level:
                res += message[1]                
        return res
    
    def start(self, _setting):
        global settings
        settings = _setting

        self.scan_list = {_setting.logPath:_setting.logMask, _setting.syncPath : _setting.syncSignature}
        self.screen_level = _setting.logScreenLevel
        self.file_level = _setting.logFileLevel
        if self.file_level > 0:
            self.log_filename = _setting.logPath + _setting.logMask + '_' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.info('Logger démarré')

    def rotate_file(self, file, directory, signature):
        limit_date = datetime.now() - timedelta(days=settings.logLimit)

        if re.search(signature, file, re.IGNORECASE):
            self.verbose(f"Analyse fichier sélectionné {file}")
            tsf = datetime.fromtimestamp(os.path.getmtime(directory + file)) # get timestamp
            if tsf < limit_date:
                if not settings.noAction:
                    os.remove(directory + file)
                    self.detail(f"Suppression du fichier log {directory}/{file}")
                else :
                    self.detail(f"NoAction : Non Suppression du fichier log {directory}/{file}")
            else:
                self.verbose(f'Fichier conservé :{file}')

    
    def rotate(self):
        """ erase old files log """
        for directory, signature in self.scan_list.items():
            self.detail("Analyse répertoire {directory}")
            self.verbose("Signature " + signature)
            files_list = os.listdir(directory)
            for file in files_list:
                self.rotate_file(file, directory , signature)             

    def send(self, message, p_level ):
        """ send message to terminal and/or logfile"""

        if p_level == 0:
            message = "ERREUR : " + message
            self.count_error += 1
        elif p_level == 1:
            message = "ATTENTION : " + message
            self.count_attention += 1

        if p_level <= self.screen_level:
            print(message)

        message = message + '\n'
        self.history.append([p_level, message, self.count_line])
        self.count_line += 1

    def error(self, message=""):
        self.send(message, 0)

    def warning(self, message=""):
        self.send(message, 1)

    def info(self, message=""):
        self.send(message, 2)

    def detail(self, message=""):
        self.send(message, 3)

    def verbose(self, message=""):
        self.send(message, 4)


class Engine(Logger):

    def __init__(self, screen_level, file_level) -> None:

        self.audio = None
        super().__init__(screen_level, file_level)
    
    def manageAudioSet(self, file_id):
        try:
            filename = file_id[RELPATH] + file_id[FILENAME]
            self.info(f"Fichier sélectionné : {filename}")
            self.audio = AudioFile(file_id)

            self.info(f"Emission/artiste présent dans la liste des émissions : {file_id[ARTIST]}" )
                # need to update tags
            tags = self.audio.models[SOURCE]
            self.detail(f"Tags calculés à partir du nom du fichier : {tags.strID(calc= True)}")
            self.detail(f"Tags enregistrés dans le fichier         : {tags.strID()}")
            if not self.audio.check_filetags(SOURCE):
                self.info("Fichier incorrectement taggé - > sauvegarde des tags")
                self.audio.correct_filetags_info(SOURCE)
            else:
                self.info("Fichier correctement taggé")
            if self.audio.process_cp:
                #les fichiers currents et previous doivent étre gérés
                self.audio.manage_cp()
            else:
                self.info("Pas de gestion des current/previous pour ce fichier")
            if self.audio.check_filename(SOURCE) !=  EQUAL:
                # vérifie que l'orthographe de l'artiste dans le nom du fichier soit celui par défaut
                if settings.autoCorrectFilename:
                    # fichier incorrrectement nommé
                    self.info("Fichier incorrectement nommé -> renommage")
                    self.audio.saveFileName()
                else:
                    self.warning(f"Fichier {filename} incorrectement nommé mais pas de renommage - voir RBTagger.ini")

            if self.audio.has_changed:
                self.change_count += 1
        except BTException as e:
            self.error(str(e))        
        except Exception as e:
            self.change_count += 1
            self.error(get_error_message())
            self.info("Erreur non gérée : fin du traitement du fichier audio" )
		    

    def scan(self):
    ### need to checl params in dirscan    
        if settings.scanDirectory:
            return DirScan()
        else:
            if os.path.exists(settings.syncPath):
                if os.path.isdir(settings.syncPath):
                    file = settings.syncPath + self.getLastFile(settings.syncPath, settings.syncSignature)
                else:
                    file = settings.syncPath
                return FileScan(file)
            else:
                self.error("Para")
        
    def getLastFile(self, directory, filter):

        # récupère le dernier fichier dnas 
        # l'ordre alphabétique des fichiers diff est aussi chronoligque

        self.dirname = directory
        files = sorted( os.listdir(self.dirname), reverse=True)
        selected = ""
        if files:
            for file in files:
                matches = re.search(filter, file, re.IGNORECASE)
                if matches:
                    # sélectionne le premmier ok
                    selected = file
                    self.detail(f"{file} : OK")
                    break
                else:
                    self.verbose("Fichier pas OK "+ file)
            return selected
        else:
            self.error("Le répertoire des logs différentiels Vide")
            return None


class TagsModel(list):
    """ Classe permettant d'accéder aux fonctions de mutagen. """

    
    def __init__(self, model, root=LOCAL, calc_tags=None) :
        self.model = model
        self.root = root
        self.fileTags = None
        self.calcTags = {}
        self.hasFile = False
        self.calcTags = calc_tags
        

    def loadSet(self, full_pathname=''):
        self.relpath, filename = split_filepath(full_pathname)
        self.calcTags[RELPATH] = RELPATH
        self.calcTags[FILENAME] = filename
        self.loadPhyTags(full_pathname)
        self.hasFile = True

    def loadPhyTags(self, full_pathname):
        try:
            self.fileTags = MP3(full_pathname, ID3=EasyID3)
        except MutagenError:
            self.fileTags = mutagen.File(full_pathname, easy=True)
            self.fileTags.add_tags()
        if self.model == SOURCE:
            self.calcTags[LENGTH]= format_lasting(self.fileTags.info.length)
        else:
            self.calcTags = self.calcTags.copy()
            for key in READ_FILE_KEYS:
                self.calcTags[key] = self.getFileTag(key)
            self.calcTags[MODEL] = self.model
            raw_title = self.fileTags[TITLE][0]    
            for key in [LENGTH, YEAR, MODEL, SHORT_MODEL, TRACK]:
                find = (r'\s?' + self.getCalcTag(key, make_milter=True) + r'\s?-?')
                raw_title = re.sub(find,'', raw_title, re.I)
            self.calcTags[RAW_TITLE] = raw_title
        return True

    def strID(self, calc = False):
        if calc:
            return " ".join( ALL_KEYS[key][0] + self.getCalcTag(key) for key in READ_FILE_KEYS )    
        else:
            return " ".join( ALL_KEYS[key][0] + self.getFileTag(key) for key in READ_FILE_KEYS )    
    
    def getCalcID(self):
        return  "".join( self.getCalcTag(key) for key in ID_KEYS  )  
        
    
    @format_field
    def getCalcTag(self, key, model=None, make_milter=False):
        """ retourne la valeur calculée et formaté d'une clé de tag"""
        if not model:
            model = self.model
        self.calcTags[MODEL] = model
        self.calcTags[SHORT_MODEL] = PHY_MODELS[model]

        if key == TITLE:
            return '-'.join( self.getCalcTag(x, model) for x in TITLE_SUM_KEYS[model] if self.getCalcTag(x, model) not in EXCLUDE_FROM_TITLE)
        else:
            return self.calcTags[key]

    def getFileTag(self, key) -> str:
        """ retourne la valeurd'une clé de tag  tags enregistrés dans fichier """
        try:
            if key in [RELPATH, FILENAME]:
                       return self.__dict__[key]
            elif key == LENGTH:
                return format_lasting(self.fileTags.info.length)
            else:
                return self.fileTags[key][0]
        except ValueError:
            self.fileTags[key] = ''
            return ''
 
    def compareTag(self, key):
        return self.getCalcTag(key) == self.getFileTag(key)
    
    def save(self, model=None):
        if not model:
            model = self.model
   
        for key in SAVE_FILE_KEYS :
                self.fileTags[key] = self.getCalcTag(key, model) 
        self.fileTags.save()


class Scanner():

    
    def __init__(self, line_filter):
        
        self.files = []
        self.audio_filter = settings.audioSignature 
        self.nblines_filter = 1
        self.line_filter = line_filter
        self.length = 0
        self.render = None
        self.current_line = 0
        
    def __enter__(self):

        self.readLines()
        if self.files:
            self.files.sort(key = lambda x : x[NORM_FILNAME], reverse=True)
            return self.files
        return []

    def __exit__(self, exc_type, exc_value, exc_traceback):
        # no need to treat this abnormal end so far
        pass


    def check_artist(self, artist) -> dict:
        """ verfie si le nom d'artiste/alias normalisé est bien présente dans la base ()"""
        norm_name = normalize_name(artist)

        if norm_name in bot.RBProgs:
            params = bot.RBProgs[norm_name]
            artist = params[0]
            process_cp = params[1]
            raw_artiste = norm_name
            return {ARTIST : artist ,'processCP' : process_cp , 'rawartist' : raw_artiste}
        else:
            return {}
        
     
    def match_audio(self, relpath, filename):
        """ vérife que le nom du fichier audio est correct et vérifie son nom d'artiste/émission"""
        finder = re.compile(self.audio_filter, re.I)
        match = finder.findall(filename)
        info = {}
        if match:
            res = match[0]
            capt_length = len(res)
            if capt_length == len(READ_FILENAME_KEYS):
                for i in range (capt_length):
                    key = READ_FILENAME_KEYS[i]
                    info[key] = res[i]
                
                artist_info = self.check_artist(info[ARTIST])
                if artist_info:
                    normfilename = re.sub(info[ARTIST], artist_info['rawartist'], filename.lower())
                    # normfilename permet de trier les fichiers par ordre chrono-inverse
                    info[FILENAME] =  filename
                    info[NORM_FILNAME] =  normfilename
                    info[RELPATH] =  relpath
                    info[LENGTH] =  "0"
                    info.update(artist_info)
                    return info
                else:
                    bot.warning(f'{relpath}{filename} : Artiste {info[ARTIST]} non présent dans la liste des émissions')
            else:
                bot.verbose(f'{relpath}{filename} : Format de nom de fichier insuffisante ou extension invalide, analyse impossible')

        else:
            bot.verbose(f'{relpath}{filename} : Format de nom de fichier incorrect, analyse impossible')
        return False

    
    def extract_file_id(self, filepath):
        """ découpe le chemin du fichier en racine/chemin/fichier et récupère ses infos incluses dans son nom"""
        relpath, filename = split_filepath(filepath)
        if self.hasnot_excludedfilepath(relpath, filename):
            file_id = self.match_audio(relpath, filename)
            if file_id:
                bot.info('Fichier OK: ' + relpath + filename )
                return file_id
            else:
                return None


    
    def get_file_id(self, line):
        """ récupère les fichiers devant être traité dans un fichier log """
        try:
            line = format_to_unixpath(line)
            bot.verbose("Ligne analysée :" + line)
            if self.current_line == 0 :
                for found_row in self.line_filter:
                    match = re.search(found_row[0], line, re.I)
                    if match:
                        self.nblines_filter = len(found_row) 
                        self.found_row = found_row
                        break # on sort
            else:
                match = re.search(self.found_row[self.current_line], line, re.IGNORECASE)
            if self.current_line == self.nblines_filter - 1:
                if match:    
                    bot.verbose('Correspondance : ' +match.group(1) )
                    self.nblines_filter = 1
                    self.current_line = 0
                    return self.extract_file_id(match.group(2))
                else:
                    bot.verbose("Pas de correspondance")
                    self.nblines_filter = 1
                    self.current_line = 0
                    return None
            else:
                # d'autre lignes sont a vérifier
                self.current_line += 1
                bot.verbose('Correspondance : ' +match.group(1) + ' --->> Ligne suivante')
        except ValueError:
            bot.warning("La ligne n'a pas pu être correctement analysée, abandon")
            return None

    def hasnot_excludedfilepath(self, relpath, filename):
        filepath = relpath + filename
        for i in settings.excludedPaths:
            if i.lower() in filepath:
                return False
        return True
    

class FileScan(Scanner):

    """
        Return audio files list from filetext content

    """

    def __init__(self, full_pathname):
        self.fullPathName = full_pathname
        super().__init__(settings.syncActionLine)
    
    def readLines(self):
        
        bot.info(STARS)
        bot.info(f"Fichier log sync séléctionné : {self.fullPathName}")
        bot.info(f'Exclusion des fichiers/dossiers contenant : {" / ".join(settings.excludedPaths)}')
        bot.info()

        if not os.path.exists(self.fullPathName):
            bot.error('Fichier de synchronisation introuvable')
        else:
            try:
                with open(self.fullPathName,'r',-1,"utf-8") as source:
                    for line in source:
                        file_id = self.get_file_id(line)
                        if file_id:    
                            self.files.append(file_id)
                    return True
            except OSError as e:
                bot.error(f"Problème fatal durant la lecture du fichier {self.fullPathName}\nDétail : {e}" )


class DirScan(Scanner):
    
    """
        Return audio files list from directory files list.

    """
    
    def __init__(self):
        super().__init__([['(^)(.*)']])
        self.directoryName = settings.root[LOCAL]

    def readLines(self):
        bot.info(STARS)
        bot.info(f'Répertoire sélectionné : {self.directoryName}')
        bot.info(f'Chemin doit contenir : {" / ".join(settings.scanPathFilter)}')
        bot.info(f'Artiste doit contenir : {" / ".join(settings.scanAudioFilter)}')
        bot.info(f'Exclusion de ceux contenant : {" / ".join(settings.excludedPaths)}')
        bot.info()

        for (root, dir, files) in os.walk(self.directoryName, topdown=True):
            for line in files:
                file = self.get_file_id(root+'/' +line)
                if file:    
                    self.files.append(file)
        
    def hasnot_excludedfilepath(self, relpath, filename):
        if not super().hasnot_excludedfilepath(relpath, filename):
            return False
        filepath = relpath + filename
        
        for i in settings.scanPathFilter:
            if i.lower() not in filepath:
                bot.verbose(f'Répertoire {filepath} non retenu, ne contient pas {" ou ". join(settings.scanPathFilter)}')
                return False
            else:
                break
        for i in settings.scanAudioFilter:
            if i.lower() not in filename:
                bot.verbose(f'{filename} non retenu, ne contient pas {" ou ". join(settings.scanAudioFilter)}')
                return False
            else:
                break
             
        return True
    

class AudioFile:
    
    def __init__(self, file_id):
        
        """Initialize the audio file

        Args:
            file_id (_type_): _description_

        Raises:
            RBFileNotFound: _description_
        """

        self.models ={SOURCE : None, CURRENT : None, PREVIOUS : None}
        self.has_changed = False
        
        self.filename = file_id[FILENAME]
        self.relative_path = file_id[RELPATH]
        self.process_cp = file_id['processCP']
        tags = {}
        for key in READ_FILENAME_KEYS:
            tags[key] = file_id[key] 
        
        self.load_models_sets(calc_tags=tags)
        self.load_modelstags()
        for root in settings.root:
            path = self.get_full_filepath(root=root)
            if (root != DISTANT or settings.makeDistCopy) and not os.path.exists(path):
                raise BTFileNotFound(path)

    def load_modelstags(self, root=LOCAL):
        for model in PHY_MODELS : # 
            if self.process_cp or model == SOURCE:
                self.load_modeltags(model, root)

    def load_modeltags(self, model=SOURCE, root=LOCAL):
        full_pathname = self.get_full_filepath(model, root, calc=True)
        if os.path.exists(full_pathname):
            self.models[model].loadSet(full_pathname)
            
    def load_models_sets(self, root=LOCAL, calc_tags=None):
        for model in PHY_MODELS : # 
            if self.process_cp or model == SOURCE:
                self.models[model] = self.load_model_sets(model, root, calc_tags)
            
    def load_model_sets(self, model, root=LOCAL, calc_tags = None):
        return TagsModel(model, root, calc_tags)
    

    def get_full_filepath(self, model=SOURCE, root=LOCAL, calc=False):
        return self.get_rootdir(root) + self.get_relative_filepath(model, calc)

    def get_relative_filepath(self, model=SOURCE, calc=False):
        return self.get_relative_path(model)  + self.get_filename(model, calc)

    def get_filename(self, model=SOURCE, calc=False):
        if model == SOURCE and not calc:
            return  self.filename
        else:
           return   '.' .join(["#".join(self.get_tag(field, model, calc=True) for field in CALC_FILENAME[model] \
                        if self.get_tag(field, model, calc=True) ) , self.get_tag(EXT, SOURCE, calc=True)])
    
    def get_rootdir(self, root=LOCAL):
            return settings.root[root]

    def get_model_rootdir(self, model=SOURCE, root=LOCAL):
        return self.roodir(root) + self.get_relative_path(model)
    
    def get_relative_path(self, model):
        if model == SOURCE:
            return  self.relative_path
        else:
            return  settings.currentPath 
    
    def get_tag(self, key, model = SOURCE, calc = False):
        if calc:
            return self.models[model].getCalcTag(key, model)
        else:
            return self.models[model].getFileTag(key)
 
    def compare_modeltag(self, model_a, model_b):
        id_a = self.models[model_a].getCalcID()
        id_b = self.models[model_b].getCalcID()
        return str_compare(id_a, id_b)
    
    def check_tags(self, model, key):
        return str_compare(self.get_tag(key, model, calc=True), self.get_tag(key, model))

    def check_filename(self, model):
        """vérifie si le nom du fichier réel est conforme au schéma du modèle """
        return str_compare(self.get_filename(model, calc=True), self.get_filename(model))   
    
    def save_filename(self):
        self.move_audio(SOURCE, SOURCE)

    def check_filetags(self, model):
        return self.check_tags(model, TITLE)  == EQUAL

    def correct_filetags_info(self, model):
        """ corrige les tags d'un fichier suivant son modèle"""
        message = "Modification des tags ID3"
        if not settings.noAction:
            try:
                root = LOCAL
                self.models[model].save()
                bot.info("OK local : " + message)
                self.has_changed = True
                if settings.makeDistCopy:
                    root = DISTANT
                    self.models[model].loadSet(self.get_full_filepath(model, root))
                    self.models[model].save()
                    bot.info("OK distant : " + message)
            except MutagenError :
                raise BTTagError(model, root)
            else :
                return True                
        else:
            bot.info(f"NoAction :  {message}")

    def copy_audio(self, model_source, model_destination):
        """ copie d'un fichier audio et corrections du nom et des tags en fonction du modèle """
        message = "Copie du fichier " + model_source + "\n\tvers " + model_destination
        source_file = self.get_full_filepath(model_source)
        dist_file = self.get_full_filepath(model_destination)
        if not settings.noAction:
            try:
                cmd = 'copy /Y "' + format_to_unixpath(source_file, reverse=True) + '" "' + \
                    format_to_unixpath(dist_file, reverse = True)+ '" 2>&1'
                bot.verbose(f"Commande : {cmd}")
                result = subprocess.call(cmd, shell=True)
                if result == 0:
                    bot.detail("Copie effectuée")
                self.models[model_destination].loadSet(dist_file)
                self.models[model_destination].save(model_destination)
                self.has_changed = True
                bot.info( f"OK : Copie du fichier {source_file}  vers {dist_file}")
                
                if settings.makeDistCopy:
                    source_file = self.get_full_filepath(model_destination)
                    dist_file = self.get_full_filepath(model_destination, DISTANT)
                    shutil.copy2(source_file, dist_file)
                    bot.info(f"OK : Copie du fichier {model_destination}  de local à distant")
            except OSError:
                raise BTCopyError(source_file, dist_file)

        else:
                bot.info("NoAction : " + message )
    
    def move_audio(self, model_source, model_destination):
        """ transforme un fichier depuis modèle vers un autre (tags et nom)"""
        audio = self.get_relative_filepath(model_source)
        message = f"Renommage du fichier {audio} de {model_source} à {model_destination}"
        if not settings.noAction:
            try:
                source_file = self.get_full_filepath(model_source)
                dest_file = self.get_full_filepath(model_destination, calc=True)
                self.models[model_source].save(model = model_destination )
                os.replace(source_file, dest_file)
                self.has_changed = True
                bot.info( message )
                if settings.makeDistCopy:
                    source_file = self.get_full_filepath(model_source, DISTANT)
                    dest_file = self.get_full_filepath(model_destination, DISTANT, calc=True)
                    self.models[model_source].loadSet(source_file)
                    self.models[model_source].save(model_destination)
                    os.replace(source_file, dest_file)
                    shutil.copystat(self.get_full_filepath(model_destination, LOCAL), dest_file)
            except OSError as e:
                raise BTMoveError(source_file, dest_file, e)
        else:
            bot.info("NoAction : {message}")

    def manage_cp(self):
        """ gestion des fichiers current et previous - fichiers les 2 plus récents pour chaque emission"""

        if self.models[CURRENT].hasFile:
            state = self.compare_modeltag(SOURCE, CURRENT)
            if state == BIGGER:
                bot.info('Fichier #current plus ancien')
                bot.info('Fichier current remplace #previous')
                self.move_audio(CURRENT, PREVIOUS)
                bot.info('Fichier traité remplace #current')
                self.copy_audio(SOURCE, CURRENT)
            elif state == SMALLER:
                bot.info('Fichier #current plus récent')
                if not self.models[PREVIOUS].hasFile or self.compare_modeltag(SOURCE, PREVIOUS) == BIGGER:
                        bot.info('Fichier #previous plus ancien ou inexistant')
                        bot.info('Fichier traité se duplique en #previous')
                        self.copy_audio(SOURCE, PREVIOUS)
                else:
                    bot.info('Fichier #previous plus ou aussi récent')
            else:
                bot.info('Fichier traité identique au #current')   
        else:
            bot.info('Fichier traité se duplique en #current (inexistant)')
            self.copy_audio(SOURCE, CURRENT)

    def save_correct_filename(self):
        """ renomme le fchier audio lorsque son nom est incorrect"""
        for root in ALL_ROOTS:
            if settings.makeDistCopy or root == LOCAL :
                self.move_audio(SOURCE, SOURCE)
 


