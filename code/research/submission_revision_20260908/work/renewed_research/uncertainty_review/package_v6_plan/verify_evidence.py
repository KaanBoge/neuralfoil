"""Separate ZIP/member verifier; no producer traversal or scientific evaluation."""
import argparse,hashlib,os,stat,struct,time,zipfile
from pathlib import Path
import stream_common as c

def directory_admission(archive,clock=None):
    """Bound central-directory allocation BEFORE ZipFile constructs ZipInfo objects.

    Our fixed <=20,001 entries, <=240 MiB archive and <4 GiB per member need
    no ZIP64 end record, even though local payload headers use force_zip64.
    Writer has no archive comment or prepended/trailing records.
    """
    size=archive.stat().st_size
    if size<22 or size>c.COMPRESSED:raise ValueError('archive admission size')
    with archive.open('rb') as f:f.seek(-22,2);tail=f.read(22)
    sig,disk,start,n_disk,n_all,cd_bytes,cd_offset,comment=struct.unpack('<4s4H2LH',tail)
    if sig!=b'PK\x05\x06' or disk or start or comment or n_disk!=n_all or not 1<=n_all<=c.MAX_FILES+1 or cd_bytes>c.METADATA or cd_offset+cd_bytes!=size-22:raise ValueError('bounded single-disk central directory')
    # ZipFile walks actual directory entries, rather than trusting EOCD n_all.
    # Count and bound that exact sequence without allocating ZipInfo objects.
    clock=clock or c.Clock();count=0;consumed=0
    with archive.open('rb') as f:
        f.seek(cd_offset)
        while consumed<cd_bytes:
            clock.check();head=f.read(46)
            if len(head)!=46 or head[:4]!=b'PK\x01\x02':raise ValueError('central header structure')
            name,extra,comment=struct.unpack_from('<3H',head,28)
            length=46+name+extra+comment;count+=1
            if not name or count>c.MAX_FILES+1 or consumed+length>cd_bytes:raise ValueError('actual central record cap')
            f.seek(name+extra+comment,1);consumed+=length
    if consumed!=cd_bytes or count!=n_all:raise ValueError('actual central count disagrees with EOCD')

def write_chunk(dst,b):
    if dst.write(b)!=len(b):raise OSError('short extracted payload write')

def verify_disk(out,expected,clock):
    for name,r in expected.items():
        clock.check();p=c.path(out,'payload/'+name)
        if not p.is_file() or p.stat().st_size!=r['bytes']:raise ValueError('emitted disk size')
        h=hashlib.sha256();n=0
        with p.open('rb') as f:
            while b:=f.read(c.CHUNK):
                clock.check();n+=len(b)
                if n>r['bytes']:raise ValueError('emitted disk grew')
                h.update(b)
        if n!=r['bytes'] or h.hexdigest()!=r['sha256']:raise ValueError('emitted disk hash')

def inventory(z,expected):
    infos=z.infolist();names=[i.filename for i in infos]
    if len(names)!=len(set(n.casefold() for n in names)) or set(names)!=set(expected)|{'MANIFEST.json'}:raise ValueError('ZIP exact member inventory')
    for i in infos:
        c.safe(i.filename)
        if i.is_dir() or stat.S_IFMT(i.external_attr>>16) not in {0,stat.S_IFREG} or i.flag_bits&1 or i.compress_type!=zipfile.ZIP_DEFLATED:raise ValueError('ZIP member type')
        limit=c.METADATA if i.filename=='MANIFEST.json' else expected[i.filename]['bytes']
        if i.file_size!=limit and i.filename!='MANIFEST.json':raise ValueError('ZIP declared size')
        if i.filename=='MANIFEST.json' and i.file_size>limit:raise ValueError('manifest cap')
    if sum(i.file_size for i in infos)>c.EXPANDED:raise ValueError('ZIP expansion cap')
    return infos
