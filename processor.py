import jpype
from matplotlib.pylab import f

jvm_path = r"C:\Program Files\Java\jdk-23\bin\server\jvm.dll"
jpype.startJVM(jvm_path)

import os
import re
import pandas as pd
import tabula
import numpy as np
from pyproj import Transformer


class DataProcessor:
    def __init__(self, csv_file="data.csv", pdf_file="atasco.pdf"):
        self.csv_file = csv_file
        self.pdf_file = pdf_file
        self.data = None

    def load_or_process_data(self):
        if os.path.exists(self.csv_file):
            print(f"Cargando datos desde {self.csv_file}...")
            self.data = pd.read_csv(self.csv_file)
        else:
            print(f"{self.csv_file} no encontrado. Procesando PDF's...")
            self.load_pdf_data()
            self.process_data()
            print(f"Guardando datos procesados en {self.csv_file}...")
            self.data.to_csv(self.csv_file, index=False)

    def load_pdf_data(self):
        dfs = tabula.read_pdf(
            self.pdf_file, pages="all", multiple_tables=True, lattice=True, encoding="latin-1"
        )
        self.data = pd.concat(dfs, ignore_index=True)

    def process_data(self):
        if self.data is None:
            raise ValueError("No hay datos cargados para procesar.")

        # Limpiar nombres de columnas
        self.data.columns = self.data.columns.str.replace(r"[\r\n]", " ", regex=True).str.strip()
        self.data.columns = self.data.columns.str.replace(r"\s+", " ", regex=True)

        # Función para limpiar texto
        def limpiar_texto(x):
            if isinstance(x, str):
                x = x.replace("\r", " ").replace("\n", " ")
                x = re.sub(r"\s+", " ", x)  # reemplaza múltiples espacios por uno
                return x.strip()
            return x

        # Aplicar limpieza solo a columnas de texto
        for col in self.data.select_dtypes(include="object").columns:
            self.data[col] = self.data[col].apply(limpiar_texto)

        # Renombrar columnas
        rename_cols = {
            "Provincia": "provincia",
            "Municipio": "municipio",
            "Coordenadas X (m) (ETRS89)": "x",
            "Coordenadas Y (m) (ETRS89)": "y",
            "Identificador de la subestación": "id_subestacion",
            "Nombre Subestación": "subestacion",
            "Nivel de tensión (kV)": "kv",
            "Denominación del Punto de Conexión": "punto_conexion",
            "Identificador del Punto de Conexión": "id_punto",
            "Capacidad firme disponible (MW)": "cap_disp",
            "Capacidad comprometida por cuestiones regulatorias": "cap_comp",
            "Capacidad de acceso firme de demanda ocupada (MW)": "cap_ocup",
            "Capacidad de acceso firme admitida y no evaluada (MW)": "cap_no_eval",
            "Comentario Regulatorio": "comentario",
        }
        self.data = self.data.rename(columns=rename_cols)

        # Convertir a float columnas numéricas
        cols_numericas = ["kv", "cap_disp", "cap_comp", "cap_ocup", "cap_no_eval"]
        for col in cols_numericas:
            if col in self.data.columns:
                self.data[col] = (
                    self.data[col]
                    .astype(str)
                    .str.replace(",", ".", regex=False)
                    .str.replace(r"[^\d\.\-]", "", regex=True)
                )
                self.data[col] = pd.to_numeric(self.data[col], errors="coerce")

        # ===== NUEVOS CÁLCULOS EN EL PROCESAMIENTO =====

        # Convertir coordenadas una sola vez
        print("Convirtiendo coordenadas ETRS89 a WGS84...")
        transformer = Transformer.from_crs("epsg:25830", "epsg:4326", always_xy=True)
        self.data["x"] = self.data["x"].astype(str).str.replace(",", ".").astype(float)
        self.data["y"] = self.data["y"].astype(str).str.replace(",", ".").astype(float)
        coords_transformed = self.data.apply(
            lambda row: transformer.transform(row["x"], row["y"]), axis=1
        )
        self.data["lon"], self.data["lat"] = zip(*coords_transformed)

        # Calcular capacidad total y porcentaje disponible
        print("Calculando capacidades y porcentajes...")
        self.data["cap_total"] = (
            self.data["cap_disp"] + self.data["cap_ocup"] + self.data["cap_no_eval"]
        )
        self.data["porcentaje_disponible"] = np.where(
            self.data["cap_total"] > 0, (self.data["cap_disp"] / self.data["cap_total"]) * 100, 0
        )

        # Pre-calcular color y radio para cada punto
        print("Pre-calculando colores y tamaños...")
        self.data["color"] = self.data["porcentaje_disponible"].apply(self._get_color_by_percentage)

        # Calcular radios normalizados
        max_capacity = self.data["cap_total"].max()
        min_capacity = self.data["cap_total"].min()

        if max_capacity > min_capacity:
            normalized_capacity = (self.data["cap_total"] - min_capacity) / (
                max_capacity - min_capacity
            )
            self.data["radius"] = 3 + (normalized_capacity * 12)  # Entre 3 y 15
        else:
            self.data["radius"] = 8  # Valor por defecto

        # Redondear valores para mejor presentación
        self.data["cap_total"] = self.data["cap_total"].round(2)
        self.data["porcentaje_disponible"] = self.data["porcentaje_disponible"].round(1)
        self.data["lat"] = self.data["lat"].round(6)
        self.data["lon"] = self.data["lon"].round(6)

        print("Procesamiento completado!")

    def _get_color_by_percentage(self, porcentaje):
        """Función auxiliar para obtener color según porcentaje"""
        if porcentaje == 0:
            return "red"
        elif porcentaje <= 25:
            return "orange"
        elif porcentaje <= 50:
            return "yellow"
        elif porcentaje <= 75:
            return "lightgreen"
        else:
            return "green"

    def get_processed_data(self):
        if self.data is None:
            self.load_or_process_data()
        return self.data

    # files = os.listdir(".")
    # pdf_files = [f for f in files if f.endswith(".pdf")]
    # print(pdf_files)

    # for pdf_file in pdf_files[:1]:
    #     # Cargar pdf en tablas
    #     dfs = tabula.read_pdf(
    #         pdf_file, pages="all", multiple_tables=True, lattice=True, encoding="latin-1"
    #     )
    #     data = pd.concat(dfs, ignore_index=True)

    #     # Limpiar nombres de columnas
    #     data.columns = data.columns.str.replace(r"[\r\n]", " ", regex=True).str.strip()
    #     data.columns = data.columns.str.replace(r"\s+", " ", regex=True)

    #     # Función para limpiar texto
    #     def limpiar_texto(x):
    #         if isinstance(x, str):
    #             x = x.replace("\r", " ").replace("\n", " ")
    #             x = re.sub(r"\s+", " ", x)  # reemplaza múltiples espacios por uno
    #             return x.strip()
    #         return x

    #     # Aplicar limpieza solo a columnas de texto
    #     for col in data.select_dtypes(include="object").columns:
    #         data[col] = data[col].apply(limpiar_texto)

    #     # Convertir a float columnas numéricas
    #     cols_numericas = [
    #         "Nivel de tensión (kV)",
    #         "Capacidad firme disponible (MW)",
    #         "Capacidad comprometida por cuestiones regulatorias",
    #         "Capacidad de acceso firme de demanda ocupada (MW)",
    #         "Capacidad de acceso firme admitida y no evaluada (MW)",
    #     ]
    #     for col in cols_numericas:
    #         if col in data.columns:
    #             data[col] = (
    #                 data[col]
    #                 .astype(str)
    #                 .str.replace(",", ".", regex=False)
    #                 .str.replace(r"[^\d\.\-]", "", regex=True)
    #             )
    #             data[col] = pd.to_numeric(data[col], errors="coerce")

    #     data.to_excel("Iberdrola.xlsx", index=False)


