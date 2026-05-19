from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import csv
import random
import os
import time
import boto3
import configparser
import pandas as pd
import io
import asyncio
import subprocess
import platform
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="Cyber-Sentinel Target Web Server")

# Todas las columnas del dataset (incluyendo IP de origen/destino requeridas por el panel)
COLUMNAS = [
    "Source IP", "Destination Port", "Flow Duration", "Total Fwd Packets", 
    "Total Backward Packets", "Total Length of Fwd Packets", "Total Length of Bwd Packets", "Label"
]

ARCHIVO_CSV = "raw_traffic.csv"

if not os.path.exists(ARCHIVO_CSV):
    with open(ARCHIVO_CSV, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNAS)

# Diccionario para manejar IP y su fecha de expiración { "IP": timestamp }
ANTECEDENTES_IPS = {}
ESTADISTICAS_IP = {}

def cargar_credenciales():
    config = configparser.ConfigParser()
    try:
        config.read('aws_details.txt')
        return config['default']['aws_access_key_id'], config['default']['aws_secret_access_key'], config['default']['aws_session_token']
    except Exception:
        print("❌ Error leyendo aws_details.txt")
        return None, None, None

def bloquear_ip_en_sistema_operativo(ip):
    """Inyecta una regla en el Firewall de Windows para destruir los paquetes antes de que toquen FastAPI"""
    if platform.system() == "Windows":
        nombre_regla = f"CyberSentinel_Drop_{ip}"
        
        # 1. Destruimos la regla anterior sin preguntar, para asegurar que no haya basura en caché
        subprocess.run(f'netsh advfirewall firewall delete rule name="{nombre_regla}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # 2. Inyectamos la regla forzando que aplique a WSL (profile=any) y bloquee absolutamente todo (protocol=any)
        print(f"🛡️ [FIREWALL] Inyectando regla de red profunda para aniquilar la IP: {ip}")
        cmd_block = f'netsh advfirewall firewall add rule name="{nombre_regla}" dir=in action=block remoteip={ip} profile=any protocol=any'
        res = subprocess.run(cmd_block, shell=True, capture_output=True, text=True)
        
        if res.returncode != 0:
            print(f"⚠️ [FIREWALL ERROR] Fallo al crear regla. REQUISITO INDISPENSABLE: Cierra esta terminal de VS Code y ábrela como ADMINISTRADOR.")
        else:
            print(f"✅ [FIREWALL] Regla '{nombre_regla}' inyectada con éxito a nivel Kernel.")

async def bucle_sincronizacion_s3():
    print("📡 [SÉNSOR] Iniciando hilo de sincronización continua con el Data Lake...")
    while True:
        try:
            global ANTECEDENTES_IPS
            aws_access_key, aws_secret_key, aws_session_token = cargar_credenciales()
            if aws_access_key:
                s3 = boto3.client(
                    's3',
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    aws_session_token=aws_session_token,
                    region_name='us-east-1'
                )
                
                objetos = s3.list_objects_v2(Bucket="bucket-proyecto-big-data", Prefix="antecedentes/")
                if 'Contents' in objetos:
                    nuevos_antecedentes = {}
                    for obj in objetos['Contents']:
                        if obj['Key'].endswith('.csv'):
                            archivo_csv = s3.get_object(Bucket="bucket-proyecto-big-data", Key=obj['Key'])
                            contenido = archivo_csv['Body'].read().decode('utf-8')
                            df = pd.read_csv(io.StringIO(contenido))
                            
                            columna_ip = 'ip_origen' if 'ip_origen' in df.columns else 'Source IP'
                            for _, row in df.iterrows():
                                ip = str(row[columna_ip])
                                if 'expiracion_bloqueo' in df.columns:
                                    expiracion = pd.to_datetime(row['expiracion_bloqueo']).timestamp()
                                elif 'bloquear_hasta' in df.columns:
                                    expiracion = pd.to_datetime(row['bloquear_hasta']).timestamp()
                                else:
                                    expiracion = time.time() + (24 * 3600)
                                    
                                nuevos_antecedentes[ip] = expiracion
                                
                                # 🔥 EL GOLPE DE GRACIA: Ejecutar el bloqueo a nivel OS
                                bloquear_ip_en_sistema_operativo(ip)
                                
                    ANTECEDENTES_IPS = nuevos_antecedentes
                    print(f" [SÉNSOR] RAM Actualizada desde S3. IPs bajo castigo: {len(ANTECEDENTES_IPS)}")
        except Exception as e:
            print(f"Error en la sincronización en vivo: {e}")
            
        await asyncio.sleep(10)

@app.on_event("startup")
async def al_iniciar_servidor():
    asyncio.create_task(bucle_sincronizacion_s3())

class MuroFirewall(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip_origen = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.client.host
        
        if ip_origen in ANTECEDENTES_IPS:
            tiempo_actual = time.time()
            if tiempo_actual < ANTECEDENTES_IPS[ip_origen]:
                # Usamos PlainTextResponse porque es infinitamente más ligero que JSONResponse
                # Si el Firewall de Windows llega a dejar pasar un paquete, lo matamos rápido aquí
                return PlainTextResponse(status_code=403, content="IP BLOQUEADA POR CYBER-SENTINEL")
            else:
                print(f"Castigo expirado para {ip_origen}. Liberando acceso.")
                del ANTECEDENTES_IPS[ip_origen]
                
        try:
            return await call_next(request)
        except Exception:
            # Si Vegeta corta la conexión a la fuerza (LocalProtocolError), atrapamos el error 
            # de forma silenciosa para que el servidor siga de pie y no colapse.
            return PlainTextResponse(status_code=500, content="Conexión Abortada")

# Levantamos el muro en la aplicación para que actúe como primera línea de defensa
app.add_middleware(MuroFirewall)

@app.middleware("http")
async def registrar_trafico_autentico(request: Request, call_next):
    ip_origen = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or request.client.host
    
    # === RECOLECCIÓN DE DATOS REALES ===
    tiempo_actual = time.time()
    
    # Si es la primera petición de la IP en este segundo, iniciamos su "Flujo"
    if ip_origen not in ESTADISTICAS_IP:
        ESTADISTICAS_IP[ip_origen] = {
            "primer_paquete": tiempo_actual,
            "conteo_peticiones": 0,
            "bytes_acumulados": 0,
            "etiqueta": "BENIGN"
        }

    # === DETECCIÓN DE ETIQUETAS SEGÚN ATACANTE_REAL.PY ===
    ruta_solicitada = request.url.path
    if "/login" in ruta_solicitada and request.method == "POST":
        ESTADISTICAS_IP[ip_origen]["etiqueta"] = "DDoS"
    elif "/admin_dashboard" in ruta_solicitada:
        if ESTADISTICAS_IP[ip_origen]["etiqueta"] == "BENIGN":
            ESTADISTICAS_IP[ip_origen]["etiqueta"] = "Fuerza Bruta"

    # Contamos la petición actual antes de procesarla
    ESTADISTICAS_IP[ip_origen]["conteo_peticiones"] += 1

    # Procesamos la respuesta del servidor
    response = await call_next(request)
    
    # Validamos que el diccionario de esta IP no haya sido borrado por otra petición concurrente rápida
    if ip_origen in ESTADISTICAS_IP:
        # Sumamos el tamaño real aproximado de los paquetes
        bytes_enviados = len(str(request.headers))
        bytes_recibidos = int(response.headers.get("content-length", 200))
        ESTADISTICAS_IP[ip_origen]["bytes_acumulados"] += bytes_enviados + bytes_recibidos

        # === AGRUPACIÓN Y ESCRITURA ===
        duracion_flujo_segundos = time.time() - ESTADISTICAS_IP[ip_origen]["primer_paquete"]
        
        # Si ya pasó 1 segundo o más desde que la IP empezó a mandar datos, cerramos el flujo y registramos
        if duracion_flujo_segundos >= 1.0:
            flow_duration_us = duracion_flujo_segundos * 1000000.0
            paquetes_totales = float(ESTADISTICAS_IP[ip_origen]["conteo_peticiones"])
            bytes_totales = float(ESTADISTICAS_IP[ip_origen]["bytes_acumulados"])
            etiqueta_final = ESTADISTICAS_IP[ip_origen]["etiqueta"]
            
            # Escribimos los datos matemáticos reales con la etiqueta detectada
            linea_csv = (f"{ip_origen},80.0,{flow_duration_us},{paquetes_totales},{paquetes_totales},"
                         f"{bytes_totales},{bytes_totales},{etiqueta_final}\n")
            
            with open("raw_traffic.csv", "a", encoding="utf-8") as f:
                f.write(linea_csv)
                
            # Reiniciamos el contador de la IP para el siguiente segundo
            del ESTADISTICAS_IP[ip_origen]
        
    return response
# --- RUTAS VISUALES ---

@app.get("/", response_class=HTMLResponse)
def inicio():
    # Una página súper casual, estilo aesthetic / lofi
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Vibes & Code ✨</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;700;900&display=swap');
            body { 
                font-family: 'Nunito', sans-serif; 
                background: linear-gradient(135deg, #a1c4fd 0%, #c2e9fb 100%); 
                margin: 0; min-height: 100vh; display: flex; flex-direction: column; 
                align-items: center; color: #333;
            }
            .navbar {
                width: 100%; padding: 20px 0; background: rgba(255, 255, 255, 0.4); 
                backdrop-filter: blur(10px); text-align: center; font-size: 26px; 
                font-weight: 900; color: #2c3e50; letter-spacing: 2px;
            }
            .container {
                display: flex; flex-wrap: wrap; justify-content: center; gap: 30px; 
                padding: 40px 20px; max-width: 900px; width: 100%;
            }
            .card {
                background: rgba(255, 255, 255, 0.7); backdrop-filter: blur(15px); 
                border-radius: 25px; padding: 35px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); 
                flex: 1; min-width: 300px; max-width: 400px; transition: transform 0.3s;
            }
            .card:hover { transform: translateY(-5px); }
            h2 { margin-top: 0; font-weight: 800; color: #ff7675; }
            p { line-height: 1.6; color: #555; font-size: 16px; }
            .login-form { display: flex; flex-direction: column; gap: 15px; margin-top: 20px; }
            input {
                padding: 15px; border: none; border-radius: 12px; background: #ffffff; 
                font-family: inherit; font-size: 15px; box-shadow: inset 0 2px 5px rgba(0,0,0,0.03); 
                transition: all 0.3s;
            }
            input:focus { outline: none; box-shadow: 0 0 0 3px #fab1a0; }
            button {
                padding: 15px; border: none; border-radius: 12px; background: #ff7675; 
                color: white; font-weight: bold; font-size: 16px; cursor: pointer; 
                transition: background 0.3s, transform 0.1s;
            }
            button:hover { background: #d63031; }
            button:active { transform: scale(0.98); }
            .footer {
                margin-top: auto; padding: 20px; text-align: center; color: #555; 
                font-weight: bold; font-size: 13px;
            }
        </style>
    </head>
    <body>
        <div class="navbar">☕ Vibes & Code ✨</div>
        <div class="container">
            <div class="card">
                <h2>Hola, Mundo! 🎧</h2>
                <p>Bienvenido a nuestro espacio seguro. Aquí compartimos fragmentos de código, escuchamos música lofi y tomamos café virtual.</p>
                <p>Ponte cómodo, explora un poco, pero recuerda siempre mantener la buena vibra.</p>
                <div style="font-size: 40px; text-align: center; margin-top: 25px;">💻 🎨 🚀</div>
            </div>
            
            <div class="card">
                <h2>Únete a la Sesión 🔒</h2>
                <p>Inicia sesión para compartir tus proyectos o unirte al chat general.</p>
                <form class="login-form" action="/login" method="post">
                    <input type="text" placeholder="Tu usuario aesthetic" name="username">
                    <input type="password" placeholder="Contraseña secreta" name="password">
                    <button type="submit">Entrar al Club 💫</button>
                </form>
            </div>
        </div>
        <div class="footer">
            🛡️ Cyber-Sentinel observando silenciosamente el tráfico de fondo.
        </div>
    </body>
    </html>
    """
    return html_content

@app.post("/login")
async def login():

    
    return {"status": "error", "mensaje": "Autenticación bloqueada."}