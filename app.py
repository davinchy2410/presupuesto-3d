import streamlit as st
import pandas as pd
import math
import os
import json
import uuid
import urllib.parse
from datetime import datetime
import time
from fpdf import FPDF
import hashlib

try:
    from supabase import create_client, Client
except ImportError:
    pass

# --- Configuración Inicial ---
st.set_page_config(page_title="Presupuesto Impresión 3D", page_icon="🖨️", layout="wide")

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except:
        return None

supabase = init_connection()

if supabase is None:
    st.error("⚠️ La base de datos Supabase aún no está conectada.")
    st.info("Faltan las credenciales. Debes agregar SUPABASE_URL y SUPABASE_KEY en la configuración secreta (Secrets) de Streamlit Cloud.")
    st.stop()

# --- Funciones BD ---
def login_user(username, password):
    hashed = hash_password(password)
    response = supabase.table('app_users').select('*').eq('username', username).execute()
    if len(response.data) > 0:
        if response.data[0]['password'] == hashed:
            return response.data[0]
    return None

def register_user(username, password, company_name):
    hashed = hash_password(password)
    default_filaments = {
        "Hyper PLA": {"precio": 18000.0, "gramos": 1000.0},
        "PETG": {"precio": 15000.0, "gramos": 1000.0}
    }
    res = supabase.table('app_users').select('username').eq('username', username).execute()
    if len(res.data) > 0:
        return False, "El nombre de usuario ya existe."
    try:
        supabase.table('app_users').insert({
            "username": username,
            "password": hashed,
            "company_name": company_name,
            "filaments": default_filaments,
            "sales_history": [],
            "clients": [],
            "currency": "$",
            "config_taller": {}
        }).execute()
        return True, "Registro exitoso."
    except Exception as e:
        return False, f"Error al registrar: {e}"

def update_user_data():
    try:
        supabase.table('app_users').update({
            "company_name": st.session_state['company_name'],
            "filaments": st.session_state['filamentos'],
            "sales_history": st.session_state['sales_history'],
            "clients": st.session_state['clients'],
            "currency": st.session_state['currency'],
            "config_taller": st.session_state.get('config_taller', {})
        }).eq('username', st.session_state['user']).execute()
    except Exception as e:
        pass


# --- Generador de PDF ---
def generar_pdf(empresa, cliente, fecha, detalle_colores, cantidad, tiempo_str, precio_total_sin_envio, precio_total, tipo_acabado, descuento, envio, moneda):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"PRESUPUESTO - {empresa.upper()}", ln=True, align='C')
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
    pdf.cell(0, 10, f"- Tiempo estimado de produccion: {tiempo_str}", ln=True)
    pdf.ln(5)
    pdf.cell(0, 10, f"Subtotal: {moneda}{precio_total_sin_envio:,.0f}", ln=True)
    if descuento > 0:
        pdf.cell(0, 10, f"Descuento ({descuento}%): -{moneda}{(precio_total_sin_envio * (descuento/100)):,.0f}", ln=True)
    if envio > 0:
        pdf.cell(0, 10, f"Costo de Envio: {moneda}{envio:,.0f}", ln=True)
        
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Precio Total del Pedido: {moneda}{precio_total:,.0f}", ln=True)
    pdf.ln(20)
    pdf.set_font("Arial", 'I', 10)
    pdf.multi_cell(0, 10, "Validez del presupuesto: 15 dias. Presupuesto sujeto a disponibilidad de material. Quedamos a su entera disposicion.")
    return pdf.output(dest='S').encode('latin-1')

def reset_cotizacion():
    st.session_state["in_nombre_cliente"] = ""
    st.session_state["in_nombre_proyecto"] = ""
    st.session_state["in_cantidad_piezas"] = 1
    st.session_state["in_cantidad_total"] = 1
    st.session_state["in_horas"] = 0
    st.session_state["in_minutos"] = 0
    st.session_state["in_cambios"] = 0
    st.session_state["in_cant_colores"] = 1
    st.session_state["in_tipo_acabado"] = "Estándar (Directo de máquina)"
    st.session_state["in_costo_acabado"] = 0.0
    for key in list(st.session_state.keys()):
        if key.startswith("gramos_"):
            st.session_state[key] = 0.0

