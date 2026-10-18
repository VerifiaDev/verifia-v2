"""
ai_engine.py
------------
Person 1 (AI / LLM / Claim Verification) module for the fact-checking
system.

Responsibilities of this module (per the team's task split):
    1. Claim Extraction & Decomposition
       Break a raw user-submitted text into atomic, independently
       verifiable claims.
    2. Verdict Generation
       Given a claim and a set of labelled evidence snippets (produced
       by Person 2's search/retrieval module), decide whether the claim
       is SUPPORTED, REFUTED, NOT ENOUGH EVIDENCE, or CONFLICTING, with
       an explanation that cites the evidence it relied on.

This module exposes exactly two functions Person 3 (Backend) needs:

    extract_claims(text: str) -> ExtractionResult
    verify_claim(claim_text: str, sources: list[Source]) -> VerdictResult

Everything else (prompt text, model choice, temperature, JSON schema
enforcement) is an internal detail Backend should not have to touch.

Provider: Groq (https://groq.com) — OpenAI-compatible Chat Completions
API with "strict" JSON-schema structured output, called via the
official `groq` Python package. (Previously this module used Gemini;
the team switched to Groq.)

Setup
-----
    pip install -r requirements.txt
    cp .env.example .env         # then put your real key in .env
    python ai_engine.py          # runs the smoke tests below
"""

from __future__ import annotations

import json
import os
import re
from typing import List, Optional

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, ConfigDict, Field

# Pick up GROQ_API_KEY (and any other overrides) from a local .env
# file if one exists. No-op if there isn't one / the vars are already
# set in the environment.
load_dotenv()


# ============================================================
# 1. CONFIG
# ============================================================

# Both of these support Groq's "strict" structured-output mode (the
# response is *guaranteed* to match our JSON schema). gpt-oss-20b is
# the faster/cheaper of the two — good for iterating during
# development; swap to openai/gpt-oss-120b for higher quality later
# if needed, via the FACTCHECK_MODEL_NAME env var.
DEFAULT_MODEL_NAME = os.environ.get("FACTCHECK_MODEL_NAME", "openai/gpt-oss-20b")

# temperature=0.0: this system must behave like a rule-following
# classifier, not a creative writer. Hallucination-suppression, not
# style, is the goal.
DEFAULT_TEMPERATURE = 0.0


# ============================================================
# 2. PYDANTIC SCHEMAS (the data contract with Backend / Person 3)
# ============================================================
#
# NOTE: these also double as the JSON schemas sent to Groq's "strict"
# structured-output mode, which requires every field to be required
# (no defaults) and every object to forbid extra properties. That's
# why `model_config = ConfigDict(extra="forbid")` is set on each one,
# and why `used_sources` below has no default — don't remove either
# without re-reading https://console.groq.com/docs/structured-outputs.

class Claim(BaseModel):
    """A single atomic, independently verifiable claim."""

    model_config = ConfigDict(extra="forbid")

    id: str
    text: str
    is_verifiable: bool = Field(
        description=(
            "False for predictions, opinions, or vague/unmeasurable "
            "statements that cannot be fact-checked against evidence."
        )
    )


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: List[Claim]


class Source(BaseModel):
    """One labelled evidence snippet handed to us by Person 2 (Search).

    This is only ever an INPUT we build ourselves (never something the
    model has to return), so it doesn't need the strict-schema config
    above.
    """

    id: str  # e.g. "kaynak_1" / "source_1" — must match what appears in prompts
    url: Optional[str] = None
    text: str


class VerdictResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str
    verdict: str = Field(
        description="One of: SUPPORTED, REFUTED, NOT ENOUGH EVIDENCE, CONFLICTING"
    )
    explanation: str
    used_sources: List[str] = Field(
        description="IDs of only the sources actually relied on in `explanation`. "
        "Use an empty list if none were used."
    )


VALID_VERDICTS = {"SUPPORTED", "REFUTED", "NOT ENOUGH EVIDENCE", "CONFLICTING"}


# ============================================================
# 3. SYSTEM PROMPTS (validated in the AI Studio playground)
# ============================================================

