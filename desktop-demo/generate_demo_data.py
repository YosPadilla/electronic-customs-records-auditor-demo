
from __future__ import annotations
import csv, html, zipfile, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "workspace_data"
ARCH = DATA / "records_3500"


def _pdf_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def pdf_doc(title: str, body: str) -> bytes:
    lines = [title, *body.splitlines(), '', 'SANDBOX PORTFOLIO DATA - NOT A REAL CUSTOMS RECORD']
    cmds = ['BT', '/F1 12 Tf', '52 760 Td']
    for idx, line in enumerate(lines):
        if idx:
            cmds.append('0 -20 Td')
        cmds.append(f'({_pdf_escape(line)}) Tj')
    cmds.append('ET')
    stream='\n'.join(cmds).encode('latin-1', errors='replace')
    objs=[]
    objs.append(b'<< /Type /Catalog /Pages 2 0 R >>')
    objs.append(b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>')
    objs.append(b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>')
    objs.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
    objs.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    out=bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets=[0]
    for i,obj in enumerate(objs,1):
        offsets.append(len(out)); out += f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n'
    xref=len(out); out += f'xref\n0 {len(objs)+1}\n'.encode()+b'0000000000 65535 f \n'
    for off in offsets[1:]: out += f'{off:010d} 00000 n \n'.encode()
    out += f'trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    return bytes(out)


def xml_doc(kind: str, body: str) -> bytes:
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<customs-document type="{html.escape(kind)}">\n'
            f'  <content>{html.escape(body)}</content>\n'
            '  <notice>SANDBOX PORTFOLIO DATA - NOT A REAL CUSTOMS RECORD</notice>\n'
            '</customs-document>\n').encode('utf-8')


def build():
    ARCH.mkdir(parents=True, exist_ok=True)
    for p in ARCH.glob('*.zip'): p.unlink()
    rows=[]
    for i in range(1,21):
        expediente=f'3500-{7000000+i}'
        pedimento=f'700{i:04d}'
        inv1=f'FAC-{i:03d}'
        invs=[inv1]
        if i in {4,8,12,15}: invs.append(f'FAC-{i:03d}-B')
        archive=f'{expediente}.zip'
        rows.append({'expediente_id':expediente,'pedimento':pedimento,'operation':'IMPORT','archive_name':archive,'expected_invoices':'|'.join(invs)})
        if i==20: continue
        files={}
        if i not in {14,17}:
            files[f'01_PEDIMENTO_PAGADO_{pedimento}.pdf']=pdf_doc('PEDIMENTO PAGADO',f'PEDIMENTO: {pedimento}\nPAGO BANCARIO: VALIDADO\nOPERACION: IMPORT')
        if i not in {13,16}:
            if i==18:
                files['03_FACTURA_CANDIDATA.pdf']=pdf_doc('FACTURA COMERCIAL','FACTURA COMERCIAL\nFOLIO: REFERENCIA-ILEGIBLE\nEvidence requires human review')
            elif i==19:
                files['03_INVOICE_SCAN.pdf']=pdf_doc('COMMERCIAL INVOICE','INVOICE\nCommercial goods evidence present, but identifier is illegible')
            else:
                for inv in (invs[:] if i!=15 else invs[:1]):
                    files[f'03_FACTURA_{inv}.pdf']=pdf_doc('FACTURA COMERCIAL',f'FACTURA: {inv}\nPEDIMENTO: {pedimento}\nMERCANCIA: COMPONENTES INDUSTRIALES')
        files[f'04_DODA_{pedimento}.pdf']=pdf_doc('DODA',f'DOCUMENTO DE OPERACION PARA DESPACHO ADUANERO\nPEDIMENTO: {pedimento}')
        if i%3!=0:
            files[f'05_CUENTA_GASTOS_CG-{i:03d}.pdf']=pdf_doc('CUENTA DE GASTOS',f'CUENTA DE GASTOS: CG-{i:03d}\nPEDIMENTO: {pedimento}')
        if i%4==0:
            files[f'08_COVE_{i:03d}.xml']=xml_doc('COVE / SUPPORTING',f'COVE-{i:03d}; PEDIMENTO: {pedimento}')
        with zipfile.ZipFile(ARCH/archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for name,payload in files.items():
                z.writestr(name,payload)
    DATA.mkdir(exist_ok=True)
    with (DATA/'audit_universe.csv').open('w',encoding='utf-8-sig',newline='') as fh:
        w=csv.DictWriter(fh,fieldnames=['expediente_id','pedimento','operation','archive_name','expected_invoices'])
        w.writeheader(); w.writerows(rows)
    # workbook path used visually in GUI; copy/refresh under a more natural name
    wb = DATA/'Customs_Audit_Universe.xlsx'
    if not wb.exists():
        # minimal placeholder file so path exists visually; bytes copied later if source exists
        wb.write_bytes(b'')
    print(f'Generated {len(rows)} synthetic records and {len(list(ARCH.glob("*.zip")))} archives.')

if __name__=='__main__':
    build()
