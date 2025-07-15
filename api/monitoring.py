"""
📊 모니터링 및 성능 관리 API

Features:
- 실시간 성능 모니터링
- 시스템 메트릭 조회
- 성능 알림 관리
- GCP 최적화 관리
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from enum import Enum

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from aiagent.core import (
    PerformanceMonitor,
    MonitoringIntegration,
    GCPOptimizer,
    GCPOptimizationService
)

logger = logging.getLogger(__name__)
router = APIRouter()


# 글로벌 의존성
async def get_performance_monitor() -> PerformanceMonitor:
    """성능 모니터 의존성 - 메인 앱에서 주입"""
    from app import performance_monitor
    if not performance_monitor:
        raise HTTPException(status_code=503, detail="성능 모니터링 시스템이 초기화되지 않았습니다")
    return performance_monitor


async def get_monitoring_integration() -> MonitoringIntegration:
    """통합 모니터링 의존성 - 메인 앱에서 주입"""
    from app import monitoring_integration
    if not monitoring_integration:
        raise HTTPException(status_code=503, detail="통합 모니터링 시스템이 초기화되지 않았습니다")
    return monitoring_integration


# Enum 정의
class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class MetricType(str, Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    AI_REQUESTS = "ai_requests"
    RESPONSE_TIME = "response_time"


class ReportType(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


# Pydantic 모델들
class MetricRequest(BaseModel):
    """메트릭 조회 요청"""
    metric_types: List[MetricType] = Field(default_factory=list, description="조회할 메트릭 타입들")
    start_time: Optional[datetime] = Field(None, description="시작 시간")
    end_time: Optional[datetime] = Field(None, description="종료 시간")
    interval: int = Field(default=60, ge=10, le=3600, description="간격 (초)")


class AlertThresholdUpdate(BaseModel):
    """알림 임계값 업데이트"""
    metric_type: MetricType = Field(..., description="메트릭 타입")
    warning_threshold: float = Field(..., description="경고 임계값")
    critical_threshold: float = Field(..., description="위험 임계값")
    emergency_threshold: float = Field(..., description="응급 임계값")


class ReportRequest(BaseModel):
    """리포트 생성 요청"""
    report_type: ReportType = Field(..., description="리포트 타입")
    include_ai_analysis: bool = Field(default=True, description="AI 분석 포함 여부")
    metric_types: List[MetricType] = Field(default_factory=list, description="포함할 메트릭 타입들")


class OptimizationRequest(BaseModel):
    """최적화 요청"""
    optimization_level: str = Field(default="balanced", description="최적화 수준 (conservative, balanced, aggressive)")
    target_metrics: List[MetricType] = Field(default_factory=list, description="타겟 메트릭들")
    auto_apply: bool = Field(default=False, description="자동 적용 여부")


# 실시간 모니터링 API
@router.get("/metrics/current", summary="현재 시스템 메트릭 조회")
async def get_current_metrics(
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """현재 시스템의 실시간 메트릭을 조회합니다."""
    try:
        current_metrics = await monitor.get_current_metrics()
        return {
            "timestamp": datetime.now(),
            "metrics": current_metrics,
            "status": "healthy" if current_metrics.get("cpu_percent", 0) < 80 else "warning"
        }
        
    except Exception as e:
        logger.error(f"현재 메트릭 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메트릭 조회 실패: {str(e)}")


@router.post("/metrics/history", summary="메트릭 이력 조회")
async def get_metrics_history(
    request: MetricRequest,
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """지정된 기간의 메트릭 이력을 조회합니다."""
    try:
        # 기본값 설정
        end_time = request.end_time or datetime.now()
        start_time = request.start_time or (end_time - timedelta(hours=1))
        
        history = await monitor.get_metrics_history(
            start_time=start_time,
            end_time=end_time,
            metric_types=[mt.value for mt in request.metric_types] if request.metric_types else None,
            interval=request.interval
        )
        
        return {
            "start_time": start_time,
            "end_time": end_time,
            "interval": request.interval,
            "data_points": len(history),
            "metrics": history
        }
        
    except Exception as e:
        logger.error(f"메트릭 이력 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메트릭 이력 조회 실패: {str(e)}")


@router.get("/metrics/summary", summary="메트릭 요약 통계")
async def get_metrics_summary(
    hours: int = Query(default=24, ge=1, le=168, description="조회 기간 (시간)"),
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """지정된 기간의 메트릭 요약 통계를 조회합니다."""
    try:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        summary = await monitor.get_metrics_summary(
            start_time=start_time,
            end_time=end_time
        )
        
        return {
            "period": f"{hours} hours",
            "start_time": start_time,
            "end_time": end_time,
            "summary": summary
        }
        
    except Exception as e:
        logger.error(f"메트릭 요약 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"메트릭 요약 조회 실패: {str(e)}")


# 알림 관리 API
@router.get("/alerts", summary="최근 알림 조회")
async def get_recent_alerts(
    limit: int = Query(default=50, ge=1, le=200, description="최대 조회 개수"),
    level: Optional[AlertLevel] = Query(None, description="알림 레벨 필터"),
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> List[Dict[str, Any]]:
    """최근 발생한 알림들을 조회합니다."""
    try:
        alerts = await monitor.get_recent_alerts(
            limit=limit,
            level=level.value if level else None
        )
        
        return [
            {
                "id": alert.id,
                "level": alert.level.value,
                "message": alert.message,
                "metric_type": alert.metric_type.value if alert.metric_type else None,
                "timestamp": alert.timestamp,
                "resolved": alert.resolved,
                "resolution_time": alert.resolution_time
            }
            for alert in alerts
        ]
        
    except Exception as e:
        logger.error(f"알림 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"알림 조회 실패: {str(e)}")


@router.get("/alerts/thresholds", summary="알림 임계값 조회")
async def get_alert_thresholds(
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """현재 설정된 알림 임계값들을 조회합니다."""
    try:
        thresholds = await monitor.get_alert_thresholds()
        return {"thresholds": thresholds}
        
    except Exception as e:
        logger.error(f"임계값 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"임계값 조회 실패: {str(e)}")


@router.put("/alerts/thresholds", summary="알림 임계값 업데이트")
async def update_alert_thresholds(
    threshold_update: AlertThresholdUpdate,
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, str]:
    """알림 임계값을 업데이트합니다."""
    try:
        await monitor.update_alert_threshold(
            metric_type=threshold_update.metric_type.value,
            warning=threshold_update.warning_threshold,
            critical=threshold_update.critical_threshold,
            emergency=threshold_update.emergency_threshold
        )
        
        return {"message": f"{threshold_update.metric_type} 임계값이 업데이트되었습니다"}
        
    except Exception as e:
        logger.error(f"임계값 업데이트 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"임계값 업데이트 실패: {str(e)}")


@router.post("/alerts/{alert_id}/resolve", summary="알림 해결 처리")
async def resolve_alert(
    alert_id: str,
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, str]:
    """특정 알림을 해결 상태로 변경합니다."""
    try:
        success = await monitor.resolve_alert(alert_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"알림을 찾을 수 없습니다: {alert_id}")
        
        return {"message": f"알림이 해결 처리되었습니다: {alert_id}"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"알림 해결 처리 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"알림 해결 처리 실패: {str(e)}")


# 리포트 생성 API
@router.post("/reports/generate", summary="성능 리포트 생성")
async def generate_performance_report(
    report_request: ReportRequest,
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """성능 분석 리포트를 생성합니다."""
    try:
        report = await monitor.generate_report(
            report_type=report_request.report_type.value,
            include_ai_analysis=report_request.include_ai_analysis,
            metric_types=[mt.value for mt in report_request.metric_types] if report_request.metric_types else None
        )
        
        return {
            "report_id": report.get("report_id"),
            "report_type": report_request.report_type.value,
            "generated_at": datetime.now(),
            "summary": report.get("summary", {}),
            "detailed_analysis": report.get("detailed_analysis", {}),
            "recommendations": report.get("recommendations", []),
            "charts_data": report.get("charts_data", {})
        }
        
    except Exception as e:
        logger.error(f"리포트 생성 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"리포트 생성 실패: {str(e)}")


@router.get("/reports", summary="생성된 리포트 목록")
async def list_reports(
    limit: int = Query(default=20, ge=1, le=100, description="최대 조회 개수"),
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> List[Dict[str, Any]]:
    """생성된 성능 리포트 목록을 조회합니다."""
    try:
        reports = await monitor.get_reports(limit=limit)
        return reports
        
    except Exception as e:
        logger.error(f"리포트 목록 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"리포트 목록 조회 실패: {str(e)}")


@router.get("/reports/{report_id}", summary="특정 리포트 조회")
async def get_report(
    report_id: str,
    monitor: PerformanceMonitor = Depends(get_performance_monitor)
) -> Dict[str, Any]:
    """특정 성능 리포트의 상세 내용을 조회합니다."""
    try:
        report = await monitor.get_report(report_id)
        if not report:
            raise HTTPException(status_code=404, detail=f"리포트를 찾을 수 없습니다: {report_id}")
        
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"리포트 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"리포트 조회 실패: {str(e)}")


# 통합 모니터링 API
@router.get("/integration/status", summary="통합 모니터링 상태")
async def get_integration_status(
    integration: MonitoringIntegration = Depends(get_monitoring_integration)
) -> Dict[str, Any]:
    """통합 모니터링 시스템의 상태를 조회합니다."""
    try:
        status = await integration.get_status()
        return {
            "monitoring_active": status.get("monitoring_active", False),
            "components": status.get("components", {}),
            "last_update": status.get("last_update"),
            "total_metrics_collected": status.get("total_metrics_collected", 0),
            "active_alerts": status.get("active_alerts", 0)
        }
        
    except Exception as e:
        logger.error(f"통합 모니터링 상태 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")


@router.get("/integration/dashboard", summary="통합 대시보드 데이터")
async def get_dashboard_data(
    integration: MonitoringIntegration = Depends(get_monitoring_integration)
) -> Dict[str, Any]:
    """통합 모니터링 대시보드용 데이터를 조회합니다."""
    try:
        dashboard_data = await integration.get_dashboard_data()
        return {
            "timestamp": datetime.now(),
            "system_overview": dashboard_data.get("system_overview", {}),
            "agent_status": dashboard_data.get("agent_status", {}),
            "recent_activity": dashboard_data.get("recent_activity", []),
            "performance_trends": dashboard_data.get("performance_trends", {}),
            "active_alerts": dashboard_data.get("active_alerts", [])
        }
        
    except Exception as e:
        logger.error(f"대시보드 데이터 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"대시보드 데이터 조회 실패: {str(e)}")


# GCP 최적화 API
@router.get("/gcp/analysis", summary="GCP 환경 분석")
async def get_gcp_analysis() -> Dict[str, Any]:
    """현재 GCP 환경을 분석합니다."""
    try:
        optimizer = GCPOptimizer()
        analysis = await optimizer.analyze_environment()
        
        return {
            "timestamp": datetime.now(),
            "instance_info": analysis.get("instance_info", {}),
            "resource_usage": analysis.get("resource_usage", {}),
            "cost_analysis": analysis.get("cost_analysis", {}),
            "performance_bottlenecks": analysis.get("performance_bottlenecks", []),
            "optimization_score": analysis.get("optimization_score", 0)
        }
        
    except Exception as e:
        logger.error(f"GCP 분석 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GCP 분석 실패: {str(e)}")


@router.post("/gcp/optimize", summary="GCP 최적화 실행")
async def execute_gcp_optimization(
    optimization_request: OptimizationRequest
) -> Dict[str, Any]:
    """GCP 환경 최적화를 실행합니다."""
    try:
        optimizer = GCPOptimizer()
        optimization_service = GCPOptimizationService(optimizer)
        
        result = await optimization_service.run_optimization(
            level=optimization_request.optimization_level,
            target_metrics=optimization_request.target_metrics,
            auto_apply=optimization_request.auto_apply
        )
        
        return {
            "optimization_id": result.get("optimization_id"),
            "level": optimization_request.optimization_level,
            "status": result.get("status", "completed"),
            "recommendations": result.get("recommendations", []),
            "estimated_savings": result.get("estimated_savings", {}),
            "applied_optimizations": result.get("applied_optimizations", []) if optimization_request.auto_apply else [],
            "next_steps": result.get("next_steps", [])
        }
        
    except Exception as e:
        logger.error(f"GCP 최적화 실행 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GCP 최적화 실행 실패: {str(e)}")


@router.get("/gcp/recommendations", summary="GCP 최적화 권장사항")
async def get_gcp_recommendations() -> Dict[str, Any]:
    """GCP 최적화 권장사항을 조회합니다."""
    try:
        optimizer = GCPOptimizer()
        recommendations = await optimizer.get_recommendations()
        
        return {
            "timestamp": datetime.now(),
            "total_recommendations": len(recommendations),
            "categories": {
                "cost_optimization": [r for r in recommendations if r.get("category") == "cost"],
                "performance_optimization": [r for r in recommendations if r.get("category") == "performance"],
                "resource_optimization": [r for r in recommendations if r.get("category") == "resource"],
                "scaling_optimization": [r for r in recommendations if r.get("category") == "scaling"]
            },
            "priority_recommendations": [r for r in recommendations if r.get("priority", 0) >= 8]
        }
        
    except Exception as e:
        logger.error(f"GCP 권장사항 조회 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"GCP 권장사항 조회 실패: {str(e)}")


# 시스템 상태 API
@router.get("/health", summary="모니터링 시스템 건강 상태")
async def get_monitoring_health(
    monitor: PerformanceMonitor = Depends(get_performance_monitor),
    integration: MonitoringIntegration = Depends(get_monitoring_integration)
) -> Dict[str, Any]:
    """모니터링 시스템의 전체 건강 상태를 확인합니다."""
    try:
        monitor_health = await monitor.get_health_status()
        integration_health = await integration.get_health_status()
        
        return {
            "status": "healthy" if all([
                monitor_health.get("status") == "healthy",
                integration_health.get("status") == "healthy"
            ]) else "degraded",
            "components": {
                "performance_monitor": monitor_health,
                "monitoring_integration": integration_health
            },
            "timestamp": datetime.now(),
            "uptime": min(
                monitor_health.get("uptime", 0),
                integration_health.get("uptime", 0)
            )
        }
        
    except Exception as e:
        logger.error(f"모니터링 시스템 건강 상태 확인 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"건강 상태 확인 실패: {str(e)}")


@router.post("/monitoring/restart", summary="모니터링 시스템 재시작")
async def restart_monitoring(
    component: str = Query(description="재시작할 컴포넌트 (monitor, integration, all)"),
    monitor: PerformanceMonitor = Depends(get_performance_monitor),
    integration: MonitoringIntegration = Depends(get_monitoring_integration)
) -> Dict[str, str]:
    """모니터링 시스템 컴포넌트를 재시작합니다."""
    try:
        if component in ["monitor", "all"]:
            await monitor.restart()
        
        if component in ["integration", "all"]:
            await integration.restart()
        
        return {"message": f"{component} 컴포넌트가 성공적으로 재시작되었습니다"}
        
    except Exception as e:
        logger.error(f"모니터링 시스템 재시작 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"재시작 실패: {str(e)}") 