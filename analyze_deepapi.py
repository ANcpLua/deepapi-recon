#!/usr/bin/env python3
"""Deep sweep of skills-main for DeepAPI usage: mentions, endpoints, env vars, URLs."""
import re, json, collections
from pathlib import Path

ROOT = Path(__file__).parent / "skills" / "skills-main"
mentions = collections.defaultdict(list)
endpoints = collections.defaultdict(set)   # endpoint -> files
urls = collections.Counter()
envvars = collections.Counter()
skills = []

ep_re = re.compile(r'\b(GET|POST|PUT|PATCH|DELETE)?\s*(/v\d+/[A-Za-z0-9_\-/{}.:]+)')
url_re = re.compile(r'https?://[^\s)"\'`\]>]+')
env_re = re.compile(r'\b([A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|KEY)[A-Z0-9_]*)\b')

for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or p.suffix not in {".md", ".py", ".sh", ".json", ".yaml", ".yml", ".txt", ""}:
        continue
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        continue
    rel = str(p.relative_to(ROOT))
    if p.name == "SKILL.md":
        m = re.search(r'^name:\s*(.+)$', text, re.M)
        d = re.search(r'^description:\s*(.+)$', text, re.M)
        skills.append({"path": rel, "name": m.group(1).strip() if m else p.parent.name,
                       "desc": (d.group(1).strip()[:160] if d else ""), "deepapi": "deepapi" in text.lower()})
    if "deepapi" not in text.lower():
        continue
    for i, line in enumerate(text.splitlines(), 1):
        ll = line.lower()
        if "deepapi" in ll:
            mentions[rel].append((i, line.strip()[:200]))
        for m in ep_re.finditer(line):
            method = m.group(1) or ""
            endpoints[f"{method} {m.group(2)}".strip()].add(rel)
        for u in url_re.findall(line):
            if "deepapi" in u.lower():
                urls[u.rstrip('.,;:')] += 1
        for e in env_re.findall(line):
            envvars[e] += 1

out = {
    "skills_total": len(skills),
    "skills_using_deepapi": [s for s in skills if s["deepapi"]],
    "endpoints": {k: sorted(v) for k, v in sorted(endpoints.items())},
    "deepapi_urls": urls.most_common(),
    "env_vars": envvars.most_common(),
    "mention_counts": {k: len(v) for k, v in sorted(mentions.items(), key=lambda kv: -len(kv[1]))},
}
(Path(__file__).parent / "deepapi_report.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2)[:6000])
