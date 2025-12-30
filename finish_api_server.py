# -*- coding: utf-8 -*-
"""
구루미 캠스터디 종료 결과 API 서버 (FastAPI)
- localhost:8080에서 실행
- GET /finish?time={총학습시간(초)} 엔드포인트 제공
- CORS 설정 포함
- 자동 API 문서: http://localhost:8080/docs
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app_analyzer import AppAnalyzer
# 시연용 판정기 사용 (나중에 실제 ML 모델 사용 시 아래 주석 해제하고 위 주석 처리)
from ml_predictor_demo import MLPredictorDemo
# from ml_predictor import MLPredictor  # 실제 ML 모델 사용 시 주석 해제

# ======== FastAPI 앱 초기화 ========
app = FastAPI(
    title="구루미 캠스터디 종료 결과 API",
    description="스터디 종료 시 학습 결과를 분석하여 제공하는 REST API",
    version="1.0.0"
)

# CORS 설정 - 구루미 도메인 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://cams-dev.gooroomee.com",
        "https://cams-dev-plus.gooroomee.com",
        "https://gooroomee.com",
        "http://localhost:8089",  # 로컬 개발
        "http://127.0.0.1:8089"
    ],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
)

# ======== 전역 변수 ========
JSON_FILE = "activity_log.json"  # 모니터링 프로그램이 저장하는 파일
MODEL_FILE = "model.pkl"  # 머신러닝 모델 파일

# 전역 분석기 인스턴스
app_analyzer: Optional[AppAnalyzer] = None
ml_predictor = None  # MLPredictorDemo 또는 MLPredictor


def init_analyzers():
    """분석기 초기화"""
    global app_analyzer, ml_predictor
    
    try:
        app_analyzer = AppAnalyzer(JSON_FILE)
    except Exception as e:
        print(f"[WARN] AppAnalyzer 초기화 실패: {e}")
        app_analyzer = None
    
    # 시연용 판정기 사용
    try:
        ml_predictor = MLPredictorDemo()
    except Exception as e:
        print(f"[WARN] MLPredictorDemo 초기화 실패: {e}")
        ml_predictor = None
    
    # 실제 ML 모델 사용 시 아래 주석 해제하고 위 코드 주석 처리
    # try:
    #     ml_predictor = MLPredictor(MODEL_FILE)
    # except Exception as e:
    #     print(f"[WARN] MLPredictor 초기화 실패: {e}")
    #     ml_predictor = None


# ======== API 엔드포인트 ========
@app.get("/finish", response_model=Dict)
def finish(
    time: int = Query(..., description="총 학습 시간 (초 단위)", gt=0)
):
    """
    스터디 종료 결과 조회 API
    
    Args:
        time: 총 학습 시간 (초 단위) - 구루미에서 받은 값
    
    Returns:
        JSON:
        {
            "appUsages": [
                {"appName": "Chrome", "usageTime": 3600, "percentage": 60.0},
                ...
            ],
            "studyResult": {
                "passed": true/false,
                "totalStudyTime": 6000,
                "learningAppTime": 5400,
                "learningRate": 90.0,
                "message": "수고하셨습니다! 목표를 달성했어요 🎉"
            }
        }
    """
    try:
        total_study_time_seconds = time
        
        # 앱 사용 분석
        app_usages = []
        if app_analyzer:
            try:
                app_usages = app_analyzer.get_app_usage_statistics()
            except Exception as e:
                print(f"[ERROR] 앱 사용 분석 실패: {e}")
                app_usages = []
        else:
            print("[WARN] AppAnalyzer가 초기화되지 않음")
        
        # 학습 앱 사용률 계산 (signal 0 비율)
        learning_rate = 0.0
        learning_app_time = 0
        if app_analyzer:
            try:
                learning_rate = app_analyzer.get_learning_app_usage_rate()
                # 학습 시간 중 학습 앱 사용 시간 계산
                learning_app_time = int(total_study_time_seconds * learning_rate / 100.0)
            except Exception as e:
                print(f"[ERROR] 학습 앱 사용률 계산 실패: {e}")
        
        # 머신러닝 합격/불합격 판정 (ml_predictor_demo 사용)
        passed = False
        message = "학습 통계 데이터를 분석 중입니다..."
        
        if ml_predictor:
            try:
                # ml_predictor_demo의 predict 메서드로 판정 (초기화된 인스턴스 재사용)
                total_time_minutes = total_study_time_seconds / 60.0
                green_ratio = learning_rate / 100.0
                
                prediction_result = ml_predictor.predict(total_time_minutes, green_ratio)
                passed = prediction_result.get("passed", False)
                
                # 메시지 생성 (합격/불합격 모두)
                if passed:
                    messages = [
                        "수고하셨습니다! 목표를 달성했어요 🎉",
                        "훌륭한 학습이었습니다! 계속 이 페이스로 가요!",
                        "완벽한 집중력을 보여주셨어요. 멋져요!",
                        "목표 달성 성공! 다음에도 화이팅! 💪"
                    ]
                    message = messages[hash(str(total_study_time_seconds)) % len(messages)]
                else:
                    # 불합격 메시지
                    messages = [
                        "아쉬워요. 다음엔 더 집중해봐요! 💪",
                        "목표까지 조금 더 남았어요. 조금만 더 힘내봐요!",
                        "오늘도 노력하셨지만, 내일은 더 좋은 결과를 기대해요!",
                        "다음엔 학습 앱에 더 집중해보면 좋을 것 같아요."
                    ]
                    message = messages[hash(str(total_study_time_seconds)) % len(messages)]
                    
            except Exception as e:
                print(f"[ERROR] ML 판정 실패: {e}")
                import traceback
                traceback.print_exc()
                # 에러 발생 시 기본값
                passed = False
                message = "판정 중 오류가 발생했습니다."
        else:
            # ml_predictor가 초기화되지 않은 경우
            print("[ERROR] MLPredictorDemo가 초기화되지 않았습니다.")
            passed = False
            message = "판정 시스템을 사용할 수 없습니다."
        
        # 응답 데이터 구성
        response_data = {
            "appUsages": app_usages,
            "studyResult": {
                "passed": passed,
                "totalStudyTime": total_study_time_seconds,
                "learningAppTime": learning_app_time,
                "learningRate": round(learning_rate, 2),
                "message": message
            }
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] /finish 엔드포인트 오류: {e}")
        import traceback
        traceback.print_exc()
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "결과 분석 중 오류가 발생했습니다.",
                "appUsages": [],
                "studyResult": {
                    "passed": False,
                    "totalStudyTime": time,
                    "learningAppTime": 0,
                    "learningRate": 0.0,
                    "message": "데이터 분석 중 오류가 발생했습니다."
                }
            }
        )


@app.get("/health", response_model=Dict)
def health():
    """헬스 체크 엔드포인트"""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "app_analyzer": "ok" if app_analyzer else "not_initialized",
        "ml_predictor": "ok" if ml_predictor else "not_initialized"
    }


# ======== 서버 시작 ========
@app.on_event("startup")
async def startup_event():
    """서버 시작 시 실행"""
    print("=" * 60)
    print("구루미 캠스터디 종료 결과 API 서버 (FastAPI)")
    print("=" * 60)
    print("포트: 8080")
    print("엔드포인트: http://localhost:8080/finish?time={총학습시간(초)}")
    print("API 문서: http://localhost:8080/docs")
    print("헬스체크: http://localhost:8080/health")
    print("=" * 60)
    
    # 분석기 초기화
    print("\n[초기화] 분석기 로딩 중...")
    init_analyzers()
    
    if app_analyzer:
        print(f"[OK] AppAnalyzer 초기화 완료")
    else:
        print(f"[WARN] AppAnalyzer 초기화 실패 - activity_log.json 파일 확인 필요")
    
    if ml_predictor:
        print(f"[OK] MLPredictorDemo (시연용) 초기화 완료")
    else:
        print(f"[WARN] MLPredictorDemo 초기화 실패")
    
    print("\n[서버 시작] 브라우저에서 접속을 기다리는 중...\n")


# 메인 실행은 main.py를 사용하세요
# if __name__ == '__main__':
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8080)
