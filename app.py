import json
import os
import textwrap
from datetime import datetime
from urllib.parse import quote

import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError
from openai import OpenAI

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

st.set_page_config(page_title="RecoMe", page_icon="🧭", layout="wide")

if load_dotenv:
    load_dotenv()

def get_secret(key):
    try:
        return st.secrets.get(key)
    except StreamlitSecretNotFoundError:
        return None


def get_openai_model():
    secret = get_secret("OPENAI_MODEL")
    if secret:
        return secret
    return os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


OPENAI_MODEL = get_openai_model()

st.title("🧭 RecoMe")
st.caption("추천 받기 → 저장 → 채팅으로 편집 → 최종 일정표 내보내기")

if "saved_itineraries" not in st.session_state:
    st.session_state.saved_itineraries = []
if "current_itinerary" not in st.session_state:
    st.session_state.current_itinerary = None
if "edit_messages" not in st.session_state:
    st.session_state.edit_messages = []
if "last_edit_summary" not in st.session_state:
    st.session_state.last_edit_summary = []
if "openai_api_key_override" not in st.session_state:
    st.session_state.openai_api_key_override = ""
if "last_generation_error" not in st.session_state:
    st.session_state.last_generation_error = ""


def get_openai_key():
    if st.session_state.openai_api_key_override:
        return st.session_state.openai_api_key_override
    secret = get_secret("OPENAI_API_KEY")
    if secret:
        return secret
    return os.getenv("OPENAI_API_KEY")


def build_generation_prompt(inputs):
    purpose_text = ", ".join(inputs["purpose"]) if inputs["purpose"] else "일반 여행"
    prompt = f"""
    여행 조건:
    - 여행 유형: {inputs['trip_type']}
    - 출발 지역: {inputs['start_city']}
    - 일정: {inputs['days_nights']}
    - 목적: {purpose_text}
    - 동행: {inputs['companions']}
    - 이동 선호: {inputs['transport_preference']}
    - 일정 밀도: {inputs['pace']}
    - 예산: {inputs['budget_level'] or '무관'}
    - 포함 희망: {inputs['must_include'] or '없음'}
    - 피하고 싶은 것: {inputs['avoid'] or '없음'}
    """
    return textwrap.dedent(prompt).strip()


def build_edit_prompt(current_json, user_msg):
    prompt = f"""
    현재 일정 JSON:
    {json.dumps(current_json, ensure_ascii=False)}

    사용자 요청:
    {user_msg}
    """
    return textwrap.dedent(prompt).strip()


def call_openai_json(system_prompt, user_prompt, model):
    api_key = get_openai_key()
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    client = OpenAI(api_key=api_key)
    last_error = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.6,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as error:  # noqa: BLE001
            last_error = error
            if attempt < 2 and isinstance(error, json.JSONDecodeError):
                retry_prompt = "JSON만 다시 반환해주세요. 추가 텍스트는 금지합니다."
                user_prompt = f"{user_prompt}\n\n{retry_prompt}"
                continue
            break
    raise ValueError(f"JSON 파싱 실패: {last_error}")


def itinerary_to_dataframe(itinerary_json):
    rows = []
    for day_entry in itinerary_json.get("itinerary", []):
        day = day_entry.get("day")
        for spot in day_entry.get("spots", []):
            rows.append(
                {
                    "day": day,
                    "order": spot.get("order"),
                    "name": spot.get("name"),
                    "category": spot.get("category"),
                    "stay_minutes": spot.get("stay_minutes"),
                    "short_reason": spot.get("short_reason"),
                }
            )
    return rows


def itinerary_to_markdown(itinerary_json):
    lines = []
    for day_entry in itinerary_json.get("itinerary", []):
        lines.append(f"### Day {day_entry.get('day')} - {day_entry.get('theme', '')}")
        for spot in day_entry.get("spots", []):
            line = (
                f"{spot.get('order')}. {spot.get('name')} "
                f"({spot.get('category')}) - {spot.get('short_reason')}"
            )
            lines.append(line)
        lines.append("")
    return "\n".join(lines).strip()


def build_map_link(trip_type, spot_name, city_region):
    query = quote(f"{city_region} {spot_name}".strip())
    if trip_type == "국내":
        return f"https://map.naver.com/v5/search/{query}"
    return f"https://www.google.com/maps/search/?api=1&query={query}"


