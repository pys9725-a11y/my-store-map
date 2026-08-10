import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from urllib.parse import quote
import requests

# 웹페이지 설정
st.set_page_config(page_title="전국 대리점 위치 현황", layout="wide")
st.title("📍 전국 대리점 위치 현황")

# 1. 구글 시트 ID 적용
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
clean_sheet_id = quote(SHEET_ID.strip())
CSV_URL = f"https://docs.google.com/spreadsheets/d/{clean_sheet_id}/export?format=csv"

# 2. 대한민국 시·도 경계 GeoJSON 데이터 URL
GEOJSON_URL = "https://raw.githubusercontent.com/southkorea/southkorea-maps/master/kostat/2013/json/skorea_provinces_2013_geo.json"

# 🎨 시·도별 색상 지정 (첨부해주신 이미지 톤 반영)
COLOR_MAP = {
    '서울특별시': '#7CB342', '인천광역시': '#7CB342', '경기도': '#7CB342',           # 수도권 (연두)
    '강원도': '#3A7CA5', '강원특별자치도': '#3A7CA5',                                # 강원 (청회색)
    '충청북도': '#E06D53', '충청남도': '#E06D53', '대전광역시': '#E06D53', '세종특별자치시': '#E06D53', # 충청 (다홍)
    '전라북도': '#F4A261', '전북특별자치도': '#F4A261',                              # 전북 (주황)
    '전라남도': '#FF70A6', '광주광역시': '#FF70A6',                                # 전남/광주 (분홍)
    '경상북도': '#48CAE4', '대구광역시': '#48CAE4',                                # 경북/대구 (하늘)
    '경상남도': '#52B788', '부산광역시': '#52B788', '울산광역시': '#52B788',           # 경남/부산/울산 (민트)
    '제주특별자치도': '#EAB308'                                                    # 제주 (노랑)
}

# 지역 매칭 보조 함수 (구글 시트 '지역' 텍스트 기반)
def get_color_by_region(region_name):
    region_str = str(region_name).strip()
    for key, color in COLOR_MAP.items():
        if key in region_str or region_str in key:
            return color
    if '서울' in region_str or '경기' in region_str or '인천' in region_str: return '#7CB342'
    if '강원' in region_str: return '#3A7CA5'
    if '충청' in region_str or '충북' in region_str or '충남' in region_str or '대전' in region_str or '세종' in region_str: return '#E06D53'
    if '전북' in region_str or '전라북도' in region_str: return '#F4A261'
    if '전남' in region_str or '전라남도' in region_str or '광주' in region_str: return '#FF70A6'
    if '경북' in region_str or '경상북도' in region_str or '대구' in region_str: return '#48CAE4'
    if '경남' in region_str or '경상남도' in region_str or '부산' in region_str or '울산' in region_str: return '#52B788'
    if '제주' in region_str: return '#EAB308'
    return '#6B7280'

# 물방울 핀 SVG 아이콘 생성 함수
def create_custom_pin(color_hex):
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 140" width="26" height="36">
        <path d="M50 0 C22.4 0 0 22.4 0 50 C0 85 50 140 50 140 C50 140 100 85 100 50 C100 22.4 77.6 0 50 0 Z" fill="{color_hex}" stroke="#FFFFFF" stroke-width="4"/>
        <circle cx="50" cy="48" r="20" fill="#FFFFFF"/>
    </svg>
    """
    return folium.DivIcon(
        html=f'<div style="transform: translate(-50%, -100%);">{svg}</div>',
        icon_size=(26, 36),
        icon_anchor=(13, 36)
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
def load_geojson():
    try:
        res = requests.get(GEOJSON_URL)
        return res.json()
    except:
        return None

try:
    df = load_data()
    geojson_data = load_geojson()

    # 사이드바 필터
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

    # 지도 기본 중앙 좌표 (대한민국 전체)
    center_lat, center_lng, zoom_level = 35.8, 127.8, 7
    if selected_region != "전체" and not filtered_df.empty:
        center_lat = filtered_df['위도'].mean()
        center_lng = filtered_df['경도'].mean()
        zoom_level = 9

    # 단색 회색조 지도 타일 생성
    m = folium.Map(
        location=[center_lat, center_lng], 
        zoom_start=zoom_level,
        tiles="CartoDB positron"
    )

    # 🗺️ 1. 시·도 면 영역 색상 칠하기 (GeoJSON Overlay)
    if geojson_data:
        folium.GeoJson(
            geojson_data,
            name="시도 경계",
            style_function=lambda feature: {
                'fillColor': COLOR_MAP.get(feature['properties'].get('name', ''), '#CBD5E1'),
                'color': '#FFFFFF',
                'weight': 1.2,
                'fillOpacity': 0.35
            }
        ).add_to(m)

    # 📌 2. 대리점 위치 핀 (지역별 맞춤 색상 마커)
    for _, row in filtered_df.iterrows():
        store_name = row.get('대리점명', '대리점')
        store_addr = row.get('주소', '')
        store_region = row.get('지역', '')
        
        region_color = get_color_by_region(store_region)
        pin_icon = create_custom_pin(region_color)
        
        popup_html = f"""
        <div style="font-family: sans-serif; padding: 4px; width: 170px;">
            <div style="font-size: 13px; font-weight: bold; color: #111; margin-bottom: 3px;">{store_name}</div>
            <div style="font-size: 11px; color: #555; line-height: 1.3;">{store_addr}</div>
            <div style="font-size: 10px; color: {region_color}; font-weight: bold; margin-top: 4px;">[{store_region}]</div>
        </div>
        """
        
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=240),
            tooltip=f"{store_name} ({store_region})",
            icon=pin_icon
        ).add_to(m)

    # 지도 화면 출력
    st_folium(m, width="100%", height=700)

except Exception as e:
    st.error(f"구글 시트 연동 오류: {e}")
