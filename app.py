import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from urllib.parse import quote
import requests

# 웹페이지 설정
st.set_page_config(page_title="전국 대리점 위치 현황", layout="wide")

st.title("📍 전국 대리점 위치 현황")

# 구글 시트 ID 적용
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
clean_sheet_id = quote(SHEET_ID.strip())
CSV_URL = f"https://docs.google.com/spreadsheets/d/{clean_sheet_id}/export?format=csv"

# 대한민국 행정구역 GeoJSON URL (시·도 및 시·군·구)
GEO_PROVINCES_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_provinces_2013_geo.json"
GEO_MUNICIPALITIES_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_municipalities_2013_geo.json"

# 🎨 지역별 핀 색상 매핑 함수
def get_region_color(region):
    region_str = str(region).strip()
    if any(k in region_str for k in ['서울', '수도권', '경기', '인천']):
        return '#2563EB'  # 파란색 (수도권)
    elif '강원' in region_str:
        return '#1E40AF'  # 남색 (강원)
    elif any(k in region_str for k in ['충청', '충북', '충남', '대전', '세종']):
        return '#65A30D'  # 연두색 (충청)
    elif any(k in region_str for k in ['전라', '전북', '전남', '광주']):
        return '#EA580C'  # 주황색 (전라)
    elif any(k in region_str for k in ['경상', '경북', '경남', '대구', '부산', '울산']):
        return '#0284C7'  # 하늘색 (경상)
    elif '제주' in region_str:
        return '#CA8A04'  # 노란색 (제주)
    else:
        return '#6B7280'  # 회색 (기타)

# 📌 50% 축소된 미니 물방울 핀 SVG 생성 함수
def create_mini_pin_icon(color_hex):
    svg_code = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 140" width="15" height="21">
        <path d="M50 0 C22.4 0 0 22.4 0 50 C0 85 50 140 50 140 C50 140 100 85 100 50 C100 22.4 77.6 0 50 0 Z" fill="{color_hex}" stroke="#FFFFFF" stroke-width="4"/>
        <circle cx="50" cy="48" r="20" fill="#FFFFFF"/>
    </svg>
    """
    return folium.DivIcon(
        html=f'<div style="transform: translate(-50%, -100%);">{svg_code}</div>',
        icon_size=(15, 21),
        icon_anchor=(7.5, 21)
    )

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv(CSV_URL)
    df.columns = [str(col).strip() for col in df.columns]
    
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

@st.cache_data
def load_geojson(url):
    try:
        res = requests.get(url)
        return res.json()
    except Exception:
        return None

try:
    df = load_data()
    geo_provinces = load_geojson(GEO_PROVINCES_URL)
    geo_municipalities = load_geojson(GEO_MUNICIPALITIES_URL)

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

    # 🎨 차분한 회색조 단색 타일
    m = folium.Map(
        location=[center_lat, center_lng], 
        zoom_start=zoom_level,
        tiles="CartoDB positron"
    )

    # 🗺️ 1. 시·군·구 세부 경계선 (얇은 선)
    if geo_municipalities:
        folium.GeoJson(
            geo_municipalities,
            name="시군구 경계",
            style_function=lambda x: {
                'fillColor': '#FFFFFF',
                'color': '#888888',
                'weight': 0.8,
                'fillOpacity': 0.6
            }
        ).add_to(m)

    # 🗺️ 2. 시·도 외곽 주요 경계선 (굵은 선)
    if geo_provinces:
        folium.GeoJson(
            geo_provinces,
            name="시도 경계",
            style_function=lambda x: {
                'fillColor': 'none',
                'color': '#111111',
                'weight': 2.0,
                'fillOpacity': 0
            }
        ).add_to(m)

    # 📌 핀 디자인: 50% 축소된 지역별 컬러 핀
    for _, row in filtered_df.iterrows():
        store_name = row.get('대리점명', '대리점')
        store_addr = row.get('주소', '')
        store_region = row.get('지역', '')
        
        region_color = get_region_color(store_region)
        pin_icon = create_mini_pin_icon(region_color)
        
        popup_html = f"""
        <div style="font-family: sans-serif; padding: 5px; width: 180px;">
            <div style="font-size: 13px; font-weight: bold; margin-bottom: 4px;">{store_name}</div>
            <div style="font-size: 11px; color: #555;">{store_addr}</div>
            <div style="font-size: 10px; color: {region_color}; font-weight: bold; margin-top: 4px;">[{store_region}]</div>
        </div>
        """
        
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{store_name} ({store_region})" if store_region else store_name,
            icon=pin_icon
        ).add_to(m)

    # 지도 출력
    st_folium(m, width="100%", height=680)

except Exception as e:
    st.error(f"구글 시트 연동 오류: {e}")
