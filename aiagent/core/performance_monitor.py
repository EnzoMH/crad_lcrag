"""
🔍 성능 모니터링 및 추적 시스템

Langchain 기반 AI 에이전트 시스템의 성능을 실시간으로 모니터링하고 추적하는 시스템
- 에이전트별 성능 메트릭
- 체인 실행 성능 추적  
- 시스템 리소스 모니터링
- AI API 사용량 추적
- 실시간 알림 및 최적화 권장사항
"""

import asyncio
import time
import json
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

import psutil
from loguru import logger

from .agent_base import BaseAgent, AgentResult, AgentMetrics
from .chain_manager import ChainManager, ChainExecutionResult
from ..utils.gemini_client import GeminiClient
from ..utils.rate_limiter import RateLimiter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain


class MetricType(Enum):
    """메트릭 유형"""
    AGENT_PERFORMANCE = "agent_performance"      # 에이전트 성능
    CHAIN_EXECUTION = "chain_execution"          # 체인 실행
    SYSTEM_RESOURCE = "system_resource"          # 시스템 리소스
    AI_API_USAGE = "ai_api_usage"               # AI API 사용량
    WORKFLOW_EFFICIENCY = "workflow_efficiency"  # 워크플로우 효율성


class AlertLevel(Enum):
    """알림 레벨"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class PerformanceMetric:
    """성능 메트릭 데이터 구조"""
    timestamp: datetime
    metric_type: MetricType
    source: str                    # 에이전트명, 체인명, 시스템 등
    metric_name: str              # CPU, memory, success_rate 등
    value: Union[float, int, str]  # 측정값
    unit: str = ""                # 단위 (%, MB, ms 등)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'metric_type': self.metric_type.value,
            'source': self.source,
            'metric_name': self.metric_name,
            'value': self.value,
            'unit': self.unit,
            'metadata': self.metadata
        }


@dataclass
class PerformanceAlert:
    """성능 알림"""
    id: str
    timestamp: datetime
    level: AlertLevel
    source: str
    title: str
    message: str
    metric_value: Union[float, int]
    threshold_value: Union[float, int]
    suggested_actions: List[str] = field(default_factory=list)
    auto_resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class SystemSnapshot:
    """시스템 스냅샷"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    active_agents: int
    running_chains: int
    api_rate_limit_usage: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PerformanceThresholds:
    """성능 임계값 설정"""
    cpu_warning: float = 70.0
    cpu_critical: float = 85.0
    memory_warning: float = 75.0
    memory_critical: float = 90.0
    disk_warning: float = 80.0
    disk_critical: float = 95.0
    
    # 에이전트 성능 임계값
    agent_success_rate_warning: float = 85.0
    agent_success_rate_critical: float = 70.0
    agent_response_time_warning: float = 10.0
    agent_response_time_critical: float = 30.0
    
    # AI API 임계값
    api_quota_warning: float = 80.0
    api_quota_critical: float = 95.0
    api_rate_limit_warning: float = 90.0


