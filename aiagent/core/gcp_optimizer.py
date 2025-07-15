"""
☁️ GCP e2-small 환경 최적화 시스템

Google Cloud Platform e2-small 인스턴스(2 vCPU, 4GB RAM) 환경에 특화된 최적화 시스템
- 리소스 제약 조건 관리
- 비용 효율성 최적화
- 성능 튜닝 및 모니터링
- 자동 스케일링 권장사항
- AI 워크로드 최적화
"""

import asyncio
import time
import json
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque

from loguru import logger

from .performance_monitor import PerformanceMonitor, MetricType, AlertLevel
from .monitoring_integration import MonitoringIntegration
from ..utils.gemini_client import GeminiClient
from ..utils.rate_limiter import RateLimiter
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain


class GCPInstanceType(Enum):
    """GCP 인스턴스 타입"""
    E2_MICRO = "e2-micro"           # 1 vCPU, 1GB RAM
    E2_SMALL = "e2-small"           # 2 vCPU, 2GB RAM
    E2_MEDIUM = "e2-medium"         # 2 vCPU, 4GB RAM
    E2_STANDARD_2 = "e2-standard-2" # 2 vCPU, 8GB RAM
    E2_STANDARD_4 = "e2-standard-4" # 4 vCPU, 16GB RAM


class OptimizationLevel(Enum):
    """최적화 수준"""
    CONSERVATIVE = "conservative"    # 보수적 최적화
    BALANCED = "balanced"           # 균형 잡힌 최적화
    AGGRESSIVE = "aggressive"       # 적극적 최적화
    MAXIMUM = "maximum"             # 최대 최적화


class ResourceConstraint(Enum):
    """리소스 제약 조건"""
    CPU_BOUND = "cpu_bound"         # CPU 제약
    MEMORY_BOUND = "memory_bound"   # 메모리 제약
    NETWORK_BOUND = "network_bound" # 네트워크 제약
    DISK_BOUND = "disk_bound"       # 디스크 제약
    API_BOUND = "api_bound"         # API 할당량 제약


@dataclass
class GCPResourceSpec:
    """GCP 리소스 사양"""
    instance_type: GCPInstanceType
    vcpu_count: int
    memory_gb: float
    network_tier: str = "standard"
    disk_type: str = "pd-balanced"
    disk_size_gb: int = 10
    
    # 실제 사용 가능한 리소스 (OS 오버헤드 고려)
    @property
    def usable_memory_gb(self) -> float:
        """사용 가능한 메모리 (OS 오버헤드 제외)"""
        return self.memory_gb * 0.85  # 15% OS 오버헤드
    
    @property
    def usable_vcpu_count(self) -> float:
        """사용 가능한 vCPU (시스템 프로세스 제외)"""
        return self.vcpu_count * 0.9  # 10% 시스템 프로세스


@dataclass
class GCPOptimizationRecommendation:
    """GCP 최적화 권장사항"""
    id: str
    category: str                           # resource/cost/performance/scaling
    priority: int                           # 1(높음) ~ 5(낮음)
    title: str
    description: str
    expected_improvement: Dict[str, float]  # {"cpu": 15.0, "memory": 20.0, "cost": 25.0}
    implementation_steps: List[str]
    estimated_effort: str                   # low/medium/high
    estimated_time: str
    cost_impact: str                        # positive/negative/neutral
    risk_level: str                         # low/medium/high
    
    # GCP 특화 정보
    gcp_services: List[str] = field(default_factory=list)
    billing_impact: Optional[str] = None
    monitoring_metrics: List[str] = field(default_factory=list)


@dataclass
class GCPWorkloadProfile:
    """GCP 워크로드 프로파일"""
    workload_type: str                      # ai_inference/web_crawling/data_processing
    peak_cpu_usage: float
    peak_memory_usage: float
    average_cpu_usage: float
    average_memory_usage: float
    network_throughput_mbps: float
    disk_io_iops: float
    api_requests_per_minute: float
    burst_capability_required: bool = False
    
    # 시간대별 패턴
    hourly_patterns: Dict[str, float] = field(default_factory=dict)
    daily_patterns: Dict[str, float] = field(default_factory=dict)


