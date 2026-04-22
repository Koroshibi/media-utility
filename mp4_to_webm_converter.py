#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convertisseur MP4 vers WebM par glisser-déposer avec barre de progression et support alpha
Utilise FFmpeg pour la conversion avec détection automatique du canal alpha
Usage: Glissez-déposez un fichier .mp4 sur ce script ou utilisez:
python convert_mp4_to_webm.py fichier.mp4
"""

import sys
import os
import subprocess
import re
import threading
import time
import json
from pathlib import Path

class ProgressBar:
    """Barre de progression en console"""
    
    def __init__(self, width=50):
        self.width = width
        self.current = 0
        
    def update(self, progress, status=""):
        """Met à jour la barre de progression
        Args:
            progress: pourcentage (0-100)
            status: texte de statut optionnel
        """
        self.current = min(100, max(0, progress))
        filled = int(self.width * self.current / 100)
        bar = '█' * filled + '░' * (self.width - filled)
        
        # Effacer la ligne précédente et afficher la nouvelle
        print(f'\r⏳ [{bar}] {self.current:6.2f}% {status}', end='', flush=True)
        
        if self.current >= 100:
            print()  # Nouvelle ligne à la fin

def get_video_info(file_path):
    """Récupère les informations détaillées de la vidéo"""
    try:
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', str(file_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        
        video_stream = None
        duration = None
        
        # Récupérer les infos de la première stream vidéo
        for stream in info.get('streams', []):
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        # Durée depuis le format ou la stream vidéo
        if 'format' in info and 'duration' in info['format']:
            duration = float(info['format']['duration'])
        elif video_stream and 'duration' in video_stream:
            duration = float(video_stream['duration'])
        
        return {
            'duration': duration,
            'video_stream': video_stream,
            'has_alpha': has_alpha_channel(video_stream) if video_stream else False
        }
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError, json.JSONDecodeError):
        return {'duration': None, 'video_stream': None, 'has_alpha': False}

def has_alpha_channel(video_stream):
    """Détermine si la vidéo a un canal alpha"""
    if not video_stream:
        return False
    
    # Vérifier le format de pixel
    pix_fmt = video_stream.get('pix_fmt', '')
    
    # Formats de pixels avec canal alpha
    alpha_formats = [
        'yuva420p', 'yuva422p', 'yuva444p',
        'rgba', 'argb', 'abgr', 'bgra',
        'yuva420p10le', 'yuva422p10le', 'yuva444p10le',
        'yuva420p12le', 'yuva422p12le', 'yuva444p12le',
        'yuva420p16le', 'yuva422p16le', 'yuva444p16le'
    ]
    
    has_alpha = pix_fmt in alpha_formats
    
    # Informations supplémentaires pour debug
    if has_alpha:
        print(f"🎭 Canal alpha détecté (format: {pix_fmt})")
    
    return has_alpha

def parse_ffmpeg_progress(line, total_duration):
    """Parse une ligne de sortie FFmpeg pour extraire le progrès"""
    # Rechercher le temps actuel (plusieurs formats possibles)
    time_patterns = [
        r'time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})',  # time=00:01:23.45
        r'time=(\d{2}):(\d{2}):(\d{2})',           # time=00:01:23
        r'out_time_ms=(\d+)',                      # out_time_ms=123456789
        r'out_time=(\d{2}):(\d{2}):(\d{2})\.(\d+)' # out_time=00:01:23.456
    ]
    
    for pattern in time_patterns:
        time_match = re.search(pattern, line)
        if time_match and total_duration:
            if 'out_time_ms' in pattern:
                # Temps en microsecondes
                current_time = int(time_match.group(1)) / 1000000
            else:
                # Format hh:mm:ss[.xxx]
                hours = int(time_match.group(1))
                minutes = int(time_match.group(2))
                seconds = int(time_match.group(3))
                if time_match.lastindex >= 4:
                    fractional = float('0.' + time_match.group(4))
                else:
                    fractional = 0
                current_time = hours * 3600 + minutes * 60 + seconds + fractional
            
            progress = (current_time / total_duration) * 100
            return min(100, progress)
    
    return None

def check_ffmpeg():
    """Vérifie si FFmpeg et FFprobe sont installés"""
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def build_ffmpeg_command(input_file, output_file, quality, has_alpha):
    """Construit la commande FFmpeg selon la présence d'un canal alpha"""
    
    base_cmd = [
        'ffmpeg',
        '-i', str(input_file),
    ]
    
    if has_alpha:
        # Configuration pour vidéos avec canal alpha
        video_params = [
            '-c:v', 'libvpx-vp9',      # Codec VP9 (supporte alpha)
            '-pix_fmt', 'yuva420p',    # Format pixel avec canal alpha
            '-crf', str(quality),      # Qualité
            '-b:v', '0',               # Bitrate variable
            '-auto-alt-ref', '0',      # Désactiver alt-ref pour alpha
        ]
        print(f"🎭 Mode alpha activé - Conservation de la transparence")
    else:
        # Configuration standard sans canal alpha
        video_params = [
            '-c:v', 'libvpx-vp9',      # Codec VP9
            '-pix_fmt', 'yuv420p',     # Format pixel standard
            '-crf', str(quality),      # Qualité
            '-b:v', '0',               # Bitrate variable
        ]
        print(f"🎥 Mode standard - Pas de canal alpha détecté")
    
    # Paramètres audio
    audio_params = [
        '-c:a', 'libopus',
        '-b:a', '128k',
    ]
    
    # Paramètres de sortie avec progression sur stderr
    output_params = [
        '-progress', '-',           # Sortie sur stderr
        '-nostats',                 # Pas de stats par défaut
        '-y',
        str(output_file)
    ]
    
    return base_cmd + video_params + audio_params + output_params

