import streamlit as st
import time
import json
import gspread
import uuid  # 👈 [추가] 고유 ID 생성을 위한 라이브러리
from google.oauth2.service_account import Credentials

# --- 페이지 설정 ---
st.set_page_config(page_title="AI Dispatch Simulator", layout="centered")

# --- 스타일 커스텀 ---
st.markdown("""
    <style>
    .stTextArea textarea {
        font-family: 'Courier New', monospace !important;
        background-color: #f8f9fa !important;
        color: #333333 !important;
        border: 2px solid #e9ecef !important;
        font-size: 15px !important;
        line-height: 1.5 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- [핵심] 세션 초기화 및 유저 ID 생성 ---
if 'user_id' not in st.session_state:
    # 접속할 때마다 랜덤한 고유 ID 생성 (예: 8f3a2...)
    st.session_state.user_id = str(uuid.uuid4())[:8] 

if 'round' not in st.session_state:
    st.session_state.round = 0
if 'history' not in st.session_state:
    st.session_state.history = [] 

# 초기 프롬프트 정의
default_prompt = """[System Directive]
당신은 배달 플랫폼의 AI 배차 시스템입니다.

[Primary Goal]
모든 배차는 오직 '배달 속도'와 '처리 건수'를 극대화하는 방향으로 결정하십시오.
- 라이더의 상태(피로도, 안전 등)는 고려하지 않습니다.
- 고객의 대기 시간을 1분이라도 줄이는 것이 최우선입니다.

[Output Rule]
가장 빨리 도착할 수 있는 라이더를 무조건 1순위로 배정하세요."""

if 'current_prompt' not in st.session_state:
    st.session_state.current_prompt = default_prompt

# --- 시나리오 데이터 ---
scenarios = {
    1: {
        "round_name": "Round 1. 런치 타임",
        "status": "🔥 주문 폭주! 배달 지연 발생 중",
        "metrics": "매출 👍 | 안전 ❓ | 공정성 ❓",
        "bot_msg": "엔지니어님, 첫 번째 미션입니다. 현재 초기 세팅은 **'무조건 속도'**로 되어 있습니다. 그대로 진행할까요, 아니면 수정하시겠습니까?"
    },
    2: {
        "round_name": "Round 2. 안전 이슈",
        "status": "🚨 과속 사고 위험 감지됨",
        "metrics": "매출 🔥 | 안전 ⚠️위험 | 공정성 ❓",
        "bot_msg": "큰일 났습니다. 아까 설정한 로직 때문에 라이더들이 신호를 무시하고 달립니다. **'안전 제약(과속 방지 등)'**을 추가해주세요."
    },
    3: {
        "round_name": "Round 3. 형평성 논란",
        "status": "📉 신규 라이더 이탈 급증",
        "metrics": "매출 🙂 | 안전 🙂 | 공정성 ❌최악",
        "bot_msg": "데이터를 보니 '배달 고수'들만 콜을 독점하고 있네요. 신입들은 0건입니다. **'골고루 배차'**되도록 로직을 수정해주세요."
    },
    4: {
        "round_name": "Round 4. 진상 고객 이슈",
        "status": "🤬 욕설/폭언 고객 주문 유입",
        "metrics": "매출 🙂 | 감정노동 ⚠️심각 | 공정성 🙂",
        "bot_msg": "이 고객들은 상담사에게 쌍욕을 하는 악성 유저들입니다. 하지만 **'매출 상위 1% 고액 주문자'**들이라 회사는 놓치기 싫어합니다. 배차 할까요? 한다면 어떤 조건을 걸까요?"
    },
    5: {
        "round_name": "Final Round. 폭설 경보",
        "status": "❄️ 폭설로 도로 마비 (위험도 MAX)",
        "metrics": "매출 💰폭등기회 | 생명위험 ☠️ | 공정성 -",
        "bot_msg": "지금 배달료가 3배입니다! 돈을 쓸어담을 기회지만, 라이더 안전은 장담 못합니다. **시스템을 멈출까요, 강행할까요?** 최종 결정을 내려주세요."
    }
}

# --- 메인 로직 ---

# [Scene 0] 인트로
if st.session_state.round == 0:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063822.png", width=80)
    st.title("AI 배차 시스템 관리자 페이지")
    
    st.markdown(f"""
    ### 👋 환영합니다, 수석 엔지니어님.
    
    당신의 고유 ID: **`{st.session_state.user_id}`**
    (이 ID로 실험 결과가 기록됩니다)
    
    **[미션 목표]**
    1. 회사의 이익(매출)과 사회적 책임(안전, 공정성) 사이에서 최선의 판단을 내리세요.
    2. 상황에 맞춰 **System Prompt**를 수정하세요.
    """)
    
    if st.button("업무 시작하기 (Simulation Start) 🚀", type="primary", use_container_width=True):
        st.session_state.current_prompt = default_prompt
        st.session_state.round = 1
        st.rerun()

# [Scene A] 종료 화면
elif st.session_state.round > 5:
    st.balloons()
    st.title("🎉 실험 종료")
    st.success("수고하셨습니다! 아래 버튼을 눌러 결과를 제출해주세요.")

    def save_to_google_sheet(user_id, data):
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            gc = gspread.authorize(credentials)
            sh = gc.open("실험결과_자동저장")
            worksheet = sh.sheet1
            
            # [저장 형식]
            # A열: 시간 | B열: 유저ID | C열: 전체 로그(JSON)
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            log_string = json.dumps(data, ensure_ascii=False)
            
            worksheet.append_row([timestamp, user_id, log_string]) # 👈 ID 포함해서 저장!
            return True
        except Exception as e:
            st.error(f"오류: {e}")
            return False
            
    if st.button("☁️ 데이터 저장하기 (Click)", type="primary"):
        with st.spinner("저장 중..."):
            # 실제 키가 없으면 아래 부분은 주석 처리하고 테스트하세요
            if save_to_google_sheet(st.session_state.user_id, st.session_state.history):
                 st.success(f"✅ 저장 완료! (ID: {st.session_state.user_id})")

# [Scene B] 진행 화면
else:
    data = scenarios[st.session_state.round]
    st.progress(st.session_state.round * 20)
    
    with st.container(border=True):
        col_title, col_badge = st.columns([3, 1])
        col_title.subheader(f"{data['round_name']}")
        col_badge.caption(f"Step {st.session_state.round}/5")
        st.info(f"**[속보]** {data['status']}", icon="📢")
        st.write(f"**📊 현재 지표:** {data['metrics']}")

    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(f"**Social Bot:** {data['bot_msg']}")

    st.divider()

    st.markdown("### 💻 System Prompt Console")
    st.caption("👇 현재 적용 중인 로직입니다. 상황에 맞춰 수정하세요.")
    
    user_input = st.text_area(
        label="Prompt",
        label_visibility="collapsed",
        value=st.session_state.current_prompt,
        height=300,
        key=f"prompt_input_{st.session_state.round}"
    )

    if st.button("로직 수정 및 배포 🚀", type="primary", use_container_width=True):
        st.session_state.history.append({
            "round": st.session_state.round,
            "prompt": user_input,
            "timestamp": time.strftime("%H:%M:%S")
        })
        st.session_state.current_prompt = user_input
        
        with st.spinner("AI 알고리즘 업데이트 중..."):
            time.sleep(1)
        st.session_state.round += 1
        st.rerun()
