import streamlit as st
import requests
import pandas as pd
import time

# --- 1. CONFIGURACION GENERAL ---
st.set_page_config(page_title="Centro de Operaciones", layout="wide")
CLAVE_API = "X"

st.title("Centro de Operaciones Automatizado")
st.markdown("Analisis de ataques detectados y cruce de IPs con bases de datos de amenazas globales.")
st.write("---")

# --- 2. DATOS DE INTELIGENCIA ARTIFICIAL ---
st.subheader("Top 5 Atacantes Detectados por la IA")

# Simulacion de datos obtenidos de analisis
datos_ia = pd.DataFrame({
    "IP de Origen": ["118.25.6.39", "176.111.173.242", "5.188.10.179", "185.222.209.14", "8.8.8.8"],
    "Tipo de Ataque": ["DDoS Hulk", "Fuerza Bruta SSH", "Escaneo de Puertos", "Ataque Web", "Falso Positivo"],
    "Paquetes Maliciosos": [25461, 15177, 8500, 4200, 150],
    "Servidor Afectado": ["Servidor Web (80)", "Servidor Respaldo (22)", "Servidor API (443)", "Servidor ERP (443)", "Servidor DNS (53)"]
})

st.dataframe(datos_ia, use_container_width=True)
st.write("---")

# --- 3. VERIFICACION AUTOMATIZADA ---
st.subheader("Validacion de Antecedentes (AbuseIPDB)")
st.write("Verificando si las IPs listadas tienen reportes previos de actividad maliciosa...")

if st.button("Iniciar Escaneo Automatizado"):
    
    barra_progreso = st.progress(0)
    resultados_api = []
    
    # Procesar cada IP listada
    for indice, direccion_ip in enumerate(datos_ia["IP de Origen"]):
        with st.spinner(f"Investigando IP: {direccion_ip}..."):
            
            url_api = 'https://api.abuseipdb.com/api/v2/check'
            parametros = {'ipAddress': direccion_ip, 'maxAgeInDays': '90'}
            cabeceras = {'Accept': 'application/json', 'Key': CLAVE_API}
            
            try:
                respuesta = requests.get(url_api, headers=cabeceras, params=parametros)
                if respuesta.status_code == 200:
                    datos = respuesta.json().get('data', {})
                    
                    resultados_api.append({
                        "IP Analizada": direccion_ip,
                        "Pais": datos.get('countryName', 'Desconocido'),
                        "Puntaje de Riesgo": f"{datos.get('abuseConfidenceScore', 0)}%",
                        "Proveedor (ISP)": datos.get('isp', 'Desconocido')
                    })
                else:
                    resultados_api.append({"IP Analizada": direccion_ip, "Pais": "Error de API", "Puntaje de Riesgo": "N/A", "Proveedor (ISP)": "N/A"})
                    
            except Exception as error:
                resultados_api.append({"IP Analizada": direccion_ip, "Pais": "Error conexion", "Puntaje de Riesgo": "N/A", "Proveedor (ISP)": "N/A"})
            
            # Limitar peticiones para evitar bloqueos
            time.sleep(1)
            barra_progreso.progress((indice + 1) / len(datos_ia))
            
    st.success("Escaneo automatico completado.")
    marco_resultados = pd.DataFrame(resultados_api)
    
    # Resaltar resultados criticos visualmente
    st.dataframe(
        marco_resultados.style.applymap(
            lambda valor_celda: 'background-color: #ff4b4b; color: white' if valor_celda == '100%' else '', 
            subset=['Puntaje de Riesgo']
        ),
        use_container_width=True
    )

st.write("---")
st.caption("Panel de Monitoreo de Seguridad de Red")