import io
import time
import requests
import streamlit as st
from google import genai
from PIL import Image

# Configuración básica de página
st.set_page_config(page_title="Gym Nutrition AI", page_icon="🏋️", layout="wide")

# Configuración del cliente Gemini API con secrets
MI_API_KEY = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=MI_API_KEY)

MODELO_ACTUAL = "gemini-3.5-flash-lite"

# Función auxiliar con reintento automático para evitar el error 503
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

# --- BARRA LATERAL: PERFIL FITNESS Y CALCULADORA DE MACROS ---
with st.sidebar:
    st.header("⚙️ Tu Perfil Fitness")
    st.caption("Ajusta tus parámetros para obtener recomendaciones de porciones exactas.")
    
    peso = st.number_input("Tu peso actual (kg):", min_value=40.0, max_value=160.0, value=74.0, step=0.5)
    fase = st.selectbox(
        "Fase de entrenamiento:",
        ["Ganar masa muscular (Volumen)", "Pérdida de grasa (Definición)", "Mantenimiento / Recomposición"]
    )
    actividad = st.select_slider(
        "Nivel de actividad semanal:",
        options=["Sedentario (1-2 días)", "Moderado (3-4 días)", "Intenso (5-6 días)", "Muy intenso (doble sesión)"],
        value="Moderado (3-4 días)"
    )
    
    # Cálculo base de referencia de macros
    multiplicador_prot = 2.2 if "Volumen" in fase else (2.4 if "Definición" in fase else 2.0)
    prot_objetivo = round(peso * multiplicador_prot)
    
    st.divider()
    st.markdown("**Meta diaria estimada:**")
    st.metric(label="Proteína sugerida", value=f"{prot_objetivo} g / día")
    st.caption(f"Calculado a {multiplicador_prot} g de proteína por kg de peso corporal.")

perfil_contexto = f"Perfil del usuario: Peso {peso}kg, Objetivo: {fase}, Nivel de actividad: {actividad}, Meta de proteína diaria estimada: {prot_objetivo}g."

# --- FUNCIONES DE ANÁLISIS ---

@st.cache_data(ttl=86400)
def consultar_open_food_facts(codigo_barras):
    url = f"https://world.openfoodfacts.org/api/v0/product/{codigo_barras}.json"
    headers = {"User-Agent": "YIM – Smart Gym Nutrition - App - Version 1.0"}
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
        extra_precio = f"\n- Precio del producto: {precio:.2f}€ por {peso_total}g.\n- Coste estimado por gramo de proteína: {coste_por_gramo_prot:.3f}€/g"

    prompt = f"""
Eres un entrenador y nutricionista deportivo de alto nivel.
{perfil_contexto}

Analiza este producto de forma directa y crítica considerando el perfil y objetivo del usuario:
- Producto: {datos['producto']} ({datos['marca']})
- Calorías (100g): {datos['calorias_100g']} kcal
- Proteínas (100g): {datos['proteinas_100g']} g
- Carbohidratos (100g): {datos['carbohidratos_100g']} g
- Grasas (100g): {datos['grasas_100g']} g
- Ingredientes: {datos['ingredientes']}
{extra_precio}

Estructura tu reporte con emojis y títulos claros:
1. ⭐ Calificación fitness del 1 al 10 (específica para su objetivo).
2. 🎯 Ajuste a sus macros (cuántos gramos o porción recomendarías consumir según su meta de {prot_objetivo}g de proteína al día).
3. 🔬 Evaluación nutricional y de calidad de macros e ingredientes.
4. 💰 Rentabilidad / Precio por gramo de proteína (si aplica).
5. 📌 Veredicto final breve.
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
Eres un entrenador y nutricionista deportivo.
{perfil_contexto}

Examina esta fotografía de un alimento, suplemento o etiqueta nutricional.
1. Extrae o estima los valores clave por 100g o por ración (Calorías, Proteínas, Carbohidratos, Grasas).
2. Da una calificación fitness del 1 al 10 adaptada al objetivo: {objetivo_usuario}.
3. 🎯 Porción recomendada: Indícale cuántos gramos o porción consumir para encajar en su requerimiento diario de {prot_objetivo}g de proteína.
4. Realiza una evaluación crítica de la calidad de sus ingredientes y fuentes de proteína.
5. Veredicto final: si vale la pena o si hay mejores alternativas.
"""
    return generar_con_reintento([prompt, img_ligera])