EXTRACTION_SYSTEM_PROMPT = """\
Sen uzman bir fact-checking veri ayrıştırıcısısın. Görevin, sana verilen
metindeki iddiaları (claims) bulmak ve bunları tekil, bağımsız cümleler
halinde parçalamaktır.

Temel ilke: Ayıklama, iddianın doğru ya da yanlış olduğuna KARAR VERMEZ.
- Açıkça yanlış görünen olgusal iddialar da AYNEN ve is_verifiable=true ile
  listelenir. Doğruluk kararını yalnızca sonraki kanıt adımı verir.
- Metinde olgusal bir iddia içeren hiçbir cümle atlanmaz.

Kurallar:
- Bir cümlede birden fazla iddia varsa, bunları ayrı ayrı maddelere böl.
- Zamirleri (o, bu, şu) bağlama göre asıl isimlerle değiştir.
- Bir kurumun veya kişinin açıklaması aktarılıyorsa, iddiayı o açıklamayı
  yapan kurum/kişinin adıyla birlikte yaz (ör. "X kurumu ... açıklamıştır"),
  çünkü bu iddianın kendisi aranacak olgu haline gelir.
- is_verifiable=true: Kanıtla sınanabilen her somut olgu (kim, ne, nerede,
  ne zaman, kaç). Olgu doğru ya da yanlış görünse de true verilir.
- is_verifiable=false: YALNIZCA öznel yargılar/görüşler (ör. "Bence ...",
  "en güzel"), gelecek tahminleri ve ölçülemez/muğlak ifadeler. Bunlar da
  listeden çıkarılmaz; is_verifiable=false ile MUTLAKA listede yer alır.
  Metin yalnızca tek bir görüş cümlesinden oluşsa bile o cümle listede
  is_verifiable=false olarak döner; bu durumda liste boş OLMAZ.
- İddia metnini kullanıcının dilinde ve anlamını değiştirmeden yaz.
- Sadece verilen JSON şemasında çıktı ver, başka hiçbir açıklama ekleme.
- Boş liste YALNIZCA metinde hiçbir iddia, görüş ya da yargı yoksa döner
  (ör. yalnızca "Merhaba" ya da anlamsız karakterler).
"""

VERDICT_SYSTEM_PROMPT = """\
Sen kesinlikle tarafsız bir doğruluk kontrol (fact-checking) yargıcısın.
Sana bir 'İddia' ve 'Kanıtlar' verilecek. Kanıtlar bölümünde her satır,
köşeli parantez içinde o kanıtın kimliğiyle başlar (ör. [source_1]: ...).

Kurallar:
- Kendi içsel bilgini KESİNLİKLE kullanma. Sadece sana verilen kanıtlara
  dayanarak karar ver.
- Kararını (verdict) şu 4 kategoriden birine oturt:
  - SUPPORTED: Kanıt, iddiayı tamamen doğruluyor.
  - REFUTED: Kanıt, iddiayı yalanlıyor veya aksini söylüyor. Kanıt,
    iddiadaki olgunun başka türlü olduğunu açıkça söylüyorsa (ör. iddia
    edilen yer, kişi, tarih, sayı ya da unvan yerine kanıt başka birini
    veriyorsa) iddia REFUTED'dir; bunu NOT ENOUGH EVIDENCE sayma. İddianın
    bir kısmı doğru olsa bile, geri kalanı kanıtla çelişiyorsa bütünü
    REFUTED say.
  - NOT ENOUGH EVIDENCE: Kanıt, iddiayı doğrulamak/yalanlamak için yeterli
    detay içermiyor.
  - CONFLICTING: En az iki kanıt, aynı olgu hakkında KENDİ ADINA birbiriyle
    çelişen değerler ileri sürüyor.
- Karar vermeden önce her kanıt için şunu sor: Bu kanıt iddiadaki olguyu
  kendi adına ileri sürüyor mu, yoksa iddia cümlesini yalnızca alıntılıyor,
  soru olarak soruyor ya da doğru/yanlış diye tartışıyor mu (ör. test
  sorusu, ödev sitesi, "... doğru mu?" sayfası)? Yalnızca alıntılayan ya da
  soran kanıt hiçbir yönde kanıt sayılmaz: iddiayı desteklemez, çelişki de
  yaratmaz. Geriye kalan kanıtlar olgunun başka türlü olduğunu söylüyorsa
  karar REFUTED'dir, CONFLICTING değil.
- 'explanation' alanını HER ZAMAN Türkçe yaz (iddia ve kanıtlar başka dilde
  olsa bile). Kısa ve net ol: en fazla 2-3 cümle.
- Atıf kuralları:
  - Atıfları yalnızca Kanıtlar bölümünde her satırın başında köşeli
    parantez içinde gösterilen kimlikle, AYNEN kopyalayarak yap.
    Örnek: [source_1] ya da [source_1, source_2].
  - Kimliği cümle içinde yazma ("source_1'de", "Kaynak 3'te" gibi);
    kimliği çevirme, büyük harfe çevirme ya da değiştirme. Atıf, dayandığı
    cümlenin sonunda köşeli parantez içinde olsun.
  - Kanıtlarda olmayan kimlik yazma.
- Konuyla alakasız kanıtları (tuzak kanıtları) tamamen yoksay ve
  'used_sources' listesine ekleme.
- 'used_sources' listesi, açıklamada atıf yaptığın kimliklerin AYNISI olsun;
  hiçbirine atıf yapmadıysan boş liste ([]) döndür.
- Sadece verilen JSON şemasında çıktı ver, başka hiçbir açıklama ekleme.
"""


