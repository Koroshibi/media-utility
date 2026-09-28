#!/usr/bin/env python3
"""Media Toolkit — une fenêtre, une liste : déposez des images, vidéos ou fichiers audio.

Le type est détecté par l'extension ; seules les options utiles s'affichent.
    Images : compresser / convertir (JPG, PNG, WebP, AVIF…) / panorama 2:1   (ImageMagick, HEIC lu)
    Vidéos : compresser H.264-H.265-VP9 / convertir (MP4, WebM, MKV, MOV, MP3) (ffmpeg)
    Audio  : convertir (MP3, M4A, OGG, Opus, FLAC, WAV)                      (ffmpeg)
    Résolution (images et vidéos) : réduction optionnelle, jamais d'agrandissement, proportions conservées.

Aucun fichier n'est jamais écrasé : en cas de collision la sortie devient nom_2, nom_3…

    python media_toolkit.py [fichiers ou dossiers…]
    python media_toolkit.py --selftest
"""

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import traceback
from datetime import datetime
from pathlib import Path
from tkinter import TclError, filedialog, messagebox, ttk

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

KINDS = {
    "image": {".png", ".jpg", ".jpeg", ".jfif", ".webp", ".bmp", ".tiff", ".tif", ".gif", ".heic", ".heif", ".avif"},
    "video": {".mp4", ".m4v", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm", ".mpg", ".mpeg", ".ts", ".mts", ".3gp"},
    "audio": {".m4a", ".opus", ".wav", ".flac", ".aac", ".ogg", ".mp3", ".wma", ".aiff"},
}
EXT2KIND = {ext: kind for kind, exts in KINDS.items() for ext in exts}
NAMES = {"image": ("Image", "Images"), "video": ("Vidéo", "Vidéos"), "audio": ("Audio", "Audio")}
NEED = {"image": ["magick"], "video": ["ffmpeg", "ffprobe"], "audio": ["ffmpeg", "ffprobe"]}
IMG_MODES = {"Compresser": "compress", "Convertir": "convert", "Panorama 2:1": "panorama"}
VID_MODES = {"Compresser": "compress", "Convertir": "convert"}
# « Convertir » : format de sortie choisi dans un menu. HEIC/HEIF ne sont qu'en entrée : ImageMagick sait les lire,
# pas les écrire.
IMG_FORMATS = {"JPG": ".jpg", "PNG": ".png", "WebP": ".webp", "AVIF": ".avif", "GIF": ".gif", "TIFF": ".tiff",
               "BMP": ".bmp"}
VID_FORMATS = {"MP4": ".mp4", "WebM": ".webm", "MKV": ".mkv", "MOV": ".mov", "MP3 (audio seul)": ".mp3"}
AUD_FORMATS = {"MP3": ".mp3", "M4A (AAC)": ".m4a", "OGG": ".ogg", "Opus": ".opus", "FLAC": ".flac", "WAV": ".wav"}
# encodeur ffmpeg + débit. Vorbis en qualité 6 (≈ 192 kb/s) : en débit fixe il refuse les sources à 96 kHz.
AUDIO_ARGS = {".mp3": ["libmp3lame", "-b:a", "192k"], ".m4a": ["aac", "-b:a", "192k"],
              ".ogg": ["libvorbis", "-q:a", "6"], ".opus": ["libopus", "-b:a", "192k"], ".flac": ["flac"],
              ".wav": ["pcm_s16le"]}
FORMAT_HINTS = {
    ".jpg": "Fond blanc à la place de la transparence.",
    ".png": "Sans perte, transparence conservée.",
    ".webp": "Plus léger que JPG, transparence et animation conservées.",
    ".avif": "Encore plus léger, transparence conservée, mais pas lu par tous les logiciels.",
    ".gif": "256 couleurs, transparence et animation conservées.",
    ".tiff": "Sans perte, transparence et pages conservées.",
    ".bmp": "Sans compression : fichier lourd.",
    ".mp4": "H.264 CRF 23 + AAC 128 kb/s, lisible partout",
    ".mkv": "H.264 CRF 23 + AAC 128 kb/s",
    ".mov": "H.264 CRF 23 + AAC 128 kb/s",
    ".webm": "VP9 CRF 30 + Opus 128 kb/s, transparence détectée automatiquement",
    ".mp3": "192 kb/s, lisible partout",
    ".m4a": "AAC 192 kb/s",
    ".ogg": "Vorbis ≈ 192 kb/s",
    ".opus": "192 kb/s",
    ".flac": "Sans perte",
    ".wav": "16 bits, non compressé : fichier lourd",
}
# Résolution : on réduit, on n'agrandit jamais, proportions conservées.
# Images = géométrie ImageMagick (« > » : seulement si plus grand) sur le GRAND côté, ou pourcentage.
IMG_SIZES = {"Originale": None, "3840 px max": "3840x3840>", "2560 px max": "2560x2560>", "1920 px max": "1920x1920>",
             "1280 px max": "1280x1280>", "800 px max": "800x800>", "75 %": "75%", "50 %": "50%", "25 %": "25%"}
# Vidéos = PETIT côté en pixels : « 1080p » vaut donc aussi pour une vidéo verticale de téléphone.
VID_SIZES = {"Originale": None, "2160p (4K)": 2160, "1440p": 1440, "1080p (Full HD)": 1080, "720p (HD)": 720,
             "480p": 480, "360p": 360}
CODECS = {"H.264 – compatible partout": "libx264", "H.265 – plus petit": "libx265", "VP9 – WebM": "libvpx-vp9"}
PRESETS = ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"]
DESTS = ["À côté des originaux", "Sous-dossier", "Dossier choisi"]
ALPHA = ("yuva", "rgba", "bgra", "argb", "abgr", "gbrap", "ya8", "ya16")
MAGICK_FMT = {".jpeg": "jpg", ".jfif": "jpg", ".tif": "tiff"}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)  # pas de console qui clignote sous pythonw
# Palette « calme » : ardoise, un seul accent sauge. Tout le thème CTk en découle (apply_theme), sans fichier .json.
BG, SURFACE, RAISED, LINE = "#1b1e23", "#21252b", "#2a2f37", "#343a44"
FG, MUTED, FAINT = "#e4e7eb", "#9aa3af", "#6b7480"
ACCENT, ACCENT_HOVER, ON_ACCENT, SELECT = "#6fbfae", "#82cdbd", "#0f1f1c", "#2f5a54"
FAIL = "#ee9d94"
KIND_COLORS = {"image": "#8fb8e0", "video": "#e3a5bf", "audio": "#e0c48c"}  # accueil + intitulés des options
KIND_ICONS = {"image": "\ue8b9", "video": "\ue714", "audio": "\ue8d6"}  # Segoe Fluent Icons / MDL2 (Windows)
# tags du Treeview : (texte, fond). Le texte de la ligne dit toujours l'état, la couleur ne fait que l'appuyer.
ROW_COLORS = {"run": (ACCENT, "#22383a"), "ok": ("#9ccfa6", ""), "fail": (FAIL, "#3a2729")}
THEME = {
    "CTkLabel": {"text_color": FG},
    "CTkButton": {"fg_color": "transparent", "hover_color": RAISED, "border_color": LINE, "border_width": 1,
                  "corner_radius": 8, "text_color": FG, "text_color_disabled": FAINT},  # « fantôme » par défaut
    "CTkSegmentedButton": {"fg_color": RAISED, "unselected_color": RAISED, "unselected_hover_color": LINE,
                           "selected_color": SELECT, "selected_hover_color": SELECT, "text_color": FG,
                           "text_color_disabled": FAINT, "corner_radius": 14},
    "CTkOptionMenu": {"fg_color": RAISED, "button_color": RAISED, "button_hover_color": LINE, "text_color": FG,
                      "text_color_disabled": FAINT, "corner_radius": 8},
    "DropdownMenu": {"fg_color": RAISED, "hover_color": LINE, "text_color": FG},
    "CTkSlider": {"fg_color": LINE, "progress_color": FAINT, "button_color": ACCENT,
                  "button_hover_color": ACCENT_HOVER},
    "CTkProgressBar": {"fg_color": LINE, "progress_color": ACCENT},
    "CTkScrollbar": {"button_color": LINE, "button_hover_color": FAINT},
    "CTkTextbox": {"fg_color": SURFACE, "text_color": MUTED, "corner_radius": 10, "border_width": 1,
                   "border_color": LINE},
}


