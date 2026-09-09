import numpy as np
import pandas as pd
NEW_LABELS=['qualified_structural_kl_harm_001', 'qualified_generic_kl_harm_001']
EXTERNAL=['SG_exposed', 'W_new_challenge']
def overlay(frame,predictions):
    """Only new columns; preserve inherited alignment rule and all old typed cells."""
    original=frame.copy(deep=True)
    if set(predictions)!=set(frame.split.unique()):raise ValueError('overlay split inventory')
    for split in frame.split.unique():
        f=predictions[split];mask=frame.split.eq(split);old=frame.loc[mask]
        if len(old)!=len(f):raise ValueError('split length')
        if split not in EXTERNAL:
            if f.nf2_row_id.duplicated().any() or old.nf2_row_id.duplicated().any():raise ValueError('duplicate score ID')
            if set(f.nf2_row_id)!=set(old.nf2_row_id):raise ValueError('score ID mismatch')
            f=f.set_index('nf2_row_id').loc[old.nf2_row_id].reset_index()
        else:np.testing.assert_array_equal(f['indices'],np.arange(len(f)))
        np.testing.assert_allclose(f.BASE_CD,old.mean8_CD,rtol=0,atol=1e-13)
        for label in NEW_LABELS:
            for key in [label,label+'__effective_fraction',label+'__strength',label+'__intervened']:
                frame.loc[mask,key]=f[key].to_numpy()
    pd.testing.assert_frame_equal(frame[original.columns],original,check_exact=True)
    return frame
