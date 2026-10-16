"""D33: the block founding call as audio for the Control Room (no live mic needed on stage).

    uv run python -m core.voice.founding_audio            # -> kit/public/audio/w147_founding.mp3 + .timeline.json

Lines are a condensed take of data/builder/w147_intake.jsonl (Tanya's own words, trimmed; Village asks the intake
questions). Tanya and Village (Luz's voice) are rendered with ElevenLabs TTS `with-timestamps`, joined with 0.6 s
gaps by ffmpeg; the timeline is [{t_ms, speaker, text}] from the measured segment lengths. Target ≤ 90 s.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "kit" / "public" / "audio"
LUZ_VOICE = "EXAVITQu4vr4xnSDxMaL"  # mom-line agent tts.voice_id
TANYA_VOICE = "cgSgspJ2msm6clMCkdW9"  # a second, distinct premade voice
GAP_S = 0.6
MAX_S = 90.0

SCRIPT: list[tuple[str, str]] = [
    ("tanya", "Power's out on our whole block and it's ninety-seven degrees. Mrs. Alvarez on five needs her oxygen machine, and Mr. Chen's insulin is warming up. Darnell's got a generator, Priya's got a car. Help me."),
    ("village", "Got it. A block outage in the heat, and two medical needs. Who on the block should I know about, and which floor are they on?"),
    ("tanya", "Mrs. Alvarez is on five in a walk-up. She's eighty-one, on home oxygen. The Okafors on three have a three-week-old. Mr. James on two is in a power wheelchair, and the elevator's out."),
    ("village", "Who only has a landline? And where do people go to make calls?"),
    ("tanya", "Mrs. Alvarez only has her landline. Ramírez Deli on the corner has its own generator and ice. People call there."),
    ("village", "Who can help, with what?"),
    ("tanya", "Darnell's generator is a two-thousand-watt inverter, about six hours of fuel, outdoors only. Priya's car has A/C and fits three."),
    ("village", "If someone can't breathe or passes out, what's the rule?"),
    ("tanya", "Nine one one first, then me. Nobody waits for me."),
    ("village", "Here's the draft: five households, two volunteers, the deli as the phone point, and nine one one first. Anything wrong?"),
    ("tanya", "Looks right. Send it."),
]
VOICES = {"tanya": TANYA_VOICE, "village": LUZ_VOICE}


def tts(client: httpx.Client, voice: str, text: str) -> tuple[bytes, float]:
    r = client.post(
        f"/text-to-speech/{voice}/with-timestamps",
        params={"output_format": "mp3_44100_128"},
        json={"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.45, "similarity_boost": 0.8}},
    )
    r.raise_for_status()
    body = r.json()
    ends = (body.get("alignment") or {}).get("character_end_times_seconds") or [0.0]
    return base64.b64decode(body["audio_base64"]), float(ends[-1])


def duration(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)], capture_output=True, text=True, check=True)
    return float(out.stdout.strip())


def build(out_dir: Path = OUT_DIR, name: str = "w147_founding") -> dict:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY missing")
    out_dir.mkdir(parents=True, exist_ok=True)
    timeline: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp, httpx.Client(base_url="https://api.elevenlabs.io/v1", headers={"xi-api-key": key}, timeout=120) as client:
        tmpd = Path(tmp)
        gap = tmpd / "gap.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(GAP_S), "-c:a", "libmp3lame", "-b:a", "128k", str(gap)], check=True)
        parts: list[Path] = []
        t = 0.0
        for i, (speaker, text) in enumerate(SCRIPT):
            audio, _spoken = tts(client, VOICES[speaker], text)
            seg = tmpd / f"seg{i:02d}.mp3"
            seg.write_bytes(audio)
            timeline.append({"t_ms": int(round(t * 1000)), "speaker": speaker, "text": text})
            t += duration(seg)
            parts.append(seg)
            if i < len(SCRIPT) - 1:
                parts.append(gap)
                t += duration(gap)
        listing = tmpd / "list.txt"
        listing.write_text("".join(f"file '{p}'\n" for p in parts))
        mp3 = out_dir / f"{name}.mp3"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing), "-ac", "1", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "96k", str(mp3)], check=True)
    total = duration(mp3)
    (out_dir / f"{name}.timeline.json").write_text(json.dumps(timeline, indent=2, ensure_ascii=False) + "\n")
    if total > MAX_S:
        print(f"WARNING: {total:.1f}s > {MAX_S}s; condense SCRIPT", file=sys.stderr)
    return {"mp3": str(mp3), "seconds": round(total, 1), "lines": len(timeline)}


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
    load_dotenv(Path.home() / "village" / ".env")
    print(json.dumps(build(), indent=2))
