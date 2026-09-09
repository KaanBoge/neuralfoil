"""Independent output replay; no production imports, fitting or old-file writes."""
from pathlib import Path
from fractions import Fraction as F
import hashlib,json,math,time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent; PROJECT=HERE.parents[3]
OUT=HERE.parent/'measurement_sensitivity/attempt_1'
KEY=['panel','procedure','baseline','weighting','target_fraction','uncertainty_model']
PROCS=['unpenalized_transfer','half_strength','mean8_CD','xlarge_CD']
BASES=['mean8_CD','xlarge_CD']; TOL=1e-13
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def panel_map(f):
    result={}
    for seed in [20260906,20260908]:
        mask=f.split.str.startswith(f'group_{seed}_')
        result[f'history_{seed}_pooled']=np.flatnonzero(mask)
        for s in sorted(f.loc[mask,'source'].unique()):
            result[f'history_{seed}_{s}']=np.flatnonzero(mask & f.source.eq(s))
    for s in sorted(x for x in f.split.unique() if x.startswith('strict_source_')):
        result[s]=np.flatnonzero(f.split.eq(s))
    eligible=f.interval_applicable.astype(str).str.lower()
    assert set(eligible)=={'true','false'}
    for s in ['SG_exposed','W_new_challenge']:
        mask=f.split.eq(s)
        for config in [None]+sorted(f.loc[mask,'configuration'].unique()):
            m=mask if config is None else mask & f.configuration.eq(config)
            result[f'{s}_{config or "pooled"}']=np.flatnonzero(m)
            result[f'eligible_only/{s}/{config or "pooled"}']=np.flatnonzero(m & eligible.eq('true'))
    return result

def loss(b,c,y,r):return (1-r)*abs(b-y)-abs(c-y)

class DirectCurve:
    def __init__(self,b,c,y,w,r):
        self.b,self.c,self.y,self.w,self.r=b,c,y,w,r
        events={}
        for bi,ci,yi,wi in zip(b,c,y,w):
            for k,j in [(-yi,r*wi),(bi-yi,2*(1-r)*wi),(ci-yi,-2*wi)]:
                events.setdefault(k,[]).append(j)
        self.knots=np.array(sorted(events))
        jumps=np.array([math.fsum(events[k]) for k in self.knots])
        self.slopes=np.cumsum(jumps)
        const=math.fsum(w*((1-r)*b-c))
        self.values=const+self.knots*np.cumsum(jumps)-np.cumsum(jumps*self.knots)
        assert abs(self.slopes[-1]+r*w.sum())<TOL
    def direct(self,d):return math.fsum(self.w*loss(self.b,self.c,np.maximum(0,self.y+d),self.r))
    def bounds(self,eps,return_delta=False):
        mask=abs(self.knots)<=eps
        ds=np.r_[-eps,self.knots[mask],eps]
        values=np.r_[self.direct(-eps),self.values[mask],self.direct(eps)]
        lo,hi=ds[np.argmin(values)],ds[np.argmax(values)]
        return (lo,hi) if return_delta else (self.direct(lo),self.direct(hi))
    def brute_knots(self,eps):
        knots=np.r_[-eps,self.knots[abs(self.knots)<=eps],eps]
        values=[]
        for start in range(0,len(knots),128):
            t=np.maximum(0,self.y[None,:]+knots[start:start+128,None])
            values.extend(np.sum(self.w[None,:]*loss(self.b[None,:],self.c[None,:],t,self.r),axis=1))
        return (min(values),max(values)),len(knots)

def box(b,c,y,w,r,eps):
    lo=np.maximum(0,y-eps);hi=y+eps
    v=np.array([loss(b,c,t,r) for t in [lo,hi,np.clip(b,lo,hi),np.clip(c,lo,hi)]])
    return math.fsum(w*v.min(axis=0)),math.fsum(w*v.max(axis=0))

