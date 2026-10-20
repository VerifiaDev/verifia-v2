import assert from "node:assert/strict";
import { it } from "node:test";
import { renderToStaticMarkup } from "react-dom/server";
import { parseCheckResponse } from "@/lib/api/adapter";
import { ClaimItem } from "@/components/ClaimItem";
import { EvidenceCard } from "@/components/EvidenceCard";

const sources = [1, 2, 3, 4, 5].map(n => ({ id: `source_${n}`, url: `https://e${n}.test`, text: `pasaj ${n}` }));
const base = { claim: "Nötr iddia", verdict: "SUPPORTED", explanation: "Açıklama.", sources };
const compatibility = Object.fromEntries(["entity", "temporal", "predicate", "scope", "metric", "modality"].map(k => [k, "MATCH"]));
function claim(extra: object = {}) { return parseCheckResponse({ ...base, ...extra }).claims[0]; }

it("structured used sources are authoritative without citations", () => {
  const c = claim({ used_sources: ["source_3", "fake", "source_3"] });
  assert.deepEqual(c.usedSourceIds, ["source_3"]);
  const html = renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />);
  assert.match(html, /5 kaynak bulundu, 1 tanesine dayanıldı/);
  assert.match(html, /Dayandığımız kanıtlar \(1\)/);
  assert.match(html, /Diğer kaynaklar \(4\)/);
  assert.ok(html.indexOf("pasaj 3") < html.indexOf("Diğer kaynaklar"));
});

it("explicit empty and malformed used sources never fall back to citations", () => {
  for (const used_sources of [[], null, "source_1", ["unknown"]]) {
    const c = claim({ used_sources, explanation: "Açıklama [source_1]." });
    assert.deepEqual(c.usedSourceIds, []);
    const html = renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />);
    assert.match(html, /5 kaynak bulundu, 0 tanesine dayanıldı/);
  }
});

it("context, limited, unknown and duplicate assessment IDs cannot become used evidence", () => {
  for (const entry of [
    { relation: "CONTEXT", strength: "STRONG", compatibility },
    { relation: "SUPPORTS", strength: "LIMITED", compatibility },
    { relation: "SUPPORTS", strength: "STRONG", compatibility: { ...compatibility, temporal: "UNKNOWN" } },
  ]) {
    assert.deepEqual(claim({ used_sources: ["source_1"], source_assessments: [{ source_id: "source_1", ...entry }] }).usedSourceIds, []);
  }
  const a = { source_id: "source_1", relation: "SUPPORTS", strength: "STRONG", compatibility };
  assert.deepEqual(claim({ used_sources: ["source_1"], source_assessments: [a, a] }).usedSourceIds, []);
  assert.deepEqual(claim({ used_sources: ["source_1"], sources: [sources[0]], source_assessments: [a] }).usedSourceIds, ["source_1"]);
});

it("legacy absent used sources retains citation fallback", () => {
  const c = claim({ explanation: "Açıklama [source_2]." });
  assert.equal(c.usedSourceIds, undefined);
  assert.match(renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />), /Dayandığımız kanıtlar \(1\)/);
});

for (const method of ["requests", "requests_short", "tavily_snippet", "tavily_pdf_snippet", "unknown"]) {
  it(`provenance and reason render truthfully: ${method}`, () => {
    const c = claim({ sources: [{ ...sources[0], metadata: { fetch_method: method }, relation: "irrelevant", assessment_reason: "Farklı kapsam." }] });
    assert.equal(c.sources[0].fetchMethod, method);
    const html = renderToStaticMarkup(<EvidenceCard source={c.sources[0]} number={1} claimId="c" />);
    assert.match(html, /Farklı kapsam/);
    assert.match(html, /Doğrudan kanıt değil/);
    if (method.includes("snippet")) {
      assert.doesNotMatch(html, /<blockquote/);
      assert.match(html, /arama özeti|Arama özeti/);
    } else if (method.startsWith("requests")) assert.match(html, /sayfadan|Sayfadan/);
  });
}


it("incomplete assessment set fails closed in the adapter", () => {
  const source_assessments = [{ source_id: "source_1", relation: "SUPPORTS", strength: "STRONG", compatibility }];
  assert.deepEqual(claim({ used_sources: ["source_1"], source_assessments }).usedSourceIds, []);
});

it("non-material UNKNOWN remains eligible while material UNKNOWN is rejected", () => {
  const a = { source_id: "source_1", relation: "SUPPORTS", strength: "STRONG",
    compatibility: { ...compatibility, metric: "UNKNOWN" } };
  const materiality = { entity: true, temporal: true, predicate: true, scope: false, metric: false, modality: true };
  const raw = { sources: [sources[0]], used_sources: ["source_1"], source_assessments: [a] };
  const c = claim({ ...raw, compatibility_materiality: materiality });
  assert.deepEqual(c.usedSourceIds, ["source_1"]);
  assert.match(renderToStaticMarkup(<ClaimItem claim={c} index={0} total={1} />), /Dayandığımız kanıtlar \(1\)/);
  for (const compatibility_materiality of [undefined, {}, { ...materiality, metric: true }, { ...materiality, metric: "false" }]) {
    assert.deepEqual(claim({ ...raw, compatibility_materiality }).usedSourceIds, []);
  }
});
