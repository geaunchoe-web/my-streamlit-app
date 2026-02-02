import random
from datetime import date

import requests
import streamlit as st

st.set_page_config(page_title="🎬 심리테스트 영화 추천", page_icon="🎬")

st.title("🎬 심리테스트로 영화 추천 받기")
st.write("간단한 질문에 답하면 당신에게 맞는 장르와 인기 영화를 추천해드려요!")

genre_map = {
    "액션": 28,
    "코미디": 35,
    "드라마": 18,
    "SF": 878,
    "로맨스": 10749,
    "판타지": 14,
}

genre_reason = {
    "액션": "짜릿한 긴장감과 빠른 전개를 좋아하는 당신에게 액션 영화가 잘 맞아요!",
    "코미디": "웃음과 가벼운 분위기를 선호하는 성향이 보여 코미디를 추천해요!",
    "드라마": "감정의 흐름과 깊은 이야기에 끌리는 당신에게 드라마가 제격이에요!",
    "SF": "새로운 세계관과 상상력을 즐기는 당신에게 SF 영화가 어울려요!",
    "로맨스": "따뜻한 감성과 관계의 이야기에 관심이 많아 로맨스를 추천해요!",
    "판타지": "모험과 마법 같은 비현실적인 세계를 즐기는 성향이 보여요!",
}

questions = [
    {
        "question": "주말에 가장 하고 싶은 일은?",
        "options": {
            "액션 넘치는 아웃도어 활동": "액션",
            "친구들과 가볍게 웃고 떠들기": "코미디",
            "조용한 카페에서 생각 정리": "드라마",
            "새로운 기술/과학 뉴스 탐색": "SF",
            "연인과 데이트 코스 즐기기": "로맨스",
            "게임/소설로 다른 세계 탐험": "판타지",
        },
    },
    {
        "question": "가장 좋아하는 스토리의 분위기는?",
        "options": {
            "박진감 넘치는 추격전": "액션",
            "유쾌하고 가벼운 코미디": "코미디",
            "잔잔하지만 여운 있는 이야기": "드라마",
            "우주/미래 배경의 설정": "SF",
            "설레는 관계 중심의 이야기": "로맨스",
            "마법과 전설이 있는 세계": "판타지",
        },
    },
    {
        "question": "가장 끌리는 주인공 유형은?",
        "options": {
            "위기에 강한 해결사": "액션",
            "재치 있고 사랑받는 인물": "코미디",
            "현실적인 고민을 가진 인물": "드라마",
            "천재 과학자 또는 탐험가": "SF",
            "따뜻한 감성의 로맨티스트": "로맨스",
            "운명적인 영웅/마법사": "판타지",
        },
    },
]

st.sidebar.header("🔑 TMDB 설정")
tmdb_api_key = st.sidebar.text_input("TMDB API Key", type="password")
st.sidebar.subheader("🎛️ 추천 옵션")
language = st.sidebar.selectbox("언어", ["ko-KR", "en-US"], index=0)
region = st.sidebar.text_input("지역(국가 코드)", value="KR")
min_vote_count = st.sidebar.slider("최소 투표 수", 0, 5000, 300, step=100)
min_rating = st.sidebar.slider("최소 평점", 0.0, 10.0, 6.5, step=0.1)
include_adult = st.sidebar.checkbox("성인 콘텐츠 포함", value=False)
recommendation_count = st.sidebar.slider("추천 영화 수", 3, 10, 5)
current_year = date.today().year
year_range = st.sidebar.slider(
    "개봉 연도 범위",
    1980,
    current_year,
    (2010, current_year),
)

st.subheader("🧠 질문에 답해주세요")

answers = []
for index, question in enumerate(questions, start=1):
    choice = st.radio(
        f"Q{index}. {question['question']}",
        list(question["options"].keys()),
        index=0,
        key=f"question_{index}",
    )
    answers.append(question["options"][choice])


