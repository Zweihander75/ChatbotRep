import streamlit as st
import sqlite3
from sqlite3 import Error
import google.generativeai as genai
import os
from langchain.sql_database import SQLDatabase

# Configuración inicial
st.set_page_config(page_title="Chatbot SQLite con Gemini", page_icon="🤖")

# Configura tu clave de API de Gemini AI correctamente
GEMINI_API_KEY = "AIzaSyBV4RlXzi2iRzi-_syqxH8HBfDY2aGgx3E" 

# Configura el modelo Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Entrada para cambiar la dirección de la base de datos
st.sidebar.header("Configuración de la Base de Datos")
db_file = st.sidebar.text_input("Ruta de la base de datos SQLite:", "lista de precios jd.sqlite")

# Función para conectarse directamente a la base de datos SQLite
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        st.error(f"Error al conectar con la base de datos: {e}")
    return conn

# Función para ejecutar consultas en la base de datos
def execute_query(conn, query):
    try:
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        columns = [desc[0] for desc in cur.description] if cur.description else []
        return columns, rows
    except Error as e:
        st.error(f"Error al ejecutar la consulta: {e}")
        return None, None

# Función mejorada para interactuar con Gemini AI
def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error al interactuar con Gemini AI: {e}")
        return "Lo siento, no puedo responder en este momento."

# Función para obtener el esquema de la base de datos
def get_schema(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    schema = []
    for table in tables:
        table_name = table[0]
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        schema.append({
            "table": table_name,
            "columns": [col[1] for col in columns]
        })
    return schema

# Interfaz de usuario con Streamlit
def main():
    st.title("🤖 Chatbot con Base de Datos SQLite")
    st.write("Este chatbot responde preguntas sobre la base de datos en lenguaje natural.")

    # Conexión a la base de datos
    if db_file:
        conn = create_connection(db_file)

        if conn:
            st.success(f"✅ Conexión exitosa a la base de datos: {db_file}")
            
            # Initialize results to avoid referencing before assignment
            results = None
            
            # Obtener esquema para el contexto
            schema = get_schema(conn)
            
            # Mostrar esquema
            with st.expander("📊 Ver estructura de la base de datos"):
                for table in schema:
                    st.write(f"**Tabla: {table['table']}**")
                    st.write(f"Columnas: {', '.join(table['columns'])}")
                    st.write("---")

            # Entrada del usuario
            user_question = st.text_input("Haz una pregunta sobre la base de datos (ej: ¿Cuál es el producto más caro?):")

            if st.button("Consultar") and user_question:
                with st.spinner("Procesando tu pregunta..."):
                    # Generar consulta SQL
                    sql_prompt = f"""
                    Eres un experto en SQLite. Basado en el siguiente esquema de base de datos:
                    {schema}
                    
                    Genera una consulta SQL para responder a: '{user_question}'
                    
                    Reglas:
                    1. Devuelve SOLO el código SQL, sin explicaciones
                    2. Usa comillas dobles para identificadores si es necesario
                    3. Usa funciones compatibles con SQLite (por ejemplo, usa MAX para obtener el valor máximo en una columna)
                    4. Si la pregunta no puede responderse con los datos, devuelve 'No se puede responder'
                    """
                    
                    sql_query = ask_gemini(sql_prompt).strip().replace("```sql", "").replace("```", "")
                    
                    if sql_query and "no se puede responder" not in sql_query.lower():
                        st.code(f"Consulta SQL generada:\n{sql_query}")
                        columns, results = execute_query(conn, sql_query)
                        
                        if results:
                            # Mostrar resultados en tabla
                            st.write("📋 Resultados:")
                            st.table(results)
                            
                            # Generar explicación en lenguaje natural
                            explanation_prompt = f"""
                            Explica estos resultados de base de datos en lenguaje natural:
                            Pregunta: {user_question}
                            Resultados: {results}
                            
                            La explicación debe ser clara, concisa (1-2 oraciones) y responder directamente a la pregunta.
                            """
                            explanation = ask_gemini(explanation_prompt)
                            st.write("💡 Explicación:", explanation)
                        else:
                            st.warning("No se encontraron resultados para esta consulta.")
                    else:
                        st.warning("No pude generar una consulta adecuada para esta pregunta.")

            # Cerrar conexión
            conn.close()
        else:
            st.error("No se pudo conectar a la base de datos. Verifica la ruta proporcionada.")
    else:
        st.warning("Por favor, ingresa la ruta de la base de datos en la barra lateral.")

if __name__ == "__main__":
    main()
