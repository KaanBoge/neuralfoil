"""Portable source adapters and exact comparison inventory; no data on import."""
import ast,io,json,sys,types
import numpy as np
import pandas as pd
import integrity
PARENT_SHA='673258868620ac2a383fa45cec9347a76680fb244b2dfd8a07010c1ac8d75ac3'
PARENT_MANIFEST='3d3c909cf96b8c36b68fae2bc73a33e4f50896e66bea19af13488c70e5bd4154'
LABELS=['qualified_structural_kl_harm_001','qualified_generic_kl_harm_001']
OLD=['qualified_structural_harm_001','qualified_generic_harm_001']
EXT=['SG_exposed','W_new_challenge']
COUNTS={'panel_metrics':527,'bootstrap':238,'group_metrics':3162,'harm_metrics':4743,
    'expected_harm_metrics':527,'bundle_harm_metrics':10336,'intervention_metrics':62,
    'candidate_summary':17,'decisions':2,'all_row_predictions':29856}
def module(name,raw,bindings=None):
    m=types.ModuleType(name);sys.modules[name]=m
    if bindings:m.__dict__.update(bindings)
    exec(compile(raw,name,'exec'),m.__dict__);return m
def extract(raw,names):
    source=raw.decode();nodes={n.name:n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
    parts=[ast.get_source_segment(source,nodes[k]) for k in names]
    witness={k:integrity.sha(ast.dump(nodes[k],include_attributes=False).encode()) for k in names}
    return '\n\n'.join(parts)+'\n',witness
def arrays(raw,ledger,name,keys=None):
    with np.load(io.BytesIO(raw),allow_pickle=False) as z:
        out={}
        for k in z.files if keys is None else keys:
            out[k]=z[k]
            if out[k].dtype.hasobject:raise ValueError('object array')
            ledger.append({'file':name,'sha256':integrity.sha(raw),'member':k,'shape':list(out[k].shape),'dtype':str(out[k].dtype)})
    return out
class Reader:
    """Read/parse authenticated immutable buffers with explicit parser events."""
    def __init__(self,buffers,ledger,origin):
        self.buffers=buffers;self.ledger=ledger;self.origin=origin
        self.hashes={k:integrity.sha(v) for k,v in buffers.items()}
    def raw(self,name,operation):
        raw=self.buffers[name]
        if integrity.sha(raw)!=self.hashes[name]:raise ValueError('buffer changed')
        self.ledger.append({'origin':self.origin,'file':name,'sha256':self.hashes[name],'operation':operation})
        return raw
    def json(self,name):return json.loads(self.raw(name,'JSON parse'))
    def csv(self,name):return pd.read_csv(io.BytesIO(self.raw(name,'pandas.read_csv')),low_memory=False)
    def arrays(self,name,keys=None):return arrays(self.raw(name,'NPZ open'),self.ledger,self.origin+'/'+name,keys)
    def code(self,name):return self.raw(name,'source execution')
def validate_roles(z,role):
    for a,b in [('proper_groups','calibration_groups'),('proper_groups','test_groups'),('calibration_groups','test_groups')]:
        if set(role[a])&set(role[b]):raise ValueError('role overlap')
    np.testing.assert_array_equal(z['indices'],role['calibration_indices'])
    np.testing.assert_array_equal(z['nf2_row_id'],role['calibration_nf2_row_ids'])
def scalar_equal(actual,expected,codec):
    if json.loads(json.dumps(actual,default=codec.encode))!=expected:raise ValueError('complete KL scalar witness mismatch')
def native_equal(actual,expected):
    if set(actual)!=set(expected):raise ValueError('native schema')
    for k,v in actual.items():np.testing.assert_array_equal(v,expected[k])
def engines(parent,addon):
    q=module('qualified_numerics',parent.code('code/qualified_numerics.py'))
    codec=module('codec',parent.code('code/codec.py'));n=module('parent_policy',parent.code('code/policy.py'))
    klraw=addon.code('code/exact_kl.py');kl=module('exact_kl',klraw)
    c=module('kl_adapter',addon.code('code/adapter.py'),{'kl':kl,'kl_raw':klraw,'n':n})
    frame=module('frame_codec',parent.code('code/frame_codec.py'))
    overlay=module('typed_overlay',addon.code('code/overlay.py'))
    metrics=module('metrics',parent.code('code/metrics.py'))
    metrics.CONTROLS=list(metrics.LABELS);metrics.CANDIDATES=LABELS;metrics.LABELS=LABELS+metrics.CONTROLS
    metrics.REFERENCES=['unpenalized_transfer','half_strength','proper_capped_half','qualified_matched_half',OLD[1],OLD[0],LABELS[1]]
    metrics.run=types.SimpleNamespace(LABELS=LABELS,EXTERNAL=EXT)
    assert len(metrics.REFERENCES)==7 and len(metrics.REFERENCES+metrics.BASELINES)==9
    return q,codec,n,c,frame,overlay,metrics
def exact_field(col):
    return col in {'rows','groups','assignment','draws','seed','index','indices','nf2_row_id','identity_count','interventions','physical_eligible_rows','qualified_eligible_rows'} or col.endswith(('_rows','_groups','_count')) or 'negative_groups' in col or 'negative_pairs' in col
def compare_tables(name,table,raw,ledger=None,difference_sink=None):
    if ledger is not None:ledger.append({'origin':'computed output','file':name,'operation':'self serialization and pandas.read_csv; not source input'})
    actual=pd.read_csv(io.StringIO(table.to_csv(index=False)),low_memory=False)
    expected=pd.read_csv(io.BytesIO(raw),low_memory=False)
    if list(actual.columns)!=list(expected.columns) or len(actual)!=COUNTS[name] or len(expected)!=len(actual):raise ValueError('table inventory')
    diff=[] if difference_sink is None else difference_sink
    for col in actual:
        x,y=actual[col],expected[col]
        if pd.api.types.is_bool_dtype(y):
            pd.testing.assert_series_equal(x,y,check_names=False)
        elif exact_field(col) or pd.api.types.is_integer_dtype(y):
            if x.dtype==bool or not pd.api.types.is_numeric_dtype(x):raise ValueError('integer/ID schema mismatch')
            if not np.array_equal(x.to_numpy(),y.to_numpy(),equal_nan=True):
                for i in np.flatnonzero((x.to_numpy()!=y.to_numpy())&~x.isna().to_numpy()):
                    diff.append({'table':name,'column':col,'row':int(i),'actual':float(x.iloc[i]),'expected':float(y.iloc[i]),
                        'difference':float(x.iloc[i]-y.iloc[i]),'within_inherited_audit_tolerance':False,'known_zero_sign_diagnostic':False,'requires_review':True,'hard_exact_field_failure':True})
                raise ValueError('exact integer/ID mismatch')
        elif pd.api.types.is_numeric_dtype(x) and x.dtype!=bool:
            np.testing.assert_array_equal(x.isna(),y.isna())
            for i in np.flatnonzero((x.to_numpy()!=y.to_numpy())&~x.isna().to_numpy()):
                if name=='all_row_predictions':raise ValueError('typed overlay expected row mismatch')
                zero_exception=(name=='bootstrap' and col=='bootstrap_fraction_benefit_positive'
                    and actual.iloc[i]['candidate']=='calibrated_incremental_harm_001'
                    and actual.iloc[i]['reference']=='qualified_generic_harm_001'
                    and int(actual.iloc[i]['assignment']) in [20260906,20260908])
                if zero_exception:
                    old_pair={20260906:(.66475,.6031),20260908:(.6952,.69405)}[int(actual.iloc[i]['assignment'])]
                    zero_exception=(float(y.iloc[i]),float(x.iloc[i]))==old_pair
                # Inherited independent-audit tolerance; every cell remains inventoried.
                within=bool(np.isclose(float(x.iloc[i]),float(y.iloc[i]),atol=2e-10,rtol=2e-12))
                diff.append({'table':name,'column':col,'row':int(i),'actual':float(x.iloc[i]),'expected':float(y.iloc[i]),
                    'difference':float(x.iloc[i]-y.iloc[i]),'within_inherited_audit_tolerance':within,
                    'known_zero_sign_diagnostic':zero_exception,'requires_review':not within or zero_exception})
        else:pd.testing.assert_series_equal(x,y,check_names=False)
    return diff
