import streamlit as st
import google.generativeai as genai
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

# Configuração da página
st.set_page_config(
    page_title="Entrevistador SBMN v6",
    page_icon="💬",
    layout="wide"
)

# Título
st.title("🎯 Entrevistador SBMN v6")
st.markdown("*Assistente especializado em modelagem SBMN para processos de negócio*")
st.markdown("---")

# Configurar a API do Gemini
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except:
    st.error("⚠️ Erro ao configurar a API. Verifique as configurações.")
    st.stop()

# Prompt do sistema (seu prompt SBMN v6)
SYSTEM_PROMPT = """
[AQUI VAI SEU PROMPT COMPLETO - vou inserir depois]
"""

# Inicializar o modelo
@st.cache_resource
def get_model():
    return genai.GenerativeModel(
        model_name='gemini-1.5-pro',
        system_instruction=SYSTEM_PROMPT
    )

model = get_model()

# Inicializar histórico de conversa
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.chat = model.start_chat(history=[])
    # Mensagem inicial
    initial_message = "Olá! Sou o Entrevistador SBMN v6. Vou conduzi-lo através de uma entrevista estruturada para modelar seu processo de negócio. Vamos começar?"
    st.session_state.messages.append({"role": "assistant", "content": initial_message})

# Função para salvar no Google Sheets
def save_to_sheets(conversation_data):
    try:
        # Configurar credenciais do Google Sheets
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)

        # Abrir a planilha
        sheet = client.open_by_key(st.secrets["SHEET_ID"]).sheet1

        # Preparar dados
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Extrair informações
        full_conversation = "\n\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in conversation_data
        ])

        # Encontrar o modelo SBMN final (última mensagem que contém "MODELO SBMN")
        sbmn_model = ""
        for msg in reversed(conversation_data):
            if "MODELO SBMN" in msg['content']:
                sbmn_model = msg['content']
                break

        # Adicionar linha na planilha
        row = [timestamp, full_conversation, sbmn_model]
        sheet.append_row(row)

        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {str(e)}")
        return False

# Exibir histórico de mensagens
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Input do usuário
if prompt := st.chat_input("Digite sua resposta aqui..."):
    # Adicionar mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Obter resposta do modelo
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            response = st.session_state.chat.send_message(prompt)
            response_text = response.text
            st.markdown(response_text)

    # Adicionar resposta ao histórico
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # Verificar se a entrevista foi concluída (contém "MODELO SBMN")
    if "MODELO SBMN" in response_text and "═══════════" in response_text:
        with st.spinner("Salvando entrevista..."):
            if save_to_sheets(st.session_state.messages):
                st.success("✅ Entrevista salva com sucesso!")
                st.balloons()

# Botão para reiniciar
if st.button("🔄 Reiniciar Entrevista"):
    st.session_state.messages = []
    st.session_state.chat = model.start_chat(history=[])
    st.rerun()

# Informações no sidebar
with st.sidebar:
    st.markdown("### 📋 Sobre")
    st.markdown("Este entrevistador usa IA para modelar processos de negócio na notação SBMN.")
    st.markdown("### 📊 Status")
    st.metric("Mensagens trocadas", len(st.session_state.messages))
