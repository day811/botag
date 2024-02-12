import os
import shutil
from typing import Any
import unicodedata
import subprocess
import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from datetime import datetime , timedelta
import re ,  sys, traceback

settings = None
_ARTIST = 'artist'
_YEAR = 'date'
_TRACK = 'tracknumber'
_LENGTH = 'length'
_RAW_TITLE = 'rawtitle'
_NORM_FILNAME = 'normfilename'
_TITLE = 'title'
_MODEL = 'model'
_SHORT_MODEL = 'shortMod'
_CURRENT = 'current'
_PREVIOUS = 'previous'
_LOCAL = 'local'
_DISTANT = 'distant'
_SOURCE = 'source'
_ID = 'id'
_FILENAME = 'filename'
_RELPATH = 'relpath'
_EXT = 'extension'
_PHY_MODELS = { _SOURCE : '', _CURRENT : "C#",_PREVIOUS : "P#"}
_CURRENT_PREVIOUS = [_CURRENT, _PREVIOUS]
_ALL_ROOTS = [_LOCAL,_DISTANT]
_SMALLER = 1
_BIGGER = 2
_EQUAL = 3
_SIMILAR = 4

_ALL_KEYS = {_FILENAME : ['F:',_FILENAME],_ARTIST : ['A:','Artiste'],_YEAR: ['Y:','Année'],_TRACK: ['P:','Piste'],
            _TITLE: ['T:','Titre'],_LENGTH: ['L:','Longuer'], _RAW_TITLE: ['C','Titre court'],
            _MODEL : ['',''],_ID : ['',''],_NORM_FILNAME : None, _EXT : ['Ex','Extension']}
_READ_FILE_KEYS = [_ARTIST,_YEAR,_TRACK,_TITLE,_LENGTH]
_SAVE_FILE_KEYS = [_ARTIST,_YEAR,_TRACK,_TITLE]
_READ_FILENAME_KEYS = [_ARTIST,_YEAR,_TRACK,_RAW_TITLE,_EXT]
_TITLE_SUM_KEYS = {
    _SOURCE : [_YEAR,_TRACK,_LENGTH,_RAW_TITLE],
    _CURRENT : [_SHORT_MODEL,_YEAR,_TRACK,_LENGTH,_RAW_TITLE],
    _PREVIOUS : [_SHORT_MODEL,_YEAR,_TRACK,_LENGTH,_RAW_TITLE],
    }
_CALC_FILENAME={
    _SOURCE : [_ARTIST,_YEAR, _TRACK, _RAW_TITLE],
    _CURRENT : [_ARTIST,_MODEL],
    _PREVIOUS : [_ARTIST,_MODEL]
}
_EXCLUDE_FROM_TITLE = ['0000','00','',None]
_ID_KEYS = [_YEAR,_TRACK,_RAW_TITLE]

def getErrorMmessage():
    exc_type, exc_value, exc_tb = sys.exc_info()
    stack_summary = traceback.extract_tb(exc_tb)
    end = stack_summary[-1]

    err_type = type(exc_type).__name__
    err_msg = str(exc_value)
    date = datetime.strftime(datetime.now(), "%B %d, %Y at precisely %I:%M %p")
    message = f"{err_type} dans {end.filename} / {end.name} en line {end.lineno} \nwith the error message: {err_msg}.\n"
    message +=f"Message d'erreur : {err_msg} / Code reponsable: {end.line!r}"
    return message

class RBException(Exception):
    def __init__(self, message) -> None:
        super().__init__(message)

class RBFileNotFound(RBException):
    def __init__(self, filepath) -> None:
        message = f'Fichier audio {filepath} inexistant'
        super().__init__(message)

class RBArtistNotFound(RBException):
    def __init__(self, artist) -> None:
        message = f"L'artiste : {artist} n'existe pas"
        super().__init__(message)

