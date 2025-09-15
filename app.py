import streamlit as st
import pandas as pd
import folium
from folium import plugins
import numpy as np
from streamlit_folium import st_folium
import matplotlib.colors as mcolors
from PIL import Image
import os

# Configuración de la página
st.set_page_config(
    page_title="Mapa de Subestaciones",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS para ajustar altura del mapa al dispositivo
st.markdown(
    """
<style>
    .main > div {
        padding-top: 1rem;
        padding-bottom: 1rem;
    }
    
    .stApp > header {
        background-color: transparent;
    }
    
    .stApp {
        margin: 0;
        padding: 0;
    }
    
    iframe {
        height: 85vh !important;
    }
</style>
""",
    unsafe_allow_html=True,
)


# Función para cargar los datos
@st.cache_data
def load_data():
    """Carga los datos del CSV"""
    try:
        df = pd.read_csv("data.csv")
        # Limpiar datos y convertir tipos
        df = df.dropna(subset=["lat", "lon"])

        # Limpiar columnas de texto
        df["provincia"] = df["provincia"].astype(str).str.strip()
        df["municipio"] = df["municipio"].astype(str).str.strip()
        df["subestacion"] = df["subestacion"].astype(str).str.strip()

        # Calcular porcentaje disponible de forma segura
        df["cap_total"] = pd.to_numeric(df["cap_total"], errors="coerce").fillna(0)
        df["cap_disp"] = pd.to_numeric(df["cap_disp"], errors="coerce").fillna(0)

        # Evitar división por cero
        df["porcentaje_disponible"] = np.where(
            df["cap_total"] > 0, (df["cap_disp"] / df["cap_total"] * 100), 0
        )

        return df
    except FileNotFoundError:
        st.error(
            "No se encontró el archivo 'data.csv'. Por favor, asegúrate de que esté en el directorio correcto."
        )
        return None
    except Exception as e:
        st.error(f"Error al cargar los datos: {str(e)}")
        return None


# Función para obtener color basado en porcentaje disponible
def get_color(porcentaje):
    """Devuelve color basado en el porcentaje de disponibilidad"""
    if porcentaje <= 20:
        return "#FF0000"  # Rojo
    elif porcentaje <= 40:
        return "#FF6600"  # Naranja
    elif porcentaje <= 60:
        return "#FFFF00"  # Amarillo
    elif porcentaje <= 80:
        return "#99FF00"  # Verde claro
    else:
        return "#00FF00"  # Verde


# Función para calcular el radio del círculo
def calculate_radius(cap_total, min_cap, max_cap, min_radius=5, max_radius=25):
    """Calcula el radio del círculo basado en la capacidad total"""
    if max_cap == min_cap:
        return min_radius
    # Escala logarítmica para mejor visualización
    normalized = (np.log1p(cap_total) - np.log1p(min_cap)) / (np.log1p(max_cap) - np.log1p(min_cap))
    return min_radius + (max_radius - min_radius) * normalized


# Sidebar
# Intentar cargar y mostrar el logo
try:
    if os.path.exists("logo.png"):
        logo = Image.open("logo.png")
        st.sidebar.image(logo, width=200)
    else:
        st.sidebar.info("Logo no encontrado (logo.png)")
except:
    st.sidebar.warning("No se pudo cargar el logo")

# Cargar datos
df = load_data()

if df is not None:
    # Filtros en el sidebar
    st.sidebar.subheader("Filtros")

    # Filtro por provincia
    provincias_unicas = df["provincia"].dropna().unique().tolist()
    provincias = ["Todas"] + sorted([str(p) for p in provincias_unicas if p])
    provincia_seleccionada = st.sidebar.selectbox("Provincia:", provincias)

    # Filtrar datos por provincia
    if provincia_seleccionada != "Todas":
        df_filtrado = df[df["provincia"] == provincia_seleccionada]
    else:
        df_filtrado = df.copy()

    # Filtro por municipio
    municipios_unicos = df_filtrado["municipio"].dropna().unique().tolist()
    municipios = ["Todos"] + sorted([str(m) for m in municipios_unicos if m])
    municipio_seleccionado = st.sidebar.selectbox("Municipio:", municipios)

    if municipio_seleccionado != "Todos":
        df_filtrado = df_filtrado[df_filtrado["municipio"] == municipio_seleccionado]

    # Filtro por tensión (kV)
    kvs_unicos = df_filtrado["kv"].dropna().unique().tolist()
    kvs = ["Todos"] + sorted([str(k) for k in kvs_unicos if pd.notna(k)])
    kv_seleccionado = st.sidebar.selectbox("Tensión (kV):", kvs)

    if kv_seleccionado != "Todos":
        kv_float = float(kv_seleccionado)
        df_filtrado = df_filtrado[df_filtrado["kv"] == kv_float]

    # Filtro por porcentaje de disponibilidad
    st.sidebar.subheader("Rango de Disponibilidad")
    min_disponible, max_disponible = st.sidebar.slider(
        "Porcentaje disponible (%):", min_value=0, max_value=100, value=(0, 100), step=5
    )

    df_filtrado = df_filtrado[
        (df_filtrado["porcentaje_disponible"] >= min_disponible)
        & (df_filtrado["porcentaje_disponible"] <= max_disponible)
    ]

    # Información del dataset filtrado
    st.sidebar.subheader("Estadísticas")
    st.sidebar.metric("Total de puntos", len(df_filtrado))
    if len(df_filtrado) > 0:
        st.sidebar.metric("Capacidad total promedio", f"{df_filtrado['cap_total'].mean():.2f} MVA")
        st.sidebar.metric(
            "Disponibilidad promedio", f"{df_filtrado['porcentaje_disponible'].mean():.1f}%"
        )

    # Leyenda
    st.sidebar.markdown(
        """
    **Colores por disponibilidad:**
    - 🔴 0-20%: Crítico
    - 🟠 21-40%: Bajo
    - 🟡 41-60%: Moderado
    - 🟢 61-80%: Bueno
    - 🟢 81-100%: Excelente
    
    **Tamaño del círculo:**
    Proporcional a la capacidad total (MVA)
    """
    )

    # Crear el mapa principal
    if len(df_filtrado) > 0:
        # Calcular centro del mapa
        center_lat = df_filtrado["lat"].mean()
        center_lon = df_filtrado["lon"].mean()

        # Crear mapa base
        m = folium.Map(location=[center_lat, center_lon], zoom_start=8, tiles="OpenStreetMap")

        # Calcular rangos para el radio
        min_cap = df_filtrado["cap_total"].min()
        max_cap = df_filtrado["cap_total"].max()

        # Agregar marcadores
        for idx, row in df_filtrado.iterrows():
            # Calcular color y radio
            color = get_color(row["porcentaje_disponible"])
            radius = calculate_radius(row["cap_total"], min_cap, max_cap)

            # Crear popup con información
            popup_text = f"""
            <div style="width: 300px;">
                <h4>{row['subestacion']}</h4>
                <hr>
                <b>📍 Ubicación:</b> {row['provincia']}, {row['municipio']}<br>
                <b>🆔 ID Subestación:</b> {row['id_subestacion']}<br>
                <b>⚡ Tensión:</b> {row['kv']} kV<br>
                <b>🔌 Punto de conexión:</b> {row['punto_conexion']}<br>
                <hr>
                <b>📊 Capacidades (MVA):</b><br>
                • Total: {row['cap_total']:.2f}<br>
                • Disponible: {row['cap_disp']:.2f}<br>
                • Comprometida: {row['cap_comp']:.2f}<br>
                • Ocupada: {row['cap_ocup']:.2f}<br>
                • No evaluada: {row['cap_no_eval']:.2f}<br>
                <hr>
                <b>📈 Disponibilidad:</b> {row['porcentaje_disponible']:.1f}%<br>
                {f"<b>💬 Comentario:</b> {row['comentario']}<br>" if pd.notna(row['comentario']) and row['comentario'] != '' else ""}
            </div>
            """

            # Agregar círculo al mapa
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=radius,
                popup=folium.Popup(popup_text, max_width=350),
                color="black",
                weight=1,
                fillColor=color,
                fillOpacity=0.7,
                tooltip=f"{row['subestacion']} - {row['porcentaje_disponible']:.1f}% disponible",
            ).add_to(m)

        # Agregar plugin de pantalla completa
        plugins.Fullscreen().add_to(m)

        # Mostrar el mapa
        st.title("Mapa de Subestaciones Eléctricas")

        # Información sobre los filtros aplicados
        if (
            provincia_seleccionada != "Todas"
            or municipio_seleccionado != "Todos"
            or kv_seleccionado != "Todos"
        ):
            filtros_activos = []
            if provincia_seleccionada != "Todas":
                filtros_activos.append(f"Provincia: {provincia_seleccionada}")
            if municipio_seleccionado != "Todos":
                filtros_activos.append(f"Municipio: {municipio_seleccionado}")
            if kv_seleccionado != "Todos":
                filtros_activos.append(f"Tensión: {kv_seleccionado} kV")

            st.info(f"🔍 Filtros activos: {' | '.join(filtros_activos)}")

        # Mostrar mapa con altura ajustada
        map_data = st_folium(m, width=None, height=600, returned_objects=["last_object_clicked"])

        # Mostrar información del punto clickeado
        if map_data["last_object_clicked"]:
            clicked_lat = map_data["last_object_clicked"]["lat"]
            clicked_lon = map_data["last_object_clicked"]["lng"]

            # Encontrar el punto más cercano
            df_filtrado["distancia"] = np.sqrt(
                (df_filtrado["lat"] - clicked_lat) ** 2 + (df_filtrado["lon"] - clicked_lon) ** 2
            )
            punto_cercano = df_filtrado.loc[df_filtrado["distancia"].idxmin()]

            st.subheader(f"📍 Información detallada: {punto_cercano['subestacion']}")

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(label="Capacidad Total", value=f"{punto_cercano['cap_total']:.2f} MVA")
                st.metric(label="Tensión", value=f"{punto_cercano['kv']} kV")

            with col2:
                st.metric(
                    label="Disponibilidad", value=f"{punto_cercano['porcentaje_disponible']:.1f}%"
                )
                st.metric(label="Cap. Disponible", value=f"{punto_cercano['cap_disp']:.2f} MVA")

            with col3:
                st.metric(label="Cap. Ocupada", value=f"{punto_cercano['cap_ocup']:.2f} MVA")
                st.metric(label="Ubicación", value=f"{punto_cercano['municipio']}")

    else:
        st.warning("⚠️ No hay datos que coincidan con los filtros seleccionados.")
        st.info("Intenta ajustar los filtros en el panel lateral.")

else:
    st.error(
        "❌ No se pudieron cargar los datos. Verifica que el archivo 'data.csv' esté presente."
    )
    st.info(
        "📋 El archivo debe tener las siguientes columnas: provincia, municipio, lat, lon, subestacion, kv, cap_total, cap_disp, cap_ocup, porcentaje_disponible, etc."
    )

# Footer
st.markdown("---")
st.markdown("🔧 **Mapa de Capacidad de Demanda** | Desarrollado por Plusenergy")
