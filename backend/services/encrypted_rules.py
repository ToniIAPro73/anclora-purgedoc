import os
import json
import base64
import logging
from typing import Dict, Any, Tuple, Optional, List
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from backend.services.rules import CustomRuleset, CustomRule, validate_rule_pattern

logger = logging.getLogger(__name__)

# Format definition
APRULES_FORMAT_NAME = "anclora-purgedoc-ruleset"
APRULES_FORMAT_VERSION = 1
SUPPORTED_CIPHER = "AES-256-GCM"
SUPPORTED_KDF = "Argon2id"

# Standard Cryptographic Defaults
DEFAULT_MEMORY_COST_KIB = 65536  # 64 MiB
DEFAULT_TIME_COST = 3            # 3 iterations
DEFAULT_PARALLELISM = 1          # 1 lane
SALT_LENGTH_BYTES = 16
NONCE_LENGTH_BYTES = 12
KEY_LENGTH_BYTES = 32

# Anti-DoS Strict Envelope Validation Limits
MIN_MEMORY_COST_KIB = 8192        # 8 MiB
MAX_MEMORY_COST_KIB = 262144      # 256 MiB
MIN_TIME_COST = 1
MAX_TIME_COST = 10
MIN_PARALLELISM = 1
MAX_PARALLELISM = 4
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MiB
MAX_PLAINTEXT_BYTES = 5 * 1024 * 1024   # 5 MiB
MAX_RULES_COUNT = 500

# Immutable built-in profile IDs that can NEVER be overwritten
IMMUTABLE_BUILTIN_RULESETS = {"rrhh", "legal", "soporte"}

class EncryptedRulesetError(Exception):
    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(detail)

def build_canonical_aad(format_name: str, format_ver: int, cipher: str, kdf: str, salt_b64: str, nonce_b64: str, mem_kib: int, time_cost: int, parallelism: int) -> bytes:
    """
    Constructs deterministic Additional Authenticated Data (AAD) for AES-GCM.
    Ensures that format, algorithm, KDF, salt, nonce, and KDF parameters
    CANNOT be tampered with in the envelope without causing an authentication tag failure.
    """
    aad_dict = {
        "format": format_name,
        "format_version": format_ver,
        "cipher": cipher,
        "kdf": kdf,
        "memory_cost_kib": mem_kib,
        "nonce": nonce_b64,
        "parallelism": parallelism,
        "salt": salt_b64,
        "time_cost": time_cost
    }
    return json.dumps(aad_dict, sort_keys=True, separators=(',', ':')).encode('utf-8')

def derive_key_argon2id(password_bytes: bytes, salt: bytes, length: int, mem_kib: int, time_cost: int, parallelism: int) -> bytes:
    """Derives a cryptographic key using Argon2id with strict parameters."""
    kdf = Argon2id(
        salt=salt,
        length=length,
        iterations=time_cost,
        lanes=parallelism,
        memory_cost=mem_kib
    )
    return kdf.derive(password_bytes)

