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
    page_title="Control Financiero",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilo visual de alto contraste
st.markdown("""
    <style>
    div[data-testid="stMetric"] {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        padding: 15px !important;
        border-radius: 10px !important;
    }
    div[data-testid="stMetricLabel"] > label {
        color: #94A3B8 !important;
        font-size: 0.95rem !important;
        font-weight: 600 !important;
    }
    div[data-testid="stMetricValue"] > div {
        color: #F8FAFC !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }
    .stButton>button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        font-weight: bold;
        background-color: #10B981 !important;
        color: white !important;
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# CONEXIÓN A GOOGLE SHEETS
# ---------------------------------------------------------
def conectar_google_sheets():
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

@st.cache_data(ttl=600)
def obtener_tc_oficial():
    try:
        res = requests.get("https://dolarapi.com/v1/dolares/oficial", timeout=5)
        if res.status_code == 200:
            return float(res.json().get("venta", 0.0))
    except Exception:
        pass
    return 1570.0

try:
    doc = conectar_google_sheets()
    sheet_mov = doc.worksheet("Movimientos")
    sheet_cajas = doc.worksheet("Cajas_Saldos")
    conexion_ok = True
except Exception as e:
    conexion_ok = False
    st.error(f"Error al conectar con Google Sheets: {e}")

# ---------------------------------------------------------
# CONFIGURACIÓN DE RUBROS Y CAJAS
# ---------------------------------------------------------
RUBROS_GASTOS = [
    "Bancos (prestamos, tarjetas de credito)", "Auto", "Casa", "Comidas",
    "Gimnasio", "Mascotas", "Belleza", "Entretenimiento/Ocio",
    "Ropa y accesorios", "Salud", "Suscripciones", "Gastos Varios", "Regalos"
]

RUBROS_INGRESOS = [
    "Sueldo", "Honorarios", "Cursos/Capacitaciones", "Comisiones",
    "Productos Millanel", "Ventas", "Otros Ingresos"
]

RUBROS_INVERSION = [
    "Ahorro", "Fondo de Emergencia", "Inversiones", "Seguro de retiro"
]

CAJAS_DISPONIBLES = ["Banco Macro", "MercadoPago", "Banco Santa Fe", "Efectivo", "Broker / Inversiones"]

# ---------------------------------------------------------
# FUNCIÓN DE LIMPIEZA NUMÉRICA AVANZADA
# ---------------------------------------------------------
def limpiar_monto(val):
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    
    val_str = str(val).replace("$", "").replace("U$S", "").strip()
    if not val_str:
        return 0.0
    
    # Manejar formatos con comas y puntos:
    # Ejemplo 1: "2,683,881.23" (Formato inglés/Sheets por defecto)
    # Ejemplo 2: "2.683.881,23" (Formato español)
    if "," in val_str and "." in val_str:
        if val_str.find(",") < val_str.find("."):
            # Coma es miles, punto es decimal
            val_str = val_str.replace(",", "")
        else:
            # Punto es miles, coma es decimal
            val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        # Solo coma: si hay dos decimales al final es coma decimal
        partes = val_str.split(",")
        if len(partes[-1]) in [1, 2]:
            val_str = val_str.replace(",", ".")
        else:
            val_str = val_str.replace(",", "")
    elif "." in val_str:
        # Solo punto: verificar si es separador de miles
        partes = val_str.split(".")
        if len(partes[-1]) == 3 and len(partes) > 1:
            val_str = "".join(partes)
            
    try:
        return float(val_str)
    except ValueError:
        return 0.0

def cargar_datos():
    raw_mov = sheet_mov.get_all_records()
    raw_cajas = sheet_cajas.get_all_records()
    
    df_mov = pd.DataFrame(raw_mov)
    df_cajas = pd.DataFrame(raw_cajas)
    
    if not df_mov.empty:
        df_mov.columns = [str(c).strip() for c in df_mov.columns]
        
        if "Caja / Cuenta" in df_mov.columns and "Caja_Origen" not in df_mov.columns:
            df_mov["Caja_Origen"] = df_mov["Caja / Cuenta"]
            df_mov["Caja_Destino"] = "-"

        if "Monto ($)" in df_mov.columns and "Monto_ARS" not in df_mov.columns:
            df_mov["Monto_ARS"] = df_mov["Monto ($)"]

        if "Monto (USD)" in df_mov.columns and "Monto_USD" not in df_mov.columns:
            df_mov["Monto_USD"] = df_mov["Monto (USD)"]
            
        df_mov["Fecha"] = pd.to_datetime(df_mov["Fecha"], errors='coerce')
        df_mov["Monto_ARS"] = df_mov["Monto_ARS"].apply(limpiar_monto)
        df_mov["Monto_USD"] = df_mov["Monto_USD"].apply(limpiar_monto)
        df_mov["Caja_Origen"] = df_mov["Caja_Origen"].astype(str).str.strip()
        df_mov["Caja_Destino"] = df_mov["Caja_Destino"].astype(str).str.strip()
        df_mov["Tipo"] = df_mov["Tipo"].astype(str).str.strip()
        
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
    
    tc_defecto = obtener_tc_oficial()
    
    tipo_op = st.radio(
        "Tipo de Movimiento", 
        ["Gasto", "Ingreso", "Transferencia", "Ahorro / Inversión"], 
        horizontal=True
    )
    
    st.divider()
    
    with st.form("form_registro", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            id_mov = st.text_input("ID Movimiento (libre tipeo)", value=datetime.now().strftime("%Y%m%d%H%M%S"))
            fecha_op = st.date_input("Fecha", value=datetime.today())
            tc_aplicado = st.number_input("Tipo de Cambio Oficial (Editable)", value=tc_defecto, step=1.0, format="%.2f")
            
            if tipo_op == "Transferencia":
                caja_origen = st.selectbox("Caja Origen (Resta)", CAJAS_DISPONIBLES)
            elif tipo_op == "Ingreso":
                caja_origen = "-"
            else:
                caja_origen = st.selectbox("Caja de Origen / Pago", CAJAS_DISPONIBLES)

        with col2:
            if tipo_op == "Ingreso":
                rubro_op = st.selectbox("Rubro de Ingreso", RUBROS_INGRESOS)
                caja_destino = st.selectbox("Caja de Destino (Ingreso)", CAJAS_DISPONIBLES)
            elif tipo_op == "Ahorro / Inversión":
                rubro_op = st.selectbox("Rubro de Inversión / Ahorro", RUBROS_INVERSION)
                caja_destino = st.selectbox("Destino de Inversión", ["Broker / Inversiones", "MercadoPago", "Efectivo"])
            elif tipo_op == "Transferencia":
                rubro_op = "Transferencia entre Cuentas"
                caja_destino = st.selectbox("Caja Destino (Suma)", [c for c in CAJAS_DISPONIBLES if c != caja_origen])
            else:  # Gasto
                rubro_op = st.selectbox("Rubro de Gasto", RUBROS_GASTOS)
                caja_destino = "-"

            concepto_op = st.text_input("Concepto / Detalle", placeholder="Ej. Cobro honorarios / Supermercado")

        monto_ars = st.number_input("Monto en Pesos ($)", min_value=0.0, step=1000.0, format="%.2f")
        monto_usd = round(monto_ars / tc_aplicado, 2) if tc_aplicado > 0 else 0.0
        
        st.caption(f"Equivalente en USD: **US$ {monto_usd:,.2f}** (TC ${tc_aplicado:,.2f})")
        
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
                float(monto_ars),
                float(tc_aplicado),
                float(monto_usd)
            ]
            sheet_mov.append_row(nueva_fila)
            st.success("¡Movimiento registrado correctamente!")
            st.cache_data.clear()
            st.rerun()

# ---------------------------------------------------------
# TAB 2: DASHBOARD MENSUAL Y DESGLOSE
# ---------------------------------------------------------
with tab_dashboard:
    if not df_movimientos.empty:
        st.subheader("Filtros de Análisis")
        
        df_movimientos["Mes_Año"] = df_movimientos["Fecha"].dt.strftime("%Y-%m")
        meses_disponibles = sorted([m for m in df_movimientos["Mes_Año"].dropna().unique()], reverse=True)
        
        if meses_disponibles:
            mes_sel = st.selectbox("Seleccionar Mes", meses_disponibles, index=0)
            df_mes = df_movimientos[df_movimientos["Mes_Año"] == mes_sel]
            
            tot_ingresos = df_mes[df_mes["Tipo"] == "Ingreso"]["Monto_ARS"].sum()
            tot_gastos = df_mes[df_mes["Tipo"] == "Gasto"]["Monto_ARS"].sum()
            tot_ahorros = df_mes[df_mes["Tipo"].str.startswith("Ahorro")]["Monto_ARS"].sum()
            balance_neto = tot_ingresos - tot_gastos
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            col_m1.metric("Ingresos Totales", f"${tot_ingresos:,.2f}")
            col_m2.metric("Gastos Totales", f"${tot_gastos:,.2f}")
            col_m3.metric("Resultado Neto", f"${balance_neto:,.2f}")
            col_m4.metric("Ahorros e Inversiones", f"${tot_ahorros:,.2f}")
            
            st.divider()
            
            # DESGLOSE DE MOVIMIENTOS DEL MES
            st.subheader("📜 Desglose de Movimientos Cargados en el Mes")
            df_display = df_mes.copy()
            df_display["Fecha"] = df_display["Fecha"].dt.strftime("%Y-%m-%d")
            df_display["Monto_ARS_Form"] = df_display["Monto_ARS"].apply(lambda x: f"${x:,.2f}")
            
            st.dataframe(
                df_display[[
                    "Fecha", "Tipo", "Caja_Origen", "Caja_Destino", "Rubro", "Concepto", "Monto_ARS_Form"
                ]].rename(columns={"Monto_ARS_Form": "Monto ($)"}),
                use_container_width=True
            )
            
            st.divider()
            st.subheader("📊 Desglose de Gastos por Rubro")
            df_gastos_rubro = df_mes[df_mes["Tipo"] == "Gasto"].groupby("Rubro")["Monto_ARS"].sum().reset_index()
            if not df_gastos_rubro.empty:
                df_gastos_rubro["Monto Formateado"] = df_gastos_rubro["Monto_ARS"].apply(lambda x: f"${x:,.2f}")
                st.dataframe(df_gastos_rubro[["Rubro", "Monto Formateado"]].sort_values(by="Rubro"), use_container_width=True)
            else:
                st.info("No hay gastos registrados en este mes.")
    else:
        st.info("No hay movimientos registrados para mostrar métricas.")

# ---------------------------------------------------------
# TAB 3: SALDOS POR CAJA Y RECONCILIACIÓN
# ---------------------------------------------------------
with tab_cajas:
    st.subheader("Estado de Cuentas y Disponibilidades")
    
    saldos_dict = {c: 0.0 for c in CAJAS_DISPONIBLES}
    
    if not df_saldos_base.empty and "Caja / Cuenta" in df_saldos_base.columns:
        for _, r in df_saldos_base.iterrows():
            caja_nombre = str(r.get("Caja / Cuenta", "")).strip()
            if caja_nombre in saldos_dict:
                saldos_dict[caja_nombre] = limpiar_monto(r.get("Saldo Inicial", 0.0))
                
    if not df_movimientos.empty:
        for _, row in df_movimientos.iterrows():
            tipo = str(row.get("Tipo", "")).strip()
            c_orig = str(row.get("Caja_Origen", "")).strip()
            c_dest = str(row.get("Caja_Destino", "")).strip()
            monto = float(row.get("Monto_ARS", 0.0))
            
            if tipo == "Ingreso" and c_dest in saldos_dict:
                saldos_dict[c_dest] += monto
            elif tipo == "Gasto" and c_orig in saldos_dict:
                saldos_dict[c_orig] -= monto
            elif tipo.startswith("Ahorro") or tipo == "Transferencia":
                if c_orig in saldos_dict:
                    saldos_dict[c_orig] -= monto
                if c_dest in saldos_dict:
                    saldos_dict[c_dest] += monto

    tc_ref = obtener_tc_oficial()
    df_resumen_cajas = pd.DataFrame([
        {
            "Caja / Cuenta": caja,
            "Saldo Actual ARS": f"${monto:,.2f}",
            "Saldo Aprox USD": f"US$ {round(monto / tc_ref, 2):,.2f}" if tc_ref > 0 else "US$ 0.00"
        }
        for caja, monto in saldos_dict.items()
    ])
    
    st.dataframe(df_resumen_cajas, use_container_width=True)
