"""
AI 에이전트 시스템 - Langchain Chain 관리자

이 모듈은 Langchain의 다양한 Chain 유형을 관리하고 
AI 처리 파이프라인을 구성하는 중앙 집중식 시스템입니다.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Union, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from langchain.chains import LLMChain, SimpleSequentialChain, SequentialChain
from langchain.chains.combine_documents import StuffDocumentsChain
from langchain.chains.mapreduce import MapReduceChain
from langchain.chains.conversation.memory import ConversationBufferMemory
from langchain.schema import BaseOutputParser, OutputParserException
from langchain.prompts import PromptTemplate, ChatPromptTemplate

from ..config.prompt_manager import PromptManager
from ..config.gemini_client import GeminiClient


class ChainType(Enum):
    """체인 유형 정의"""
    SIMPLE = "simple"                    # 단순 LLM 체인
    SEQUENTIAL = "sequential"            # 순차 체인 
    CONVERSATION = "conversation"        # 대화 체인
    MAP_REDUCE = "map_reduce"           # 맵-리듀스 체인
    RETRIEVAL_QA = "retrieval_qa"       # 검색 기반 QA 체인
    SUMMARIZATION = "summarization"      # 요약 체인
    EXTRACTION = "extraction"           # 정보 추출 체인
    VALIDATION = "validation"           # 검증 체인
    OPTIMIZATION = "optimization"       # 최적화 체인
    ANALYSIS = "analysis"              # 분석 체인


@dataclass
class ChainConfig:
    """체인 설정 클래스"""
    chain_type: ChainType
    prompt_name: str
    llm_model: str = "gemini-1.5-flash"
    temperature: float = 0.7
    max_tokens: int = 2048
    use_memory: bool = False
    memory_size: int = 10
    custom_parser: Optional[str] = None
    input_variables: List[str] = None
    output_key: str = "output"
    verbose: bool = False
    
    def __post_init__(self):
        if self.input_variables is None:
            self.input_variables = []


@dataclass 
class ChainResult:
    """체인 실행 결과 클래스"""
    success: bool
    output: Any
    execution_time: float
    chain_type: ChainType
    prompt_name: str
    input_data: Dict[str, Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChainOutputParser(BaseOutputParser):
    """체인 출력 파싱 클래스"""
    
    def __init__(self, parser_type: str = "default"):
        """
        출력 파싱기 초기화
        
        Args:
            parser_type: 파싱 유형 ("default", "json", "list", "structured")
        """
        self.parser_type = parser_type
    
    def parse(self, text: str) -> Any:
        """
        텍스트 출력을 파싱
        
        Args:
            text: 파싱할 텍스트
            
        Returns:
            파싱된 결과
        """
        try:
            if self.parser_type == "json":
                import json
                return json.loads(text.strip())
            elif self.parser_type == "list":
                return [item.strip() for item in text.split('\n') if item.strip()]
            elif self.parser_type == "structured":
                return self._parse_structured_output(text)
            else:
                return text.strip()
        except Exception as e:
            raise OutputParserException(f"파싱 오류: {str(e)}")
    
    def _parse_structured_output(self, text: str) -> Dict[str, Any]:
        """구조화된 출력 파싱"""
        result = {}
        lines = text.strip().split('\n')
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                result[key.strip()] = value.strip()
        
        return result


class ChainManager:
    """Langchain Chain 관리자 클래스"""
    
    def __init__(self, gemini_client: GeminiClient, prompt_manager: PromptManager):
        """
        체인 관리자 초기화
        
        Args:
            gemini_client: Gemini 클라이언트
            prompt_manager: 프롬프트 관리자
        """
        self.gemini_client = gemini_client
        self.prompt_manager = prompt_manager
        self.logger = logging.getLogger(__name__)
        
        # 활성 체인 저장소
        self.active_chains: Dict[str, Any] = {}
        
        # 체인 실행 통계
        self.chain_stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "execution_times": [],
            "chain_type_stats": {}
        }
        
        # 메모리 저장소
        self.memories: Dict[str, ConversationBufferMemory] = {}
        
        self.logger.info("ChainManager 초기화 완료")
    
    async def create_chain(self, chain_id: str, config: ChainConfig) -> bool:
        """
        새로운 체인 생성
        
        Args:
            chain_id: 체인 고유 ID
            config: 체인 설정
            
        Returns:
            생성 성공 여부
        """
        try:
            self.logger.info(f"체인 생성 시작: {chain_id} (타입: {config.chain_type.value})")
            
            # LLM 클라이언트 가져오기
            llm = self.gemini_client.get_client(config.llm_model)
            if not llm:
                raise ValueError(f"LLM 클라이언트 생성 실패: {config.llm_model}")
            
            # 프롬프트 가져오기
            prompt_template = self.prompt_manager.get_prompt(config.prompt_name)
            if not prompt_template:
                raise ValueError(f"프롬프트 템플릿을 찾을 수 없음: {config.prompt_name}")
            
            # 체인 유형별 생성
            chain = await self._create_chain_by_type(chain_id, config, llm, prompt_template)
            
            if chain:
                self.active_chains[chain_id] = {
                    "chain": chain,
                    "config": config,
                    "created_at": datetime.now(),
                    "execution_count": 0
                }
                
                self.logger.info(f"체인 생성 완료: {chain_id}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"체인 생성 오류 {chain_id}: {str(e)}")
            return False
    
    async def _create_chain_by_type(self, chain_id: str, config: ChainConfig, 
                                   llm: Any, prompt_template: Any) -> Optional[Any]:
        """
        체인 유형별 생성 로직
        
        Args:
            chain_id: 체인 ID
            config: 체인 설정
            llm: LLM 클라이언트
            prompt_template: 프롬프트 템플릿
            
        Returns:
            생성된 체인 객체
        """
        try:
            if config.chain_type == ChainType.SIMPLE:
                return await self._create_simple_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.SEQUENTIAL:
                return await self._create_sequential_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.CONVERSATION:
                return await self._create_conversation_chain(chain_id, config, llm, prompt_template)
            
            elif config.chain_type == ChainType.MAP_REDUCE:
                return await self._create_map_reduce_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.RETRIEVAL_QA:
                return await self._create_retrieval_qa_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.SUMMARIZATION:
                return await self._create_summarization_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.EXTRACTION:
                return await self._create_extraction_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.VALIDATION:
                return await self._create_validation_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.OPTIMIZATION:
                return await self._create_optimization_chain(config, llm, prompt_template)
            
            elif config.chain_type == ChainType.ANALYSIS:
                return await self._create_analysis_chain(config, llm, prompt_template)
            
            else:
                raise ValueError(f"지원하지 않는 체인 타입: {config.chain_type}")
                
        except Exception as e:
            self.logger.error(f"체인 타입별 생성 오류: {str(e)}")
            return None
    
    async def _create_simple_chain(self, config: ChainConfig, llm: Any, 
                                  prompt_template: Any) -> LLMChain:
        """단순 LLM 체인 생성"""
        output_parser = None
        if config.custom_parser:
            output_parser = ChainOutputParser(config.custom_parser)
        
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            output_parser=output_parser,
            verbose=config.verbose
        )
    
    async def _create_sequential_chain(self, config: ChainConfig, llm: Any,
                                     prompt_template: Any) -> SequentialChain:
        """순차 체인 생성"""
        # 기본 체인 생성
        base_chain = LLMChain(
            llm=llm,
            prompt=prompt_template,
            output_key="step1_output",
            verbose=config.verbose
        )
        
        # 추가 단계를 위한 프롬프트 (필요시 확장 가능)
        additional_chains = [base_chain]
        
        return SequentialChain(
            chains=additional_chains,
            input_variables=config.input_variables or prompt_template.input_variables,
            output_variables=["step1_output"],
            verbose=config.verbose
        )
    
    async def _create_conversation_chain(self, chain_id: str, config: ChainConfig,
                                       llm: Any, prompt_template: Any) -> LLMChain:
        """대화 체인 생성"""
        if config.use_memory:
            memory = ConversationBufferMemory(
                memory_key="chat_history",
                k=config.memory_size,
                return_messages=True
            )
            self.memories[chain_id] = memory
        else:
            memory = None
        
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            memory=memory,
            verbose=config.verbose
        )
    
    async def _create_map_reduce_chain(self, config: ChainConfig, llm: Any,
                                     prompt_template: Any) -> Any:
        """맵-리듀스 체인 생성"""
        # 맵 단계 체인
        map_chain = LLMChain(
            llm=llm,
            prompt=prompt_template,
            verbose=config.verbose
        )
        
        # 리듀스 단계 프롬프트 (요약용)
        reduce_prompt = PromptTemplate(
            template="다음 결과들을 종합하여 최종 결과를 생성하세요:\n{doc_summaries}\n\n최종 결과:",
            input_variables=["doc_summaries"]
        )
        
        reduce_chain = LLMChain(
            llm=llm,
            prompt=reduce_prompt,
            verbose=config.verbose
        )
        
        # 문서 결합 체인
        combine_documents_chain = StuffDocumentsChain(
            llm_chain=reduce_chain,
            document_variable_name="doc_summaries"
        )
        
        return {
            "map_chain": map_chain,
            "reduce_chain": combine_documents_chain,
            "type": "map_reduce"
        }
    
    async def _create_retrieval_qa_chain(self, config: ChainConfig, llm: Any,
                                       prompt_template: Any) -> LLMChain:
        """검색 기반 QA 체인 생성"""
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            verbose=config.verbose
        )
    
    async def _create_summarization_chain(self, config: ChainConfig, llm: Any,
                                        prompt_template: Any) -> LLMChain:
        """요약 체인 생성"""
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            verbose=config.verbose
        )
    
    async def _create_extraction_chain(self, config: ChainConfig, llm: Any,
                                     prompt_template: Any) -> LLMChain:
        """정보 추출 체인 생성"""
        output_parser = ChainOutputParser("structured")
        
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            output_parser=output_parser,
            verbose=config.verbose
        )
    
    async def _create_validation_chain(self, config: ChainConfig, llm: Any,
                                     prompt_template: Any) -> LLMChain:
        """검증 체인 생성"""
        output_parser = ChainOutputParser("json")
        
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            output_parser=output_parser,
            verbose=config.verbose
        )
    
    async def _create_optimization_chain(self, config: ChainConfig, llm: Any,
                                       prompt_template: Any) -> LLMChain:
        """최적화 체인 생성"""
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            verbose=config.verbose
        )
    
    async def _create_analysis_chain(self, config: ChainConfig, llm: Any,
                                   prompt_template: Any) -> LLMChain:
        """분석 체인 생성"""
        output_parser = ChainOutputParser("structured")
        
        return LLMChain(
            llm=llm,
            prompt=prompt_template,
            output_parser=output_parser,
            verbose=config.verbose
        )
    
    async def execute_chain(self, chain_id: str, input_data: Dict[str, Any],
                          **kwargs) -> ChainResult:
        """
        체인 실행
        
        Args:
            chain_id: 실행할 체인 ID
            input_data: 입력 데이터
            **kwargs: 추가 실행 옵션
            
        Returns:
            체인 실행 결과
        """
        start_time = time.time()
        
        try:
            if chain_id not in self.active_chains:
                raise ValueError(f"체인을 찾을 수 없음: {chain_id}")
            
            chain_info = self.active_chains[chain_id]
            chain = chain_info["chain"]
            config = chain_info["config"]
            
            self.logger.info(f"체인 실행 시작: {chain_id}")
            
            # 체인 유형별 실행
            if isinstance(chain, dict) and chain.get("type") == "map_reduce":
                output = await self._execute_map_reduce_chain(chain, input_data, **kwargs)
            else:
                # 일반 체인 실행
                if asyncio.iscoroutinefunction(chain.arun):
                    output = await chain.arun(**input_data, **kwargs)
                else:
                    output = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: chain.run(**input_data, **kwargs)
                    )
            
            execution_time = time.time() - start_time
            
            # 통계 업데이트
            self._update_execution_stats(config.chain_type, execution_time, True)
            chain_info["execution_count"] += 1
            
            result = ChainResult(
                success=True,
                output=output,
                execution_time=execution_time,
                chain_type=config.chain_type,
                prompt_name=config.prompt_name,
                input_data=input_data,
                metadata={
                    "chain_id": chain_id,
                    "execution_count": chain_info["execution_count"],
                    "model": config.llm_model
                }
            )
            
            self.logger.info(f"체인 실행 완료: {chain_id} ({execution_time:.2f}초)")
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = str(e)
            
            # 실패 통계 업데이트
            if chain_id in self.active_chains:
                config = self.active_chains[chain_id]["config"]
                self._update_execution_stats(config.chain_type, execution_time, False)
            
            self.logger.error(f"체인 실행 오류 {chain_id}: {error_msg}")
            
            return ChainResult(
                success=False,
                output=None,
                execution_time=execution_time,
                chain_type=config.chain_type if chain_id in self.active_chains else ChainType.SIMPLE,
                prompt_name=config.prompt_name if chain_id in self.active_chains else "unknown",
                input_data=input_data,
                error=error_msg
            )
    
    async def _execute_map_reduce_chain(self, chain_dict: Dict[str, Any],
                                      input_data: Dict[str, Any], **kwargs) -> Any:
        """맵-리듀스 체인 실행"""
        map_chain = chain_dict["map_chain"]
        reduce_chain = chain_dict["reduce_chain"]
        
        # 입력 데이터 분할 (예: 텍스트를 문단별로 분할)
        documents = input_data.get("documents", [])
        if not documents and "text" in input_data:
            # 텍스트를 문단별로 분할
            text = input_data["text"]
            documents = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        # 맵 단계: 각 문서 처리
        map_results = []
        for doc in documents:
            map_input = {**input_data, "text": doc}
            result = await map_chain.arun(**map_input)
            map_results.append(result)
        
        # 리듀스 단계: 결과 결합
        reduce_input = {"doc_summaries": "\n".join(map_results)}
        final_result = await reduce_chain.run(**reduce_input)
        
        return final_result
    
    def _update_execution_stats(self, chain_type: ChainType, execution_time: float,
                               success: bool):
        """실행 통계 업데이트"""
        self.chain_stats["total_executions"] += 1
        
        if success:
            self.chain_stats["successful_executions"] += 1
        else:
            self.chain_stats["failed_executions"] += 1
        
        self.chain_stats["execution_times"].append(execution_time)
        
        # 체인 타입별 통계
        type_key = chain_type.value
        if type_key not in self.chain_stats["chain_type_stats"]:
            self.chain_stats["chain_type_stats"][type_key] = {
                "executions": 0,
                "successes": 0,
                "failures": 0,
                "avg_time": 0.0
            }
        
        type_stats = self.chain_stats["chain_type_stats"][type_key]
        type_stats["executions"] += 1
        
        if success:
            type_stats["successes"] += 1
        else:
            type_stats["failures"] += 1
        
        # 평균 실행 시간 계산
        type_stats["avg_time"] = (
            (type_stats["avg_time"] * (type_stats["executions"] - 1) + execution_time) /
            type_stats["executions"]
        )
    
    async def execute_batch_chains(self, batch_requests: List[Dict[str, Any]]) -> List[ChainResult]:
        """
        배치 체인 실행
        
        Args:
            batch_requests: 배치 요청 목록
                각 요청은 {"chain_id": str, "input_data": dict, "kwargs": dict} 형태
        
        Returns:
            배치 실행 결과 목록
        """
        self.logger.info(f"배치 체인 실행 시작: {len(batch_requests)}개 요청")
        
        tasks = []
        for request in batch_requests:
            chain_id = request["chain_id"]
            input_data = request["input_data"]
            kwargs = request.get("kwargs", {})
            
            task = self.execute_chain(chain_id, input_data, **kwargs)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 예외 처리된 결과 변환
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                request = batch_requests[i]
                processed_results.append(ChainResult(
                    success=False,
                    output=None,
                    execution_time=0.0,
                    chain_type=ChainType.SIMPLE,
                    prompt_name="unknown",
                    input_data=request["input_data"],
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        self.logger.info(f"배치 체인 실행 완료: {len(processed_results)}개 결과")
        return processed_results
    
    def get_chain_info(self, chain_id: str) -> Optional[Dict[str, Any]]:
        """
        체인 정보 조회
        
        Args:
            chain_id: 체인 ID
            
        Returns:
            체인 정보
        """
        if chain_id not in self.active_chains:
            return None
        
        chain_info = self.active_chains[chain_id]
        config = chain_info["config"]
        
        return {
            "chain_id": chain_id,
            "chain_type": config.chain_type.value,
            "prompt_name": config.prompt_name,
            "llm_model": config.llm_model,
            "created_at": chain_info["created_at"].isoformat(),
            "execution_count": chain_info["execution_count"],
            "config": asdict(config)
        }
    
    def list_active_chains(self) -> List[Dict[str, Any]]:
        """활성 체인 목록 조회"""
        return [self.get_chain_info(chain_id) for chain_id in self.active_chains.keys()]
    
    def delete_chain(self, chain_id: str) -> bool:
        """
        체인 삭제
        
        Args:
            chain_id: 삭제할 체인 ID
            
        Returns:
            삭제 성공 여부
        """
        if chain_id in self.active_chains:
            del self.active_chains[chain_id]
            
            # 메모리도 함께 삭제
            if chain_id in self.memories:
                del self.memories[chain_id]
            
            self.logger.info(f"체인 삭제 완료: {chain_id}")
            return True
        
        return False
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """실행 통계 조회"""
        stats = self.chain_stats.copy()
        
        # 평균 실행 시간 계산
        if stats["execution_times"]:
            stats["avg_execution_time"] = sum(stats["execution_times"]) / len(stats["execution_times"])
            stats["min_execution_time"] = min(stats["execution_times"])
            stats["max_execution_time"] = max(stats["execution_times"])
        else:
            stats["avg_execution_time"] = 0.0
            stats["min_execution_time"] = 0.0
            stats["max_execution_time"] = 0.0
        
        # 성공률 계산
        if stats["total_executions"] > 0:
            stats["success_rate"] = stats["successful_executions"] / stats["total_executions"]
        else:
            stats["success_rate"] = 0.0
        
        return stats
    
    def clear_memory(self, chain_id: str) -> bool:
        """
        체인 메모리 초기화
        
        Args:
            chain_id: 체인 ID
            
        Returns:
            초기화 성공 여부
        """
        if chain_id in self.memories:
            self.memories[chain_id].clear()
            self.logger.info(f"체인 메모리 초기화 완료: {chain_id}")
            return True
        
        return False
    
    async def cleanup_inactive_chains(self, max_idle_hours: int = 24) -> int:
        """
        비활성 체인 정리
        
        Args:
            max_idle_hours: 최대 유휴 시간 (시간)
            
        Returns:
            정리된 체인 수
        """
        from datetime import timedelta
        
        current_time = datetime.now()
        chains_to_delete = []
        
        for chain_id, chain_info in self.active_chains.items():
            idle_time = current_time - chain_info["created_at"]
            if idle_time > timedelta(hours=max_idle_hours):
                chains_to_delete.append(chain_id)
        
        deleted_count = 0
        for chain_id in chains_to_delete:
            if self.delete_chain(chain_id):
                deleted_count += 1
        
        if deleted_count > 0:
            self.logger.info(f"비활성 체인 정리 완료: {deleted_count}개")
        
        return deleted_count


# 사전 정의된 체인 설정들
PREDEFINED_CHAIN_CONFIGS = {
    "search_strategy_chain": ChainConfig(
        chain_type=ChainType.SIMPLE,
        prompt_name="search_strategy",
        temperature=0.3,
        max_tokens=1024,
        custom_parser="structured"
    ),
    
    "contact_extraction_chain": ChainConfig(
        chain_type=ChainType.EXTRACTION,
        prompt_name="contact_extraction", 
        temperature=0.1,
        max_tokens=2048,
        custom_parser="structured"
    ),
    
    "data_validation_chain": ChainConfig(
        chain_type=ChainType.VALIDATION,
        prompt_name="data_validation",
        temperature=0.0,
        max_tokens=1024,
        custom_parser="json"
    ),
    
    "performance_optimization_chain": ChainConfig(
        chain_type=ChainType.OPTIMIZATION,
        prompt_name="performance_optimization",
        temperature=0.2,
        max_tokens=2048
    ),
    
    "text_summarization_chain": ChainConfig(
        chain_type=ChainType.SUMMARIZATION,
        prompt_name="text_summarization",
        temperature=0.3,
        max_tokens=1024
    ),
    
    "conversation_chain": ChainConfig(
        chain_type=ChainType.CONVERSATION,
        prompt_name="conversation",
        temperature=0.7,
        max_tokens=2048,
        use_memory=True,
        memory_size=10
    ),
    
    "document_analysis_chain": ChainConfig(
        chain_type=ChainType.MAP_REDUCE,
        prompt_name="document_analysis",
        temperature=0.2,
        max_tokens=1024
    ),
    
    "quality_assessment_chain": ChainConfig(
        chain_type=ChainType.ANALYSIS,
        prompt_name="quality_assessment",
        temperature=0.1,
        max_tokens=1024,
        custom_parser="structured"
    )
}


def get_predefined_chain_config(chain_name: str) -> Optional[ChainConfig]:
    """
    사전 정의된 체인 설정 가져오기
    
    Args:
        chain_name: 체인 이름
        
    Returns:
        체인 설정 또는 None
    """
    return PREDEFINED_CHAIN_CONFIGS.get(chain_name)


def list_predefined_chains() -> List[str]:
    """사전 정의된 체인 목록 반환"""
    return list(PREDEFINED_CHAIN_CONFIGS.keys()) 