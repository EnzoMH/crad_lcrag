"""
AI 에이전트 시스템 - Chain 서비스 통합 인터페이스

이 모듈은 ChainManager와 ChainPipeline을 통합하여
사용자가 쉽게 활용할 수 있는 고수준 API를 제공합니다.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass

from .chain_manager import (
    ChainManager, ChainConfig, ChainResult, ChainType,
    PREDEFINED_CHAIN_CONFIGS, get_predefined_chain_config
)
from .chain_pipeline import (
    ChainPipeline, PipelineConfig, PipelineResult,
    PIPELINE_TEMPLATES, get_pipeline_template
)
from ..config.gemini_client import GeminiClient
from ..config.prompt_manager import PromptManager


@dataclass
class ChainServiceConfig:
    """Chain 서비스 설정"""
    enable_auto_cleanup: bool = True        # 자동 정리 활성화
    cleanup_interval_hours: int = 24        # 정리 주기 (시간)
    max_concurrent_executions: int = 10     # 최대 동시 실행 수
    default_timeout: float = 300.0          # 기본 타임아웃 (초)
    enable_caching: bool = True             # 결과 캐싱 활성화
    cache_ttl_seconds: int = 3600          # 캐시 TTL (초)
    log_level: str = "INFO"                # 로그 레벨


class ChainService:
    """Chain 서비스 통합 클래스"""
    
    def __init__(self, gemini_client: GeminiClient, prompt_manager: PromptManager,
                 config: Optional[ChainServiceConfig] = None):
        """
        Chain 서비스 초기화
        
        Args:
            gemini_client: Gemini 클라이언트
            prompt_manager: 프롬프트 관리자
            config: 서비스 설정
        """
        self.config = config or ChainServiceConfig()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, self.config.log_level))
        
        # 핵심 컴포넌트 초기화
        self.chain_manager = ChainManager(gemini_client, prompt_manager)
        self.chain_pipeline = ChainPipeline(self.chain_manager)
        
        # 실행 제어
        self.execution_semaphore = asyncio.Semaphore(self.config.max_concurrent_executions)
        
        # 결과 캐시 (간단한 메모리 캐시)
        self.result_cache: Dict[str, Dict[str, Any]] = {}
        
        # 자동 정리 태스크
        self.cleanup_task: Optional[asyncio.Task] = None
        
        self.logger.info("ChainService 초기화 완료")
    
    async def initialize(self):
        """서비스 초기화 (비동기 작업)"""
        try:
            # 사전 정의된 체인들 자동 생성
            await self._setup_predefined_chains()
            
            # 사전 정의된 파이프라인들 자동 등록
            await self._setup_predefined_pipelines()
            
            # 자동 정리 시작
            if self.config.enable_auto_cleanup:
                await self._start_auto_cleanup()
            
            self.logger.info("ChainService 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"ChainService 초기화 오류: {str(e)}")
            raise e
    
    async def _setup_predefined_chains(self):
        """사전 정의된 체인들 설정"""
        self.logger.info("사전 정의된 체인들 생성 중...")
        
        for chain_name, chain_config in PREDEFINED_CHAIN_CONFIGS.items():
            success = await self.chain_manager.create_chain(chain_name, chain_config)
            if success:
                self.logger.info(f"체인 생성 완료: {chain_name}")
            else:
                self.logger.warning(f"체인 생성 실패: {chain_name}")
    
    async def _setup_predefined_pipelines(self):
        """사전 정의된 파이프라인들 설정"""
        self.logger.info("사전 정의된 파이프라인들 등록 중...")
        
        for template_name in PIPELINE_TEMPLATES.keys():
            pipeline_config = get_pipeline_template(template_name)
            if pipeline_config:
                success = self.chain_pipeline.register_pipeline(pipeline_config)
                if success:
                    self.logger.info(f"파이프라인 등록 완료: {template_name}")
                else:
                    self.logger.warning(f"파이프라인 등록 실패: {template_name}")
    
    async def _start_auto_cleanup(self):
        """자동 정리 태스크 시작"""
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(self.config.cleanup_interval_hours * 3600)
                    await self._cleanup_resources()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"자동 정리 오류: {str(e)}")
        
        self.cleanup_task = asyncio.create_task(cleanup_loop())
        self.logger.info("자동 정리 태스크 시작")
    
    async def _cleanup_resources(self):
        """리소스 정리"""
        # 비활성 체인 정리
        deleted_chains = await self.chain_manager.cleanup_inactive_chains(
            self.config.cleanup_interval_hours
        )
        
        # 캐시 정리
        if self.config.enable_caching:
            current_time = datetime.now()
            expired_keys = []
            
            for cache_key, cache_data in self.result_cache.items():
                cache_time = cache_data.get("timestamp")
                if cache_time:
                    age = (current_time - cache_time).total_seconds()
                    if age > self.config.cache_ttl_seconds:
                        expired_keys.append(cache_key)
            
            for key in expired_keys:
                del self.result_cache[key]
            
            if expired_keys:
                self.logger.info(f"캐시 정리 완료: {len(expired_keys)}개 항목 삭제")
        
        if deleted_chains > 0:
            self.logger.info(f"리소스 정리 완료: 체인 {deleted_chains}개 삭제")
    
    # === Chain 관리 API ===
    
    async def create_chain(self, chain_id: str, chain_config: Union[ChainConfig, str]) -> bool:
        """
        새 체인 생성
        
        Args:
            chain_id: 체인 고유 ID
            chain_config: 체인 설정 또는 사전 정의된 체인 이름
            
        Returns:
            생성 성공 여부
        """
        if isinstance(chain_config, str):
            # 사전 정의된 체인 설정 사용
            predefined_config = get_predefined_chain_config(chain_config)
            if not predefined_config:
                self.logger.error(f"사전 정의된 체인을 찾을 수 없음: {chain_config}")
                return False
            chain_config = predefined_config
        
        return await self.chain_manager.create_chain(chain_id, chain_config)
    
    async def execute_chain(self, chain_id: str, input_data: Dict[str, Any],
                          use_cache: bool = True, **kwargs) -> ChainResult:
        """
        체인 실행
        
        Args:
            chain_id: 실행할 체인 ID
            input_data: 입력 데이터
            use_cache: 캐시 사용 여부
            **kwargs: 추가 실행 옵션
            
        Returns:
            체인 실행 결과
        """
        # 캐시 확인
        cache_key = None
        if self.config.enable_caching and use_cache:
            cache_key = self._generate_cache_key(chain_id, input_data)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self.logger.info(f"캐시된 결과 반환: {chain_id}")
                return cached_result
        
        # 동시 실행 제어
        async with self.execution_semaphore:
            result = await self.chain_manager.execute_chain(chain_id, input_data, **kwargs)
        
        # 성공한 결과 캐싱
        if (self.config.enable_caching and use_cache and 
            result.success and cache_key):
            self._cache_result(cache_key, result)
        
        return result
    
    async def execute_batch_chains(self, batch_requests: List[Dict[str, Any]],
                                 use_cache: bool = True) -> List[ChainResult]:
        """
        배치 체인 실행
        
        Args:
            batch_requests: 배치 요청 목록
            use_cache: 캐시 사용 여부
            
        Returns:
            배치 실행 결과 목록
        """
        # 캐시된 결과와 실행 필요한 요청 분리
        cached_results = {}
        pending_requests = []
        
        if self.config.enable_caching and use_cache:
            for i, request in enumerate(batch_requests):
                cache_key = self._generate_cache_key(
                    request["chain_id"], 
                    request["input_data"]
                )
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_results[i] = cached_result
                else:
                    pending_requests.append((i, request))
        else:
            pending_requests = list(enumerate(batch_requests))
        
        # 남은 요청들 실행
        pending_results = {}
        if pending_requests:
            requests_only = [req[1] for req in pending_requests]
            results = await self.chain_manager.execute_batch_chains(requests_only)
            
            for (i, request), result in zip(pending_requests, results):
                pending_results[i] = result
                
                # 성공한 결과 캐싱
                if (self.config.enable_caching and use_cache and result.success):
                    cache_key = self._generate_cache_key(
                        request["chain_id"], 
                        request["input_data"]
                    )
                    self._cache_result(cache_key, result)
        
        # 최종 결과 조합
        final_results = []
        for i in range(len(batch_requests)):
            if i in cached_results:
                final_results.append(cached_results[i])
            else:
                final_results.append(pending_results[i])
        
        return final_results
    
    def get_chain_info(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """체인 정보 조회"""
        return self.chain_manager.get_chain_info(chain_id)
    
    def list_active_chains(self) -> List[Dict[str, Any]]:
        """활성 체인 목록 조회"""
        return self.chain_manager.list_active_chains()
    
    def delete_chain(self, chain_id: str) -> bool:
        """체인 삭제"""
        return self.chain_manager.delete_chain(chain_id)
    
    # === Pipeline 관리 API ===
    
    def register_pipeline(self, pipeline_config: Union[PipelineConfig, str]) -> bool:
        """
        파이프라인 등록
        
        Args:
            pipeline_config: 파이프라인 설정 또는 템플릿 이름
            
        Returns:
            등록 성공 여부
        """
        if isinstance(pipeline_config, str):
            # 템플릿 사용
            template_config = get_pipeline_template(pipeline_config)
            if not template_config:
                self.logger.error(f"파이프라인 템플릿을 찾을 수 없음: {pipeline_config}")
                return False
            pipeline_config = template_config
        
        return self.chain_pipeline.register_pipeline(pipeline_config)
    
    async def execute_pipeline(self, pipeline_id: str, initial_input: Dict[str, Any],
                             use_cache: bool = True, **kwargs) -> PipelineResult:
        """
        파이프라인 실행
        
        Args:
            pipeline_id: 실행할 파이프라인 ID
            initial_input: 초기 입력 데이터
            use_cache: 캐시 사용 여부
            **kwargs: 추가 실행 옵션
            
        Returns:
            파이프라인 실행 결과
        """
        # 캐시 확인
        cache_key = None
        if self.config.enable_caching and use_cache:
            cache_key = self._generate_cache_key(f"pipeline_{pipeline_id}", initial_input)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                self.logger.info(f"캐시된 파이프라인 결과 반환: {pipeline_id}")
                return cached_result
        
        # 동시 실행 제어
        async with self.execution_semaphore:
            result = await self.chain_pipeline.execute_pipeline(
                pipeline_id, initial_input, **kwargs
            )
        
        # 성공한 결과 캐싱
        if (self.config.enable_caching and use_cache and 
            result.success and cache_key):
            self._cache_result(cache_key, result)
        
        return result
    
    def get_pipeline_info(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """파이프라인 정보 조회"""
        return self.chain_pipeline.get_pipeline_info(pipeline_id)
    
    def list_active_pipelines(self) -> List[Dict[str, Any]]:
        """활성 파이프라인 목록 조회"""
        return self.chain_pipeline.list_active_pipelines()
    
    def delete_pipeline(self, pipeline_id: str) -> bool:
        """파이프라인 삭제"""
        return self.chain_pipeline.delete_pipeline(pipeline_id)
    
    # === 통계 및 모니터링 ===
    
    def get_service_stats(self) -> Dict[str, Any]:
        """서비스 통계 조회"""
        chain_stats = self.chain_manager.get_execution_stats()
        pipeline_stats = self.chain_pipeline.get_pipeline_stats()
        
        return {
            "chains": {
                "active_count": len(self.chain_manager.active_chains),
                "execution_stats": chain_stats
            },
            "pipelines": {
                "active_count": len(self.chain_pipeline.active_pipelines),
                "execution_stats": pipeline_stats
            },
            "cache": {
                "enabled": self.config.enable_caching,
                "size": len(self.result_cache),
                "ttl_seconds": self.config.cache_ttl_seconds
            },
            "config": {
                "max_concurrent": self.config.max_concurrent_executions,
                "auto_cleanup": self.config.enable_auto_cleanup,
                "cleanup_interval_hours": self.config.cleanup_interval_hours
            }
        }
    
    def get_health_status(self) -> Dict[str, Any]:
        """서비스 상태 확인"""
        try:
            active_chains = len(self.chain_manager.active_chains)
            active_pipelines = len(self.chain_pipeline.active_pipelines)
            cache_size = len(self.result_cache)
            
            # 기본 상태 정보
            status = {
                "healthy": True,
                "timestamp": datetime.now().isoformat(),
                "components": {
                    "chain_manager": {
                        "status": "healthy",
                        "active_chains": active_chains
                    },
                    "pipeline_manager": {
                        "status": "healthy", 
                        "active_pipelines": active_pipelines
                    },
                    "cache": {
                        "status": "healthy",
                        "size": cache_size
                    }
                }
            }
            
            # 자동 정리 태스크 상태
            if self.cleanup_task:
                status["components"]["auto_cleanup"] = {
                    "status": "running" if not self.cleanup_task.done() else "stopped"
                }
            
            return status
            
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    # === 캐시 관리 ===
    
    def _generate_cache_key(self, identifier: str, data: Dict[str, Any]) -> str:
        """캐시 키 생성"""
        import hashlib
        import json
        
        # 데이터를 정렬하여 일관된 해시 생성
        sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        hash_obj = hashlib.md5(f"{identifier}:{sorted_data}".encode('utf-8'))
        return hash_obj.hexdigest()
    
    def _get_cached_result(self, cache_key: str) -> Optional[Union[ChainResult, PipelineResult]]:
        """캐시된 결과 조회"""
        if cache_key in self.result_cache:
            cache_data = self.result_cache[cache_key]
            cache_time = cache_data.get("timestamp")
            
            if cache_time:
                age = (datetime.now() - cache_time).total_seconds()
                if age <= self.config.cache_ttl_seconds:
                    return cache_data.get("result")
                else:
                    # 만료된 캐시 삭제
                    del self.result_cache[cache_key]
        
        return None
    
    def _cache_result(self, cache_key: str, result: Union[ChainResult, PipelineResult]):
        """결과 캐싱"""
        self.result_cache[cache_key] = {
            "result": result,
            "timestamp": datetime.now()
        }
    
    def clear_cache(self) -> int:
        """캐시 전체 삭제"""
        count = len(self.result_cache)
        self.result_cache.clear()
        self.logger.info(f"캐시 전체 삭제: {count}개 항목")
        return count
    
    def clear_cache_by_pattern(self, pattern: str) -> int:
        """패턴 매칭으로 캐시 삭제"""
        import re
        
        regex = re.compile(pattern)
        keys_to_delete = [key for key in self.result_cache.keys() if regex.search(key)]
        
        for key in keys_to_delete:
            del self.result_cache[key]
        
        self.logger.info(f"패턴 캐시 삭제: {len(keys_to_delete)}개 항목 (패턴: {pattern})")
        return len(keys_to_delete)
    
    # === 고급 기능 ===
    
    async def warmup_chains(self, chain_ids: List[str], 
                          sample_input: Dict[str, Any]) -> Dict[str, bool]:
        """
        체인 워밍업 (초기 실행으로 준비 상태 만들기)
        
        Args:
            chain_ids: 워밍업할 체인 ID 목록
            sample_input: 샘플 입력 데이터
            
        Returns:
            체인별 워밍업 성공 여부
        """
        results = {}
        
        for chain_id in chain_ids:
            try:
                result = await self.execute_chain(chain_id, sample_input, use_cache=False)
                results[chain_id] = result.success
                self.logger.info(f"체인 워밍업 {'성공' if result.success else '실패'}: {chain_id}")
            except Exception as e:
                results[chain_id] = False
                self.logger.error(f"체인 워밍업 오류 {chain_id}: {str(e)}")
        
        return results
    
    async def benchmark_chains(self, chain_ids: List[str],
                             sample_input: Dict[str, Any],
                             iterations: int = 5) -> Dict[str, Dict[str, float]]:
        """
        체인 성능 벤치마크
        
        Args:
            chain_ids: 벤치마크할 체인 ID 목록
            sample_input: 샘플 입력 데이터
            iterations: 반복 횟수
            
        Returns:
            체인별 성능 통계
        """
        benchmark_results = {}
        
        for chain_id in chain_ids:
            execution_times = []
            success_count = 0
            
            for i in range(iterations):
                try:
                    result = await self.execute_chain(chain_id, sample_input, use_cache=False)
                    execution_times.append(result.execution_time)
                    if result.success:
                        success_count += 1
                except Exception as e:
                    self.logger.error(f"벤치마크 오류 {chain_id}: {str(e)}")
            
            if execution_times:
                benchmark_results[chain_id] = {
                    "avg_time": sum(execution_times) / len(execution_times),
                    "min_time": min(execution_times),
                    "max_time": max(execution_times),
                    "success_rate": success_count / iterations,
                    "total_iterations": iterations
                }
        
        return benchmark_results
    
    # === 라이프사이클 관리 ===
    
    async def shutdown(self):
        """서비스 종료"""
        try:
            # 자동 정리 태스크 중단
            if self.cleanup_task and not self.cleanup_task.done():
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # 리소스 정리
            await self._cleanup_resources()
            
            self.logger.info("ChainService 종료 완료")
            
        except Exception as e:
            self.logger.error(f"ChainService 종료 오류: {str(e)}")


# 편의 함수들
async def create_chain_service(gemini_client: GeminiClient, 
                             prompt_manager: PromptManager,
                             config: Optional[ChainServiceConfig] = None) -> ChainService:
    """
    Chain 서비스 생성 및 초기화
    
    Args:
        gemini_client: Gemini 클라이언트
        prompt_manager: 프롬프트 관리자
        config: 서비스 설정
        
    Returns:
        초기화된 Chain 서비스
    """
    service = ChainService(gemini_client, prompt_manager, config)
    await service.initialize()
    return service 