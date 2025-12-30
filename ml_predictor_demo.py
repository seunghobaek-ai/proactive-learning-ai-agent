# -*- coding: utf-8 -*-
"""
시연을 위한 머신러닝 합격/불합격 판정 모듈
- 실제 ML 모델 대신 간단한 규칙 기반 판정 사용
- 시연 목적으로 빠르고 명확한 결과 제공
"""

from typing import Dict


class MLPredictorDemo:
    """시연용 머신러닝 합격/불합격 판정기"""
    
    def __init__(self):
        """
        시연용 판정기 초기화
        실제 모델 파일이 필요 없음
        """
        print("[INFO] 시연용 ML 판정기 초기화 완료")
    
    def predict(self, total_time_minutes: float, green_ratio: float) -> Dict[str, bool]:
        """
        합격/불합격 예측 (시연용)
        
        기준:
        - 총 학습 시간: 1분 이상
        - 초록색(signal 0) 비율: 80% 이상
        - 두 조건을 동시에 만족해야 합격
        
        Args:
            total_time_minutes: 총 이용시간 (분)
            green_ratio: 초록불 비율 (0.0 ~ 1.0)
        
        Returns:
            {"passed": True/False}
        """
        # 기준 1: 총 학습 시간 1분 이상
        min_time_met = total_time_minutes >= 1.0
        
        # 기준 2: 초록색 비율 80% 이상
        min_green_ratio_met = green_ratio >= 0.8
        
        # 두 조건 모두 만족해야 합격
        passed = min_time_met and min_green_ratio_met
        
        return {"passed": passed}

