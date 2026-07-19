# INSTALACIÓN Y PREPARACIÓN
!apt-get update -qq
!apt-get install openjdk-11-jre-headless -qq > /dev/null
!pip install pyspark boto3 joblib -q

import os
from google.colab import userdata
from pyspark.sql import SparkSession

print("Dependencias instaladas. Creando sesión de Spark...")

# Creación de la sesión de PySpark.
spark = SparkSession.builder \
    .appName("Security_Pipeline_Auto") \
    .master("local[*]") \
    .config("spark.driver.memory", "4g") \
    .getOrCreate()

print("Sesión de PySpark iniciada")

# CONEXIÓN Y GESTOR DE ESTADO DE AWS S3
import boto3
import time

NOMBRE_BUCKET = 'bucket-proyecto-big-data'

credenciales_raw = """
[default]
aws_access_key_id=<KEY>
aws_secret_access_key=<KEY>
aws_session_token=<KEY>
"""

aws_access_key = ""
aws_secret_key = ""
aws_session_token = ""

for linea in credenciales_raw.strip().split('\n'):
    if linea.startswith('aws_access_key_id='): aws_access_key = linea.split('=', 1)[1].strip()
    elif linea.startswith('aws_secret_access_key='): aws_secret_key = linea.split('=', 1)[1].strip()
    elif linea.startswith('aws_session_token='): aws_session_token = linea.split('=', 1)[1].strip()

# iniciar cliente S3
s3_client = boto3.client(
    's3', aws_access_key_id=aws_access_key,
    aws_secret_access_key=aws_secret_key,
    aws_session_token=aws_session_token, region_name='us-east-1'
)
print("Conectado a AWS S3")

# Funcion para archivar en el bucket
def archivar_en_s3(ruta_original):
    nombre_archivo = ruta_original.split('/')[-1]
    ruta_archivada = f"trafico_red/archivados/{nombre_archivo}"
    s3_client.copy_object(Bucket=NOMBRE_BUCKET, CopySource=f"{NOMBRE_BUCKET}/{ruta_original}", Key=ruta_archivada)
    s3_client.delete_object(Bucket=NOMBRE_BUCKET, Key=ruta_original)

# Buscar archivos csv que no hayan sido procesados
def obtener_pendientes_servidor():
    respuesta = s3_client.list_objects_v2(Bucket=NOMBRE_BUCKET, Prefix='trafico_red/')
    pendientes = []
    if 'Contents' in respuesta:
        for obj in respuesta['Contents']:
            if obj['Key'].endswith('.csv') and 'archivados' not in obj['Key']:
                pendientes.append((obj['Key'], obj['LastModified']))
    pendientes.sort(key=lambda x: x[1])
    return [p[0] for p in pendientes]

# Revisar si la IA ya esta entrenada
def verificar_datos_estaticos_procesados():
    respuesta = s3_client.list_objects_v2(Bucket=NOMBRE_BUCKET, Prefix='modelos/modelo_rf.pkl')
    return 'Contents' in respuesta


# PIPELINE DE TRANSFORMACIÓN, IA Y DEFENSA
import pandas as pd
import joblib
import requests
from pyspark.sql.functions import col, split, explode, lit, expr
from pyspark.sql.types import DoubleType
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta

os.makedirs('/content/temp', exist_ok=True)
os.makedirs('/content/servidores', exist_ok=True)
os.makedirs('/content/modelos', exist_ok=True)

# Descargar archivos del S3 al colab
def descargar_lista_s3(lista_rutas_s3, carpeta_local):
    archivos_locales = []
    for ruta in lista_rutas_s3:
        nombre = ruta.split('/')[-1]
        ruta_local = os.path.join(carpeta_local, nombre)
        s3_client.download_file(NOMBRE_BUCKET, ruta, ruta_local)
        archivos_locales.append(ruta_local)
    return archivos_locales

