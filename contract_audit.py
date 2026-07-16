#!/usr/bin/env python3
"""Audit a DeepAPI client against the SKILL.md error contract, emit SARIF 2.1.0.

Runs the three contract checks (tests/contract_checks.py) against a target client.
Every check the target FAILS becomes a SARIF result anchored to the offending
line, so GitHub Code Scanning renders it as a PR annotation / Security alert.
Also writes a Markdown summary (for the Actions job summary) and prints the
naive-vs-fixed matrix.

    python3 contract_audit.py                       # audit the naive baseline
    python3 contract_audit.py --target deepapi_client.py
    python3 contract_audit.py --out results.sarif --summary summary.md
"""
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tests"))
import contract_checks as cc

# spectr-ai-style severity -> SARIF level, plus GitHub's security-severity score.
SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning",
               "low": "note", "informational": "note"}
SECURITY_SEVERITY = {"critical": "9.5", "high": "8.1", "medium": "5.5",
                     "low": "3.1", "informational": "1.0"}


def line_of(path, anchor):
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if anchor in line:
                return i
    return 1


def build_sarif(target_path, target_uri, client):
    rules, results = [], []
    for gap in cc.GAPS:
        level = SARIF_LEVEL[gap["severity"]]
        rules.append({
            "id": gap["id"],
            "name": "".join(w.capitalize() for w in gap["id"].split("/")[-1].split("-")),
            "shortDescription": {"text": gap["title"]},
            "fullDescription": {"text": gap["description"]},
            "helpUri": "https://deepapi.co/llms.txt",
            "help": {"text": f"{gap['description']}\n\nRecommendation: {gap['recommendation']}"},
            "defaultConfiguration": {"level": level},
            "properties": {
                "tags": ["security", "reliability", "deepapi-contract"],
                "security-severity": SECURITY_SEVERITY[gap["severity"]],
            },
        })
        if not gap["check"](client):                        # target fails the check -> finding
            line = line_of(target_path, gap["anchor"])
            results.append({
                "ruleId": gap["id"],
                "ruleIndex": len(rules) - 1,
                "level": level,
                "message": {"text": f"{gap['description']}\n\nRecommendation: {gap['recommendation']}"},
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": target_uri},
                        "region": {"startLine": line, "endLine": line},
                    },
                }],
                "partialFingerprints": {"deepapiContractRule/v1": gap["id"]},
            })
    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "deepapi-contract-audit",
                "informationUri": "https://github.com/ANcpLua/deepapi-recon",
                "version": "1.0.0",
                "rules": rules,
            }},
            "automationDetails": {"id": "deepapi-contract-audit/"},
            "results": results,
        }],
    }, results


def markdown(target_uri, results):
    sev_emoji = {"error": "🔴", "warning": "🟠", "note": "🟡"}
    lines = ["## DeepAPI client contract audit\n",
             f"Audited `{target_uri}` against the SKILL.md error contract "
             f"— **{len(results)} finding{'s' if len(results) != 1 else ''}**. "
             "These are client-side compliance gaps, not defects in DeepAPI.\n",
             "| gap | naive | fixed |", "|---|:---:|:---:|"]
    for i, g in enumerate(cc.GAPS, 1):
        n = "✅" if g["check"](cc.NAIVE) else "❌"
        x = "✅" if g["check"](cc.FIXED) else "❌"
        lines.append(f"| {i}. {g['label']} | {n} | {x} |")
    if results:
        lines += ["", "### Findings", "| sev | rule | location | issue |", "|---|---|---|---|"]
        for r in results:
            loc = r["locations"][0]["physicalLocation"]
            uri = loc["artifactLocation"]["uri"]; ln = loc["region"]["startLine"]
            title = next(g["title"] for g in cc.GAPS if g["id"] == r["ruleId"])
            lines.append(f"| {sev_emoji.get(r['level'], '⚪')} {r['level']} | `{r['ruleId']}` | "
                         f"`{uri}:{ln}` | {title} |")
    else:
        lines += ["", "✅ **Clean** — the client honors every rule in the contract."]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", default="tests/_naive_client.py",
                    help="client file to audit (repo-relative). Default: the naive baseline.")
    ap.add_argument("--out", default="results.sarif", help="SARIF output path")
    ap.add_argument("--summary", help="write a Markdown summary to this path (for the job summary)")
    ap.add_argument("--fail-on-error", action="store_true",
                    help="exit 1 if any error-level finding is present")
    args = ap.parse_args()

    target_uri = args.target.replace("\\", "/")
    target_path = os.path.join(HERE, target_uri)
    client = cc.FIXED if os.path.abspath(target_path) == os.path.abspath(cc.FIXED_PATH) else cc.NAIVE

    sarif, results = build_sarif(target_path, target_uri, client)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(sarif, f, indent=2)

    md = markdown(target_uri, results)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write(md)
    print(md)
    print(f"→ wrote {args.out} ({len(results)} result(s))")

    if args.fail_on_error and any(r["level"] == "error" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
