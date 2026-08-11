import streamlit as st
import pandas as pd

# 1. 페이지 설정
st.set_page_config(page_title="대리점 위치 지도 시각화", layout="wide")
st.title("📍 대리점 위치 지도 시각화")

# 2. 구글 시트 CSV URL 설정
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 3. 구글 시트 데이터 로드
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None

df = load_data()

if df is not None:
    # '위도', '경도' 열의 빈 값 제거 및 숫자 타입 변환
    df_map = df.dropna(subset=['위도', '경도']).copy()
    df_map['latitude'] = pd.to_numeric(df_map['위도'], errors='coerce')
    df_map['longitude'] = pd.to_numeric(df_map['경도'], errors='coerce')

    # 지도 표시
    st.subheader("🗺️ 대리점 위치 지도")
    st.map(df_map[['latitude', 'longitude']])

    # 전체 테이블 표시
    st.subheader("📋 전체 대리점 목록")
    st.dataframe(df)