class PerformanceMonitor:
    """
    🔍 성능 모니터링 및 추적 시스템
    
    기능:
    - 실시간 성능 메트릭 수집
    - 임계값 기반 알림 시스템
    - 성능 추세 분석
    - 자동 최적화 권장사항
    - 성능 리포트 생성
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        성능 모니터 초기화
        
        Args:
            config: 설정 딕셔너리
        """
        self.config = config or {}
        self.thresholds = PerformanceThresholds()
        
        # 메트릭 저장소
        self.metrics_buffer: deque = deque(maxlen=10000)  # 최근 10K 메트릭
        self.system_snapshots: deque = deque(maxlen=1440)  # 24시간 (분당 스냅샷)
        self.alerts: deque = deque(maxlen=1000)  # 최근 1K 알림
        
        # 성능 통계
        self.agent_stats: Dict[str, Dict] = defaultdict(dict)
        self.chain_stats: Dict[str, Dict] = defaultdict(dict)
        
        # 모니터링 상태
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        self.monitoring_interval = self.config.get('monitoring_interval', 60)  # 60초
        
        # 스레드 풀
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # AI 클라이언트 (분석용)
        self.gemini_client = GeminiClient()
        
        # 분석 프롬프트
        self.analysis_prompt = PromptTemplate(
            input_variables=["metrics_summary", "system_state", "recent_alerts"],
            template="""
            다음 성능 데이터를 분석하여 시스템 상태를 평가하고 최적화 권장사항을 제공해주세요:

            메트릭 요약:
            {metrics_summary}

            시스템 상태:
            {system_state}

            최근 알림:
            {recent_alerts}

            다음 형식으로 JSON 응답:
            {{
                "system_health_score": 85.5,
                "status": "healthy/warning/critical",
                "key_insights": [
                    "주요 발견사항들"
                ],
                "performance_trends": {{
                    "cpu_trend": "increasing/stable/decreasing",
                    "memory_trend": "increasing/stable/decreasing",
                    "agent_performance_trend": "improving/stable/degrading"
                }},
                "optimization_recommendations": [
                    {{
                        "priority": "high/medium/low",
                        "category": "resource/agent/api/workflow",
                        "description": "권장사항 설명",
                        "expected_improvement": "예상 개선 효과",
                        "implementation_steps": ["단계1", "단계2"]
                    }}
                ],
                "immediate_actions": [
                    "즉시 실행해야 할 조치들"
                ]
            }}
            """
        )
        
        logger.info("🔍 성능 모니터링 시스템 초기화 완료")

    async def start_monitoring(self):
        """모니터링 시작"""
        if self.is_monitoring:
            logger.warning("⚠️ 모니터링이 이미 실행 중입니다")
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("📊 성능 모니터링 시작")

    async def stop_monitoring(self):
        """모니터링 중지"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("📊 성능 모니터링 중지")

    async def _monitoring_loop(self):
        """모니터링 메인 루프"""
        while self.is_monitoring:
            try:
                # 시스템 스냅샷 수집
                snapshot = await self._collect_system_snapshot()
                self.system_snapshots.append(snapshot)
                
                # 메트릭 수집
                await self._collect_metrics()
                
                # 임계값 확인 및 알림 생성
                await self._check_thresholds()
                
                # 성능 통계 업데이트
                await self._update_performance_stats()
                
                # 다음 수집까지 대기
                await asyncio.sleep(self.monitoring_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 모니터링 루프 오류: {e}")
                await asyncio.sleep(10)  # 오류 발생 시 10초 대기

    async def _collect_system_snapshot(self) -> SystemSnapshot:
        """시스템 스냅샷 수집"""
        # CPU 사용률
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # 메모리 사용률
        memory_info = psutil.virtual_memory()
        memory_usage = memory_info.percent
        
        # 디스크 사용률
        disk_info = psutil.disk_usage('/')
        disk_usage = (disk_info.used / disk_info.total) * 100
        
        # 네트워크 I/O
        network_io = psutil.net_io_counters()
        network_data = {
            "bytes_sent_mb": network_io.bytes_sent / (1024 * 1024),
            "bytes_recv_mb": network_io.bytes_recv / (1024 * 1024)
        }
        
        # 시스템 정보 (시뮬레이션)
        active_agents = len(self.agent_stats)
        running_chains = sum(1 for stats in self.chain_stats.values() 
                           if stats.get('is_running', False))
        
        # API 사용량 (시뮬레이션)
        api_rate_limit_usage = {
            "gemini_quota": 45.2,
            "requests_per_minute": 23
        }
        
        return SystemSnapshot(
            timestamp=datetime.now(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_io=network_data,
            active_agents=active_agents,
            running_chains=running_chains,
            api_rate_limit_usage=api_rate_limit_usage
        )

    async def _collect_metrics(self):
        """각종 메트릭 수집"""
        current_time = datetime.now()
        
        # 시스템 리소스 메트릭
        if self.system_snapshots:
            latest_snapshot = self.system_snapshots[-1]
            
            system_metrics = [
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.SYSTEM_RESOURCE,
                    source="system",
                    metric_name="cpu_usage",
                    value=latest_snapshot.cpu_usage,
                    unit="%"
                ),
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.SYSTEM_RESOURCE,
                    source="system",
                    metric_name="memory_usage",
                    value=latest_snapshot.memory_usage,
                    unit="%"
                ),
                PerformanceMetric(
                    timestamp=current_time,
                    metric_type=MetricType.SYSTEM_RESOURCE,
                    source="system",
                    metric_name="disk_usage",
                    value=latest_snapshot.disk_usage,
                    unit="%"
                )
            ]
            
            for metric in system_metrics:
                self.metrics_buffer.append(metric)

    async def _check_thresholds(self):
        """임계값 확인 및 알림 생성"""
        if not self.system_snapshots:
            return
        
        latest_snapshot = self.system_snapshots[-1]
        
        # CPU 확인
        await self._check_cpu_threshold(latest_snapshot)
        
        # 메모리 확인
        await self._check_memory_threshold(latest_snapshot)
        
        # 디스크 확인
        await self._check_disk_threshold(latest_snapshot)

    async def _check_cpu_threshold(self, snapshot: SystemSnapshot):
        """CPU 임계값 확인"""
        if snapshot.cpu_usage >= self.thresholds.cpu_critical:
            alert = PerformanceAlert(
                id=f"cpu_critical_{int(time.time())}",
                timestamp=snapshot.timestamp,
                level=AlertLevel.CRITICAL,
                source="system",
                title="CPU 사용률 위험",
                message=f"CPU 사용률이 {snapshot.cpu_usage:.1f}%로 위험 수준입니다",
                metric_value=snapshot.cpu_usage,
                threshold_value=self.thresholds.cpu_critical,
                suggested_actions=[
                    "동시 실행 에이전트 수 감소",
                    "배치 크기 축소",
                    "비필수 프로세스 중지"
                ]
            )
            self.alerts.append(alert)
            logger.warning(f"🚨 {alert.title}: {alert.message}")
            
        elif snapshot.cpu_usage >= self.thresholds.cpu_warning:
            alert = PerformanceAlert(
                id=f"cpu_warning_{int(time.time())}",
                timestamp=snapshot.timestamp,
                level=AlertLevel.WARNING,
                source="system",
                title="CPU 사용률 경고",
                message=f"CPU 사용률이 {snapshot.cpu_usage:.1f}%로 경고 수준입니다",
                metric_value=snapshot.cpu_usage,
                threshold_value=self.thresholds.cpu_warning,
                suggested_actions=[
                    "작업 부하 모니터링",
                    "필요시 병렬 처리 수 조정"
                ]
            )
            self.alerts.append(alert)
            logger.warning(f"⚠️ {alert.title}: {alert.message}")

    async def _check_memory_threshold(self, snapshot: SystemSnapshot):
        """메모리 임계값 확인"""
        if snapshot.memory_usage >= self.thresholds.memory_critical:
            alert = PerformanceAlert(
                id=f"memory_critical_{int(time.time())}",
                timestamp=snapshot.timestamp,
                level=AlertLevel.CRITICAL,
                source="system",
                title="메모리 사용률 위험",
                message=f"메모리 사용률이 {snapshot.memory_usage:.1f}%로 위험 수준입니다",
                metric_value=snapshot.memory_usage,
                threshold_value=self.thresholds.memory_critical,
                suggested_actions=[
                    "메모리 집약적 작업 중지",
                    "데이터 배치 크기 감소",
                    "가비지 컬렉션 강제 실행"
                ]
            )
            self.alerts.append(alert)
            logger.error(f"🚨 {alert.title}: {alert.message}")
            
        elif snapshot.memory_usage >= self.thresholds.memory_warning:
            alert = PerformanceAlert(
                id=f"memory_warning_{int(time.time())}",
                timestamp=snapshot.timestamp,
                level=AlertLevel.WARNING,
                source="system",
                title="메모리 사용률 경고",
                message=f"메모리 사용률이 {snapshot.memory_usage:.1f}%로 경고 수준입니다",
                metric_value=snapshot.memory_usage,
                threshold_value=self.thresholds.memory_warning,
                suggested_actions=[
                    "메모리 사용량 모니터링",
                    "불필요한 캐시 정리"
                ]
            )
            self.alerts.append(alert)
            logger.warning(f"⚠️ {alert.title}: {alert.message}")

    async def _check_disk_threshold(self, snapshot: SystemSnapshot):
        """디스크 임계값 확인"""
        if snapshot.disk_usage >= self.thresholds.disk_critical:
            alert = PerformanceAlert(
                id=f"disk_critical_{int(time.time())}",
                timestamp=snapshot.timestamp,
                level=AlertLevel.CRITICAL,
                source="system",
                title="디스크 사용률 위험",
                message=f"디스크 사용률이 {snapshot.disk_usage:.1f}%로 위험 수준입니다",
                metric_value=snapshot.disk_usage,
                threshold_value=self.thresholds.disk_critical,
                suggested_actions=[
                    "불필요한 파일 삭제",
                    "로그 파일 정리",
                    "임시 파일 삭제"
                ]
            )
            self.alerts.append(alert)
            logger.error(f"🚨 {alert.title}: {alert.message}")

    async def _update_performance_stats(self):
        """성능 통계 업데이트"""
        # 시간 기반 통계 계산
        current_time = datetime.now()
        hour_ago = current_time - timedelta(hours=1)
        
        # 최근 1시간 메트릭 필터링
        recent_metrics = [
            m for m in self.metrics_buffer
            if m.timestamp >= hour_ago
        ]
        
        # 시스템 리소스 평균 계산
        if recent_metrics:
            cpu_metrics = [m for m in recent_metrics 
                          if m.metric_name == "cpu_usage"]
            if cpu_metrics:
                avg_cpu = sum(m.value for m in cpu_metrics) / len(cpu_metrics)
                self.agent_stats["system"]["avg_cpu_1h"] = avg_cpu

    def record_agent_metric(
        self,
        agent_name: str,
        metric_name: str,
        value: Union[float, int],
        unit: str = "",
        metadata: Dict[str, Any] = None
    ):
        """에이전트 메트릭 기록"""
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            metric_type=MetricType.AGENT_PERFORMANCE,
            source=agent_name,
            metric_name=metric_name,
            value=value,
            unit=unit,
            metadata=metadata or {}
        )
        
        self.metrics_buffer.append(metric)
        
        # 에이전트 통계 업데이트
        if agent_name not in self.agent_stats:
            self.agent_stats[agent_name] = defaultdict(list)
        
        self.agent_stats[agent_name][metric_name].append({
            'timestamp': metric.timestamp,
            'value': value
        })

    def record_chain_metric(
        self,
        chain_name: str,
        execution_result: Any,
        execution_time: float
    ):
        """체인 실행 메트릭 기록"""
        metric = PerformanceMetric(
            timestamp=datetime.now(),
            metric_type=MetricType.CHAIN_EXECUTION,
            source=chain_name,
            metric_name="execution_time",
            value=execution_time,
            unit="seconds",
            metadata={
                'success': getattr(execution_result, 'success', True),
                'output_length': len(str(execution_result)) if execution_result else 0
            }
        )
        
        self.metrics_buffer.append(metric)
        
        # 체인 통계 업데이트
        if chain_name not in self.chain_stats:
            self.chain_stats[chain_name] = {
                'total_executions': 0,
                'successful_executions': 0,
                'total_time': 0.0,
                'average_time': 0.0
            }
        
        stats = self.chain_stats[chain_name]
        stats['total_executions'] += 1
        stats['total_time'] += execution_time
        stats['average_time'] = stats['total_time'] / stats['total_executions']
        
        if metric.metadata.get('success', True):
            stats['successful_executions'] += 1

    async def get_performance_report(
        self,
        time_range: str = "1hour"
    ) -> Dict[str, Any]:
        """성능 리포트 생성"""
        current_time = datetime.now()
        
        # 시간 범위 계산
        if time_range == "1hour":
            start_time = current_time - timedelta(hours=1)
        elif time_range == "6hours":
            start_time = current_time - timedelta(hours=6)
        elif time_range == "24hours":
            start_time = current_time - timedelta(hours=24)
        else:
            start_time = current_time - timedelta(hours=1)
        
        # 시간 범위 내 데이터 필터링
        relevant_metrics = [
            m for m in self.metrics_buffer
            if m.timestamp >= start_time
        ]
        
        relevant_snapshots = [
            s for s in self.system_snapshots
            if s.timestamp >= start_time
        ]
        
        relevant_alerts = [
            a for a in self.alerts
            if a.timestamp >= start_time
        ]
        
        # 리포트 생성
        report = {
            "report_info": {
                "generated_at": current_time.isoformat(),
                "time_range": time_range,
                "start_time": start_time.isoformat(),
                "end_time": current_time.isoformat()
            },
            "system_overview": await self._generate_system_overview(relevant_snapshots),
            "agent_performance": await self._generate_agent_performance_summary(),
            "chain_performance": await self._generate_chain_performance_summary(),
            "alerts_summary": await self._generate_alerts_summary(relevant_alerts),
            "recommendations": await self._generate_ai_recommendations(
                relevant_metrics, relevant_snapshots, relevant_alerts
            )
        }
        
        return report

    async def _generate_system_overview(
        self,
        snapshots: List[SystemSnapshot]
    ) -> Dict[str, Any]:
        """시스템 개요 생성"""
        if not snapshots:
            return {"message": "데이터 없음"}
        
        # 평균값 계산
        avg_cpu = sum(s.cpu_usage for s in snapshots) / len(snapshots)
        avg_memory = sum(s.memory_usage for s in snapshots) / len(snapshots)
        avg_disk = sum(s.disk_usage for s in snapshots) / len(snapshots)
        
        # 최대값
        max_cpu = max(s.cpu_usage for s in snapshots)
        max_memory = max(s.memory_usage for s in snapshots)
        
        return {
            "resource_usage": {
                "cpu": {
                    "average": round(avg_cpu, 2),
                    "peak": round(max_cpu, 2),
                    "status": "critical" if max_cpu > 85 else "warning" if max_cpu > 70 else "normal"
                },
                "memory": {
                    "average": round(avg_memory, 2),
                    "peak": round(max_memory, 2),
                    "status": "critical" if max_memory > 90 else "warning" if max_memory > 75 else "normal"
                },
                "disk": {
                    "average": round(avg_disk, 2),
                    "status": "warning" if avg_disk > 80 else "normal"
                }
            },
            "activity_level": {
                "active_agents": snapshots[-1].active_agents if snapshots else 0,
                "running_chains": snapshots[-1].running_chains if snapshots else 0
            }
        }

    async def _generate_agent_performance_summary(self) -> Dict[str, Any]:
        """에이전트 성능 요약 생성"""
        summary = {}
        
        for agent_name, stats in self.agent_stats.items():
            if agent_name == "system":
                continue
                
            summary[agent_name] = {
                "metrics_count": len(stats),
                "recent_activity": bool(stats),
                "status": "active" if stats else "inactive"
            }
        
        return {
            "total_agents": len(summary),
            "active_agents": sum(1 for s in summary.values() if s["status"] == "active"),
            "agent_details": summary
        }

    async def _generate_chain_performance_summary(self) -> Dict[str, Any]:
        """체인 성능 요약 생성"""
        summary = {}
        
        for chain_name, stats in self.chain_stats.items():
            success_rate = (stats['successful_executions'] / stats['total_executions'] 
                          if stats['total_executions'] > 0 else 0) * 100
            
            summary[chain_name] = {
                "total_executions": stats['total_executions'],
                "success_rate": round(success_rate, 2),
                "average_execution_time": round(stats['average_time'], 3),
                "status": ("excellent" if success_rate > 95 else 
                          "good" if success_rate > 85 else 
                          "needs_attention")
            }
        
        return {
            "total_chains": len(summary),
            "chain_details": summary
        }

    async def _generate_alerts_summary(
        self,
        alerts: List[PerformanceAlert]
    ) -> Dict[str, Any]:
        """알림 요약 생성"""
        if not alerts:
            return {"total_alerts": 0, "alert_levels": {}}
        
        # 레벨별 분류
        level_counts = defaultdict(int)
        for alert in alerts:
            level_counts[alert.level.value] += 1
        
        # 최근 알림
        recent_alerts = sorted(alerts, key=lambda a: a.timestamp, reverse=True)[:5]
        
        return {
            "total_alerts": len(alerts),
            "alert_levels": dict(level_counts),
            "recent_alerts": [
                {
                    "timestamp": alert.timestamp.isoformat(),
                    "level": alert.level.value,
                    "title": alert.title,
                    "source": alert.source
                }
                for alert in recent_alerts
            ]
        }

    async def _generate_ai_recommendations(
        self,
        metrics: List[PerformanceMetric],
        snapshots: List[SystemSnapshot],
        alerts: List[PerformanceAlert]
    ) -> Dict[str, Any]:
        """AI 기반 권장사항 생성"""
        try:
            # 데이터 요약 준비
            metrics_summary = {
                "total_metrics": len(metrics),
                "metric_types": list(set(m.metric_type.value for m in metrics))
            }
            
            system_state = {
                "snapshots_count": len(snapshots),
                "current_cpu": snapshots[-1].cpu_usage if snapshots else 0,
                "current_memory": snapshots[-1].memory_usage if snapshots else 0
            }
            
            recent_alerts_summary = {
                "total_alerts": len(alerts),
                "critical_alerts": len([a for a in alerts if a.level == AlertLevel.CRITICAL])
            }
            
            # AI 체인 실행
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.analysis_prompt
            )
            
            response = await chain.arun(
                metrics_summary=json.dumps(metrics_summary),
                system_state=json.dumps(system_state),
                recent_alerts=json.dumps(recent_alerts_summary)
            )
            
            # JSON 파싱
            ai_analysis = json.loads(response.strip())
            
            return ai_analysis
            
        except Exception as e:
            logger.warning(f"⚠️ AI 권장사항 생성 실패: {e}")
            return {
                "system_health_score": 50.0,
                "status": "unknown",
                "error": "AI 분석을 사용할 수 없습니다",
                "key_insights": ["AI 분석 시스템에 오류가 발생했습니다"],
                "optimization_recommendations": [],
                "immediate_actions": []
            }

    def get_current_status(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        current_time = datetime.now()
        
        # 최신 스냅샷
        latest_snapshot = self.system_snapshots[-1] if self.system_snapshots else None
        
        # 최근 알림 (1시간 이내)
        hour_ago = current_time - timedelta(hours=1)
        recent_alerts = [a for a in self.alerts if a.timestamp >= hour_ago]
        
        return {
            "monitoring_status": "active" if self.is_monitoring else "inactive",
            "last_update": current_time.isoformat(),
            "system_snapshot": latest_snapshot.to_dict() if latest_snapshot else None,
            "recent_alerts_count": len(recent_alerts),
            "metrics_buffer_size": len(self.metrics_buffer),
            "tracked_agents": len(self.agent_stats),
            "tracked_chains": len(self.chain_stats)
        }

    def clear_old_data(self, hours: int = 24):
        """오래된 데이터 정리"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # 메트릭 정리
        self.metrics_buffer = deque(
            [m for m in self.metrics_buffer if m.timestamp >= cutoff_time],
            maxlen=10000
        )
        
        # 알림 정리
        self.alerts = deque(
            [a for a in self.alerts if a.timestamp >= cutoff_time],
            maxlen=1000
        )
        
        logger.info(f"🧹 {hours}시간 이전 데이터 정리 완료")

    def __del__(self):
        """소멸자 - 리소스 정리"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=False) 