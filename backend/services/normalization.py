import unicodedata
import re
from typing import List, Set

# Non-sensitive common keywords that should never be treated as standalone sensitive targets
STOPWORDS = {
    "tech", "sol", "solutions", "sl", "sa", "empresa", "consulting", "spain", "madrid"
}

def normalize_text(text: str) -> str:
    """
    Normalizes text for adversarial string searching:
    - NFKC Unicode normalization
    - Strip accents/diacritics
    - Lowercase
    - Normalize internal whitespace
    """
    if not text:
        return ""
    nfkc = unicodedata.normalize("NFKC", text)
    decomposed = unicodedata.normalize("NFD", nfkc)
    stripped_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = stripped_accents.lower().strip()
    normalized_space = re.sub(r'\s+', ' ', lowered)
    return normalized_space

def generate_adversarial_variants(text: str) -> Set[str]:
    """
    Generates potential adversarial string variants that an attacker might search for:
    - Original raw
    - Normalized lowercase
    - Whitespace collapsed
    - Compact (no spaces/hyphens/dots/slashes)
    - DNI/NIE formatted variants (with or without hyphen/space)
    - IBAN formatted variants (with or without 4-digit grouping)
    - Phone variants (with or without +34 prefix, spaces, dashes)
    """
    variants = set()
    raw = text.strip()
    if not raw:
        return variants

    variants.add(raw)
    norm = normalize_text(raw)
    variants.add(norm)

    compact = re.sub(r'[\s\-_.:,/]+', '', norm)

    # DNI/NIE specific variants
    dni_match = re.search(r'([XYZxyz]?\d{7,8}[A-Za-z])', compact)
    if dni_match:
        val = dni_match.group(1).upper()
        variants.add(val)
        variants.add(f"{val[:-1]}-{val[-1]}")
        variants.add(f"{val[:-1]} {val[-1]}")

    # IBAN variants: Only generate full 24-char variants, never standalone repeating zeroes!
    if norm.startswith("es") and len(compact) >= 20:
        variants.add(compact.upper())
        chunks = [compact[i:i+4].upper() for i in range(0, len(compact), 4)]
        variants.add(" ".join(chunks))

    # Phone variants
    digits = re.sub(r'\D', '', raw)
    if len(digits) >= 9 and ("+" in raw or "6" in raw or "7" in raw or "9" in raw):
        last9 = digits[-9:]
        variants.add(last9)
        variants.add(f"+34 {last9}")
        variants.add(f"+34{last9}")
        variants.add(f"{last9[:3]} {last9[3:6]} {last9[6:]}")
        variants.add(f"{last9[:3]}-{last9[3:6]}-{last9[6:]}")

    # Filter out empty or trivially short tokens and generic stopwords
    filtered = set()
    for v in variants:
        v_clean = v.strip().lower()
        if len(v.strip()) >= 4 and v_clean not in STOPWORDS:
            # Do not allow variants consisting solely of zeros (e.g. '000000000' from dummy IBAN)
            if re.match(r'^0+$', v.strip()):
                continue
            filtered.add(v)

    return filtered
