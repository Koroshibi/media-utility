import os
import sys
import subprocess
from tqdm import tqdm
from pathlib import Path

# Liste des extensions audio supportées
SUPPORTED_EXT = (".m4a", ".opus", ".wav", ".flac", ".aac", ".ogg")

def find_audio_files(paths):
    """Retourne la liste de tous les fichiers audio trouvés dans les chemins donnés."""
    files = []
    for path in paths:
        p = Path(path)
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXT:
            files.append(p)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.suffix.lower() in SUPPORTED_EXT:
                    files.append(f)
    return files

def convert_file(input_path, output_path):
    """Convertit un fichier en mp3 avec ffmpeg."""
    subprocess.run([
        "ffmpeg", "-y", "-i", str(input_path),
        "-vn", "-codec:a", "libmp3lame", "-b:a", "192k",
        str(output_path)
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def main():
    if len(sys.argv) < 2:
        print("👉 Glisse et dépose tes fichiers ou dossiers sur ce script pour lancer la conversion.")
        input("Appuie sur Entrée pour quitter...")
        return

    input_paths = sys.argv[1:]
    files = find_audio_files(input_paths)

    if not files:
        print("Aucun fichier audio trouvé.")
        return

    # Crée un dossier de sortie
    output_folder = Path("converted_mp3")
    output_folder.mkdir(exist_ok=True)

    print(f"\n🎧 {len(files)} fichiers à convertir → {output_folder.resolve()}\n")

    # Conversion avec barre de progression
    for f in tqdm(files, desc="Conversion en cours", unit="fichier"):
        output_file = output_folder / (f.stem + ".mp3")
        convert_file(f, output_file)

    print("\n✅ Conversion terminée !")
    input("Appuie sur Entrée pour fermer...")

if __name__ == "__main__":
    main()
