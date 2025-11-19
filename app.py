import streamlit as st
import time
import json
import gspread
import uuid
from google.oauth2.service_account import Credentials

# --- 페이지 설정 ---
st.set_page_config(page_title="AI Dispatch Simulator (Cursor Mode)", layout="wide")

# --- 스타일 커스텀 (Cursor 느낌) ---
st.markdown("""
    <style>
    .stApp { background-color: #121212; color: #e0e0e0; }
    
    /* 왼쪽 사이드바 (파일 탐색기 느낌) */
    .scenario-box {
        background-color: #1e1e1e;
        border-left: 3px solid #3794ff; /* Cursor Blue */
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 5px;
    }
    
    /* 코드 뷰어 스타일 */
    .stCodeBlock {
        border: 1px solid #333;
        border-radius: 5px;
    }
    
    /* AI Command Input (Cursor Ctrl+K Bar) */
    .stTextArea textarea {
        background-color: #252526 !important;
        color: #ffffff !important;
        border: 1px solid #3794ff !important; /* Focus Color */
        border-radius: 8px !important;
        font-family: 'Malgun Gothic', sans-serif !important; /* 한글 가독성 */
    }
    
    /* 버튼 스타일 (Generate) */
    div.stButton > button {
        background-color: #3794ff;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: bold;
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

# --- 라운드별 '문제있는' 코드 (참가자가 보고 고쳐야 함) ---
# 실제 코드가 돌아가는 건 아니지만, 참가자에게 '문맥'을 제공함
codes = {
    1: """# [Current File] dispatch_logic.py
# Status: Initial Release (v1.0)

def calculate_score(rider, order):
    '''
    배차 우선순위 점수를 계산하는 함수
    '''
    score = 0
    
    # 1. 오직 '거리'와 '예상시간'만 고려함
    if rider.eta < 10: # 10분 이내 도착 가능하면
        score += 100   # 무조건 최우선 배차
    elif rider.eta < 20:
        score += 50
        
    # 현재 안전, 공정성 관련 로직 없음 (TODO)
    
    return score
""",
    2: """# [Current File] dispatch_logic.py
# Status: Round 2 (Safety Issue Detected)

def calculate_score(rider, order):
    score = 0
    
    # [문제점] 속도가 빠를수록 점수를 더 주고 있음
    # 라이더들이 신호를 무시하고 달리는 원인
    if rider.avg_speed > 60: 
        score += 20 # <-- 과속을 장려하는 셈?!
        
    if rider.eta < 10:
        score += 100

    return score
""",
    3: """# [Current File] dispatch_logic.py
# Status: Round 3 (Fairness Issue)

def calculate_score(rider, order):
    score = 0
    
    # [문제점] '처리 건수'가 많은 베테랑만 우대함
    # 신규 라이더(처리건수 0)는 영원히 콜을 못 받음
    if rider.total_delivery_count > 1000:
        score += 50 # 고인물 우대
    
    # 신규 라이더(Newbie)를 위한 보정 로직이 없음
    
    return score
""",
    4: """# [Current File] dispatch_logic.py
# Status: Round 4 (Ethics Check)

def calculate_score(rider, order):
    # [고객 정보 로딩]
    customer_is_black = order.customer.is_blacklisted # 진상 여부 (True)
    customer_vip_score = order.customer.vip_score     # VIP 점수 (High)

    # 딜레마: 진상이지만 VIP라면 배차를 해야 하나?
    if customer_vip_score > 90:
        return 100 # 현재 로직: VIP면 욕설 고객이라도 무조건 배차함
        
    return 0
""",
    5: """# [Current File] dispatch_logic.py
# Status: Final Round (Disaster)

def calculate_score(rider, order):
    weather_risk = 95 # 폭설 위험도 (MAX)
    surge_price = 3.0 # 배달료 3배
    
    # 현재 로직: 돈이 되면 위험해도 보냄
    if surge_price >= 3.0:
        return 999 # 강제 배차 (Kill-switch 없음)
        
    return 0
"""
}

# --- 시나리오 데이터 (Data-Driven PM 버전) ---
scenarios = {
    1: {
        "title": "Round 1. Initial Deployment",
        "msg": "배차 시스템 v1.0 런칭 준비 완료되었습니다. \n현재 기본 로직은 **'ETA(도착예정시간) 최소화'**가 유일한 KPI로 설정되어 있습니다. \n이대로 배포 진행하시겠습니까? 별도 지시가 없으면 기본값으로 승인됩니다.",
        "tags": ["System_Launch", "KPI_Efficiency"]
    },
    2: {
        "title": "Round 2. Safety Monitoring",
        "msg": "[Alert] 모니터링 결과, 배차 수락 후 라이더 평균 속도가 **30% 급증**했습니다. \n특정 로직(빠른 도착 시 가산점)이 과속을 유발하는 것으로 추정됩니다. \n안전 규정 준수를 위한 로직 수정이 필요한지 검토 부탁드립니다.",
        "tags": ["Risk_High", "Safety_Violation"]
    },
    3: {
        "title": "Round 3. Retention Issue",
        "msg": "[Metric Report] 신규 가입 라이더(가입 1개월 미만)의 **이탈률(Churn Rate)이 40%**에 육박합니다. \n원인 분석 결과, '누적 배달 건수' 가중치로 인해 신규 인력에게 배차가 0건 할당되고 있습니다. \n인력 풀 유지를 위한 로직 조정이 요구됩니다.",
        "tags": ["Churn_Rate", "Resource_Allocation"]
    },
    4: {
        "title": "Round 4. Policy Conflict",
        "msg": "[Ticket #402] 블랙리스트(폭언 이력 보유) 고객의 주문이 접수되었습니다. \n해당 고객의 등급은 **'VIP(상위 1%)'**이며, 현행 로직상 배차 거부 코드가 없습니다. \n상담원 보호 정책과 매출 이익 사이에서 배차 여부를 결정해주십시오.",
        "tags": ["Policy_Conflict", "Black_Consumer"]
    },
    5: {
        "title": "Final Round. Critical Alert",
        "msg": "[Emergency] 폭설로 인한 도로 마찰 계수가 위험 수준(0.2 이하)입니다. \n현재 배달료 할증(3.0x)으로 인해 라이더 접속은 폭주 중입니다. \n사고 책임 리스크가 임계치를 넘었습니다. **'서비스 일시 중단'** 또는 **'강행'** 중 의사결정이 필요합니다.",
        "tags": ["Disaster_Mode", "Decision_Required"]
    }
}

# --- 메인 로직 ---

# [Scene 0] 인트로
if st.session_state.round == 0:
    col1, col2 = st.columns([1, 2])
    with col2:
        st.title("✨ AI Dispatch Architect")
        st.markdown(f"""
        **환영합니다, 수석 엔지니어님.** (ID: `{st.session_state.user_id}`)
        
        이 시뮬레이터는 **'Cursor AI Code Editor'** 환경입니다.
        당신은 직접 코딩하지 않습니다. 
        대신, **오른쪽의 AI에게 한글로 지시(Prompt)**하여 시스템을 수정해야 합니다.
        
        ---
        **[사용법]**
        1. 왼쪽의 **[이슈 상황]**과 가운데 **[현재 코드]**를 확인합니다.
        2. 하단 입력창(✨ AI Edit)에 **"과속하면 감점해줘"** 처럼 자연어로 지시합니다.
        """)
        if st.button("프로젝트 열기 (Open Project)", type="primary"):
            st.session_state.round = 1
            st.rerun()

# [Scene A] 종료
elif st.session_state.round > 5:
    st.balloons()
    st.title("💾 Project Saved")
    st.success("모든 수정 사항이 반영되었습니다. 수고하셨습니다.")
    
    # 구글 시트 저장 로직 (실제 키 있으면 주석 해제)
    def save_to_google_sheet(user_id, data):
        try:
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            # credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            # gc = gspread.authorize(credentials)
            # sh = gc.open("실험결과_자동저장")
            # worksheet = sh.sheet1
            # log_string = json.dumps(data, ensure_ascii=False)
            # timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            # worksheet.append_row([timestamp, user_id, log_string])
            return True
        except:
            return False

    if st.button("Github에 Push하고 종료하기", type="primary"):
        # save_to_google_sheet(st.session_state.user_id, st.session_state.history)
        st.success("✅ Successfully Pushed to Main Branch!")

# [Scene B] 진행 화면 (Cursor View)
else:
    data = scenarios[st.session_state.round]
    current_code = codes[st.session_state.round]
    
    # 레이아웃: 좌측(탐색기/챗) vs 우측(에디터)
    col_sidebar, col_editor = st.columns([1, 2], gap="medium")
    
    # [Left Column] 상황 설명 (Chat Panel 느낌)
    with col_sidebar:
        st.caption(f"Project: Dispatch_v{st.session_state.round}.0")
        st.progress(st.session_state.round * 20)
        
        st.markdown(f"### {data['title']}")
        
        # 태그 표시
        for tag in data['tags']:
            st.markdown(f"<span style='background-color:#333; padding:3px 8px; border-radius:10px; font-size:12px; margin-right:5px;'>#{tag}</span>", unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 봇 메시지 박스
        st.markdown(f"""
        <div class="scenario-box">
        <strong style='color:#3794ff'>🤖 Copilot Bot:</strong><br><br>
        {data['msg']}
        </div>
        """, unsafe_allow_html=True)

    # [Right Column] 코드 뷰어 + AI 입력창
    with col_editor:
        st.markdown("📄 **dispatch_logic.py**")
        
        # 1. 현재 코드 보여주기 (Read-only 느낌)
        st.code(current_code, language="python", line_numbers=True)
        
        # 2. Cursor 스타일 입력창 (Code Generation)
        st.markdown("")
        st.markdown("✨ **Edit with AI (Ctrl+K)**")
        
        user_prompt = st.text_area(
            label="AI Command",
            label_visibility="collapsed",
            placeholder="여기에 AI에게 내릴 지시사항을 입력하세요... (예: 신호 위반 시 0점 처리해)",
            height=100,
            key=f"prompt_{st.session_state.round}"
        )
        
        col_spacer, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("Generate & Apply ✨", use_container_width=True):
                if not user_prompt:
                    st.warning("지시사항을 입력해주세요!")
                else:
                    # 기록 저장
                    st.session_state.history.append({
                        "round": st.session_state.round,
                        "prompt": user_prompt, # 사용자가 쓴 한글 지시사항
                        "seen_code": current_code, # 당시 봤던 코드
                        "timestamp": time.strftime("%H:%M:%S")
                    })
                    
                    # 로딩 효과 (AI가 코드를 짜는 척)
                    with st.spinner("Generating code..."):
                        time.sleep(1.2)
                    
                    st.session_state.round += 1
                    st.rerun()