class GCPOptimizer:
    """
    ☁️ GCP e2-small 환경 최적화 시스템
    
    기능:
    - GCP 리소스 사양 분석 및 최적화
    - 비용 효율성 개선
    - 성능 병목점 해결
    - 자동 스케일링 권장사항
    - AI 워크로드 최적화
    """
    
    def __init__(
        self,
        target_instance: GCPInstanceType = GCPInstanceType.E2_SMALL,
        optimization_level: OptimizationLevel = OptimizationLevel.BALANCED,
        performance_monitor: Optional[PerformanceMonitor] = None
    ):
        """
        GCP 최적화 시스템 초기화
        
        Args:
            target_instance: 대상 GCP 인스턴스 타입
            optimization_level: 최적화 수준
            performance_monitor: 성능 모니터링 시스템
        """
        self.target_instance = target_instance
        self.optimization_level = optimization_level
        self.performance_monitor = performance_monitor
        
        # GCP 리소스 사양 정의
        self.resource_specs = {
            GCPInstanceType.E2_MICRO: GCPResourceSpec(GCPInstanceType.E2_MICRO, 1, 1.0),
            GCPInstanceType.E2_SMALL: GCPResourceSpec(GCPInstanceType.E2_SMALL, 2, 2.0),
            GCPInstanceType.E2_MEDIUM: GCPResourceSpec(GCPInstanceType.E2_MEDIUM, 2, 4.0),
            GCPInstanceType.E2_STANDARD_2: GCPResourceSpec(GCPInstanceType.E2_STANDARD_2, 2, 8.0),
            GCPInstanceType.E2_STANDARD_4: GCPResourceSpec(GCPInstanceType.E2_STANDARD_4, 4, 16.0)
        }
        
        self.current_spec = self.resource_specs[target_instance]
        
        # 최적화 히스토리
        self.optimization_history: deque = deque(maxlen=100)
        self.recommendation_cache: Dict[str, GCPOptimizationRecommendation] = {}
        
        # AI 클라이언트
        self.gemini_client = GeminiClient()
        
        # 최적화 임계값 설정
        self._setup_optimization_thresholds()
        
        # Langchain 프롬프트 템플릿
        self._setup_prompts()
        
        logger.info(f"☁️ GCP 최적화 시스템 초기화: {target_instance.value} ({optimization_level.value})")

    def _setup_optimization_thresholds(self):
        """최적화 임계값 설정"""
        base_thresholds = {
            "cpu_warning": 65.0,
            "cpu_critical": 80.0,
            "memory_warning": 70.0,
            "memory_critical": 85.0,
            "cost_efficiency_min": 0.7,
            "performance_score_min": 0.8
        }
        
        # 최적화 수준에 따른 임계값 조정
        if self.optimization_level == OptimizationLevel.CONSERVATIVE:
            self.thresholds = {k: v * 0.8 for k, v in base_thresholds.items()}
        elif self.optimization_level == OptimizationLevel.AGGRESSIVE:
            self.thresholds = {k: v * 1.2 for k, v in base_thresholds.items()}
        elif self.optimization_level == OptimizationLevel.MAXIMUM:
            self.thresholds = {k: v * 1.3 for k, v in base_thresholds.items()}
        else:  # BALANCED
            self.thresholds = base_thresholds

    def _setup_prompts(self):
        """Langchain 프롬프트 템플릿 설정"""
        
        self.gcp_optimization_prompt = PromptTemplate(
            input_variables=["resource_spec", "current_usage", "workload_profile", "constraints"],
            template="""
            GCP e2-small 환경의 최적화 분석을 수행해주세요:

            리소스 사양:
            {resource_spec}

            현재 사용량:
            {current_usage}

            워크로드 프로파일:
            {workload_profile}

            제약 조건:
            {constraints}

            다음 형식으로 JSON 응답:
            {{
                "analysis": {{
                    "current_efficiency": 0.75,
                    "bottlenecks": ["메모리 부족", "API 호출 과다"],
                    "optimization_potential": 35.5
                }},
                "recommendations": [
                    {{
                        "category": "resource/cost/performance/scaling",
                        "priority": 1,
                        "title": "권장사항 제목",
                        "description": "상세 설명",
                        "expected_improvement": {{"cpu": 15.0, "memory": 20.0}},
                        "implementation_steps": ["단계1", "단계2"],
                        "estimated_effort": "low/medium/high",
                        "cost_impact": "positive/negative/neutral",
                        "gcp_services": ["Compute Engine", "Cloud Monitoring"]
                    }}
                ],
                "scaling_recommendations": {{
                    "current_instance_adequate": true,
                    "recommended_instance": "e2-medium",
                    "scaling_triggers": {{"cpu": 85, "memory": 90}},
                    "cost_analysis": {{"current_monthly": 24.27, "optimized_monthly": 18.50}}
                }}
            }}
            """
        )
        
        self.workload_analysis_prompt = PromptTemplate(
            input_variables=["metrics_data", "time_patterns", "resource_constraints"],
            template="""
            다음 워크로드 데이터를 분석하여 GCP 환경 최적화 방안을 제안해주세요:

            메트릭 데이터:
            {metrics_data}

            시간대별 패턴:
            {time_patterns}

            리소스 제약사항:
            {resource_constraints}

            JSON 형식으로 응답:
            {{
                "workload_classification": "ai_inference/web_crawling/data_processing",
                "resource_utilization": {{
                    "cpu_efficiency": 0.82,
                    "memory_efficiency": 0.75,
                    "peak_to_average_ratio": 2.1
                }},
                "optimization_opportunities": [
                    {{
                        "area": "memory_management",
                        "current_waste": 25.5,
                        "optimization_method": "배치 크기 조정",
                        "expected_savings": 20.0
                    }}
                ],
                "recommended_configuration": {{
                    "max_workers": 3,
                    "batch_size": 20,
                    "memory_limit": "3.2GB",
                    "gc_settings": {{"enabled": true, "interval": 300}}
                }}
            }}
            """
        )

    async def analyze_current_environment(self) -> Dict[str, Any]:
        """
        현재 GCP 환경 분석
        
        Returns:
            환경 분석 결과
        """
        logger.info("📊 GCP 환경 분석 시작")
        
        try:
            # 시스템 리소스 수집
            system_metrics = await self._collect_system_metrics()
            
            # 워크로드 프로파일 생성
            workload_profile = await self._analyze_workload_profile()
            
            # 리소스 제약사항 분석
            constraints = await self._analyze_resource_constraints()
            
            # 비용 효율성 분석
            cost_analysis = await self._analyze_cost_efficiency()
            
            # 성능 병목점 분석
            bottlenecks = await self._identify_performance_bottlenecks()
            
            analysis_result = {
                "timestamp": datetime.now().isoformat(),
                "instance_type": self.target_instance.value,
                "resource_specification": asdict(self.current_spec),
                "system_metrics": system_metrics,
                "workload_profile": asdict(workload_profile),
                "resource_constraints": constraints,
                "cost_analysis": cost_analysis,
                "performance_bottlenecks": bottlenecks,
                "optimization_potential": await self._calculate_optimization_potential(
                    system_metrics, workload_profile, constraints
                )
            }
            
            logger.info("✅ GCP 환경 분석 완료")
            return analysis_result
            
        except Exception as e:
            logger.error(f"❌ GCP 환경 분석 실패: {e}")
            return {"error": str(e)}

    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """시스템 메트릭 수집"""
        # CPU 정보
        cpu_info = {
            "usage_percent": psutil.cpu_percent(interval=1),
            "count": psutil.cpu_count(),
            "freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
            "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
        }
        
        # 메모리 정보
        memory_info = psutil.virtual_memory()._asdict()
        memory_info['usage_percent'] = memory_info['percent']
        memory_info['available_gb'] = memory_info['available'] / (1024**3)
        memory_info['used_gb'] = memory_info['used'] / (1024**3)
        
        # 디스크 정보
        disk_info = psutil.disk_usage('/')._asdict()
        disk_info['usage_percent'] = (disk_info['used'] / disk_info['total']) * 100
        
        # 네트워크 정보
        network_info = psutil.net_io_counters()._asdict()
        
        # 프로세스 정보
        process_count = len(psutil.pids())
        
        return {
            "cpu": cpu_info,
            "memory": memory_info,
            "disk": disk_info,
            "network": network_info,
            "process_count": process_count,
            "collection_time": datetime.now().isoformat()
        }

    async def _analyze_workload_profile(self) -> GCPWorkloadProfile:
        """워크로드 프로파일 분석"""
        # 성능 모니터에서 데이터 수집
        if self.performance_monitor:
            # 최근 1시간 데이터 사용
            metrics_data = []
            for metric in list(self.performance_monitor.metrics_buffer)[-60:]:  # 최근 60개
                if metric.metric_type == MetricType.SYSTEM_RESOURCE:
                    metrics_data.append(metric)
        else:
            # 성능 모니터가 없는 경우 현재 값 사용
            current_metrics = await self._collect_system_metrics()
            metrics_data = [current_metrics]
        
        # 워크로드 분류 (AI 추론 기반)
        workload_type = "ai_inference"  # 기본값
        
        # CPU/메모리 사용량 패턴 분석
        if metrics_data:
            if isinstance(metrics_data[0], dict):
                # 딕셔너리 형태의 메트릭
                cpu_values = [m.get('cpu', {}).get('usage_percent', 0) for m in metrics_data]
                memory_values = [m.get('memory', {}).get('usage_percent', 0) for m in metrics_data]
            else:
                # PerformanceMetric 객체
                cpu_values = [m.value for m in metrics_data if m.metric_name == 'cpu_usage']
                memory_values = [m.value for m in metrics_data if m.metric_name == 'memory_usage']
            
            if cpu_values and memory_values:
                peak_cpu = max(cpu_values)
                peak_memory = max(memory_values)
                avg_cpu = sum(cpu_values) / len(cpu_values)
                avg_memory = sum(memory_values) / len(memory_values)
            else:
                # 현재 값 사용
                current = await self._collect_system_metrics()
                peak_cpu = avg_cpu = current['cpu']['usage_percent']
                peak_memory = avg_memory = current['memory']['usage_percent']
        else:
            # 기본값
            current = await self._collect_system_metrics()
            peak_cpu = avg_cpu = current['cpu']['usage_percent']
            peak_memory = avg_memory = current['memory']['usage_percent']
        
        return GCPWorkloadProfile(
            workload_type=workload_type,
            peak_cpu_usage=peak_cpu,
            peak_memory_usage=peak_memory,
            average_cpu_usage=avg_cpu,
            average_memory_usage=avg_memory,
            network_throughput_mbps=10.0,  # 추정값
            disk_io_iops=100.0,  # 추정값
            api_requests_per_minute=30.0,  # 추정값
            burst_capability_required=peak_cpu > avg_cpu * 1.5
        )

    async def _analyze_resource_constraints(self) -> List[ResourceConstraint]:
        """리소스 제약사항 분석"""
        constraints = []
        
        current_metrics = await self._collect_system_metrics()
        
        # CPU 제약 확인
        cpu_usage = current_metrics['cpu']['usage_percent']
        if cpu_usage > self.thresholds['cpu_warning']:
            constraints.append(ResourceConstraint.CPU_BOUND)
        
        # 메모리 제약 확인
        memory_usage = current_metrics['memory']['usage_percent']
        if memory_usage > self.thresholds['memory_warning']:
            constraints.append(ResourceConstraint.MEMORY_BOUND)
        
        # 디스크 제약 확인
        disk_usage = current_metrics['disk']['usage_percent']
        if disk_usage > 80.0:
            constraints.append(ResourceConstraint.DISK_BOUND)
        
        # API 제약 확인 (시뮬레이션)
        # 실제로는 Cloud Monitoring API에서 할당량 정보 수집
        if hasattr(self, 'api_quota_usage') and self.api_quota_usage > 80.0:
            constraints.append(ResourceConstraint.API_BOUND)
        
        return constraints

    async def _analyze_cost_efficiency(self) -> Dict[str, Any]:
        """비용 효율성 분석"""
        # GCP e2-small 기본 비용 (us-central1 기준)
        base_cost_per_hour = 0.033444  # USD
        hours_per_month = 24 * 30
        monthly_base_cost = base_cost_per_hour * hours_per_month
        
        # 실제 리소스 사용률 기반 비용 효율성 계산
        current_metrics = await self._collect_system_metrics()
        
        cpu_utilization = current_metrics['cpu']['usage_percent'] / 100
        memory_utilization = current_metrics['memory']['usage_percent'] / 100
        
        # 평균 사용률
        avg_utilization = (cpu_utilization + memory_utilization) / 2
        
        # 비용 효율성 점수 (사용률 기반)
        efficiency_score = min(avg_utilization / 0.7, 1.0)  # 70% 사용률을 100% 효율성으로 간주
        
        # 예상 절약 가능 비용
        if avg_utilization < 0.3:  # 30% 이하 사용 시 다운그레이드 권장
            potential_savings = monthly_base_cost * 0.4  # e2-micro로 다운그레이드
        elif avg_utilization > 0.9:  # 90% 이상 사용 시 업그레이드 필요
            potential_savings = -monthly_base_cost * 0.5  # e2-medium으로 업그레이드 비용
        else:
            potential_savings = 0
        
        return {
            "current_monthly_cost": monthly_base_cost,
            "efficiency_score": efficiency_score,
            "avg_utilization": avg_utilization,
            "potential_monthly_savings": potential_savings,
            "cost_per_effective_hour": monthly_base_cost / (hours_per_month * avg_utilization) if avg_utilization > 0 else float('inf'),
            "optimization_recommendations": [
                "리소스 사용률 최적화를 통한 비용 절감 가능" if efficiency_score < 0.7 else "현재 비용 효율성 양호"
            ]
        }

    async def _identify_performance_bottlenecks(self) -> List[Dict[str, Any]]:
        """성능 병목점 식별"""
        bottlenecks = []
        
        current_metrics = await self._collect_system_metrics()
        
        # CPU 병목
        cpu_usage = current_metrics['cpu']['usage_percent']
        if cpu_usage > self.thresholds['cpu_critical']:
            bottlenecks.append({
                "type": "cpu",
                "severity": "critical",
                "current_value": cpu_usage,
                "threshold": self.thresholds['cpu_critical'],
                "impact": "high",
                "recommendations": [
                    "동시 작업 수 감소",
                    "CPU 집약적 작업 최적화",
                    "인스턴스 업그레이드 고려"
                ]
            })
        elif cpu_usage > self.thresholds['cpu_warning']:
            bottlenecks.append({
                "type": "cpu",
                "severity": "warning",
                "current_value": cpu_usage,
                "threshold": self.thresholds['cpu_warning'],
                "impact": "medium",
                "recommendations": [
                    "작업 스케줄링 최적화",
                    "불필요한 프로세스 정리"
                ]
            })
        
        # 메모리 병목
        memory_usage = current_metrics['memory']['usage_percent']
        if memory_usage > self.thresholds['memory_critical']:
            bottlenecks.append({
                "type": "memory",
                "severity": "critical",
                "current_value": memory_usage,
                "threshold": self.thresholds['memory_critical'],
                "impact": "high",
                "recommendations": [
                    "메모리 누수 확인",
                    "배치 크기 감소",
                    "가비지 컬렉션 최적화",
                    "메모리 증설 고려"
                ]
            })
        elif memory_usage > self.thresholds['memory_warning']:
            bottlenecks.append({
                "type": "memory",
                "severity": "warning",
                "current_value": memory_usage,
                "threshold": self.thresholds['memory_warning'],
                "impact": "medium",
                "recommendations": [
                    "불필요한 캐시 정리",
                    "메모리 사용량 모니터링 강화"
                ]
            })
        
        # 디스크 I/O 병목 (간접 측정)
        disk_usage = current_metrics['disk']['usage_percent']
        if disk_usage > 90:
            bottlenecks.append({
                "type": "disk",
                "severity": "warning",
                "current_value": disk_usage,
                "threshold": 90,
                "impact": "medium",
                "recommendations": [
                    "불필요한 파일 정리",
                    "로그 파일 로테이션",
                    "디스크 용량 증설"
                ]
            })
        
        return bottlenecks

    async def _calculate_optimization_potential(
        self,
        system_metrics: Dict[str, Any],
        workload_profile: GCPWorkloadProfile,
        constraints: List[ResourceConstraint]
    ) -> Dict[str, Any]:
        """최적화 잠재력 계산"""
        
        # 현재 리소스 사용 효율성
        cpu_efficiency = min(workload_profile.average_cpu_usage / 70.0, 1.0)  # 70%를 최적으로 간주
        memory_efficiency = min(workload_profile.average_memory_usage / 70.0, 1.0)
        
        overall_efficiency = (cpu_efficiency + memory_efficiency) / 2
        
        # 최적화 잠재력 (1 - 효율성)
        optimization_potential = (1 - overall_efficiency) * 100
        
        # 제약사항별 개선 가능성
        improvement_areas = []
        
        if ResourceConstraint.CPU_BOUND in constraints:
            improvement_areas.append({
                "area": "CPU 최적화",
                "potential": min(30.0, optimization_potential * 0.4),
                "methods": ["병렬 처리 최적화", "알고리즘 개선", "캐싱 전략"]
            })
        
        if ResourceConstraint.MEMORY_BOUND in constraints:
            improvement_areas.append({
                "area": "메모리 최적화",
                "potential": min(35.0, optimization_potential * 0.5),
                "methods": ["메모리 풀링", "배치 크기 조정", "가비지 컬렉션 튜닝"]
            })
        
        if ResourceConstraint.API_BOUND in constraints:
            improvement_areas.append({
                "area": "API 최적화",
                "potential": min(25.0, optimization_potential * 0.3),
                "methods": ["요청 캐싱", "배치 처리", "API 호출 최적화"]
            })
        
        return {
            "overall_potential_percent": optimization_potential,
            "current_efficiency": overall_efficiency,
            "improvement_areas": improvement_areas,
            "expected_performance_gain": optimization_potential * 0.6,  # 보수적 추정
            "expected_cost_savings": optimization_potential * 0.4,
            "optimization_complexity": "medium" if optimization_potential > 20 else "low"
        }

    async def generate_optimization_recommendations(
        self,
        analysis_result: Optional[Dict[str, Any]] = None
    ) -> List[GCPOptimizationRecommendation]:
        """
        GCP 최적화 권장사항 생성
        
        Args:
            analysis_result: 환경 분석 결과 (None인 경우 새로 분석)
            
        Returns:
            최적화 권장사항 목록
        """
        logger.info("🎯 GCP 최적화 권장사항 생성 시작")
        
        try:
            # 분석 결과가 없으면 새로 분석
            if not analysis_result:
                analysis_result = await self.analyze_current_environment()
            
            recommendations = []
            
            # 1. 리소스 최적화 권장사항
            resource_recommendations = await self._generate_resource_recommendations(analysis_result)
            recommendations.extend(resource_recommendations)
            
            # 2. 비용 최적화 권장사항
            cost_recommendations = await self._generate_cost_recommendations(analysis_result)
            recommendations.extend(cost_recommendations)
            
            # 3. 성능 최적화 권장사항
            performance_recommendations = await self._generate_performance_recommendations(analysis_result)
            recommendations.extend(performance_recommendations)
            
            # 4. 스케일링 권장사항
            scaling_recommendations = await self._generate_scaling_recommendations(analysis_result)
            recommendations.extend(scaling_recommendations)
            
            # 5. AI 기반 추가 권장사항
            ai_recommendations = await self._generate_ai_recommendations(analysis_result)
            recommendations.extend(ai_recommendations)
            
            # 우선순위별 정렬
            recommendations.sort(key=lambda x: (x.priority, x.risk_level))
            
            # 권장사항 캐시에 저장
            for rec in recommendations:
                self.recommendation_cache[rec.id] = rec
            
            logger.info(f"✅ {len(recommendations)}개의 최적화 권장사항 생성 완료")
            
            return recommendations
            
        except Exception as e:
            logger.error(f"❌ 최적화 권장사항 생성 실패: {e}")
            return []

    async def _generate_resource_recommendations(
        self,
        analysis: Dict[str, Any]
    ) -> List[GCPOptimizationRecommendation]:
        """리소스 최적화 권장사항 생성"""
        recommendations = []
        
        bottlenecks = analysis.get('performance_bottlenecks', [])
        workload = analysis.get('workload_profile', {})
        
        # CPU 최적화
        for bottleneck in bottlenecks:
            if bottleneck.get('type') == 'cpu' and bottleneck.get('severity') == 'critical':
                recommendations.append(GCPOptimizationRecommendation(
                    id=f"cpu_opt_{int(time.time())}",
                    category="resource",
                    priority=1,
                    title="CPU 사용률 최적화",
                    description=f"현재 CPU 사용률이 {bottleneck['current_value']:.1f}%로 임계값을 초과했습니다. 동시 작업 수를 줄이고 CPU 집약적 작업을 최적화해야 합니다.",
                    expected_improvement={"cpu": 25.0, "performance": 20.0},
                    implementation_steps=[
                        "현재 실행 중인 프로세스 분석",
                        "동시 크롤링 워커 수를 2개에서 1개로 감소",
                        "AI 추론 배치 크기를 50%로 감소",
                        "CPU 프로파일링을 통한 병목점 식별"
                    ],
                    estimated_effort="medium",
                    estimated_time="2-4시간",
                    cost_impact="positive",
                    risk_level="low",
                    gcp_services=["Compute Engine", "Cloud Monitoring"],
                    billing_impact="비용 절감 예상",
                    monitoring_metrics=["cpu_utilization", "load_average"]
                ))
        
        # 메모리 최적화
        for bottleneck in bottlenecks:
            if bottleneck.get('type') == 'memory':
                severity = bottleneck.get('severity')
                priority = 1 if severity == 'critical' else 2
                
                recommendations.append(GCPOptimizationRecommendation(
                    id=f"memory_opt_{int(time.time())}",
                    category="resource",
                    priority=priority,
                    title="메모리 사용량 최적화",
                    description=f"메모리 사용률이 {bottleneck['current_value']:.1f}%입니다. 메모리 효율성을 개선하여 안정성을 확보해야 합니다.",
                    expected_improvement={"memory": 30.0, "stability": 25.0},
                    implementation_steps=[
                        "메모리 사용량 분석 및 누수 탐지",
                        "데이터 배치 크기를 25개에서 15개로 감소",
                        "가비지 컬렉션 설정 최적화",
                        "불필요한 캐시 데이터 정리",
                        "메모리 모니터링 강화"
                    ],
                    estimated_effort="medium",
                    estimated_time="3-6시간",
                    cost_impact="positive",
                    risk_level="low",
                    gcp_services=["Compute Engine", "Cloud Monitoring"],
                    monitoring_metrics=["memory_utilization", "memory_usage"]
                ))
        
        return recommendations

    async def _generate_cost_recommendations(
        self,
        analysis: Dict[str, Any]
    ) -> List[GCPOptimizationRecommendation]:
        """비용 최적화 권장사항 생성"""
        recommendations = []
        
        cost_analysis = analysis.get('cost_analysis', {})
        efficiency_score = cost_analysis.get('efficiency_score', 0.5)
        potential_savings = cost_analysis.get('potential_monthly_savings', 0)
        
        if efficiency_score < 0.6:
            recommendations.append(GCPOptimizationRecommendation(
                id=f"cost_efficiency_{int(time.time())}",
                category="cost",
                priority=2,
                title="비용 효율성 개선",
                description=f"현재 비용 효율성이 {efficiency_score:.1%}로 낮습니다. 리소스 사용률을 개선하여 비용을 절감할 수 있습니다.",
                expected_improvement={"cost": abs(potential_savings) / cost_analysis.get('current_monthly_cost', 1) * 100},
                implementation_steps=[
                    "리소스 사용 패턴 분석",
                    "유휴 시간대 작업 스케줄링 최적화",
                    "불필요한 백그라운드 프로세스 정리",
                    "스케줄 기반 자동 종료 설정 고려"
                ],
                estimated_effort="low",
                estimated_time="1-2시간",
                cost_impact="positive",
                risk_level="low",
                gcp_services=["Compute Engine", "Cloud Scheduler"],
                billing_impact=f"월 ${abs(potential_savings):.2f} 절감 예상",
                monitoring_metrics=["billing_data", "resource_utilization"]
            ))
        
        # API 비용 최적화
        workload = analysis.get('workload_profile', {})
        api_rpm = workload.get('api_requests_per_minute', 0)
        
        if api_rpm > 40:  # 높은 API 사용량
            recommendations.append(GCPOptimizationRecommendation(
                id=f"api_cost_opt_{int(time.time())}",
                category="cost",
                priority=2,
                title="AI API 비용 최적화",
                description=f"분당 {api_rpm}회의 API 호출로 비용이 높습니다. 캐싱과 배치 처리를 통해 API 비용을 절감할 수 있습니다.",
                expected_improvement={"cost": 40.0, "api_efficiency": 35.0},
                implementation_steps=[
                    "API 응답 캐싱 시스템 구현",
                    "유사한 요청들의 배치 처리",
                    "저품질 데이터에 대한 AI 처리 생략",
                    "API 사용량 모니터링 강화"
                ],
                estimated_effort="medium",
                estimated_time="4-8시간",
                cost_impact="positive",
                risk_level="low",
                gcp_services=["Vertex AI", "Cloud Functions"],
                billing_impact="API 비용 30-40% 절감 예상",
                monitoring_metrics=["api_request_count", "api_cost"]
            ))
        
        return recommendations

    async def _generate_performance_recommendations(
        self,
        analysis: Dict[str, Any]
    ) -> List[GCPOptimizationRecommendation]:
        """성능 최적화 권장사항 생성"""
        recommendations = []
        
        workload = analysis.get('workload_profile', {})
        optimization_potential = analysis.get('optimization_potential', {})
        
        # 네트워크 최적화
        if workload.get('network_throughput_mbps', 0) > 8:  # e2-small 네트워크 제한 고려
            recommendations.append(GCPOptimizationRecommendation(
                id=f"network_opt_{int(time.time())}",
                category="performance",
                priority=3,
                title="네트워크 처리량 최적화",
                description="높은 네트워크 사용량으로 인한 병목 가능성이 있습니다. 연결 풀링과 압축을 통해 성능을 개선할 수 있습니다.",
                expected_improvement={"network": 25.0, "latency": 20.0},
                implementation_steps=[
                    "HTTP 연결 풀링 구현",
                    "응답 데이터 압축 활성화",
                    "불필요한 네트워크 요청 제거",
                    "CDN 사용 고려 (정적 리소스)"
                ],
                estimated_effort="medium",
                estimated_time="3-5시간",
                cost_impact="neutral",
                risk_level="low",
                gcp_services=["Compute Engine", "Cloud CDN"],
                monitoring_metrics=["network_throughput", "latency"]
            ))
        
        # 워크로드 스케줄링 최적화
        if workload.get('burst_capability_required', False):
            recommendations.append(GCPOptimizationRecommendation(
                id=f"scheduling_opt_{int(time.time())}",
                category="performance",
                priority=2,
                title="워크로드 스케줄링 최적화",
                description="버스트 작업이 감지되었습니다. 작업 스케줄링을 최적화하여 리소스 사용을 평준화할 수 있습니다.",
                expected_improvement={"performance": 30.0, "stability": 25.0},
                implementation_steps=[
                    "피크 시간대 분석",
                    "작업 큐 시스템 구현",
                    "점진적 작업 처리 (스로틀링)",
                    "백그라운드 작업 우선순위 조정"
                ],
                estimated_effort="high",
                estimated_time="1-2일",
                cost_impact="positive",
                risk_level="medium",
                gcp_services=["Cloud Tasks", "Cloud Scheduler"],
                monitoring_metrics=["queue_depth", "processing_time"]
            ))
        
        return recommendations

    async def _generate_scaling_recommendations(
        self,
        analysis: Dict[str, Any]
    ) -> List[GCPOptimizationRecommendation]:
        """스케일링 권장사항 생성"""
        recommendations = []
        
        workload = analysis.get('workload_profile', {})
        cost_analysis = analysis.get('cost_analysis', {})
        
        avg_cpu = workload.get('average_cpu_usage', 0)
        avg_memory = workload.get('average_memory_usage', 0)
        peak_cpu = workload.get('peak_cpu_usage', 0)
        peak_memory = workload.get('peak_memory_usage', 0)
        
        # 다운그레이드 권장 (저사용률)
        if avg_cpu < 30 and avg_memory < 40:
            recommendations.append(GCPOptimizationRecommendation(
                id=f"downgrade_{int(time.time())}",
                category="scaling",
                priority=3,
                title="인스턴스 다운그레이드 고려",
                description=f"평균 리소스 사용률이 낮습니다 (CPU: {avg_cpu:.1f}%, Memory: {avg_memory:.1f}%). e2-micro로 다운그레이드하여 비용을 절감할 수 있습니다.",
                expected_improvement={"cost": 50.0},
                implementation_steps=[
                    "e2-micro 환경에서 테스트 수행",
                    "성능 임계값 모니터링",
                    "점진적 마이그레이션 계획",
                    "롤백 계획 수립"
                ],
                estimated_effort="high",
                estimated_time="1-2일",
                cost_impact="positive",
                risk_level="medium",
                gcp_services=["Compute Engine"],
                billing_impact="월 $12-15 절감 예상",
                monitoring_metrics=["instance_performance", "cost_metrics"]
            ))
        
        # 업그레이드 권장 (고사용률)
        elif peak_cpu > 85 or peak_memory > 85:
            next_instance = "e2-medium" if self.target_instance == GCPInstanceType.E2_SMALL else "e2-standard-2"
            
            recommendations.append(GCPOptimizationRecommendation(
                id=f"upgrade_{int(time.time())}",
                category="scaling",
                priority=1,
                title=f"{next_instance}로 업그레이드 권장",
                description=f"피크 시간 리소스 사용률이 높습니다 (CPU: {peak_cpu:.1f}%, Memory: {peak_memory:.1f}%). 안정성 확보를 위해 업그레이드를 고려해야 합니다.",
                expected_improvement={"performance": 40.0, "stability": 50.0},
                implementation_steps=[
                    "업그레이드 시점 계획",
                    "데이터 백업 수행",
                    "인스턴스 크기 변경",
                    "성능 검증 및 모니터링"
                ],
                estimated_effort="medium",
                estimated_time="2-4시간",
                cost_impact="negative",
                risk_level="low",
                gcp_services=["Compute Engine"],
                billing_impact=f"월 ${24.27 * 0.5:.2f} 비용 증가 예상",
                monitoring_metrics=["instance_performance", "resource_utilization"]
            ))
        
        return recommendations

    async def _generate_ai_recommendations(
        self,
        analysis: Dict[str, Any]
    ) -> List[GCPOptimizationRecommendation]:
        """AI 기반 고급 권장사항 생성"""
        try:
            # AI 체인을 사용한 종합 분석
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.gcp_optimization_prompt
            )
            
            # 분석 데이터 준비
            resource_spec = json.dumps(asdict(self.current_spec))
            current_usage = json.dumps(analysis.get('system_metrics', {}))
            workload_profile = json.dumps(analysis.get('workload_profile', {}))
            constraints = json.dumps([c.value for c in analysis.get('resource_constraints', [])])
            
            # AI 분석 실행
            response = await chain.arun(
                resource_spec=resource_spec,
                current_usage=current_usage,
                workload_profile=workload_profile,
                constraints=constraints
            )
            
            # JSON 응답 파싱
            ai_analysis = json.loads(response.strip())
            
            # AI 권장사항을 GCPOptimizationRecommendation 객체로 변환
            ai_recommendations = []
            
            for rec_data in ai_analysis.get('recommendations', []):
                recommendation = GCPOptimizationRecommendation(
                    id=f"ai_rec_{int(time.time())}_{len(ai_recommendations)}",
                    category=rec_data.get('category', 'performance'),
                    priority=rec_data.get('priority', 3),
                    title=rec_data.get('title', 'AI 권장사항'),
                    description=rec_data.get('description', ''),
                    expected_improvement=rec_data.get('expected_improvement', {}),
                    implementation_steps=rec_data.get('implementation_steps', []),
                    estimated_effort=rec_data.get('estimated_effort', 'medium'),
                    estimated_time="AI 분석 기반",
                    cost_impact=rec_data.get('cost_impact', 'neutral'),
                    risk_level="low",
                    gcp_services=rec_data.get('gcp_services', []),
                    billing_impact="AI 분석 기반 예측",
                    monitoring_metrics=["ai_recommendation_metrics"]
                )
                ai_recommendations.append(recommendation)
            
            return ai_recommendations
            
        except Exception as e:
            logger.warning(f"⚠️ AI 권장사항 생성 실패: {e}")
            return []

    async def apply_optimization(
        self,
        recommendation_id: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        최적화 권장사항 적용
        
        Args:
            recommendation_id: 적용할 권장사항 ID
            dry_run: 테스트 실행 여부
            
        Returns:
            적용 결과
        """
        logger.info(f"🚀 최적화 적용 시작: {recommendation_id} (dry_run: {dry_run})")
        
        if recommendation_id not in self.recommendation_cache:
            return {"error": "권장사항을 찾을 수 없습니다"}
        
        recommendation = self.recommendation_cache[recommendation_id]
        
        try:
            # 사전 검증
            validation_result = await self._validate_optimization(recommendation)
            if not validation_result['valid']:
                return {"error": f"검증 실패: {validation_result['reason']}"}
            
            # 적용 전 상태 백업
            pre_state = await self._capture_system_state()
            
            if dry_run:
                # 드라이 런 시뮬레이션
                simulation_result = await self._simulate_optimization(recommendation)
                return {
                    "status": "dry_run_completed",
                    "recommendation": asdict(recommendation),
                    "validation": validation_result,
                    "simulation": simulation_result,
                    "pre_state": pre_state
                }
            else:
                # 실제 적용
                application_result = await self._apply_optimization_real(recommendation)
                
                # 적용 후 상태 확인
                post_state = await self._capture_system_state()
                
                # 결과 기록
                self.optimization_history.append({
                    "timestamp": datetime.now().isoformat(),
                    "recommendation_id": recommendation_id,
                    "recommendation": asdict(recommendation),
                    "pre_state": pre_state,
                    "post_state": post_state,
                    "result": application_result
                })
                
                return {
                    "status": "applied",
                    "recommendation": asdict(recommendation),
                    "pre_state": pre_state,
                    "post_state": post_state,
                    "application_result": application_result
                }
            
        except Exception as e:
            logger.error(f"❌ 최적화 적용 실패: {e}")
            return {"error": str(e)}

    async def _validate_optimization(
        self,
        recommendation: GCPOptimizationRecommendation
    ) -> Dict[str, Any]:
        """최적화 권장사항 검증"""
        
        # 기본 검증
        if recommendation.risk_level == "high":
            return {
                "valid": False,
                "reason": "고위험 권장사항은 수동 검토가 필요합니다"
            }
        
        # 리소스 가용성 확인
        current_metrics = await self._collect_system_metrics()
        
        if recommendation.category == "scaling":
            # 스케일링 권장사항의 경우 현재 사용률 확인
            cpu_usage = current_metrics['cpu']['usage_percent']
            memory_usage = current_metrics['memory']['usage_percent']
            
            if "업그레이드" in recommendation.title and (cpu_usage < 50 or memory_usage < 50):
                return {
                    "valid": False,
                    "reason": "현재 리소스 사용률이 낮아 업그레이드가 불필요합니다"
                }
        
        return {"valid": True, "reason": "검증 통과"}

    async def _capture_system_state(self) -> Dict[str, Any]:
        """시스템 상태 캡처"""
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": await self._collect_system_metrics(),
            "processes": len(psutil.pids()),
            "instance_type": self.target_instance.value
        }

    async def _simulate_optimization(
        self,
        recommendation: GCPOptimizationRecommendation
    ) -> Dict[str, Any]:
        """최적화 시뮬레이션"""
        
        simulation_result = {
            "simulated_improvements": recommendation.expected_improvement,
            "estimated_risks": [],
            "resource_impact": {},
            "recommendations": [
                "시뮬레이션 결과를 신중히 검토하세요",
                "실제 적용 전 백업을 수행하세요",
                "점진적 적용을 고려하세요"
            ]
        }
        
        # 카테고리별 시뮬레이션
        if recommendation.category == "resource":
            simulation_result["resource_impact"] = {
                "cpu_reduction": recommendation.expected_improvement.get("cpu", 0),
                "memory_reduction": recommendation.expected_improvement.get("memory", 0)
            }
        
        elif recommendation.category == "cost":
            cost_savings = recommendation.expected_improvement.get("cost", 0)
            simulation_result["cost_impact"] = {
                "monthly_savings": f"${cost_savings * 0.24:.2f}",  # 추정 계산
                "annual_savings": f"${cost_savings * 0.24 * 12:.2f}"
            }
        
        return simulation_result

    async def _apply_optimization_real(
        self,
        recommendation: GCPOptimizationRecommendation
    ) -> Dict[str, Any]:
        """실제 최적화 적용 (시뮬레이션)"""
        
        # 실제 환경에서는 GCP API를 통한 리소스 변경을 수행
        # 여기서는 시뮬레이션으로 처리
        
        logger.info(f"🔧 최적화 적용 중: {recommendation.title}")
        
        # 적용 시뮬레이션
        await asyncio.sleep(2)  # 적용 지연 시뮬레이션
        
        return {
            "status": "completed",
            "applied_steps": recommendation.implementation_steps,
            "duration": "2초 (시뮬레이션)",
            "success": True,
            "message": f"{recommendation.title} 적용 완료 (시뮬레이션)"
        }

    def get_optimization_history(self) -> List[Dict[str, Any]]:
        """최적화 이력 반환"""
        return list(self.optimization_history)

    def get_current_recommendations(self) -> List[GCPOptimizationRecommendation]:
        """현재 권장사항 목록 반환"""
        return list(self.recommendation_cache.values())

    async def generate_optimization_report(self) -> Dict[str, Any]:
        """
        종합 최적화 리포트 생성
        
        Returns:
            종합 최적화 리포트
        """
        logger.info("📊 GCP 최적화 리포트 생성 시작")
        
        try:
            # 환경 분석
            analysis = await self.analyze_current_environment()
            
            # 최적화 권장사항 생성
            recommendations = await self.generate_optimization_recommendations(analysis)
            
            # 리포트 구성
            report = {
                "report_metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "target_instance": self.target_instance.value,
                    "optimization_level": self.optimization_level.value,
                    "analysis_version": "1.0.0"
                },
                "executive_summary": {
                    "current_efficiency": analysis.get('optimization_potential', {}).get('current_efficiency', 0.5),
                    "optimization_potential": analysis.get('optimization_potential', {}).get('overall_potential_percent', 0),
                    "total_recommendations": len(recommendations),
                    "high_priority_recommendations": len([r for r in recommendations if r.priority <= 2]),
                    "estimated_cost_savings": analysis.get('cost_analysis', {}).get('potential_monthly_savings', 0)
                },
                "current_state_analysis": analysis,
                "optimization_recommendations": [asdict(rec) for rec in recommendations],
                "implementation_roadmap": self._create_implementation_roadmap(recommendations),
                "monitoring_recommendations": self._generate_monitoring_recommendations(),
                "optimization_history": self.get_optimization_history()
            }
            
            logger.info("✅ GCP 최적화 리포트 생성 완료")
            return report
            
        except Exception as e:
            logger.error(f"❌ 최적화 리포트 생성 실패: {e}")
            return {"error": str(e)}

    def _create_implementation_roadmap(
        self,
        recommendations: List[GCPOptimizationRecommendation]
    ) -> Dict[str, Any]:
        """구현 로드맵 생성"""
        
        # 우선순위별 그룹화
        high_priority = [r for r in recommendations if r.priority <= 2]
        medium_priority = [r for r in recommendations if r.priority == 3]
        low_priority = [r for r in recommendations if r.priority >= 4]
        
        return {
            "phase_1_immediate": {
                "duration": "1-2주",
                "recommendations": [r.title for r in high_priority],
                "expected_impact": "높은 성능 및 비용 개선"
            },
            "phase_2_medium_term": {
                "duration": "1-2개월",
                "recommendations": [r.title for r in medium_priority],
                "expected_impact": "안정성 및 효율성 개선"
            },
            "phase_3_long_term": {
                "duration": "2-6개월",
                "recommendations": [r.title for r in low_priority],
                "expected_impact": "장기적 최적화 및 비용 절감"
            }
        }

    def _generate_monitoring_recommendations(self) -> List[str]:
        """모니터링 권장사항 생성"""
        return [
            "Cloud Monitoring을 통한 실시간 리소스 모니터링 설정",
            "비용 알림 설정 (월 예산 초과 시 알림)",
            "성능 임계값 모니터링 (CPU 80%, 메모리 85%)",
            "API 사용량 추적 및 비용 모니터링",
            "주간 성능 리포트 자동 생성 설정",
            "스케일링 트리거 조건 모니터링"
        ] 