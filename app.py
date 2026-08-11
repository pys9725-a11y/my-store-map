import streamlit as st
import pandas as pd
import pydeck as pdk

# 1. 페이지 설정
st.set_page_config(page_title="대리점 위치 지도 시각화", layout="wide")
st.title("📍 대리점 위치 지도 시각화")

# 2. 구글 시트 URL 설정
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 3. 데이터 로드
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None

df_raw = load_data()

if df_raw is not None:
    # '위도', '경도' 필수 처리 및 숫자형 변환
    df = df_raw.dropna(subset=['위도', '경도']).copy()
    df['lat'] = pd.to_numeric(df['위도'], errors='coerce')
    df['lon'] = pd.to_numeric(df['경도'], errors='coerce')
    df = df.dropna(subset=['lat', 'lon'])

    # 4. 검색바 영역
    search_query = st.text_input("🔍 검색어를 입력하세요 (대리점명, 센터, 부서, 주소, 대표자명 등)", "")

    # 검색 결과 필터링 및 색상(RGB) 지정
    def match_search(row, query):
        if not query.strip():
            return False
        query_lower = query.lower()
        # 모든 열의 텍스트 중 검색어가 포함되는지 확인
        return any(query_lower in str(val).lower() for val in row.values)

    if search_query.strip():
        df['is_searched'] = df.apply(lambda row: match_search(row, search_query), axis=1)
    else:
        df['is_searched'] = False

    # 색상 부여: 검색 매칭 = 빨간색 [230, 50, 50], 미매칭 = 파란색 [30, 100, 230]
    df['color'] = df['is_searched'].apply(
        lambda matched: [230, 50, 50, 200] if matched else [30, 100, 230, 160]
    )
    # 검색된 마커 크기를 조금 더 크게 표현
    df['radius'] = df['is_searched'].apply(lambda matched: 120 if matched else 80)

    # 5. 지도 표시 (PyDeck)
    st.subheader("🗺️ 대리점 위치 지도")
    st.caption("🔴 빨간색: 검색 조건과 일치하는 위치 | 🔵 파란색: 전체 위치")

    # 지도의 중앙점 자동 계산
    mid_lat = df['lat'].mean()
    mid_lon = df['lon'].mean()

    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius="radius",
        pickable=True,
        auto_highlight=True,
    )

    view_state = pdk.ViewState(
        latitude=mid_lat if not pd.isna(mid_lat) else 37.5,
        longitude=mid_lon if not pd.isna(mid_lon) else 127.0,
        zoom=9,
        pitch=0,
    )

    # 마우스 오버 툴팁 설정
    tooltip = {
        "html": "<b>대리점명:</b> {대리점명}<br/>"
                "<b>센터/부서:</b> {센터} / {부서}<br/>"
                "<b>주소:</b> {주소}<br/>"
                "<b>대표자:</b> {대표자명} ({전화번호})",
        "style": {
            "backgroundColor": "black",
            "color": "white",
            "fontSize": "13px",
            "padding": "8px"
        }
    }

    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style="mapbox://styles/mapbox/light-v10"
        )
    )

    # 6. 표 데이터 표시 (위도, 경도 제외)
    st.subheader("📋 대리점 목록")
    
    # 지도를 위해 내부적으로 추가했던 컬럼들과 '위도', '경도' 제거
    columns_to_drop = ['위도', '경도', 'lat', 'lon', 'is_searched', 'color', 'radius']
    df_display = df.drop(columns=[col for col in columns_to_drop if col in df.columns])

    # 검색어가 있을 경우 검색 결과만 표에 강조 표시
    if search_query.strip():
        searched_count = df['is_searched'].sum()
        st.info(f"'{search_query}' 검색 결과: 총 {searched_count}건")
    
    st.dataframe(df_display, use_container_width=True)
