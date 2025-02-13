# Botag 

**Botag** est un outil automatique de taggage ID3 qui extrait les informations des noms de fichiers audio pour définir les tags ID3.  
Son but initial est d'insérer des émissions dans une base de données d'un logiciel de diffusion radio par l'intermédiaire des tags MP3  
Le nom des fichiers audio doit contenir des informations nécessaires à son étiquettage.  
Les règles de lectures des noms et d'écriture des tags sont régies par des expression régilières paramétrables   
Les paramètres sont contenus dans botag.ini mais peuvent être surchargés via les paramètres en ligne de commande  

## Fonctionnalités ##

- **Taggage automatique** : Extrait automatiquement les informations des noms de fichiers audio.
- **Analyse automatisable** de fichiers log de mise à jour de fichiers ou  de répertoire
- **Synchronisation** possible sur 2 dépots différents
- **Gestion automatisée** des plus récentes émissions crées pour rediffusion automatique
- **Logs** complets

## Installation ##

Pour installer Botag, vous pouvez cloner ce dépôt et installer les dépendances nécessaires :

bash
git clone https://github.com/day811/botag.git
cd botag
pip install -r requirements.txt

## Utilisation ##

> python botag.py  
  -> lance le programme avec les paramètres du fichier botag.ini
> python botag.py --noaction True   
  -> lance le programme avec les paramètres du fichier botag.ini mais n'effectue pas de mise à jour
> python botag.py --scanDirectory True --scanAudioFilter 'emissionA' --scanPathFilter 'janvier'  
  ->lance le programme en sélectionnant les répertoires contenant 'janvier' et les nom d'émission 'emissionA'

## Liste des émissions ##
Un fichier doit contenir les émissions devant être traitées, ses possibles alias(émisions renommées) et le traitement automatique éventuel du dernier enregistrement
Format de ligne : 
**nomprog,currentStauts,Alias1,Alias2...**


## Liste des paramètres ##

- progFileTxt : Chemin vers le fichier des émissions de la Radio.
- noAction : Si True, exécute le programme sans effectuer de changements.
- makeDistCopy : Si True, effectue également les modifications sur les fichiers distants.
- autoCorrectFilename : Si True, renomme les fichiers lorsque l'artiste est détecté mais mal orthographié.
- excludedPaths : Liste des mots-clés pour exclure certains fichiers du traitement.
- testEnv : Si True, utilise les chemins en mode test.
- changeLimit : Limite le nombre de fichiers traités.
- syncPath : Chemin vers le dossier des logs de synchronisation 
- syncSignature : Signature pour identifier les fichiers log.
- syncActionLine0, syncActionLine1, syncActionLine2 : Expressions régulières pour identifier les lignes mentionnant des fichiers à traiter.
- scanDirectory : Si True, scanne le répertoire scanSubDir dans rootLocal.
- scanAudioFilter : Filtre inclusif à appliquer au paramètre précédent.
- scanPathFilter : Filtre inclusif à appliquer au paramètre précédent.
- allowedExtensions : Extensions autorisées pour les fichiers audio.
- localRoot : Chemin racine pour les fichiers locaux.
- distRoot : Chemin racine pour les fichiers distants.
- currentPath : Sous-chemin où sont stockés les fichiers current et previous.
- audioSignature : Signature pour extraire les tags à partir du nom du fichier.
- logScreenLevel : Niveau de filtrage des logs affichés à l'écran.
- logFileLevel : Niveau de filtrage des logs écrits dans le fichier.
- logPath : Chemin vers les fichiers logs générés.
- logMask : Base du nom des fichiers logs.
- logRotation : Si True, supprime automatiquement les logs de synchronisation et de taggage.
- logLimit : Nombre de jours de rétention des fichiers logs.
