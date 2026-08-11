import streamlit as st
import pandas as pd
import requests

# 1. 페이지 설정
st.set_page_config(page_title="대리점 위치 지도 시각화", layout="wide")
st.title("📍 카카오 API 기반 대리점 지도 시각화")

# 2. API 키 및 구글 시트 URL 설정
try:
    KAKAO_API_KEY = st.secrets["KAKAO_API_KEY"]
except KeyError:
    st.error("Secrets에서 KAKAO_API_KEY를 찾을 수 없습니다. Settings -> Secrets를 확인해 주세요.")
    st.stop()

# 구글 시트 ID 넣기
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 3. 구글 시트 불러오기
@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None

# 4. 카카오 로컬 API로 주소를 위도/경도로 변환
def get_kakao_lat_lon(address, api_key):
    if pd.isna(address) or not str(address).strip():
        return pd.Series([None, None])
    
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {"query": address}
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        if response.status_code == 200:
            result = response.json()
            documents = result.get("documents")
            if documents:
                # x: 경도(lon), y: 위도(lat)
                lon = float(documents[0]["x"])
                lat = float(documents[0]["y"])
                return pd.Series([lat, lon])
    except Exception:
        pass
    
    return pd.Series([None, None])

# 캐싱 처리 (매번 API 재호출 방지)
@st.cache_data
def process_geocoding(df, api_key):
    df[['위도', '경도']] = df['주소'].apply(lambda addr: get_kakao_lat_lon(addr, api_key))
    return df

# 메인 로직
df_raw = load_data()

if df_raw is not None:
    st.subheader("📊 원본 구글 시트 데이터")
    st.dataframe(df_raw)

    with st.spinner("카카오 지도 API로 주소를 좌표로 변환하는 중..."):
        df = process_geocoding(df_raw, KAKAO_API_KEY)

    # 좌표가 정상 변환된 행만 필터링
    df_map = df.dropna(subset=['위도', '경도']).copy()
    
    # Streamlit 지도 표준 컬럼 생성
    df_map['latitude'] = df_map['위도']
    df_map['longitude'] = df_map['경도']

    if not df_map.empty:
        st.subheader("🗺️ 대리점 위치 지도")
        st.map(df_map[['latitude', 'longitude']])

        st.subheader("✅ 변환 완료 데이터")
        st.dataframe(df)
    else:
        st.warning("위도와 경도를 추출할 수 있는 유효한 주소가 없습니다. D열 헤더가 '주소'로 되어 있는지 확인해 주세요.")
