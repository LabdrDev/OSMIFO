# pemilah_full_custom_dark.py
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk
import os
import shutil
from datetime import datetime

# optional: send to recycle bin
try:
    from send2trash import send2trash
except Exception:
    send2trash = None

# optional: customtkinter (theme / improved widgets)
try:
    import customtkinter as ctk
    CTK_AVAILABLE = True
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
except Exception:
    CTK_AVAILABLE = False

# THEME CONSTANTS (dark theme)
DARK_BG = "#020403"         # main dark background
PANEL_BG = "#111"           # panel / image background
BTN_BG = "#2b2b2b"          # standard tk button background
BTN_ACTIVE = "#3c3c3c"      # active background for tk buttons
FG = "white"                # primary foreground
MUTED = "lightgray"         # secondary/placeholder text color
MAX_IMAGE_SIZE = (800, 600)          # batas maksimum tampilan gambar (bukan ukuran wajib)
SMALL_THUMB_SIZE = (160, 120)        # ukuran cuplikan prev/next
GALLERY_THUMB_SIZE = (160, 120)      # ukuran thumbnail di Gallery Mode
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')


def human_readable_size(num_bytes: int) -> str:
    try:
        n = float(num_bytes)
        for unit in ['bytes', 'KB', 'MB', 'GB', 'TB']:
            if n < 1024.0 or unit == 'TB':
                if unit == 'bytes':
                    return f"{int(n)} {unit}"
                return f"{n:0.1f} {unit}"
            n /= 1024.0
    except Exception:
        pass
    return "—"


def human_readable_datetime(timestamp: float) -> str:
    try:
        dt = datetime.fromtimestamp(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "—"


class ToolTip:
    """Tooltip sederhana untuk widget Tkinter."""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tw = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, _event):
        if self.tw or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tw = tk.Toplevel(self.widget)
        self.tw.wm_overrideredirect(True)
        self.tw.geometry(f"+{x}+{y}")
        lbl = tk.Label(self.tw, text=self.text, background="#ffffe0", relief="solid", borderwidth=1)
        lbl.pack(ipadx=6, ipady=3)

    def hide(self, _event):
        if self.tw:
            self.tw.destroy()
            self.tw = None


