# Media Toolkit

Compresser et convertir des images, des vidéos et des fichiers audio, dans une seule fenêtre.

## Utilisation

1. Double-cliquez sur **`launch.bat`** (ou `python media_toolkit.py`).
2. **Glissez vos fichiers — ou un dossier — n'importe où dans la fenêtre** (ou « + Ajouter… », `Ctrl+O`).
   Images, vidéos et audio peuvent être mélangés : le type est reconnu automatiquement
   et seules les options utiles s'affichent.
3. Cliquez sur **Convertir** (`Entrée`). Chaque ligne affiche sa progression, puis le gain de taille.
   **Annuler** (`Échap`) arrête proprement ; relancer reprend là où on s'était arrêté.

La colonne « Résultat » montre **avant de lancer** le nom exact du fichier qui sera créé.
Pour retirer des fichiers : clic sur `✕`, ou sélection (`Ctrl`/`Maj`, `Ctrl+A`) puis `Suppr`.
Pour refaire un fichier déjà traité avec d'autres réglages, redéposez-le : il repasse en attente
(et la nouvelle sortie s'appellera `nom_2`, rien n'est remplacé).

Astuce : des fichiers déposés sur `launch.bat` (ou passés en arguments) sont préchargés dans la liste.

## Ce que fait chaque mode

| Type   | Mode              | Résultat                                                                  | Fichier créé                 |
|--------|-------------------|---------------------------------------------------------------------------|------------------------------|
| Image  | Compresser        | Même format. Le curseur Qualité agit sur JPG/WebP/AVIF ; PNG, GIF, TIFF, BMP sont recompressés sans perte, transparence et animation conservées. HEIC/HEIF → JPG | `nom_compressed.ext` |
| Image  | Convertir         | Menu **Format** : JPG (fond blanc à la place de la transparence), PNG, WebP, AVIF, GIF, TIFF, BMP | `nom.ext` |
| Image  | Panorama 2:1      | JPG étiré en largeur = 2 × hauteur, fond blanc                            | `nom_compressed.jpg`         |
| Vidéo  | Compresser        | H.264, H.265 ou VP9 · CRF 0-51 (23 par défaut) · vitesse `ultrafast`…`slow` · audio 128 kb/s | `nom_compressed.ext` |
| Vidéo  | Convertir         | Menu **Format** : MP4, MKV, MOV (H.264 CRF 23 + AAC 128 kb/s, lisible partout) · WebM (VP9 CRF 30 + Opus 128 kb/s, **transparence détectée et conservée**) · MP3 (piste audio seule) | `nom.ext` |
| Audio  | —                 | Menu **Format** : MP3, M4A (AAC), Opus à 192 kb/s · OGG (Vorbis ≈ 192 kb/s) · FLAC (sans perte) · WAV (16 bits) | `nom.ext` |

Formats acceptés — images : png jpg jpeg jfif webp bmp tiff tif gif **heic heif avif** ·
vidéos : mp4 m4v avi mkv mov wmv flv webm mpg mpeg ts mts 3gp · audio : m4a opus wav flac aac ogg mp3 wma aiff.
Les autres fichiers sont ignorés, et la barre d'état le signale.

### Convertir une image

- **HEIC** (photos d'iPhone) : lu, jamais écrit — ImageMagick ne sait pas l'encoder. « Convertir » propose donc
  JPG, PNG, WebP… et « Compresser » un HEIC donne un JPG.
- Les photos sortent **à l'endroit** : l'orientation du téléphone est appliquée à l'image elle-même, y compris
  vers GIF ou BMP qui ne savent pas la noter.
- JPG, PNG, BMP et AVIF ne contiennent qu'une image : d'un GIF animé, d'un TIFF multipage ou d'un HEIC qui en
  contient plusieurs, seule la première est gardée. WebP, GIF et TIFF gardent l'animation ou les pages.
- Vers PNG, GIF, TIFF ou BMP, le curseur Qualité est grisé : ces formats sont sans perte (GIF : 256 couleurs).

### Résolution

Chaque bloc (Images, Vidéos) a un menu **Résolution**, réglé sur « Originale » par défaut. Il fonctionne avec
tous les modes, **réduit seulement, n'agrandit jamais**, et conserve toujours les proportions :

- **Images** — `3840 / 2560 / 1920 / 1280 / 800 px max` : le plus grand côté est ramené à cette valeur
  (une photo 4000 × 3000 en « 1920 px max » devient 1920 × 1440). Ou `75 % / 50 % / 25 %` de la taille d'origine.
  En mode Panorama, le résultat reste exactement 2:1 (« 1920 px max » donne 1920 × 960).
  Les GIF et WebP animés gardent toutes leurs images.
  Captures d'écran, logos et GIF à aplats : le lissage dû à la réduction peut alourdir un fichier sans perte
  (la ligne indique alors « plus gros ») ; dans ce cas, préférez « Convertir en JPG ».
- **Vidéos** — `2160p / 1440p / 1080p / 720p / 480p / 360p` : c'est le **petit côté** qui est ramené à cette
  valeur, donc « 720p » donne 1280 × 720 pour une vidéo horizontale et 720 × 1280 pour une vidéo verticale
  de téléphone. Les dimensions sont arrondies au nombre pair inférieur (exigé par les encodeurs).
  Une vidéo entrelacée (caméscope, DV, enregistrement TV) est désentrelacée avant d'être réduite.

H.264 sort toujours en 8 bits 4:2:0, le seul profil réellement lisible partout (téléviseurs, navigateurs,
téléphones). Si le conteneur d'origine ne peut pas contenir le codec choisi (ex. H.264 dans un `.avi` ou un `.webm`),
la sortie passe en `.mp4` (ou `.webm` pour VP9) et le journal le signale.

## Où vont les fichiers

Réglage **Sortie** :

- **À côté des originaux** (par défaut)
- **Sous-dossier** : `compressed/` (images, vidéos) ou `converted_<format>/` (audio : `converted_mp3/`,
  `converted_flac/`…), à côté de chaque original
- **Dossier choisi** : le dossier sélectionné avec « Parcourir… »

**Rien n'est jamais écrasé.** Si le nom est déjà pris (y compris par l'original lui-même, ex. JPG → JPG),
la sortie devient `nom_2`, `nom_3`… L'écriture se fait dans un fichier `.part` renommé seulement en cas
de succès : une annulation ou un échec ne laisse aucun fichier à moitié écrit.

