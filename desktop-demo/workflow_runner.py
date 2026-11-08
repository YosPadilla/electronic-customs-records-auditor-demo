from __future__ import annotations
import json, os, subprocess, sys, time, traceback
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from desktop.windows_control import find_window, maximize_foreground, close_window, click, minimize_console
from generate_demo_data import build as build_demo_data

ROOT = Path(__file__).resolve().parent
ARCH = ROOT / 'workspace_data' / 'records_3500'
OUT = ROOT / 'output'
READY = OUT / '.gui_ready.json'
DONE = OUT / '.desktop_demo_complete'
SETUP = OUT / '.recording_setup.json'
LOG = OUT / 'RUN_ALL_LOG.txt'
GUI_TITLE = 'Electronic Customs Records Auditor'
IMPACT_TITLE = 'Audit Outcome — Operational Summary'
IMPACT_READY = OUT / '.impact_ready.json'
IMPACT_DONE = OUT / '.impact_complete'
FINAL_VIDEO = OUT / 'electronic-customs-records-auditor-demo.mp4'
TEMP_VIDEO_DIR = OUT / '.recording'
TEMP_VIDEO = TEMP_VIDEO_DIR / 'capture.mp4'
VIDEO_REPORT = OUT / 'VIDEO_VALIDATION.json'
OVERLAY_SCRIPT = ROOT / 'video_overlay.py'


def show_overlay(exe: str, *, mode='lower', step='', title='', detail='', badge='', duration=2.6, accent='cyan', wait=False):
    """Show a workflow narration overlay used by the guided demo."""
    args = [exe, str(OVERLAY_SCRIPT), '--mode', mode, '--step', step, '--title', title,
            '--detail', detail, '--badge', badge, '--duration', str(duration), '--accent', accent]
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    proc = subprocess.Popen(args, cwd=ROOT, creationflags=flags)
    # Give Tk time to paint before the next recorded action.
    time.sleep(.35)
    if wait:
        time.sleep(max(.2, duration-.15))
    return proc


def log(msg):
    print(msg, flush=True)
    try:
        with LOG.open('a', encoding='utf-8') as fh: fh.write(msg + '\n')
    except Exception: pass


