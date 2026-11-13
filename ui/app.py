"""Interfaz de escritorio integrada con el prototipo original Banco Senior+.

La capa visual invoca Sistema y sus módulos. No implementa Observer ni Mediator.
"""
from __future__ import annotations

import csv
import io
import queue
import re
import shutil
import sys
import tempfile
import threading
import tkinter as tk
import uuid
from collections import deque
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from banco_senior.formato import pesos
from banco_senior.pension import HistorialConsignaciones
from banco_senior.sistema import armar_desde_csv

NAVY = '#142B4A'
BLUE = '#2864A6'
PALE = '#F3F6FA'
INK = '#243449'
MUTED = '#718096'
GREEN = '#18845B'
RED = '#C34444'
GOLD = '#B7791F'
WHITE = '#FFFFFF'


class QueueWriter(io.TextIOBase):
    def __init__(self, output_queue): self.output_queue = output_queue
    def write(self, value):
        if value: self.output_queue.put(value)
        return len(value)
    def flush(self): pass


class Diagrama(tk.Canvas):
    """Diagrama de cajas y flechas que se ilumina con los pasos de la traza.

    Solo dibuja: no implementa ni sustituye a Observer o Mediator. Las posiciones
    son fracciones del tamaño del lienzo, así que se redibuja al cambiar de tamaño.
    """

    REPOSO = '#F6F8FB'
    LINEA = '#B8C4D2'

    def __init__(self, parent, nodos, aristas, color, inactivos=(), height=260):
        super().__init__(parent, height=height, bg=WHITE, highlightthickness=0)
        self.nodos = nodos        # nombre -> (fx, fy, etiqueta)
        self.aristas = aristas    # (origen, destino, doble_flecha)
        self.color = color
        self.activo = {n: n not in inactivos for n in nodos}
        self._ids = {}
        self._tok = {}
        self.bind('<Configure>', lambda e: self._dibujar())

    def _caja(self, nombre):
        fx, fy, _ = self.nodos[nombre]
        return fx * self.winfo_width(), fy * self.winfo_height(), 58, 24

    def _punto(self, a, b):
        ax, ay, hw, hh = self._caja(a)
        bx, by, _, _ = self._caja(b)
        dx, dy = bx - ax, by - ay
        if not dx and not dy:
            return ax, ay
        t = min(hw / abs(dx) if dx else 1e9, hh / abs(dy) if dy else 1e9)
        return ax + dx * t, ay + dy * t

    def _dibujar(self):
        self.delete('all')
        self._ids = {}
        if self.winfo_width() < 50:
            return
        for a, b, doble in self.aristas:
            x1, y1 = self._punto(a, b)
            x2, y2 = self._punto(b, a)
            linea = self.create_line(x1, y1, x2, y2, width=2, fill=self.LINEA,
                                     arrow='both' if doble else 'last', arrowshape=(10, 12, 4))
            self._ids[(a, b)] = self._ids[(b, a)] = linea
        for nombre, (fx, fy, etiqueta) in self.nodos.items():
            cx, cy, hw, hh = self._caja(nombre)
            act = self.activo[nombre]
            rect = self.create_rectangle(cx - hw, cy - hh, cx + hw, cy + hh, fill=self.REPOSO,
                                         outline=self.color, width=2, dash=None if act else (4, 3))
            texto = self.create_text(cx, cy, text=etiqueta, justify='center',
                                     font=('Segoe UI', 9, 'bold'), fill=NAVY if act else MUTED)
            self._ids[nombre] = (rect, texto)

    def _marcar(self, clave, ms, volver):
        tok = self._tok[clave] = self._tok.get(clave, 0) + 1
        def revertir():
            try:
                if self._tok.get(clave) == tok and clave in self._ids:
                    volver()
            except tk.TclError:
                pass
        self.after(ms, revertir)

    def encender(self, nombre, ms=700):
        ids = self._ids.get(nombre)
        if not ids:
            return
        rect, texto = ids
        self.itemconfigure(rect, fill=self.color, outline=self.color)
        self.itemconfigure(texto, fill=WHITE)
        def volver():
            self.itemconfigure(rect, fill=self.REPOSO, outline=self.color)
            self.itemconfigure(texto, fill=NAVY if self.activo.get(nombre, True) else MUTED)
        self._marcar(nombre, ms, volver)

    def pulso(self, a, b, ms=700):
        linea = self._ids.get((a, b))
        if linea is None:
            return
        self.itemconfigure(linea, fill=self.color, width=4)
        self._marcar((a, b), ms, lambda: self.itemconfigure(linea, fill=self.LINEA, width=2))

    def set_activo(self, nombre, valor):
        if nombre in self.activo and self.activo[nombre] != valor:
            self.activo[nombre] = valor
            self._dibujar()


# Nombre de la clase del backend -> nodo del diagrama.
NODO = {'GestionUsuario': 'Gestion', 'Notificaciones': 'Notificaciones', 'Auditoria': 'Auditoria',
        'HistorialConsignaciones': 'Historial', 'ProcesadorConsignacion': 'Procesador'}
VELOCIDADES = {'Lenta': 900, 'Normal': 450, 'Rápida': 150}


class BancoSeniorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Banco Senior+ | Centro de operaciones')
        self.geometry('1420x900')
        self.minsize(1120, 720)
        self.configure(bg=PALE)
        self.output_queue = queue.Queue()
        self.anim_queue = deque()
        self.busy = False
        self.historial = None
        self.historial_suscrito = False
        self.last_result = None
        self.current_page = 'Inicio'
        self.doc_combos = []
        self.speed_var = tk.StringVar(value='Normal')
        self.pay_vars = {'doc': tk.StringVar(), 'monto': tk.StringVar(value='1500000'),
                         'periodo': tk.StringVar(value=datetime.now().strftime('%Y-%m'))}
        self.system = self._new_system()
        self._style()
        self._layout()
        self.show_page('Inicio')
        self.after(100, self._drain_output)
        self.after(100, self._anim_tick)

    def _new_system(self):
        # El fallo de Jorge forma parte del escenario didáctico original.
        return armar_desde_csv(ROOT / 'datos' / 'pensionados.csv', fallar_para=('3001110002',))

    def _style(self):
        s = ttk.Style(self)
        try: s.theme_use('clam')
        except tk.TclError: pass
        s.configure('Treeview', background=WHITE, fieldbackground=WHITE, foreground=INK,
                    rowheight=34, font=('Segoe UI', 10), borderwidth=0)
        s.configure('Treeview.Heading', background='#E8EEF5', foreground=NAVY,
                    font=('Segoe UI Semibold', 10), padding=9)
        s.map('Treeview', background=[('selected', '#DCE9F7')], foreground=[('selected', NAVY)])
        s.configure('TCombobox', padding=7, font=('Segoe UI', 10))
        s.configure('TEntry', padding=8, font=('Segoe UI', 10))

    def _layout(self):
        shell = tk.Frame(self, bg=PALE); shell.pack(fill='both', expand=True)
        side = tk.Frame(shell, bg=NAVY, width=250); side.pack(side='left', fill='y'); side.pack_propagate(False)
        brand = tk.Frame(side, bg=NAVY); brand.pack(fill='x', padx=22, pady=(28, 34))
        tk.Label(brand, text='BS+', bg='#24486F', fg='white', font=('Segoe UI', 19, 'bold'),
                 width=3, height=1).pack(anchor='w')
        tk.Label(brand, text='Banco Senior+', bg=NAVY, fg=WHITE,
                 font=('Segoe UI', 17, 'bold')).pack(anchor='w', pady=(12, 2))
        tk.Label(brand, text='CENTRO DE OPERACIONES', bg=NAVY, fg='#AFC2D8',
                 font=('Segoe UI', 8, 'bold')).pack(anchor='w')
        self.nav_buttons = {}
        for label in ['Inicio', 'Usuarios', 'Pensión y productos', 'Notificaciones', 'Auditoría', 'Patrones', 'Escenarios']:
            b = tk.Button(side, text='  '+label, anchor='w', relief='flat', bd=0,
                          bg=NAVY, fg='#D7E2EE', activebackground='#24486F', activeforeground=WHITE,
                          font=('Segoe UI', 11), padx=18, pady=13,
                          command=lambda x=label: self.show_page(x))
            b.pack(fill='x', padx=12, pady=2); self.nav_buttons[label] = b
        tk.Frame(side, bg='#35516F', height=1).pack(fill='x', padx=20, pady=(24, 12))
        tk.Label(side, text='PROTOTIPO ACADÉMICO\nDatos sintéticos · ejecución local', bg=NAVY,
                 fg='#AFC2D8', justify='left', font=('Segoe UI', 9), padx=22).pack(anchor='w')

        main = tk.Frame(shell, bg=PALE); main.pack(side='left', fill='both', expand=True)
        top = tk.Frame(main, bg=WHITE, height=68); top.pack(fill='x'); top.pack_propagate(False)
        self.page_title = tk.Label(top, text='', bg=WHITE, fg=NAVY, font=('Segoe UI', 18, 'bold'))
        self.page_title.pack(side='left', padx=28)
        self.status = tk.Label(top, text='● Sistema listo', bg=WHITE, fg=GREEN, font=('Segoe UI', 10, 'bold'))
        self.status.pack(side='right', padx=28)
        tk.Button(top, text='↻ Reiniciar sistema', command=self.reset_system, bg=WHITE, fg=BLUE,
                  activebackground=PALE, relief='flat', bd=0, cursor='hand2',
                  font=('Segoe UI', 10, 'bold')).pack(side='right', padx=4)
        self.content = tk.Frame(main, bg=PALE); self.content.pack(fill='both', expand=True, padx=26, pady=22)
        self._build_pages()

    def _build_pages(self):
        self.pages = {}
        for name in ['Inicio','Usuarios','Pensión y productos','Notificaciones','Auditoría','Patrones','Escenarios']:
            f = tk.Frame(self.content, bg=PALE); self.pages[name] = f
        self._dashboard(self.pages['Inicio'])
        self._users(self.pages['Usuarios'])
        self._pension(self.pages['Pensión y productos'])
        self._notifications(self.pages['Notificaciones'])
        self._audit(self.pages['Auditoría'])
        self._patterns(self.pages['Patrones'])
        self._scenarios(self.pages['Escenarios'])

    def show_page(self, name):
        for p in self.pages.values(): p.pack_forget()
        self.pages[name].pack(fill='both', expand=True)
        self.current_page = name
        self.page_title.config(text=name)
        for n,b in self.nav_buttons.items():
            b.config(bg='#24486F' if n == name else NAVY, fg=WHITE if n == name else '#D7E2EE')
        self.refresh_all()

    def _heading(self, parent, title, subtitle):
        tk.Label(parent, text=title, bg=PALE, fg=NAVY, font=('Segoe UI', 19, 'bold')).pack(anchor='w')
        tk.Label(parent, text=subtitle, bg=PALE, fg=MUTED, font=('Segoe UI', 10)).pack(anchor='w', pady=(4,18))

    def _card(self, parent, label, value, color=BLUE):
        c=tk.Frame(parent,bg=WHITE,highlightthickness=1,highlightbackground='#E5EAF0')
        tk.Frame(c,bg=color,width=5).pack(side='left',fill='y')
        body=tk.Frame(c,bg=WHITE); body.pack(side='left',fill='both',expand=True,padx=16,pady=15)
        tk.Label(body,text=label,bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(anchor='w')
        val=tk.Label(body,text=value,bg=WHITE,fg=NAVY,font=('Segoe UI',22,'bold')); val.pack(anchor='w',pady=(5,0))
        return c,val

    def _button(self, parent, text, command, color=BLUE):
        return tk.Button(parent,text=text,command=command,bg=color,fg=WHITE,activebackground=NAVY,
                         activeforeground=WHITE,relief='flat',bd=0,cursor='hand2',
                         font=('Segoe UI',10,'bold'),padx=15,pady=10)

    def _tree(self, parent, columns, headings, widths=None, height=9):
        wrap=tk.Frame(parent,bg=WHITE); wrap.pack(fill='both',expand=True)
        tree=ttk.Treeview(wrap,columns=columns,show='headings',height=height)
        for i,(col,head) in enumerate(zip(columns,headings)):
            tree.heading(col,text=head); tree.column(col,width=(widths[i] if widths else 150),anchor='w')
        y=ttk.Scrollbar(wrap,orient='vertical',command=tree.yview); tree.configure(yscrollcommand=y.set)
        tree.pack(side='left',fill='both',expand=True); y.pack(side='right',fill='y')
        return tree

    def _dashboard(self, p):
        self._heading(p,'Bienvenida a Banco Senior+','Vista general del prototipo y de la actividad registrada en esta sesión.')
        cards=tk.Frame(p,bg=PALE); cards.pack(fill='x')
        self.kpis=[]
        destinos=[('Usuarios',None),('Auditoría','AbonoRegistrado'),('Notificaciones',None),('Patrones',None)]
        for (label,val,col),(page,filt) in zip([('Pensionados','—',BLUE),('Abonos procesados','0',GREEN),('Avisos enviados','0',GOLD),('Eventos Observer','0',RED)],destinos):
            c,v=self._card(cards,label,val,col); c.pack(side='left',fill='x',expand=True,padx=(0,12)); self.kpis.append(v)
            self._clickable(c,lambda pg=page,fl=filt:self.open_page(pg,fl))
        tk.Label(p,text='Haz clic en un indicador para ver su detalle.',bg=PALE,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(6,0))
        lower=tk.Frame(p,bg=PALE); lower.pack(fill='both',expand=True,pady=(20,0))
        left=tk.Frame(lower,bg=WHITE); left.pack(side='left',fill='both',expand=True,padx=(0,12))
        tk.Label(left,text='Actividad reciente',bg=WHITE,fg=NAVY,font=('Segoe UI',13,'bold')).pack(anchor='w',padx=18,pady=15)
        self.activity=tk.Text(left,height=14,bg=WHITE,fg=INK,relief='flat',font=('Consolas',9),wrap='word')
        self.activity.pack(fill='both',expand=True,padx=16,pady=(0,16)); self.activity.insert('end','Ejecute cualquiera de los escenarios para observar la actividad real del backend.'); self.activity.config(state='disabled')
        right=tk.Frame(lower,bg=WHITE,width=290); right.pack(side='left',fill='y'); right.pack_propagate(False)
        tk.Label(right,text='Demostraciones',bg=WHITE,fg=NAVY,font=('Segoe UI',13,'bold')).pack(anchor='w',padx=18,pady=15)
        for i,(t,desc) in enumerate([('Día de pago','Archivo de noviembre'),('Registro con código','Alta y envío vía Mediator'),('Seguridad','Alerta y bloqueo al quinto intento'),('Escalabilidad','Nuevo suscriptor Observer')],1):
            row=tk.Frame(right,bg=WHITE); row.pack(fill='x',padx=16,pady=8)
            tk.Label(row,text=f'{i}. {t}',bg=WHITE,fg=INK,font=('Segoe UI',10,'bold')).pack(anchor='w')
            tk.Label(row,text=desc,bg=WHITE,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w')
            self._button(row,'Ejecutar',lambda n=i:self.run_scenario(n)).pack(anchor='w',pady=5)

    def _users(self,p):
        self._heading(p,'Gestión de usuarios','Consulta los pensionados cargados y registra nuevas personas usando GestionUsuario.')
        form=tk.Frame(p,bg=WHITE); form.pack(fill='x',pady=(0,14))
        self.user_vars={k:tk.StringVar() for k in ['doc','name','phone','email','channel']}
        fields=[('Documento','doc',150),('Nombre completo','name',230),('Celular','phone',160),('Correo','email',250)]
        for label,key,w in fields:
            box=tk.Frame(form,bg=WHITE); box.pack(side='left',padx=10,pady=12)
            tk.Label(box,text=label,bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(anchor='w')
            ttk.Entry(box,textvariable=self.user_vars[key],width=max(16,w//9)).pack(pady=5)
        box=tk.Frame(form,bg=WHITE); box.pack(side='left',padx=10,pady=12)
        tk.Label(box,text='Canal preferido',bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(anchor='w')
        ttk.Combobox(box,textvariable=self.user_vars['channel'],values=['sms','correo','llamada'],state='readonly',width=12).pack(pady=5)
        self._button(form,'Registrar y enviar código',self.register_user).pack(side='left',padx=12,pady=25)
        body=tk.Frame(p,bg=PALE); body.pack(fill='both',expand=True)
        left=tk.Frame(body,bg=PALE); left.pack(side='left',fill='both',expand=True)
        self.users_tree=self._tree(left,('doc','name','phone','email','channel','state'),('Documento','Pensionado','Celular','Correo','Canal','Estado'),[95,170,100,170,70,90],10)
        acciones=tk.Frame(left,bg=PALE); acciones.pack(anchor='w',pady=12)
        self._button(acciones,'Simular intento fallido (usuario seleccionado)',self.fail_selected, color=GOLD).pack(side='left')
        self._button(acciones,'Ver reacción en Patrones ▸',lambda:self.show_page('Patrones'), color=NAVY).pack(side='left',padx=10)
        right=tk.Frame(body,bg=WHITE,width=380); right.pack(side='left',fill='y',padx=(14,0)); right.pack_propagate(False)
        tk.Label(right,text='Detalle del pensionado',bg=WHITE,fg=NAVY,font=('Segoe UI',13,'bold')).pack(anchor='w',padx=16,pady=(14,6))
        self.detail=tk.Text(right,bg=WHITE,fg=INK,relief='flat',font=('Segoe UI',10),wrap='word',padx=6,state='disabled')
        self.detail.pack(fill='both',expand=True,padx=10,pady=(0,12))
        self.detail.tag_configure('h',foreground=NAVY,font=('Segoe UI',10,'bold'),spacing1=8)
        self.detail.tag_configure('muted',foreground=MUTED)
        self.users_tree.bind('<<TreeviewSelect>>',self.show_detail)

    def _pension(self,p):
        self._heading(p,'Pensión y productos','Procesamiento de archivos CSV, conciliación, saldos y movimientos del core simulado.')
        bar=tk.Frame(p,bg=WHITE); bar.pack(fill='x',pady=(0,14))
        self._button(bar,'Procesar archivo de pagos…',self.choose_payment_file).pack(side='left',padx=14,pady=14)
        self._button(bar,'Procesar noviembre',lambda:self.run_action(lambda:self.process_file('pagos_2026-11.csv'))).pack(side='left',padx=6)
        self._button(bar,'Procesar diciembre',lambda:self.run_action(lambda:self.process_file('pagos_2026-12.csv'))).pack(side='left',padx=6)
        pay=tk.Frame(p,bg=WHITE); pay.pack(fill='x',pady=(0,14))
        tk.Label(pay,text='Pago manual',bg=WHITE,fg=NAVY,font=('Segoe UI',10,'bold')).pack(side='left',padx=(14,8),pady=14)
        self._pay_form(pay)
        self._button(pay,'Ver reacción en Patrones ▸',lambda:self.show_page('Patrones'),color=NAVY).pack(side='left',padx=6)
        self.balance_tree=self._tree(p,('doc','name','account','balance'),('Documento','Pensionado','Cuenta','Saldo simulado'),[140,300,180,180],7)
        self.balance_tree.bind('<Double-1>',self._open_selected_balance)
        tk.Label(p,text='Doble clic en un pensionado para ver su detalle.',bg=PALE,fg=MUTED,font=('Segoe UI',9)).pack(anchor='w',pady=(4,0))
        tk.Label(p,text='Resultado del último archivo procesado · diferencias de conciliación',bg=PALE,fg=NAVY,font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(14,6))
        self.diff_tree=self._tree(p,('doc','name','amount','period'),('Documento','Registro no conciliado','Monto','Periodo'),[150,300,160,140],4)
        note=tk.Label(p,text='Los saldos se calculan desde CoreBancarioSimulado. El prototipo original conserva los datos en memoria.',bg=PALE,fg=MUTED,font=('Segoe UI',9))
        note.pack(anchor='w',pady=10)

    def _notifications(self,p):
        self._heading(p,'Centro de notificaciones','Entregas del operador simulado y resultados registrados por Auditoría.')
        bar=tk.Frame(p,bg=WHITE); bar.pack(fill='x',pady=(0,14))
        self.notif_doc=tk.StringVar(); self.notif_channel=tk.StringVar(value='sms')
        tk.Label(bar,text='Documento',bg=WHITE,fg=MUTED).pack(side='left',padx=(14,5),pady=18)
        ttk.Entry(bar,textvariable=self.notif_doc,width=18).pack(side='left')
        ttk.Combobox(bar,textvariable=self.notif_channel,values=['sms','correo','llamada'],state='readonly',width=12).pack(side='left',padx=10)
        self._button(bar,'Guardar canal preferido',self.save_channel).pack(side='left',padx=6)
        self.notif_tree=self._tree(p,('date','doc','channel','destination','message'),('Fecha y hora','Documento','Canal','Destino','Mensaje'),[150,110,90,210,500],12)

    def _audit(self,p):
        self._heading(p,'Auditoría','Registros reales emitidos por el suscriptor Auditoria y por las solicitudes RegistrarResultado.')
        self.audit_filter=tk.StringVar(value='Todos')
        bar=tk.Frame(p,bg=PALE); bar.pack(fill='x',pady=(0,12))
        tk.Label(bar,text='Tipo de registro',bg=PALE,fg=INK).pack(side='left')
        combo=ttk.Combobox(bar,textvariable=self.audit_filter,values=['Todos','AbonoRegistrado','AccesoSospechoso','CuentaBloqueada','Aviso enviado','Aviso FALLIDO'],state='readonly',width=24)
        combo.pack(side='left',padx=10); combo.bind('<<ComboboxSelected>>',lambda e:self.refresh_audit())
        self.audit_tree=self._tree(p,('time','doc','type','detail'),('Fecha y hora','Documento','Tipo de evento / acción','Descripción'),[170,130,200,600],13)

    def _pay_form(self,parent):
        tk.Label(parent,text='Documento',bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(side='left',padx=(6,4))
        combo=ttk.Combobox(parent,textvariable=self.pay_vars['doc'],width=30); combo.pack(side='left'); self.doc_combos.append(combo)
        tk.Label(parent,text='Monto',bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(side='left',padx=(12,4))
        ttk.Entry(parent,textvariable=self.pay_vars['monto'],width=12).pack(side='left')
        tk.Label(parent,text='Periodo',bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(side='left',padx=(12,4))
        ttk.Entry(parent,textvariable=self.pay_vars['periodo'],width=9).pack(side='left')
        self._button(parent,'Registrar pago',self.pay_manual,color=GREEN).pack(side='left',padx=12)

    def _patterns(self,p):
        self._heading(p,'Patrones de diseño en vivo','Ejecuta una acción y mira cómo Observer (uno a muchos) y Mediator (peticiones entre módulos) reaccionan paso a paso.')
        lab=tk.Frame(p,bg=WHITE); lab.pack(fill='x',pady=(0,10))
        row1=tk.Frame(lab,bg=WHITE); row1.pack(fill='x',padx=8,pady=(10,4))
        self._pay_form(row1)
        row2=tk.Frame(lab,bg=WHITE); row2.pack(fill='x',padx=8,pady=(4,10))
        self._button(row2,'Intento fallido (del documento)',self.fail_doc,color=GOLD).pack(side='left',padx=4)
        self._button(row2,'Registrar usuario de prueba',self.register_test_user).pack(side='left',padx=4)
        self.hist_btn=self._button(row2,'Suscribir Historial',self.toggle_historial,color=GREEN); self.hist_btn.pack(side='left',padx=4)
        ttk.Combobox(row2,textvariable=self.speed_var,values=list(VELOCIDADES),state='readonly',width=8).pack(side='right',padx=(4,10))
        tk.Label(row2,text='Velocidad',bg=WHITE,fg=MUTED,font=('Segoe UI',9,'bold')).pack(side='right')
        grid=tk.Frame(p,bg=PALE); grid.pack(fill='x')
        specs=[
            ('OBSERVER',GOLD,'Quien publica no conoce a nadie: el Publicador entrega cada evento a todos sus suscriptores.',
             {'Procesador':(0.17,0.28,'Procesador\nConsignación'),'Gestion':(0.17,0.74,'Gestión\nUsuario'),
              'Publicador':(0.5,0.5,'Publicador\nEventos'),'Auditoria':(0.83,0.17,'Auditoría'),
              'Notificaciones':(0.83,0.5,'Notificaciones'),'Historial':(0.83,0.83,'Historial\nConsignaciones')},
             [('Procesador','Publicador',False),('Gestion','Publicador',False),('Publicador','Auditoria',False),
              ('Publicador','Notificaciones',False),('Publicador','Historial',False)],('Historial',)),
            ('MEDIATOR',BLUE,'Los módulos no se conocen: cada petición pasa por el Mediador, que decide quién la atiende.',
             {'Gestion':(0.2,0.2,'Gestión\nUsuario'),'Notificaciones':(0.8,0.2,'Notificaciones'),
              'Auditoria':(0.5,0.88,'Auditoría'),'Mediador':(0.5,0.45,'Mediador\nMódulos')},
             [('Gestion','Mediador',True),('Notificaciones','Mediador',True),('Auditoria','Mediador',True)],())]
        for col,(title,color,desc,nodos,aristas,inactivos) in enumerate(specs):
            card=tk.Frame(grid,bg=WHITE,highlightbackground='#E2E8F0',highlightthickness=1)
            card.grid(row=0,column=col,sticky='nsew',padx=8,pady=4); grid.grid_columnconfigure(col,weight=1,uniform='diag')
            tk.Label(card,text=title,bg=WHITE,fg=color,font=('Segoe UI',15,'bold')).pack(anchor='w',padx=18,pady=(12,2))
            tk.Label(card,text=desc,bg=WHITE,fg=INK,wraplength=440,justify='left',font=('Segoe UI',9)).pack(anchor='w',padx=18,pady=(0,4))
            d=Diagrama(card,nodos,aristas,color,inactivos); d.pack(fill='x',padx=8,pady=(0,8))
            if title=='OBSERVER': self.diag_obs=d
            else: self.diag_med=d
        box=tk.Frame(p,bg=WHITE); box.pack(fill='both',expand=True,pady=(10,0))
        tk.Label(box,text='Paso a paso',bg=WHITE,fg=NAVY,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=14,pady=(8,2))
        self.steps=tk.Text(box,height=5,bg=WHITE,fg=INK,relief='flat',font=('Consolas',9),wrap='none',state='disabled')
        self.steps.pack(fill='both',expand=True,padx=12,pady=(0,10))
        self.steps.tag_configure('observer',foreground=GOLD); self.steps.tag_configure('mediator',foreground=BLUE)

    def _scenarios(self,p):
        self._heading(p,'Escenarios de demostración','Los cuatro flujos corresponden a los escenarios descritos en el prototipo y en el documento académico.')
        data=[('1 · Día de pago','Procesa pagos_2026-11.csv: cuatro abonos, una diferencia y fallo simulado de aviso para Jorge.'),
              ('2 · Registro con código','Registra a Ana Beatriz Gómez y solicita EnviarCodigo por Mediator.'),
              ('3 · Seguridad','Registra cinco intentos fallidos de Luis; publica AccesoSospechoso y CuentaBloqueada.'),
              ('4 · Escalabilidad','Suscribe HistorialConsignaciones y procesa pagos_2026-12.csv sin cambiar el procesador.')]
        for i,(title,desc) in enumerate(data,1):
            row=tk.Frame(p,bg=WHITE,highlightbackground='#E5EAF0',highlightthickness=1); row.pack(fill='x',pady=7)
            tk.Label(row,text=title,bg=WHITE,fg=NAVY,font=('Segoe UI',12,'bold')).pack(anchor='w',padx=18,pady=(13,3))
            tk.Label(row,text=desc,bg=WHITE,fg=MUTED,font=('Segoe UI',10),wraplength=900).pack(anchor='w',padx=18)
            self._button(row,'Ejecutar escenario',lambda n=i:self.run_scenario(n)).pack(anchor='e',padx=18,pady=12)
        logbox=tk.Frame(p,bg=WHITE); logbox.pack(fill='both',expand=True,pady=(12,0))
        tk.Label(logbox,text='Traza en tiempo real · backend original',bg=WHITE,fg=NAVY,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=14,pady=9)
        self.log=tk.Text(logbox,bg='#101D2D',fg='#D9E4EF',insertbackground=WHITE,relief='flat',font=('Consolas',9),height=12,wrap='word')
        self.log.pack(fill='both',expand=True,padx=12,pady=(0,12))
        self.log.tag_configure('observer',foreground='#F5B94C'); self.log.tag_configure('mediator',foreground='#78B7F5'); self.log.tag_configure('error',foreground='#FF8585')

    def _run_worker(self, fn, done=None):
        if self.busy: return
        self.busy=True; self.status.config(text='● Ejecutando operación…',fg=GOLD)
        self.anim_queue.clear(); self._clear_steps()
        def work():
            result=None; error=None
            try:
                with redirect_stdout(QueueWriter(self.output_queue)):
                    result=fn()
            except Exception as exc: error=exc
            self.output_queue.put(('__DONE__',result,error,done))
        threading.Thread(target=work,daemon=True).start()

    def _drain_output(self):
        try:
            while True:
                item=self.output_queue.get_nowait()
                if isinstance(item,tuple) and item and item[0]=='__DONE__':
                    _,result,error,done=item; self.busy=False
                    self.status.config(text='● Sistema listo' if not error else '● Operación con error',fg=GREEN if not error else RED)
                    if error: messagebox.showerror('No se pudo completar la operación',str(error))
                    if done and not error: done(result)
                    self.refresh_all()
                else:
                    self._append_log(str(item))
        except queue.Empty: pass
        self.after(100,self._drain_output)

    def _enqueue_trace(self,text):
        m=re.match(r'\s*\[(\w+)\]\s*(.*)',text)
        if m and m.group(1) in ('PENSION','GESTION','OBSERVER','MEDIATOR','HISTORIAL'):
            self.anim_queue.append((m.group(1),m.group(2).strip()))

    def _delay(self):
        base=VELOCIDADES.get(self.speed_var.get(),450)
        return min(base,120) if len(self.anim_queue)>30 else base

    def _anim_tick(self):
        # Los pasos esperan en la cola hasta que se abre la página Patrones.
        if self.anim_queue and self.current_page=='Patrones':
            tag,msg=self.anim_queue.popleft()
            try: self._apply_step(tag,msg)
            except tk.TclError: pass
            self.after(self._delay(),self._anim_tick)
        else:
            self.after(100,self._anim_tick)

    def _apply_step(self,tag,msg):
        ms=int(self._delay()*1.6); obs,med=self.diag_obs,self.diag_med
        if tag=='PENSION' and msg.startswith('Procesando'):
            obs.encender('Procesador',ms)
        elif tag=='GESTION':
            obs.encender('Gestion',ms); med.encender('Gestion',ms)
        elif tag=='HISTORIAL':
            obs.encender('Historial',ms)
        elif tag=='OBSERVER':
            m=re.match(r'Se publica (\w+)\(',msg)
            if m:
                pub='Procesador' if m.group(1)=='AbonoRegistrado' else 'Gestion'
                obs.pulso(pub,'Publicador',ms); obs.encender('Publicador',ms)
            else:
                m=re.match(r'-> (\w+)\.actualizar',msg)
                nodo=NODO.get(m.group(1)) if m else None
                if nodo: obs.pulso('Publicador',nodo,ms); obs.encender(nodo,ms)
        elif tag=='MEDIATOR':
            m=re.match(r'(\w+) pide .* -> la atiende (\w+)',msg)
            if m and m.group(1) in NODO and m.group(2) in NODO:
                a,b=NODO[m.group(1)],NODO[m.group(2)]
                med.encender(a,ms); med.pulso(a,'Mediador',ms); med.encender('Mediador',ms)
                med.pulso('Mediador',b,ms); med.encender(b,ms)
        self.steps.config(state='normal')
        self.steps.insert('end',f'[{tag}] {msg}\n',tag.lower() if tag in ('OBSERVER','MEDIATOR') else ())
        if int(self.steps.index('end-1c').split('.')[0])>200: self.steps.delete('1.0','50.0')
        self.steps.see('end'); self.steps.config(state='disabled')

    def _clear_steps(self):
        if hasattr(self,'steps'):
            self.steps.config(state='normal'); self.steps.delete('1.0','end'); self.steps.config(state='disabled')

    def _append_log(self,text):
        self._enqueue_trace(text)
        if hasattr(self,'log') and self.log.winfo_exists():
            tag='observer' if '[OBSERVER]' in text else ('mediator' if '[MEDIATOR]' in text else ('error' if 'FALLIDO' in text or 'falló' in text else None))
            self.log.insert('end',text,tag); self.log.see('end')
        if hasattr(self,'activity') and self.activity.winfo_exists():
            self.activity.config(state='normal'); self.activity.insert('end',text); self.activity.see('end'); self.activity.config(state='disabled')

    def run_action(self,fn,done=None): self._run_worker(fn,done)
    def process_file(self,name):
        result=self.system.procesador.procesar(ROOT/'datos'/name); self.last_result=result
        return result
    def choose_payment_file(self):
        path=filedialog.askopenfilename(title='Seleccionar archivo de pagos',initialdir=ROOT/'datos',filetypes=[('CSV','*.csv')])
        if path: self.run_action(lambda:self._process_custom(path))
    def _process_custom(self,path):
        result=self.system.procesador.procesar(path); self.last_result=result; return result

    def run_scenario(self,n):
        if self.busy: return
        if hasattr(self,'log'):
            self.log.delete('1.0','end')
        if n==1: fn=lambda:self.process_file('pagos_2026-11.csv')
        elif n==2: fn=lambda:self.system.gestion.registrar('1001005','Ana Beatriz Gómez','3001110005','ana.gomez@correo.test')
        elif n==3:
            def security():
                persona=self.system.gestion._pensionados['1001004']
                persona.intentos_fallidos.clear(); persona.bloqueada_hasta=None
                for _ in range(5): self.system.gestion.intento_fallido('1001004')
                return self.system.gestion.bloqueada_hasta('1001004')
            fn=security
        else:
            def scale():
                if self.historial is None: self.historial=HistorialConsignaciones()
                self.system.publicador.suscribir(self.historial); self.historial_suscrito=True
                return self.process_file('pagos_2026-12.csv')
            fn=scale
        self._run_worker(fn,lambda result:messagebox.showinfo(f'Escenario {n} completado',self._scenario_summary(n,result)))

    def _scenario_summary(self,n,r):
        if n==1: return f'Abonos: {len(r.abonos)}\nDiferencias: {len(r.diferencias)}\nAviso de Jorge: fallido de forma simulada; el abono permanece.'
        if n==2: return 'Registro de Ana realizado. Resultado del envío del código: '+('enviado' if r else 'no enviado')+'.'
        if n==3: return 'Cuenta de Luis bloqueada hasta '+str(r)+'.'
        return f'Archivo: {r.archivo}\nAbonos: {len(r.abonos)}\nEl suscriptor HistorialConsignaciones recibe los nuevos eventos.'

    def register_user(self):
        v={k:x.get().strip() for k,x in self.user_vars.items()}
        if not all(v[k] for k in ('doc','name','phone','email')):
            messagebox.showwarning('Datos incompletos','Completa documento, nombre, celular y correo.'); return
        if '@' not in v['email'] or len(v['doc'])<5 or len(v['phone'])<7:
            messagebox.showwarning('Revisa los datos','Verifica el documento, el celular y el formato del correo.'); return
        def action():
            self.system.notificaciones.preferir_canal(v['doc'],v['channel'] or 'sms')
            return self.system.gestion.registrar(v['doc'],v['name'],v['phone'],v['email'])
        self._run_worker(action,lambda sent:messagebox.showinfo('Registro','Persona registrada. Código '+('enviado.' if sent else 'no enviado; revisa Auditoría.')))

    def fail_selected(self):
        sel=self.users_tree.selection()
        if not sel: messagebox.showwarning('Selecciona un pensionado','Elige una fila de la tabla.'); return
        doc=sel[0]
        self._run_worker(lambda:self.system.gestion.intento_fallido(doc))

    # --- Acciones interactivas ------------------------------------------------

    def _selected_doc(self):
        partes=self.pay_vars['doc'].get().split()
        return partes[0] if partes else ''

    def pay_manual(self):
        if self.busy: return
        doc=self._selected_doc()
        digitos=re.sub(r'\D','',self.pay_vars['monto'].get())
        periodo=self.pay_vars['periodo'].get().strip()
        if not doc: messagebox.showwarning('Documento requerido','Elige o escribe el documento del pensionado.'); return
        if not digitos or int(digitos)<=0: messagebox.showwarning('Monto inválido','Escribe un monto mayor que cero.'); return
        if not re.fullmatch(r'\d{4}-\d{2}',periodo): messagebox.showwarning('Periodo inválido','Usa el formato AAAA-MM, por ejemplo 2026-11.'); return
        monto=int(digitos)
        persona=self.system.gestion._pensionados.get(doc)
        nombre=persona.nombre if persona else 'Documento sin registrar'
        def action():
            # El backend procesa archivos: se arma un CSV de una fila y se le entrega a ProcesadorConsignacion.
            carpeta=Path(tempfile.mkdtemp(prefix='bs_pago_'))
            try:
                ruta=carpeta/'pago_manual.csv'
                with open(ruta,'w',encoding='utf-8',newline='') as f:
                    w=csv.writer(f)
                    w.writerow(['documento','nombre','monto','periodo','referencia'])
                    w.writerow([doc,nombre,monto,periodo,uuid.uuid4().hex])
                resultado=self.system.procesador.procesar(ruta)
            finally:
                shutil.rmtree(carpeta,ignore_errors=True)
            self.last_result=resultado
            return resultado
        def done(r):
            if r.abonos:
                messagebox.showinfo('Pago registrado',f'Abono de {pesos(monto)} a {nombre} ({r.abonos[0].transaccion}).\nObserver publicó AbonoRegistrado: revisa Notificaciones, Auditoría y el diagrama de Patrones.')
            else:
                messagebox.showinfo('Pago no conciliado',f'El documento {doc} no tiene cuenta en el banco: el pago pasó al reporte de diferencias y no se abonó.')
        self._run_worker(action,done)

    def fail_doc(self):
        doc=self._selected_doc()
        if doc not in self.system.gestion._pensionados:
            messagebox.showwarning('Documento no registrado','Elige un pensionado registrado en el campo Documento.'); return
        self._run_worker(lambda:self.system.gestion.intento_fallido(doc))

    def register_test_user(self):
        if self.busy: return
        people=self.system.gestion._pensionados
        n=1001005
        while str(n) in people: n+=1
        doc=str(n)
        self._run_worker(lambda:self.system.gestion.registrar(doc,f'Persona Prueba {n-1001000}',f'300111{n%10000:04d}',f'prueba{n}@correo.test'))

    def toggle_historial(self):
        if self.busy: return
        def action():
            if self.historial is None: self.historial=HistorialConsignaciones()
            if self.historial_suscrito:
                self.system.publicador.desuscribir(self.historial); self.historial_suscrito=False
            else:
                self.system.publicador.suscribir(self.historial); self.historial_suscrito=True
        self._run_worker(action)

    def reset_system(self):
        if self.busy: return
        if not messagebox.askyesno('Reiniciar sistema','Se borrarán los usuarios registrados, abonos, avisos y auditoría de esta sesión. ¿Continuar?'): return
        self.system=self._new_system()
        self.historial=None; self.historial_suscrito=False; self.last_result=None
        self.anim_queue.clear(); self._clear_steps()
        self.log.delete('1.0','end')
        self.activity.config(state='normal'); self.activity.delete('1.0','end')
        self.activity.insert('end','Sistema reiniciado. Ejecute cualquiera de los escenarios para observar la actividad real del backend.'); self.activity.config(state='disabled')
        self.status.config(text='● Sistema listo',fg=GREEN)
        self.refresh_all()

    def _clickable(self,widget,command):
        widget.configure(cursor='hand2'); widget.bind('<Button-1>',lambda e:command())
        for child in widget.winfo_children(): self._clickable(child,command)

    def open_page(self,page,audit_filter=None):
        self.audit_filter.set(audit_filter or 'Todos')
        self.show_page(page)

    def _open_selected_balance(self,_event=None):
        sel=self.balance_tree.selection()
        if not sel: return
        doc=str(self.balance_tree.item(sel[0])['values'][0])
        self.show_page('Usuarios')
        if self.users_tree.exists(doc):
            self.users_tree.selection_set(doc); self.users_tree.see(doc)

    def show_detail(self,_event=None):
        t=self.detail; t.config(state='normal'); t.delete('1.0','end')
        sel=self.users_tree.selection()
        persona=self.system.gestion._pensionados.get(sel[0]) if sel else None
        if persona is None:
            t.insert('end','Selecciona un pensionado de la tabla para ver su saldo, abonos, avisos y auditoría.','muted')
            t.config(state='disabled'); return
        doc=persona.documento; core=self.system.core; hora=lambda m:m.strftime('%d/%m %H:%M:%S')
        estado='Bloqueada hasta '+hora(persona.bloqueada_hasta) if persona.bloqueada_hasta else ('Verificada' if persona.verificado else 'Pendiente de verificar')
        t.insert('end',persona.nombre+'\n','h')
        t.insert('end',f'Documento {doc} · {estado}\nCanal preferido: {self.system.notificaciones.canal_de(doc)}\nCelular {persona.celular}\nCorreo {persona.correo}\n')
        cuenta=core.cuenta_de(doc)
        t.insert('end','Cuenta y saldo\n','h')
        t.insert('end',f'{cuenta} · {pesos(core.saldo(cuenta))}\n' if cuenta else 'Sin cuenta en el core simulado.\n')
        t.insert('end','Intentos fallidos\n','h'); t.insert('end',f'{len(persona.intentos_fallidos)} de {self.system.gestion.MAX_INTENTOS}\n')
        registros=[r for r in self.system.auditoria.registros if r.documento==doc]
        abonos=[r for r in registros if r.tipo=='AbonoRegistrado']
        t.insert('end',f'Abonos ({len(abonos)})\n','h')
        for r in abonos[-6:]: t.insert('end',f'{hora(r.momento)}  {r.detalle}\n')
        if not abonos: t.insert('end','Ninguno todavía.\n','muted')
        avisos=[e for e in self.system.operador.enviados if e[2] in (persona.celular,persona.correo)]
        t.insert('end',f'Avisos entregados ({len(avisos)})\n','h')
        for m,canal,_,msg in avisos[-5:]: t.insert('end',f'{hora(m)}  {canal}: {msg}\n')
        if not avisos: t.insert('end','Ninguno todavía.\n','muted')
        if self.historial is not None:
            t.insert('end','Historial de consignaciones\n','h')
            filas=self.historial.consultar(doc)
            for c in filas: t.insert('end',f'{c.periodo}  {pesos(c.monto)}  {c.estado}\n')
            if not filas: t.insert('end','Sin consignaciones desde que se suscribió.\n','muted')
        t.insert('end','Auditoría\n','h')
        for r in registros[-8:]: t.insert('end',f'{hora(r.momento)}  {r.tipo}\n')
        if not registros: t.insert('end','Sin registros.\n','muted')
        t.config(state='disabled')

    def save_channel(self):
        doc=self.notif_doc.get().strip()
        if not doc: messagebox.showwarning('Documento requerido','Escribe el documento del pensionado.'); return
        try: self.system.notificaciones.preferir_canal(doc,self.notif_channel.get())
        except ValueError as e: messagebox.showerror('Canal inválido',str(e)); return
        messagebox.showinfo('Preferencia actualizada','El canal preferido se actualizó en Notificaciones.')
        self.refresh_all()

    def refresh_all(self):
        if not hasattr(self,'users_tree'): return
        people=getattr(self.system.gestion,'_pensionados',{})
        sel=self.users_tree.selection(); sel_doc=sel[0] if sel else None
        for tree in [self.users_tree,self.balance_tree,self.notif_tree,self.diff_tree]:
            for i in tree.get_children(): tree.delete(i)
        docs=[f'{d} · {p.nombre}' for d,p in people.items()]
        for combo in self.doc_combos: combo['values']=docs
        if docs and not self.pay_vars['doc'].get(): self.pay_vars['doc'].set(docs[0])
        for doc,person in people.items():
            state='Bloqueada' if person.bloqueada_hasta else ('Verificada' if person.verificado else 'Pendiente')
            self.users_tree.insert('', 'end',iid=doc,values=(doc,person.nombre,person.celular,person.correo,self.system.notificaciones.canal_de(doc),state))
            account=self.system.core.cuenta_de(doc)
            if account:
                balance=self.system.core.saldo(account)
                self.balance_tree.insert('', 'end',values=(doc,person.nombre,account,pesos(balance)))
        if self.last_result is not None:
            for row in self.last_result.diferencias:
                self.diff_tree.insert('', 'end', values=(row.get('documento',''),row.get('nombre',''),pesos(int(row.get('monto',0))),row.get('periodo','')))
        for moment,channel,dest,message in self.system.operador.enviados:
            self.notif_tree.insert('', 'end',values=(moment.strftime('%d/%m/%Y %H:%M:%S'),'',channel,dest,message))
        # Añade el documento desde los registros auditables asociados al destino cuando es posible.
        for idx,item in enumerate(self.notif_tree.get_children()):
            vals=list(self.notif_tree.item(item)['values'])
            vals[1]=self._document_for_destination(vals[3]); self.notif_tree.item(item,values=vals)
        self.refresh_audit()
        if sel_doc and self.users_tree.exists(sel_doc): self.users_tree.selection_set(sel_doc)
        self.show_detail()
        if hasattr(self,'diag_obs'):
            self.diag_obs.set_activo('Historial',self.historial_suscrito)
            self.hist_btn.config(text='Retirar Historial' if self.historial_suscrito else 'Suscribir Historial',bg=RED if self.historial_suscrito else GREEN)
        if hasattr(self,'kpis'):
            self.kpis[0].config(text=str(len(people)))
            self.kpis[1].config(text=str(sum(1 for r in self.system.auditoria.registros if r.tipo=='AbonoRegistrado')))
            self.kpis[2].config(text=str(len(self.system.operador.enviados)))
            self.kpis[3].config(text=str(self.system.publicador.eventos_publicados))

    def _document_for_destination(self,dest):
        for doc,p in getattr(self.system.gestion,'_pensionados',{}).items():
            if dest in (p.celular,p.correo): return doc
        return '—'

    def refresh_audit(self):
        if not hasattr(self,'audit_tree'): return
        for i in self.audit_tree.get_children(): self.audit_tree.delete(i)
        filt=self.audit_filter.get() if hasattr(self,'audit_filter') else 'Todos'
        for r in self.system.auditoria.registros:
            if filt!='Todos' and r.tipo!=filt: continue
            self.audit_tree.insert('','end',values=(r.momento.strftime('%d/%m/%Y %H:%M:%S'),r.documento,r.tipo,r.detalle))


def main():
    app=BancoSeniorApp(); app.mainloop()
