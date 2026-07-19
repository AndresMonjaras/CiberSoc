import boto3
import configparser
import time
import os

ARCHIVO_CONFIGURACION_AWS = 'aws_details.txt'
NOMBRE_CUBO_S3 = "bucket-proyecto-big-data"
ARCHIVO_TRAFICO_LOCAL = "raw_traffic.csv"

# Encabezados estandar para analisis
COLUMNAS_CSV = [
    "IP Origen", "Puerto Destino", "Duracion Flujo", "Total Paquetes Adelante", 
    "Total Paquetes Atras", "Longitud Total Paquetes Adelante", "Longitud Total Paquetes Atras", "Etiqueta"
]
CABECERAS_CSV = ",".join(COLUMNAS_CSV) + "\n"

def cargar_credenciales_aws():
    # Carga credenciales desde archivo de configuracion
    configuracion = configparser.ConfigParser()
    try:
        configuracion.read(ARCHIVO_CONFIGURACION_AWS)
        return configuracion['default']['aws_access_key_id'], configuracion['default']['aws_secret_access_key'], configuracion['default']['aws_session_token']
    except Exception:
        print("Error al leer archivo de credenciales AWS")
        return None, None, None

def sincronizacion_aws_vivo():
    acceso_aws, secreto_aws, token_aws = cargar_credenciales_aws()
    if not acceso_aws: 
        print("No se encontraron credenciales. Saliendo.")
        return

    cliente_s3 = boto3.client(
        's3',
        aws_access_key_id=acceso_aws,
        aws_secret_access_key=secreto_aws,
        aws_session_token=token_aws,
        region_name='us-east-1'
    )

    print("Iniciando sincronizacion en vivo a AWS S3...")
    print("Subiendo lotes de datos... (Presiona CTRL+C para detener)")
    
    lotes_subidos = 0
    tiempo_ultimo_reporte = time.time()

    while True:
        try:
            # Verifica si el archivo tiene datos
            if os.path.exists(ARCHIVO_TRAFICO_LOCAL) and os.path.getsize(ARCHIVO_TRAFICO_LOCAL) > 0:
                with open(ARCHIVO_TRAFICO_LOCAL, 'r', encoding='utf-8') as archivo:
                    lineas = archivo.readlines()

                if len(lineas) > 1:
                    marca_tiempo_actual = int(time.time() * 1000)  
                    nombre_archivo_lote = f"lote_{marca_tiempo_actual}.csv"
                    ruta_s3 = f"trafico_red/{nombre_archivo_lote}"
                    
                    # Renombrar archivo para evitar conflictos
                    os.rename(ARCHIVO_TRAFICO_LOCAL, nombre_archivo_lote)
                    
                    # Insertar encabezados si faltan
                    with open(nombre_archivo_lote, 'r', encoding='utf-8') as archivo:
                        primera_linea = archivo.readline()
                        
                    if not primera_linea.startswith("IP Origen"):
                        with open(nombre_archivo_lote, 'r', encoding='utf-8') as archivo:
                            contenido = archivo.read()
                        with open(nombre_archivo_lote, 'w', encoding='utf-8') as archivo:
                            archivo.write(CABECERAS_CSV + contenido)

                    # Subida del archivo a S3
                    cliente_s3.upload_file(nombre_archivo_lote, NOMBRE_CUBO_S3, ruta_s3)
                    lotes_subidos += 1
                    
                    # Reporte de progreso cada 5 segundos
                    if time.time() - tiempo_ultimo_reporte >= 5:
                        print(f"Lotes subidos: {lotes_subidos} | Hora: {time.strftime('%H:%M:%S')}")
                        tiempo_ultimo_reporte = time.time()
            
            time.sleep(2)
            
        except FileNotFoundError:
            time.sleep(1)
        except PermissionError:
            time.sleep(0.5) 
        except Exception as error:
            print(f"Error en la transmision: {error}")
            time.sleep(3)

if __name__ == "__main__":
    sincronizacion_aws_vivo()