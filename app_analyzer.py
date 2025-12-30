# -*- coding: utf-8 -*-
"""
앱 사용 데이터 분석 모듈
- activity_log.json에서 데이터 읽기
- 앱별 사용 시간 및 비율 계산
- 학습 앱 사용률(signal 0 비율) 계산
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict


class AppAnalyzer:
    """앱 사용 데이터 분석기"""

    def __init__(self, json_file: str = "activity_log.json"):
        """
        Args:
            json_file: 이벤트 로그 JSON 파일 경로
        """
        self.json_file = json_file
        self.events: List[Dict] = []
        self._load_events()

    def _load_events(self):
        """이벤트 로그 파일 로드"""
        if not os.path.exists(self.json_file):
            print(f"[WARN] {self.json_file} 파일이 없습니다.")
            self.events = []
            return

        try:
            with open(self.json_file, "r", encoding="utf-8") as f:
                data = f.read().strip()
                if not data:
                    self.events = []
                    return

                # JSON 배열 형태로 파싱
                self.events = json.loads(data)
                if not isinstance(self.events, list):
                    self.events = [self.events] if self.events else []

            print(f"[INFO] {len(self.events)}개의 이벤트 로드 완료")

            # 이벤트 형식 확인 (출력 형식 또는 저장 형식)
            if self.events:
                sample = self.events[0]
                if "app" in sample:
                    print("[INFO] 출력 형식 감지: {'time', 'app', 'signal', 'message'}")
                elif "snapshot" in sample:
                    print("[INFO] 저장 형식 감지: {'time', 'snapshot', 'signal', 'message'}")

        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON 파싱 오류: {e}")
            self.events = []
        except Exception as e:
            print(f"[ERROR] 파일 읽기 오류: {e}")
            self.events = []

    def get_app_usage_statistics(self) -> List[Dict[str, float]]:
        """
        앱별 사용 시간 및 비율 계산

        Returns:
            [
                {"appName": "Chrome", "usageTime": 3600, "percentage": 60.0},
                ...
            ]
        """
        # 최신 데이터 로드
        self._load_events()

        if not self.events or len(self.events) < 2:
            return []

        # 시간 파싱 및 정렬
        try:
            events_with_time = []
            for event in self.events:
                if "time" not in event:
                    continue

                try:
                    time_obj = datetime.strptime(event["time"], "%Y-%m-%d %H:%M:%S")
                    events_with_time.append((time_obj, event))
                except Exception:
                    continue

            if len(events_with_time) < 2:
                return []

            # 시간순 정렬
            events_with_time.sort(key=lambda x: x[0])

            # 앱별 사용 시간 집계 (초 단위)
            app_time_dict = defaultdict(float)
            total_time_seconds = 0.0

            for i in range(len(events_with_time) - 1):
                time1, event1 = events_with_time[i]
                time2, event2 = events_with_time[i + 1]

                # 시간 차이 계산 (초)
                time_diff = (time2 - time1).total_seconds()
                if time_diff <= 0:
                    continue

                # 해당 이벤트의 앱 이름 추출
                # 출력 형식: {"time": "...", "app": "...", "signal": 1, "message": "..."}
                # 저장 형식: {"time": "...", "snapshot": {...}, "signal": 1, "message": "..."}
                if "app" in event1:
                    # 직접 app 필드가 있는 경우 (출력 형식)
                    app_name = event1.get("app", "")
                else:
                    # snapshot에서 추출하는 경우 (저장 형식)
                    snapshot = event1.get("snapshot", {})
                    app_name = self._extract_app_name(snapshot)

                if app_name:
                    app_time_dict[app_name] += time_diff
                    total_time_seconds += time_diff

            # 마지막 이벤트도 처리 (마지막으로부터 이전 이벤트까지의 시간)
            if len(events_with_time) >= 2:
                time_last, event_last = events_with_time[-1]
                time_prev, event_prev = events_with_time[-2]
                time_diff = (time_last - time_prev).total_seconds()

                # 마지막 이벤트의 앱 이름 추출
                if "app" in event_last:
                    app_name = event_last.get("app", "")
                else:
                    snapshot = event_last.get("snapshot", {})
                    app_name = self._extract_app_name(snapshot)

                if app_name and time_diff > 0:
                    app_time_dict[app_name] += time_diff
                    total_time_seconds += time_diff

            if total_time_seconds == 0:
                return []

            # 비율 계산 및 정렬
            app_usages = []
            for app_name, usage_time in app_time_dict.items():
                percentage = (usage_time / total_time_seconds) * 100.0
                app_usages.append({
                    "appName": app_name,
                    "usageTime": int(usage_time),
                    "percentage": round(percentage, 2)
                })

            # 비율 내림차순 정렬
            app_usages.sort(key=lambda x: x["percentage"], reverse=True)

            return app_usages

        except Exception as e:
            print(f"[ERROR] 앱 사용 통계 계산 오류: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_learning_app_usage_rate(self) -> float:
        """
        학습 앱 사용률 계산 (signal 0 비율)

        Returns:
            학습 앱 사용률 (0.0 ~ 100.0)
        """
        # 최신 데이터 로드
        self._load_events()

        if not self.events or len(self.events) < 2:
            return 0.0

        try:
            events_with_time = []
            for event in self.events:
                if "time" not in event:
                    continue

                try:
                    time_obj = datetime.strptime(event["time"], "%Y-%m-%d %H:%M:%S")
                    events_with_time.append((time_obj, event))
                except Exception:
                    continue

            if len(events_with_time) < 2:
                return 0.0

            events_with_time.sort(key=lambda x: x[0])

            total_time_seconds = 0.0
            learning_time_seconds = 0.0

            for i in range(len(events_with_time) - 1):
                time1, event1 = events_with_time[i]
                time2, event2 = events_with_time[i + 1]

                time_diff = (time2 - time1).total_seconds()
                if time_diff <= 0:
                    continue

                # signal 확인 (0이면 학습 앱)
                signal = event1.get("signal", 1)
                if signal == 0:
                    learning_time_seconds += time_diff

                total_time_seconds += time_diff

            # 마지막 이벤트 처리
            if len(events_with_time) >= 2:
                time_last, event_last = events_with_time[-1]
                time_prev, event_prev = events_with_time[-2]
                time_diff = (time_last - time_prev).total_seconds()

                if time_diff > 0:
                    signal = event_last.get("signal", 1)
                    if signal == 0:
                        learning_time_seconds += time_diff
                    total_time_seconds += time_diff

            if total_time_seconds == 0:
                return 0.0

            learning_rate = (learning_time_seconds / total_time_seconds) * 100.0
            return round(learning_rate, 2)

        except Exception as e:
            print(f"[ERROR] 학습 앱 사용률 계산 오류: {e}")
            import traceback
            traceback.print_exc()
            return 0.0

    def get_total_study_time_seconds(self) -> float:
        """
        총 학습 시간 계산 (초 단위)

        Returns:
            총 학습 시간 (초)
        """
        if not self.events or len(self.events) < 2:
            return 0.0

        try:
            events_with_time = []
            for event in self.events:
                if "time" not in event:
                    continue

                try:
                    time_obj = datetime.strptime(event["time"], "%Y-%m-%d %H:%M:%S")
                    events_with_time.append(time_obj)
                except Exception:
                    continue

            if len(events_with_time) < 2:
                return 0.0

            events_with_time.sort()

            # 첫 이벤트와 마지막 이벤트의 시간 차이
            total_seconds = (events_with_time[-1] - events_with_time[0]).total_seconds()
            return max(0.0, total_seconds)

        except Exception as e:
            print(f"[ERROR] 총 학습 시간 계산 오류: {e}")
            return 0.0

    def _extract_app_name(self, snapshot: Dict) -> str:
        """
        스냅샷에서 앱 이름 추출

        Args:
            snapshot: 이벤트의 snapshot 딕셔너리

        Returns:
            앱 이름 문자열 (예: "chrome(notion.so)")
        """
        if not snapshot:
            return "unknown"

        # snapshot에 "app" 키가 있으면 직접 사용
        app = snapshot.get("app", "")

        # domain이 있으면 "app(domain)" 형식으로
        domain = snapshot.get("domain", "")

        if domain:
            # 브라우저 앱 이름 정규화
            app_lower = app.lower()
            if app_lower == "google chrome":
                return f"chrome({domain})"
            elif app_lower == "safari":
                return f"safari({domain})"
            elif app_lower == "microsoft edge":
                return f"edge({domain})"
            elif app_lower == "firefox":
                return f"firefox({domain})"
            else:
                return f"{app}({domain})" if app else domain
        else:
            # 앱 이름만
            app_lower = app.lower()
            if app_lower == "google chrome":
                return "chrome"
            elif app_lower == "safari":
                return "safari"
            elif app_lower == "microsoft edge":
                return "edge"
            elif app_lower == "firefox":
                return "firefox"
            else:
                return app if app else "unknown"
