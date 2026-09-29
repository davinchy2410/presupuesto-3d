import streamlit as st
import pandas as pd
import math
import os
from datetime import datetime
from fpdf import FPDF

def generar_pdf(cliente, fecha, detalle_colores, cantidad, horas, precio_unitario, precio_total, tipo_acabado):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "PRESUPUESTO DE SERVICIOS DE IMPRESIÓN 3D", ln=True, align='C')
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Fecha de emisión: {fecha}", ln=True, align='R')
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Cliente / Proyecto: {cliente}", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.ln(5)
    pdf.cell(0, 10, f"- Cantidad total de piezas: {cantidad}", ln=True)
    pdf.cell(0, 10, f"- Materiales y colores: {detalle_colores}", ln=True)
    pdf.cell(0, 10, f"- Acabado: {tipo_acabado}", ln=True)
    pdf.cell(0, 10, f"- Tiempo estimado de producción: {horas:,.1f} horas", ln=True)
    pdf.ln(5)
    pdf.cell(0, 10, f"Precio por unidad: ${precio_unitario:,.0f}", ln=True)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Precio Total del Pedido: ${precio_total:,.0f}", ln=True)
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 10, "Validez del presupuesto: 15 días. Presupuesto sujeto a disponibilidad de material. Quedamos a su entera disposición.")
    
    return pdf.output(dest='S').encode('latin-1')

def reset_cotizacion():
    st.session_state["in_nombre_cliente"] = ""
    st.session_state["in_cantidad_piezas"] = 1
    st.session_state["in_cantidad_total"] = 1
    st.session_state["in_tiempo"] = 0.0
    st.session_state["in_cambios"] = 0
    st.session_state["in_cant_colores"] = 1
    st.session_state["in_tipo_acabado"] = "Estándar (Directo de máquina)"
    st.session_state["in_costo_acabado"] = 0.0
    
    for key in list(st.session_state.keys()):
        if key.startswith("gramos_"):
            st.session_state[key] = 0.0

# Configuración inicial de la página
st.set_page_config(page_title="Presupuesto Impresión 3D", page_icon="🖨️", layout="wide")

# 1. Inicialización de Sesión (Perfiles de Filamento)
if 'filamentos' not in st.session_state:
    st.session_state['filamentos'] = {
        "Hyper PLA": {"precio": 18000.0, "gramos": 1000.0},
        "PETG": {"precio": 15000.0, "gramos": 1000.0}
    }

# 2. Barra Lateral (⚙️ Configuración del Taller)
with st.sidebar:
    st.header("⚙️ Configuración del Taller")
    
    valor_impresora = st.number_input("Valor de la Impresora ($)", value=1850000.0)
    vida_util = st.number_input("Vida Útil (horas)", value=3000.0)
    consumo = st.number_input("Consumo (kW)", value=0.20)
    precio_kwh = st.number_input("Precio kWh ($)", value=150.0)
    mantenimiento_hora = st.number_input("Mantenimiento por Hora ($)", value=100.0)
    ganancia_extra = st.number_input("Ganancia Extra por Hora ($)", value=1750.0)
    multiplicador = st.number_input("Multiplicador de Material (x)", value=2.5)
    precio_cambio_color = st.number_input("Precio Cambio de Color ($)", value=1500.0)
    
    st.markdown("---")
    
    with st.expander("🎨 Gestor de Filamentos"):
        with st.form("nuevo_filamento_form", clear_on_submit=True):
            nombre_material = st.text_input("Nombre del Material")
            precio_material = st.number_input("Precio ($)", min_value=0.0, step=100.0)
            gramos_material = st.number_input("Gramos (g)", min_value=1.0, step=100.0)
            
            submit_btn = st.form_submit_button("Guardar Filamento")
            
            if submit_btn and nombre_material:
                st.session_state['filamentos'][nombre_material] = {
                    "precio": precio_material,
                    "gramos": gramos_material
                }
                st.success(f"¡{nombre_material} guardado correctamente!")
                
        # Mostrar los filamentos actuales
        st.markdown("**Filamentos Guardados:**")
        df_filamentos = pd.DataFrame.from_dict(st.session_state['filamentos'], orient='index')
        st.dataframe(df_filamentos, use_container_width=True)
        
    with st.expander("📈 Historial y Ganancias"):
        archivo_csv = "registro_ventas.csv"
        if os.path.exists(archivo_csv):
            try:
                df_ventas = pd.read_csv(archivo_csv)
                st.dataframe(df_ventas.tail(5), use_container_width=True)
                total_ganancias = df_ventas["Precio Total"].sum()
                st.metric("Total Histórico Facturado", f"${total_ganancias:,.2f}")
            except Exception as e:
                st.error("Error al leer el archivo de ventas.")
        else:
            st.info("Aún no hay ventas registradas.")

