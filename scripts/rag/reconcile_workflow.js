export const meta = {
  name: 'ontology-reconcile',
  description: 'Read the coverage gaps + flagged VRs semantically; propose domain_config / ontology-seed updates (validated vs CLAUDE.md, gated not auto-applied)',
  phases: [
    { title: 'Interpret', detail: 'unseeded objects, uncaptured notation, unknown relations, alias drift — each read by meaning' },
    { title: 'Synthesize', detail: 'merge into a reviewable reconciliation proposal' },
  ],
}

const R = "/Users/user/Projects/r14-verify"
const CTX = `The audit tool's deterministic self-coverage audit (${R}/data/rag/coverage_report.json) flagged corpus content its structured layers do not capture. Your job is to read that content BY MEANING and propose concrete updates to the domain config (${R}/scripts/rag/domain_config.json) or the ontology seeds (${R}/scripts/rag/canonical_objects.json, object_properties_seed.json, domain_links_seed.json). Authoritative facts: ${R}/CLAUDE.md. Corpus: ${R}/verification_ready/*.md. You may grep/read freely. Propose, do NOT apply. Every proposed fact needs corpus/CLAUDE.md provenance. Reject candidates that are noise (truncation garbage, one-off prose, already-captured-as-concepts).`

phase('Interpret')

const ANGLES = [
  { key: 'unseeded_objects', prompt:
`${CTX}
From coverage_report.json 'unseeded_objects' (object-shaped, high-mention entities absent from the ontology seed — e.g. 11a1, 571a1, 27a1, 49a1, K₂, ...): for the top ~12, read a few VRs that mention each and determine (a) is it a REAL domain object worth seeding (an elliptic curve / field actually studied), or noise/truncation (K_)? (b) what ROLE does it play (auxiliary curve? calibration curve? a field in the tower?) (c) propose a canonical_objects.json entry {id,type,title,aliases,note} if worth seeding, with corpus provenance. Distinguish genuine study objects (e.g. 11a1 may be a comparison/CM curve) from incidental mentions.` },

  { key: 'uncaptured_notation', prompt:
`${CTX}
From coverage_report.json 'uncaptured_tokens' (recurring notation no entity pattern matches — e.g. Θ₂, Θ₁, Sel₂, E′, val₂, higher_descent, C₂, K₂): classify EACH of the top ~12 as one of: domain OBJECT (should be a canonical object / new entity family), QUANTITY (like rank/sha — a tracked value), METHOD/CONCEPT (already covered by concepts.json / method_registry, no action), or NOISE. For objects/quantities, propose a domain_config.json entity_family entry {pattern,template} or a quantity entry. E.g. C₂ is the cyclic group order 2 (extend the group entity pattern); Sel₂ is a Selmer group (object); val₂ is the 2-adic valuation (quantity). Give the concrete regex addition.` },

  { key: 'uncaptured_relations', prompt:
`${CTX}
From coverage_report.json 'uncaptured_relations' (verbs adjacent to VR-refs that are not known supersession relations — e.g. confirms, validated, closes, matches, established, identified): for each, read 2-3 example "VR-X <verb> VR-Y" usages and decide whether it is a genuine SEMANTIC RELATION worth adding to the supersession graph (e.g. 'confirms'/'validates' = a corroboration edge; 'closes' = resolves-an-open-question edge; 'matches' = agreement, maybe not a correction). Propose domain_config.json supersession_patterns entries {pattern, relation} for the ones that carry real graph meaning, and say which are too weak/ambiguous to add.` },

  { key: 'alias_drift', prompt:
`${CTX}
From coverage_report.json 'alias_drift' (canonical objects whose dominant RECENT corpus form differs from the seed primary — e.g. E->64a1, stem_1->stem₁, E^-7->E^{-7}): for each, confirm the dominant form is already in the object's alias list (then it is benign — informational), or propose adding it / changing the primary. Recommend whether to re-point any 'primary' to the corpus-dominant form. Keep it conservative; only flag real misses.` },
]

const interp = await parallel(ANGLES.map(a => () =>
  agent(a.prompt, { label: `interpret:${a.key}`, phase: 'Interpret' }).then(t => ({ key: a.key, text: t }))))
const bundle = interp.filter(Boolean).map(r => `### ${r.key}\n${r.text}`).join('\n\n')

phase('Synthesize')

const PROPOSAL = {
  type: 'object', additionalProperties: false,
  properties: {
    config_additions: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { target: { type: 'string', enum: ['entity_family','quantity','supersession_pattern'] },
        spec: { type: 'string', description: 'the concrete JSON entry to add to domain_config.json' },
        rationale: { type: 'string' }, provenance: { type: 'string' } },
      required: ['target','spec','rationale','provenance'] } },
    object_additions: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { id: { type: 'string' }, type: { type: 'string' }, title: { type: 'string' },
        aliases: { type: 'array', items: { type: 'string' } }, role: { type: 'string' }, provenance: { type: 'string' } },
      required: ['id','type','title','aliases','provenance'] } },
    alias_updates: { type: 'array', items: { type: 'object', additionalProperties: false,
      properties: { object: { type: 'string' }, change: { type: 'string' }, rationale: { type: 'string' } },
      required: ['object','change','rationale'] } },
    no_action: { type: 'array', items: { type: 'string' }, description: 'flagged items that are noise or already-covered (with why)' },
    summary: { type: 'string' },
  },
  required: ['config_additions','object_additions','alias_updates','no_action','summary'],
}

return await agent(
  `Synthesize the semantic interpretation of the coverage gaps into a single REVIEWABLE reconciliation proposal (gated — for a human/agent to apply, not auto-applied). Separate: config_additions (new entity families / quantities / relations for domain_config.json), object_additions (new canonical objects), alias_updates, and no_action (noise / already-covered, with the reason). Be conservative and precise; every addition carries provenance.

=== SEMANTIC INTERPRETATION ===
${bundle}`,
  { label: 'proposal', phase: 'Synthesize', schema: PROPOSAL })