def wait_file(path, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        if path.exists(): return True
        time.sleep(.15)
    return False


def open_explorer(path: Path, title_hint: str):
    subprocess.Popen(['explorer.exe', str(path)])
    hwnd = find_window(title_hint, timeout=9)
    if hwnd: maximize_foreground(hwnd)
    time.sleep(.7)
    return hwnd


def open_zip(path: Path, title_hint: str):
    subprocess.Popen(['explorer.exe', str(path)])
    hwnd = find_window(title_hint, timeout=9)
    if hwnd: maximize_foreground(hwnd)
    time.sleep(.7)
    return hwnd


def safe_shot(recorder, name):
    try:
        ok = recorder.screenshot(OUT / name)
        if ok is False:
            log(f'[WARNING] Screenshot {name} could not be captured.')
    except Exception as exc:
        log(f'[WARNING] Screenshot {name} failed: {exc}')


def show_error(title: str, message: str):
    try:
        r = tk.Tk(); r.withdraw()
        messagebox.showerror(title, message)
        r.destroy()
    except Exception:
        pass


def show_info(title: str, message: str):
    try:
        r = tk.Tk(); r.withdraw()
        messagebox.showinfo(title, message)
        r.destroy()
    except Exception:
        pass


def main():
    if os.name != 'nt':
        print('Electronic Customs Records Auditor is designed for Windows 10/11.')
        return 2

    setup = {}
    try:
        if SETUP.exists(): setup = json.loads(SETUP.read_text(encoding='utf-8'))
    except Exception as exc:
        log(f'[ERROR] Could not read recording setup state: {exc}')
        return 2

    screenshots_only = bool(setup.get('explicit_screenshots_only'))
    if not screenshots_only:
        if not setup.get('recording') or not setup.get('validated') or not setup.get('ffmpeg'):
            log('[ERROR] Recording preflight was not validated. Run RUN_ALL.bat again.')
            show_error('Recording preflight failed', 'The MP4 recorder was not validated.\n\nRun RUN_ALL.bat again and review output\\RUN_ALL_LOG.txt if the problem continues.')
            return 4
        os.environ['FFMPEG_EXE'] = str(setup['ffmpeg'])

    try:
        from desktop.desktop_recorder import DesktopRecorder, ScreenshotOnlyRecorder, validate_video
    except Exception as exc:
        log(f'[ERROR] Recorder module could not load: {exc}')
        show_error('Recorder unavailable', f'The recording module could not be loaded:\n\n{exc}')
        return 4

    root = tk.Tk(); root.withdraw()
    if screenshots_only:
        note = (
            'Screenshot-only guided workflow.\n\n'
            'The workflow will run normally and milestone PNG files will be captured, but no MP4 will be created.\n\n'
            'Close or mute sensitive notifications and do not use the mouse or keyboard during the sequence.'
        )
        title = 'Customs Auditor — Screenshot Sequence'
    else:
        note = (
            'Video recording is READY and has passed the desktop-capture preflight.\n\n'
            'This guided workflow will record Windows Explorer, two synthetic customs-record examples, '
            'the desktop auditor, the results workbook, and the final operational-outcome scene.\n\n'
            'Close or mute sensitive notifications before continuing. Do not use the mouse or keyboard during the sequence.\n\n'
            'Only synthetic portfolio data are opened.'
        )
        title = 'Customs Auditor — Record Portfolio Video'
    ok = messagebox.askokcancel(title, note)
    root.destroy()
    if not ok:
        log('[INFO] User cancelled before the guided workflow started.')
        return 0

    build_demo_data(); OUT.mkdir(exist_ok=True)

    # Clear prior run artifacts while preserving diagnostic/setup state.
    preserve = {'RUN_ALL_LOG.txt', '.recording_setup.json', '.gitkeep'}
    for p in OUT.iterdir():
        if p.name in preserve:
            continue
        if p.is_file():
            try: p.unlink()
            except Exception: pass
        elif p.is_dir():
            import shutil
            try: shutil.rmtree(p)
            except Exception: pass
    TEMP_VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    recorder = None
    recording_active = False
    recording_error = None

    if screenshots_only:
        recorder = ScreenshotOnlyRecorder()
        log('[INFO] Explicit screenshot-only run started.')
    else:
        try:
            fps = int(setup.get('fps') or 20)
            recorder = DesktopRecorder(TEMP_VIDEO, fps=fps, log_path=OUT / '.ffmpeg-capture.log')
            recorder.start()
            recording_active = True
            log(f'[OK] Desktop recording started at {fps} fps.')
        except Exception as exc:
            recording_error = str(exc)
            log(f'[ERROR] Video recording failed to start after a successful preflight: {exc}')
            show_error('Video recording failed', f'The preflight passed, but the final recorder could not start:\n\n{exc}\n\nThe guided workflow was stopped so you do not end up with screenshots only.')
            return 5

    try:
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        pyw = Path(sys.executable).with_name('pythonw.exe')
        exe = str(pyw if pyw.exists() else Path(sys.executable))

        # Opening: a true transition card, not a static jump into Explorer.
        show_overlay(
            exe, mode='card', step='01 / EVIDENCE SOURCES',
            title='Map the audit universe',
            detail='Each customs record is linked to the archive and commercial evidence expected for review.',
            badge='SOURCE →', duration=4.35, accent='cyan', wait=True
        )

        # 01 · Explorer overview
        exp_hwnd = open_explorer(ARCH, 'records_3500')
        show_overlay(
            exe, step='AUDIT UNIVERSE', title='20 customs records are in scope',
            detail='The review starts from a controlled list of expected records and supporting archives.',
            badge='20 RECORDS', duration=2.7, accent='cyan'
        )
        time.sleep(1.7); safe_shot(recorder, '01-explorer-records.png')
        time.sleep(1.0)

        # 02 · Complete example
        p1 = ARCH / '3500-7000001.zip'
        h1 = open_zip(p1, '3500-7000001')
        show_overlay(
            exe, step='EVIDENCE MATCH', title='Critical evidence is complete',
            detail='The paid declaration and expected commercial invoice references match the audit universe.',
            badge='✓ MATCHED', duration=3.0, accent='green'
        )
        time.sleep(1.6); safe_shot(recorder, '02-expediente-complete.png')
        time.sleep(1.3)
        if h1: close_window(h1)
        time.sleep(.9)
        if exp_hwnd: maximize_foreground(exp_hwnd)

        # 03 · Review example
        p2 = ARCH / '3500-7000018.zip'
        h2 = open_zip(p2, '3500-7000018')
        show_overlay(
            exe, step='EXCEPTION ROUTING', title='Ambiguous evidence is escalated',
            detail='The invoice is detected, but the identifier is not reliable enough to close automatically. The case is routed for analyst review.',
            badge='⚠ REVIEW', duration=3.3, accent='amber'
        )
        time.sleep(1.7); safe_shot(recorder, '03-expediente-review.png')
        time.sleep(1.4)
        if h2: close_window(h2)
        time.sleep(.9)
        if exp_hwnd: close_window(exp_hwnd)
        time.sleep(.7)

        # Transition into the audit engine.
        show_overlay(
            exe, mode='card', step='02 / BATCH AUDIT',
            title='Scan → classify → match → route',
            detail='The engine evaluates each archive and converts file-level evidence into actionable audit statuses.',
            badge='PROCESS →', duration=4.15, accent='cyan', wait=True
        )

        # 04–06 · Native auditor execution
        subprocess.Popen([exe, str(ROOT / 'desktop_gui.py'), '--guided'], cwd=ROOT, creationflags=flags)
        if not wait_file(READY, 15):
            raise RuntimeError('Desktop GUI did not signal ready state. See output\\RUN_ALL_LOG.txt.')
        hwnd = find_window(GUI_TITLE, timeout=10)
        if not hwnd: raise RuntimeError('Desktop GUI window was not detected.')
        maximize_foreground(hwnd); time.sleep(1.2)
        show_overlay(
            exe, step='AUDIT ENGINE', title='Evidence rules are ready',
            detail='Each archive is inspected, documents are classified and critical evidence is matched against the expected record.',
            badge='READY ✓', duration=2.6, accent='cyan'
        )
        time.sleep(1.0); safe_shot(recorder, '04-gui-ready.png')
        time.sleep(.9)

        coords = json.loads(READY.read_text(encoding='utf-8'))
        click(coords['run_x'], coords['run_y'])
        time.sleep(.5)
        show_overlay(
            exe, step='BATCH PROCESSING', title='Exceptions surface in real time',
            detail='COMPLETE records can close; missing, ambiguous or absent evidence remains visible for analyst follow-up.',
            badge='RUNNING …', duration=3.1, accent='cyan'
        )
        time.sleep(1.9); safe_shot(recorder, '05-audit-running.png')
        if not wait_file(DONE, 45):
            raise RuntimeError('Audit did not complete within the expected demo window.')
        time.sleep(.8)
        show_overlay(
            exe, step='BATCH RESULT', title='20 records evaluated',
            detail='12 complete · 5 incomplete · 2 require review · 1 expected archive not found.',
            badge='✓ 20 / 20', duration=3.0, accent='green'
        )
        time.sleep(1.3); safe_shot(recorder, '06-audit-complete.png')
        time.sleep(1.7)
        close_window(hwnd); time.sleep(.8)

        # Transition to the report so the app change is explained, not abrupt.
        show_overlay(
            exe, mode='card', step='03 / AUDIT REPORT',
            title='Convert findings into traceable outputs',
            detail='The audit produces a reviewable Excel report plus machine-readable exports and an evidence map.',
            badge='EXPORT ↓', duration=4.25, accent='green', wait=True
        )

        # 07 · Deliberate workbook review beat
        results_book = OUT / 'CUSTOMS_AUDIT_RESULTS.xlsx'
        excel_hwnd = None
        if results_book.exists():
            try:
                os.startfile(str(results_book))
                excel_hwnd = find_window('CUSTOMS_AUDIT_RESULTS', timeout=14)
                if excel_hwnd:
                    maximize_foreground(excel_hwnd)
                    time.sleep(2.0)
                    show_overlay(
                        exe, step='AUDIT REPORT', title='One row = one audited customs record',
                        detail='STATUS shows the routing decision; the remaining columns show which critical evidence was actually found and matched.',
                        badge='XLSX ✓', duration=3.2, accent='green'
                    )
                    time.sleep(1.4)
                    show_overlay(
                        exe, step='HOW TO READ IT', title='Status drives the next action',
                        detail='COMPLETE = close · INCOMPLETE = recover evidence · REVIEW = analyst decision · NOT FOUND = locate the expected archive.',
                        badge='DECISION →', duration=3.4, accent='amber'
                    )
                    time.sleep(1.5); safe_shot(recorder, '07-results-workbook.png')
                    time.sleep(2.0)
                    close_window(excel_hwnd)
                    time.sleep(1.1)
                else:
                    log('[WARNING] Results workbook opened but its window could not be detected for the staged review.')
            except Exception as exc:
                log(f'[WARNING] Could not open results workbook: {exc}')
        else:
            log('[WARNING] Results workbook was not found after audit completion.')

        # 08 · Full-screen impact scene
        show_overlay(
            exe, mode='card', step='04 / OPERATIONAL OUTCOME',
            title='Focus analyst time on exceptions',
            detail='Routine matches are separated from records that need evidence recovery or human judgment.',
            badge='OUTCOME', duration=4.45, accent='amber', wait=True
        )
        for marker in [IMPACT_READY, IMPACT_DONE]:
            try: marker.unlink()
            except Exception: pass
        subprocess.Popen([exe, str(ROOT / 'impact_scene.py')], cwd=ROOT, creationflags=flags)
        if not wait_file(IMPACT_READY, 12):
            raise RuntimeError('Impact scene did not signal ready state.')
        impact_hwnd = find_window(IMPACT_TITLE, timeout=10)
        if impact_hwnd: maximize_foreground(impact_hwnd)
        if not wait_file(IMPACT_DONE, 14):
            raise RuntimeError('Impact scene did not complete within the expected window.')
        # Hold the final outcome long enough to be read. The guided story ends here.
        time.sleep(1.2); safe_shot(recorder, '08-impact-scene.png')
        time.sleep(4.8)
        log('[OK] Narrated natural desktop sequence reached the final outcome scene.')

    except Exception as exc:
        log('[ERROR] Natural desktop sequence failed: ' + str(exc))
        log(traceback.format_exc())
        show_error('guided workflow stopped', f'The sequence stopped at an unexpected step:\n\n{exc}\n\nDiagnostic log:\n{LOG}')
        return 1
    finally:
        if recorder is not None:
            try:
                rc = recorder.stop()
                if recording_active and rc not in (0, None):
                    recording_error = f'FFmpeg exited with code {rc}'
                    log(f'[ERROR] {recording_error}')
            except Exception as exc:
                recording_error = f'Recorder shutdown failed: {exc}'
                log(f'[ERROR] {recording_error}')

    if screenshots_only:
        log('[OK] Screenshot-only sequence complete. No MP4 was requested.')
        show_info('Sequence complete', 'Screenshot sequence completed successfully.\n\nThe sequence ends on the operational outcome scene. Milestone images and audit reports are in the output folder.')
        return 0

    # v1.7 requirement: the run is NOT successful until the MP4 passes validation.
    if recording_error:
        show_error('Video validation failed', f'The visual sequence completed, but the MP4 recorder reported an error:\n\n{recording_error}\n\nSee output\\RUN_ALL_LOG.txt and output\\.ffmpeg-capture.log.')
        return 6

    check = validate_video(TEMP_VIDEO, ffmpeg=str(setup.get('ffmpeg')), min_duration=25.0, min_size=250_000)
    VIDEO_REPORT.write_text(json.dumps(check, indent=2), encoding='utf-8')
    if not check.get('ok'):
        reason = check.get('reason', 'unknown validation error')
        log(f'[ERROR] Final MP4 validation failed: {reason}')
        show_error('MP4 not valid', f'The guided workflow completed, but the recorded MP4 did not pass validation:\n\n{reason}\n\nNo false success message will be shown. Review VIDEO_VALIDATION.json and .ffmpeg-capture.log.')
        return 7

    try:
        if FINAL_VIDEO.exists(): FINAL_VIDEO.unlink()
        TEMP_VIDEO.replace(FINAL_VIDEO)
        try: TEMP_VIDEO_DIR.rmdir()
        except Exception: pass
    except Exception as exc:
        log(f'[ERROR] Valid video could not be moved to its final filename: {exc}')
        return 8

    size_mb = FINAL_VIDEO.stat().st_size / (1024 * 1024)
    duration = float(check.get('duration_seconds') or 0)
    log(f'[OK] MP4 validated: {FINAL_VIDEO}')
    log(f'[OK] Video duration: {duration:.2f}s · size: {size_mb:.2f} MB · H.264 MP4')

    # Recording has already stopped. Open/select the finished MP4 for the user; this is intentionally outside the video.
    try:
        subprocess.Popen(['explorer.exe', '/select,', str(FINAL_VIDEO)])
    except Exception:
        try: subprocess.Popen(['explorer.exe', str(OUT)])
        except Exception: pass

    show_info(
        'Portfolio video ready',
        f'Video recording completed and passed validation.\n\n'
        f'File: {FINAL_VIDEO.name}\n'
        f'Duration: {duration:.1f} seconds\n'
        f'Size: {size_mb:.1f} MB\n\n'
        'The milestone screenshots and audit reports are in the same output folder.'
    )
    return 0


if __name__ == '__main__':
    try: minimize_console()
    except Exception: pass
    raise SystemExit(main())
