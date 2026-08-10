import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from urllib.parse import quote

# 페이지 기본 설정 (한글)
st.set_page_config(page_title="전국 대리점 위치 현황 대시보드", layout="wide")

st.title("📍 전국 대리점 위치 현황 대시보드")
st.caption("구글 시트 연동 실시간 전국 대리점 지도 서비스")

# 구글 시트 ID 설정
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
clean_sheet_id = quote(SHEET_ID.strip())
CSV_URL = f"https://docs.google.com/spreadsheets/d/{clean_sheet_id}/export?format=csv"

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
        raise KeyError(f"구글 시트에 '위도' 또는 '경도' 열이 없습니다. 읽어온 열 목록: {list(df.columns)}")
        
    df['위도'] = pd.to_numeric(df['위도'], errors='coerce')
    df['경도'] = pd.to_numeric(df['경도'], errors='coerce')
    df = df.dropna(subset=['위도', '경도'])
    return df

# 지역별 핀 색상 매핑 함수 (제공해주신 지도 스타일 기준)
def get_region_color(region):
    region_str = str(region)
    if any(k in region_str for k in ['서울', '수도권', '경기', '인천']):
        return '#2563EB'  # 파란색
    elif '강원' in region_str:
        return '#1E40AF'  # 진한 남색
    elif any(k in region_str for k in ['충청', '충북', '충남', '대전', '세종']):
        return '#65A30D'  # 연두색
    elif any(k in region_str for k in ['전라', '전북', '전남', '광주']):
        return '#EA580C'  # 주황색 / 다홍색
    elif any(k in region_str for k in ['경상', '경북', '경남', '대구', '부산', '울산']):
        return '#0284C7'  # 밝은 하늘색
    elif '제주' in region_str:
        return '#CA8A04'  # 노란색
    else:
        return '#4B5563'  # 기타 회색

# 보내주신 물방울 핀 모양 SVG 생성 함수
def create_custom_pin_icon(color_hex):
    svg_code = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 140" width="30" height="42">
        <path d="M50 0 C22.4 0 0 22.4 0 50 C0 85 50 140 50 140 C50 140 100 85 100 50 C100 22.4 77.6 0 50 0 Z" fill="{color_hex}"/>
        <circle cx="50" cy="48" r="22" fill="#FFFFFF"/>
    </svg>
    """
    return folium.DivIcon(
        html=f'<div style="transform: translate(-50%, -100%);">{svg_code}</div>',
        icon_size=(30, 42),
        icon_anchor=(15, 42)
    )

try:
    df = load_data()

    # 사이드바 필터 (전체 한글화)
    st.sidebar.header("🔍 대리점 검색 및 필터")
    
    if '지역' in df.columns:
        region_list = ["전체 보기"] + sorted(list(df['지역'].dropna().unique()))
        selected_region = st.sidebar.selectbox("지역 선택", region_list)
    else:
        selected_region = "전체 보기"

    search_keyword = st.sidebar.text_input("대리점명 검색")

    filtered_df = df.copy()
    if selected_region != "전체 보기" and '지역' in df.columns:
        filtered_df = filtered_df[filtered_df['지역'] == selected_region]
    if search_keyword and '대리점명' in df.columns:
        filtered_df = filtered_df[filtered_df['대리점명'].astype(str).str.contains(search_keyword, na=False)]

    st.sidebar.markdown("---")
    st.sidebar.metric("조회된 대리점 수", f"{len(filtered_df)} 개")

    # 지도 중심 좌표 설정 (대한민국 중심)
    if selected_region == "전체 보기" or filtered_df.empty:
        center_lat, center_lng, zoom_level = 35.8, 127.8, 7
    else:
        center_lat = filtered_df['위도'].mean()
        center_lng = filtered_df['경도'].mean()
        zoom_level = 10

    # 대한민국 중심의 깔끔한 한글지도 생성
    m = folium.Map(
        location=[center_lat, center_lng],
        zoom_start=zoom_level,
        tiles="CartoDB positron",
        control_scale=True
    )

    # 핀 마커 등록 (지역별 색상 적용)
    for _, row in filtered_df.iterrows():
        store_name = row.get('대리점명', '대리점')
        store_addr = row.get('주소', '주소 정보 없음')
        store_region = row.get('지역', '기타')
        
        pin_color = get_region_color(store_region)
        pin_icon = create_custom_pin_icon(pin_color)
        
        popup_html = f"""
        <div style="font-family: 'Malgun Gothic', sans-serif; padding: 6px; width: 200px;">
            <div style="font-size: 15px; font-weight: bold; color: #111; margin-bottom: 4px;">{store_name}</div>
            <div style="font-size: 12px; color: #666; line-height: 1.4;">{store_addr}</div>
            <div style="font-size: 11px; color: {pin_color}; font-weight: bold; margin-top: 6px;">[ {store_region} ]</div>
        </div>
        """
        
        folium.Marker(
            location=[row['위도'], row['경도']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=f"{store_name} ({store_region})",
            icon=pin_icon
        ).add_to(m)

    # 화면 출력
    st_folium(m, width="100%", height=700)

except Exception as e:
    st.error(f"구글 시트 연동 중 오류가 발생했습니다: {e}")