# ==========================================

RENAME_DICT = {
    # Gestor de red
    "Gestor de Red": "gestor_red",
    "Gestor de red": "gestor_red",
    # Provincia y municipio
    "Provincia": "provincia",
    "Municipio": "municipio",
    # Coordenadas
    "Coordenada UTM X": "x",
    "Coordenada UTM Y": "y",
    "Coordenada UTM X [1]": "x",
    "Coordenada UTM Y [1]": "y",
    "Coordenadas X (m) (ETRS89)": "x",
    "Coordenadas Y (m) (ETRS89)": "y",
    # Subestación
    "Subestación": "subestacion",
    "Subestación ": "subestacion",
    "Nombre Subestación": "subestacion_nombre",
    "Nombre subestación": "subestacion_nombre",
    "Identificador de la subestación": "subestacion",
    "Matrícula Sub.": "subestacion_matricula",
    # Nivel de tensión
    "Nivel de Tensión (kV)": "kv",
    "Nivel de tensión (kV)": "kv",
    # Capacidad
    "Capacidad disponible (MW)": "cap_disp",
    "Capacidad firme disponible (MW)": "cap_disp",
    "Capacidad firme disponible (MW) [2]": "cap_disp",
    "Capacidad comprometida por cuestiones regulatorias": "cap_comp",
    "Capacidad ocupada (MW)": "cap_ocup",
    "Capacidad de acceso firme de demanda ocupada (MW)": "cap_ocup",
    "Capacidad de acceso firme de demanda ocupada (MW) [3]": "cap_ocup",
    "Capacidad admitida y no resuelta (MW)": "cap_no_eval",
    "Capacidad de acceso firme admitida y no evaluada (MW)": "cap_no_eval",
    "Capacidad de acceso firme admitida y no evaluada (MW) [4]": "cap_no_eval",
    # Posiciones
    "Posiciones ocupadas": "pos_ocupadas",
    "Posiciones libres": "pos_libres",
    # Nudos
    "Nudo Afección RdT": "nudo",
    "Nudo de afección RdT": "nudo",
    "Nudo limitado por Scc ": "nudo",
    "Nudo 0*": "nudo",
    "Nudo 0* ": "nudo",
    # Comentarios
    "Comentarios": "comentarios",
    "Comentario Regulatorio": "comentarios",
    # Comunidad Autónoma
    "Comunidad Autónoma": "comunidad_autonoma",
    # Puntos de conexión
    "Denominación del Punto de Conexión": "punto_conexion",
    "Identificador del Punto de Conexión": "id_punto",
}


