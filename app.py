import streamlit as st
import pandas as pd
from datetime import datetime
import psycopg2

st.set_page_config(page_title="Salón Luz - SIG", layout="centered")

# --- CONEXIÓN A LA NUBE (SUPABASE) ---
DB_URI = "postgresql://postgres:AdminSalonLuz2026!@db.couvhlpyufqbhaczqoto.supabase.co:5432/postgres"

def conectar():
    return psycopg2.connect(DB_URI)

# --- 1. SISTEMA DE LOGIN Y ROLES ---
if 'logeado' not in st.session_state:
    st.session_state.logeado = False
    st.session_state.rol = ''

if not st.session_state.logeado:
    st.title("🔒 Acceso Seguro - Salón Luz")
    st.info("El sistema está conectado a la Nube. Ingrese sus credenciales.")
    
    with st.form("login_form"):
        usuario = st.selectbox("Usuario", ["Cajera", "Administradora"])
        clave = st.text_input("Contraseña", type="password")
        submit_login = st.form_submit_button("Ingresar")
        
        if submit_login:
            if usuario == "Cajera" and clave == "caja123":
                st.session_state.logeado = True
                st.session_state.rol = "Cajera"
                st.rerun()
            elif usuario == "Administradora" and clave == "admin123":
                st.session_state.logeado = True
                st.session_state.rol = "Administradora"
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
                
# --- 2. SISTEMA PRINCIPAL ---
else:
    st.sidebar.success(f"👤 Conectado como: **{st.session_state.rol}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logeado = False
        st.session_state.rol = ''
        st.rerun()

    st.title("✂️ Salón Luz - Sistema Gerencial")

    if st.session_state.rol == "Administradora":
        tab1, tab2 = st.tabs(["🛒 Punto de Venta (POS)", "📊 Cierre de Caja Confidencial"])
    else:
        tab1, = st.tabs(["🛒 Punto de Venta (POS)"])

    # --- PESTAÑA 1 (Caja) ---
    with tab1:
        st.markdown("### Registro Transaccional (Cloud)")
        conn = conectar()
        df_colaboradores = pd.read_sql_query("SELECT * FROM COLABORADORES", conn)
        df_servicios = pd.read_sql_query("SELECT * FROM SERVICIOS", conn)
        conn.close()

        with st.form("caja_form"):
            col1, col2 = st.columns(2)
            with col1:
                estilista = st.selectbox("1. Estilista", df_colaboradores['nombre'])
                servicio = st.selectbox("2. Servicio", df_servicios['nombre_servicio'])
            with col2:
                monto = st.number_input("3. Monto Cobrado (S/)", min_value=0.0, format="%.2f", step=10.0)
                pago = st.selectbox("4. Medio de Pago", ["Yape", "Efectivo", "Plin", "Tarjeta"])
            
            submit = st.form_submit_button("Registrar e Imprimir Pre-Ticket")

        if submit and monto > 0:
            id_colab = df_colaboradores[df_colaboradores['nombre'] == estilista]['id_colaborador'].values[0]
            porcentaje = df_colaboradores[df_colaboradores['nombre'] == estilista]['porcentaje_acordado'].values[0]
            id_serv = df_servicios[df_servicios['nombre_servicio'] == servicio]['id_servicio'].values[0]
            
            comision = float(monto) * float(porcentaje)
            ganancia = float(monto) - comision
            
            conn = conectar()
            cursor = conn.cursor()
            # Sintaxis PostgreSQL
            cursor.execute('''INSERT INTO VENTAS_TPS 
                              (id_colaborador, id_servicio, monto_cobrado, comision_pagada, ganancia_salon_liquida, medio_pago) 
                              VALUES (%s, %s, %s, %s, %s, %s) RETURNING id_venta''', 
                           (int(id_colab), int(id_serv), float(monto), float(comision), float(ganancia), pago))
            id_ticket = cursor.fetchone()[0]
            conn.commit()
            conn.close()
            
            st.markdown(f"""
            <div style="border: 2px dashed #4CAF50; padding: 20px; border-radius: 10px; text-align: center; background-color: #1e1e1e; color: white; margin-top: 15px;">
                <h3 style="margin-top: 0; color: #4CAF50;">💇‍♀️ SALÓN LUZ 💇‍♂️</h3>
                <p style="margin:0;"><b>Pre-Ticket Auditable N°:</b> 000-{id_ticket}</p>
                <hr style="border: 1px dashed #4CAF50;">
                <p style="margin:5px 0;"><b>Servicio:</b> {servicio}</p>
                <p style="margin:5px 0;"><b>Atendido por:</b> {estilista.split(' ')[0]}</p>
                <h2 style="color: #4CAF50; margin: 10px 0;">TOTAL: S/ {monto:.2f}</h2>
            </div>
            """, unsafe_allow_html=True)

    # --- PESTAÑA 2 (Reportes) ---
    if st.session_state.rol == "Administradora":
        with tab2:
            st.markdown("### 📈 Cierre de Caja Diario (Hora Perú)")
            conn = conectar()
            
            # Sintaxis PostgreSQL para Zonas Horarias (UTC-5)
            query_general = """
                SELECT SUM(monto_cobrado) as Ingresos_Totales, SUM(comision_pagada) as Pago_Estilistas, SUM(ganancia_salon_liquida) as Ganancia_Salon
                FROM VENTAS_TPS 
                WHERE (fecha - INTERVAL '5 hours')::date = (CURRENT_TIMESTAMP - INTERVAL '5 hours')::date
            """
            df_general = pd.read_sql_query(query_general, conn)
            
            if df_general['Ingresos_Totales'][0] is not None:
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Ingresos Totales (Hoy)", f"S/ {df_general['Ingresos_Totales'][0]:.2f}")
                col_b.metric("A Pagar a Estilistas", f"S/ {df_general['Pago_Estilistas'][0]:.2f}")
                col_c.metric("Ganancia Neta Salón", f"S/ {df_general['Ganancia_Salon'][0]:.2f}")
                
                st.markdown("#### ✂️ Comisiones a Pagar")
                query_colab = """
                    SELECT c.nombre as Estilista, COUNT(v.id_venta) as Servicios, SUM(v.comision_pagada) as Total_a_Pagar
                    FROM VENTAS_TPS v JOIN COLABORADORES c ON v.id_colaborador = c.id_colaborador
                    WHERE (v.fecha - INTERVAL '5 hours')::date = (CURRENT_TIMESTAMP - INTERVAL '5 hours')::date 
                    GROUP BY c.nombre
                """
                df_colab = pd.read_sql_query(query_colab, conn)
                st.dataframe(df_colab, use_container_width=True, hide_index=True)
            else:
                st.write("Aún no hay ventas registradas el día de hoy.")
            conn.close()