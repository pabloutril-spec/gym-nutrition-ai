import io
import time
import requests
import streamlit as st
from google import genai
from PIL import Image

# 1. Configuración de página
st.set_page_config(
    page_title="YIM – Smart Gym Nutrition",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Configuración API
MI_API_KEY = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=MI_API_KEY)
MODELO_ACTUAL = "gemini-3.5-flash-lite"

# 3. Inyección de CSS para Diseño Dark Premium & Cyber Fitness
st.markdown("""
<style>
    /* Estilos globales y fondo oscuro */
    .stApp {
        background-color: #0b0f19;
        color: #f1f5f9;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Barra lateral */
    section[data-testid="stSidebar"] {
        background-color: #111827 !important;
        border-right: 1px solid #1f2937;
    }

    /* Título principal con degradado neón */
    .hero-title {
        font-size: 2.6rem;
        font-weight: 800;
        letter-spacing: -0.04em;
        background: linear-gradient(135deg, #00FF87 0%, #60EFFF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .hero-subtitle {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-bottom: 1.8rem;
        font-weight: 400;
    }

    /* Tarjetas de Métricas estilo Glassmorphism */
    div[data-testid="stMetric"] {
        background: rgba(31, 41, 55, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 12px 18px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        backdrop-filter: blur(8px);
    }
    div[data-testid="stMetricLabel"] {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetricValue"] {
        color: #00FF87 !important;
        font-weight: 700 !important;
    }

    /* Botones primarios de alto impacto */
    div.stButton > button:first-child {
        background: linear-gradient(135deg, #00FF87 0%, #00c96b 100%) !important;
        color: #05140d !important;
        font-weight: 700 !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.6rem 1.8rem !important;
        transition: all 0.25s ease !important;
        box-shadow: 0 0 15px rgba(0, 255, 135, 0.25) !important;
    }
    div.stButton > button:first-child:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 0 25px rgba(0, 255, 135, 0.5) !important;
    }

    /* Caja de reporte IA */
    .report-box {
        background: #131b2e;
        border-left: 4px solid #00FF87;
        border-radius: 0 12px 12px 0;
        padding: 20px 24px;
        margin-top: 15px;
        margin-bottom: 20px;
        line-height: 1.6;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.4);
    }

    /* Inputs, selectbox y sliders oscuros */
    .stTextInput input, .stNumberInput input {
        background-color: #1a2234 !important;
        color: #ffffff !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #00FF87 !important;
        box-shadow: 0 0 0 1px #00FF87 !important;
    }
</style>
""", unsafe_allow_html=True)

# Función con reintentos para estabilidad de API
def generar_con_reintento(contents, reintentos=3, espera=2):
    for intento in range(reintentos):
        try:
            response = client.models.generate_content(
                model=MODELO_ACTUAL,
                contents=contents,
            )
            return response.text
        except Exception as e:
            if "503" in str(e) and intento < reintentos - 1:
                time.sleep(espera)
                continue
            return f"Error al generar reporte: {e}"

# --- BARRA LATERAL: PERFIL FITNESS ---
with st.sidebar:
    st.markdown("### ⚡ **Tu Perfil Fitness**")
    st.caption("Métricas clave que calibran las sugerencias de la IA.")
    
    peso = st.number_input("Peso corporal actual (kg):", min_value=40.0, max_value=160.0, value=74.0, step=0.5)
    fase = st.selectbox(
        "Fase de entrenamiento:",
        ["Ganar masa muscular (Volumen)", "Pérdida de grasa (Definición)", "Mantenimiento / Recomposición"]
    )
    actividad = st.select_slider(
        "Nivel de actividad:",
        options=["Sedentario (1-2 días)", "Moderado (3-4 días)", "Intenso (5-6 días)", "Muy intenso (doble sesión)"],
        value="Moderado (3-4 días)"
    )
    
    multiplicador_prot = 2.2 if "Volumen" in fase else (2.4 if "Definición" in fase else 2.0)
    prot_objetivo = round(peso * multiplicador_prot)
    
    st.divider()
    st.markdown("<p style='color:#94a3b8; font-size:0.85rem; font-weight:600;'>META DIARIA SUGERIDA</p>", unsafe_allow_html=True)
    st.metric(label="Proteína diaria", value=f"{prot_objetivo} g")
    st.caption(f"Ratio: {multiplicador_prot} g de proteína / kg")