def run(root,approval,approval_sha,output):
    out=None
    with c.deadline() as clock:
        try:
            rd=c.Reader(root,clock);target=c.path(rd.root,output)
            if target.exists():raise FileExistsError('fresh extraction required')
            a,s,rows=c.authorize(rd,approval,approval_sha,'VERIFY_EXTRACT',output)
            archive=c.path(rd.root,a['archive'])
            if archive.stat().st_size>c.COMPRESSED:raise ValueError('archive size admission')
            rd.check(a['archive'],a['archive_sha256'])
            directory_admission(archive,clock)
            receipt=c.parse(rd.check(a['writer_receipt'],a['writer_receipt_sha256'],True))
            if (c.path(rd.root,a['writer_receipt']).parent/'FAILURE.json').exists():raise ValueError('writer failed after receipt publication')
            wa=c.parse(rd.check(a['writer_approval'],a['writer_approval_sha256'],True))
            if receipt.get('approval_sha256')!=a['writer_approval_sha256'] or wa.get('phase')!='CREATE' or wa.get('execution_authorized') is not True or wa.get('selection_sha256')!=a['selection_sha256'] or wa.get('source_pins')!=a['source_pins'] or c.path(rd.root,wa['output'])!=c.path(rd.root,a['writer_receipt']).parent:raise ValueError('explicit original creation approval chain')
            if receipt.get('status')!='CREATED_STREAMED_EVIDENCE_EXTRACTION_PENDING' or receipt.get('archive_sha256')!=a['archive_sha256'] or receipt.get('selection_sha256')!=a['selection_sha256'] or receipt.get('source_pins')!=a['source_pins'] or receipt.get('scientific_execution') is not False:raise ValueError('writer receipt chain')
            expected={r['target']:{'sha256':r['sha256'],'bytes':r['bytes']} for r in rows}
            with zipfile.ZipFile(archive) as z:
                infos=inventory(z,expected);mb=z.read('MANIFEST.json');m=c.parse(mb)
                if m!={'schema':'v9-saved-evidence-1','selection_sha256':a['selection_sha256'],'claim':s['claim'],'files':expected} or c.digest(mb)!=receipt['manifest_sha256']:raise ValueError('manifest exact external binding')
                # First pass hashes EVERY member before any extraction output.
                for i in infos:
                    if i.filename=='MANIFEST.json':continue
                    h=hashlib.sha256();n=0
                    with z.open(i) as f:
                        while b:=f.read(c.CHUNK):
                            clock.check();n+=len(b)
                            if n>expected[i.filename]['bytes']:raise ValueError('expanded stream overrun')
                            h.update(b)
                    if n!=expected[i.filename]['bytes'] or h.hexdigest()!=expected[i.filename]['sha256']:raise ValueError('member digest')
                clock.check();target.mkdir(parents=False);out=target
                # Second pass independently checks the actual extracted bytes too.
                for i in infos:
                    p=c.path(out,'payload/'+i.filename);p.parent.mkdir(parents=True,exist_ok=True);h=hashlib.sha256();n=0
                    with z.open(i) as src,p.open('xb') as dst:
                        while b:=src.read(c.CHUNK):
                            clock.check();n+=len(b)
                            if n>i.file_size:raise ValueError('extraction stream overrun')
                            h.update(b);write_chunk(dst,b)
                        dst.flush();os.fsync(dst.fileno())
                    expected_hash=receipt['manifest_sha256'] if i.filename=='MANIFEST.json' else expected[i.filename]['sha256']
                    if h.hexdigest()!=expected_hash or n!=i.file_size:raise ValueError('extraction digest')
            verify_disk(out,{**expected,'MANIFEST.json':{'sha256':receipt['manifest_sha256'],'bytes':len(mb)}},clock)
            rd.end();result={'status':'VERIFIED_STREAMED_EVIDENCE','phase':'VERIFY_EXTRACT','approval_sha256':approval_sha,'selection_sha256':a['selection_sha256'],'writer_receipt_sha256':a['writer_receipt_sha256'],'source_pins':a['source_pins'],'archive_sha256':a['archive_sha256'],'archive_bytes':archive.stat().st_size,'manifest_sha256':receipt['manifest_sha256'],'files':len(rows),'verified_payload_bytes':sum(r['bytes'] for r in rows),'disk_files_reopened':len(rows)+1,'seconds':time.monotonic()-clock.start,'scientific_execution':False,'portable_pipeline_replayed':False}
            c.publish(out/'COMPLETE.json',result,clock);return result
        except BaseException as e:c.failure(out,e);raise
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['root','approval','approval-sha256','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();print(run(a.root,a.approval,a.approval_sha256,a.output))
