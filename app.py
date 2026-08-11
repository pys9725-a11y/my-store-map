import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# 1. 페이지 설정
st.set_page_config(page_title="주소 기반 지도 시각화", layout="wide")
st.title("📍 구글 시트 주소 데이터 지도 시각화")

# 2. 구글 시트 데이터 불러오기
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
# CSV 형태 다운로드 URL 구성
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data
def load_data():
    try:
        # CSV 파일 로드
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None

df = load_data()

if df is not None:
    st.subheader("📊 불러온 원본 데이터")
    st.dataframe(df.head())

    # 3. 주소를 위도/경도로 변환 (지오코딩)
    st.info("주소를 위도/경도로 변환하는 중입니다...")
    
    # 무료 지오코딩 서비스 (Nominatim) 설정
    geolocator = Nominatim(user_agent="my_streamlit_map_app")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    def get_lat_lon(address):
        try:
            location = geocode(address)
            if location:
                return pd.Series([location.latitude, location.longitude])
            else:
                return pd.Series([None, None])
        except:
            return pd.Series([None, None])

    # df['address'] 열의 주소를 바탕으로 lat(위도), lon(경도) 컬럼 생성
    df[['lat', 'lon']] = df['address'].apply(get_lat_lon)

    # 위도/경도를 찾지 못한 행(NaN) 제거
    df_map = df.dropna(subset=['lat', 'lon'])

    if not df_map.empty:
        st.subheader("🗺️ 지도 시각화")
        # Streamlit 내장 지도 표시
        st.map(df_map[['lat', 'lon']])

        st.subheader("✅ 변환 완료 데이터")
        st.dataframe(df_map)
    else:
        st.warning("위도와 경도를 추출할 수 있는 유효한 주소가 없습니다. 구글 시트의 주소 컬럼명을 'address'로 맞췄는지 확인해 주세요.")