perfil_contexto = f"Perfil del usuario: Peso {peso}kg, Objetivo: {fase}, Nivel de actividad: {actividad}, Meta de proteína: {prot_objetivo}g/día."

# --- SERVICIOS Y FUNCIONES ---
@st.cache_data(ttl=86400)
def consultar_open_food_facts(codigo_barras):
    url = f"https://world.openfoodfacts.org/api/v0/product/{codigo_barras}.json"
    headers = {"User-Agent": "YIM-SmartNutrition - App - Version 1.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if data.get("status") == 1:
            prod = data.get("product", {})
            nutriments = prod.get("nutriments", {})
            return {
                "encontrado": True,
                "producto": prod.get("product_name", "Desconocido"),
                "marca": prod.get("brands", "Marca no especificada"),
                "calorias_100g": nutriments.get("energy-kcal_100g", 0),
                "proteinas_100g": nutriments.get("proteins_100g", 0),
                "carbohidratos_100g": nutriments.get("carbohydrates_100g", 0),
                "grasas_100g": nutriments.get("fat_100g", 0),
                "ingredientes": prod.get("ingredients_text", "No disponibles"),
            }
        return {"encontrado": False}
    except Exception:
        return {"encontrado": False}

def analizar_datos_ia(datos, objetivo_usuario, precio=None, peso_total=None):
    extra_precio = ""
    if precio and peso_total:
        prot_totales = (datos["proteinas_100g"] / 100) * peso_total
        coste_por_gramo_prot = precio / prot_totales if prot_totales > 0 else 0
        extra_precio = f"\n- Precio: {precio:.2f}€ por {peso_total}g. Coste por gramo de proteína: {coste_por_gramo_prot:.3f}€/g"

    prompt = f"""
Eres un entrenador y nutricionista deportivo de élite.
{perfil_contexto}

Analiza este producto para usuarios de gimnasio con criterio estricto y profesional:
- Producto: {datos['producto']} ({datos['marca']})
- Calorías (100g): {datos['calorias_100g']} kcal
- Proteínas (100g): {datos['proteinas_100g']} g
- Carbohidratos (100g): {datos['carbohidratos_100g']} g
- Grasas (100g): {datos['grasas_100g']} g
- Ingredientes: {datos['ingredientes']}
{extra_precio}

Estructura el dictamen con formato markdown claro:
1. ⭐ **Calificación Fitness (1 a 10)**: con justificación directa.
2. 🎯 **Ajuste a tus Macros**: gramos o porción sugerida respecto a su objetivo de {prot_objetivo}g diarios de proteína.
3. 🔬 **Análisis de Ingredientes y Fuentes Proteicas**: biodisponibilidad y calidad.
4. 💰 **Rentabilidad Proteica** (si aplica).
5. 📌 **Veredicto Final**.
"""
    return generar_con_reintento(prompt)

def analizar_foto_ia(imagen_pil, objetivo_usuario):
    img = imagen_pil.convert("RGB")
    img.thumbnail((700, 700))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    buffer.seek(0)
    img_ligera = Image.open(buffer)

    prompt = f"""
Eres un nutricionista y preparador físico deportivo.
{perfil_contexto}

Examina esta imagen de producto, tabla nutricional o etiqueta:
1. Estima o extrae los macros principales por 100g o ración.
2. Da una **Calificación Fitness del 1 al 10** adaptada a su meta ({objetivo_usuario}).
3. Recomienda una **porción exacta** para encajar en su objetivo proteico de {prot_objetivo}g/día.
4. Evalúa de forma crítica la calidad de ingredientes (azúcares añadidos, aceites refinados, aditivos).
5. Veredicto final rápido.
"""
    return generar_con_reintento([prompt, img_ligera])

def comparar_productos_ia(prod_a, prod_b, objetivo_usuario):
    prompt = f"""
Actúa como nutricionista de alto rendimiento.
{perfil_contexto}

Compara estos dos productos y declara un ganador categórico para {objetivo_usuario}:
A: {prod_a['nombre']} ({prod_a['marca']}) | Macros: {prod_a['kcal']} kcal, P:{prod_a['prot']}g, C:{prod_a['carb']}g, G:{prod_a['grasas']}g | Coste: {prod_a['coste_prot']}
B: {prod_b['nombre']} ({prod_b['marca']}) | Macros: {prod_b['kcal']} kcal, P:{prod_b['prot']}g, C:{prod_b['carb']}g, G:{prod_b['grasas']}g | Coste: {prod_b['coste_prot']}

Responde con:
1. 🏆 **Ganador Indiscutible**
2. 🥊 **Comparativa Directa**
3. 💡 **Estrategia de Consumo**
"""
    return generar_con_reintento(prompt)

# --- CABECERA PRINCIPAL ---
st.markdown('<div class="hero-title">⚡ YIM – Smart Gym Nutrition</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Inteligencia artificial aplicada a tu nutrición, rendimiento y objetivos de gimnasio.</div>', unsafe_allow_html=True)

herramienta = st.radio(
    "Selecciona herramienta:",
    ["🔍 Código de Barras", "📷 Foto de Etiqueta", "⚔️ Cara a Cara"],
    horizontal=True,
)

st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

# 1. CÓDIGO DE BARRAS
if herramienta == "🔍 Código de Barras":
    codigo = st.text_input("Código de barras del producto:", value="3017620422003")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        precio_input = st.number_input("Precio (€) [Opcional]:", min_value=0.0, value=0.0, step=0.1)
    with col_p2:
        peso_input = st.number_input("Peso total (g) [Opcional]:", min_value=0.0, value=0.0, step=10.0)

    if st.button("Analizar con YIM", type="primary"):
        with st.spinner("Procesando datos nutricionales con IA..."):
            info = consultar_open_food_facts(codigo)
            if info["encontrado"]:
                st.markdown(f"### **{info['producto']}** <span style='color:#94a3b8; font-size:1.1rem;'>({info['marca']})</span>", unsafe_allow_html=True)
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Calorías (100g)", f"{info['calorias_100g']} kcal")
                m2.metric("Proteínas", f"{info['proteinas_100g']} g")
                m3.metric("Carbohidratos", f"{info['carbohidratos_100g']} g")
                m4.metric("Grasas", f"{info['grasas_100g']} g")

                dictamen = analizar_datos_ia(info, fase, precio_input, peso_input)
                st.markdown(f"<div class='report-box'>{dictamen}</div>", unsafe_allow_html=True)

                st.download_button(
                    label="📥 Descargar Informe (.md)",
                    data=f"# YIM Nutrition Report: {info['producto']}\n\n{dictamen}",
                    file_name=f"yim_reporte_{codigo}.md",
                    mime="text/markdown",
                )
            else:
                st.error("No se localizó el producto en la base de datos.")

# 2. FOTO DE ETIQUETA
elif herramienta == "📷 Foto de Etiqueta":
    st.write("Sube o fotografía la etiqueta, ingredientes o tabla de macros del alimento.")
    archivo_foto = st.file_uploader("Subir imagen...", type=["jpg", "jpeg", "png", "webp"])

    if archivo_foto:
        img_subida = Image.open(archivo_foto)
        st.image(img_subida, caption="Imagen cargada", width=260)

        if st.button("Escanear Etiqueta con YIM", type="primary"):
            with st.spinner("Decodificando etiqueta con Visión Artificial..."):
                dictamen = analizar_foto_ia(img_subida, fase)
                st.markdown(f"<div class='report-box'>{dictamen}</div>", unsafe_allow_html=True)
                
                st.download_button(
                    label="📥 Descargar Análisis (.md)",
                    data=f"# YIM - Análisis de Etiqueta\n\n{dictamen}",
                    file_name="yim_analisis_foto.md",
                    mime="text/markdown",
                )

# 3. CARA A CARA
elif herramienta == "⚔️ Cara a Cara":
    st.write("Compara dos alimentos y descubre cuál optimiza mejor tus macros e inversión económica.")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### **Producto A**")
        cod_a = st.text_input("Código de barras A:", key="cb_a")
        pr_a = st.number_input("Precio (€) A:", min_value=0.0, step=0.1, key="pr_a")
        pe_a = st.number_input("Peso neto (g) A:", min_value=0.0, step=10.0, key="pe_a")

    with c2:
        st.markdown("#### **Producto B**")
        cod_b = st.text_input("Código de barras B:", key="cb_b")
        pr_b = st.number_input("Precio (€) B:", min_value=0.0, step=0.1, key="pr_b")
        pe_b = st.number_input("Peso neto (g) B:", min_value=0.0, step=10.0, key="pe_b")

    if st.button("Enfrentar Productos", type="primary"):
        if cod_a and cod_b:
            with st.spinner("Comparando y calculando rentabilidad proteica..."):
                datos_a = consultar_open_food_facts(cod_a)
                datos_b = consultar_open_food_facts(cod_b)

                if datos_a["encontrado"] and datos_b["encontrado"]:
                    def calc_coste(d, pr, pe):
                        if pr > 0 and pe > 0:
                            p_tot = (d["proteinas_100g"] / 100) * pe
                            return f"{(pr / p_tot):.3f} €/g" if p_tot > 0 else "N/A"
                        return "No calculado"

                    res_a = {
                        "nombre": datos_a["producto"], "marca": datos_a["marca"],
                        "kcal": datos_a["calorias_100g"], "prot": datos_a["proteinas_100g"],
                        "carb": datos_a["carbohidratos_100g"], "grasas": datos_a["grasas_100g"],
                        "coste_prot": calc_coste(datos_a, pr_a, pe_a),
                        "ingredientes": datos_a["ingredientes"]
                    }
                    res_b = {
                        "nombre": datos_b["producto"], "marca": datos_b["marca"],
                        "kcal": datos_b["calorias_100g"], "prot": datos_b["proteinas_100g"],
                        "carb": datos_b["carbohidratos_100g"], "grasas": datos_b["grasas_100g"],
                        "coste_prot": calc_coste(datos_b, pr_b, pe_b),
                        "ingredientes": datos_b["ingredientes"]
                    }

                    col_r1, col_r2 = st.columns(2)
                    with col_r1:
                        st.info(f"**{res_a['nombre']}** ({res_a['marca']})\n\n"
                                f"🥩 Proteína: {res_a['prot']}g | 🔥 {res_a['kcal']} kcal\n\n"
                                f"💵 Coste prot: {res_a['coste_prot']}")
                    with col_r2:
                        st.info(f"**{res_b['nombre']}** ({res_b['marca']})\n\n"
                                f"🥩 Proteína: {res_b['prot']}g | 🔥 {res_b['kcal']} kcal\n\n"
                                f"💵 Coste prot: {res_b['coste_prot']}")

                    dictamen = comparar_productos_ia(res_a, res_b, fase)
                    st.markdown(f"<div class='report-box'>{dictamen}</div>", unsafe_allow_html=True)
                else:
                    st.error("No se pudo obtener información de ambos productos.")
        else:
            st.warning("Introduce los dos códigos de barras para comenzar.")
