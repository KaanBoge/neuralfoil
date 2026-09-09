"""Supplementary structural extraction; no document generation."""
from pathlib import Path
import json,re,hashlib,xml.etree.ElementTree as ET
P=Path(__file__).resolve().parent
d=json.loads((P/'NATIVE_MATH.json').read_text());E=P.parents[3]/'renewed_manuscript_v7'
ns={'m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
records={}
for kind in ['main','supplement']:
    md=(E/f'{kind}.complete.md').read_text()
    src=[a or b for a,b in re.findall(r'\$\$(.*?)\$\$|\\\[(.*?)\\\]',md,re.S)]
    assert len(src)==len(d[kind])
    out=[]
    for raw,source in zip(d[kind],src):
        x=ET.fromstring(raw['xml'])
        text=lambda z:''.join(z.itertext()) if z is not None else ''
        out.append(dict(number=raw['number'],source_latex=source,omml_text=raw['text'],
          fractions=[{'numerator':text(f.find('m:num',ns)),'denominator':text(f.find('m:den',ns))} for f in x.findall('.//m:f',ns)],
          radicals=[text(r.find('m:e',ns)) for r in x.findall('.//m:rad',ns)],
          delimiters=[{y.tag.split('}')[1]:y.attrib for y in z} for z in x.findall('.//m:dPr',ns)],
          accents=[z.attrib for z in x.findall('.//m:accPr/m:chr',ns)],
          bars=[text(z.find('m:e',ns)) for z in x.findall('.//m:bar',ns)],
          sums=[{'operator':z.find('m:naryPr/m:chr',ns).attrib,'lower':text(z.find('m:sub',ns)),'upper':text(z.find('m:sup',ns))} for z in x.findall('.//m:nary',ns)]))
    records[kind]=out
dest=P/'MATH_STRUCTURE.json';assert not dest.exists();dest.write_text(json.dumps(records,indent=2)+'\n')
for kind,select in [('main',[3,6,9,10,11,13]),('supplement',list(range(19,29)))]:
    for i in select:print(kind,json.dumps(records[kind][i-1],ensure_ascii=False))