def convert_mp4_to_webm(input_path, quality='30'):
    """
    Convertit un fichier MP4 en WebM avec barre de progression et support alpha
    
    Args:
        input_path: Chemin vers le fichier MP4
        quality: Qualité de la conversion (0-63, plus bas = meilleure qualité)
    """
    input_file = Path(input_path)
    
    # Vérifications de base
    if not input_file.exists():
        print(f"❌ Erreur : Le fichier '{input_file}' n'existe pas.")
        return False
    
    if input_file.suffix.lower() != '.mp4':
        print(f"❌ Erreur : Le fichier doit être un .mp4 (reçu: {input_file.suffix})")
        return False
    
    output_file = input_file.with_suffix('.webm')
    
    print(f"🎬 Conversion de '{input_file.name}' vers '{output_file.name}'...")
    print(f"📁 Dossier de sortie : {output_file.parent}")
    
    # Analyser le fichier vidéo
    print("📊 Analyse du fichier vidéo...")
    video_info = get_video_info(input_file)
    
    if video_info['duration']:
        duration_str = f"{int(video_info['duration']//60):02d}:{int(video_info['duration']%60):02d}"
        print(f"⏱️  Durée de la vidéo : {duration_str}")
    else:
        print("⚠️  Impossible de déterminer la durée (progression approximative)")
    
    # Afficher les infos sur le canal alpha
    if video_info['has_alpha']:
        pix_fmt = video_info['video_stream'].get('pix_fmt', 'inconnu')
        print(f"✨ Canal alpha détecté - Format: {pix_fmt}")
        print("   → La transparence sera conservée dans le WebM")
    else:
        print("🎥 Aucun canal alpha détecté - Conversion standard")
    
    # Construire la commande FFmpeg
    cmd = build_ffmpeg_command(input_file, output_file, quality, video_info['has_alpha'])
    
    try:
        print("\n🚀 Démarrage de la conversion...")
        
        # Lancer FFmpeg
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,  # Rediriger stderr vers stdout
            universal_newlines=True,
            bufsize=1
        )
        
        # Initialiser la barre de progression
        progress_bar = ProgressBar(width=40)
        last_progress = 0
        start_time = time.time()
        
        # Variables pour gérer l'affichage
        last_output_time = time.time()
        fallback_progress = 0
        
        # Lire la sortie en temps réel
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
                
            if output:
                line = output.strip()
                
                # Parser le progrès depuis la sortie FFmpeg
                progress = parse_ffmpeg_progress(line, video_info['duration'])
                
                if progress is not None and progress > last_progress:
                    last_progress = progress
                    last_output_time = time.time()
                    
                    # Calculer le temps restant estimé
                    elapsed_time = time.time() - start_time
                    if progress > 0 and elapsed_time > 0:
                        estimated_total = elapsed_time * (100 / progress)
                        remaining = max(0, estimated_total - elapsed_time)
                        remaining_str = f"(~{int(remaining//60):02d}:{int(remaining%60):02d} restant)"
                    else:
                        remaining_str = ""
                    
                    progress_bar.update(progress, remaining_str)
                
                # Système de fallback si pas de progression détectée
                elif time.time() - last_output_time > 2:  # 2 secondes sans mise à jour
                    fallback_progress = min(99, fallback_progress + 1)
                    elapsed_time = time.time() - start_time
                    progress_bar.update(fallback_progress, f"({int(elapsed_time)}s écoulées)")
                    last_output_time = time.time()
        
        # Attendre la fin du processus
        process.wait()
        
        # Finaliser la barre de progression
        progress_bar.update(100, "Finalisation...")
        
        # Vérifier le résultat
        if process.returncode == 0 and output_file.exists():
            input_size = input_file.stat().st_size
            output_size = output_file.stat().st_size
            compression_ratio = (1 - output_size / input_size) * 100
            
            print(f"\n✅ Conversion terminée avec succès !")
            print(f"📄 Fichier original : {input_size / (1024*1024):.1f} MB")
            print(f"📄 Fichier converti : {output_size / (1024*1024):.1f} MB")
            print(f"📉 Compression : {compression_ratio:.1f}%")
            
            if video_info['has_alpha']:
                print(f"🎭 Canal alpha : Conservé dans le fichier WebM")
            
            print(f"💾 Fichier sauvegardé : {output_file}")
            return True
        else:
            print(f"\n❌ Erreur lors de la conversion (code: {process.returncode})")
            return False
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Conversion interrompue par l'utilisateur.")
        if process:
            process.terminate()
        return False
        
    except Exception as e:
        print(f"\n❌ Erreur inattendue : {e}")
        return False

