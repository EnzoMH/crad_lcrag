"""
🤖 AI Agent System Package

Langchain 기반 AI 에이전트 시스템
- 모듈화된 에이전트 아키텍처
- GoogleGenerativeAI 통합
- 멀티 API 키 지원
- GCP 최적화 지원

Author: MyoengHo Shin
Version: 2.3.0
"""

from .core.agent_system import AIAgentSystem
from .core.agent_base import BaseAgent
from .core.coordinator import AgentCoordinator

__version__ = "2.3.0"
__author__ = "MyoengHo Shin"

__all__ = [
    "AIAgentSystem",
    "BaseAgent", 
    "AgentCoordinator"
] 