def comparar_productos_ia(prod_a, prod_b, objetivo_usuario):
    prompt = f"""
Actúa como nutricionista de alto rendimiento.
{perfil_contexto}

Compara estos dos productos y elige un único ganador para la fase de '{objetivo_usuario}':

PRODUCTO A:
- Nombre: {prod_a['nombre']} ({prod_a['marca']})
- Macros (100g): {prod_a['kcal']} kcal | P: {prod_a['prot']}g | C: {prod_a['carb']}g | G: {prod_a['grasas']}g
- Coste por gramo de proteína: {prod_a['coste_prot']}
- Ingredientes: {prod_a['ingredientes']}

PRODUCTO B:
- Nombre: {prod_b['nombre']} ({prod_b['marca']})
- Macros (100g): {prod_b['kcal']} kcal | P: {prod_b['prot']}g | C: {prod_b['carb']}g | G: {prod_b['grasas']}g
- Coste por gramo de proteína: {prod_b['coste_prot']}
- Ingredientes: {prod_b['ingredientes']}

Responde con:
1. 🏆 Ganador indiscutible.
2. 🥊 Comparativa directa (calidad de proteína, pureza de ingredientes y rentabilidad).
3. 💡 Recomendación práctica para integrarlo en su dieta diaria.
"""
    return generar_con_reintento(prompt)

# --- INTERFAZ PRINCIPAL ---

st.title("🏋️ Gym Nutrition AI")

herramienta = st.radio(
    "Selecciona herramienta:",
    ["🔍 Código de Barras", "📷 Foto de Etiqueta", "⚔️ Cara a Cara"],
    horizontal=True,
)

if herramienta == "🔍 Código de Barras":
    codigo = st.text_input("Código de barras:", value="3017620422003")
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        precio_input = st.number_input("Precio del envase (€) [Opcional]:", min_value=0.0, value=0.0, step=0.1)
    with col_p2:
        peso_input = st.number_input("Peso total (gramos) [Opcional]:", min_value=0.0, value=0.0, step=10.0)

    if st.button("Analizar Producto", type="primary"):
        with st.spinner("Buscando y evaluando con IA..."):
            info = consultar_open_food_facts(codigo)
            if info["encontrado"]:
                st.subheader(f"{info['producto']} - {info['marca']}")
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Calorías", f"{info['calorias_100g']} kcal")
                c2.metric("Proteínas", f"{info['proteinas_100g']} g")
                c3.metric("Carbohidratos", f"{info['carbohidratos_100g']} g")
                c4.metric("Grasas", f"{info['grasas_100g']} g")

                dictamen = analizar_datos_ia(info, fase, precio_input, peso_input)
                st.markdown("### 📋 Dictamen del Entrenador IA")
                st.markdown(dictamen)

                st.download_button(
                    label="📥 Descargar Reporte (.md)",
                    data=f"# Reporte: {info['producto']}\n\n{dictamen}",
                    file_name=f"reporte_{codigo}.md",
                    mime="text/markdown",
                )
            else:
                st.error("Producto no encontrado en la base de datos de Open Food Facts.")

elif herramienta == "📷 Foto de Etiqueta":
    st.write("Sube una foto clara de la etiqueta nutricional, envase o tabla de ingredientes.")
    archivo_foto = st.file_uploader("Elige una foto...", type=["jpg", "jpeg", "png", "webp"])

    if archivo_foto:
        img_subida = Image.open(archivo_foto)
        st.image(img_subida, caption="Imagen cargada", width=250)

        if st.button("Escanear y Analizar Etiqueta", type="primary"):
            with st.spinner("Analizando la imagen y calculando ración ideal..."):
                dictamen = analizar_foto_ia(img_subida, fase)
                st.markdown("### 📋 Dictamen de la Etiqueta")
                st.markdown(dictamen)

                st.download_button(
                    label="📥 Descargar Análisis de Etiqueta (.md)",
                    data=f"# Análisis de Etiqueta\n\n{dictamen}",
                    file_name="analisis_etiqueta.md",
                    mime="text/markdown",
                )

