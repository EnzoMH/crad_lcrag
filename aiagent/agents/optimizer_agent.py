# 성능 최적화 및 리소스 관리 에이전트
# 크롤링 성능 모니터링, 리소스 최적화, 시스템 튜닝을 담당하는 AI 에이전트

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio
import json
import logging
import psutil
import time
from enum import Enum
from collections import defaultdict, deque

from ..core.agent_base import BaseAgent, AgentResult, AgentConfig
from ..utils.gemini_client import GeminiClient
from ..utils.rate_limiter import RateLimiter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class OptimizationType(Enum):
    """최적화 유형"""
    PERFORMANCE = "performance"       # 성능 최적화
    RESOURCE = "resource"            # 리소스 최적화
    COST = "cost"                    # 비용 최적화
    QUALITY = "quality"              # 품질 최적화
    THROUGHPUT = "throughput"        # 처리량 최적화

class ResourceType(Enum):
    """리소스 타입"""
    CPU = "cpu"
    MEMORY = "memory"
    NETWORK = "network"
    DISK = "disk"
    API_QUOTA = "api_quota"

@dataclass
class PerformanceMetrics:
    """성능 지표"""
    timestamp: datetime
    cpu_usage: float             # CPU 사용률 (%)
    memory_usage: float          # 메모리 사용률 (%)
    disk_usage: float           # 디스크 사용률 (%)
    network_io: Dict[str, float] # 네트워크 I/O
    
    # 크롤링 관련 지표
    requests_per_minute: float   # 분당 요청 수
    success_rate: float          # 성공률
    average_response_time: float # 평균 응답 시간
    error_rate: float           # 오류율
    
    # AI 관련 지표
    ai_requests_count: int       # AI 요청 수
    ai_response_time: float      # AI 응답 시간
    api_quota_usage: float       # API 할당량 사용률

@dataclass
class OptimizationRecommendation:
    """최적화 권장사항"""
    type: OptimizationType
    priority: int                # 우선순위 (1: 높음, 5: 낮음)
    description: str             # 설명
    expected_improvement: float  # 예상 개선율 (%)
    implementation_cost: str     # 구현 비용 (low/medium/high)
    action_items: List[str]      # 실행 항목들
    estimated_time: str          # 예상 소요 시간

@dataclass
class SystemState:
    """시스템 상태"""
    current_load: float          # 현재 부하
    available_resources: Dict[str, float]  # 사용 가능 리소스
    bottlenecks: List[str]       # 병목 지점들
    recommendations: List[OptimizationRecommendation]

