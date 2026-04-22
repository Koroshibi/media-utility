#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import threading
from pathlib import Path
import json

class VideoCompressor:
    def __init__(self, root):
        self.root = root
        self.root.title("Video Compressor Pro")
        self.root.geometry("950x750")
        self.root.minsize(850, 650)
        
        # Variables
        self.video_files = []
        self.output_directory = tk.StringVar()
        self.resolution = tk.StringVar()
        self.quality = tk.StringVar(value="23")
        self.preset = tk.StringVar(value="medium")
        self.codec = tk.StringVar(value="libx264")
        self.custom_resolution = tk.BooleanVar(value=False)
        self.keep_audio = tk.BooleanVar(value=True)
        self.keep_aspect_ratio = tk.BooleanVar(value=True)
        
        # Couleurs du thème
        self.colors = {
            'bg_primary': '#1e1e2e',
            'bg_secondary': '#2a2a3e',
            'bg_tertiary': '#35354a',
            'accent': '#7c3aed',
            'accent_hover': '#6d28d9',
            'success': '#10b981',
            'danger': '#ef4444',
            'warning': '#f59e0b',
            'text_primary': '#f8f8f2',
            'text_secondary': '#a0a0b0',
            'border': '#404056'
        }
        
        self.setup_styles()
        self.setup_ui()
        
    def setup_styles(self):
        self.root.configure(bg=self.colors['bg_primary'])
        
        style = ttk.Style()
        style.theme_use('clam')
        
        style.configure('TNotebook', background=self.colors['bg_primary'])
        style.configure('TNotebook.Tab', background=self.colors['bg_secondary'],
                       foreground=self.colors['text_primary'], padding=[20, 8])
        style.map('TNotebook.Tab', background=[('selected', self.colors['bg_tertiary'])])
        
    def setup_ui(self):
        # Container principal
        main_container = tk.Frame(self.root, bg=self.colors['bg_primary'])
        main_container.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Canvas scrollable
        canvas = tk.Canvas(main_container, bg=self.colors['bg_primary'], highlightthickness=0)
        scrollbar = tk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg=self.colors['bg_primary'])
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Header
        header_frame = tk.Frame(scrollable_frame, bg=self.colors['bg_primary'])
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_container = tk.Frame(header_frame, bg=self.colors['bg_primary'])
        title_container.pack(side='left')
        
        tk.Label(title_container, text="🎬", font=('Segoe UI', 24),
                bg=self.colors['bg_primary']).pack(side='left', padx=(0, 10))
        
        tk.Label(title_container, text="Video Compressor Pro",
                font=('Segoe UI', 20, 'bold'),
                fg=self.colors['text_primary'],
                bg=self.colors['bg_primary']).pack(side='left')
        
        tk.Label(title_container, text=" - Compressez vos vidéos avec style",
                font=('Segoe UI', 10),
                fg=self.colors['text_secondary'],
                bg=self.colors['bg_primary']).pack(side='left', pady=(8, 0))
        
        # Container pour le contenu
        content_container = tk.Frame(scrollable_frame, bg=self.colors['bg_primary'])
        content_container.pack(fill='both', expand=True)
        
        # Section Fichiers
        files_frame = tk.Frame(content_container, bg=self.colors['bg_secondary'],
                              highlightbackground=self.colors['border'],
                              highlightthickness=1)
        files_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        files_title_frame = tk.Frame(files_frame, bg=self.colors['bg_tertiary'], height=35)
        files_title_frame.pack(fill='x')
        files_title_frame.pack_propagate(False)
        
        tk.Label(files_title_frame, text="📁 Fichiers d'entrée",
                bg=self.colors['bg_tertiary'],
                fg=self.colors['text_primary'],
                font=('Segoe UI', 10, 'bold')).pack(side='left', padx=10, pady=8)
        
        files_content = tk.Frame(files_frame, bg=self.colors['bg_secondary'])
        files_content.pack(fill='both', expand=True, padx=10, pady=10)
        
        list_frame = tk.Frame(files_content, bg=self.colors['bg_secondary'])
        list_frame.pack(fill='both', expand=True)
        
        self.files_listbox = tk.Listbox(list_frame,
                                        bg=self.colors['bg_tertiary'],
                                        fg=self.colors['text_primary'],
                                        selectbackground=self.colors['accent'],
                                        selectforeground='white',
                                        font=('Segoe UI', 9),
                                        height=4,
                                        bd=0,
                                        highlightthickness=1,
                                        highlightbackground=self.colors['border'],
                                        highlightcolor=self.colors['accent'])
        self.files_listbox.pack(side='left', fill='both', expand=True)
        
        files_scrollbar = tk.Scrollbar(list_frame, bg=self.colors['bg_tertiary'])
        files_scrollbar.pack(side='right', fill='y')
        self.files_listbox.config(yscrollcommand=files_scrollbar.set)
        files_scrollbar.config(command=self.files_listbox.yview)
        
        btn_container = tk.Frame(files_content, bg=self.colors['bg_secondary'])
        btn_container.pack(fill='x', pady=(8, 0))
        
        self.add_btn = self.create_button(btn_container, "➕ Ajouter", self.add_videos,
                                          self.colors['accent'], width=10)
        self.add_btn.pack(side='left', padx=(0, 3))
        
        self.remove_btn = self.create_button(btn_container, "➖ Retirer", self.remove_selected,
                                             self.colors['warning'], width=10)
        self.remove_btn.pack(side='left', padx=3)
        
        self.clear_btn = self.create_button(btn_container, "🗑️ Vider", self.clear_list,
                                           self.colors['danger'], width=10)
        self.clear_btn.pack(side='left', padx=3)
        
        self.files_stats = tk.Label(btn_container, text="0 fichier(s)",
                                    bg=self.colors['bg_secondary'],
                                    fg=self.colors['text_secondary'],
                                    font=('Segoe UI', 9))
        self.files_stats.pack(side='right')
        
        # Notebook pour les paramètres
        notebook = ttk.Notebook(content_container)
        notebook.pack(fill='both', expand=False, pady=(0, 10))
        
        # Onglet Compression
        compression_tab = tk.Frame(notebook, bg=self.colors['bg_secondary'])
        notebook.add(compression_tab, text='🎥 Compression')
        
        comp_frame = tk.Frame(compression_tab, bg=self.colors['bg_secondary'])
        comp_frame.pack(padx=15, pady=15)
        
        tk.Label(comp_frame, text="Codec:", bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'], font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', pady=5)
        
        codec_combo = ttk.Combobox(comp_frame, textvariable=self.codec, width=20,
                                   values=('libx264', 'libx265', 'libvpx-vp9', 'libav1'), state='readonly')
        codec_combo.grid(row=0, column=1, sticky='w', padx=(10, 0))
        
        tk.Label(comp_frame, text="Qualité (CRF):", bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'], font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', pady=(10, 5))
        
        quality_container = tk.Frame(comp_frame, bg=self.colors['bg_secondary'])
        quality_container.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(0, 5))
        
        label_frame = tk.Frame(quality_container, bg=self.colors['bg_secondary'], width=120)
        label_frame.pack(side='right', fill='y')
        label_frame.pack_propagate(False)
        
        self.quality_label = tk.Label(label_frame, text="23 - Recommandé",
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['accent'],
                                     font=('Segoe UI', 9, 'bold'))
        self.quality_label.pack(expand=True)
        
        self.quality_scale = tk.Scale(quality_container, from_=0, to=51,
                                     orient='horizontal',
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'],
                                     troughcolor=self.colors['bg_tertiary'],
                                     activebackground=self.colors['accent'],
                                     highlightthickness=0,
                                     command=self.update_quality_label,
                                     length=250)
        self.quality_scale.set(23)
        self.quality_scale.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        tk.Label(comp_frame, text="Vitesse:", bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'], font=('Segoe UI', 10)).grid(row=3, column=0, sticky='w', pady=(10, 5))
        
        preset_combo = ttk.Combobox(comp_frame, textvariable=self.preset, width=20,
                                    values=('ultrafast', 'superfast', 'veryfast', 'faster',
                                           'fast', 'medium', 'slow', 'slower', 'veryslow'), state='readonly')
        preset_combo.grid(row=3, column=1, sticky='w', padx=(10, 0))
        
        # Onglet Résolution
        resolution_tab = tk.Frame(notebook, bg=self.colors['bg_secondary'])
        notebook.add(resolution_tab, text='📐 Résolution & Audio')
        
        res_frame = tk.Frame(resolution_tab, bg=self.colors['bg_secondary'])
        res_frame.pack(padx=15, pady=15)
        
        tk.Radiobutton(res_frame, text="Conserver l'originale",
                      variable=self.custom_resolution, value=False,
                      command=self.toggle_resolution,
                      bg=self.colors['bg_secondary'],
                      fg=self.colors['text_primary'],
                      activebackground=self.colors['bg_secondary'],
                      selectcolor=self.colors['bg_tertiary'],
                      font=('Segoe UI', 10)).grid(row=0, column=0, sticky='w', pady=5)
        
        tk.Radiobutton(res_frame, text="Personnalisée:",
                      variable=self.custom_resolution, value=True,
                      command=self.toggle_resolution,
                      bg=self.colors['bg_secondary'],
                      fg=self.colors['text_primary'],
                      activebackground=self.colors['bg_secondary'],
                      selectcolor=self.colors['bg_tertiary'],
                      font=('Segoe UI', 10)).grid(row=1, column=0, sticky='w', pady=5)
        
        self.resolution_combo = ttk.Combobox(res_frame, textvariable=self.resolution, width=30,
                                            values=('3840x2160 (4K UHD)', 
                                                   '2560x1440 (2K QHD)', 
                                                   '2160x1920 (Full HD 3D SBS - Vertical 9:8)',
                                                   '1920x1080 (Full HD)',
                                                   '1280x720 (HD Ready)', 
                                                   '854x480 (480p)', 
                                                   '640x360 (360p)',
                                                   'Échelle proportionnelle...'),
                                            state='disabled')
        self.resolution_combo.grid(row=2, column=0, sticky='w', pady=5, padx=(20, 0))
        self.resolution.set('1920x1080 (Full HD)')
        
        # Option pour garder le ratio d'aspect
        self.aspect_check = tk.Checkbutton(res_frame, text="🔒 Préserver le ratio d'aspect",
                                          variable=self.keep_aspect_ratio,
                                          bg=self.colors['bg_secondary'],
                                          fg=self.colors['text_primary'],
                                          activebackground=self.colors['bg_secondary'],
                                          selectcolor=self.colors['bg_tertiary'],
                                          font=('Segoe UI', 10))
        self.aspect_check.grid(row=3, column=0, sticky='w', pady=5, padx=(20, 0))
        
        tk.Label(res_frame, text="💡 Évite la déformation de l'image",
                bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'],
                font=('Segoe UI', 8)).grid(row=4, column=0, sticky='w', padx=(40, 0))
        
        tk.Frame(res_frame, bg=self.colors['bg_secondary'], height=15).grid(row=5, column=0)
        
        self.audio_check = tk.Checkbutton(res_frame, text="🔊 Conserver l'audio",
                                         variable=self.keep_audio,
                                         bg=self.colors['bg_secondary'],
                                         fg=self.colors['text_primary'],
                                         activebackground=self.colors['bg_secondary'],
                                         selectcolor=self.colors['bg_tertiary'],
                                         font=('Segoe UI', 10))
        self.audio_check.grid(row=6, column=0, sticky='w', pady=5)
        
        # Onglet Sortie
        output_tab = tk.Frame(notebook, bg=self.colors['bg_secondary'])
        notebook.add(output_tab, text='💾 Sortie')
        
        out_frame = tk.Frame(output_tab, bg=self.colors['bg_secondary'])
        out_frame.pack(padx=15, pady=15, fill='x')
        
        tk.Label(out_frame, text="Dossier de sortie:", bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'], font=('Segoe UI', 10)).pack(anchor='w', pady=(0, 5))
        
        output_container = tk.Frame(out_frame, bg=self.colors['bg_secondary'])
        output_container.pack(fill='x', pady=(0, 5))
        
        self.output_entry = tk.Entry(output_container, textvariable=self.output_directory,
                                    bg=self.colors['bg_tertiary'],
                                    fg=self.colors['text_primary'],
                                    insertbackground=self.colors['text_primary'],
                                    font=('Segoe UI', 9),
                                    bd=0,
                                    highlightthickness=1,
                                    highlightbackground=self.colors['border'],
                                    highlightcolor=self.colors['accent'])
        self.output_entry.pack(side='left', fill='x', expand=True, ipady=4)
        
        browse_btn = self.create_button(output_container, "📂", self.browse_output,
                                       self.colors['accent'], width=3)
        browse_btn.pack(side='right', padx=(5, 0))
        
        tk.Label(out_frame, text="💡 Vide = dossier original", bg=self.colors['bg_secondary'],
                fg=self.colors['text_secondary'], font=('Segoe UI', 8)).pack(anchor='w', pady=(5, 10))
        
        tk.Label(out_frame, text="Suffixe:", bg=self.colors['bg_secondary'],
                fg=self.colors['text_primary'], font=('Segoe UI', 10)).pack(anchor='w', pady=(10, 5))
        
        self.suffix_var = tk.StringVar(value="_compressed")
        tk.Entry(out_frame, textvariable=self.suffix_var,
                bg=self.colors['bg_tertiary'],
                fg=self.colors['text_primary'],
                insertbackground=self.colors['text_primary'],
                font=('Segoe UI', 9),
                bd=0,
                width=25,
                highlightthickness=1,
                highlightbackground=self.colors['border'],
                highlightcolor=self.colors['accent']).pack(anchor='w', ipady=4)
        
        # Progression et Actions
        progress_frame = tk.Frame(content_container, bg=self.colors['bg_secondary'],
                                 highlightbackground=self.colors['border'],
                                 highlightthickness=1)
        progress_frame.pack(fill='x', pady=(0, 10))
        
        progress_content = tk.Frame(progress_frame, bg=self.colors['bg_secondary'])
        progress_content.pack(padx=10, pady=10)
        
        progress_bg = tk.Frame(progress_content, bg=self.colors['bg_tertiary'], height=6)
        progress_bg.pack(fill='x', pady=(0, 8))
        
        self.progress_fill = tk.Frame(progress_bg, bg=self.colors['accent'], height=6)
        self.progress_fill.place(x=0, y=0, relwidth=0.0, relheight=1.0)
        
        status_container = tk.Frame(progress_content, bg=self.colors['bg_secondary'])
        status_container.pack(fill='x')
        
        self.status_label = tk.Label(status_container, text="Prêt à compresser",
                                    bg=self.colors['bg_secondary'],
                                    fg=self.colors['text_primary'],
                                    font=('Segoe UI', 10))
        self.status_label.pack(side='left')
        
        self.progress_percent = tk.Label(status_container, text="0%",
                                        bg=self.colors['bg_secondary'],
                                        fg=self.colors['accent'],
                                        font=('Segoe UI', 10, 'bold'))
        self.progress_percent.pack(side='right')
        
        action_frame = tk.Frame(progress_content, bg=self.colors['bg_secondary'])
        action_frame.pack(pady=(10, 0))
        
        self.compress_btn = self.create_button(action_frame, "🚀 COMPRESSER", self.start_compression,
                                              self.colors['success'], width=15)
        self.compress_btn.pack(side='left', padx=5)
        
        quit_btn = self.create_button(action_frame, "✖ QUITTER", self.root.quit,
                                      self.colors['danger'], width=15)
        quit_btn.pack(side='left', padx=5)
        
        # Zone de log
        log_frame = tk.Frame(content_container, bg=self.colors['bg_secondary'],
                            highlightbackground=self.colors['border'],
                            highlightthickness=1)
        log_frame.pack(fill='both', expand=True)
        
        log_title_frame = tk.Frame(log_frame, bg=self.colors['bg_tertiary'], height=30)
        log_title_frame.pack(fill='x')
        log_title_frame.pack_propagate(False)
        
        tk.Label(log_title_frame, text="📝 Journal",
                bg=self.colors['bg_tertiary'],
                fg=self.colors['text_primary'],
                font=('Segoe UI', 9, 'bold')).pack(side='left', padx=10, pady=6)
        
        log_container = tk.Frame(log_frame, bg=self.colors['bg_tertiary'])
        log_container.pack(fill='both', expand=True, padx=1, pady=1)
        
        self.log_text = tk.Text(log_container,
                               bg=self.colors['bg_tertiary'],
                               fg=self.colors['text_primary'],
                               font=('Consolas', 8),
                               wrap='word',
                               bd=0,
                               padx=8,
                               pady=8,
                               height=6)
        self.log_text.pack(side='left', fill='both', expand=True)
        
        log_scrollbar = tk.Scrollbar(log_container, bg=self.colors['bg_tertiary'])
        log_scrollbar.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        log_scrollbar.config(command=self.log_text.yview)
        
        self.log_text.tag_config('success', foreground=self.colors['success'])
        self.log_text.tag_config('error', foreground=self.colors['danger'])
        self.log_text.tag_config('warning', foreground=self.colors['warning'])
        self.log_text.tag_config('info', foreground=self.colors['text_secondary'])
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    def create_button(self, parent, text, command, color, width=None, height=None):
        btn = tk.Button(parent, text=text, command=command,
                       bg=color, fg='white',
                       font=('Segoe UI', 9, 'bold'),
                       bd=0,
                       padx=10, pady=5,
                       cursor='hand2',
                       activebackground=color,
                       activeforeground='white')
        if width:
            btn.config(width=width)
        if height:
            btn.config(height=height)
        
        def on_enter(e):
            if btn['state'] != 'disabled':
                btn['bg'] = self.adjust_color(color, -20)
        
        def on_leave(e):
            btn['bg'] = color
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        
        return btn
    
    def adjust_color(self, hex_color, brightness_offset):
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (1, 3, 5))
        rgb = tuple(max(0, min(255, c + brightness_offset)) for c in rgb)
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
    
    def update_quality_label(self, value):
        val = int(float(value))
        self.quality.set(str(val))
        
        if val <= 18:
            quality_text = f"{val} - Excellente"
            color = self.colors['success']
        elif val <= 23:
            quality_text = f"{val} - Recommandé"
            color = self.colors['accent']
        elif val <= 28:
            quality_text = f"{val} - Bonne"
            color = self.colors['warning']
        elif val <= 35:
            quality_text = f"{val} - Moyenne"
            color = self.colors['warning']
        else:
            quality_text = f"{val} - Faible"
            color = self.colors['danger']
        
        self.quality_label.config(text=quality_text, fg=color)
    
    def toggle_resolution(self):
        if self.custom_resolution.get():
            self.resolution_combo.config(state='readonly')
        else:
            self.resolution_combo.config(state='disabled')
    
    def update_file_stats(self):
        count = len(self.video_files)
        text = f"{count} fichier{'s' if count > 1 else ''}"
        self.files_stats.config(text=text)
    
    def add_videos(self):
        files = filedialog.askopenfilenames(
            title="Sélectionner des vidéos",
            filetypes=[
                ("Fichiers vidéo", "*.mp4 *.avi *.mkv *.mov *.wmv *.flv *.webm *.m4v *.mpg *.mpeg"),
                ("Tous les fichiers", "*.*")
            ]
        )
        
        for file in files:
            if file not in self.video_files:
                self.video_files.append(file)
                self.files_listbox.insert(tk.END, f"📹 {os.path.basename(file)}")
                self.log(f"✅ Ajouté: {os.path.basename(file)}", 'success')
        
        self.update_file_stats()
    
    def remove_selected(self):
        selection = self.files_listbox.curselection()
        if selection:
            index = selection[0]
            removed_file = self.video_files.pop(index)
            self.files_listbox.delete(index)
            self.log(f"⚠️ Retiré: {os.path.basename(removed_file)}", 'warning')
            self.update_file_stats()
    
    def clear_list(self):
        if self.video_files:
            self.video_files.clear()
            self.files_listbox.delete(0, tk.END)
            self.log("🗑️ Liste vidée", 'warning')
            self.update_file_stats()
    
    def browse_output(self):
        directory = filedialog.askdirectory(title="Sélectionner le dossier de sortie")
        if directory:
            self.output_directory.set(directory)
            self.log(f"📂 Dossier de sortie: {directory}", 'info')
    
    def log(self, message, tag=None):
        self.log_text.insert(tk.END, f"{message}\n", tag)
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_progress(self, value):
        self.progress_fill.place(relwidth=value/100)
        self.progress_percent.config(text=f"{int(value)}%")
        self.root.update_idletasks()
    
    def check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def get_video_info(self, input_file):
        try:
            cmd = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height,duration',
                '-of', 'json',
                input_file
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout)
            
            if info['streams']:
                stream = info['streams'][0]
                return {
                    'width': stream.get('width'),
                    'height': stream.get('height'),
                    'duration': float(stream.get('duration', 0))
                }
        except:
            pass
        return None
    
    def compress_video(self, input_file, output_file):
        cmd = ['ffmpeg', '-i', input_file, '-y']
        
        cmd.extend(['-c:v', self.codec.get()])
        cmd.extend(['-crf', self.quality.get()])
        cmd.extend(['-preset', self.preset.get()])
        
        if self.custom_resolution.get() and self.resolution.get():
            # Extraire juste la résolution (partie avant la parenthèse)
            resolution = self.resolution.get().split(' (')[0]
            cmd.extend(['-s', resolution])
        
        if self.keep_audio.get():
            cmd.extend(['-c:a', 'aac', '-b:a', '128k'])
        else:
            cmd.extend(['-an'])
        
        cmd.append(output_file)
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        for line in process.stderr:
            if 'time=' in line:
                self.root.update_idletasks()
        
        process.wait()
        return process.returncode == 0
    
    def start_compression(self):
        if not self.video_files:
            messagebox.showwarning("Attention", "Veuillez ajouter au moins une vidéo")
            return
        
        if not self.check_ffmpeg():
            messagebox.showerror(
                "Erreur", 
                "ffmpeg n'est pas installé ou accessible.\n"
                "Veuillez installer ffmpeg: https://ffmpeg.org/download.html"
            )
            return
        
        self.compress_btn.config(state='disabled', bg=self.colors['bg_tertiary'])
        
        thread = threading.Thread(target=self.compress_videos)
        thread.daemon = True
        thread.start()
    
    def compress_videos(self):
        total_files = len(self.video_files)
        
        for i, input_file in enumerate(self.video_files, 1):
            filename = os.path.basename(input_file)
            self.status_label.config(text=f"Compression {i}/{total_files}: {filename}")
            self.update_progress((i - 1) / total_files * 100)
            
            input_path = Path(input_file)
            
            if self.output_directory.get():
                output_dir = Path(self.output_directory.get())
            else:
                output_dir = input_path.parent
            
            output_name = input_path.stem + self.suffix_var.get() + input_path.suffix
            output_file = output_dir / output_name
            
            self.log(f"\n🎬 Compression de: {filename}")
            self.log(f"📍 Sortie: {output_file}", 'info')
            
            info = self.get_video_info(input_file)
            if info:
                self.log(f"📐 Résolution originale: {info['width']}x{info['height']}", 'info')
            
            success = self.compress_video(str(input_file), str(output_file))
            
            if success:
                original_size = os.path.getsize(input_file)
                compressed_size = os.path.getsize(output_file)
                reduction = (1 - compressed_size / original_size) * 100
                
                self.log(f"✅ Compression terminée!", 'success')
                self.log(f"📊 Réduction: {reduction:.1f}%", 'success')
                self.log(f"💾 Taille originale: {original_size / (1024*1024):.2f} MB", 'info')
                self.log(f"💾 Taille compressée: {compressed_size / (1024*1024):.2f} MB", 'info')
            else:
                self.log(f"❌ Erreur lors de la compression de {filename}", 'error')
            
            self.log("─" * 50, 'info')
            
            self.update_progress(i / total_files * 100)
        
        self.status_label.config(text="🎉 Compression terminée!")
        self.compress_btn.config(state='normal', bg=self.colors['success'])
        
        self.log(f"\n🏆 Terminé! {total_files} vidéo(s) compressée(s)", 'success')
        
        messagebox.showinfo("Terminé", f"Compression de {total_files} vidéo(s) terminée avec succès!")

def main():
    root = tk.Tk()
    
    # Configuration pour un meilleur rendu sur écrans haute résolution
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except:
        pass
    
    app = VideoCompressor(root)
    
    # Centrer la fenêtre
    root.update_idletasks()
    width = root.winfo_width()
    height = root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (width // 2)
    y = (root.winfo_screenheight() // 2) - (height // 2)
    root.geometry(f'{width}x{height}+{x}+{y}')
    
    root.mainloop()

if __name__ == "__main__":
    main()