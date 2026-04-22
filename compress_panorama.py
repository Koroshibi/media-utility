import sys
import os
import subprocess

def compress_and_convert_image(input_path, output_path, quality=2):
    # Redimensionner l'image en un ratio 2:1
    command = [
        'ffmpeg', '-i', input_path,
        '-vf', 'scale=2*ih:ih,setsar=1',
        '-q:v', str(quality),
        output_path
    ]
    subprocess.run(command, check=True)

def main():
    if len(sys.argv) < 2:
        print("Usage: drag and drop image files onto this script.")
        sys.exit(1)

    # Le premier argument est le nom du script, on le saute
    input_files = sys.argv[1:]

    for input_path in input_files:
        if not os.path.isfile(input_path):
            print(f"File not found: {input_path}")
            continue
        
        file_name, _ = os.path.splitext(input_path)
        output_path = f"{file_name}_compressed.jpg"
        
        try:
            compress_and_convert_image(input_path, output_path)
            print(f"Compressed and converted {input_path} -> {output_path}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to compress and convert {input_path}: {e}")

if __name__ == "__main__":
    main()
