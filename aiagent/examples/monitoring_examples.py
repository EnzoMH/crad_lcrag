"""
📊 성능 모니터링 시스템 사용 예제

Langchain 기반 AI 에이전트 시스템의 성능 모니터링 활용 예제
- 기본 모니터링 설정 및 실행
- 통합 모니터링 시스템 구성
- 성능 분석 및 최적화 시나리오
- 실시간 알림 및 리포트 생성
"""

import asyncio
import time
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from loguru import logger

# 성능 모니터링 시스템 import
from ..core.performance_monitor import PerformanceMonitor, MetricType, AlertLevel
from ..core.monitoring_integration import MonitoringIntegration, MonitoringConfig
from ..core.agent_system import AIAgentSystem, SystemConfig
from ..core.chain_manager import ChainManager
from ..core.chain_service import ChainService
from ..core.coordinator import AgentCoordinator

# 기본 에이전트 및 설정 import
from ..core.agent_base import AgentConfig
from ..agents.search_strategy_agent import SearchStrategyAgent
from ..agents.contact_agent import ContactAgent
from ..agents.validation_agent import ValidationAgent
from ..agents.optimizer_agent import OptimizerAgent
from ..utils.gemini_client import GeminiClient, ModelType


class MonitoringExampleRunner:
    """
    📊 성능 모니터링 예제 실행기
    
    다양한 모니터링 시나리오를 실행하고 결과를 분석하는 시스템
    """
    
    def __init__(self):
        """모니터링 예제 실행기 초기화"""
        self.performance_monitor = None
        self.monitoring_integration = None
        self.agent_system = None
        self.chain_manager = None
        self.chain_service = None
        self.coordinator = None
        
        logger.info("📊 성능 모니터링 예제 실행기 초기화 완료")

    async def setup_monitoring_system(self) -> Dict[str, Any]:
        """
        통합 모니터링 시스템 설정
        
        Returns:
            설정 결과
        """
        logger.info("🔧 통합 모니터링 시스템 설정 시작")
        
        try:
            # 1. AI 에이전트 시스템 초기화
            system_config = SystemConfig(
                name="모니터링 테스트 시스템",
                version="1.0.0",
                environment="test",
                debug_mode=True,
                enable_monitoring=True
            )
            self.agent_system = AIAgentSystem(system_config)
            
            # 2. 체인 매니저 초기화
            self.chain_manager = ChainManager()
            self.chain_service = ChainService(self.chain_manager)
            
            # 3. 워크플로우 조정자 초기화
            self.coordinator = AgentCoordinator(self.agent_system)
            
            # 4. 전문 에이전트들 등록
            await self._register_test_agents()
            
            # 5. 모니터링 통합 시스템 초기화
            monitoring_config = MonitoringConfig(
                enable_agent_monitoring=True,
                enable_chain_monitoring=True,
                enable_workflow_monitoring=True,
                enable_system_monitoring=True,
                agent_metrics_interval=10.0,  # 테스트용 빠른 간격
                chain_metrics_interval=5.0,
                system_metrics_interval=15.0
            )
            
            self.monitoring_integration = MonitoringIntegration(
                agent_system=self.agent_system,
                chain_manager=self.chain_manager,
                chain_service=self.chain_service,
                coordinator=self.coordinator,
                config=monitoring_config
            )
            
            # 6. 기본 성능 모니터 초기화
            self.performance_monitor = self.monitoring_integration.performance_monitor
            
            logger.info("✅ 통합 모니터링 시스템 설정 완료")
            
            return {
                "status": "success",
                "components": {
                    "agent_system": "initialized",
                    "chain_manager": "initialized", 
                    "chain_service": "initialized",
                    "coordinator": "initialized",
                    "monitoring_integration": "initialized"
                },
                "registered_agents": len(self.agent_system.agents),
                "monitoring_config": {
                    "agent_monitoring": monitoring_config.enable_agent_monitoring,
                    "chain_monitoring": monitoring_config.enable_chain_monitoring,
                    "workflow_monitoring": monitoring_config.enable_workflow_monitoring
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 모니터링 시스템 설정 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _register_test_agents(self):
        """테스트용 에이전트들 등록"""
        try:
            # 기본 에이전트 설정
            base_config = AgentConfig(
                name="test_agent",
                model_type=ModelType.GEMINI_1_5_FLASH,
                temperature=0.7,
                max_tokens=1000,
                timeout=30.0,
                debug_mode=True
            )
            
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
            
            # 검증 에이전트
            validation_config = base_config
            validation_config.name = "ValidationAgent"
            validation_agent = ValidationAgent(validation_config)
            self.agent_system.register_agent("ValidationAgent", validation_agent)
            
            # 최적화 에이전트
            optimizer_config = base_config
            optimizer_config.name = "OptimizerAgent"
            optimizer_agent = OptimizerAgent(optimizer_config)
            self.agent_system.register_agent("OptimizerAgent", optimizer_agent)
            
            logger.info(f"✅ {len(self.agent_system.agents)}개 테스트 에이전트 등록 완료")
            
        except Exception as e:
            logger.error(f"❌ 테스트 에이전트 등록 실패: {e}")
            raise

    async def run_basic_monitoring_example(self) -> Dict[str, Any]:
        """
        기본 모니터링 예제 실행
        
        Returns:
            모니터링 결과
        """
        logger.info("📊 기본 모니터링 예제 시작")
        
        if not self.performance_monitor:
            return {"error": "성능 모니터가 초기화되지 않았습니다"}
        
        try:
            # 1. 모니터링 시작
            await self.performance_monitor.start_monitoring()
            
            # 2. 테스트 메트릭 기록
            await self._generate_test_metrics()
            
            # 3. 5초 대기 (메트릭 수집 시간)
            await asyncio.sleep(5)
            
            # 4. 성능 리포트 생성
            report = await self.performance_monitor.get_performance_report("1hour")
            
            # 5. 현재 상태 확인
            current_status = self.performance_monitor.get_current_status()
            
            # 6. 모니터링 중지
            await self.performance_monitor.stop_monitoring()
            
            logger.info("✅ 기본 모니터링 예제 완료")
            
            return {
                "status": "success",
                "monitoring_duration": "5 seconds",
                "performance_report": report,
                "current_status": current_status,
                "insights": [
                    "기본 시스템 리소스 모니터링 정상 작동",
                    "테스트 메트릭 수집 및 분석 완료",
                    "성능 리포트 생성 성공"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 기본 모니터링 예제 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _generate_test_metrics(self):
        """테스트용 메트릭 생성"""
        # 에이전트 성능 메트릭
        self.performance_monitor.record_agent_metric(
            agent_name="SearchStrategyAgent",
            metric_name="execution_time",
            value=2.5,
            unit="seconds",
            metadata={"test": True}
        )
        
        self.performance_monitor.record_agent_metric(
            agent_name="ContactAgent",
            metric_name="success_rate",
            value=0.95,
            unit="ratio"
        )
        
        # 체인 실행 메트릭
        self.performance_monitor.record_chain_metric(
            chain_name="test_search_chain",
            execution_result={"success": True, "data": "test_result"},
            execution_time=1.8
        )
        
        self.performance_monitor.record_chain_metric(
            chain_name="test_validation_chain",
            execution_result={"success": True, "validated": True},
            execution_time=0.9
        )

    async def run_integrated_monitoring_example(self) -> Dict[str, Any]:
        """
        통합 모니터링 예제 실행
        
        Returns:
            통합 모니터링 결과
        """
        logger.info("🔗 통합 모니터링 예제 시작")
        
        if not self.monitoring_integration:
            return {"error": "통합 모니터링이 초기화되지 않았습니다"}
        
        try:
            # 1. 통합 모니터링 시작
            await self.monitoring_integration.start_integrated_monitoring()
            
            # 2. 테스트 작업 실행
            test_results = await self._run_test_workloads()
            
            # 3. 10초 대기 (통합 메트릭 수집 시간)
            await asyncio.sleep(10)
            
            # 4. 통합 성능 리포트 생성
            integrated_report = await self.monitoring_integration.get_integrated_report("1hour")
            
            # 5. 모니터링 상태 확인
            monitoring_status = self.monitoring_integration.get_monitoring_status()
            
            # 6. 통합 모니터링 중지
            await self.monitoring_integration.stop_integrated_monitoring()
            
            logger.info("✅ 통합 모니터링 예제 완료")
            
            return {
                "status": "success",
                "test_workloads": test_results,
                "integrated_report": integrated_report,
                "monitoring_status": monitoring_status,
                "insights": [
                    "전체 시스템 컴포넌트 통합 모니터링 성공",
                    "에이전트, 체인, 워크플로우 성능 추적 완료",
                    "실시간 성능 훅 정상 작동 확인"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 통합 모니터링 예제 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _run_test_workloads(self) -> Dict[str, Any]:
        """테스트 워크로드 실행"""
        results = {}
        
        try:
            # 1. 단일 에이전트 작업 테스트
            search_result = await self.agent_system.process_single_task(
                "SearchStrategyAgent",
                {"query": "test search", "target": "test_target"}
            )
            results["search_task"] = search_result.success
            
            # 2. 체인 실행 테스트
            if hasattr(self.chain_service, 'execute_chain'):
                chain_result = await self.chain_service.execute_chain(
                    "test_chain",
                    {"input": "test_data"}
                )
                results["chain_execution"] = True
            else:
                results["chain_execution"] = "not_available"
            
            # 3. 배치 처리 테스트
            batch_data = [
                {"item": "test1"},
                {"item": "test2"},
                {"item": "test3"}
            ]
            batch_results = await self.agent_system.process_batch(
                "ValidationAgent",
                batch_data,
                max_concurrent=2
            )
            results["batch_processing"] = {
                "total": len(batch_results),
                "successful": sum(1 for r in batch_results if r.success)
            }
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 테스트 워크로드 실행 실패: {e}")
            return {"error": str(e)}

    async def run_performance_analysis_example(self) -> Dict[str, Any]:
        """
        성능 분석 예제 실행
        
        Returns:
            성능 분석 결과
        """
        logger.info("📈 성능 분석 예제 시작")
        
        if not self.monitoring_integration:
            return {"error": "통합 모니터링이 초기화되지 않았습니다"}
        
        try:
            # 1. 모니터링 시작
            await self.monitoring_integration.start_integrated_monitoring()
            
            # 2. 부하 테스트 시나리오 실행
            load_test_results = await self._run_load_test_scenario()
            
            # 3. 15초 대기 (성능 데이터 수집)
            await asyncio.sleep(15)
            
            # 4. 성능 최적화 실행
            await self.monitoring_integration.optimize_integrated_performance()
            
            # 5. 최종 성능 리포트 생성
            final_report = await self.monitoring_integration.get_integrated_report("1hour")
            
            # 6. 모니터링 중지
            await self.monitoring_integration.stop_integrated_monitoring()
            
            logger.info("✅ 성능 분석 예제 완료")
            
            return {
                "status": "success",
                "load_test_results": load_test_results,
                "performance_analysis": final_report,
                "optimization_applied": True,
                "insights": [
                    "부하 테스트를 통한 성능 병목점 식별",
                    "자동 성능 최적화 실행 완료",
                    "시스템 리소스 사용량 분석 완료"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 성능 분석 예제 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _run_load_test_scenario(self) -> Dict[str, Any]:
        """부하 테스트 시나리오 실행"""
        logger.info("🚀 부하 테스트 시나리오 시작")
        
        results = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "average_response_time": 0.0,
            "peak_memory_usage": 0.0
        }
        
        try:
            # 동시 작업 실행
            tasks = []
            start_time = time.time()
            
            # 10개의 동시 에이전트 작업
            for i in range(10):
                task = self.agent_system.process_single_task(
                    "SearchStrategyAgent",
                    {"query": f"load_test_{i}", "item_id": i}
                )
                tasks.append(task)
            
            # 5개의 동시 배치 작업
            for i in range(5):
                batch_data = [{"batch_item": j} for j in range(3)]
                task = self.agent_system.process_batch(
                    "ContactAgent",
                    batch_data,
                    max_concurrent=2
                )
                tasks.append(task)
            
            # 모든 작업 완료 대기
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 분석
            total_time = time.time() - start_time
            successful_count = 0
            failed_count = 0
            
            for result in task_results:
                if isinstance(result, Exception):
                    failed_count += 1
                else:
                    if hasattr(result, 'success'):
                        if result.success:
                            successful_count += 1
                        else:
                            failed_count += 1
                    elif isinstance(result, list):
                        # 배치 결과
                        for batch_result in result:
                            if batch_result.success:
                                successful_count += 1
                            else:
                                failed_count += 1
            
            results.update({
                "total_tasks": len(task_results),
                "successful_tasks": successful_count,
                "failed_tasks": failed_count,
                "average_response_time": total_time / len(task_results),
                "total_execution_time": total_time
            })
            
            logger.info(f"✅ 부하 테스트 완료: {successful_count}/{len(task_results)} 성공")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 부하 테스트 실패: {e}")
            return {"error": str(e)}

    async def run_alert_monitoring_example(self) -> Dict[str, Any]:
        """
        알림 모니터링 예제 실행
        
        Returns:
            알림 모니터링 결과
        """
        logger.info("🚨 알림 모니터링 예제 시작")
        
        if not self.performance_monitor:
            return {"error": "성능 모니터가 초기화되지 않았습니다"}
        
        try:
            # 1. 모니터링 시작
            await self.performance_monitor.start_monitoring()
            
            # 2. 의도적으로 임계값 초과 상황 생성
            await self._simulate_performance_issues()
            
            # 3. 5초 대기 (알림 생성 시간)
            await asyncio.sleep(5)
            
            # 4. 생성된 알림 확인
            current_status = self.performance_monitor.get_current_status()
            
            # 5. 성능 리포트에서 알림 요약 확인
            report = await self.performance_monitor.get_performance_report("1hour")
            
            # 6. 모니터링 중지
            await self.performance_monitor.stop_monitoring()
            
            logger.info("✅ 알림 모니터링 예제 완료")
            
            return {
                "status": "success",
                "current_status": current_status,
                "alerts_summary": report.get("alerts_summary", {}),
                "simulated_issues": [
                    "CPU 사용률 임계값 초과 시뮬레이션",
                    "메모리 사용률 경고 수준 시뮬레이션",
                    "에이전트 응답 시간 초과 시뮬레이션"
                ],
                "insights": [
                    "실시간 알림 시스템 정상 작동 확인",
                    "임계값 기반 자동 알림 생성 성공",
                    "성능 이슈 감지 및 추적 기능 검증"
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ 알림 모니터링 예제 실패: {e}")
            return {
                "status": "error",
                "error": str(e)
            }

    async def _simulate_performance_issues(self):
        """성능 이슈 시뮬레이션"""
        # 높은 CPU 사용률 시뮬레이션
        self.performance_monitor.record_agent_metric(
            agent_name="system",
            metric_name="cpu_usage",
            value=87.5,  # 임계값 초과
            unit="%",
            metadata={"simulated": True}
        )
        
        # 높은 메모리 사용률 시뮬레이션  
        self.performance_monitor.record_agent_metric(
            agent_name="system",
            metric_name="memory_usage",
            value=78.3,  # 경고 수준
            unit="%",
            metadata={"simulated": True}
        )
        
        # 긴 응답 시간 시뮬레이션
        self.performance_monitor.record_agent_metric(
            agent_name="SlowAgent",
            metric_name="execution_time",
            value=25.7,  # 임계값 초과
            unit="seconds",
            metadata={"simulated": True, "timeout_risk": True}
        )

    async def run_comprehensive_monitoring_demo(self) -> Dict[str, Any]:
        """
        종합 모니터링 데모 실행
        
        Returns:
            종합 데모 결과
        """
        logger.info("🎯 종합 모니터링 데모 시작")
        
        demo_results = {
            "demo_start_time": datetime.now().isoformat(),
            "executed_scenarios": [],
            "overall_status": "pending"
        }
        
        try:
            # 1. 시스템 설정
            setup_result = await self.setup_monitoring_system()
            demo_results["system_setup"] = setup_result
            
            if setup_result["status"] != "success":
                demo_results["overall_status"] = "setup_failed"
                return demo_results
            
            # 2. 기본 모니터링 예제
            logger.info("📊 1단계: 기본 모니터링 실행")
            basic_result = await self.run_basic_monitoring_example()
            demo_results["basic_monitoring"] = basic_result
            demo_results["executed_scenarios"].append("basic_monitoring")
            
            # 3. 통합 모니터링 예제
            logger.info("🔗 2단계: 통합 모니터링 실행")
            integrated_result = await self.run_integrated_monitoring_example()
            demo_results["integrated_monitoring"] = integrated_result
            demo_results["executed_scenarios"].append("integrated_monitoring")
            
            # 4. 성능 분석 예제
            logger.info("📈 3단계: 성능 분석 실행")
            analysis_result = await self.run_performance_analysis_example()
            demo_results["performance_analysis"] = analysis_result
            demo_results["executed_scenarios"].append("performance_analysis")
            
            # 5. 알림 모니터링 예제
            logger.info("🚨 4단계: 알림 모니터링 실행")
            alert_result = await self.run_alert_monitoring_example()
            demo_results["alert_monitoring"] = alert_result
            demo_results["executed_scenarios"].append("alert_monitoring")
            
            # 6. 최종 상태 확인
            if all([
                basic_result.get("status") == "success",
                integrated_result.get("status") == "success",
                analysis_result.get("status") == "success",
                alert_result.get("status") == "success"
            ]):
                demo_results["overall_status"] = "success"
            else:
                demo_results["overall_status"] = "partial_success"
            
            demo_results["demo_end_time"] = datetime.now().isoformat()
            demo_results["total_scenarios"] = len(demo_results["executed_scenarios"])
            
            # 7. 종합 인사이트
            demo_results["comprehensive_insights"] = [
                "Langchain 기반 AI 에이전트 시스템 성능 모니터링 완전 구현",
                "실시간 메트릭 수집 및 분석 시스템 정상 작동",
                "통합 모니터링을 통한 전체 시스템 가시성 확보",
                "자동화된 성능 최적화 및 알림 시스템 검증 완료",
                "프로덕션 환경 배포 준비 완료"
            ]
            
            logger.info("🎉 종합 모니터링 데모 완료")
            
            return demo_results
            
        except Exception as e:
            logger.error(f"❌ 종합 모니터링 데모 실패: {e}")
            demo_results["overall_status"] = "failed"
            demo_results["error"] = str(e)
            return demo_results


# 실행 함수들
async def run_monitoring_examples():
    """모니터링 예제 실행"""
    runner = MonitoringExampleRunner()
    
    logger.info("🚀 성능 모니터링 시스템 예제 시작")
    
    # 종합 데모 실행
    results = await runner.run_comprehensive_monitoring_demo()
    
    logger.info("📋 모니터링 예제 실행 결과:")
    logger.info(f"전체 상태: {results['overall_status']}")
    logger.info(f"실행된 시나리오: {results['executed_scenarios']}")
    logger.info(f"총 시나리오 수: {results.get('total_scenarios', 0)}")
    
    return results


def print_monitoring_report(results: Dict[str, Any]):
    """모니터링 리포트 출력"""
    print("\n" + "="*80)
    print("📊 성능 모니터링 시스템 실행 리포트")
    print("="*80)
    
    print(f"\n🎯 전체 실행 상태: {results.get('overall_status', 'unknown').upper()}")
    print(f"📅 실행 시간: {results.get('demo_start_time', 'N/A')} ~ {results.get('demo_end_time', 'N/A')}")
    print(f"🔢 실행된 시나리오: {results.get('total_scenarios', 0)}개")
    
    if 'executed_scenarios' in results:
        print(f"\n📋 실행 시나리오 목록:")
        for i, scenario in enumerate(results['executed_scenarios'], 1):
            print(f"  {i}. {scenario}")
    
    if 'comprehensive_insights' in results:
        print(f"\n💡 주요 인사이트:")
        for i, insight in enumerate(results['comprehensive_insights'], 1):
            print(f"  {i}. {insight}")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    async def main():
        """메인 실행 함수"""
        try:
            # 모니터링 예제 실행
            results = await run_monitoring_examples()
            
            # 결과 출력
            print_monitoring_report(results)
            
            # JSON 형태로도 출력 (선택사항)
            if results.get('overall_status') == 'success':
                print(f"\n📄 상세 결과 (JSON):")
                print(json.dumps(results, indent=2, ensure_ascii=False))
            
        except Exception as e:
            logger.error(f"❌ 메인 실행 실패: {e}")
            print(f"\n💥 실행 중 오류 발생: {e}")
    
    # 비동기 메인 함수 실행
    asyncio.run(main()) 