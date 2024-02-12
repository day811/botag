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
_TITLE = 'title'
_ALL_KEYS = {_ARTIST : ['A:','Artiste'],_YEAR: ['Y:','Année'],_TRACK: ['P:','Piste'],
            _TITLE: ['T:','Titre'],_LENGTH: ['L:','Longuer'], _RAW_TITLE: ['C','Titre court']}
_READ_FILE_KEYS = [_ARTIST,_YEAR,_TRACK,_TITLE,_LENGTH]
_SAVE_FILE_KEYS = [_ARTIST,_YEAR,_TRACK,_TITLE]
_READ_FILENAME_KEYS = [_ARTIST,_YEAR,_TRACK,_RAW_TITLE]
_FNAME_TITLE_SUM_KEYS = [_YEAR,_TRACK,_RAW_TITLE]
_CURRENT = 'current'
_PREVIOUS = 'previous'
_LOCAL = 'local'
_DISTANT = 'distant'
_FILE = 'file'
_FILENAME = 'filename'
_PHY_MODELS = [_FILE,_CURRENT,_PREVIOUS]
_CURRENT_PREVIOUS = [_CURRENT, _PREVIOUS]
_ALL_ROOTS = [_LOCAL,_DISTANT]

_OLDER = 1
_NEWER = 2
SAME = 3

def getErrorMmessage():
    exc_type, exc_value, exc_tb = sys.exc_info()
    stack_summary = traceback.extract_tb(exc_tb)
    end = stack_summary[-1]

    err_type = type(exc_type).__name__
    err_msg = str(exc_value)
    date = datetime.strftime(datetime.now(), "%B %d, %Y at precisely %I:%M %p")
    message = f"{err_type} dans {end.filename} / {end.name} en line {end.lineno} with the error message: {err_msg}.\n"
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
        message = f'lors de l\'écriture du fichier audio {filename}'
        super().__init__(message)

class RBCopyError(RBException):
    def __init__(self, fromFile,toFile) -> None:
        message = f'lors de la copie du fichier {fromFile} vers {toFile}'
        super().__init__(message)

class Engine():

    def __init__(self,screenLevel,fileLevel) -> None:

        self.audio = None
        self.wrapper = None
        self.logFilename = None
        self.screenLevel = screenLevel
        self.fileLevel = fileLevel
        self.countAttention = 0
        self.countError = 0
        self.history = ''
        self.timeStamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.changeCount = 0
 
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        self.close()
    
        return False
    
    def close(self):
        if self.history is not None and self.logFilename is not None:
            if self.countError:
                self.logFilename += '_[ERREUR]'
            elif self.countAttention:
                self.logFilename += '_[ATTENTION]'
            self.logFilename +='.log'
            if self.open():
                self.wrapper.write(self.history)
                self.history = None
                self.wrapper.close()
        logFilename = formatToUnixPath(bot.logFilename)
 
    def open(self):

        try:
            self.wrapper = open(self.logFilename ,"w",encoding="utf-8")
        except:
            print("Création impossible du fichier des logs : " + self.logFilename )
            input("Tapez une touche pour terminer ou fermez cette fenêtre")
            exit()
        else:
            return True        

    def launchActions(self,fileID):
        try:
            self.Info("Fichier sélecionné : " + fileID['relpath'] + fileID[_FILENAME])
            self.audio = AudioFile(fileID)

            self.Info("Emission/artiste présent dans la liste des émissions : " + self.audio.getTag(_ARTIST) )
                # need to update tags
            if not self.audio.checkTags():
                self.Info("Fichier incorrectement taggé - > sauvegarde des tags")
                self.audio.correctFileTagsInfo()
            else:
                self.Info("Fichier correctement taggé - > aucune action")
            if self.audio.processCP:
                #les fichiers currents et previous doivent étre gérés
                self.audio.manageCP()
            else:
                self.Info("Pas de gestion des current/previous pour ce fichier")
            # vérifie que l'orthographe de l'artiste dans le nom du fichier soit celui par défaut
            if strCompare(self.audio.getTag(_ARTIST,_FILENAME),self.audio.getTag(_ARTIST,_FILE)) < 2:
                # fichier incorrrectement nommé
                if settings.autoCorrectFilename:
                    self.Info("Fichier incorrectement nommé -> renommage")
                    self.audio.saveFileName()
                else:
                    self.Warning("Fichier incorrectement nommé mais pas de renommage - voir RBTagger.ini")

            if self.audio.hasChanged:
                self.changeCount +=1
        except RBException as e:
            self.Error(str(e))        
        except Exception as e:
            self.Error(getErrorMmessage())
            self.Error(f"Erreur non gérée : fin du traitement du fichier audio" )

    def start(self,_setting):
        global settings
        settings = _setting

        self.scanList = {_setting.logPath:_setting.logMask,_setting.syncPath : _setting.syncSignature}
        self.screenLevel = _setting.logScreenLevel
        self.fileLevel = _setting.logFileLevel
        if self.fileLevel > 0:
            self.logFilename = _setting.logPath + _setting.logMask + '_' + datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.Info('Logger démarré')
    
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
        
    def rotate(self):

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
        # p_destintion : 0:term 1:logfile 2:both

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

        if p_level <= self.fileLevel:
            self.history += now  + message + '\n'

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

    def getLastFile(self,directory,filter):

        # get last diff logfile path
        # l'ordre alphabétique des fichiers diff est aussi chronoligque

        self.dirname = directory
        my_files = sorted( os.listdir(self.dirname),reverse=True)
        #ajd=datetime.now().strftime("%Y-%m-%d")
        selected = ""
        if my_files:
            for my_file in my_files:
                matches = re.search(filter,my_file,re.IGNORECASE)
                if matches:
                    # sélectionne le premmier ok
                    selected = my_file
                    self.Detail(f"{my_file} : OK")
                    break
                else:
                    self.Verbose("Fichier pas OK "+ my_file)
            return selected
        else:
            self.Error("Le répertoire des logs différentiels Vide")
            return None

