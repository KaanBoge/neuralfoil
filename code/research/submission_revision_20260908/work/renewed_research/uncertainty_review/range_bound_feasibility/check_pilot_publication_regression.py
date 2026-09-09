"""Synthetic complete-state publication check; never loads exported models."""
from pathlib import Path
import hashlib,importlib.util,json,sys,tempfile,traceback
HERE=Path(__file__).resolve().parent
PILOT=HERE.parents[1]/'tree_range_refinement'
sys.path.insert(0,str(PILOT))
import test_pilot as t
def main():
    model=t.E.SequentialHist(t.arrays([t.stump(),t.stump(10.,0.)]),required_stages=2)
    states=[]
    t.engine.refine(model.stages,0.,t.Q.sequential_range,t.engine.Limits(model.stages),states.append,splits=1)
    result={'source_sha256':{n:hashlib.sha256((PILOT/n).read_bytes()).hexdigest() for n in ['pilot_engine.py','pilot_runner.py','pilot_checker.py']},'synthetic_only':True,'states':len(states)}
    with tempfile.TemporaryDirectory() as d:
        out=Path(d)/'candidate.json'
        try:t.exclusive_json(out,states[0])
        except TypeError as e:
            result.update(status='PUBLICATION_SERIALIZATION_BLOCKER_REPRODUCED',exception=str(e),partial_exists=Path(str(out)+'.partial').exists(),completed_exists=out.exists())
        else:
            value=json.loads(out.read_text());t.checker.replay(value,model.stages,0.,t.Q.sequential_range)
            result.update(status='PASS_SYNTHETIC_PUBLICATION_AND_REPLAY')
    return result
if __name__=='__main__':
    out=HERE/'PILOT_PUBLICATION_REGRESSION.json';assert not out.exists()
    r=main()
    with out.open('x') as f:json.dump(r,f,indent=2)
    print(json.dumps(r,indent=2))