# --- CONTROL DE SESIÓN ---
if 'user' not in st.session_state:
    st.session_state['user'] = None

if st.session_state['user'] is None:
    st.title("🔐 Acceso al Sistema de Presupuestos")
    tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
    
    with tab1:
        with st.form("login_form"):
            log_user = st.text_input("Usuario")
            log_pass = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                user_data = login_user(log_user, log_pass)
                if user_data:
                    st.session_state['user'] = user_data['username']
                    st.session_state['company_name'] = user_data['company_name']
                    st.session_state['filamentos'] = user_data.get('filaments', {})
                    st.session_state['sales_history'] = user_data.get('sales_history', [])
                    st.session_state['clients'] = user_data.get('clients', [])
                    st.session_state['currency'] = user_data.get('currency', '$')
                    st.session_state['config_taller'] = user_data.get('config_taller') or {}
                    st.success("¡Bienvenido!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
                    
    with tab2:
        with st.form("register_form"):
            reg_user = st.text_input("Nuevo Usuario")
            reg_pass = st.text_input("Contraseña", type="password")
            reg_company = st.text_input("Nombre de tu Empresa (Se usará en PDFs y WhatsApp)")
            if st.form_submit_button("Crear Cuenta", use_container_width=True):
                if reg_user and reg_pass and reg_company:
                    success, msg = register_user(reg_user, reg_pass, reg_company)
                    if success:
                        st.success(msg + " Ahora puedes iniciar sesión en la otra pestaña.")
                    else:
                        st.error(msg)
                else:
                    st.warning("Completa todos los campos.")
    st.stop()


# --- APLICACIÓN PRINCIPAL ---

with st.sidebar:
    st.header(f"🏢 {st.session_state['company_name']}")
    st.caption(f"Usuario Logueado: {st.session_state['user']}")
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['user'] = None
        st.rerun()
        
    st.divider()
    st.header("⚙️ Configuración del Taller")
    with st.form("config_taller_form"):
        cfg = st.session_state.get('config_taller', {})
        valor_impresora = st.number_input("Valor de la Impresora ($)", value=float(cfg.get('valor_impresora', 1850000.0)))
        vida_util = st.number_input("Vida Útil (horas)", value=float(cfg.get('vida_util', 3000.0)))
        consumo = st.number_input("Consumo (kW)", value=float(cfg.get('consumo', 0.20)))
        precio_kwh = st.number_input("Precio kWh ($)", value=float(cfg.get('precio_kwh', 150.0)))
        mantenimiento_hora = st.number_input("Mantenimiento por Hora ($)", value=float(cfg.get('mantenimiento', 100.0)))
        ganancia_extra = st.number_input("Ganancia Extra por Hora ($)", value=float(cfg.get('ganancia', 1750.0)))
        multiplicador = st.number_input("Multiplicador de Material (x)", value=float(cfg.get('multiplicador', 2.5)))
        precio_cambio_color = st.number_input("Precio Cambio de Color ($)", value=float(cfg.get('cambio_color', 1500.0)))
        
        if st.form_submit_button("💾 Guardar Configuración", use_container_width=True):
            st.session_state['config_taller'] = {
                "valor_impresora": valor_impresora,
                "vida_util": vida_util,
                "consumo": consumo,
                "precio_kwh": precio_kwh,
                "mantenimiento": mantenimiento_hora,
                "ganancia": ganancia_extra,
                "multiplicador": multiplicador,
                "cambio_color": precio_cambio_color
            }
            update_user_data()
            st.success("¡Configuración guardada!")
    
    st.markdown("---")
    
    with st.expander("🛠️ Personalizar Empresa"):
        new_company = st.text_input("Nombre de la Empresa", value=st.session_state['company_name'])
        new_currency = st.text_input("Símbolo de Moneda (ej. $, €, ARS, MXN)", value=st.session_state.get('currency', '$'))
        if st.button("Actualizar Ajustes", use_container_width=True):
            st.session_state['company_name'] = new_company
            st.session_state['currency'] = new_currency
            update_user_data()
            st.success("¡Ajustes actualizados!")
            st.rerun()
            

# --- INTERFAZ DE PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["🧮 Nueva Cotización", "📋 Gestor de Pedidos", "🏭 Taller y CRM"])

with tab1:
    st.title("🖨️ Presupuesto de Impresión 3D")
    st.markdown("Calculadora con modelo de cobro híbrido (Material + Tiempo Máquina + Intervención)")

    st.header("📦 Datos del Pedido")

    moneda = st.session_state.get('currency', '$')

    # Gestor de Clientes Inline
    nombres_clientes_guardados = [c['nombre'] for c in st.session_state.get('clients', [])]
    opciones_cliente = ["-- Cliente Casual --"] + nombres_clientes_guardados

    seleccion_cliente = st.selectbox("Seleccionar Cliente (Desde el CRM)", opciones_cliente)

    if seleccion_cliente == "-- Cliente Casual --":
        nombre_cliente = st.text_input("Nombre del Cliente (Temporal)", key="in_nombre_cliente")
    else:
        nombre_cliente = seleccion_cliente

    nombre_proyecto = st.text_input("Nombre del Proyecto / Pieza (Ej: Maceta Groot, Llaveros...)", key="in_nombre_proyecto")

    # Fila 1: Piezas por cama y Tiempo
    row1_col1, row1_col2, row1_col3 = st.columns([2, 1, 1])
    with row1_col1:
        cantidad_piezas = st.number_input("Cantidad de piezas en la cama", min_value=1, value=1, step=1, key="in_cantidad_piezas")
    with row1_col2:
        horas_impresion = st.number_input("Horas (impresión)", min_value=0, value=2, step=1, key="in_horas")
    with row1_col3:
        minutos_impresion = st.number_input("Minutos", min_value=0, max_value=59, value=30, step=1, key="in_minutos")

    tiempo_impresion = horas_impresion + (minutos_impresion / 60.0)

    # Fila 2: Total del pedido y Cambios de color
    row2_col1, row2_col2 = st.columns(2)
    with row2_col1:
        cantidad_total_pedido = st.number_input("Cantidad total del pedido (piezas)", min_value=1, value=300, step=1, key="in_cantidad_total")
    with row2_col2:
        cambios_color = st.number_input("Cambios de color manuales (por cama)", value=1, min_value=0, step=1, key="in_cambios")

    st.subheader("🛠️ Post-Procesado, Riesgos y Logística")
    col_acabado1, col_acabado2, col_acabado3 = st.columns(3)
    with col_acabado1:
        tipo_acabado = st.selectbox("Tipo de Acabado", [
            "Estándar (Directo de máquina)", "Lijado y Pulido", "Imprimado y Pintado", "Alisado Químico", "Baño de Resina Epóxica", "Otro"
        ], key="in_tipo_acabado")
    with col_acabado2:
        costo_extra_acabado = st.number_input(f"Costo Extra por Acabado (p/u) {moneda}", value=0.0, step=100.0, key="in_costo_acabado")
    with col_acabado3:
        riesgo_fallo = st.selectbox("Margen de Riesgo (Fallas)", ["Sin riesgo (+0%)", "Riesgo Bajo (+10% material)", "Riesgo Alto (+25% material)"])

    col_fin1, col_fin2, col_fin3 = st.columns(3)
    with col_fin1:
        link_stl = st.text_input("🔗 Enlace del Modelo 3D (Opcional)", placeholder="https://thingiverse.com/...")
    with col_fin2:
        descuento = st.number_input(f"Descuento Comercial (%)", min_value=0.0, max_value=100.0, value=0.0)
    with col_fin3:
        costo_envio = st.number_input(f"Costo de Envío {moneda}", value=0.0, step=500.0)

    st.subheader("🎨 Desglose de Colores")
    cantidad_colores = st.number_input("Cantidad de colores distintos en la cama", min_value=1, value=2, step=1, key="in_cant_colores")

    colores_data = []
    peso_pieza = 0.0
    costo_material_real = 0.0

    if not st.session_state['filamentos']:
        st.warning("No tienes filamentos guardados. Ve a la barra lateral para agregar uno.")
        st.stop()

    for i in range(cantidad_colores):
        col_a, col_b = st.columns(2)
        with col_a:
            fil = st.selectbox(f"Filamento Color {i+1}", options=list(st.session_state['filamentos'].keys()), key=f"filamento_{i}")
        with col_b:
            gramos = st.number_input(f"Gramos por cama (Color {i+1})", value=10.0, key=f"gramos_{i}")
        colores_data.append({"filamento": fil, "gramos": gramos})
        peso_pieza += gramos
        datos_fil = st.session_state['filamentos'][fil]
        costo_material_real += gramos * (datos_fil["precio"] / datos_fil["gramos"])

    # Aplicar riesgo al material
    if "10%" in riesgo_fallo: costo_material_real *= 1.10
    elif "25%" in riesgo_fallo: costo_material_real *= 1.25

    amortizacion_hora = valor_impresora / vida_util if vida_util > 0 else 0
    costo_electrico_hora = consumo * precio_kwh
    costo_total_maquina_hora = amortizacion_hora + costo_electrico_hora + mantenimiento_hora

    cobro_material = costo_material_real * multiplicador
    cobro_maquina = (costo_total_maquina_hora + ganancia_extra) * tiempo_impresion
    cobro_intervencion = cambios_color * precio_cambio_color

    precio_final_cama = cobro_material + cobro_maquina + cobro_intervencion
    precio_unitario_base = (precio_final_cama / cantidad_piezas) + costo_extra_acabado

    camas_necesarias = math.ceil(cantidad_total_pedido / cantidad_piezas)
    total_filamento_gramos = camas_necesarias * peso_pieza
    total_tiempo_horas = camas_necesarias * tiempo_impresion

    total_h = int(total_tiempo_horas)
    total_m = int(round((total_tiempo_horas - total_h) * 60))
    tiempo_formateado = f"{total_h}h {total_m}m"

    # Descuentos y envíos
    precio_total_sin_envio_desc = precio_unitario_base * cantidad_total_pedido
    valor_descontado = precio_total_sin_envio_desc * (descuento / 100)
    precio_total_pedido = (precio_total_sin_envio_desc - valor_descontado) + costo_envio
    precio_unitario_final = precio_total_pedido / cantidad_total_pedido if cantidad_total_pedido > 0 else 0

    st.info(f"**📊 Logística de Producción (Uso Interno)**\n- Camas totales a imprimir: {camas_necesarias}\n- Consumo total estimado: {total_filamento_gramos:,.1f} g ({(total_filamento_gramos/1000):,.2f} kg)\n- Tiempo total de máquina: {tiempo_formateado}")

    for color_data in colores_data:
        consumo_c = color_data['gramos'] * camas_necesarias
        fil_name = color_data['filamento']
        stock_actual = st.session_state['filamentos'][fil_name].get('stock', 0)
        alerta = " ⚠️ ¡STOCK INSUFICIENTE!" if stock_actual < consumo_c else ""
        st.write(f"🔹 Consumo total de {fil_name}: {consumo_c:,.1f} g *(Stock disponible: {stock_actual:,.1f} g)* {alerta}")

    st.divider()
    col_res1, col_res2, col_res3, col_res4 = st.columns(4)
    with col_res1: st.metric(label="Costo Material", value=f"{moneda}{cobro_material:,.2f}")
    with col_res2: st.metric(label="Costo Máquina + Ganancia", value=f"{moneda}{cobro_maquina:,.2f}")
    with col_res3: st.metric(label="Mano de Obra (Color)", value=f"{moneda}{cobro_intervencion:,.2f}")
    with col_res4: st.metric(label="Acabado Extra", value=f"{moneda}{costo_extra_acabado * cantidad_total_pedido:,.2f}")

    st.success(f"### 🏷️ PRECIO SUGERIDO POR PIEZA: {moneda}{precio_unitario_final:,.0f}\n*(Precio Total del Pedido: {moneda}{precio_total_pedido:,.0f})*")

    st.markdown("### 📱 Resumen para Enviar")
    nombres_filamentos = ", ".join(list(set([d['filamento'] for d in colores_data])))
    resumen_whatsapp = f"""¡Hola! 👋 Te paso el presupuesto de tu pedido en impresión 3D con {st.session_state['company_name']}:

    🔹 Proyecto: {nombre_proyecto if nombre_proyecto else 'Impresión 3D'}
    🔹 Detalle: {cantidad_total_pedido} piezas
    🔹 Materiales: {nombres_filamentos}
    🔹 Acabado: {tipo_acabado}

    Subtotal: {moneda}{precio_total_sin_envio_desc:,.0f}"""
    if descuento > 0: resumen_whatsapp += f"\nDescuento ({descuento}%): -{moneda}{valor_descontado:,.0f}"
    if costo_envio > 0: resumen_whatsapp += f"\nEnvío: {moneda}{costo_envio:,.0f}"
    resumen_whatsapp += f"\n\nTotal del pedido: *{moneda}{precio_total_pedido:,.0f}*"
    resumen_whatsapp += f"\n\nAvísame si avanzamos para agendar la impresión. ¡Saludos!"

    whatsapp_editado = st.text_area("Puedes modificar el mensaje antes de enviarlo:", value=resumen_whatsapp, height=250)

    telefono_destino = ""
    if seleccion_cliente != "-- Cliente Casual --":
        for c in st.session_state['clients']:
            if c['nombre'] == seleccion_cliente:
                telefono_destino = c.get('telefono', "").strip()
                break

    msg_codificado = urllib.parse.quote(whatsapp_editado)
    if telefono_destino:
        link_wa = f"https://wa.me/{telefono_destino}?text={msg_codificado}"
        st.link_button(f"📲 Enviar al WhatsApp de {seleccion_cliente}", url=link_wa, type="primary", use_container_width=True)
    else:
        link_wa = f"https://api.whatsapp.com/send?text={msg_codificado}"
        st.link_button("📲 Compartir por WhatsApp (Seleccionar contacto)", url=link_wa, use_container_width=True)

    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns(3)

    with col_btn1:
        if st.button("💾 Guardar y Registrar Pedido", use_container_width=True):
            if not nombre_cliente:
                st.warning("Por favor, ingresa el Nombre del Cliente.")
            else:
                consumos_dict = {c['filamento']: c['gramos'] * camas_necesarias for c in colores_data}
                nuevo_pedido = {
                    "ID": str(uuid.uuid4())[:6].upper(),
                    "Fecha": datetime.now().strftime("%d/%m/%Y"),
                    "Cliente": nombre_cliente,
                    "Proyecto": nombre_proyecto,
                    "Filamentos": nombres_filamentos,
                    "Link STL": link_stl,
                    "Cantidad Total": cantidad_total_pedido,
                    "Tiempo Total": tiempo_formateado,
                    "Precio Total": round(precio_total_pedido, 2),
                    "Estado": "🔴 Pendiente",
                    "Consumo_Gramos": consumos_dict,
                    "Stock_Descontado": False
                }
                st.session_state['sales_history'].append(nuevo_pedido)
            
                update_user_data()
                st.success("¡Presupuesto registrado como Pendiente! (El stock se descontará cuando cambies el estado a Imprimiendo)")
                time.sleep(1.5)
                st.rerun()

    with col_btn2:
        st.button("🔄 Nueva Cotización", type="secondary", use_container_width=True, on_click=reset_cotizacion)

    with col_btn3:
        if nombre_cliente:
            pdf_bytes = generar_pdf(
                empresa=st.session_state['company_name'],
                cliente=nombre_cliente,
                fecha=datetime.now().strftime("%d/%m/%Y"),
                detalle_colores=nombres_filamentos,
                cantidad=cantidad_total_pedido,
                tiempo_str=tiempo_formateado,
                precio_total_sin_envio=precio_total_sin_envio_desc,
                precio_total=precio_total_pedido,
                tipo_acabado=tipo_acabado,
                descuento=descuento,
                envio=costo_envio,
                moneda=moneda
            )
            st.download_button(label="📄 Descargar Presupuesto en PDF", data=pdf_bytes, file_name=f"Presupuesto_{nombre_cliente.replace(' ', '_')}.pdf", mime="application/pdf", use_container_width=True)

with tab2:
    st.header('📋 Gestor de Pedidos y Análisis')
    historial = st.session_state.get('sales_history', [])
    if len(historial) > 0:
        df_ventas = pd.DataFrame(historial)
        
        st.markdown("### 📋 Gestor de Pedidos")
        st.caption("Puedes editar el estado de los pedidos o **eliminar filas completas** seleccionándolas y presionando la tecla Delete (Suprimir) o usando el ícono de papelera.")
        
        # Asegurar compatibilidad de columnas en historiales viejos
        if "Estado" not in df_ventas.columns: df_ventas["Estado"] = "🔴 Pendiente"
        if "Link STL" not in df_ventas.columns: df_ventas["Link STL"] = ""
        if "ID" not in df_ventas.columns: df_ventas["ID"] = [str(uuid.uuid4()) for _ in range(len(df_ventas))]
        if "Proyecto" not in df_ventas.columns: df_ventas["Proyecto"] = "S/N"
        
        # Acortar IDs largos visualmente
        df_ventas["ID"] = df_ventas["ID"].apply(lambda x: str(x)[:6].upper() if len(str(x)) > 10 else x)
        
        # Data Editor Mágico (Editable y Borrable)
        edited_df = st.data_editor(
            df_ventas,
            column_config={
                "ID": st.column_config.TextColumn("ID", disabled=True),
                "Proyecto": st.column_config.TextColumn("Proyecto", disabled=False),
                "Estado": st.column_config.SelectboxColumn("Estado", options=["🔴 Pendiente", "🟡 Imprimiendo", "🟢 Entregado / Pagado"], required=True),
                "Link STL": st.column_config.LinkColumn("Modelo 3D")
            },
            disabled=["ID", "Fecha", "Cliente", "Filamentos", "Cantidad Total", "Precio Total", "Tiempo Total (Horas)", "Tiempo Total"],
            use_container_width=True,
            num_rows="dynamic", # Permite eliminar filas
            key="editor_historial"
        )
        
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("💾 Guardar Cambios en Historial", use_container_width=True):
                df_clean = edited_df.dropna(how='all')
                df_clean = df_clean[df_clean['ID'].notnull()]
                
                nuevos_pedidos = df_clean.to_dict('records')
                viejos_pedidos = st.session_state.get('sales_history', [])
                
                # Deducción inteligente de stock
                for nuevo_p in nuevos_pedidos:
                    viejo_p = next((p for p in viejos_pedidos if p['ID'] == nuevo_p['ID']), None)
                    if viejo_p:
                        estado_nuevo = nuevo_p.get('Estado', '')
                        ya_descontado = viejo_p.get('Stock_Descontado', False)
                        
                        if estado_nuevo in ["🟡 Imprimiendo", "🟢 Entregado / Pagado"] and not ya_descontado:
                            consumos = viejo_p.get("Consumo_Gramos", {})
                            for fil, gramos in consumos.items():
                                if fil in st.session_state['filamentos'] and 'stock' in st.session_state['filamentos'][fil]:
                                    st.session_state['filamentos'][fil]['stock'] -= gramos
                            nuevo_p['Stock_Descontado'] = True
                        elif estado_nuevo == "🔴 Pendiente":
                            nuevo_p['Stock_Descontado'] = ya_descontado # Mantiene el estado
                            
                st.session_state['sales_history'] = nuevos_pedidos
                update_user_data()
                st.success("¡Historial actualizado permanentemente!")
                time.sleep(1.2)
                st.rerun()
        with col_act2:
            csv = edited_df.to_csv(index=False).encode('utf-8')
            st.download_button("📊 Descargar Excel (CSV)", csv, "historial_impresion3d.csv", "text/csv", use_container_width=True)
        
        st.divider()
        st.markdown("### 📊 Análisis de Ganancias")
        
        try:
            df_grafico = df_ventas.copy()
            df_grafico['Fecha_Obj'] = pd.to_datetime(df_grafico['Fecha'], format='%d/%m/%Y', errors='coerce')
            df_grafico['Mes'] = df_grafico['Fecha_Obj'].dt.strftime('%Y-%m')
            ganancias_mes = df_grafico.groupby('Mes')['Precio Total'].sum().reset_index()
            if not ganancias_mes.empty:
                st.bar_chart(data=ganancias_mes, x='Mes', y='Precio Total')
        except Exception as e:
            st.caption("No hay suficientes datos con fechas válidas para graficar.")
        
        total_ganancias = df_ventas["Precio Total"].sum()
        st.metric("Total Histórico Global", f"{st.session_state.get('currency', '$')}{total_ganancias:,.2f}")
    else:
        st.info("Aún no hay ventas registradas.")


with tab3:
    st.header('🎨 Gestor y Stock de Filamentos')
    with st.form("nuevo_filamento_form", clear_on_submit=True):
        nombre_material = st.text_input("Nombre del Material (Ej: PLA Negro)")
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: precio_material = st.number_input("Precio Rollo ($)", min_value=0.0, step=100.0)
        with col_f2: gramos_material = st.number_input("Peso Rollo (g)", min_value=1.0, value=1000.0, step=100.0)
        with col_f3: stock_inicial = st.number_input("Stock Actual (g)", min_value=0.0, value=1000.0, step=100.0)
        
        submit_btn = st.form_submit_button("Guardar Filamento")
        if submit_btn and nombre_material:
            st.session_state['filamentos'][nombre_material] = {"precio": precio_material, "gramos": gramos_material, "stock": stock_inicial}
            update_user_data()
            st.success(f"¡{nombre_material} guardado!")
            st.rerun()
            
    st.markdown("**Inventario Actual:**")
    st.caption("💡 **Tip:** Haz doble clic en cualquier número de la tabla para editarlo como en Excel. Para borrar, selecciona la fila y presiona Suprimir (Delete).")
    if st.session_state['filamentos']:
        # Compatibilidad con datos anteriores
        for k, v in st.session_state['filamentos'].items():
            if 'stock' not in v: v['stock'] = 0.0

        df_filamentos = pd.DataFrame.from_dict(st.session_state['filamentos'], orient='index')
        edited_fil = st.data_editor(df_filamentos, use_container_width=True, num_rows="dynamic", key="editor_filamentos")
        if st.button("💾 Guardar Cambios de Inventario"):
            # Limpiar la fila vacía que agrega Streamlit al final
            df_clean = edited_fil.dropna(how='all')
            df_clean = df_clean[df_clean.index.notnull()]
            df_clean = df_clean.dropna()
            st.session_state['filamentos'] = df_clean.to_dict(orient='index')
            update_user_data()
            st.success("¡Stock actualizado!")
            st.rerun()
        
    st.divider()
    st.header('👥 Gestor de Clientes (CRM)')
    with st.form("nuevo_cliente_form", clear_on_submit=True):
        nombre_cliente_nuevo = st.text_input("Nombre del Cliente o Empresa")
        telefono_cliente = st.text_input("Teléfono (ej: 5491123456789)", help="Código de país y área, sin el '+'. Solo números.")
        ig_email_cliente = st.text_input("Instagram o Email")
        notas_cliente = st.text_input("Notas / Preferencias")
        
        if st.form_submit_button("Guardar Cliente"):
            if nombre_cliente_nuevo:
                cliente_existente = next((c for c in st.session_state['clients'] if c['nombre'] == nombre_cliente_nuevo), None)
                if cliente_existente:
                    cliente_existente.update({"telefono": telefono_cliente, "contacto": ig_email_cliente, "notas": notas_cliente})
                else:
                    st.session_state['clients'].append({
                        "nombre": nombre_cliente_nuevo, "telefono": telefono_cliente, "contacto": ig_email_cliente, "notas": notas_cliente
                    })
                update_user_data()
                st.success(f"¡{nombre_cliente_nuevo} guardado en el directorio!")
                st.rerun()
            else:
                st.warning("Debes poner al menos el nombre.")
                
    st.markdown("**Directorio:**")
    if st.session_state['clients']:
        df_clientes = pd.DataFrame(st.session_state['clients'])
        for col in ["telefono", "contacto", "notas"]:
            if col not in df_clientes.columns: df_clientes[col] = ""
        
        edited_clientes = st.data_editor(
            df_clientes, 
            use_container_width=True, 
            num_rows="dynamic",
            key="editor_clientes"
        )
        if st.button("💾 Guardar Cambios en CRM"):
            df_clean = edited_clientes.dropna(how='all').fillna("")
            df_clean = df_clean[df_clean['nombre'].astype(str).str.strip() != ""]
            st.session_state['clients'] = df_clean.to_dict('records')
            update_user_data()
            st.success("CRM actualizado permanentemente.")
            st.rerun()
    
