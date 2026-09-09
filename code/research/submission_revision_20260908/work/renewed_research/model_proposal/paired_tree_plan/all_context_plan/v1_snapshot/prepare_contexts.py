"""Finite metadata-only named-model registry; never opens any model NPZ."""
import adapter as a

def main():
    ledger=[]
    a.read(a.HERE/'PROTOCOL_DRAFT.md','61077ab1e5470c5ba7bff35ec6c6bee9872923d7185005c7f62f29eee97d76cf',ledger)
    manifest=a.json_read(a.ROOT/a.MANIFEST,a.MANIFEST_SHA,ledger)
    rows=[{'context':ctx,'member':f'arrays/tree_{2*i+1:02d}_capped.npz','sha256':manifest['files'][f'arrays/tree_{2*i+1:02d}_capped.npz']} for i,ctx in enumerate(a.CONTEXTS)]
    a.verify_contexts(rows,manifest)
    print(a.save(a.HERE/'CONTEXTS.json',rows))
    a.save(a.HERE/'CONTEXT_METADATA_RECEIPT.json',{'model_arrays_opened':0,'ledger':ledger})

if __name__=='__main__':main()
