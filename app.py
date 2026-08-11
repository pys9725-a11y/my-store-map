import streamlit as st
import pandas as pd
import pydeck as pdk

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

    # 1. 부서(B열) 기준 색상 팔레트 매핑
    color_palette = [
        [255, 75, 75, 220],   # Red
        [31, 119, 180, 220],  # Blue
        [44, 160, 44, 220],   # Green
        [255, 127, 14, 220],  # Orange
        [148, 103, 189, 220], # Purple
        [140, 86, 75, 220],   # Brown
        [227, 119, 194, 220], # Pink
        [127, 127, 127, 220], # Gray
    ]
    unique_depts = df_valid['부서'].dropna().unique()
    dept_color_map = {dept: color_palette[i % len(color_palette)] for i, dept in enumerate(unique_depts)}
    df_valid['color'] = df_valid['부서'].map(lambda d: dept_color_map.get(d, [100, 100, 100, 220]))

    # 2. 검색 기능
    search_query = st.text_input("🔍 검색어 입력 (대리점명, 센터, 부서, 주소, 대표자명 등)", "")

    if search_query.strip():
        mask = df_valid.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        df_display = df_valid[mask]
        st.info(f"'{search_query}' 검색 결과: 총 {len(df_display)}건")
    else:
        df_display = df_valid

    # 3. 지도 출력 영역
    st.subheader("🗺️ 대리점 위치 지도")

    if not df_display.empty:
        # 부서별 색상 범례 표시
        st.markdown("**🎨 부서별 색상 범례**")
        legend_cols = st.columns(min(len(unique_depts), 6))
        for i, dept in enumerate(unique_depts):
            rgb = dept_color_map[dept]
            color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
            col_idx = i % 6
            with legend_cols[col_idx]:
                st.markdown(f"<span style='color:{color_hex}; font-weight:bold;'>■</span> {dept}", unsafe_allow_html=True)

        # 지도 중심점 계산
        mid_lat = df_display['lat'].mean()
        mid_lon = df_display['lon'].mean()

        # 초기 줌 레벨 설정 및 축소 제한(min_zoom)
        initial_zoom = 8.5
        view_state = pdk.ViewState(
            latitude=mid_lat if not pd.isna(mid_lat) else 37.5,
            longitude=mid_lon if not pd.isna(mid_lon) else 127.0,
            zoom=initial_zoom,
            min_zoom=initial_zoom,  # 초기 화면보다 더 축소(Zoom-out)되지 않도록 제한
            max_zoom=16,            # 확대(Zoom-in)는 가능
            pitch=0,
        )

        # PyDeck 마커 레이어
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_display,
            get_position=["lon", "lat"],
            get_color="color",
            get_radius=150,
            radius_scale=10,
            radius_min_pixels=6,
            radius_max_pixels=16,
            pickable=True,        # 클릭/호버 이벤트 허용
            auto_highlight=True,  # 마우스 오버 강조 효과
        )

        # 점 클릭/마우스 오버 팝업 툴팁 정보창
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

        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip=tooltip,
                map_style="mapbox://styles/mapbox/light-v10"
            )
        )
    else:
        st.warning("표시할 수 있는 위치 데이터가 없거나, 구글 시트의 위도/경도 값이 올바르지 않습니다.")

    # 4. 데이터 표 출력 (위도, 경도 관련 열 모두 제외)
    st.subheader("📋 대리점 목록")
    cols_to_exclude = ['위도', '경도', 'lat', 'lon', 'latitude', 'longitude', 'color']
    display_columns = [col for col in df_display.columns if col not in cols_to_exclude]

    st.dataframe(df_display[display_columns], use_container_width=True)