elif herramienta == "⚔️ Cara a Cara":
    st.write("Compara dos productos para saber cuál te conviene comprar según tus objetivos.")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Producto A")
        cod_a = st.text_input("Código de barras A:", key="cb_a")
        pr_a = st.number_input("Precio (€) A:", min_value=0.0, step=0.1, key="pr_a")
        pe_a = st.number_input("Peso neto (g) A:", min_value=0.0, step=10.0, key="pe_a")

    with col2:
        st.subheader("Producto B")
        cod_b = st.text_input("Código de barras B:", key="cb_b")
        pr_b = st.number_input("Precio (€) B:", min_value=0.0, step=0.1, key="pr_b")
        pe_b = st.number_input("Peso neto (g) B:", min_value=0.0, step=10.0, key="pe_b")

    if st.button("Comparar Ambos Productos", type="primary"):
        if cod_a and cod_b:
            with st.spinner("Extrayendo datos y enfrentando productos..."):
                datos_a = consultar_open_food_facts(cod_a)
                datos_b = consultar_open_food_facts(cod_b)

                if datos_a["encontrado"] and datos_b["encontrado"]:
                    def calc_coste(d, pr, pe):
                        if pr > 0 and pe > 0:
                            p_tot = (d["proteinas_100g"] / 100) * pe
                            return f"{(pr / p_tot):.3f} €/g" if p_tot > 0 else "N/A"
                        return "No calculado"

                    resumen_a = {
                        "nombre": datos_a["producto"], "marca": datos_a["marca"],
                        "kcal": datos_a["calorias_100g"], "prot": datos_a["proteinas_100g"],
                        "carb": datos_a["carbohidratos_100g"], "grasas": datos_a["grasas_100g"],
                        "coste_prot": calc_coste(datos_a, pr_a, pe_a),
                        "ingredientes": datos_a["ingredientes"]
                    }
                    resumen_b = {
                        "nombre": datos_b["producto"], "marca": datos_b["marca"],
                        "kcal": datos_b["calorias_100g"], "prot": datos_b["proteinas_100g"],
                        "carb": datos_b["carbohidratos_100g"], "grasas": datos_b["grasas_100g"],
                        "coste_prot": calc_coste(datos_b, pr_b, pe_b),
                        "ingredientes": datos_b["ingredientes"]
                    }

                    c_res1, c_res2 = st.columns(2)
                    with c_res1:
                        st.info(f"**{resumen_a['nombre']}** ({resumen_a['marca']})\n\n"
                                f"🥩 Proteínas: {resumen_a['prot']}g | 🔥 {resumen_a['kcal']} kcal\n\n"
                                f"💵 Coste prot: {resumen_a['coste_prot']}")
                    with c_res2:
                        st.info(f"**{resumen_b['nombre']}** ({resumen_b['marca']})\n\n"
                                f"🥩 Proteínas: {resumen_b['prot']}g | 🔥 {resumen_b['kcal']} kcal\n\n"
                                f"💵 Coste prot: {resumen_b['coste_prot']}")

                    st.divider()
                    dictamen = comparar_productos_ia(resumen_a, resumen_b, fase)
                    st.markdown("### 🏆 Decisión del Entrenador IA")
                    st.markdown(dictamen)

                    st.download_button(
                        label="📥 Descargar Comparativa (.md)",
                        data=f"# Comparativa: {resumen_a['nombre']} VS {resumen_b['nombre']}\n\n{dictamen}",
                        file_name="comparativa_nutricional.md",
                        mime="text/markdown",
                    )
                else:
                    st.error("Uno o ambos códigos de barras no se encontraron.")
        else:
            st.warning("Introduce los dos códigos de barras para comparar.")
