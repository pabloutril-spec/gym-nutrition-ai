import io
import requests
import streamlit as st
from PIL import Image
from google import genai

st.set_page_config(page_title="Gym Nutrition AI", page_icon="🏋️", layout="wide")

MI_API_KEY = st.secrets["GEMINI_API_KEY"]
client = genai.Client(api_key=MI_API_KEY)

@st.cache_data(show_spinner=False)
def buscar_nutricion(codigo_barras):
    url = f"https://world.openfoodfacts.org/api/v0/product/{codigo_barras}.json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=8)
    except Exception as e:
        return None, f"Error de conexión: {e}"
        
    if response.status_code != 200:
        return None, "Error al contactar con la base de datos."
        
    data = response.json()
    if data.get("status") == 0:
        return None, f"Producto con código {codigo_barras} no encontrado."
        
    prod = data.get("product", {})
    nutri = prod.get("nutriments", {})
    
    def limpiar_num(valor):
        try:
            return round(float(valor), 1)
        except (ValueError, TypeError):
            return 0.0

    info = {
        "producto": prod.get("product_name", "Desconocido"),
        "marca": prod.get("brands", "Desconocida"),
        "imagen": prod.get("image_url", None),
        "calorias_100g": limpiar_num(nutri.get("energy-kcal_100g", 0)),
        "proteinas_100g": limpiar_num(nutri.get("proteins_100g", 0)),
        "grasas_100g": limpiar_num(nutri.get("fat_100g", 0)),
        "carbohidratos_100g": limpiar_num(nutri.get("carbohydrates_100g", 0)),
        "ingredientes": prod.get("ingredients_text", "No especificados")
    }
    return info, None

