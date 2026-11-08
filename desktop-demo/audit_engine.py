from __future__ import annotations

import csv
import json
import re
import time
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "workspace_data"
ARCHIVES_DIR = DATA_DIR / "records_3500"
UNIVERSE_CSV = DATA_DIR / "audit_universe.csv"
OUTPUT_DIR = ROOT / "output"

STATUS_ORDER = ["COMPLETE", "INCOMPLETE", "REVIEW", "NOT FOUND"]

@dataclass
class RecordResult:
    row: int
    expediente_id: str
    pedimento: str
    operation: str
    archive: str
    status: str
    paid_declaration: bool
    invoices_expected: int
    invoices_found: int
    doda: bool
    expense_account: bool
    evidence_count: int
    reason: str
    documents: list[dict]


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", s.upper()).strip()


def classify_document(name: str, content: str) -> str:
    hay = _norm(name + " " + content[:5000])
    if any(k in hay for k in ["PEDIMENTO PAGADO", "PEDIMENTO COMPLETO", " PC ", "PAGO BANCARIO"]):
        return "PAID DECLARATION"
    if "DODA" in hay or "DOCUMENTO DE OPERACION" in hay:
        return "DODA"
    if any(k in hay for k in ["CUENTA DE GASTOS", " CUENTA GASTOS ", " CG "]):
        return "EXPENSE ACCOUNT"
    if any(k in hay for k in ["FACTURA", "INVOICE", " FA "]):
        return "COMMERCIAL INVOICE"
    if "COVE" in hay:
        return "COVE / SUPPORTING"
    return "OTHER"


def _invoice_ids(text: str) -> set[str]:
    return set(re.findall(r"FAC-\d{3}(?:-[A-Z])?", text.upper()))