class RBTagError(RBException):
    def __init__(self, model,root) -> None:
        filename = bot.audio.getFullFilePath(model,root)
        message = f'lors de l\'écriture des tags dans {filename}'
        super().__init__(message)

class RBCopyError(RBException):
    def __init__(self, fromFile,toFile) -> None:
        message = f'lors de la copie du fichier {fromFile} vers {toFile}'
        super().__init__(message)

class RBMoveError(RBException):
    def __init__(self, fromFile,toFile) -> None:
        message = f'lors du déplacement du fichier {fromFile} vers {toFile}'
        super().__init__(message)

class Logger():
    
    def __init__(self,screenLevel,fileLevel) -> None:

        self.wrapper = None
        self.logFilename = None
        self.screenLevel = screenLevel
        self.fileLevel = fileLevel
        self.countAttention = 0
        self.countError = 0
        self.countLine = 0
        self.history = []
        self.timeStamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.changeCount = 0
 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
    
        return False
    
    def open(self):

        try:
            self.wrapper = open(self.logFilename ,"w",encoding="utf-8")
        except:
            print("Création impossible du fichier des logs : " + self.logFilename )
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()
        else:
            return True        

    def close(self):
        if self.history is not None and self.logFilename is not None:
            if self.countError:
                self.logFilename += '_[ERREUR]'
            elif self.countAttention:
                self.logFilename += '_[ATTENTION]'
            self.logFilename +='.log'
            if self.open():
                self.wrapper.write("\tCréation du fichier log " + self.logFilename+ '\n')
                for message in self.history:
                    if message[0] <= self.fileLevel:
                        self.wrapper.write("{:05.0f}".format(message[2]) + f' : {message[1]}' )
                if self.countAttention + self.countError >0:
                    self.wrapper.write("\nLISTES DES ERREURS / ATTENTIONS\n")
                    self.wrapper.write(self.getlevelMessage(1))
                    self.wrapper.write(self.getlevelMessage(0))
                self.history = None
                self.wrapper.close()
        logFilename = formatToUnixPath(bot.logFilename)
    
    
    def getlevelMessage(self, level):
        res = ''
        for message in bot.history:
            if message[0] == level:
                res += message[1]                
        return res
    
    def start(self,_setting):
        global settings
        settings = _setting

        self.scanList = {_setting.logPath:_setting.logMask,_setting.syncPath : _setting.syncSignature}
        self.screenLevel = _setting.logScreenLevel
        self.fileLevel = _setting.logFileLevel
        if self.fileLevel > 0:
            self.logFilename = _setting.logPath + _setting.logMask + '_' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.Info('Logger démarré')

    def rotate(self):
        """ erase old files log """
        limitDate = datetime.now() - timedelta(days=settings.logLimit)
        for directory,signature in self.scanList.items():
            self.Detail("Analyse répertoire " + directory)
            self.Verbose("Signature " + signature)
            fileList = os.listdir(directory)
            for file in fileList:
                if re.search(signature,file,re.IGNORECASE):
                    self.Verbose("Analyse fichier sélectionné " + file)
                    tsf = datetime.fromtimestamp(os.path.getmtime(directory + file)) # get timestamp
                    if tsf < limitDate:
                        if not settings.noAction:
                            os.remove(directory + file)
                            self.Detail("Suppression du fichier log " + directory + file)
                        else :
                            self.Detail("NoAction : Non Suppression du fichier log " + directory + file)
                    else:
                        self.Verbose('Fichier conservé :' + file)

    def send(self,message,p_level ):
        """ send message to terminal and/or logfile"""
        if message :
            now = datetime.now().strftime("%H:%M:%S,%f") + " --- "
        else:
            now=""

        if p_level == 0:
            message = "ERREUR : " + message
            self.countError += 1
        elif p_level ==1:
            message = "ATTENTION : " + message
            self.countAttention += 1

        if p_level <= self.screenLevel:
            print(message)

        message = message + '\n'
        self.history.append([p_level,message,self.countLine])
        self.countLine +=1

    def Error(self,message=""):
        self.send(message,0)

    def Warning(self,message=""):
        self.send(message,1)

    def Info(self,message=""):
        self.send(message,2)

    def Detail(self,message=""):
        self.send(message,3)

    def Verbose(self,message=""):
        self.send(message,4)

