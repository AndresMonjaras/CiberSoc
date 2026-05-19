import requests
import time
import random
URL = "http://127.0.0.1:8000"

# Simulamos una Botnet (múltiples IPs falsas) para que el ataque sea distribuido
BOTNET_IPS = ["118.25.6.39", "176.111.173.242", "5.188.10.179", "185.222.209.14", "8.8.8.8", "192.168.1.15"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "curl/7.68.0", # Típico de scripts automatizados
    "python-requests/2.25.1",
    "DirBuster-1.0-RC1" # Típico de escáner de vulnerabilidades (herramienta hacker)
]

print("🚀 Iniciando simulación de tráfico y ataques Cyber-Sentinel...")

while True:
    dado = random.randint(1, 100)
    ip_falsa = random.choice(BOTNET_IPS)
    headers = {
        "X-Forwarded-For": ip_falsa,
        "User-Agent": random.choice(USER_AGENTS)
    }
    
    try:
        if dado <= 70:
            print(f"[🟢 NORMAL] {ip_falsa} navegando en el inicio...")
            requests.get(f"{URL}/", headers=headers)
            time.sleep(random.uniform(0.5, 1.5))
            
        elif 70 < dado <= 85:
            print(f"🔥 [🔴 DDoS] Ráfaga de {ip_falsa} al login!")
            # Dispara 30 peticiones rápidas
            for _ in range(30):
                requests.post(f"{URL}/login", headers=headers)
            time.sleep(1)
            
        else:
            print(f"🔨 [🟠 FUERZA BRUTA] {ip_falsa} escaneando directorios...")
            # Peticiones que darán error 404 intencionalmente
            for _ in range(15):
                requests.get(f"{URL}/admin_dashboard_{random.randint(1,50)}", headers=headers)
            time.sleep(1)
                
    except requests.exceptions.ConnectionError:
        print("⚠️ El servidor no responde. ¿Está encendido?")
        time.sleep(2)

        