def load_universe() -> list[dict]:
    with UNIVERSE_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def audit_record(row_num: int, record: dict) -> RecordResult:
    expediente_id = record["expediente_id"]
    archive_name = record["archive_name"]
    archive_path = ARCHIVES_DIR / archive_name
    expected = [x for x in record["expected_invoices"].split("|") if x]

    if not archive_path.exists():
        return RecordResult(
            row=row_num, expediente_id=expediente_id, pedimento=record["pedimento"], operation=record["operation"],
            archive=archive_name, status="NOT FOUND", paid_declaration=False,
            invoices_expected=len(expected), invoices_found=0, doda=False, expense_account=False,
            evidence_count=0, reason="No archive found for the expected customs record.", documents=[]
        )

    documents: list[dict] = []
    found_invoice_ids: set[str] = set()
    paid = False
    doda = False
    expense = False
    ambiguous_invoice = False

    with zipfile.ZipFile(archive_path, "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            raw = zf.read(info.filename)
            text = raw.decode("utf-8", errors="ignore")
            cls = classify_document(info.filename, text)
            ids = _invoice_ids(info.filename + " " + text)
            if cls == "PAID DECLARATION":
                paid = True
            elif cls == "DODA":
                doda = True
            elif cls == "EXPENSE ACCOUNT":
                expense = True
            elif cls == "COMMERCIAL INVOICE":
                found_invoice_ids.update(ids)
                if not ids:
                    ambiguous_invoice = True
            documents.append({
                "name": info.filename,
                "type": cls,
                "size": info.file_size,
                "invoice_ids": sorted(ids),
            })

    matched = set(expected) & found_invoice_ids
    missing = [x for x in expected if x not in matched]
    unexpected = sorted(found_invoice_ids - set(expected))

    if ambiguous_invoice or unexpected:
        status = "REVIEW"
        bits = []
        if ambiguous_invoice:
            bits.append("Commercial evidence detected without a reliable invoice identifier")
        if unexpected:
            bits.append("Invoice identifier does not match the expected evidence map")
        reason = "; ".join(bits) + "."
    elif not paid:
        status = "INCOMPLETE"
        reason = "Paid customs declaration is missing."
    elif missing:
        status = "INCOMPLETE"
        reason = f"Missing {len(missing)} expected commercial invoice(s): {', '.join(missing)}."
    else:
        status = "COMPLETE"
        reason = "Critical evidence matched: paid declaration and expected commercial invoice(s)."

    return RecordResult(
        row=row_num, expediente_id=expediente_id, pedimento=record["pedimento"], operation=record["operation"],
        archive=archive_name, status=status, paid_declaration=paid,
        invoices_expected=len(expected), invoices_found=len(matched), doda=doda, expense_account=expense,
        evidence_count=len(documents), reason=reason, documents=documents
    )


def run_audit(progress=None, per_record_delay: float = 0.0) -> dict:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    universe = load_universe()
    started = time.time()
    results = []
    for i, record in enumerate(universe, start=1):
        if progress:
            progress({"phase": "start", "row": i, "expediente_id": record["expediente_id"], "archive": record["archive_name"]})
        result = audit_record(i, record)
        results.append(result)
        if progress:
            progress({"phase": "result", "row": i, "record": asdict(result)})
        if per_record_delay:
            time.sleep(per_record_delay)
    elapsed = round(time.time() - started, 3)

    counts = {s: sum(1 for r in results if r.status == s) for s in STATUS_ORDER}
    found = len(results) - counts["NOT FOUND"]
    summary = {
        "total": len(results),
        "archives_found": found,
        "counts": counts,
        "elapsed_seconds": elapsed,
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "boundary": "Sandbox portfolio simulation using synthetic customs records only."
    }

    export_results(results, summary)
    return {"summary": summary, "records": [asdict(r) for r in results]}


def export_results(results: list[RecordResult], summary: dict) -> None:
    csv_path = OUTPUT_DIR / "CUSTOMS_AUDIT_RESULTS.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ROW", "EXPEDIENTE", "PEDIMENTO", "OPERATION", "STATUS", "PAID_DECLARATION", "INVOICES_EXPECTED", "INVOICES_FOUND", "DODA", "EXPENSE_ACCOUNT", "EVIDENCE_COUNT", "REASON"])
        for r in results:
            writer.writerow([r.row, r.expediente_id, r.pedimento, r.operation, r.status, "YES" if r.paid_declaration else "NO", r.invoices_expected, r.invoices_found, "YES" if r.doda else "NO", "YES" if r.expense_account else "NO", r.evidence_count, r.reason])

    evidence_path = OUTPUT_DIR / "EVIDENCE_MAP.csv"
    with evidence_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["EXPEDIENTE", "STATUS", "FILE", "CLASSIFICATION", "SIZE_BYTES", "INVOICE_IDS"])
        for r in results:
            for d in r.documents:
                writer.writerow([r.expediente_id, r.status, d["name"], d["type"], d["size"], " | ".join(d["invoice_ids"])])

    (OUTPUT_DIR / "ACHIEVEMENT_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (OUTPUT_DIR / "AUDIT_LOG.txt").write_text("\n".join(
        [f"{r.row:02d}/20 · {r.expediente_id} · {r.status} · {r.reason}" for r in results]
    ) + "\n", encoding="utf-8")

    write_xlsx(OUTPUT_DIR / "CUSTOMS_AUDIT_RESULTS.xlsx", results, summary)


def col_letter(n: int) -> str:
    out = ""
    while n:
        n, rem = divmod(n - 1, 26)
        out = chr(65 + rem) + out
    return out


def _cell_xml(ref: str, value, style: int = 0) -> str:
    sattr = f' s="{style}"' if style else ''
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{sattr}><v>{value}</v></c>'
    txt = escape(str(value if value is not None else ""))
    return f'<c r="{ref}" t="inlineStr"{sattr}><is><t xml:space="preserve">{txt}</t></is></c>'