def show_help():
    """Affiche l'aide du script"""
    help_text = """
🎬 Convertisseur MP4 vers WebM avec support alpha et barre de progression

UTILISATION:
  • Glisser-déposer : Glissez un fichier .mp4 sur ce script
  • Ligne de commande : python convert_mp4_to_webm.py fichier.mp4 [qualité]

PARAMÈTRES:
  fichier.mp4    Fichier MP4 à convertir
  qualité        Qualité de 0 à 63 (optionnel, défaut: 30)
                 0 = meilleure qualité, 63 = plus petite taille

EXEMPLES:
  python convert_mp4_to_webm.py video.mp4
  python convert_mp4_to_webm.py video_alpha.mp4 20    # Avec transparence
  python convert_mp4_to_webm.py video.mp4 40         # Plus compressé

FONCTIONNALITÉS:
  • Détection automatique du canal alpha (transparence)
  • Barre de progression en temps réel
  • Estimation du temps restant
  • Conservation de la transparence pour les vidéos avec canal alpha
  • Statistiques de compression
  • Interruption possible avec Ctrl+C

FORMATS ALPHA SUPPORTÉS:
  • yuva420p, yuva422p, yuva444p (plus courants)
  • rgba, argb, abgr, bgra
  • Versions 10/12/16 bits des formats yuva

PRÉREQUIS:
  FFmpeg et FFprobe doivent être installés et accessibles dans le PATH
  Windows: https://ffmpeg.org/download.html
  Mac: brew install ffmpeg
  Linux: sudo apt install ffmpeg
"""
    print(help_text)

def main():
    """Fonction principale"""
    
    # Vérifier FFmpeg
    if not check_ffmpeg():
        print("❌ Erreur : FFmpeg/FFprobe n'est pas installé ou n'est pas dans le PATH.")
        print("📥 Veuillez installer FFmpeg :")
        print("   • Windows : https://ffmpeg.org/download.html")
        print("   • Mac : brew install ffmpeg") 
        print("   • Linux : sudo apt install ffmpeg")
        input("\nAppuyez sur Entrée pour quitter...")
        sys.exit(1)
    
    # Gestion des arguments
    if len(sys.argv) == 1:
        print("❌ Aucun fichier spécifié.")
        show_help()
        input("\nAppuyez sur Entrée pour quitter...")
        sys.exit(1)
    
    if sys.argv[1] in ['-h', '--help', 'help']:
        show_help()
        sys.exit(0)
    
    # Récupérer le fichier et la qualité
    input_file = sys.argv[1]
    quality = sys.argv[2] if len(sys.argv) > 2 else '30'
    
    # Valider la qualité
    try:
        quality_int = int(quality)
        if not (0 <= quality_int <= 63):
            print("❌ Erreur : La qualité doit être entre 0 et 63.")
            sys.exit(1)
    except ValueError:
        print("❌ Erreur : La qualité doit être un nombre.")
        sys.exit(1)
    
    # Convertir
    print("=" * 70)
    start_time = time.time()
    success = convert_mp4_to_webm(input_file, quality)
    total_time = time.time() - start_time
    
    print("=" * 70)
    if success:
        print(f"🎉 Conversion terminée en {int(total_time//60):02d}:{int(total_time%60):02d} !")
    else:
        print("💥 La conversion a échoué.")
    
    print("\n💡 Conseils :")
    print("   • Appuyez sur Ctrl+C pour interrompre une conversion")
    print("   • Les vidéos avec canal alpha conservent leur transparence")
    input("\nAppuyez sur Entrée pour quitter...")
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
