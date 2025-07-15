"""
🕷️ 지능형 크롤링 서비스 API

Features:
- 크롤링 작업 관리
- 스케줄링 관리
- 실시간 모니터링
- 크롤링 전략 설정
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Query
from pydantic import BaseModel, Field

from aiagent.core import IntelligentCrawlingService, CrawlingAgentIntegration

logger = logging.getLogger(__name__)
router = APIRouter()


# 글로벌 의존성
async def get_crawling_service() -> IntelligentCrawlingService:
    """크롤링 서비스 의존성 - 메인 앱에서 주입"""
    from app import intelligent_crawling_service
    if not intelligent_crawling_service:
        raise HTTPException(status_code=503, detail="크롤링 서비스가 초기화되지 않았습니다")
    return intelligent_crawling_service


# Enum 정의
class CrawlingStrategy(str, Enum):
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    AI_ADAPTIVE = "ai_adaptive"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Pydantic 모델들
class CrawlingTarget(BaseModel):
    """크롤링 대상"""
    name: str = Field(..., description="기관/대상 이름")
    category: str = Field(..., description="카테고리 (교회, 학원, 병원 등)")
    region: Optional[str] = Field(None, description="지역")
    address: Optional[str] = Field(None, description="주소")
    keywords: Optional[List[str]] = Field(default_factory=list, description="검색 키워드")


class CrawlingJobRequest(BaseModel):
    """크롤링 작업 요청"""
    name: str = Field(..., description="작업 이름")
    targets: List[CrawlingTarget] = Field(..., description="크롤링 대상 목록")
    strategy: CrawlingStrategy = Field(default=CrawlingStrategy.BALANCED, description="크롤링 전략")
    max_concurrent: int = Field(default=3, ge=1, le=10, description="최대 동시 처리 수")
    use_ai: bool = Field(default=True, description="AI 분석 사용 여부")
    timeout: int = Field(default=300, ge=60, le=3600, description="작업 타임아웃 (초)")
    priority: int = Field(default=1, ge=1, le=10, description="작업 우선순위")


class ScheduledJobRequest(BaseModel):
    """스케줄 작업 요청"""
    job_request: CrawlingJobRequest = Field(..., description="크롤링 작업 요청")
    cron_expression: str = Field(..., description="Cron 표현식")
    timezone: str = Field(default="Asia/Seoul", description="시간대")
    max_runs: Optional[int] = Field(None, description="최대 실행 횟수")
    end_time: Optional[datetime] = Field(None, description="종료 시간")


class JobResponse(BaseModel):
    """작업 응답"""
    job_id: str
    name: str
    status: JobStatus
    strategy: CrawlingStrategy
    targets_count: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = Field(default=0.0, description="진행률 (0.0-1.0)")
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class CrawlingResult(BaseModel):
    """크롤링 결과"""
    target_name: str
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time: float
    extracted_contacts: int = 0
    validation_score: float = 0.0


class JobProgressResponse(BaseModel):
    """작업 진행 상황"""
    job_id: str
    status: JobStatus
    progress: float
    current_target: Optional[str] = None
    completed_targets: int = 0
    total_targets: int = 0
    results: List[CrawlingResult] = Field(default_factory=list)
    estimated_completion: Optional[datetime] = None


# 크롤링 작업 관리 API
@router.post("/jobs", summary="새 크롤링 작업 생성")
async def create_crawling_job(
    job_request: CrawlingJobRequest,
    background_tasks: BackgroundTasks,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> JobResponse:
    """새로운 크롤링 작업을 생성하고 실행합니다."""
    try:
        # 작업 생성
        job_id = await service.create_job(
            name=job_request.name,
            targets=[target.dict() for target in job_request.targets],
            config={
                "strategy": job_request.strategy.value,
                "max_concurrent": job_request.max_concurrent,
                "use_ai": job_request.use_ai,
                "timeout": job_request.timeout,
                "priority": job_request.priority
            }
        )
        
        # 백그라운드에서 작업 실행
        background_tasks.add_task(
            service.start_job,
            job_id
        )
        
        return JobResponse(
            job_id=job_id,
            name=job_request.name,
            status=JobStatus.PENDING,
            strategy=job_request.strategy,
            targets_count=len(job_request.targets),
            created_at=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"크롤링 작업 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 생성 실패: {str(e)}")


@router.get("/jobs", summary="크롤링 작업 목록 조회")
async def list_crawling_jobs(
    status: Optional[JobStatus] = Query(None, description="상태별 필터링"),
    limit: int = Query(default=50, ge=1, le=100, description="최대 조회 개수"),
    offset: int = Query(default=0, ge=0, description="오프셋"),
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> List[JobResponse]:
    """크롤링 작업 목록을 조회합니다."""
    try:
        jobs = await service.get_jobs(
            status=status.value if status else None,
            limit=limit,
            offset=offset
        )
        
        return [
            JobResponse(
                job_id=job["job_id"],
                name=job["name"],
                status=JobStatus(job["status"]),
                strategy=CrawlingStrategy(job["strategy"]),
                targets_count=job["targets_count"],
                created_at=job["created_at"],
                started_at=job.get("started_at"),
                completed_at=job.get("completed_at"),
                progress=job.get("progress", 0.0),
                results=job.get("results"),
                error=job.get("error")
            )
            for job in jobs
        ]
        
    except Exception as e:
        logger.error(f"작업 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 목록 조회 실패: {str(e)}")


@router.get("/jobs/{job_id}", summary="특정 크롤링 작업 조회")
async def get_crawling_job(
    job_id: str,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> JobResponse:
    """특정 크롤링 작업의 상세 정보를 조회합니다."""
    try:
        job = await service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
        
        return JobResponse(
            job_id=job["job_id"],
            name=job["name"],
            status=JobStatus(job["status"]),
            strategy=CrawlingStrategy(job["strategy"]),
            targets_count=job["targets_count"],
            created_at=job["created_at"],
            started_at=job.get("started_at"),
            completed_at=job.get("completed_at"),
            progress=job.get("progress", 0.0),
            results=job.get("results"),
            error=job.get("error")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 조회 실패: {str(e)}")


@router.get("/jobs/{job_id}/progress", summary="작업 진행 상황 조회")
async def get_job_progress(
    job_id: str,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> JobProgressResponse:
    """크롤링 작업의 실시간 진행 상황을 조회합니다."""
    try:
        progress = await service.get_job_progress(job_id)
        if not progress:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
        
        return JobProgressResponse(
            job_id=job_id,
            status=JobStatus(progress["status"]),
            progress=progress["progress"],
            current_target=progress.get("current_target"),
            completed_targets=progress.get("completed_targets", 0),
            total_targets=progress.get("total_targets", 0),
            results=[
                CrawlingResult(
                    target_name=result["target_name"],
                    success=result["success"],
                    data=result.get("data"),
                    error=result.get("error"),
                    processing_time=result.get("processing_time", 0.0),
                    extracted_contacts=result.get("extracted_contacts", 0),
                    validation_score=result.get("validation_score", 0.0)
                )
                for result in progress.get("results", [])
            ],
            estimated_completion=progress.get("estimated_completion")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 진행 상황 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"진행 상황 조회 실패: {str(e)}")


@router.post("/jobs/{job_id}/cancel", summary="크롤링 작업 취소")
async def cancel_crawling_job(
    job_id: str,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, str]:
    """실행 중인 크롤링 작업을 취소합니다."""
    try:
        success = await service.cancel_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없거나 취소할 수 없습니다: {job_id}")
        
        return {"message": f"작업이 성공적으로 취소되었습니다: {job_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 취소 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 취소 실패: {str(e)}")


@router.delete("/jobs/{job_id}", summary="크롤링 작업 삭제")
async def delete_crawling_job(
    job_id: str,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, str]:
    """완료된 크롤링 작업을 삭제합니다."""
    try:
        success = await service.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"작업을 찾을 수 없습니다: {job_id}")
        
        return {"message": f"작업이 성공적으로 삭제되었습니다: {job_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"작업 삭제 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"작업 삭제 실패: {str(e)}")


# 스케줄링 관리 API
@router.post("/schedules", summary="스케줄 작업 생성")
async def create_scheduled_job(
    schedule_request: ScheduledJobRequest,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, str]:
    """새로운 스케줄 크롤링 작업을 생성합니다."""
    try:
        schedule_id = await service.create_schedule(
            job_config={
                "name": schedule_request.job_request.name,
                "targets": [target.dict() for target in schedule_request.job_request.targets],
                "strategy": schedule_request.job_request.strategy.value,
                "max_concurrent": schedule_request.job_request.max_concurrent,
                "use_ai": schedule_request.job_request.use_ai,
                "timeout": schedule_request.job_request.timeout,
                "priority": schedule_request.job_request.priority
            },
            cron_expression=schedule_request.cron_expression,
            timezone=schedule_request.timezone,
            max_runs=schedule_request.max_runs,
            end_time=schedule_request.end_time
        )
        
        return {
            "message": "스케줄 작업이 성공적으로 생성되었습니다",
            "schedule_id": schedule_id
        }
        
    except Exception as e:
        logger.error(f"스케줄 작업 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스케줄 작업 생성 실패: {str(e)}")


@router.get("/schedules", summary="스케줄 작업 목록 조회")
async def list_scheduled_jobs(
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> List[Dict[str, Any]]:
    """등록된 스케줄 작업 목록을 조회합니다."""
    try:
        schedules = await service.get_schedules()
        return schedules
        
    except Exception as e:
        logger.error(f"스케줄 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스케줄 목록 조회 실패: {str(e)}")


@router.delete("/schedules/{schedule_id}", summary="스케줄 작업 삭제")
async def delete_scheduled_job(
    schedule_id: str,
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, str]:
    """스케줄 작업을 삭제합니다."""
    try:
        success = await service.delete_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"스케줄을 찾을 수 없습니다: {schedule_id}")
        
        return {"message": f"스케줄이 성공적으로 삭제되었습니다: {schedule_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"스케줄 삭제 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"스케줄 삭제 실패: {str(e)}")


# 모니터링 및 통계 API
@router.get("/statistics", summary="크롤링 통계 조회")
async def get_crawling_statistics(
    days: int = Query(default=7, ge=1, le=90, description="조회 기간 (일)"),
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, Any]:
    """크롤링 작업 통계를 조회합니다."""
    try:
        stats = await service.get_statistics(days=days)
        return {
            "period_days": days,
            "total_jobs": stats.get("total_jobs", 0),
            "completed_jobs": stats.get("completed_jobs", 0),
            "failed_jobs": stats.get("failed_jobs", 0),
            "success_rate": stats.get("success_rate", 0.0),
            "total_targets": stats.get("total_targets", 0),
            "extracted_contacts": stats.get("extracted_contacts", 0),
            "average_processing_time": stats.get("average_processing_time", 0.0),
            "strategy_usage": stats.get("strategy_usage", {}),
            "daily_stats": stats.get("daily_stats", [])
        }
        
    except Exception as e:
        logger.error(f"통계 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.get("/queue/status", summary="작업 큐 상태 조회")
async def get_queue_status(
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, Any]:
    """현재 작업 큐의 상태를 조회합니다."""
    try:
        status = await service.get_queue_status()
        return {
            "queue_size": status.get("queue_size", 0),
            "running_jobs": status.get("running_jobs", 0),
            "max_concurrent": status.get("max_concurrent", 5),
            "pending_jobs": status.get("pending_jobs", []),
            "active_jobs": status.get("active_jobs", [])
        }
        
    except Exception as e:
        logger.error(f"큐 상태 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"큐 상태 조회 실패: {str(e)}")


# 설정 관리 API
@router.get("/config", summary="크롤링 서비스 설정 조회")
async def get_service_config(
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, Any]:
    """크롤링 서비스의 현재 설정을 조회합니다."""
    try:
        config = await service.get_config()
        return config
        
    except Exception as e:
        logger.error(f"설정 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"설정 조회 실패: {str(e)}")


@router.put("/config", summary="크롤링 서비스 설정 업데이트")
async def update_service_config(
    config_updates: Dict[str, Any],
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, str]:
    """크롤링 서비스의 설정을 업데이트합니다."""
    try:
        await service.update_config(config_updates)
        return {"message": "설정이 성공적으로 업데이트되었습니다"}
        
    except Exception as e:
        logger.error(f"설정 업데이트 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"설정 업데이트 실패: {str(e)}")


# 상태 확인 API
@router.get("/health", summary="크롤링 서비스 건강 상태")
async def get_service_health(
    service: IntelligentCrawlingService = Depends(get_crawling_service)
) -> Dict[str, Any]:
    """크롤링 서비스의 건강 상태를 확인합니다."""
    try:
        health = await service.get_health_status()
        return {
            "status": health.get("status", "unknown"),
            "uptime": health.get("uptime", 0),
            "active_jobs": health.get("active_jobs", 0),
            "queue_size": health.get("queue_size", 0),
            "last_error": health.get("last_error"),
            "ai_client_status": health.get("ai_client_status", "unknown"),
            "timestamp": datetime.now()
        }
        
    except Exception as e:
        logger.error(f"서비스 상태 확인 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"상태 확인 실패: {str(e)}") 