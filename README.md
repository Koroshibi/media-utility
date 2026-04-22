# Media Toolkit 🛠️

Application de conversion média (images, vidéos, audio) avec interface moderne
CustomTkinter, drag & drop et mise en page responsive.

---

## 🚀 Lancement rapide

Sous Windows : double-cliquez sur **`launch.bat`**.

Ou en ligne de commande :

```bash
python media_toolkit.py
```

---

## 📦 Installation

### Prérequis système

| Outil       | Rôle                       | Lien                                              |
|-------------|----------------------------|---------------------------------------------------|
| Python 3.8+ | Runtime                    | https://python.org                                |
| FFmpeg      | Conversion vidéo/audio     | https://ffmpeg.org/download.html                  |
| ImageMagick | Traitement images          | https://imagemagick.org/script/download.php       |

> `ffmpeg`, `ffprobe` et `magick` doivent être accessibles dans le **PATH**.
> L'application le vérifie au démarrage et affiche un avertissement dans le
> journal si quelque chose manque.

### Dépendances Python

```bash
pip install -r requirements.txt
```

Contenu :
- **`customtkinter`** — requis, interface graphique
- **`tkinterdnd2`** — optionnel, active le glisser-déposer. Sans lui,
  l'application fonctionne parfaitement via le bouton « + Ajouter ».

---

## ✨ Fonctionnalités

### 🖼️ Images
- **Compression** — réduire la taille (PNG, JPG, WebP, BMP, TIFF, GIF)
- **Conversion JPG** — avec fond blanc pour les images à transparence
- **Panorama 2:1** — format panorama pour articles / bannières
- Qualité réglable de 1 (compression max) à 100 (qualité max)

### 🎬 Vidéos
- **Compression** — H.264, H.265 ou VP9 avec contrôle CRF et preset vitesse
- **MP4 → WebM** — conversion VP9 avec détection automatique du canal alpha
  (yuva420p / yuv420p selon le flux source)
- Affichage en direct de la valeur CRF

### 🎵 Audio
- **Conversion MP3** — M4A, OPUS, WAV, FLAC, AAC, OGG → MP3
- Bitrate 192k, codec `libmp3lame`
- Dossier de sortie configurable (avec bouton parcourir)

---

## 🎨 Interface

- **Thème sombre moderne** (CustomTkinter)
- **Drag & Drop** si `tkinterdnd2` est installé — sinon bouton « + Ajouter »
- **Responsive** — les deux colonnes d'options passent en empilé sous 850 px
  de largeur ; tous les onglets sont scrollables pour rester utilisables sur
  petits écrans
- **Taille minimale** : 780 × 560 px (compatible laptops 1366 × 768)
- **Journal en temps réel** avec messages d'erreur FFmpeg/ImageMagick
- **Anti double-clic** sur le bouton de lancement (un seul traitement à la fois)

---

## 🛠️ Structure du projet

```
img-utility/
├── media_toolkit.py          Application principale (UI + logique)
├── launch.bat                 Lanceur Windows avec auto-install CTk
├── requirements.txt           Dépendances Python
├── README.md                  Ce fichier
├── .gitignore                 Exclusions git
│
└── [anciens scripts, conservés pour référence]
    ├── compress_images.py
    ├── compress_image_to_jpg.py
    ├── compress_panorama.py
    ├── mp3converter.py
    ├── mp4_to_webm_converter.py
    └── video_compressor_gui.py
```

---

## 🧪 Vérifier l'installation

```bash
python -c "import customtkinter; print('ctk', customtkinter.__version__)"
python -c "import tkinterdnd2; print('tkdnd ok')"
ffmpeg  -version
ffprobe -version
magick  -version
```

Les trois commandes externes doivent répondre sans erreur.

---

## 📝 Changelog

### v3.0
- Interface **responsive** : colonnes d'options qui s'empilent sur écran
  étroit, onglets scrollables, `minsize` réduit à 780 × 560.
- Correction : compression vidéo (bug `Path.with_suffix` qui levait
  `ValueError`).
- Détection canal alpha améliorée (yuva/rgba/bgra/argb/abgr/gbrap/ya8/ya16).
- Journal thread-safe, messages d'erreur ffmpeg lisibles, bouton de
  lancement désactivé pendant le traitement.
- Bouton « Parcourir » pour le dossier de sortie audio.
- Affichage de la valeur CRF à côté du slider vidéo.

---

## 📄 Licence

Utilisation personnelle. Adaptez selon vos besoins.