# ---------- logique pure (couverte par --selftest) ----------

def fmt_size(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return (f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}").replace(".", ",")
        n /= 1024


def delta(before, after):
    p = round((after - before) / before * 100) if before else 0
    return f"+{p} %" if after > before else f"−{-p} %"


def has_alpha(pix_fmt):
    return any(tok in (pix_fmt or "") for tok in ALPHA)


def video_ext(src_ext, codec):
    """Conteneur de sortie : on garde celui de la source seulement s'il accepte le codec."""
    ok, default = ((".webm", ".mkv", ".mp4"), ".webm") if codec == "libvpx-vp9" else ((".mp4", ".mkv", ".mov"), ".mp4")
    return src_ext if src_ext in ok else default


def out_name(src, kind, s):
    if kind == "audio":
        return src.stem, s["aud_fmt"]
    if kind == "video":
        if s["vid_mode"] == "convert":
            return src.stem, s["vid_fmt"]
        return f"{src.stem}_compressed", video_ext(src.suffix.lower(), s["codec"])
    if s["img_mode"] == "convert":
        return src.stem, s["img_fmt"]
    jpg = s["img_mode"] == "panorama" or src.suffix.lower() in (".heic", ".heif")  # HEIC compressé : sortie JPG
    return f"{src.stem}_compressed", ".jpg" if jpg else src.suffix


def part(out):
    """Fichier temporaire voisin ; garde la vraie extension car ffmpeg en déduit le format."""
    return out.with_name(f"{out.stem}.part{out.suffix}")


def out_path(src, kind, s, taken):
    """Chemin de sortie libre : jamais la source, jamais un fichier existant, jamais deux fois le même."""
    base, ext = out_name(src, kind, s)
    if s["dest"] == DESTS[2] and s["custom"]:
        dest = Path(s["custom"])
    else:
        sub = f"converted_{ext[1:]}" if kind == "audio" else "compressed"  # converted_mp3, converted_flac…
        dest = src.parent / sub if s["dest"] == DESTS[1] else src.parent
    n = 1
    while True:
        out = dest / f"{base}{'' if n == 1 else f'_{n}'}{ext}"
        keys = {os.path.normcase(out), os.path.normcase(part(out))}  # le .part est réservé lui aussi
        if not (out.exists() or part(out).exists() or keys & taken):
            taken |= keys
            return out
        n += 1


def image_args(fmt, s):
    q = str(s["quality"])
    size = ["-resize", s["img_size"]] if s["img_size"] else []
    pre = []
    if s["img_mode"] == "convert":
        # formats à image unique : on garde la 1re d'un GIF animé, d'un TIFF multipage ou d'un HEIC multiple,
        # sinon ImageMagick les écrit toutes bout à bout dans le même fichier.
        # -auto-orient : GIF, BMP… n'ont pas de balise d'orientation, la photo de téléphone sortirait couchée.
        pre = [*(["-delete", "1--1"] if fmt in ("jpg", "png", "bmp", "avif") else []), "-auto-orient"]
        if fmt == "jpg":
            return [*pre, "-background", "white", "-flatten", *size, "-quality", q]
    if s["img_mode"] == "panorama":
        # plafond en px APRÈS l'étirement 2:1 ; pourcentage AVANT, sinon largeur et hauteur s'arrondissent
        # séparément et le 2:1 est faux d'un pixel
        pct = size if size and size[1].endswith("%") else []
        return ["-auto-orient", "-background", "white", "-flatten", *pct, "-resize", "%[fx:2*h]x%[fx:h]!",
                *([] if pct else size), "-quality", q]
    if fmt == "gif" or (size and fmt == "webp"):
        # animation : recomposer les images partielles AVANT de redimensionner, sinon chacune est réduite
        # d'un facteur différent (le plafond « 1920x1920> » se calcule image par image).
        # -fuzz : une fois réduit, le fond fixe d'un GIF n'est plus identique au pixel près d'une image à
        # l'autre ; sans tolérance, Optimize ne l'élimine plus et le GIF réduit sort PLUS lourd que l'original.
        size = ["-coalesce", *size, *(["-fuzz", "2%"] if size and fmt == "gif" else [])]
    return pre + size + {
        "jpg": ["-quality", q],
        "webp": ["-quality", q],
        "avif": ["-quality", q],
        "png": ["-quality", "95"],  # PNG : « quality » = niveau zlib, toujours sans perte
        "gif": ["-layers", "Optimize"],
        "tiff": ["-compress", "Zip"],
    }.get(fmt, [])


def scale_filter(short_side, even=False):
    """Filtre ffmpeg : petit côté ramené à short_side (jamais agrandi), dimensions paires. [] s'il n'y a rien à faire."""
    pre = ""
    if short_side:
        # multiplier AVANT de diviser : 1192*480/596 tombe juste, 1192*(480/596) donnerait 959,99… -> 958
        w, h = (f"min({d},{d}*{short_side}/min(iw,ih))" for d in ("iw", "ih"))
        # réduire une image entrelacée (caméscope, DV, TV) mélange ses deux trames en un fantôme définitif ;
        # yadif n'agit que sur les images signalées entrelacées, il ne touche pas aux vidéos progressives
        pre = "yadif=deint=interlaced,"
    elif even:
        w, h = "iw", "ih"
    else:
        return []
    return ["-vf", f"{pre}scale=w='trunc({w}/2)*2':h='trunc({h}/2)*2'"]


def video_args(out_ext, s, alpha=False):
    if s["vid_mode"] == "convert":
        if out_ext == ".webm":
            pix = ["-pix_fmt", "yuva420p", "-auto-alt-ref", "0"] if alpha else ["-pix_fmt", "yuv420p"]
            return ["-c:v", "libvpx-vp9", *scale_filter(s["vid_size"]), *pix, "-crf", "30", "-b:v", "0",
                    "-c:a", "libopus", "-b:a", "128k"]
        s = {**s, "codec": "libx264", "crf": 23, "preset": "medium"}  # MP4, MKV, MOV : lisibles partout
    video = ["-c:v", s["codec"], "-crf", str(s["crf"])]
    video += ["-b:v", "0"] if s["codec"] == "libvpx-vp9" else ["-preset", s["preset"]]
    x264 = s["codec"] == "libx264"  # « compatible partout » = 8 bits 4:2:0, dimensions paires
    video += scale_filter(s["vid_size"], even=x264) + (["-pix_fmt", "yuv420p"] if x264 else [])
    return video + ["-c:a", "libopus" if out_ext == ".webm" else "aac", "-b:a", "128k"]


def probe(src):
    """(durée en secondes ou None, pix_fmt du premier flux vidéo, arguments de décodage à placer avant -i)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration:stream=codec_type,codec_name,pix_fmt:stream_tags=alpha_mode",
                            "-of", "json", str(src)], capture_output=True, stdin=subprocess.DEVNULL,
                           creationflags=NO_WINDOW)
        info = json.loads(r.stdout or b"{}")
        v = next((st for st in info.get("streams", []) if st.get("codec_type") == "video"), {})
        pix, decoder = v.get("pix_fmt", ""), []
        tags = {k.lower(): val for k, val in v.get("tags", {}).items()}
        if tags.get("alpha_mode") == "1" and v.get("codec_name") in ("vp8", "vp9"):
            # WebM transparent : ffprobe annonce yuv420p, seul le décodeur libvpx restitue l'alpha
            pix, decoder = "yuva420p", ["-c:v", "libvpx-vp9" if v["codec_name"] == "vp9" else "libvpx"]
        return float(info.get("format", {}).get("duration") or 0) or None, pix, decoder
    except (OSError, ValueError):
        return None, "", []


def selftest():
    s = {"img_mode": "convert", "img_fmt": ".jpg", "quality": 75, "vid_mode": "compress", "vid_fmt": ".mp4",
         "codec": "libx264", "crf": 23, "preset": "medium", "aud_fmt": ".mp3", "dest": DESTS[0], "custom": "",
         "img_size": None, "vid_size": None}
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "a.jpg").touch()
        assert out_path(d / "a.jpg", "image", s, set()) == d / "a_2.jpg", "la sortie ne doit jamais être la source"
        taken = set()
        outs = {out_path(d / name, "image", s, taken) for name in ("b.png", "b.webp")}
        assert len(outs) == 2 and not any(o.exists() for o in outs)
        taken = set()  # a.wav -> a.mp3 passe par a.part.mp3, qui est aussi la sortie naturelle de a.part.wav
        outs = [out_path(d / name, "audio", s, taken) for name in ("a.part.wav", "a.wav")]
        assert not {outs[0], part(outs[0])} & {outs[1], part(outs[1])}, outs
        (d / "c_compressed.part.png").touch()
        assert out_path(d / "c.png", "image", {**s, "img_mode": "compress"}, set()).name == "c_compressed_2.png"
        sub = {**s, "dest": DESTS[1]}
        assert out_path(d / "z.png", "image", sub, set()) == d / "compressed" / "z.jpg"
        assert out_path(d / "z.wav", "audio", sub, set()) == d / "converted_mp3" / "z.mp3"
        assert out_path(d / "z.wav", "audio", {**s, "dest": DESTS[2], "custom": str(d / "x")}, set()) == d / "x" / "z.mp3"
        # Convertir : le format choisi donne l'extension ; HEIC se lit mais ne s'écrit pas (Compresser -> JPG)
        assert out_path(d / "z.wav", "audio", {**sub, "aud_fmt": ".flac"}, set()) == d / "converted_flac" / "z.flac"
        assert out_path(d / "p.HEIC", "image", {**s, "img_fmt": ".png"}, set()).name == "p.png"
        assert out_path(d / "p.HEIC", "image", {**s, "img_mode": "compress"}, set()).name == "p_compressed.jpg"
        assert out_path(d / "v.mov", "video", {**s, "vid_mode": "convert"}, set()).name == "v.mp4"
    for ext, codec, want in ((".avi", "libx264", ".mp4"), (".webm", "libx264", ".mp4"), (".mov", "libx265", ".mov"),
                             (".webm", "libvpx-vp9", ".webm"), (".avi", "libvpx-vp9", ".webm")):
        assert video_ext(ext, codec) == want, (ext, codec)
    vp9 = video_args(".webm", {**s, "codec": "libvpx-vp9"})
    assert "libopus" in vp9 and "-b:v" in vp9 and "-preset" not in vp9 and "aac" not in vp9
    x264 = video_args(".mp4", s)
    assert "-preset" in x264 and "aac" in x264
    assert "yuva420p" in video_args(".webm", {**s, "vid_mode": "convert"}, alpha=True)
    conv = video_args(".mkv", {**s, "vid_mode": "convert", "codec": "libx265", "crf": 40, "preset": "slow"})
    assert conv[:6] == ["-c:v", "libx264", "-crf", "23", "-preset", "medium"] and "aac" in conv, conv
    for ext in VID_FORMATS.values():  # chaque format vidéo : son seul, WebM, ou un conteneur qui accepte H.264
        assert ext in AUDIO_ARGS or ext == ".webm" or video_ext(ext, "libx264") == ext, ext
    assert set(AUD_FORMATS.values()) <= set(AUDIO_ARGS)
    everything = {*IMG_FORMATS.values(), *VID_FORMATS.values(), *AUD_FORMATS.values()}
    assert everything <= set(FORMAT_HINTS), everything - set(FORMAT_HINTS)
    for fmt in ("jpg", "png", "bmp", "avif", "webp", "gif", "tiff"):  # une seule image là où le format n'en a qu'une
        a = image_args(fmt, s)
        assert ("-delete" in a) == (fmt in ("jpg", "png", "bmp", "avif")) and "-auto-orient" in a, (fmt, a)
    assert has_alpha("yuva444p10le") and has_alpha("rgba") and not has_alpha("yuv420p")
    png = image_args("png", {**s, "img_mode": "compress"})
    assert "95" in png and "-flatten" not in png
    assert "-flatten" in image_args("jpg", s)
    assert image_args("jpg", {**s, "img_mode": "panorama"})[0] == "-auto-orient"  # photos de téléphone en portrait
    # Résolution : rien par défaut ; GIF/WebP recomposés avant d'être réduits ; panorama plafonné après l'étirement
    assert "-resize" not in png and "-vf" not in vp9 and "-vf" in x264
    small = {**s, "img_mode": "compress", "img_size": IMG_SIZES["1920 px max"]}
    for fmt in ("gif", "webp"):
        a = image_args(fmt, small)
        assert a.index("-coalesce") < a.index("-resize"), a
    assert "-coalesce" not in image_args("webp", {**s, "img_mode": "compress"})
    pano = image_args("jpg", {**small, "img_mode": "panorama"})
    assert pano.index("%[fx:2*h]x%[fx:h]!") < pano.index("1920x1920>")
    pano = image_args("jpg", {**small, "img_mode": "panorama", "img_size": IMG_SIZES["50 %"]})
    assert pano.index("50%") < pano.index("%[fx:2*h]x%[fx:h]!")  # sinon le 2:1 est faux d'un pixel
    assert all(g is None or g[-1] in ">%" for g in IMG_SIZES.values())  # jamais d'agrandissement
    for mode in IMG_MODES.values():
        assert "1920x1920>" in image_args("jpg", {**small, "img_mode": mode}), mode
    for fmt in ("jpg", "webp", "png", "gif", "tiff", "bmp"):
        assert "1920x1920>" in image_args(fmt, small), fmt
    assert "-fuzz" in image_args("gif", small) and "-fuzz" not in image_args("gif", {**s, "img_mode": "compress"})
    for codec in CODECS.values():
        assert "min(iw,iw*720/min(iw,ih))" in " ".join(video_args(".mp4", {**s, "codec": codec, "vid_size": 720})), codec
    assert "yadif" not in " ".join(x264)  # « Originale » : aucun désentrelacement, rien ne change
    vf = video_args(".mp4", {**s, "vid_size": 720})
    assert "720/min(iw,ih)" in vf[vf.index("-vf") + 1] and vf.count("-vf") == 1
    assert "-vf" in video_args(".webm", {**s, "vid_mode": "convert", "vid_size": 720}, alpha=True)
    assert fmt_size(1536) == "1,5 Ko" and delta(100, 39) == "−61 %" and delta(100, 103) == "+3 %" and delta(1000, 1001) == "+0 %"
    print("selftest OK")


# ---------- interface ----------

def apply_theme(root):
    """Applique la palette au thème CTk en mémoire ; à appeler avant de créer les widgets."""
    family = "Segoe UI Variable Text" if "Segoe UI Variable Text" in root.tk.call("font", "families") else "Segoe UI"
    ctk.ThemeManager.theme["CTkFont"].update(family=family, size=13)
    for widget, values in THEME.items():
        ctk.ThemeManager.theme[widget].update(values)
    return family


class App(ctk.CTk, TkinterDnD.DnDWrapper):
    def __init__(self):
        super().__init__(fg_color=BG)
        self.family = apply_theme(self)
        self.title("Media Toolkit")
        self.geometry("880x550")
        self.minsize(720, 520)  # pire cas (images + vidéos + audio dans la liste, journal replié) entièrement visible
        self.rows = {}  # iid (chemin normalisé) -> {"src", "kind", "size", "state": todo | ok | fail}
        self.q = queue.Queue()  # le worker ne touche jamais Tk : il poste ici, pump() dépile
        self.cancel = threading.Event()
        self.proc = None
        self.running = self.closing = False
        self.custom = ""
        self.prev_dest = DESTS[0]
        self.last_dir = None
        self.missing = [t for t in ("ffmpeg", "ffprobe", "magick") if not shutil.which(t)]
        self._build()
        self.log(f"Manquants : {', '.join(self.missing)}" if self.missing else "ffmpeg, ffprobe, magick : OK")
        try:
            TkinterDnD._require(self)
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self.on_drop)
        except (RuntimeError, TclError) as e:
            self.log(f"Glisser-déposer indisponible ({e}) : utilisez « + Ajouter… »")
        for key in "oO":  # Verr. Maj envoie « O »
            self.bind(f"<Control-{key}>", self.browse)
        self.bind("<Return>", self.start)
        self.bind("<Escape>", self.stop)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh()
        self.pump()

    def _build(self):
        bold, caps, small = ctk.CTkFont(weight="bold"), ctk.CTkFont(size=11, weight="bold"), ctk.CTkFont(size=12)
        k = ctk.ScalingTracker.get_window_scaling(self)  # CTk ne met à l'échelle du DPI ni ttk ni grid minsize
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1, minsize=round(132 * k))  # la liste garde toujours ~3 lignes

        def row(r, title="", pady=10, color=MUTED):
            f = ctk.CTkFrame(self, fg_color="transparent")
            f.grid(row=r, column=0, sticky="ew", padx=20, pady=(pady, 0))
            if title:  # intitulé de section : petites capitales, à la teinte du type de média
                ctk.CTkLabel(f, text=title.upper(), width=70, height=28, anchor="w", font=caps,
                             text_color=color).grid(row=0, column=0, sticky="w")
            return f

        def hint(parent, r=1):
            lbl = ctk.CTkLabel(parent, text="", text_color=MUTED, font=small, anchor="w", height=18)
            lbl.grid(row=r, column=1, columnspan=9, sticky="w")
            return lbl

        def mode_line(parent, modes, sizes):
            """1re ligne d'un bloc d'options : sélecteur de mode, puis menu Résolution."""
            line = ctk.CTkFrame(parent, fg_color="transparent")
            line.grid(row=0, column=1, sticky="w")
            seg = ctk.CTkSegmentedButton(line, values=list(modes), command=self.refresh)
            seg.set("Compresser")
            seg.pack(side="left", padx=(0, 20))
            ctk.CTkLabel(line, text="Résolution", text_color=MUTED).pack(side="left", padx=(0, 8))
            menu = ctk.CTkOptionMenu(line, values=list(sizes), width=140)
            menu.pack(side="left")
            return seg, menu

        def format_box(parent, formats):
            """Cadre « Format [menu] » : format de sortie de Convertir. Renvoie (cadre, menu)."""
            box = ctk.CTkFrame(parent, fg_color="transparent")
            ctk.CTkLabel(box, text="Format", text_color=MUTED).pack(side="left", padx=(0, 8))
            menu = ctk.CTkOptionMenu(box, values=list(formats), width=120, command=self.refresh)
            menu.pack(side="left")
            return box, menu

        # 0 : barre d'outils
        bar = row(0, pady=12)
        self.b_add = ctk.CTkButton(bar, text="+ Ajouter…", width=112, fg_color=RAISED, hover_color=LINE,
                                   command=self.browse)
        self.b_del = ctk.CTkButton(bar, text="Retirer la sélection", width=150, command=self.remove_selected)
        self.b_clear = ctk.CTkButton(bar, text="Tout vider", width=96, command=lambda: self.remove(list(self.rows)))
        for b in (self.b_add, self.b_del, self.b_clear):
            b.pack(side="left", padx=(0, 6))
        self.counter = ctk.CTkLabel(bar, text="", text_color=MUTED)
        self.counter.pack(side="right")

        # 1 : bandeau outil manquant
        msgs = ["magick introuvable dans le PATH : images désactivées"] if "magick" in self.missing else []
        ff = [t for t in ("ffmpeg", "ffprobe") if t in self.missing]
        if ff:
            msgs.append(f"{' / '.join(ff)} introuvable dans le PATH : vidéos et audio désactivés")
        if msgs:
            ctk.CTkLabel(self, text=" — ".join(msgs), text_color=FAIL, anchor="w").grid(
                row=1, column=0, sticky="ew", padx=20, pady=(6, 0))

        # 2 : la liste unique (ttk.Treeview : CTk n'a pas de liste multi-colonnes)
        box = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=10, border_width=1, border_color=LINE)
        box.grid(row=2, column=0, sticky="nsew", padx=20, pady=(10, 0))
        box.grid_columnconfigure(0, weight=1)
        box.grid_rowconfigure(0, weight=1)
        st = ttk.Style(self)
        st.theme_use("default")  # le thème « vista » ignore background
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # sans cadre : le focus se lit sur la boîte
        st.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=FG, borderwidth=0,
                     rowheight=round(28 * k), font=(self.family, -round(13 * k)))
        st.configure("Treeview.Heading", background=SURFACE, foreground=MUTED, relief="flat",
                     padding=(round(2 * k), round(4 * k)), font=(self.family, -round(12 * k)))
        st.map("Treeview", background=[("selected", SELECT)])
        st.map("Treeview.Heading", background=[("active", SURFACE)])
        cols = (("file", "Fichier", 200, "w", True), ("kind", "Type", 70, "w", False),
                ("size", "Taille", 80, "w", False), ("result", "Résultat", 260, "w", True),
                ("x", "", 30, "center", False))
        self.tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings", selectmode="extended")
        for cid, text, width, anchor, stretch in cols:
            self.tree.heading(cid, text=text, anchor=anchor)
            self.tree.column(cid, width=round(width * k), minwidth=round(width * k), anchor=anchor, stretch=stretch)
        for tag, (fg, bg) in ROW_COLORS.items():
            self.tree.tag_configure(tag, foreground=fg, background=bg)
        sb = ctk.CTkScrollbar(box, command=self.tree.yview)

        def on_scroll(*_):  # yview() relu à chaque étape : CTk redessine et peut rappeler on_scroll en cours de route
            sb.set(*self.tree.yview())
            sb.configure(button_color=SURFACE if self.tree.yview() == (0, 1) else LINE)  # rien à défiler : invisible
        self.tree.configure(yscrollcommand=on_scroll)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(4, 6))
        sb.grid(row=0, column=1, sticky="ns", padx=(0, 3), pady=6)
        self.tree.bind("<FocusIn>", lambda e: box.configure(border_color=ACCENT))  # focus clavier visible
        self.tree.bind("<FocusOut>", lambda e: box.configure(border_color=LINE))
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Delete>", self.remove_selected)
        for key in "aA":
            self.tree.bind(f"<Control-{key}>", lambda e: self.tree.selection_set(self.tree.get_children()))
        self.empty = ctk.CTkFrame(box, fg_color=SURFACE, cursor="hand2")  # recouvre la liste vide, en-têtes compris
        inner = ctk.CTkFrame(self.empty, fg_color="transparent")
        inner.place(relx=.5, rely=.5, anchor="center")
        fams = self.tk.call("font", "families")
        icon_font = next((f for f in ("Segoe Fluent Icons", "Segoe MDL2 Assets") if f in fams), None)
        if icon_font:  # sans police d'icônes (hors Windows 10/11) : l'accueil reste lisible, en texte seul
            icons = ctk.CTkFrame(inner, fg_color="transparent")
            icons.pack(pady=(0, 10))
            for kind, glyph in KIND_ICONS.items():
                ctk.CTkLabel(icons, text=glyph, font=(icon_font, 34), text_color=KIND_COLORS[kind]).pack(
                    side="left", padx=14)
        ctk.CTkLabel(inner, text="Glissez ici des images, des vidéos ou des fichiers audio (ou un dossier)",
                     font=ctk.CTkFont(size=16, weight="bold")).pack()
        ctk.CTkLabel(inner, text="ou cliquez pour parcourir", text_color=ACCENT).pack(pady=(2, 14))
        table = ctk.CTkFrame(inner, fg_color="transparent")
        table.pack()
        for r, (kind, what) in enumerate((("image", "compresser, panorama 2:1, convertir en JPG, PNG, WebP…"),
                                          ("video", "compresser, convertir en MP4, WebM, MP3…"),
                                          ("audio", "convertir en MP3, FLAC, WAV…"))):
            ctk.CTkLabel(table, text=f"{NAMES[kind][1]} :", font=bold, text_color=KIND_COLORS[kind], height=22).grid(
                row=r, column=0, sticky="e", padx=(0, 8))
            ctk.CTkLabel(table, text=what, text_color=MUTED, height=22).grid(row=r, column=1, sticky="w")

        def clickable(w):  # tout l'accueil ouvre le sélecteur, sans zone morte entre les textes
            w.bind("<Button-1>", self.browse)
            w.configure(cursor="hand2")
            for child in w.winfo_children():
                clickable(child)
        clickable(self.empty)

        # 3-5 : options, visibles seulement si la liste contient ce type
        self.opt = {}
        f = self.opt["image"] = row(3, NAMES["image"][1], color=KIND_COLORS["image"])
        f.grid_columnconfigure(1, weight=1)
        self.img_mode, self.img_size = mode_line(f, IMG_MODES, IMG_SIZES)
        q_line = ctk.CTkFrame(f, fg_color="transparent")
        q_line.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        q_line.grid_columnconfigure(2, weight=1)
        self.img_conv, self.img_fmt = format_box(q_line, IMG_FORMATS)  # Convertir seulement ; le curseur s'étire
        self.img_conv.grid(row=0, column=0, padx=(0, 20))
        ctk.CTkLabel(q_line, text="Qualité", text_color=MUTED).grid(row=0, column=1, padx=(0, 8))
        self.q_val = ctk.CTkLabel(q_line, text="75", width=30, font=bold)
        self.quality = ctk.CTkSlider(q_line, from_=1, to=100, number_of_steps=99, width=80,
                                     command=lambda v: self.q_val.configure(text=str(int(v))))
        self.quality.set(75)
        self.quality.grid(row=0, column=2, sticky="ew")
        self.q_val.grid(row=0, column=3)
        self.img_hint = hint(f, r=2)

        f = self.opt["video"] = row(4, NAMES["video"][1], color=KIND_COLORS["video"])
        f.grid_columnconfigure(1, weight=1)
        self.vid_mode, self.vid_size = mode_line(f, VID_MODES, VID_SIZES)
        self.vid_line = ctk.CTkFrame(f, fg_color="transparent")
        self.vid_line.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        self.vid_line.grid_columnconfigure(2, weight=1)
        self.codec = ctk.CTkOptionMenu(self.vid_line, values=list(CODECS), width=200, command=self.refresh)
        self.codec.grid(row=0, column=0, padx=(0, 20))
        ctk.CTkLabel(self.vid_line, text="CRF (bas = mieux)", text_color=MUTED).grid(row=0, column=1, padx=(0, 8))
        self.crf_val = ctk.CTkLabel(self.vid_line, text="23", width=30, font=bold)
        self.crf = ctk.CTkSlider(self.vid_line, from_=0, to=51, number_of_steps=51, width=80,
                                 command=lambda v: self.crf_val.configure(text=str(int(v))))
        self.crf.set(23)
        self.crf.grid(row=0, column=2, sticky="ew")
        self.crf_val.grid(row=0, column=3)
        ctk.CTkLabel(self.vid_line, text="Vitesse", text_color=MUTED).grid(row=0, column=4, padx=(16, 8))
        self.preset = ctk.CTkOptionMenu(self.vid_line, values=PRESETS, width=100)
        self.preset.set("medium")
        self.preset.grid(row=0, column=5)
        self.vid_conv, self.vid_fmt = format_box(f, VID_FORMATS)  # remplace la ligne ci-dessus en mode Convertir
        self.vid_conv.grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.vid_hint = ctk.CTkLabel(self.vid_conv, text="", text_color=MUTED, font=small)
        self.vid_hint.pack(side="left", padx=(16, 0))

        f = self.opt["audio"] = row(5, NAMES["audio"][1], color=KIND_COLORS["audio"])
        box, self.aud_fmt = format_box(f, AUD_FORMATS)
        box.grid(row=0, column=1, sticky="w")
        self.aud_hint = ctk.CTkLabel(box, text="", text_color=MUTED, font=small)
        self.aud_hint.pack(side="left", padx=(16, 0))

        # 6 : sortie
        f = row(6, "Sortie")
        f.grid_columnconfigure(3, weight=1)  # l'aide, plus large que les boutons, ne les décale pas
        self.dest = ctk.CTkSegmentedButton(f, values=DESTS, command=self.on_dest)
        self.dest.set(DESTS[0])
        self.dest.grid(row=0, column=1, padx=(0, 8))
        self.b_browse = ctk.CTkButton(f, text="Parcourir…", width=100, command=self.pick_folder)
        self.b_browse.grid(row=0, column=2)
        self.dest_hint = hint(f)

        # 7 : action. La barre de progression, fine, sépare les options du pied de fenêtre ;
        # Convertir est le seul bouton plein de tout l'écran.
        f = row(7, pady=10)
        f.grid_columnconfigure(1, weight=1)
        self.bar = ctk.CTkProgressBar(f, height=4, corner_radius=0)
        self.bar.set(0)
        self.bar.grid(row=0, column=0, columnspan=5, sticky="ew")
        self.status = ctk.CTkLabel(f, text="Prêt", anchor="w", height=18)
        self.status.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(6, 4))
        link = dict(border_width=0, corner_radius=6, text_color=MUTED, anchor="w", cursor="hand2")
        self.b_journal = ctk.CTkButton(f, text="Journal ▸", width=80, **link,  # liens texte, alignés sur la marge
                                       command=lambda: self.show_journal(not self.journal.winfo_ismapped()))
        self.b_erase = ctk.CTkButton(f, text="Effacer", width=70, **link, command=self.clear_log)
        self.b_open = ctk.CTkButton(f, text="Ouvrir le dossier", width=132, height=30,
                                    command=lambda: os.startfile(self.last_dir))
        self.b_stop = ctk.CTkButton(f, text="Annuler", width=92, height=30, command=self.stop)
        self.b_go = ctk.CTkButton(f, text="Convertir", width=132, height=30, font=bold, border_width=0,
                                  fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color=ON_ACCENT, command=self.start)
        for col, b in enumerate((self.b_journal, self.b_erase, self.b_open, self.b_stop, self.b_go)):
            b.grid(row=2, column=col, sticky="w", padx=(8 if col > 1 else 0, 0))
        self.b_erase.grid_remove()

        # 9 : journal, replié par défaut, s'ouvre au premier échec
        mono = "Cascadia Mono" if "Cascadia Mono" in fams else "Consolas"
        self.journal = ctk.CTkTextbox(self, height=90, font=(mono, 12), state="disabled")
        ctk.CTkFrame(self, height=10, fg_color="transparent").grid(row=10, column=0)

        self.controls = (self.b_add, self.img_mode, self.img_size, self.img_fmt, self.vid_mode, self.vid_size,
                         self.vid_fmt, self.codec, self.aud_fmt, self.dest, self.b_browse)  # + curseurs : refresh()

    # ---------- journal ----------

    def log(self, msg):
        self.journal.configure(state="normal")
        self.journal.insert("end", f"[{datetime.now():%H:%M:%S}] {msg}\n")
        self.journal.see("end")
        self.journal.configure(state="disabled")

    def clear_log(self):
        self.journal.configure(state="normal")
        self.journal.delete("1.0", "end")
        self.journal.configure(state="disabled")

    def show_journal(self, show):
        self.minsize(720, 620 if show else 520)  # Tk agrandit la fenêtre au besoin : journal jamais hors champ
        if show:
            self.journal.grid(row=9, column=0, sticky="ew", padx=20, pady=(8, 0))
            self.b_erase.grid()
        else:
            self.journal.grid_remove()
            self.b_erase.grid_remove()
        self.b_journal.configure(text="Journal ▾" if show else "Journal ▸")

    def report_callback_exception(self, *exc):  # sous pythonw une exception serait invisible
        self.log("".join(traceback.format_exception(*exc)).strip())
        self.show_journal(True)

    # ---------- liste ----------

    def browse(self, *_):
        if self.running:
            return
        pat = lambda exts: " ".join(f"*{e}" for e in sorted(exts))
        types = [("Tous les médias", pat(EXT2KIND))] + [(NAMES[k][1], pat(exts)) for k, exts in KINDS.items()]
        self.add_paths(filedialog.askopenfilenames(title="Ajouter des fichiers", filetypes=types))

    def on_drop(self, event):
        if self.running:
            self.status.configure(text="Conversion en cours : ajout ignoré")
        else:
            self.add_paths(self.tk.splitlist(event.data))
        return event.action

    def add_paths(self, paths):
        files = []
        for p in map(Path, paths):
            files += sorted(p.iterdir()) if p.is_dir() else [p]
        added, ignored = 0, []
        for p in files:
            kind = EXT2KIND.get(p.suffix.lower())
            if not (kind and p.is_file()):
                ignored.append(p.name)
                continue
            iid = os.path.normcase(os.path.realpath(p)).replace("\\", "/")
            if iid in self.rows:
                if self.rows[iid]["state"] != "todo":  # déjà traité : on le remet dans la file
                    self.rows[iid]["state"] = "todo"
                    self.log(f"Remis en attente : {p.name}")
                continue
            size = p.stat().st_size
            self.rows[iid] = {"src": p, "kind": kind, "size": size, "state": "todo"}
            self.tree.insert("", "end", iid=iid, values=(p.name, NAMES[kind][0], fmt_size(size), "", "✕"))
            added += 1
        if added or ignored:
            names = ", ".join(ignored[:5]) + ("…" if len(ignored) > 5 else "")
            msg = f"{added} ajouté(s)" + (f", {len(ignored)} ignoré(s), format non pris en charge : {names}" if ignored else "")
            self.log(msg)
            if ignored:
                self.status.configure(text=msg)
        self.tree.focus_set()
        self.refresh()

    def remove(self, iids):
        if self.running:
            return
        for iid in iids:
            del self.rows[iid]
            self.tree.delete(iid)
        self.refresh()

    def remove_selected(self, *_):
        if not self.tree.selection() and not self.running:
            self.status.configure(text="Sélectionnez d'abord des fichiers dans la liste (ou cliquez sur leur ✕)")
        self.remove(self.tree.selection())

    def on_click(self, e):
        if self.tree.identify_region(e.x, e.y) == "cell" and self.tree.identify_column(e.x) == "#5":
            self.remove([self.tree.identify_row(e.y)])
            return "break"

    # ---------- réglages ----------

    def settings(self):
        return {"img_mode": IMG_MODES[self.img_mode.get()], "img_fmt": IMG_FORMATS[self.img_fmt.get()],
                "quality": int(self.quality.get()), "vid_mode": VID_MODES[self.vid_mode.get()],
                "vid_fmt": VID_FORMATS[self.vid_fmt.get()], "codec": CODECS[self.codec.get()],
                "crf": int(self.crf.get()), "preset": self.preset.get(), "aud_fmt": AUD_FORMATS[self.aud_fmt.get()],
                "img_size": IMG_SIZES[self.img_size.get()], "vid_size": VID_SIZES[self.vid_size.get()],
                "dest": self.dest.get(), "custom": self.custom}

    def plan(self):
        """Réglages figés + (iid, source, type, sortie) de tout ce qui n'est pas OK. Sert à l'aperçu ET au lancement."""
        s, taken = self.settings(), set()
        return s, [(iid, r["src"], r["kind"], out_path(r["src"], r["kind"], s, taken))
                   for iid, r in self.rows.items() if r["state"] != "ok"]

    def on_dest(self, value):
        if value == DESTS[2] and not self.custom:
            return self.pick_folder()
        self.prev_dest = value
        self.refresh()

    def pick_folder(self):
        folder = filedialog.askdirectory(title="Choisir le dossier de sortie")
        if folder:
            self.custom = folder
            self.prev_dest = DESTS[2]
        self.dest.set(self.prev_dest)
        self.refresh()

    def refresh(self, *_):
        """Recalcule tout ce qui dépend de la liste et des réglages : visibilité, aides, aperçus, boutons."""
        kinds = [r["kind"] for r in self.rows.values()]
        for kind, frame in self.opt.items():
            frame.grid() if kind in kinds else frame.grid_remove()
        self.empty.place_forget() if kinds else self.empty.place(in_=self.tree, relwidth=1, relheight=1)
        convert, img_ext = self.img_mode.get() == "Convertir", IMG_FORMATS[self.img_fmt.get()]
        self.img_conv.grid() if convert else self.img_conv.grid_remove()
        self.img_hint.configure(text=FORMAT_HINTS[img_ext] if convert else {
            "Compresser": "Le curseur agit sur JPG, WebP, AVIF. PNG, GIF, TIFF, BMP : sans perte, "
                          "transparence conservée. HEIC : sortie JPG.",
            "Panorama 2:1": "Image étirée (déformée) à largeur = 2 × hauteur. Sortie JPG, fond blanc.",
        }[self.img_mode.get()])
        compress = self.vid_mode.get() == "Compresser"
        self.vid_line.grid() if compress else self.vid_line.grid_remove()
        self.vid_conv.grid_remove() if compress else self.vid_conv.grid()
        self.vid_hint.configure(text=FORMAT_HINTS[VID_FORMATS[self.vid_fmt.get()]])
        self.aud_hint.configure(text=FORMAT_HINTS[AUD_FORMATS[self.aud_fmt.get()]])
        self.dest_hint.configure(text={
            DESTS[0]: "Les fichiers sont créés à côté de chaque original",
            DESTS[1]: "Sous-dossier « compressed » (images, vidéos) ou « converted_mp3 », « converted_flac »… (audio)",
        }.get(self.dest.get(), self.custom))

        parts = [f"{c} {NAMES[k][c > 1].lower()}" for k in KINDS if (c := kinds.count(k))]
        n = len(kinds)
        self.counter.configure(text=f"{n} fichier{'s' if n > 1 else ''}"
                               + (f" ({', '.join(parts)})" if len(parts) > 1 else ""))
        if not self.running:
            for iid, _, _, out in self.plan()[1]:
                if self.rows[iid]["state"] == "todo":
                    self.tree.set(iid, "result", f"→ {out.name}")
                    self.tree.item(iid, tags=())

        state = lambda on: "normal" if on else "disabled"
        idle = not self.running
        for w in self.controls:
            w.configure(state=state(idle))
        lossy = not convert or img_ext in (".jpg", ".webp", ".avif")  # PNG, GIF… : le curseur n'agirait pas
        for slider, on in ((self.quality, idle and lossy), (self.crf, idle)):
            slider.configure(state=state(on), button_color=ACCENT if on else FAINT)
        self.preset.configure(state=state(idle and CODECS[self.codec.get()] != "libvpx-vp9"))
        self.b_del.configure(state=state(idle and kinds))
        self.b_clear.configure(state=state(idle and kinds))
        go = idle and any(r["state"] != "ok" for r in self.rows.values())
        self.b_go.configure(state=state(go), fg_color=ACCENT if go else RAISED)  # désactivé = visiblement gris
        self.b_stop.configure(state=state(self.running))
        self.b_open.configure(state=state(self.last_dir))

    # ---------- traitement ----------

    def start(self, *_):
        if self.running:
            return
        s, jobs = self.plan()
        if not jobs:
            return
        self.running = True  # posé ici, de façon synchrone : double lancement impossible
        self.cancel.clear()
        self.bar.configure(progress_color=ACCENT)
        self.bar.set(0)
        self.refresh()
        threading.Thread(target=self.work, args=(s, jobs), daemon=True).start()

    def stop(self, *_):
        if self.running:
            self.cancel.set()
            if self.proc:
                self.proc.terminate()
            self.status.configure(text="Annulation…")

    def on_close(self):
        if self.running and not messagebox.askyesno("Conversion en cours",
                                                    "Une conversion est en cours. L'annuler et quitter ?"):
            return
        if not self.running:  # au repos, ou lot terminé pendant que la boîte était ouverte
            return self.destroy()
        self.closing = True  # destroy() se fera quand le worker aura rendu la main (pas de ffmpeg orphelin)
        self.stop()

    def pump(self):
        """Thread Tk : applique les messages du worker."""
        self.after(100, self.pump)  # réarmé d'abord : une exception plus bas ne doit pas figer l'interface
        try:
            while True:
                what, *a = self.q.get_nowait()
                if what == "row":
                    iid, text, state = a
                    self.tree.set(iid, "result", text)
                    self.tree.item(iid, tags=(state or "run",))  # couleur de ligne : en cours / ok / fail
                    if state:
                        self.rows[iid]["state"] = state
                    if state == "fail":
                        self.show_journal(True)
                elif what == "log":
                    self.log(a[0])
                elif what == "status":
                    self.status.configure(text=a[0])
                elif what == "progress":
                    self.bar.set(a[0])
                elif what == "done":
                    self.finish(*a)
                    if self.closing:
                        return
        except queue.Empty:
            pass

    def finish(self, ok, fail, total, before, after):
        self.running = False
        self.proc = None
        if self.closing:
            return self.destroy()
        if self.cancel.is_set() and ok + fail < total:
            text = f"Annulé — {ok + fail}/{total} traités"
            self.bar.set(0)
        else:
            text = f"Terminé : {ok} OK, {fail} échec{'s' if fail > 1 else ''}"
            if ok:
                text += f" — {fmt_size(before)} → {fmt_size(after)} ({delta(before, after)})"
            if not fail:
                text += ". Autres réglages ? Redéposez les fichiers."
        failed = [iid for iid, r in self.rows.items() if r["state"] == "fail"]
        if failed:
            self.bar.configure(progress_color=FAIL)
            self.after(100, lambda: self.tree.exists(failed[0]) and self.tree.see(failed[0]))  # après le réagencement
        self.status.configure(text=text)
        self.log(text)
        self.refresh()

    def work(self, s, jobs):
        """Thread worker : aucun appel Tk ici, tout passe par self.q."""
        put, total = self.q.put, len(jobs)
        ok = fail = before = after = 0
        try:
            for i, (iid, src, kind, out) in enumerate(jobs):
                if self.cancel.is_set():
                    break
                put(("status", f"{i + 1}/{total} – {src.name}"))
                put(("row", iid, "En cours…", None))

                def progress(frac, i=i, iid=iid):
                    put(("progress", (i + frac) / total))
                    put(("row", iid, f"{round(frac * 100)} %", None))
                try:
                    size_in, size_out = self.convert(src, kind, out, s, progress)
                except Exception as e:  # un fichier en échec ne doit jamais arrêter le lot
                    if self.cancel.is_set():
                        break  # la ligne reste « todo » : Convertir reprendra là
                    lines = [ln for ln in str(e).splitlines() if ln.strip()] or [repr(e)]
                    fail += 1
                    put(("row", iid, f"Échec : {lines[0]}", "fail"))
                    put(("log", f"[{i + 1}/{total}] {src.name} — Échec : " + "\n    ".join(lines[:6])))
                else:
                    ok += 1
                    before, after = before + size_in, after + size_out
                    self.last_dir = out.parent
                    bigger = " (plus gros)" if size_out > size_in else ""
                    put(("row", iid, f"OK  {delta(size_in, size_out)}{bigger}  → {out.name}", "ok"))
                    put(("log", f"[{i + 1}/{total}] {src.name} → {out}  ({fmt_size(size_in)} → {fmt_size(size_out)})"))
                put(("progress", (i + 1) / total))
        finally:  # quoi qu'il arrive, l'interface sort de l'état « en cours »
            put(("done", ok, fail, total, before, after))

    def convert(self, src, kind, out, s, progress):
        """Écrit dans un voisin .part puis renomme : ni écrasement, ni fichier partiel laissé derrière."""
        gone = [t for t in NEED[kind] if t in self.missing]
        if gone:
            raise RuntimeError(f"{' / '.join(gone)} introuvable dans le PATH")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = part(out)
        if tmp.exists() or out.exists():  # apparu depuis la planification ; AVANT le try, dont le finally supprime tmp
            raise FileExistsError(f"{tmp.name if tmp.exists() else out.name} existe déjà")
        try:
            if kind == "image":
                # magick lit stdin et écrit stdout : il ne voit jamais un nom de fichier ([, %, : sans danger)
                fmt = MAGICK_FMT.get(out.suffix.lower(), out.suffix.lower()[1:])
                with open(src, "rb") as fin, open(tmp, "wb") as fout:
                    self.proc = subprocess.Popen(["magick", "-", *image_args(fmt, s), f"{fmt}:-"], stdin=fin,
                                                 stdout=fout, stderr=subprocess.PIPE, creationflags=NO_WINDOW)
                    if self.cancel.is_set():  # Annuler a pu arriver entre deux fichiers
                        self.proc.terminate()
                    err = self.proc.communicate()[1].decode("utf-8", "replace")
            else:
                ext = out.suffix.lower()
                duration, pix, decoder = probe(src)
                alpha = has_alpha(pix)
                if kind == "video":
                    if s["vid_mode"] == "convert" and ext == ".webm" and alpha:
                        self.q.put(("log", f"{src.name} : transparence détectée ({pix})"))
                    elif s["vid_mode"] == "compress" and ext != src.suffix.lower():
                        self.q.put(("log", f"{src.name} : conteneur {src.suffix} incompatible avec {s['codec']} "
                                           f"→ sortie {out.suffix}"))
                # audio, ou vidéo convertie en MP3 : -vn ne garde que le son
                args = ["-vn", "-codec:a", *AUDIO_ARGS[ext]] if ext in AUDIO_ARGS else video_args(ext, s, alpha)
                # stderr dans un fichier temporaire : deux PIPE lus l'un après l'autre = interblocage
                with tempfile.TemporaryFile() as errf:
                    self.proc = subprocess.Popen(
                        ["ffmpeg", "-hide_banner", "-v", "error", "-nostdin", "-nostats", "-n",
                         "-progress", "pipe:1", *decoder, "-i", str(src), *args, str(tmp)],
                        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errf, text=True,
                        encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                    if self.cancel.is_set():
                        self.proc.terminate()
                    for line in self.proc.stdout:
                        key, _, val = line.strip().partition("=")
                        if key == "out_time_us" and val.isdigit() and duration:
                            progress(min(1.0, int(val) / 1e6 / duration))
                    self.proc.wait()
                    errf.seek(0)
                    err = errf.read().decode("utf-8", "replace")
            if self.proc.returncode:
                raise RuntimeError(err.strip() or f"code de sortie {self.proc.returncode}")
            if err.strip():  # code 0 mais source abîmée (JPEG tronqué…) : le dire au moins dans le journal
                self.q.put(("log", f"{src.name} : avertissement — {err.strip().splitlines()[0]}"))
            tmp.rename(out)  # sous Windows rename() échoue si la cible existe : jamais d'écrasement
            return src.stat().st_size, out.stat().st_size
        finally:
            tmp.unlink(missing_ok=True)


def main():
    if "--selftest" in sys.argv:
        return selftest()
    try:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        app = App()
        app.add_paths([a for a in sys.argv[1:] if not a.startswith("--")])
        app.mainloop()
    except Exception:
        messagebox.showerror("Media Toolkit", traceback.format_exc())


if __name__ == "__main__":
    main()
