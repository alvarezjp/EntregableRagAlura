import os
import streamlit as st
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

# --- Configuración inicial ---
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

RUTA_DOCUMENTO = "Documentos/guiaTiempoYCostoEnvio.pdf"


# --- Construcción del RAG (cacheado para no reprocesar en cada interacción) ---
@st.cache_resource(show_spinner="Preparando el agente, un momento...")
def construir_agente():
    # Fase 1: cargar y trocear el documento
    loader = PyPDFLoader(RUTA_DOCUMENTO)
    paginas = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = splitter.split_documents(paginas)

    # Fase 2: embeddings + vector store
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embeddings)
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 3})

    # LLM de Groq
    llm = ChatGroq(
        groq_api_key=GROQ_API_KEY,
        model_name="llama-3.3-70b-versatile",
        temperature=0
    )

    # Cadena de recuperación
    system_prompt = (
        "Usa el siguiente contexto para responder la pregunta del usuario. "
        "Si no sabes la respuesta, di que no la sabes. "
        "Responde de forma clara y concisa.\n\n"
        "Contexto:\n{context}"
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    qa_chain = create_retrieval_chain(retriever, question_answer_chain)

    return qa_chain


# --- Interfaz de Streamlit ---
st.set_page_config(page_title="Alura Agente", page_icon="🤖")
st.title("🤖 Alura Agente")
st.write("Hazme una pregunta sobre el documento (Guia de tiempo y costo de envio) y te responderé según su contenido.")

# Validación de la API key
if not GROQ_API_KEY:
    st.error("No se encontró la variable GROQ_API_KEY. Verifica tu archivo .env o los secrets de la app.")
    st.stop()

qa_chain = construir_agente()

pregunta = st.text_input("Escribe tu pregunta:")

if pregunta:
    with st.spinner("Buscando la respuesta..."):
        respuesta = qa_chain.invoke({"input": pregunta})

    st.subheader("Respuesta")
    st.write(respuesta["answer"])