JSON_SCHEMA = textwrap.dedent(
    """
    {
      "destination": {
        "country": "",
        "city_region": "",
        "why_fit": ""
      },
      "itinerary": [
        {
          "day": 1,
          "theme": "",
          "spots": [
            {
              "order": 1,
              "name": "",
              "category": "",
              "stay_minutes": 0,
              "short_reason": ""
            }
          ]
        }
      ],
      "summary_one_liner": "",
      "alt_route": {
        "vibe": "",
        "spots_brief": ["", "", ""]
      }
    }
    """
).strip()

GENERATION_SYSTEM_PROMPT = textwrap.dedent(
    f"""
    너는 여행 플래너 AI다.
    사용자의 조건(국내/해외, 기간, 목적, 동행, 이동 선호, pace)을 반영해:
    - 추천 여행지 1곳
    - day-by-day 루트(여유: 3개/일, 보통: 4개/일, 빡빡: 5개/일)
    - 각 spot reason 1문장
    - summary_one_liner
    - alt_route(다른 vibe)
    반드시 아래 JSON 스키마만 반환하고, 추가 텍스트는 금지한다.
    JSON 스키마:
    {JSON_SCHEMA}
    """
).strip()

EDIT_SYSTEM_PROMPT = textwrap.dedent(
    f"""
    너는 itinerary editor AI다.
    입력: (현재 itinerary JSON) + (user edit request)
    규칙:
    - destination은 사용자가 바꾸라고 하지 않으면 유지
    - "너무 빡빡" => spots 수 줄이거나 stay_minutes 조정 + 동선 단순화
    - "A 대신 카페" => A 제거 후 cafe spot 추가
    - "쇼핑 추가" => shopping spot 1개 추가(과밀 금지)
    - "삭제" => 해당 spot 제거 후 order 재정렬
    - pace 기준 유지(여유 3, 보통 4, 빡빡 5를 기본으로)
    출력: 동일 스키마 JSON만 반환
    JSON 스키마:
    {JSON_SCHEMA}
    """
).strip()


def summarize_changes(before, after):
    summaries = []
    before_days = {d.get("day"): d.get("spots", []) for d in before.get("itinerary", [])}
    after_days = {d.get("day"): d.get("spots", []) for d in after.get("itinerary", [])}

    for day in sorted(after_days.keys()):
        before_spots = {spot.get("name") for spot in before_days.get(day, [])}
        after_spots = {spot.get("name") for spot in after_days.get(day, [])}
        added = list(after_spots - before_spots)
        removed = list(before_spots - after_spots)
        if added or removed:
            summary = f"Day {day}:"
            if added:
                summary += f" 추가 {', '.join(added)};"
            if removed:
                summary += f" 삭제 {', '.join(removed)};"
            summaries.append(summary.rstrip(";"))
        if len(summaries) >= 3:
            break

    if not summaries:
        summaries.append("일정 구조를 유지한 채 체류 시간과 동선을 조정했습니다.")
    return summaries


with st.sidebar:
    st.header("입력 정보")
    st.subheader("API 키 (선택)")
    openai_key_input = st.text_input(
        "OpenAI API Key",
        type="password",
        value=st.session_state.openai_api_key_override,
        help="로컬 테스트용 입력칸입니다. 비워두면 .env 또는 st.secrets 값을 사용합니다.",
    )
    st.session_state.openai_api_key_override = openai_key_input.strip()
    st.divider()

    trip_type = st.radio("여행 유형", ["국내", "해외"], horizontal=True)
    start_city = st.text_input("출발 지역", placeholder="예: 서울, 부산, 인천")
    days_nights = st.selectbox("일정", ["당일", "1박2일", "2박3일", "3박4일"])
    purpose = st.multiselect("여행 목적", ["힐링", "관광", "맛집", "활동"])
    companions = st.selectbox("동행", ["혼자", "친구", "연인", "가족"])
    transport_preference = st.selectbox("이동 선호", ["도보", "대중교통", "최소 이동"])
    pace = st.selectbox("일정 밀도", ["여유", "보통", "빡빡"])
    budget_level = st.selectbox("예산", ["저예산", "보통", "여유"], index=1)
    must_include = st.text_input("포함 희망 키워드/장소", placeholder="예: 카페거리, 바다")
    avoid = st.text_input("피하고 싶은 것", placeholder="예: 등산, 스시")

    st.divider()
    if st.button("루트 추천받기", use_container_width=True):
        if not start_city:
            st.error("출발 지역을 입력해주세요.")
        else:
            user_inputs = {
                "trip_type": trip_type,
                "start_city": start_city,
                "days_nights": days_nights,
                "purpose": purpose,
                "companions": companions,
                "transport_preference": transport_preference,
                "pace": pace,
                "budget_level": budget_level,
                "must_include": must_include,
                "avoid": avoid,
            }
            prompt = build_generation_prompt(user_inputs)
            with st.spinner("추천 루트를 생성하는 중..."):
                try:
                    itinerary = call_openai_json(GENERATION_SYSTEM_PROMPT, prompt, OPENAI_MODEL)
                except ValueError as error:
                    st.error(str(error))
                    itinerary = None
                    st.session_state.last_generation_error = str(error)
                else:
                    st.session_state.last_generation_error = ""
            st.session_state.current_itinerary = itinerary
            st.session_state.last_edit_summary = []


