"""Authenticated caller only. Original loader, request-local service substitute."""
import loader_v5
from serving_optimized import Serving
from response_snapshot import ResponseSnapshot

def load(root,registry,route=None,with_references=False,access=None):
    original,refs,runtime,access,runtime_pins=loader_v5.load(root,registry,route,with_references,access)
    optimized=Serving(original.f,original.asb,original.original,original.qualified,original.policy,original.q,original.scalars,ResponseSnapshot(original.workload).copy())
    return optimized,refs,runtime,access,runtime_pins,original

finish=loader_v5.finish

def references(registry,access):
    """Only approved V6 normal-reference members; no candidate selection."""
    result={}
    for route,spec in registry['v6_reference_files'].items():
        result[route]=access.arrays(access.file(spec['path']),spec['path'],spec['members'])
    return result

def authenticate_legacy(registry,access):
    # Metadata identities are pinned by the new approval-bound registry.
    for path in registry['legacy_metadata_paths']:access.file(path)