def summary_sheet_xml(summary: dict) -> str:
    rows = [
        ["Electronic Customs Records Auditor", "", "", ""],
        ["Operational summary", "", "", ""],
        ["TOTAL RECORDS", summary["total"], "ARCHIVES FOUND", summary["archives_found"]],
        ["COMPLETE", summary["counts"]["COMPLETE"], "INCOMPLETE", summary["counts"]["INCOMPLETE"]],
        ["REVIEW", summary["counts"]["REVIEW"], "NOT FOUND", summary["counts"]["NOT FOUND"]],
        ["Generated", summary["generated_at"], "", ""],
        ["Data note", "Illustrative dataset · no production systems connected", "", ""],
    ]
    parts=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           '<dimension ref="A1:D7"/>',
           '<sheetViews><sheetView workbookViewId="0" showGridLines="0"/></sheetViews>',
           '<sheetFormatPr defaultRowHeight="18"/>',
           '<cols><col min="1" max="1" width="23" customWidth="1"/><col min="2" max="2" width="26" customWidth="1"/><col min="3" max="3" width="23" customWidth="1"/><col min="4" max="4" width="22" customWidth="1"/></cols>',
           '<sheetData>']
    for r_idx,row in enumerate(rows,1):
        parts.append(f'<row r="{r_idx}" ht="{34 if r_idx==1 else 24}" customHeight="1">')
        for c_idx,value in enumerate(row,1):
            style=0
            if r_idx==1: style=2
            elif r_idx==2: style=3
            elif r_idx in {3,4,5} and c_idx in {1,3}: style=4
            elif r_idx in {3,4,5} and c_idx in {2,4}:
                if r_idx==4 and c_idx==2: style=5
                elif r_idx==4 and c_idx==4: style=6
                elif r_idx==5 and c_idx==2: style=7
                elif r_idx==5 and c_idx==4: style=8
                else: style=9
            elif r_idx>=6 and c_idx==1: style=4
            parts.append(_cell_xml(f'{col_letter(c_idx)}{r_idx}',value,style))
        parts.append('</row>')
    parts += ['</sheetData>',
              '<mergeCells count="3"><mergeCell ref="A1:D1"/><mergeCell ref="A2:D2"/><mergeCell ref="B7:D7"/></mergeCells>',
              '<pageMargins left="0.7" right="0.7" top="0.75" bottom="0.75" header="0.3" footer="0.3"/>',
              '</worksheet>']
    return ''.join(parts)


