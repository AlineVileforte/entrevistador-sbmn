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

# Prompt do sistema (seu prompt SBMN v6)
SYSTEM_PROMPT = """Você é um Analista de Processos de Negócio especializado em SBMN. 

IMPORTANTE: Siga RIGOROSAMENTE este protocolo:

FASE 1 - COLETA INICIAL (3 perguntas sequenciais):
1. Pergunte: "Qual é o nome do processo que vamos modelar?"
2. Depois, pergunte: "Qual é o setor ou área de aplicação deste processo?"
3. Por último, pergunte: "Liste as principais atividades e eventos que compõem este processo, do início ao fim. Separe por vírgulas."

FASE 2 - PERGUNTAS SOBRE DEPENDÊNCIAS:
Após receber a lista de atividades, faça perguntas OBJETIVAS SIM/NÃO sobre as relações entre pares de atividades.

Para cada par de atividades [A] e [B], pergunte:

PERGUNTA TIPO 1 (Dependência):
"A atividade '[B]' precisa esperar '[A]' terminar para poder começar? Responda: SIM ou NÃO"

Se SIM, pergunte:
"A atividade '[A]' SEMPRE acontece neste processo, ou ela é OPCIONAL? Responda: SEMPRE ou OPCIONAL"
- SEMPRE = B DEP A (Dependência Estrita)
- OPCIONAL = B DEPC A (Dependência Circunstancial)

Se NÃO na pergunta de dependência, pergunte:

PERGUNTA TIPO 2 (Exclusividade):
"As atividades '[A]' e '[B]' podem acontecer JUNTAS na mesma execução do processo? Responda: SIM ou NÃO"
- NÃO = A XOR B (são mutuamente exclusivas)
- SIM = continue para próxima pergunta

PERGUNTA TIPO 3 (União):
"No processo, é OBRIGATÓRIO que pelo menos UMA das atividades ('[A]' OU '[B]') aconteça? Responda: APENAS A | APENAS B | AMBAS | NENHUMA"
- APENAS A = A UNI B (A é obrigatória)
- APENAS B = B UNI A (B é obrigatória)
- AMBAS = A UNI B (ambas obrigatórias)
- NENHUMA = sem relação especial

FASE 3 - APRESENTAÇÃO:
Após mapear todas as relações, apresente o MODELO SBMN no formato:

═══════════════════════════════════════════════════
MODELO SBMN: [Nome do Processo]
Setor: [Setor]
Data: [Data]
═══════════════════════════════════════════════════

📋 DOMÍNIO (AFOs):
A = [nome da atividade]
B = [nome da atividade]
...

🔗 SITUAÇÕES IDENTIFICADAS:

DEP (Dependências Estritas):
• [listar]

DEPC (Dependências Circunstanciais):
• [listar]

XOR (Não-Coexistências):
• [listar]

UNI (Uniões Inclusivas):
• [listar]

═══════════════════════════════════════════════════

REGRAS CRÍTICAS:
- Faça perguntas CURTAS e OBJETIVAS
- UMA pergunta por vez
- Aguarde resposta antes da próxima pergunta
- Use formato SIM/NÃO sempre que possível
- NÃO faça perguntas abertas ou explicativas
- NÃO peça esclarecimentos desnecessários
- FOQUE apenas nas 3 perguntas iniciais e depois nas perguntas de dependência"""

# Configurar a API do Gemini
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"⚠️ Erro ao configurar a API: {str(e)}")
    st.stop()

# Inicializar o modelo com system instruction
@st.cache_resource
def get_model():
    try:
        generation_config = {
            "temperature": 0.3,  # Reduzida para maior precisão
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,  # Reduzida para respostas mais diretas
        }

        model = genai.GenerativeModel(
            model_name='gemini-2.5-flash',
            generation_config=generation_config,
            system_instruction=SYSTEM_PROMPT
        )
        return model
    except Exception as e:
        st.error(f"Erro ao criar modelo: {str(e)}")
        return None

model = get_model()

if model is None:
    st.error("Não foi possível inicializar o modelo. Verifique as configurações.")
    st.stop()

# Inicializar histórico de conversa
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.chat = model.start_chat(history=[])
    # Mensagem inicial
    initial_message = "Olá! Sou o Entrevistador SBMN v6. Vou conduzi-lo através de uma entrevista estruturada para modelar seu processo de negócio. Vamos começar?"
    st.session_state.messages.append({
        "role": "assistant", 
        "content": initial_message
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

        full_conversation = "\n\n".join([
            f"{msg['role'].upper()}: {msg['content']}" 
            for msg in conversation_data
        ])

        sbmn_model = ""
        for msg in reversed(conversation_data):
            if "MODELO SBMN" in msg['content']:
                sbmn_model = msg['content']
                break

        row = [timestamp, full_conversation, sbmn_model]
        sheet.append_row(row)

        return True
    except Exception as e:
        st.error(f"Erro ao salvar: {str(e)}")
        return False

# Exibir histórico
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
            try:
                response = st.session_state.chat.send_message(prompt)
                response_text = response.text
                st.markdown(response_text)
            except Exception as e:
                response_text = f"Erro ao obter resposta: {str(e)}"
                st.error(response_text)

    # Adicionar resposta ao histórico
    st.session_state.messages.append({"role": "assistant", "content": response_text})

    # Verificar se a entrevista foi concluída
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

# Sidebar
with st.sidebar:
    st.markdown("### 📋 Sobre")
    st.markdown("Este entrevistador usa IA para modelar processos de negócio na notação SBMN.")
    st.markdown("### 📊 Status")
    st.metric("Mensagens trocadas", len(st.session_state.messages))

    st.markdown("---")
    st.markdown("### ⚙️ Configuração")
    if st.button("Limpar Histórico"):
        st.session_state.messages = []
        st.session_state.chat = model.start_chat(history=[])
        st.rerun()
