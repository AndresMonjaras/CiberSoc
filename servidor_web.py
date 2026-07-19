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
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from starlette.middleware.base import BaseHTTPMiddleware
from contextlib import asynccontextmanager

# ==========================================
# 1. CONFIGURACION Y ESTADO GLOBAL
# ==========================================

COLUMNAS_CSV = [
    "IP Origen", "Puerto Destino", "Duracion Flujo", "Total Paquetes Adelante", 
    "Total Paquetes Atras", "Longitud Total Paquetes Adelante", "Longitud Total Paquetes Atras", "Etiqueta"
]
ARCHIVO_CSV_TRAFICO = "raw_traffic.csv"
TIEMPO_AGRUPACION_SEG = 5.0

# Diccionarios de almacenamiento en memoria
estado_ips_bloqueadas = {}  # Formato: { "IP": timestamp_expiracion }
estadisticas_trafico_ip = {}   # Formato: { "IP": { ... metricas de trafico ... } }

if not os.path.exists(ARCHIVO_CSV_TRAFICO):
    with open(ARCHIVO_CSV_TRAFICO, "w", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(COLUMNAS_CSV)

# ==========================================
# 2. FUNCIONES DE UTILIDAD (AWS & FIREWALL)
# ==========================================

def cargar_credenciales_aws():
    """Lee las credenciales de AWS desde un archivo local."""
    configuracion = configparser.ConfigParser()
    try:
        configuracion.read('aws_details.txt')
        return configuracion['default']['aws_access_key_id'], configuracion['default']['aws_secret_access_key'], configuracion['default']['aws_session_token']
    except Exception:
        print("Error leyendo aws_details.txt")
        return None, None, None

def bloquear_ip_en_so(direccion_ip):
    """Crea una regla en el firewall del sistema operativo para bloquear la IP."""
    if platform.system() == "Windows":
        nombre_regla = f"Bloqueo_{direccion_ip}"
        
        # Eliminar regla existente
        subprocess.run(f'netsh advfirewall firewall delete rule name="{nombre_regla}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Inyectar nueva regla de bloqueo
        print(f"[FIREWALL] Aplicando bloqueo de red para la IP: {direccion_ip}")
        comando = f'netsh advfirewall firewall add rule name="{nombre_regla}" dir=in action=block remoteip={direccion_ip} profile=any protocol=any'
        resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
        
        if resultado.returncode != 0:
            print("[ERROR FIREWALL] Privilegios insuficientes. Ejecuta como administrador.")
        else:
            print(f"[FIREWALL] Regla creada con exito.")

# ==========================================
# 3. TAREAS EN SEGUNDO PLANO
# ==========================================

async def tarea_sincronizacion_s3():
    """Sincroniza la lista de IPs bloqueadas desde AWS S3 en tiempo real."""
    print("[SISTEMA] Iniciando tarea de monitoreo S3...")
    global estado_ips_bloqueadas
    
    while True:
        try:
            acceso_aws, secreto_aws, token_aws = cargar_credenciales_aws()
            if acceso_aws:
                cliente_s3 = boto3.client(
                    's3',
                    aws_access_key_id=acceso_aws,
                    aws_secret_access_key=secreto_aws,
                    aws_session_token=token_aws,
                    region_name='us-east-1'
                )
                
                respuesta = cliente_s3.list_objects_v2(Bucket="bucket-proyecto-big-data", Prefix="antecedentes/")
                if 'Contents' in respuesta:
                    nuevas_ips_bloqueadas = {}
                    
                    for objeto in respuesta['Contents']:
                        if objeto['Key'].endswith('.csv'):
                            objeto_csv = cliente_s3.get_object(Bucket="bucket-proyecto-big-data", Key=objeto['Key'])
                            contenido = objeto_csv['Body'].read().decode('utf-8')
                            marco_datos = pd.read_csv(io.StringIO(contenido))
                            
                            col_ip = 'ip_origen' if 'ip_origen' in marco_datos.columns else 'Source IP'
                            
                            for _, fila in marco_datos.iterrows():
                                direccion_ip = str(fila[col_ip])
                                
                                # Obtener tiempo de expiracion
                                if 'expiracion_bloqueo' in marco_datos.columns:
                                    expiracion = pd.to_datetime(fila['expiracion_bloqueo']).timestamp()
                                elif 'bloquear_hasta' in marco_datos.columns:
                                    expiracion = pd.to_datetime(fila['bloquear_hasta']).timestamp()
                                else:
                                    expiracion = time.time() + (24 * 3600) # 24 horas por defecto
                                    
                                nuevas_ips_bloqueadas[direccion_ip] = expiracion
                                bloquear_ip_en_so(direccion_ip)
                                
                    estado_ips_bloqueadas = nuevas_ips_bloqueadas
                    print(f"[SISTEMA] Lista de control actualizada. Total IPs bloqueadas: {len(estado_ips_bloqueadas)}")
        except Exception as e:
            print(f"Error en sincronizacion: {e}")
            
        await asyncio.sleep(10)

@asynccontextmanager
async def ciclo_vida_aplicacion(aplicacion: FastAPI):
    # Iniciar procesos en segundo plano
    tarea = asyncio.create_task(tarea_sincronizacion_s3())
    yield
    # Limpiar recursos al apagar
    tarea.cancel()

# ==========================================
# 4. CONFIGURACION DE APLICACION Y MIDDLEWARES
# ==========================================

aplicacion = FastAPI(title="Servidor Web Seguro", lifespan=ciclo_vida_aplicacion)

class MiddlewareCortafuegos(BaseHTTPMiddleware):
    """Filtra peticiones entrantes basandose en la lista de IPs bloqueadas."""
    async def dispatch(self, peticion: Request, llamar_siguiente):
        ip_origen = peticion.headers.get("X-Forwarded-For", "").split(",")[0].strip() or peticion.client.host
        
        if ip_origen in estado_ips_bloqueadas:
            tiempo_actual = time.time()
            if tiempo_actual < estado_ips_bloqueadas[ip_origen]:
                return PlainTextResponse(status_code=403, content="ACCESO DENEGADO")
            else:
                print(f"Bloqueo expirado para {ip_origen}. Restaurando privilegios.")
                del estado_ips_bloqueadas[ip_origen]
                
        try:
            return await llamar_siguiente(peticion)
        except Exception:
            return PlainTextResponse(status_code=500, content="Error interno de red")

aplicacion.add_middleware(MiddlewareCortafuegos)

@aplicacion.middleware("http")
async def middleware_analizador_trafico(peticion: Request, llamar_siguiente):
    """Recolecta estadisticas de trafico de red y las guarda en un archivo CSV."""
    ip_origen = peticion.headers.get("X-Forwarded-For", "").split(",")[0].strip() or peticion.client.host
    tiempo_actual = time.time()
    
    # Inicializar contador para IP
    if ip_origen not in estadisticas_trafico_ip:
        estadisticas_trafico_ip[ip_origen] = {
            "tiempo_primer_paquete": tiempo_actual,
            "conteo_peticiones": 0,
            "bytes_acumulados": 0,
            "etiqueta_trafico": "BENIGNO"
        }

    # Asignar etiquetas segun el comportamiento
    ruta_solicitada = peticion.url.path
    if "/login" in ruta_solicitada and peticion.method == "POST":
        estadisticas_trafico_ip[ip_origen]["etiqueta_trafico"] = "DDoS"
    elif "/admin_dashboard" in ruta_solicitada:
        if estadisticas_trafico_ip[ip_origen]["etiqueta_trafico"] == "BENIGNO":
            estadisticas_trafico_ip[ip_origen]["etiqueta_trafico"] = "Fuerza Bruta"

    estadisticas_trafico_ip[ip_origen]["conteo_peticiones"] += 1

    # Continuar la peticion
    respuesta = await llamar_siguiente(peticion)
    
    # Escribir registros si se supera el tiempo establecido
    if ip_origen in estadisticas_trafico_ip:
        bytes_enviados = len(str(peticion.headers))
        bytes_recibidos = int(respuesta.headers.get("content-length", 200))
        estadisticas_trafico_ip[ip_origen]["bytes_acumulados"] += bytes_enviados + bytes_recibidos

        duracion_flujo = time.time() - estadisticas_trafico_ip[ip_origen]["tiempo_primer_paquete"]
        
        if duracion_flujo >= TIEMPO_AGRUPACION_SEG:
            duracion_flujo_us = duracion_flujo * 1000000.0
            total_paquetes = float(estadisticas_trafico_ip[ip_origen]["conteo_peticiones"])
            total_bytes = float(estadisticas_trafico_ip[ip_origen]["bytes_acumulados"])
            etiqueta_final = estadisticas_trafico_ip[ip_origen]["etiqueta_trafico"]
            
            linea_csv = (f"{ip_origen},80.0,{duracion_flujo_us},{total_paquetes},{total_paquetes},"
                        f"{total_bytes},{total_bytes},{etiqueta_final}\n")
            
            with open(ARCHIVO_CSV_TRAFICO, "a", encoding="utf-8") as archivo:
                archivo.write(linea_csv)
                
            del estadisticas_trafico_ip[ip_origen]
        
    return respuesta

# ==========================================
# 5. RUTAS DE LA API (WEB)
# ==========================================

@aplicacion.get("/", response_class=HTMLResponse)
def pagina_inicio():
    contenido_html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Portal Seguro</title>
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
        <div class="navbar">Portal Web</div>
        <div class="container">
            <div class="card">
                <h2>Bienvenido</h2>
                <p>Este es un portal para pruebas de seguridad y analisis de trafico.</p>
                <p>Manten un comportamiento adecuado. Todas las conexiones son monitoreadas.</p>
            </div>
            
            <div class="card">
                <h2>Acceso Restringido</h2>
                <p>Inicia sesion para administrar el sistema.</p>
                <form class="login-form" action="/login" method="post">
                    <input type="text" placeholder="Usuario" name="username">
                    <input type="password" placeholder="Contrasena" name="password">
                    <button type="submit">Autenticar</button>
                </form>
            </div>
        </div>
        <div class="footer">
            Monitoreo de red activo
        </div>
    </body>
    </html>
    """
    return contenido_html

@aplicacion.post("/login")
async def punto_acceso_login():
    return {"estado": "error", "mensaje": "Autenticacion deshabilitada."}