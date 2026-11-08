
from __future__ import annotations
import argparse, json, queue, threading, time
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from audit_engine import run_audit

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'workspace_data'
ARCH=DATA/'records_3500'
OUTPUT=ROOT/'output'
READY=OUTPUT/'.gui_ready.json'
DONE=OUTPUT/'.desktop_demo_complete'
TITLE='Electronic Customs Records Auditor'

class App:
    def __init__(self, root, director=False):
        self.root=root; self.director=director; self.q=queue.Queue(); self.results={}; self.stage_labels=[]; self.overlay=None
        root.title(TITLE); root.geometry('1440x860'); root.minsize(1180,760)
        try: root.state('zoomed')
        except Exception: pass
        self.input_var=tk.StringVar(value=str(DATA/'Customs_Audit_Universe.xlsx'))
        self.arch_var=tk.StringVar(value=str(ARCH))
        self.out_var=tk.StringVar(value=str(OUTPUT))
        self.status_var=tk.StringVar(value='Ready · 20 customs records loaded for review')
        self.current_var=tk.StringVar(value='Universe ready')
        self.progress_var=tk.DoubleVar(value=0)
        self.live_metric_var=tk.StringVar(value='0 / 20 processed')
        self._build(); self.root.after(120,self._poll); self.root.after(650,self._write_ready)

    def _build(self):
        bg='#eef3f7'; panel='#ffffff'; navy='#12324a'; blue='#0a6ed1'; muted='#58707f'; green='#1f7a54'; amber='#a06a00'; red='#b03f3f'; purple='#7a4d9b'
        self.colors={'COMPLETE':green,'INCOMPLETE':red,'REVIEW':amber,'NOT FOUND':purple}
        self.root.configure(bg=bg)
        style=ttk.Style();
        try: style.theme_use('clam')
        except Exception: pass
        style.configure('TFrame',background=bg); style.configure('Panel.TFrame',background=panel)
        style.configure('TLabel',background=bg,font=('Segoe UI',9),foreground='#28404d')
        style.configure('Title.TLabel',font=('Segoe UI',20,'bold'),foreground=navy)
        style.configure('Sub.TLabel',font=('Segoe UI',9),foreground=muted)
        style.configure('Field.TLabel',font=('Segoe UI',9,'bold'),foreground=navy)
        style.configure('Primary.TButton',font=('Segoe UI',10,'bold'))
        style.configure('Treeview',font=('Segoe UI',8),rowheight=24,background='white',fieldbackground='white')
        style.configure('Treeview.Heading',font=('Segoe UI',8,'bold'))
        style.configure('Accent.Horizontal.TProgressbar', troughcolor='#d8e3ea', bordercolor='#d8e3ea', background=blue, lightcolor=blue, darkcolor=blue)
        outer=ttk.Frame(self.root,padding=(18,14),style='TFrame'); outer.pack(fill='both',expand=True)

        # header
        header = tk.Frame(outer,bg=navy,height=88)
        header.pack(fill='x')
        header.pack_propagate(False)
        left = tk.Frame(header,bg=navy); left.pack(side='left',fill='both',expand=True,padx=18,pady=14)
        tk.Label(left,text='Electronic Customs Records Auditor',bg=navy,fg='white',font=('Segoe UI',20,'bold')).pack(anchor='w')
        tk.Label(left,text='Operational review across compressed customs-record archives',bg=navy,fg='#c5d5e2',font=('Segoe UI',9)).pack(anchor='w',pady=(2,0))
        right = tk.Frame(header,bg=navy); right.pack(side='right',padx=18,pady=16)
        tk.Label(right,text='ILLUSTRATIVE DATA',bg='#1d4665',fg='#dfeffc',font=('Segoe UI',8,'bold'),padx=10,pady=6).pack(anchor='e')
        tk.Label(right,textvariable=self.live_metric_var,bg=navy,fg='#d9e7f2',font=('Segoe UI',9,'bold')).pack(anchor='e',pady=(10,0))

        # workflow rail
        rail = tk.Frame(outer,bg=bg)
        rail.pack(fill='x',pady=(10,8))
        steps = ['UNIVERSE LOADED','SCAN ARCHIVES','VERIFY EVIDENCE','WRITE OUTPUTS','SUMMARY']
        for i,step in enumerate(steps):
            cell=tk.Frame(rail,bg=bg)
            cell.pack(side='left',fill='x',expand=True)
            dot=tk.Label(cell,text='●',bg=bg,fg='#9fb4c3',font=('Segoe UI',10,'bold'))
            dot.pack(side='left')
            lbl=tk.Label(cell,text=step,bg=bg,fg='#6c8595',font=('Segoe UI',8,'bold'))
            lbl.pack(side='left',padx=(4,0))
            self.stage_labels.append((dot,lbl))
            if i < len(steps)-1:
                tk.Frame(cell,bg='#d3dee6',height=2,width=40).pack(side='left',fill='x',expand=True,padx=8)
        self._set_stage(0)

        # inputs
        formpanel=tk.Frame(outer,bg=panel,highlightthickness=1,highlightbackground='#d7e1e8')
        formpanel.pack(fill='x',pady=(2,8))
        form=ttk.Frame(formpanel,padding=(12,10),style='Panel.TFrame'); form.pack(fill='x')
        self._path_row(form,0,'Audit workbook',self.input_var,False)
        self._path_row(form,1,'Records folder',self.arch_var,True)
        self._path_row(form,2,'Output folder',self.out_var,True)

        options=ttk.Frame(outer); options.pack(fill='x',pady=(6,6))
        ttk.Label(options,text='Audit options',style='Field.TLabel').pack(side='left')
        for txt in ['Inspect ZIP archives','Validate paid declaration','Match commercial invoices','Generate evidence map']:
            v=tk.BooleanVar(value=True); ttk.Checkbutton(options,text=txt,variable=v).pack(side='left',padx=(14,0))

        action=ttk.Frame(outer); action.pack(fill='x',pady=(2,8))
        self.run_btn=ttk.Button(action,text='Run audit',style='Primary.TButton',command=self.run); self.run_btn.pack(side='left')
        self.open_btn=ttk.Button(action,text='Open output folder',command=self.open_output); self.open_btn.pack(side='left',padx=7)
        ttk.Label(action,textvariable=self.status_var,style='Sub.TLabel').pack(side='left',padx=14)
        self.progress=ttk.Progressbar(action,variable=self.progress_var,maximum=20,length=300,style='Accent.Horizontal.TProgressbar'); self.progress.pack(side='right')

        body=ttk.Panedwindow(outer,orient='horizontal'); body.pack(fill='both',expand=True)
        left=ttk.Frame(body,padding=(0,0,10,0)); right=ttk.Frame(body,padding=(10,0,0,0)); body.add(left,weight=7); body.add(right,weight=3)

        # current activity card
        curr=tk.Frame(left,bg=panel,highlightthickness=1,highlightbackground='#d7e1e8')
        curr.pack(fill='x',pady=(0,8))
        currin=ttk.Frame(curr,padding=(12,10),style='Panel.TFrame'); currin.pack(fill='x')
        ttk.Label(currin,text='Current activity',style='Field.TLabel').pack(anchor='w')
        topcurr=ttk.Frame(currin,style='Panel.TFrame'); topcurr.pack(fill='x',pady=(4,0))
        self.current_title=tk.Label(topcurr,textvariable=self.current_var,bg=panel,fg=navy,font=('Segoe UI',11,'bold'))
        self.current_title.pack(side='left')
        self.current_status=tk.Label(topcurr,text='Awaiting execution',bg='#edf4fa',fg='#3f6278',font=('Segoe UI',8,'bold'),padx=9,pady=4)
        self.current_status.pack(side='right')
        self.current_meta=tk.Label(currin,text='Open archive → classify evidence → match expected invoices → assign status',bg=panel,fg=muted,font=('Segoe UI',9))
        self.current_meta.pack(anchor='w',pady=(6,0))

        head=ttk.Frame(left); head.pack(fill='x',pady=(0,6))
        ttk.Label(head,text='Audit results',style='Field.TLabel').pack(side='left')
        cols=('row','exp','ped','status','paid','inv','doda','cg','evidence')
        self.tree=ttk.Treeview(left,columns=cols,show='headings',height=16)
        headers=[('row','#',42),('exp','EXPEDIENTE',180),('ped','PEDIMENTO',90),('status','STATUS',105),('paid','PAID',55),('inv','INVOICES',78),('doda','DODA',55),('cg','EXPENSE',65),('evidence','EVIDENCE',65)]
        for c,h,w in headers: self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor='center' if c!='exp' else 'w',stretch=c=='exp')
        self.tree.pack(fill='both',expand=True)
        for name,color in self.colors.items(): self.tree.tag_configure(name,foreground=color)

        logbox=tk.Frame(left,bg=panel,highlightthickness=1,highlightbackground='#d7e1e8')
        logbox.pack(fill='x',pady=(8,0))
        loginner=ttk.Frame(logbox,padding=8,style='Panel.TFrame'); loginner.pack(fill='x')
        ttk.Label(loginner,text='Processing timeline',style='Field.TLabel').pack(anchor='w')
        self.log=tk.Text(loginner,height=7,font=('Consolas',8),bg='#f8fbfd',fg='#243842',relief='flat',wrap='word'); self.log.pack(fill='x',pady=(6,0))

        summary=tk.Frame(right,bg=panel,highlightthickness=1,highlightbackground='#d7e1e8')
        summary.pack(fill='x')
        inner=ttk.Frame(summary,padding=(10,10),style='Panel.TFrame'); inner.pack(fill='x')
        ttk.Label(inner,text='Batch summary',style='Field.TLabel').pack(anchor='w')
        self.cards={}
        for label in ['COMPLETE','INCOMPLETE','REVIEW','NOT FOUND']:
            color=self.colors[label]
            f=tk.Frame(inner,bg='white',highlightthickness=1,highlightbackground='#d8e1e6')
            f.pack(fill='x',pady=5)
            n=tk.Label(f,text='0',bg='white',fg=color,font=('Segoe UI',24,'bold'),width=4,anchor='e'); n.pack(side='left',padx=(6,10),pady=8)
            tx=tk.Frame(f,bg='white'); tx.pack(side='left',fill='both',expand=True,pady=8)
            tk.Label(tx,text=label,bg='white',fg='#415968',font=('Segoe UI',9,'bold')).pack(anchor='w')
            subt = {
                'COMPLETE':'Paid declaration and expected invoices matched',
                'INCOMPLETE':'Critical evidence missing',
                'REVIEW':'Needs analyst validation',
                'NOT FOUND':'Expected archive absent'
            }[label]
            tk.Label(tx,text=subt,bg='white',fg='#6b8190',font=('Segoe UI',8)).pack(anchor='w')
            self.cards[label]=n
        logic=tk.Frame(right,bg=panel,highlightthickness=1,highlightbackground='#d7e1e8')
        logic.pack(fill='x',pady=(10,0))
        logicin=ttk.Frame(logic,padding=10,style='Panel.TFrame'); logicin.pack(fill='x')
        ttk.Label(logicin,text='Evidence logic',style='Field.TLabel').pack(anchor='w')
        txt='COMPLETE  ·  Paid declaration + expected commercial invoices matched\nINCOMPLETE  ·  Critical evidence is missing\nREVIEW  ·  Commercial evidence exists but needs human validation\nNOT FOUND  ·  Expected archive is absent'
        ttk.Label(logicin,text=txt,style='Sub.TLabel',justify='left',wraplength=320).pack(anchor='w',pady=(6,0))

    def _set_stage(self, idx:int):
        for i,(dot,lbl) in enumerate(self.stage_labels):
            if i < idx:
                dot.config(fg='#18a957'); lbl.config(fg='#355a49')
            elif i == idx:
                dot.config(fg='#0a6ed1'); lbl.config(fg='#12324a')
            else:
                dot.config(fg='#9fb4c3'); lbl.config(fg='#6c8595')

    def _path_row(self,parent,row,label,var,is_dir):
        ttk.Label(parent,text=label,style='Field.TLabel').grid(row=row,column=0,sticky='w',pady=3)
        e=ttk.Entry(parent,textvariable=var); e.grid(row=row,column=1,sticky='ew',padx=10,pady=3)
        def browse():
            p=filedialog.askdirectory() if is_dir else filedialog.askopenfilename(filetypes=[('Excel workbook','*.xlsx')])
            if p: var.set(p)
        ttk.Button(parent,text='Browse…',command=browse,width=11).grid(row=row,column=2,pady=3)
        parent.columnconfigure(1,weight=1)

    def _write_ready(self):
        try:
            self.root.update_idletasks()
            READY.parent.mkdir(exist_ok=True)
            READY.write_text(json.dumps({'run_x':self.run_btn.winfo_rootx()+self.run_btn.winfo_width()//2,'run_y':self.run_btn.winfo_rooty()+self.run_btn.winfo_height()//2}),encoding='utf-8')
        except Exception: pass

    def append_log(self,msg):
        self.log.insert('end',time.strftime('%H:%M:%S')+'  '+msg+'\n'); self.log.see('end')

    def run(self):
        if self.run_btn['state']=='disabled': return
        if self.overlay is not None:
            self.overlay.destroy(); self.overlay=None
        try: DONE.unlink()
        except Exception: pass
        self.tree.delete(*self.tree.get_children()); self.progress_var.set(0); self.current_var.set('Initializing audit run')
        self.current_status.config(text='RUNNING',bg='#e8f3ff',fg='#0a6ed1')
        self.current_meta.config(text='Loading audit universe and preparing compressed-record scan')
        self.results = {}
        self.live_metric_var.set('0 / 20 processed')
        self._set_stage(1)
        for x in self.cards.values(): x.config(text='0')
        self.run_btn.config(state='disabled'); self.status_var.set('Audit in progress…'); self.append_log('Loading audit universe and scanning compressed records.')
        threading.Thread(target=self._worker,daemon=True).start()

    def _worker(self):
        def cb(evt): self.q.put(('progress',evt))
        try:
            data=run_audit(progress=cb,per_record_delay=.20)
            self.q.put(('done',data))
        except Exception as e: self.q.put(('error',str(e)))

    def _poll(self):
        try:
            while True:
                kind,payload=self.q.get_nowait()
                if kind=='progress': self._progress(payload)
                elif kind=='done': self._done(payload)
                else: self.status_var.set('Audit failed'); self.append_log('ERROR · '+payload); self.current_status.config(text='FAILED',bg='#fdeaea',fg='#b03f3f'); self.run_btn.config(state='normal')
        except queue.Empty: pass
        self.root.after(100,self._poll)

    def _bump_card(self, label):
        target=self.results.get(label,0)
        self.cards[label].config(text=str(target))
        # pulse
        w=self.cards[label]
        orig=w.cget('font')
        w.config(font=('Segoe UI',26,'bold'))
        self.root.after(180, lambda: w.config(font=('Segoe UI',24,'bold')))

    def _progress(self,e):
        if e.get('phase')=='start':
            self.current_var.set(f"Processing {e['row']:02d}/20 · {e['expediente_id']}")
            self.current_meta.config(text=f"Opening {e['archive']} and classifying evidence")
            self.live_metric_var.set(f"{e['row']-1} / 20 processed")
            self._set_stage(2)
            self.append_log(f"Opening {e['archive']} …")
        elif e.get('phase')=='result':
            r=e['record']; self.progress_var.set(r['row']);
            item=self.tree.insert('', 'end', values=(r['row'],r['expediente_id'],r['pedimento'],r['status'],'YES' if r['paid_declaration'] else 'NO',f"{r['invoices_found']}/{r['invoices_expected']}",'YES' if r['doda'] else 'NO','YES' if r['expense_account'] else 'NO',r['evidence_count']),tags=(r['status'],))
            self.tree.selection_set(item); self.tree.focus(item); self.tree.see(item)
            self.results[r['status']]=self.results.get(r['status'],0)+1; self._bump_card(r['status'])
            self.live_metric_var.set(f"{r['row']} / 20 processed")
            self.current_status.config(text=r['status'],bg='#eef4f8',fg=self.colors[r['status']])
            self.current_meta.config(text=r['reason'])
            self.append_log(f"{r['status']} · {r['expediente_id']} · {r['reason']}")

    def _animate_summary(self, overlay, counts):
        labels={}
        colors=self.colors
        hdr=tk.Label(overlay,text='Audit complete',bg='#102c41',fg='white',font=('Segoe UI',16,'bold'))
        hdr.pack(anchor='w')
        tk.Label(overlay,text='Operational summary · compressed-record evidence review finished successfully',bg='#102c41',fg='#cfe0ec',font=('Segoe UI',9)).pack(anchor='w',pady=(3,14))
        row=tk.Frame(overlay,bg='#102c41'); row.pack(fill='x')
        for label in ['COMPLETE','INCOMPLETE','REVIEW','NOT FOUND']:
            box=tk.Frame(row,bg='white',highlightthickness=1,highlightbackground='#cdd9e1')
            box.pack(side='left',fill='both',expand=True,padx=5)
            num=tk.Label(box,text='0',bg='white',fg=colors[label],font=('Segoe UI',24,'bold'))
            num.pack(pady=(14,2))
            tk.Label(box,text=label,bg='white',fg='#425a68',font=('Segoe UI',8,'bold')).pack(pady=(0,12))
            labels[label]=num
        foot=tk.Label(overlay,text='Reports generated · XLSX · CSV · evidence map · audit log',bg='#102c41',fg='#d3e3ef',font=('Segoe UI',9,'bold'))
        foot.pack(anchor='w',pady=(14,0))
        def run_sequence(order=['COMPLETE','INCOMPLETE','REVIEW','NOT FOUND'], idx=0):
            if idx>=len(order):
                return
            lab=order[idx]; target=counts.get(lab,0)
            current=0
            def step():
                nonlocal current
                if current < target:
                    current += 1
                    labels[lab].config(text=str(current))
                    self.root.after(80, step)
                else:
                    self.root.after(150, lambda: run_sequence(order, idx+1))
            step()
        run_sequence()

    def _show_overlay(self, data):
        if self.overlay is not None:
            self.overlay.destroy()
        self.overlay=tk.Frame(self.root,bg='#102c41',highlightthickness=2,highlightbackground='#d1dee7')
        # place in center over tree area
        self.overlay.place(relx=0.5, rely=0.52, anchor='center', width=760, height=260)
        inner=tk.Frame(self.overlay,bg='#102c41',padx=18,pady=16)
        inner.pack(fill='both',expand=True)
        self._animate_summary(inner, data['summary']['counts'])

    def _done(self,data):
        s=data['summary']; self.status_var.set(f"Audit complete · {s['archives_found']} archives found · reports generated")
        self.current_var.set('20/20 processed'); self.current_status.config(text='COMPLETE',bg='#e9f6ef',fg='#1f7a54')
        self.current_meta.config(text='XLSX, CSV, evidence map and audit log were written to the output folder')
        self.live_metric_var.set('20 / 20 processed')
        self._set_stage(4)
        self.run_btn.config(state='normal'); self.append_log('Exports generated: XLSX · CSV · evidence map · audit log.')
        DONE.write_text(json.dumps(s,indent=2),encoding='utf-8')
        if not self.director: messagebox.showinfo('Audit complete','20 records processed.\n\nResults were written to the output folder.')

    def open_output(self):
        import os; os.startfile(str(OUTPUT))

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--director',action='store_true'); a=ap.parse_args()
    OUTPUT.mkdir(exist_ok=True)
    for p in [READY,DONE]:
        try:p.unlink()
        except Exception:pass
    root=tk.Tk(); App(root,a.director); root.mainloop()
if __name__=='__main__': main()
