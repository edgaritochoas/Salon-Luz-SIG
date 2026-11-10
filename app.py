import sqlite3
import streamlit as st
import pandas as pd
from datetime import datetime

# Configuración inicial de la página
st.set_page_config(page_title="Salón Luz - SIG", layout="centered")

def conectar():
    return sqlite3.connect('salon_luz.db')

st.title("✂️ Salón Luz - Sistema Gerencial")

# CREAMOS DOS PESTAÑAS: Una para la Cajera y otra para la Dueña
tab1, tab2 = st.tabs(["🛒 Punto de Venta (POS)", "📊 Cierre de Caja"])

# --- PESTAÑA 1: EL PUNTO DE VENTA (CAPA TPS) ---
with tab1:
    st.markdown("### Registro Transaccional y Emisión de Pre-Ticket")
    
    conn = conectar()
    df_colaboradores = pd.read_sql_query("SELECT * FROM COLABORADORES", conn)
    df_servicios = pd.read_sql_query("SELECT * FROM SERVICIOS", conn)
    conn.close()

    # Formulario
    with st.form("caja_form"):
        col1, col2 = st.columns(2)
        with col1:
            estilista = st.selectbox("1. Estilista", df_colaboradores['nombre'])
            servicio = st.selectbox("2. Servicio", df_servicios['nombre_servicio'])
        with col2:
            monto = st.number_input("3. Monto Cobrado (S/)", min_value=0.0, format="%.2f", step=10.0)
            pago = st.selectbox("4. Medio de Pago", ["Yape", "Efectivo", "Plin", "Tarjeta"])
        
        submit = st.form_submit_button("Registrar Venta e Imprimir Pre-Ticket")

    if submit:
        if monto > 0:
            # Buscar datos exactos en la BD
            id_colab = df_colaboradores[df_colaboradores['nombre'] == estilista]['id_colaborador'].values[0]
            porcentaje = df_colaboradores[df_colaboradores['nombre'] == estilista]['porcentaje_acordado'].values[0]
            id_serv = df_servicios[df_servicios['nombre_servicio'] == servicio]['id_servicio'].values[0]
            
            # Matemática de comisiones
            comision = float(monto) * float(porcentaje)
            ganancia = float(monto) - comision
            
            # Guardar en Base de Datos (SQL)
            conn = conectar()
            cursor = conn.cursor()
            cursor.execute('''INSERT INTO VENTAS_TPS 
                              (id_colaborador, id_servicio, monto_cobrado, comision_pagada, ganancia_salon_liquida, medio_pago) 
                              VALUES (?, ?, ?, ?, ?, ?)''', 
                           (int(id_colab), int(id_serv), float(monto), float(comision), float(ganancia), pago))
            id_ticket = cursor.lastrowid # Recuperar el N° de transacción
            conn.commit()
            conn.close()
            
            # --- GENERAR EL PRE-TICKET VISUAL ---
            st.success("✅ Venta guardada en la nube (SQLite).")
            
            st.markdown(f"""
            <div style="border: 2px dashed #4CAF50; padding: 20px; border-radius: 10px; text-align: center; background-color: #1e1e1e; color: white;">
                <h3 style="margin-top: 0;">💇‍♀️ SALÓN LUZ 💇‍♂️</h3>
                <p style="margin:0;"><b>Pre-Ticket Auditable N°:</b> 000-{id_ticket}</p>
                <p style="margin:0;"><b>Fecha:</b> {datetime.now().strftime("%d/%m/%Y %H:%M")}</p>
                <hr style="border: 1px dashed #4CAF50;">
                <p style="margin:5px 0;"><b>Servicio:</b> {servicio}</p>
                <p style="margin:5px 0;"><b>Atendido por:</b> {estilista.split(' ')[0]}</p>
                <p style="margin:5px 0;"><b>Medio de Pago:</b> {pago}</p>
                <hr style="border: 1px dashed #4CAF50;">
                <h2 style="color: #4CAF50; margin: 10px 0;">TOTAL COBRADO: S/ {monto:.2f}</h2>
                <p style="font-size: 12px; color: #aaa; margin:0;">Este ticket evita el subregistro de caja.</p>
            </div>
            """, unsafe_allow_html=True)
            
        else:
            st.error("⚠️ El monto debe ser mayor a 0.")

# --- PESTAÑA 2: CIERRE DE CAJA AUTOMÁTICO ---
with tab2:
    st.markdown("### 📈 Cierre de Caja Diario")
    conn = conectar()
    
    # CORRECCIÓN: Le decimos a SQL que convierta la hora a 'localtime' (Hora Perú)
    query_general = """
        SELECT SUM(monto_cobrado) as Ingresos_Totales, SUM(comision_pagada) as Pago_Estilistas, SUM(ganancia_salon_liquida) as Ganancia_Salon
        FROM VENTAS_TPS WHERE date(fecha, 'localtime') = date('now', 'localtime')
    """
    df_general = pd.read_sql_query(query_general, conn)
    
    if df_general['Ingresos_Totales'][0] is not None:
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Ingresos Totales (Hoy)", f"S/ {df_general['Ingresos_Totales'][0]:.2f}")
        col_b.metric("A Pagar a Estilistas", f"S/ {df_general['Pago_Estilistas'][0]:.2f}")
        col_c.metric("Ganancia Neta Salón", f"S/ {df_general['Ganancia_Salon'][0]:.2f}")
        
        st.markdown("#### ✂️ Comisiones a Pagar por Estilista")
        
        # CORRECCIÓN TAMBIÉN AQUÍ PARA LA TABLA
        query_colab = """
            SELECT c.nombre as Estilista, COUNT(v.id_venta) as Servicios, SUM(v.comision_pagada) as Total_a_Pagar
            FROM VENTAS_TPS v JOIN COLABORADORES c ON v.id_colaborador = c.id_colaborador
            WHERE date(v.fecha, 'localtime') = date('now', 'localtime') GROUP BY c.nombre
        """
        df_colab = pd.read_sql_query(query_colab, conn)
        st.dataframe(df_colab, use_container_width=True, hide_index=True)
    else:
        st.write("Aún no hay ventas registradas el día de hoy.")
    conn.close()