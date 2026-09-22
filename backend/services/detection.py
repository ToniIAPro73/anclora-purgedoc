import os
import re
import yaml
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
import spacy
from backend.models import MatchItem, BoundingBox, hash_text

logger = logging.getLogger(__name__)
CONFIG_DIR = Path(__file__).parent.parent / "config" / "profiles"

class DetectionEngine:
    def __init__(self):
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self.nlp_models: Dict[str, Any] = {}
        self._load_profiles()
        self._load_spacy_models()

    def _load_profiles(self):
        for profile_file in CONFIG_DIR.glob("*.yaml"):
            try:
                with open(profile_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    self.profiles[data["id"]] = data
            except Exception as e:
                logger.error(f"Error loading profile {profile_file}: {e}")

    def _load_spacy_models(self):
        # Load local spaCy models without internet dependency
        try:
            self.nlp_models["es"] = spacy.load("es_core_news_sm")
            logger.info("Loaded spaCy es_core_news_sm")
        except Exception as e:
            logger.warning(f"Could not load es_core_news_sm: {e}")
        try:
            self.nlp_models["en"] = spacy.load("en_core_web_sm")
            logger.info("Loaded spaCy en_core_web_sm")
        except Exception as e:
            logger.warning(f"Could not load en_core_web_sm: {e}")

    def detect_language(self, text_sample: str) -> str:
        """Lightweight local heuristic for Spanish vs English"""
        sample = text_sample.lower()
        es_keywords = ["de", "la", "el", "en", "y", "a", "los", "se", "del", "las", "por", "un", "para", "con", "no", "una", "su", "al", "lo", "como", "más", "contrato", "cláusula", "trabajador", "empresa", "código", "dirección"]
        en_keywords = ["the", "of", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for", "on", "are", "as", "with", "his", "they", "at", "be", "this", "from", "contract", "employee", "company"]
        
        words = re.findall(r'\b\w+\b', sample)
        if not words:
            return "es"
        es_score = sum(1 for w in words if w in es_keywords)
        en_score = sum(1 for w in words if w in en_keywords)
        return "es" if es_score >= en_score else "en"

    def analyze_document_content(
        self,
        doc_id: str,
        profile_id: str,
        pages_content: List[Dict[str, Any]] # [{"page_num": 1, "text": str, "words_or_rects": [...]}]
    ) -> List[MatchItem]:
        profile = self.profiles.get(profile_id, self.profiles.get("rrhh"))
        profile_version = profile.get("version", "1.0.0")
        
        # Combine sample text to detect language
        all_text_sample = " ".join([p.get("text", "") for p in pages_content[:3]])
        lang = self.detect_language(all_text_sample)
        nlp = self.nlp_models.get(lang, self.nlp_models.get("es"))

        raw_matches: List[MatchItem] = []

        for page in pages_content:
            p_num = page["page_num"]
            p_text = page.get("text", "")
            page_rects = page.get("rects", []) # PyMuPDF rects or bounding boxes
            page_w = page.get("width", 595.0)
            page_h = page.get("height", 842.0)

            # 1. Regex Rules
            for rule in profile.get("regex_rules", []):
                pattern = rule["pattern"]
                ent_type = rule["entity_type"]
                conf = rule.get("confidence", 0.90)
                rule_id = rule["id"]
                flags = 0 if rule.get("case_sensitive", False) else re.IGNORECASE

                try:
                    for m in re.finditer(pattern, p_text, flags):
                        raw_val = m.group(0).strip()
                        if len(raw_val) < 2:
                            continue
                        
                        bbox = self._find_bbox_for_text(raw_val, page_rects, page_w, page_h)
                        preview = self._make_preview(raw_val, ent_type)
                        raw_matches.append(MatchItem(
                            document_id=doc_id,
                            entity_type=ent_type,
                            source=["regex"],
                            confidence=conf,
                            original_text_hash=hash_text(raw_val),
                            text_preview=preview,
                            raw_text=raw_val,
                            page=p_num,
                            bbox=bbox,
                            status="pending",
                            rule_id=rule_id,
                            profile_id=profile_id,
                            profile_version=profile_version
                        ))
                except Exception as ex:
                    logger.warning(f"Error running regex {rule_id}: {ex}")

            # 2. Local spaCy NER
            if profile.get("ner", {}).get("enabled", True) and nlp:
                try:
                    doc = nlp(p_text)
                    allowed_entities = profile.get("ner", {}).get("entities", ["PERSON", "ORG", "LOC"])
                    for ent in doc.ents:
                        if ent.label_ in allowed_entities:
                            raw_val = ent.text.strip()
                            if len(raw_val) < 3 or re.match(r'^\d+$', raw_val):
                                continue
                            
                            # Normalise entity label to internal categories
                            norm_cat = "PERSON" if ent.label_ == "PERSON" else ("ADDRESS" if ent.label_ in ["LOC", "GPE"] else "OTHER_SENSITIVE")
                            bbox = self._find_bbox_for_text(raw_val, page_rects, page_w, page_h)
                            preview = self._make_preview(raw_val, norm_cat)
                            raw_matches.append(MatchItem(
                                document_id=doc_id,
                                entity_type=norm_cat,
                                source=["ner"],
                                confidence=0.82,
                                original_text_hash=hash_text(raw_val),
                                text_preview=preview,
                                raw_text=raw_val,
                                page=p_num,
                                bbox=bbox,
                                status="pending",
                                rule_id=f"ner.{lang}.{ent.label_.lower()}",
                                profile_id=profile_id,
                                profile_version=profile_version
                            ))
                except Exception as ex:
                    logger.warning(f"Error in NER detection: {ex}")

        # 3. Deduplication and consolidation
        deduplicated = self._deduplicate_matches(raw_matches)
        return deduplicated

    def _make_preview(self, text: str, entity_type: str) -> str:
        """Create privacy-conscious masked preview for review screen, e.g. '12***78Z'"""
        if len(text) <= 4:
            return text[0] + "***" + text[-1]
        elif entity_type in ["EMAIL", "API_TOKEN", "DNI_NIE_NIF", "IBAN", "PHONE"]:
            prefix = text[:3]
            suffix = text[-3:]
            return f"{prefix}...{suffix}"
        else:
            return text[:15] + ("..." if len(text) > 15 else "")

    def _find_bbox_for_text(self, text: str, page_rects: List[Dict[str, Any]], page_w: float, page_h: float) -> Optional[BoundingBox]:
        """Finds matching rectangle from PyMuPDF word rects list"""
        # Exact or partial match search across page words
        clean_target = "".join(text.split()).lower()
        if not clean_target or not page_rects:
            return None
            
        for item in page_rects:
            item_text = "".join(item.get("text", "").split()).lower()
            if clean_target in item_text or item_text in clean_target:
                b = item["bbox"]
                return BoundingBox(
                    x0=float(b[0]),
                    y0=float(b[1]),
                    x1=float(b[2]),
                    y1=float(b[3]),
                    page_width=page_w,
                    page_height=page_h
                )
        return None

    def _deduplicate_matches(self, matches: List[MatchItem]) -> List[MatchItem]:
        """Consolidates overlapping matches and merges sources (e.g. regex + ner -> hybrid)"""
        consolidated: Dict[str, MatchItem] = {}

        for m in matches:
            # Key based on page and raw text
            key = f"{m.page}_{m.raw_text.strip().lower()}"
            if key in consolidated:
                existing = consolidated[key]
                # Merge sources
                all_sources = list(set(existing.source + m.source))
                existing.source = all_sources
                # Prioritize regex confidence and more specific entity types
                if m.confidence > existing.confidence:
                    existing.confidence = m.confidence
                    existing.entity_type = m.entity_type
                    existing.rule_id = m.rule_id
                if not existing.bbox and m.bbox:
                    existing.bbox = m.bbox
            else:
                consolidated[key] = m

        return list(consolidated.values())

detection_engine = DetectionEngine()