# ETL
def ejecutar_etl_y_guardar(archivos_trafico, sufijo_batch):
    print(f"ETL: Procesando {len(archivos_trafico)} archivos con PySpark...")
    es_historico = (sufijo_batch == "historico_base")

    # ignorar filas corruptas en la lectura
    df_trafico = spark.read.option("mode", "DROPMALFORMED").csv(archivos_trafico, header=True, inferSchema=False)

    # Limpiar espacios vacios
    df_trafico = df_trafico.toDF(*[c.strip() for c in df_trafico.columns])

    # Si faltan IPs o la etiqueta, se rellenan como desconocidos
    if "Source IP" not in df_trafico.columns: df_trafico = df_trafico.withColumn("Source IP", lit("Desconocida"))
    if "Destination IP" not in df_trafico.columns: df_trafico = df_trafico.withColumn("Destination IP", lit("Desconocida"))
    if "Label" not in df_trafico.columns: df_trafico = df_trafico.withColumn("Label", lit("DESCONOCIDO"))

    # Lista metricas que usará el modelo
    columnas_clave = [
        "Source IP", "Destination IP", "Destination Port", "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
        "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Fwd Packet Length Max",
        "Fwd Packet Length Min", "Fwd Packet Length Mean", "Bwd Packet Length Max",
        "Bwd Packet Length Min", "Bwd Packet Length Mean", "Flow IAT Mean", "Flow IAT Std",
        "ACK Flag Count", "SYN Flag Count", "Init_Win_bytes_forward", "Label"
    ]

    # Convertir columnas numericas de string a Double
    for col_str in ["Total Fwd Packets", "Total Backward Packets", "Flow Duration",
                     "Total Length of Fwd Packets", "Total Length of Bwd Packets"]:
        if col_str in df_trafico.columns:
            df_trafico = df_trafico.withColumn(col_str, expr(f"try_cast(`{col_str}` AS DOUBLE)"))

  # Valores típicos de un usuario normal navegando
    valores_humanos = {
        "Fwd Packet Length Max": 120.0, "Fwd Packet Length Min": 0.0, "Fwd Packet Length Mean": 45.0,
        "Bwd Packet Length Max": 1500.0, "Bwd Packet Length Min": 0.0, "Bwd Packet Length Mean": 800.0,
        "Flow IAT Mean": 50000.0, "Flow IAT Std": 1000.0, "ACK Flag Count": 1.0, "SYN Flag Count": 0.0,
        "Init_Win_bytes_forward": 8192.0
    }

    # Valores típicos de un bot haciendo DDoS (rápido, corto)
    valores_ataque = {
        "Fwd Packet Length Max": 1500.0, "Fwd Packet Length Min": 0.0, "Fwd Packet Length Mean": 800.0,
        "Bwd Packet Length Max": 0.0, "Bwd Packet Length Min": 0.0, "Bwd Packet Length Mean": 0.0,
        "Flow IAT Mean": 100.0,   # Tiempos ridículamente rápidos (típico de DDoS)
        "Flow IAT Std": 5000.0,   # Alta variabilidad (inundación)
        "ACK Flag Count": 0.0,    # El atacante no confirma nada
        "SYN Flag Count": 1.0,    # Solo manda SYN, nunca completa handshake
        "Init_Win_bytes_forward": 256.0  # Ventana TCP minúscula
    }

    # Rellenamos las columnas faltantes
    for c in columnas_clave:
        if c not in df_trafico.columns:
            # Si hay datos de paquetes y tiempo, inferimos si es ataque o no.
            if "Total Fwd Packets" in df_trafico.columns and "Flow Duration" in df_trafico.columns:
                df_trafico = df_trafico.withColumn(
                    c,
                    expr(f"""
                        CASE
                            WHEN `Total Fwd Packets` > 120
                             AND `Flow Duration` < 15000000
                            THEN {valores_ataque.get(c, 0.0)}
                            ELSE {valores_humanos.get(c, 0.0)}
                        END
                    """).cast(DoubleType())
                )
            else:
                valor_relleno = valores_humanos.get(c, 0.0)
                df_trafico = df_trafico.withColumn(c, lit(valor_relleno).cast(DoubleType()))

    # Selección final y casteo a numérico (excepto IPs y Labels)
    df_limpio = df_trafico.select([
        col(c).cast(DoubleType()) if c not in ["Label", "Source IP", "Destination IP"]
        else col(c) for c in columnas_clave
    ])

    df_limpio = df_limpio.dropna()
    df_master = df_limpio

    if es_historico:
        df_master = df_master.orderBy(expr("rand()")).limit(100000)
    else:
        conteo_filas = df_master.count()
        if conteo_filas > 100000:
            print(f"Límite de seguridad activado: Reduciendo lote de {conteo_filas} a 100,000 registros para proteger la RAM...")
            df_master = df_master.limit(100000)


    ruta_local_temp = f'/content/temp/preparados_{sufijo_batch}.csv'
    ruta_s3_inferencia = f'inferencia/datos_preparados_{sufijo_batch}.csv'

    print("Convirtiendo a formato Pandas de forma segura...")
    df_master.toPandas().to_csv(ruta_local_temp, index=False)
    s3_client.upload_file(ruta_local_temp, NOMBRE_BUCKET, ruta_s3_inferencia)
    os.remove(ruta_local_temp)
    return ruta_s3_inferencia



