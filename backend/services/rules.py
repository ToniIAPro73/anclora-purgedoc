import re
import time
import hashlib
import json
import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Check if google_re2 is available
try:
    import google_re2 as re2
    HAS_RE2 = True
except ImportError:
    try:
        import re2
        HAS_RE2 = True
    except ImportError:
        HAS_RE2 = False

# Maximum pattern length to avoid resource exhaustion
MAX_PATTERN_LENGTH = 1000
# Maximum test bench text length
MAX_TEST_TEXT_LENGTH = 10000
# Execution timeout in seconds for regex testing
REGEX_TIMEOUT_SECONDS = 1.0

# Dangerous or prone to catastrophic backtracking constructs in PCRE
DANGEROUS_PCRE_PATTERNS = [
    r'\((?:[a-zA-Z0-9\.\*\+\?]+\+)\)\+',     # (a+)+
    r'\((?:[a-zA-Z0-9\.\*\+\?]+\*)\)\*',     # (a*)*
    r'\((?:[a-zA-Z0-9\.\*\+\?]+\*)\)\+',     # (a*)+
    r'\((?:[a-zA-Z0-9\.\*\+\?]+\+)\)\*',     # (a+)*
    r'\([a-zA-Z0-9\|]+\)\*\{',               # (a|aa)*{
]

class CustomRule(BaseModel):
    id: str = Field(default_factory=lambda: f"rule_{uuid.uuid4().hex[:8]}")
    name: str
    description: Optional[str] = ""
    entity_type: str = "CUSTOM_SENSITIVE"
    pattern: str
    case_sensitive: bool = False
    confidence: float = Field(default=0.95, ge=0.0, le=1.0)
    priority: int = Field(default=10, ge=1, le=100) # Higher = checked first
    profiles: List[str] = Field(default_factory=lambda: ["rrhh", "legal", "soporte"])
    enabled: bool = True
    example: Optional[str] = ""
    created_at: Optional[float] = Field(default_factory=time.time)
    updated_at: Optional[float] = Field(default_factory=time.time)

class CustomRuleset(BaseModel):
    ruleset_id: str = "default_custom_ruleset"
    version: str = "1.0.0"
    rules: List[CustomRule] = Field(default_factory=list)

    def calculate_hash(self) -> str:
        """Deterministic SHA-256 hash of active rules in the ruleset"""
        active_rules = sorted(
            [r for r in self.rules if r.enabled],
            key=lambda r: (r.id, r.pattern, r.entity_type)
        )
        content_repr = json.dumps([
            {
                "id": r.id,
                "pattern": r.pattern,
                "entity_type": r.entity_type,
                "case_sensitive": r.case_sensitive,
                "priority": r.priority,
                "profiles": sorted(r.profiles)
            }
            for r in active_rules
        ], sort_keys=True)
        return f"sha256:{hashlib.sha256(content_repr.encode('utf-8')).hexdigest()}"

class RuleValidationResult(BaseModel):
    valid: bool
    error: Optional[str] = None
    is_safe: bool = True
    engine: str = "re2" if HAS_RE2 else "re_safe"

class RuleTestMatch(BaseModel):
    match_text: str
    start: int
    end: int
    entity_type: str
    rule_name: str

class RuleTestResponse(BaseModel):
    matches: List[RuleTestMatch]
    count: int
    execution_time_ms: float
    timed_out: bool = False
    error: Optional[str] = None

class RegexValidator:
    @staticmethod
    def validate_pattern(pattern: str, case_sensitive: bool = False) -> RuleValidationResult:
        if not pattern or not pattern.strip():
            return RuleValidationResult(valid=False, error="La expresión regular no puede estar vacía.", is_safe=False)

        if len(pattern) > MAX_PATTERN_LENGTH:
            return RuleValidationResult(
                valid=False,
                error=f"La longitud de la expresión ({len(pattern)}) excede el límite permitido ({MAX_PATTERN_LENGTH}).",
                is_safe=False
            )

        # Check for obvious catastrophic backtracking patterns
        for dp in DANGEROUS_PCRE_PATTERNS:
            if re.search(dp, pattern):
                return RuleValidationResult(
                    valid=False,
                    error="Patrón rechazado: detectada estructura susceptible a Catastrophic Backtracking (ReDoS).",
                    is_safe=False
                )

        # Validate with RE2 if available (guarantees linear time matching, immune to ReDoS)
        if HAS_RE2:
            try:
                options = re2.Options()
                options.case_sensitive = case_sensitive
                _ = re2.compile(pattern, options=options)
                return RuleValidationResult(valid=True, error=None, is_safe=True, engine="google-re2")
            except Exception as e:
                # If RE2 rejects it, test Python's standard re with caution
                return RuleValidationResult(valid=False, error=f"Sintaxis inválida para motor seguro: {str(e)}", is_safe=False)
        else:
            # Fallback to standard re compilation check
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                _ = re.compile(pattern, flags)
                return RuleValidationResult(valid=True, error=None, is_safe=True, engine="python-re")
            except Exception as e:
                return RuleValidationResult(valid=False, error=f"Sintaxis inválida: {str(e)}", is_safe=False)

    @staticmethod
    def test_rule(rule: CustomRule, test_text: str) -> RuleTestResponse:
        t0 = time.time()
        if len(test_text) > MAX_TEST_TEXT_LENGTH:
            return RuleTestResponse(
                matches=[],
                count=0,
                execution_time_ms=0.0,
                error=f"El texto de prueba excede los {MAX_TEST_TEXT_LENGTH} caracteres permitidos."
            )

        val_res = RegexValidator.validate_pattern(rule.pattern, rule.case_sensitive)
        if not val_res.valid:
            return RuleTestResponse(
                matches=[],
                count=0,
                execution_time_ms=0.0,
                error=val_res.error
            )

        matches_found = []
        timed_out = False

        if HAS_RE2:
            try:
                options = re2.Options()
                options.case_sensitive = rule.case_sensitive
                compiled = re2.compile(rule.pattern, options=options)
                for m in compiled.finditer(test_text):
                    matches_found.append(RuleTestMatch(
                        match_text=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        entity_type=rule.entity_type,
                        rule_name=rule.name
                    ))
            except Exception as ex:
                return RuleTestResponse(matches=[], count=0, execution_time_ms=0.0, error=str(ex))
        else:
            flags = 0 if rule.case_sensitive else re.IGNORECASE
            try:
                compiled = re.compile(rule.pattern, flags)
                # Safeguarded iteration with time limit
                for m in compiled.finditer(test_text):
                    if (time.time() - t0) > REGEX_TIMEOUT_SECONDS:
                        timed_out = True
                        break
                    matches_found.append(RuleTestMatch(
                        match_text=m.group(0),
                        start=m.start(),
                        end=m.end(),
                        entity_type=rule.entity_type,
                        rule_name=rule.name
                    ))
            except Exception as ex:
                return RuleTestResponse(matches=[], count=0, execution_time_ms=0.0, error=str(ex))

        elapsed_ms = (time.time() - t0) * 1000.0
        return RuleTestResponse(
            matches=matches_found,
            count=len(matches_found),
            execution_time_ms=round(elapsed_ms, 2),
            timed_out=timed_out
        )

regex_validator = RegexValidator()
