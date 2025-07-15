"""
⚡ API 요청 제한 관리 시스템

Gemini API의 RPM(분당 요청수) 및 TPM(분당 토큰수) 제한을 관리
- 토큰 버킷 알고리즘 사용
- 멀티 API 키 지원
- 실시간 사용량 추적
"""

import time
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from collections import deque
from threading import Lock

from loguru import logger


@dataclass
class RateLimitConfig:
    """요청 제한 설정"""
    rpm_limit: int = 2000  # 분당 요청 제한
    tpm_limit: int = 4000000  # 분당 토큰 제한
    burst_limit: int = 100  # 버스트 허용 한도
    window_size: int = 60  # 시간 윈도우 (초)


@dataclass
class TokenBucket:
    """토큰 버킷"""
    capacity: int
    tokens: float = field(default_factory=lambda: 0)
    last_refill: float = field(default_factory=time.time)
    refill_rate: float = field(default=1.0)  # 초당 토큰 보충률
    
    def __post_init__(self):
        self.tokens = self.capacity
        self.refill_rate = self.capacity / 60.0  # 분당 용량을 초당으로 변환


class RateLimiter:
    """
    ⚡ API 요청 제한 관리자
    
    Features:
    - 토큰 버킷 알고리즘
    - 멀티 API 키 지원
    - 실시간 사용량 추적
    - 자동 토큰 보충
    """
    
    def __init__(self, config: RateLimitConfig = None):
        """
        RateLimiter 초기화
        
        Args:
            config: 요청 제한 설정
        """
        self.config = config or RateLimitConfig()
        
        # API 키별 토큰 버킷
        self.request_buckets: Dict[str, TokenBucket] = {}
        self.token_buckets: Dict[str, TokenBucket] = {}
        
        # 요청 히스토리 (윈도우 기반 추적)
        self.request_history: Dict[str, deque] = {}
        self.token_history: Dict[str, deque] = {}
        
        # 스레드 안전성을 위한 락
        self.lock = Lock()
        
        logger.info(f"⚡ RateLimiter 초기화 - RPM: {self.config.rpm_limit}, TPM: {self.config.tpm_limit}")
    
    def _get_or_create_buckets(self, api_key: str) -> tuple[TokenBucket, TokenBucket]:
        """API 키에 대한 토큰 버킷 생성 또는 반환"""
        with self.lock:
            if api_key not in self.request_buckets:
                self.request_buckets[api_key] = TokenBucket(
                    capacity=self.config.rpm_limit,
                    refill_rate=self.config.rpm_limit / 60.0
                )
                
                self.token_buckets[api_key] = TokenBucket(
                    capacity=self.config.tpm_limit,
                    refill_rate=self.config.tpm_limit / 60.0
                )
                
                self.request_history[api_key] = deque(maxlen=self.config.rpm_limit)
                self.token_history[api_key] = deque(maxlen=self.config.tpm_limit)
                
                logger.debug(f"🔧 API 키 {api_key[:10]}... 토큰 버킷 생성")
            
            return self.request_buckets[api_key], self.token_buckets[api_key]
    
    def _refill_bucket(self, bucket: TokenBucket):
        """토큰 버킷 보충"""
        current_time = time.time()
        time_passed = current_time - bucket.last_refill
        
        # 보충할 토큰 수 계산
        tokens_to_add = time_passed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + tokens_to_add)
        bucket.last_refill = current_time
    
    def _check_window_limit(self, api_key: str, estimated_tokens: int = 1) -> bool:
        """윈도우 기반 제한 확인"""
        current_time = time.time()
        window_start = current_time - self.config.window_size
        
        # 요청 히스토리 정리
        request_history = self.request_history[api_key]
        while request_history and request_history[0] < window_start:
            request_history.popleft()
        
        # 토큰 히스토리 정리
        token_history = self.token_history[api_key]
        while token_history and token_history[0]['timestamp'] < window_start:
            token_history.popleft()
        
        # 현재 윈도우 내 사용량 계산
        current_requests = len(request_history)
        current_tokens = sum(entry['tokens'] for entry in token_history)
        
        # 제한 확인
        if current_requests >= self.config.rpm_limit:
            logger.warning(f"⚠️ API 키 {api_key[:10]}... RPM 제한 초과: {current_requests}/{self.config.rpm_limit}")
            return False
        
        if current_tokens + estimated_tokens > self.config.tpm_limit:
            logger.warning(f"⚠️ API 키 {api_key[:10]}... TPM 제한 초과: {current_tokens + estimated_tokens}/{self.config.tpm_limit}")
            return False
        
        return True
    
    async def acquire_permission(
        self,
        api_key: str,
        estimated_tokens: int = 1,
        timeout: float = 10.0
    ) -> bool:
        """
        요청 허가 획득
        
        Args:
            api_key: API 키
            estimated_tokens: 예상 토큰 수
            timeout: 타임아웃 (초)
            
        Returns:
            허가 여부
        """
        start_time = time.time()
        
        # 토큰 버킷 가져오기
        request_bucket, token_bucket = self._get_or_create_buckets(api_key)
        
        while time.time() - start_time < timeout:
            with self.lock:
                # 토큰 버킷 보충
                self._refill_bucket(request_bucket)
                self._refill_bucket(token_bucket)
                
                # 윈도우 기반 제한 확인
                if not self._check_window_limit(api_key, estimated_tokens):
                    await asyncio.sleep(0.1)
                    continue
                
                # 토큰 버킷 확인
                if request_bucket.tokens >= 1 and token_bucket.tokens >= estimated_tokens:
                    # 토큰 소비
                    request_bucket.tokens -= 1
                    token_bucket.tokens -= estimated_tokens
                    
                    # 히스토리 업데이트
                    current_time = time.time()
                    self.request_history[api_key].append(current_time)
                    self.token_history[api_key].append({
                        'timestamp': current_time,
                        'tokens': estimated_tokens
                    })
                    
                    logger.debug(f"✅ 요청 허가 승인: {api_key[:10]}... (토큰: {estimated_tokens})")
                    return True
            
            # 잠시 대기
            await asyncio.sleep(0.1)
        
        logger.warning(f"⏰ 요청 허가 타임아웃: {api_key[:10]}...")
        return False
    
    def get_usage_stats(self, api_key: str) -> Dict[str, Any]:
        """API 키별 사용량 통계"""
        if api_key not in self.request_buckets:
            return {
                "requests_available": self.config.rpm_limit,
                "tokens_available": self.config.tpm_limit,
                "requests_used": 0,
                "tokens_used": 0,
                "usage_rate": 0.0
            }
        
        request_bucket, token_bucket = self._get_or_create_buckets(api_key)
        
        # 토큰 버킷 보충
        self._refill_bucket(request_bucket)
        self._refill_bucket(token_bucket)
        
        # 현재 윈도우 내 사용량 계산
        current_time = time.time()
        window_start = current_time - self.config.window_size
        
        recent_requests = [
            req for req in self.request_history[api_key]
            if req > window_start
        ]
        
        recent_tokens = sum(
            entry['tokens'] for entry in self.token_history[api_key]
            if entry['timestamp'] > window_start
        )
        
        return {
            "requests_available": int(request_bucket.tokens),
            "tokens_available": int(token_bucket.tokens),
            "requests_used": len(recent_requests),
            "tokens_used": recent_tokens,
            "usage_rate": len(recent_requests) / self.config.rpm_limit,
            "request_bucket_capacity": request_bucket.capacity,
            "token_bucket_capacity": token_bucket.capacity
        }
    
    def get_all_usage_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 API 키의 사용량 통계"""
        stats = {}
        
        for api_key in self.request_buckets.keys():
            key_id = api_key[:10] + "..."
            stats[key_id] = self.get_usage_stats(api_key)
        
        return stats
    
    def reset_limits(self, api_key: str = None):
        """제한 초기화"""
        if api_key:
            # 특정 API 키 초기화
            if api_key in self.request_buckets:
                self.request_buckets[api_key].tokens = self.request_buckets[api_key].capacity
                self.token_buckets[api_key].tokens = self.token_buckets[api_key].capacity
                self.request_history[api_key].clear()
                self.token_history[api_key].clear()
                logger.info(f"🔄 API 키 {api_key[:10]}... 제한 초기화")
        else:
            # 모든 API 키 초기화
            for key in self.request_buckets.keys():
                self.reset_limits(key)
            logger.info("🔄 모든 API 키 제한 초기화")
    
    async def wait_for_availability(
        self,
        api_key: str,
        estimated_tokens: int = 1,
        max_wait: float = 60.0
    ) -> float:
        """
        사용 가능할 때까지 대기
        
        Args:
            api_key: API 키
            estimated_tokens: 예상 토큰 수
            max_wait: 최대 대기 시간 (초)
            
        Returns:
            대기 시간 (초)
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if await self.acquire_permission(api_key, estimated_tokens, timeout=0.1):
                return time.time() - start_time
            
            await asyncio.sleep(0.5)
        
        raise TimeoutError(f"⏰ API 키 {api_key[:10]}... 최대 대기 시간 초과")
    
    def estimate_tokens(self, text: str) -> int:
        """텍스트의 토큰 수 추정"""
        # 간단한 추정 (실제로는 더 정확한 토큰화 필요)
        return max(1, len(text) // 4)
    
    def get_best_available_key(self, api_keys: list[str], estimated_tokens: int = 1) -> Optional[str]:
        """가장 사용 가능한 API 키 반환"""
        best_key = None
        best_score = -1
        
        for api_key in api_keys:
            stats = self.get_usage_stats(api_key)
            
            # 사용 가능한지 확인
            if (stats["requests_available"] >= 1 and 
                stats["tokens_available"] >= estimated_tokens):
                
                # 점수 계산 (사용률이 낮을수록 좋음)
                score = (1 - stats["usage_rate"]) * stats["requests_available"]
                
                if score > best_score:
                    best_score = score
                    best_key = api_key
        
        return best_key
    
    async def health_check(self) -> Dict[str, Any]:
        """시스템 상태 확인"""
        total_keys = len(self.request_buckets)
        healthy_keys = 0
        
        key_status = {}
        
        for api_key in self.request_buckets.keys():
            key_id = api_key[:10] + "..."
            stats = self.get_usage_stats(api_key)
            
            is_healthy = (
                stats["requests_available"] > 0 and
                stats["tokens_available"] > 0 and
                stats["usage_rate"] < 0.9
            )
            
            if is_healthy:
                healthy_keys += 1
                key_status[key_id] = "healthy"
            else:
                key_status[key_id] = "overloaded"
        
        # 전체 상태 결정
        if healthy_keys == 0:
            overall_status = "critical"
        elif healthy_keys < total_keys * 0.5:
            overall_status = "warning"
        else:
            overall_status = "healthy"
        
        return {
            "status": overall_status,
            "healthy_keys": healthy_keys,
            "total_keys": total_keys,
            "key_status": key_status,
            "config": {
                "rpm_limit": self.config.rpm_limit,
                "tpm_limit": self.config.tpm_limit,
                "window_size": self.config.window_size
            }
        } 