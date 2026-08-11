import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter

# 1. 페이지 설정
st.set_page_config(page_title="대리점 위치 지도 시각화", layout="wide")
st.title("📍 구글 시트 기반 대리점 위치 지도 시각화")

# 2. 구글 시트 데이터 불러오기
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data
def load_data():
    try:
        df = pd.read_csv(SHEET_URL)
        return df
    except Exception as e:
        st.error(f"구글 시트를 불러오는데 실패했습니다: {e}")
        return None

df = load_data()

if df is not None:
    st.subheader("📊 불러온 원본 데이터")
    st.dataframe(df)

    # 3. 주소(D열: '주소') 기반으로 위도(H열: '위도'), 경도(I열: '경도') 추출
    st.info("주소를 위도/경도로 변환 중입니다...")
    
    geolocator = Nominatim(user_agent="my_map_app_v1")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    def get_lat_lon(address):
        if pd.isna(address):
            return pd.Series([None, None])
        try:
            location = geocode(address)
            if location:
                return pd.Series([location.latitude, location.longitude])
            else:
                return pd.Series([None, None])
        except:
            return pd.Series([None, None])

    # 구글 시트의 '주소' 열을 사용하여 '위도', '경도' 열 채우기
    df[['위도', '경도']] = df['주소'].apply(get_lat_lon)

    # 위도, 경도 값이 정상적으로 생성된 데이터만 필터링
    df_map = df.dropna(subset=['위도', '경도']).copy()

    # Streamlit 지도 표시용 컬럼명(latitude, longitude) 매핑
    df_map['latitude'] = df_map['위도']
    df_map['longitude'] = df_map['경도']

    if not df_map.empty:
        st.subheader("🗺️ 대리점 지도 시각화")
        # 지도에 위치 표시
        st.map(df_map[['latitude', 'longitude']])

        st.subheader("✅ 위도/경도 변환 완료 데이터")
        st.dataframe(df)
    else:
        st.warning("위도와 경도를 추출할 수 있는 유효한 주소가 없습니다. 구글 시트의 D열 헤더가 '주소'로 잘 설정되어 있는지 확인해 주세요.")
