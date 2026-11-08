import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y ESTILOS
# ---------------------------------------------------------
st.set_page_config(
    page_title="Gestión Financiera Personal",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual adaptado para uso ágil en celular
st.markdown("""
    <style>
    .stMetric { background-color: #f8f9fa; padding: 12px; border-radius: 8px; border: 1px solid #e9ecef; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# CONEXIÓN A GOOGLE SHEETS Y API DÓLAR
# ---------------------------------------------------------
@st.cache_resource
def conectar_google_sheets():
    # Carga credenciales desde st.secrets o archivo local
    scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
    credentials = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(credentials)
    sheet = client.open("APP - Financiero mensual")
    return sheet

@st.cache_data(ttl=1800)
def obtener_tc_oficial():
    """Consulta la cotización oficial del dólar en tiempo real vía DolarApi"""
    try:
        res = requests.get("https://dolarapi.com/v1/dolares/oficial", timeout=5)
        if res.status_code == 200:
            return float(res.json().get("venta", 0.0))
    except Exception:
        pass
    return 1570.0  # valor por defecto si falla la API

# Inicializar conexión
try:
    doc = conectar_google_sheets()
    sheet_mov = doc.worksheet("Movimientos")
    sheet_cajas = doc.worksheet("Cajas_Saldos")
    conexion_ok = True
except Exception as e:
    conexion_ok = False
    st.error(f"Error al conectar con Google Sheets: {e}")

# ---------------------------------------------------------
# OPCIONES DE LISTAS DESPLEGABLES
# ---------------------------------------------------------
RUBROS_GASTOS = [
    "Bancos (prestamos, tarjetas de credito)",
    "Auto",
    "Casa",
    "Comidas",
    "Gimnasio",
    "Mascotas",
    "Belleza",
    "Entretenimiento/Ocio",
    "Ropa y accesorios",
    "Salud",
    "Suscripciones",
    "Gastos Varios",
    "Regalos"
]

RUBROS_INGRESOS = ["Sueldo", "Honorarios", "Cursos/Capacitaciones", "Comisiones", "Otros Ingresos"]
RUBROS_INVERSION = ["Ahorro Reserva", "Inversión MEP/CEDEARs", "Fondo de Emergencia", "Seguro de Retiro"]
CAJAS_DISPONIBLES = ["Banco Macro", "MercadoPago", "Banco Santa Fe", "Efectivo", "Broker / Inversiones"]

# ---------------------------------------------------------
# LECTURA Y PROCESAMIENTO DE DATOS
# ---------------------------------------------------------
def cargar_datos():
    df_mov = pd.DataFrame(sheet_mov.get_all_records())
    df_cajas = pd.DataFrame(sheet_cajas.get_all_records())
    
    if not df_mov.empty:
        df_mov["Fecha"] = pd.to_datetime(df_mov["Fecha"])
        df_mov["Monto_ARS"] = pd.to_numeric(df_mov["Monto_ARS"], errors='coerce').fillna(0.0)
        df_mov["Monto_USD"] = pd.to_numeric(df_mov["Monto_USD"], errors='coerce').fillna(0.0)
    return df_mov, df_cajas

if conexion_ok:
    df_movimientos, df_saldos_base = cargar_datos()
else:
    df_movimientos = pd.DataFrame()
    df_saldos_base = pd.DataFrame()

# ---------------------------------------------------------
# INTERFAZ PRINCIPAL
# ---------------------------------------------------------
st.title("💰 Control Financiero")

tab_carga, tab_dashboard, tab_cajas = st.tabs(["📝 Cargar Movimiento", "📊 Dashboard Mensual", "🏦 Saldos por Caja"])

# ---------------------------------------------------------
# TAB 1: FORMULARIO DE CARGA
# ---------------------------------------------------------
with tab_carga:
    st.subheader("Registrar Operación")
    
    tc_actual = obtener_tc_oficial()
    st.info(f"💵 **Tipo de Cambio Oficial Hoy (Venta):** ${tc_actual:,.2f}")
    
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            id_mov = st.text_input("ID Movimiento (opcional/libre tipeo)", value=datetime.now().strftime("%Y%m%d%H%M%S"))
            fecha_op = st.date_input("Fecha", value=datetime.today())
            tipo_op = st.selectbox("Tipo de Movimiento", ["Gasto", "Ingreso", "Transferencia", "Ahorro / Inversión"])
        
        with col2:
            if tipo_op == "Transferencia":
                caja_origen = st.selectbox("Caja Origen (Resta)", CAJAS_DISPONIBLES)
                caja_destino = st.selectbox("Caja Destino (Suma)", [c for c in CAJAS_DISPONIBLES if c != caja_origen])
                rubro_op = "Transferencia entre Cuentas"
            elif tipo_op == "Ingreso":
                caja_origen = "-"
                caja_destino = st.selectbox("Caja Ingreso", CAJAS_DISPONIBLES)
                rubro_op = st.selectbox("Rubro", RUBROS_INGRESOS)
            elif tipo_op == "Ahorro / Inversión":
                caja_origen = st.selectbox("Caja Origen", CAJAS_DISPONIBLES)
                caja_destino = st.selectbox("Destino Inversión", ["Broker / Inversiones", "MercadoPago Reserva"])
                rubro_op = st.selectbox("Rubro", RUBROS_INVERSION)
            else:  # Gasto
                caja_origen = st.selectbox("Caja de Pago", CAJAS_DISPONIBLES)
                caja_destino = "-"
                rubro_op = st.selectbox("Rubro", RUBROS_GASTOS)

            concepto_op = st.text_input("Concepto / Detalle", placeholder="Ej. Compras supermercado")

        monto_ars = st.number_input("Monto en Pesos ($)", min_value=0.0, step=100.0, format="%.2f")
        monto_usd = round(monto_ars / tc_actual, 2) if tc_actual > 0 else 0.0
        
        st.caption(f"Equivalente en USD al guardar: **US$ {monto_usd:,.2f}**")
        
        btn_guardar = st.form_submit_button("💾 Guardar Movimiento")

    if btn_guardar and conexion_ok:
        if monto_ars <= 0:
            st.warning("El monto debe ser mayor a cero.")
        else:
            nueva_fila = [
                str(id_mov),
                fecha_op.strftime("%Y-%m-%d"),
                tipo_op,
                caja_origen,
                caja_destino,
                rubro_op,
                concepto_op,
                monto_ars,
                tc_actual,
                monto_usd
            ]
            sheet_mov.append_row(nueva_fila)
            st.success("¡Movimiento registrado con éxito en Google Sheets!")
            st.cache_data.clear()
            st.rerun()

# ---------------------------------------------------------
# TAB 2: DASHBOARD Y BALANCES MENSUALES
# ---------------------------------------------------------
with tab_dashboard:
    if not df_movimientos.empty:
        st.subheader("Filtros de Análisis")
        
        df_movimientos["Mes_Año"] = df_movimientos["Fecha"].dt.strftime("%Y-%m")
        meses_disponibles = sorted(df_movimientos["Mes_Año"].unique(), reverse=True)
        mes_sel = st.selectbox("Seleccionar Mes", meses_disponibles, index=0)
        
        df_mes = df_movimientos[df_movimientos["Mes_Año"] == mes_sel]
        
        tot_ingresos = df_mes[df_mes["Tipo"] == "Ingreso"]["Monto_ARS"].sum()
        tot_gastos = df_mes[df_mes["Tipo"] == "Gasto"]["Monto_ARS"].sum()
        tot_ahorros = df_mes[df_mes["Tipo"] == "Ahorro / Inversión"]["Monto_ARS"].sum()
        balance_neto = tot_ingresos - tot_gastos
        
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Ingresos Totales", f"${tot_ingresos:,.2f}")
        col_m2.metric("Gastos Totales", f"${tot_gastos:,.2f}")
        col_m3.metric("Resultado Neto", f"${balance_neto:,.2f}", delta=f"{balance_neto:,.2f}")
        col_m4.metric("Ahorros e Inversiones", f"${tot_ahorros:,.2f}")
        
        st.divider()
        st.subheader("Desglose de Gastos por Rubro")
        df_gastos_rubro = df_mes[df_mes["Tipo"] == "Gasto"].groupby("Rubro")["Monto_ARS"].sum().reset_index()
        st.dataframe(df_gastos_rubro.sort_values(by="Monto_ARS", ascending=False), use_container_width=True)
    else:
        st.info("No hay movimientos registrados para mostrar métricas.")

# ---------------------------------------------------------
# TAB 3: SALDOS REALES POR CAJA Y TRANSFERENCIAS
# ---------------------------------------------------------
with tab_cajas:
    st.subheader("Estado de Cuentas y Disponibilidades")
    
    saldos_dict = {c: 0.0 for c in CAJAS_DISPONIBLES}
    
    # Cargar saldos iniciales desde Google Sheets
    if not df_saldos_base.empty:
        for _, r in df_saldos_base.iterrows():
            if r["Caja"] in saldos_dict:
                saldos_dict[r["Caja"]] = float(r.get("Saldo_Inicial", 0.0))
                
    # Procesar la suma/resta de cada movimiento
    if not df_movimientos.empty:
        for _, row in df_movimientos.iterrows():
            tipo = row["Tipo"]
            c_orig = row["Caja_Origen"]
            c_dest = row["Caja_Destino"]
            monto = float(row["Monto_ARS"])
            
            if tipo == "Ingreso" and c_dest in saldos_dict:
                saldos_dict[c_dest] += monto
            elif tipo == "Gasto" and c_orig in saldos_dict:
                saldos_dict[c_orig] -= monto
            elif tipo == "Ahorro / Inversión":
                if c_orig in saldos_dict:
                    saldos_dict[c_orig] -= monto
                if c_dest in saldos_dict:
                    saldos_dict[c_dest] += monto
            elif tipo == "Transferencia":
                if c_orig in saldos_dict:
                    saldos_dict[c_orig] -= monto
                if c_dest in saldos_dict:
                    saldos_dict[c_dest] += monto

    df_resumen_cajas = pd.DataFrame([
        {"Caja / Cuenta": caja, "Saldo Actual ARS": monto, "Saldo Aprox USD": round(monto / obtener_tc_oficial(), 2)}
        for caja, monto in saldos_dict.items()
    ])
    
    st.dataframe(df_resumen_cajas, use_container_width=True)