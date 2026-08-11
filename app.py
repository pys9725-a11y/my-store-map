import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="진단 모드", layout="wide")
st.title("🔍 오류 진단 모드")

# 1. API 키 확인
if "KAKAO_API_KEY" not in st.secrets:
    st.error("❌ Secrets에 KAKAO_API_KEY가 설정되지 않았습니다.")
    st.stop()
else:
    st.success("✅ KAKAO_API_KEY가 Secrets에 정상 등록되어 있습니다.")

KAKAO_API_KEY = st.secrets["KAKAO_API_KEY"]
SHEET_ID = "1o-FqwhkRsmUN5aH4ook5T7kQ_RAq6zSg6VV1Jymqi8E"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

# 2. 구글 시트 로드 확인
try:
    df = pd.read_csv(SHEET_URL)
    st.success("✅ 구글 시트를 성공적으로 불러왔습니다.")
    st.write("📋 인식된 열(Column) 이름 목록:", list(df.columns))
    st.dataframe(df.head(3))
except Exception as e:
    st.error(f"❌ 구글 시트를 불러오지 못했습니다: {e}")
    st.stop()

# 3. '주소' 열 존재 여부 체크
if '주소' not in df.columns:
    st.error("❌ 구글 시트에 '주소'라는 열 이름이 없습니다. 위 목록의 열 이름을 확인해 주세요.")
    st.stop()

# 4. 카카오 API 테스트
sample_address = df['주소'].dropna().iloc[0] if not df['주소'].dropna().empty else None

if sample_address:
    st.write(f"🧪 첫 번째 주소 샘플 테스트: `{sample_address}`")
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    response = requests.get(url, headers=headers, params={"query": sample_address})
    
    st.write(f"📡 카카오 API 응답 코드: `{response.status_code}`")
    if response.status_code == 200:
        st.json(response.json())
    else:
        st.error(f"❌ 카카오 API 호출 실패 (응답 내용: {response.text})")