# ============================================================
# 4. CITATION NORMALISATION
# ============================================================
# The site links a citation to a source only when it is written in square
# brackets with the evidence id copied exactly, e.g. [source_1] or
# [source_1, source_2]. The prompt asks for that format; this is the
# deterministic safety net for when the model drifts ("Source_3'te",
# "[Kaynak_2]", an id that was never given, used_sources out of sync).

_BRACKET = re.compile(r"\s?\[([^\[\]]*)\]")
_DOUBLE_BRACKET = re.compile(r"\[\s*\[([^\[\]]*)\]\s*\]")
# "source_1", "Kaynak 2", "kanıt-3", "SRC_4" ... -> number N
_SOURCE_TOKEN = re.compile(r"(?i)^(?:source|kaynak|kan[ıi]t|src|ref)[\s_-]?(\d+)$")
# What the site (lib/citations.ts) treats as an id inside brackets: starts with a
# letter, contains "_" (e.g. nasa_overview). Unknown ones show as a missing source.
_ID_LIKE = re.compile(r"^[^\W\d_][^\W_]*_\w+$")
_GROUP_SPLIT = re.compile(r"\s*(?:[,;&]|\bve\b|\band\b)\s*", re.IGNORECASE)
# bare ids in prose; not inside URLs/paths (".../source_1") or query strings
_BARE_TOKEN = re.compile(r"(?i)(?<![/=#?&.\w-])(?:source|kaynak)_(\d+)\b")


def normalize_citations(explanation: str, valid_ids: List[str]) -> tuple[str, List[str]]:
    """Return (explanation, cited_ids) with every citation as [id] / [id, id].

    Mirrors what the site links (lib/citations.ts): a bracket group whose parts
    are all ids. For such groups:
    * ids are matched case-insensitively and rewritten to the exact evidence id;
      "kaynak_N" / "kanıt_N" / "Kaynak N" / "[N]" map to the evidence id with
      the same number ("source_N") when it exists
    * ids that are not in the evidence are dropped (an emptied bracket is
      removed), so the site never shows "Kaynak eşleşmesi bulunamadı"
    * "ve" / "and" / ";" / "&" separators become ", "; doubled brackets are
      collapsed; empty parts ("[source_1,]") are ignored
    Other brackets ([2023], [sic], [...]) are left untouched. Bare ids in a
    sentence ("source_1'de") are wrapped as [source_1] unless part of a URL.
    cited_ids lists the ids actually cited, in order, without duplicates.
    """
    text = explanation or ""
    by_fold = {i.casefold(): i for i in valid_ids}

    def by_number(num: str) -> Optional[str]:
        for name in ("source", "kaynak"):
            hit = by_fold.get(f"{name}_{num}")
            if hit:
                return hit
        return None

    def resolve(part: str) -> Optional[str]:
        exact = by_fold.get(part.casefold())
        if exact:
            return exact
        m = _SOURCE_TOKEN.match(part)
        return by_number(m.group(1)) if m else None

    cited: List[str] = []

    def note(ident: str) -> str:
        if ident not in cited:
            cited.append(ident)
        return ident

    def fix_bracket(m: "re.Match[str]") -> str:
        parts = [p for p in _GROUP_SPLIT.split(m.group(1).strip()) if p]
        if not parts:
            return m.group(0)
        if all(p.isdigit() for p in parts):
            # "[1, 2]" is a citation only if every number is an evidence number;
            # otherwise it is ordinary text such as a year: "[2023]".
            if not all(by_number(p) for p in parts):
                return m.group(0)
        elif not all(_SOURCE_TOKEN.match(p) or _ID_LIKE.match(p) or resolve(p) for p in parts):
            return m.group(0)  # not a citation (e.g. "[sic]", "[...]"): leave as is
        ids: List[str] = []
        for p in parts:
            ident = by_number(p) if p.isdigit() else resolve(p)
            if ident and ident not in ids:
                ids.append(note(ident))
        if not ids:
            return ""
        lead = " " if m.group(0)[:1].isspace() else ""
        return f"{lead}[{', '.join(ids)}]"

    def fix_bare(chunk: str) -> str:
        def wrap(m: "re.Match[str]") -> str:
            ident = by_number(m.group(1))
            return f"[{note(ident)}]" if ident else m.group(0)
        return _BARE_TOKEN.sub(wrap, chunk)

    prev = None
    while prev != text:  # "[[source_1]]" -> "[source_1]"
        prev, text = text, _DOUBLE_BRACKET.sub(r"[\1]", text)

    out: List[str] = []
    pos = 0
    for m in _BRACKET.finditer(text):
        out.append(fix_bare(text[pos:m.start()]))
        out.append(fix_bracket(m))
        pos = m.end()
    out.append(fix_bare(text[pos:]))
    return "".join(out), cited


