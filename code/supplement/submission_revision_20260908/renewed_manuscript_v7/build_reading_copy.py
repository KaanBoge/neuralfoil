"""Build the exact, marker-free Markdown reading artifact from pinned inputs."""
from pathlib import Path
import hashlib
import json
import sys

HERE = Path(__file__).resolve().parent
HELPERS = HERE.parent / 'work/renewed_research/independent_environment/final_qa_tools'
HELPER_PIN = 'e61d1024315fd29f5b0efc1a6a2707d9b525fa2381a75ed3517e0c70254852dc'
SOURCE_PIN = 'd606685bebc00dd78ef48b28bde620fc8ddcf3d132d9745a56f20c8fba45cfa7'
MAP_PIN = '65f7b8ae2fe38fe39d0e6fc432e122070111080eae7b9f343d4af6b6d8a86580'
READING_PIN = '1ca782b231a4793d4c87c243c87624963b58815eba53a212351a2024c1521b5c'

def checked(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Changed input: ' + str(path))
    return raw

def main():
    checked(HELPERS / 'finalize_v7_v3.py', HELPER_PIN)
    sys.path.insert(0, str(HELPERS))
    from finalize_v7_v3 import reading_source_bytes
    config = json.loads((HERE / 'work/ROOT_FINAL_QA_CONFIG_v2.json').read_bytes())
    source = checked(HERE / 'supplement.complete.md', SOURCE_PIN)
    page_map = json.loads(checked(HERE / 'work/render_supplement/v8/PAGE_MAP.json', MAP_PIN))
    result = reading_source_bytes('supplement', source, config['documents']['supplement']['toc_labels'], page_map)
    if hashlib.sha256(result).hexdigest() != READING_PIN:
        raise ValueError('Reading copy differs from reviewed deterministic output')
    with (HERE / 'supplement.reading.md').open('xb') as stream:
        stream.write(result)
    print(json.dumps({'status': 'GENERATED_EXACT_READING_COPY', 'sha256': READING_PIN, 'bytes': len(result)}))

if __name__ == '__main__':
    main()
