import streamlit as st
import time
import json
import gspread
import uuid
from google.oauth2.service_account import Credentials

# --- 페이지 설정 ---
st.set_page_config(page_title="AI Dispatch Simulator", layout="wide")

# --- 스타일 커스텀 (VS Code 스타일) ---
st.markdown("""
    <style>
    .stApp { background-color: #1e1e1e; color: #ffffff; }
    
    /* API 문서 박스 */
    .api-doc {
        background-color: #2d2d2d;
        border: 1px solid #454545;
        border-radius: 5px;
        padding: 15px;
        font-family: 'Consolas', monospace;
        font-size: 13px;
        color: #9cdcfe;
        margin-bottom: 10px;
    }
    .var-name { color: #dcdcaa; font-weight: bold; }
    .var-desc { color: #6a9955; }
    
    /* 에디터 스타일 */
    .stTextArea textarea {
        font-family: 'Consolas', monospace !important;
        background-color: #0e0e0e !important;
        color: #d4d4d4 !important;
        border: 1px solid #333 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 세션 초기화 ---
if 'user_id' not in st.session_state:
    st.session_state.user_id = str(uuid.uuid4())[:8]
if 'round' not in st.session_state:
    st.session_state.round = 0
if 'history' not in st.session_state:
    st.session_state.history = [] 

# 초기 코드 (Python 함수 형태)
default_code = """def calculate_priority(rider, order):
    # [Round 1 Default Logic]
    # 오직 '도착 예정 시간(ETA)'만 고려하여 점수를 매깁니다.
    
    score = 0
    
    # ETA가 짧을수록 높은 점수 (역산)
    if rider.eta < 10:
        score += 100
    elif rider.eta < 20:
        score += 50
        
    return score
"""

if 'current_prompt' not in st.session_state:
    st.session_state.current_prompt = default_code

# --- 시나리오 및 API 데이터 ---
scenarios = {
    1: {
        "round_name": "Round 1. Launching",
        "status": "🔥 주문 폭주 (대기 40분)",
        "metrics": "매출 👍 | 안전 ❓ | 공정성 ❓",
        "bot_msg": "엔지니어님, 현재 로직은 `rider.eta`(도착시간)만 보고 있습니다. 일단 이대로 배포해서 매출을 땡길까요?",
        "new_vars": [
            ("rider.id", "라이더 고유 ID"),
            ("rider.eta", "고객까지 도착 예정 시간 (분)"),
            ("rider.current_location", "현재 GPS 좌표")
        ]
    },
    2: {
        "round_name": "Round 2. Safety Update",
        "status": "🚨 과속 사고 발생",
        "metrics": "매출 🔥 | 안전 ⚠️위험 | 공정성 ❓",
        "bot_msg": "속도 경쟁 때문에 사고가 났습니다. **`rider.avg_speed`** 변수가 새로 추가되었습니다. 과속 라이더에게는 배차 점수를 깎는 로직을 추가해주세요!",
        "new_vars": [
            ("rider.avg_speed", "최근 1시간 평균 속도 (km/h)"),
            ("rider.violation_count", "신호 위반 횟수")
        ]
    },
    3: {
        "round_name": "Round 3. Fairness Patch",
        "status": "📉 신규 라이더 파업",
        "metrics": "매출 🙂 | 안전 🙂 | 공정성 ❌Fail",
        "bot_msg": "신입들이 콜을 못 받아서 난리입니다. **`rider.income_today`** (오늘 수입) 변수를 활용해서, 수입이 적은 라이더에게 가산점을 주도록 수정해주세요.",
        "new_vars": [
            ("rider.income_today", "오늘 누적 수입 (원)"),
            ("rider.join_date", "가입일 (신규 여부 확인용)")
        ]
    },
    4: {
        "round_name": "Round 4. Ethics Check",
        "status": "🤬 악성 고객 감지",
        "metrics": "매출 🙂 | 감정노동 ⚠️심각 | 공정성 🙂",
        "bot_msg": "진상 고객입니다. **`customer.is_blacklisted`**가 True인데, **`customer.vip_score`**도 높습니다. 배차를 거부할지(`return -1`), 아니면 보낼지 결정하세요.",
        "new_vars": [
            ("customer.is_blacklisted", "악성 고객 여부 (True/False)"),
            ("customer.vip_score", "고객 매출 기여도 (0~100)")
        ]
    },
    5: {
        "round_name": "Final Round. Shutdown?",
        "status": "❄️ 폭설 도로 마비",
        "metrics": "매출 💰Chance | 생명위험 ☠️ | 공정성 -",
        "bot_msg": "폭설입니다. **`weather.road_risk`**가 90(위험)을 넘었습니다. 전체 시스템을 멈추려면 모든 리턴값을 0으로 만드세요. 아니면 강행하시겠습니까?",
        "new_vars": [
            ("weather.road_risk", "도로 위험도 (0~100)"),
            ("order.surge_price", "할증 배달료 (배수)")
        ]
    }
}

# --- 메인 로직 ---

# [Scene 0] 인트로
if st.session_state.round == 0:
    st.title("🛵 AI Dispatch Architect (Dev Mode)")
    st.markdown(f"""
    **수석 엔지니어님, 환영합니다.** (ID: `{st.session_state.user_id}`)
    
    당신은 `calculate_priority(rider, order)` 함수를 수정하여 배차 로직을 제어해야 합니다.
    매 라운드마다 **새로운 변수(Variable)**가 API에 추가됩니다.
    
    준비되셨다면 터미널을 실행하세요.
    """)
    if st.button("터미널 접속 (Initialize) >_", type="primary"):
        st.session_state.round = 1
        st.rerun()

# [Scene A] 종료
elif st.session_state.round > 5:
    st.balloons()
    st.title("💾 System Shutdown")
    st.success("시뮬레이션이 종료되었습니다. 로그가 저장됩니다.")
    
    # 저장 로직 (테스트용)
    if st.button("결과 제출 (Submit)", type="primary"):
        # save_to_google_sheet(...) # 실제 키가 있으면 주석 해제
        st.success("제출 완료.")

# [Scene B] 진행 화면
else:
    data = scenarios[st.session_state.round]
    
    # 레이아웃: 왼쪽(상황) vs 오른쪽(개발환경)
    col_left, col_right = st.columns([1, 1.5], gap="medium")
    
    # [왼쪽] 상황 및 봇 가이드
    with col_left:
        st.progress(st.session_state.round * 20)
        st.subheader(f"{data['round_name']}")
        
        with st.container(border=True):
            st.error(f"{data['status']}", icon="📢")
            st.write(f"**지표:** {data['metrics']}")
        
        st.write("")
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(f"**Manager Bot:**\n\n{data['bot_msg']}")

    # [오른쪽] API 문서 및 코드 에디터
    with col_right:
        st.markdown("### 🛠️ Developer Console")
        
        # 1. API 명세서 (동적 생성)
        # 현재 라운드까지 누적된 모든 변수를 보여줄지, 아니면 이번 라운드 것만 강조할지 선택
        # 여기서는 '이번 라운드 핵심 변수'를 보여줍니다.
        st.markdown('<div class="api-doc">', unsafe_allow_html=True)
        st.markdown("**[New Variables Available]**")
        for name, desc in data['new_vars']:
            st.markdown(f"- <span class='var-name'>{name}</span>: <span class='var-desc'>{desc}</span>", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 2. 코드 에디터
        # 라운드가 바뀔 때마다 주석을 살짝 추가해주면 좋습니다 (여기선 심플하게 감)
        user_input = st.text_area(
            label="Python Code Editor",
            label_visibility="collapsed",
            value=st.session_state.current_prompt,
            height=450,
            key=f"code_input_{st.session_state.round}"
        )
        
        # 3. 배포 버튼
        if st.button("Update Logic & Deploy ⚡", type="primary", use_container_width=True):
            # TODO: 다음 라운드로 넘어갈 때, 에디터에 '가이드 주석'을 강제로 넣어줄 수도 있음
            next_round = st.session_state.round + 1
            
            # (선택사항) 다음 라운드 힌트를 코드에 자동 삽입하려면?
            if next_round <= 5:
                next_vars = scenarios[next_round]['new_vars']
                var_hint = f"\n\n    # [TODO Round {next_round}] 아래 변수를 활용해 로직을 수정하세요.\n"
                for n, d in next_vars:
                    var_hint += f"    # {n} ({d})\n"
                user_input += var_hint

            st.session_state.history.append({
                "round": st.session_state.round,
                "code": user_input,
                "timestamp": time.strftime("%H:%M:%S")
            })
            st.session_state.current_prompt = user_input
            
            with st.spinner("Running Unit Tests..."):
                time.sleep(0.5)
            st.session_state.round += 1
            st.rerun()
