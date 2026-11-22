"""Vista Optimizar: limpieza de caché, programas de inicio, procesos y herramientas."""
from tkinter import messagebox

import customtkinter as ctk

from .. import cleaner, systools
from ..platform_utils import IS_WIN, human_size, is_admin
from .widgets import (ACCENT, ACCENT_HOVER, BORDER, DANGER, MUTED, SUCCESS, SURFACE2, TEXT, WARNING, Card,
                      badge, danger_button, emoji_font, font, ghost_button, header, primary_button)


def fmt_uptime(sec):
    if sec is None:
        return "—"
    d, rem = divmod(int(sec), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return f"{d} d {h} h" if d else f"{h} h {m} min"


class StatCard(Card):
    def __init__(self, master, icon, title):
        super().__init__(master)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 0))
        ctk.CTkLabel(top, text=icon, font=emoji_font(18)).pack(side="left")
        ctk.CTkLabel(top, text=title, font=font(12), text_color=MUTED).pack(side="left", padx=6)
        self.value = ctk.CTkLabel(self, text="—", font=font(24, "bold"), anchor="w")
        self.value.pack(fill="x", padx=16)
        self.sub = ctk.CTkLabel(self, text="", font=font(11), text_color=MUTED, anchor="w")
        self.sub.pack(fill="x", padx=16)
        self.bar = ctk.CTkProgressBar(self, height=6, corner_radius=3, progress_color=ACCENT)
        self.bar.set(0)
        self.bar.pack(fill="x", padx=16, pady=(6, 14))

    def set(self, value, sub="", pct=None):
        self.value.configure(text=value)
        self.sub.configure(text=sub)
        if pct is not None:
            self.bar.set(max(0, min(1, pct / 100)))
            color = DANGER if pct > 90 else WARNING if pct > 75 else ACCENT
            self.bar.configure(progress_color=color)