def main():
    started=time.monotonic();manifest=json.loads((OUT/'manifest.json').read_text())
    for p,h in manifest['input_sha256'].items():assert sha(p)==h,p
    for p,h in manifest['output_sha256'].items():assert sha(OUT/p)==h,p
    assert 'Ran 9 tests' in (OUT/'synthetic_tests.txt').read_text()
    source=PROJECT/'model_development_20260908_adaptive_scale/assessment'
    frame=pd.read_csv(source/'all_row_predictions.csv',low_memory=False)
    old=pd.read_csv(source/'panel_metrics.csv')
    grid=pd.read_csv(OUT/'grid.csv');radii=pd.read_csv(OUT/'radii.csv');panels=panel_map(frame)
    assert len(frame)==29856 and len(panels)==31 and len(grid)==23808 and len(radii)==2976
    assert not grid.duplicated(KEY+['epsilon_CD']).any() and not radii.duplicated(KEY).any()
    for seed in [20260906,20260908]:
        f=frame.iloc[panels[f'history_{seed}_pooled']]
        assert len(f)==f.nf2_row_id.nunique()==8371 and f.group.nunique()==93
    archived_checks=0;errors=[];large=[];rational=[];endpoints=0
    radius_lookup=radii.set_index(KEY)
    for p,ix in panels.items():
        f=frame.iloc[ix];n=len(f)
        ext=f.split.isin(['SG_exposed','W_new_challenge']).all()
        groups=(f.configuration if ext else f.group).astype(str).to_numpy()
        sources=(f.split if ext else f.source).astype(str).to_numpy()
        names,inv,counts=np.unique(groups,return_inverse=True,return_counts=True)
        assert n==old.loc[old.panel.eq(p),'rows'].iloc[0]
        pg=grid[grid.panel.eq(p)]
        assert len(pg)==768
        for proc in PROCS:
            for base in BASES:
                y=f.measured_CD.to_numpy();b=f[base].to_numpy();c=f[proc].to_numpy()
                if proc in PROCS[:2]:
                    expected=old[old.panel.eq(p)&old.candidate.eq(proc)].iloc[0]
                    gain=100*(1-np.mean(abs(c-y))/np.mean(abs(b-y)))
                    assert abs(gain-expected[base+'_improvement_percent'])<1e-8
                    archived_checks+=1
                for weighting in ['row','equal_bundle']:
                    w=np.ones(n)/n if weighting=='row' else 1/(len(names)*counts[inv])
                    for r in [0.,.09]:
                        observed=math.fsum(w*loss(b,c,y,r))
                        for mode in ['row_box','source_shift','bundle_shift']:
                            key=(p,proc,base,weighting,r,mode)
                            rows=pg[pg.procedure.eq(proc)&pg.baseline.eq(base)&pg.weighting.eq(weighting)&pg.target_fraction.eq(r)&pg.uncertainty_model.eq(mode)]
                            assert len(rows)==8
                            curves=[]
                            if mode!='row_box':
                                blocks=sources if mode=='source_shift' else groups
                                curves=[DirectCurve(b[blocks==g],c[blocks==g],y[blocks==g],w[blocks==g],r) for g in np.unique(blocks)]
                            def bounds(e):
                                if e==0:return observed,observed
                                if r==0 and np.array_equal(b,c):return 0.,0.
                                if mode=='row_box':return box(b,c,y,w,r,e)
                                values=[z.bounds(e) for z in curves]
                                return tuple(math.fsum(v[j] for v in values) for j in [0,1])
                            for row in rows.itertuples():
                                low,high=bounds(row.epsilon_CD)
                                errors.extend([abs(low-row.lower_margin_CD),abs(high-row.upper_margin_CD),abs(observed-row.observed_margin_CD)])
                                l=np.maximum(0,y-row.epsilon_CD);u=y+row.epsilon_CD
                                bm=math.fsum(w*np.maximum(np.maximum(l-b,b-u),0))
                                errors.append(abs(bm-row.box_minimum_baseline_mae_CD))
                                assert (bm>0)==row.percentage_defined_everywhere_sufficient
                            rr=radius_lookup.loc[key]
                            status=rr.radius_status
                            if observed<=0:
                                assert status==('observed_negative' if observed<0 else 'observed_zero')
                            elif status=='finite_bracket':
                                e0,e1=rr.radius_lower_CD,rr.radius_upper_CD
                                assert 0<=e0<e1<=1 and e1-e0<=1.0002e-12
                                q0,q1=bounds(e0)[0],bounds(e1)[0]
                                errors.extend([abs(q0-rr.lower_endpoint_margin_CD),abs(q1-rr.upper_endpoint_margin_CD)])
                                assert q0>=-TOL and q1<=TOL
                                assert rr.lower_endpoint_margin_CD>0 and rr.upper_endpoint_margin_CD<=0
                                endpoints+=2
                                # Exact binary-Fraction checks on four full-history row boxes.
                                if p=='history_20260906_pooled' and proc=='unpenalized_transfer' and mode=='row_box' and weighting=='row':
                                    exact=[]
                                    for ep in [e0,e1]:
                                        ep=F(float(ep));fr=F(float(r));total=F(0)
                                        for bi,ci,yi,wi in zip(b,c,y,w):
                                            bi,ci,yi,wi=map(lambda x:F(float(x)),(bi,ci,yi,wi))
                                            l=max(F(0),yi-ep);u=yi+ep
                                            total+=wi*min(loss(bi,ci,l,fr),loss(bi,ci,u,fr))
                                        exact.append(total)
                                    assert exact[0]>0 and exact[1]<=0
                                    rational.append(dict(key=list(key),lower_sign=1,upper_sign=int(np.sign(float(exact[1])))))
                            else:
                                assert status=='right_censored' and bounds(1)[0]>0
                            # Independent exhaustive direct knot evaluation on largest actual blocks.
                            if p=='history_20260906_pooled' and proc=='unpenalized_transfer' and base=='xlarge_CD' and weighting=='row' and curves:
                                curve=max(curves,key=lambda z:len(z.y))
                                eps=1.0
                                direct,knots=curve.brute_knots(eps)
                                selected=curve.bounds(eps)
                                assert max(abs(a-bb) for a,bb in zip(direct,selected))<TOL
                                large.append(dict(mode=mode,target=r,rows=len(curve.y),knots=knots,epsilon=eps,max_difference=max(abs(a-bb) for a,bb in zip(direct,selected))))
        print('audited',p,flush=True)
    assert archived_checks==124 and max(errors)<TOL
    for p,h in manifest['input_sha256'].items():assert sha(p)==h,p
    for p,h in manifest['output_sha256'].items():assert sha(OUT/p)==h,p
    result=dict(status='PASS',grid_rows=len(grid),radius_rows=len(radii),panels=len(panels),archived_checks=archived_checks,
                radius_endpoints_replayed=endpoints,max_absolute_CD_difference=max(errors),direct_large_block_checks=large,
                exact_rational_radius_checks=rational,manifest_sha256=sha(OUT/'manifest.json'),audit_sha256=sha(__file__),seconds=time.monotonic()-started)
    (HERE/'EMPIRICAL_QA.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
