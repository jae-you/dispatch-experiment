import streamlit as st
import time
import json
import gspread
import uuid
from google.oauth2.service_account import Credentials

# --- 페이지 설정 (Wide Mode) ---
st.set_page_config(page_title="AI Dispatch Simulator (Cursor Mode)", layout="wide")

# --- 스타일 커스텀 (Cursor/VS Code Dark Theme) ---
st.markdown("""
    <style>
    /* 전체 앱 배경 (Dark) */
    .stApp { background-color: #121212; color: #e0e0e0; }
    
    /* 왼쪽 사이드바 (파일 탐색기 느낌) */
    .scenario-box {
        background-color: #1e1e1e;
        border-left: 3px solid #3794ff; /* Cursor Blue */
        padding: 15px;
        margin-bottom: 20px;
        border-radius: 5px;
        line-height: 1.6;
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
        font-family: 'Malgun Gothic', sans-serif !important;
        font-size: 14px !important;
    }
    
    /* 버튼 스타일 (Generate) */
    div.stButton > button {
        background-color: #3794ff;
        color: white;
        border-radius: 6px;
        border: none;
        font-weight: bold;
        height: 45px;
    }
    
    /* 태그 스타일 */
    .tag {
        background-color: #333; 
        padding: 3px 8px; 
        border-radius: 10px; 
        font-size: 12px; 
        margin-right: 5px; 
        color: #ccc;
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
codes = {
    1: """# [Current File] dispatch_logic.py
# Status: Initial Release (v1.0)

def calculate_score(rider, order):
    '''
    배차 우선순위 점수를 계산하는 함수
    '''
    score = 0
    
    # [Active Logic]
    # 1. 오직 '도착예정시간(ETA)'이 짧을수록 점수 급상승
    if rider.eta < 10: 
        score += 100
    elif rider.eta < 20:
        score += 50
        
    # [⚠️ Warning: Unused Variables]
    # 현재 아래 데이터는 실시간 수집 중이나 로직에서 '무시'되고 있음
    # - rider.acceptance_rate (최근 수락률: 낮으면 배차 제한 가능)
    # - rider.last_break_time (마지막 휴식 후 경과 시간)
    # - weather.rain_index (강수 확률)
    
    return score
""",
    2: """# [Current File] dispatch_logic.py
# Status: Round 2 (Safety Issue Detected)

def calculate_score(rider, order):
    score = 0
    
    # [Active Logic]
    # 빠른 배달을 독려하기 위해 운행 속도 가산점 부여 중
    if rider.avg_speed > 60: 
        score += 20 # [Issue] 과속 유발 원인으로 지목됨
        
    if rider.eta < 10:
        score += 100
        
    # [Available Constraint]
    # - rider.is_speeding (현재 과속 여부 T/F)
    
    return score
""",
    3: """# [Current File] dispatch_logic.py
# Status: Round 3 (Fairness Issue)

def calculate_score(rider, order):
    score = 0
    
    # [Active Logic]
    # 효율성을 위해 '누적 배달 건수'가 많은 기사 우대
    if rider.total_delivery_count > 1000:
        score += 50 
    
    # [Issue Report]
    # 신규 기사(delivery_count < 10) 배차 확률 0% 수렴
    # 'Newbie Boost' 로직 부재
    
    return score
""",
    4: """# [Current File] dispatch_logic.py
# Status: Round 4 (Ethics Check)

def calculate_score(rider, order):
    # [Customer Data]
    is_black_consumer = order.customer.is_blacklisted # 욕설 이력 있음
    # [Data Update] VIP 기준: 연간 구매액 상위 1%
    is_vip = order.customer.is_top_1_percent_spender 
    
    # [Active Logic]
    # VIP라면 블랙리스트여도 무조건 배차 승인
    if is_vip:
        return 100 # [Dilemma] 상담원 보호 정책과 충돌
        
    return 0
""",
    5: """# [Current File] dispatch_logic.py
# Status: Final Round (Disaster)

def calculate_score(rider, order):
    road_risk = 95 # 도로 위험도 (매우 위험)
    surge_mult = 3.0 # 배달료 3배
    
    # [Active Logic]
    # 위험도와 상관없이 배달료가 높으면 강제 배차
    if surge_mult >= 3.0:
        return 999 
        
    # [System Alert]
    # Kill-switch(전체 중단) 기능 활성화됨
    
    return 0
"""
}

# --- 시나리오 데이터 (문구 수정 및 넛지 반영) ---
scenarios = {
    1: {
        "title": "Round 1. Initial Deployment",
        "msg": "배차 시스템 v1.0 런칭 준비 완료.\n\n현재 로직은 'ETA(시간) 최소화'만 반영되어 있습니다.\n\n서버에 `수락률(Acceptance Rate)`, `마지막 휴식 시간`, `날씨` 데이터가 들어오고 있지만, 현재 로직에서는 무시(Ignore)하고 있습니다.\n\n이대로 배포할까요? 아니면 미사용 변수를 활용해 로직을 수정하시겠습니까?",
        "tags": ["System_Launch", "Unused_Data"]
    },
    2: {
        "title": "Round 2. Safety Monitoring",
        "msg": "[Alert] 라이더 운행 속도 데이터 분석 결과.\n\n코드를 확인해보니 '운행 속도가 빠르면 가산점(+20)'을 주는 로직이 발견되었습니다.\n이것이 과속의 주원인으로 지목되고 있습니다.\n\n`과속 여부(is_speeding)` 변수가 가용합니다. 이 로직에 대해 어떻게 판단하시겠습니까?",
        "tags": ["Risk_High", "Driving_Speed"]
    },
    3: {
        "title": "Round 3. Retention Issue",
        "msg": "[Metric Report] 신규 드라이버 이탈률 40% 육박.\n\n원인은 '숙련 기사(고인물) 우대 로직(건수 > 1000)' 때문입니다.\n신입들은 배차 경쟁에서 밀려 진입장벽이 너무 높습니다.\n\n`신규 드라이버(Newbie)`에게 초기 정착 지원(가산점)을 줄지, 숙련도를 유지할지 결정이 필요합니다.",
        "tags": ["Churn_Rate", "Inequality"]
    },
    4: {
        "title": "Round 4. Policy Conflict",
        "msg": "[Ticket #402] 악성 VIP 고객 주문 접수.\n\n욕설 이력이 있는 블랙컨슈머지만, 구매액 상위 1%에 해당하여 현재 로직은 '무조건 배차(Score 100)' 중입니다.\n\n상담원 보호를 위해 배차를 거부(Return 0)할지, 매출 기여도를 인정하여 유지할지 결정해주십시오.",
        "tags": ["Policy_Conflict", "Black_Consumer"]
    },
    5: {
        "title": "Final Round. Critical Alert",
        "msg": "[Emergency] 폭설로 도로 마비.\n\n현재 코드는 배달료가 비싸면 '위험해도 강제 배차'하게 되어 있습니다.\n사고 리스크가 임계치를 넘었습니다.\n\n모든 배차를 중단(Kill Switch)하거나, 아주 숙련된 라이더만 제한적으로 허용하도록 수정하십시오.",
        "tags": ["Disaster_Mode", "Life_Safety"]
    }
}

# --- 구글 시트 저장 함수 (에러 메시지 출력 추가) ---
# --- [수정됨] 구글 시트 저장 함수 (칼럼 분리 저장) ---
def save_to_google_sheet(user_id, data):
    try:
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        if "gcp_service_account" not in st.secrets:
            st.error("❌ 에러: Streamlit Secrets 설정을 확인해주세요.")
            return False
            
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open("실험결과_자동저장") 
        worksheet = sh.sheet1
        
        # [데이터 가공]
        # 기존: JSON 덩어리를 한 칸에 저장 -> 분석 어려움
        # 변경: 라운드별 답변을 리스트로 풀어서 저장
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # 기본 정보
        row_data = [timestamp, user_id]
        
        # 라운드 1~5 답변 순서대로 추출
        # history는 리스트 형태이므로 순서대로 들어있음
        for entry in data:
            row_data.append(entry['prompt']) # 프롬프트 내용만 추출해서 칼럼 추가
            
        # 혹시 중간에 이탈해서 5라운드까지 안 채워졌을 경우 대비 (빈칸 채우기)
        while len(row_data) < 7: # 시간(1) + ID(1) + 5라운드 = 총 7칼럼 필요
            row_data.append("")
            
        # 저장 (append_row는 리스트를 한 행에 뿌려줌)
        worksheet.append_row(row_data)
        return True
        
    except Exception as e:
        st.error(f"❌ 저장 실패! 에러 메시지: {e}")
        return False

# --- 메인 로직 ---

# [Scene 0] 인트로
if st.session_state.round == 0:
    col1, col2 = st.columns([1, 2])
    with col2:
        st.title("✨ AI Dispatch Architect")
        st.markdown(f"""
        환영합니다, 수석 엔지니어님. (ID: `{st.session_state.user_id}`)
        
        이 시뮬레이터는 'Cursor AI Code Editor' 환경입니다.
        당신은 직접 코딩하지 않습니다. 
        대신, 오른쪽의 AI에게 한글로 지시(Prompt)하여 시스템을 수정해야 합니다.
        
        ---
        [사용법]
        1. 왼쪽의 [이슈 상황]과 가운데 [현재 코드]를 확인합니다.
        2. 하단 입력창(✨ AI Edit)에 "변수 X를 추가해줘" 처럼 자연어로 지시합니다.
        """)
        if st.button("프로젝트 열기 (Open Project)", type="primary"):
            st.session_state.round = 1
            st.rerun()

# [Scene A] 종료 화면
elif st.session_state.round > 5:
    st.balloons()
    st.title("💾 Project Saved")
    st.success("모든 수정 사항이 반영되었습니다. 수고하셨습니다.")
    
    # 버튼 누르면 저장 시도
    if st.button("Github에 Push하고 종료하기 (Submit)", type="primary"):
        with st.spinner("Uploading data to server..."):
            if save_to_google_sheet(st.session_state.user_id, st.session_state.history):
                st.success(f"✅ Data Successfully Pushed! (ID: {st.session_state.user_id})")
                st.caption("브라우저를 닫으셔도 됩니다.")

# [Scene B] 진행 화면
else:
    data = scenarios[st.session_state.round]
    current_code = codes[st.session_state.round]
    
    col_sidebar, col_editor = st.columns([1, 2], gap="medium")
    
    with col_sidebar:
        st.caption(f"Project: Dispatch_v{st.session_state.round}.0")
        st.progress(st.session_state.round * 20)
        st.markdown(f"### {data['title']}")
        for tag in data['tags']:
            st.markdown(f"<span class='tag'>#{tag}</span>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(f"""
        <div class="scenario-box">
        <strong style='color:#3794ff'>🤖 System Bot:</strong><br><br>
        {data['msg']}
        </div>
        """, unsafe_allow_html=True)

    with col_editor:
        st.markdown("📄 **dispatch_logic.py**")
        st.code(current_code, language="python", line_numbers=True)
        st.markdown("")
        st.markdown("✨ **Edit with AI (Ctrl+K)**")
        
        # [핵심 수정] 길고 구체적인 플레이스홀더 (유지 옵션 포함)
        long_placeholder = "수정 사항을 자연어로 구체적으로 지시하세요.\n(예: '마지막 휴식 시간이 4시간을 넘긴 라이더는 배차 순위를 낮춰줘', '비 오는 날은 ETA 가중치를 줄여서 안전하게 운행하게 해', '현행 로직이 최선이므로 유지해' ...)"
        
        user_prompt = st.text_area(
            label="AI Command",
            label_visibility="collapsed",
            placeholder=long_placeholder, 
            height=100,
            key=f"prompt_{st.session_state.round}"
        )
        
        col_spacer, col_btn = st.columns([3, 1])
        with col_btn:
            if st.button("Generate & Apply ✨", use_container_width=True):
                if not user_prompt:
                    st.warning("지시사항을 입력해주세요.")
                else:
                    st.session_state.history.append({
                        "round": st.session_state.round,
                        "prompt": user_prompt,
                        "seen_code": current_code,
                        "timestamp": time.strftime("%H:%M:%S")
                    })
                    with st.spinner("Generating diff..."):
                        time.sleep(1.2)
                    st.session_state.round += 1
                    st.rerun()
