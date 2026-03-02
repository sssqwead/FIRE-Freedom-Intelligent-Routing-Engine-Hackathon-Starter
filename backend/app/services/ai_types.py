from dataclasses import dataclass

@dataclass
class AIRulesResult:
    language: str
    type: str
    sentiment: str
    priority: int
    summary: str
    recommendation: str
    confidence: int
    reason: str