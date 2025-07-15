# 데이터 검증 및 품질 보증 에이전트
# 크롤링으로 수집된 데이터의 정확성, 완성도, 일관성을 검증하는 AI 에이전트

from typing import Dict, List, Optional, Any, Union, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio
import json
import logging
import re
from enum import Enum

from ..core.agent_base import BaseAgent, AgentResult, AgentConfig
from ..utils.gemini_client import GeminiClient
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

logger = logging.getLogger(__name__)

class ValidationLevel(Enum):
    """검증 수준"""
    BASIC = "basic"           # 기본 검증 (형식, 필수 필드)
    STANDARD = "standard"     # 표준 검증 (논리적 일관성)
    ADVANCED = "advanced"     # 고급 검증 (외부 검증, AI 분석)
    COMPREHENSIVE = "comprehensive"  # 종합 검증 (모든 검증)

class ValidationCategory(Enum):
    """검증 카테고리"""
    FORMAT = "format"         # 형식 검증
    COMPLETENESS = "completeness"  # 완성도 검증
    CONSISTENCY = "consistency"    # 일관성 검증
    ACCURACY = "accuracy"     # 정확성 검증
    DUPLICATION = "duplication"    # 중복 검증
    BUSINESS_LOGIC = "business_logic"  # 비즈니스 로직 검증

@dataclass
class ValidationRule:
    """검증 규칙"""
    name: str                 # 규칙명
    category: ValidationCategory
    level: ValidationLevel
    description: str          # 규칙 설명
    field_names: List[str]    # 대상 필드들
    validation_function: str  # 검증 함수명
    error_message: str        # 오류 메시지
    severity: str = "error"   # 심각도 (error, warning, info)

@dataclass
class ValidationIssue:
    """검증 문제"""
    rule_name: str           # 규칙명
    category: ValidationCategory
    severity: str            # 심각도
    field_name: str          # 문제 필드
    current_value: Any       # 현재 값
    expected_value: Optional[Any] = None  # 예상 값
    suggestion: Optional[str] = None      # 수정 제안
    confidence: float = 1.0  # 확신도

@dataclass
class ValidationTarget:
    """검증 대상 데이터"""
    id: str                  # 데이터 ID
    name: str                # 기관명
    category: str            # 카테고리
    data: Dict[str, Any]     # 검증할 데이터
    metadata: Dict[str, Any] = None  # 메타데이터

@dataclass
class ValidationResult:
    """검증 결과"""
    target: ValidationTarget
    is_valid: bool           # 전체 검증 통과 여부
    quality_score: float     # 품질 점수 (0.0 ~ 1.0)
    completeness_score: float # 완성도 점수
    issues: List[ValidationIssue]  # 발견된 문제들
    validation_time: float   # 검증 소요 시간
    rules_applied: List[str] # 적용된 규칙들

