# -*- coding: utf-8 -*-

import asyncio

import json

import os

import platform

import subprocess

from datetime import datetime

from typing import Dict, List, Optional, Tuple

from urllib.parse import urlparse, quote

import random

from collections import deque



import aiohttp

from openai import OpenAI



# ======== 사용자/환경 설정 ========

# 필수

ROOM_PATH = "groomee-god" # 방이 바뀔때마다 최신화 시키기

SENDER_EMAIL = "hsu_demo_02@gooroomee.com"



# 기본 엔드포인트(스펙 기준)

API_BASE = os.getenv(

    "API_BASE",

    "https://cams-dev.gooroomee.com/api/v1/monitor/room-url"

).rstrip("/")



# 만약 담당자에게 받은 "정확한 단일 URL"이 있다면 여기에 그대로 넣으면 상단 설정 무시하고 이 URL만 사용

FULL_ENDPOINT = os.getenv("FULL_ENDPOINT", "").strip()



# 서버가 POST 외 메서드를 요구하는 경우 강제 지정 (예: "PUT" / "GET"), 기본은 자동 탐색

API_METHOD = os.getenv("API_METHOD", "").strip().upper()



# 필요 시 추가 헤더(JSON) 예: {"x-functions-key":"xxxx", "Authorization":"Bearer ..."}

try:

    EXTRA_HEADERS = json.loads(os.getenv("EXTRA_HEADERS", "{}"))

    if not isinstance(EXTRA_HEADERS, dict):

        EXTRA_HEADERS = {}

except Exception:

    EXTRA_HEADERS = {}



# 로컬 기록

EVENT_HISTORY: List[Dict] = []

JSON_FILE = "activity_log.json"

POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "1.0"))  # 초

LAST_MESSAGES: deque[str] = deque(maxlen=8)

_RNG = random.SystemRandom()



# ======== macOS 프런트 앱/윈도우 감지 ========

def _run_osascript(script: str) -> str:

    return subprocess.run(

        ["osascript", "-e", script],

        capture_output=True,

        text=True,

    ).stdout.strip()



def _host_from_url(url: str) -> str:

    try:

        host = urlparse(url).hostname or ""

        return host.replace("www.", "") if host else "unknown"

    except Exception:

        return "unknown"



def _front_app_and_window() -> Dict[str, str]:

    script = (

        'tell application "System Events"\n'

        'set frontApp to first process whose frontmost is true\n'

        "set appName to name of frontApp\n"

        'set windowName to ""\n'

        "try\n"

        "set windowName to name of front window of frontApp\n"

        "end try\n"

        "end tell\n"

        'return appName & "||" & windowName'

    )

    output = _run_osascript(script)

    parts = output.split("||", 1) if output else []

    return {

        "app": parts[0].strip() if parts else "",

        "window": parts[1].strip() if len(parts) > 1 else "",

    }



def _format_display(app_name: str, window_name: str = "", detail: Optional[str] = None) -> str:

    base = app_name or "unknown"

    if detail:

        return f"{base} · {detail}"

    if window_name and window_name.lower() != base.lower():

        return f"{base} · {window_name}"

    return base



def get_active_snapshot() -> Dict[str, str]:

    if platform.system() != "Darwin":

        return {"app": "unknown", "window": "", "display": "unknown"}

    try:

        front = _front_app_and_window()

        app_name = front.get("app", "") or "unknown"

        window_name = front.get("window", "")

        snapshot: Dict[str, str] = {

            "app": app_name,

            "window": window_name,

        }



        detail: Optional[str] = None

        app_lower = app_name.lower()



        if app_lower == "safari":

            url = _run_osascript('tell application "Safari" to get URL of front document')

            site = _host_from_url(url)

            snapshot["url"] = url

            snapshot["domain"] = site

            detail = site or url

        elif app_lower == "google chrome":

            url = _run_osascript('tell application "Google Chrome" to get URL of active tab of front window')

            site = _host_from_url(url)

            snapshot["url"] = url

            snapshot["domain"] = site

            detail = site or url



        snapshot["display"] = _format_display(app_name, window_name, detail)

        return snapshot

    except Exception as e:

        return {"app": "error", "window": "", "display": f"error({e})"}



