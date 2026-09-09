"""Bind actual root page reviews and exact inherited PNG witnesses; no rendering."""
from pathlib import Path
import datetime
import hashlib
import json
import types

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
HELPER = HERE.parent / 'work/renewed_research/independent_environment/final_qa_tools/finalize_v7_v3.py'
REPORT = HERE / 'work/VISUAL_REVIEW_FINAL_CANDIDATES_IN_PROGRESS.md'
def check(p, pin):
    raw = p.read_bytes()
    if hashlib.sha256(raw).hexdigest() != pin:
        raise ValueError('changed witnessed file ' + str(p))
    return raw
def spec(p):
    return dict(path=str(p.relative_to(PROJECT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
def save(p, value):
    with p.open('x') as f:
        json.dump(value, f, indent=2); f.write('\n')
    return spec(p)
def main():
    check(REPORT, '4a6a368e2da92708ae33d8dabab5dc364e72572882cc065f516c4d01d654b1ae')
    old = json.loads(check(HERE.parent / 'renewed_manuscript_v7/work/ROOT_FINAL_QA_CONFIG_v3.json', 'cbd25ed36e0f1527e96d811bd990b79ffb46ed0f23515d53c704f78f97af654f'))
    helper = types.ModuleType('visual_helper'); helper.__file__ = str(HELPER)
    exec(compile(check(HELPER, 'e61d1024315fd29f5b0efc1a6a2707d9b525fa2381a75ed3517e0c70254852dc'), str(HELPER), 'exec'), helper.__dict__)
    definitions = {
        'main': ('v2', 30, 'Manuscript', 'f3a0775cf53a9213df69c8e5ca2722a990a96801bfebe4d02bdc732f026a2cf6', '86561f93e5fe73ea5650fef7c4131a384f9097c28ae1b9c45385867809e8aed5'),
        'supplement': ('v3', 80, 'Supplement', 'd8e51b01a6131a7c111f558b39617cf1018fecbe0aac635e084d755d46ffc5d4', '0e2542857f15688ca21c4db287191275ec5be23188b5b44b70eb0be407a57730')}
    bindings = {}; inherited = {}; all_pins = helper.Pins(PROJECT)
    for kind, (version, total, title, pdfpin, layoutpin) in definitions.items():
        folder = HERE / f'work/render_{kind}/{version}'
        pdf = folder / f'NeuralFoil_Measurement_Correction_{title}.pdf'
        check(pdf, pdfpin)
        layout = json.loads(check(folder / 'LAYOUT_AUDIT.json', layoutpin))
        assert layout['status'] == 'PASS_PROGRAMMATIC' and layout['pages'] == total and not layout['violations']
        assert layout['pdf_sha256'] == pdfpin
        rows = {r['page']:r for r in layout['ledger']}
        assert set(rows) == set(range(1,total+1))
        direct = list(range(1,total+1)) if kind == 'main' else [1] + list(range(23,81))
        pages = []
        for p in range(1,total+1):
            check(folder / f'page-{p}.png', rows[p]['png_sha256'])
            if p in direct:
                pages.append(dict(page=p, result='PASS', individually_viewed_original_resolution=True,
                                  png_sha256=rows[p]['png_sha256']))
        ledger = dict(pdf_sha256=pdfpin, pages=pages, reviewer='root',
                      report_sha256=spec(REPORT)['sha256'],
                      review_scope='Actual original-resolution visual review in this active research turn; no author approval.',
                      created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
        ledger_spec = save(HERE / f'work/ROOT_VISUAL_{kind.upper()}_FINAL.json', ledger)
        bindings[kind] = {}
        for index, r in enumerate(pages):
            p = r['page']
            bindings[kind][str(p)] = dict(ledger=ledger_spec, report=spec(REPORT), record_pointer=f'/pages/{index}',
                    reviewed_page=p, reviewed_png=spec(folder / f'page-{p}.png'), reviewed_pdf=spec(pdf))
        for p in range(1,total+1):
            if p not in direct:
                entry = old['documents'][kind]['visual'][str(p)]
                proof = helper.visual_page(all_pins, folder / f'page-{p}.png', entry)
                bindings[kind][str(p)] = entry
                inherited[str(p)] = proof
        assert set(bindings[kind]) == {str(p) for p in range(1,total+1)}
        for p, entry in bindings[kind].items():
            helper.visual_page(all_pins, folder / f'page-{p}.png', entry)
    all_pins.reread()
    witness = dict(status='ALL_110_FINAL_PAGES_VISUALLY_ACCOUNTED', direct_pages=89, inherited_pages=21,
                   documents=bindings, inherited_full_png_identity=inherited,
                   pinned_witnesses=all_pins.files, script_sha256=spec(Path(__file__))['sha256'])
    pin = save(HERE / 'work/VISUAL_BINDINGS_FINAL.json', witness)
    print(json.dumps(dict(status=witness['status'], direct_pages=89, inherited_pages=21, witness=pin)))
if __name__ == '__main__': main()