class Engine(Logger):

    def __init__(self,screenLevel,fileLevel) -> None:

        self.audio = None
        super().__init__(screenLevel,fileLevel)
    
    def manageAudioSet(self,fileID):
        try:
            filename = fileID[_RELPATH] + fileID[_FILENAME]
            self.Info("Fichier sélectionné : " + filename)
            self.audio = AudioFile(fileID)

            self.Info("Emission/artiste présent dans la liste des émissions : " + fileID[_ARTIST] )
                # need to update tags
            tags = self.audio.models[_SOURCE]
            self.Detail("Tags calculés à partir du nom du fichier : " + tags.strID(calc=True))
            self.Detail("Tags enregistrés dans le fichier         : " +  tags.strID())
            if not self.audio.checkFileTags(_SOURCE):
                self.Info("Fichier incorrectement taggé - > sauvegarde des tags")
                self.audio.correctFileTagsInfo(_SOURCE)
            else:
                self.Info("Fichier correctement taggé")
            if self.audio.processCP:
                #les fichiers currents et previous doivent étre gérés
                self.audio.manageCP()
            else:
                self.Info("Pas de gestion des current/previous pour ce fichier")
            if self.audio.checkFilename(_SOURCE) !=  _EQUAL:
                # vérifie que l'orthographe de l'artiste dans le nom du fichier soit celui par défaut
                if settings.autoCorrectFilename:
                    # fichier incorrrectement nommé
                    self.Info("Fichier incorrectement nommé -> renommage")
                    self.audio.saveFileName()
                else:
                    self.Warning(f"Fichier {filename} incorrectement nommé mais pas de renommage - voir RBTagger.ini")

            if self.audio.hasChanged:
                self.changeCount +=1
        except RBException as e:
            self.Error(str(e))        
        except Exception as e:
            self.changeCount +=1
            self.Error(getErrorMmessage())
            self.Info(f"Erreur non gérée : fin du traitement du fichier audio" )
		    

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
                self.Error("Para")
        
    def getLastFile(self,directory,filter):

        # récupère le dernier fichier dnas 
        # l'ordre alphabétique des fichiers diff est aussi chronoligque

        self.dirname = directory
        files = sorted( os.listdir(self.dirname),reverse=True)
        #ajd=datetime.now().strftime("%Y-%m-%d")
        selected = ""
        if files:
            for file in files:
                matches = re.search(filter,file,re.IGNORECASE)
                if matches:
                    # sélectionne le premmier ok
                    selected = file
                    self.Detail(f"{file} : OK")
                    break
                else:
                    self.Verbose("Fichier pas OK "+ file)
            return selected
        else:
            self.Error("Le répertoire des logs différentiels Vide")
            return None

bot = Engine(1,3)

def formatToUnixPath(path,isDir=False,reverse = False,removeQuotes = False):
    path = re.sub('\\n','',path)
    if removeQuotes:
        path = re.sub('"|\'','',path)
        
    fromSep = "\\"
    toSep = "/"
    if reverse:
        fromSep = '/'
        toSep = r'\\'
    newPath =  path.replace(fromSep,toSep)
    if isDir and newPath[-1:] != toSep : 
        newPath += toSep
    return newPath

def normalizeName(a) -> str:
    """ retoune une chaine de caractères uniquement alphanumérique en minuscule et sans accent ni espace."""
    return re.sub(r'[\W_]+', '', removeAccents(a.lower()))

def removeAccents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')