def save_events_to_json():

    with open(JSON_FILE, "w", encoding="utf-8") as f:

        json.dump(EVENT_HISTORY, f, ensure_ascii=False, indent=4)



# ======== 유틸: "chrome(notion.so)" → ("chrome","notion.so") ========

def _parse_app(current_app: str) -> tuple[str, str]:

    s = (current_app or "").strip()

    if "(" in s and s.endswith(")"):

        core = s[: s.index("(")].strip()

        site = s[s.index("(") + 1 : -1].strip()

        return core.lower(), site.lower()

    return s.lower(), ""



def _normalize_browser_name(app_name: str) -> str:

    lower = (app_name or "").lower()

    if lower == "google chrome":

        return "chrome"

    if lower == "safari":

        return "safari"

    if lower == "microsoft edge":

        return "edge"

    if lower == "firefox":

        return "firefox"

    return lower



def snapshot_to_current_app_string(snapshot: Dict[str, str]) -> str:

    app_name = snapshot.get("app", "") or "unknown"

    domain = snapshot.get("domain", "") or ""

    browser_core = _normalize_browser_name(app_name)

    if browser_core in {"chrome", "safari", "edge", "firefox"}:

        if domain:

            return f"{browser_core}({domain})"

        return browser_core

    return app_name



# ======== LLM 판정 ========

