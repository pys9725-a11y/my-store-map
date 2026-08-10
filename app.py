import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from urllib.parse import quote

st.set_page_config(page_title="전국 대리점 지도 현황", layout="wide")
st.title("📍 전국 대리점 위치 현황 대시보드")

# ⚠️ 아래 따옴표 안에 복사한 본인의 구글 시트 ID를 정확히 붙여넣으세요.
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"

# URL에 한글/특수문자가 섞여도 에러가 나지 않도록 인코딩 처리
clean_sheet_id = quote(SHEET_ID.strip())
CSV_URL = f"https://docs.google.com/spreadsheets/d/{clean_sheet_id}/export?format=csv"

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_URL)
    
    # 열 이름 공백 제거 및 한글 통일
    df.columns = [str(col).strip() for col in df.columns]
    rename_dict = {
        'latitude': '위도', 'lat': '위도', 'Lat': '위도', 'Latitude': '위도',
        'longitude': '경도', 'lng': '경도', 'Lng': '경도', 'Longitude': '경도',
        'name': '대리점명', 'store': '대리점명', 'Store': '대리점명',
        'address': '주소', 'Address': '주소'
    }
    df = df.rename(columns=rename_dict)
    
    if '위도' not in df.columns or '경도' not in df.columns:
        raise KeyError(f"구글 시트에 '위도' 또는 '경도' 열이 없습니다. 현재 읽어온 열 목록: {list(df.columns)}")
        
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    df = df.dropna(subset=['위도', '경도'])
    return df

try:
    df = load_data()

    st.sidebar.header("🔍 대리점 검색 및 필터")
    
    # 지역 필터
    if '지역' in df.columns:
        region_list = ["전체"] + sorted(list(df['지역'].dropna().unique()))
        selected_region = st.sidebar.selectbox("지역 선택", region_list)
    else:
        selected_region = "전체"

    # 대리점명 검색 필터
    search_keyword = st.sidebar.text_input("대리점명 검색")

    filtered_df = df.copy()
    if selected_region != "전체" and '지역' in df.columns:
        filtered_df = filtered_df[filtered_df['지역'] == selected_region]
    if search_keyword and '대리점명' in df.columns:
        filtered_df = filtered_df[filtered_df['대리점명'].astype(str).str.contains(search_keyword, na=False)]

    st.sidebar.metric("조회된 대리점 수", f"{len(filtered_df)} 개")

    # 지도 좌표 및 생성
    if not filtered_df.empty:
        center_lat = filtered_df['위도'].mean()
        center_lng = filtered_df['경도'].mean()
        zoom_level = 7 if selected_region == "전체" else 10
    else:
        center_lat, center_lng, zoom_level = 36.5, 127.5, 7

    m = folium.Map(location=[center_lat, center_lng], zoom_start=zoom_level)

    for _, row in filtered_df.iterrows():
        store_name = row.get('대리점명', '대리점')
        store_addr = row.get('주소', '')
        
        popup_html = f"<b>{store_name}</b><br>{store_addr}"
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=store_name,
            icon=folium.Icon(color='blue', icon='info-sign')
        ).add_to(m)

    st_folium(m, width="100%", height=650)

except Exception as e:
    st.error(f"구글 시트 연동 오류: {e}")
