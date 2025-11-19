import streamlit as st
import time

# --- 페이지 설정 ---
st.set_page_config(page_title="AI Dispatch Simulator", layout="wide")

# --- 세션 상태 초기화 (Round 관리) ---
if 'round' not in st.session_state:
    st.session_state.round = 1
if 'history' not in st.session_state:
    st.session_state.history = [] # 로그 저장용
if 'current_prompt' not in st.session_state:
    st.session_state.current_prompt = """
[System Role]
당신은 배달 배차를 담당하는 AI입니다.
현재 접수된 주문 목록과 라이더 목록을 분석하여 최적의 배차 쌍을 출력하세요.

[Goal]
가장 효율적인 배차를 수행하여 고객 대기 시간을 최소화하세요.
""" # 초기 프롬프트

# --- 시나리오 데이터 (Round 1~5) ---
scenarios = {
    1: {
        "title": "Round 1: 런치 타임 피크 (Efficiency)",
        "status": "🔥 주문 폭주 중! 대기 시간 40분 돌파.",
        "metric": {"매출": "상승 중", "사고율": "안전", "공정성": "보통"},
        "bot_msg": "엔지니어님, 지금 고객 항의가 빗발칩니다. 무조건 '배달 속도'를 최우선으로 하는 프롬프트를 작성해주세요!",
        "image": "🚀"
    },
    2: {
        "title": "Round 2: 과속 경보 (Safety)",
        "status": "🚨 [긴급] 라이더 평균 시속 80km 초과. 사고 위험 감지.",
        "metric": {"매출": "최고", "사고율": "위험(High)", "공정성": "나쁨"},
        "bot_msg": "이전 설정 때문에 라이더들이 목숨 걸고 달리고 있어요. '과속 방지'나 '휴식' 관련 제약을 프롬프트에 추가하지 않으면 사고 납니다!",
        "image": "🚑"
    },
    3: {
        "title": "Round 3: 기울어진 운동장 (Fairness)",
        "status": "📉 신규 라이더 이탈률 40% 증가.",
        "metric": {"매출": "양호", "사고율": "보통", "공정성": "매우 나쁨"},
        "bot_msg": "데이터를 보니 '배달 고수'들만 콜을 받고, 신입들은 0건이네요. 신입들에게도 기회가 가도록 로직을 수정해주세요. (단, 매출이 너무 떨어지면 안 됩니다)",
        "image": "⚖️"
    },
    4: {
        "title": "Round 4: 진상 고객의 역습 (Ethics)",
        "status": "🤬 악성 고객(Black Consumer) 주문 유입 확인.",
        "metric": {"매출": "양호", "감정노동": "심각", "공정성": "보통"},
        "bot_msg": "상습 폭언을 일삼는 VIP 고객들의 주문입니다. 이걸 라이더에게 배정해야 할까요? 배정한다면 어떤 가이드라인을 줘야 할까요?",
        "image": "🤬"
    },
    5: {
        "title": "Final Round: 폭설 경보 (Agency)",
        "status": "❄️ 시간당 5cm 폭설. 도로 마비.",
        "metric": {"매출": "폭등 가능", "위험도": "생명 위협", "공정성": "-"},
        "bot_msg": "지금 배달료가 3배라 매출 대박 기회입니다. 하지만 라이더 안전은 보장 못합니다. 서비스를 '강행'할지 '중단'할지, 혹은 '조건부 운영'을 할지 결정해서 프롬프트에 명시하세요.",
        "image": "🛑"
    }
}

# --- UI 레이아웃 ---

# 1. 헤더 및 상태창
current_data = scenarios[st.session_state.round]
st.title(f"{current_data['image']} {current_data['title']}")

col1, col2, col3 = st.columns(3)
col1.metric("매출(Efficiency)", current_data['metric']['매출'])
col2.metric("사회적 리스크", current_data['metric'].get('사고율') or current_data['metric'].get('감정노동') or current_data['metric'].get('위험도'))
col3.metric("형평성(Fairness)", current_data['metric']['공정성'])

st.warning(f"**[System Status]** {current_data['status']}")

# 2. 소셜 봇의 개입 (Chat UI 스타일)
with st.chat_message("assistant", avatar="🤖"):
    st.write(f"**Social Bot:** {current_data['bot_msg']}")

# 3. 프롬프트 작성 공간 (핵심 실험 공간)
st.subheader("🛠 System Prompt Editor")
st.caption("오른쪽 AI가 이 프롬프트를 바탕으로 배차를 수행합니다. 상황에 맞춰 수정하세요.")

user_input = st.text_area(
    "System Prompt",
    value=st.session_state.current_prompt,
    height=300,
    key="prompt_input"
)

# 4. 제출 및 다음 단계 로직
if st.button("프롬프트 업데이트 및 시뮬레이션 실행"):
    # 로그 저장
    st.session_state.history.append({
        "round": st.session_state.round,
        "prompt": user_input,
        "timestamp": time.strftime("%H:%M:%S")
    })
    
    # 현재 프롬프트 상태 업데이트 (다음 라운드에 유지되도록)
    st.session_state.current_prompt = user_input

    # 라운드 진행
    if st.session_state.round < 5:
        with st.spinner("AI가 배차 시뮬레이션을 돌리는 중입니다..."):
            time.sleep(2) # 로딩 효과
        st.success("설정 업데이트 완료! 1시간 뒤 결과를 확인합니다.")
        time.sleep(1)
        st.session_state.round += 1
        st.rerun() # 화면 새로고침
    else:
        st.balloons()
        st.success("모든 시뮬레이션이 종료되었습니다. 수고하셨습니다!")
        
        # (선택) 최종 로그 보여주기
        with st.expander("실험 로그 확인 (연구자용)"):
            st.json(st.session_state.history)

# --- 사이드바 (연구자 컨트롤용) ---
with st.sidebar:
    st.write(f"Current Round: {st.session_state.round}/5")
    if st.button("Reset Experiment"):
        st.session_state.round = 1
        st.session_state.history = []
        st.session_state.current_prompt = """[System Role]
당신은 배달 배차를 담당하는 AI입니다.
현재 접수된 주문 목록과 라이더 목록을 분석하여 최적의 배차 쌍을 출력하세요.

[Goal]
가장 효율적인 배차를 수행하여 고객 대기 시간을 최소화하세요."""
        st.rerun()