def step2_llm_signal_and_message(

    current_app: str,

    model: str = "gpt-4o-mini",

    default_on_error: Tuple[int, str] = (1, "LLM 판정 중 문제가 발생했어요. 잠시 후 다시 시도해 주세요."),

) -> Tuple[int, str]:

    def _fallback_classify(app_string: str) -> Tuple[int, str]:

        app_core, site = _parse_app(app_string)

        core = app_core.lower()

        site_l = (site or "").lower()



        games = {

            "lol","league of legends","valorant","steam","battlenet","nexon",

            "maple","lostark","fortnite","roblox","genshin","pubg","minecraft","fifa","fc online",

        }

        study_tools = {

            "vscode","visual studio","pycharm","cursor","slack","microsoft word","notes","apple notes",

            "intellij","android studio","jupyter","colab","notion","obsidian","excel","powerpoint","ppt",

            "pdf","skim","acrobat","postman","figma","miro","xcode","matlab","rstudio","latex",

        }

        study_domains = {

            "notion.so","colab.research.google.com","leetcode.com","github.com","stackoverflow.com",

            "paperswithcode.com","arxiv.org","scholar.google.com","kaggle.com","coursera.org","edx.org",

            "udemy.com","docs.python.org","gooroomee.com","cams-dev.gooroomee.com","cams-dev-plus.gooroomee.com",

        }

        content_domains = {

            "youtube.com","netflix.com","twitch.tv","instagram.com","tiktok.com","spotify.com",

            "music.youtube.com","webtoon.kakao.com","webtoons.com","facebook.com",

        }

        browsers = {"chrome","safari","edge","firefox","google chrome"}



        def _pick(choices: List[str]) -> str:

            shuffled = choices[:]

            _RNG.shuffle(shuffled)

            for c in shuffled:

                if c not in LAST_MESSAGES:

                    return c

            return shuffled[0]



        if core in games:

            return 2, _pick([

                "지금은 집중 시간이에요, 게임은 잠시 접어둘까요?",

                "목표에 맞춰보아요, 게임은 이따 쉬는 시간에 즐겨볼까요?",

                "학습 우선으로 전환해볼까요? 게임은 잠깐 내려두는 게 어때요?",

            ])



        if core in browsers:

            if not site_l:

                return 1, _pick([

                    "현재 탭이 학습과 연결되는지 확인하고 목표 페이지로 이동해볼까요?",

                    "학습 목적의 페이지인지 점검하고 필요한 자료로 전환해볼까요?",

                    "이번 세션 목표와 맞는 탭인지 확인한 뒤 이어가볼까요?",

                ])

            if site_l in study_domains or site_l.endswith(".edu"):

                return 0, _pick([

                    f"{site_l}에서 집중 중이시네요, 20~30분만 더 몰입해볼까요?",

                    f"{site_l} 작업 흐름 좋아요, 지금 리듬 유지해 한 구간 더 가볼까요?",

                    f"{site_l} 학습 괜찮습니다, 잠깐 더 밀고 나가면 좋겠어요.",

                    f"{site_l} 진행 좋아요, 짧은 몰입 구간을 한 번 더 가져볼까요?",

                ])

            if site_l in content_domains:

                return 1, _pick([

                    f"{site_l} 이용 중이네요. 학습 영상/자료라면 이어가고, 아니면 목표로 돌아가볼까요?",

                    f"{site_l}이 학습 목적이라면 괜찮아요, 아니라면 계획한 페이지로 전환해볼까요?",

                    f"{site_l} 콘텐츠가 목표와 맞는지 확인하고 필요한 경우 과제 화면으로 갈까요?",

                    f"{site_l} 시청이 학습에 도움이 되는지 점검하고, 아니면 학습 탭으로 전환해볼까요?",

                ])

            return 1, _pick([

                "현재 페이지가 목표와 연결되는지 확인하고 필요한 자료로 이동해볼까요?",

                "이번 세션 목표에 맞는지 점검하고 과제 화면으로 이어가볼까요?",

                "목표와의 연관성을 확인한 뒤 필요한 경우 학습 탭으로 돌아가볼까요?",

            ])



        if core in study_tools:

            pretty = {"pycharm":"PyCharm","vscode":"VS Code","rstudio":"RStudio","latex":"LaTeX"}.get(core, core.capitalize())

            return 0, _pick([

                f"{pretty}에서 집중 중이시네요, 한 구간 더 몰입해볼까요?",

                f"{pretty} 작업 흐름 좋아요, 20~30분 페이스 유지해볼까요?",

                f"{pretty} 진행 좋습니다, 지금 리듬으로 조금만 더 이어가볼까요?",

                f"{pretty}에서 코드/문서 작업 좋습니다, 짧게 한 토막 더 가볼까요?",

                f"{pretty} 흐름 괜찮아요, 잠깐만 더 밀어붙이고 휴식하실까요?",

            ])



        return 1, _pick([

            "학습 목적이면 이어가고, 아니라면 목표 화면으로 전환해볼까요?",

            "현재 활동이 목표와 맞다면 계속, 아니면 계획한 작업으로 돌아가볼까요?",

            "목표와의 연관성을 확인하고 필요하면 학습 화면으로 넘어가볼까요?",

            "지금 활동이 과제/학습과 맞으면 유지, 아니면 목표로 전환해볼까요?",

        ])



    current_app = str(current_app or "").strip()

    if not current_app:

        return (1, "앱이 감지되지 않았어요. 학습 화면을 열면 바로 체크할게요.")



    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:

        return _fallback_classify(current_app)



    app_core, site = _parse_app(current_app)



    system_prompt = (

        "너는 학습 보조 AI 에이전트다. 입력값(app_core, site)을 기반으로 \"학습 집중도 신호등\"을 판정하고, 한 문장 코멘트를 생성한다.\n\n"

        "【최종 산출물】\n"

        "1) signal: 0(초록) | 1(주황) | 2(빨강)\n"

        "2) message: 한 문장, 존댓말, 18~60자, 과장/반말/감탄사 남발 금지, 이모지 금지\n\n"

        "【우선순위 규칙】 A:게임=2, B:학습=0, C:애매/소비=1\n"

        "브라우저는 site로 판정, site가 비면 1.\n"

        "출력은 오직 JSON: {\"signal\":0|1|2,\"message\":\"...\"}\n"

    )



    user_prompt = {

        "current_app_raw": current_app,

        "app_core": app_core,

        "site": site,

        "time_of_day": datetime.now().strftime("%H:%M"),

        "variation_hint": int(datetime.now().strftime("%M")),

        "recent_messages": list(LAST_MESSAGES),

        "avoid_phrases": list(LAST_MESSAGES),

        "schema": {"signal": "0|1|2", "message": "18~60자, 한 문장, 존댓말"},

    }



    base_url = os.getenv("OPENAI_BASE_URL") or None

    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)

    try:

        resp = client.chat.completions.create(

            model=model,

            temperature=0.6,

            response_format={"type": "json_object"},

            messages=[

                {"role": "system", "content": system_prompt},

                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},

            ],

            timeout=20,

        )

        content = resp.choices[0].message.content or "{}"

        data = json.loads(content)



        raw_signal = data.get("signal", 1)

        try:

            signal = int(raw_signal)

        except Exception:

            signal = 1



        message = str(data.get("message") or "").strip()



        if message in LAST_MESSAGES:

            try:

                user_prompt_retry = {

                    **user_prompt,

                    "variation_hint": (user_prompt["variation_hint"] + 7) % 60,

                    "avoid_phrases": list(LAST_MESSAGES),

                }

                resp2 = client.chat.completions.create(

                    model=model,

                    temperature=0.8,

                    response_format={"type": "json_object"},

                    messages=[

                        {"role": "system", "content": system_prompt},

                        {"role": "user", "content": json.dumps(user_prompt_retry, ensure_ascii=False)},

                    ],

                    timeout=20,

                )

                content2 = resp2.choices[0].message.content or "{}"

                data2 = json.loads(content2)

                message2 = str(data2.get("message") or "").strip()

                if 18 <= len(message2) <= 60 and message2 not in LAST_MESSAGES:

                    message = message2

                    raw_signal2 = data2.get("signal", signal)

                    try:

                        signal = int(raw_signal2)

                    except Exception:

                        pass

            except Exception:

                pass



        if signal not in (0, 1, 2):

            signal = 1

        if not (18 <= len(message) <= 60):

            if signal == 2:

                message = "지금은 공부 시간이에요, 게임은 잠시 접어둘까요?"

            elif signal == 1:

                message = "학습 목적이면 계속 진행하세요, 아니면 목표로 돌아가봐요."

            else:

                message = "좋아요, 이 흐름으로 25분만 더 집중해볼까요?"



        LAST_MESSAGES.append(message)

        return (signal, message)

    except Exception as e:

        print(f"[API ERROR] {e}")

        signal, message = _fallback_classify(current_app)

        LAST_MESSAGES.append(message)

        return signal, message



