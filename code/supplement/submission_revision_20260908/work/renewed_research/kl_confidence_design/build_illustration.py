"""Fixed synthetic confidence grid and a two-panel scientific illustration."""
from pathlib import Path
from fractions import Fraction as F
import hashlib
import json
import math
import signal
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
PRODUCTION = HERE.parent/'kl_confidence_production/confidence.py'
PIN = '03c41a6aa79f44bd04fe374953c560db029d2f4a98f8cd1de552ed35657d9ad9'
COUNTS = (1,2,3,4,6,8,9,12,16,24,32,48,64,96,128,192,256)
MEANS = (F(0), F(1,50), F(1,10))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(x):
    if isinstance(x, F):
        return {'encoding':'signed-hex-v1','numerator':format(x.numerator,'x'),
                'denominator':format(x.denominator,'x')}
    raise TypeError(type(x).__name__)


def write_json(path, obj):
    payload = json.dumps(obj,default=encode,indent=2,allow_nan=False)+'\n'
    with path.open('x') as f:
        f.write(payload)


def main():
    if sha(PRODUCTION) != PIN:
        raise ValueError('production code pin')
    sys.path.insert(0,str(PRODUCTION.parent))
    import confidence as c
    dest = HERE/'illustration_attempt_1'
    dest.mkdir(exist_ok=False)
    started = time.monotonic()
    def timeout(*unused):
        raise TimeoutError('fixed 180-second illustration guard')
    signal.signal(signal.SIGALRM,timeout)
    signal.alarm(180)
    rows=[]
    try:
        for q in MEANS:
            for m in COUNTS:
                result = c.calibrate_kl_groups([q/2]*m,F(1,2))
                if result['upper'] > result['matched_hoeffding_upper']:
                    raise ArithmeticError('endpoint ordering')
                rows.append({'q':q,'groups':m,'B':F(1,2),'result':result})
        if len(rows)!=51:
            raise ValueError('complete declared grid required')
        write_json(dest/'GRID.json',rows)
    except BaseException:
        write_json(dest/'FAILURE.json',{'traceback':traceback.format_exc(),
            'complete_rows':len(rows),'elapsed_seconds':time.monotonic()-started})
        raise
    finally:
        signal.alarm(0)
    computational_seconds = time.monotonic()-started
    from reportlab.graphics.shapes import Drawing, String, Line, Rect
    from reportlab.graphics import renderPDF, renderSVG
    from reportlab.lib.colors import HexColor
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import reportlab
    font = Path(reportlab.__file__).parent/'fonts'
    pdfmetrics.registerFont(TTFont('KLSans',str(font/'Vera.ttf')))
    pdfmetrics.registerFont(TTFont('KLBold',str(font/'VeraBd.ttf')))
    d=Drawing(468,280)
    d.add(Rect(0,0,468,280,fillColor=HexColor('#FFFFFF'),strokeColor=None))
    colors=['#216A9C','#A95F0D','#7254A3']
    def text(x,y,s,size=9.5,anchor='start',bold=False):
        d.add(String(x,y,s,fontName='KLBold' if bold else 'KLSans',fontSize=size,
                     fillColor=HexColor('#182A3A'),textAnchor=anchor))
    for panel in range(2):
        x0=39+238*panel; y0=74; width=180; height=153
        xx=lambda m:x0+math.log2(m)/8*width
        yy=lambda value:y0+float(value)*height
        text(x0,263,'A  Confidence endpoint U / B' if panel==0 else 'B  Permitted extra fraction t',10,bold=True)
        for y in [0,.25,.5,.75,1]:
            d.add(Line(x0,yy(y),x0+width,yy(y),strokeColor=HexColor('#DEE5EB'),strokeWidth=.5))
            text(x0-6,yy(y)-3,f'{y:g}',9,anchor='end')
        for m in [1,4,16,64,256]:
            text(xx(m),y0-15,str(m),9,anchor='middle')
        d.add(Line(x0,y0,x0+width,y0,strokeColor=HexColor('#596675'),strokeWidth=.7))
        text(x0+width/2,42,'Calibration identities m (log scale)',9,anchor='middle')
        for q,color in zip(MEANS,colors):
            subset=[r for r in rows if r['q']==q]
            for method,dash in [('Hoeffding',[3,2]),('KL',None)]:
                previous=None
                for row in subset:
                    r=row['result']
                    value=(r['matched_hoeffding_upper'] if method=='Hoeffding' else r['upper'])/row['B'] if panel==0 else (r['matched_hoeffding_t'] if method=='Hoeffding' else r['t'])
                    current=(xx(row['groups']),yy(value))
                    if previous is not None:
                        d.add(Line(*previous,*current,strokeColor=HexColor(color),strokeWidth=1.1,strokeDashArray=dash))
                    previous=current
    for j,(q,color) in enumerate(zip(MEANS,colors)):
        x=24+j*109
        d.add(Line(x,243,x+16,243,strokeColor=HexColor(color),strokeWidth=1.5))
        text(x+21,240,'q = '+f'{float(q):g}',9)
    d.add(Line(344,247,362,247,strokeColor=HexColor('#182A3A'),strokeWidth=1.1))
    text(368,244,'KL',9)
    d.add(Line(344,233,362,233,strokeColor=HexColor('#182A3A'),strokeWidth=1.1,strokeDashArray=[3,2]))
    text(368,230,'Hoeffding',9)
    text(234,22,'Illustration only: B = 0.5; tau = 0.01; beta = 0.05.',9,anchor='middle')
    text(234,7,'Larger permitted t does not imply lower prediction error.',9,anchor='middle')
    stem=dest/'confidence_rule_illustration'
    renderPDF.drawToFile(d,str(stem.with_suffix('.pdf')))
    renderSVG.drawToFile(d,str(stem.with_suffix('.svg')))
    subprocess.run(['/PATH_TO_YOUR_HOME/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm',
                    '-singlefile','-r','300','-png',str(stem.with_suffix('.pdf')),str(stem)],check=True)
    write_json(dest/'MANIFEST.json',{'status':'BUILT_REQUIRES_INDEPENDENT_AND_VISUAL_REVIEW',
        'rows':51,'synthetic_only':True,'new_core_fits':0,'computational_seconds':computational_seconds,
        'input_sha256':{str(PRODUCTION):PIN,str(HERE/'ILLUSTRATION_PLAN.md'):sha(HERE/'ILLUSTRATION_PLAN.md'),
                        str(Path(__file__)):sha(Path(__file__))},
        'output_sha256':{p.name:sha(p) for p in sorted(dest.iterdir()) if p.is_file()}})
    print(json.dumps({'rows':51,'computational_seconds':computational_seconds,'directory':str(dest)}))


if __name__=='__main__':
    main()