class OptimizeView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.admin = is_admin()

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=28, pady=(24, 12))
        header(top, "Optimizar PC", "Libera espacio, acelera el arranque y controla qué consume tu equipo.").pack(side="left")

        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.pack(fill="x", padx=28, pady=(0, 8))
        self.s_cpu = StatCard(stats, "⚙", "Procesador")
        self.s_ram = StatCard(stats, "🧠", "Memoria RAM")
        self.s_disk = StatCard(stats, "💾", f"Disco {systools.system_drive()}")
        self.s_up = StatCard(stats, "⏱", "Encendido desde hace")
        for i, c in enumerate((self.s_cpu, self.s_ram, self.s_disk, self.s_up)):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 10, 0))
            stats.grid_columnconfigure(i, weight=1)

        self.tabs = ctk.CTkTabview(self, fg_color=("#ffffff", "#181b22"), segmented_button_selected_color=ACCENT,
                                   segmented_button_selected_hover_color=ACCENT_HOVER, corner_radius=14,
                                   border_width=1, border_color=BORDER)
        self.tabs.pack(fill="both", expand=True, padx=28, pady=(4, 16))
        self._build_clean(self.tabs.add("🧹  Limpieza"))
        self._build_startup(self.tabs.add("🚀  Inicio de Windows"))
        self._build_procs(self.tabs.add("📊  Procesos"))
        self._build_tools(self.tabs.add("🛠  Herramientas"))
        self.tabs.configure(command=self._on_tab)
        self._startup_loaded = False
        self._procs_loaded = False
        self.after(500, self._tick)

    # ================================================================ stats
    def _tick(self):
        if self.winfo_ismapped():
            def done(s, err):
                if err or not s:
                    return
                if s["cpu"] is not None:
                    self.s_cpu.set(f"{s['cpu']:.0f} %", "uso actual", s["cpu"])
                if s["ram_pct"] is not None:
                    self.s_ram.set(f"{s['ram_pct']:.0f} %",
                                   f"{human_size(s['ram_used'])} de {human_size(s['ram_total'])}", s["ram_pct"])
                if s["disk_pct"] is not None:
                    self.s_disk.set(f"{human_size(s['disk_free'])} libres",
                                    f"de {human_size(s['disk_total'])} ({s['disk_pct']:.0f} % usado)", s["disk_pct"])
                self.s_up.set(fmt_uptime(s["uptime"]), "reinicia de vez en cuando 😉")
                if s["uptime"]:
                    self.s_up.bar.set(min(1, s["uptime"] / (7 * 86400)))
            self.app.run_bg(systools.stats, done)
        self.after(2000, self._tick)

    def _on_tab(self):
        t = self.tabs.get()
        if "Inicio" in t and not self._startup_loaded:
            self.load_startup()
        elif "Procesos" in t and not self._procs_loaded:
            self.load_procs()

    # ================================================================ limpieza
    def _build_clean(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=6, pady=(4, 6))
        ghost_button(bar, "🔍  Analizar", self.analyze, width=120).pack(side="left")
        self.clean_btn = primary_button(bar, "🧹  Limpiar seleccionados", self.clean, width=200)
        self.clean_btn.pack(side="left", padx=8)
        ghost_button(bar, "Recomendados", self.select_recommended, width=120).pack(side="left")
        self.total = ctk.CTkLabel(bar, text="", font=font(15, "bold"), text_color=ACCENT)
        self.total.pack(side="right", padx=6)

        self.progress = ctk.CTkProgressBar(tab, height=4, progress_color=ACCENT, mode="indeterminate")
        self.warn = ctk.CTkLabel(tab, text="", font=font(12), text_color=WARNING, anchor="w", justify="left")
        self.warn.pack(fill="x", padx=10)

        lst = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        lst.pack(fill="both", expand=True)
        lst.grid_columnconfigure(0, weight=1)
        self.clean_rows = {}
        for i, t in enumerate(cleaner.TARGETS):
            row = ctk.CTkFrame(lst, fg_color=SURFACE2 if i % 2 == 0 else "transparent", corner_radius=10)
            row.grid(row=i, column=0, sticky="ew", pady=2)
            row.grid_columnconfigure(1, weight=1)
            var = ctk.BooleanVar(value=t.get("default", False))
            locked = t.get("admin") and not self.admin and IS_WIN
            cb = ctk.CTkCheckBox(row, text="", variable=var, width=24, fg_color=ACCENT, hover_color=ACCENT_HOVER)
            cb.grid(row=0, column=0, rowspan=2, padx=(12, 4), pady=8)
            if locked:
                var.set(False)
                cb.configure(state="disabled")
            title = ctk.CTkFrame(row, fg_color="transparent")
            title.grid(row=0, column=1, sticky="w", pady=(8, 0))
            ctk.CTkLabel(title, text=t["name"], font=font(13, "bold")).pack(side="left")
            if t.get("admin"):
                badge(title, "🔒 Requiere admin" if locked else "Admin", WARNING if locked else SUCCESS
                      ).pack(side="left", padx=8)
            ctk.CTkLabel(row, text=t["desc"], font=font(11), text_color=MUTED, anchor="w").grid(
                row=1, column=1, sticky="w", pady=(0, 8))
            size = ctk.CTkLabel(row, text="—", font=font(13, "bold"), width=110, anchor="e")
            size.grid(row=0, column=2, rowspan=2, padx=14)
            self.clean_rows[t["id"]] = {"var": var, "size": size, "target": t, "locked": locked, "bytes": 0}
        if not IS_WIN:
            self.warn.configure(text="Esta función está pensada para Windows.")

    def select_recommended(self):
        for r in self.clean_rows.values():
            if not r["locked"]:
                r["var"].set(r["target"].get("default", False))
        self._update_total()

    def _update_total(self):
        total = sum(r["bytes"] for r in self.clean_rows.values() if r["var"].get())
        self.total.configure(text=f"Seleccionado: {human_size(total)}" if total else "")

    def _busy(self, on):
        if on:
            self.progress.pack(fill="x", padx=10, pady=(0, 4), before=self.warn)
            self.progress.start()
            self.clean_btn.configure(state="disabled")
        else:
            self.progress.stop()
            self.progress.pack_forget()
            self.clean_btn.configure(state="normal")

    def analyze(self):
        self._busy(True)
        rows = list(self.clean_rows.values())
        for r in rows:
            r["size"].configure(text="…", text_color=TEXT)

        def work():
            for r in rows:
                if r["locked"]:
                    self.app.call_soon(lambda r=r: r["size"].configure(text="—", text_color=MUTED))
                    continue
                m = cleaner.measure(r["target"])
                r["bytes"] = m["size"]
                self.app.call_soon(lambda r=r, m=m: r["size"].configure(
                    text=human_size(m["size"]), text_color=TEXT if m["size"] > 1024 * 1024 else MUTED))
            procs = set()
            for r in rows:
                procs.update(r["target"].get("procs", []))
            return cleaner.running_processes(procs)

        def done(running, err):
            self._busy(False)
            self._update_total()
            if running:
                self.warn.configure(text="⚠ Abiertos ahora: " + ", ".join(running) +
                                         ". Ciérralos para limpiar su caché por completo.")
            elif IS_WIN:
                self.warn.configure(text="")
        self.app.run_bg(work, done)

    def clean(self):
        selected = [r for r in self.clean_rows.values() if r["var"].get() and not r["locked"]]
        if not selected:
            messagebox.showinfo("Nada seleccionado", "Marca al menos una casilla.", parent=self)
            return
        names = "\n".join(f"• {r['target']['name']}" for r in selected)
        if not messagebox.askyesno("Limpiar", f"Se borrarán estos archivos temporales:\n\n{names}\n\n"
                                              "Los archivos en uso se saltarán automáticamente. ¿Continuar?",
                                   parent=self):
            return
        self._busy(True)

        def work():
            total = {"freed": 0, "deleted": 0, "failed": 0}
            for r in selected:
                self.app.call_soon(lambda r=r: r["size"].configure(text="Limpiando…", text_color=ACCENT))
                s = cleaner.clean(r["target"])
                for k in total:
                    total[k] += s[k]
                self.app.call_soon(lambda r=r, s=s: r["size"].configure(
                    text=f"✓ {human_size(s['freed'])}", text_color=SUCCESS))
                r["bytes"] = 0
            return total

        def done(total, err):
            self._busy(False)
            if err:
                messagebox.showerror("Error", str(err), parent=self)
                return
            self._update_total()
            msg = f"🧹 Liberados {human_size(total['freed'])} ({total['deleted']} archivos)"
            if total["failed"]:
                msg += f" · {total['failed']} en uso se saltaron"
            self.app.notify(msg)
            self.total.configure(text=f"✓ Liberado: {human_size(total['freed'])}", text_color=SUCCESS)
            self.app.add_freed(total["freed"])
        self.app.run_bg(work, done)

    # ================================================================ inicio
    def _build_startup(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=6, pady=(4, 6))
        ghost_button(bar, "🔄  Actualizar", self.load_startup, width=120).pack(side="left")
        ctk.CTkLabel(bar, text="Desactiva lo que no necesites al encender el PC para que arranque más rápido.\n"
                               "Funciona igual que el Administrador de tareas y se puede reactivar cuando quieras.",
                     font=font(12), text_color=MUTED, justify="left").pack(side="left", padx=12)
        self.startup_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.startup_list.pack(fill="both", expand=True)
        self.startup_list.grid_columnconfigure(1, weight=1)

    def load_startup(self):
        self._startup_loaded = True
        for w in self.startup_list.winfo_children():
            w.destroy()
        if not IS_WIN:
            ctk.CTkLabel(self.startup_list, text="Disponible solo en Windows.", text_color=MUTED).grid(pady=30)
            return

        def done(items, err):
            if err:
                ctk.CTkLabel(self.startup_list, text=f"Error: {err}", text_color=DANGER).grid(pady=30)
                return
            if not items:
                ctk.CTkLabel(self.startup_list, text="No hay programas configurados para iniciarse.",
                             text_color=MUTED).grid(pady=30)
            on = sum(1 for i in items if i["enabled"])
            for idx, it in enumerate(items):
                row = ctk.CTkFrame(self.startup_list, fg_color=SURFACE2 if idx % 2 == 0 else "transparent",
                                   corner_radius=10)
                row.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=2)
                row.grid_columnconfigure(1, weight=1)
                sw = ctk.CTkSwitch(row, text="", width=46, progress_color=ACCENT)
                sw.grid(row=0, column=0, rowspan=2, padx=(14, 8), pady=8)
                if it["enabled"]:
                    sw.select()
                sw.configure(command=lambda it=it, sw=sw: self.toggle_startup(it, sw))
                ctk.CTkLabel(row, text=it["name"], font=font(13, "bold"), anchor="w").grid(row=0, column=1, sticky="w",
                                                                                            pady=(8, 0))
                cmd = it["command"]
                ctk.CTkLabel(row, text=cmd if len(cmd) < 110 else cmd[:107] + "…", font=font(11),
                             text_color=MUTED, anchor="w").grid(row=1, column=1, sticky="w", pady=(0, 8))
                ctk.CTkLabel(row, text=it["where"], font=font(11), text_color=MUTED).grid(row=0, column=2, rowspan=2,
                                                                                        padx=14)
            self.app.notify(f"{len(items)} programas de inicio · {on} activados")
        self.app.run_bg(systools.startup_items, done)

    def toggle_startup(self, item, switch):
        want = bool(switch.get())
        try:
            systools.set_startup_enabled(item, want)
            item["enabled"] = want
            self.app.notify(f"{item['name']}: {'activado' if want else 'desactivado'} al iniciar Windows")
        except PermissionError:
            switch.select() if item["enabled"] else switch.deselect()
            messagebox.showwarning("Permisos", "Este elemento es de todos los usuarios.\n"
                                               "Pulsa «Ejecutar como administrador» (abajo a la izquierda) "
                                               "para poder cambiarlo.", parent=self)
        except Exception as e:  # noqa: BLE001
            switch.select() if item["enabled"] else switch.deselect()
            messagebox.showerror("Error", str(e), parent=self)

    # ================================================================ procesos
    def _build_procs(self, tab):
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=6, pady=(4, 6))
        ghost_button(bar, "🔄  Actualizar", self.load_procs, width=120).pack(side="left")
        ctk.CTkLabel(bar, text="Programas que más memoria usan ahora mismo. Cierra los que no estés usando.",
                     font=font(12), text_color=MUTED).pack(side="left", padx=12)
        self.proc_list = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        self.proc_list.pack(fill="both", expand=True)
        self.proc_list.grid_columnconfigure(1, weight=1)

    def load_procs(self):
        self._procs_loaded = True

        def done(procs, err):
            for w in self.proc_list.winfo_children():
                w.destroy()
            if err or not procs:
                ctk.CTkLabel(self.proc_list, text="No disponible (instala «psutil»).", text_color=MUTED).grid(pady=30)
                return
            top = max(p["mem"] for p in procs) or 1
            for idx, p in enumerate(procs):
                row = ctk.CTkFrame(self.proc_list, fg_color=SURFACE2 if idx % 2 == 0 else "transparent",
                                   corner_radius=10)
                row.grid(row=idx, column=0, columnspan=4, sticky="ew", pady=2)
                row.grid_columnconfigure(1, weight=1)
                label = p["name"] + (f"  ×{p['count']}" if p["count"] > 1 else "")
                ctk.CTkLabel(row, text=label, font=font(13, "bold"), width=260, anchor="w").grid(
                    row=0, column=0, padx=(14, 8), pady=8, sticky="w")
                bar = ctk.CTkProgressBar(row, height=8, progress_color=ACCENT)
                bar.set(p["mem"] / top)
                bar.grid(row=0, column=1, sticky="ew", padx=8)
                ctk.CTkLabel(row, text=human_size(p["mem"]), font=font(12), width=90, anchor="e").grid(
                    row=0, column=2, padx=8)
                if p["protected"]:
                    ctk.CTkLabel(row, text="Sistema", font=font(11), text_color=MUTED, width=90).grid(
                        row=0, column=3, padx=(0, 12))
                else:
                    danger_button(row, "Finalizar", lambda p=p: self.kill(p), width=90).grid(
                        row=0, column=3, padx=(0, 12))
        self.app.run_bg(systools.top_processes, done)

    def kill(self, p):
        n = f"{p['count']} procesos" if p["count"] > 1 else "el proceso"
        if not messagebox.askyesno("Finalizar", f"¿Cerrar {n} de «{p['name']}»?\n"
                                                "Se perderá lo que no hayas guardado en ese programa.", parent=self):
            return
        killed, failed = systools.kill_pids(p["pids"])
        self.app.notify(f"{p['name']}: {killed} cerrados" + (f", {failed} sin permiso" if failed else ""))
        self.after(800, self.load_procs)

    # ================================================================ herramientas
    def _build_tools(self, tab):
        grid = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        for c in range(3):
            grid.grid_columnconfigure(c, weight=1, uniform="t")

        def tool(fn):
            def run():
                try:
                    r = fn()
                    if isinstance(r, tuple):
                        ok, msg = r
                        (self.app.notify if ok else lambda m: messagebox.showwarning("Aviso", m, parent=self))(msg)
                except Exception as e:  # noqa: BLE001
                    messagebox.showerror("Error", str(e), parent=self)
            return run

        def power(guid):
            ok, msg = systools.set_power_plan(guid)
            self.after(300, self._refresh_power)
            return ok, msg

        tools = [
            ("🌐", "Vaciar caché DNS", "Soluciona webs que no cargan o cargan lento.", "Ejecutar",
             tool(systools.flush_dns)),
            ("⚡", "Plan Alto rendimiento", "Máxima potencia del procesador (ideal para jugar).", "Activar",
             tool(lambda: power(systools.HIGH_PERF))),
            ("🔋", "Plan Equilibrado", "Vuelve al plan normal de Windows (ahorra energía).", "Activar",
             tool(lambda: power(systools.BALANCED))),
            ("🎮", "Modo juego de Windows", "Abre la configuración del Modo juego.", "Abrir",
             tool(lambda: systools.open_tool("gamemode"))),
            ("🖥", "Gráficos por aplicación", "Elige la GPU de alto rendimiento para cada juego.", "Abrir",
             tool(lambda: systools.open_tool("graphics"))),
            ("✨", "Efectos visuales", "Desactiva animaciones para ganar fluidez en PCs lentos.", "Abrir",
             tool(lambda: systools.open_tool("visual"))),
            ("🧽", "Liberador de espacio", "Herramienta de limpieza oficial de Windows.", "Abrir",
             tool(lambda: systools.open_tool("cleanmgr"))),
            ("💽", "Optimizar unidades", "Desfragmenta HDD / aplica TRIM en SSD.", "Abrir",
             tool(lambda: systools.open_tool("dfrgui"))),
            ("📦", "Sensor de almacenamiento", "Limpieza automática de Windows.", "Abrir",
             tool(lambda: systools.open_tool("storage"))),
            ("🩺", "Reparar archivos (SFC)", "Comprueba y repara archivos dañados de Windows.", "Ejecutar",
             tool(lambda: systools.open_tool("sfc"))),
            ("🧰", "Reparar imagen (DISM)", "Repara la imagen de Windows (tarda unos minutos).", "Ejecutar",
             tool(lambda: systools.open_tool("dism"))),
            ("🗑", "Desinstalar programas", "Lista de aplicaciones instaladas de Windows.", "Abrir",
             tool(lambda: systools.open_tool("apps"))),
            ("📈", "Administrador de tareas", "Vista avanzada de procesos y rendimiento.", "Abrir",
             tool(lambda: systools.open_tool("taskmgr"))),
        ]
        self.power_label = ctk.CTkLabel(grid, text="", font=font(12), text_color=MUTED, anchor="w")
        self.power_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(2, 6))
        for i, (icon, name, desc, btn, fn) in enumerate(tools):
            c = Card(grid, fg_color=SURFACE2, border_width=0)
            c.grid(row=1 + i // 3, column=i % 3, sticky="nsew", padx=6, pady=6)
            top = ctk.CTkFrame(c, fg_color="transparent")
            top.pack(fill="x", padx=14, pady=(12, 0))
            ctk.CTkLabel(top, text=icon, font=emoji_font(20)).pack(side="left")
            ctk.CTkLabel(top, text=name, font=font(13, "bold")).pack(side="left", padx=8)
            ctk.CTkLabel(c, text=desc, font=font(11), text_color=MUTED, anchor="w", justify="left",
                         wraplength=250).pack(fill="x", padx=14, pady=(4, 6))
            ctk.CTkButton(c, text=btn, command=fn, height=30, width=100, corner_radius=8, fg_color=ACCENT,
                          hover_color=ACCENT_HOVER, font=font(12, "bold")).pack(anchor="w", padx=14, pady=(0, 12))
        if IS_WIN:
            self.after(1000, self._refresh_power)

    def _refresh_power(self):
        def done(name, err):
            if name:
                self.power_label.configure(text=f"Plan de energía actual: {name}")
        self.app.run_bg(systools.active_power_plan, done)
