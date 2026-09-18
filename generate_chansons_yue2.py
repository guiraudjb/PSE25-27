#!/usr/bin/env python3
"""Génère les chansons reggae PSE25-27 manquantes localement via YuE2, en
remplacement de Suno (bloqué par le quota mensuel de téléchargement — voir
memory chansons-suno-reggae.md). Paroles déjà écrites dans chanson/*.txt (152),
ce script ne fait que le rendu audio pour celles sans chanson/<nom>.mp3.

Sortie directe : chanson/<nom fiche>.mp3 (même convention que les MP3 Suno déjà
en place). Aucun artefact intermédiaire n'est conservé (FLAC temporaire supprimé
après conversion).

Usage (avec le venv YuE2, PAS le python système) :
    /home/adm1/RAID/aitools/YuE/.venv/bin/python generate_chansons_yue2.py [--limit N] [--files "03-80" ...]

--files prend le préfixe numérique du module (ex: "03-80"), pas le nom complet.
"""
import argparse
import glob
import hashlib
import subprocess
import sys
import tempfile
import time
from pathlib import Path

CHANSON_DIR = Path("chanson")
STYLE = ("French, roots reggae, laid-back male lead vocal, offbeat guitar chop, "
         "warm bassline, one-drop drums, organ bubble, relaxed groove, 76 BPM")


def stable_seed(name: str) -> int:
    return int(hashlib.sha256(name.encode()).hexdigest()[:8], 16) % (2**31)


def module_id(txt_path: Path) -> str:
    # "03-80 Stratégie ...txt" -> "03-80" (id doit rester alphanumérique/-/_/.)
    return txt_path.stem.split(" ", 1)[0]


def lyrics_body(txt_path: Path) -> str:
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[1:]).strip()  # sans la ligne "TITRE : ..."


def generate_one(pipe, txt_path: Path) -> bool:
    base = txt_path.stem
    mp3_path = CHANSON_DIR / f"{base}.mp3"
    if mp3_path.exists():
        print(f"[skip] {base} (déjà généré)")
        return True
    seed = stable_seed(base)
    print(f"[start] {base} (seed={seed})", flush=True)
    t0 = time.time()
    try:
        song = pipe(style=STYLE, lyrics=lyrics_body(txt_path), id=module_id(txt_path),
                    seed=seed, cot="full")
    except Exception as exc:
        print(f"[FAIL] {base}: {exc}")
        return False
    elapsed = time.time() - t0
    truncated = song.truncated
    if any(truncated.values()):
        print(f"[WARN] {base}: génération tronquée ({truncated}) — à vérifier à l'écoute")
    with tempfile.NamedTemporaryFile(suffix=".flac", delete=True) as tmp:
        song.save(tmp.name)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp.name,
                        "-codec:a", "libmp3lame", "-qscale:a", "2", str(mp3_path)], check=True)
    duration = len(song.audio) / song.sample_rate
    print(f"[done] {base} audio={duration:.1f}s elapsed={elapsed:.1f}s", flush=True)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--files", nargs="*", default=None, help="préfixes numériques de module, ex: 03-80")
    args = ap.parse_args()

    if args.files:
        files = []
        for prefix in args.files:
            matches = sorted(glob.glob(str(CHANSON_DIR / f"{prefix} *.txt")))
            if not matches:
                print(f"[FAIL] aucun fichier trouvé pour préfixe {prefix!r}")
                sys.exit(2)
            files.append(Path(matches[0]))
    else:
        files = sorted(CHANSON_DIR.glob("*.txt"))
        if args.limit:
            files = files[: args.limit]

    from yue2 import YuE2Pipeline
    print("Chargement du pipeline YuE2 (modèle + décodeur)...", flush=True)
    with YuE2Pipeline.from_pretrained("m-a-p/YuE2-3B", vae="m-a-p/YuE2-Vae", device="cuda") as pipe:
        print(f"=== {len(files)} chanson(s) à traiter ===", flush=True)
        t0 = time.time()
        failures = 0
        for f in files:
            if not generate_one(pipe, f):
                failures += 1
        print(f"=== terminé en {time.time()-t0:.1f}s ({failures} échec(s)) ===")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