# ======== 서버 전송 ========

_post_diag_once = False  # 과도 로그 방지



def _signal_to_color(sig: int) -> str:

    return {0: "green", 1: "yellow", 2: "red"}.get(sig, "yellow")



async def _probe_allow(session: aiohttp.ClientSession, url: str) -> Tuple[set, str]:

    try:

        async with session.options(url) as r:

            allow = r.headers.get("Allow", "")

            return {m.strip().upper() for m in allow.split(",") if m.strip()}, allow

    except Exception:

        return set(), ""



def _candidate_urls() -> List[str]:

    if FULL_ENDPOINT:

        return [FULL_ENDPOINT]  # 단일 URL 고정

    room = quote(ROOM_PATH.strip("/"))

    base = API_BASE.rstrip("/")

    return [

        f"{base}/{room}",

        f"{base}/{room}/",

        f"{base}?roomUrl={room}",

    ]



async def _post_signal_to_server_async(app_str: str, signal: int, message: str) -> None:

    global _post_diag_once



    payload = {

        "email": SENDER_EMAIL,

        "color": _signal_to_color(signal),

        "name": app_str,

        "text": message,

    }

    headers = {

        "Accept": "application/json, */*",

        "Content-Type": "application/json; charset=utf-8",

        "User-Agent": "cams-agent/1.0",

        **EXTRA_HEADERS,

    }



    timeout = aiohttp.ClientTimeout(total=6)

    async with aiohttp.ClientSession(timeout=timeout) as session:

        last_err = None

        for url in _candidate_urls():

            allowed, allow_raw = await _probe_allow(session, url)

            if not _post_diag_once:

                print(f"[POST DIAG] URL={url} | Allow={allow_raw or '(none)'} | payload={payload}")

                _post_diag_once = True



            # 호출 메서드 결정

            methods_chain = []

            if API_METHOD:

                methods_chain = [API_METHOD]

            else:

                if allowed:

                    if "POST" in allowed: methods_chain.append("POST")

                    if "GET" in allowed:  methods_chain.append("GET")

                    if "PUT" in allowed:  methods_chain.append("PUT")

                else:

                    # Allow 헤더가 없으면 세 가지 모두 시도

                    methods_chain = ["POST", "GET", "PUT"]



            for method in methods_chain:

                for attempt in range(2):

                    try:

                        if method == "GET":

                            q = (f"{url}"

                                 f"{'&' if '?' in url else '?'}email={quote(SENDER_EMAIL)}"

                                 f"&color={_signal_to_color(signal)}"

                                 f"&name={quote(app_str)}"

                                 f"&text={quote(message)}")

                            async with session.get(q, headers=headers) as resp:

                                text = await resp.text()

                                if resp.status < 400:

                                    return

                                if resp.status == 405:

                                    last_err = f"405 GET {url}: {text}"

                                    break

                                raise RuntimeError(f"HTTP {resp.status} GET {url}: {text}")

                        else:

                            req = session.post if method == "POST" else session.put

                            async with req(url, json=payload, headers=headers) as resp:

                                text = await resp.text()

                                if resp.status < 400:

                                    return

                                if resp.status == 405:

                                    last_err = f"405 {method} {url}: {text}"

                                    break

                                raise RuntimeError(f"HTTP {resp.status} {method} {url}: {text}")

                    except Exception as e:

                        last_err = f"{type(e).__name__} {method} {url}: {e}"

                        await asyncio.sleep(0.4 * (attempt + 1))

                if isinstance(last_err, str) and last_err.startswith("405"):

                    continue  # 다음 메서드

            # 다음 URL 후보

        print(f"[POST ERROR] all candidates failed.\nlast={last_err}\n"

              f"hint: 정적 CDN/스토리지로 라우팅 중일 수 있습니다. 정확한 게이트웨이 URL/메서드/인증 헤더 확인 필요.")



