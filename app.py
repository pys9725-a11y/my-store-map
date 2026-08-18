import colorsys
import math
import re

import altair as alt
import streamlit as st
import pandas as pd
import pydeck as pdk
import streamlit_shadcn_ui as ui


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

# 컨설턴트 시트: 같은 문서의 다른 탭(워크시트). gid로 특정 탭을 지정해서 불러옴.
# 1행 = 컨설턴트명(컬럼 헤더), 2~30행 = 그 컨설턴트가 담당하는 대리점명 목록
# (컨설턴트별로 세로 나열된 "가로형" 시트라 df.melt()로 세로 목록으로 펼쳐서 사용)
CONSULTANT_GID = "680750607"
CONSULTANT_SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={CONSULTANT_GID}"

# 한국 좌표 범위 (대략적인 육지 + 도서 지역 포함)
LAT_RANGE = (33, 39)
LON_RANGE = (124, 132)

# 지도 최소 줌(=최대 축소) — 대한민국 전체가 보이는 수준으로 제한.
# 사용자가 지도 "-" 버튼/스크롤로 이보다 더 축소하지 못하도록 min_zoom으로도 사용됨
KOREA_OVERVIEW_ZOOM = 6.3


@st.cache_data(ttl=600)  # 10분마다 구글 시트에서 최신 데이터를 다시 불러옴
def load_data():
    try:
        return pd.read_csv(SHEET_URL)
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None


@st.cache_data(ttl=600)
def load_consultant_data():
    try:
        return pd.read_csv(CONSULTANT_SHEET_URL)
    except Exception as e:
        st.warning(f"컨설턴트 시트를 불러오는데 실패했습니다: {e}")
        return None


