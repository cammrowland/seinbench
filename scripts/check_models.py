"""Daily scout: refresh data/models.json from OpenRouter and flag new major releases.

Makes no model calls and costs nothing. If new major releases showed up since the
last run, writes an email to email.txt and sets notify=true for the workflow.
"""
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text())
MODELS_FILE = ROOT / "data" / "models.json"
EMAIL_FILE = ROOT / "email.txt"
DAY = 86400


def fetch_models():
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/models",
        headers={"User-Agent": "SeinBench/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["data"]


def is_major(model_id):
    lab, _, rest = model_id.partition("/")
    if lab not in CONFIG["major_labs"] or ":" in rest:
        return False  # unknown lab, or a variant like ":free" / ":extended"
    tokens = set(re.split(r"[-._/]", rest.lower()))
    if tokens & set(CONFIG["minor_tokens"]):
        return False
    if re.search(r"-(\d{4}|\d{2}-\d{2}|\d{4}-\d{2}-\d{2})$", rest):
        return False  # dated snapshot of a model we already know
    sizes = [float(n) for n in re.findall(r"(?<![a-z0-9])(\d+(?:\.\d+)?)b(?![a-z0-9])", rest.lower())]
    if sizes and max(sizes) < CONFIG["min_params_b"]:
        return False
    return True


def price(model, key):
    try:
        return round(float(model["pricing"][key]) * 1e6, 4)  # dollars per million tokens
    except (KeyError, TypeError, ValueError):
        return None


def main():
    now = int(time.time())
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    previous = json.loads(MODELS_FILE.read_text()) if MODELS_FILE.exists() else None
    seen = {m["id"]: m for m in previous["models"]} if previous else {}

    models = []
    for m in fetch_models():
        if "text" not in (m.get("architecture", {}).get("output_modalities") or ["text"]):
            continue
        lab = m["id"].split("/")[0]
        models.append({
            "id": m["id"],
            "name": m.get("name") or m["id"],
            "lab": CONFIG["major_labs"].get(lab, lab),
            "created": m.get("created") or 0,
            "firstSeen": seen.get(m["id"], {}).get("firstSeen", today),
            "major": is_major(m["id"]),
            "inPrice": price(m, "prompt"),
            "outPrice": price(m, "completion"),
            "context": m.get("context_length"),
            "description": (m.get("description") or "")[:280],
        })
    models.sort(key=lambda m: m["created"], reverse=True)

    MODELS_FILE.write_text(json.dumps({"updated": today, "models": models}, indent=1) + "\n")

    if previous is None:
        print(f"Baseline run: recorded {len(models)} models, no email.")
        return

    cutoff = now - CONFIG["new_window_days"] * DAY
    new = [m for m in models if m["id"] not in seen]
    new_major = [m for m in new if m["major"] and m["created"] >= cutoff]
    print(f"{len(models)} models, {len(new)} new, {len(new_major)} new major releases.")
    for m in new_major:
        print("  major:", m["id"])

    if new_major:
        write_email(new_major, [m for m in new if m not in new_major])
        set_output("notify", "true")


def write_email(majors, others):
    desk = CONFIG["site_url"] + "writers-room.html"
    n = len(majors)
    lines = [
        f"Subject: SeinBench: {n} new major model{'s' if n != 1 else ''} worth a look",
        "",
        "Hello, Newman. I mean, hello.",
        "",
        f"{n} new major release{'s' if n != 1 else ''} just showed up on OpenRouter:",
        "",
    ]
    for m in majors:
        cost = f"${m['outPrice']:g}/M output tokens" if m["outPrice"] is not None else "price unknown"
        lines.append(f"  - {m['name']}  ({m['id']}, {cost})")
    lines += ["", f"Make an episode with any of them here:", desk, ""]
    if others:
        lines.append(f"Also new but probably minor ({len(others)}): " + ", ".join(m["id"] for m in others[:15])
                     + (" ..." if len(others) > 15 else ""))
        lines.append("")
    lines.append("Nothing was generated and nothing was charged. That's your call.")
    EMAIL_FILE.write_text("\n".join(lines) + "\n")


def set_output(key, value):
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a") as f:
            f.write(f"{key}={value}\n")


if __name__ == "__main__":
    sys.exit(main())