# 3. Cuerpo Principal (📦 Datos del Pedido)
st.title("🖨️ Presupuesto de Impresión 3D")
st.markdown("Calculadora con modelo de cobro híbrido (Material + Tiempo Máquina + Intervención)")

st.header("📦 Datos del Pedido")
nombre_cliente = st.text_input("Nombre del Cliente o Proyecto", key="in_nombre_cliente")

col1, col2 = st.columns(2)

with col1:
    cantidad_piezas = st.number_input("Cantidad de piezas en la cama", min_value=1, value=1, step=1, key="in_cantidad_piezas")
    cantidad_total_pedido = st.number_input("Cantidad total del pedido (piezas)", min_value=1, value=300, step=1, key="in_cantidad_total")

with col2:
    tiempo_impresion = st.number_input("Tiempo de impresión (horas decimales)", value=2.5, key="in_tiempo")
    cambios_color = st.number_input("Cambios de color manuales (por cama)", value=1, min_value=0, step=1, key="in_cambios")

st.subheader("🛠️ Post-Procesado y Acabado")
col_acabado1, col_acabado2 = st.columns(2)
with col_acabado1:
    tipo_acabado = st.selectbox("Tipo de Acabado", [
        "Estándar (Directo de máquina)",
        "Lijado y Pulido",
        "Imprimado y Pintado",
        "Alisado Químico",
        "Baño de Resina Epóxica",
        "Otro (Personalizado)"
    ], key="in_tipo_acabado")
with col_acabado2:
    costo_extra_acabado = st.number_input("Costo Extra por Acabado (por pieza) $", value=0.0, step=100.0, key="in_costo_acabado")

st.subheader("🎨 Desglose de Colores")
cantidad_colores = st.number_input("Cantidad de colores distintos en la cama", min_value=1, value=2, step=1, key="in_cant_colores")

colores_data = []
peso_pieza = 0.0
costo_material_real = 0.0

for i in range(cantidad_colores):
    col_a, col_b = st.columns(2)
    with col_a:
        fil = st.selectbox(
            f"Filamento Color {i+1}", 
            options=list(st.session_state['filamentos'].keys()),
            key=f"filamento_{i}"
        )
    with col_b:
        gramos = st.number_input(
            f"Gramos por cama (Color {i+1})", 
            value=10.0,
            key=f"gramos_{i}"
        )
    colores_data.append({"filamento": fil, "gramos": gramos})
    peso_pieza += gramos
    
    # Costo parcial del material
    datos_fil = st.session_state['filamentos'][fil]
    precio_bobina = datos_fil["precio"]
    gramos_bobina = datos_fil["gramos"]
    costo_material_real += gramos * (precio_bobina / gramos_bobina)

# 4. Cálculos Matemáticos

# Cálculos Costos Máquina
amortizacion_hora = valor_impresora / vida_util if vida_util > 0 else 0
costo_electrico_hora = consumo * precio_kwh
costo_total_maquina_hora = amortizacion_hora + costo_electrico_hora + mantenimiento_hora

# Cálculos Material
cobro_material = costo_material_real * multiplicador

# Cálculos Tiempo y Mano de Obra
cobro_maquina = (costo_total_maquina_hora + ganancia_extra) * tiempo_impresion
cobro_intervencion = cambios_color * precio_cambio_color

# Cálculo Final
precio_final = cobro_material + cobro_maquina + cobro_intervencion
precio_unitario = (precio_final / cantidad_piezas) + costo_extra_acabado

