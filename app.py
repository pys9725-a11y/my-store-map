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

    # 라이트 배경 지도에서 잘 보이는 선명한 부서별 색상 팔레트
    color_palette = [
        [220, 38, 38, 220],   # Red
        [37, 99, 235, 220],   # Blue
        [22, 163, 74, 220],   # Green
        [217, 119, 6, 220],   # Orange
        [147, 51, 234, 220],  # Purple
        [219, 39, 119, 220],  # Pink
        [13, 148, 136, 220],  # Teal
        [75, 85, 99, 220]     # Gray
    ]
    unique_depts = df_valid['부서'].dropna().unique() if '부서' in df_valid.columns else []
    dept_color_map = {dept: color_palette[i % len(color_palette)] for i, dept in enumerate(unique_depts)}
    df_valid['color'] = df_valid['부서'].map(lambda d: dept_color_map.get(d, [100, 100, 100, 220]))

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
        # 부서별 색상 범례 표시
        if len(unique_depts) > 0:
            st.markdown("**🎨 부서별 색상 범례**")
            legend_cols = st.columns(min(len(unique_depts), 6))
            for i, dept in enumerate(unique_depts):
                rgb = dept_color_map[dept]
                color_hex = f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
                with legend_cols[i % 6]:
                    st.markdown(f"<span style='color:{color_hex}; font-weight:bold;'>■</span> {dept}", unsafe_allow_html=True)

        # 지도 중심점 자동 계산
        mid_lat = df_display['lat'].mean()
        mid_lon = df_display['lon'].mean()

        view_state = pdk.ViewState(
            latitude=mid_lat if not pd.isna(mid_lat) else 37.5,
            longitude=mid_lon if not pd.isna(mid_lon) else 127.0,
            zoom=8,
            pitch=0,
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df_display,
            get_position=["lon", "lat"],
            get_color="color",
            get_radius=180,
            radius_scale=6,
            radius_min_pixels=7,
            radius_max_pixels=16,
            pickable=True,        # 클릭/마우스 오버 허용
            auto_highlight=True,  # 마우스 오버 시 강조
        )

        # 라이트 모드에 맞춘 깔끔한 카드형 팝업 툴팁
        tooltip = {
            "html": "<div style='font-family: sans-serif; line-height: 1.5;'>"
                    "<b style='font-size: 14px; color: #1E293B;'>{대리점명}</b><hr style='margin: 4px 0; border: 0.5px solid #E2E8F0;'/>"
                    "<b>부서:</b> {부서}<br/>"
                    "<b>주소:</b> {주소}<br/>"
                    "<b>대표자:</b> {대표자명}"
                    "</div>",
            "style": {
                "backgroundColor": "#FFFFFF",
                "color": #334155,
                "fontSize": "12px",
                "padding": "10px 14px",
                "borderRadius": "8px",
                "boxShadow": "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
                "border": "1px solid #E2E8F0"
            }
        }

        # CartoDB Positron 오픈소스 라이트 지도 타일 적용
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                tooltip=tooltip
            )
        )
    else:
        st.warning("표시할 수 있는 위치 데이터가 없거나, 구글 시트의 위도/경도 값이 올바르지 않습니다.")

    # 3. 데이터 표 출력 (위도, 경도 및 내부 생성 컬럼 모두 제외)
    st.subheader("📋 대리점 목록")
    
    cols_to_exclude = ['위도', '경도', 'lat', 'lon', 'latitude', 'longitude', 'color']
    display_columns = [col for col in df_display.columns if col not in cols_to_exclude]
    
    st.dataframe(df_display[display_columns], use_container_width=True)
