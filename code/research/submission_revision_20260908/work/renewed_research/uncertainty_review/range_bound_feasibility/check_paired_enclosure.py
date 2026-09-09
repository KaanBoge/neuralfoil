"""Fixed independent synthetic sequence-containment checks; no trees."""
from pathlib import Path
from fractions import Fraction as F
import importlib.util,itertools,random,math,json,hashlib
HERE=Path(__file__).resolve().parent;P=HERE.parents[1]/'feature_relation_certification/paired_enclosure.py'
s=importlib.util.spec_from_file_location('paired',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def main():
    rng=random.Random(202609081901);cases=0;paths=0
    for _ in range(256):
        initial=rng.uniform(-1,1)
        stages=[[math.ldexp(float(rng.randrange(-7,8)),rng.randrange(-1074,30)) for j in range(2)] for i in range(8)]
        full=[list(itertools.product(stages[i],stages[i+1])) for i in range(0,8,2)]
        subset=[block[::2] for block in full]
        x=m.enclose(initial,subset);y=m.enclose(initial,full)
        assert y['lower']<=x['lower']<=x['upper']<=y['upper']
        for path in itertools.product(*subset):
            v=initial
            for pair in path:
                for value in pair:v=float(F(v)+F(value))
            assert x['lower']<=F(v)<=x['upper'];paths+=1
        # Check each directed result is not merely safe but the nearest outward endpoint.
        for q in [F(initial)+F(stages[0][0]),F(initial)+F(stages[-1][-1])]:
            lo=m._directed(q,False);hi=m._directed(q,True)
            assert lo<=q<=hi
            assert F(math.nextafter(float(lo),math.inf))>q
            assert F(math.nextafter(float(hi),-math.inf))<q
        cases+=1
    return {'status':'PASS','cases':cases,'explicit_RN_paths':paths,'seed':202609081901,'source_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'scope':'pure supplied sequences; no compatibility extraction or real data'}
if __name__=='__main__':
    r=main()
    with (HERE/'PAIRED_ENCLOSURE_QA.json').open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
