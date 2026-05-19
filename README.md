# 🛡️ Proyecto Big Data: Cyber-Sentinel

Este proyecto procesa **2.8 millones de registros** de tráfico de red para detectar intrusiones en la infraestructura corporativa.

## 🏗️ Arquitectura del Sistema
- **Procesamiento Distribuido:** Google Colab con PySpark.
- **Inteligencia Artificial:** Modelo Random Forest (99% de precisión).
- **Inteligencia de Amenazas:** API de AbuseIPDB para validación en tiempo real.


# 🛡️ Detección de Intrusiones con Big Data e IA

Este proyecto procesa el dataset **CIC-IDS2017** utilizando una arquitectura híbrida: **PySpark** para el procesamiento masivo y **Scikit-Learn** para la detección de anomalías.

## 🚀 Pipeline del Proyecto
1. **Fase 1 (Spark ETL):** Procesamiento de archivos CSV masivos en Google Colab para limpieza y reducción de dimensionalidad.
2. **Fase 2 (Análisis Estadístico):** Validación de coherencia mediante matrices de correlación (Heatmaps).
3. **Fase 3 (Machine Learning):** Implementación de **Isolation Forest** para identificar patrones de tráfico inusuales.
4. **Fase 4 (Visualización):** Generación de evidencias visuales con Seaborn mostrando la separación de flujos maliciosos.

## 📊 Hallazgos Clave
- Se identificó una alta correlación (0.96+) entre el volumen de paquetes y la duración del flujo.
- El modelo Isolation Forest logró segmentar el tráfico masivo de DDoS frente al tráfico Benigno.