# ======== 최종 JSON 빌더 ========

def build_signal_json_from_snapshot(snapshot: Dict[str, str]) -> Dict[str, object]:

    current_app_str = snapshot_to_current_app_string(snapshot)

    signal, message = step2_llm_signal_and_message(current_app_str)

    return {"app": current_app_str, "signal": signal, "message": message}



# ======== 실행 루프 ========

async def monitor_activity_and_send_on_change():

    prev_display: Optional[str] = None

    while True:

        snapshot = get_active_snapshot()

        current_display = snapshot.get("display", snapshot.get("app", "unknown"))

        if prev_display is None or current_display != prev_display:

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            result = build_signal_json_from_snapshot(snapshot)

            result_with_time = {"time": timestamp, **result}

            print(json.dumps(result_with_time, ensure_ascii=False), flush=True)



            # 로컬 이벤트 로그

            EVENT_HISTORY.append({

                "time": timestamp,

                "from": prev_display,

                "to": current_display,

                "snapshot": snapshot,

                "signal": result["signal"],

                "message": result["message"],

            })

            save_events_to_json()



            # 서버 전송(앱 변경 즉시)

            try:

                await _post_signal_to_server_async(

                    app_str=result["app"],

                    signal=result["signal"],

                    message=result["message"],

                )

            except Exception as e:

                print(f"[POST FATAL] {e}")



            prev_display = current_display

        await asyncio.sleep(POLL_INTERVAL)



async def monitor_activity_and_send_every_tick():

    while True:

        snapshot = get_active_snapshot()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        result = build_signal_json_from_snapshot(snapshot)

        result_with_time = {"time": timestamp, **result}

        print(json.dumps(result_with_time, ensure_ascii=False), flush=True)



        EVENT_HISTORY.append({

            "time": timestamp,

            "from": None,

            "to": snapshot.get("display", snapshot.get("app", "unknown")),

            "snapshot": snapshot,

            "signal": result["signal"],

            "message": result["message"],

        })

        save_events_to_json()



        try:

            await _post_signal_to_server_async(

                app_str=result["app"],

                signal=result["signal"],

                message=result["message"],

            )

        except Exception as e:

            print(f"[POST FATAL] {e}")



        await asyncio.sleep(POLL_INTERVAL)



def run_once_and_print_json():

    snapshot = get_active_snapshot()

    result = build_signal_json_from_snapshot(snapshot)

    print(json.dumps(result, ensure_ascii=False))



# ======== 엔트리 포인트 ========

# 메인 실행은 main.py를 사용하세요
# if __name__ == "__main__":
#     mode = (os.getenv("MODE") or "monitor").lower()
#     if mode == "once":
#         run_once_and_print_json()
#     elif mode == "tick":
#         asyncio.run(monitor_activity_and_send_every_tick())
#     else:
#         asyncio.run(monitor_activity_and_send_on_change())