current = st.session_state.current_itinerary
if current:
    destination = current.get("destination", {})
    summary_one_liner = current.get("summary_one_liner", "")

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("추천 여행지")
        st.markdown(
            f"**{destination.get('country', '')} / {destination.get('city_region', '')}**"
        )
        st.write(destination.get("why_fit", ""))
    with col2:
        st.subheader("한 줄 요약")
        st.success(summary_one_liner)

    st.subheader("추천 일정표")
    rows = itinerary_to_dataframe(current)
    if rows:
        st.dataframe(rows, use_container_width=True)
    else:
        st.warning("추천 일정표 데이터가 비어 있습니다. 다시 추천을 받아주세요.")

    st.subheader("지도 링크")
    for day_entry in current.get("itinerary", []):
        with st.expander(f"Day {day_entry.get('day')} 지도 링크"):
            for spot in day_entry.get("spots", []):
                link = build_map_link(
                    trip_type,
                    spot.get("name", ""),
                    destination.get("city_region", ""),
                )
                st.markdown(f"- [{spot.get('name')}]({link})")

    alt_route = current.get("alt_route", {})
    st.subheader("대안 루트")
    st.write(f"분위기: {alt_route.get('vibe', '')}")
    for spot in alt_route.get("spots_brief", []):
        st.write(f"- {spot}")

    if st.button("이 루트 저장"):
        st.session_state.saved_itineraries.append(
            {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "input": {
                    "trip_type": trip_type,
                    "start_city": start_city,
                    "days_nights": days_nights,
                    "purpose": purpose,
                    "companions": companions,
                    "transport_preference": transport_preference,
                    "pace": pace,
                    "budget_level": budget_level,
                    "must_include": must_include,
                    "avoid": avoid,
                },
                "itinerary": current,
            }
        )
        st.success("저장되었습니다!")

    st.divider()
    st.subheader("채팅으로 일정 편집")

    for message in st.session_state.edit_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_edit = st.chat_input("수정 요청을 입력하세요")
    if user_edit:
        st.session_state.edit_messages.append({"role": "user", "content": user_edit})
        with st.chat_message("user"):
            st.markdown(user_edit)

        with st.chat_message("assistant"):
            with st.spinner("일정을 수정하는 중..."):
                try:
                    edit_prompt = build_edit_prompt(current, user_edit)
                    updated = call_openai_json(
                        EDIT_SYSTEM_PROMPT, edit_prompt, OPENAI_MODEL
                    )
                except ValueError as error:
                    st.error(str(error))
                    updated = None
            if updated:
                st.session_state.last_edit_summary = summarize_changes(current, updated)
                st.session_state.current_itinerary = updated
                st.markdown("수정 완료! 아래 결과를 확인하세요.")
        if updated:
            st.session_state.edit_messages.append(
                {"role": "assistant", "content": "수정 완료! 아래 결과를 확인하세요."}
            )

    if st.session_state.last_edit_summary:
        st.subheader("변경 요약")
        for line in st.session_state.last_edit_summary[:3]:
            st.write(f"- {line}")

    st.subheader("최종 일정표 내보내기")
    markdown_text = itinerary_to_markdown(st.session_state.current_itinerary)
    st.download_button(
        "JSON 다운로드",
        data=json.dumps(st.session_state.current_itinerary, ensure_ascii=False, indent=2),
        file_name="recome_itinerary.json",
        mime="application/json",
    )
    st.text_area("마크다운 일정표", value=markdown_text, height=200)

elif st.session_state.saved_itineraries:
    st.info("저장된 루트를 보려면 새 루트를 추천받아 주세요.")
else:
    if st.session_state.last_generation_error:
        st.error(
            "루트 생성 중 오류가 발생했습니다. 입력한 API 키와 네트워크 상태를 확인해주세요."
        )
        st.caption(st.session_state.last_generation_error)
    else:
        st.info("왼쪽에서 여행 조건을 입력하고 루트를 추천받아 주세요.")