class ValidationAgent(BaseAgent):
    """
    데이터 검증 및 품질 보증 에이전트
    
    기능:
    - 다층 검증 시스템 (형식, 완성도, 일관성, 정확성)
    - AI 기반 지능형 데이터 검증
    - 실시간 품질 점수 계산
    - 자동 수정 제안 생성
    """
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.validation_rules = self._load_validation_rules()
        self.phone_regex = re.compile(r'^0\d{1,2}-\d{3,4}-\d{4}$')
        self.email_regex = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        self.url_regex = re.compile(r'^https?://[^\s/$.?#].[^\s]*$')
        
        # Langchain 프롬프트 템플릿
        self.consistency_prompt = PromptTemplate(
            input_variables=["organization_data", "category"],
            template="""
            다음 기관 데이터의 논리적 일관성을 검증해주세요:

            기관 정보:
            {organization_data}
            
            카테고리: {category}

            검증 항목:
            1. 기관명과 카테고리의 일치성
            2. 주소 정보의 일관성 (시/구/동 등)
            3. 연락처 정보의 일관성 (지역번호와 주소)
            4. 카테고리별 특수 규칙 적용

            JSON 형식으로 응답:
            {{
                "is_consistent": true/false,
                "issues": [
                    {{
                        "field": "필드명",
                        "issue": "문제 설명",
                        "severity": "error/warning/info",
                        "suggestion": "수정 제안"
                    }}
                ],
                "overall_score": 0.85,
                "confidence": 0.9
            }}
            """
        )
        
        # 정확성 검증 프롬프트
        self.accuracy_prompt = PromptTemplate(
            input_variables=["organization_name", "category", "contact_info", "address"],
            template="""
            다음 기관 정보의 정확성을 판단해주세요:

            기관명: {organization_name}
            카테고리: {category}
            연락처: {contact_info}
            주소: {address}

            검증 기준:
            1. 기관명이 실제 존재하는 기관인지
            2. 연락처가 해당 기관의 것인지
            3. 주소가 실제 주소인지
            4. 전반적인 신뢰성

            JSON 응답:
            {{
                "accuracy_score": 0.85,
                "reliability_factors": [
                    "확인된 요소들"
                ],
                "concerns": [
                    "의심스러운 요소들"
                ],
                "verification_suggestions": [
                    "추가 검증 방법들"
                ]
            }}
            """
        )
    
    def _load_validation_rules(self) -> List[ValidationRule]:
        """검증 규칙 로드"""
        rules = [
            # 형식 검증 규칙
            ValidationRule(
                name="phone_format",
                category=ValidationCategory.FORMAT,
                level=ValidationLevel.BASIC,
                description="전화번호 형식 검증",
                field_names=["phone", "mobile", "fax"],
                validation_function="_validate_phone_format",
                error_message="전화번호 형식이 올바르지 않습니다"
            ),
            ValidationRule(
                name="email_format",
                category=ValidationCategory.FORMAT,
                level=ValidationLevel.BASIC,
                description="이메일 형식 검증",
                field_names=["email"],
                validation_function="_validate_email_format",
                error_message="이메일 형식이 올바르지 않습니다"
            ),
            ValidationRule(
                name="url_format",
                category=ValidationCategory.FORMAT,
                level=ValidationLevel.BASIC,
                description="URL 형식 검증",
                field_names=["homepage"],
                validation_function="_validate_url_format",
                error_message="URL 형식이 올바르지 않습니다"
            ),
            
            # 완성도 검증 규칙
            ValidationRule(
                name="required_fields",
                category=ValidationCategory.COMPLETENESS,
                level=ValidationLevel.BASIC,
                description="필수 필드 존재 검증",
                field_names=["name", "category"],
                validation_function="_validate_required_fields",
                error_message="필수 필드가 누락되었습니다"
            ),
            ValidationRule(
                name="contact_completeness",
                category=ValidationCategory.COMPLETENESS,
                level=ValidationLevel.STANDARD,
                description="연락처 정보 완성도 검증",
                field_names=["phone", "mobile", "email", "homepage"],
                validation_function="_validate_contact_completeness",
                error_message="연락처 정보가 부족합니다",
                severity="warning"
            ),
            
            # 일관성 검증 규칙
            ValidationRule(
                name="name_category_consistency",
                category=ValidationCategory.CONSISTENCY,
                level=ValidationLevel.STANDARD,
                description="기관명과 카테고리 일치성 검증",
                field_names=["name", "category"],
                validation_function="_validate_name_category_consistency",
                error_message="기관명과 카테고리가 일치하지 않습니다"
            ),
            ValidationRule(
                name="address_phone_consistency",
                category=ValidationCategory.CONSISTENCY,
                level=ValidationLevel.STANDARD,
                description="주소와 전화번호 지역 일치성 검증",
                field_names=["address", "phone"],
                validation_function="_validate_address_phone_consistency",
                error_message="주소와 전화번호 지역이 일치하지 않습니다",
                severity="warning"
            ),
            
            # 정확성 검증 규칙
            ValidationRule(
                name="data_accuracy",
                category=ValidationCategory.ACCURACY,
                level=ValidationLevel.ADVANCED,
                description="AI 기반 데이터 정확성 검증",
                field_names=["name", "category", "phone", "email", "address"],
                validation_function="_validate_data_accuracy",
                error_message="데이터 정확성에 문제가 있습니다",
                severity="warning"
            ),
            
            # 중복 검증 규칙
            ValidationRule(
                name="duplicate_detection",
                category=ValidationCategory.DUPLICATION,
                level=ValidationLevel.STANDARD,
                description="중복 데이터 검증",
                field_names=["name", "phone", "address"],
                validation_function="_validate_duplicates",
                error_message="중복 데이터가 발견되었습니다",
                severity="warning"
            )
        ]
        
        return rules
    
    async def process(self, data: Dict[str, Any]) -> AgentResult:
        """
        데이터 검증 메인 프로세스
        
        Args:
            data: {
                "targets": List[ValidationTarget] 또는 Dict,
                "validation_level": ValidationLevel,
                "categories": List[ValidationCategory] (선택적),
                "fix_issues": bool (자동 수정 여부)
            }
        
        Returns:
            AgentResult: 검증 결과
        """
        try:
            # 입력 데이터 파싱
            targets = self._parse_targets(data.get("targets", []))
            validation_level = ValidationLevel(data.get("validation_level", "standard"))
            categories = [ValidationCategory(cat) for cat in data.get("categories", [])] if data.get("categories") else None
            fix_issues = data.get("fix_issues", False)
            
            results = []
            
            # 병렬 처리를 위한 세마포어
            semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
            
            # 각 대상에 대해 검증 수행
            tasks = []
            for target in targets:
                task = self._validate_with_semaphore(
                    semaphore, target, validation_level, categories, fix_issues
                )
                tasks.append(task)
            
            # 병렬 실행
            validation_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 결과 처리
            valid_count = 0
            total_issues = 0
            
            for i, result in enumerate(validation_results):
                if isinstance(result, Exception):
                    logger.error(f"검증 실패 - {targets[i].name}: {str(result)}")
                    results.append(ValidationResult(
                        target=targets[i],
                        is_valid=False,
                        quality_score=0.0,
                        completeness_score=0.0,
                        issues=[],
                        validation_time=0.0,
                        rules_applied=[]
                    ))
                    self.metrics.error_count += 1
                else:
                    results.append(result)
                    if result.is_valid:
                        valid_count += 1
                        self.metrics.success_count += 1
                    total_issues += len(result.issues)
                
                self.metrics.processed_items += 1
            
            # 전체 결과 분석
            analysis = self._analyze_validation_results(results)
            
            result_data = {
                "validation_results": [asdict(result) for result in results],
                "summary": {
                    "total_targets": len(targets),
                    "valid_targets": valid_count,
                    "validation_rate": valid_count / len(targets) if targets else 0,
                    "total_issues": total_issues,
                    "average_quality_score": sum(r.quality_score for r in results) / len(results) if results else 0
                },
                "analysis": analysis
            }
            
            return AgentResult(
                success=True,
                data=result_data,
                message=f"{valid_count}/{len(targets)}개 데이터 검증 완료, {total_issues}개 문제 발견",
                execution_time=self.metrics.get_execution_time(),
                metadata={
                    "agent_type": "ValidationAgent",
                    "validation_level": validation_level.value,
                    "processing_time": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"검증 프로세스 실패: {str(e)}")
            self.metrics.error_count += 1
            
            return AgentResult(
                success=False,
                data={},
                message=f"검증 실패: {str(e)}",
                execution_time=self.metrics.get_execution_time(),
                metadata={"error": str(e)}
            )
    
    async def _validate_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        target: ValidationTarget,
        validation_level: ValidationLevel,
        categories: Optional[List[ValidationCategory]],
        fix_issues: bool
    ) -> ValidationResult:
        """세마포어를 사용한 데이터 검증"""
        async with semaphore:
            return await self._validate_target(target, validation_level, categories, fix_issues)
    
    async def _validate_target(
        self,
        target: ValidationTarget,
        validation_level: ValidationLevel,
        categories: Optional[List[ValidationCategory]],
        fix_issues: bool
    ) -> ValidationResult:
        """개별 대상 검증"""
        start_time = datetime.now()
        
        try:
            issues = []
            applied_rules = []
            
            # 적용할 규칙 필터링
            applicable_rules = [
                rule for rule in self.validation_rules
                if self._is_rule_applicable(rule, validation_level, categories)
            ]
            
            # 각 규칙 적용
            for rule in applicable_rules:
                try:
                    rule_issues = await self._apply_validation_rule(rule, target)
                    issues.extend(rule_issues)
                    applied_rules.append(rule.name)
                except Exception as e:
                    logger.warning(f"규칙 적용 실패 - {rule.name}: {str(e)}")
            
            # 자동 수정 수행
            if fix_issues:
                target.data = self._auto_fix_issues(target.data, issues)
                # 수정 후 재검증
                for rule in applicable_rules:
                    if rule.category in [ValidationCategory.FORMAT]:  # 형식 오류만 재검증
                        try:
                            recheck_issues = await self._apply_validation_rule(rule, target)
                            # 수정된 이슈들 제거
                            issues = [issue for issue in issues if issue.rule_name != rule.name]
                            issues.extend(recheck_issues)
                        except Exception as e:
                            continue
            
            # 품질 점수 계산
            quality_score = self._calculate_quality_score(target, issues)
            completeness_score = self._calculate_completeness_score(target)
            
            # 전체 검증 통과 여부 결정
            is_valid = self._determine_validity(issues)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ValidationResult(
                target=target,
                is_valid=is_valid,
                quality_score=quality_score,
                completeness_score=completeness_score,
                issues=issues,
                validation_time=execution_time,
                rules_applied=applied_rules
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"대상 검증 실패 - {target.name}: {str(e)}")
            
            return ValidationResult(
                target=target,
                is_valid=False,
                quality_score=0.0,
                completeness_score=0.0,
                issues=[],
                validation_time=execution_time,
                rules_applied=[]
            )
    
    def _is_rule_applicable(
        self,
        rule: ValidationRule,
        validation_level: ValidationLevel,
        categories: Optional[List[ValidationCategory]]
    ) -> bool:
        """규칙 적용 가능 여부 확인"""
        # 검증 수준 확인
        level_order = [ValidationLevel.BASIC, ValidationLevel.STANDARD, ValidationLevel.ADVANCED, ValidationLevel.COMPREHENSIVE]
        if level_order.index(rule.level) > level_order.index(validation_level):
            return False
        
        # 카테고리 필터 확인
        if categories and rule.category not in categories:
            return False
        
        return True
    
    async def _apply_validation_rule(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """검증 규칙 적용"""
        validation_function = getattr(self, rule.validation_function, None)
        if not validation_function:
            logger.warning(f"검증 함수 없음: {rule.validation_function}")
            return []
        
        try:
            return await validation_function(rule, target)
        except Exception as e:
            logger.error(f"검증 규칙 실행 실패 - {rule.name}: {str(e)}")
            return []
    
    # 검증 함수들
    async def _validate_phone_format(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """전화번호 형식 검증"""
        issues = []
        
        for field_name in rule.field_names:
            value = target.data.get(field_name)
            if value and not self.phone_regex.match(str(value)):
                issues.append(ValidationIssue(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    field_name=field_name,
                    current_value=value,
                    suggestion="올바른 전화번호 형식: 02-1234-5678 또는 010-1234-5678"
                ))
        
        return issues
    
    async def _validate_email_format(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """이메일 형식 검증"""
        issues = []
        
        for field_name in rule.field_names:
            value = target.data.get(field_name)
            if value and not self.email_regex.match(str(value)):
                issues.append(ValidationIssue(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    field_name=field_name,
                    current_value=value,
                    suggestion="올바른 이메일 형식: example@domain.com"
                ))
        
        return issues
    
    async def _validate_url_format(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """URL 형식 검증"""
        issues = []
        
        for field_name in rule.field_names:
            value = target.data.get(field_name)
            if value and not self.url_regex.match(str(value)):
                issues.append(ValidationIssue(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    field_name=field_name,
                    current_value=value,
                    suggestion="올바른 URL 형식: http://example.com 또는 https://example.com"
                ))
        
        return issues
    
    async def _validate_required_fields(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """필수 필드 검증"""
        issues = []
        
        for field_name in rule.field_names:
            value = target.data.get(field_name)
            if not value or (isinstance(value, str) and not value.strip()):
                issues.append(ValidationIssue(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    field_name=field_name,
                    current_value=value,
                    suggestion=f"{field_name} 필드는 필수입니다"
                ))
        
        return issues
    
    async def _validate_contact_completeness(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """연락처 완성도 검증"""
        issues = []
        
        contact_fields = ["phone", "mobile", "email", "homepage"]
        available_contacts = sum(1 for field in contact_fields if target.data.get(field))
        
        if available_contacts < 2:  # 최소 2개 연락처 필요
            issues.append(ValidationIssue(
                rule_name=rule.name,
                category=rule.category,
                severity=rule.severity,
                field_name="contact_info",
                current_value=f"{available_contacts}개 연락처",
                suggestion="최소 2개 이상의 연락처 정보가 필요합니다 (전화, 이메일, 홈페이지 등)"
            ))
        
        return issues
    
    async def _validate_name_category_consistency(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """기관명-카테고리 일치성 검증"""
        issues = []
        
        name = target.data.get("name", "")
        category = target.data.get("category", "")
        
        # 카테고리별 키워드 매핑
        category_keywords = {
            "교회": ["교회", "성당", "교단", "선교", "목사", "신부"],
            "학원": ["학원", "교습소", "과외", "교육", "아카데미"],
            "주민센터": ["주민센터", "동사무소", "구청", "시청", "행정"]
        }
        
        if category in category_keywords:
            keywords = category_keywords[category]
            if not any(keyword in name for keyword in keywords):
                issues.append(ValidationIssue(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    field_name="name",
                    current_value=name,
                    suggestion=f"'{category}' 카테고리에 맞는 기관명인지 확인이 필요합니다"
                ))
        
        return issues
    
    async def _validate_address_phone_consistency(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """주소-전화번호 지역 일치성 검증"""
        issues = []
        
        address = target.data.get("address", "")
        phone = target.data.get("phone", "")
        
        if address and phone:
            # 지역번호 추출
            area_code = phone.split("-")[0] if "-" in phone else ""
            
            # 지역번호와 주소 매핑
            area_mappings = {
                "02": ["서울"],
                "031": ["경기", "인천"],
                "032": ["인천"],
                "042": ["대전"],
                "043": ["충북"],
                "044": ["세종"],
                "051": ["부산"],
                "052": ["울산"],
                "053": ["대구"],
                "054": ["경북"],
                "055": ["경남"],
                "061": ["전남"],
                "062": ["광주"],
                "063": ["전북"],
                "064": ["제주"]
            }
            
            if area_code in area_mappings:
                expected_regions = area_mappings[area_code]
                if not any(region in address for region in expected_regions):
                    issues.append(ValidationIssue(
                        rule_name=rule.name,
                        category=rule.category,
                        severity=rule.severity,
                        field_name="phone",
                        current_value=phone,
                        suggestion=f"전화번호 지역번호({area_code})와 주소 지역이 일치하지 않을 수 있습니다"
                    ))
        
        return issues
    
    async def _validate_data_accuracy(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """AI 기반 데이터 정확성 검증"""
        issues = []
        
        try:
            # AI 체인으로 정확성 검증
            chain = LLMChain(
                llm=self.gemini_client.get_llm(),
                prompt=self.accuracy_prompt
            )
            
            contact_info = f"전화: {target.data.get('phone', '없음')}, 이메일: {target.data.get('email', '없음')}"
            
            response = await chain.arun(
                organization_name=target.name,
                category=target.category,
                contact_info=contact_info,
                address=target.data.get("address", "없음")
            )
            
            accuracy_data = json.loads(response.strip())
            accuracy_score = accuracy_data.get("accuracy_score", 0.5)
            
            if accuracy_score < 0.7:  # 70% 미만이면 문제 제기
                concerns = accuracy_data.get("concerns", [])
                issues.append(ValidationIssue(
                    rule_name=rule.name,
                    category=rule.category,
                    severity=rule.severity,
                    field_name="overall",
                    current_value=f"정확성 점수: {accuracy_score}",
                    suggestion=f"데이터 정확성 검토 필요: {', '.join(concerns)}"
                ))
            
        except Exception as e:
            logger.warning(f"AI 정확성 검증 실패: {str(e)}")
        
        return issues
    
    async def _validate_duplicates(self, rule: ValidationRule, target: ValidationTarget) -> List[ValidationIssue]:
        """중복 데이터 검증 (단일 대상에서는 제한적)"""
        issues = []
        
        # 단일 대상 검증에서는 중복 검증이 제한적
        # 실제로는 전체 데이터셋과 비교 필요
        
        name = target.data.get("name", "")
        phone = target.data.get("phone", "")
        
        # 같은 이름과 전화번호가 있는지 체크 (외부 데이터베이스 필요)
        # 여기서는 기본적인 자체 일관성만 체크
        
        return issues
    
    def _calculate_quality_score(self, target: ValidationTarget, issues: List[ValidationIssue]) -> float:
        """품질 점수 계산"""
        base_score = 100.0
        
        # 이슈별 점수 차감
        for issue in issues:
            if issue.severity == "error":
                base_score -= 20
            elif issue.severity == "warning":
                base_score -= 10
            elif issue.severity == "info":
                base_score -= 5
        
        # 데이터 완성도 보너스
        completeness_bonus = self._calculate_completeness_score(target) * 20
        
        final_score = (base_score + completeness_bonus) / 100
        return max(0.0, min(1.0, final_score))
    
    def _calculate_completeness_score(self, target: ValidationTarget) -> float:
        """완성도 점수 계산"""
        total_fields = ["name", "category", "address", "phone", "mobile", "email", "homepage", "fax"]
        completed_fields = sum(1 for field in total_fields if target.data.get(field))
        
        return completed_fields / len(total_fields)
    
    def _determine_validity(self, issues: List[ValidationIssue]) -> bool:
        """전체 검증 통과 여부 결정"""
        error_count = sum(1 for issue in issues if issue.severity == "error")
        return error_count == 0
    
    def _auto_fix_issues(self, data: Dict[str, Any], issues: List[ValidationIssue]) -> Dict[str, Any]:
        """자동 수정 수행"""
        fixed_data = data.copy()
        
        for issue in issues:
            if issue.category == ValidationCategory.FORMAT:
                # 형식 오류 자동 수정
                if issue.field_name in ["phone", "mobile", "fax"]:
                    fixed_data[issue.field_name] = self._fix_phone_format(issue.current_value)
                elif issue.field_name == "email":
                    fixed_data[issue.field_name] = self._fix_email_format(issue.current_value)
                elif issue.field_name == "homepage":
                    fixed_data[issue.field_name] = self._fix_url_format(issue.current_value)
        
        return fixed_data
    
    def _fix_phone_format(self, phone: Any) -> str:
        """전화번호 형식 자동 수정"""
        if not phone:
            return ""
        
        # 숫자만 추출
        digits = re.sub(r'[^\d]', '', str(phone))
        
        # 형식별 정리
        if len(digits) == 11 and digits.startswith('010'):
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:]}"
        elif len(digits) == 10 and digits.startswith('02'):
            return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
        elif len(digits) >= 10:
            return f"{digits[:3]}-{digits[3:7]}-{digits[7:11]}"
        
        return str(phone)  # 수정할 수 없으면 원본 반환
    
    def _fix_email_format(self, email: Any) -> str:
        """이메일 형식 자동 수정"""
        if not email:
            return ""
        
        email_str = str(email).strip()
        
        # 기본적인 수정만 수행
        if "@" in email_str and "." in email_str:
            return email_str.lower()
        
        return email_str
    
    def _fix_url_format(self, url: Any) -> str:
        """URL 형식 자동 수정"""
        if not url:
            return ""
        
        url_str = str(url).strip()
        
        # http/https 접두사 추가
        if not url_str.startswith(('http://', 'https://')):
            if '.' in url_str:
                return f"http://{url_str}"
        
        return url_str
    
    def _parse_targets(self, targets_data: Union[List, Dict]) -> List[ValidationTarget]:
        """검증 대상 데이터 파싱"""
        targets = []
        
        if isinstance(targets_data, dict):
            targets_data = [targets_data]
        
        for i, target_data in enumerate(targets_data):
            if isinstance(target_data, dict):
                target = ValidationTarget(
                    id=target_data.get("id", str(i)),
                    name=target_data.get("name", ""),
                    category=target_data.get("category", ""),
                    data=target_data.get("data", target_data),  # data 필드가 없으면 전체를 data로 사용
                    metadata=target_data.get("metadata", {})
                )
                targets.append(target)
        
        return targets
    
    def _analyze_validation_results(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """검증 결과 분석"""
        if not results:
            return {}
        
        # 카테고리별 이슈 분석
        category_issues = {}
        for result in results:
            for issue in result.issues:
                category = issue.category.value
                if category not in category_issues:
                    category_issues[category] = 0
                category_issues[category] += 1
        
        # 심각도별 이슈 분석
        severity_issues = {}
        for result in results:
            for issue in result.issues:
                severity = issue.severity
                if severity not in severity_issues:
                    severity_issues[severity] = 0
                severity_issues[severity] += 1
        
        # 가장 문제가 많은 필드
        field_issues = {}
        for result in results:
            for issue in result.issues:
                field = issue.field_name
                if field not in field_issues:
                    field_issues[field] = 0
                field_issues[field] += 1
        
        # 상위 문제 필드 (최대 5개)
        top_problem_fields = sorted(field_issues.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            "quality_distribution": {
                "excellent": sum(1 for r in results if r.quality_score >= 0.9),
                "good": sum(1 for r in results if 0.7 <= r.quality_score < 0.9),
                "fair": sum(1 for r in results if 0.5 <= r.quality_score < 0.7),
                "poor": sum(1 for r in results if r.quality_score < 0.5)
            },
            "category_issues": category_issues,
            "severity_distribution": severity_issues,
            "top_problem_fields": top_problem_fields,
            "average_completeness": sum(r.completeness_score for r in results) / len(results),
            "validation_recommendations": self._generate_recommendations(results)
        }
    
    def _generate_recommendations(self, results: List[ValidationResult]) -> List[str]:
        """검증 결과 기반 권장사항 생성"""
        recommendations = []
        
        # 가장 많은 이슈 카테고리 파악
        category_counts = {}
        for result in results:
            for issue in result.issues:
                category = issue.category.value
                category_counts[category] = category_counts.get(category, 0) + 1
        
        if category_counts:
            top_category = max(category_counts.items(), key=lambda x: x[1])
            recommendations.append(f"{top_category[0]} 관련 문제가 {top_category[1]}건 발견되었습니다. 우선적으로 해결하세요.")
        
        # 품질 점수 기반 권장사항
        low_quality_count = sum(1 for r in results if r.quality_score < 0.7)
        if low_quality_count > len(results) * 0.3:  # 30% 이상이 낮은 품질
            recommendations.append("전체적인 데이터 품질이 낮습니다. 데이터 수집 프로세스를 재검토하세요.")
        
        # 완성도 기반 권장사항
        avg_completeness = sum(r.completeness_score for r in results) / len(results)
        if avg_completeness < 0.6:
            recommendations.append("데이터 완성도가 낮습니다. 추가 정보 수집이 필요합니다.")
        
        return recommendations 