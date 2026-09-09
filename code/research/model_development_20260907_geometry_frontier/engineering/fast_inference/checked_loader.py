"""Optional authenticated loader; parse the exact model bytes verified once."""
from pathlib import Path
import hashlib,json
from prepared import MANIFEST_SHA256,prepare

def load_prepared_checked(directory,expected_manifest_sha256=MANIFEST_SHA256):
    """Prepare unchanged inference from verified bytes, without a model reread.

    The manifest digest is the trust anchor. A caller override must come from an
    independently trusted source, not an untrusted neighboring manifest file.
    """
    directory=Path(directory)
    raw_manifest=(directory/'manifest.json').read_bytes()
    if hashlib.sha256(raw_manifest).hexdigest()!=expected_manifest_sha256:
        raise ValueError('Manifest authentication failed')
    manifest=json.loads(raw_manifest)
    verified_model_bytes=None
    for name,expected in manifest['package_hashes'].items():
        if Path(name).name!=name:raise ValueError('Invalid manifest member path')
        content=(directory/name).read_bytes()
        if hashlib.sha256(content).hexdigest()!=expected:
            raise ValueError('Package hash mismatch: '+name)
        if name=='experimental_policies.json':verified_model_bytes=content
    if verified_model_bytes is None:raise ValueError('Manifest has no model member')
    # Never reopen the path after verification: the on-disk package may change,
    # but it cannot substitute bytes into this already-authenticated model.
    return prepare(json.loads(verified_model_bytes))
