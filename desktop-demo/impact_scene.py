from __future__ import annotations
import json, time
from pathlib import Path
import tkinter as tk

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'output'
READY = OUTPUT / '.impact_ready.json'
DONE = OUTPUT / '.impact_complete'
TITLE = 'Audit Outcome — Operational Summary'

BG = '#020914'
TEXT = '#f5f8fb'
MUTED = '#8ea6ba'
SOFT = '#607a90'
CYAN = '#38bdf8'
GREEN = '#56d69a'
AMBER = '#f4bd61'
RED = '#ef6b6b'
PURPLE = '#b27bdd'


def ease_out_cubic(p: float) -> float:
    return 1 - (1-p)**3


class ImpactScene:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.w = root.winfo_screenwidth()
        self.h = root.winfo_screenheight()
        root.title(TITLE)
        root.configure(bg=BG)
        root.geometry(f'{self.w}x{self.h}+0+0')
        try: root.attributes('-fullscreen', True)
        except Exception: pass
        try: root.attributes('-topmost', True)
        except Exception: pass
        try: root.attributes('-alpha', 0.02)
        except Exception: pass
        root.bind('<Escape>', lambda e: root.destroy())

        self.canvas = tk.Canvas(root, width=self.w, height=self.h, bg=BG, highlightthickness=0)
        self.canvas.pack(fill='both', expand=True)
        self._background()
        self._build()
        OUTPUT.mkdir(exist_ok=True)
        for p in [READY, DONE]:
            try: p.unlink()
            except Exception: pass
        root.after(80, self._fade_in)
        root.after(150, self._write_ready)
        root.after(420, self._sequence)

    def _background(self):
        cx, cy = int(self.w*.74), int(self.h*.25)
        for i in range(12, 0, -1):
            radius = int(min(self.w, self.h) * (0.06 + i*0.027))
            c = max(10, 28 - i)
            color = f'#{2:02x}{9+c//4:02x}{20+c:02x}'
            self.canvas.create_oval(cx-radius, cy-radius, cx+radius, cy+radius, fill=color, outline='')
        self.canvas.create_rectangle(0, 0, self.w, self.h, fill=BG, outline='', stipple='gray75')
        self.canvas.create_line(int(self.w*.08), int(self.h*.18), int(self.w*.92), int(self.h*.18), fill='#0b2132', width=1)
        self.canvas.create_line(int(self.w*.08), int(self.h*.82), int(self.w*.92), int(self.h*.82), fill='#071b2a', width=1)

    def _build(self):
        cx = self.w // 2
        self.eyebrow = self.canvas.create_text(cx, int(self.h*.145), text='AUDIT OUTCOME', fill=CYAN,
                                                font=('Segoe UI', 10, 'bold'), anchor='center', state='hidden')
        self.context = self.canvas.create_text(cx, int(self.h*.19), text='Electronic customs evidence review · 20 records', fill=MUTED,
                                              font=('Segoe UI', 13), anchor='center', state='hidden')

        left_x = int(self.w*.31); right_x = int(self.w*.69); y = int(self.h*.43)
        self.left_num = self.canvas.create_text(left_x, y, text='0', fill=TEXT, font=('Georgia', 108, 'bold'), anchor='center', state='hidden')
        self.left_label = self.canvas.create_text(left_x, y+92, text='RECORDS AUDITED', fill=SOFT, font=('Segoe UI', 10, 'bold'), anchor='center', state='hidden')
        self.right_num = self.canvas.create_text(right_x, y, text='0', fill=GREEN, font=('Georgia', 108, 'bold'), anchor='center', state='hidden')
        self.right_label = self.canvas.create_text(right_x, y+92, text='COMPLETE', fill=SOFT, font=('Segoe UI', 10, 'bold'), anchor='center', state='hidden')

        self.line_start = int(self.w*.43); self.line_end = int(self.w*.57); self.line_y = y+6
        self.flow_line = self.canvas.create_line(self.line_start, self.line_y, self.line_start, self.line_y, fill=CYAN, width=2, state='hidden')
        self.flow_arrow = self.canvas.create_text(self.line_end+18, self.line_y, text='→', fill=CYAN, font=('Segoe UI', 26), anchor='center', state='hidden')

        head_y = int(self.h*.665)
        self.follow_num = self.canvas.create_text(int(self.w*.44), head_y, text='0', fill=TEXT, font=('Georgia', 48, 'bold'), anchor='e', state='hidden')
        self.follow_text = self.canvas.create_text(int(self.w*.45), head_y+2, text=' records surfaced for follow-up', fill=TEXT,
                                                 font=('Georgia', 38), anchor='w', state='hidden')

        by = int(self.h*.735)
        self.breakdown=[]
        items=[('5', 'INCOMPLETE', RED), ('2', 'REVIEW', AMBER), ('1', 'NOT FOUND', PURPLE)]
        xs=[int(self.w*.38), int(self.w*.50), int(self.w*.62)]
        for x, (n, label, color) in zip(xs, items):
            num=self.canvas.create_text(x, by, text=n, fill=color, font=('Segoe UI', 17, 'bold'), anchor='e', state='hidden')
            lab=self.canvas.create_text(x+8, by, text=label, fill=MUTED, font=('Segoe UI', 9, 'bold'), anchor='w', state='hidden')
            self.breakdown.append((num, lab))

        self.foot = self.canvas.create_text(cx, int(self.h*.865), text='Traceable outputs · XLSX · CSV · evidence map · audit log', fill=SOFT,
                                           font=('Segoe UI', 9), anchor='center', state='hidden')
        self.boundary = self.canvas.create_text(cx, int(self.h*.905), text='Illustrative dataset · no production systems connected', fill='#405b70',
                                               font=('Segoe UI', 8), anchor='center', state='hidden')

    def _fade_in(self, step=0):
        try:
            self.root.attributes('-alpha', min(1.0, 0.02 + step/18))
        except Exception:
            return
        if step < 18:
            self.root.after(24, lambda: self._fade_in(step+1))

    def _show(self, *items):
        for item in items:
            self.canvas.itemconfigure(item, state='normal')

    def animate_number(self, item, start, end, duration, on_done=None):
        t0=time.perf_counter()
        def frame():
            p=min(1.0, (time.perf_counter()-t0)/duration)
            value=round(start + (end-start)*ease_out_cubic(p))
            self.canvas.itemconfigure(item, text=str(value))
            if p < 1:
                self.root.after(16, frame)
            elif on_done:
                on_done()
        frame()

    def animate_line(self, duration=.8, on_done=None):
        t0=time.perf_counter(); self._show(self.flow_line)
        def frame():
            p=min(1.0, (time.perf_counter()-t0)/duration)
            x=self.line_start + (self.line_end-self.line_start)*ease_out_cubic(p)
            self.canvas.coords(self.flow_line, self.line_start, self.line_y, x, self.line_y)
            if p < 1:
                self.root.after(16, frame)
            else:
                self._show(self.flow_arrow)
                if on_done: self.root.after(160, on_done)
        frame()

    def _sequence(self):
        self._show(self.eyebrow, self.context)
        self.root.after(320, self._beat_left)

    def _beat_left(self):
        self._show(self.left_num, self.left_label)
        self.animate_number(self.left_num, 0, 20, .9, lambda: self.root.after(170, self._beat_line))

    def _beat_line(self):
        self.animate_line(.72, self._beat_right)

    def _beat_right(self):
        self._show(self.right_num, self.right_label)
        self.animate_number(self.right_num, 0, 12, .68, lambda: self.root.after(330, self._beat_follow))

    def _beat_follow(self):
        self._show(self.follow_num, self.follow_text)
        self.animate_number(self.follow_num, 0, 8, .78, lambda: self.root.after(280, self._beat_breakdown))

    def _beat_breakdown(self, idx=0):
        if idx < len(self.breakdown):
            self._show(*self.breakdown[idx])
            self.root.after(230, lambda: self._beat_breakdown(idx+1))
            return
        self.root.after(220, self._finish)

    def _finish(self):
        self._show(self.foot, self.boundary)
        DONE.write_text(json.dumps({'complete':12, 'incomplete':5, 'review':2, 'not_found':1}), encoding='utf-8')

    def _write_ready(self):
        try: READY.write_text(json.dumps({'title': TITLE}), encoding='utf-8')
        except Exception: pass


def main():
    root=tk.Tk(); ImpactScene(root); root.mainloop()

if __name__=='__main__': main()
