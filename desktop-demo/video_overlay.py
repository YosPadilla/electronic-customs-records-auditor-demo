from __future__ import annotations
import argparse
import tkinter as tk

NAVY = '#071827'
NAVY_2 = '#0B2235'
TEXT = '#F5F8FB'
MUTED = '#A6BAC8'
CYAN = '#38BDF8'
GREEN = '#56D69A'
AMBER = '#F4BD61'
RED = '#EF6B6B'
PURPLE = '#B78AF0'

ACCENTS = {
    'cyan': CYAN,
    'green': GREEN,
    'amber': AMBER,
    'red': RED,
    'purple': PURPLE,
}


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


class Overlay:
    def __init__(self, root: tk.Tk, mode: str, step: str, title: str, detail: str, badge: str, duration: float, accent: str):
        self.root = root
        self.mode = mode
        self.duration = max(0.9, duration)
        self.accent = ACCENTS.get(accent, CYAN)
        self.screen_w = root.winfo_screenwidth()
        self.screen_h = root.winfo_screenheight()
        self.lower_target = None
        self.card_line = None
        self.card_line_coords = None
        root.overrideredirect(True)
        root.attributes('-topmost', True)
        try: root.attributes('-alpha', 0.0)
        except Exception: pass
        root.configure(bg=NAVY)

        if mode == 'card':
            self._build_card(step, title, detail, badge)
        else:
            self._build_lower(step, title, detail, badge)

        self._fade_in(0)
        if self.mode == 'lower' and self.lower_target:
            self._slide_in(0)
        if self.mode == 'card' and self.card_line is not None:
            self.root.after(180, lambda: self._grow_line(0))
        root.after(int((self.duration - .35) * 1000), lambda: self._fade_out(0))

    def _build_card(self, step, title, detail, badge):
        self.root.geometry(f'{self.screen_w}x{self.screen_h}+0+0')
        canvas = tk.Canvas(self.root, width=self.screen_w, height=self.screen_h, bg=NAVY, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        cx, cy = self.screen_w // 2, self.screen_h // 2
        canvas.create_text(cx, cy-122, text='CUSTOMS AUDIT WORKFLOW', fill=self.accent,
                           font=('Segoe UI', 10, 'bold'), anchor='center')
        canvas.create_text(cx, cy-73, text=step, fill=MUTED,
                           font=('Segoe UI', 11, 'bold'), anchor='center')
        canvas.create_text(cx, cy-8, text=title, fill=TEXT,
                           font=('Georgia', 36, 'bold'), anchor='center')
        canvas.create_text(cx, cy+55, text=detail, fill=MUTED,
                           font=('Segoe UI', 13), anchor='center', width=int(self.screen_w*.68), justify='center')
        self.card_line_coords=(cx-155, cy+105, cx+155, cy+105)
        self.card_line = canvas.create_line(cx-155, cy+105, cx-155, cy+105, fill=self.accent, width=2)
        self.card_canvas = canvas
        if badge:
            canvas.create_text(cx, cy+145, text=f'  {badge}  ', fill=NAVY, font=('Segoe UI', 10, 'bold'),
                               anchor='center', tags='badge')
            bbox = canvas.bbox('badge')
            if bbox:
                pad = 8
                rect = canvas.create_rectangle(bbox[0]-pad, bbox[1]-5, bbox[2]+pad, bbox[3]+5,
                                               fill=self.accent, outline=self.accent)
                canvas.tag_lower(rect, 'badge')

    def _build_lower(self, step, title, detail, badge):
        w = min(900, int(self.screen_w*.62))
        h = 132
        x = 42
        y = self.screen_h - h - 72
        self.lower_target=(w,h,x,y)
        self.root.geometry(f'{w}x{h}+{-w}+{y}')
        outer = tk.Frame(self.root, bg=NAVY, highlightthickness=1, highlightbackground='#27475E')
        outer.pack(fill='both', expand=True)
        tk.Frame(outer, bg=self.accent, width=7).pack(side='left', fill='y')
        body = tk.Frame(outer, bg=NAVY, padx=18, pady=13)
        body.pack(side='left', fill='both', expand=True)
        top = tk.Frame(body, bg=NAVY)
        top.pack(fill='x')
        tk.Label(top, text=step, bg=NAVY, fg=self.accent, font=('Segoe UI', 9, 'bold')).pack(side='left')
        if badge:
            tk.Label(top, text=f'  {badge}  ', bg=self.accent, fg=NAVY, font=('Segoe UI', 9, 'bold'), padx=5, pady=2).pack(side='right')
        tk.Label(body, text=title, bg=NAVY, fg=TEXT, font=('Segoe UI', 16, 'bold'), anchor='w').pack(fill='x', pady=(8,2))
        tk.Label(body, text=detail, bg=NAVY, fg=MUTED, font=('Segoe UI', 10), anchor='w', justify='left', wraplength=w-70).pack(fill='x')


    def _slide_in(self, step):
        if not self.lower_target:
            return
        w,h,target_x,y=self.lower_target
        p=min(1.0, step/12)
        x=round(-w + (target_x+w)*ease_out_cubic(p))
        self.root.geometry(f'{w}x{h}+{x}+{y}')
        if step < 12:
            self.root.after(18, lambda: self._slide_in(step+1))

    def _grow_line(self, step):
        if self.card_line is None or not self.card_line_coords:
            return
        x1,y1,x2,y2=self.card_line_coords
        p=min(1.0, step/14)
        half=(x2-x1)/2*ease_out_cubic(p)
        cx=(x1+x2)/2
        self.card_canvas.coords(self.card_line, cx-half, y1, cx+half, y2)
        if step < 14:
            self.root.after(18, lambda: self._grow_line(step+1))
    def _fade_in(self, step):
        p = min(1.0, step/12)
        try: self.root.attributes('-alpha', .96 * ease_out_cubic(p))
        except Exception: pass
        if step < 12:
            self.root.after(18, lambda: self._fade_in(step+1))

    def _fade_out(self, step):
        p = min(1.0, step/10)
        try: self.root.attributes('-alpha', .96 * (1-p))
        except Exception: pass
        if step < 10:
            self.root.after(20, lambda: self._fade_out(step+1))
        else:
            self.root.destroy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['card','lower'], default='lower')
    ap.add_argument('--step', default='')
    ap.add_argument('--title', default='')
    ap.add_argument('--detail', default='')
    ap.add_argument('--badge', default='')
    ap.add_argument('--duration', type=float, default=2.6)
    ap.add_argument('--accent', choices=list(ACCENTS), default='cyan')
    a = ap.parse_args()
    root = tk.Tk()
    Overlay(root, a.mode, a.step, a.title, a.detail, a.badge, a.duration, a.accent)
    root.mainloop()

if __name__ == '__main__':
    main()
