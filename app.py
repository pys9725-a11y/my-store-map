import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from urllib.parse import quote

# 웹페이지 설정
st.set_page_config(page_title="전국 대리점 위치 현황", layout="wide")

st.title("📍 전국 대리점 위치 현황")

# 구글 시트 ID 적용
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
clean_sheet_id = quote(SHEET_ID.strip())
CSV_URL = f"https://docs.google.com/spreadsheets/d/{clean_sheet_id}/export?format=csv"

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_URL)
    
    # 열 이름 공백 제거
    df.columns = [str(col).strip() for col in df.columns]
    
    # 열 이름 한글 표준화
    rename_dict = {
        'latitude': '위도', 'lat': '위도', 'Lat': '위도', 'Latitude': '위도',
        'longitude': '경도', 'lng': '경도', 'Lng': '경도', 'Longitude': '경도',
        'name': '대리점명', 'store': '대리점명', 'Store': '대리점명',
        'address': '주소', 'Address': '주소'
    }
    df = df.rename(columns=rename_dict)
    
    if '위도' not in df.columns or '경도' not in df.columns:
        raise KeyError(f"구글 시트에 '위도' 또는 '경도' 열이 없습니다. 현재 열 목록: {list(df.columns)}")
        
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    df = df.dropna(subset=['위도', '경도'])
    return df

try:
    df = load_data()

    # 사이드바 검색 기능
    st.sidebar.header("🔍 검색 및 필터")
    
    if '지역' in df.columns:
        region_list = ["전체"] + sorted(list(df['지역'].dropna().unique()))
        selected_region = st.sidebar.selectbox("지역 선택", region_list)
    else:
        selected_region = "전체"

    search_keyword = st.sidebar.text_input("대리점명 검색")

    filtered_df = df.copy()
    if selected_region != "전체" and '지역' in df.columns:
        filtered_df = filtered_df[filtered_df['지역'] == selected_region]
    if search_keyword and '대리점명' in df.columns:
        filtered_df = filtered_df[filtered_df['대리점명'].astype(str).str.contains(search_keyword, na=False)]

    st.sidebar.metric("대리점 수", f"{len(filtered_df)} 개")

    # 지도 위치 설정
    if not filtered_df.empty:
        center_lat = filtered_df['위도'].mean()
        center_lng = filtered_df['경도'].mean()
        zoom_level = 7 if selected_region == "전체" else 10
    else:
        center_lat, center_lng, zoom_level = 36.5, 127.5, 7

    # 🎨 지도 디자인: 단색/회색조의 차분한 백그라운드 타일 (CartoDB positron)
    m = folium.Map(
        location=[center_lat, center_lng], 
        zoom_start=zoom_level,
        tiles="CartoDB positron"
    )

    # 📌 핀 디자인: 심플한 검은색 슬림 마커
    for _, row in filtered_df.iterrows():
        store_name = row.get('대리점명', '대리점')
        store_addr = row.get('주소', '')
        
        popup_html = f"""
        <div style="font-family: sans-serif; padding: 5px;">
            <div style="font-size: 14px; font-weight: bold; margin-bottom: 4px;">{store_name}</div>
            <div style="font-size: 12px; color: #555;">{store_addr}</div>
        </div>
        """
        
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=store_name,
            icon=folium.Icon(color='black', icon='map-pin', prefix='fa')
        ).add_to(m)

    # 지도 출력
    st_folium(m, width="100%", height=680)

except Exception as e:
    st.error(f"구글 시트 연동 오류: {e}")
