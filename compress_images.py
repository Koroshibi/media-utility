import sys
import os
import subprocess

def compress_image(input_path, output_path):
    # Vérifier si ImageMagick est disponible
    magick_available = False
    
    try:
        # Vérifier si la commande magick est disponible
        subprocess.run(['magick', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        magick_available = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("ImageMagick n'est pas installé. Tentative d'installation...")
        try:
            # Essayer d'installer ImageMagick avec winget
            subprocess.run(["winget", "install", "ImageMagick.ImageMagick"], check=True)
            print("ImageMagick a été installé avec succès.")
            magick_available = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Impossible d'installer ImageMagick. Vérifiez que winget est disponible ou installez ImageMagick manuellement.")
            print("Téléchargement: https://imagemagick.org/script/download.php")
            return False
    
    if magick_available:
        # Utiliser ImageMagick pour la conversion (gère parfaitement la transparence)
        try:
            command = [
                'magick', 'convert',
                input_path,
                '-resize', '100%',
                '-quality', str(50),  # ImageMagick utilise une échelle 1-100
                '-background', 'white',
                '-flatten',  # Aplatit les couches avec fond blanc
                output_path
            ]
            subprocess.run(command, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Erreur lors de l'utilisation d'ImageMagick: {e}")
            print(f"Impossible de convertir l'image {input_path}.")
            return False
    
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: drag and drop image files onto this script.")
        sys.exit(1)

    # The first argument is the script name, so we skip it
    input_files = sys.argv[1:]

    for input_path in input_files:
        if not os.path.isfile(input_path):
            print(f"File not found: {input_path}")
            continue
        
        file_name, file_ext = os.path.splitext(input_path)
        output_path = f"{file_name}_compressed{file_ext}"
        
        try:
            compress_image(input_path, output_path)
            print(f"Compressed {input_path} -> {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to compress {input_path}: {e}")

if __name__ == "__main__":
    main()