## Installation

| Outil                 | Rôle            | Lien                                         |
|-----------------------|-----------------|----------------------------------------------|
| Python 3.8+           | Runtime         | https://python.org                           |
| FFmpeg (+ ffprobe)    | Vidéo et audio  | https://ffmpeg.org/download.html             |
| ImageMagick 7         | Images          | https://imagemagick.org/script/download.php  |

`ffmpeg`, `ffprobe` et `magick` doivent être dans le **PATH**. S'il en manque un, un bandeau rouge
l'indique au démarrage et seul le type de média concerné est désactivé.

HEIC et AVIF passent par le module `heic` d'ImageMagick, inclus dans l'installateur Windows officiel :
`magick -list format` doit afficher les lignes `HEIC` et `AVIF`.

`launch.bat` installe tout seul les deux paquets Python au premier lancement. À la main :

```bash
pip install -r requirements.txt
```

## Vérifier

```bash
python media_toolkit.py --selftest
```

Teste, sans interface ni ffmpeg, les règles qui protègent vos fichiers (nommage, anti-écrasement,
choix du conteneur, arguments des encodeurs). Doit afficher `selftest OK`.

## Changements par rapport à la v3

- Nouvel habillage : palette ardoise avec un seul accent vert sauge, une teinte douce par type de média
  (images, vidéos, audio), écran d'accueil illustré, lignes colorées selon l'état (en cours, OK, échec) —
  l'état reste toujours écrit en toutes lettres. Aucune dépendance ni fichier d'image ajouté.
- Nouveau : menu **Résolution** pour les images et les vidéos (voir plus haut).
- Nouveau : **conversion de format**. « Convertir en JPG » et « Convertir en WebM » deviennent « Convertir »
  avec un menu Format (JPG, PNG, WebP, AVIF… · MP4, WebM, MKV, MOV, MP3), et l'audio a un menu Format
  (MP3 par défaut, comme avant). Photos HEIC, HEIF et AVIF acceptées.
  La fenêtre fait au minimum 720 × 520 (620 journal ouvert) pour que images, vidéos et audio tiennent ensemble.
- Une seule liste au lieu de trois onglets ; glisser-déposer sur toute la fenêtre, dossiers acceptés.
- Barre de progression, pourcentage par fichier, bouton Annuler, bilan des tailles.
- Retrait du fichier de son choix (avant : seulement le dernier).
- Plus aucun écrasement (avant : `-y` partout, et « Convertir en JPG » sur un seul `.jpg` écrasait l'original).
- Compresser une image ne détruit plus la transparence ni l'animation (avant : aplatie sur fond blanc).
- Compresser un `.webm` fonctionne (avant : échec, H.264 + AAC impossibles dans ce conteneur). Les `.avi`,
  `.wmv`, `.flv` compressés sortent désormais en `.mp4`, lisible partout.
- Panorama 2:1 : ImageMagick au lieu de ffmpeg — même étirement, vraie échelle de qualité 1-100,
  fond blanc (avant : noir) sous la transparence.
- Sorties créées à côté des originaux par défaut (avant : MP3 dans `converted_mp3/` du dossier de l'appli,
  et « Convertir en JPG » de plusieurs fichiers dans `compressed/`) ; **Sortie > Sous-dossier** retrouve
  l'ancien rangement.
- La liste des extensions acceptées est élargie, mais le filtre « Tous les fichiers » a disparu : l'extension
  sert à reconnaître le type.
- La conversion en WebM et la compression VP9 conservent aussi la transparence d'un WebM déjà transparent.
- Un fichier en échec n'arrête plus le lot ; le journal affiche la vraie cause.

Les anciens scripts (`compress_*.py`, `mp3converter.py`, `mp4_to_webm_converter.py`,
`video_compressor_gui.py`) sont conservés pour référence ; l'application ne les utilise pas.

## Licence

Utilisation personnelle. Adaptez selon vos besoins.
