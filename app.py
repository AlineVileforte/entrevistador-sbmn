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

# Prompt do sistema condensado
SYSTEM_PROMPT = """Você é um Entrevistador SBMN. Siga EXATAMENTE este protocolo:

FASE 1 (3 perguntas obrigatórias):
1. "Qual é o nome do processo que vamos modelar?"
2. "Qual é o setor ou área de aplicação deste processo?"
3. "Liste as principais atividades que compõem este processo, do início ao fim. Separe por vírgulas."

FASE 2 (perguntas sobre relações):
Para cada par de atividades [A] e [B], pergunte:

"A atividade '[B]' precisa esperar '[A]' terminar para começar? Responda: SIM ou NÃO"

Se SIM: "A atividade '[A]' SEMPRE acontece ou é OPCIONAL? Responda: SEMPRE ou OPCIONAL"
- SEMPRE = B DEP A
- OPCIONAL = B DEPC A

Se NÃO: "As atividades '[A]' e '[B]' podem acontecer JUNTAS? Responda: SIM ou NÃO"
- NÃO = A XOR B
- SIM: "É OBRIGATÓRIO que pelo menos uma aconteça? Responda: APENAS A | APENAS B | AMBAS | NENHUMA"

FASE 3 (apresentação):
Apresente o modelo no formato:
═══════════════════════════════════════════════════
MODELO SBMN: [nome]
Setor: [setor]
═══════════════════════════════════════════════════

📋 DOMÍNIO (AFOs):
A = [atividade]
B = [atividade]

🔗 SITUAÇÕES IDENTIFICADAS:
DEP: [lista]
DEPC: [lista]
XOR: [lista]
UNI: [lista]
═══════════════════════════════════════════════════

REGRAS:
- Faça UMA pergunta por vez
- Perguntas CURTAS e OBJETIVAS
- Use SIM/NÃO sempre que possível
- NÃO peça esclarecimentos desnecessários"""

# Configurar API
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"⚠️ Erro ao configurar a API: {str(e)}")
    st.stop()

# Inicializar modelo
@st.cache_resource
def get_model():
    try:
        generation_config = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            generation_config=generation_config
        )
        return model
    except Exception as e:
        st.error(f"Erro ao criar modelo: {str(e)}")
        return None

model = get_model()

if model is None:
    st.stop()

# Inicializar sessão
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.chat = None
    # Primeira mensagem com instruções do sistema
    st.session_state.messages.append({
        "role": "user", 
        "content": SYSTEM_PROMPT + "\n\nConfirme que entendeu respondendo: 'Olá! Sou o Entrevistador SBMN v6. Vamos começar?'"
    })
    # Iniciar chat e obter primeira resposta
    st.session_state.chat = model.start_chat()
    response = st.session_state.chat.send_message(st.session_state.messages[0]["content"])
    st.session_state.messages.append({
        "role": "assistant",
        "content": response.text
    })

# Função para salvar no Google Sheets
def save_to_sheets(conversation_data):
    try:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]

        creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)

        sheet = client.open_by_key(st.secrets["SHEET_ID"]).sheet1

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Filtrar mensagens do usuário (excluindo a primeira com o SYSTEM_PROMPT)
        filtered_msgs = [msg for i, msg in enumerate(conversation_data) if i > 0]

        full_conversation = "\n\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in filtered_msgs
        ])

        sbmn_model = ""
        for msg in reversed(filtered_msgs):
            if "MODELO SBMN" in msg['content']:
                sbmn_model = msg['content']
                break

        row = [timestamp, full_conversation, sbmn_model]
        sheet.append_row(row)

        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {str(e)}")
        return False

# Exibir histórico (exceto primeira mensagem com SYSTEM_PROMPT)
for i, message in enumerate(st.session_state.messages):
    if i > 0:  # Pular a primeira mensagem (SYSTEM_PROMPT)
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Input do usuário
if prompt := st.chat_input("Digite sua resposta aqui..."):
    # Adicionar mensagem do usuário
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Obter resposta
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
            except Exception as e:
                response_text = f"Erro: {str(e)}"
                st.error(response_text)

    # Adicionar resposta ao histórico
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # Verificar se concluiu
    if "MODELO SBMN" in response_text and "═══════════" in response_text:
        with st.spinner("Salvando entrevista..."):
            if save_to_sheets(st.session_state.messages):
                st.success("✅ Entrevista salva com sucesso!")
                st.balloons()

# Botão reiniciar
if st.button("🔄 Reiniciar Entrevista"):
    st.session_state.messages = []
    st.session_state.chat = None
    st.rerun()

# Sidebar
with st.sidebar:
    st.markdown("### 📋 Sobre")
    st.markdown("Entrevistador para modelagem SBMN de processos.")
    st.markdown("### 📊 Status")
    # Subtrair 1 da contagem (não contar SYSTEM_PROMPT)
    msg_count = max(0, len(st.session_state.messages) - 1)
    st.metric("Mensagens", msg_count)

    st.markdown("---")
    if st.button("Limpar Histórico"):
        st.session_state.messages = []
        st.session_state.chat = None
        st.rerun()