def _get_color_by_percentage(porcentaje):
    """Función auxiliar para obtener color según porcentaje"""
    if porcentaje == 0:
        return "red"
    elif porcentaje <= 25:
        return "orange"
    elif porcentaje <= 50:
        return "yellow"
    elif porcentaje <= 75:
        return "lightgreen"
    else:
        return "green"


if __name__ == "__main__":
    files = os.listdir(".")
    excel_files = [f for f in files if f.endswith(".xlsx")]

    dfs_results = pd.DataFrame()
    for file in excel_files:
        df = pd.read_excel(file)
        df = df.rename(columns=RENAME_DICT)

        # Convertir coordenadas una sola vez
        transformer = Transformer.from_crs("epsg:25830", "epsg:4326", always_xy=True)
        df["x"] = df["x"].astype(str).str.replace(",", ".").astype(float)
        df["y"] = df["y"].astype(str).str.replace(",", ".").astype(float)
        coords_transformed = df.apply(lambda row: transformer.transform(row["x"], row["y"]), axis=1)
        df["lon"], df["lat"] = zip(*coords_transformed)

        df["gestor_red"] = file.split(".")[0]
        df = df[
            [
                "gestor_red",
                "provincia",
                "municipio",
                "lat",
                "lon",
                "subestacion_nombre",
                "subestacion",
                "kv",
                "cap_disp",
                "cap_comp",
                "cap_ocup",
                "cap_no_eval",
                # "nudo",
                "comentarios",
            ]
        ]

        # Calcular capacidad total y porcentaje disponible
        print("Calculando capacidades y porcentajes...")

        # Normalizar números y vacíos
        df["cap_disp"] = (
            df["cap_disp"]
            .astype(str)
            .str.replace(",", ".")
            .str.strip()
            .replace("", np.nan)
            .astype(float)
        )
        df["cap_comp"] = (
            df["cap_comp"]
            .astype(str)
            .str.replace(",", ".")
            .str.strip()
            .replace("", np.nan)
            .astype(float)
        )
        df["cap_ocup"] = (
            df["cap_ocup"]
            .astype(str)
            .str.replace(",", ".")
            .str.strip()
            .replace("", np.nan)
            .astype(float)
        )
        df["cap_no_eval"] = (
            df["cap_no_eval"]
            .astype(str)
            .str.replace(",", ".")
            .str.strip()
            .replace("", np.nan)
            .astype(float)
        )

        df["cap_total"] = df["cap_disp"] + df["cap_comp"] + df["cap_ocup"] + df["cap_no_eval"]
        df["porcentaje_disponible"] = np.where(
            df["cap_total"] > 0, (df["cap_disp"] / df["cap_total"]) * 100, 0
        )

        # Pre-calcular color y radio para cada punto
        print("Pre-calculando colores y tamaños...")
        df["color"] = df["porcentaje_disponible"].apply(_get_color_by_percentage)

        dfs_results = pd.concat([df, dfs_results], ignore_index=True)

    # Calcular radios normalizados
    max_capacity = dfs_results["cap_total"].max()
    min_capacity = dfs_results["cap_total"].min()

    if max_capacity > min_capacity:
        normalized_capacity = (dfs_results["cap_total"] - min_capacity) / (
            max_capacity - min_capacity
        )
        dfs_results["radius"] = 3 + (normalized_capacity * 12)  # Entre 3 y 15
    else:
        dfs_results["radius"] = 8  # Valor por defecto

    # Redondear valores para mejor presentación
    dfs_results["cap_total"] = dfs_results["cap_total"].round(2)
    dfs_results["porcentaje_disponible"] = dfs_results["porcentaje_disponible"].round(1)
    dfs_results["lat"] = dfs_results["lat"].round(6)
    dfs_results["lon"] = dfs_results["lon"].round(6)

    print("Procesamiento completado!")

    print(dfs_results.head().to_string())

    print(dfs_results.to_csv("data.csv", index=False))


#     print("🚀 Iniciando procesamiento de datos...")

#     try:
#         # Crear y ejecutar el procesador
#         processor = DataProcessor()
#         processor.load_or_process_data()

#         # Mostrar información del archivo generado
#         df = processor.get_processed_data()
#         print(f"\n✅ Proceso completado exitosamente!")
#         print(f"📊 Archivo generado: data.csv")
#         print(f"📈 Total de registros: {len(df)}")
#         print(f"📋 Columnas: {list(df.columns)}")
#         print(f"🌍 Provincias únicas: {df['provincia'].nunique()}")
#         print(f"⚡ Niveles de tensión: {sorted(df['kv'].unique())}")

#         print("\n🎯 Ahora puedes ejecutar la aplicación Streamlit!")

#     except Exception as e:
#         print(f"❌ Error durante el procesamiento: {e}")
#         print("   Verifica que todos los archivos necesarios estén presentes.")