def normalize_dealer_name(name) -> str:
    """대리점명을 매칭 비교 전용으로 정규화 ('지점'/'대리점' 표기 차이를 '대리점'으로 통일).
    화면에 실제로 보여주는 원래 이름은 건드리지 않고, 두 시트를 비교할 때만 사용.
    예) '행복지점' / '행복대리점' -> 둘 다 '행복대리점'으로 정규화되어 같은 곳으로 매칭됨
    """
    name = str(name).strip()
    stripped = re.sub(r"(지점|대리점)$", "", name).strip()
    return f"{stripped}대리점" if stripped else name


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

    # 라이트 배경 지도에서 잘 보이는 부서별 색상 (지도 점 색상 전용)
    def generate_dept_colors(n: int):
        """지사 수(n)에 맞춰 서로 뚜렷이 구분되는 색상을 자동 생성.
        - 이모지/고정 팔레트는 8개 안팎이 한계라 지사가 많아지면 색이 반복되므로,
          지사 수와 무관하게 항상 고유하게 생성
        - 단순히 순서대로 균등 분할하면 시트에서 바로 옆(=지리적으로도 가까운
          경우가 많음)에 있는 지사끼리 색상환에서도 이웃한 색을 받아 비슷해
          보이므로, 골든 앵글(약 137.5도)만큼씩 건너뛰어 배치해 인접한 항목도
          최대한 멀리 떨어진 색을 받도록 함
        - 채도를 높고 명도를 밝게 고정해서 칙칙하지 않고 선명한 색이 나오게 함
        - 자극적으로 보이는 순수 빨강 계열(색상환 0도 부근)은 피함
        """
        colors = []
        if n <= 0:
            return colors
        hue_start, hue_end = 15, 345  # 0도(빨강) 부근 제외
        span = hue_end - hue_start
        golden_angle = 137.508
        lightness, saturation = 0.55, 0.85  # 선명하고 밝은 톤 고정 (칙칙해 보이지 않도록)
        for i in range(n):
            hue_deg = hue_start + ((i * golden_angle) % span)
            r, g, b = colorsys.hls_to_rgb(hue_deg / 360.0, lightness, saturation)
            colors.append([int(r * 255), int(g * 255), int(b * 255), 230])
        return colors

    if "부서" in df_valid.columns:
        unique_depts = df_valid["부서"].dropna().unique()
        dept_color_map = dict(zip(unique_depts, generate_dept_colors(len(unique_depts))))
        dept_hex_map = {d: "#{:02x}{:02x}{:02x}".format(*rgb[:3]) for d, rgb in dept_color_map.items()}
        df_valid["color"] = df_valid["부서"].map(lambda d: dept_color_map.get(d, [100, 100, 100, 220]))
    else:
        unique_depts = []
        dept_color_map = {}
        dept_hex_map = {}
        df_valid["color"] = [[100, 100, 100, 220]] * len(df_valid)

    # 대리점 시트와 컨설턴트 시트를 대리점명 기준으로 매칭
    df_consultant_raw = load_consultant_data()

    unique_consultants = []
    unmatched_in_dealer_sheet = []      # 컨설턴트 시트에는 있는데 대리점 시트에서 못 찾은 이름
    unmatched_in_consultant_sheet = []  # 대리점 시트에는 있는데 컨설턴트 시트에서 못 찾은 이름
    duplicate_assignments = []          # 같은 대리점이 컨설턴트 2명 이상에게 배정된 경우

    if df_consultant_raw is not None and "대리점명" in df_valid.columns:
        df_consultant_raw.columns = df_consultant_raw.columns.astype(str).str.strip()

        # 시트에 같은 컨설턴트 이름의 컬럼이 여러 번 나오면(예: 담당 대리점이
        # 많아서 컬럼을 나눠 적은 경우), 구글시트 CSV를 읽을 때 pandas가
        # "고화주", "고화주.1" 처럼 자동으로 이름을 바꿔서 서로 다른 사람으로
        # 인식해버리므로, 그 자동 접미사(.1, .2 ...)를 떼어내 다시 같은
        # 이름으로 되돌려서 같은 컨설턴트로 합쳐지도록 함
        df_consultant_raw.columns = df_consultant_raw.columns.str.replace(r"\.\d+$", "", regex=True)

        # 컬럼 헤더가 정확히 "컨설턴트"인 경우는 실제 담당자 이름이 아니라
        # 레이블/참고용 컬럼일 가능성이 높으므로 매칭 대상에서 제외
        df_consultant_raw = df_consultant_raw.loc[:, df_consultant_raw.columns != "컨설턴트"]

        # 컨설턴트별로 세로 나열된 "가로형" 시트를 (컨설턴트, 대리점명) 세로 목록으로 펼침
        consultant_long = (
            df_consultant_raw.melt(var_name="컨설턴트", value_name="대리점명")
            .dropna(subset=["대리점명"])
        )
        consultant_long["대리점명"] = consultant_long["대리점명"].astype(str).str.strip()
        consultant_long["컨설턴트"] = consultant_long["컨설턴트"].astype(str).str.strip()
        consultant_long = consultant_long[
            (consultant_long["대리점명"] != "")
            & (~consultant_long["컨설턴트"].str.startswith("Unnamed"))
        ]
        # 매칭 비교 전용 정규화 컬럼 ('지점'/'대리점' 표기 차이를 '대리점'으로 통일)
        consultant_long["_dealer_norm"] = consultant_long["대리점명"].map(normalize_dealer_name)

        df_valid["_dealer_norm"] = df_valid["대리점명"].astype(str).str.strip().map(normalize_dealer_name)

        dealer_to_consultants = consultant_long.groupby("_dealer_norm")["컨설턴트"].apply(list).to_dict()

        # 정규화된 이름 -> 원래 표기 하나(대표값) 매핑 (불일치 목록을 원래 표기로 보여주기 위함)
        norm_to_original_in_store = dict(zip(df_valid["_dealer_norm"], df_valid["대리점명"]))
        norm_to_original_in_consultant = dict(zip(consultant_long["_dealer_norm"], consultant_long["대리점명"]))

        duplicate_assignments = [
            (norm_to_original_in_store.get(norm, norm_to_original_in_consultant.get(norm, norm)), sorted(set(names)))
            for norm, names in dealer_to_consultants.items()
            if len(set(names)) > 1
        ]

        store_norm_set = set(df_valid["_dealer_norm"])
        consultant_norm_set = set(dealer_to_consultants.keys())
        unmatched_in_dealer_sheet = sorted(
            norm_to_original_in_consultant[n] for n in (consultant_norm_set - store_norm_set)
        )
        unmatched_in_consultant_sheet = sorted(
            norm_to_original_in_store[n] for n in (store_norm_set - consultant_norm_set)
        )

        df_valid["담당컨설턴트"] = df_valid["_dealer_norm"].map(
            lambda norm: ", ".join(dict.fromkeys(dealer_to_consultants.get(norm, [])))
        )
        df_valid.loc[df_valid["담당컨설턴트"] == "", "담당컨설턴트"] = "미지정"
        unique_consultants = sorted(consultant_long["컨설턴트"].unique())
    else:
        df_valid["담당컨설턴트"] = "미지정"

    # 대리점 시트에 원래부터 있던 '담당' 컬럼과 새로 계산한 '담당컨설턴트'가
    # 같은 정보라 목록 표에 중복으로 나타나므로 하나로 합침.
    # 계산된 값(컨설턴트 시트 매칭 결과)을 우선 쓰고, 매칭이 안 돼 '미지정'인
    # 경우에만 원래 '담당' 컬럼 값으로 채운 뒤, 원래 컬럼은 표에서 제거.
    if "담당" in df_valid.columns:
        def _clean_value(v):
            s = str(v).strip()
            return "" if s.lower() in ("", "none", "nan", "nat") else s

        fallback = df_valid["담당"].map(_clean_value)
        needs_fallback = (df_valid["담당컨설턴트"] == "미지정") & (fallback != "")
        df_valid.loc[needs_fallback, "담당컨설턴트"] = fallback[needs_fallback]
        df_valid = df_valid.drop(columns=["담당"])

    # 0-1. 지사별 통계 요약 (검색/필터와 무관하게 전체 데이터 기준)
    # streamlit-shadcn-ui의 카드형 metric_card 사용 (shadcn/ui 스타일)
    st.subheader("📊 전체 현황")
    summary_col1, summary_col2 = st.columns(2)
    with summary_col1:
        ui.metric_card(label="총 대리점 수", value=f"{len(df_valid):,}개", description="전체 등록 기준")
    with summary_col2:
        ui.metric_card(label="총 지사 수", value=f"{len(unique_depts):,}개", description="운영 중인 지사")

    if len(unique_depts) > 0:
        dept_counts_df = (
            df_valid["부서"]
            .value_counts()
            .reindex(unique_depts)
            .rename("대리점 수")
            .rename_axis("지사")
            .reset_index()
        )
        # st.bar_chart는 값 범위를 고정할 수 없고 기본으로 확대/이동(pan-zoom)이
        # 켜져 있어 스크롤이 끝없이 되므로, Altair로 직접 그려서 0~40으로 고정하고
        # 확대/이동은 끈다 (.interactive() 호출하지 않음)
        # 세로 막대 + 지도 마커와 동일한 지사별 색상 적용
        dept_bar = alt.Chart(dept_counts_df).mark_bar().encode(
            x=alt.X("지사:N", sort=list(unique_depts), title=None, axis=alt.Axis(labelAngle=-40)),
            y=alt.Y("대리점 수:Q", scale=alt.Scale(domain=[0, 40], clamp=True), title="대리점 수"),
            color=alt.Color(
                "지사:N",
                scale=alt.Scale(domain=list(unique_depts), range=[dept_hex_map[d] for d in unique_depts]),
                legend=None,
            ),
            tooltip=["지사", "대리점 수"],
        )
        # 막대 위에 값(대리점 수) 라벨을 텍스트로 표시해 한눈에 값이 보이게 함
        # (기본 글자 크기 11px에서 5단계 키운 16px)
        dept_labels = alt.Chart(dept_counts_df).mark_text(dy=-8, fontWeight="bold", fontSize=16).encode(
            x=alt.X("지사:N", sort=list(unique_depts)),
            y=alt.Y("대리점 수:Q", scale=alt.Scale(domain=[0, 40], clamp=True)),
            text="대리점 수:Q",
        )
        st.altair_chart(dept_bar + dept_labels, use_container_width=True)

    # 0-2. 지도 색상 토글 버튼 (지사를 클릭하면 해당 지사만 지도에 표시,
    # 다시 클릭해서 선택 해제하면 원래 크기의 전체 지도로 돌아감)
    # streamlit-shadcn-ui의 toggle_group(selection_mode="multiple")으로 다중 선택 지원
    if len(unique_depts) > 0:
        selected_depts = ui.toggle_group(
            options=list(unique_depts),
            value=[],
            selection_mode="multiple",
            label="🗺️ 지도 색상 (지사를 클릭하면 해당 지사만 지도에 표시됩니다 · 여러 개 선택 가능, 선택 해제 시 전체 지도로 복귀)",
            key="dept_toggle_group",
        ) or []

        # 버튼 글자만으로는 지사가 많을 때 색을 구분해서 표시할 수 없어서,
        # 실제 지도 점/그래프 막대 색상과 정확히 일치하는 참고용 범례를 별도로 표시 (선택과는 무관)
        legend_items = [
            f"<span style='color:{dept_hex_map[dept]};'>■</span> {dept}" for dept in unique_depts
        ]
        st.markdown(
            f"<div style='font-size:12px; color:#64748B;'>지도 점 색상: {' &nbsp; '.join(legend_items)}</div>",
            unsafe_allow_html=True,
        )
    else:
        selected_depts = []

    # 0-3. 담당 컨설턴트 토글 버튼 (지사 버튼과 동일한 방식 — 클릭하면 해당
    # 컨설턴트가 담당하는 대리점만 표시, 다시 클릭하면 해제)
    if unique_consultants:
        selected_consultants = ui.toggle_group(
            options=unique_consultants,
            value=[],
            selection_mode="multiple",
            label="👤 담당 컨설턴트 (클릭하면 해당 컨설턴트가 담당하는 대리점만 표시됩니다 · 여러 명 선택 가능)",
            key="consultant_toggle_group",
        ) or []
    else:
        selected_consultants = []

    # 지사 선택 + 컨설턴트 선택은 둘 다 지정된 경우에만 표시(AND)되도록 결합
    df_dept_base = df_valid
    if selected_depts and "부서" in df_valid.columns:
        df_dept_base = df_dept_base[df_dept_base["부서"].isin(selected_depts)]
    if selected_consultants:
        mask = df_dept_base["담당컨설턴트"].apply(
            lambda v: any(c in [x.strip() for x in v.split(",")] for c in selected_consultants)
        )
        df_dept_base = df_dept_base[mask]

    active_filters = []
    if selected_depts:
        active_filters.append(f"지사({', '.join(selected_depts)})")
    if selected_consultants:
        active_filters.append(f"컨설턴트({', '.join(selected_consultants)})")
    if active_filters:
        st.caption(f"📍 {' · '.join(active_filters)} 조건으로 표시 중 — 총 {len(df_dept_base)}건")

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

    # 대리점 시트 <-> 컨설턴트 시트 매칭 불일치 확인
    mismatch_total = len(unmatched_in_dealer_sheet) + len(unmatched_in_consultant_sheet) + len(duplicate_assignments)
    if mismatch_total > 0:
        with st.expander(f"⚠️ 대리점-컨설턴트 매칭 불일치 {mismatch_total}건 확인"):
            if unmatched_in_consultant_sheet:
                st.markdown(f"**컨설턴트가 지정되지 않은 대리점 ({len(unmatched_in_consultant_sheet)}건)**")
                st.caption("대리점 시트에는 있지만, 컨설턴트 시트 어느 컬럼에도 이 대리점명이 없습니다.")
                st.dataframe(pd.DataFrame({"대리점명": unmatched_in_consultant_sheet}), use_container_width=True)
            if unmatched_in_dealer_sheet:
                st.markdown(f"**대리점 시트에서 찾을 수 없는 이름 ({len(unmatched_in_dealer_sheet)}건, 오타 의심)**")
                st.caption("컨설턴트 시트에는 있지만, 대리점 시트의 '대리점명'과 정확히 일치하지 않습니다.")
                st.dataframe(pd.DataFrame({"대리점명": unmatched_in_dealer_sheet}), use_container_width=True)
            if duplicate_assignments:
                st.markdown(f"**컨설턴트가 2명 이상 겹쳐서 배정된 대리점 ({len(duplicate_assignments)}건)**")
                st.dataframe(
                    pd.DataFrame([{"대리점명": d, "컨설턴트": ", ".join(names)} for d, names in duplicate_assignments]),
                    use_container_width=True,
                )

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
            return max(KOREA_OVERVIEW_ZOOM, min(zoom, 14.0))

        view_latitude = float(mid_lat) if not pd.isna(mid_lat) else 37.5
        view_longitude = float(mid_lon) if not pd.isna(mid_lon) else 127.0
        view_zoom = compute_zoom(df_display["lat"], df_display["lon"])

        view_state = pdk.ViewState(
            latitude=view_latitude,
            longitude=view_longitude,
            zoom=view_zoom,
            # 사용자가 지도의 "-" 버튼이나 스크롤/핀치로 직접 축소하더라도
            # 대한민국 전체 범위보다 더 축소되지 않도록 하드 제한
            min_zoom=KOREA_OVERVIEW_ZOOM,
            max_zoom=18,
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
                    "<b>대표자:</b> {대표자명} ({전화번호})<br/>"
                    "<b>담당 컨설턴트:</b> {담당컨설턴트}"
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
        #
        # key를 넣지 않으면 브라우저에 이미 떠 있는 지도 컴포넌트가 코드에서 바뀐
        # initial_view_state(줌/중심 좌표)를 무시하고 예전 뷰 상태를 그대로 유지하는
        # 경우가 있어, 표시 중인 데이터가 바뀔 때마다(줌/중심 좌표가 달라질 때마다)
        # key도 함께 바꿔서 지도를 강제로 새로 그리도록 함
        st.pydeck_chart(
            pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                tooltip=tooltip
            ),
            height=600,
            use_container_width=True,
            key=f"store_map_{view_latitude:.4f}_{view_longitude:.4f}_{view_zoom:.2f}_{len(df_display)}",
        )
    else:
        st.warning("표시할 수 있는 위치 데이터가 없거나, 구글 시트의 위도/경도 값이 올바르지 않습니다.")

    # 3. 데이터 표 출력 (위도, 경도 및 내부 생성 컬럼 모두 제외)
    st.subheader("📋 대리점 목록")

    cols_to_exclude = ["위도", "경도", "lat", "lon", "latitude", "longitude", "color", "_dealer_norm"]
    display_columns = [col for col in df_display.columns if col not in cols_to_exclude]

    st.dataframe(df_display[display_columns], use_container_width=True)
