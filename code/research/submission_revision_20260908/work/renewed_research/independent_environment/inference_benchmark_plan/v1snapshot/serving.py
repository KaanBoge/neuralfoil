"""Source-only seven-route adapter. Dependencies supplied after authentication."""
import numpy as np

QUALIFIED=('qualified_generic_harm_001','qualified_structural_harm_001',
           'qualified_generic_kl_harm_001','qualified_structural_kl_harm_001')
ROUTES=('native_xlarge_raw_and_quantized6','native_mean8_raw_and_per_size_quantized6',
        'original_unpenalized_transfer_quantized_teacher',*QUALIFIED)
COHORTS=('SG_exposed','W_new_challenge')

def exact(actual,expected):
    if set(actual)!=set(expected):raise ValueError('fidelity key mismatch')
    for k,a in actual.items():
        a=np.asarray(a);b=np.asarray(expected[k])
        if a.shape!=b.shape or a.dtype!=b.dtype or not np.array_equal(a,b):
            raise ValueError('exact fidelity mismatch: '+k)

class Serving:
    def __init__(self,math,asb,original,qualified,policy,q,scalars,workload):
        self.f,self.asb,self.original,self.qualified=math,asb,original,qualified
        self.policy,self.q,self.scalars,self.workload=policy,q,scalars,workload

    def features(self,w):
        f=self.f;n=len(w['alpha']);output={};mat={k:np.empty((n,5)) for k in f.FIELDS};k18=np.empty((n,18))
        # Preserve manifest insertion order and original full-design call shapes.
        for name,text in w['coordinates'].items():
            coords=f.load_pts(text);ix=np.flatnonzero(w['airfoil']==name)
            kp=self.asb.Airfoil(name='shape_sensitivity',coordinates=coords).to_kulfan_airfoil().kulfan_parameters
            k18[ix]=np.r_[kp['upper_weights'],kp['lower_weights'],kp['leading_edge_weight'],kp['TE_thickness']]
            sensitivity=f.calc(coords,w['alpha'][ix],w['Re'][ix])
            for k in mat:mat[k][ix]=sensitivity[k]
            base=f.predict_base(coords,w['alpha'][ix],w['Re'][ix])
            base['all_model_CD']=base.pop('all_CD');base['all_model_CL']=base.pop('all_CL')
            for k in ('X9','X16','BASE_CD','XLARGE_CD','all_model_CD','all_model_CL'):
                if k not in output:output[k]=np.empty((n,*base[k].shape[1:]),dtype=base[k].dtype)
                output[k][ix]=base[k]
        f.add_features(output);output['K18']=k18
        output['X44']=f.supplement(output['X24'],mat)
        output['X62']=np.column_stack([output['X44'],k18])
        output.update({'ncrit_'+k:v for k,v in mat.items()})
        return output

    def native(self,w,mean8):
        n=len(w['alpha']);raw=np.empty(n);quantized=np.empty(n)
        sizes=self.f.SIZES if mean8 else ['xlarge']
        for name,text in w['coordinates'].items():
            ix=np.flatnonzero(w['airfoil']==name);coords=self.f.load_pts(text)
            foil=self.asb.Airfoil(name='external_evaluation',coordinates=coords).to_kulfan_airfoil()
            cds=np.column_stack([np.atleast_1d(foil.get_aero_from_neuralfoil(alpha=w['alpha'][ix],Re=w['Re'][ix],mach=0.,n_crit=9,model_size=s)['CD']) for s in sizes])
            formatted=np.array([[float(f'{v:.6f}') for v in row] for row in cds])
            raw[ix]=cds.mean(axis=1);quantized[ix]=formatted.mean(axis=1)
        return {'raw_CD':raw,'quantized_CD':quantized}

    def request(self,route,diagnostics=False):
        if route not in ROUTES:raise ValueError('unknown route')
        result={}
        for cohort in COHORTS:
            w=self.workload[cohort]
            if route.startswith('native_'):
                values=self.native(w,route==ROUTES[1])
            else:
                d=self.features(w);b=d['BASE_CD'];g=w['gate']
                if route==ROUTES[2]:
                    pred,strength=self.original.predict(d['X62'],b,d['all_model_CD'],g,label='unpenalized_transfer')
                    values={'CD':pred,'strength':strength}
                else:
                    raw=self.qualified.predict_raw(d['X62'])
                    core,anchor,active=self.q.guarded_core(b,raw,g)
                    s=self.scalars[route]
                    pred,effective=self.policy.predictions(s,b,core,anchor,active)
                    values={'CD':pred,'effective_fraction':effective,'strength':np.where(active,.5+.5*s['t'],0.),'intervened':abs(pred-anchor)>1e-12}
                    if diagnostics:values.update(raw=raw,core=core,anchor=anchor,gate=active)
                if diagnostics:values.update(d)
            for k,v in values.items():
                if len(v)!=len(w['alpha']):raise ValueError('output row mismatch')
                result[cohort+'/'+k]=v
        return result