class PhotoSorterApp:
    def __init__(self, root):
        # If customtkinter available and it's a CTk root, use it; otherwise plain tk root
        self.root = root
        self.root.title("OSMIFO - Aplikasi Pemilah Foto by OSMIB Eduvasi v5")
        self.root.geometry("1200x900")
        try:
            self.root.configure(bg=DARK_BG)
        except Exception:
            pass

        # State
        self.source_dir = ""
        self.dest_dirs = []
        self.image_list = []
        self.current_index = 0
        self.copy_mode = tk.BooleanVar(value=False)  # central source of truth for copy/move
        self.in_gallery_mode = False

        # Zoom state
        self.zoom_scale = 1.0       # manual scale (1.0 == 100%)
        self.zoom_step = 1.25
        self.zoom_min = 0.2
        self.zoom_max = 8.0
        self.fit_mode = True        # True -> fit to window behavior (default)

        # Cache
        self.thumb_cache = {}
        self.gallery_cache = {}
        self.current_path = None
        self.current_pil = None
        self.current_photo = None

        # Root layout
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(3, weight=1)

        # watch copy_mode changes to update UI indicator
        try:
            # Python 3.7+ : trace_add
            self.copy_mode.trace_add("write", self._on_copy_mode_changed)
        except Exception:
            # older trace API
            self.copy_mode.trace("w", lambda *a: self._on_copy_mode_changed())

        self.create_widgets()
        self.bind_shortcuts()

    # ------------------------------ UI BUILD ------------------------------
    def create_widgets(self):
        top = tk.Frame(self.root, pady=8, bg=DARK_BG)
        top.grid(row=0, column=0, sticky="ew")
        top.grid_columnconfigure(2, weight=1)

        if CTK_AVAILABLE:
            btn_source = ctk.CTkButton(top, text="1) Pilih Folder Sumber Foto", command=self.select_source_folder, width=220)
            btn_source.grid(row=0, column=0, padx=10, sticky="w")
        else:
            btn_source = tk.Button(top, text="1) Pilih Folder Sumber Foto", command=self.select_source_folder,
                                   bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            btn_source.grid(row=0, column=0, padx=10, sticky="w")

        title_frame = tk.Frame(top, bg=DARK_BG)
        title_frame.grid(row=0, column=1, sticky="w")
        title_label = tk.Label(title_frame, text="OMIFO", font=("Helvetica", 18, "bold"), fg=FG, bg=DARK_BG)
        title_label.pack(side="left")
        ver_label = tk.Label(title_frame, text=" v5", font=("Helvetica", 12), fg=FG, bg=DARK_BG)
        ver_label.pack(side="left", padx=(4, 0))

        self.source_label = tk.Label(top, text="Belum ada folder sumber yang dipilih", fg=MUTED, bg=DARK_BG, anchor="w")
        self.source_label.grid(row=0, column=2, sticky="ew", padx=(8, 14))

        self.source_tooltip = None

        # dest area
        self.dest_frame = tk.Frame(self.root, pady=6, bg=DARK_BG)
        self.dest_frame.grid(row=1, column=0, sticky="ew", padx=10)
        self.dest_frame.grid_columnconfigure(0, weight=1)

        row1 = tk.Frame(self.dest_frame, bg=DARK_BG)
        row1.grid(row=0, column=0, sticky="w")

        if CTK_AVAILABLE:
            add_one_btn = ctk.CTkButton(row1, text="2) Tambah 1 Folder Tujuan (+)", command=self.add_dest_folder_single, width=220)
            add_one_btn.pack(side="left", padx=(0, 6))
            add_multi_btn = ctk.CTkButton(row1, text="2b) Tambah Banyak Folder (Multi)", command=self.open_multi_dest_picker)
            add_multi_btn.pack(side="left")
        else:
            add_one_btn = tk.Button(row1, text="2) Tambah 1 Folder Tujuan (+)", command=self.add_dest_folder_single,
                                    bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            add_one_btn.pack(side="left", padx=(0, 6))
            add_multi_btn = tk.Button(row1, text="2b) Tambah Banyak Folder (Multi)", command=self.open_multi_dest_picker,
                                      bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            add_multi_btn.pack(side="left")

        self.dest_buttons_frame = tk.Frame(self.root, bg=DARK_BG)
        self.dest_buttons_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=6)

        self.main_area = tk.Frame(self.root, bg=DARK_BG)
        self.main_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self.main_area.grid_columnconfigure(0, weight=1)
        self.main_area.grid_rowconfigure(0, weight=1)

        # image view (canvas)
        self.image_frame = tk.Frame(self.main_area, relief="sunken", borderwidth=2, bg=PANEL_BG)
        self.image_frame.grid(row=0, column=0, sticky="nsew")
        self.image_frame.grid_propagate(False)

        self.image_canvas = tk.Canvas(self.image_frame, bg=PANEL_BG, highlightthickness=0)
        self.image_hbar = tk.Scrollbar(self.image_frame, orient="horizontal", command=self.image_canvas.xview)
        self.image_vbar = tk.Scrollbar(self.image_frame, orient="vertical", command=self.image_canvas.yview)
        self.image_canvas.configure(xscrollcommand=self.image_hbar.set, yscrollcommand=self.image_vbar.set)

        self.image_canvas.pack(fill="both", expand=True, side="left")
        self.image_vbar.pack(fill="y", side="right")
        self.image_hbar.pack(fill="x", side="bottom")

        self.image_canvas_img_id = None

        # panning
        self._pan_start = None
        self.image_canvas.bind("<ButtonPress-1>", self._start_pan)
        self.image_canvas.bind("<B1-Motion>", self._do_pan)

        # zoom with Ctrl+wheel
        self.root.bind_all("<Control-MouseWheel>", self._on_ctrl_mousewheel)
        self.root.bind_all("<Control-Button-4>", self._on_ctrl_mousewheel)
        self.root.bind_all("<Control-Button-5>", self._on_ctrl_mousewheel)

        # info panel
        self.info_frame = tk.Frame(self.main_area, width=360, bg=DARK_BG)
        self.info_frame.grid(row=0, column=1, sticky="ns", padx=(12, 0))
        self.info_frame.grid_propagate(False)

        info_title = tk.Label(self.info_frame, text="Detail File", font=("TkDefaultFont", 12, "bold"), bg=DARK_BG, fg=FG)
        info_title.pack(anchor="nw", pady=(6, 4))

        self.file_name_label = tk.Label(self.info_frame, text="Nama: —", anchor="w", justify="left", wraplength=340, bg=DARK_BG, fg=FG)
        self.file_name_label.pack(anchor="nw", fill="x", pady=(6, 2))

        self.file_size_label = tk.Label(self.info_frame, text="Ukuran: —", anchor="w", justify="left", bg=DARK_BG, fg=FG)
        self.file_size_label.pack(anchor="nw", fill="x", pady=(2, 2))

        self.file_type_label = tk.Label(self.info_frame, text="Tipe: —", anchor="w", justify="left", bg=DARK_BG, fg=FG)
        self.file_type_label.pack(anchor="nw", fill="x", pady=(2, 2))

        self.file_resolution_label = tk.Label(self.info_frame, text="Resolusi: —", anchor="w", justify="left", bg=DARK_BG, fg=FG)
        self.file_resolution_label.pack(anchor="nw", fill="x", pady=(2, 2))

        self.file_created_label = tk.Label(self.info_frame, text="Tanggal dibuat: —", anchor="w", justify="left", bg=DARK_BG, fg=FG)
        self.file_created_label.pack(anchor="nw", fill="x", pady=(6, 2))

        self.file_path_label = tk.Label(self.info_frame, text="Path: —", anchor="w", justify="left", wraplength=340, fg="gray", bg=DARK_BG)
        self.file_path_label.pack(anchor="nw", fill="x", pady=(8, 2))

        def copy_path_to_clipboard():
            text = self.file_path_label.cget("text")
            if text and text != "Path: —":
                self.root.clipboard_clear()
                self.root.clipboard_append(text)
                messagebox.showinfo("Copied", "Path file disalin ke clipboard.")
        if CTK_AVAILABLE:
            ctk.CTkButton(self.info_frame, text="Salin Path", command=copy_path_to_clipboard).pack(anchor="nw", pady=(6, 0))
        else:
            tk.Button(self.info_frame, text="Salin Path", command=copy_path_to_clipboard, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG).pack(anchor="nw", pady=(6, 0))

        # gallery
        self.gallery_frame = None

        # nav area
        nav_outer = tk.Frame(self.root, pady=6, bg=DARK_BG)
        nav_outer.grid(row=4, column=0, sticky="ew")

        thumbs_row = tk.Frame(nav_outer, bg=DARK_BG)
        thumbs_row.pack(fill="x", pady=(0, 6))

        prev_box = tk.Frame(thumbs_row, width=SMALL_THUMB_SIZE[0], height=SMALL_THUMB_SIZE[1], relief="groove", bd=1, bg=DARK_BG)
        prev_box.pack(side="left", padx=10)
        prev_box.pack_propagate(False)
        self.prev_thumb_label = tk.Label(prev_box, text="— Prev —", bg=DARK_BG, fg=MUTED)
        self.prev_thumb_label.pack(fill="both", expand=True)
        prev_box.bind("<Button-1>", lambda e: self.jump_prev())
        self.prev_thumb_label.bind("<Button-1>", lambda e: self.jump_prev())

        spacer = tk.Frame(thumbs_row, bg=DARK_BG)
        spacer.pack(side="left", expand=True, fill="x")

        next_box = tk.Frame(thumbs_row, width=SMALL_THUMB_SIZE[0], height=SMALL_THUMB_SIZE[1], relief="groove", bd=1, bg=DARK_BG)
        next_box.pack(side="right", padx=10)
        next_box.pack_propagate(False)
        self.next_thumb_label = tk.Label(next_box, text="— Next —", bg=DARK_BG, fg=MUTED)
        self.next_thumb_label.pack(fill="both", expand=True)
        next_box.bind("<Button-1>", lambda e: self.jump_next())
        self.next_thumb_label.bind("<Button-1>", lambda e: self.jump_next())

        nav = tk.Frame(nav_outer, bg=DARK_BG)
        nav.pack(fill="x")

        if CTK_AVAILABLE:
            self.back_button = ctk.CTkButton(nav, text="⬅️ Kembali", command=self.go_back, width=140)
        else:
            self.back_button = tk.Button(nav, text="⬅️ Kembali", command=self.go_back, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
        self.back_button.pack(side="left", expand=True, padx=10)

        if CTK_AVAILABLE:
            self.gallery_button = ctk.CTkButton(nav, text="📂 Gallery Mode", command=self.toggle_gallery_mode, width=160)
        else:
            self.gallery_button = tk.Button(nav, text="📂 Gallery Mode", command=self.toggle_gallery_mode, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
        self.gallery_button.pack(side="left", expand=True, padx=10)

        # copy control
        if CTK_AVAILABLE:
            try:
                self.copy_switch = ctk.CTkSwitch(nav, text="Salin file (Copy)", variable=self.copy_mode)
                self.copy_switch.pack(side="left", expand=True)
            except Exception:
                self.copy_checkbox = ctk.CTkCheckBox(nav, text="Salin file (Copy) — bukan pindah", variable=self.copy_mode)
                self.copy_checkbox.pack(side="left", expand=True)
        else:
            self.copy_checkbox = tk.Checkbutton(
                nav,
                text="Salin file (Copy) — bukan pindah",
                variable=self.copy_mode,
                bg=DARK_BG,
                fg=FG,
                selectcolor=DARK_BG,
                activebackground=DARK_BG,
                activeforeground=FG,
                highlightthickness=0,
                bd=0
            )
            self.copy_checkbox.pack(side="left", expand=True)

        status_container = tk.Frame(nav, bg=DARK_BG)
        status_container.pack(side="left", padx=(8, 6))
        self.copy_status_canvas = tk.Canvas(status_container, width=18, height=18, highlightthickness=0, bg=DARK_BG)
        self.copy_status_canvas.pack(side="left")
        self.copy_status_text = tk.Label(status_container, text="MOVE", anchor="w", bg=DARK_BG, fg=FG)
        self.copy_status_text.pack(side="left", padx=(6, 0))
        self._update_copy_indicator(initial=True)

        # Zoom controls: Out, In, Fit, Actual(100%)
        if CTK_AVAILABLE:
            self.zoom_out_btn = ctk.CTkButton(nav, text="🔍-", command=self.zoom_out, width=60)
            self.zoom_in_btn = ctk.CTkButton(nav, text="🔍+", command=self.zoom_in, width=60)
            self.fit_btn = ctk.CTkButton(nav, text="Fit", command=self.fit_to_window, width=60)
            self.actual_btn = ctk.CTkButton(nav, text="100%", command=self.actual_size, width=60)
        else:
            self.zoom_out_btn = tk.Button(nav, text="🔍-", command=self.zoom_out, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            self.zoom_in_btn = tk.Button(nav, text="🔍+", command=self.zoom_in, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            self.fit_btn = tk.Button(nav, text="Fit", command=self.fit_to_window, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            self.actual_btn = tk.Button(nav, text="100%", command=self.actual_size, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)

        self.zoom_out_btn.pack(side="left", padx=(8, 2))
        self.zoom_in_btn.pack(side="left", padx=(2, 2))
        self.fit_btn.pack(side="left", padx=(2, 2))
        self.actual_btn.pack(side="left", padx=(2, 10))

        if CTK_AVAILABLE:
            self.delete_button = ctk.CTkButton(nav, text="🗑️ Hapus (Recycle Bin)", command=self.delete_current_file, width=140)
        else:
            self.delete_button = tk.Button(nav, text="🗑️ Hapus (Recycle Bin)", command=self.delete_current_file, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
        self.delete_button.pack(side="left", expand=True, padx=6)

        if CTK_AVAILABLE:
            self.next_button = ctk.CTkButton(nav, text="Berikutnya ➡️", command=self.go_next, width=140)
        else:
            self.next_button = tk.Button(nav, text="Berikutnya ➡️", command=self.go_next, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
        self.next_button.pack(side="left", expand=True, padx=10)

        # status bar
        self.status_label = tk.Label(self.root, text="Selamat datang! Pilih folder sumber.", bd=1, relief="sunken", anchor="w", bg=DARK_BG, fg=FG)
        self.status_label.grid(row=5, column=0, sticky="ew")

        self.render_dest_buttons()

    # ------------------------------ Shortcuts ------------------------------
    def bind_shortcuts(self):
        self.root.bind_all("<Left>", lambda e: self.go_back())
        self.root.bind_all("<Right>", lambda e: self.go_next())
        self.root.bind_all("<c>", lambda e: self.copy_mode.set(not self.copy_mode.get()))
        self.root.bind_all("<C>", lambda e: self.copy_mode.set(not self.copy_mode.get()))

        try:
            self.root.bind_all("=", lambda e: self.zoom_in())
            self.root.bind_all("-", lambda e: self.zoom_out())
        except Exception:
            pass

        digit_map = [('1', 0), ('2', 1), ('3', 2), ('4', 3), ('5', 4),
                     ('6', 5), ('7', 6), ('8', 7), ('9', 8), ('0', 9)]
        for key, idx in digit_map:
            self.root.bind_all(key, self.make_hotkey_handler(idx))

        self.root.bind_all("<Delete>", lambda e: self.delete_current_file())
        self.root.bind_all("x", lambda e: self.delete_current_file())
        self.root.bind_all("X", lambda e: self.delete_current_file())

    def make_hotkey_handler(self, dest_index_zero_based):
        def handler(_event):
            if 0 <= dest_index_zero_based < len(self.dest_dirs) and self.image_list and not self.in_gallery_mode:
                self.status_label.config(text=f"[HOTKEY] Proses ke folder #{dest_index_zero_based+1}")
                self.process_file(self.dest_dirs[dest_index_zero_based]['path'])
            else:
                self.status_label.config(text="Shortcut belum terisi folder tujuan tersebut.")
        return handler

    def toggle_copy_mode(self):
        self.copy_mode.set(not self.copy_mode.get())

    def _on_copy_mode_changed(self, *args):
        self._update_copy_indicator()
        self.update_status_bar()

    def _update_copy_indicator(self, initial=False):
        is_copy = bool(self.copy_mode.get())
        color = "#2ecc71" if is_copy else "#f39c12"
        text = "COPY" if is_copy else "MOVE"
        try:
            self.copy_status_canvas.delete("all")
            self.copy_status_canvas.create_oval(2, 2, 16, 16, fill=color, outline=color)
        except Exception:
            pass
        try:
            self.copy_status_text.config(text=text, fg=FG)
        except Exception:
            try:
                self.copy_status_text.config(text=text)
            except Exception:
                pass
        if initial:
            try:
                ToolTip(self.copy_status_canvas, "Mode saat ini: COPY/MOVE")
            except Exception:
                pass

    # ------------------------------ Gallery Mode ------------------------------
    def toggle_gallery_mode(self):
        if self.in_gallery_mode:
            self.close_gallery_mode()
        else:
            self.open_gallery_mode()

    def open_gallery_mode(self):
        if not self.image_list or self.in_gallery_mode:
            return
        self.in_gallery_mode = True
        try:
            if CTK_AVAILABLE:
                self.gallery_button.configure(text="⬅️ Tutup Gallery")
            else:
                self.gallery_button.config(text="⬅️ Tutup Gallery")
        except Exception:
            pass

        self.image_frame.grid_remove()
        self.info_frame.grid_remove()

        self.gallery_frame = tk.Frame(self.main_area, bg=DARK_BG)
        self.gallery_frame.grid(row=0, column=0, columnspan=2, sticky="nsew")

        canvas = tk.Canvas(self.gallery_frame, highlightthickness=0, bg=DARK_BG)
        vbar = tk.Scrollbar(self.gallery_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vbar.set)

        inner = tk.Frame(canvas, bg=DARK_BG)
        canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_config(_e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_config)

        canvas.pack(side="left", fill="both", expand=True)
        vbar.pack(side="right", fill="y")

        max_cols = 5
        for i, fname in enumerate(self.image_list):
            path = os.path.normpath(os.path.join(self.source_dir, fname))
            thumb = self._make_gallery_thumb(path)

            cell = tk.Frame(inner, padx=6, pady=6, bg=DARK_BG)
            cell.grid(row=i // max_cols, column=i % max_cols, sticky="n")

            if thumb is not None:
                btn = tk.Button(cell, image=thumb, command=lambda idx=i: self.open_image_from_gallery(idx), bg=DARK_BG)
                btn.image = thumb
                btn.pack()
            else:
                btn = tk.Button(cell, text="Preview\nunavailable", width=22, height=8, command=lambda idx=i: self.open_image_from_gallery(idx), bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
                btn.pack()

            lbl = tk.Label(cell, text=fname, wraplength=GALLERY_THUMB_SIZE[0], justify="center", bg=DARK_BG, fg=FG)
            lbl.pack(pady=(4, 0))

    def close_gallery_mode(self):
        if not self.in_gallery_mode:
            return
        if self.gallery_frame:
            self.gallery_frame.destroy()
            self.gallery_frame = None
        self.image_frame.grid()
        self.info_frame.grid()
        self.in_gallery_mode = False
        try:
            if CTK_AVAILABLE:
                self.gallery_button.configure(text="📂 Gallery Mode")
            else:
                self.gallery_button.config(text="📂 Gallery Mode")
        except Exception:
            pass

    def refresh_gallery_if_open(self):
        if self.in_gallery_mode:
            self.close_gallery_mode()
            self.open_gallery_mode()

    def _make_gallery_thumb(self, image_path):
        image_path = os.path.normpath(image_path)
        if image_path in self.gallery_cache:
            return self.gallery_cache[image_path]
        try:
            with Image.open(image_path) as img:
                img = img.copy()
            img.thumbnail(GALLERY_THUMB_SIZE, Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self.gallery_cache[image_path] = ph
            return ph
        except Exception:
            return None

    def open_image_from_gallery(self, idx):
        if 0 <= idx < len(self.image_list):
            self.current_index = idx
            self.close_gallery_mode()
            self.display_current_image()

    # ------------------------------ Sumber & Tujuan ------------------------------
    def select_source_folder(self):
        folder_path = filedialog.askdirectory(title="Pilih Folder Sumber Foto")
        if folder_path:
            self.source_dir = os.path.normpath(folder_path)
            name = os.path.basename(folder_path) or folder_path
            self.source_label.config(text=f"Sumber: {name}", fg=FG)
            if self.source_tooltip:
                try:
                    self.source_tooltip.hide(None)
                except Exception:
                    pass
            self.source_tooltip = ToolTip(self.source_label, self.source_dir)
            self.load_images()

    def add_dest_folder_single(self):
        folder_path = filedialog.askdirectory(title="Pilih Folder Tujuan")
        if not folder_path:
            return
        self.add_dest_paths([folder_path])

    def open_multi_dest_picker(self):
        win = tk.Toplevel(self.root)
        win.title("Pilih Banyak Folder Tujuan")
        win.geometry("640x420")
        win.transient(self.root)
        win.grab_set()
        try:
            win.configure(bg=DARK_BG)
        except Exception:
            pass

        top = tk.Frame(win, pady=6, padx=8, bg=DARK_BG)
        top.pack(fill="x")
        tk.Label(top, text="Tambahkan beberapa folder ke daftar, lalu klik 'Tambahkan ke Aplikasi'.", bg=DARK_BG, fg=FG).pack(anchor="w")

        mid = tk.Frame(win, padx=8, bg=DARK_BG)
        mid.pack(fill="both", expand=True)

        lb_paths = tk.Listbox(mid, selectmode="extended", bg=BTN_BG, fg=FG)
        lb_paths.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(mid, orient="vertical", command=lb_paths.yview)
        sb.pack(side="left", fill="y")
        lb_paths.config(yscrollcommand=sb.set)

        side = tk.Frame(mid, padx=8, bg=DARK_BG)
        side.pack(side="left", fill="y")

        def add_folder_to_list():
            p = filedialog.askdirectory(title="Pilih Folder Tujuan")
            if not p:
                return
            p = os.path.normpath(p)
            existing = [lb_paths.get(i) for i in range(lb_paths.size())]
            already_in_app = [d['path'] for d in self.dest_dirs]
            if p in existing or p in already_in_app:
                messagebox.showinfo("Lewati", "Folder sudah ada di daftar tujuan.")
                return
            lb_paths.insert("end", p)

        def remove_selected_from_list():
            sel = list(lb_paths.curselection())
            if not sel:
                return
            sel.reverse()
            for i in sel:
                lb_paths.delete(i)

        def add_all_to_app():
            paths = [lb_paths.get(i) for i in range(lb_paths.size())]
            if not paths:
                win.destroy()
                return
            self.add_dest_paths(paths)
            win.destroy()

        tk.Button(side, text="➕ Tambah Folder…", command=add_folder_to_list, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG).pack(fill="x", pady=(0, 6))
        tk.Button(side, text="🗑️ Hapus dari Daftar", command=remove_selected_from_list, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG).pack(fill="x", pady=(0, 6))
        tk.Button(side, text="✅ Tambahkan ke Aplikasi", command=add_all_to_app, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG).pack(fill="x", pady=(0, 6))
        tk.Button(side, text="Tutup", command=win.destroy, bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG).pack(fill="x")

    def add_dest_paths(self, paths):
        added = 0
        for p in paths:
            p = os.path.normpath(p)
            if not os.path.isdir(p):
                continue
            if p in [d['path'] for d in self.dest_dirs]:
                continue
            folder_name = os.path.basename(p) or p
            self.dest_dirs.append({'path': p, 'name': folder_name, 'button': None})
            added += 1
        if added == 0:
            messagebox.showinfo("Info", "Tidak ada folder baru yang ditambahkan (mungkin duplikat/invalid).")
        self.render_dest_buttons()
        self.update_buttons_state()

    def remove_dest_folder(self, idx):
        if not (0 <= idx < len(self.dest_dirs)):
            return
        d = self.dest_dirs[idx]
        ok = messagebox.askyesno("Hapus Folder Tujuan?", f"Hapus dari daftar tujuan?\n\n{d['name']}\n{d['path']}")
        if not ok:
            return
        self.dest_dirs.pop(idx)
        self.render_dest_buttons()
        self.update_buttons_state()

    def render_dest_buttons(self):
        for w in self.dest_buttons_frame.winfo_children():
            w.destroy()

        max_cols = 4
        for c in range(max_cols):
            self.dest_buttons_frame.grid_columnconfigure(c, weight=1, uniform="btns")

        for i, d in enumerate(self.dest_dirs):
            r, c = divmod(i, max_cols)
            cell = tk.Frame(self.dest_buttons_frame, bg=DARK_BG)
            cell.grid(row=r, column=c, padx=6, pady=6, sticky="ew")

            if i < 9:
                prefix = f"{i + 1}. "
            elif i == 9:
                prefix = "0. "
            else:
                prefix = ""

            if CTK_AVAILABLE:
                btn = ctk.CTkButton(cell, text=f"{prefix}Proses ke '{d['name']}'", command=lambda p=d['path']: self.process_file(p))
            else:
                btn = tk.Button(cell, text=f"{prefix}Proses ke '{d['name']}'", command=lambda p=d['path']: self.process_file(p), bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            btn.pack(side="left", fill="x", expand=True)

            rm = tk.Button(cell, text="❌", width=3, command=lambda idx=i: self.remove_dest_folder(idx), bg=BTN_BG, fg=FG, activebackground=BTN_ACTIVE, activeforeground=FG)
            rm.pack(side="left", padx=(6, 0))

            d['button'] = btn

    # ------------------------------ Manajemen Gambar ------------------------------
    def load_images(self):
        try:
            self.image_list = sorted([
                f for f in os.listdir(self.source_dir)
                if f.lower().endswith(SUPPORTED_EXTENSIONS)
            ])
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membaca folder sumber: {e}")
            self.image_list = []

        self.current_index = 0
        self.thumb_cache.clear()
        self.gallery_cache.clear()
        self.current_path = None
        self.current_pil = None
        self.current_photo = None
        self.zoom_scale = 1.0
        self.fit_mode = True

        if self.in_gallery_mode:
            self.close_gallery_mode()

        if not self.image_list:
            messagebox.showinfo("Kosong", "Tidak ada file foto yang ditemukan di folder ini.")
            self.image_canvas.delete("all")
            self.image_canvas.create_text(10, 10, text="Tidak ada foto di folder sumber. Pilih folder lain.", anchor="nw", fill=FG)
            self._clear_file_details()
            self.update_buttons_state()
            self.update_status_bar()
            return

        self.display_current_image()

    def _clear_file_details(self):
        self.file_name_label.config(text="Nama: —")
        self.file_size_label.config(text="Ukuran: —")
        self.file_type_label.config(text="Tipe: —")
        self.file_resolution_label.config(text="Resolusi: —")
        self.file_created_label.config(text="Tanggal dibuat: —")
        self.file_path_label.config(text="Path: —")
        self.prev_thumb_label.config(image='', text="— Prev —", fg=MUTED, bg=DARK_BG)
        self.prev_thumb_label.image = None
        self.next_thumb_label.config(image='', text="— Next —", fg=MUTED, bg=DARK_BG)
        self.next_thumb_label.image = None

    def _make_small_thumb(self, image_path):
        image_path = os.path.normpath(image_path)
        if image_path in self.thumb_cache:
            return self.thumb_cache[image_path]
        try:
            with Image.open(image_path) as img:
                img = img.copy()
            img.thumbnail(SMALL_THUMB_SIZE, Image.Resampling.LANCZOS)
            ph = ImageTk.PhotoImage(img)
            self.thumb_cache[image_path] = ph
            return ph
        except Exception:
            return None

    def update_prev_next_thumbs(self):
        prev_index = self.current_index - 1
        if 0 <= prev_index < len(self.image_list):
            prev_path = os.path.normpath(os.path.join(self.source_dir, self.image_list[prev_index]))
            ph = self._make_small_thumb(prev_path)
            if ph:
                self.prev_thumb_label.config(image=ph, text="")
                self.prev_thumb_label.image = ph
            else:
                self.prev_thumb_label.config(image='', text="— Prev —", fg=MUTED, bg=DARK_BG)
                self.prev_thumb_label.image = None
        else:
            self.prev_thumb_label.config(image='', text="— Prev —", fg=MUTED, bg=DARK_BG)
            self.prev_thumb_label.image = None

        next_index = self.current_index + 1
        if next_index < len(self.image_list):
            next_path = os.path.normpath(os.path.join(self.source_dir, self.image_list[next_index]))
            ph = self._make_small_thumb(next_path)
            if ph:
                self.next_thumb_label.config(image=ph, text="")
                self.next_thumb_label.image = ph
            else:
                self.next_thumb_label.config(image='', text="— Next —", fg=MUTED, bg=DARK_BG)
                self.next_thumb_label.image = None
        else:
            self.next_thumb_label.config(image='', text="— Next —", fg=MUTED, bg=DARK_BG)
            self.next_thumb_label.image = None

    def _render_current_image_fit(self):
        """Render ulang gambar aktif agar pas di image_canvas sesuai mode (fit/manual)."""
        if not self.current_pil:
            return

        try:
            cw = max(self.image_canvas.winfo_width(), 1)
            ch = max(self.image_canvas.winfo_height(), 1)
        except Exception:
            cw, ch = MAX_IMAGE_SIZE

        iw, ih = self.current_pil.width, self.current_pil.height
        if iw == 0 or ih == 0:
            return

        if self.fit_mode:
            # Fit to viewport (allow upscaling if image smaller)
            scale = min(cw / iw, ch / ih)
            target_w = int(iw * scale)
            target_h = int(ih * scale)
        else:
            # Manual zoom
            z = max(self.zoom_min, min(self.zoom_scale, self.zoom_max))
            target_w = int(iw * z)
            target_h = int(ih * z)

        try:
            img = self.current_pil.copy()
            if (img.width, img.height) != (target_w, target_h):
                img = img.resize((max(1, target_w), max(1, target_h)), Image.Resampling.LANCZOS)
            self.current_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            print("[Error] render image:", e)
            return

        # place image on canvas
        self.image_canvas.delete("all")
        self.image_canvas_img_id = self.image_canvas.create_image(0, 0, anchor='nw', image=self.current_photo)
        self.image_canvas.config(scrollregion=(0, 0, target_w, target_h))

        # center if smaller than canvas
        cx = max((cw - target_w) // 2, 0)
        cy = max((ch - target_h) // 2, 0)
        self.image_canvas.coords(self.image_canvas_img_id, cx, cy)

    def zoom_in(self):
        # disable fit mode when user actively zooms
        self.fit_mode = False
        new_zoom = min(self.zoom_scale * self.zoom_step, self.zoom_max)
        if abs(new_zoom - self.zoom_scale) < 1e-6:
            return
        self.zoom_scale = new_zoom
        self._render_current_image_fit()
        self.update_status_bar()

    def zoom_out(self):
        self.fit_mode = False
        new_zoom = max(self.zoom_scale / self.zoom_step, self.zoom_min)
        if abs(new_zoom - self.zoom_scale) < 1e-6:
            return
        self.zoom_scale = new_zoom
        self._render_current_image_fit()
        self.update_status_bar()

    def fit_to_window(self):
        """Set mode ke Fit-to-Window (gambar di-scale supaya memenuhi viewport)."""
        if not self.current_pil:
            return
        self.fit_mode = True
        # zoom_scale tetap sebagai 1.0 (tidak dipakai saat fit_mode True)
        self.zoom_scale = 1.0
        self._render_current_image_fit()
        self.update_status_bar()

    def actual_size(self):
        """Tampilkan gambar pada 100% (actual pixels)."""
        if not self.current_pil:
            return
        self.fit_mode = False
        self.zoom_scale = 1.0
        self._render_current_image_fit()
        self.update_status_bar()

    def _on_ctrl_mousewheel(self, event):
        try:
            delta = getattr(event, 'delta', None)
            if delta is not None:
                if delta > 0:
                    self.zoom_in()
                else:
                    self.zoom_out()
                return
        except Exception:
            pass
        try:
            num = event.num
            if num == 4:
                self.zoom_in()
            elif num == 5:
                self.zoom_out()
        except Exception:
            pass

    def _start_pan(self, event):
        self._pan_start = (event.x, event.y, self.image_canvas.canvasx(0), self.image_canvas.canvasy(0))

    def _do_pan(self, event):
        if not self._pan_start:
            return
        sx, sy, scx, scy = self._pan_start
        dx = sx - event.x
        dy = sy - event.y
        try:
            bbox = self.image_canvas.bbox("all")
            if bbox:
                total_w = max(1, bbox[2])
                total_h = max(1, bbox[3])
                self.image_canvas.xview_moveto((scx + dx) / total_w)
                self.image_canvas.yview_moveto((scy + dy) / total_h)
            else:
                self.image_canvas.scan_mark(sx, sy)
                self.image_canvas.scan_dragto(event.x, event.y, gain=1)
        except Exception:
            try:
                self.image_canvas.scan_mark(sx, sy)
                self.image_canvas.scan_dragto(event.x, event.y, gain=1)
            except Exception:
                pass

    def display_current_image(self):
        if not (0 <= self.current_index < len(self.image_list)):
            self.image_canvas.delete("all")
            self.image_canvas.create_text(10, 10, text="✅ Semua foto telah dipilah!\nPilih folder sumber baru atau tutup aplikasi.", anchor="nw", fill=FG)
            self.current_path = None
            self.current_pil = None
            self.current_photo = None
            self._clear_file_details()
            self.update_buttons_state()
            self.update_status_bar()
            return

        image_path = os.path.normpath(os.path.join(self.source_dir, self.image_list[self.current_index]))

        try:
            with Image.open(image_path) as im:
                self.current_pil = im.copy()
            self.current_path = image_path
        except Exception as e:
            print(f"[Skip] Gagal buka {image_path}: {e}")
            try:
                self.image_list.pop(self.current_index)
            except Exception:
                pass
            if not self.image_list:
                self.image_canvas.delete("all")
                self.image_canvas.create_text(10, 10, text="Tidak ada foto valid.", anchor="nw", fill=FG)
                self._clear_file_details()
                self.update_buttons_state()
                self.update_status_bar()
                return
            if self.current_index >= len(self.image_list):
                self.current_index = len(self.image_list) - 1
            self.display_current_image()
            return

        # reset ke fit-by-default saat membuka gambar baru
        self.zoom_scale = 1.0
        self.fit_mode = True

        self._render_current_image_fit()

        try:
            fname = os.path.basename(image_path)
            fsize = os.path.getsize(image_path)
            fext = os.path.splitext(fname)[1].lower().lstrip('.') or '—'
            res_text = f"{self.current_pil.width} x {self.current_pil.height}"
            created_ts = os.path.getctime(image_path)
            created_text = human_readable_datetime(created_ts)

            self.file_name_label.config(text=f"Nama: {fname}")
            self.file_size_label.config(text=f"Ukuran: {human_readable_size(fsize)}")
            self.file_type_label.config(text=f"Tipe: {fext}")
            self.file_resolution_label.config(text=f"Resolusi: {res_text}")
            self.file_created_label.config(text=f"Tanggal dibuat: {created_text}")
            self.file_path_label.config(text=os.path.abspath(image_path))
        except Exception:
            self._clear_file_details()

        self.update_prev_next_thumbs()
        self.update_buttons_state()
        self.update_status_bar()

    # ------------------------------ File Actions ------------------------------
    def process_file(self, dest_path):
        if not (0 <= self.current_index < len(self.image_list)):
            return

        src_name = self.image_list[self.current_index]
        src_path = os.path.normpath(os.path.join(self.source_dir, src_name))
        dest_path = os.path.normpath(dest_path)

        try:
            target_path = self.make_unique_path(dest_path, src_name)

            if self.copy_mode.get():
                shutil.copy2(src_path, target_path)
            else:
                shutil.move(src_path, target_path)

            if self.current_path and os.path.normpath(self.current_path) == src_path:
                self.current_pil = None
                self.current_photo = None
                self.current_path = None

            if src_path in self.thumb_cache:
                del self.thumb_cache[src_path]
            if src_path in self.gallery_cache:
                del self.gallery_cache[src_path]

            self.image_list.pop(self.current_index)
            if self.current_index >= len(self.image_list) and self.image_list:
                self.current_index -= 1

            self.refresh_gallery_if_open()
            self.display_current_image()

        except Exception as e:
            messagebox.showerror("Error", f"Gagal memproses file:\n{e}")

    def delete_current_file(self):
        if not (0 <= self.current_index < len(self.image_list)):
            return

        src_name = self.image_list[self.current_index]
        src_path = os.path.normpath(os.path.join(self.source_dir, src_name))

        if send2trash is None:
            resp = messagebox.askyesno(
                "send2trash tidak terinstal",
                "Paket 'send2trash' tidak ditemukan.\n"
                "Untuk mengirim file ke Recycle Bin, instal dengan:\n"
                "pip install send2trash\n\n"
                "Klik 'Ya' untuk panduan, 'Tidak' untuk menghapus PERMANEN file ini."
            )
            if resp:
                messagebox.showinfo("Panduan", "Jalankan di terminal:\n\npip install send2trash\n\nLalu jalankan ulang aplikasi.")
                return

            confirm_perm = messagebox.askyesno(
                "Hapus Permanen?",
                f"Anda akan menghapus file PERMANEN:\n{src_name}\n\nLanjutkan?"
            )
            if not confirm_perm:
                return

            try:
                os.remove(src_path)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menghapus file:\n{e}")
                return
        else:
            confirm = messagebox.askyesno(
                "Hapus ke Recycle Bin?",
                f"Kirim file ini ke Recycle Bin?\n\n{src_name}"
            )
            if not confirm:
                return
            try:
                send2trash(src_path)
            except Exception as e:
                messagebox.showerror("Error", f"Gagal mengirim file ke Recycle Bin:\n{e}")
                return

        if self.current_path and os.path.normpath(self.current_path) == src_path:
            self.current_pil = None
            self.current_photo = None
            self.current_path = None
        if src_path in self.thumb_cache:
            del self.thumb_cache[src_path]
        if src_path in self.gallery_cache:
            del self.gallery_cache[src_path]

        try:
            self.image_list.pop(self.current_index)
        except Exception:
            pass

        if self.current_index >= len(self.image_list) and self.image_list:
            self.current_index -= 1

        self.status_label.config(text=f"[INFO] File dihapus: {src_name}")
        self.refresh_gallery_if_open()
        self.display_current_image()

    def make_unique_path(self, dest_dir, filename):
        base, ext = os.path.splitext(filename)
        dest_dir = os.path.abspath(dest_dir)
        if not os.path.exists(dest_dir):
            try:
                os.makedirs(dest_dir, exist_ok=True)
            except Exception:
                pass
        candidate = os.path.join(dest_dir, filename)
        if os.path.exists(candidate):
            n = 2
            while True:
                candidate = os.path.join(dest_dir, f"{base} ({n}){ext}")
                if not os.path.exists(candidate):
                    break
                n += 1
        return candidate

    # ------------------------------ Navigation & Status ------------------------------
    def go_next(self):
        if self.in_gallery_mode:
            if self.current_index < len(self.image_list) - 1:
                self.current_index += 1
                self.close_gallery_mode()
                self.display_current_image()
            return
        if self.current_index < len(self.image_list) - 1:
            self.current_index += 1
            self.display_current_image()

    def go_back(self):
        if self.in_gallery_mode:
            if self.current_index > 0:
                self.current_index -= 1
                self.close_gallery_mode()
                self.display_current_image()
            return
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_image()

    def jump_prev(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_image()

    def jump_next(self):
        if self.current_index < len(self.image_list) - 1:
            self.current_index += 1
            self.display_current_image()

    def update_buttons_state(self):
        has_photos = bool(self.image_list)
        state = "normal" if has_photos else "disabled"
        for d in self.dest_dirs:
            if d.get('button'):
                try:
                    d['button'].config(state=state)
                except Exception:
                    pass
        try:
            self.back_button.config(state="normal" if has_photos and self.current_index > 0 else "disabled")
            self.next_button.config(state="normal" if has_photos and self.current_index < len(self.image_list) - 1 else "disabled")
            self.delete_button.config(state="normal" if has_photos else "disabled")
            self.gallery_button.config(state="normal" if has_photos else "disabled")
        except Exception:
            pass

    def update_status_bar(self):
        mode = "COPY" if self.copy_mode.get() else "MOVE"
        zoom_pct = ""
        if self.current_pil:
            try:
                cw = max(self.image_canvas.winfo_width(), 1)
                ch = max(self.image_canvas.winfo_height(), 1)
                iw, ih = self.current_pil.width, self.current_pil.height
                if self.fit_mode:
                    fit_scale = min(cw / iw, ch / ih)
                    zoom_pct = f" | Zoom: {int(fit_scale*100)}% (Fit)"
                else:
                    zoom_pct = f" | Zoom: {int(self.zoom_scale*100)}%"
            except Exception:
                zoom_pct = f" | Zoom: {int(self.zoom_scale*100)}%"

        if self.image_list and (0 <= self.current_index < len(self.image_list)):
            self.status_label.config(
                text=f"[{mode}]  Foto {self.current_index + 1} / {len(self.image_list)}  |  Nama: {self.image_list[self.current_index]}{zoom_pct}"
            )
        else:
            self.status_label.config(text=f"[{mode}]  Tidak ada foto aktif.{zoom_pct}")


if __name__ == "__main__":
    if CTK_AVAILABLE:
        root = ctk.CTk()
    else:
        root = tk.Tk()
    app = PhotoSorterApp(root)
    root.mainloop()
