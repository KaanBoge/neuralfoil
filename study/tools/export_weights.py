"""Export all 8 NeuralFoil nets + input scaling to flat f32 .bin files + manifest,
for in-browser inference on the site."""
import json, os
import numpy as np
OUT = 'nfweights'
os.makedirs(OUT, exist_ok=True)
import neuralfoil
base = os.path.join(os.path.dirname(neuralfoil.__file__), 'nn_weights_and_biases')
manifest = {}
for f in sorted(os.listdir(base)):
    if not f.endswith('.npz'): continue
    d = np.load(os.path.join(base, f))
    name = f[:-4]
    entry = []
    blob = b''
    for k in d.files:
        a = np.ascontiguousarray(d[k].astype('<f4'))
        entry.append({'name': k, 'shape': list(a.shape), 'offset': len(blob) // 4})
        blob += a.tobytes()
    with open(os.path.join(OUT, name + '.bin'), 'wb') as fh:
        fh.write(blob)
    manifest[name] = {'file': name + '.bin', 'tensors': entry, 'floats': len(blob) // 4}
    print(f"{name}: {len(blob)/1e6:.2f} MB, {len(entry)} tensors")
json.dump(manifest, open(os.path.join(OUT, 'manifest.json'), 'w'))
print("done")
