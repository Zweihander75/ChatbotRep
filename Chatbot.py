import streamlit as st
import sqlite3
from sqlite3 import Error
import google.generativeai as genai
from langchain.sql_database import SQLDatabase
import pandas as pd
import os

# Excel a SQLite
def excel_to_sqlite(excel_file, output_dir=os.path.abspath(__file__)):
    try:

        # Crear el directorio para guardar las bases de datos si no existe
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # Generar el nombre del archivo SQLite
        excel_filename = os.path.splitext(excel_file.name)[0]  # Obtener el nombre sin extensión
        db_file = os.path.join(output_dir, f"{excel_filename}.sqlite")

        # Leer el archivo Excel
        df = pd.read_excel(excel_file)
        
        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(db_file)
        
        # Guardar los datos
        df.to_sql("imported_data", conn, if_exists="replace", index=False)
        
        conn.close()
        return True, "Archivo Excel convertido y guardado en la base de datos SQLite exitosamente.", db_file
    except Exception as e:
        return False, f"Error al convertir el archivo Excel: {e}", None


st.set_page_config(page_title="Chatbot SQLite con Gemini", page_icon="🤖")


GEMINI_API_KEY = "AIzaSyBV4RlXzi2iRzi-_syqxH8HBfDY2aGgx3E"  

# Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# Conexión con LangChain
try:
    db = SQLDatabase.from_uri("sqlite:///lista de precios jd.sqlite")
except Exception as e:
    st.error(f"Error al conectar con la base de datos: {e}")

# Conectarse a la base de datos SQLite
def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
    except Error as e:
        st.error(f"Error al conectar con la base de datos: {e}")
    return conn

# Ejecutar consultas
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


def ask_gemini(prompt):
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        st.error(f"Error al interactuar con Gemini AI: {e}")
        return "Lo siento, no puedo responder en este momento."

# Obtener el esquema de la base de datos
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

# Interfaz
def main():
    st.title("🤖 Chatbot con Base de Datos SQLite")
    st.write("Este chatbot responde preguntas sobre la base de datos en lenguaje natural.")

    # Directorio de bases de datos
    db_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.exists(db_dir):
        os.makedirs(db_dir)

    # Excel a SQLite
    st.subheader("📂 Convertir archivo Excel a SQLite")
    uploaded_file = st.file_uploader("Sube un archivo Excel para convertirlo a SQLite", type=["xlsx"])
    
    if uploaded_file:
        success, message, db_file = excel_to_sqlite(uploaded_file, db_dir)
        if success:
            st.success(message)
        else:
            st.error(message)        

    # Bases de datos disponibles
    db_files = [f for f in os.listdir(db_dir) if f.endswith((".sqlite", ".db"))]

    if not db_files:
        st.warning("No se encontraron bases de datos en la carpeta. Por favor, sube un archivo Excel para crear una.")
        uploaded_file = st.file_uploader("Sube un archivo Excel para convertirlo a SQLite", type=["xlsx"])
        if uploaded_file:
            success, message, db_file = excel_to_sqlite(uploaded_file, db_dir)
            if success:
                st.success(message)
                db_files = [os.path.basename(db_file)]  
            else:
                st.error(message)
    else:
        # Menú desplegable
        selected_db = st.selectbox("Selecciona una base de datos:", db_files)
        db_file = os.path.join(db_dir, selected_db)

        
        conn = create_connection(db_file)
    if conn:
        st.success("✅ Conexión exitosa a la base de datos.")
        
        results = None
    
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
                3. Asegúrate de incluir el nombre del producto y su precio en el resultado
                4. Usa funciones compatibles con SQLite
                5. Si la pregunta es sobre el producto más caro o mas barato, devuelve solo el producto que tiene ese precio, junto con sus detalles.
                6. Si la pregunta no puede responderse con los datos, devuelve 'No se puede responder'
                7. Si la pregunta contiene lo que al principo parecería una palabra aleatoria (ejemplo: bujia) utiliza esa palabra como un filtro para la consulta SQL
                8. si la pregunta contiene la siguiente estructura o semejante ("X de Y") la consulta debe buscar registros que contengan "X" y "Y" en sus columnas correspondientes.
                9. Si la pregunta no es lo suficientemente específica, devuelve preguntas que el usuario podría hacer para obtener información útil.
                10. Si la pregunta no puede responderse con los datos, devuelve 'No se puede responder'.
                11. si la pregunta tiene palabras en pluraL, asegurate de buscar tanto la palabra en plural como en singular.
                12. A menos que se especifique lo contrario, muestra toda la fila del producto.
                """
                
                sql_query = ask_gemini(sql_prompt).strip().replace("```sql", "").replace("```", "")
                
            if "no se puede responder" in sql_query.lower():
                # Generar sugerencias
                suggestion_prompt = f"""
                Basado en el siguiente esquema de base de datos y la pregunta del usuario:
                {schema}
                {user_question}
                
                Sugiere 3 preguntas relevantes que un usuario podría hacer para conseguir lo que quería en su pregunta original (Solo las preguntas sin explicación).
                """
                suggestions = ask_gemini(suggestion_prompt).strip()
                st.warning("La pregunta no es lo suficientemente específica o no está relacionada con la base de datos.")
                st.write("💡 Sugerencias de preguntas:")
                st.write(suggestions)
            else:
                print()                
                    
                # Ejecutar la consulta
                columns, results = execute_query(conn, sql_query)
                
                if results:
                    if columns:
                        df = pd.DataFrame(results, columns=columns)
                    else:
                        df = pd.DataFrame(results)

                    # Mostrar la consulta generada
                    with st.expander("📝 Consulta generada (SQL)"):
                        st.code(sql_query, language="sql")

                    # Mostrar resultados generados
                    with st.expander("📋 Ver resultados de la consulta"):
                        st.markdown(
                            """
                            <style>
                            .stTable {
                                max-width: 90%; /* Ajusta el ancho máximo de la tabla */
                                margin: 0 auto; /* Centra la tabla */
                            }
                            </style>
                            """,
                            unsafe_allow_html=True
                        )
                        st.dataframe(df, use_container_width=True)

                    # Explicación en lenguaje natural
                    explanation_prompt = f"""
                    Explica estos resultados de base de datos en lenguaje natural:
                    Pregunta: {user_question}
                    Resultados: {results}
                    
                    La explicación debe ser clara y responder a la pregunta.
                    """
                    explanation = ask_gemini(explanation_prompt)
                    st.write("💡 Explicación:", explanation)
                else:
                    with st.expander("📝 Consulta generada (SQL)"):
                        st.code(sql_query, language="sql")

                    explanation_prompt = f"""
                    No se encontraron resultados para la consulta SQL generada:
                    Pregunta: {user_question}
                    Base de datos: {schema}
                    Consulta: {sql_query}
                    
                    Utiliza la pregunta, la base de datos y la consulta para generar un mensaje corto explicando la situación
                    (que no contenga la consulta ni la base de datos) y si es posible una recomendación posterior.
                    """ 

                    explanation = ask_gemini(explanation_prompt)
                    st.write("💡 Explicación:", explanation)
                    
        conn.close()

if __name__ == "__main__":
    main()
