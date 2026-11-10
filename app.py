import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Salón Luz - SIG", layout="centered")

def conectar():
    return sqlite3.connect('salon_luz.db')

# --- 1. SISTEMA DE LOGIN Y ROLES ---
# Creamos la memoria de la sesión para saber si alguien ya entró
if 'logeado' not in st.session_state:
    st.session_state.logeado = False
    st.session_state.rol = ''

# Si no está logeado, mostramos el candado
if not st.session_state.logeado:
    st.title("🔒 Acceso Seguro - Salón Luz")
    st.info("El sistema está protegido. Ingrese sus credenciales para continuar.")
    
    with st.form("login_form"):
        usuario = st.selectbox("Usuario", ["Cajera", "Administradora"])
        clave = st.text_input("Contraseña", type="password")
        submit_login = st.form_submit_button("Ingresar")
        
        if submit_login:
            # Validamos las contraseñas
            if usuario == "Cajera" and clave == "caja123":
                st.session_state.logeado = True
                st.session_state.rol = "Cajera"
                st.rerun() # Actualiza la pantalla
            elif usuario == "Administradora" and clave == "admin123":
                st.session_state.logeado = True
                st.session_state.rol = "Administradora"
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
                
# --- 2. SISTEMA PRINCIPAL (SOLO SI PASÓ EL LOGIN) ---
else:
    # Menú lateral para cerrar sesión
    st.sidebar.success(f"👤 Conectado como: **{st.session_state.rol}**")
    if st.sidebar.button("Cerrar Sesión"):
        st.session_state.logeado = False
        st.session_state.rol = ''
        st.rerun()

    st.title("✂️ Salón Luz - Sistema Gerencial")

    # MAGIA DE ROLES: Dependiendo de quién entró, mostramos pestañas distintas
    if st.session_state.rol == "Administradora":
        tab1, tab2 = st.tabs(["🛒 Punto de Venta (POS)", "📊 Cierre de Caja Confidencial"])
    else:
        # La cajera NO tiene acceso a la pestaña 2
        tab1, = st.tabs(["🛒 Punto de Venta (POS)"])

    # --- PESTAÑA 1 (Ambos roles la ven) ---
    with tab1:
        st.markdown("### Registro Transaccional")
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
            cursor.execute('''INSERT INTO VENTAS_TPS 
                              (id_colaborador, id_servicio, monto_cobrado, comision_pagada, ganancia_salon_liquida, medio_pago) 
                              VALUES (?, ?, ?, ?, ?, ?)''', 
                           (int(id_colab), int(id_serv), float(monto), float(comision), float(ganancia), pago))
            id_ticket = cursor.lastrowid 
            conn.commit()
            conn.close()
            
            st.markdown(f"""
            <div style="border: 2px dashed #4CAF50; padding: 20px; border-radius: 10px; text-align: center; background-color: #1e1e1e; color: white; margin-top: 15px;">
                <h3 style="margin-top: 0; color: #4CAF50;">💇‍♀️ SALÓN LUZ 💇‍♂️</h3>
                <p style="margin:0;"><b>Pre-Ticket Auditable N°:</b> 000-{id_ticket}</p>
                <p style="margin:0; font-size: 14px; color: #ccc;"><b>Fecha:</b> {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
                <hr style="border: 1px dashed #4CAF50;">
                <p style="margin:5px 0;"><b>Servicio:</b> {servicio}</p>
                <p style="margin:5px 0;"><b>Atendido por:</b> {estilista.split(' ')[0]}</p>
                <h2 style="color: #4CAF50; margin: 10px 0;">TOTAL: S/ {monto:.2f}</h2>
            </div>
            """, unsafe_allow_html=True)

  # --- PESTAÑA 2 (Protegida: Solo la ve la Administradora) ---
if st.session_state.rol == "Administradora":
    with tab2:
        st.markdown("### 📈 Cierre de Caja Diario (Hora Perú)")
        conn = conectar()
        
        # CORRECCIÓN: Forzamos la zona horaria UTC-5 (Lima, Perú)
        query_general = """
            SELECT SUM(monto_cobrado) as Ingresos_Totales, SUM(comision_pagada) as Pago_Estilistas, SUM(ganancia_salon_liquida) as Ganancia_Salon
            FROM VENTAS_TPS 
            WHERE date(fecha, '-5 hours') = date('now', '-5 hours')
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
                WHERE date(v.fecha, '-5 hours') = date('now', '-5 hours') 
                GROUP BY c.nombre
            """
            df_colab = pd.read_sql_query(query_colab, conn)
            st.dataframe(df_colab, use_container_width=True, hide_index=True)
        else:
            st.write("Aún no hay ventas registradas el día de hoy.")
        conn.close()