# Cálculos de Producción
camas_necesarias = math.ceil(cantidad_total_pedido / cantidad_piezas)
total_filamento_gramos = camas_necesarias * peso_pieza
total_tiempo_horas = camas_necesarias * tiempo_impresion
precio_total_pedido = precio_unitario * cantidad_total_pedido

# Logística de Producción
st.info(f"""
**📊 Logística de Producción (Uso Interno)**
- Camas totales a imprimir: {camas_necesarias}
- Consumo total estimado: {total_filamento_gramos:,.1f} g ({(total_filamento_gramos/1000):,.2f} kg)
- Tiempo total de máquina: {total_tiempo_horas:,.1f} horas
""")
for color_data in colores_data:
    st.write(f"🔹 Consumo total de {color_data['filamento']}: {color_data['gramos'] * camas_necesarias:,.1f} g")

# 5. Interfaz de Resultados
st.divider()

col_res1, col_res2, col_res3, col_res4 = st.columns(4)

with col_res1:
    st.metric(label="Costo Material", value=f"${cobro_material:,.2f}")
    
with col_res2:
    st.metric(label="Costo Máquina + Ganancia", value=f"${cobro_maquina:,.2f}")

with col_res3:
    st.metric(label="Mano de Obra (Color)", value=f"${cobro_intervencion:,.2f}")

with col_res4:
    st.metric(label="Acabado Extra", value=f"${costo_extra_acabado * cantidad_total_pedido:,.2f}")

st.success(f"""
### 🏷️ PRECIO SUGERIDO POR PIEZA: ${precio_unitario:,.0f}
*(Precio Total del Pedido: ${precio_total_pedido:,.0f})*
""")

# Resumen para WhatsApp
st.markdown("### 📱 Resumen para Enviar")
nombres_filamentos = ", ".join(list(set([d['filamento'] for d in colores_data])))
resumen_whatsapp = f"""¡Hola! 👋 Te paso el presupuesto de tu pedido en impresión 3D:

🔹 Detalle: {cantidad_total_pedido} piezas
🔹 Materiales: {nombres_filamentos}
🔹 Acabado: {tipo_acabado}

Precio por unidad: ${precio_unitario:,.0f}
Total del pedido: ${precio_total_pedido:,.0f}

Avísame si avanzamos para agendar la impresión. ¡Saludos!"""

st.text_area("Copia y pega este mensaje en WhatsApp:", value=resumen_whatsapp, height=200)

st.divider()

col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    if st.button("💾 Guardar y Registrar Pedido", use_container_width=True):
        if not nombre_cliente:
            st.warning("Por favor, ingresa el Nombre del Cliente o Proyecto antes de guardar.")
        else:
            archivo_csv = "registro_ventas.csv"
            existe = os.path.exists(archivo_csv)
            
            nuevo_pedido = {
                "Fecha": datetime.now().strftime("%d/%m/%Y"),
                "Cliente": nombre_cliente,
                "Filamentos": nombres_filamentos,
                "Cantidad Total": cantidad_total_pedido,
                "Tiempo Total (Horas)": round(total_tiempo_horas, 2),
                "Precio Total": round(precio_total_pedido, 2)
            }
            
            df_nuevo = pd.DataFrame([nuevo_pedido])
            df_nuevo.to_csv(archivo_csv, mode='a', index=False, header=not existe)
            
            st.success("¡Pedido registrado con éxito!")

with col_btn2:
    st.button("🔄 Nueva Cotización", type="secondary", use_container_width=True, on_click=reset_cotizacion)

with col_btn3:
    if nombre_cliente:
        pdf_bytes = generar_pdf(
            cliente=nombre_cliente,
            fecha=datetime.now().strftime("%d/%m/%Y"),
            detalle_colores=nombres_filamentos,
            cantidad=cantidad_total_pedido,
            horas=total_tiempo_horas,
            precio_unitario=precio_unitario,
            precio_total=precio_total_pedido,
            tipo_acabado=tipo_acabado
        )
        nombre_archivo = f"Presupuesto_{nombre_cliente.replace(' ', '_')}.pdf"
        st.download_button(
            label="📄 Descargar Presupuesto en PDF",
            data=pdf_bytes,
            file_name=nombre_archivo,
            mime="application/pdf",
            use_container_width=True
        )