def results_sheet_xml(results: list[RecordResult]) -> str:
    headers=["#","EXPEDIENTE","PEDIMENTO","STATUS","PAID","INVOICES MATCHED","DODA","EXPENSE","EVIDENCE","WHY / FOLLOW-UP"]
    widths=[5.5,18,12,13,8,16,8,10,9,43]
    end_row=len(results)+4
    parts=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
           f'<dimension ref="A1:J{end_row}"/>',
           '<sheetViews><sheetView workbookViewId="0" showGridLines="0" zoomScale="85" zoomScaleNormal="85">'
           '<pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/>'
           '<selection pane="bottomLeft" activeCell="A5" sqref="A5"/>'
           '</sheetView></sheetViews>',
           '<sheetFormatPr defaultRowHeight="18"/>',
           '<cols>']
    for i,w in enumerate(widths,1):
        parts.append(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>')
    parts += ['</cols>','<sheetData>']
    parts.append('<row r="1" ht="34" customHeight="1">')
    parts.append(_cell_xml('A1','CUSTOMS AUDIT RESULTS',2)); parts.append('</row>')
    parts.append('<row r="2" ht="23" customHeight="1">')
    parts.append(_cell_xml('A2','Critical evidence checks · exceptions highlighted for analyst follow-up',3)); parts.append('</row>')
    parts.append('<row r="3" ht="8" customHeight="1"></row>')
    parts.append('<row r="4" ht="38" customHeight="1">')
    for c_idx,h in enumerate(headers,1): parts.append(_cell_xml(f'{col_letter(c_idx)}4',h,11))
    parts.append('</row>')
    status_style={'COMPLETE':5,'INCOMPLETE':6,'REVIEW':7,'NOT FOUND':8}
    for ridx,r in enumerate(results,5):
        invoice_display=f'{r.invoices_found} / {r.invoices_expected}'
        row=[r.row,r.expediente_id,r.pedimento,r.status,"YES" if r.paid_declaration else "NO",invoice_display,
             "YES" if r.doda else "NO","YES" if r.expense_account else "NO",r.evidence_count,r.reason]
        parts.append(f'<row r="{ridx}" ht="24" customHeight="1">')
        for c_idx,value in enumerate(row,1):
            if c_idx==4: style=status_style.get(r.status,0)
            elif c_idx in {1,3,5,6,7,8,9}: style=9
            else: style=10 if ridx%2==1 else 0
            parts.append(_cell_xml(f'{col_letter(c_idx)}{ridx}',value,style))
        parts.append('</row>')
    parts += ['</sheetData>',
              f'<autoFilter ref="A4:J{end_row}"/>',
              '<mergeCells count="2"><mergeCell ref="A1:J1"/><mergeCell ref="A2:J2"/></mergeCells>',
              '<pageMargins left="0.35" right="0.35" top="0.55" bottom="0.55" header="0.2" footer="0.2"/>',
              '<pageSetup orientation="landscape" fitToWidth="1" fitToHeight="0"/>',
              '</worksheet>']
    return ''.join(parts)


def write_xlsx(path: Path, results: list[RecordResult], summary: dict) -> None:
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>'''
    workbook = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<bookViews><workbookView activeTab="1"/></bookViews>
<sheets><sheet name="Summary" sheetId="1" r:id="rId1"/><sheet name="Audit Results" sheetId="2" r:id="rId2"/></sheets>
</workbook>'''
    wb_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="4">
 <font><sz val="10"/><name val="Aptos"/><family val="2"/></font>
 <font><b/><color rgb="FFFFFFFF"/><sz val="10"/><name val="Aptos"/><family val="2"/></font>
 <font><b/><color rgb="FFFFFFFF"/><sz val="18"/><name val="Aptos Display"/><family val="2"/></font>
 <font><b/><color rgb="FF17324A"/><sz val="10"/><name val="Aptos"/><family val="2"/></font>
</fonts>
<fills count="9">
 <fill><patternFill patternType="none"/></fill>
 <fill><patternFill patternType="gray125"/></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FF173A53"/><bgColor indexed="64"/></patternFill></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FFEAF2F7"/><bgColor indexed="64"/></patternFill></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FFDDF3E7"/><bgColor indexed="64"/></patternFill></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FFF9DEDE"/><bgColor indexed="64"/></patternFill></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FFFFF0CF"/><bgColor indexed="64"/></patternFill></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FFEFE2FA"/><bgColor indexed="64"/></patternFill></fill>
 <fill><patternFill patternType="solid"><fgColor rgb="FFF6F9FB"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
 <border><left/><right/><top/><bottom/><diagonal/></border>
 <border><left style="thin"><color rgb="FFD4E0E7"/></left><right style="thin"><color rgb="FFD4E0E7"/></right><top style="thin"><color rgb="FFD4E0E7"/></top><bottom style="thin"><color rgb="FFD4E0E7"/></bottom><diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="12">
 <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
 <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"><alignment vertical="center"/></xf>
 <xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment vertical="center"/></xf>
 <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"><alignment vertical="center"/></xf>
 <xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"/>
 <xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"/>
 <xf numFmtId="0" fontId="3" fillId="5" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"/>
 <xf numFmtId="0" fontId="3" fillId="6" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"/>
 <xf numFmtId="0" fontId="3" fillId="7" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1"/>
 <xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
 <xf numFmtId="0" fontId="0" fillId="8" borderId="0" xfId="0" applyFill="1"/>
 <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFill="1" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
<dxfs count="0"/>
<tableStyles count="0" defaultTableStyle="TableStyleMedium2" defaultPivotStyle="PivotStyleLight16"/>
</styleSheet>'''
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", summary_sheet_xml(summary))
        z.writestr("xl/worksheets/sheet2.xml", results_sheet_xml(results))


if __name__ == "__main__":
    print(json.dumps(run_audit(), indent=2))
