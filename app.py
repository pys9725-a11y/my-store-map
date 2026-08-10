import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# 웹페이지 설정
st.set_page_config(page_title="전국 대리점 위치 지도", layout="wide")

st.title("📍 전국 대리점 위치 현황 대시보드")
st.write("구글 시트 데이터와 실시간 연동된 지도 서비스입니다.")

# 1. 구글 시트 연동 설정 (본인의 구글 시트 ID를 넣으세요)
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 데이터 불러오기 함수 (5분마다 자동 갱신)
@st.cache_data(ttl=300)
def load_data():
    df = pd.read_csv(CSV_URL)
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    df = df.dropna(subset=['위도', '경도'])
    return df

try:
    df = load_data()

    # 사이드바 검색 및 필터 기능
    st.sidebar.header("🔍 대리점 필터")
    
    # 지역 선택 필터
    region_list = ["전체"] + sorted(list(df['지역'].dropna().unique()))
    selected_region = st.sidebar.selectbox("지역 선택", region_list)

    # 대리점명 검색 필터
    search_keyword = st.sidebar.text_input("대리점명 검색")

    # 데이터 필터링
    filtered_df = df.copy()
    if selected_region != "전체":
        filtered_df = filtered_df[filtered_df['지역'] == selected_region]
    if search_keyword:
        filtered_df = filtered_df[filtered_df['대리점명'].str.contains(search_keyword, na=False)]

    st.sidebar.metric("조회된 대리점 수", f"{len(filtered_df)} 개")

    # 지도 중심점 설정 (기본값: 대한민국 중심)
    if not filtered_df.empty:
        center_lat = filtered_df['위도'].mean()
        center_lng = filtered_df['경도'].mean()
        zoom_level = 7 if selected_region == "전체" else 10
    else:
        center_lat, center_lng, zoom_level = 36.5, 127.5, 7

    # 지도 생성 (Folium)
    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level)

    # 핀 마커 추가
    for _, row in filtered_df.iterrows():
        popup_html = f"<b>{row['대리점명']}</b><br>{row['주소']}"
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=row['대리점명'],
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

    # Streamlit 화면에 지도 출력
    st_folium(m, width="100%", height=600)

except Exception as e:
    st.error(f"구글 시트 데이터를 불러오는데 실패했습니다: {e}")