# ============================================================
# 5. ENGINE
# ============================================================

def _strict_response_format(model: type[BaseModel], name: str) -> dict:
    """Build the {"type": "json_schema", ...} block Groq's strict mode expects."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "strict": True,
            "schema": model.model_json_schema(),
        },
    }


class FactCheckEngine:
    """Thin, stateless wrapper around the two Groq calls this module owns."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = DEFAULT_MODEL_NAME,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        api_key = api_key or os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "No Groq API key found. Create a .env file (see "
                ".env.example) with GROQ_API_KEY=..., or pass "
                "api_key=... explicitly. Get a key at "
                "https://console.groq.com/keys"
            )
        self.client = Groq(api_key=api_key)
        self.model_name = model_name
        self.temperature = temperature

    # -- internal helper --------------------------------------------------

    def _generate(self, system_prompt: str, user_prompt: str, schema_model, schema_name: str):
        completion = self.client.chat.completions.create(
            model=self.model_name,
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=_strict_response_format(schema_model, schema_name),
        )
        content = completion.choices[0].message.content
        return schema_model.model_validate(json.loads(content))

    # -- public API (this is the contract Backend/Person 3 calls) --------

    def extract_claims(self, text: str) -> ExtractionResult:
        """Split raw user text into atomic, verifiable claims."""
        return self._generate(
            EXTRACTION_SYSTEM_PROMPT,
            f"Metin: {text}",
            ExtractionResult,
            "extraction_result",
        )

    def verify_claim(self, claim_text: str, sources: List[Source]) -> VerdictResult:
        """Judge a single claim against labelled evidence snippets."""
        evidence_block = "\n".join(f"[{s.id}]: {s.text}" for s in sources)
        prompt = f"İddia: {claim_text}\n\nKanıtlar:\n{evidence_block}"

        result = self._generate(
            VERDICT_SYSTEM_PROMPT, prompt, VerdictResult, "verdict_result"
        )

        if result.verdict not in VALID_VERDICTS:
            raise ValueError(
                f"Model returned an unexpected verdict label: {result.verdict!r}"
            )
        # Citations must match the evidence ids exactly, and used_sources must
        # be exactly the ids cited in the explanation (see normalize_citations).
        result.explanation, result.used_sources = normalize_citations(
            result.explanation, [s.id for s in sources]
        )
        return result


# ============================================================
# 6. SMOKE TEST (run this file directly: `python ai_engine.py`)
# ============================================================

if __name__ == "__main__":
    engine = FactCheckEngine()

    print("--- CLAIM EXTRACTION ---")
    extraction = engine.extract_claims(
        "Apple Türkiye'de fabrika açtı ve bence bu harika bir karar."
    )
    print(extraction.model_dump_json(indent=2))

    print("\n--- VERDICT (Porsche example from the design chat) ---")
    verdict = engine.verify_claim(
        claim_text="Porsche 911 GT3 RS modeli V8 motora sahiptir.",
        sources=[
            Source(
                id="kaynak_1",
                text=(
                    "Porsche 911 GT3 RS, arka kısma yerleştirilmiş 4.0 litrelik "
                    "atmosferik 6 silindirli (flat-six) boxer motor kullanmaktadır. "
                    "Model serisinde V8 motor seçeneği hiçbir zaman sunulmamıştır."
                ),
            )
        ],
    )
    print(verdict.model_dump_json(indent=2))
