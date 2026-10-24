"""Write one Seinfeld episode with one model.

  python scripts/make_episode.py generate <model_id>   # calls OpenRouter, writes new_episode.json
  python scripts/make_episode.py add                   # merges new_episode.json into data/episodes.json

The two steps are split so the (paid) model call happens once, while the merge can be
retried against a fresh checkout if a rating was saved at the same moment.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "scripts" / "config.json").read_text())
EPISODES_FILE = ROOT / "data" / "episodes.json"
NEW_FILE = ROOT / "new_episode.json"

# The one fixed prompt every model gets. Changing it invalidates comparisons, so don't.
PROMPT = (ROOT / "data" / "prompt.txt").read_text().strip()

SETTINGS = {"temperature": 1.0, "max_tokens": 6000, "reasoning": {"effort": "medium", "exclude": True}}


def generate(model_id):
    if not re.fullmatch(r"[A-Za-z0-9._~:/-]{3,120}", model_id):
        sys.exit(f"Not a valid OpenRouter model id: {model_id!r}")
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        sys.exit("OPENROUTER_API_KEY secret is not set.")

    body = {"model": model_id, "messages": [{"role": "user", "content": PROMPT}],
            "usage": {"include": True}, **SETTINGS}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": CONFIG["site_url"],
            "X-Title": "SeinBench",
        },
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"OpenRouter returned {e.code}: {e.read().decode(errors='replace')[:500]}")
    seconds = round(time.time() - started, 1)

    if "error" in data:
        sys.exit(f"OpenRouter error: {json.dumps(data['error'])[:500]}")
    text, repeated = collapse_repeat((data["choices"][0]["message"].get("content") or "").strip())
    if not text:
        sys.exit("The model returned an empty episode. Even 'The Pilot' had words.")

    usage = data.get("usage") or {}
    now = time.gmtime()
    episode = {
        "id": slug(model_id) + time.strftime("-%Y%m%d-%H%M%S", now),
        "model": model_id,
        "modelName": model_name(model_id),
        "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", now),
        **parse(text),
        "raw": text,
        "stats": {
            "seconds": seconds,
            "outputTokens": usage.get("completion_tokens"),
            "cost": usage.get("cost"),
            "provider": data.get("provider"),
            "repeatCollapsed": repeated,
        },
        "rating": None,
        "ratedAt": None,
    }
    NEW_FILE.write_text(json.dumps(episode, indent=1) + "\n")
    print(f"Wrote '{episode['title']}' with {model_id} in {seconds}s.")


def collapse_repeat(text):
    """Providers occasionally deliver the whole reply twice, back to back. Keep one copy.

    Only an exact duplicate counts; a model that genuinely writes two versions is left alone.
    """
    half = len(text) // 2
    first, second = text[:half].strip(), text[half:].strip()
    if len(text) % 2 == 0 and first and first == second:
        return first, True
    return text, False


def parse(text):
    """Pull TITLE / SYNOPSIS / SCENE out of whatever the model actually sent back."""
    # Normalize "**TITLE:**", "## Title:", "__SCENE__:" and friends to "TITLE: ".
    clean = re.sub(r"^[\s#*_>]*(TITLE|SYNOPSIS|SCENE)[\s*_]*:[ \t*_]*",
                   lambda m: m.group(1).upper() + ": ", text, flags=re.M | re.I)
    title = re.search(r"TITLE\s*:\s*(.+)", clean)
    synopsis = re.search(r"SYNOPSIS\s*:\s*(.+?)(?=\n\s*SCENE\s*:|\Z)", clean, re.S)
    scene = re.search(r"SCENE\s*:\s*\n?(.*?)(?=TITLE\s*:|\Z)", clean, re.S)  # stop at a second episode
    return {
        "title": title.group(1).strip().strip("*\"") if title else "Untitled (The Show About Nothing)",
        "synopsis": synopsis.group(1).strip() if synopsis else "",
        "scene": scene.group(1).strip() if scene else clean,
    }


def slug(model_id):
    return re.sub(r"[^a-z0-9]+", "-", model_id.lower()).strip("-")


def model_name(model_id):
    models_file = ROOT / "data" / "models.json"
    if models_file.exists():
        for m in json.loads(models_file.read_text())["models"]:
            if m["id"] == model_id:
                return m["name"]
    return model_id


def add():
    episode = json.loads(NEW_FILE.read_text())
    episodes = json.loads(EPISODES_FILE.read_text()) if EPISODES_FILE.exists() else []
    if not any(e["id"] == episode["id"] for e in episodes):
        episodes.append(episode)
    EPISODES_FILE.write_text(json.dumps(episodes, indent=1, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["generate"] and len(sys.argv) == 3:
        generate(sys.argv[2].strip())
    elif sys.argv[1:] == ["add"]:
        add()
    else:
        sys.exit(__doc__)
