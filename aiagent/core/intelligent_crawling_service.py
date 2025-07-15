"""
🎯 지능형 크롤링 서비스

크롤링 에이전트 통합 시스템의 고수준 인터페이스
- 사용자 친화적 API 제공
- 크롤링 작업 스케줄링
- 결과 관리 및 리포팅
- 성능 모니터링 통합
"""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import json
from pathlib import Path

from loguru import logger

from .crawling_integration import (
    CrawlingAgentIntegration, CrawlingJobConfig, CrawlingJobStatus,
    CrawlingTarget, CrawlingResult, CrawlingStrategy, CrawlingPhase,
    create_crawling_target, create_crawling_job_config
)
from .agent_system import AIAgentSystem
from .performance_monitor import PerformanceMonitor
from .monitoring_integration import MonitoringIntegration
from .gcp_optimization_service import GCPOptimizationService


class ServiceStatus(Enum):
    """서비스 상태"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class IntelligentCrawlingConfig:
    """지능형 크롤링 서비스 설정"""
    service_name: str = "IntelligentCrawlingService"
    max_concurrent_jobs: int = 3            # 최대 동시 작업 수
    job_queue_size: int = 100               # 작업 큐 크기
    default_strategy: CrawlingStrategy = CrawlingStrategy.BALANCED  # 기본 전략
    auto_cleanup_hours: int = 24            # 자동 정리 주기 (시간)
    enable_scheduling: bool = True          # 스케줄링 활성화
    enable_monitoring: bool = True          # 모니터링 활성화
    enable_optimization: bool = True        # 최적화 활성화
    results_retention_days: int = 30        # 결과 보관 기간 (일)
    log_level: str = "INFO"                 # 로그 레벨


@dataclass 
class JobSchedule:
    """작업 스케줄 정의"""
    schedule_id: str                        # 스케줄 ID
    job_config: CrawlingJobConfig           # 작업 설정
    cron_expression: str                    # Cron 표현식
    enabled: bool = True                    # 활성화 여부
    last_run: Optional[datetime] = None     # 마지막 실행 시간
    next_run: Optional[datetime] = None     # 다음 실행 시간
    run_count: int = 0                      # 실행 횟수
    metadata: Dict[str, Any] = None         # 메타데이터


class IntelligentCrawlingService:
    """
    🎯 지능형 크롤링 서비스
    
    기능:
    - 고수준 크롤링 API 제공
    - 작업 스케줄링 및 큐 관리
    - 결과 저장 및 조회
    - 성능 모니터링 통합
    - 자동 최적화
    """
    
    def __init__(
        self,
        agent_system: AIAgentSystem,
        performance_monitor: PerformanceMonitor,
        monitoring_integration: MonitoringIntegration,
        gcp_optimization_service: Optional[GCPOptimizationService] = None,
        config: IntelligentCrawlingConfig = None
    ):
        """
        지능형 크롤링 서비스 초기화
        
        Args:
            agent_system: AI 에이전트 시스템
            performance_monitor: 성능 모니터
            monitoring_integration: 통합 모니터링
            gcp_optimization_service: GCP 최적화 서비스
            config: 서비스 설정
        """
        self.config = config or IntelligentCrawlingConfig()
        self.status = ServiceStatus.STOPPED
        
        # 핵심 컴포넌트 초기화
        self.crawling_integration = CrawlingAgentIntegration(
            agent_system=agent_system,
            performance_monitor=performance_monitor,
            monitoring_integration=monitoring_integration,
            gcp_optimization_service=gcp_optimization_service
        )
        
        # 작업 관리
        self.job_queue: asyncio.Queue = asyncio.Queue(maxsize=self.config.job_queue_size)
        self.active_jobs: Dict[str, CrawlingJobStatus] = {}
        self.completed_jobs: Dict[str, CrawlingJobStatus] = {}
        self.scheduled_jobs: Dict[str, JobSchedule] = {}
        
        # 서비스 태스크
        self.service_tasks: List[asyncio.Task] = []
        self.job_processor_semaphore = asyncio.Semaphore(self.config.max_concurrent_jobs)
        
        # 통계 및 메트릭
        self.service_metrics = {
            "service_start_time": None,
            "total_jobs_processed": 0,
            "successful_jobs": 0,
            "failed_jobs": 0,
            "average_job_duration": 0.0,
            "total_targets_processed": 0,
            "current_queue_size": 0,
            "peak_queue_size": 0
        }
        
        logger.info("🎯 지능형 크롤링 서비스 초기화 완료")
    
    async def start_service(self):
        """서비스 시작"""
        if self.status == ServiceStatus.RUNNING:
            logger.warning("⚠️ 서비스가 이미 실행 중입니다")
            return
        
        try:
            self.status = ServiceStatus.STARTING
            self.service_metrics["service_start_time"] = datetime.now()
            
            # 작업 처리기 시작
            processor_task = asyncio.create_task(self._job_processor())
            self.service_tasks.append(processor_task)
            
            # 스케줄러 시작
            if self.config.enable_scheduling:
                scheduler_task = asyncio.create_task(self._job_scheduler())
                self.service_tasks.append(scheduler_task)
            
            # 모니터링 시작
            if self.config.enable_monitoring:
                monitoring_task = asyncio.create_task(self._monitoring_loop())
                self.service_tasks.append(monitoring_task)
            
            # 자동 정리 시작
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self.service_tasks.append(cleanup_task)
            
            self.status = ServiceStatus.RUNNING
            logger.info("🚀 지능형 크롤링 서비스 시작 완료")
            
        except Exception as e:
            self.status = ServiceStatus.ERROR
            logger.error(f"❌ 서비스 시작 실패: {e}")
            raise e
    
    async def stop_service(self):
        """서비스 중지"""
        if self.status == ServiceStatus.STOPPED:
            return
        
        try:
            logger.info("🛑 지능형 크롤링 서비스 중지 중...")
            
            # 서비스 태스크들 중지
            for task in self.service_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            self.service_tasks.clear()
            
            # 활성 작업들 완료 대기
            if self.active_jobs:
                logger.info(f"⏳ {len(self.active_jobs)}개 활성 작업 완료 대기...")
                while self.active_jobs:
                    await asyncio.sleep(1)
            
            # 크롤링 통합 시스템 정리
            await self.crawling_integration.cleanup()
            
            self.status = ServiceStatus.STOPPED
            logger.info("✅ 지능형 크롤링 서비스 중지 완료")
            
        except Exception as e:
            logger.error(f"❌ 서비스 중지 중 오류: {e}")
            self.status = ServiceStatus.ERROR
    
    async def submit_crawling_job(
        self,
        targets: List[Dict[str, Any]],
        strategy: CrawlingStrategy = None,
        job_options: Dict[str, Any] = None
    ) -> str:
        """
        크롤링 작업 제출
        
        Args:
            targets: 크롤링 대상 목록
            strategy: 크롤링 전략
            job_options: 작업 옵션
            
        Returns:
            str: 작업 ID
        """
        try:
            # 크롤링 대상 객체 생성
            crawling_targets = []
            for target_data in targets:
                target = create_crawling_target(
                    name=target_data["name"],
                    category=target_data.get("category", "기타"),
                    existing_data=target_data.get("existing_data", {}),
                    target_urls=target_data.get("target_urls", []),
                    search_keywords=target_data.get("search_keywords", []),
                    priority=target_data.get("priority", 1)
                )
                crawling_targets.append(target)
            
            # 작업 설정 생성
            job_config = create_crawling_job_config(
                targets=crawling_targets,
                strategy=strategy or self.config.default_strategy,
                max_concurrent=job_options.get("max_concurrent", 5) if job_options else 5,
                enable_ai_validation=job_options.get("enable_ai_validation", True) if job_options else True,
                enable_enrichment=job_options.get("enable_enrichment", True) if job_options else True,
                enable_optimization=self.config.enable_optimization
            )
            
            # 작업 큐에 추가
            await self.job_queue.put(job_config)
            
            # 큐 크기 통계 업데이트
            current_size = self.job_queue.qsize()
            self.service_metrics["current_queue_size"] = current_size
            if current_size > self.service_metrics["peak_queue_size"]:
                self.service_metrics["peak_queue_size"] = current_size
            
            logger.info(f"📝 크롤링 작업 제출 완료: {job_config.job_id} ({len(crawling_targets)}개 대상)")
            
            return job_config.job_id
            
        except Exception as e:
            logger.error(f"❌ 크롤링 작업 제출 실패: {e}")
            raise e
    
    async def schedule_crawling_job(
        self,
        schedule_id: str,
        targets: List[Dict[str, Any]],
        cron_expression: str,
        strategy: CrawlingStrategy = None,
        job_options: Dict[str, Any] = None,
        enabled: bool = True
    ) -> bool:
        """
        크롤링 작업 스케줄 등록
        
        Args:
            schedule_id: 스케줄 ID
            targets: 크롤링 대상 목록
            cron_expression: Cron 표현식
            strategy: 크롤링 전략
            job_options: 작업 옵션
            enabled: 활성화 여부
            
        Returns:
            bool: 등록 성공 여부
        """
        try:
            # 크롤링 대상 객체 생성
            crawling_targets = []
            for target_data in targets:
                target = create_crawling_target(
                    name=target_data["name"],
                    category=target_data.get("category", "기타"),
                    existing_data=target_data.get("existing_data", {}),
                    target_urls=target_data.get("target_urls", []),
                    search_keywords=target_data.get("search_keywords", []),
                    priority=target_data.get("priority", 1)
                )
                crawling_targets.append(target)
            
            # 작업 설정 생성 (템플릿)
            job_config_template = create_crawling_job_config(
                targets=crawling_targets,
                strategy=strategy or self.config.default_strategy,
                max_concurrent=job_options.get("max_concurrent", 5) if job_options else 5,
                enable_ai_validation=job_options.get("enable_ai_validation", True) if job_options else True,
                enable_enrichment=job_options.get("enable_enrichment", True) if job_options else True,
                enable_optimization=self.config.enable_optimization
            )
            
            # 스케줄 등록
            schedule = JobSchedule(
                schedule_id=schedule_id,
                job_config=job_config_template,
                cron_expression=cron_expression,
                enabled=enabled,
                next_run=self._calculate_next_run(cron_expression),
                metadata=job_options or {}
            )
            
            self.scheduled_jobs[schedule_id] = schedule
            
            logger.info(f"📅 크롤링 작업 스케줄 등록: {schedule_id} ({cron_expression})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 크롤링 작업 스케줄 등록 실패: {e}")
            return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""
        # 활성 작업에서 검색
        if job_id in self.active_jobs:
            return asdict(self.active_jobs[job_id])
        
        # 완료된 작업에서 검색
        if job_id in self.completed_jobs:
            return asdict(self.completed_jobs[job_id])
        
        # 크롤링 통합 시스템에서 검색
        status = self.crawling_integration.get_job_status(job_id)
        if status:
            return asdict(status)
        
        return None
    
    def get_active_jobs(self) -> List[Dict[str, Any]]:
        """활성 작업 목록 조회"""
        return [asdict(job) for job in self.active_jobs.values()]
    
    def get_recent_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """최근 작업 목록 조회"""
        recent_jobs = list(self.completed_jobs.values())[-limit:]
        return [asdict(job) for job in recent_jobs]
    
    def get_scheduled_jobs(self) -> List[Dict[str, Any]]:
        """스케줄된 작업 목록 조회"""
        return [asdict(schedule) for schedule in self.scheduled_jobs.values()]
    
    def get_service_metrics(self) -> Dict[str, Any]:
        """서비스 메트릭 조회"""
        metrics = self.service_metrics.copy()
        metrics.update({
            "service_status": self.status.value,
            "active_jobs_count": len(self.active_jobs),
            "completed_jobs_count": len(self.completed_jobs),
            "scheduled_jobs_count": len(self.scheduled_jobs),
            "current_queue_size": self.job_queue.qsize(),
            "crawling_integration_stats": self.crawling_integration.get_performance_stats()
        })
        return metrics
    
    async def cancel_job(self, job_id: str) -> bool:
        """작업 취소"""
        try:
            if job_id in self.active_jobs:
                # 실제 구현에서는 실행 중인 작업을 취소하는 로직 필요
                self.active_jobs[job_id].status = "cancelled"
                logger.info(f"🚫 작업 취소 요청: {job_id}")
                return True
            else:
                logger.warning(f"⚠️ 취소할 작업을 찾을 수 없음: {job_id}")
                return False
        except Exception as e:
            logger.error(f"❌ 작업 취소 실패: {job_id} - {e}")
            return False
    
    async def pause_service(self):
        """서비스 일시 정지"""
        if self.status == ServiceStatus.RUNNING:
            self.status = ServiceStatus.PAUSED
            logger.info("⏸️ 지능형 크롤링 서비스 일시 정지")
    
    async def resume_service(self):
        """서비스 재개"""
        if self.status == ServiceStatus.PAUSED:
            self.status = ServiceStatus.RUNNING
            logger.info("▶️ 지능형 크롤링 서비스 재개")
    
    async def _job_processor(self):
        """작업 처리기 루프"""
        logger.info("🔄 작업 처리기 시작")
        
        while True:
            try:
                if self.status != ServiceStatus.RUNNING:
                    await asyncio.sleep(1)
                    continue
                
                # 작업 큐에서 작업 가져오기
                try:
                    job_config = await asyncio.wait_for(self.job_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                
                # 동시 실행 제한
                async with self.job_processor_semaphore:
                    # 작업 실행
                    task = asyncio.create_task(self._execute_job(job_config))
                    # 백그라운드에서 실행되도록 함 (await 하지 않음)
                
                # 큐 크기 업데이트
                self.service_metrics["current_queue_size"] = self.job_queue.qsize()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 작업 처리기 오류: {e}")
                await asyncio.sleep(5)
        
        logger.info("🛑 작업 처리기 종료")
    
    async def _execute_job(self, job_config: CrawlingJobConfig):
        """개별 작업 실행"""
        job_id = job_config.job_id
        
        try:
            # 활성 작업으로 등록
            job_status = CrawlingJobStatus(
                job_id=job_id,
                status="running",
                total_targets=len(job_config.targets),
                started_at=datetime.now()
            )
            self.active_jobs[job_id] = job_status
            
            logger.info(f"⚡ 작업 실행 시작: {job_id}")
            
            # 크롤링 통합 시스템을 통한 실행
            result = await self.crawling_integration.start_intelligent_crawling_job(job_config)
            
            # 결과 처리
            if result.status == "completed":
                self.service_metrics["successful_jobs"] += 1
            else:
                self.service_metrics["failed_jobs"] += 1
            
            self.service_metrics["total_jobs_processed"] += 1
            self.service_metrics["total_targets_processed"] += result.total_targets
            
            # 평균 작업 시간 업데이트
            if result.total_processing_time > 0:
                total_duration = self.service_metrics["average_job_duration"] * (self.service_metrics["total_jobs_processed"] - 1)
                total_duration += result.total_processing_time
                self.service_metrics["average_job_duration"] = total_duration / self.service_metrics["total_jobs_processed"]
            
            # 완료된 작업으로 이동
            self.completed_jobs[job_id] = result
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            
            logger.info(f"✅ 작업 실행 완료: {job_id} (성공률: {result.success_rate:.1%})")
            
        except Exception as e:
            logger.error(f"❌ 작업 실행 실패: {job_id} - {e}")
            
            # 실패한 작업 처리
            if job_id in self.active_jobs:
                self.active_jobs[job_id].status = "failed"
                self.active_jobs[job_id].completed_at = datetime.now()
                
                # 완료된 작업으로 이동
                self.completed_jobs[job_id] = self.active_jobs[job_id]
                del self.active_jobs[job_id]
            
            self.service_metrics["failed_jobs"] += 1
            self.service_metrics["total_jobs_processed"] += 1
    
    async def _job_scheduler(self):
        """작업 스케줄러 루프"""
        logger.info("📅 작업 스케줄러 시작")
        
        while True:
            try:
                if self.status != ServiceStatus.RUNNING:
                    await asyncio.sleep(10)
                    continue
                
                current_time = datetime.now()
                
                # 실행할 스케줄된 작업 확인
                for schedule_id, schedule in self.scheduled_jobs.items():
                    if (schedule.enabled and 
                        schedule.next_run and 
                        current_time >= schedule.next_run):
                        
                        # 새로운 작업 ID 생성
                        import uuid
                        new_job_config = schedule.job_config
                        new_job_config.job_id = f"scheduled_{schedule_id}_{int(time.time())}_{str(uuid.uuid4())[:8]}"
                        
                        # 작업 큐에 추가
                        try:
                            await self.job_queue.put(new_job_config)
                            
                            # 스케줄 정보 업데이트
                            schedule.last_run = current_time
                            schedule.next_run = self._calculate_next_run(schedule.cron_expression)
                            schedule.run_count += 1
                            
                            logger.info(f"📅 스케줄된 작업 실행: {schedule_id} -> {new_job_config.job_id}")
                            
                        except asyncio.QueueFull:
                            logger.warning(f"⚠️ 작업 큐가 가득참, 스케줄된 작업 건너뜀: {schedule_id}")
                
                # 1분마다 확인
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 작업 스케줄러 오류: {e}")
                await asyncio.sleep(60)
        
        logger.info("🛑 작업 스케줄러 종료")
    
    async def _monitoring_loop(self):
        """모니터링 루프"""
        logger.info("📊 모니터링 루프 시작")
        
        while True:
            try:
                if self.status != ServiceStatus.RUNNING:
                    await asyncio.sleep(30)
                    continue
                
                # 서비스 상태 모니터링
                metrics = self.get_service_metrics()
                
                # 큐 크기 모니터링
                queue_size = self.job_queue.qsize()
                if queue_size > self.config.job_queue_size * 0.8:
                    logger.warning(f"⚠️ 작업 큐 사용률 높음: {queue_size}/{self.config.job_queue_size}")
                
                # 활성 작업 모니터링
                active_count = len(self.active_jobs)
                if active_count > self.config.max_concurrent_jobs * 0.9:
                    logger.warning(f"⚠️ 활성 작업 수 높음: {active_count}/{self.config.max_concurrent_jobs}")
                
                # 30초마다 모니터링
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 모니터링 루프 오류: {e}")
                await asyncio.sleep(60)
        
        logger.info("🛑 모니터링 루프 종료")
    
    async def _cleanup_loop(self):
        """자동 정리 루프"""
        logger.info("🧹 자동 정리 루프 시작")
        
        while True:
            try:
                if self.status != ServiceStatus.RUNNING:
                    await asyncio.sleep(3600)  # 1시간
                    continue
                
                # 오래된 완료 작업 정리
                cutoff_time = datetime.now() - timedelta(days=self.config.results_retention_days)
                
                jobs_to_remove = []
                for job_id, job_status in self.completed_jobs.items():
                    if job_status.completed_at and job_status.completed_at < cutoff_time:
                        jobs_to_remove.append(job_id)
                
                for job_id in jobs_to_remove:
                    del self.completed_jobs[job_id]
                
                if jobs_to_remove:
                    logger.info(f"🧹 오래된 작업 정리 완료: {len(jobs_to_remove)}개")
                
                # 설정된 주기마다 정리 (기본 24시간)
                await asyncio.sleep(self.config.auto_cleanup_hours * 3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 자동 정리 루프 오류: {e}")
                await asyncio.sleep(3600)
        
        logger.info("🛑 자동 정리 루프 종료")
    
    def _calculate_next_run(self, cron_expression: str) -> datetime:
        """Cron 표현식을 기반으로 다음 실행 시간 계산"""
        # 간단한 Cron 파싱 (실제 구현에서는 croniter 등의 라이브러리 사용 권장)
        # 예: "0 9 * * *" -> 매일 오전 9시
        
        try:
            # 기본적으로 1시간 후로 설정 (실제 구현에서는 정확한 Cron 파싱 필요)
            return datetime.now() + timedelta(hours=1)
        except Exception:
            # 파싱 실패 시 1시간 후
            return datetime.now() + timedelta(hours=1)


# 편의 함수들
async def create_intelligent_crawling_service(
    agent_system: AIAgentSystem,
    performance_monitor: PerformanceMonitor,
    monitoring_integration: MonitoringIntegration,
    gcp_optimization_service: Optional[GCPOptimizationService] = None,
    config: IntelligentCrawlingConfig = None
) -> IntelligentCrawlingService:
    """지능형 크롤링 서비스 생성 및 시작"""
    service = IntelligentCrawlingService(
        agent_system=agent_system,
        performance_monitor=performance_monitor,
        monitoring_integration=monitoring_integration,
        gcp_optimization_service=gcp_optimization_service,
        config=config
    )
    
    await service.start_service()
    return service


def create_crawling_targets_from_dict(targets_data: List[Dict[str, Any]]) -> List[CrawlingTarget]:
    """딕셔너리 데이터에서 크롤링 대상 생성"""
    targets = []
    for data in targets_data:
        target = create_crawling_target(
            name=data["name"],
            category=data.get("category", "기타"),
            existing_data=data.get("existing_data", {}),
            target_urls=data.get("target_urls", []),
            search_keywords=data.get("search_keywords", []),
            priority=data.get("priority", 1)
        )
        targets.append(target)
    return targets 