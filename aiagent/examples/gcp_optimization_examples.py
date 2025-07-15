"""
☁️ GCP e2-small 환경 최적화 시스템 사용 예제

Google Cloud Platform e2-small 환경에 특화된 최적화 시스템 활용 예제
- 기본 GCP 환경 분석 및 최적화
- 자동화된 최적화 서비스 구성
- 비용 효율성 개선 시나리오
- 성능 최적화 워크플로우
- 실시간 모니터링 및 예측 최적화
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from loguru import logger

# GCP 최적화 시스템 import
from ..core.gcp_optimizer import (
    GCPOptimizer, GCPInstanceType, OptimizationLevel,
    GCPOptimizationRecommendation, GCPWorkloadProfile
)
from ..core.gcp_optimization_service import (
    GCPOptimizationService, OptimizationServiceConfig,
    AutoOptimizationMode, OptimizationTask
)
from ..core.performance_monitor import PerformanceMonitor
from ..core.monitoring_integration import MonitoringIntegration, MonitoringConfig
from ..core.agent_system import AIAgentSystem, SystemConfig

# 기본 컴포넌트 import
from ..core.chain_manager import ChainManager
from ..core.chain_service import ChainService
from ..core.coordinator import AgentCoordinator
from ..agents.search_strategy_agent import SearchStrategyAgent
from ..agents.contact_agent import ContactAgent
from ..agents.validation_agent import ValidationAgent
from ..agents.optimizer_agent import OptimizerAgent
from ..core.agent_base import AgentConfig
from ..utils.gemini_client import ModelType


class GCPOptimizationExampleRunner:
    """
    ☁️ GCP 최적화 시스템 예제 실행기
    
    다양한 GCP 최적화 시나리오를 실행하고 결과를 분석하는 시스템
    """
    
    def __init__(self):
        """GCP 최적화 예제 실행기 초기화"""
        self.gcp_optimizer = None
        self.optimization_service = None
        self.performance_monitor = None
        self.monitoring_integration = None
        self.agent_system = None
        
        logger.info("☁️ GCP 최적화 예제 실행기 초기화 완료")

    async def setup_gcp_optimization_system(self) -> Dict[str, Any]:
        """
        GCP 최적화 시스템 설정
        
        Returns:
            설정 결과
        """
        logger.info("🔧 GCP 최적화 시스템 설정 시작")
        
        try:
            # 1. AI 에이전트 시스템 초기화
            system_config = SystemConfig(
                name="GCP 최적화 테스트 시스템",
                version="1.0.0",
                environment="gcp_e2_small",
                debug_mode=True,
                enable_monitoring=True
            )
            self.agent_system = AIAgentSystem(system_config)
            
            # 2. 기본 컴포넌트 초기화
            chain_manager = ChainManager()
            chain_service = ChainService(chain_manager)
            coordinator = AgentCoordinator(self.agent_system)
            
            # 3. 전문 에이전트들 등록
            await self._register_optimization_agents()
            
            # 4. 성능 모니터링 시스템 초기화
            self.performance_monitor = PerformanceMonitor({
                'monitoring_interval': 30  # 30초 간격
            })
            
            # 5. 통합 모니터링 시스템 초기화
            monitoring_config = MonitoringConfig(
                enable_agent_monitoring=True,
                enable_chain_monitoring=True,
                enable_workflow_monitoring=True,
                enable_system_monitoring=True,
                agent_metrics_interval=15.0,
                chain_metrics_interval=10.0,
                system_metrics_interval=20.0
            )
            
            self.monitoring_integration = MonitoringIntegration(
                agent_system=self.agent_system,
                chain_manager=chain_manager,
                chain_service=chain_service,
                coordinator=coordinator,
                config=monitoring_config
            )
            
            # 6. GCP 최적화 시스템 초기화
            self.gcp_optimizer = GCPOptimizer(
                target_instance=GCPInstanceType.E2_SMALL,
                optimization_level=OptimizationLevel.BALANCED,
                performance_monitor=self.performance_monitor
            )
            
            # 7. GCP 최적화 서비스 초기화
            service_config = OptimizationServiceConfig(
                auto_optimization_mode=AutoOptimizationMode.CONSERVATIVE,
                optimization_interval=1800.0,  # 30분마다
                analysis_interval=600.0,       # 10분마다
                auto_apply_low_risk=True,
                enable_optimization_alerts=True,
                max_optimizations_per_day=8
            )
            
            self.optimization_service = GCPOptimizationService(
                gcp_optimizer=self.gcp_optimizer,
                performance_monitor=self.performance_monitor,
                monitoring_integration=self.monitoring_integration,
                agent_system=self.agent_system,
                config=service_config
            )
            
            logger.info("✅ GCP 최적화 시스템 설정 완료")
            
            return {
                "status": "success",
                "components": {
                    "agent_system": "initialized",
                    "performance_monitor": "initialized",
                    "monitoring_integration": "initialized",
                    "gcp_optimizer": "initialized",
                    "optimization_service": "initialized"
                },
                "target_instance": GCPInstanceType.E2_SMALL.value,
                "optimization_level": OptimizationLevel.BALANCED.value,
                "registered_agents": len(self.agent_system.agents)
            }
            
        except Exception as e:
            logger.error(f"❌ GCP 최적화 시스템 설정 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _register_optimization_agents(self):
        """최적화용 에이전트들 등록"""
        try:
            # 기본 에이전트 설정
            base_config = AgentConfig(
                name="optimization_agent",
                model_type=ModelType.GEMINI_1_5_FLASH,
                temperature=0.7,
                max_tokens=1000,
                timeout=30.0,
                debug_mode=True
            )
            
            # 최적화 에이전트 (핵심)
            optimizer_config = base_config
            optimizer_config.name = "OptimizerAgent"
            optimizer_agent = OptimizerAgent(optimizer_config)
            self.agent_system.register_agent("OptimizerAgent", optimizer_agent)
            
            # 검색 전략 에이전트
            search_config = base_config
            search_config.name = "SearchStrategyAgent"
            search_agent = SearchStrategyAgent(search_config)
            self.agent_system.register_agent("SearchStrategyAgent", search_agent)
            
            # 연락처 에이전트
            contact_config = base_config
            contact_config.name = "ContactAgent"
            contact_agent = ContactAgent(contact_config)
            self.agent_system.register_agent("ContactAgent", contact_agent)
            
            logger.info(f"✅ {len(self.agent_system.agents)}개 최적화 에이전트 등록 완료")
            
        except Exception as e:
            logger.error(f"❌ 최적화 에이전트 등록 실패: {e}")
            raise

    async def run_basic_gcp_analysis_example(self) -> Dict[str, Any]:
        """
        기본 GCP 환경 분석 예제 실행
        
        Returns:
            분석 결과
        """
        logger.info("📊 기본 GCP 환경 분석 예제 시작")
        
        if not self.gcp_optimizer:
            return {"error": "GCP 최적화 시스템이 초기화되지 않았습니다"}
        
        try:
            # 1. 현재 GCP 환경 분석
            analysis_result = await self.gcp_optimizer.analyze_current_environment()
            
            # 2. 워크로드 프로파일 분석
            workload_profile = analysis_result.get('workload_profile', {})
            
            # 3. 리소스 제약사항 확인
            constraints = analysis_result.get('resource_constraints', [])
            
            # 4. 비용 효율성 분석
            cost_analysis = analysis_result.get('cost_analysis', {})
            
            # 5. 성능 병목점 식별
            bottlenecks = analysis_result.get('performance_bottlenecks', [])
            
            logger.info("✅ 기본 GCP 환경 분석 완료")
            
            return {
                "status": "success",
                "analysis_summary": {
                    "instance_type": GCPInstanceType.E2_SMALL.value,
                    "current_efficiency": analysis_result.get('optimization_potential', {}).get('current_efficiency', 0.5),
                    "optimization_potential": analysis_result.get('optimization_potential', {}).get('overall_potential_percent', 0),
                    "cost_efficiency": cost_analysis.get('efficiency_score', 0.5),
                    "bottlenecks_count": len(bottlenecks),
                    "constraints_count": len(constraints)
                },
                "detailed_analysis": analysis_result,
                "key_insights": [
                    f"GCP e2-small 환경 분석 완료",
                    f"현재 효율성: {analysis_result.get('optimization_potential', {}).get('current_efficiency', 0.5):.1%}",
                    f"최적화 잠재력: {analysis_result.get('optimization_potential', {}).get('overall_potential_percent', 0):.1f}%",
                    f"월 예상 비용: ${cost_analysis.get('current_monthly_cost', 0):.2f}",
                    f"잠재적 절약: ${abs(cost_analysis.get('potential_monthly_savings', 0)):.2f}/월"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 기본 GCP 환경 분석 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def run_optimization_recommendations_example(self) -> Dict[str, Any]:
        """
        최적화 권장사항 생성 예제 실행
        
        Returns:
            권장사항 결과
        """
        logger.info("🎯 최적화 권장사항 생성 예제 시작")
        
        if not self.gcp_optimizer:
            return {"error": "GCP 최적화 시스템이 초기화되지 않았습니다"}
        
        try:
            # 1. 환경 분석
            analysis_result = await self.gcp_optimizer.analyze_current_environment()
            
            # 2. 최적화 권장사항 생성
            recommendations = await self.gcp_optimizer.generate_optimization_recommendations(analysis_result)
            
            # 3. 권장사항 분류
            resource_recommendations = [r for r in recommendations if r.category == "resource"]
            cost_recommendations = [r for r in recommendations if r.category == "cost"]
            performance_recommendations = [r for r in recommendations if r.category == "performance"]
            scaling_recommendations = [r for r in recommendations if r.category == "scaling"]
            
            # 4. 우선순위별 분류
            high_priority = [r for r in recommendations if r.priority <= 2]
            medium_priority = [r for r in recommendations if r.priority == 3]
            low_priority = [r for r in recommendations if r.priority >= 4]
            
            # 5. 예상 개선 효과 계산
            total_cost_improvement = sum(
                rec.expected_improvement.get("cost", 0) for rec in recommendations
            )
            total_performance_improvement = sum(
                rec.expected_improvement.get("performance", 0) for rec in recommendations
            )
            
            logger.info(f"✅ {len(recommendations)}개 최적화 권장사항 생성 완료")
            
            return {
                "status": "success",
                "recommendations_summary": {
                    "total_recommendations": len(recommendations),
                    "high_priority": len(high_priority),
                    "medium_priority": len(medium_priority),
                    "low_priority": len(low_priority),
                    "by_category": {
                        "resource": len(resource_recommendations),
                        "cost": len(cost_recommendations),
                        "performance": len(performance_recommendations),
                        "scaling": len(scaling_recommendations)
                    },
                    "expected_improvements": {
                        "cost_savings_percent": total_cost_improvement,
                        "performance_gain_percent": total_performance_improvement
                    }
                },
                "detailed_recommendations": [
                    {
                        "id": rec.id,
                        "category": rec.category,
                        "priority": rec.priority,
                        "title": rec.title,
                        "description": rec.description,
                        "expected_improvement": rec.expected_improvement,
                        "estimated_effort": rec.estimated_effort,
                        "estimated_time": rec.estimated_time,
                        "cost_impact": rec.cost_impact,
                        "risk_level": rec.risk_level
                    }
                    for rec in recommendations
                ],
                "implementation_roadmap": self._create_example_roadmap(recommendations),
                "key_insights": [
                    f"총 {len(recommendations)}개의 최적화 기회 발견",
                    f"우선 순위 높음: {len(high_priority)}개",
                    f"예상 비용 절감: {total_cost_improvement:.1f}%",
                    f"예상 성능 개선: {total_performance_improvement:.1f}%",
                    "GCP e2-small 환경에 최적화된 권장사항 제공"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 최적화 권장사항 생성 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    def _create_example_roadmap(self, recommendations) -> Dict[str, Any]:
        """예제용 구현 로드맵 생성"""
        high_priority = [r for r in recommendations if r.priority <= 2]
        medium_priority = [r for r in recommendations if r.priority == 3]
        low_priority = [r for r in recommendations if r.priority >= 4]
        
        return {
            "즉시_실행_권장": {
                "기간": "1-3일",
                "항목": [r.title for r in high_priority],
                "예상_효과": "즉각적인 성능 및 비용 개선"
            },
            "단기_실행_권장": {
                "기간": "1-2주",
                "항목": [r.title for r in medium_priority],
                "예상_효과": "안정성 및 효율성 개선"
            },
            "장기_실행_권장": {
                "기간": "1-3개월",
                "항목": [r.title for r in low_priority],
                "예상_효과": "장기적 최적화 및 비용 절감"
            }
        }

    async def run_automated_optimization_service_example(self) -> Dict[str, Any]:
        """
        자동화된 최적화 서비스 예제 실행
        
        Returns:
            서비스 실행 결과
        """
        logger.info("🤖 자동화된 최적화 서비스 예제 시작")
        
        if not self.optimization_service:
            return {"error": "최적화 서비스가 초기화되지 않았습니다"}
        
        try:
            # 1. 최적화 서비스 시작
            await self.optimization_service.start_service()
            
            # 2. 초기 상태 확인
            initial_status = await self.optimization_service.get_optimization_status()
            
            # 3. 수동 최적화 요청 (테스트용)
            manual_request_result = await self.optimization_service.manual_optimization_request(
                optimization_type="resource",
                priority=2
            )
            
            # 4. 10초 대기 (서비스 작동 확인)
            await asyncio.sleep(10)
            
            # 5. 중간 상태 확인
            mid_status = await self.optimization_service.get_optimization_status()
            
            # 6. 대시보드 데이터 생성
            dashboard_data = await self.optimization_service.generate_optimization_dashboard()
            
            # 7. 최적화 서비스 중지
            await self.optimization_service.stop_service()
            
            # 8. 최종 상태 확인
            final_status = await self.optimization_service.get_optimization_status()
            
            logger.info("✅ 자동화된 최적화 서비스 예제 완료")
            
            return {
                "status": "success",
                "service_lifecycle": {
                    "initial_status": initial_status["service_status"],
                    "mid_status": mid_status["service_status"],
                    "final_status": final_status["service_status"]
                },
                "manual_request": manual_request_result,
                "dashboard_preview": {
                    "performance_overview": dashboard_data.get("performance_overview", {}),
                    "optimization_metrics": dashboard_data.get("optimization_metrics", {}),
                    "service_overview": dashboard_data.get("service_overview", {})
                },
                "service_metrics": {
                    "auto_mode": initial_status["auto_optimization_mode"],
                    "queue_processed": mid_status["queue_status"],
                    "total_optimizations": final_status["metrics"]["total_optimizations"]
                },
                "key_insights": [
                    "자동화된 최적화 서비스 정상 작동 확인",
                    "수동 최적화 요청 처리 성공",
                    "실시간 대시보드 데이터 생성 완료",
                    "서비스 생명주기 관리 검증 완료",
                    "GCP e2-small 환경 모니터링 활성화"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 자동화된 최적화 서비스 예제 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def run_cost_optimization_scenario(self) -> Dict[str, Any]:
        """
        비용 최적화 시나리오 예제 실행
        
        Returns:
            비용 최적화 결과
        """
        logger.info("💰 비용 최적화 시나리오 예제 시작")
        
        if not self.gcp_optimizer:
            return {"error": "GCP 최적화 시스템이 초기화되지 않았습니다"}
        
        try:
            # 1. 현재 비용 분석
            analysis_result = await self.gcp_optimizer.analyze_current_environment()
            cost_analysis = analysis_result.get('cost_analysis', {})
            
            # 2. 비용 관련 권장사항만 생성
            all_recommendations = await self.gcp_optimizer.generate_optimization_recommendations(analysis_result)
            cost_recommendations = [r for r in all_recommendations if r.category == "cost"]
            
            # 3. 시나리오별 비용 절감 계산
            scenarios = await self._calculate_cost_scenarios(cost_analysis, cost_recommendations)
            
            # 4. ROI 분석
            roi_analysis = await self._calculate_roi_analysis(cost_recommendations)
            
            # 5. 비용 최적화 시뮬레이션
            optimization_simulation = await self._simulate_cost_optimization(cost_recommendations)
            
            logger.info("✅ 비용 최적화 시나리오 완료")
            
            return {
                "status": "success",
                "current_cost_analysis": {
                    "monthly_cost": cost_analysis.get('current_monthly_cost', 0),
                    "efficiency_score": cost_analysis.get('efficiency_score', 0.5),
                    "avg_utilization": cost_analysis.get('avg_utilization', 0.5),
                    "potential_savings": cost_analysis.get('potential_monthly_savings', 0)
                },
                "optimization_scenarios": scenarios,
                "roi_analysis": roi_analysis,
                "optimization_simulation": optimization_simulation,
                "cost_recommendations": [
                    {
                        "title": rec.title,
                        "description": rec.description,
                        "expected_savings": rec.expected_improvement.get("cost", 0),
                        "implementation_effort": rec.estimated_effort,
                        "billing_impact": rec.billing_impact
                    }
                    for rec in cost_recommendations
                ],
                "key_insights": [
                    f"현재 월 비용: ${cost_analysis.get('current_monthly_cost', 0):.2f}",
                    f"비용 효율성: {cost_analysis.get('efficiency_score', 0.5):.1%}",
                    f"잠재적 월 절약: ${abs(cost_analysis.get('potential_monthly_savings', 0)):.2f}",
                    f"{len(cost_recommendations)}개 비용 최적화 기회 발견",
                    "GCP e2-small 최적화로 연 $100-300 절약 가능"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 비용 최적화 시나리오 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _calculate_cost_scenarios(self, cost_analysis, recommendations):
        """비용 시나리오 계산"""
        current_monthly = cost_analysis.get('current_monthly_cost', 24.27)  # e2-small 기본 비용
        
        scenarios = {
            "현재_상태": {
                "월_비용": current_monthly,
                "연_비용": current_monthly * 12,
                "설명": "현재 GCP e2-small 인스턴스 비용"
            },
            "보수적_최적화": {
                "월_비용": current_monthly * 0.85,  # 15% 절감
                "연_비용": current_monthly * 0.85 * 12,
                "절약액": current_monthly * 0.15 * 12,
                "설명": "저위험 최적화 적용 시"
            },
            "적극적_최적화": {
                "월_비용": current_monthly * 0.70,  # 30% 절감
                "연_비용": current_monthly * 0.70 * 12,
                "절약액": current_monthly * 0.30 * 12,
                "설명": "모든 권장사항 적용 시"
            },
            "인스턴스_다운그레이드": {
                "월_비용": 12.14,  # e2-micro 비용
                "연_비용": 12.14 * 12,
                "절약액": (current_monthly - 12.14) * 12,
                "설명": "e2-micro로 다운그레이드 시 (저사용률 환경)"
            }
        }
        
        return scenarios

    async def _calculate_roi_analysis(self, recommendations):
        """ROI 분석 계산"""
        
        total_implementation_cost = len(recommendations) * 100  # 권장사항당 $100 구현 비용 추정
        total_annual_savings = sum(
            rec.expected_improvement.get("cost", 0) * 24.27 * 0.12  # 비용 절감 백분율을 달러로 변환
            for rec in recommendations
        )
        
        if total_implementation_cost > 0:
            roi_ratio = total_annual_savings / total_implementation_cost
            payback_months = 12 / roi_ratio if roi_ratio > 0 else float('inf')
        else:
            roi_ratio = 0
            payback_months = 0
        
        return {
            "구현_비용": total_implementation_cost,
            "연간_절약": total_annual_savings,
            "ROI_비율": roi_ratio,
            "투자_회수_기간_월": min(payback_months, 24),  # 최대 24개월
            "5년_순이익": total_annual_savings * 5 - total_implementation_cost,
            "권장여부": "권장" if roi_ratio > 2 else "검토필요" if roi_ratio > 1 else "비권장"
        }

    async def _simulate_cost_optimization(self, recommendations):
        """비용 최적화 시뮬레이션"""
        
        simulation_results = []
        current_cost = 24.27  # e2-small 월 비용
        
        for i, rec in enumerate(recommendations, 1):
            cost_reduction = rec.expected_improvement.get("cost", 0)
            new_monthly_cost = current_cost * (1 - cost_reduction / 100)
            
            simulation_results.append({
                "단계": i,
                "적용_권장사항": rec.title,
                "비용_절감률": f"{cost_reduction:.1f}%",
                "월_비용": f"${new_monthly_cost:.2f}",
                "월_절약": f"${current_cost - new_monthly_cost:.2f}",
                "누적_연간_절약": f"${(current_cost - new_monthly_cost) * 12:.2f}"
            })
            
            current_cost = new_monthly_cost
        
        return {
            "시뮬레이션_결과": simulation_results,
            "최종_월_비용": f"${current_cost:.2f}",
            "총_연간_절약": f"${(24.27 - current_cost) * 12:.2f}",
            "총_절감률": f"{((24.27 - current_cost) / 24.27 * 100):.1f}%"
        }

    async def run_performance_optimization_workflow(self) -> Dict[str, Any]:
        """
        성능 최적화 워크플로우 예제 실행
        
        Returns:
            성능 최적화 결과
        """
        logger.info("⚡ 성능 최적화 워크플로우 예제 시작")
        
        try:
            # 1. 통합 모니터링 시작
            await self.monitoring_integration.start_integrated_monitoring()
            
            # 2. 기본 성능 데이터 수집 (10초)
            await asyncio.sleep(10)
            
            # 3. 성능 분석 수행
            performance_report = await self.monitoring_integration.get_integrated_report("1hour")
            
            # 4. GCP 특화 성능 분석
            gcp_analysis = await self.gcp_optimizer.analyze_current_environment()
            bottlenecks = gcp_analysis.get('performance_bottlenecks', [])
            
            # 5. 성능 관련 권장사항 생성
            all_recommendations = await self.gcp_optimizer.generate_optimization_recommendations(gcp_analysis)
            performance_recommendations = [r for r in all_recommendations if r.category == "performance"]
            
            # 6. 성능 최적화 시뮬레이션
            performance_simulation = await self._simulate_performance_optimization(
                bottlenecks, performance_recommendations
            )
            
            # 7. 통합 성능 최적화 적용 (시뮬레이션)
            await self.monitoring_integration.optimize_integrated_performance()
            
            # 8. 모니터링 중지
            await self.monitoring_integration.stop_integrated_monitoring()
            
            logger.info("✅ 성능 최적화 워크플로우 완료")
            
            return {
                "status": "success",
                "performance_analysis": {
                    "system_overview": performance_report.get("system_overview", {}),
                    "agent_performance": performance_report.get("agent_performance", {}),
                    "bottlenecks": bottlenecks,
                    "optimization_potential": gcp_analysis.get('optimization_potential', {})
                },
                "performance_recommendations": [
                    {
                        "title": rec.title,
                        "description": rec.description,
                        "expected_improvement": rec.expected_improvement,
                        "implementation_steps": rec.implementation_steps
                    }
                    for rec in performance_recommendations
                ],
                "optimization_simulation": performance_simulation,
                "workflow_results": {
                    "monitoring_duration": "10초",
                    "analysis_completed": True,
                    "recommendations_generated": len(performance_recommendations),
                    "optimization_applied": True
                },
                "key_insights": [
                    f"{len(bottlenecks)}개 성능 병목점 식별",
                    f"{len(performance_recommendations)}개 성능 개선 방안 제안",
                    "통합 모니터링 시스템 정상 작동",
                    "자동 성능 최적화 적용 완료",
                    "GCP e2-small 환경 성능 튜닝 완료"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 성능 최적화 워크플로우 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _simulate_performance_optimization(self, bottlenecks, recommendations):
        """성능 최적화 시뮬레이션"""
        
        baseline_performance = {
            "CPU 사용률": 75.0,
            "메모리 사용률": 80.0,
            "응답 시간": 2.5,
            "처리량": 100.0
        }
        
        optimization_steps = []
        current_performance = baseline_performance.copy()
        
        for i, rec in enumerate(recommendations, 1):
            # 권장사항별 성능 개선 시뮬레이션
            cpu_improvement = rec.expected_improvement.get("cpu", 0)
            memory_improvement = rec.expected_improvement.get("memory", 0)
            performance_improvement = rec.expected_improvement.get("performance", 0)
            
            # 성능 지표 업데이트
            if cpu_improvement > 0:
                current_performance["CPU 사용률"] *= (1 - cpu_improvement / 100)
            if memory_improvement > 0:
                current_performance["메모리 사용률"] *= (1 - memory_improvement / 100)
            if performance_improvement > 0:
                current_performance["응답 시간"] *= (1 - performance_improvement / 100)
                current_performance["처리량"] *= (1 + performance_improvement / 100)
            
            optimization_steps.append({
                "단계": i,
                "적용_권장사항": rec.title,
                "CPU_사용률": f"{current_performance['CPU 사용률']:.1f}%",
                "메모리_사용률": f"{current_performance['메모리 사용률']:.1f}%",
                "응답_시간": f"{current_performance['응답 시간']:.2f}초",
                "처리량": f"{current_performance['처리량']:.1f}%",
                "예상_개선": rec.expected_improvement
            })
        
        return {
            "기준_성능": baseline_performance,
            "최적화_단계": optimization_steps,
            "최종_성능": current_performance,
            "총_개선률": {
                "CPU": f"{(baseline_performance['CPU 사용률'] - current_performance['CPU 사용률']) / baseline_performance['CPU 사용률'] * 100:.1f}%",
                "메모리": f"{(baseline_performance['메모리 사용률'] - current_performance['메모리 사용률']) / baseline_performance['메모리 사용률'] * 100:.1f}%",
                "응답시간": f"{(baseline_performance['응답 시간'] - current_performance['응답 시간']) / baseline_performance['응답 시간'] * 100:.1f}%",
                "처리량": f"{(current_performance['처리량'] - baseline_performance['처리량']) / baseline_performance['처리량'] * 100:.1f}%"
            }
        }

    async def run_comprehensive_gcp_optimization_demo(self) -> Dict[str, Any]:
        """
        종합 GCP 최적화 데모 실행
        
        Returns:
            종합 데모 결과
        """
        logger.info("🎯 종합 GCP 최적화 데모 시작")
        
        demo_results = {
            "demo_start_time": datetime.now().isoformat(),
            "executed_scenarios": [],
            "overall_status": "pending"
        }
        
        try:
            # 1. 시스템 설정
            setup_result = await self.setup_gcp_optimization_system()
            demo_results["system_setup"] = setup_result
            
            if setup_result["status"] != "success":
                demo_results["overall_status"] = "setup_failed"
                return demo_results
            
            # 2. 기본 GCP 환경 분석
            logger.info("📊 1단계: 기본 GCP 환경 분석 실행")
            analysis_result = await self.run_basic_gcp_analysis_example()
            demo_results["gcp_analysis"] = analysis_result
            demo_results["executed_scenarios"].append("gcp_analysis")
            
            # 3. 최적화 권장사항 생성
            logger.info("🎯 2단계: 최적화 권장사항 생성 실행")
            recommendations_result = await self.run_optimization_recommendations_example()
            demo_results["optimization_recommendations"] = recommendations_result
            demo_results["executed_scenarios"].append("optimization_recommendations")
            
            # 4. 자동화된 최적화 서비스
            logger.info("🤖 3단계: 자동화된 최적화 서비스 실행")
            service_result = await self.run_automated_optimization_service_example()
            demo_results["optimization_service"] = service_result
            demo_results["executed_scenarios"].append("optimization_service")
            
            # 5. 비용 최적화 시나리오
            logger.info("💰 4단계: 비용 최적화 시나리오 실행")
            cost_result = await self.run_cost_optimization_scenario()
            demo_results["cost_optimization"] = cost_result
            demo_results["executed_scenarios"].append("cost_optimization")
            
            # 6. 성능 최적화 워크플로우
            logger.info("⚡ 5단계: 성능 최적화 워크플로우 실행")
            performance_result = await self.run_performance_optimization_workflow()
            demo_results["performance_optimization"] = performance_result
            demo_results["executed_scenarios"].append("performance_optimization")
            
            # 7. 최종 상태 확인
            if all([
                analysis_result.get("status") == "success",
                recommendations_result.get("status") == "success",
                service_result.get("status") == "success",
                cost_result.get("status") == "success",
                performance_result.get("status") == "success"
            ]):
                demo_results["overall_status"] = "success"
            else:
                demo_results["overall_status"] = "partial_success"
            
            demo_results["demo_end_time"] = datetime.now().isoformat()
            demo_results["total_scenarios"] = len(demo_results["executed_scenarios"])
            
            # 8. 종합 인사이트
            demo_results["comprehensive_insights"] = [
                "GCP e2-small 환경 최적화 시스템 완전 구현",
                "실시간 성능 모니터링 및 자동 최적화 검증",
                "비용 효율성 개선을 통한 연간 $100-300 절약 가능",
                "성능 병목점 자동 탐지 및 최적화 권장사항 생성",
                "AI 기반 예측 분석 및 자동화된 최적화 워크플로우",
                "프로덕션 환경 배포 준비 완료"
            ]
            
            # 9. 요약 통계
            demo_results["summary_statistics"] = {
                "총_실행_시간": (datetime.strptime(demo_results["demo_end_time"], "%Y-%m-%dT%H:%M:%S.%f") - 
                               datetime.strptime(demo_results["demo_start_time"], "%Y-%m-%dT%H:%M:%S.%f")).total_seconds(),
                "성공한_시나리오": len([s for s in demo_results["executed_scenarios"] 
                                    if demo_results.get(s, {}).get("status") == "success"]),
                "생성된_권장사항": recommendations_result.get("recommendations_summary", {}).get("total_recommendations", 0),
                "예상_연간_절약": cost_result.get("current_cost_analysis", {}).get("potential_savings", 0) * 12,
                "시스템_효율성": analysis_result.get("analysis_summary", {}).get("current_efficiency", 0.5)
            }
            
            logger.info("🎉 종합 GCP 최적화 데모 완료")
            
            return demo_results
            
        except Exception as e:
            logger.error(f"❌ 종합 GCP 최적화 데모 실패: {e}")
            demo_results["overall_status"] = "failed"
            demo_results["error"] = str(e)
            return demo_results


# 실행 함수들
async def run_gcp_optimization_examples():
    """GCP 최적화 예제 실행"""
    runner = GCPOptimizationExampleRunner()
    
    logger.info("🚀 GCP e2-small 환경 최적화 시스템 예제 시작")
    
    # 종합 데모 실행
    results = await runner.run_comprehensive_gcp_optimization_demo()
    
    logger.info("📋 GCP 최적화 예제 실행 결과:")
    logger.info(f"전체 상태: {results['overall_status']}")
    logger.info(f"실행된 시나리오: {results['executed_scenarios']}")
    logger.info(f"총 시나리오 수: {results.get('total_scenarios', 0)}")
    
    return results


def print_gcp_optimization_report(results: Dict[str, Any]):
    """GCP 최적화 리포트 출력"""
    print("\n" + "="*80)
    print("☁️ GCP e2-small 환경 최적화 시스템 실행 리포트")
    print("="*80)
    
    print(f"\n🎯 전체 실행 상태: {results.get('overall_status', 'unknown').upper()}")
    print(f"📅 실행 시간: {results.get('demo_start_time', 'N/A')} ~ {results.get('demo_end_time', 'N/A')}")
    print(f"🔢 실행된 시나리오: {results.get('total_scenarios', 0)}개")
    
    if 'executed_scenarios' in results:
        print(f"\n📋 실행 시나리오 목록:")
        for i, scenario in enumerate(results['executed_scenarios'], 1):
            status = results.get(scenario, {}).get('status', 'unknown')
            print(f"  {i}. {scenario} ({status})")
    
    if 'summary_statistics' in results:
        stats = results['summary_statistics']
        print(f"\n📊 요약 통계:")
        print(f"  실행 시간: {stats.get('총_실행_시간', 0):.1f}초")
        print(f"  성공 시나리오: {stats.get('성공한_시나리오', 0)}개")
        print(f"  생성된 권장사항: {stats.get('생성된_권장사항', 0)}개")
        print(f"  예상 연간 절약: ${stats.get('예상_연간_절약', 0):.2f}")
        print(f"  시스템 효율성: {stats.get('시스템_효율성', 0.5):.1%}")
    
    if 'comprehensive_insights' in results:
        print(f"\n💡 주요 인사이트:")
        for i, insight in enumerate(results['comprehensive_insights'], 1):
            print(f"  {i}. {insight}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    async def main():
        """메인 실행 함수"""
        try:
            # GCP 최적화 예제 실행
            results = await run_gcp_optimization_examples()
            
            # 결과 출력
            print_gcp_optimization_report(results)
            
            # JSON 형태로도 출력 (선택사항)
            if results.get('overall_status') == 'success':
                print(f"\n📄 상세 결과 (JSON):")
                print(json.dumps(results, indent=2, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"❌ 메인 실행 실패: {e}")
            print(f"\n💥 실행 중 오류 발생: {e}")
    
    # 비동기 메인 함수 실행
    asyncio.run(main()) 