class OptimizerAgent(BaseAgent):
    """
    성능 최적화 및 리소스 관리 에이전트
    
    기능:
    - 실시간 시스템 모니터링
    - 자동 성능 분석 및 병목 지점 탐지
    - AI 기반 최적화 권장사항 생성
    - 리소스 사용량 예측 및 조정
    - GCP e2-small 환경 최적화
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.metrics_history: deque = deque(maxlen=1000)  # 최근 1000개 지표 보관
        self.optimization_history: List[OptimizationRecommendation] = []
        self.rate_limiter = RateLimiter()
        
        # 시스템 임계값 설정
        self.thresholds = {
            "cpu_warning": 70.0,      # CPU 경고 임계값
            "cpu_critical": 85.0,     # CPU 위험 임계값
            "memory_warning": 75.0,   # 메모리 경고 임계값
            "memory_critical": 90.0,  # 메모리 위험 임계값
            "disk_warning": 80.0,     # 디스크 경고 임계값
            "disk_critical": 95.0,    # 디스크 위험 임계값
            "success_rate_min": 85.0, # 최소 성공률
            "response_time_max": 30.0 # 최대 응답 시간 (초)
        }
        
        # Langchain 프롬프트 템플릿
        self.optimization_prompt = PromptTemplate(
            input_variables=["system_metrics", "performance_history", "bottlenecks"],
            template="""
            다음 시스템 지표를 분석하여 성능 최적화 방안을 제안해주세요:

            현재 시스템 지표:
            {system_metrics}

            성능 히스토리:
            {performance_history}

            식별된 병목 지점:
            {bottlenecks}

            환경: GCP e2-small (2 vCPU, 4GB RAM)
            용도: 웹 크롤링 + AI 데이터 처리

            다음 형식으로 최적화 권장사항을 제안해주세요:
            {{
                "recommendations": [
                    {{
                        "type": "performance/resource/cost/quality/throughput",
                        "priority": 1-5,
                        "description": "권장사항 설명",
                        "expected_improvement": 25.5,
                        "implementation_cost": "low/medium/high",
                        "action_items": ["항목1", "항목2"],
                        "estimated_time": "1일/1주/1개월"
                    }}
                ],
                "immediate_actions": ["즉시 실행할 항목들"],
                "long_term_strategy": "장기 전략"
            }}
            """
        )
        
        # 리소스 예측 프롬프트
        self.prediction_prompt = PromptTemplate(
            input_variables=["current_usage", "usage_trend", "workload_forecast"],
            template="""
            다음 정보를 바탕으로 리소스 사용량을 예측해주세요:

            현재 사용량:
            {current_usage}

            사용량 추세:
            {usage_trend}

            예상 작업량:
            {workload_forecast}

            JSON 형식으로 응답:
            {{
                "predictions": {{
                    "next_hour": {{"cpu": 65.5, "memory": 72.1}},
                    "next_day": {{"cpu": 68.2, "memory": 75.0}},
                    "next_week": {{"cpu": 70.0, "memory": 78.5}}
                }},
                "risk_factors": ["위험 요소들"],
                "preventive_measures": ["예방 조치들"]
            }}
            """
        )
    
    async def process(self, data: Dict[str, Any]) -> AgentResult:
        """
        성능 최적화 메인 프로세스
        
        Args:
            data: {
                "operation_type": str (monitor/optimize/predict/analyze),
                "target_metrics": List[str] (모니터링할 지표들),
                "optimization_types": List[OptimizationType],
                "time_range": str (분석 시간 범위)
            }
        
        Returns:
            AgentResult: 최적화 분석 결과
        """
        try:
            operation_type = data.get("operation_type", "monitor")
            target_metrics = data.get("target_metrics", ["all"])
            optimization_types = [OptimizationType(t) for t in data.get("optimization_types", ["performance"])]
            time_range = data.get("time_range", "1hour")
            
            result_data = {}
            
            if operation_type == "monitor":
                # 실시간 모니터링
                result_data = await self._perform_monitoring(target_metrics)
                
            elif operation_type == "optimize":
                # 최적화 분석 및 권장사항 생성
                result_data = await self._perform_optimization(optimization_types)
                
            elif operation_type == "predict":
                # 리소스 사용량 예측
                result_data = await self._perform_prediction(time_range)
                
            elif operation_type == "analyze":
                # 성능 분석
                result_data = await self._perform_analysis(time_range)
            
            else:
                raise ValueError(f"지원하지 않는 작업 유형: {operation_type}")
            
            self.metrics.success_count += 1
            self.metrics.processed_items += 1
            
            return AgentResult(
                success=True,
                data=result_data,
                message=f"최적화 작업 완료: {operation_type}",
                execution_time=self.metrics.get_execution_time(),
                metadata={
                    "agent_type": "OptimizerAgent",
                    "operation_type": operation_type,
                    "processing_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"최적화 프로세스 실패: {str(e)}")
            self.metrics.error_count += 1
            
            return AgentResult(
                success=False,
                data={},
                message=f"최적화 실패: {str(e)}",
                execution_time=self.metrics.get_execution_time(),
                metadata={"error": str(e)}
            )
    
    async def _perform_monitoring(self, target_metrics: List[str]) -> Dict[str, Any]:
        """실시간 모니터링 수행"""
        current_metrics = self._collect_system_metrics()
        self.metrics_history.append(current_metrics)
        
        # 임계값 확인
        alerts = self._check_thresholds(current_metrics)
        
        # 시스템 상태 평가
        system_state = self._evaluate_system_state(current_metrics)
        
        return {
            "current_metrics": asdict(current_metrics),
            "system_state": asdict(system_state),
            "alerts": alerts,
            "trends": self._analyze_trends(),
            "recommendations": [asdict(rec) for rec in system_state.recommendations]
        }
    
    async def _perform_optimization(self, optimization_types: List[OptimizationType]) -> Dict[str, Any]:
        """최적화 분석 및 권장사항 생성"""
        # 현재 시스템 지표 수집
        current_metrics = self._collect_system_metrics()
        
        # 성능 히스토리 분석
        performance_history = self._analyze_performance_history()
        
        # 병목 지점 탐지
        bottlenecks = self._detect_bottlenecks()
        
        # AI 기반 최적화 권장사항 생성
        ai_recommendations = await self._generate_ai_recommendations(
            current_metrics, performance_history, bottlenecks
        )
        
        # 규칙 기반 추가 권장사항
        rule_based_recommendations = self._generate_rule_based_recommendations(
            current_metrics, optimization_types
        )
        
        # 권장사항 통합 및 우선순위 정렬
        all_recommendations = ai_recommendations + rule_based_recommendations
        prioritized_recommendations = sorted(all_recommendations, key=lambda x: x.priority)
        
        return {
            "optimization_analysis": {
                "current_performance": asdict(current_metrics),
                "bottlenecks": bottlenecks,
                "optimization_opportunities": len(prioritized_recommendations)
            },
            "recommendations": [asdict(rec) for rec in prioritized_recommendations],
            "immediate_actions": self._get_immediate_actions(prioritized_recommendations),
            "implementation_roadmap": self._create_implementation_roadmap(prioritized_recommendations)
        }
    
    async def _perform_prediction(self, time_range: str) -> Dict[str, Any]:
        """리소스 사용량 예측"""
        # 현재 사용량 분석
        current_usage = self._analyze_current_usage()
        
        # 사용량 추세 분석
        usage_trend = self._analyze_usage_trend(time_range)
        
        # 작업량 예측
        workload_forecast = self._forecast_workload()
        
        # AI 기반 예측
        ai_prediction = await self._generate_ai_prediction(
            current_usage, usage_trend, workload_forecast
        )
        
        # 통계 기반 예측
        statistical_prediction = self._generate_statistical_prediction()
        
        return {
            "current_usage": current_usage,
            "usage_trends": usage_trend,
            "predictions": {
                "ai_based": ai_prediction,
                "statistical": statistical_prediction
            },
            "capacity_planning": self._generate_capacity_plan(),
            "risk_assessment": self._assess_risks()
        }
    
    async def _perform_analysis(self, time_range: str) -> Dict[str, Any]:
        """성능 분석 수행"""
        # 지정된 시간 범위의 데이터 추출
        time_delta = self._parse_time_range(time_range)
        start_time = datetime.now() - time_delta
        
        relevant_metrics = [
            m for m in self.metrics_history
            if m.timestamp >= start_time
        ]
        
        if not relevant_metrics:
            return {"error": "분석할 데이터가 없습니다"}
        
        # 성능 분석
        performance_analysis = self._analyze_performance_data(relevant_metrics)
        
        # 리소스 효율성 분석
        efficiency_analysis = self._analyze_resource_efficiency(relevant_metrics)
        
        # 병목 패턴 분석
        bottleneck_patterns = self._analyze_bottleneck_patterns(relevant_metrics)
        
        return {
            "analysis_period": {
                "start": start_time.isoformat(),
                "end": datetime.now().isoformat(),
                "data_points": len(relevant_metrics)
            },
            "performance_analysis": performance_analysis,
            "efficiency_analysis": efficiency_analysis,
            "bottleneck_patterns": bottleneck_patterns,
            "insights": self._generate_insights(relevant_metrics)
        }
    
    def _collect_system_metrics(self) -> PerformanceMetrics:
        """현재 시스템 지표 수집"""
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
            "bytes_sent": float(network_io.bytes_sent),
            "bytes_recv": float(network_io.bytes_recv),
            "packets_sent": float(network_io.packets_sent),
            "packets_recv": float(network_io.packets_recv)
        }
        
        # 크롤링 관련 지표 (시뮬레이션)
        requests_per_minute = self._calculate_requests_per_minute()
        success_rate = self._calculate_success_rate()
        average_response_time = self._calculate_average_response_time()
        error_rate = self._calculate_error_rate()
        
        # AI 관련 지표
        ai_metrics = self._collect_ai_metrics()
        
        return PerformanceMetrics(
            timestamp=datetime.now(),
            cpu_usage=cpu_usage,
            memory_usage=memory_usage,
            disk_usage=disk_usage,
            network_io=network_data,
            requests_per_minute=requests_per_minute,
            success_rate=success_rate,
            average_response_time=average_response_time,
            error_rate=error_rate,
            ai_requests_count=ai_metrics["requests_count"],
            ai_response_time=ai_metrics["response_time"],
            api_quota_usage=ai_metrics["quota_usage"]
        )
    
    def _calculate_requests_per_minute(self) -> float:
        """분당 요청 수 계산"""
        # 실제로는 크롤링 시스템에서 가져와야 함
        if len(self.metrics_history) < 2:
            return 0.0
        
        recent_metrics = list(self.metrics_history)[-10:]  # 최근 10개 지표
        if not recent_metrics:
            return 0.0
        
        # 시뮬레이션된 값 반환 (실제로는 크롤링 통계에서 가져옴)
        return 45.0  # 예시값
    
    def _calculate_success_rate(self) -> float:
        """성공률 계산"""
        # 실제로는 크롤링 결과에서 계산
        return 87.5  # 예시값
    
    def _calculate_average_response_time(self) -> float:
        """평균 응답 시간 계산"""
        # 실제로는 HTTP 요청 로그에서 계산
        return 2.3  # 예시값 (초)
    
    def _calculate_error_rate(self) -> float:
        """오류율 계산"""
        # 실제로는 에러 로그에서 계산
        return 12.5  # 예시값 (%)
    
    def _collect_ai_metrics(self) -> Dict[str, float]:
        """AI 관련 지표 수집"""
        # Gemini API 사용량 통계
        rate_limiter_stats = self.rate_limiter.get_statistics()
        
        return {
            "requests_count": rate_limiter_stats.get("requests_count", 0),
            "response_time": rate_limiter_stats.get("avg_response_time", 0.0),
            "quota_usage": rate_limiter_stats.get("quota_usage_percent", 0.0)
        }
    
    def _check_thresholds(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """임계값 확인 및 알림 생성"""
        alerts = []
        
        # CPU 확인
        if metrics.cpu_usage >= self.thresholds["cpu_critical"]:
            alerts.append({
                "type": "critical",
                "resource": "cpu",
                "current_value": metrics.cpu_usage,
                "threshold": self.thresholds["cpu_critical"],
                "message": "CPU 사용률이 위험 수준입니다"
            })
        elif metrics.cpu_usage >= self.thresholds["cpu_warning"]:
            alerts.append({
                "type": "warning",
                "resource": "cpu",
                "current_value": metrics.cpu_usage,
                "threshold": self.thresholds["cpu_warning"],
                "message": "CPU 사용률이 경고 수준입니다"
            })
        
        # 메모리 확인
        if metrics.memory_usage >= self.thresholds["memory_critical"]:
            alerts.append({
                "type": "critical",
                "resource": "memory",
                "current_value": metrics.memory_usage,
                "threshold": self.thresholds["memory_critical"],
                "message": "메모리 사용률이 위험 수준입니다"
            })
        elif metrics.memory_usage >= self.thresholds["memory_warning"]:
            alerts.append({
                "type": "warning",
                "resource": "memory",
                "current_value": metrics.memory_usage,
                "threshold": self.thresholds["memory_warning"],
                "message": "메모리 사용률이 경고 수준입니다"
            })
        
        # 성능 지표 확인
        if metrics.success_rate < self.thresholds["success_rate_min"]:
            alerts.append({
                "type": "warning",
                "resource": "success_rate",
                "current_value": metrics.success_rate,
                "threshold": self.thresholds["success_rate_min"],
                "message": "크롤링 성공률이 낮습니다"
            })
        
        if metrics.average_response_time > self.thresholds["response_time_max"]:
            alerts.append({
                "type": "warning",
                "resource": "response_time",
                "current_value": metrics.average_response_time,
                "threshold": self.thresholds["response_time_max"],
                "message": "응답 시간이 너무 깁니다"
            })
        
        return alerts
    
    def _evaluate_system_state(self, metrics: PerformanceMetrics) -> SystemState:
        """시스템 상태 평가"""
        # 현재 부하 계산
        current_load = (metrics.cpu_usage + metrics.memory_usage) / 200  # 평균 부하율
        
        # 사용 가능 리소스 계산
        available_resources = {
            "cpu": 100 - metrics.cpu_usage,
            "memory": 100 - metrics.memory_usage,
            "disk": 100 - metrics.disk_usage
        }
        
        # 병목 지점 탐지
        bottlenecks = []
        if metrics.cpu_usage > 80:
            bottlenecks.append("CPU")
        if metrics.memory_usage > 80:
            bottlenecks.append("Memory")
        if metrics.average_response_time > 10:
            bottlenecks.append("Network")
        
        # 즉시 권장사항 생성
        recommendations = self._generate_immediate_recommendations(metrics, bottlenecks)
        
        return SystemState(
            current_load=current_load,
            available_resources=available_resources,
            bottlenecks=bottlenecks,
            recommendations=recommendations
        )
    
    def _generate_immediate_recommendations(
        self,
        metrics: PerformanceMetrics,
        bottlenecks: List[str]
    ) -> List[OptimizationRecommendation]:
        """즉시 권장사항 생성"""
        recommendations = []
        
        # CPU 최적화
        if metrics.cpu_usage > 80:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.PERFORMANCE,
                priority=1,
                description="동시 크롤링 스레드 수 감소",
                expected_improvement=15.0,
                implementation_cost="low",
                action_items=["max_workers 값을 현재의 50%로 감소", "배치 크기 축소"],
                estimated_time="즉시"
            ))
        
        # 메모리 최적화
        if metrics.memory_usage > 80:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.RESOURCE,
                priority=1,
                description="메모리 사용량 감소",
                expected_improvement=20.0,
                implementation_cost="low",
                action_items=["크롤링 데이터 배치 크기 감소", "가비지 컬렉션 강제 실행"],
                estimated_time="즉시"
            ))
        
        # 성공률 개선
        if metrics.success_rate < 85:
            recommendations.append(OptimizationRecommendation(
                type=OptimizationType.QUALITY,
                priority=2,
                description="크롤링 성공률 향상",
                expected_improvement=10.0,
                implementation_cost="medium",
                action_items=["재시도 로직 강화", "타임아웃 값 조정", "사용자 에이전트 순환"],
                estimated_time="1일"
            ))
        
        return recommendations
    
    def _analyze_trends(self) -> Dict[str, Any]:
        """성능 추세 분석"""
        if len(self.metrics_history) < 10:
            return {"message": "충분한 데이터가 없습니다"}
        
        recent_metrics = list(self.metrics_history)[-10:]
        
        # CPU 추세
        cpu_values = [m.cpu_usage for m in recent_metrics]
        cpu_trend = "increasing" if cpu_values[-1] > cpu_values[0] else "decreasing"
        
        # 메모리 추세
        memory_values = [m.memory_usage for m in recent_metrics]
        memory_trend = "increasing" if memory_values[-1] > memory_values[0] else "decreasing"
        
        # 성능 추세
        success_values = [m.success_rate for m in recent_metrics]
        performance_trend = "improving" if success_values[-1] > success_values[0] else "degrading"
        
        return {
            "cpu_trend": cpu_trend,
            "memory_trend": memory_trend,
            "performance_trend": performance_trend,
            "analysis_period": f"최근 {len(recent_metrics)}개 측정값"
        }
    
    def _detect_bottlenecks(self) -> List[str]:
        """병목 지점 탐지"""
        bottlenecks = []
        
        if not self.metrics_history:
            return bottlenecks
        
        recent_metrics = list(self.metrics_history)[-5:]  # 최근 5개 지표
        
        # 평균값 계산
        avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
        avg_response_time = sum(m.average_response_time for m in recent_metrics) / len(recent_metrics)
        
        # 병목 지점 판단
        if avg_cpu > 75:
            bottlenecks.append("CPU 과부하")
        if avg_memory > 80:
            bottlenecks.append("메모리 부족")
        if avg_response_time > 10:
            bottlenecks.append("네트워크 지연")
        
        return bottlenecks
    
    async def _generate_ai_recommendations(
        self,
        current_metrics: PerformanceMetrics,
        performance_history: Dict,
        bottlenecks: List[str]
    ) -> List[OptimizationRecommendation]:
        """AI 기반 최적화 권장사항 생성"""
        try:
            # AI 체인 생성
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.optimization_prompt
            )
            
            # 지표 데이터 준비
            metrics_summary = f"CPU: {current_metrics.cpu_usage}%, Memory: {current_metrics.memory_usage}%, Success Rate: {current_metrics.success_rate}%"
            history_summary = json.dumps(performance_history)
            bottlenecks_str = ", ".join(bottlenecks) if bottlenecks else "없음"
            
            # AI 실행
            response = await chain.arun(
                system_metrics=metrics_summary,
                performance_history=history_summary,
                bottlenecks=bottlenecks_str
            )
            
            # JSON 파싱
            ai_data = json.loads(response.strip())
            recommendations = []
            
            for rec_data in ai_data.get("recommendations", []):
                recommendation = OptimizationRecommendation(
                    type=OptimizationType(rec_data.get("type", "performance")),
                    priority=rec_data.get("priority", 3),
                    description=rec_data.get("description", ""),
                    expected_improvement=rec_data.get("expected_improvement", 0.0),
                    implementation_cost=rec_data.get("implementation_cost", "medium"),
                    action_items=rec_data.get("action_items", []),
                    estimated_time=rec_data.get("estimated_time", "미정")
                )
                recommendations.append(recommendation)
            
            return recommendations
            
        except Exception as e:
            logger.warning(f"AI 권장사항 생성 실패: {str(e)}")
            return []
    
    def _generate_rule_based_recommendations(
        self,
        metrics: PerformanceMetrics,
        optimization_types: List[OptimizationType]
    ) -> List[OptimizationRecommendation]:
        """규칙 기반 권장사항 생성"""
        recommendations = []
        
        # GCP e2-small 환경 특화 권장사항
        if OptimizationType.RESOURCE in optimization_types:
            if metrics.memory_usage > 70:
                recommendations.append(OptimizationRecommendation(
                    type=OptimizationType.RESOURCE,
                    priority=2,
                    description="GCP e2-small 메모리 최적화",
                    expected_improvement=25.0,
                    implementation_cost="low",
                    action_items=[
                        "크롤링 배치 크기를 50개에서 25개로 감소",
                        "불필요한 데이터 캐시 정리",
                        "가비지 컬렉션 주기 조정"
                    ],
                    estimated_time="30분"
                ))
        
        if OptimizationType.PERFORMANCE in optimization_types:
            if metrics.success_rate < 90:
                recommendations.append(OptimizationRecommendation(
                    type=OptimizationType.PERFORMANCE,
                    priority=1,
                    description="크롤링 안정성 향상",
                    expected_improvement=15.0,
                    implementation_cost="medium",
                    action_items=[
                        "User-Agent 로테이션 구현",
                        "요청 간격 증가 (1초 → 2초)",
                        "실패 시 지수 백오프 재시도"
                    ],
                    estimated_time="2시간"
                ))
        
        if OptimizationType.COST in optimization_types:
            if metrics.api_quota_usage > 80:
                recommendations.append(OptimizationRecommendation(
                    type=OptimizationType.COST,
                    priority=2,
                    description="API 비용 최적화",
                    expected_improvement=30.0,
                    implementation_cost="medium",
                    action_items=[
                        "Gemini API 호출 캐싱 구현",
                        "배치 요청으로 API 호출 감소",
                        "저품질 데이터에 대한 AI 처리 생략"
                    ],
                    estimated_time="1일"
                ))
        
        return recommendations
    
    def _parse_time_range(self, time_range: str) -> timedelta:
        """시간 범위 문자열 파싱"""
        if time_range == "1hour":
            return timedelta(hours=1)
        elif time_range == "6hours":
            return timedelta(hours=6)
        elif time_range == "1day":
            return timedelta(days=1)
        elif time_range == "1week":
            return timedelta(weeks=1)
        else:
            return timedelta(hours=1)  # 기본값
    
    def _analyze_performance_history(self) -> Dict[str, Any]:
        """성능 히스토리 분석"""
        if len(self.metrics_history) < 10:
            return {"status": "insufficient_data"}
        
        recent_metrics = list(self.metrics_history)[-20:]  # 최근 20개
        
        # 평균 성능 지표
        avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)
        avg_success_rate = sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
        
        # 성능 변화율
        first_half = recent_metrics[:10]
        second_half = recent_metrics[10:]
        
        cpu_change = (sum(m.cpu_usage for m in second_half) / 10) - (sum(m.cpu_usage for m in first_half) / 10)
        memory_change = (sum(m.memory_usage for m in second_half) / 10) - (sum(m.memory_usage for m in first_half) / 10)
        
        return {
            "averages": {
                "cpu": avg_cpu,
                "memory": avg_memory,
                "success_rate": avg_success_rate
            },
            "trends": {
                "cpu_change": cpu_change,
                "memory_change": memory_change
            },
            "analysis_period": f"{len(recent_metrics)}개 측정점"
        }
    
    async def _generate_ai_prediction(
        self,
        current_usage: Dict,
        usage_trend: Dict,
        workload_forecast: Dict
    ) -> Dict[str, Any]:
        """AI 기반 리소스 사용량 예측"""
        try:
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.prediction_prompt
            )
            
            response = await chain.arun(
                current_usage=json.dumps(current_usage),
                usage_trend=json.dumps(usage_trend),
                workload_forecast=json.dumps(workload_forecast)
            )
            
            return json.loads(response.strip())
            
        except Exception as e:
            logger.warning(f"AI 예측 실패: {str(e)}")
            return {"error": "AI 예측을 수행할 수 없습니다"}
    
    def _analyze_current_usage(self) -> Dict[str, float]:
        """현재 리소스 사용량 분석"""
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        return {
            "cpu": latest.cpu_usage,
            "memory": latest.memory_usage,
            "disk": latest.disk_usage,
            "network_io": sum(latest.network_io.values())
        }
    
    def _analyze_usage_trend(self, time_range: str) -> Dict[str, str]:
        """사용량 추세 분석"""
        if len(self.metrics_history) < 5:
            return {"status": "insufficient_data"}
        
        recent = list(self.metrics_history)[-5:]
        
        cpu_trend = "stable"
        if recent[-1].cpu_usage > recent[0].cpu_usage + 10:
            cpu_trend = "increasing"
        elif recent[-1].cpu_usage < recent[0].cpu_usage - 10:
            cpu_trend = "decreasing"
        
        memory_trend = "stable"
        if recent[-1].memory_usage > recent[0].memory_usage + 10:
            memory_trend = "increasing"
        elif recent[-1].memory_usage < recent[0].memory_usage - 10:
            memory_trend = "decreasing"
        
        return {
            "cpu_trend": cpu_trend,
            "memory_trend": memory_trend,
            "time_period": time_range
        }
    
    def _forecast_workload(self) -> Dict[str, Any]:
        """작업량 예측"""
        # 실제로는 크롤링 스케줄과 대상 데이터 크기를 기반으로 예측
        return {
            "expected_crawl_targets": 1000,
            "estimated_duration": "2시간",
            "peak_hours": ["10:00-12:00", "14:00-16:00"]
        }
    
    def _generate_statistical_prediction(self) -> Dict[str, Any]:
        """통계 기반 예측"""
        if len(self.metrics_history) < 10:
            return {"error": "insufficient_data"}
        
        recent = list(self.metrics_history)[-10:]
        
        # 평균값 기반 예측
        avg_cpu = sum(m.cpu_usage for m in recent) / len(recent)
        avg_memory = sum(m.memory_usage for m in recent) / len(recent)
        
        # 추세 기반 조정
        cpu_slope = (recent[-1].cpu_usage - recent[0].cpu_usage) / len(recent)
        memory_slope = (recent[-1].memory_usage - recent[0].memory_usage) / len(recent)
        
        return {
            "next_hour": {
                "cpu": min(100, max(0, avg_cpu + cpu_slope * 6)),
                "memory": min(100, max(0, avg_memory + memory_slope * 6))
            },
            "confidence": 0.7
        }
    
    def _generate_capacity_plan(self) -> Dict[str, Any]:
        """용량 계획 생성"""
        return {
            "current_capacity": "GCP e2-small (2 vCPU, 4GB RAM)",
            "recommended_upgrades": [],
            "scaling_triggers": {
                "cpu_threshold": 85,
                "memory_threshold": 90,
                "sustained_duration": "15분"
            }
        }
    
    def _assess_risks(self) -> List[str]:
        """위험 요소 평가"""
        risks = []
        
        if not self.metrics_history:
            return ["데이터 부족으로 위험 평가 불가"]
        
        latest = self.metrics_history[-1]
        
        if latest.cpu_usage > 80:
            risks.append("CPU 과부하 위험")
        if latest.memory_usage > 85:
            risks.append("메모리 부족 위험")
        if latest.success_rate < 80:
            risks.append("서비스 안정성 위험")
        
        return risks
    
    def _get_immediate_actions(self, recommendations: List[OptimizationRecommendation]) -> List[str]:
        """즉시 실행 가능한 항목들 추출"""
        immediate_actions = []
        
        for rec in recommendations:
            if rec.priority == 1 and rec.implementation_cost == "low":
                immediate_actions.extend(rec.action_items)
        
        return immediate_actions[:5]  # 최대 5개
    
    def _create_implementation_roadmap(self, recommendations: List[OptimizationRecommendation]) -> Dict[str, List[str]]:
        """구현 로드맵 생성"""
        roadmap = {
            "immediate": [],
            "short_term": [],
            "long_term": []
        }
        
        for rec in recommendations:
            if rec.estimated_time in ["즉시", "30분", "1시간"]:
                roadmap["immediate"].append(rec.description)
            elif rec.estimated_time in ["1일", "2일", "1주"]:
                roadmap["short_term"].append(rec.description)
            else:
                roadmap["long_term"].append(rec.description)
        
        return roadmap
    
    def _analyze_performance_data(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """성능 데이터 분석"""
        if not metrics:
            return {}
        
        # 평균값 계산
        avg_cpu = sum(m.cpu_usage for m in metrics) / len(metrics)
        avg_memory = sum(m.memory_usage for m in metrics) / len(metrics)
        avg_success_rate = sum(m.success_rate for m in metrics) / len(metrics)
        
        # 최대/최소값
        max_cpu = max(m.cpu_usage for m in metrics)
        min_cpu = min(m.cpu_usage for m in metrics)
        
        return {
            "averages": {
                "cpu": avg_cpu,
                "memory": avg_memory,
                "success_rate": avg_success_rate
            },
            "ranges": {
                "cpu_range": [min_cpu, max_cpu],
                "performance_stability": max_cpu - min_cpu < 20
            }
        }
    
    def _analyze_resource_efficiency(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """리소스 효율성 분석"""
        if not metrics:
            return {}
        
        # 효율성 지표 계산
        efficiency_scores = []
        for m in metrics:
            # 성공률 대비 리소스 사용률
            resource_usage = (m.cpu_usage + m.memory_usage) / 2
            if resource_usage > 0:
                efficiency = m.success_rate / resource_usage
                efficiency_scores.append(efficiency)
        
        avg_efficiency = sum(efficiency_scores) / len(efficiency_scores) if efficiency_scores else 0
        
        return {
            "efficiency_score": avg_efficiency,
            "resource_utilization": "good" if avg_efficiency > 1.0 else "needs_improvement"
        }
    
    def _analyze_bottleneck_patterns(self, metrics: List[PerformanceMetrics]) -> Dict[str, Any]:
        """병목 패턴 분석"""
        patterns = defaultdict(int)
        
        for m in metrics:
            if m.cpu_usage > 80:
                patterns["cpu_bottleneck"] += 1
            if m.memory_usage > 80:
                patterns["memory_bottleneck"] += 1
            if m.average_response_time > 10:
                patterns["network_bottleneck"] += 1
        
        return dict(patterns)
    
    def _generate_insights(self, metrics: List[PerformanceMetrics]) -> List[str]:
        """인사이트 생성"""
        insights = []
        
        if not metrics:
            return ["분석할 데이터가 없습니다"]
        
        avg_cpu = sum(m.cpu_usage for m in metrics) / len(metrics)
        avg_memory = sum(m.memory_usage for m in metrics) / len(metrics)
        avg_success_rate = sum(m.success_rate for m in metrics) / len(metrics)
        
        if avg_cpu > 70:
            insights.append("CPU 사용률이 높습니다. 작업 병렬성을 줄이는 것을 고려하세요.")
        
        if avg_memory > 75:
            insights.append("메모리 사용률이 높습니다. 데이터 배치 크기를 줄이세요.")
        
        if avg_success_rate < 85:
            insights.append("크롤링 성공률이 낮습니다. 재시도 로직과 대기 시간을 조정하세요.")
        
        if len(insights) == 0:
            insights.append("시스템이 안정적으로 운영되고 있습니다.")
        
        return insights 