def analizar_datos_ia(datos, precio_producto=None, peso_total_g=None):
    extra_precio = ""
    if precio_producto and peso_total_g and peso_total_g > 0:
        gramos_proteina_totales = (datos['proteinas_100g'] / 100) * peso_total_g
        coste_por_g_prot = (precio_producto / gramos_proteina_totales) if gramos_proteina_totales > 0 else 0
        extra_precio = f"""
        - Precio total: {precio_producto} €
        - Peso del envase: {peso_total_g} g
        - Proteína total en envase: {round(gramos_proteina_totales, 1)} g
        - Coste estimado por gramo de proteína: {round(coste_por_g_prot, 4)} €/g
        """

    prompt = f"""
    Eres un entrenador y nutricionista deportivo de alto nivel.
    Analiza este producto de forma directa y crítica para usuarios de gimnasio:
    - Producto: {datos['producto']} ({datos['marca']})
    - Calorías (100g): {datos['calorias_100g']} kcal
    - Proteínas (100g): {datos['proteinas_100g']} g
    - Carbohidratos (100g): {datos['carbohidratos_100g']} g
    - Grasas (100g): {datos['grasas_100g']} g
    - Ingredientes: {datos['ingredientes']}
    {extra_precio}

    Estructura tu reporte con emojis y títulos claros:
    1. ⭐️ Calificación fitness del 1 al 10.
    2. 🎯 Objetivo óptimo (Volumen, Definición o Evitar).
    3. 📊 Evaluación nutricional y de calidad de macros.
    4. 💰 Rentabilidad / Precio por gramo de proteína (si aplica).
    5. 📌 Veredicto final breve.
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error al generar reporte: {e}"

def analizar_foto_ia(imagen_pil, objetivo_usuario):
    img = imagen_pil.convert("RGB")
    img.thumbnail((700, 700))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80)
    buffer.seek(0)
    img_ligera = Image.open(buffer)

    prompt = f"""
    Eres un entrenador y nutricionista deportivo.
    Examina esta fotografía de un alimento, suplemento o etiqueta nutricional.
    Objetivo del usuario: {objetivo_usuario}.
    
    1. Identifica el producto y transcribe los macros aproximados (Calorías, Proteínas, Carbohidratos, Grasas).
    2. Calificación fitness del 1 al 10 para su objetivo ({objetivo_usuario}).
    3. Evaluación crítica de ingredientes (fuente de proteína, azúcares, calidad).
    4. Veredicto final breve.
    """

    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[img_ligera, prompt],
        )
        return response.text
    except Exception as e:
        return f"Error al analizar la imagen: {e}"

def comparar_productos_ia(prod_a, prod_b, obj):
    prompt = f"""
    Eres un entrenador y nutricionista deportivo. Compara breve y directamente estos dos productos para un atleta cuyo objetivo es: {obj}.

    PRODUCTO A: {prod_a['nombre']} ({prod_a['marca']})
    - Macros por 100g: {prod_a['kcal']} kcal | P: {prod_a['prot']}g | C: {prod_a['carb']}g | G: {prod_a['grasas']}g
    - Coste por gramo de proteína: {prod_a['coste_prot']}

    PRODUCTO B: {prod_b['nombre']} ({prod_b['marca']})
    - Macros por 100g: {prod_b['kcal']} kcal | P: {prod_b['prot']}g | C: {prod_b['carb']}g | G: {prod_b['grasas']}g
    - Coste por gramo de proteína: {prod_b['coste_prot']}

    Estructura la respuesta de forma directa:
    1. 🥊 Comparativa nutricional rápida (densidad de proteína vs calorías).
    2. 💰 Rentabilidad / Precio.
    3. 🏆 Ganador claro para {obj} y justificación en 2 frases.
    """
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )
        return response.text
    except Exception as e:
        return f"Error en la IA: {e}"

# --- INTERFAZ STREAMLIT ---
st.title("🏋️ Gym Nutrition AI")

modo = st.radio("Selecciona herramienta:", ["🔍 Código de Barras", "📷 Foto de Etiqueta", "⚔️ Cara a Cara"], horizontal=True)

if modo == "🔍 Código de Barras":
    codigo = st.text_input("Código de barras:", value="3017620422003")
    col1, col2 = st.columns(2)
    with col1:
        precio = st.number_input("Precio del envase (€) [Opcional]:", min_value=0.0, value=0.0, step=0.10)
    with col2:
        peso = st.number_input("Peso total (gramos) [Opcional]:", min_value=0.0, value=0.0, step=50.0)

    if st.button("Analizar Producto", type="primary"):
        with st.spinner("Buscando en base de datos y consultando a la IA..."):
            datos, error = buscar_nutricion(codigo.strip())
            
            if error:
                st.error(error)
            else:
                st.subheader(f"{datos['producto']} - {datos['marca']}")
                if datos['imagen']:
                    st.image(datos['imagen'], width=180)
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Calorías (100g)", f"{datos['calorias_100g']} kcal")
                m2.metric("Proteínas", f"{datos['proteinas_100g']} g")
                m3.metric("Carbohidratos", f"{datos['carbohidratos_100g']} g")
                m4.metric("Grasas", f"{datos['grasas_100g']} g")
                
                st.divider()
                st.markdown("### 🤖 Veredicto del Entrenador IA")
                informe = analizar_datos_ia(datos, precio if precio > 0 else None, peso if peso > 0 else None)
                st.markdown(informe)
                
                st.download_button(
                    label="📥 Descargar Ficha Técnica (.md)",
                    data=f"# Ficha Nutricional: {datos['producto']}\n\n" + informe,
                    file_name=f"informe_{codigo.strip()}.md",
                    mime="text/markdown"
                )

elif modo == "📷 Foto de Etiqueta":
    st.write("Sube una foto clara de la etiqueta nutricional, envase o tabla de ingredientes.")
    objetivo = st.selectbox("Tu objetivo principal:", ["Ganar masa muscular (Volumen)", "Perder grasa (Definición)", "Salud general y rendimiento"])
    archivo_foto = st.file_uploader("Elige una foto...", type=["jpg", "jpeg", "png", "webp"])
    
    if archivo_foto:
        img = Image.open(archivo_foto)
        st.image(img, caption="Imagen cargada", width=250)
        
        if st.button("Escanear y Analizar Etiqueta", type="primary"):
            with st.spinner("Leyendo macros y preparando dictamen técnico..."):
                resultado_foto = analizar_foto_ia(img, objetivo)
                st.divider()
                st.markdown("### 🤖 Dictamen de la Etiqueta")
                st.markdown(resultado_foto)
                
                st.download_button(
                    label="📥 Descargar Análisis de Etiqueta (.md)",
                    data=f"# Análisis de Etiqueta Nutricional\n\nObjetivo: {objetivo}\n\n" + resultado_foto,
                    file_name="analisis_etiqueta.md",
                    mime="text/markdown"
                )

else:
    st.subheader("⚔️ Comparador directo de dos productos")
    obj_comp = st.selectbox("Objetivo para la comparación:", ["Ganar masa muscular (Volumen)", "Perder grasa (Definición)", "Mejor relación calidad/precio"])
    
    c_izq, c_der = st.columns(2)
    
    with c_izq:
        st.markdown("### 📦 Producto A")
        cb_a = st.text_input("Código de barras A:", value="8480000165039")
        pr_a = st.number_input("Precio A (€):", min_value=0.0, value=2.50, step=0.10, key="pr_a")
        pe_a = st.number_input("Peso envase A (g):", min_value=0.0, value=200.0, step=50.0, key="pe_a")
        
    with c_der:
        st.markdown("### 📦 Producto B")
        cb_b = st.text_input("Código de barras B:", value="3017620422003")
        pr_b = st.number_input("Precio B (€):", min_value=0.0, value=3.20, step=0.10, key="pr_b")
        pe_b = st.number_input("Peso envase B (g):", min_value=0.0, value=400.0, step=50.0, key="pe_b")
        
    if st.button("Comparar Cara a Cara", type="primary"):
        with st.spinner("Comparando productos y consultando al nutricionista IA..."):
            datos_a, err_a = buscar_nutricion(cb_a.strip())
            datos_b, err_b = buscar_nutricion(cb_b.strip())
            
            if err_a or err_b:
                st.error(f"Error al obtener productos: {err_a or ''} {err_b or ''}")
            else:
                def calc_coste(datos, precio, peso):
                    if precio > 0 and peso > 0:
                        tot_prot = (datos['proteinas_100g'] / 100) * peso
                        return f"{round(precio / tot_prot, 4)} €/g" if tot_prot > 0 else "N/A"
                    return "No especificado"

                resumen_a = {
                    "nombre": datos_a['producto'], "marca": datos_a['marca'],
                    "kcal": datos_a['calorias_100g'], "prot": datos_a['proteinas_100g'],
                    "carb": datos_a['carbohidratos_100g'], "grasas": datos_a['grasas_100g'],
                    "coste_prot": calc_coste(datos_a, pr_a, pe_a),
                    "ingredientes": datos_a['ingredientes']
                }
                resumen_b = {
                    "nombre": datos_b['producto'], "marca": datos_b['marca'],
                    "kcal": datos_b['calorias_100g'], "prot": datos_b['proteinas_100g'],
                    "carb": datos_b['carbohidratos_100g'], "grasas": datos_b['grasas_100g'],
                    "coste_prot": calc_coste(datos_b, pr_b, pe_b),
                    "ingredientes": datos_b['ingredientes']
                }
                
                col_res1, col_res2 = st.columns(2)
                with col_res1:
                    st.info(f"**{resumen_a['nombre']}** ({resumen_a['marca']})\n\n"
                            f"🍗 Proteínas: {resumen_a['prot']} g | 🔥 {resumen_a['kcal']} kcal\n\n"
                            f"💶 Coste prot: {resumen_a['coste_prot']}")
                with col_res2:
                    st.info(f"**{resumen_b['nombre']}** ({resumen_b['marca']})\n\n"
                            f"🍗 Proteínas: {resumen_b['prot']} g | 🔥 {resumen_b['kcal']} kcal\n\n"
                            f"💶 Coste prot: {resumen_b['coste_prot']}")
                
                st.divider()
                st.markdown("### 🏆 Decisión del Entrenador IA")
                dictamen = comparar_productos_ia(resumen_a, resumen_b, obj_comp)
                st.markdown(dictamen)
                
                st.download_button(
                    label="📥 Descargar Comparativa (.md)",
                    data=f"# Comparativa Nutricional\n\n**{resumen_a['nombre']}** VS **{resumen_b['nombre']}**\nObjetivo: {obj_comp}\n\n" + dictamen,
                    file_name="comparativa_nutricional.md",
                    mime="text/markdown"
                )
