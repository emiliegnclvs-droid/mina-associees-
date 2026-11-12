"""Calcule le minutage du Reel d'après la durée réelle de chaque phrase de voix off,
puis réécrit index.html (scènes + pistes audio), les constantes K de chaque scène et la musique.
Usage : python3 tools/minutage.py   (depuis reel-bouthier/)"""
import json, re, subprocess

def dur(p):
    return float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p]).decode())

V = {i: dur(f"assets/voice/{i}.wav") for i, _ in json.load(open("tools/lignes.json"))}
voix = []          # (id, début absolu)
scenes = []        # (id, début, durée)
K = {}
r = lambda x: round(x, 2)

# 1. Intro
t0 = 0; voix.append(("a1", 0.4))
D = max(3.8, 0.4 + V["a1"] + 0.4); scenes.append(("intro", t0, D)); K["intro"] = {"D": r(D)}
# 2. Équipe (prisme)
t0 += D; t = 0.45; loc = {}
for i, gap in [("b1", 0.05), ("b2", 0.15), ("b3", 0.05), ("b4", 0.2), ("b5", 0)]:
    loc[i] = t; voix.append((i, t0 + t)); t += V[i] + gap
D = t + 0.7; scenes.append(("equipe", t0, D))
K["equipe"] = {"D": r(D), "r1": r(loc["b2"] - 0.2), "r2": r(loc["b3"] - 0.2), "r3": r(loc["b4"] - 0.2), "pin": r(loc["b5"] - 0.15)}
# 3. Métiers (carrousel)
t0 += D; t = 0.55; T = []
for k in range(1, 9):
    i = f"c{k}"; T.append(r(t)); voix.append((i, t0 + t + 0.05)); t += max(1.15, V[i] + 0.3)
D = t + 0.35; scenes.append(("metiers", t0, D)); K["metiers"] = {"D": r(D), "T": T}
# 4. Écrans (ordinateur puis téléphone)
t0 += D; voix.append(("d1", t0 + 0.4)); L = 0.4 + V["d1"] + 0.4
voix.append(("d2", t0 + L + 0.3)); D = L + 0.3 + V["d2"] + 0.8
scenes.append(("ecrans", t0, D)); K["ecrans"] = {"D": r(D), "L": r(L), "url": 1.5, "ig": r(L + 0.35 + V["d2"] * 0.75)}
# 5. Chantiers
t0 += D; voix.append(("e1", t0 + 0.35)); D = max(3.4, 0.35 + V["e1"] + 0.6)
scenes.append(("chantiers", t0, D)); K["chantiers"] = {"D": r(D), "b1": 0.3, "b2": r(0.35 + V["e1"] * 0.45)}
# 6. Fin
t0 += D; voix.append(("f1", t0 + 0.3)); f2 = 0.3 + V["f1"]
D = f2 + 3.4; scenes.append(("fin", t0, D)); K["fin"] = {"D": r(D), "devis": r(0.3), "tel": r(f2 + 0.15)}
TOTAL = r(t0 + D)

for sid, k in K.items():
    p = f"compositions/{sid}.html"; s = open(p).read()
    s = re.sub(r"/\*K\*/.*?/\*K\*/", "/*K*/" + json.dumps(k) + "/*K*/", s, flags=re.S); open(p, "w").write(s)

h = open("index.html").read()
h = re.sub(r'(id="main" data-start="0" data-duration=")[0-9.]+', lambda m: m.group(1) + str(TOTAL), h)
for sid, a, d in scenes:
    h = re.sub(r'(<div id="%s" data-composition-id="%s" data-composition-src="[^"]+"\s+data-start=")[0-9.]+(" data-duration=")[0-9.]+' % (sid, sid),
               lambda m: m.group(1) + str(r(a)) + m.group(2) + str(r(d)), h)
h = re.sub(r'(<div id="cadre"[^>]*?data-duration=")[0-9.]+', lambda m: m.group(1) + str(TOTAL), h, flags=re.S)
# Pistes audio : voix, musique, bruitages calés sur les coupes.
h = re.sub(r"\n\s*<audio id=\"(voix|musique|sfx)[^\n]*</audio>", "", h)
starts = [a for _, a, _ in scenes]
sfx = [("sfx-w1", "whoosh.mp3", starts[1] - 0.15, 0.5, 5), ("sfx-w2", "whoosh-short.mp3", starts[2] - 0.1, 0.5, 5),
       ("sfx-w3", "whoosh-cinematic.mp3", starts[3] - 0.15, 0.45, 6), ("sfx-w4", "whoosh.mp3", starts[3] + K["ecrans"]["L"] - 0.25, 0.5, 5),
       ("sfx-w5", "whoosh-short.mp3", starts[4] - 0.1, 0.5, 6), ("sfx-impact", "impact-bass-1.mp3", starts[5] + 0.05, 0.6, 5)]
tags = [f'      <audio id="musique" class="clip" src="assets/bgm/musique.wav" data-duration="{TOTAL}" data-start="0" data-track-index="4" data-volume="0.3"></audio>']
tags += [f'      <audio id="voix-{i}" class="clip" src="assets/voice/{i}.wav" data-duration="{r(V[i]) if False else round(V[i],3)}" data-start="{r(a)}" data-track-index="3" data-volume="1.2"></audio>' for i, a in voix]
tags += [f'      <audio id="{i}" class="clip" src="assets/sfx/{f}" data-duration="{round(dur("assets/sfx/" + f), 3)}" data-start="{r(a)}" data-track-index="{tr}" data-volume="{v}"></audio>' for i, f, a, v, tr in sfx]
h = h.replace("    </div>\n    <script>", "\n".join(tags) + "\n    </div>\n    <script>", 1)
open("index.html", "w").write(h)

# Musique : la boucle générée est enchaînée en fondu jusqu'à la durée totale.
n = int(TOTAL // 22) + 2
inp = sum([["-i", "assets/bgm/source-musicgen.wav"] for _ in range(n)], [])
chain, last = [], "[0]"
for k in range(1, n):
    out = f"[x{k}]"; chain.append(f"{last}[{k}]acrossfade=d=2:c1=tri:c2=tri{out}"); last = out
chain.append(f"{last}atrim=0:{TOTAL},afade=t=in:d=0.3,afade=t=out:st={TOTAL-2.8}:d=2.8,loudnorm=I=-14:TP=-1.5:LRA=7,aresample=44100[o]")
subprocess.run(["ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", ";".join(chain), "-map", "[o]", "-ac", "2", "assets/bgm/musique.wav"], check=True)
print("total", TOTAL); [print(s) for s in scenes]; print(json.dumps(K))
