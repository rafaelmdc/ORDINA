"""Map Disbiome diseases -> MONDO (canonical), using name/synonym match first,
MeSH as a bridge, and the MedDRA code only as weak corroboration + provenance.

Inputs (all local):
  - Disbiome diseases : ~/.cache/braidworks/disbiome/disbiome.sqlite
  - MONDO ontology    : scratchpad/mondo.obo   (release 2026-06-02)
Outputs (scratchpad):
  - disbiome_mondo_mapping.tsv
  - prints a coverage report to stderr
"""
from __future__ import annotations
import os, sqlite3, json, re, sys, difflib
from pathlib import Path

HERE = Path(__file__).parent
# Inputs (override via env). mondo.obo: http://purl.obolibrary.org/obo/mondo.obo
# disbiome.sqlite: built by the Disbiome connector (contains an `association(full_json)` table).
OBO = Path(os.environ.get("MONDO_OBO", HERE / "mondo.obo"))
DISBIOME = os.environ.get("DISBIOME_DB", str(Path.home() / ".cache/braidworks/disbiome/disbiome.sqlite"))

def norm(s: str) -> str:
    s = s.lower().strip()
    s = s.replace("&", " and ")
    s = s.replace("'", "").replace("’", "")     # possessives: crohn's -> crohns
    s = re.sub(r"[^a-z0-9]+", " ", s)
    # British -> American, applied to BOTH sides so the difference cancels out
    s = s.replace("oe", "e").replace("ae", "e")           # oesophagus->esophagus, anaemia->anemia
    s = s.replace("tumour", "tumor").replace("isation", "ization").replace("ised", "ized")
    s = re.sub(r"\s+", " ", s).strip()
    if s.startswith("the "):
        s = s[4:]
    return s

_STOP = {"disease", "disorder", "syndrome", "infection", "chronic", "acute"}
def tokset(nn: str) -> frozenset:
    return frozenset(nn.split())

# ---- 1. parse mondo.obo --------------------------------------------------
terms = {}   # mondo_id -> dict
cur = None
def flush(t):
    if t and t.get("id", "").startswith("MONDO:"):
        terms[t["id"]] = t

for line in OBO.read_text().splitlines():
    if line == "[Term]":
        flush(cur); cur = {"exact": set(), "related": set(), "mesh": set(), "meddra": set()}
        continue
    if cur is None:
        continue
    if line.startswith("[") and line.endswith("]"):   # another stanza type
        flush(cur); cur = None; continue
    if line.startswith("id: "):
        cur["id"] = line[4:].strip()
    elif line.startswith("name: "):
        cur["name"] = line[6:].strip()
    elif line.startswith("is_obsolete: true"):
        cur["obsolete"] = True
    elif line.startswith("synonym: "):
        m = re.match(r'synonym: "(.*?)" (\w+)', line)
        if m:
            text, scope = m.group(1), m.group(2)
            (cur["exact"] if scope == "EXACT" else cur["related"]).add(text)
        for mc in re.findall(r"MESH:(\w+)", line):
            cur["mesh"].add(mc)
    elif line.startswith("xref: MESH:"):
        cur["mesh"].add(line.split("MESH:")[1].split()[0].strip())
    elif "MESH:" in line and "exactMatch" in line:
        cur["mesh"].add(line.split("MESH:")[1].split()[0].strip())
    elif "MEDDRA:" in line:
        for mc in re.findall(r"MEDDRA:(\d+)", line):
            cur["meddra"].add(mc)
flush(cur)

live = {i: t for i, t in terms.items() if not t.get("obsolete") and t.get("name")}
print(f"[mondo] terms parsed={len(terms)} live={len(live)}", file=sys.stderr)

# ---- 2. build lookup indexes (live terms only) ---------------------------
label_idx, exsyn_idx, relsyn_idx = {}, {}, {}
meddra_idx, mesh_terms = {}, {}
for i, t in live.items():
    label_idx.setdefault(norm(t["name"]), set()).add(i)
    for s in t["exact"]:
        exsyn_idx.setdefault(norm(s), set()).add(i)
    for s in t["related"]:
        relsyn_idx.setdefault(norm(s), set()).add(i)
    for mc in t["meddra"]:
        meddra_idx.setdefault(mc, set()).add(i)
    mesh_terms[i] = t["mesh"]
label_keys = list(label_idx) + list(exsyn_idx)                 # fuzzy pool
cand_tokens = {k: tokset(k) for k in set(label_keys)}          # token-subset pool
key_to_ids = {}
for k in label_idx: key_to_ids.setdefault(k, set()).update(label_idx[k])
for k in exsyn_idx: key_to_ids.setdefault(k, set()).update(exsyn_idx[k])

# ---- 3. Disbiome disease universe ---------------------------------------
con = sqlite3.connect(f"file:{DISBIOME}?mode=ro", uri=True)
dis = {}
for (fj,) in con.execute("SELECT full_json FROM association"):
    j = json.loads(fj); d = j.get("disease") or {}
    name = d.get("name") or j.get("disease_name")
    meddra = str(d.get("meddra_id") or j.get("meddra_id") or "") or None
    if name:
        dis.setdefault((name, meddra), 0)
        dis[(name, meddra)] += 1

# ---- 4. match ------------------------------------------------------------
def pick(ids):  # deterministic pick + ambiguity flag
    ids = sorted(ids)
    return ids[0], (len(ids) > 1)

# CONFIRMED tiers = high precision (exact label/synonym/related-syn, unambiguous MedDRA xref).
# SUGGESTION tiers = likely but must be confirmed (token-subset, then typo-level fuzzy).
CONFIRMED = {"mondo_label", "mondo_exact_synonym", "mondo_related_synonym", "meddra_xref"}

