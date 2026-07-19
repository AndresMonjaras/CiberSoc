# Proyecto Big Data; CIBERSOC

Este repositorio almacena el codigo y los datos para un sistema avanzado de deteccion de intrusiones corporativas; El proyecto procesa informacion masiva utilizando tecnologias de Big Data para identificar anomalias en la red;

## Estructura del Repositorio

El sistema se divide en varios componentes y directorios principales;

### Archivos Principales de Ejecucion
- `servidor_web.py`; Servidor web que actua como blanco de ataques y recolecta estadisticas del trafico entrante;
- `tablero_seguridad.py`; Interfaz visual para evaluar las direcciones IP maliciosas detectadas;
- `simulador_trafico.py`; Herramienta disenada para generar peticiones benignas y maliciosas automatizadas;
- `sincronizacion_aws.py`; Script de conexion para enviar los archivos de trafico hacia los buckets de AWS;

### Carpetas de Datos y Entrenamiento
- `entrenamientoIA/`; Contiene los archivos CSV del conjunto de datos original para entrenar los modelos de Inteligencia Artificial;
- `simulacion_trafico/`; Almacena archivos CSV adicionales utilizados para pruebas de estres y evaluacion;
- `data/`; Guarda archivos temporales como los registros crudos de red;

### Modelado y Limpieza de Datos
- `GOOGLE_COLAB/ETL_e_IA.py`; Contiene el codigo ejecutado en Google Colab para procesar los conjuntos de datos masivos usando PySpark; Tambien incluye la implementacion del modelo de clasificacion;

### Configuracion
- `requirements.txt`; Especifica las dependencias necesarias para ejecutar el sistema localmente;
- `aws_details.txt`; Archivo requerido para autenticar la conexion con los buckets de almacenamiento en la nube;

## Objetivos del Proyecto
1; Procesar millones de registros de red para extraer caracteristicas clave utilizando PySpark;
2; Implementar un algoritmo de aprendizaje automatico capaz de separar el trafico normal de los ataques de fuerza bruta o denegacion de servicio
3; Integrar el bloqueo dinamico de atacantes a nivel del cortafuegos del sistema operativo;

## Ejecucion del Proyecto
Para poner en marcha el sistema completo, inicie el servidor objetivo;
```bash
uvicorn servidor_web:aplicacion --reload
```
Posteriormente, inicie el panel de control y el puente hacia la nube en terminales separadas;
```bash
streamlit run tablero_seguridad.py
python sincronizacion_aws.py
```
Finalmente, ejecute el generador de ataques;
```bash
python simulador_trafico.py
```

## Resultados
- La segmentacion del trafico demostro ser sumamente eficaz;
- Los datos se limpiaron exitosamente gracias a la arquitectura distribuida de PySpark;
- El tiempo de respuesta para bloquear atacantes se redujo significativamente