bot = Engine(1,3)

def formatToUnixPath(path,isDir=False,reverse = False):
    path = re.sub('\\n','',path)
    fromSep = "\\"
    toSep = "/"
    if reverse:
        fromSep = '/'
        toSep = r"\\"
    newPath =  path.replace(fromSep,toSep)
    if isDir and newPath[-1:] != toSep : 
        newPath += toSep
    return newPath

def normalizeName(a) -> str:
    """ retoune une chaine de caractères uniquement alphanumérique en minuscule et sans accent."""
    return re.sub(r'[\W_]+', '', removeAccents(a.lower()))

def removeAccents(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')

def strCompare(a,b) -> int:
    if a == b:
        return 2
    if (normalizeName(a) == normalizeName(b)):
        return 1
    return 0

def formatLasting(lasting):
            length = float(lasting)
            minutes = "{:02d}".format(int(length // 60))
            seconds = "{:02d}".format(int(round(length % 60)))
            return '(' + ":".join([minutes, seconds]) + ')'

def striptFilePath(fullPathname):
    global settings
    
    pathTab = fullPathname.rsplit('/',maxsplit=1)
    path = pathTab[0]
    find = '(' + '|'.join(settings.root[x] for x in settings.root)+ r')(.*)'
    match = re.search(find,path,re.I)
    if match:
        return match.group(2)+'/',pathTab[1]
    else:
        return None,None

class TagsSet(list):
    """ Classe permettant d'accéder aux fonctions de mutagen. """

    
    def __init__(self,model,root=_LOCAL,fullPathname='') :
        self.keys = {}
        self.model = model
        self.root = root
        self.audio = None
        self.tags={}

        if model in _PHY_MODELS:
            self.loadfromFile(fullPathname)
            
    def __str__(self) -> str:
           return " ".join( _ALL_KEYS[key][0] + self.keys[key] for key in _SAVE_FILE_KEYS)
    
    def loadfromFile(self,fullPathName):
        try:
            self.tags = MP3(fullPathName, ID3=EasyID3)
            # print(self.tags.valid_keys.keys())
        except:
            # le fichier ne possède aucun tag
            self.tags = mutagen.File(fullPathName, easy=True)
            self.tags.add_tags()
        finally:
            for key in _READ_FILE_KEYS:
                self.keys[key] = self.readTag(key)

            if self.model in _CURRENT_PREVIOUS:
                self.keys[_TITLE] = re.sub(self.model + '-','',self.keys[_TITLE],re.IGNORECASE)
            return True

    
    def loadFromTags(self,tags):
        pass

    def readTag(self,Key) -> str:
        try:
            if Key == _LENGTH:
                return self.tags.info.length
            else:
                return self.tags[Key][0]
        except:
            self.tags[Key] = ''
            return ''
 
    def save(self):
        for key in _READ_FILE_KEYS :
            if key != _LENGTH :
                self.tags[key] = self.keys[key] 
        try:
            self.tags.save()
        except:
            raise RBTagError(self.model, self.root)

class Scanner():

    
    def __init__(self,lineFilter):
        
        self.files = []
        self.audioFilter = settings.audioSignature + r'\.(' + "|" . join(settings.allowedExtensions) + ')'
        self.nbLinesFilter = 1
        self.lineFilter = lineFilter
        self.length = 0
        self.render = None
        self.currentLine = 0
        
    def __enter__(self):

        self.getFiles()
        if self.files:
            self.files.sort(key = lambda x : x['normfilename'],reverse=True)
            return self.files
        return []

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def sortFilename(taglist):
        artist = normalizeName(taglist[0])

        pass

    def checkArtist(self,artist) -> bool:
        """ returns if file is  referenced in radio programms txt file"""
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
        finder = re.compile(self.audioFilter,re.I)
        match = finder.findall(filename)
        if match:
            res = match[0]
            if len(res)==5:
                artist = res[0] 
                artistInfo = self.checkArtist(artist)
                if artistInfo:
                    date = res[1] 
                    tracknumber = res[2]
                    title = res[3]
                    extension = res[4]
                    normfilename = re.sub(artist,artistInfo['rawartist'], filename.lower())
                    info = {_YEAR : date, _TRACK : tracknumber, _RAW_TITLE : title, _FILENAME : filename,
                            'normfilename' : normfilename, 'relpath' : relpath, 'ext' : extension}
                    info.update(artistInfo)
                    return info
                else:
                    bot.Warning(f'{relpath}{filename} : Artiste {artist} non présent dans la liste des émissions')
        else:
            bot.Info(f'{relpath}{filename} : Format de nom de fichier incorrect, analyse impossible')
        return False

    def captureFind(self, find):
        return  '(' + find[self.currentLine] + ')'
    

    def getFileID(self,line):

        try:
            line = formatToUnixPath(line)
            bot.Detail("Ligne analysée :" + line)
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
                    filepath = match.group(2)
                    relpath,filename = striptFilePath(filepath)
                    self.nbLinesFilter = 1
                    self.currentLine = 0
                    if self.hasNotExcludedFilePath(relpath, filename):
                        fileID = self.matchAudio(relpath, filename)
                        if fileID:
                            bot.Info('Fichier OK: ' + relpath + filename )
                            return fileID
                else:
                    bot.Detail("Pas de correspondance")
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
    
    def getFiles(self):
        
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

    def __init__(self):
        
        super().__init__([['(^)(.*)']])
        self.directoryName = settings.root[_LOCAL]


    def getFiles(self):
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

        self.tags={_FILE : None, _CURRENT : None, _PREVIOUS : None,_FILENAME:None}
        self.hasChanged = False
        key = r'(' + '|'.join(settings.root.values()) + r')(.+/)(.+)\.' \
            + r'(' + '|'.join(settings.allowedExtensions) + r')'
        
        self.filename = fileID[_FILENAME]
        self.relativePath = fileID['relpath']
        self.extension = fileID['ext']
        self.processCP = fileID['processCP']
        tag = TagsSet(_FILENAME)
        for key in _READ_FILENAME_KEYS:
            tag.keys[key] = fileID[key] 
        tag.keys[_TITLE] = '-'.join(tag.keys[x] for x in _FNAME_TITLE_SUM_KEYS if tag.keys[x])
       
        self.tags[_FILENAME] = tag

        for root in settings.root.keys():
            path = self.getFullFilePath(_FILE,root)
            if (root == _LOCAL or settings.makeDistCopy) and not os.path.exists(path) :
                raise RBFileNotFound(path)

    def loadAllTags(self):

        self.tags[_FILE] = self.loadTags(_FILE,_LOCAL)
        self.tags[_FILENAME].keys[_TITLE] += ' ' + formatLasting(self.tags[_FILE].keys[_LENGTH])
        if self.processCP:
            for model in _CURRENT_PREVIOUS :
                self.tags[model] = self.loadTags(model,_LOCAL)
        
    def loadTags(self,model=_FILE,root=_LOCAL):
        if model != _FILENAME:
            fullPathName = self.getFullFilePath(model,root)
            if not os.path.exists(fullPathName):
                bot.Info("Fichier " + fullPathName + " inexistant : lecture tag impossible")
                return None
            return TagsSet(model,root,fullPathName)
        else:
            return TagsSet(model,root)

    def getFullFilePath(self,model=_FILE,root=_LOCAL):
        return self.getRootDir(root) + self.getRelativeFilePath(model)

    def getRelativeFilePath(self,model=_FILE):
        return self.getRelativePath(model)  + self.getFileName(model)

    def getFileName(self,model=_FILE):
        tags = self.tags[_FILENAME]
        
        if model == _FILE:
            return self.filename
        elif model == "filename":
            return "#".join(tags.keys[x] for x in _READ_FILENAME_KEYS if tags.keys[x]) + "." + self.extension
        elif model in _CURRENT_PREVIOUS: 
            return "#".join([tags.keys[_ARTIST],model]) + "." + self.extension

    def getRootDir(self,root=_LOCAL):
            return settings.root[root]

    def getModelRootDir(self,model=_FILE,root=_LOCAL):
        return self.roodir(root) + self.getRelativePath(model)
    
    def getRelativePath(self,model):
        if model == _FILE:
            return  self.relativePath
        else:
            return  settings.currentPath 
    
    def getRealName(self):
        return self.tags[_FILENAME].artist
    
    def getTag(self, key, model = _FILENAME, root = _LOCAL):
        return self.tags[model].keys[key]
        
        return self.tags[model].keys[key]

       # détermine la soure de synchro

    def audioIsNewer(self,modelA,modelB):
        if self.tagsAreSame(modelA,modelB) : return SAME
        if self.tags[modelA].keys[_TITLE] > self.tags[modelB].keys[_TITLE]: 
            return _NEWER
        else:
            return _OLDER
    
    def tagsAreSame(self,modelA,modelB):
        if modelA and modelB :
            return (self.tags[modelA].keys[_TITLE] == self.tags[modelB].keys[_TITLE])
        else:
            return False
    
    def artistsAreSame(self,modelA,modelB):
        isok = self.tags[modelA].artist == self.tags[modelB].artist
        if modelA and modelB :
            if not isok:
                bot.Detail( self.tags[modelA].artist + " != " + self.tags[modelB].artist)
            return isok
        else:
            return False
         
    def checkTags(self):
        self.loadAllTags()
        bot.Detail("Tags calculés à partir du nom du fichier : " + str(self.tags[_FILENAME]))
        bot.Detail("Tags enregistrés dans le fichier         : " + str(self.tags[_FILE]))
        if not self.tagsAreSame(_FILENAME,_FILE):
            return False
        return True

    def correctFileTagsInfo(self):

        if not settings.noAction:
            try:
                message = "Modification locale des tags ID3"
                root = _LOCAL
                self.copyTags(self.tags[_FILENAME],self.tags[_FILE])    
                bot.Info("OK local : " + message)
                if settings.makeDistCopy:
                    root = _DISTANT
                    distantTags = self.loadTags(_FILE,root)
                    self.copyTags(self.tags[_FILENAME],distantTags)  
                    bot.Info("OK distant : " + message)
            except:
                raise RBTagError(_FILE,root)
        else:
            bot.Info("NoAction : Commande modification des tags ID3 non exécutée")

    def copyAudio(self,modelSource,modelDestination):
        message = "Copie du fichier " + modelSource + " vers " + modelDestination
        sourceFile = self.getFullFilePath(modelSource)
        distFile = self.getFullFilePath(modelDestination)
        if not settings.noAction:
            if modelDestination in (_CURRENT,_PREVIOUS):
                try:
                    cmd = 'copy /Y "' + formatToUnixPath(sourceFile, reverse=True) + '" "' + \
                        formatToUnixPath(distFile, reverse = True)+ '" 2>&1'
                    bot.Verbose("Commande : " + cmd)
                    if subprocess.call(cmd, shell=True):
                        bot.Detail("Copie effectuée")
                    newTags = self.loadTags(modelDestination,_LOCAL)
                    newTags.keys[_TITLE] = "-".join([modelDestination, newTags.keys[_TITLE]])
                    newTags.save()
                    self.tags[modelDestination] = newTags 
                    self.hasChanged = True
                    bot.Info( f"OK : Copie du fichier {sourceFile}  vers {distFile}")
                    sourceFile = self.getFullFilePath(modelDestination)
                    distFile = self.getFullFilePath(modelDestination,_DISTANT)
                    if settings.makeDistCopy:
                        shutil.copy2(sourceFile,distFile)
                        bot.Info( f"OK : Copie du fichier {modelDestination}  de local à distant")
                except:
                    raise RBCopyError(sourceFile,distFile)

        else:
                bot.Info("NoAction : " + message )
    
    def renameAudio(self,modelSource,modelDestination):

        message = "Renommage du fichier " + modelSource + " en " + modelDestination
        if not settings.noAction:
            try:
                if modelDestination in (_CURRENT,_PREVIOUS):
                    self.tags[modelSource].keys[_TITLE]  = modelDestination + "-" +self.tags[modelSource].keys[_TITLE] 
                    self.tags[modelSource].save()
                    os.replace(self.getFullFilePath(modelSource), self.getFullFilePath(modelDestination))
                    self.hasChanged = True
                    bot.Info( message )
                if settings.makeDistCopy:
                        #shutil.copy2(self.getFullFilePath(modelDestination),self.getFullFilePath(modelDestination,_DISTANT))
                    if modelDestination in (_CURRENT,_PREVIOUS):
                        distTags = self.loadTags(modelSource,_DISTANT)
                        if distTags:
                            distTags.keys[_TITLE]  = modelDestination + "-" + distTags.keys[_TITLE] 
                            distTags.save()
                    os.replace(self.getFullFilePath(modelSource,_DISTANT), self.getFullFilePath(modelDestination,_DISTANT))
                    shutil.copystat(self.getFullFilePath(modelDestination,_LOCAL),self.getFullFilePath(modelDestination,_DISTANT))
            except:
                bot.Error('Erreur fatala lors de ' + message)
        else:
            bot.Info("NoAction : " + message )

    def copyTags(self,sourceTags,destTags):
            
        for key in _SAVE_FILE_KEYS:
            destTags.keys[key] = sourceTags.keys[key]
        if destTags.model in _CURRENT_PREVIOUS:
            destTags.keys[_TITLE] = '-'.join(destTags.model , destTags.keys[_TITLE] )
        destTags.save()


    def manageCP(self):
        #spn_current : emplacement court du fichier current local relatif au dossier root 5bYAYUk9vv8Lfn9*

        if self.tags[_CURRENT] is not None:
            state = self.audioIsNewer(_FILE,_CURRENT)
            if state == _NEWER:
                bot.Info('Fichier #current plus ancien')
                bot.Info('Fichier current remplace #previous')
                self.renameAudio(_CURRENT,_PREVIOUS)
                bot.Info('Fichier traité remplace #current')
                self.copyAudio(_FILE,_CURRENT)
            elif state == _OLDER:
                bot.Info('Fichier #current plus récent')
                if self.tags[_PREVIOUS] is None or self.audioIsNewer(_FILE,_PREVIOUS) == _NEWER:
                        bot.Info('Fichier #previous plus ancien ou inexistant')
                        bot.Info('Fichier traité se duplique en #previous')
                        self.copyAudio(_FILE,_PREVIOUS)
                else:
                    bot.Info('Fichier #previous plus ou aussi récent')
            else:
                bot.Info('Fichier traité identique au #current')   
        else:
            bot.Info('Fichier traité se duplique en #current (inexistant)')
            self.copyAudio(_FILE,_CURRENT)

    def saveCorrectFileName(self):
        for root in (_LOCAL,_DISTANT):
            if settings.makeDistCopy :
                self.renameAudio(_FILE,_FILENAME)
 


