"""Exact V8 navigation-only reading copy; preview before explicit hash-bound write."""
from pathlib import Path
import argparse
import hashlib
import json
import types

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
HELPER = HERE.parent / 'work/renewed_research/independent_environment/final_qa_tools/finalize_v7_v3.py'
def check(p, pin):
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('changed input ' + str(p))
    return raw
def main(expected=None):
    source = check(HERE / 'supplement.complete.md', 'cd1fd7942bd7dbf1881a6012d8c90de5726315f45d0c97b7651e0bf709c81157')
    page_map = json.loads(check(HERE / 'work/render_supplement/v3/PAGE_MAP.json', 'bcb671f228e95e0fe7195d7299810d0c5fae44b4b7f0590d69f1aa6e9f6664a9'))
    prior = json.loads(check(HERE.parent / 'renewed_manuscript_v7/work/ROOT_FINAL_QA_CONFIG_v3.json', 'cbd25ed36e0f1527e96d811bd990b79ffb46ed0f23515d53c704f78f97af654f'))
    labels = prior['documents']['supplement']['toc_labels']
    helper = types.ModuleType('reading_helper'); helper.__file__ = str(HELPER)
    exec(compile(check(HELPER, 'e61d1024315fd29f5b0efc1a6a2707d9b525fa2381a75ed3517e0c70254852dc'), str(HELPER), 'exec'), helper.__dict__)
    raw = helper.reading_source_bytes('supplement', source, labels, page_map)
    pin = hashlib.sha256(raw).hexdigest()
    receipt = dict(status='PREVIEW_ONLY' if expected is None else 'GENERATED_EXACT_READING_COPY',
                   sha256=pin, bytes=len(raw), toc={label:page_map[heading] for heading,label in labels.items()},
                   source_sha256=hashlib.sha256(source).hexdigest(), builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if expected is not None:
        if expected != pin:
            raise ValueError('reviewed deterministic reading hash mismatch')
        with (HERE / 'supplement.reading.md').open('xb') as f:
            f.write(raw)
        with (HERE / 'work/READING_COPY.json').open('x') as f:
            json.dump(receipt, f, indent=2); f.write('\n')
    print(json.dumps(receipt, indent=2))
if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--expected-sha256'); a = p.parse_args()
    main(a.expected_sha256)
