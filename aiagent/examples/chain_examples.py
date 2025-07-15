"""
AI 에이전트 시스템 - Langchain Chain 사용 예제

이 모듈은 Langchain Chain 기반 AI 처리 파이프라인의
다양한 사용 방법을 보여주는 예제들을 포함합니다.
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
import os
import dotenv

from ..config.gemini_client import GeminiClient, GeminiConfig
from ..config.prompt_manager import PromptManager
from ..core.chain_service import ChainService, ChainServiceConfig, create_chain_service
from ..core.chain_manager import ChainConfig, ChainType
from ..core.chain_pipeline import (
    PipelineConfig, PipelineStep, PipelineStepType,
    create_contact_enrichment_pipeline, create_document_analysis_pipeline
)

os.getenv("GEMINI_API_KEY") 
os.getenv("GEMINI_API_KEY_2") 
os.getenv("GEMINI_API_KEY_3") 
os.getenv("GEMINI_API_KEY_4") 

class ChainExampleRunner:
    """Chain 시스템 예제 실행기"""
    
    def __init__(self):
        """예제 실행기 초기화"""
        self.logger = logging.getLogger(__name__)
        self.chain_service: ChainService = None
        
        # 예제 데이터
        self.sample_data = {
            "organization": {
                "name": "삼성교회",
                "category": "교회",
                "address": "서울시 강남구 삼성동",
                "phone": "",
                "email": "",
                "homepage": ""
            },
            "search_query": "삼성교회 연락처 정보",
            "document_text": """
            삼성교회는 1980년에 설립된 대한예수교장로회 소속 교회입니다.
            
            주소: 서울시 강남구 삼성동 159-1
            전화: 02-555-1234
            팩스: 02-555-5678
            이메일: contact@samsung-church.org
            홈페이지: https://www.samsung-church.org
            
            매주 주일예배는 오전 10시 30분에 시작되며,
            수요예배는 오후 7시 30분에 진행됩니다.
            
            교육관, 본당, 주차장 등의 시설을 갖추고 있으며,
            유아부부터 장년부까지 다양한 교육 프로그램을 운영하고 있습니다.
            """,
            "validation_data": {
                "phone": "02-555-1234",
                "email": "contact@samsung-church.org",
                "address": "서울시 강남구 삼성동 159-1",
                "homepage": "https://www.samsung-church.org"
            }
        }
    
    async def initialize(self):
        """Chain 서비스 초기화"""
        try:
            # Gemini 클라이언트 설정
            gemini_config = GeminiConfig(
                api_keys=[GEMIN_API_KEY],  # 실제 API 키로 교체 필요
                model_name="gemini-1.5-flash",
                max_requests_per_minute=60,
                max_tokens_per_minute=40000
            )
            gemini_client = GeminiClient(gemini_config)
            
            # 프롬프트 관리자 초기화
            prompt_manager = PromptManager()
            
            # Chain 서비스 생성 및 초기화
            service_config = ChainServiceConfig(
                enable_auto_cleanup=True,
                cleanup_interval_hours=1,  # 1시간마다 정리
                max_concurrent_executions=5,
                default_timeout=120.0,
                enable_caching=True,
                cache_ttl_seconds=1800,  # 30분 캐시
                log_level="INFO"
            )
            
            self.chain_service = await create_chain_service(
                gemini_client, prompt_manager, service_config
            )
            
            self.logger.info("Chain 서비스 초기화 완료")
            
        except Exception as e:
            self.logger.error(f"초기화 오류: {str(e)}")
            raise e
    
    async def example_1_basic_chain_usage(self):
        """예제 1: 기본 Chain 사용법"""
        print("\n" + "="*60)
        print("예제 1: 기본 Chain 사용법")
        print("="*60)
        
        try:
            # 1. 검색 전략 체인 실행
            print("\n1. 검색 전략 체인 실행:")
            search_input = {
                "organization_name": self.sample_data["organization"]["name"],
                "organization_category": self.sample_data["organization"]["category"],
                "current_info": json.dumps(self.sample_data["organization"], ensure_ascii=False)
            }
            
            search_result = await self.chain_service.execute_chain(
                "search_strategy_chain", search_input
            )
            
            print(f"  성공: {search_result.success}")
            print(f"  실행 시간: {search_result.execution_time:.2f}초")
            if search_result.success:
                print(f"  결과: {search_result.output}")
            else:
                print(f"  오류: {search_result.error}")
            
            # 2. 연락처 추출 체인 실행
            print("\n2. 연락처 추출 체인 실행:")
            contact_input = {
                "organization_name": self.sample_data["organization"]["name"],
                "webpage_content": self.sample_data["document_text"],
                "current_contact_info": json.dumps({
                    "phone": self.sample_data["organization"]["phone"],
                    "email": self.sample_data["organization"]["email"]
                }, ensure_ascii=False)
            }
            
            contact_result = await self.chain_service.execute_chain(
                "contact_extraction_chain", contact_input
            )
            
            print(f"  성공: {contact_result.success}")
            print(f"  실행 시간: {contact_result.execution_time:.2f}초")
            if contact_result.success:
                print(f"  결과: {contact_result.output}")
            else:
                print(f"  오류: {contact_result.error}")
            
            # 3. 데이터 검증 체인 실행
            print("\n3. 데이터 검증 체인 실행:")
            validation_input = {
                "data_to_validate": json.dumps(self.sample_data["validation_data"], ensure_ascii=False),
                "validation_rules": "전화번호, 이메일, 주소, 홈페이지 형식 검증"
            }
            
            validation_result = await self.chain_service.execute_chain(
                "data_validation_chain", validation_input
            )
            
            print(f"  성공: {validation_result.success}")
            print(f"  실행 시간: {validation_result.execution_time:.2f}초")
            if validation_result.success:
                print(f"  결과: {validation_result.output}")
            else:
                print(f"  오류: {validation_result.error}")
                
        except Exception as e:
            print(f"예제 1 실행 오류: {str(e)}")
    
    async def example_2_batch_chain_execution(self):
        """예제 2: 배치 Chain 실행"""
        print("\n" + "="*60)
        print("예제 2: 배치 Chain 실행")
        print("="*60)
        
        try:
            # 배치 요청 준비
            batch_requests = [
                {
                    "chain_id": "search_strategy_chain",
                    "input_data": {
                        "organization_name": "삼성교회",
                        "organization_category": "교회",
                        "current_info": '{"name": "삼성교회", "category": "교회"}'
                    }
                },
                {
                    "chain_id": "search_strategy_chain", 
                    "input_data": {
                        "organization_name": "강남학원",
                        "organization_category": "학원",
                        "current_info": '{"name": "강남학원", "category": "학원"}'
                    }
                },
                {
                    "chain_id": "text_summarization_chain",
                    "input_data": {
                        "text_to_summarize": self.sample_data["document_text"],
                        "summary_length": "3-5 문장"
                    }
                }
            ]
            
            print(f"배치 요청 수: {len(batch_requests)}")
            
            # 배치 실행
            batch_results = await self.chain_service.execute_batch_chains(batch_requests)
            
            print(f"배치 결과 수: {len(batch_results)}")
            
            # 결과 출력
            for i, result in enumerate(batch_results):
                print(f"\n요청 {i+1}:")
                print(f"  체인: {batch_requests[i]['chain_id']}")
                print(f"  성공: {result.success}")
                print(f"  실행 시간: {result.execution_time:.2f}초")
                if result.success:
                    output_preview = str(result.output)[:100] + "..." if len(str(result.output)) > 100 else str(result.output)
                    print(f"  결과 미리보기: {output_preview}")
                else:
                    print(f"  오류: {result.error}")
                    
        except Exception as e:
            print(f"예제 2 실행 오류: {str(e)}")
    
    async def example_3_pipeline_usage(self):
        """예제 3: 파이프라인 사용법"""
        print("\n" + "="*60)
        print("예제 3: 파이프라인 사용법")
        print("="*60)
        
        try:
            # 1. 연락처 보강 파이프라인 실행
            print("\n1. 연락처 보강 파이프라인 실행:")
            
            enrichment_input = {
                "organization_name": self.sample_data["organization"]["name"],
                "organization_category": self.sample_data["organization"]["category"],
                "current_info": json.dumps(self.sample_data["organization"], ensure_ascii=False),
                "webpage_content": self.sample_data["document_text"]
            }
            
            pipeline_result = await self.chain_service.execute_pipeline(
                "contact_enrichment_pipeline", enrichment_input
            )
            
            print(f"  파이프라인 성공: {pipeline_result.success}")
            print(f"  총 실행 시간: {pipeline_result.execution_time:.2f}초")
            print(f"  실행된 단계: {pipeline_result.steps_executed}")
            print(f"  실패한 단계: {pipeline_result.steps_failed}")
            
            if pipeline_result.success:
                print(f"  최종 결과: {pipeline_result.final_output}")
                
                # 단계별 결과 출력
                print("\n  단계별 결과:")
                for step_result in pipeline_result.step_results:
                    print(f"    {step_result['step_id']}: {step_result['success']} ({step_result['execution_time']:.2f}초)")
            else:
                print(f"  오류: {pipeline_result.error}")
            
            # 2. 문서 분석 파이프라인 실행
            print("\n2. 문서 분석 파이프라인 실행:")
            
            analysis_input = {
                "text": self.sample_data["document_text"],
                "analysis_type": "연락처 정보 추출 및 요약"
            }
            
            analysis_result = await self.chain_service.execute_pipeline(
                "document_analysis_pipeline", analysis_input
            )
            
            print(f"  파이프라인 성공: {analysis_result.success}")
            print(f"  총 실행 시간: {analysis_result.execution_time:.2f}초")
            print(f"  실행된 단계: {analysis_result.steps_executed}")
            print(f"  실패한 단계: {analysis_result.steps_failed}")
            
            if analysis_result.success:
                output_preview = str(analysis_result.final_output)[:200] + "..." if len(str(analysis_result.final_output)) > 200 else str(analysis_result.final_output)
                print(f"  최종 결과 미리보기: {output_preview}")
                
        except Exception as e:
            print(f"예제 3 실행 오류: {str(e)}")
    
    async def example_4_custom_chain_creation(self):
        """예제 4: 커스텀 Chain 생성"""
        print("\n" + "="*60)
        print("예제 4: 커스텀 Chain 생성")
        print("="*60)
        
        try:
            # 커스텀 체인 설정
            custom_config = ChainConfig(
                chain_type=ChainType.SIMPLE,
                prompt_name="conversation",  # 기본 대화 프롬프트 사용
                llm_model="gemini-1.5-flash",
                temperature=0.8,
                max_tokens=1024,
                use_memory=True,
                memory_size=5,
                verbose=True
            )
            
            # 커스텀 체인 생성
            custom_chain_id = "custom_conversation_chain"
            creation_success = await self.chain_service.create_chain(
                custom_chain_id, custom_config
            )
            
            print(f"커스텀 체인 생성: {creation_success}")
            
            if creation_success:
                # 대화형 체인 테스트
                conversation_inputs = [
                    {"input": "안녕하세요! 교회 정보 관리에 대해 도움을 받고 싶습니다."},
                    {"input": "삼성교회의 연락처 정보를 어떻게 관리하면 좋을까요?"},
                    {"input": "감사합니다. 추가로 질문이 있으면 연락드리겠습니다."}
                ]
                
                print("\n대화형 체인 테스트:")
                for i, conv_input in enumerate(conversation_inputs):
                    print(f"\n  대화 {i+1}:")
                    print(f"    입력: {conv_input['input']}")
                    
                    result = await self.chain_service.execute_chain(
                        custom_chain_id, conv_input, use_cache=False
                    )
                    
                    print(f"    성공: {result.success}")
                    if result.success:
                        print(f"    응답: {result.output}")
                    else:
                        print(f"    오류: {result.error}")
                
                # 체인 삭제
                deletion_success = self.chain_service.delete_chain(custom_chain_id)
                print(f"\n커스텀 체인 삭제: {deletion_success}")
                
        except Exception as e:
            print(f"예제 4 실행 오류: {str(e)}")
    
    async def example_5_custom_pipeline_creation(self):
        """예제 5: 커스텀 파이프라인 생성"""
        print("\n" + "="*60)
        print("예제 5: 커스텀 파이프라인 생성")
        print("="*60)
        
        try:
            # 커스텀 파이프라인 설정
            custom_pipeline = PipelineConfig(
                pipeline_id="custom_analysis_pipeline",
                name="커스텀 분석 파이프라인",
                description="텍스트 분석 후 요약하고 검증하는 파이프라인",
                steps=[
                    PipelineStep(
                        step_id="text_analysis",
                        step_type=PipelineStepType.SEQUENTIAL,
                        chain_ids=["document_analysis_chain"]
                    ),
                    PipelineStep(
                        step_id="summarization",
                        step_type=PipelineStepType.SEQUENTIAL,
                        chain_ids=["text_summarization_chain"],
                        dependencies=["text_analysis"]
                    ),
                    PipelineStep(
                        step_id="validation",
                        step_type=PipelineStepType.SEQUENTIAL,
                        chain_ids=["quality_assessment_chain"],
                        dependencies=["summarization"]
                    )
                ],
                error_handling="continue",
                max_retries=2
            )
            
            # 파이프라인 등록
            registration_success = self.chain_service.register_pipeline(custom_pipeline)
            print(f"커스텀 파이프라인 등록: {registration_success}")
            
            if registration_success:
                # 파이프라인 실행
                pipeline_input = {
                    "text": self.sample_data["document_text"],
                    "analysis_focus": "연락처 정보 및 시설 현황",
                    "summary_length": "2-3 문장"
                }
                
                print("\n커스텀 파이프라인 실행:")
                custom_result = await self.chain_service.execute_pipeline(
                    "custom_analysis_pipeline", pipeline_input
                )
                
                print(f"  성공: {custom_result.success}")
                print(f"  실행 시간: {custom_result.execution_time:.2f}초")
                print(f"  실행 단계: {custom_result.steps_executed}/{len(custom_pipeline.steps)}")
                
                if custom_result.success:
                    print(f"  최종 결과: {custom_result.final_output}")
                else:
                    print(f"  오류: {custom_result.error}")
                
                # 파이프라인 삭제
                deletion_success = self.chain_service.delete_pipeline("custom_analysis_pipeline")
                print(f"\n커스텀 파이프라인 삭제: {deletion_success}")
                
        except Exception as e:
            print(f"예제 5 실행 오류: {str(e)}")
    
    async def example_6_service_monitoring(self):
        """예제 6: 서비스 모니터링"""
        print("\n" + "="*60)
        print("예제 6: 서비스 모니터링")
        print("="*60)
        
        try:
            # 1. 서비스 상태 확인
            print("1. 서비스 상태:")
            health_status = self.chain_service.get_health_status()
            print(f"  전체 상태: {'정상' if health_status['healthy'] else '비정상'}")
            print(f"  확인 시간: {health_status['timestamp']}")
            
            if 'components' in health_status:
                for component, status in health_status['components'].items():
                    print(f"  {component}: {status}")
            
            # 2. 서비스 통계
            print("\n2. 서비스 통계:")
            service_stats = self.chain_service.get_service_stats()
            
            print(f"  활성 체인 수: {service_stats['chains']['active_count']}")
            print(f"  활성 파이프라인 수: {service_stats['pipelines']['active_count']}")
            print(f"  캐시 활성화: {service_stats['cache']['enabled']}")
            print(f"  캐시 크기: {service_stats['cache']['size']}")
            
            # Chain 실행 통계
            chain_stats = service_stats['chains']['execution_stats']
            if chain_stats['total_executions'] > 0:
                print(f"  체인 총 실행: {chain_stats['total_executions']}")
                print(f"  체인 성공률: {chain_stats['success_rate']:.2%}")
                print(f"  체인 평균 시간: {chain_stats['avg_execution_time']:.2f}초")
            
            # 3. 활성 체인 목록
            print("\n3. 활성 체인 목록:")
            active_chains = self.chain_service.list_active_chains()
            for chain_info in active_chains[:5]:  # 처음 5개만 표시
                print(f"  - {chain_info['chain_id']} ({chain_info['chain_type']})")
                print(f"    실행 횟수: {chain_info['execution_count']}")
                print(f"    생성 시간: {chain_info['created_at']}")
            
            # 4. 활성 파이프라인 목록
            print("\n4. 활성 파이프라인 목록:")
            active_pipelines = self.chain_service.list_active_pipelines()
            for pipeline_info in active_pipelines:
                print(f"  - {pipeline_info['pipeline_id']}: {pipeline_info['name']}")
                print(f"    단계 수: {pipeline_info['total_steps']}")
                print(f"    설명: {pipeline_info['description']}")
                
        except Exception as e:
            print(f"예제 6 실행 오류: {str(e)}")
    
    async def example_7_performance_testing(self):
        """예제 7: 성능 테스트"""
        print("\n" + "="*60)
        print("예제 7: 성능 테스트")
        print("="*60)
        
        try:
            # 1. 체인 워밍업
            print("1. 체인 워밍업:")
            warmup_chains = ["search_strategy_chain", "contact_extraction_chain", "data_validation_chain"]
            sample_input = {"input": "테스트 데이터", "test": True}
            
            warmup_results = await self.chain_service.warmup_chains(warmup_chains, sample_input)
            
            for chain_id, success in warmup_results.items():
                print(f"  {chain_id}: {'성공' if success else '실패'}")
            
            # 2. 성능 벤치마크
            print("\n2. 성능 벤치마크 (각 체인 3회 실행):")
            benchmark_results = await self.chain_service.benchmark_chains(
                warmup_chains, sample_input, iterations=3
            )
            
            for chain_id, stats in benchmark_results.items():
                print(f"  {chain_id}:")
                print(f"    평균 시간: {stats['avg_time']:.2f}초")
                print(f"    최소/최대: {stats['min_time']:.2f}초 / {stats['max_time']:.2f}초")
                print(f"    성공률: {stats['success_rate']:.2%}")
            
            # 3. 캐시 성능 테스트
            print("\n3. 캐시 성능 테스트:")
            
            # 캐시 없이 실행
            start_time = asyncio.get_event_loop().time()
            result1 = await self.chain_service.execute_chain(
                "search_strategy_chain", sample_input, use_cache=False
            )
            no_cache_time = asyncio.get_event_loop().time() - start_time
            
            # 캐시 사용하여 실행
            start_time = asyncio.get_event_loop().time()
            result2 = await self.chain_service.execute_chain(
                "search_strategy_chain", sample_input, use_cache=True
            )
            cache_time = asyncio.get_event_loop().time() - start_time
            
            print(f"  캐시 없이: {no_cache_time:.3f}초")
            print(f"  캐시 사용: {cache_time:.3f}초")
            if no_cache_time > 0:
                speedup = no_cache_time / cache_time if cache_time > 0 else float('inf')
                print(f"  속도 향상: {speedup:.1f}x")
                
        except Exception as e:
            print(f"예제 7 실행 오류: {str(e)}")
    
    async def run_all_examples(self):
        """모든 예제 실행"""
        print("Langchain Chain 기반 AI 처리 파이프라인 예제")
        print("=" * 80)
        
        try:
            # 초기화
            await self.initialize()
            
            # 모든 예제 실행
            await self.example_1_basic_chain_usage()
            await self.example_2_batch_chain_execution()
            await self.example_3_pipeline_usage()
            await self.example_4_custom_chain_creation()
            await self.example_5_custom_pipeline_creation()
            await self.example_6_service_monitoring()
            await self.example_7_performance_testing()
            
            print("\n" + "="*80)
            print("모든 예제 실행 완료!")
            
        except Exception as e:
            print(f"예제 실행 중 오류 발생: {str(e)}")
        
        finally:
            # 서비스 종료
            if self.chain_service:
                await self.chain_service.shutdown()
                print("Chain 서비스 종료 완료")


async def main():
    """메인 실행 함수"""
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 예제 실행
    runner = ChainExampleRunner()
    await runner.run_all_examples()


if __name__ == "__main__":
    # 예제 실행
    asyncio.run(main()) 