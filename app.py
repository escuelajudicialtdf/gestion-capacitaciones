import streamlit as st
import sqlite3
import pandas as pd
from PIL import Image
from datetime import date, datetime
import os
import base64
import io

# --- 1. CONFIGURACIÓN DE USUARIOS Y CONTRASEÑAS ---
USUARIOS = {
    "Escuelajudicial": {
        "password": "20Superior",
        "role": "admin"
    },
    "Invitado": {
        "password": "Metodos2025",
        "role": "invitado"
    }
}

# --------------------------------------------------------------------------------
# LÓGICA DE LOGIN
# --------------------------------------------------------------------------------
def login():
    st.set_page_config(page_title="Login", layout="centered")
    st.header("Gestión en Mediación")
    st.subheader("Inicio de Sesión")

    with st.form("login_form"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

        if submitted:
            user_data = USUARIOS.get(username)
            if user_data and user_data["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.role = user_data["role"]
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")

# Inicializa el estado de la sesión si no existe
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Si no está logueado, muestra el formulario de login. Si sí, muestra la app.
if not st.session_state.logged_in:
    login()
else:
    # --- APLICACIÓN PRINCIPAL ---
    st.set_page_config(page_title="Gestión en Mediación", layout="wide")

    @st.cache_data
    def cargar_excel_completo():
        try:
            excel_data = pd.read_excel(
                "datos_mediacion.xlsx",
                sheet_name=['Personal', 'Inscripciones'],
                dtype={'DNI': str, 'Legajo': str, 'Celular': str}
            )
            df_personal = excel_data.get('Personal')
            if df_personal is not None:
                df_personal['Busqueda'] = df_personal['Apellido'] + ", " + df_personal['Nombre'] + " (DNI: " + df_personal['DNI'] + ")"
            return excel_data
        except FileNotFoundError:
            st.error("Error: No se encontró el archivo 'datos_mediacion.xlsx'. Asegúrate de que esté en la misma carpeta.")
            return None
        except Exception as e:
            st.error(f"Error al leer 'datos_mediacion.xlsx': {e}")
            return None

    excel_data = cargar_excel_completo()

    st.markdown("""
    <style>
        [data-testid="stSidebar"] > div:first-child {
            display: flex;
            flex-direction: column;
            align-items: center;
            width: 100%;
        }
        h2, h3 { color: #1e5a8c; }
    </style>
    """, unsafe_allow_html=True)

    ESTADOS_INSCRIPCION = ["Completo", "Incompleto"]

    def init_db():
        conn = sqlite3.connect('capacitaciones.db')
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS capacitaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT, titulo TEXT NOT NULL, año INTEGER NOT NULL,
                docentes TEXT, aclaracion TEXT, modalidad TEXT, fecha_inicio TEXT, fecha_fin TEXT,
                realizado_ushuaia BOOLEAN, realizado_tolhuin BOOLEAN, realizado_rio_grande BOOLEAN,
                UNIQUE (titulo, año)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS alumnos (
                id INTEGER PRIMARY KEY AUTOINCREMENT, dni TEXT UNIQUE, legajo TEXT, nombre TEXT, apellido TEXT,
                email TEXT, email_alternativo TEXT, tipo TEXT, celular TEXT, lugar_de_trabajo TEXT, profesion TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS inscripciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT, alumno_id INTEGER, capacitacion_id INTEGER, status TEXT,
                FOREIGN KEY (alumno_id) REFERENCES alumnos(id) ON DELETE CASCADE,
                FOREIGN KEY (capacitacion_id) REFERENCES capacitaciones(id) ON DELETE CASCADE,
                UNIQUE (alumno_id, capacitacion_id)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS clases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capacitacion_id INTEGER,
                fecha_clase TEXT NOT NULL,
                tema TEXT,
                FOREIGN KEY (capacitacion_id) REFERENCES capacitaciones(id) ON DELETE CASCADE,
                UNIQUE (capacitacion_id, fecha_clase)
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS asistencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                clase_id INTEGER,
                alumno_id INTEGER,
                presente BOOLEAN NOT NULL CHECK (presente IN (0, 1)),
                FOREIGN KEY (clase_id) REFERENCES clases(id) ON DELETE CASCADE,
                FOREIGN KEY (alumno_id) REFERENCES alumnos(id) ON DELETE CASCADE,
                UNIQUE (clase_id, alumno_id)
            )
        ''')
        conn.commit()
        conn.close()

    init_db()

    def get_db_connection():
        conn = sqlite3.connect('capacitaciones.db')
        conn.row_factory = sqlite3.Row
        return conn

    with st.sidebar:
        try:
            logo = Image.open("Logopj.png")
            st.image(logo, width=120)
        except FileNotFoundError:
            st.error("No se encontró 'Logopj.png'")
        st.title("Gestión Capacitaciones en Mediación")
        st.divider()

        st.write(f"Bienvenido, **{st.session_state.username}**")
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False
            st.session_state.opcion_menu = "INICIO"
            st.session_state.asistencia_cap_id = None
            st.session_state.editing_capacitacion_id = None
            st.rerun()
        st.divider()

        if 'opcion_menu' not in st.session_state:
            st.session_state.opcion_menu = "INICIO"

        if st.session_state.role == 'admin':
            opciones = ["INICIO", "ALUMNOS", "CAPACITACION", "BUSCADOR", "NORMATIVA"]
        else:
            opciones = ["INICIO", "ALUMNOS", "BUSCADOR", "NORMATIVA"]

        for opcion in opciones:
            if st.button(opcion, use_container_width=True, key=f"menu_{opcion}"):
                st.session_state.opcion_menu = opcion
        
        opcion_menu = st.session_state.opcion_menu
        st.divider()

    if opcion_menu == "INICIO":
        if 'asistencia_cap_id' not in st.session_state: st.session_state.asistencia_cap_id = None
        if st.session_state.asistencia_cap_id:
            conn = get_db_connection()
            cap_id = st.session_state.asistencia_cap_id
            cap_info = conn.execute("SELECT titulo, año FROM capacitaciones WHERE id = ?", (cap_id,)).fetchone()
            st.header(f"Gestión de Asistencia"); st.subheader(f"{cap_info['titulo']} ({cap_info['año']})")
            if st.button("⬅️ Volver al listado de capacitaciones"):
                st.session_state.asistencia_cap_id = None; st.rerun()
            tabs = ["Gestionar Fechas", "Registrar Asistencia", "Planillas de Asistencia", "Enviar Emails"]
            tab1, tab2, tab3, tab4 = st.tabs(tabs)
            with tab1:
                st.subheader("Agregar y ver fechas de clases")
                with st.form("form_nueva_fecha"):
                    nueva_fecha = st.date_input("Fecha de la nueva clase")
                    tema_clase = st.text_input("Tema o descripción de la clase (opcional)")
                    if st.form_submit_button("Agregar Fecha"):
                        try:
                            conn.execute("INSERT INTO clases (capacitacion_id, fecha_clase, tema) VALUES (?, ?, ?)",
                                         (cap_id, nueva_fecha.strftime("%Y-%m-%d"), tema_clase))
                            conn.commit(); st.success(f"Fecha {nueva_fecha.strftime('%d/%m/%Y')} agregada.")
                        except sqlite3.IntegrityError: st.warning("Esa fecha ya existe para esta capacitación.")
                st.divider()
                clases_existentes = conn.execute("SELECT id, fecha_clase, tema FROM clases WHERE capacitacion_id = ? ORDER BY fecha_clase", (cap_id,)).fetchall()
                if not clases_existentes: st.info("Aún no se han agregado fechas para esta capacitación.")
                else:
                    for clase in clases_existentes:
                        cols = st.columns([4, 1])
                        cols[0].write(f"**Fecha:** {datetime.strptime(clase['fecha_clase'], '%Y-%m-%d').strftime('%d/%m/%Y')} - **Tema:** {clase['tema'] or 'N/A'}")
                        if cols[1].button("Eliminar", key=f"del_clase_{clase['id']}", type="primary"):
                            conn.execute("DELETE FROM clases WHERE id = ?", (clase['id'],)); conn.commit(); st.rerun()
            with tab2:
                st.subheader("Seleccionar una clase para registrar asistencia")
                clases_existentes = conn.execute("SELECT id, fecha_clase, tema FROM clases WHERE capacitacion_id = ? ORDER BY fecha_clase", (cap_id,)).fetchall()
                if not clases_existentes: st.warning("Primero debes agregar fechas de clases en la pestaña 'Gestionar Fechas'.")
                else:
                    mapa_clases = {f"{datetime.strptime(c['fecha_clase'], '%Y-%m-%d').strftime('%d/%m/%Y')} - {c['tema'] or 'Clase'}": c['id'] for c in clases_existentes}
                    clase_seleccionada_str = st.selectbox("Elige una fecha:", options=mapa_clases.keys())
                    if clase_seleccionada_str:
                        clase_id = mapa_clases[clase_seleccionada_str]
                        inscriptos = conn.execute("SELECT a.id, a.apellido, a.nombre FROM alumnos a JOIN inscripciones i ON a.id = i.alumno_id WHERE i.capacitacion_id = ? ORDER BY a.apellido, a.nombre", (cap_id,)).fetchall()
                        asistencia_actual = {row['alumno_id']: row['presente'] for row in conn.execute("SELECT alumno_id, presente FROM asistencias WHERE clase_id = ?", (clase_id,)).fetchall()}
                        with st.form("form_asistencia"):
                            nuevas_asistencias = {}
                            for alumno in inscriptos:
                                nuevas_asistencias[alumno['id']] = st.checkbox(f"{alumno['apellido']}, {alumno['nombre']}", value=asistencia_actual.get(alumno['id'], False), key=f"asist_{alumno['id']}")
                            if st.form_submit_button("Guardar Asistencia"):
                                for alumno_id, presente in nuevas_asistencias.items():
                                    conn.execute("INSERT INTO asistencias (clase_id, alumno_id, presente) VALUES (?, ?, ?) ON CONFLICT(clase_id, alumno_id) DO UPDATE SET presente = excluded.presente", (clase_id, alumno_id, presente))
                                conn.commit(); st.success(f"Asistencia para la clase del {clase_seleccionada_str.split(' - ')[0]} guardada.")
            with tab3:
                st.subheader("Generar y descargar planillas")
                clases_existentes_dl = conn.execute("SELECT id, fecha_clase FROM clases WHERE capacitacion_id = ? ORDER BY fecha_clase", (cap_id,)).fetchall()
                inscriptos_dl = conn.execute("SELECT a.id, apellido, nombre, dni FROM alumnos a JOIN inscripciones i ON a.id = i.alumno_id WHERE i.capacitacion_id = ? ORDER BY a.apellido, a.nombre", (cap_id,)).fetchall()
                st.markdown("**1. Planilla para Firmas (por clase)**")
                if not clases_existentes_dl: st.info("Agrega fechas de clases para poder descargar planillas.")
                else:
                    mapa_clases_dl = {f"{datetime.strptime(c['fecha_clase'], '%Y-%m-%d').strftime('%d/%m/%Y')}": c['id'] for c in clases_existentes_dl}
                    fecha_para_firmas = st.selectbox("Selecciona la fecha de la clase:", options=mapa_clases_dl.keys())
                    df_firmas = pd.DataFrame(inscriptos_dl, columns=['id', 'Apellido', 'Nombre', 'DNI'])[['Apellido', 'Nombre', 'DNI']]; df_firmas['Firma'] = ''
                    output_firmas = io.BytesIO()
                    with pd.ExcelWriter(output_firmas, engine='xlsxwriter') as writer:
                        df_firmas.to_excel(writer, index=False, sheet_name=f"Asistencia_{fecha_para_firmas.replace('/', '-')}")
                        worksheet = writer.sheets[f"Asistencia_{fecha_para_firmas.replace('/', '-')}"]; worksheet.set_column('A:C', 25); worksheet.set_column('D:D', 30)
                    st.download_button(label="📥 Descargar Planilla para Firmas", data=output_firmas.getvalue(), file_name=f"firmas_{cap_info['titulo']}_{fecha_para_firmas.replace('/', '-')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                st.divider()
                st.markdown("**2. Reporte Consolidado de Asistencia**")
                if st.button("Generar Reporte Consolidado"):
                    asistencias_raw = conn.execute("SELECT a.id as alumno_id, a.apellido, a.nombre, c.fecha_clase, s.presente FROM asistencias s JOIN clases c ON s.clase_id = c.id JOIN alumnos a ON s.alumno_id = a.id WHERE c.capacitacion_id = ?", (cap_id,)).fetchall()
                    if not asistencias_raw: st.warning("No hay registros de asistencia para generar un reporte consolidado.")
                    else:
                        df_consolidado = pd.DataFrame(asistencias_raw)
                        df_consolidado.columns = ['alumno_id', 'apellido', 'nombre', 'fecha_clase', 'presente']
                        df_consolidado['presente'] = df_consolidado['presente'].apply(lambda x: 'Presente' if x else 'Ausente')
                        df_consolidado['fecha_clase'] = pd.to_datetime(df_consolidado['fecha_clase']).dt.strftime('%d/%m/%Y')
                        df_pivot = df_consolidado.pivot_table(index=['apellido', 'nombre'], columns='fecha_clase', values='presente', aggfunc='first').reset_index()
                        output_consolidado = io.BytesIO()
                        with pd.ExcelWriter(output_consolidado, engine='xlsxwriter') as writer:
                            df_pivot.to_excel(writer, index=False, sheet_name='Reporte Consolidado'); writer.sheets['Reporte Consolidado'].set_column('A:B', 25)
                        st.download_button(label="📥 Descargar Reporte Consolidado", data=output_consolidado.getvalue(), file_name=f"reporte_asistencia_{cap_info['titulo']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            with tab4:
                st.subheader("Comunicación con Alumnos por Asistencia")
                total_clases = len(conn.execute("SELECT id FROM clases WHERE capacitacion_id = ?", (cap_id,)).fetchall())
                st.info(f"Esta capacitación tiene un total de **{total_clases}** clases registradas.")
                if total_clases > 0:
                    min_asistencias = st.number_input("Mínimo de clases presentes para enviar email:", min_value=1, max_value=total_clases, value=total_clases, step=1)
                    if st.button("Filtrar alumnos y obtener emails"):
                        query = """
                            SELECT a.apellido, a.nombre, a.email, COALESCE(SUM(s.presente), 0) as clases_presente
                            FROM alumnos a
                            JOIN inscripciones i ON a.id = i.alumno_id
                            LEFT JOIN clases c ON i.capacitacion_id = c.capacitacion_id
                            LEFT JOIN asistencias s ON a.id = s.alumno_id AND s.clase_id = c.id
                            WHERE i.capacitacion_id = ?
                            GROUP BY a.id, a.apellido, a.nombre, a.email
                            HAVING clases_presente >= ?
                            ORDER BY a.apellido, a.nombre
                        """
                        alumnos_calificados = conn.execute(query, (cap_id, min_asistencias)).fetchall()
                        if not alumnos_calificados: st.warning("No se encontraron alumnos que cumplan con el criterio de asistencia.")
                        else:
                            st.success(f"Se encontraron {len(alumnos_calificados)} alumnos que cumplen el requisito:")
                            nombres = [f"- {a['apellido']}, {a['nombre']}" for a in alumnos_calificados]
                            st.markdown("\n".join(nombres))
                            emails = [a['email'] for a in alumnos_calificados if a['email']]
                            lista_emails = "; ".join(emails)
                            st.markdown("**Lista de emails para copiar:**")
                            st.text_area("Copia esta lista y pégala en el campo CCO (o BCC) de tu correo electrónico.", value=lista_emails, height=150)
                else: st.warning("Agrega y registra la asistencia de las clases para poder usar esta función.")
            conn.close()
        else:
            st.header("Listado de Capacitaciones"); st.info("Expanda una capacitación para ver sus detalles.")
            conn = get_db_connection(); capacitaciones = conn.execute('SELECT * FROM capacitaciones ORDER BY año DESC, fecha_inicio DESC').fetchall()
            if 'editing_capacitacion_id' not in st.session_state: st.session_state.editing_capacitacion_id = None
            if not capacitaciones: st.warning("Aún no hay capacitaciones cargadas en el sistema.")
            for cap in capacitaciones:
                with st.expander(f"**{cap['titulo']}** ({cap['año']})", expanded=(st.session_state.editing_capacitacion_id == cap['id'])):
                    if st.session_state.role == 'admin' and st.session_state.editing_capacitacion_id == cap['id']:
                        st.subheader("📝 Modificar Capacitación")
                        alumnos_db = conn.execute("SELECT id, dni, apellido, nombre FROM alumnos ORDER BY apellido").fetchall()
                        mapa_alumnos_completo = {f"{a['apellido']}, {a['nombre']} (DNI: {a['dni']})": a['id'] for a in alumnos_db}
                        inscriptos_actuales_ids = [row['alumno_id'] for row in conn.execute("SELECT alumno_id FROM inscripciones WHERE capacitacion_id = ?", (cap['id'],)).fetchall()]
                        inscriptos_actuales_str = [key for key, val in mapa_alumnos_completo.items() if val in inscriptos_actuales_ids]
                        with st.form(key=f"form_modificar_{cap['id']}"):
                            titulo = st.text_input("Título", value=cap['titulo']); año = st.number_input("Año", min_value=2005, max_value=date.today().year + 5, value=cap['año'])
                            try: fecha_inicio_val = datetime.strptime(cap['fecha_inicio'], "%Y-%m-%d").date() if cap['fecha_inicio'] else None; fecha_fin_val = datetime.strptime(cap['fecha_fin'], "%Y-%m-%d").date() if cap['fecha_fin'] else None
                            except: fecha_inicio_val = None; fecha_fin_val = None
                            col_f1, col_f2 = st.columns(2); fecha_inicio = col_f1.date_input("Fecha de inicio", value=fecha_inicio_val); fecha_fin = col_f2.date_input("Fecha de finalización", value=fecha_fin_val)
                            modalidades = ["A determinar", "Presencial", "Virtual", "Mixta"]; modalidad_idx = modalidades.index(cap['modalidad']) if cap['modalidad'] in modalidades else 0
                            modalidad = st.selectbox("Modalidad", modalidades, index=modalidad_idx); docentes = st.text_input("Docentes", value=cap['docentes']); aclaracion = st.text_area("Aclaración", value=cap['aclaracion'])
                            st.write("Ciudad(es):"); c1, c2, c3 = st.columns(3); ushuaia = c1.checkbox("Ushuaia", value=cap['realizado_ushuaia']); tolhuin = c2.checkbox("Tolhuin", value=cap['realizado_tolhuin']); rio_grande = c3.checkbox("Río Grande", value=cap['realizado_rio_grande'])
                            st.divider(); st.subheader("Modificar Alumnos Inscriptos"); alumnos_seleccionados = st.multiselect("Seleccione los alumnos:", options=mapa_alumnos_completo.keys(), default=inscriptos_actuales_str)
                            col_save, col_cancel = st.columns(2)
                            if col_save.form_submit_button("✅ Guardar Cambios"):
                                conn.execute('UPDATE capacitaciones SET titulo=?, año=?, docentes=?, aclaracion=?, modalidad=?, fecha_inicio=?, fecha_fin=?, realizado_ushuaia=?, realizado_tolhuin=?, realizado_rio_grande=? WHERE id=?',
                                             (titulo, año, docentes, aclaracion, modalidad, fecha_inicio.strftime("%Y-%m-%d") if fecha_inicio else None, fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None, ushuaia, tolhuin, rio_grande, cap['id']))
                                nuevos_alumnos_ids = {mapa_alumnos_completo[nombre] for nombre in alumnos_seleccionados}
                                alumnos_a_eliminar = set(inscriptos_actuales_ids) - nuevos_alumnos_ids
                                if alumnos_a_eliminar: conn.executemany("DELETE FROM inscripciones WHERE alumno_id = ? AND capacitacion_id = ?", [(alu_id, cap['id']) for alu_id in alumnos_a_eliminar])
                                alumnos_a_agregar = nuevos_alumnos_ids - set(inscriptos_actuales_ids)
                                if alumnos_a_agregar: conn.executemany("INSERT INTO inscripciones (alumno_id, capacitacion_id, status) VALUES (?, ?, ?)", [(alu_id, cap['id'], "Incompleto") for alu_id in alumnos_a_agregar])
                                conn.commit(); st.success(f"Capacitación '{titulo}' actualizada."); st.session_state.editing_capacitacion_id = None; st.rerun()
                            if col_cancel.form_submit_button("❌ Cancelar"): st.session_state.editing_capacitacion_id = None; st.rerun()
                    else:
                        st.write(f"**Período:** {cap['fecha_inicio'] or 'No definido'} al {cap['fecha_fin'] or 'No definido'} | **Modalidad:** {cap['modalidad'] or 'No definida'}")
                        st.subheader("Inscriptos")
                        
                        # --- CORRECCIÓN AQUÍ: Se añade i.id a la consulta ---
                        inscriptos_query = 'SELECT i.id, a.apellido, a.nombre, i.status FROM inscripciones i JOIN alumnos a ON i.alumno_id = a.id WHERE i.capacitacion_id = ? ORDER BY a.apellido, a.nombre'
                        inscriptos = conn.execute(inscriptos_query, (cap['id'],)).fetchall()

                        if not inscriptos: st.write("Aún no hay alumnos inscriptos.")
                        else:
                            if st.session_state.role == 'admin':
                                with st.form(key=f"form_status_{cap['id']}"):
                                    nuevos_status = {}
                                    for ins in inscriptos:
                                        col1, col2 = st.columns(2); col1.write(f"{ins['apellido']}, {ins['nombre']}")
                                        status_actual = col2.selectbox("Status", ESTADOS_INSCRIPCION, index=ESTADOS_INSCRIPCION.index(ins['status']) if ins['status'] in ESTADOS_INSCRIPCION else 1, key=f"status_{ins['id']}", label_visibility="collapsed")
                                        nuevos_status[ins['id']] = status_actual
                                    if st.form_submit_button("Actualizar Estados"):
                                        for ins_id, new_status in nuevos_status.items():
                                            conn.execute("UPDATE inscripciones SET status = ? WHERE id = ?", (new_status, ins_id))
                                        conn.commit(); st.success("Estados actualizados."); st.rerun()
                            else:
                                df_inscriptos = pd.DataFrame(inscriptos, columns=['id', 'Apellido', 'Nombre', 'Status'])[['Apellido', 'Nombre', 'Status']]; st.dataframe(df_inscriptos, use_container_width=True)
                        
                        if st.session_state.role == 'admin':
                            st.divider()
                            cols_acciones = st.columns(3)
                            if cols_acciones[0].button("Modificar", key=f"mod_{cap['id']}"): st.session_state.editing_capacitacion_id = cap['id']; st.rerun()
                            if cols_acciones[1].button("Asistencia", key=f"asistencia_{cap['id']}"): st.session_state.asistencia_cap_id = cap['id']; st.rerun()
                            if cols_acciones[2].button("Eliminar", type="primary", key=f"del_{cap['id']}"):
                                conn.execute("DELETE FROM capacitaciones WHERE id = ?", (cap['id'],)); conn.commit(); st.success(f"Capacitación '{cap['titulo']}' eliminada."); st.rerun()
            conn.close()

    elif opcion_menu == "ALUMNOS":
        st.header("Gestión del Padrón de Alumnos")
        if st.session_state.role == 'admin':
            tab_ver, tab_agregar, tab_modificar = st.tabs(["Listado Completo", "Agregar Nuevo Alumno", "Modificar Alumno Existente"])
        else:
            tab_ver = st.tabs(["Listado Completo"])[0]

        with tab_ver:
            if st.session_state.role == 'admin':
                st.subheader("Sincronización completa desde Excel")
                st.info("Utiliza este botón para cargar o actualizar la base de datos completa desde el archivo 'datos_mediacion.xlsx'.")
                if excel_data is None: st.error("No se pudo cargar el archivo Excel.")
                elif st.button("Sincronizar Base de Datos con Excel"):
                    with st.spinner("Realizando sincronización completa..."):
                        conn = get_db_connection()
                        df_personal = excel_data.get('Personal')
                        df_inscripciones = excel_data.get('Inscripciones')
                        if df_personal is not None:
                            for _, row in df_personal.iterrows():
                                conn.execute('''INSERT INTO alumnos (dni, legajo, nombre, apellido, email, email_alternativo, tipo, celular, lugar_de_trabajo, profesion)
                                                VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(dni) DO UPDATE SET
                                                legajo=excluded.legajo, nombre=excluded.nombre, apellido=excluded.apellido, email=excluded.email,
                                                email_alternativo=excluded.email_alternativo, tipo=excluded.tipo, celular=excluded.celular,
                                                lugar_de_trabajo=excluded.lugar_de_trabajo, profesion=excluded.profesion''',
                                             (row.get('DNI'), row.get('Legajo'), row.get('Nombre'), row.get('Apellido'), row.get('Email'), row.get('Email Alternativo'), row.get('Tipo'), row.get('Celular'), row.get('Lugar de Trabajo'), row.get('Profesion')))
                            st.success("Paso 1: Alumnos de 'Personal' sincronizados.")
                        if df_inscripciones is not None:
                            df_inscripciones.dropna(subset=['DNI', 'Apellido', 'Nombre'], inplace=True)
                            for _, row in df_inscripciones.iterrows():
                                conn.execute('''INSERT INTO alumnos (dni, nombre, apellido, profesion, email, celular, lugar_de_trabajo)
                                                VALUES (?,?,?,?,?,?,?) ON CONFLICT(dni) DO NOTHING''',
                                             (row.get('DNI'), row.get('Nombre'), row.get('Apellido'), row.get('Profesion'), row.get('Email'), row.get('Celular'), row.get('Lugar de Trabajo')))
                            st.success("Paso 2: Alumnos de 'Inscripciones' verificados.")
                            capacitaciones_excel = df_inscripciones[['Titulo_Capacitacion', 'Año_Capacitacion', 'Ciudad']].drop_duplicates()
                            for _, row in capacitaciones_excel.iterrows():
                                ciudad = str(row.get('Ciudad', '')).lower()
                                ush = 'ushuaia' in ciudad; rg = 'grande' in ciudad; tol = 'tolhuin' in ciudad
                                conn.execute('''INSERT INTO capacitaciones (titulo, año, modalidad, realizado_ushuaia, realizado_rio_grande, realizado_tolhuin)
                                                VALUES (?, ?, 'A determinar', ?, ?, ?) ON CONFLICT(titulo, año) DO NOTHING''',
                                             (row['Titulo_Capacitacion'], row['Año_Capacitacion'], ush, rg, tol))
                            st.success("Paso 3: Capacitaciones sincronizadas.")
                            for index, row in df_inscripciones.iterrows():
                                try:
                                    alumno_id_result = conn.execute("SELECT id FROM alumnos WHERE dni = ?", (row['DNI'],)).fetchone()
                                    capacitacion_id_result = conn.execute("SELECT id FROM capacitaciones WHERE titulo = ? AND año = ?", (row['Titulo_Capacitacion'], row['Año_Capacitacion'])).fetchone()
                                    if alumno_id_result and capacitacion_id_result:
                                        conn.execute("INSERT INTO inscripciones (alumno_id, capacitacion_id, status) VALUES (?, ?, ?) ON CONFLICT(alumno_id, capacitacion_id) DO NOTHING",
                                                     (alumno_id_result['id'], capacitacion_id_result['id'], row.get('Status', 'Incompleto')))
                                except Exception as e:
                                    st.warning(f"No se pudo procesar la inscripción en la fila {index+2} del Excel: {e}")
                            st.success("Paso 4: Inscripciones sincronizadas.")
                        conn.commit()
                        conn.close()
                        st.balloons()
                        st.success("¡Sincronización completa finalizada!")
                        st.rerun()
            
            st.divider()
            st.subheader("Padrón de Alumnos en el Sistema")
            conn = get_db_connection()
            df_alumnos = pd.DataFrame(conn.execute("SELECT legajo, apellido, nombre, dni, celular, tipo, lugar_de_trabajo, profesion, email, email_alternativo FROM alumnos ORDER BY apellido, nombre").fetchall())
            if not df_alumnos.empty:
                df_alumnos.columns = ["Legajo", "Apellido", "Nombre", "DNI", "Celular", "Tipo", "Lugar de Trabajo", "Profesión", "Email", "Email Alternativo"]
            st.dataframe(df_alumnos, use_container_width=True)
            conn.close()

        if st.session_state.role == 'admin':
            with tab_agregar:
                st.subheader("Formulario de Carga de Nuevo Alumno")
                with st.form("form_nuevo_alumno", clear_on_submit=True):
                    apellido = st.text_input("Apellido*"); nombre = st.text_input("Nombre*"); dni = st.text_input("DNI* (sin puntos)"); legajo = st.text_input("Legajo")
                    email = st.text_input("Email"); email_alt = st.text_input("Email Alternativo"); tipo = st.text_input("Tipo (Ej: E, F)"); celular = st.text_input("Celular")
                    profesion = st.text_input("Profesión"); lugar_trabajo = st.text_input("Lugar de Trabajo")
                    if st.form_submit_button("Guardar Alumno"):
                        if not all([apellido, nombre, dni]): st.warning("Apellido, Nombre y DNI son campos obligatorios.")
                        else:
                            try:
                                conn = get_db_connection()
                                conn.execute("INSERT INTO alumnos (dni, legajo, nombre, apellido, email, email_alternativo, tipo, celular, lugar_de_trabajo, profesion) VALUES (?,?,?,?,?,?,?,?,?,?)",
                                             (dni, legajo, nombre, apellido, email, email_alt, tipo, celular, lugar_trabajo, profesion))
                                conn.commit(); conn.close(); st.success(f"Alumno '{apellido}, {nombre}' agregado."); st.rerun()
                            except sqlite3.IntegrityError: st.error(f"Error: Ya existe un alumno con el DNI {dni}.")
            with tab_modificar:
                st.subheader("Formulario de Modificación de Alumno")
                conn = get_db_connection()
                alumnos_db = conn.execute("SELECT id, dni, apellido, nombre FROM alumnos ORDER BY apellido").fetchall()
                mapa_alumnos_mod = {f"{a['apellido']}, {a['nombre']} (DNI: {a['dni']})": a['id'] for a in alumnos_db}
                alumno_a_modificar_str = st.selectbox("Seleccione un alumno para editar:", options=mapa_alumnos_mod.keys(), index=None, placeholder="Escriba para buscar...")
                if alumno_a_modificar_str:
                    alumno_id = mapa_alumnos_mod[alumno_a_modificar_str]
                    alumno_actual = conn.execute("SELECT * FROM alumnos WHERE id = ?", (alumno_id,)).fetchone()
                    with st.form("form_modificar_alumno"):
                        st.write(f"**Editando:** {alumno_actual['apellido']}, {alumno_actual['nombre']}")
                        legajo = st.text_input("Legajo", value=alumno_actual['legajo'] or ""); apellido = st.text_input("Apellido*", value=alumno_actual['apellido'] or "")
                        nombre = st.text_input("Nombre*", value=alumno_actual['nombre'] or ""); dni = st.text_input("DNI*", value=alumno_actual['dni'] or "")
                        email = st.text_input("Email", value=alumno_actual['email'] or ""); email_alt = st.text_input("Email Alternativo", value=alumno_actual['email_alternativo'] or "")
                        tipo = st.text_input("Tipo", value=alumno_actual['tipo'] or ""); celular = st.text_input("Celular", value=alumno_actual['celular'] or "")
                        profesion = st.text_input("Profesión", value=alumno_actual['profesion'] or ""); lugar_trabajo = st.text_input("Lugar de Trabajo", value=alumno_actual['lugar_de_trabajo'] or "")
                        if st.form_submit_button("Actualizar Datos"):
                            if not all([apellido, nombre, dni]): st.warning("Apellido, Nombre y DNI son obligatorios.")
                            else:
                                try:
                                    conn.execute('''UPDATE alumnos SET dni=?, legajo=?, nombre=?, apellido=?, email=?, email_alternativo=?, tipo=?, celular=?, lugar_de_trabajo=?, profesion=? WHERE id=?''',
                                                 (dni, legajo, nombre, apellido, email, email_alt, tipo, celular, lugar_trabajo, profesion, alumno_id))
                                    conn.commit(); st.success(f"Datos de '{apellido}, {nombre}' actualizados."); st.rerun()
                                except sqlite3.IntegrityError: st.error(f"Error: El DNI {dni} ya pertenece a otro alumno.")
                conn.close()

    elif opcion_menu == "CAPACITACION" and st.session_state.role == 'admin':
        st.header("Gestión de Capacitaciones")
        conn = get_db_connection()
        alumnos_db = conn.execute("SELECT id, dni, apellido, nombre FROM alumnos ORDER BY apellido").fetchall()
        mapa_alumnos = {f"{a['apellido']}, {a['nombre']} (DNI: {a['dni']})": a['id'] for a in alumnos_db}
        conn.close()
        if not mapa_alumnos: st.warning("No hay alumnos en la base de datos.")
        else:
            with st.form("form_nueva_capacitacion"):
                titulo = st.text_input("Título de la capacitación"); año = st.number_input("Año", min_value=2005, max_value=date.today().year + 5, value=date.today().year)
                col_f1, col_f2 = st.columns(2); fecha_inicio = col_f1.date_input("Fecha de inicio", value=None); fecha_fin = col_f2.date_input("Fecha de finalización", value=None)
                modalidad = st.selectbox("Modalidad", ["Presencial", "Virtual", "Mixta"]); docentes = st.text_input("Docentes (separados por coma)")
                aclaracion = st.text_area("Aclaración"); st.write("Ciudad(es) donde se realiza:")
                c1, c2, c3 = st.columns(3); ushuaia = c1.checkbox("Ushuaia"); tolhuin = c2.checkbox("Tolhuin"); rio_grande = c3.checkbox("Río Grande")
                st.divider(); st.subheader("Inscribir Alumnos")
                alumnos_a_inscribir = st.multiselect("Seleccione los alumnos a inscribir:", options=mapa_alumnos.keys())
                if st.form_submit_button("Guardar Capacitación"):
                    if titulo:
                        conn = get_db_connection()
                        conn.execute('INSERT INTO capacitaciones (titulo, año, docentes, aclaracion, modalidad, fecha_inicio, fecha_fin, realizado_ushuaia, realizado_tolhuin, realizado_rio_grande) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(titulo, año) DO UPDATE SET docentes=excluded.docentes, aclaracion=excluded.aclaracion, modalidad=excluded.modalidad, fecha_inicio=excluded.fecha_inicio, fecha_fin=excluded.fecha_fin, realizado_ushuaia=excluded.realizado_ushuaia, realizado_tolhuin=excluded.realizado_tolhuin, realizado_rio_grande=excluded.realizado_rio_grande',
                                       (titulo, año, docentes, aclaracion, modalidad, fecha_inicio.strftime("%Y-%m-%d") if fecha_inicio else None, fecha_fin.strftime("%Y-%m-%d") if fecha_fin else None, ushuaia, tolhuin, rio_grande))
                        capacitacion_id = conn.execute("SELECT id FROM capacitaciones WHERE titulo = ? AND año = ?", (titulo, año)).fetchone()['id']
                        for persona_str in alumnos_a_inscribir:
                            conn.execute("INSERT INTO inscripciones (alumno_id, capacitacion_id, status) VALUES (?,?,?) ON CONFLICT(alumno_id, capacitacion_id) DO NOTHING", (mapa_alumnos[persona_str], capacitacion_id, "Incompleto"))
                        conn.commit(); conn.close(); st.success(f"Capacitación '{titulo}' guardada."); st.rerun()
                    else: st.warning("El título es obligatorio.")

    elif opcion_menu == "BUSCADOR":
        st.header("Buscador Avanzado")
        tab_cap, tab_alu = st.tabs(["Buscar por Capacitación", "Buscar por Alumno"])
        with tab_cap:
            conn = get_db_connection()
            nombres_caps = [c['titulo'] for c in conn.execute("SELECT DISTINCT titulo FROM capacitaciones ORDER BY titulo").fetchall()]
            with st.form("form_buscar_cap"):
                col1, col2 = st.columns(2)
                filtro_nombre = col1.selectbox("Nombre de Capacitación:", ["Todas"] + nombres_caps)
                filtro_año_inicio = col2.number_input("Desde el año:", 2005, date.today().year + 5, 2023)
                filtro_año_fin = col2.number_input("Hasta el año:", 2005, date.today().year + 5, date.today().year)
                filtro_docente = st.text_input("Docente (contiene):")
                filtro_ciudad = st.selectbox("Ciudad:", ["Todas", "Ushuaia", "Tolhuin", "Río Grande"])
                if st.form_submit_button("Buscar Capacitaciones"):
                    base_query = 'SELECT a.apellido, a.nombre, a.celular, a.email, a.profesion, c.titulo as capacitacion, c.año FROM alumnos a JOIN inscripciones i ON a.id = i.alumno_id JOIN capacitaciones c ON i.capacitacion_id = c.id'
                    conditions, params = ["c.año BETWEEN ? AND ?"], [filtro_año_inicio, filtro_año_fin]
                    if filtro_nombre != "Todas": conditions.append("c.titulo = ?"); params.append(filtro_nombre)
                    if filtro_docente: conditions.append("c.docentes LIKE ?"); params.append(f"%{filtro_docente}%")
                    if filtro_ciudad != "Todas": conditions.append(f"c.realizado_{filtro_ciudad.lower().replace('í', 'i')} = ?"); params.append(True)
                    base_query += " WHERE " + " AND ".join(conditions) + " ORDER BY c.año DESC, a.apellido"
                    resultados = pd.DataFrame(conn.execute(base_query, params).fetchall())
                    if not resultados.empty:
                        resultados.columns = ["Apellido", "Nombre", "Celular", "Email", "Profesión", "Capacitación", "Año"]
                        st.dataframe(resultados, use_container_width=True)
                        csv = resultados.to_csv(index=False).encode('utf-8')
                        st.download_button("Descargar Resultados (CSV)", csv, "reporte_capacitaciones.csv", 'text/csv')
                    else: st.warning("No se encontraron resultados.")
            conn.close()
        with tab_alu:
            conn = get_db_connection()
            with st.form("form_buscar_alu"):
                filtro_texto_alumno = st.text_input("Buscar por Apellido o Nombre (contiene):")
                filtro_profesion_alu = st.text_input("Profesión (contiene):")
                if st.form_submit_button("Buscar Alumnos"):
                    base_query = "SELECT * FROM alumnos"; conditions, params = [], []
                    if filtro_texto_alumno: conditions.append("(apellido LIKE ? OR nombre LIKE ?)"); params.extend([f"%{filtro_texto_alumno}%"]*2)
                    if filtro_profesion_alu: conditions.append("profesion LIKE ?"); params.append(f"%{filtro_profesion_alu}%")
                    if conditions: base_query += " WHERE " + " AND ".join(conditions)
                    base_query += " ORDER BY apellido, nombre"
                    resultados_alumnos = conn.execute(base_query, params).fetchall()
                    if resultados_alumnos:
                        st.write(f"Se encontraron {len(resultados_alumnos)} alumno(s).")
                        for alumno in resultados_alumnos:
                            with st.expander(f"**{alumno['apellido']}, {alumno['nombre']}** (DNI: {alumno['dni']})"):
                                st.write(f"**Profesión:** {alumno['profesion'] or 'N/A'}")
                                st.write(f"**Email:** {alumno['email']} | **Alternativo:** {alumno['email_alternativo']}")
                                st.write(f"**Celular:** {alumno['celular']} | **Tipo:** {alumno['tipo']}")
                                st.divider(); st.write("**Historial de Capacitaciones:**")
                                historial = conn.execute('SELECT c.titulo, c.año, i.status FROM capacitaciones c JOIN inscripciones i ON c.id = i.capacitacion_id WHERE i.alumno_id = ? ORDER BY c.año DESC', (alumno['id'],)).fetchall()
                                if historial:
                                    for curso in historial: st.write(f"- {curso['titulo']} ({curso['año']}) - **Estado:** {curso['status']}")
                                else: st.write("Sin capacitaciones registradas.")
                    else: st.warning("No se encontraron alumnos para esta búsqueda.")
            conn.close()

    elif opcion_menu == "NORMATIVA":
        st.header("Normativa y Documentación")
        ruta_base = "normativa"
        if st.session_state.role == 'admin':
            with st.expander("⬆️ Subir Nuevo Documento"):
                uploaded_files = st.file_uploader("Selecciona documentos", accept_multiple_files=True)
                if st.button("Guardar Archivos Subidos"):
                    if uploaded_files:
                        os.makedirs(ruta_base, exist_ok=True)
                        for uploaded_file in uploaded_files:
                            save_path = os.path.join(ruta_base, uploaded_file.name)
                            if os.path.exists(save_path): st.warning(f"El archivo '{uploaded_file.name}' ya existe.")
                            else:
                                with open(save_path, "wb") as f: f.write(uploaded_file.getvalue())
                                st.success(f"Archivo '{uploaded_file.name}' subido.")
                        st.rerun()
                    else: st.info("Por favor, selecciona al menos un archivo para subir.")
        st.divider()
        st.subheader("Documentos Disponibles")
        if 'file_to_view' not in st.session_state: st.session_state.file_to_view = None
        if not os.path.exists(ruta_base): st.warning(f"No se encontró la carpeta '{ruta_base}'.")
        else:
            try:
                archivos = [f for f in os.listdir(ruta_base) if os.path.isfile(os.path.join(ruta_base, f))]
                if not archivos: st.info("La carpeta 'normativa' no contiene archivos.")
                else:
                    for archivo in sorted(archivos):
                        ruta_archivo = os.path.join(ruta_base, archivo)
                        col_name, col_view, col_dl = st.columns([8, 1, 1])
                        col_name.write(archivo)
                        if col_view.button("👁️", key=f"view_{archivo}", help="Visualizar archivo"): st.session_state.file_to_view = ruta_archivo; st.rerun()
                        with open(ruta_archivo, "rb") as f:
                            col_dl.download_button(label="📥", data=f.read(), file_name=archivo, mime="application/octet-stream", key=f"dl_{archivo}", help="Descargar archivo")
                    st.divider()
            except Exception as e: st.error(f"Ocurrió un error: {e}")
        if st.session_state.file_to_view:
            st.subheader(f"Visualizando: {os.path.basename(st.session_state.file_to_view)}")
            if st.button("❌ Cerrar Visualizador"): st.session_state.file_to_view = None; st.rerun()
            try:
                with open(st.session_state.file_to_view, "rb") as f:
                    base64_pdf = base64.b64encode(f.read()).decode('utf-8')
                pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="800" type="application/pdf"></iframe>'
                st.markdown(pdf_display, unsafe_allow_html=True)
            except Exception as e: st.error(f"No se pudo cargar el archivo: {e}"); st.session_state.file_to_view = None