def strCompare(a,b) -> int:
    if a == b: 
        return _EQUAL
    if (normalizeName(a) == normalizeName(b)):
        return _SIMILAR
    if a > b:
        return _BIGGER
    else:
        return _SMALLER

def splitFilePath(fullPathname):
    global settings
    pathTab = fullPathname.rsplit('/',maxsplit=1)
    path = pathTab[0]+'/'
    filename = pathTab[1]
    find = '(' + '|'.join(settings.root[x] for x in settings.root)+ r')(.*)'
    match = re.search(find,path,re.I)
    if match:
        relpath = match.group(2)
        return relpath,filename
    else:
        return None,None

def formatLasting(lasting):
    """ convert time in sec into time mmm:ss """
    length = float(lasting)
    minutes = "{:02d}".format(int(length // 60))
    seconds = "{:02d}".format(int(round(length % 60)))
    return  ":".join([minutes, seconds]) 

def formatField(func):
    """ formatte les clés (tag) """
    def inner(*args, **kwargs):
        value = func(*args, **kwargs)
        key = args[1]
        makeFilter = False
        if 'makeFilter' in  kwargs:
            makeFilter = kwargs['makeFilter']
        if key == _YEAR:
            return "{:04.0f}".format(int(value))
        elif key == _TRACK:
            if value == '': 
                value = "0"
            return "{:02.0f}".format(int(value))
        elif key == _LENGTH:
            if makeFilter: wrapper = [r'\(',r'\)']
            else: wrapper = ['(',')']
            return value.join(wrapper)
        return value
    return inner
    

class TagsModel(list):
    """ Classe permettant d'accéder aux fonctions de mutagen. """

    
    def __init__(self,model, root=_LOCAL, calcTags=None) :
        self.model = model
        self.root = root
        self.fileTags = None
        self.calcTags = {}
        self.hasFile = False
        self.calcTags = calcTags
        

    def loadSet(self,fullPathname=''):
        self.relpath, filename = splitFilePath(fullPathname)
        self.calcTags[_RELPATH] = _RELPATH
        self.calcTags[_FILENAME] = filename
        self.loadPhyTags(fullPathname)
        self.hasFile = True

    def loadPhyTags(self,fullPathName):
        try:
            self.fileTags = MP3(fullPathName, ID3=EasyID3)
        except:
            self.fileTags = mutagen.File(fullPathName, easy=True)
            self.fileTags.add_tags()
        if self.model == _SOURCE:
            self.calcTags[_LENGTH]= formatLasting(self.fileTags.info.length)
        else:
            self.calcTags = self.calcTags.copy()
            for key in _READ_FILE_KEYS:
                self.calcTags[key] = self.getFileTag(key)
            self.calcTags[_MODEL] = self.model
            rawTitle = self.fileTags[_TITLE][0]    
            for key in [_LENGTH, _YEAR, _MODEL,_SHORT_MODEL,_TRACK]:
                find = (r'\s?' + self.getCalcTag(key,makeFilter=True) + r'\s?-?')
                rawTitle = re.sub(find,'',rawTitle,re.I)
            self.calcTags[_RAW_TITLE] = rawTitle
        return True

    def strID(self, calc = False):
        if calc:
            return " ".join( _ALL_KEYS[key][0] + self.getCalcTag(key) for key in _READ_FILE_KEYS )    
        else:
            return " ".join( _ALL_KEYS[key][0] + self.getFileTag(key) for key in _READ_FILE_KEYS )    
    
    def getCalcID(self):
        return  "".join( self.getCalcTag(key) for key in _ID_KEYS  )  
        
    
    @formatField
    def getCalcTag(self,key,model= None,makeFilter = False):
        """ retourne la valeur calculée et formaté d'une clé de tag"""
        if not model:
            model = self.model
        self.calcTags[_MODEL] = model
        self.calcTags[_SHORT_MODEL] = _PHY_MODELS[model]

        if key == _TITLE:
            return '-'.join( self.getCalcTag(x,model) for x in _TITLE_SUM_KEYS[model] if self.getCalcTag(x,model) not in _EXCLUDE_FROM_TITLE)
        else:
            return self.calcTags[key]

    def getFileTag(self,key) -> str:
        """ retourne la valeurd'une clé de tag  tags enregistrés dans fichier """
        try:
            if key in [_RELPATH,_FILENAME]:
                       return self.__dict__[key]
            elif key == _LENGTH:
                return formatLasting(self.fileTags.info.length)
            else:
                return self.fileTags[key][0]
        except:
            self.fileTags[key] = ''
            return ''
 
    def compareTag(self,key):
        return self.getCalcTag(key) == self.getFileTag(key)
    
    def save(self,model=None):
        if not model:
            model =self.model
   
        for key in _SAVE_FILE_KEYS :
                self.fileTags[key] = self.getCalcTag(key,model) 
        self.fileTags.save()

class Scanner():

    
    def __init__(self,lineFilter):
        
        self.files = []
        self.audioFilter = settings.audioSignature 
        self.nbLinesFilter = 1
        self.lineFilter = lineFilter
        self.length = 0
        self.render = None
        self.currentLine = 0
        
    def __enter__(self):

        self.readLines()
        if self.files:
            self.files.sort(key = lambda x : x[_NORM_FILNAME],reverse=True)
            return self.files
        return []

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass


    def checkArtist(self,artist) -> bool:
        """ verfie si le nom d'artiste/alias normalisé est bien présente dans la base ()"""
        normName = normalizeName(artist)

        if normName in bot.RBProgs:
            params = bot.RBProgs[normName]
            artist = params[0]
            processCP =params[1]
            rawArtiste = normName
            return {_ARTIST : artist ,'processCP' : processCP , 'rawartist' : rawArtiste}
        else:
            return False
        
     
    def matchAudio(self,relpath, filename):
        """ vérife que le nom du fichier audio est correct et vérifie son nom d'artiste/émission"""
        finder = re.compile(self.audioFilter,re.I)
        match = finder.findall(filename)
        info = {}
        if match:
            res = match[0]
            captLen = len(res)
            if captLen == len(_READ_FILENAME_KEYS):
                for i in range (captLen):
                    key = _READ_FILENAME_KEYS[i]
                    info[key] = res[i]
                
                artistInfo = self.checkArtist(info[_ARTIST])
                if artistInfo:
                    normfilename = re.sub(info[_ARTIST],artistInfo['rawartist'], filename.lower())
                    # normfilename permet de trier les fichiers par ordre chrono-inverse
                    info[_FILENAME] =  filename
                    info[_NORM_FILNAME] =  normfilename
                    info[_RELPATH] =  relpath
                    info[_LENGTH] =  "0"
                    info.update(artistInfo)
                    return info
                else:
                    bot.Warning(f'{relpath}{filename} : Artiste {info[_ARTIST]} non présent dans la liste des émissions')
            else:
                bot.Verbose(f'{relpath}{filename} : Format de nom de fichier insuffisante ou extension invalide, analyse impossible')

        else:
            bot.Verbose(f'{relpath}{filename} : Format de nom de fichier incorrect, analyse impossible')
        return False

    
    def extractFileID(self, filepath):
        """ découpe le chemin du fichier en racine/chemin/fichier et récupère ses infos incluses dans son nom"""
        relpath,filename = splitFilePath(filepath)
        if self.hasNotExcludedFilePath(relpath, filename):
            fileID = self.matchAudio(relpath, filename)
            if fileID:
                bot.Info('Fichier OK: ' + relpath + filename )
                return fileID
            else:
                return None


    
    def getFileID(self,line):
        """ récupère les fichiers devant être traité dans un fichier log """
        try:
            line = formatToUnixPath(line)
            bot.Verbose("Ligne analysée :" + line)
            if self.currentLine == 0 :
                for findRow in self.lineFilter:
                    match = re.search(findRow[0], line,re.I)
                    if match:
                        self.nbLinesFilter =len(findRow) 
                        self.findRow = findRow
                        break # on sort
            else:
                match = re.search(self.findRow[self.currentLine],line,re.IGNORECASE)
            if self.currentLine == self.nbLinesFilter-1:
                if match:    
                    bot.Verbose('Correspondance : ' +match.group(1) )
                    self.nbLinesFilter = 1
                    self.currentLine = 0
                    return self.extractFileID(match.group(2))
                else:
                    bot.Verbose("Pas de correspondance")
                    self.nbLinesFilter = 1
                    self.currentLine=0
                    return None
            else:
                # d'autre lignes sont a vérifier
                self.currentLine +=1
                bot.Verbose('Correspondance : ' +match.group(1) + ' --->> Ligne suivante')
        except :
            bot.Warning("La ligne n'a pas pu être correctement analysée, abandon")
            return None

    def hasNotExcludedFilePath(self,relpath, filename):
        filepath = relpath + filename
        for i in settings.excludedPaths:
            if i.lower() in filepath:
                return False
        return True
    
class FileScan(Scanner):

    def __init__(self,fullPathName):
        self.fullPathName = fullPathName
        super().__init__(settings.syncActionLine)
    
    def readLines(self):
        
        bot.Info('*****************************************************************')
        bot.Info("Fichier log sync séléctionné : " + self.fullPathName)
        bot.Info('EXclusion des fichiers/dossiers contenant : ' + " / ".join(settings.excludedPaths))
        bot.Info()

        if not os.path.exists(self.fullPathName):
            bot.Error('Fichier de synchronisation introuvable')
        else:
            try:
                with open(self.fullPathName,'r',-1,"utf-8") as source:
                    for line in source:
                        fileID = self.getFileID(line)
                        if fileID:    
                            self.files.append(fileID)
                    return True
            except:
                bot.Error("Problème fatal durant la lecture du fichier " + self.fullPathName)
                pass

class DirScan(Scanner):
    """ Render audio files list from directory scan """
    
    def __init__(self):
        super().__init__([['(^)(.*)']])
        self.directoryName = settings.root[_LOCAL]

    def readLines(self):
        bot.Info('*****************************************************************')
        bot.Info("Répertoire sélectionné : " + self.directoryName)
        bot.Info('Chemin doit contenir : ' + " / ".join(settings.scanPathFilter))
        bot.Info('Artiste doit contenir : ' + " / ".join(settings.scanAudioFilter))
        bot.Info('Exclusion de ceux contenant : ' + " / ".join(settings.excludedPaths))
        bot.Info()

        for (root,dir,files) in os.walk(self.directoryName,topdown=True):
            for line in files:
                file = self.getFileID(root+'/' +line)
                if file:    
                    self.files.append(file)
        
    def hasNotExcludedFilePath(self,relpath, filename):
        if not super().hasNotExcludedFilePath(relpath, filename):
            return False
        filepath = relpath + filename
        
        for i in settings.scanPathFilter:
            if i.lower() not in filepath:
                bot.Verbose(f'Répertoire {filepath} non retenu, ne contient pas ' + " ou ".join(settings.scanPathFilter))
                return False
            else:
                break
        for i in settings.scanAudioFilter:
            if i.lower() not in filename:
                bot.Verbose(f'{filename} non retenu, ne contient pas ' + " ou ".join(settings.scanAudioFilter))
                return False
            else:
                break
             
        return True
    
class AudioFile:
    
    def __init__(self,fileID):

        self.models={_SOURCE : None, _CURRENT : None, _PREVIOUS : None}
        self.hasChanged = False
        
        self.filename = fileID[_FILENAME]
        self.relativePath = fileID[_RELPATH]
        self.processCP = fileID['processCP']
        tags = {}
        for key in _READ_FILENAME_KEYS:
            tags[key] = fileID[key] 
        
        self.loadModelsSets(calcTags=tags)
        self.loadModelsTags()
        for root in settings.root:
            path = self.getFullFilePath(root=root)
            if (root != _DISTANT or settings.makeDistCopy) and not os.path.exists(path):
                raise RBFileNotFound(path)

    def loadModelsTags(self,root=_LOCAL):
        for model in _PHY_MODELS : # 
            if self.processCP or model == _SOURCE:
                self.loadModelTags(model,root)

    def loadModelTags(self,model=_SOURCE,root=_LOCAL):
        fullPathName = self.getFullFilePath(model,root,calc=True)
        if os.path.exists(fullPathName):
            self.models[model].loadSet(fullPathName)
            
    def loadModelsSets(self,root=_LOCAL,calcTags=None):
        for model in _PHY_MODELS : # 
            if self.processCP or model == _SOURCE:
                self.models[model] = self.loadModelSets(model, root=_LOCAL, calcTags = calcTags)
            
    def loadModelSets(self, model, root=_LOCAL, calcTags = None, fullPathName = None):
        return TagsModel(model,root,calcTags)
    

    def getFullFilePath(self,model=_SOURCE,root=_LOCAL,calc=False):
        return self.getRootDir(root) + self.getRelativeFilePath(model,calc=calc)

    def getRelativeFilePath(self,model=_SOURCE,calc=False):
        return self.getRelativePath(model)  + self.getFileName(model)

    def getFileName(self,model=_SOURCE,calc=False):
        if model == _SOURCE and not calc:
            return  self.filename
        else:
           return   '.' .join(["#".join(self.getTag(field,model,calc=True) for field in _CALC_FILENAME[model] \
                        if self.getTag(field,model,calc=True) ) , self.getTag(_EXT,_SOURCE,calc=True)])
    
    def getRootDir(self,root=_LOCAL):
            return settings.root[root]

    def getModelRootDir(self,model=_SOURCE,root=_LOCAL):
        return self.roodir(root) + self.getRelativePath(model)
    
    def getRelativePath(self,model,calc=False):
        if model == _SOURCE:
            return  self.relativePath
        else:
            return  settings.currentPath 
    
    def getTag(self, key,model = _SOURCE,calc = False):
        if calc:
            return self.models[model].getCalcTag(key,model)
        else:
            return self.models[model].getFileTag(key)
 
    def compareModelTag(self,modelA,modelB):
        IdA = self.models[modelA].getCalcID()
        IdB = self.models[modelB].getCalcID()
        return strCompare(IdA,IdB)
    
    def checkTags(self,model,key):
        return strCompare(self.getTag(key,model,calc=True),self.getTag(key,model))

    def checkFilename(self, model):
        """vérifie si le nom du fichier réel est conforme au schéma du modèle """
        return strCompare(self.getFileName(model,calc=True),self.getFileName(model))   
    
    def saveFilename(self,model):
        self.moveAudio(_SOURCE,_SOURCE)

    def checkFileTags(self,model):
        return self.checkTags(model,_TITLE)  == _EQUAL

    def correctFileTagsInfo(self,model):
        """ corrige les tags d'un fichier suivant son modèle"""
        message = "Modification des tags ID3"
        if not settings.noAction:
            try:
                root = _LOCAL
                self.models[model].save()
                bot.Info("OK local : " + message)
                self.hasChanged = True
                if settings.makeDistCopy:
                    root = _DISTANT
                    self.models[model].loadSet(self.getFullFilePath(model,root))
                    self.models[model].save()
                    bot.Info("OK distant : " + message)
            except:
                raise RBTagError(model,root)
            else :
                return True                
        else:
            bot.Info(f"NoAction :  {message}")

    def copyAudio(self,modelSource,modelDestination):
        """ copie d'un fichier audio et corrections du nom et des tags en fonction du modèle """
        message = "Copie du fichier " + modelSource + "\n\tvers " + modelDestination
        sourceFile = self.getFullFilePath(modelSource)
        distFile = self.getFullFilePath(modelDestination)
        if not settings.noAction:
            try:
                cmd = 'copy /Y "' + formatToUnixPath(sourceFile, reverse=True) + '" "' + \
                    formatToUnixPath(distFile, reverse = True)+ '" 2>&1'
                bot.Verbose("Commande : " + cmd)
                result = subprocess.call(cmd, shell=True)
                if result == 0:
                    bot.Detail("Copie effectuée")
                self.models[modelDestination].loadSet(distFile)
                self.models[modelDestination].save(modelDestination)
                self.hasChanged = True
                bot.Info( f"OK : Copie du fichier {sourceFile}  vers {distFile}")
                
                if settings.makeDistCopy:
                    sourceFile = self.getFullFilePath(modelDestination)
                    distFile = self.getFullFilePath(modelDestination,_DISTANT)
                    shutil.copy2(sourceFile,distFile)
                    bot.Info( f"OK : Copie du fichier {modelDestination}  de local à distant")
            except:
                raise RBCopyError(sourceFile,distFile)

        else:
                bot.Info("NoAction : " + message )
    
    def moveAudio(self,modelSource,modelDestination):
        """ transforme un fichier depuis modèle vers un autre (tags et nom)"""
        audio = self.getRelativeFilePath(modelSource)
        message = f"Renommage du fichier {audio} de {modelSource} à {modelDestination}"
        if not settings.noAction:
            try:
                sourceFile = self.getFullFilePath(modelSource)
                destFile = self.getFullFilePath(modelDestination,calc=True)
                self.models[modelSource].save(model = modelDestination )
                os.replace(sourceFile, )
                self.hasChanged = True
                bot.Info( message )
                if settings.makeDistCopy:
                    sourceFile = self.getFullFilePath(modelSource,_DISTANT)
                    destFile = self.getFullFilePath(modelDestination,_DISTANT,calc=True)
                    self.models[modelSource].loadSet(sourceFile)
                    self.models[modelSource].save(modelDestination)
                    os.replace(sourceFile, destFile)
                    shutil.copystat(self.getFullFilePath(modelDestination,_LOCAL),destFile)
            except:
                raise RBMoveError(sourceFile,destFile)
        else:
            bot.Info("NoAction : " + message )

    def manageCP(self):
        """ gestion des fichiers current et previous - fichiers les 2 plus récents pour chaque emission"""

        if self.models[_CURRENT].hasFile:
            state = self.compareModelTag(_SOURCE,_CURRENT)
            if state == _BIGGER:
                bot.Info('Fichier #current plus ancien')
                bot.Info('Fichier current remplace #previous')
                self.moveAudio(_CURRENT,_PREVIOUS)
                bot.Info('Fichier traité remplace #current')
                self.copyAudio(_SOURCE,_CURRENT)
            elif state == _SMALLER:
                bot.Info('Fichier #current plus récent')
                if not self.models[_PREVIOUS].hasFile or self.compareModelTag(_SOURCE,_PREVIOUS) == _BIGGER:
                        bot.Info('Fichier #previous plus ancien ou inexistant')
                        bot.Info('Fichier traité se duplique en #previous')
                        self.copyAudio(_SOURCE,_PREVIOUS)
                else:
                    bot.Info('Fichier #previous plus ou aussi récent')
            else:
                bot.Info('Fichier traité identique au #current')   
        else:
            bot.Info('Fichier traité se duplique en #current (inexistant)')
            self.copyAudio(_SOURCE,_CURRENT)

    def saveCorrectFileName(self):
        """ renomme le fchier audio lorsque son nom est incorrect"""
        for root in _ALL_ROOTS:
            if settings.makeDistCopy or root == _LOCAL :
                self.moveAudio(_SOURCE,_SOURCE)
 


