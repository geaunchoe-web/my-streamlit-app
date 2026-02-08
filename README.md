# RecoMe

여행지와 여행 루트를 추천하고, 채팅으로 편집한 뒤 최종 일정표를 내보낼 수 있는 Streamlit MVP입니다.

## 실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

## OpenAI API Key 설정

아래 두 가지 방법을 모두 지원합니다.

### 1) `.env` 사용

프로젝트 루트에 `.env` 파일을 만들고 아래처럼 입력합니다.

```
OPENAI_API_KEY=YOUR_KEY
OPENAI_MODEL=gpt-4.1-mini
```

### 2) `st.secrets` 사용

`.streamlit/secrets.toml` 파일에 아래처럼 입력합니다.

```
OPENAI_API_KEY = "YOUR_KEY"
OPENAI_MODEL = "gpt-4.1-mini"
```

## 사용 방법

1. 사이드바에서 여행 조건을 입력하고 **"루트 추천받기"** 버튼을 누릅니다.
2. 추천 결과(여행지 카드 + 일정표 + 지도 링크 + 대안 루트)를 확인합니다.
3. **"이 루트 저장"**으로 세션에 저장합니다.
4. 하단 채팅 입력창에서 자연어로 편집 요청을 보냅니다.
5. 변경 요약을 확인하고, JSON 다운로드 또는 마크다운 일정표를 복사합니다.

## 지도 링크

- 국내: 네이버 지도 검색 링크
- 해외: 구글 지도 검색 링크

API 키가 없어도 검색 링크 방식으로 동작합니다.
