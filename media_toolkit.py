#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Media Toolkit — interface unifiée pour conversion média.

Onglets :
    - Images : compression, conversion JPG, panorama 2:1 (ImageMagick + ffmpeg)
    - Vidéos : compression H.264/H.265/VP9, MP4 → WebM (ffmpeg)
    - Audio  : conversion vers MP3 192k (ffmpeg)

Dépendances runtime :
    - customtkinter (requis)
    - tkinterdnd2   (optionnel, active le glisser-déposer)
    - ffmpeg/ffprobe et magick (ImageMagick) dans le PATH système

Entrée : `python media_toolkit.py`
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import subprocess
import threading
import json
from pathlib import Path
from datetime import datetime

# tkinterdnd2 - gestionnaire de DnD stable
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    TKDND_AVAILABLE = True
except ImportError:
    TKDND_AVAILABLE = False
    print("tkinterdnd2 non disponible - installation: pip install tkinterdnd2")

# Configuration CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Classe principale qui hérite de TkinterDnD si disponible
if TKDND_AVAILABLE:
    class BaseApp(TkinterDnD.Tk):
        pass
else:
    class BaseApp:
        pass

class MediaToolkitApp:
    """Application principale.

    Gère la fenêtre racine (TkinterDnD.Tk si dispo, sinon ctk.CTk), les
    trois onglets (images / vidéos / audio), le journal et la logique
    responsive : au-dessus de `NARROW_WIDTH_THRESHOLD` pixels, les cards
    d'options sont côte à côte ; en dessous, elles s'empilent.
    """

    # Seuil en pixels sous lequel les 2 colonnes d'options sont empilées
    NARROW_WIDTH_THRESHOLD = 850

    def __init__(self):
        if TKDND_AVAILABLE:
            self.root = BaseApp()
            # Appliquer la couleur de fond du thème CTk à la root TkinterDnD
            # (sinon un liseré gris tk apparaît autour des widgets CTk)
            try:
                bg = ctk.ThemeManager.theme["CTk"]["fg_color"]
                self.root.configure(bg=bg[1] if isinstance(bg, (list, tuple)) else bg)
            except Exception:
                self.root.configure(bg="#242424")
        else:
            self.root = ctk.CTk()

        self.root.title("Media Toolkit")
        # Géométrie adaptée aux laptops courants (1366x768 et plus)
        self.root.geometry("1050x780")
        self.root.minsize(780, 560)

        # Variables
        self.image_mode = ctk.StringVar(value="compress")
        self.video_mode = ctk.StringVar(value="compress")
        self.audio_output = ctk.StringVar(value="converted_mp3")

        # Stockage fichiers
        self.image_files = []
        self.video_files = []
        self.audio_files = []

        # État de traitement (évite les lancements concurrents)
        self.processing = False
        # Liste des "option frames" responsive à reflow au resize
        self._responsive_option_frames = []
        self._current_narrow_mode = None

        self.setup_ui()
        self.check_dependencies()

        # Bind resize pour reflow responsive
        self.root.bind("<Configure>", self._on_root_configure)
        
    def setup_ui(self):
        """Construit la structure principale : header, tabview, journal."""
        # Grid : header (0) | main (1, flex) | log (2, fixe)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(1, weight=1)

        # ========== HEADER ==========
        # Pas de grid_propagate(False) : on laisse le header se dimensionner
        # selon le contenu (utile si le DPI système change la police).
        header = ctk.CTkFrame(self.root, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=12)

        ctk.CTkLabel(title_frame, text="🛠️", font=("Segoe UI", 26)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(title_frame, text="Media Toolkit", font=("Segoe UI", 22, "bold")).pack(side="left")

        dnd_status = " (DnD actif)" if TKDND_AVAILABLE else ""
        ctk.CTkLabel(title_frame, text=f"v3.0{dnd_status}", font=("Segoe UI", 11),
                     text_color="gray").pack(side="left", padx=(10, 0), pady=(6, 0))

        # ========== MAIN CONTENT ==========
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(0, weight=1)

        # Tabview
        self.tabview = ctk.CTkTabview(main_frame, corner_radius=15)
        self.tabview.grid(row=0, column=0, sticky="nsew")

        self.tabview.add("  🖼️ Images  ")
        self.tabview.add("  🎬 Vidéos  ")
        self.tabview.add("  🎵 Audio  ")

        # Setup tabs
        self.setup_images_tab()
        self.setup_videos_tab()
        self.setup_audio_tab()

        # ========== LOG SECTION ==========
        log_frame = ctk.CTkFrame(self.root, corner_radius=0)
        log_frame.grid(row=2, column=0, sticky="ew")

        log_header = ctk.CTkFrame(log_frame, fg_color="transparent")
        log_header.pack(fill="x", padx=15, pady=(8, 4))

        ctk.CTkLabel(log_header, text="📝 Journal", font=("Segoe UI", 12, "bold")).pack(side="left")

        ctk.CTkButton(log_header, text="Effacer", width=80, height=25,
                     command=self.clear_log).pack(side="right")

        # Hauteur log réduite pour laisser de la place au reste ;
        # l'utilisateur peut toujours scroller dans le textbox.
        self.log_text = ctk.CTkTextbox(log_frame, height=90, font=("Consolas", 10),
                                      corner_radius=10)
        self.log_text.pack(fill="x", padx=15, pady=(0, 10))
        
    def setup_images_tab(self):
        """Onglet Images : compression, conversion JPG, panorama 2:1."""
        tab = self.tabview.tab("  🖼️ Images  ")
        # On utilise un CTkScrollableFrame pour que le contenu reste accessible
        # quand la fenêtre est petite. Le DnD s'enregistre sur les widgets
        # enfants, donc le scroll n'empêche pas le glisser-déposer.
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Frame fichiers
        files_frame = ctk.CTkFrame(scroll, corner_radius=15)
        files_frame.pack(fill="x", padx=10, pady=10)

        # Header avec compteur
        header = ctk.CTkFrame(files_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 0))

        dnd_text = " (Drag && Drop supporté)" if TKDND_AVAILABLE else ""
        ctk.CTkLabel(header, text=f"📁 Fichiers à traiter{dnd_text}",
                     font=("Segoe UI", 14, "bold")).pack(side="left")
        self.img_count = ctk.CTkLabel(header, text="0 fichier",
                                      font=("Segoe UI", 11), text_color="gray")
        self.img_count.pack(side="right")

        # Zone de drop (hauteur réduite, pas de pack_propagate figé)
        if TKDND_AVAILABLE:
            self.img_drop_frame = ctk.CTkFrame(files_frame, fg_color=("gray85", "gray17"),
                                              border_width=2, border_color=("gray70", "gray30"),
                                              corner_radius=10, height=80)
            self.img_drop_frame.pack(fill="x", padx=15, pady=10)
            self.img_drop_frame.pack_propagate(False)

            self.img_drop_label = ctk.CTkLabel(self.img_drop_frame,
                                              text="📂 Glissez-déposez vos fichiers images ici\nou cliquez sur « + Ajouter »",
                                              font=("Segoe UI", 12), justify="center")
            self.img_drop_label.pack(expand=True)

            # Activer DnD
            self._setup_dnd(self.img_drop_frame, self.on_image_drop)

        # Liste des fichiers
        self.img_listbox = ctk.CTkTextbox(files_frame, height=110, font=("Segoe UI", 11),
                                         state="disabled", corner_radius=10)
        self.img_listbox.pack(fill="x", padx=15, pady=(0, 10))

        # Boutons
        btn_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(btn_frame, text="+ Ajouter", command=self.add_images,
                     width=100, height=35, corner_radius=8).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="− Retirer", command=self.remove_image,
                     width=100, height=35, fg_color="#f59e0b", hover_color="#d97706",
                     corner_radius=8).pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="× Vider", command=self.clear_images,
                     width=100, height=35, fg_color="#ef4444", hover_color="#dc2626",
                     corner_radius=8).pack(side="left", padx=4)

        # Options : conteneur responsive (2 colonnes -> 1 sur écran étroit)
        options_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        options_frame.pack(fill="x", padx=10, pady=(5, 10))

        # Mode card
        mode_card = ctk.CTkFrame(options_frame, corner_radius=15)

        ctk.CTkLabel(mode_card, text="⚙️ Mode de conversion",
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))

        modes = [
            ("compress", "Compression", "Réduire la taille, même format"),
            ("to_jpg", "Convertir en JPG", "Conversion avec fond blanc"),
            ("panorama", "Panorama 2:1", "Format panorama pour articles")
        ]

        for val, title, desc in modes:
            frame = ctk.CTkFrame(mode_card, fg_color="transparent")
            frame.pack(fill="x", padx=10, pady=3)

            rb = ctk.CTkRadioButton(frame, text=title, variable=self.image_mode,
                                   value=val, font=("Segoe UI", 11))
            rb.pack(side="left")

            ctk.CTkLabel(frame, text=desc, font=("Segoe UI", 10),
                         text_color="gray").pack(side="left", padx=(20, 10))

        # Spacer pour aérer le bas de la card
        ctk.CTkFrame(mode_card, fg_color="transparent", height=8).pack()

        # Qualité card
        qual_card = ctk.CTkFrame(options_frame, corner_radius=15)

        ctk.CTkLabel(qual_card, text="📊 Qualité",
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))

        qual_inner = ctk.CTkFrame(qual_card, fg_color="transparent")
        qual_inner.pack(fill="x", padx=15, pady=(5, 15))

        self.qual_label = ctk.CTkLabel(qual_inner, text="75%", font=("Segoe UI", 36, "bold"),
                                      text_color="#6366f1")
        self.qual_label.pack()

        # Slider qui remplit la largeur dispo (width=0 -> fill=x prend le relais)
        self.qual_slider = ctk.CTkSlider(qual_inner, from_=1, to=100, number_of_steps=99,
                                        command=self.update_qual_label)
        self.qual_slider.set(75)
        self.qual_slider.pack(fill="x", pady=10)

        ctk.CTkLabel(qual_inner, text="1 = compression max  •  100 = qualité max",
                    font=("Segoe UI", 10), text_color="gray").pack()

        # Enregistrer pour reflow responsive
        self._register_responsive_options(options_frame, mode_card, qual_card)

        # Bouton action
        action_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        action_frame.pack(pady=15)

        self.img_action_btn = ctk.CTkButton(action_frame, text="🚀 Lancer la conversion",
                     command=self.process_images,
                     width=250, height=45, font=("Segoe UI", 14, "bold"),
                     fg_color="#22c55e", hover_color="#16a34a", corner_radius=10)
        self.img_action_btn.pack()
        
    def _setup_dnd(self, widget, callback):
        """Configure le drag & drop pour un widget"""
        if not TKDND_AVAILABLE:
            return
            
        try:
            # Récupérer le widget tkinter sous-jacent
            tk_widget = widget.winfo_toplevel()
            
            # Enregistrer la zone de drop
            widget.drop_target_register(DND_FILES)
            widget.dnd_bind('<<Drop>>', lambda e: self._handle_drop(e, callback))
            widget.dnd_bind('<<DragEnter>>', lambda e: self._on_drag_enter(widget))
            widget.dnd_bind('<<DragLeave>>', lambda e: self._on_drag_leave(widget))
        except Exception as e:
            print(f"DnD setup error: {e}")
            
    def _handle_drop(self, event, callback):
        """Gère le drop de fichiers"""
        try:
            # Parser les fichiers (format: {file1} {file2} ...)
            files = self.root.tk.splitlist(event.data)
            if files and callback:
                callback(files)
        except Exception as e:
            print(f"Drop error: {e}")
            
    def _on_drag_enter(self, widget):
        """Appelé quand on entre dans la zone"""
        try:
            widget.configure(border_color="#6366f1")
        except:
            pass
            
    def _on_drag_leave(self, widget):
        """Appelé quand on quitte la zone"""
        try:
            widget.configure(border_color=("gray70", "gray30"))
        except:
            pass
        
    def setup_videos_tab(self):
        """Onglet Vidéos : compression H.264/H.265/VP9, MP4 → WebM."""
        tab = self.tabview.tab("  🎬 Vidéos  ")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Fichiers
        files_frame = ctk.CTkFrame(scroll, corner_radius=15)
        files_frame.pack(fill="x", padx=10, pady=10)

        header = ctk.CTkFrame(files_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 0))

        dnd_text = " (Drag && Drop supporté)" if TKDND_AVAILABLE else ""
        ctk.CTkLabel(header, text=f"📁 Fichiers vidéo{dnd_text}",
                     font=("Segoe UI", 14, "bold")).pack(side="left")
        self.vid_count = ctk.CTkLabel(header, text="0 fichier",
                                      font=("Segoe UI", 11), text_color="gray")
        self.vid_count.pack(side="right")

        if TKDND_AVAILABLE:
            self.vid_drop_frame = ctk.CTkFrame(files_frame, fg_color=("gray85", "gray17"),
                                              border_width=2, border_color=("gray70", "gray30"),
                                              corner_radius=10, height=70)
            self.vid_drop_frame.pack(fill="x", padx=15, pady=10)
            self.vid_drop_frame.pack_propagate(False)

            ctk.CTkLabel(self.vid_drop_frame,
                        text="📂 Glissez-déposez vos fichiers vidéo ici",
                        font=("Segoe UI", 12)).pack(expand=True)

            self._setup_dnd(self.vid_drop_frame, self.on_video_drop)

        self.vid_listbox = ctk.CTkTextbox(files_frame, height=90, font=("Segoe UI", 11),
                                         state="disabled", corner_radius=10)
        self.vid_listbox.pack(fill="x", padx=15, pady=(0, 10))

        btn_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(btn_frame, text="+ Ajouter", command=self.add_videos,
                     width=100, height=35).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="− Retirer", command=self.remove_video,
                     width=100, height=35,
                     fg_color="#f59e0b", hover_color="#d97706").pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="× Vider", command=self.clear_videos,
                     width=100, height=35,
                     fg_color="#ef4444", hover_color="#dc2626").pack(side="left", padx=4)

        # Options
        options_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        options_frame.pack(fill="x", padx=10, pady=(5, 10))

        # Mode
        mode_card = ctk.CTkFrame(options_frame, corner_radius=15)

        ctk.CTkLabel(mode_card, text="🎯 Mode",
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))

        ctk.CTkRadioButton(mode_card, text="Compression H.264/H.265", variable=self.video_mode,
                          value="compress", font=("Segoe UI", 11)).pack(anchor="w", padx=15, pady=5)
        ctk.CTkLabel(mode_card, text="Réduire la taille des vidéos",
                     font=("Segoe UI", 10), text_color="gray").pack(anchor="w", padx=(45, 15))

        ctk.CTkRadioButton(mode_card, text="MP4 → WebM", variable=self.video_mode,
                          value="mp4_to_webm", font=("Segoe UI", 11)).pack(anchor="w", padx=15, pady=(15, 5))
        ctk.CTkLabel(mode_card, text="Conversion VP9 avec alpha supporté",
                     font=("Segoe UI", 10), text_color="gray").pack(anchor="w", padx=(45, 15))

        ctk.CTkFrame(mode_card, fg_color="transparent", height=10).pack()

        # Paramètres
        params_card = ctk.CTkFrame(options_frame, corner_radius=15)

        ctk.CTkLabel(params_card, text="⚙️ Paramètres",
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))

        # Codec — on utilise fill="x" pour que ça s'adapte
        ctk.CTkLabel(params_card, text="Codec:",
                     font=("Segoe UI", 11)).pack(anchor="w", padx=15, pady=(5, 0))
        self.vid_codec = ctk.CTkOptionMenu(params_card,
                                          values=["libx264", "libx265", "libvpx-vp9"],
                                          font=("Segoe UI", 11))
        self.vid_codec.set("libx264")
        self.vid_codec.pack(fill="x", padx=15, pady=(5, 10))

        # CRF (avec valeur affichée)
        crf_row = ctk.CTkFrame(params_card, fg_color="transparent")
        crf_row.pack(fill="x", padx=15)
        ctk.CTkLabel(crf_row, text="CRF (qualité):",
                     font=("Segoe UI", 11)).pack(side="left")
        self.vid_crf_label = ctk.CTkLabel(crf_row, text="23",
                                          font=("Segoe UI", 11, "bold"),
                                          text_color="#6366f1")
        self.vid_crf_label.pack(side="right")
        self.vid_crf = ctk.CTkSlider(params_card, from_=0, to=51, number_of_steps=51,
                                     command=lambda v: self.vid_crf_label.configure(text=f"{int(v)}"))
        self.vid_crf.set(23)
        self.vid_crf.pack(fill="x", padx=15, pady=5)

        # Preset
        ctk.CTkLabel(params_card, text="Vitesse:",
                     font=("Segoe UI", 11)).pack(anchor="w", padx=15, pady=(10, 0))
        self.vid_preset = ctk.CTkOptionMenu(params_card,
                                           values=["ultrafast", "superfast", "veryfast",
                                                   "faster", "fast", "medium", "slow"],
                                           font=("Segoe UI", 11))
        self.vid_preset.set("medium")
        self.vid_preset.pack(fill="x", padx=15, pady=(5, 15))

        self._register_responsive_options(options_frame, mode_card, params_card)

        # Bouton
        action_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        action_frame.pack(pady=15)

        self.vid_action_btn = ctk.CTkButton(action_frame, text="🚀 Lancer la conversion",
                     command=self.process_videos,
                     width=250, height=45, font=("Segoe UI", 14, "bold"),
                     fg_color="#22c55e", hover_color="#16a34a", corner_radius=10)
        self.vid_action_btn.pack()
        
    def setup_audio_tab(self):
        """Onglet Audio : conversion en MP3 192k."""
        tab = self.tabview.tab("  🎵 Audio  ")
        scroll = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Fichiers
        files_frame = ctk.CTkFrame(scroll, corner_radius=15)
        files_frame.pack(fill="x", padx=10, pady=10)

        header = ctk.CTkFrame(files_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 0))

        dnd_text = " (Drag && Drop supporté)" if TKDND_AVAILABLE else ""
        ctk.CTkLabel(header, text=f"📁 Fichiers audio{dnd_text}",
                     font=("Segoe UI", 14, "bold")).pack(side="left")
        self.aud_count = ctk.CTkLabel(header, text="0 fichier",
                                      font=("Segoe UI", 11), text_color="gray")
        self.aud_count.pack(side="right")

        if TKDND_AVAILABLE:
            self.aud_drop_frame = ctk.CTkFrame(files_frame, fg_color=("gray85", "gray17"),
                                              border_width=2, border_color=("gray70", "gray30"),
                                              corner_radius=10, height=70)
            self.aud_drop_frame.pack(fill="x", padx=15, pady=10)
            self.aud_drop_frame.pack_propagate(False)

            ctk.CTkLabel(self.aud_drop_frame,
                        text="📂 Glissez-déposez vos fichiers audio ici",
                        font=("Segoe UI", 12)).pack(expand=True)

            self._setup_dnd(self.aud_drop_frame, self.on_audio_drop)

        self.aud_listbox = ctk.CTkTextbox(files_frame, height=90, font=("Segoe UI", 11),
                                         state="disabled", corner_radius=10)
        self.aud_listbox.pack(fill="x", padx=15, pady=(0, 10))

        btn_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkButton(btn_frame, text="+ Ajouter", command=self.add_audio,
                     width=100, height=35).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_frame, text="− Retirer", command=self.remove_audio,
                     width=100, height=35,
                     fg_color="#f59e0b", hover_color="#d97706").pack(side="left", padx=4)
        ctk.CTkButton(btn_frame, text="× Vider", command=self.clear_audio,
                     width=100, height=35,
                     fg_color="#ef4444", hover_color="#dc2626").pack(side="left", padx=4)

        # Info
        info_card = ctk.CTkFrame(scroll, corner_radius=15)
        info_card.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(info_card, text="ℹ️ Informations",
                     font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=15, pady=(15, 10))
        ctk.CTkLabel(info_card, text="Conversion vers MP3",
                     font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15)
        ctk.CTkLabel(info_card,
                     text="\nFormats supportés : M4A, OPUS, WAV, FLAC, AAC, OGG\nBitrate : 192k  •  Codec : libmp3lame",
                     font=("Segoe UI", 11), text_color="gray",
                     justify="left").pack(anchor="w", padx=15)

        # Dossier sortie avec bouton parcourir
        ctk.CTkLabel(info_card, text="Dossier de sortie :",
                     font=("Segoe UI", 11)).pack(anchor="w", padx=15, pady=(15, 5))

        out_row = ctk.CTkFrame(info_card, fg_color="transparent")
        out_row.pack(fill="x", padx=15, pady=(0, 15))

        ctk.CTkEntry(out_row, textvariable=self.audio_output,
                     font=("Segoe UI", 11)).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(out_row, text="📁 Parcourir", width=110, height=28,
                      command=self._choose_audio_output).pack(side="right", padx=(8, 0))

        # Bouton
        action_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        action_frame.pack(pady=20)

        self.aud_action_btn = ctk.CTkButton(action_frame, text="🚀 Lancer la conversion",
                     command=self.process_audio,
                     width=250, height=45, font=("Segoe UI", 14, "bold"),
                     fg_color="#22c55e", hover_color="#16a34a", corner_radius=10)
        self.aud_action_btn.pack()

    def _choose_audio_output(self):
        folder = filedialog.askdirectory(title="Choisir le dossier de sortie")
        if folder:
            self.audio_output.set(folder)
        
    # ========== RESPONSIVE LAYOUT ==========
    def _register_responsive_options(self, container, left_card, right_card):
        """Enregistre une paire de cards à reflow automatiquement.

        Au-dessus du seuil : 2 colonnes côte à côte (grid col 0/1, weight 1).
        En-dessous : une seule colonne, empilée verticalement.
        """
        self._responsive_option_frames.append((container, left_card, right_card))
        # Layout initial (2 colonnes par défaut)
        self._apply_options_layout(container, left_card, right_card, narrow=False)

    def _apply_options_layout(self, container, left, right, narrow):
        # Retirer l'ancien placement
        for w in (left, right):
            try:
                w.grid_forget()
            except Exception:
                pass
            try:
                w.pack_forget()
            except Exception:
                pass

        if narrow:
            # 1 colonne : empiler verticalement
            container.grid_columnconfigure(0, weight=1)
            container.grid_columnconfigure(1, weight=0)
            left.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
            right.grid(row=1, column=0, sticky="nsew")
        else:
            # 2 colonnes égales
            container.grid_columnconfigure(0, weight=1)
            container.grid_columnconfigure(1, weight=1)
            left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
            right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

    def _on_root_configure(self, event):
        # N'agir que sur l'événement de la root window
        if event.widget is not self.root:
            return
        narrow = event.width < self.NARROW_WIDTH_THRESHOLD
        if narrow == self._current_narrow_mode:
            return
        self._current_narrow_mode = narrow
        for container, left, right in self._responsive_option_frames:
            self._apply_options_layout(container, left, right, narrow)

    def update_qual_label(self, value):
        self.qual_label.configure(text=f"{int(value)}%")
        
    def log(self, message, tag=None):
        # Thread-safe : déléguer l'insertion au thread Tk principal
        def _insert():
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_text.configure(state="normal")
            self.log_text.insert("end", f"[{timestamp}] {message}\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        try:
            self.root.after(0, _insert)
        except Exception:
            _insert()

    def clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_processing(self, active, which):
        """Désactive le bouton d'action pendant un traitement (thread-safe)."""
        def _apply():
            self.processing = active
            btns = {
                "img": getattr(self, "img_action_btn", None),
                "vid": getattr(self, "vid_action_btn", None),
                "aud": getattr(self, "aud_action_btn", None),
            }
            btn = btns.get(which)
            if btn is None:
                return
            if active:
                btn.configure(state="disabled", text="⏳ Traitement en cours...")
            else:
                btn.configure(state="normal", text="🚀 Lancer la conversion")
        try:
            self.root.after(0, _apply)
        except Exception:
            _apply()
        
    def check_dependencies(self):
        """Vérifie la présence de ffmpeg / ffprobe / magick dans le PATH."""
        deps = {'ffmpeg': False, 'ffprobe': False, 'magick': False}
        for cmd in deps:
            try:
                subprocess.run([cmd, '-version'], capture_output=True, check=True)
                deps[cmd] = True
            except:
                pass
                
        missing = [k for k, v in deps.items() if not v]
        if missing:
            self.log(f"⚠️ Manquants: {', '.join(missing)}")
        else:
            self.log("✅ Toutes les dépendances sont disponibles")
            
    # ========== UPDATE LISTBOXES ==========
    def update_img_list(self):
        self.img_listbox.configure(state="normal")
        self.img_listbox.delete("1.0", "end")
        for f in self.image_files:
            icon = "🖼️" if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')) else "📄"
            self.img_listbox.insert("end", f"{icon} {os.path.basename(f)}\n")
        self.img_listbox.configure(state="disabled")
        self.img_count.configure(text=f"{len(self.image_files)} fichier{'s' if len(self.image_files) != 1 else ''}")
        
    def update_vid_list(self):
        self.vid_listbox.configure(state="normal")
        self.vid_listbox.delete("1.0", "end")
        for f in self.video_files:
            self.vid_listbox.insert("end", f"🎬 {os.path.basename(f)}\n")
        self.vid_listbox.configure(state="disabled")
        self.vid_count.configure(text=f"{len(self.video_files)} fichier{'s' if len(self.video_files) != 1 else ''}")
        
    def update_aud_list(self):
        self.aud_listbox.configure(state="normal")
        self.aud_listbox.delete("1.0", "end")
        for f in self.audio_files:
            self.aud_listbox.insert("end", f"🎵 {os.path.basename(f)}\n")
        self.aud_listbox.configure(state="disabled")
        self.aud_count.configure(text=f"{len(self.audio_files)} fichier{'s' if len(self.audio_files) != 1 else ''}")
        
    # ========== DROP HANDLERS ==========
    def on_image_drop(self, files):
        valid_ext = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.gif']
        added = 0
        for f in files:
            if Path(f).suffix.lower() in valid_ext and f not in self.image_files:
                self.image_files.append(f)
                added += 1
        if added > 0:
            self.update_img_list()
            self.log(f"🖼️ {added} image(s) ajoutée(s) par glisser-déposer")
            
    def on_video_drop(self, files):
        valid_ext = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        added = 0
        for f in files:
            if Path(f).suffix.lower() in valid_ext and f not in self.video_files:
                self.video_files.append(f)
                added += 1
        if added > 0:
            self.update_vid_list()
            self.log(f"🎬 {added} vidéo(s) ajoutée(s) par glisser-déposer")
            
    def on_audio_drop(self, files):
        valid_ext = ['.m4a', '.opus', '.wav', '.flac', '.aac', '.ogg', '.mp3']
        added = 0
        for f in files:
            if Path(f).suffix.lower() in valid_ext and f not in self.audio_files:
                self.audio_files.append(f)
                added += 1
        if added > 0:
            self.update_aud_list()
            self.log(f"🎵 {added} fichier(s) audio ajouté(s) par glisser-déposer")
        
    # ========== IMAGE ACTIONS ==========
    def add_images(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.gif"), ("Tous", "*.*")]
        )
        for f in files:
            if f not in self.image_files:
                self.image_files.append(f)
        self.update_img_list()
        
    def remove_image(self):
        if self.image_files:
            self.image_files.pop()
            self.update_img_list()
            
    def clear_images(self):
        self.image_files.clear()
        self.update_img_list()
        
    def process_images(self):
        if self.processing:
            return
        if not self.image_files:
            messagebox.showwarning("Attention", "Aucun fichier sélectionné")
            return
        self._set_processing(True, "img")
        threading.Thread(target=self._proc_img, daemon=True).start()
        
    def _proc_img(self):
        try:
            mode = self.image_mode.get()
            quality = int(self.qual_slider.get())

            self.log(f"🖼️ Traitement de {len(self.image_files)} image(s)...")

            for i, path in enumerate(self.image_files, 1):
                fname = os.path.basename(path)
                self.log(f"  [{i}/{len(self.image_files)}] {fname}")

                try:
                    if mode == "compress":
                        name, ext = os.path.splitext(path)
                        out = f"{name}_compressed{ext}"
                        cmd = ['magick', 'convert', path, '-resize', '100%', '-quality', str(quality),
                               '-background', 'white', '-flatten', out]
                    elif mode == "to_jpg":
                        name = os.path.splitext(os.path.basename(path))[0]
                        base = os.path.dirname(path)
                        out_dir = os.path.join(base, "compressed") if len(self.image_files) > 1 else base
                        os.makedirs(out_dir, exist_ok=True)
                        out = os.path.join(out_dir, f"{name}.jpg")
                        cmd = ['magick', 'convert', path, '-resize', '100%', '-quality', str(quality),
                               '-background', 'white', '-flatten', out]
                    else:
                        name, _ = os.path.splitext(path)
                        out = f"{name}_compressed.jpg"
                        q = max(1, min(31, int((100 - quality) / 3.2)))
                        cmd = ['ffmpeg', '-y', '-i', path, '-vf', 'scale=2*ih:ih,setsar=1',
                               '-q:v', str(q), out]

                    result = subprocess.run(cmd, capture_output=True, text=True)
                    ok = result.returncode == 0
                    if ok:
                        self.log(f"  ✅ Terminé → {os.path.basename(out)}")
                    else:
                        err = (result.stderr or "").strip().splitlines()
                        tail = err[-1] if err else "(pas de détail)"
                        self.log(f"  ❌ Échec : {tail}")
                except Exception as e:
                    self.log(f"  ❌ Erreur : {e}")

            self.log("🏁 Terminé !")
        finally:
            self._set_processing(False, "img")
        
    # ========== VIDEO ACTIONS ==========
    def add_videos(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Vidéos", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm"), ("Tous", "*.*")]
        )
        for f in files:
            if f not in self.video_files:
                self.video_files.append(f)
        self.update_vid_list()
        
    def remove_video(self):
        if self.video_files:
            self.video_files.pop()
            self.update_vid_list()
            
    def clear_videos(self):
        self.video_files.clear()
        self.update_vid_list()
        
    def process_videos(self):
        if self.processing:
            return
        if not self.video_files:
            messagebox.showwarning("Attention", "Aucun fichier sélectionné")
            return
        self._set_processing(True, "vid")
        threading.Thread(target=self._proc_vid, daemon=True).start()

    def _proc_vid(self):
        try:
            mode = self.video_mode.get()
            codec = self.vid_codec.get()
            crf = int(self.vid_crf.get())
            preset = self.vid_preset.get()

            self.log(f"🎬 Traitement de {len(self.video_files)} vidéo(s)...")

            for i, path in enumerate(self.video_files, 1):
                fname = os.path.basename(path)
                self.log(f"  [{i}/{len(self.video_files)}] {fname}")

                try:
                    if mode == "compress":
                        f = Path(path)
                        # BUG FIX : with_suffix n'accepte qu'un suffixe commençant par '.'
                        # On construit le chemin manuellement.
                        out = f.with_name(f"{f.stem}_compressed{f.suffix}")
                        cmd = ['ffmpeg', '-y', '-i', str(path), '-c:v', codec, '-crf', str(crf),
                               '-preset', preset, '-c:a', 'aac', '-b:a', '128k', str(out)]
                    else:
                        f = Path(path)
                        out = f.with_suffix('.webm')
                        has_a = False
                        try:
                            r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                                              '-show_streams', str(path)],
                                              capture_output=True, text=True)
                            info = json.loads(r.stdout or "{}")
                            for s in info.get('streams', []):
                                if s.get('codec_type') == 'video':
                                    pix = s.get('pix_fmt', '') or ''
                                    # Formats avec canal alpha typiques : yuva*, rgba, bgra, ya8, ya16, argb, abgr, gbrap*
                                    if any(tok in pix for tok in ('yuva', 'rgba', 'bgra', 'argb',
                                                                   'abgr', 'gbrap', 'ya8', 'ya16')):
                                        has_a = True
                                        break
                        except Exception:
                            pass

                        cmd = ['ffmpeg', '-y', '-i', str(path)]
                        if has_a:
                            cmd.extend(['-c:v', 'libvpx-vp9', '-pix_fmt', 'yuva420p',
                                        '-auto-alt-ref', '0'])
                        else:
                            cmd.extend(['-c:v', 'libvpx-vp9', '-pix_fmt', 'yuv420p'])
                        cmd.extend(['-crf', '30', '-b:v', '0',
                                    '-c:a', 'libopus', '-b:a', '128k', str(out)])

                    result = subprocess.run(cmd, capture_output=True, text=True)
                    ok = result.returncode == 0
                    if ok:
                        self.log(f"  ✅ Terminé → {out.name}")
                    else:
                        err = (result.stderr or "").strip().splitlines()
                        tail = err[-1] if err else "(pas de détail)"
                        self.log(f"  ❌ Échec : {tail}")
                except Exception as e:
                    self.log(f"  ❌ Erreur : {e}")

            self.log("🏁 Terminé !")
        finally:
            self._set_processing(False, "vid")
        
    # ========== AUDIO ACTIONS ==========
    def add_audio(self):
        files = filedialog.askopenfilenames(
            filetypes=[("Audio", "*.m4a *.opus *.wav *.flac *.aac *.ogg *.mp3"), ("Tous", "*.*")]
        )
        for f in files:
            if f not in self.audio_files:
                self.audio_files.append(f)
        self.update_aud_list()
        
    def remove_audio(self):
        if self.audio_files:
            self.audio_files.pop()
            self.update_aud_list()
            
    def clear_audio(self):
        self.audio_files.clear()
        self.update_aud_list()
        
    def process_audio(self):
        if self.processing:
            return
        if not self.audio_files:
            messagebox.showwarning("Attention", "Aucun fichier sélectionné")
            return
        self._set_processing(True, "aud")
        threading.Thread(target=self._proc_aud, daemon=True).start()

    def _proc_aud(self):
        try:
            raw = (self.audio_output.get() or "").strip() or "converted_mp3"
            out_dir = Path(raw)
            try:
                # parents=True pour supporter les chemins imbriqués
                out_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.log(f"❌ Impossible de créer le dossier de sortie : {e}")
                return

            self.log(f"🎵 Conversion de {len(self.audio_files)} fichier(s)...")

            for i, path in enumerate(self.audio_files, 1):
                fname = os.path.basename(path)
                out = out_dir / f"{Path(fname).stem}.mp3"

                self.log(f"  [{i}/{len(self.audio_files)}] {fname}")

                cmd = ['ffmpeg', '-y', '-i', str(path), '-vn', '-codec:a', 'libmp3lame',
                       '-b:a', '192k', str(out)]
                r = subprocess.run(cmd, capture_output=True, text=True)

                if r.returncode == 0:
                    self.log(f"  ✅ Terminé → {out.name}")
                else:
                    err = (r.stderr or "").strip().splitlines()
                    tail = err[-1] if err else "(pas de détail)"
                    self.log(f"  ❌ Échec : {tail}")

            self.log(f"🏁 Terminé ! → {out_dir}")
        finally:
            self._set_processing(False, "aud")
        
    def run(self):
        self.root.mainloop()

def main():
    app = MediaToolkitApp()
    app.run()

if __name__ == "__main__":
    main()
