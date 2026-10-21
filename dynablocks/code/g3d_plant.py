"""Plant a known text into a thumbnail window (model prediction + Gaussian noise) for feasibility tests.
    python3 g3d_plant.py THUMB BG FNT calib.json "text" x y size r0 r1 c0 c1 noise_mse OUT.png"""
import json, sys
import numpy as np
from PIL import Image
import g3d_text as G, g3d_font as GF
thumb, bg, fnt, cj, text = sys.argv[1:6]; x, y, size = map(float, sys.argv[6:9]); r0, r1, c0, c1 = map(int, sys.argv[9:13]); nm = float(sys.argv[13]); out = sys.argv[14]
gf = GF.Font(fnt); C = json.load(open(cj)); K = np.array(C["coef"]); M = G.Model(thumb, bg, fnt); W = (r0, r1, c0, c1)
_, _, pred = M.solve([M.feats_g3d(text, x, y, size, W, gf, C["bw"], C["mode"])], W, K)
T = M.T.copy(); T[r0:r1, c0:c1] = pred + np.random.default_rng(3).normal(0, nm ** 0.5, pred.shape)
Image.fromarray(np.clip(T, 0, 255).astype(np.uint8)).save(out)
