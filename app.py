import math

import streamlit as st
import pandas as pd
import pydeck as pdk


st.markdown(
    """
    <style>
        /* 1. 우측 상단 툴바, 헤더, 푸터 및 Manage App 버튼 숨기기 */
        header[data-testid="stHeader"] {
            visibility: hidden;
            height: 0rem;
        }
        footer {
            visibility: hidden;
        }
        [data-testid="manage-app-button"],
        .stAppViewerBadge,
        div[class*="viewerBadge"] {
            display: none !important;
        }

</style>
""",
    unsafe_allow_html=True,
)


st.set_page_config(page_title="전국 대리점 위치 현황", layout="wide")
st.title("📍 전국 대리점 위치 현황")

SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 한국 좌표 범위 (대략적인 육지 + 도서 지역 포함)
LAT_RANGE = (33, 39)
LON_RANGE = (124, 132)


@st.cache_data(ttl=600)  # 10분마다 구글 시트에서 최신 데이터를 다시 불러옴
def load_data():
    try:
        return pd.read_csv(SHEET_URL)
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None


def parse_coord(series: pd.Series) -> pd.Series:
    """구글 시트에서 온 좌표 문자열을 숫자로 안전하게 변환.
    - 앞뒤 공백/보이지 않는 공백 문자 제거
    - 천단위 구분자로 잘못 들어간 쉼표 제거
    - 숫자, 부호(-), 소수점(.) 이외의 문자(°, N, E 등) 제거
    """
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(" ", "", regex=False)  # non-breaking space
        .str.replace(",", "", regex=False)
        .str.replace(r"[^0-9.\-]", "", regex=True)
    )
    return pd.to_numeric(cleaned, errors="coerce")


df_raw = load_data()

