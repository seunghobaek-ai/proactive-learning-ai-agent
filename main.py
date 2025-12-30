# -*- coding: utf-8 -*-
"""
구루미 캠스터디 종료 결과 API - 메인 실행 파일
- app_monitor.py와 finish_api_server.py를 함께 실행
- 한 번의 실행으로 앱 감지와 API 서버가 모두 시작됩니다
"""

import asyncio
import threading
import sys
import os
from pathlib import Path

# 프로젝트 루트 경로를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def run_app_monitor():
    """app_monitor.py를 백그라운드에서 실행"""
    print("[앱 감지] app_monitor.py 시작 중...")
    
    # app_monitor.py의 모니터링 함수를 직접 import하여 실행
    try:
        from app_monitor import monitor_activity_and_send_on_change
        
        # asyncio 이벤트 루프를 새 스레드에서 실행
        def run_async():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(monitor_activity_and_send_on_change())
            except KeyboardInterrupt:
                print("\n[앱 감지] 종료 중...")
            finally:
                loop.close()
        
        monitor_thread = threading.Thread(target=run_async, daemon=True)
        monitor_thread.start()
        print("[앱 감지] ✅ 앱 감지 프로그램이 백그라운드에서 실행 중입니다")
        return monitor_thread
        
    except Exception as e:
        print(f"[앱 감지] ❌ 오류 발생: {e}")
        print("[앱 감지] ⚠️  앱 감지 없이 서버만 실행됩니다")
        return None


def run_api_server():
    """finish_api_server.py의 API 서버 실행"""
    print("[API 서버] finish_api_server.py 시작 중...")
    
    try:
        import uvicorn
        from finish_api_server import app
        
        print("\n" + "=" * 60)
        print("구루미 캠스터디 종료 결과 API 서버 (FastAPI)")
        print("=" * 60)
        print("포트: 8080")
        print("엔드포인트: http://localhost:8080/finish?time={총학습시간(초)}")
        print("API 문서: http://localhost:8080/docs")
        print("헬스체크: http://localhost:8080/health")
        print("=" * 60)
        print("\n[서버 시작] 브라우저에서 접속을 기다리는 중...\n")
        
        # 서버 실행 (메인 스레드에서 실행)
        uvicorn.run(app, host="0.0.0.0", port=8080)
        
    except KeyboardInterrupt:
        print("\n[API 서버] 종료 중...")
    except Exception as e:
        print(f"[API 서버] ❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


def main():
    """메인 함수 - 앱 감지와 API 서버를 함께 실행"""
    print("=" * 60)
    print("구루미 캠스터디 종료 결과 API - 통합 실행")
    print("=" * 60)
    print()
    
    # 1. 앱 감지 프로그램 시작 (백그라운드)
    monitor_thread = run_app_monitor()
    
    # 잠시 대기 (앱 감지 초기화 시간)
    import time
    time.sleep(1)
    
    # 2. API 서버 시작 (메인 스레드)
    print()
    run_api_server()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[종료] 프로그램을 종료합니다...")
        sys.exit(0)

