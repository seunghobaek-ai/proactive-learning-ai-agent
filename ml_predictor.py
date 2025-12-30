# -*- coding: utf-8 -*-
"""
머신러닝 합격/불합격 판정 모듈
- model.pkl 파일에서 모델 로드
- (총 이용시간[분], 초록불비율) 특징으로 예측
"""

import os
import pickle
import numpy as np
from typing import Dict, Optional


class MLPredictor:
    """머신러닝 합격/불합격 판정기"""
    
    def __init__(self, model_file: str = "model.pkl"):
        """
        Args:
            model_file: 모델 파일 경로 (.pkl)
        """
        self.model_file = model_file
        self.model = None
        self.scaler = None
        self._load_model()
    
    def _load_model(self):
        """모델 및 스케일러 로드"""
        if not os.path.exists(self.model_file):
            print(f"[WARN] {self.model_file} 파일이 없습니다.")
            return
        
        try:
            with open(self.model_file, "rb") as f:
                obj = pickle.load(f)
            
            # 모델 저장 형식에 따라 분기
            if isinstance(obj, dict):
                self.model = obj.get("model")
                self.scaler = obj.get("scaler", None)
            else:
                self.model = obj
                self.scaler = None
            
            if self.model is None:
                raise RuntimeError(f"{self.model_file}에서 'model'을 찾을 수 없습니다.")
            
            print(f"[INFO] 모델 로드 완료: {self.model_file}")
            if self.scaler:
                print("[INFO] 스케일러도 함께 로드됨")
                
        except Exception as e:
            print(f"[ERROR] 모델 로드 오류: {e}")
            import traceback
            traceback.print_exc()
            self.model = None
            self.scaler = None
    
    def predict(self, total_time_minutes: float, green_ratio: float) -> Dict[str, bool]:
        """
        합격/불합격 예측
        
        Args:
            total_time_minutes: 총 이용시간 (분)
            green_ratio: 초록불 비율 (0.0 ~ 1.0)
        
        Returns:
            {"passed": True/False}
        """
        if self.model is None:
            # 모델이 없으면 기본 규칙 기반 판정
            passed = (total_time_minutes >= 30) and (green_ratio >= 0.7)
            return {"passed": passed}
        
        try:
            # 특징 벡터 생성
            X = np.array([[total_time_minutes, green_ratio]], dtype=float)
            
            # 스케일러 적용 (있으면)
            if self.scaler is not None:
                X = self.scaler.transform(X)
            
            # 예측
            y = self.model.predict(X)[0]
            
            # "합격/불합격"으로 변환
            passed = self._to_pass_fail(y)
            
            return {"passed": passed}
            
        except Exception as e:
            print(f"[ERROR] 예측 오류: {e}")
            import traceback
            traceback.print_exc()
            
            # 오류 시 기본 규칙 기반 판정
            passed = (total_time_minutes >= 30) and (green_ratio >= 0.7)
            return {"passed": passed}
    
    def _to_pass_fail(self, pred) -> bool:
        """
        예측 결과를 합격/불합격으로 변환
        
        Args:
            pred: 모델 예측 결과 (str, int, bool 등)
        
        Returns:
            True (합격) 또는 False (불합격)
        """
        if isinstance(pred, str):
            s = pred.strip().lower()
            return ("합격" in s or s in {"pass", "passed", "ok", "success"})
        
        # int나 bool인 경우
        return (pred == 1 or pred is True)