_GENERIC = {"cancer", "tumor", "tumour", "carcinoma", "neoplasm", "infection",
            "syndrome", "disease", "disorder", "deficiency", "inflammation", "failure"}
def token_subset(nn):
    """Safest recall booster: query tokens are a subset of a candidate's tokens
    (or vice-versa). Unlike fuzzy, 'hepatitis c' cannot match 'hepatitis d ...'."""
    qt = tokset(nn)
    if len(qt) < 2:
        # single distinctive word only (avoid 'cancer'->everything); tight extra budget
        w = next(iter(qt), "")
        if len(w) < 5 or w in _GENERIC:
            return None
        fwd = [(len(ct - qt), k) for k, ct in cand_tokens.items() if qt <= ct and len(ct - qt) <= 1]
        return (min(fwd)[1], "token_subset_narrower") if fwd else None
    fwd = [(len(ct - qt), k) for k, ct in cand_tokens.items() if qt <= ct and len(ct - qt) <= 3]
    if fwd:
        return min(fwd)[1], "token_subset_narrower"      # MONDO term is more specific
    rev = [(len(qt - ct), k) for k, ct in cand_tokens.items() if ct <= qt and len(qt - ct) <= 2]
    if rev:
        return min(rev)[1], "token_subset_broader"       # MONDO term is more general (rollup)
    return None

rows = []
for (name, meddra), n_exp in sorted(dis.items(), key=lambda kv: -kv[1]):
    nn = norm(name)
    mid = method = None; conf = 0.0; ambig = False
    if nn in label_idx:
        mid, ambig = pick(label_idx[nn]); method, conf = "mondo_label", 1.0
    elif nn in exsyn_idx:
        mid, ambig = pick(exsyn_idx[nn]); method, conf = "mondo_exact_synonym", 0.95
    elif nn in relsyn_idx:
        mid, ambig = pick(relsyn_idx[nn]); method, conf = "mondo_related_synonym", 0.85
    elif meddra and meddra in meddra_idx:
        mid, ambig = pick(meddra_idx[meddra]); method, conf = "meddra_xref", 0.80
    elif (ts := token_subset(nn)):
        hit, method = ts; mid, ambig = pick(key_to_ids[hit]); conf = 0.75
    else:
        close = difflib.get_close_matches(nn, label_keys, n=1, cutoff=0.93)  # typo-level only
        if close:
            mid, ambig = pick(key_to_ids[close[0]]); method, conf = "fuzzy_suggestion", 0.60
        else:
            method, conf = "UNMAPPED", 0.0
    confirmed = (method in CONFIRMED) and not ambig
    meddra_corrob = bool(mid and meddra and meddra in live[mid]["meddra"])
    rows.append({
        "disbiome_disease": name, "meddra_id": meddra or "",
        "mondo_id": mid or "", "mondo_label": live[mid]["name"] if mid else "",
        "mesh_ids": "|".join(sorted(mesh_terms.get(mid, set()))) if mid else "",
        "match_method": method, "confidence": conf,
        "status": "confirmed" if confirmed else ("unmapped" if method == "UNMAPPED" else "review"),
        "meddra_corroborates": "yes" if meddra_corrob else "",
        "ambiguous": "yes" if ambig else "",
        "n_experiments": n_exp,
    })

# ---- 5. write + report ---------------------------------------------------
cols = ["disbiome_disease","meddra_id","mondo_id","mondo_label","mesh_ids",
        "match_method","confidence","status","meddra_corroborates","ambiguous","n_experiments"]
out = HERE / "disbiome_mondo_mapping.tsv"
with out.open("w") as f:
    f.write("\t".join(cols) + "\n")
    for r in rows:
        f.write("\t".join(str(r[c]) for c in cols) + "\n")

import collections
by_status = collections.Counter(r["status"] for r in rows)
by_method = collections.Counter(r["match_method"] for r in rows)
with_mesh = sum(1 for r in rows if r["mesh_ids"])
exp_total = sum(r["n_experiments"] for r in rows)
exp_conf  = sum(r["n_experiments"] for r in rows if r["status"] == "confirmed")
print(f"\n[disbiome] distinct diseases: {len(rows)}  (covering {exp_total} experiments)", file=sys.stderr)
print(f"[status]  " + ", ".join(f"{k}={v}" for k, v in by_status.most_common()), file=sys.stderr)
print(f"[confirmed weight] confirmed diseases cover {exp_conf}/{exp_total} "
      f"({100*exp_conf/exp_total:.1f}%) of all experiments", file=sys.stderr)
print(f"[mesh bridge] {with_mesh} mapped diseases carry a MeSH id", file=sys.stderr)
print("[by method] " + ", ".join(f"{k}={v}" for k, v in by_method.most_common()), file=sys.stderr)
print(f"\n[written] {out}", file=sys.stderr)
print("\n--- REVIEW worklist: suggestions to confirm (method / disbiome -> MONDO guess) ---", file=sys.stderr)
for r in rows:
    if r["status"] == "review":
        print(f"  {r['match_method']:24s} {r['disbiome_disease'][:40]:40s} -> {r['mondo_label'][:38]} ({r['mondo_id']})", file=sys.stderr)
print("\n--- UNMAPPED: no MONDO candidate found (need manual curation) ---", file=sys.stderr)
print("  " + " | ".join(r["disbiome_disease"] for r in rows if r["status"] == "unmapped"), file=sys.stderr)
