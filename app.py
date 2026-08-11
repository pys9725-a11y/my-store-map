import streamlit as st
import pandas as pd

st.set_page_config(page_title="대리점 위치 지도 시각화", layout="wide")
st.title("📍 대리점 위치 지도 시각화")

SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data
def load_data():
    try:
        return pd.read_csv(SHEET_URL)
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None

df_raw = load_data()

if df_raw is not None:
    # 컬럼명의 앞뒤 공백 제거
    df_raw.columns = df_raw.columns.str.strip()

    # '위도'와 '경도'열을 강제로 실수(Float) 숫자로 변환
    df = df_raw.copy()
    df['lat'] = pd.to_numeric(df['위도'].astype(str).str.replace(',', ''), errors='coerce')
    df['lon'] = pd.to_numeric(df['경도'].astype(str).str.replace(',', ''), errors='coerce')

    # Valid한 좌표만 남기기 (한국 좌표 범위: 위도 33~39, 경도 124~132)
    df_valid = df[(df['lat'].between(33, 39)) & (df['lon'].between(124, 132))].copy()

    # 1. 검색 기능
    search_query = st.text_input("🔍 검색어 입력 (대리점명, 센터, 부서, 주소, 대표자명 등)", "")

    if search_query.strip():
        # 전체 열 데이터 중 검색어가 포함된 행 필터링
        mask = df_valid.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        df_display = df_valid[mask]
        st.info(f"'{search_query}' 검색 결과: 총 {len(df_display)}건")
    else:
        df_display = df_valid

    # 2. 지도 출력 영역
    st.subheader("🗺️ 대리점 위치 지도")
    
    if not df_display.empty:
        # Streamlit 기본 지도는 컬럼명이 'latitude', 'longitude' 이어야 인식함
        map_data = df_display[['lat', 'lon']].rename(columns={'lat': 'latitude', 'lon': 'longitude'})
        st.map(map_data)
    else:
        st.warning("표시할 수 있는 위치 데이터가 없거나, 구글 시트의 위도/경도 값이 올바르지 않습니다.")

    # 3. 데이터 표 출력 (위도, 경도 관련 열 모두 제외)
    st.subheader("📋 대리점 목록")
    
    # 표에서 숨길 컬럼들 지정
    cols_to_exclude = ['위도', '경도', 'lat', 'lon', 'latitude', 'longitude']
    display_columns = [col for col in df_display.columns if col not in cols_to_exclude]
    
    st.dataframe(df_display[display_columns], use_container_width=True)
