import streamlit as st
import pandas as pd
import pydeck as pdk

# 1. 페이지 설정
st.set_page_config(page_title="대리점 위치 지도 시각화", layout="wide")
st.title("📍 대리점 위치 지도 시각화")

# 2. 구글 시트 URL 설정
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
    # 컬럼명 공백 제거
    df_raw.columns = df_raw.columns.str.strip()

    # '위도'와 '경도'열 실수(Float) 변환
    df = df_raw.copy()
    df['lat'] = pd.to_numeric(df['위도'].astype(str).str.replace(',', ''), errors='coerce')
    df['lon'] = pd.to_numeric(df['경도'].astype(str).str.replace(',', ''), errors='coerce')

    # 유효한 대한민국 좌표 데이터만 추출
    df_valid = df[(df['lat'].between(33, 39)) & (df['lon'].between(124, 132))].copy()

    # 3. '부서' 기준 색상 팔레트 자동 생성 (RGB)
    color_palette = [
        [255, 75, 75, 200],   # Red
        [31, 119, 180, 200],  # Blue
        [44, 160, 44, 200],   # Green
        [255, 127, 14, 200],  # Orange
        [148, 103, 189, 200], # Purple
        [140, 86, 75, 200],   # Brown
        [227, 119, 194, 200], # Pink
        [127, 127, 127, 200], # Gray
    ]

    unique_depts = df_valid['부서'].dropna().unique()
    dept_color_map = {dept: color_palette[i % len(color_palette)] for i, dept in enumerate(unique_depts)}
    
    # 각 행에 부서별 색상 부여
    df_valid['color'] = df_valid['부서'].map(lambda d: dept_color_map.get(d, [100, 100, 100, 200]))

    # 4. 검색 기능
    search_query = st.text_input("🔍 검색어 입력 (대리점명, 센터, 부서, 주소, 대표자명 등)", "")

    if search_query.strip():
        mask = df_valid.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        df_display = df_valid[mask]
        st.info(f"'{search_query}' 검색 결과: 총 {len(df_display)}건")
    else:
        df_display = df_valid

    # 5. 지도 범례 (부서별 색상 안내)
    st.subheader("🗺️ 대리점 위치 지도")
    st.markdown("**🎨 부서별 색상 범례**")
    legend_cols = st.columns(min(len(unique_depts), 6))
    for i, dept in enumerate(unique_depts):
        rgb = dept_color_map[dept]
        color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
        col_idx = i % 6
        with legend_cols[col_idx]:
            st.markdown(f"<span style='color:{color_hex}; font-weight:bold;'>■</span> {dept}", unsafe_allow_html=True)

    # 6. 대한민국 전역으로 범위 고정 (ViewState 설정)
    view_state = pdk.ViewState(
        latitude=36.2,    # 대한민국 중심 위도
        longitude=127.8,  # 대한민국 중심 경도
        zoom=6.8,         # 한반도 전체가 시원하게 보이는 줌 레벨
        pitch=0,
    )

    # PyDeck 산점도 레이어 정의
    layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_display,
        get_position=["lon", "lat"],
        get_color="color",
        get_radius=4000,
        radius_min_pixels=7,
        radius_max_pixels=18,
        pickable=True,       # 정보 클릭/마우스 오버 허용
        auto_highlight=True, # 마우스 올렸을 때 강조 효과
    )

    # 마우스 오버/클릭 시 노출될 툴팁 정보창
    tooltip = {
        "html": "<b>대리점명:</b> {대리점명}<br/>"
                "<b>부서:</b> {부서} ({센터})<br/>"
                "<b>주소:</b> {주소}<br/>"
                "<b>대표자:</b> {대표자명} ({전화번호})",
        "style": {
            "backgroundColor": "#1E293B",
            "color": "white",
            "fontSize": "13px",
            "padding": "10px",
            "borderRadius": "6px"
        }
    }

    # 지도 출력
    st.pydeck_chart(
        pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style="mapbox://styles/mapbox/light-v10"
        )
    )

    # 7. 데이터 표 출력 (위도, 경도 및 내부용 데이터 제외)
    st.subheader("📋 대리점 목록")
    cols_to_exclude = ['위도', '경도', 'lat', 'lon', 'color']
    display_columns = [col for col in df_display.columns if col not in cols_to_exclude]
    
    st.dataframe(df_display[display_columns], use_container_width=True)
