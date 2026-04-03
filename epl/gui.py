"""
EPL GUI Framework (v0.6)
Desktop GUI framework using tkinter. Provides EPL-friendly API for creating
windows, buttons, labels, text inputs, checkboxes, dropdowns, canvases,
menus, dialogs, and event handling.
"""

import sys

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, colorchooser, font as tkfont
    HAS_TK = True
except ImportError:
    HAS_TK = False


class EPLWidget:
    """Base EPL widget wrapper."""
    def __init__(self, tk_widget=None):
        self.tk_widget = tk_widget
        self.children = []

    def set_property(self, key, value):
        if self.tk_widget:
            try:
                self.tk_widget.configure(**{key: value})
            except Exception:
                pass

    def get_property(self, key):
        if self.tk_widget:
            try:
                return self.tk_widget.cget(key)
            except Exception:
                return None
        return None


class EPLWindow(EPLWidget):
    """Main application window."""
    def __init__(self, title="EPL App", width=800, height=600):
        if not HAS_TK:
            raise RuntimeError("tkinter is required for GUI. Install Python with Tk support.")
        self.root = tk.Tk()
        self.root.title(title)
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg='#0f172a')
        super().__init__(self.root)
        self._style_widgets()
        self._event_handlers = {}
        self._named_widgets = {}
        self._variables = {}

    def _style_widgets(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('EPL.TButton', font=('Segoe UI', 11), padding=8,
                        background='#3b82f6', foreground='white')
        style.map('EPL.TButton', background=[('active', '#2563eb')])
        style.configure('EPL.TLabel', font=('Segoe UI', 11),
                        background='#0f172a', foreground='#f1f5f9')
        style.configure('EPL.TEntry', font=('Segoe UI', 11), padding=6)
        style.configure('EPL.TFrame', background='#0f172a')
        style.configure('EPL.TCheckbutton', font=('Segoe UI', 11),
                        background='#0f172a', foreground='#f1f5f9')
        style.configure('EPL.TCombobox', font=('Segoe UI', 11))

    def set_title(self, title):
        self.root.title(title)

    def set_size(self, width, height):
        self.root.geometry(f"{width}x{height}")

    def set_background(self, color):
        self.root.configure(bg=color)

    def show(self):
        self.root.mainloop()

    def close(self):
        self.root.destroy()

    def after(self, ms, callback):
        self.root.after(ms, callback)

    # ─── Widget Creation ─────────────────────────────────

    def add_label(self, text, name=None, row=None, col=None, **kwargs):
        label = ttk.Label(self.root, text=text, style='EPL.TLabel', **kwargs)
        if row is not None and col is not None:
            label.grid(row=row, column=col, padx=8, pady=4, sticky='w')
        else:
            label.pack(padx=12, pady=6, anchor='w')
        w = EPLWidget(label)
        if name: self._named_widgets[name] = w
        self.children.append(w)
        return w

    def add_button(self, text, command=None, name=None, row=None, col=None, **kwargs):
        btn = ttk.Button(self.root, text=text, style='EPL.TButton', command=command, **kwargs)
        if row is not None and col is not None:
            btn.grid(row=row, column=col, padx=8, pady=4)
        else:
            btn.pack(padx=12, pady=6)
        w = EPLWidget(btn)
        if name: self._named_widgets[name] = w
        self.children.append(w)
        return w

    def add_input(self, placeholder="", name=None, row=None, col=None, **kwargs):
        var = tk.StringVar()
        entry = ttk.Entry(self.root, textvariable=var, style='EPL.TEntry', **kwargs)
        if placeholder:
            entry.insert(0, placeholder)
            entry.bind('<FocusIn>', lambda e: entry.delete(0, tk.END) if entry.get() == placeholder else None)
            entry.bind('<FocusOut>', lambda e: entry.insert(0, placeholder) if not entry.get() else None)
        if row is not None and col is not None:
            entry.grid(row=row, column=col, padx=8, pady=4, sticky='ew')
        else:
            entry.pack(padx=12, pady=6, fill='x')
        w = EPLWidget(entry)
        w.variable = var
        if name:
            self._named_widgets[name] = w
            self._variables[name] = var
        self.children.append(w)
        return w

    def add_text_area(self, text="", name=None, rows=6, **kwargs):
        ta = tk.Text(self.root, height=rows, font=('Consolas', 11),
                     bg='#1e293b', fg='#f1f5f9', insertbackground='white',
                     relief='flat', padx=8, pady=8, **kwargs)
        if text: ta.insert('1.0', text)
        ta.pack(padx=12, pady=6, fill='both', expand=True)
        w = EPLWidget(ta)
        if name: self._named_widgets[name] = w
        self.children.append(w)
        return w

    def add_checkbox(self, text, name=None, row=None, col=None, **kwargs):
        var = tk.BooleanVar()
        cb = ttk.Checkbutton(self.root, text=text, variable=var,
                             style='EPL.TCheckbutton', **kwargs)
        if row is not None and col is not None:
            cb.grid(row=row, column=col, padx=8, pady=4, sticky='w')
        else:
            cb.pack(padx=12, pady=6, anchor='w')
        w = EPLWidget(cb)
        w.variable = var
        if name:
            self._named_widgets[name] = w
            self._variables[name] = var
        self.children.append(w)
        return w

    def add_dropdown(self, options, name=None, row=None, col=None, **kwargs):
        var = tk.StringVar()
        if options: var.set(options[0])
        dd = ttk.Combobox(self.root, textvariable=var, values=options,
                          style='EPL.TCombobox', state='readonly', **kwargs)
        if row is not None and col is not None:
            dd.grid(row=row, column=col, padx=8, pady=4)
        else:
            dd.pack(padx=12, pady=6)
        w = EPLWidget(dd)
        w.variable = var
        if name:
            self._named_widgets[name] = w
            self._variables[name] = var
        self.children.append(w)
        return w

    def add_canvas(self, width=400, height=300, name=None, bg='#1e293b', **kwargs):
        c = tk.Canvas(self.root, width=width, height=height, bg=bg,
                      highlightthickness=0, **kwargs)
        c.pack(padx=12, pady=6)
        w = EPLWidget(c)
        if name: self._named_widgets[name] = w
        self.children.append(w)
        return w

    def add_image(self, path, name=None, **kwargs):
        try:
            img = tk.PhotoImage(file=path)
            label = ttk.Label(self.root, image=img)
            label.image = img  # prevent GC
            label.pack(padx=12, pady=6)
            w = EPLWidget(label)
            if name: self._named_widgets[name] = w
            self.children.append(w)
            return w
        except Exception:
            return self.add_label(f"[Image: {path}]", name=name)

    def add_listbox(self, items=None, name=None, **kwargs):
        lb = tk.Listbox(self.root, font=('Segoe UI', 11),
                        bg='#1e293b', fg='#f1f5f9', selectbackground='#3b82f6',
                        relief='flat', **kwargs)
        if items:
            for item in items: lb.insert(tk.END, item)
        lb.pack(padx=12, pady=6, fill='both', expand=True)
        w = EPLWidget(lb)
        if name: self._named_widgets[name] = w
        self.children.append(w)
        return w

    def add_separator(self):
        sep = ttk.Separator(self.root, orient='horizontal')
        sep.pack(fill='x', padx=12, pady=8)

    # ─── Layout Containers ───────────────────────────────

    def add_row(self, name=None):
        frame = ttk.Frame(self.root, style='EPL.TFrame')
        frame.pack(fill='x', padx=12, pady=4)
        w = EPLWidget(frame)
        if name: self._named_widgets[name] = w
        return frame

    def add_column(self, name=None):
        frame = ttk.Frame(self.root, style='EPL.TFrame')
        frame.pack(side='left', fill='y', padx=12, pady=4)
        w = EPLWidget(frame)
        if name: self._named_widgets[name] = w
        return frame

    # ─── Menu ────────────────────────────────────────────

    def add_menu(self, menu_def):
        """Add a menu bar. menu_def = {'File': [('New', cmd), ('Exit', cmd)], ...}"""
        menubar = tk.Menu(self.root)
        for label, items in menu_def.items():
            menu = tk.Menu(menubar, tearoff=0)
            for name, command in items:
                if name == '-':
                    menu.add_separator()
                else:
                    menu.add_command(label=name, command=command)
            menubar.add_cascade(label=label, menu=menu)
        self.root.config(menu=menubar)

    # ─── Dialogs ─────────────────────────────────────────

    def show_message(self, title, message):
        messagebox.showinfo(title, message)

    def show_error(self, title, message):
        messagebox.showerror(title, message)

    def ask_yes_no(self, title, message):
        return messagebox.askyesno(title, message)

    def ask_text(self, title, prompt):
        from tkinter import simpledialog
        return simpledialog.askstring(title, prompt)

    def open_file_dialog(self, filetypes=None):
        if not filetypes: filetypes = [('All files', '*.*')]
        return filedialog.askopenfilename(filetypes=filetypes)

    def save_file_dialog(self, filetypes=None):
        if not filetypes: filetypes = [('All files', '*.*')]
        return filedialog.asksaveasfilename(filetypes=filetypes)

    def pick_color(self):
        color = colorchooser.askcolor()
        return color[1] if color else None

    # ─── Widget Access ───────────────────────────────────

    def get_widget(self, name):
        return self._named_widgets.get(name)

    def get_value(self, name):
        """Get the current value of a named input widget."""
        w = self._named_widgets.get(name)
        if w and hasattr(w, 'variable'):
            return w.variable.get()
        if w and w.tk_widget:
            if isinstance(w.tk_widget, tk.Text):
                return w.tk_widget.get('1.0', tk.END).rstrip('\n')
            if isinstance(w.tk_widget, tk.Listbox):
                sel = w.tk_widget.curselection()
                return w.tk_widget.get(sel[0]) if sel else None
        return None

    def set_value(self, name, value):
        """Set the value of a named widget."""
        w = self._named_widgets.get(name)
        if w and hasattr(w, 'variable'):
            w.variable.set(value)
        elif w and w.tk_widget:
            if isinstance(w.tk_widget, ttk.Label):
                w.tk_widget.configure(text=value)
            elif isinstance(w.tk_widget, tk.Text):
                w.tk_widget.delete('1.0', tk.END)
                w.tk_widget.insert('1.0', value)

    # ─── Events ──────────────────────────────────────────

    def on_event(self, widget_name, event, callback):
        """Bind an event to a named widget. Events: click, double_click, key, change."""
        w = self._named_widgets.get(widget_name)
        if not w or not w.tk_widget: return
        event_map = {
            'click': '<Button-1>', 'double_click': '<Double-1>',
            'key': '<Key>', 'enter': '<Return>', 'escape': '<Escape>',
            'focus_in': '<FocusIn>', 'focus_out': '<FocusOut>',
            'right_click': '<Button-3>',
        }
        tk_event = event_map.get(event, event)
        w.tk_widget.bind(tk_event, lambda e: callback())

    # ─── Canvas Drawing ──────────────────────────────────

    def draw_rect(self, canvas_name, x, y, w, h, color='#3b82f6', outline=''):
        c = self._named_widgets.get(canvas_name)
        if c and c.tk_widget:
            c.tk_widget.create_rectangle(x, y, x+w, y+h, fill=color, outline=outline)

    def draw_circle(self, canvas_name, x, y, r, color='#8b5cf6', outline=''):
        c = self._named_widgets.get(canvas_name)
        if c and c.tk_widget:
            c.tk_widget.create_oval(x-r, y-r, x+r, y+r, fill=color, outline=outline)

    def draw_line(self, canvas_name, x1, y1, x2, y2, color='#f1f5f9', width=2):
        c = self._named_widgets.get(canvas_name)
        if c and c.tk_widget:
            c.tk_widget.create_line(x1, y1, x2, y2, fill=color, width=width)

    def draw_text(self, canvas_name, x, y, text, color='#f1f5f9', size=12):
        c = self._named_widgets.get(canvas_name)
        if c and c.tk_widget:
            c.tk_widget.create_text(x, y, text=text, fill=color,
                                     font=('Segoe UI', size))

    def clear_canvas(self, canvas_name):
        c = self._named_widgets.get(canvas_name)
        if c and c.tk_widget:
            c.tk_widget.delete('all')


# ─── Convenience Functions for EPL Interpreter ───────────

_current_window = None


def create_window(title="EPL App", width=800, height=600):
    global _current_window
    _current_window = EPLWindow(title, width, height)
    return _current_window


def get_window():
    return _current_window


def gui_available():
    return HAS_TK
