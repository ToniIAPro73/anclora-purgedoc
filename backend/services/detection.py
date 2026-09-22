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
        pages_content: List[Dict[str, Any]]
    ) -> List[MatchItem]:
        profile = self.profiles.get(profile_id, self.profiles.get("rrhh"))
        profile_version = profile.get("version", "1.0.0")
        
        all_text_sample = " ".join([p.get("text", "") for p in pages_content[:3]])
        lang = self.detect_language(all_text_sample)
        nlp = self.nlp_models.get(lang, self.nlp_models.get("es"))

        raw_matches: List[MatchItem] = []

        for page in pages_content:
            p_num = page["page_num"]
            p_text = page.get("text", "")
            page_rects = page.get("rects", [])
            page_w = page.get("width", 595.0)
            page_h = page.get("height", 842.0)
            is_ocr = page.get("is_ocr", False)

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
                        
                        bboxes = self._find_all_bboxes_for_text(raw_val, page_rects, page_w, page_h)
                        preview = self._make_preview(raw_val, ent_type)
                        source_tag = ["ocr", "regex"] if is_ocr else ["regex"]

                        if bboxes:
                            for b in bboxes:
                                raw_matches.append(MatchItem(
                                    document_id=doc_id,
                                    entity_type=ent_type,
                                    source=source_tag,
                                    confidence=conf,
                                    original_text_hash=hash_text(raw_val),
                                    text_preview=preview,
                                    raw_text=raw_val,
                                    page=p_num,
                                    bbox=b,
                                    status="pending",
                                    rule_id=rule_id,
                                    profile_id=profile_id,
                                    profile_version=profile_version
                                ))
                        else:
                            raw_matches.append(MatchItem(
                                document_id=doc_id,
                                entity_type=ent_type,
                                source=source_tag,
                                confidence=conf,
                                original_text_hash=hash_text(raw_val),
                                text_preview=preview,
                                raw_text=raw_val,
                                page=p_num,
                                bbox=None,
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
                    allowed_entities = profile.get("ner", {}).get("entities", ["PERSON", "LOC", "GPE"])
                    for ent in doc.ents:
                        if ent.label_ in allowed_entities:
                            raw_val = ent.text.strip()
                            if len(raw_val) < 4 or re.match(r'^\d+$', raw_val):
                                continue
                            
                            norm_cat = "PERSON" if ent.label_ == "PERSON" else ("ADDRESS" if ent.label_ in ["LOC", "GPE"] else "OTHER_SENSITIVE")
                            bboxes = self._find_all_bboxes_for_text(raw_val, page_rects, page_w, page_h)
                            preview = self._make_preview(raw_val, norm_cat)
                            source_tag = ["ocr", "ner"] if is_ocr else ["ner"]
                            
                            if bboxes:
                                for b in bboxes:
                                    raw_matches.append(MatchItem(
                                        document_id=doc_id,
                                        entity_type=norm_cat,
                                        source=source_tag,
                                        confidence=0.82,
                                        original_text_hash=hash_text(raw_val),
                                        text_preview=preview,
                                        raw_text=raw_val,
                                        page=p_num,
                                        bbox=b,
                                        status="pending",
                                        rule_id=f"ner.{lang}.{ent.label_.lower()}",
                                        profile_id=profile_id,
                                        profile_version=profile_version
                                    ))
                            else:
                                raw_matches.append(MatchItem(
                                    document_id=doc_id,
                                    entity_type=norm_cat,
                                    source=source_tag,
                                    confidence=0.82,
                                    original_text_hash=hash_text(raw_val),
                                    text_preview=preview,
                                    raw_text=raw_val,
                                    page=p_num,
                                    bbox=None,
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
        if len(text) <= 4:
            return text[0] + "***" + text[-1]
        elif entity_type in ["EMAIL", "API_TOKEN", "DNI_NIE_NIF", "IBAN", "PHONE"]:
            prefix = text[:3]
            suffix = text[-3:]
            return f"{prefix}...{suffix}"
        else:
            return text[:15] + ("..." if len(text) > 15 else "")

    def _find_all_bboxes_for_text(self, text: str, page_rects: List[Dict[str, Any]], page_w: float, page_h: float) -> List[BoundingBox]:
        clean_target = "".join(re.findall(r'[a-zA-Z0-9@.]+', text)).lower()
        if not clean_target or not page_rects:
            return []

        matched_boxes = []

        # 1. Exact matches on single word
        for item in page_rects:
            item_clean = "".join(re.findall(r'[a-zA-Z0-9@.]+', item.get("text", ""))).lower()
            if clean_target == item_clean:
                b = item["bbox"]
                matched_boxes.append(BoundingBox(
                    x0=float(b[0]), y0=float(b[1]), x1=float(b[2]), y1=float(b[3]),
                    page_width=page_w, page_height=page_h
                ))

        if matched_boxes:
            return matched_boxes

        # 2. Sequential multi-word search
        words = text.split()
        if len(words) > 1:
            i = 0
            while i < len(page_rects):
                word_idx = 0
                seq_boxes = []
                j = i
                while j < len(page_rects) and word_idx < len(words):
                    curr_target = "".join(re.findall(r'[a-zA-Z0-9@.]+', words[word_idx])).lower()
                    item_clean = "".join(re.findall(r'[a-zA-Z0-9@.]+', page_rects[j].get("text", ""))).lower()
                    if curr_target in item_clean or item_clean in curr_target:
                        seq_boxes.append(page_rects[j]["bbox"])
                        word_idx += 1
                        j += 1
                    else:
                        break
                if word_idx == len(words) and seq_boxes:
                    min_x = min(b[0] for b in seq_boxes)
                    min_y = min(b[1] for b in seq_boxes)
                    max_x = max(b[2] for b in seq_boxes)
                    max_y = max(b[3] for b in seq_boxes)
                    matched_boxes.append(BoundingBox(
                        x0=float(min_x), y0=float(min_y), x1=float(max_x), y1=float(max_y),
                        page_width=page_w, page_height=page_h
                    ))
                    i = j
                else:
                    i += 1

        if matched_boxes:
            return matched_boxes

        # 3. Substring containment match (find all occurrences)
        for item in page_rects:
            item_clean = "".join(re.findall(r'[a-zA-Z0-9@.]+', item.get("text", ""))).lower()
            if len(item_clean) >= 3 and (clean_target in item_clean or item_clean in clean_target):
                b = item["bbox"]
                matched_boxes.append(BoundingBox(
                    x0=float(b[0]), y0=float(b[1]), x1=float(b[2]), y1=float(b[3]),
                    page_width=page_w, page_height=page_h
                ))

        return matched_boxes

    def _deduplicate_matches(self, matches: List[MatchItem]) -> List[MatchItem]:
        consolidated: Dict[str, MatchItem] = {}

        for m in matches:
            bbox_key = f"{round(m.bbox.x0, 1)}_{round(m.bbox.y0, 1)}" if m.bbox else "nobbox"
            key = f"{m.page}_{m.raw_text.strip().lower()}_{bbox_key}"
            if key in consolidated:
                existing = consolidated[key]
                all_sources = list(set(existing.source + m.source))
                existing.source = all_sources
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