def analyze_genre(selected_genres):
    scores = {genre: 0 for genre in genre_map}
    for genre in selected_genres:
        scores[genre] += 1
    max_score = max(scores.values())
    top_genres = [genre for genre, score in scores.items() if score == max_score]
    return top_genres[0]


@st.cache_data(ttl=600)
def fetch_movies(api_key, genre_id, filters):
    url = "https://api.themoviedb.org/3/discover/movie"
    params = {
        "api_key": api_key,
        "with_genres": genre_id,
        "language": filters["language"],
        "region": filters["region"],
        "sort_by": "popularity.desc",
        "vote_count.gte": filters["min_vote_count"],
        "vote_average.gte": filters["min_rating"],
        "include_adult": filters["include_adult"],
        "primary_release_date.gte": f"{filters['year_range'][0]}-01-01",
        "primary_release_date.lte": f"{filters['year_range'][1]}-12-31",
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    return data.get("results", [])


def build_reason(genre, rating, votes):
    base = genre_reason[genre]
    if rating >= 8:
        rating_note = "평점이 높아서 완성도 측면에서도 만족도가 높을 가능성이 큽니다."
    elif rating >= 7:
        rating_note = "평점이 안정적으로 좋아서 부담 없이 보기 좋은 작품이에요."
    else:
        rating_note = "가볍게 즐길 수 있는 작품이라 취향 테스트에 좋아요."
    popularity_note = "관객 반응이 풍부한 작품" if votes >= 500 else "숨은 보석 같은 작품"
    return f"{base} 또한 {popularity_note}이라서 추천해요. {rating_note}"


def chunk_movies(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


st.divider()
if st.button("결과 보기"):
    if not tmdb_api_key:
        st.error("⚠️ 사이드바에서 TMDB API Key를 입력해주세요!")
    else:
        recommended_genre = analyze_genre(answers)
        st.markdown(f"## 당신에게 딱인 장르는: **{recommended_genre}**!")
        st.caption(genre_reason[recommended_genre])

        filters = {
            "language": language,
            "region": region,
            "min_vote_count": min_vote_count,
            "min_rating": min_rating,
            "include_adult": include_adult,
            "year_range": year_range,
        }

        with st.spinner("TMDB에서 영화를 찾는 중..."):
            try:
                movies = fetch_movies(
                    tmdb_api_key, genre_map[recommended_genre], filters
                )
            except requests.RequestException:
                st.error("TMDB API 요청에 실패했어요. API Key를 확인해주세요.")
                movies = []

        if movies:
            random.shuffle(movies)
            movies = movies[:recommendation_count]
            st.subheader("🍿 추천 영화 리스트")
            for row in chunk_movies(movies, 3):
                columns = st.columns(3)
                for column, movie in zip(columns, row):
                    poster_path = movie.get("poster_path")
                    poster_url = (
                        f"https://image.tmdb.org/t/p/w500{poster_path}"
                        if poster_path
                        else None
                    )
                    title = movie.get("title", "제목 없음")
                    rating = movie.get("vote_average", 0)
                    votes = movie.get("vote_count", 0)
                    overview = movie.get("overview", "줄거리 정보가 없습니다.")
                    release_date = movie.get("release_date", "정보 없음")

                    with column:
                        if poster_url:
                            st.image(poster_url, use_container_width=True)
                        else:
                            st.write("포스터 없음")
                        st.markdown(f"**{title}**")
                        st.write(f"평점: {rating}")
                        with st.expander("상세 정보 보기"):
                            st.write(f"개봉일: {release_date}")
                            st.write(f"투표 수: {votes}")
                            st.write(overview)
                            st.info(
                                "이 영화를 추천하는 이유: "
                                f"{build_reason(recommended_genre, rating, votes)}"
                            )
        else:
            st.warning("추천할 영화를 가져오지 못했어요. 잠시 후 다시 시도해주세요.")
