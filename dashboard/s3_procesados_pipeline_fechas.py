import boto3
import pandas as pd
import time
import io
from datetime import datetime

# CONFIG 
bucket = "bucket-proyecto-big-data"
prefix = "procesados/"

s3 = boto3.client("s3")

dfs = []
procesados = set()

print("Pipeline iniciado...")

# extrae el timestamp del nombre del archivo y lo convierte a datetime legible
def extraer_timestamp(key):
    try:
        nombre = key.split("/")[-1].replace(".csv", "")
        partes = nombre.split("_")
        fecha_str = partes[-2] + partes[-1]
        dt = datetime.strptime(fecha_str, "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

while True:

    try:

        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix=prefix
        )

        files = [
            obj["Key"]
            for obj in response.get("Contents", [])
            if obj["Key"].endswith(".csv")
        ]

        nuevos = [f for f in files if f not in procesados]

        if nuevos:

            print(f"\nNuevos archivos detectados: {len(nuevos)}")

            for f in nuevos:

                try:

                    print("Leyendo:", f)

                    obj = s3.get_object(Bucket=bucket, Key=f)
                    body = obj["Body"].read()

                    df_temp = pd.read_csv(io.BytesIO(body), low_memory=False)

                    # Agregar columna de fecha/hora extraída del nombre del archivo
                    df_temp["Fecha_Hora_Ataque"] = extraer_timestamp(f)

                    dfs.append(df_temp)
                    procesados.add(f)

                    print(f"  ✔ {f} ({len(df_temp)} filas)")

                except Exception as e:
                    print("Error leyendo archivo:", e)

            if dfs:

                df = pd.concat(dfs, ignore_index=True)

                print(f"\nDATAFRAME ACTUALIZADO: {df.shape}")

                df.to_csv("datos_consolidados.csv", index=False)

                print("CSV consolidado actualizado ✔")

        else:
            print("Sin nuevos archivos...")

    except Exception as e:
        print("Error general:", e)

    time.sleep(5)
