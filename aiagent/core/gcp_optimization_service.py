"""
🏗️ GCP 최적화 통합 서비스

GCP 최적화 시스템과 성능 모니터링을 통합하여 자동화된 최적화 서비스를 제공
- 실시간 최적화 모니터링
- 자동화된 최적화 워크플로우
- 최적화 이력 관리
- 통합 리포트 생성
- 예측 기반 최적화
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import deque

from loguru import logger

from .gcp_optimizer import GCPOptimizer, GCPOptimizationRecommendation, GCPInstanceType, OptimizationLevel
from .performance_monitor import PerformanceMonitor, MetricType, AlertLevel
from .monitoring_integration import MonitoringIntegration, MonitoringConfig
from .agent_system import AIAgentSystem
from ..utils.gemini_client import GeminiClient
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain


class OptimizationServiceStatus(Enum):
    """최적화 서비스 상태"""
    IDLE = "idle"
    MONITORING = "monitoring"
    ANALYZING = "analyzing"
    OPTIMIZING = "optimizing"
    ERROR = "error"


class AutoOptimizationMode(Enum):
    """자동 최적화 모드"""
    DISABLED = "disabled"           # 비활성화
    CONSERVATIVE = "conservative"   # 보수적 자동 최적화
    BALANCED = "balanced"          # 균형 잡힌 자동 최적화
    AGGRESSIVE = "aggressive"      # 적극적 자동 최적화


@dataclass
class OptimizationServiceConfig:
    """최적화 서비스 설정"""
    auto_optimization_mode: AutoOptimizationMode = AutoOptimizationMode.CONSERVATIVE
    optimization_interval: float = 3600.0  # 1시간마다 최적화 검토
    analysis_interval: float = 900.0       # 15분마다 분석
    auto_apply_low_risk: bool = True        # 저위험 권장사항 자동 적용
    auto_apply_threshold: float = 0.8       # 자동 적용 신뢰도 임계값
    
    # 알림 설정
    enable_optimization_alerts: bool = True
    alert_channels: List[str] = field(default_factory=lambda: ["log"])
    
    # 최적화 제한
    max_optimizations_per_day: int = 5
    min_time_between_optimizations: float = 1800.0  # 30분


@dataclass
class OptimizationTask:
    """최적화 작업"""
    id: str
    created_at: datetime
    status: str                     # pending/running/completed/failed
    recommendation_id: str
    estimated_duration: str
    priority: int
    auto_apply: bool = False
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


@dataclass
class OptimizationMetrics:
    """최적화 메트릭"""
    total_optimizations: int = 0
    successful_optimizations: int = 0
    failed_optimizations: int = 0
    total_cost_savings: float = 0.0
    total_performance_improvement: float = 0.0
    average_optimization_time: float = 0.0
    last_optimization: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        return self.successful_optimizations / self.total_optimizations if self.total_optimizations > 0 else 0.0


class GCPOptimizationService:
    """
    🏗️ GCP 최적화 통합 서비스
    
    기능:
    - 실시간 최적화 모니터링
    - 자동화된 최적화 실행
    - 최적화 워크플로우 관리
    - 통합 성능 분석
    - 예측 기반 최적화
    """
    
    def __init__(
        self,
        gcp_optimizer: GCPOptimizer,
        performance_monitor: PerformanceMonitor,
        monitoring_integration: MonitoringIntegration,
        agent_system: AIAgentSystem,
        config: OptimizationServiceConfig = None
    ):
        """
        GCP 최적화 서비스 초기화
        
        Args:
            gcp_optimizer: GCP 최적화 시스템
            performance_monitor: 성능 모니터
            monitoring_integration: 통합 모니터링
            agent_system: AI 에이전트 시스템
            config: 서비스 설정
        """
        self.gcp_optimizer = gcp_optimizer
        self.performance_monitor = performance_monitor
        self.monitoring_integration = monitoring_integration
        self.agent_system = agent_system
        self.config = config or OptimizationServiceConfig()
        
        # 서비스 상태
        self.status = OptimizationServiceStatus.IDLE
        self.is_running = False
        
        # 최적화 작업 관리
        self.optimization_queue: deque = deque()
        self.active_tasks: Dict[str, OptimizationTask] = {}
        self.task_history: deque = deque(maxlen=1000)
        
        # 메트릭 및 통계
        self.metrics = OptimizationMetrics()
        
        # 서비스 태스크
        self.service_tasks: List[asyncio.Task] = []
        
        # AI 클라이언트
        self.gemini_client = GeminiClient()
        
        # 최적화 예측 프롬프트
        self.prediction_prompt = PromptTemplate(
            input_variables=["current_metrics", "historical_data", "optimization_history"],
            template="""
            다음 데이터를 바탕으로 GCP 환경의 최적화 필요성을 예측해주세요:

            현재 메트릭:
            {current_metrics}

            과거 데이터:
            {historical_data}

            최적화 이력:
            {optimization_history}

            다음 형식으로 JSON 응답:
            {{
                "optimization_urgency": 0.75,
                "predicted_issues": [
                    {{
                        "issue": "메모리 부족",
                        "probability": 0.8,
                        "expected_time": "2시간 후",
                        "severity": "high"
                    }}
                ],
                "recommended_actions": [
                    {{
                        "action": "메모리 사용량 최적화",
                        "priority": "high",
                        "expected_benefit": "30% 성능 향상"
                    }}
                ],
                "optimal_optimization_time": "현재",
                "confidence_score": 0.85
            }}
            """
        )
        
        logger.info("🏗️ GCP 최적화 통합 서비스 초기화 완료")

    async def start_service(self):
        """최적화 서비스 시작"""
        if self.is_running:
            logger.warning("⚠️ 최적화 서비스가 이미 실행 중입니다")
            return
        
        self.is_running = True
        self.status = OptimizationServiceStatus.MONITORING
        
        # 기본 모니터링 시스템 시작
        await self.monitoring_integration.start_integrated_monitoring()
        
        # 서비스 태스크들 시작
        if self.config.auto_optimization_mode != AutoOptimizationMode.DISABLED:
            task = asyncio.create_task(self._optimization_monitoring_loop())
            self.service_tasks.append(task)
        
        task = asyncio.create_task(self._analysis_loop())
        self.service_tasks.append(task)
        
        task = asyncio.create_task(self._task_execution_loop())
        self.service_tasks.append(task)
        
        logger.info("🚀 GCP 최적화 서비스 시작 완료")

    async def stop_service(self):
        """최적화 서비스 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        self.status = OptimizationServiceStatus.IDLE
        
        # 모니터링 시스템 중지
        await self.monitoring_integration.stop_integrated_monitoring()
        
        # 서비스 태스크들 중지
        for task in self.service_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self.service_tasks.clear()
        
        logger.info("🛑 GCP 최적화 서비스 중지 완료")

    async def _optimization_monitoring_loop(self):
        """최적화 모니터링 루프"""
        while self.is_running:
            try:
                self.status = OptimizationServiceStatus.MONITORING
                
                # 최적화 필요성 검토
                optimization_needed = await self._check_optimization_needed()
                
                if optimization_needed['needed']:
                    logger.info(f"🔍 최적화 필요성 감지: {optimization_needed['reason']}")
                    
                    # 최적화 분석 수행
                    await self._perform_optimization_analysis()
                
                # 다음 검토까지 대기
                await asyncio.sleep(self.config.optimization_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 최적화 모니터링 루프 오류: {e}")
                await asyncio.sleep(60)  # 오류 발생 시 1분 대기

    async def _analysis_loop(self):
        """정기 분석 루프"""
        while self.is_running:
            try:
                self.status = OptimizationServiceStatus.ANALYZING
                
                # 성능 분석 수행
                analysis_result = await self._perform_periodic_analysis()
                
                # 예측 분석 수행
                prediction_result = await self._perform_predictive_analysis()
                
                # 결과 기록
                if analysis_result.get('recommendations'):
                    await self._process_analysis_recommendations(analysis_result['recommendations'])
                
                # 다음 분석까지 대기
                await asyncio.sleep(self.config.analysis_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 분석 루프 오류: {e}")
                await asyncio.sleep(60)

    async def _task_execution_loop(self):
        """작업 실행 루프"""
        while self.is_running:
            try:
                # 대기 중인 작업 확인
                if self.optimization_queue:
                    task = self.optimization_queue.popleft()
                    await self._execute_optimization_task(task)
                
                # 잠시 대기
                await asyncio.sleep(10)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 작업 실행 루프 오류: {e}")
                await asyncio.sleep(30)

    async def _check_optimization_needed(self) -> Dict[str, Any]:
        """최적화 필요성 검토"""
        
        # 최근 모니터링 데이터 확인
        monitoring_status = self.monitoring_integration.get_monitoring_status()
        performance_status = self.performance_monitor.get_current_status()
        
        # 임계값 확인
        needs_optimization = False
        reasons = []
        
        # 최근 알림 확인
        if self.performance_monitor.alerts:
            recent_alerts = [
                alert for alert in self.performance_monitor.alerts
                if (datetime.now() - alert.timestamp).total_seconds() < 3600  # 1시간 이내
            ]
            
            critical_alerts = [alert for alert in recent_alerts if alert.level == AlertLevel.CRITICAL]
            
            if critical_alerts:
                needs_optimization = True
                reasons.append(f"{len(critical_alerts)}개의 치명적 알림 발생")
        
        # 리소스 사용률 확인
        latest_snapshot = None
        if self.performance_monitor.system_snapshots:
            latest_snapshot = self.performance_monitor.system_snapshots[-1]
            
            if latest_snapshot.cpu_usage > 80 or latest_snapshot.memory_usage > 80:
                needs_optimization = True
                reasons.append("높은 리소스 사용률")
        
        # 마지막 최적화 시점 확인
        if (self.metrics.last_optimization and 
            (datetime.now() - self.metrics.last_optimization).total_seconds() > 86400):  # 24시간
            needs_optimization = True
            reasons.append("24시간 이상 최적화 미수행")
        
        # 일일 최적화 제한 확인
        today_optimizations = len([
            task for task in self.task_history
            if task.completed_at and task.completed_at.date() == datetime.now().date()
        ])
        
        if today_optimizations >= self.config.max_optimizations_per_day:
            needs_optimization = False
            reasons = ["일일 최적화 제한 도달"]
        
        return {
            "needed": needs_optimization,
            "reason": ", ".join(reasons) if reasons else "최적화 불필요",
            "urgency": "high" if "치명적" in str(reasons) else "medium" if needs_optimization else "low",
            "latest_snapshot": asdict(latest_snapshot) if latest_snapshot else None
        }

    async def _perform_optimization_analysis(self):
        """최적화 분석 수행"""
        try:
            logger.info("📊 최적화 분석 시작")
            
            # GCP 환경 분석
            analysis_result = await self.gcp_optimizer.analyze_current_environment()
            
            # 최적화 권장사항 생성
            recommendations = await self.gcp_optimizer.generate_optimization_recommendations(analysis_result)
            
            # 권장사항 처리
            await self._process_analysis_recommendations(recommendations)
            
            logger.info(f"✅ 최적화 분석 완료: {len(recommendations)}개 권장사항")
            
        except Exception as e:
            logger.error(f"❌ 최적화 분석 실패: {e}")

    async def _perform_periodic_analysis(self) -> Dict[str, Any]:
        """정기 성능 분석"""
        try:
            # 통합 성능 리포트 생성
            performance_report = await self.monitoring_integration.get_integrated_report("1hour")
            
            # GCP 특화 분석
            gcp_analysis = await self.gcp_optimizer.analyze_current_environment()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "performance_report": performance_report,
                "gcp_analysis": gcp_analysis,
                "recommendations": []
            }
            
        except Exception as e:
            logger.error(f"❌ 정기 분석 실패: {e}")
            return {"error": str(e)}

    async def _perform_predictive_analysis(self) -> Dict[str, Any]:
        """예측 분석 수행"""
        try:
            # 현재 메트릭 수집
            current_metrics = self.performance_monitor.get_current_status()
            
            # 과거 데이터 수집
            historical_data = {
                "metrics_count": len(self.performance_monitor.metrics_buffer),
                "snapshots_count": len(self.performance_monitor.system_snapshots)
            }
            
            # 최적화 이력
            optimization_history = {
                "total_optimizations": self.metrics.total_optimizations,
                "success_rate": self.metrics.success_rate,
                "recent_optimizations": len(self.task_history)
            }
            
            # AI 예측 실행
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.prediction_prompt
            )
            
            response = await chain.arun(
                current_metrics=json.dumps(current_metrics),
                historical_data=json.dumps(historical_data),
                optimization_history=json.dumps(optimization_history)
            )
            
            prediction_result = json.loads(response.strip())
            
            logger.info(f"🔮 예측 분석 완료: 긴급도 {prediction_result.get('optimization_urgency', 0)}")
            
            return prediction_result
            
        except Exception as e:
            logger.warning(f"⚠️ 예측 분석 실패: {e}")
            return {"error": str(e)}

    async def _process_analysis_recommendations(
        self,
        recommendations: List[GCPOptimizationRecommendation]
    ):
        """분석 권장사항 처리"""
        
        for recommendation in recommendations:
            # 자동 적용 여부 판단
            auto_apply = (
                self.config.auto_apply_low_risk and
                recommendation.risk_level == "low" and
                recommendation.priority <= 2
            )
            
            # 최적화 작업 생성
            task = OptimizationTask(
                id=f"opt_task_{int(time.time())}_{recommendation.id}",
                created_at=datetime.now(),
                status="pending",
                recommendation_id=recommendation.id,
                estimated_duration=recommendation.estimated_time,
                priority=recommendation.priority,
                auto_apply=auto_apply
            )
            
            # 작업 큐에 추가
            self.optimization_queue.append(task)
            self.active_tasks[task.id] = task
            
            logger.info(f"📋 최적화 작업 생성: {task.id} (자동실행: {auto_apply})")

    async def _execute_optimization_task(self, task: OptimizationTask):
        """최적화 작업 실행"""
        try:
            logger.info(f"🚀 최적화 작업 실행 시작: {task.id}")
            
            task.status = "running"
            self.status = OptimizationServiceStatus.OPTIMIZING
            
            # 최적화 적용
            result = await self.gcp_optimizer.apply_optimization(
                task.recommendation_id,
                dry_run=not task.auto_apply
            )
            
            # 결과 처리
            if result.get("error"):
                task.status = "failed"
                task.error_message = result["error"]
                self.metrics.failed_optimizations += 1
            else:
                task.status = "completed"
                task.result = result
                self.metrics.successful_optimizations += 1
                
                # 성과 지표 업데이트
                if "expected_improvement" in result.get("recommendation", {}):
                    improvement = result["recommendation"]["expected_improvement"]
                    if "cost" in improvement:
                        self.metrics.total_cost_savings += improvement["cost"]
                    if "performance" in improvement:
                        self.metrics.total_performance_improvement += improvement["performance"]
            
            task.completed_at = datetime.now()
            self.metrics.total_optimizations += 1
            self.metrics.last_optimization = datetime.now()
            
            # 작업 이력에 추가
            self.task_history.append(task)
            
            # 활성 작업에서 제거
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            
            logger.info(f"✅ 최적화 작업 완료: {task.id} ({task.status})")
            
            # 알림 발송
            if self.config.enable_optimization_alerts:
                await self._send_optimization_alert(task)
            
        except Exception as e:
            logger.error(f"❌ 최적화 작업 실행 실패: {task.id} - {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = datetime.now()
            
            self.metrics.failed_optimizations += 1
            self.metrics.total_optimizations += 1

    async def _send_optimization_alert(self, task: OptimizationTask):
        """최적화 알림 발송"""
        
        if task.status == "completed":
            message = f"✅ 최적화 완료: {task.id}"
            if task.result and "expected_improvement" in task.result.get("recommendation", {}):
                improvement = task.result["recommendation"]["expected_improvement"]
                message += f" (개선: {improvement})"
        else:
            message = f"❌ 최적화 실패: {task.id} - {task.error_message}"
        
        # 로그 알림
        if "log" in self.config.alert_channels:
            logger.info(f"📢 {message}")
        
        # 추가 알림 채널 (이메일, 슬랙 등) 구현 가능

    async def manual_optimization_request(
        self,
        optimization_type: str = "full",
        priority: int = 1
    ) -> Dict[str, Any]:
        """
        수동 최적화 요청
        
        Args:
            optimization_type: 최적화 유형 (full/resource/cost/performance)
            priority: 우선순위 (1-5)
            
        Returns:
            요청 결과
        """
        try:
            logger.info(f"🎯 수동 최적화 요청: {optimization_type}")
            
            # 최적화 분석 수행
            analysis_result = await self.gcp_optimizer.analyze_current_environment()
            
            # 권장사항 생성
            recommendations = await self.gcp_optimizer.generate_optimization_recommendations(analysis_result)
            
            # 유형별 필터링
            if optimization_type != "full":
                recommendations = [
                    rec for rec in recommendations
                    if rec.category == optimization_type
                ]
            
            # 우선순위 적용
            recommendations = [
                rec for rec in recommendations
                if rec.priority <= priority
            ]
            
            # 작업 생성
            created_tasks = []
            for recommendation in recommendations:
                task = OptimizationTask(
                    id=f"manual_opt_{int(time.time())}_{recommendation.id}",
                    created_at=datetime.now(),
                    status="pending",
                    recommendation_id=recommendation.id,
                    estimated_duration=recommendation.estimated_time,
                    priority=recommendation.priority,
                    auto_apply=False  # 수동 요청은 자동 적용 안함
                )
                
                self.optimization_queue.append(task)
                self.active_tasks[task.id] = task
                created_tasks.append(task.id)
            
            return {
                "status": "success",
                "created_tasks": created_tasks,
                "total_recommendations": len(recommendations),
                "estimated_total_time": sum(
                    int(rec.estimated_time.split()[0]) if rec.estimated_time.split()[0].isdigit() else 60
                    for rec in recommendations
                ),
                "analysis_result": analysis_result
            }
            
        except Exception as e:
            logger.error(f"❌ 수동 최적화 요청 실패: {e}")
            return {"status": "error", "error": str(e)}

    async def get_optimization_status(self) -> Dict[str, Any]:
        """최적화 상태 조회"""
        
        # 현재 실행 중인 작업
        running_tasks = [task for task in self.active_tasks.values() if task.status == "running"]
        pending_tasks = [task for task in self.active_tasks.values() if task.status == "pending"]
        
        # 최근 완료된 작업 (24시간 이내)
        recent_completed = [
            task for task in self.task_history
            if (task.completed_at and 
                (datetime.now() - task.completed_at).total_seconds() < 86400)
        ]
        
        return {
            "service_status": self.status.value,
            "is_running": self.is_running,
            "auto_optimization_mode": self.config.auto_optimization_mode.value,
            "queue_status": {
                "pending_tasks": len(pending_tasks),
                "running_tasks": len(running_tasks),
                "queue_size": len(self.optimization_queue)
            },
            "metrics": asdict(self.metrics),
            "recent_activity": {
                "completed_today": len([
                    task for task in recent_completed
                    if task.completed_at.date() == datetime.now().date()
                ]),
                "recent_completed": len(recent_completed),
                "recent_failures": len([
                    task for task in recent_completed
                    if task.status == "failed"
                ])
            },
            "next_scheduled_analysis": (
                datetime.now() + timedelta(seconds=self.config.analysis_interval)
            ).isoformat(),
            "gcp_optimizer_status": {
                "target_instance": self.gcp_optimizer.target_instance.value,
                "optimization_level": self.gcp_optimizer.optimization_level.value,
                "cached_recommendations": len(self.gcp_optimizer.recommendation_cache)
            }
        }

    async def generate_optimization_dashboard(self) -> Dict[str, Any]:
        """
        최적화 대시보드 데이터 생성
        
        Returns:
            대시보드 데이터
        """
        try:
            # 현재 상태
            status = await self.get_optimization_status()
            
            # GCP 환경 분석
            gcp_analysis = await self.gcp_optimizer.analyze_current_environment()
            
            # 성능 리포트
            performance_report = await self.monitoring_integration.get_integrated_report("24hours")
            
            # 비용 분석
            cost_analysis = gcp_analysis.get('cost_analysis', {})
            
            # 최적화 트렌드 (최근 7일)
            recent_tasks = [
                task for task in self.task_history
                if (task.completed_at and 
                    (datetime.now() - task.completed_at).total_seconds() < 604800)  # 7일
            ]
            
            optimization_trend = {}
            for i in range(7):
                date = (datetime.now() - timedelta(days=i)).date()
                day_tasks = [task for task in recent_tasks if task.completed_at.date() == date]
                optimization_trend[date.isoformat()] = {
                    "total": len(day_tasks),
                    "successful": len([task for task in day_tasks if task.status == "completed"]),
                    "failed": len([task for task in day_tasks if task.status == "failed"])
                }
            
            dashboard_data = {
                "generated_at": datetime.now().isoformat(),
                "service_overview": {
                    "status": status["service_status"],
                    "auto_mode": status["auto_optimization_mode"],
                    "uptime": "running" if self.is_running else "stopped"
                },
                "performance_overview": {
                    "current_efficiency": gcp_analysis.get('optimization_potential', {}).get('current_efficiency', 0.5),
                    "optimization_potential": gcp_analysis.get('optimization_potential', {}).get('overall_potential_percent', 0),
                    "cost_efficiency": cost_analysis.get('efficiency_score', 0.5),
                    "monthly_cost": cost_analysis.get('current_monthly_cost', 0),
                    "potential_savings": cost_analysis.get('potential_monthly_savings', 0)
                },
                "optimization_metrics": asdict(self.metrics),
                "current_recommendations": len(self.gcp_optimizer.recommendation_cache),
                "optimization_trend": optimization_trend,
                "resource_status": gcp_analysis.get('system_metrics', {}),
                "alerts": {
                    "critical": len([
                        alert for alert in self.performance_monitor.alerts
                        if alert.level == AlertLevel.CRITICAL
                    ]),
                    "warning": len([
                        alert for alert in self.performance_monitor.alerts
                        if alert.level == AlertLevel.WARNING
                    ])
                },
                "quick_actions": [
                    "수동 최적화 실행",
                    "성능 분석 보고서 생성",
                    "비용 최적화 분석",
                    "리소스 사용량 확인"
                ]
            }
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"❌ 대시보드 생성 실패: {e}")
            return {"error": str(e)}

    def get_service_config(self) -> Dict[str, Any]:
        """서비스 설정 반환"""
        return asdict(self.config)

    async def update_service_config(self, new_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        서비스 설정 업데이트
        
        Args:
            new_config: 새로운 설정
            
        Returns:
            업데이트 결과
        """
        try:
            updated_fields = []
            
            for key, value in new_config.items():
                if hasattr(self.config, key):
                    old_value = getattr(self.config, key)
                    setattr(self.config, key, value)
                    updated_fields.append(f"{key}: {old_value} → {value}")
                    logger.info(f"🔧 설정 업데이트: {key} = {value}")
            
            return {
                "status": "success",
                "updated_fields": updated_fields,
                "new_config": asdict(self.config)
            }
            
        except Exception as e:
            logger.error(f"❌ 설정 업데이트 실패: {e}")
            return {"status": "error", "error": str(e)} 