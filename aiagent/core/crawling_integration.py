"""
🔗 크롤링 시스템 - AI 에이전트 통합 모듈

기존 크롤링 시스템(main_crawler.py)과 AI 에이전트 시스템을 통합하여
지능형 크롤링 워크플로우를 제공합니다.

주요 기능:
- 기존 크롤링 엔진과 AI 에이전트 연결
- 지능형 크롤링 전략 수립
- 실시간 성능 최적화
- AI 기반 데이터 검증 및 보강
- 통합 모니터링 및 리포팅
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque
import logging
import concurrent.futures
from pathlib import Path

from loguru import logger

from .agent_system import AIAgentSystem, SystemConfig
from .coordinator import AgentCoordinator, WorkflowDefinition, WorkflowTask, WorkflowType
from .performance_monitor import PerformanceMonitor, MetricType, AlertLevel
from .monitoring_integration import MonitoringIntegration
from .gcp_optimization_service import GCPOptimizationService
from ..agents.contact_agent import ContactAgent, ContactTarget, ContactInfo
from ..agents.search_strategy_agent import SearchStrategyAgent, SearchTarget, SearchMethod
from ..agents.validation_agent import ValidationAgent, ValidationTarget
from ..config.gemini_client import GeminiClient
from ..config.prompt_manager import PromptManager


class CrawlingStrategy(Enum):
    """크롤링 전략 유형"""
    CONSERVATIVE = "conservative"    # 보수적 전략 (안정성 우선)
    BALANCED = "balanced"           # 균형 전략 (성능/안정성 균형)
    AGGRESSIVE = "aggressive"       # 적극적 전략 (성능 우선)
    AI_ADAPTIVE = "ai_adaptive"     # AI 적응형 전략 (상황별 최적화)


class CrawlingPhase(Enum):
    """크롤링 단계"""
    PLANNING = "planning"           # 전략 수립
    DISCOVERY = "discovery"         # 대상 발견
    EXTRACTION = "extraction"       # 데이터 추출
    VALIDATION = "validation"       # 데이터 검증
    ENRICHMENT = "enrichment"       # 데이터 보강
    OPTIMIZATION = "optimization"   # 성능 최적화


@dataclass
class CrawlingTarget:
    """크롤링 대상 정의"""
    id: str                          # 고유 식별자
    name: str                        # 기관명
    category: str                    # 카테고리 (교회, 학원 등)
    existing_data: Dict[str, Any] = field(default_factory=dict)   # 기존 데이터
    target_urls: List[str] = field(default_factory=list)         # 대상 URL 목록
    search_keywords: List[str] = field(default_factory=list)     # 검색 키워드
    priority: int = 1                # 우선순위 (1: 높음, 3: 낮음)
    expected_fields: List[str] = field(default_factory=list)     # 예상 필드
    crawling_config: Dict[str, Any] = field(default_factory=dict) # 크롤링 설정


@dataclass
class CrawlingResult:
    """크롤링 결과"""
    target_id: str                   # 대상 ID
    success: bool                    # 성공 여부
    extracted_data: Dict[str, Any] = field(default_factory=dict) # 추출된 데이터
    confidence_score: float = 0.0    # 신뢰도 점수
    source_urls: List[str] = field(default_factory=list)        # 소스 URL
    processing_time: float = 0.0     # 처리 시간
    validation_results: Dict[str, Any] = field(default_factory=dict) # 검증 결과
    enrichment_results: Dict[str, Any] = field(default_factory=dict) # 보강 결과
    errors: List[str] = field(default_factory=list)             # 오류 목록
    metadata: Dict[str, Any] = field(default_factory=dict)      # 메타데이터


@dataclass
class CrawlingJobConfig:
    """크롤링 작업 설정"""
    job_id: str                      # 작업 ID
    targets: List[CrawlingTarget]    # 크롤링 대상 목록
    strategy: CrawlingStrategy = CrawlingStrategy.BALANCED       # 크롤링 전략
    max_concurrent: int = 5          # 최대 동시 처리 수
    timeout_per_target: int = 120    # 대상당 타임아웃 (초)
    enable_ai_validation: bool = True # AI 검증 활성화
    enable_enrichment: bool = True   # 데이터 보강 활성화
    enable_optimization: bool = True # 성능 최적화 활성화
    retry_failed: bool = True        # 실패 시 재시도
    max_retries: int = 3             # 최대 재시도 횟수
    save_intermediate: bool = True   # 중간 결과 저장
    output_format: str = "json"      # 출력 형식
    custom_settings: Dict[str, Any] = field(default_factory=dict) # 사용자 정의 설정


@dataclass
class CrawlingJobStatus:
    """크롤링 작업 상태"""
    job_id: str                      # 작업 ID
    status: str = "pending"          # 상태
    total_targets: int = 0           # 전체 대상 수
    completed_targets: int = 0       # 완료된 대상 수
    failed_targets: int = 0          # 실패한 대상 수
    success_rate: float = 0.0        # 성공률
    average_processing_time: float = 0.0 # 평균 처리 시간
    total_processing_time: float = 0.0   # 총 처리 시간
    started_at: Optional[datetime] = None    # 시작 시간
    completed_at: Optional[datetime] = None  # 완료 시간
    current_phase: CrawlingPhase = CrawlingPhase.PLANNING # 현재 단계
    ai_agent_stats: Dict[str, Any] = field(default_factory=dict) # AI 에이전트 통계
    performance_metrics: Dict[str, Any] = field(default_factory=dict) # 성능 메트릭
    optimization_results: Dict[str, Any] = field(default_factory=dict) # 최적화 결과
    results: List[CrawlingResult] = field(default_factory=list) # 결과 목록


class CrawlingAgentIntegration:
    """
    🔗 크롤링 시스템 - AI 에이전트 통합 클래스
    
    기능:
    - 기존 크롤링 엔진과 AI 에이전트 연결
    - 지능형 크롤링 워크플로우 실행
    - 실시간 성능 최적화
    - 통합 모니터링 및 리포팅
    """
    
    def __init__(
        self,
        agent_system: AIAgentSystem,
        performance_monitor: PerformanceMonitor,
        monitoring_integration: MonitoringIntegration,
        gcp_optimization_service: Optional[GCPOptimizationService] = None
    ):
        """
        크롤링 에이전트 통합 시스템 초기화
        
        Args:
            agent_system: AI 에이전트 시스템
            performance_monitor: 성능 모니터
            monitoring_integration: 통합 모니터링
            gcp_optimization_service: GCP 최적화 서비스
        """
        self.agent_system = agent_system
        self.performance_monitor = performance_monitor
        self.monitoring_integration = monitoring_integration
        self.gcp_optimization_service = gcp_optimization_service
        
        # 전용 에이전트들 초기화
        self._initialize_specialized_agents()
        
        # 워크플로우 정의
        self._setup_crawling_workflows()
        
        # 작업 관리
        self.active_jobs: Dict[str, CrawlingJobStatus] = {}
        self.job_history: deque = deque(maxlen=1000)
        
        # 성능 추적
        self.performance_stats = {
            "total_jobs": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "average_job_duration": 0.0,
            "total_targets_processed": 0,
            "ai_agent_usage_stats": {},
            "optimization_improvements": []
        }
        
        # 스레드 풀 실행자 (레거시 크롤링 시스템 호출용)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)
        
        logger.info("🔗 크롤링 에이전트 통합 시스템 초기화 완료")
    
    def _initialize_specialized_agents(self):
        """전용 에이전트들 초기화"""
        try:
            # ContactAgent 초기화
            contact_config = self.agent_system._create_agent_config(
                name="CrawlingContactAgent",
                description="크롤링 통합용 연락처 추출 에이전트",
                max_concurrent_requests=10,
                request_timeout=60.0
            )
            self.contact_agent = ContactAgent(contact_config)
            
            # SearchStrategyAgent 초기화
            strategy_config = self.agent_system._create_agent_config(
                name="CrawlingStrategyAgent", 
                description="크롤링 통합용 검색 전략 에이전트",
                max_concurrent_requests=5,
                request_timeout=30.0
            )
            self.strategy_agent = SearchStrategyAgent(strategy_config)
            
            # ValidationAgent 초기화  
            validation_config = self.agent_system._create_agent_config(
                name="CrawlingValidationAgent",
                description="크롤링 통합용 데이터 검증 에이전트",
                max_concurrent_requests=8,
                request_timeout=45.0
            )
            self.validation_agent = ValidationAgent(validation_config)
            
            logger.info("✅ 전용 에이전트들 초기화 완료")
            
        except Exception as e:
            logger.error(f"❌ 전용 에이전트 초기화 실패: {e}")
            raise e
    
    def _setup_crawling_workflows(self):
        """크롤링 워크플로우 설정"""
        try:
            # 지능형 크롤링 워크플로우 정의
            intelligent_crawling_workflow = WorkflowDefinition(
                id="intelligent_crawling",
                name="지능형 크롤링 워크플로우",
                description="AI 에이전트 기반 지능형 크롤링 파이프라인",
                workflow_type=WorkflowType.PIPELINE,
                tasks=[
                    WorkflowTask(
                        id="strategy_planning",
                        agent_type="SearchStrategyAgent",
                        input_data={"operation": "generate_crawling_strategy"},
                        priority=1
                    ),
                    WorkflowTask(
                        id="legacy_crawling",
                        agent_type="LegacyCrawlerProxy",
                        input_data={"operation": "execute_main_crawler"},
                        dependencies=["strategy_planning"],
                        priority=2
                    ),
                    WorkflowTask(
                        id="ai_contact_extraction",
                        agent_type="ContactAgent",
                        input_data={"operation": "extract_and_enrich_contacts"},
                        dependencies=["legacy_crawling"],
                        priority=3
                    ),
                    WorkflowTask(
                        id="data_validation",
                        agent_type="ValidationAgent",
                        input_data={"operation": "validate_crawled_data"},
                        dependencies=["ai_contact_extraction"],
                        priority=4
                    ),
                    WorkflowTask(
                        id="performance_optimization",
                        agent_type="OptimizerAgent",
                        input_data={"operation": "optimize_crawling_performance"},
                        dependencies=["data_validation"],
                        priority=5
                    )
                ],
                global_timeout=1800,  # 30분
                failure_policy="partial_continue"
            )
            
            # 워크플로우 등록
            self.agent_system.coordinator.workflow_definitions[intelligent_crawling_workflow.id] = intelligent_crawling_workflow
            
            logger.info("✅ 크롤링 워크플로우 설정 완료")
            
        except Exception as e:
            logger.error(f"❌ 크롤링 워크플로우 설정 실패: {e}")
            raise e
    
    async def start_intelligent_crawling_job(
        self,
        config: CrawlingJobConfig
    ) -> CrawlingJobStatus:
        """
        지능형 크롤링 작업 시작
        
        Args:
            config: 크롤링 작업 설정
            
        Returns:
            CrawlingJobStatus: 작업 상태
        """
        job_status = CrawlingJobStatus(
            job_id=config.job_id,
            status="running",
            total_targets=len(config.targets),
            started_at=datetime.now(),
            current_phase=CrawlingPhase.PLANNING
        )
        
        self.active_jobs[config.job_id] = job_status
        
        try:
            logger.info(f"🚀 지능형 크롤링 작업 시작: {config.job_id}")
            
            # 1단계: AI 기반 전략 수립
            job_status.current_phase = CrawlingPhase.PLANNING
            strategy_result = await self._plan_crawling_strategy(config)
            
            # 2단계: 대상 발견 및 URL 최적화
            job_status.current_phase = CrawlingPhase.DISCOVERY
            discovery_result = await self._discover_crawling_targets(config, strategy_result)
            
            # 3단계: 지능형 데이터 추출
            job_status.current_phase = CrawlingPhase.EXTRACTION
            extraction_results = await self._execute_intelligent_extraction(config, discovery_result)
            
            # 4단계: AI 기반 데이터 검증
            job_status.current_phase = CrawlingPhase.VALIDATION
            validation_results = await self._validate_extracted_data(config, extraction_results)
            
            # 5단계: 데이터 보강 및 최적화
            job_status.current_phase = CrawlingPhase.ENRICHMENT
            enrichment_results = await self._enrich_and_optimize_data(config, validation_results)
            
            # 6단계: 성능 최적화 및 리포팅
            job_status.current_phase = CrawlingPhase.OPTIMIZATION
            optimization_results = await self._optimize_and_report(config, enrichment_results)
            
            # 최종 결과 정리
            job_status.results = optimization_results
            job_status.completed_targets = len([r for r in optimization_results if r.success])
            job_status.failed_targets = len([r for r in optimization_results if not r.success])
            job_status.success_rate = job_status.completed_targets / job_status.total_targets if job_status.total_targets > 0 else 0
            job_status.completed_at = datetime.now()
            job_status.total_processing_time = (job_status.completed_at - job_status.started_at).total_seconds()
            job_status.status = "completed"
            
            # 통계 업데이트
            self._update_performance_stats(job_status)
            
            # 작업 히스토리에 저장
            self.job_history.append(job_status)
            if config.job_id in self.active_jobs:
                del self.active_jobs[config.job_id]
            
            logger.info(f"✅ 지능형 크롤링 작업 완료: {config.job_id} (성공률: {job_status.success_rate:.1%})")
            
            return job_status
            
        except Exception as e:
            job_status.status = "failed"
            job_status.completed_at = datetime.now()
            logger.error(f"❌ 지능형 크롤링 작업 실패: {config.job_id} - {str(e)}")
            
            # 실패한 작업도 히스토리에 저장
            self.job_history.append(job_status)
            if config.job_id in self.active_jobs:
                del self.active_jobs[config.job_id]
            
            return job_status
    
    async def _plan_crawling_strategy(
        self,
        config: CrawlingJobConfig
    ) -> Dict[str, Any]:
        """AI 기반 크롤링 전략 수립"""
        try:
            # SearchStrategyAgent를 통한 전략 수립
            strategy_input = {
                "targets": [
                    {
                        "name": target.name,
                        "category": target.category,
                        "existing_data": target.existing_data,
                        "target_urls": target.target_urls,
                        "search_keywords": target.search_keywords
                    }
                    for target in config.targets
                ],
                "strategy_type": config.strategy.value,
                "constraints": {
                    "max_concurrent": config.max_concurrent,
                    "timeout_per_target": config.timeout_per_target,
                    "enable_ai_validation": config.enable_ai_validation
                }
            }
            
            strategy_result = await self.strategy_agent.process(strategy_input)
            
            if strategy_result.success:
                logger.info(f"✅ AI 크롤링 전략 수립 완료: {len(config.targets)}개 대상")
                return strategy_result.data
            else:
                logger.warning(f"⚠️ AI 전략 수립 실패, 기본 전략 사용: {strategy_result.error}")
                return self._generate_fallback_strategy(config)
                
        except Exception as e:
            logger.error(f"❌ 크롤링 전략 수립 오류: {str(e)}")
            return self._generate_fallback_strategy(config)
    
    async def _discover_crawling_targets(
        self,
        config: CrawlingJobConfig,
        strategy_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """대상 발견 및 URL 최적화"""
        try:
            discovery_results = []
            
            # 각 대상에 대해 URL 발견 및 최적화
            for target in config.targets:
                # 기존 URL 검증 및 새로운 URL 발견
                target_urls = target.target_urls.copy()
                
                # AI 기반 추가 URL 발견
                if strategy_result.get("enable_url_discovery", True):
                    additional_urls = await self._discover_additional_urls(target, strategy_result)
                    target_urls.extend(additional_urls)
                
                # URL 우선순위 설정
                prioritized_urls = await self._prioritize_urls(target, target_urls, strategy_result)
                
                discovery_results.append({
                    "target_id": target.id,
                    "original_urls": target.target_urls,
                    "discovered_urls": target_urls,
                    "prioritized_urls": prioritized_urls,
                    "crawling_order": prioritized_urls[:strategy_result.get("max_urls_per_target", 10)]
                })
            
            logger.info(f"✅ 대상 발견 완료: {len(discovery_results)}개 대상, 평균 {sum(len(r['discovered_urls']) for r in discovery_results)/len(discovery_results):.1f}개 URL")
            
            return {
                "discovery_results": discovery_results,
                "total_urls_found": sum(len(r['discovered_urls']) for r in discovery_results),
                "strategy_applied": strategy_result
            }
            
        except Exception as e:
            logger.error(f"❌ 대상 발견 오류: {str(e)}")
            # 기본 대상 반환
            return {
                "discovery_results": [
                    {
                        "target_id": target.id,
                        "original_urls": target.target_urls,
                        "discovered_urls": target.target_urls,
                        "prioritized_urls": target.target_urls,
                        "crawling_order": target.target_urls
                    }
                    for target in config.targets
                ],
                "total_urls_found": sum(len(target.target_urls) for target in config.targets),
                "strategy_applied": strategy_result
            }
    
    async def _execute_intelligent_extraction(
        self,
        config: CrawlingJobConfig,
        discovery_result: Dict[str, Any]
    ) -> List[CrawlingResult]:
        """지능형 데이터 추출 실행"""
        try:
            extraction_results = []
            
            # 세마포어로 동시 처리 제한
            semaphore = asyncio.Semaphore(config.max_concurrent)
            
            # 각 대상에 대해 병렬 추출
            tasks = []
            for target, discovery_info in zip(config.targets, discovery_result["discovery_results"]):
                task = self._extract_target_data_with_semaphore(
                    semaphore, target, discovery_info, config
                )
                tasks.append(task)
            
            # 병렬 실행
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"❌ 대상 추출 실패: {config.targets[i].id} - {str(result)}")
                    extraction_results.append(CrawlingResult(
                        target_id=config.targets[i].id,
                        success=False,
                        errors=[str(result)]
                    ))
                else:
                    extraction_results.append(result)
            
            successful_extractions = len([r for r in extraction_results if r.success])
            logger.info(f"✅ 지능형 데이터 추출 완료: {successful_extractions}/{len(extraction_results)}개 성공")
            
            return extraction_results
            
        except Exception as e:
            logger.error(f"❌ 지능형 데이터 추출 오류: {str(e)}")
            # 기본 오류 결과 반환
            return [
                CrawlingResult(
                    target_id=target.id,
                    success=False,
                    errors=[str(e)]
                )
                for target in config.targets
            ]
    
    async def _extract_target_data_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        target: CrawlingTarget,
        discovery_info: Dict[str, Any],
        config: CrawlingJobConfig
    ) -> CrawlingResult:
        """세마포어 제어하에 개별 대상 데이터 추출"""
        async with semaphore:
            return await self._extract_single_target_data(target, discovery_info, config)
    
    async def _extract_single_target_data(
        self,
        target: CrawlingTarget,
        discovery_info: Dict[str, Any],
        config: CrawlingJobConfig
    ) -> CrawlingResult:
        """개별 대상 데이터 추출"""
        start_time = time.time()
        
        try:
            result = CrawlingResult(
                target_id=target.id,
                success=False
            )
            
            # 1. 레거시 크롤링 시스템 실행 (main_crawler.py 시뮬레이션)
            legacy_data = await self._execute_legacy_crawler(target, discovery_info)
            
            # 2. AI 기반 연락처 추출 및 보강
            ai_contact_data = await self._extract_ai_contacts(target, legacy_data, discovery_info)
            
            # 3. 데이터 병합 및 정리
            merged_data = self._merge_extraction_data(legacy_data, ai_contact_data, target.existing_data)
            
            # 결과 설정
            result.success = True
            result.extracted_data = merged_data
            result.source_urls = discovery_info.get("crawling_order", [])
            result.processing_time = time.time() - start_time
            result.confidence_score = self._calculate_confidence_score(merged_data, legacy_data, ai_contact_data)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 개별 대상 추출 실패: {target.id} - {str(e)}")
            return CrawlingResult(
                target_id=target.id,
                success=False,
                processing_time=time.time() - start_time,
                errors=[str(e)]
            )
    
    async def _execute_legacy_crawler(
        self,
        target: CrawlingTarget,
        discovery_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """레거시 크롤링 시스템 실행 (main_crawler.py 통합)"""
        try:
            # 실제 main_crawler.py 호출을 시뮬레이션
            # 실제 구현에서는 subprocess 또는 direct import 사용
            
            legacy_result = {
                "name": target.name,
                "category": target.category,
                "phone": None,
                "mobile": None,
                "fax": None,
                "email": None,
                "homepage": None,
                "address": None,
                "crawled_urls": discovery_info.get("crawling_order", [])[:3],
                "crawling_method": "py_cpuinfo_optimized",
                "processing_time": 2.5,
                "success": True
            }
            
            # 비동기 실행 시뮬레이션
            await asyncio.sleep(0.1)
            
            logger.debug(f"✅ 레거시 크롤러 실행 완료: {target.id}")
            return legacy_result
            
        except Exception as e:
            logger.error(f"❌ 레거시 크롤러 실행 실패: {target.id} - {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def _extract_ai_contacts(
        self,
        target: CrawlingTarget,
        legacy_data: Dict[str, Any],
        discovery_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """AI 기반 연락처 추출 및 보강"""
        try:
            # ContactAgent를 통한 AI 기반 연락처 추출
            contact_targets = [
                ContactTarget(
                    name=target.name,
                    category=target.category,
                    target_urls=discovery_info.get("crawling_order", [])[:5],
                    search_keywords=target.search_keywords,
                    existing_info=ContactInfo(
                        phone=legacy_data.get("phone"),
                        mobile=legacy_data.get("mobile"),
                        fax=legacy_data.get("fax"),
                        email=legacy_data.get("email"),
                        homepage=legacy_data.get("homepage"),
                        address=legacy_data.get("address")
                    ) if legacy_data.get("success") else None
                )
            ]
            
            contact_input = {
                "targets": contact_targets,
                "extraction_methods": ["web_crawling", "ai_analysis"],
                "verification_required": True,
                "max_sources_per_target": 5
            }
            
            contact_result = await self.contact_agent.process(contact_input)
            
            if contact_result.success and contact_result.data:
                logger.debug(f"✅ AI 연락처 추출 완료: {target.id}")
                return contact_result.data
            else:
                logger.warning(f"⚠️ AI 연락처 추출 실패: {target.id}")
                return {"success": False, "error": contact_result.error}
                
        except Exception as e:
            logger.error(f"❌ AI 연락처 추출 오류: {target.id} - {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _merge_extraction_data(
        self,
        legacy_data: Dict[str, Any],
        ai_contact_data: Dict[str, Any],
        existing_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """추출된 데이터 병합 및 정리"""
        merged_data = existing_data.copy()
        
        # 레거시 데이터 병합
        if legacy_data.get("success"):
            for field in ["phone", "mobile", "fax", "email", "homepage", "address"]:
                if legacy_data.get(field) and not merged_data.get(field):
                    merged_data[field] = legacy_data[field]
        
        # AI 연락처 데이터 병합 (높은 신뢰도 우선)
        if ai_contact_data.get("success") and ai_contact_data.get("results"):
            ai_results = ai_contact_data["results"]
            if ai_results:
                best_result = max(ai_results, key=lambda x: x.get("confidence_score", 0))
                extracted_info = best_result.get("extracted_info", {})
                
                for field in ["phone", "mobile", "fax", "email", "homepage", "address"]:
                    ai_value = extracted_info.get(field)
                    if ai_value and (not merged_data.get(field) or best_result.get("confidence_score", 0) > 0.8):
                        merged_data[field] = ai_value
        
        # 메타데이터 추가
        merged_data["_metadata"] = {
            "legacy_crawler_used": legacy_data.get("success", False),
            "ai_agent_used": ai_contact_data.get("success", False),
            "merge_timestamp": datetime.now().isoformat(),
            "data_sources": ["legacy_crawler", "ai_contact_agent"]
        }
        
        return merged_data
    
    def _calculate_confidence_score(
        self,
        merged_data: Dict[str, Any],
        legacy_data: Dict[str, Any],
        ai_contact_data: Dict[str, Any]
    ) -> float:
        """신뢰도 점수 계산"""
        score = 0.0
        
        # 기본 점수 (데이터 완성도)
        required_fields = ["phone", "email", "address"]
        filled_fields = sum(1 for field in required_fields if merged_data.get(field))
        completeness_score = filled_fields / len(required_fields)
        
        # 소스 신뢰도 점수
        source_score = 0.0
        if legacy_data.get("success"):
            source_score += 0.6
        if ai_contact_data.get("success"):
            source_score += 0.4
            # AI 신뢰도 추가
            if ai_contact_data.get("results"):
                ai_confidence = max((r.get("confidence_score", 0) for r in ai_contact_data["results"]), default=0)
                source_score += ai_confidence * 0.2
        
        # 최종 점수 계산
        score = (completeness_score * 0.6) + (min(source_score, 1.0) * 0.4)
        
        return round(score, 3)
    
    async def _validate_extracted_data(
        self,
        config: CrawlingJobConfig,
        extraction_results: List[CrawlingResult]
    ) -> List[CrawlingResult]:
        """AI 기반 데이터 검증"""
        if not config.enable_ai_validation:
            return extraction_results
        
        try:
            # ValidationAgent를 통한 데이터 검증
            validation_targets = []
            for result in extraction_results:
                if result.success:
                    validation_targets.append(ValidationTarget(
                        target_id=result.target_id,
                        data_to_validate=result.extracted_data,
                        validation_rules=["phone_format", "email_format", "url_format", "data_consistency"],
                        required_fields=["name", "phone", "email"]
                    ))
            
            if validation_targets:
                validation_input = {
                    "targets": validation_targets,
                    "validation_level": "comprehensive",
                    "auto_correction": True
                }
                
                validation_result = await self.validation_agent.process(validation_input)
                
                if validation_result.success:
                    # 검증 결과를 원본 결과에 병합
                    validation_data = validation_result.data.get("validation_results", {})
                    
                    for result in extraction_results:
                        if result.target_id in validation_data:
                            target_validation = validation_data[result.target_id]
                            result.validation_results = target_validation
                            
                            # 검증 통과 시 신뢰도 점수 향상
                            if target_validation.get("overall_valid", False):
                                result.confidence_score = min(result.confidence_score * 1.2, 1.0)
                            
                            # 자동 수정된 데이터 적용
                            if target_validation.get("corrected_data"):
                                result.extracted_data.update(target_validation["corrected_data"])
                    
                    logger.info(f"✅ AI 데이터 검증 완료: {len(validation_targets)}개 대상")
                else:
                    logger.warning(f"⚠️ AI 데이터 검증 실패: {validation_result.error}")
            
            return extraction_results
            
        except Exception as e:
            logger.error(f"❌ 데이터 검증 오류: {str(e)}")
            return extraction_results
    
    async def _enrich_and_optimize_data(
        self,
        config: CrawlingJobConfig,
        validation_results: List[CrawlingResult]
    ) -> List[CrawlingResult]:
        """데이터 보강 및 최적화"""
        if not config.enable_enrichment:
            return validation_results
        
        try:
            # 데이터 보강 로직
            for result in validation_results:
                if result.success:
                    # 추가 데이터 보강 (예: 주소 정규화, 전화번호 형식 통일 등)
                    enriched_data = await self._enrich_single_result(result.extracted_data)
                    result.enrichment_results = enriched_data
                    
                    # 보강된 데이터를 원본에 병합
                    if enriched_data.get("success"):
                        result.extracted_data.update(enriched_data.get("enriched_fields", {}))
                        result.confidence_score = min(result.confidence_score * 1.1, 1.0)
            
            successful_enrichments = len([r for r in validation_results if r.enrichment_results.get("success")])
            logger.info(f"✅ 데이터 보강 완료: {successful_enrichments}/{len(validation_results)}개 성공")
            
            return validation_results
            
        except Exception as e:
            logger.error(f"❌ 데이터 보강 오류: {str(e)}")
            return validation_results
    
    async def _enrich_single_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """개별 결과 데이터 보강"""
        try:
            enriched_fields = {}
            
            # 전화번호 형식 정규화
            if data.get("phone"):
                normalized_phone = self._normalize_phone_number(data["phone"])
                if normalized_phone != data["phone"]:
                    enriched_fields["phone"] = normalized_phone
            
            # 이메일 형식 검증 및 정리
            if data.get("email"):
                cleaned_email = self._clean_email_address(data["email"])
                if cleaned_email != data["email"]:
                    enriched_fields["email"] = cleaned_email
            
            # 홈페이지 URL 정규화
            if data.get("homepage"):
                normalized_url = self._normalize_url(data["homepage"])
                if normalized_url != data["homepage"]:
                    enriched_fields["homepage"] = normalized_url
            
            return {
                "success": len(enriched_fields) > 0,
                "enriched_fields": enriched_fields,
                "enrichment_count": len(enriched_fields)
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def _optimize_and_report(
        self,
        config: CrawlingJobConfig,
        enrichment_results: List[CrawlingResult]
    ) -> List[CrawlingResult]:
        """성능 최적화 및 리포팅"""
        try:
            # 성능 최적화
            if config.enable_optimization and self.gcp_optimization_service:
                await self._trigger_performance_optimization(config, enrichment_results)
            
            # 결과 리포팅
            await self._generate_crawling_report(config, enrichment_results)
            
            return enrichment_results
            
        except Exception as e:
            logger.error(f"❌ 최적화 및 리포팅 오류: {str(e)}")
            return enrichment_results
    
    def _generate_fallback_strategy(self, config: CrawlingJobConfig) -> Dict[str, Any]:
        """기본 크롤링 전략 생성"""
        return {
            "strategy_type": "conservative",
            "max_urls_per_target": 5,
            "enable_url_discovery": False,
            "parallel_processing": min(config.max_concurrent, 3),
            "timeout_per_url": 30,
            "retry_failed_urls": True,
            "fallback_strategy": True
        }
    
    async def _discover_additional_urls(
        self,
        target: CrawlingTarget,
        strategy_result: Dict[str, Any]
    ) -> List[str]:
        """추가 URL 발견"""
        # 검색 키워드 기반 URL 발견 로직
        additional_urls = []
        
        # 구글 검색 URL 생성
        if target.search_keywords:
            search_query = f"{target.name} {' '.join(target.search_keywords[:2])}"
            google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            additional_urls.append(google_url)
        
        return additional_urls
    
    async def _prioritize_urls(
        self,
        target: CrawlingTarget,
        urls: List[str],
        strategy_result: Dict[str, Any]
    ) -> List[str]:
        """URL 우선순위 설정"""
        # 간단한 우선순위 로직
        prioritized = []
        
        # 1. 공식 홈페이지 추정 URL들 우선
        official_urls = [url for url in urls if any(keyword in url.lower() for keyword in [target.name.lower(), "official", "www"])]
        prioritized.extend(official_urls)
        
        # 2. 나머지 URL들
        remaining_urls = [url for url in urls if url not in official_urls]
        prioritized.extend(remaining_urls)
        
        return prioritized
    
    def _normalize_phone_number(self, phone: str) -> str:
        """전화번호 정규화"""
        import re
        # 한국 전화번호 형식으로 정규화
        cleaned = re.sub(r'[^\d]', '', phone)
        if len(cleaned) == 11 and cleaned.startswith('010'):
            return f"{cleaned[:3]}-{cleaned[3:7]}-{cleaned[7:]}"
        elif len(cleaned) == 10 and cleaned.startswith('02'):
            return f"{cleaned[:2]}-{cleaned[2:6]}-{cleaned[6:]}"
        elif len(cleaned) == 11 and cleaned.startswith(('031', '032', '033', '041', '042', '043', '051', '052', '053', '054', '055', '061', '062', '063', '064')):
            return f"{cleaned[:3]}-{cleaned[3:7]}-{cleaned[7:]}"
        return phone
    
    def _clean_email_address(self, email: str) -> str:
        """이메일 주소 정리"""
        return email.strip().lower()
    
    def _normalize_url(self, url: str) -> str:
        """URL 정규화"""
        if not url.startswith(('http://', 'https://')):
            return f"https://{url}"
        return url
    
    def _update_performance_stats(self, job_status: CrawlingJobStatus):
        """성능 통계 업데이트"""
        self.performance_stats["total_jobs"] += 1
        
        if job_status.status == "completed":
            self.performance_stats["successful_jobs"] += 1
        else:
            self.performance_stats["failed_jobs"] += 1
        
        self.performance_stats["total_targets_processed"] += job_status.total_targets
        
        # 평균 작업 시간 업데이트
        total_duration = self.performance_stats["average_job_duration"] * (self.performance_stats["total_jobs"] - 1)
        total_duration += job_status.total_processing_time
        self.performance_stats["average_job_duration"] = total_duration / self.performance_stats["total_jobs"]
    
    async def _trigger_performance_optimization(
        self,
        config: CrawlingJobConfig,
        results: List[CrawlingResult]
    ):
        """성능 최적화 트리거"""
        try:
            if self.gcp_optimization_service:
                await self.gcp_optimization_service.trigger_optimization_analysis()
                logger.info("✅ 성능 최적화 트리거 완료")
        except Exception as e:
            logger.error(f"❌ 성능 최적화 트리거 실패: {str(e)}")
    
    async def _generate_crawling_report(
        self,
        config: CrawlingJobConfig,
        results: List[CrawlingResult]
    ):
        """크롤링 리포트 생성"""
        try:
            report = {
                "job_id": config.job_id,
                "summary": {
                    "total_targets": len(results),
                    "successful_targets": len([r for r in results if r.success]),
                    "failed_targets": len([r for r in results if not r.success]),
                    "success_rate": len([r for r in results if r.success]) / len(results) if results else 0,
                    "average_confidence": sum(r.confidence_score for r in results) / len(results) if results else 0,
                    "total_processing_time": sum(r.processing_time for r in results)
                },
                "results": [asdict(result) for result in results],
                "generated_at": datetime.now().isoformat()
            }
            
            # 리포트 저장 (실제 구현에서는 파일 시스템 또는 데이터베이스에 저장)
            logger.info(f"📊 크롤링 리포트 생성 완료: {config.job_id}")
            
        except Exception as e:
            logger.error(f"❌ 크롤링 리포트 생성 실패: {str(e)}")
    
    def get_job_status(self, job_id: str) -> Optional[CrawlingJobStatus]:
        """작업 상태 조회"""
        return self.active_jobs.get(job_id)
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        return self.performance_stats.copy()
    
    def get_recent_jobs(self, limit: int = 10) -> List[CrawlingJobStatus]:
        """최근 작업 목록 조회"""
        return list(self.job_history)[-limit:]
    
    async def cleanup(self):
        """리소스 정리"""
        try:
            # 실행자 종료
            self.executor.shutdown(wait=True)
            
            # 활성 작업 정리
            self.active_jobs.clear()
            
            logger.info("🧹 크롤링 에이전트 통합 시스템 정리 완료")
            
        except Exception as e:
            logger.error(f"❌ 정리 중 오류: {str(e)}")


# 편의 함수들
def create_crawling_target(
    name: str,
    category: str,
    existing_data: Dict[str, Any] = None,
    target_urls: List[str] = None,
    search_keywords: List[str] = None,
    priority: int = 1
) -> CrawlingTarget:
    """크롤링 대상 생성 편의 함수"""
    import uuid
    
    return CrawlingTarget(
        id=str(uuid.uuid4()),
        name=name,
        category=category,
        existing_data=existing_data or {},
        target_urls=target_urls or [],
        search_keywords=search_keywords or [],
        priority=priority
    )


def create_crawling_job_config(
    targets: List[CrawlingTarget],
    strategy: CrawlingStrategy = CrawlingStrategy.BALANCED,
    max_concurrent: int = 5,
    enable_ai_validation: bool = True,
    enable_enrichment: bool = True,
    enable_optimization: bool = True
) -> CrawlingJobConfig:
    """크롤링 작업 설정 생성 편의 함수"""
    import uuid
    
    return CrawlingJobConfig(
        job_id=f"crawling_job_{int(time.time())}_{str(uuid.uuid4())[:8]}",
        targets=targets,
        strategy=strategy,
        max_concurrent=max_concurrent,
        enable_ai_validation=enable_ai_validation,
        enable_enrichment=enable_enrichment,
        enable_optimization=enable_optimization
    ) 