def export_encrypted_ruleset(ruleset: CustomRuleset, password: str, ruleset_name: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Exports a CustomRuleset into the canonical encrypted .aprules envelope.
    All functional rule metadata, regexes, and names are encrypted inside the AES-GCM ciphertext.
    Zero plaintext rules, regexes or names exist in the outer envelope.
    """
    if not password:
        raise EncryptedRulesetError("INVALID_PASSWORD", "La contraseña de cifrado no puede estar vacía.")

    password_bytes = password.encode('utf-8')
    salt = os.urandom(SALT_LENGTH_BYTES)
    nonce = os.urandom(NONCE_LENGTH_BYTES)
    salt_b64 = base64.b64encode(salt).decode('ascii')
    nonce_b64 = base64.b64encode(nonce).decode('ascii')

    # Construct Inner Plaintext Payload
    canonical_hash = ruleset.calculate_hash()
    payload_dict = {
        "ruleset_id": ruleset.ruleset_id,
        "name": ruleset_name or ruleset.ruleset_id,
        "description": description or "",
        "version": ruleset.version,
        "canonical_hash": canonical_hash,
        "min_purgedoc_version": "1.0.0",
        "rules": [r.model_dump() for r in ruleset.rules]
    }
    plaintext_bytes = json.dumps(payload_dict, sort_keys=True, ensure_ascii=False).encode('utf-8')

    # Derive AES-256 Key
    key = derive_key_argon2id(
        password_bytes=password_bytes,
        salt=salt,
        length=KEY_LENGTH_BYTES,
        mem_kib=DEFAULT_MEMORY_COST_KIB,
        time_cost=DEFAULT_TIME_COST,
        parallelism=DEFAULT_PARALLELISM
    )

    # Compute AAD
    aad = build_canonical_aad(
        format_name=APRULES_FORMAT_NAME,
        format_ver=APRULES_FORMAT_VERSION,
        cipher=SUPPORTED_CIPHER,
        kdf=SUPPORTED_KDF,
        salt_b64=salt_b64,
        nonce_b64=nonce_b64,
        mem_kib=DEFAULT_MEMORY_COST_KIB,
        time_cost=DEFAULT_TIME_COST,
        parallelism=DEFAULT_PARALLELISM
    )

    # Encrypt with AES-GCM (ciphertext includes standard 16-byte authentication tag)
    aesgcm = AESGCM(key)
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext_bytes, aad)
    ciphertext_b64 = base64.b64encode(ciphertext_with_tag).decode('ascii')

    # Construct Outer Envelope (Zero sensitive plaintext)
    envelope = {
        "format": APRULES_FORMAT_NAME,
        "format_version": APRULES_FORMAT_VERSION,
        "crypto": {
            "cipher": SUPPORTED_CIPHER,
            "kdf": SUPPORTED_KDF,
            "salt": salt_b64,
            "nonce": nonce_b64,
            "memory_cost_kib": DEFAULT_MEMORY_COST_KIB,
            "time_cost": DEFAULT_TIME_COST,
            "parallelism": DEFAULT_PARALLELISM
        },
        "ciphertext": ciphertext_b64
    }
    return envelope

def preview_encrypted_ruleset(envelope: Dict[str, Any], password: str, current_rules: Optional[List[CustomRule]] = None) -> Dict[str, Any]:
    """
    Validates envelope, enforces anti-DoS limits, authenticates and decrypts the payload,
    re-validates all rules with google-re2, checks canonical hash integrity, and detects conflicts.
    Does NOT commit the import (safe read-only transactional preview).
    """
    if not isinstance(envelope, dict):
        raise EncryptedRulesetError("INVALID_APRULES_FORMAT", "El archivo proporcionado no es un JSON válido o tiene un formato corrupto.")

    if envelope.get("format") != APRULES_FORMAT_NAME:
        raise EncryptedRulesetError("INVALID_APRULES_FORMAT", f"Formato no soportado. Se esperaba '{APRULES_FORMAT_NAME}'.")

    if envelope.get("format_version") != APRULES_FORMAT_VERSION:
        raise EncryptedRulesetError("UNSUPPORTED_APRULES_VERSION", f"Versión de formato '{envelope.get('format_version')}' no soportada por esta versión de Purgedoc.")

    crypto_meta = envelope.get("crypto", {})
    if crypto_meta.get("cipher") != SUPPORTED_CIPHER or crypto_meta.get("kdf") != SUPPORTED_KDF:
        raise EncryptedRulesetError("UNSUPPORTED_CRYPTO_PARAMETERS", "Algoritmo de cifrado o KDF no soportado.")

    # Validate Anti-DoS KDF Parameters BEFORE executing Argon2
    mem_kib = crypto_meta.get("memory_cost_kib", 0)
    time_cost = crypto_meta.get("time_cost", 0)
    parallelism = crypto_meta.get("parallelism", 0)
    salt_b64 = crypto_meta.get("salt", "")
    nonce_b64 = crypto_meta.get("nonce", "")
    ciphertext_b64 = envelope.get("ciphertext", "")

    if not (MIN_MEMORY_COST_KIB <= mem_kib <= MAX_MEMORY_COST_KIB):
        raise EncryptedRulesetError("UNSUPPORTED_CRYPTO_PARAMETERS", f"memory_cost_kib ({mem_kib}) fuera de límites permitidos.")
    if not (MIN_TIME_COST <= time_cost <= MAX_TIME_COST):
        raise EncryptedRulesetError("UNSUPPORTED_CRYPTO_PARAMETERS", f"time_cost ({time_cost}) fuera de límites permitidos.")
    if not (MIN_PARALLELISM <= parallelism <= MAX_PARALLELISM):
        raise EncryptedRulesetError("UNSUPPORTED_CRYPTO_PARAMETERS", f"parallelism ({parallelism}) fuera de límites permitidos.")

    try:
        salt = base64.b64decode(salt_b64)
        nonce = base64.b64decode(nonce_b64)
        ciphertext_with_tag = base64.b64decode(ciphertext_b64)
    except Exception:
        raise EncryptedRulesetError("INVALID_APRULES_FORMAT", "Codificación Base64 inválida en los parámetros criptográficos o ciphertext.")

    if len(salt) != SALT_LENGTH_BYTES:
        raise EncryptedRulesetError("UNSUPPORTED_CRYPTO_PARAMETERS", f"Longitud de salt inválida ({len(salt)} bytes).")
    if len(nonce) != NONCE_LENGTH_BYTES:
        raise EncryptedRulesetError("UNSUPPORTED_CRYPTO_PARAMETERS", f"Longitud de nonce inválida ({len(nonce)} bytes).")
    if len(ciphertext_with_tag) > MAX_PLAINTEXT_BYTES + 1024:
        raise EncryptedRulesetError("APRULES_FILE_TOO_LARGE", "El tamaño del contenido cifrado excede el límite máximo permitido.")

    # Reconstruct AAD
    aad = build_canonical_aad(
        format_name=APRULES_FORMAT_NAME,
        format_ver=APRULES_FORMAT_VERSION,
        cipher=SUPPORTED_CIPHER,
        kdf=SUPPORTED_KDF,
        salt_b64=salt_b64,
        nonce_b64=nonce_b64,
        mem_kib=mem_kib,
        time_cost=time_cost,
        parallelism=parallelism
    )

    # Derive key and attempt authenticated decryption
    try:
        key = derive_key_argon2id(
            password_bytes=password.encode('utf-8'),
            salt=salt,
            length=KEY_LENGTH_BYTES,
            mem_kib=mem_kib,
            time_cost=time_cost,
            parallelism=parallelism
        )
        aesgcm = AESGCM(key)
        plaintext_bytes = aesgcm.decrypt(nonce, ciphertext_with_tag, aad)
    except Exception as e:
        logger.warning("Decryption/Authentication failed for encrypted ruleset")
        raise EncryptedRulesetError("ENCRYPTED_RULESET_AUTH_FAILED", "Autenticación fallida: contraseña incorrecta o archivo manipulado.")

    if len(plaintext_bytes) > MAX_PLAINTEXT_BYTES:
        raise EncryptedRulesetError("APRULES_FILE_TOO_LARGE", "El contenido descifrado excede el límite máximo de memoria.")

    try:
        payload = json.loads(plaintext_bytes.decode('utf-8'))
    except Exception:
        raise EncryptedRulesetError("INVALID_RULESET_SCHEMA", "El contenido descifrado no contiene una estructura JSON válida.")

    # Validate Schema of Decrypted Content
    imported_rules_data = payload.get("rules", [])
    if not isinstance(imported_rules_data, list):
        raise EncryptedRulesetError("INVALID_RULESET_SCHEMA", "Estructura de reglas inválida en el archivo.")
    if len(imported_rules_data) > MAX_RULES_COUNT:
        raise EncryptedRulesetError("INVALID_RULESET_SCHEMA", f"El número de reglas ({len(imported_rules_data)}) excede el límite máximo ({MAX_RULES_COUNT}).")

    rules_obj_list = []
    for r_dict in imported_rules_data:
        try:
            r_obj = CustomRule(**r_dict)
            # Re-validate with google-re2 against ReDoS
            v_res = validate_rule_pattern(r_obj.pattern, r_obj.case_sensitive)
            if not v_res.valid:
                raise EncryptedRulesetError("INVALID_RULE_PATTERN", f"La regla '{r_obj.name}' contiene un patrón regex inválido o inseguro: {v_res.error}")
            rules_obj_list.append(r_obj)
        except Exception as err:
            if isinstance(err, EncryptedRulesetError):
                raise err
            raise EncryptedRulesetError("INVALID_RULESET_SCHEMA", f"Error validando esquema de regla: {err}")

    imported_ruleset = CustomRuleset(
        ruleset_id=payload.get("ruleset_id", "imported_ruleset"),
        version=payload.get("version", "1.0.0"),
        rules=rules_obj_list
    )

    # Verify canonical hash integrity
    computed_canonical_hash = imported_ruleset.calculate_hash()
    stored_canonical_hash = payload.get("canonical_hash")
    if stored_canonical_hash and stored_canonical_hash != computed_canonical_hash:
        raise EncryptedRulesetError("ENCRYPTED_RULESET_AUTH_FAILED", "Discrepancia en el hash canónico del ruleset descifrado.")

    # Check for conflicts against existing rules
    current_rule_ids = {r.id for r in (current_rules or [])}
    current_rule_names = {r.name for r in (current_rules or [])}
    conflicts = []

    for r in imported_ruleset.rules:
        # Check against immutable built-in rulesets
        if r.id.lower() in IMMUTABLE_BUILTIN_RULESETS or r.name.lower() in IMMUTABLE_BUILTIN_RULESETS:
            raise EncryptedRulesetError("BUILTIN_RULESET_CONFLICT", f"Conflicto prohibido: no se permite importar una regla que coincida con el perfil protegido '{r.name}'.")

        has_id_conflict = r.id in current_rule_ids
        has_name_conflict = r.name in current_rule_names

        if has_id_conflict or has_name_conflict:
            conflicts.append({
                "rule_id": r.id,
                "name": r.name,
                "type": "both" if (has_id_conflict and has_name_conflict) else ("id" if has_id_conflict else "name")
            })

    affected_profiles = sorted(list({p for r in imported_ruleset.rules for p in r.profiles}))

    return {
        "ruleset_id": imported_ruleset.ruleset_id,
        "name": payload.get("name", imported_ruleset.ruleset_id),
        "description": payload.get("description", ""),
        "version": imported_ruleset.version,
        "canonical_hash": computed_canonical_hash,
        "rules_count": len(imported_ruleset.rules),
        "affected_profiles": affected_profiles,
        "conflicts": conflicts,
        "rules": [r.model_dump() for r in imported_ruleset.rules]
    }
