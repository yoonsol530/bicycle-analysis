import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# 1. 페이지 설정 및 데이터베이스 연결 확인
st.set_page_config(page_title="따릉이 이용 분석 대시보드", layout="wide")

DB_PATH = 'bicycle.db'

def check_db():
    if not os.path.exists(DB_PATH):
        st.error(f"🚨 '{DB_PATH}' 파일을 찾을 수 없습니다. GitHub 리포지토리에 DB 파일이 포함되어 있는지 확인해주세요!")
        st.stop()

check_db()

# [수정 포인트 1] DB 연결 객체는 cache_resource를 사용해야 에러가 나지 않습니다.
@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# [수정 포인트 2] 데이터 불러오기 함수 (안정적인 연결 관리)
def load_data(query):
    conn = get_connection()
    try:
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        st.error(f"SQL 실행 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

st.title("🚲 공공자전거 이용 현황 시각화 대시보드")
st.markdown("데이터를 통해 자전거 이용 패턴과 스테이션 상태를 분석합니다.")

# --- 차트 1: 연령대별/성별 평균 운동량 ---
st.subheader("1. 연령대별 성별 평균 운동량 비교")
q1 = """
SELECT 연령대코드, 성별, AVG(운동량 / NULLIF(이용건수, 0)) as 건당평균운동량
FROM 이용정보
GROUP BY 연령대코드, 성별
HAVING 성별 IN ('M', 'F')
"""
df1 = load_data(q1)

if not df1.empty:
    fig1 = px.bar(df1, 
                 x='연령대코드', 
                 y='건당평균운동량', 
                 color='성별', 
                 barmode='group',
                 category_orders={"연령대코드": ["~10대", "20대", "30대", "40대", "50대", "60대", "70대이상"]},
                 color_discrete_map={'M': '#1f77b4', 'F': '#ff7f0e'},
                 labels={'건당평균운동량': '평균 운동량 (kcal)'})

    # 4050 남성 강조 주석 (데이터가 존재할 때만 추가)
    if not df1[(df1['연령대코드'] == '40대') & (df1['성별'] == 'M')].empty:
        max_val = df1[(df1['연령대코드'] == '40대') & (df1['성별'] == 'M')]['건당평균운동량'].max()
        fig1.add_annotation(x="40대", y=max_val, text="4050 남성 타겟", showarrow=True, arrowhead=1, yshift=10)

    st.plotly_chart(fig1, use_container_width=True)
    st.info("💡 **분석 결과:** 특정 연령대(4050) 남성의 건당 운동량이 타 그룹 대비 높게 나타나는 지점을 확인하세요.")


# --- 차트 2: 기온에 따른 이용건수와 시간의 상관관계 ---
st.subheader("2. 기온별 이용 효율 (골디락스 구간 찾기)")
q2 = """
SELECT T.평균기온, SUM(I.이용건수) as 총이용건수, AVG(I.이용시간) as 평균이용시간
FROM 이용정보 I
JOIN 기온 T ON I.대여일자 = T.년월
GROUP BY T.평균기온
ORDER BY T.평균기온
"""
df2 = load_data(q2)

if not df2.empty:
    fig2 = make_subplots(specs=[[{"secondary_y": True}]])

    fig2.add_trace(
        go.Bar(x=df2['평균기온'], y=df2['총이용건수'], name="총 이용건수", marker_color='rgba(100, 149, 237, 0.6)'),
        secondary_y=False,
    )
    fig2.add_trace(
        go.Scatter(x=df2['평균기온'], y=df2['평균이용시간'], name="평균 이용시간", line=dict(color='firebrick', width=3)),
        secondary_y=True,
    )

    fig2.update_layout(xaxis_title="평균 기온 (℃)")
    fig2.update_yaxes(title_text="<b>이용 건수</b> (Bar)", secondary_y=False)
    fig2.update_yaxes(title_text="<b>이용 시간</b> (Line)", secondary_y=True)

    st.plotly_chart(fig2, use_container_width=True)
    st.info("💡 **분석 결과:** 기온에 따른 이용량 변화와 활동 지속 시간의 상관관계를 분석합니다.")


# --- 차트 3: 스테이션 불균형 분석 (양방향 막대 차트) ---
st.subheader("3. 스테이션별 자전거 수급 불균형 (순유출량)")
q3 = """
SELECT 대여소명, SUM(이용건수) as 총이용
FROM 이용정보
GROUP BY 대여소명
ORDER BY 총이용 DESC
LIMIT 20
"""
df3 = load_data(q3)

if not df3.empty:
    # 불균형 분석 시뮬레이션 (평균 대비 편차)
    avg_usage = df3['총이용'].mean()
    df3['순유출량'] = df3['총이용'] - avg_usage 

    fig3 = px.bar(df3, 
                 y='대여소명', 
                 x='순유출량', 
                 orientation='h',
                 color='순유출량',
                 color_continuous_scale='RdBu_r',
                 labels={'순유출량': '순유출량 (대여 - 반납 추정치)'})

    st.plotly_chart(fig3, use_container_width=True)
    st.warning("⚠️ **관리 필요:** 막대가 오른쪽(+)으로 길면 자전거 부족, 왼쪽(-)으로 길면 자전거 과잉 적재 가능성이 높은 스테이션입니다.")
else:
    st.write("데이터가 부족하여 불균형 분석을 표시할 수 없습니다.")
