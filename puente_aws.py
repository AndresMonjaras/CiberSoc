import boto3
import configparser
import time
import os
from botocore.exceptions import NoCredentialsError

def cargar_credenciales():
    config = configparser.ConfigParser()
    try:
        config.read('aws_details.txt')
        return config['default']['aws_access_key_id'], config['default']['aws_secret_access_key'], config['default']['aws_session_token']
    except Exception:
        print("❌ Error leyendo aws_details.txt")
        return None, None, None

def observador_en_vivo():
    aws_access_key, aws_secret_key, aws_session_token = cargar_credenciales()
    if not aws_access_key: return

    BUCKET_NAME = "bucket-proyecto-big-data"
    ARCHIVO_LOCAL = "raw_traffic.csv"
    
    # 📌 ENCABEZADOS OFICIALES (CIC-IDS2017)
    COLUMNAS = [
        "Source IP", "Destination Port", "Flow Duration", "Total Fwd Packets", 
        "Total Backward Packets", "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Label"
    ]
    ENCABEZADOS = ",".join(COLUMNAS) + "\n"

    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        aws_session_token=aws_session_token,
        region_name='us-east-1'
    )

    print("📡 Iniciando enlace EN VIVO (Modo Micro-Batching)...")
    print("👀 Generando y subiendo lotes únicos a AWS S3... (CTRL+C para detener)")

    while True:
        try:
            # Si el archivo existe y tiene datos (más de 0 bytes)
            if os.path.exists(ARCHIVO_LOCAL) and os.path.getsize(ARCHIVO_LOCAL) > 0:
                
                # 1. Generamos un ID único basado en el tiempo exacto
                timestamp_actual = int(time.time())
                archivo_lote = f"batch_{timestamp_actual}.csv"
                ruta_s3 = f"trafico_red/{archivo_lote}"
                
                # 2. Secuestramos el archivo (lo renombramos). 
                # FastAPI creará uno nuevo automáticamente en la siguiente petición.
                os.rename(ARCHIVO_LOCAL, archivo_lote)
                
                # 3. Revisamos si tiene los encabezados, si no, se los inyectamos
                with open(archivo_lote, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                    
                if not contenido.startswith("Source IP,Destination Port"):
                    with open(archivo_lote, 'w', encoding='utf-8') as f:
                        f.write(ENCABEZADOS + contenido)
                        print("🔧 Encabezados inyectados automáticamente.")

                # 4. Subimos el lote a la nube
                print(f"🔄 Subiendo nuevo lote: {archivo_lote}...")
                s3.upload_file(archivo_lote, BUCKET_NAME, ruta_s3)
                print(f"✅ ¡Lote {archivo_lote} guardado en el Data Lake!")
                
                # 5. Eliminamos el lote local para mantener limpio tu Windows
                os.remove(archivo_lote)
            
            # Esperamos 10 segundos antes de generar el siguiente lote
            time.sleep(10)
            
        except FileNotFoundError:
            # Pasa si el servidor aún no recibe tráfico
            time.sleep(2)
        except PermissionError:
            # Pasa si justo en ese milisegundo FastAPI estaba escribiendo en el archivo. 
            # No pasa nada, lo intentará de nuevo en 10 segundos.
            pass
        except Exception as e:
            print(f"❌ Error en la transmisión: {e}")
            time.sleep(5)

if __name__ == "__main__":
    observador_en_vivo()