if df_raw is not None:
    # 컬럼명의 앞뒤 공백 제거
    df_raw.columns = df_raw.columns.str.strip()

    if "위도" not in df_raw.columns or "경도" not in df_raw.columns:
        st.error("시트에 '위도' 또는 '경도' 컬럼이 없습니다. 컬럼명을 확인해주세요.")
        st.stop()

    df = df_raw.copy()
    df["lat"] = parse_coord(df["위도"])
    df["lon"] = parse_coord(df["경도"])

    # 위도/경도 칸이 뒤바뀌어 입력된 행 자동 보정
    # (위도 칸 값이 경도 범위에, 경도 칸 값이 위도 범위에 들어가는 경우)
    swapped = df["lat"].between(*LON_RANGE) & df["lon"].between(*LAT_RANGE)
    if swapped.any():
        df.loc[swapped, ["lat", "lon"]] = df.loc[swapped, ["lon", "lat"]].values

    # Valid한 좌표만 남기기 (한국 좌표 범위: 위도 33~39, 경도 124~132)
    in_range = df["lat"].between(*LAT_RANGE) & df["lon"].between(*LON_RANGE)
    df_valid = df[in_range].copy()
    df_invalid = df[~in_range].copy()

    # 라이트 배경 지도에서 잘 보이는 선명한 부서별 색상 팔레트
    # (아래 지사 선택 UI의 색상 사각형 이모지와 순서를 맞춰서 지도 점 색상과 일치시킴)
    color_palette = [
        [229, 57, 53, 220],   # 🟥 Red
        [244, 140, 6, 220],   # 🟧 Orange
        [234, 179, 8, 220],   # 🟨 Yellow
        [22, 163, 74, 220],   # 🟩 Green
        [37, 99, 235, 220],   # 🟦 Blue
        [147, 51, 234, 220],  # 🟪 Purple
        [120, 72, 43, 220],   # 🟫 Brown
        [55, 65, 81, 220],    # ⬛ Black/Gray
    ]
    emoji_palette = ["🟥", "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛"]

    if "부서" in df_valid.columns:
        unique_depts = df_valid["부서"].dropna().unique()
        dept_color_map = {dept: color_palette[i % len(color_palette)] for i, dept in enumerate(unique_depts)}
        dept_emoji_map = {dept: emoji_palette[i % len(emoji_palette)] for i, dept in enumerate(unique_depts)}
        df_valid["color"] = df_valid["부서"].map(lambda d: dept_color_map.get(d, [100, 100, 100, 220]))
    else:
        unique_depts = []
        dept_color_map = {}
        dept_emoji_map = {}
        df_valid["color"] = [[100, 100, 100, 220]] * len(df_valid)

    # 0. 전체 지사 목록 (다중 선택 가능한 필터 — 새로고침 없이 즉시 지도에 반영됨)
    if len(unique_depts) > 0:
        dept_option_labels = [f"{dept_emoji_map[d]} {d}" for d in unique_depts]
        label_to_dept = dict(zip(dept_option_labels, unique_depts))

        selected_labels = st.multiselect(
            "🏢 전체 지사 목록 (지사를 선택하면 해당 지사만 지도에 표시됩니다 · 여러 개 선택 가능, 비워두면 전체 표시)",
            options=dept_option_labels,
            default=[],
        )
        selected_depts = [label_to_dept[label] for label in selected_labels]
    else:
        selected_depts = []

    if selected_depts and "부서" in df_valid.columns:
        df_dept_base = df_valid[df_valid["부서"].isin(selected_depts)]
        st.caption(f"📍 선택된 지사({', '.join(selected_depts)})만 표시 중 — 총 {len(df_dept_base)}건")
    else:
        df_dept_base = df_valid

    # 1. 검색 기능
    search_query = st.text_input("🔍 검색어 입력 (대리점명, 센터, 부서, 주소, 대표자명 등)", "")

    if search_query.strip():
        # 전체 열 데이터 중 검색어가 포함된 행 필터링
        mask = df_dept_base.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        df_display = df_dept_base[mask]
        st.info(f"'{search_query}' 검색 결과: 총 {len(df_display)}건")
    else:
        df_display = df_dept_base

    # 좌표 범위를 벗어나 지도에서 제외된 데이터가 있으면 알려주고, 원인 확인용으로 표시
    if not df_invalid.empty:
        with st.expander(f"⚠️ 좌표 범위를 벗어나 지도에 표시되지 않은 데이터 {len(df_invalid)}건 확인"):
            st.caption("위도는 33~39, 경도는 124~132 범위를 벗어나거나 숫자로 변환할 수 없는 값입니다. 원본 시트 값을 확인해주세요.")
            invalid_preview_cols = [c for c in df_invalid.columns if c not in ["lat", "lon", "color"]]
            st.dataframe(df_invalid[invalid_preview_cols], use_container_width=True)

    # 2. 지도 출력 영역
    st.subheader("🗺️ 대리점 위치 지도")

    if not df_display.empty:
        # 지도 중심점 자동 계산
        mid_lat = df_display["lat"].mean()
        mid_lon = df_display["lon"].mean()

        # 데이터가 퍼져있는 범위(bounding box)에 맞춰 줌 레벨을 자동 계산
        # (고정 zoom=8만 쓰면 데이터가 한 곳에 몰려있을 때 불필요하게 축소되어 보임)
        def compute_zoom(lat_series, lon_series):
            if len(lat_series) <= 1:
                return 12.0
            span = max(lat_series.max() - lat_series.min(), lon_series.max() - lon_series.min())
            if span <= 0:
                return 12.0
            # span(위경도 폭)이 좁을수록 확대, 넓을수록 축소되도록 로그 스케일로 계산
            zoom = math.log2(360 / span) - 1
            return max(4.0, min(zoom, 14.0))

        view_state = pdk.ViewState(
            # numpy 타입이 그대로 JSON 직렬화될 때 값이 깨지는 것을 방지하기 위해 float()로 명시 변환
            latitude=float(mid_lat) if not pd.isna(mid_lat) else 37.5,
            longitude=float(mid_lon) if not pd.isna(mid_lon) else 127.0,
            zoom=compute_zoom(df_display["lat"], df_display["lon"]),
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

        # 팝업 툴팁 (대표자명 옆 전화번호 반영)
        tooltip = {
            "html": "<div style='font-family: sans-serif; line-height: 1.5;'>"
                    "<b style='font-size: 14px; color: #1E293B;'>{대리점명}</b><hr style='margin: 4px 0; border: 0.5px solid #E2E8F0;'/>"
                    "<b>부서:</b> {부서}<br/>"
                    "<b>주소:</b> {주소}<br/>"
                    "<b>대표자:</b> {대표자명} ({전화번호})"
                    "</div>",
            "style": {
                "backgroundColor": "#FFFFFF",
                "color": "#334155",
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
            ),
            height=600,
            use_container_width=True,
        )
    else:
        st.warning("표시할 수 있는 위치 데이터가 없거나, 구글 시트의 위도/경도 값이 올바르지 않습니다.")

    # 3. 데이터 표 출력 (위도, 경도 및 내부 생성 컬럼 모두 제외)
    st.subheader("📋 대리점 목록")

    cols_to_exclude = ["위도", "경도", "lat", "lon", "latitude", "longitude", "color"]
    display_columns = [col for col in df_display.columns if col not in cols_to_exclude]

    st.dataframe(df_display[display_columns], use_container_width=True)