def ejecutar_ia(ruta_s3_inferencia, es_entrenamiento_estatico, sufijo_batch, modo_aprendizaje_continuo=False):
    print("Iniciando análisis de Inteligencia Artificial...")
    ruta_local_descarga = f'/content/temp/descarga_inferencia_{sufijo_batch}.csv'
    s3_client.download_file(NOMBRE_BUCKET, ruta_s3_inferencia, ruta_local_descarga)
    df = pd.read_csv(ruta_local_descarga)

    if df.empty:
        print(f"El lote {sufijo_batch} está vacío. Saltando...")
        os.remove(ruta_local_descarga)
        s3_client.delete_object(Bucket=NOMBRE_BUCKET, Key=ruta_s3_inferencia)
        return

    features = [
        "Destination Port", "Flow Duration", "Total Fwd Packets", "Total Backward Packets",
        "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Fwd Packet Length Max",
        "Fwd Packet Length Min", "Fwd Packet Length Mean", "Bwd Packet Length Max",
        "Bwd Packet Length Min", "Bwd Packet Length Mean", "Flow IAT Mean", "Flow IAT Std",
        "ACK Flag Count", "SYN Flag Count", "Init_Win_bytes_forward"
    ]
    X = df[features].fillna(0)
    scaler = StandardScaler()

    if es_entrenamiento_estatico:
        print("IA: Entrenando SUPER MODELO MULTICLASE desde cero...")
        df['Label'] = df['Label'].astype(str).str.strip()
        X_scaled = scaler.fit_transform(X)
        modelo_rf = RandomForestClassifier(n_estimators=50, random_state=42, n_jobs=-1)
        modelo_rf.fit(X_scaled, df['Label'])
        joblib.dump(modelo_rf, '/content/modelos/modelo_rf.pkl')
        joblib.dump(scaler, '/content/modelos/scaler.pkl')
        s3_client.upload_file('/content/modelos/modelo_rf.pkl', NOMBRE_BUCKET, 'modelos/modelo_rf.pkl')
        s3_client.upload_file('/content/modelos/scaler.pkl', NOMBRE_BUCKET, 'modelos/scaler.pkl')
        df['Prediccion_IA'] = modelo_rf.predict(X_scaled)
    else:
        print("IA: Cargando 'Cerebro' almacenado...")
        if not os.path.exists('/content/modelos/modelo_rf.pkl'):
            s3_client.download_file(NOMBRE_BUCKET, 'modelos/modelo_rf.pkl', '/content/modelos/modelo_rf.pkl')
            s3_client.download_file(NOMBRE_BUCKET, 'modelos/scaler.pkl', '/content/modelos/scaler.pkl')

        modelo_rf = joblib.load('/content/modelos/modelo_rf.pkl')
        scaler_guardado = joblib.load('/content/modelos/scaler.pkl')

        print("Modo Producción: Realizando inferencia pura...")
        X_scaled_new = scaler_guardado.transform(X)
        df['Prediccion_IA'] = modelo_rf.predict(X_scaled_new)
        print(f"Veredicto de la IA: {df['Prediccion_IA'].value_counts().to_dict()}")

        # === ABUSEIPDB ===
        ataques_detectados = df[df['Prediccion_IA'] != 'BENIGN']
        if not ataques_detectados.empty:
            conteo_ips = ataques_detectados['Source IP'].value_counts().reset_index()
            conteo_ips.columns = ['Source IP', 'Count']
            top_ips = conteo_ips[conteo_ips['Source IP'] != 'Desconocida'].head(5)['Source IP']

            if len(top_ips) > 0:
                print(f"{len(conteo_ips)} IPs maliciosas únicas detectadas.")
                print(f"Consultando AbuseIPDB SOLO para el TOP {len(top_ips)} de IPs más agresivas...")

                ABUSEIPDB_API_KEY = "95e15ed18c868ef4242c2c2498b3559e6a974170fec638e07bb1a77b21d1fdb8c55dfb5154b77aff"
                URL_API = "https://api.abuseipdb.com/api/v2/check"
                headers = {'Accept': 'application/json', 'Key': ABUSEIPDB_API_KEY}
                lista_antecedentes = []

                for ip in top_ips:
                    score = 0
                    try:
                        if not (ip.startswith("192.168.") or ip.startswith("172.") or ip.startswith("10.")):
                            res = requests.get(URL_API, headers=headers, params={'ipAddress': ip, 'maxAgeInDays': '90'}, timeout=3)
                            if res.status_code == 200:
                                score = res.json()['data']['abuseConfidenceScore']
                    except Exception:
                        pass

                    fecha_expiracion = (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
                    lista_antecedentes.append({"ip_origen": ip, "score_abuso": score, "expiracion_bloqueo": fecha_expiracion})

                if lista_antecedentes:
                    df_bloqueo = pd.DataFrame(lista_antecedentes)
                    ruta_bloqueo = '/content/temp/ips_bloqueadas.csv'
                    df_bloqueo.to_csv(ruta_bloqueo, index=False)
                    ruta_antecedentes_s3 = 'antecedentes/ips_bloqueadas.csv'
                    s3_client.upload_file(ruta_bloqueo, NOMBRE_BUCKET, ruta_antecedentes_s3)
                    print(f"¡ALERTA! Lista negra actualizada en s3://{NOMBRE_BUCKET}/{ruta_antecedentes_s3}")
                    if os.path.exists(ruta_bloqueo): os.remove(ruta_bloqueo)


    df['Fecha_Hora_Ataque'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')


    mapa_departamentos = {
        '192.168.1.10': 'Finanzas', '192.168.1.11': 'Finanzas',
        '192.168.1.12': 'Recursos Humanos', '192.168.1.13': 'Ventas',
        '192.168.1.14': 'TI', '192.168.1.15': 'TI',
        '192.168.1.16': 'TI', '192.168.1.17': 'TI',
        '192.168.1.18': 'TI', '192.168.1.19': 'TI',
        '192.168.1.20': 'Operaciones', '192.168.1.21': 'Logistica',
        '192.168.1.22': 'Finanzas', '192.168.1.23': 'TI',
        '192.168.1.24': 'TI', '192.168.1.25': 'TI',
        '192.168.1.26': 'TI', '192.168.1.27': 'TI',
        '192.168.1.28': 'Finanzas', '192.168.1.29': 'TI',
        '192.168.1.30': 'Seguridad', '192.168.1.31': 'Administracion',
        '192.168.1.32': 'TI', '192.168.1.33': 'TI',
        '192.168.1.34': 'TI'
    }

    mapa_servidores = {
        '192.168.1.10': 'Servidor de Pagos', '192.168.1.11': 'Servidor ERP',
        '192.168.1.12': 'Servidor Nomina', '192.168.1.13': 'Servidor CRM',
        '192.168.1.14': 'Servidor Web Principal', '192.168.1.15': 'Servidor Web Secundario',
        '192.168.1.16': 'Servidor Base de Datos', '192.168.1.17': 'Servidor Backup',
        '192.168.1.18': 'Servidor DNS Interno', '192.168.1.19': 'Servidor DHCP',
        '192.168.1.20': 'Servidor Archivos', '192.168.1.21': 'Servidor Inventario',
        '192.168.1.22': 'Servidor Facturacion', '192.168.1.23': 'Servidor Correo',
        '192.168.1.24': 'Servidor VPN', '192.168.1.25': 'Servidor Desarrollo',
        '192.168.1.26': 'Servidor Pruebas QA', '192.168.1.27': 'Servidor Monitoreo',
        '192.168.1.28': 'Servidor BI', '192.168.1.29': 'Servidor Seguridad',
        '192.168.1.30': 'Servidor Control Accesos', '192.168.1.31': 'Servidor Documentos',
        '192.168.1.32': 'Servidor Aplicaciones Internas', '192.168.1.33': 'Servidor API',
        '192.168.1.34': 'Servidor Logs'
    }

    df['Departamento'] = df['Destination IP'].map(mapa_departamentos).fillna('Desconocido')
    df['Nombre_Servidor'] = df['Destination IP'].map(mapa_servidores).fillna('Desconocido')

    # Columnas obligatorias
    columnas_exportar = ['Fecha_Hora_Ataque', 'Prediccion_IA', 'Departamento', 'Source IP']

    # Columnas opcionales (se exportan si existen en el DataFrame)
    columnas_opcionales = [
        'Nombre_Servidor',
        'Destination IP', 'Destination Port', 'Flow Duration',
        'Total Fwd Packets', 'Total Backward Packets',
        'Total Length of Fwd Packets', 'Total Length of Bwd Packets',
        'Fwd Packet Length Max', 'Fwd Packet Length Min', 'Fwd Packet Length Mean',
        'Bwd Packet Length Max', 'Bwd Packet Length Min', 'Bwd Packet Length Mean',
        'Flow IAT Mean', 'Flow IAT Std', 'ACK Flag Count', 'SYN Flag Count',
        'Init_Win_bytes_forward', 'Label'
    ]

    for col in columnas_opcionales:
        if col in df.columns and col not in columnas_exportar:
            columnas_exportar.append(col)

    # Exportamos
    df_export = df[columnas_exportar]

    ruta_procesado_local = f'/content/temp/procesados_temp_{sufijo_batch}.csv'
    df_export.to_csv(ruta_procesado_local, index=False)
    s3_client.upload_file(ruta_procesado_local, NOMBRE_BUCKET, f'procesados/datos_analizados_{sufijo_batch}.csv')
    print(f"Análisis guardado en procesados/datos_analizados_{sufijo_batch}.csv")

    os.remove(ruta_local_descarga)
    os.remove(ruta_procesado_local)
    s3_client.delete_object(Bucket=NOMBRE_BUCKET, Key=ruta_s3_inferencia)

print("Iniciando Sistema...")

if not verificar_datos_estaticos_procesados():
    print("Datos históricos no procesados. Iniciando fase de entrenamiento...")
    print("Buscando archivos en s3://bucket-proyecto-big-data/entrenamiento/ ...")
    respuesta = s3_client.list_objects_v2(Bucket=NOMBRE_BUCKET, Prefix='entrenamiento/')

    estaticos_s3 = []
    if 'Contents' in respuesta:
        for obj in respuesta['Contents']:
            llave = obj['Key']
            if llave.endswith('.csv'):
                estaticos_s3.append(llave)

    if len(estaticos_s3) == 0:
        print("ERROR: No se encontraron archivos .csv en la carpeta de entrenamiento.")
    else:
        print(f"Se encontraron {len(estaticos_s3)} archivos para entrenar.")
        archivos_locales = descargar_lista_s3(estaticos_s3, '/content/temp')
        ruta_inf = ejecutar_etl_y_guardar(archivos_locales, "historico_base")
        ejecutar_ia(ruta_inf, es_entrenamiento_estatico=True, sufijo_batch="historico_base")
        for f in archivos_locales:
            if os.path.exists(f): os.remove(f)
else:
    print("Entrenamiento detectado. El modelo ya sabe reconocer ataques.")

print("\nIniciando vigilancia de tráfico en tiempo real...")

MODO_ENTRENAMIENTO_CONTINUO = False

if MODO_ENTRENAMIENTO_CONTINUO:
    print("MODO APRENDIZAJE ACTIVO: La IA se entrenará con los datos.")
else:
    print("MODO PRODUCCIÓN: Inferencia pura sin modificar el modelo.")

while True:
    pendientes = obtener_pendientes_servidor()

    if len(pendientes) >= 1:
        lote_a_procesar = pendientes[:1]
        nombre_archivo_s3 = lote_a_procesar[0].split('/')[-1]
        timestamp_lote = time.strftime("%Y%m%d_%H%M%S")

        print(f"\n¡Tráfico detectado en S3! Procesando: {nombre_archivo_s3} ({timestamp_lote})...")

        archivos_locales = descargar_lista_s3(lote_a_procesar, '/content/temp')
        ruta_inf = ejecutar_etl_y_guardar(archivos_locales, timestamp_lote)
        ejecutar_ia(ruta_inf, es_entrenamiento_estatico=False, sufijo_batch=timestamp_lote, modo_aprendizaje_continuo=MODO_ENTRENAMIENTO_CONTINUO)

        for ruta_s3 in lote_a_procesar: archivar_en_s3(ruta_s3)
        for f in archivos_locales:
            if os.path.exists(f): os.remove(f)

        print(f"Archivo '{nombre_archivo_s3}' procesado con éxito y movido a /archivados.")

    else:
        print(f"Esperando datos en S3... ({len(pendientes)} archivos en cola). Reintentando en 3s...")
        time.sleep(3)