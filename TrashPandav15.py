import os
import json
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, Scrollbar
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image, ExifTags, ImageTk
import pillow_heif
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import shutil
import webbrowser

# --- Optional Dependency Imports ---
try:
    import cairosvg
except ImportError:
    cairosvg = None
try:
    import rawpy
except ImportError:
    rawpy = None

# Register the HEIC opener with Pillow
pillow_heif.register_heif_opener()

class MediaConverterApp(TkinterDnD.Tk):
    """
    An optimized GUI application for viewing metadata and converting media files.
    Refactored into a class for better structure, performance, and maintainability.
    """
    def __init__(self):
        super().__init__()
        self.style = ttk.Style(theme="cosmo")
        self.withdraw()

        # --- Application Info ---
        self.APP_NAME = "Trash Panda"
        self.APP_VERSION = "2.0.0" # Updated version
        self.APP_AUTHOR = "fl6ki"
        self.DONATION_LINK = "https://buymeacoffee.com/fl6ki" # Updated link

        # --- Application State ---
        self.selected_files = []
        self.ffmpeg_path = shutil.which('ffmpeg')
        self.ffprobe_path = shutil.which('ffprobe')
        self.current_theme = tk.StringVar(value="light")

        # --- Tkinter UI Variables ---
        self.remove_metadata_var = tk.BooleanVar(value=True)
        self.resize_images_var = tk.BooleanVar(value=False)
        self.save_format_var = tk.StringVar(value="JPEG")

        # --- UI Widget References ---
        self.file_listbox = None
        self.image_preview_label = None
        self.progress_bar = None
        self.progress_label = None
        self.status_bar_label = None
        self.action_buttons = {}

        self.show_splash()

    def show_splash(self):
        """Displays a splash screen while the app initializes."""
        splash = tk.Toplevel(self)
        splash.overrideredirect(True)
        
        splash_width, splash_height = 400, 400
        screen_width, screen_height = self.winfo_screenwidth(), self.winfo_screenheight()
        x = (screen_width // 2) - (splash_width // 2)
        y = (screen_height // 2) - (splash_height // 2)
        splash.geometry(f'{splash_width}x{splash_height}+{x}+{y}')
        splash.configure(bg="#ffffff")

        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            image_path = os.path.join(base_path, "panda.jpg")
            if os.path.exists(image_path):
                splash_img = Image.open(image_path).resize((280, 280), Image.Resampling.LANCZOS)
                self.splash_img_tk = ImageTk.PhotoImage(splash_img)
                img_label = tk.Label(splash, image=self.splash_img_tk, bg="#ffffff")
                img_label.pack(pady=(20, 10))
            else:
                tk.Label(splash, text="🐼", font=("Segoe UI Emoji", 120), bg="#ffffff").pack(pady=(50, 10))
        except Exception as e:
            print(f"Splash image error: {e}")
            tk.Label(splash, text="🐼", font=("Segoe UI Emoji", 120), bg="#ffffff").pack(pady=(50, 10))

        tk.Label(splash, text=f"{self.APP_NAME} is waking up...", font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#333333").pack()
        
        splash.after(1200, lambda: [splash.destroy(), self.run_main_app()])

    def run_main_app(self):
        """Initializes and displays the main application window."""
        self.deiconify()
        self.setup_main_window()
        if not self.ffmpeg_path or not self.ffprobe_path:
            messagebox.showwarning("Dependency Not Found",
                                   "FFmpeg/FFprobe not found. Video features will be disabled. "
                                   "Please install FFmpeg and ensure it's in your system's PATH.")

    def setup_main_window(self):
        """Creates all the widgets for the main application window."""
        self.title(f"{self.APP_NAME} Media Converter")
        self.geometry("850x750") # Increased width for preview panel

        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_path, 'new_panda.ico')
            if os.path.exists(icon_path): self.iconbitmap(icon_path)
        except Exception as e:
            print(f"Could not load window icon: {e}")

        # --- Top Header ---
        header_frame = ttk.Frame(self, padding=(10, 5))
        header_frame.pack(fill="x")
        ttk.Label(header_frame, text="Theme:").pack(side="left")
        theme_toggle = ttk.Checkbutton(header_frame, text="Light / Dark", style="switch.TCheckbutton", command=self.toggle_theme)
        theme_toggle.pack(side="left", padx=5)

        # --- Main Paned Window (for resizable panels) ---
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.pack(fill="both", expand=True, padx=10, pady=5)

        # --- LEFT PANEL (File List & Controls) ---
        left_panel = ttk.Frame(main_pane, padding=5)
        main_pane.add(left_panel, weight=1)

        list_frame = ttk.Labelframe(left_panel, text="Files", padding=10)
        list_frame.pack(fill="both", expand=True)
        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, width=40, height=12, bg="#f8f9fa", fg="#343a40", selectbackground="#0d6efd", selectforeground="white", font=("Segoe UI", 10), borderwidth=0, highlightthickness=0)
        self.file_listbox.pack(pady=5, fill="both", expand=True)
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)
        self.file_listbox.bind("<Delete>", self.delete_selected_files)
        self.file_listbox.bind("<BackSpace>", self.delete_selected_files)

        button_frame = ttk.Frame(left_panel)
        button_frame.pack(pady=5, fill="x")
        button_frame.columnconfigure((0, 1), weight=1)
        self.action_buttons['select'] = ttk.Button(button_frame, text="Select Files", style="primary.TButton", command=self.select_files)
        self.action_buttons['select'].grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.action_buttons['clear'] = ttk.Button(button_frame, text="Clear List", style="warning.TButton", command=self.clear_file_list)
        self.action_buttons['clear'].grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        self.action_buttons['about'] = ttk.Button(button_frame, text="About", style="secondary.TButton", command=self.show_about_window)
        self.action_buttons['about'].grid(row=1, column=0, columnspan=2, padx=2, pady=2, sticky="ew")

        # --- RIGHT PANEL (Image Preview) ---
        right_panel = ttk.Frame(main_pane, padding=5)
        main_pane.add(right_panel, weight=2)
        preview_lf = ttk.Labelframe(right_panel, text="Image Preview", padding=10)
        preview_lf.pack(fill="both", expand=True)
        self.image_preview_label = ttk.Label(preview_lf, text="Select an image to preview", anchor="center")
        self.image_preview_label.pack(fill="both", expand=True)

        # --- BOTTOM SECTION (Options & Conversion) ---
        options_lf = ttk.Labelframe(self, text="Processing Options", padding=15)
        options_lf.pack(pady=5, padx=10, fill="x")
        ttk.Checkbutton(options_lf, text="Remove Metadata (Images & Videos)", variable=self.remove_metadata_var, style="primary.TCheckbutton").pack(anchor="w", pady=2)
        ttk.Checkbutton(options_lf, text="Shrink Images to 50%", variable=self.resize_images_var, style="primary.TCheckbutton").pack(anchor="w", pady=2)

        convert_lf = ttk.Labelframe(self, text="Start Conversion", padding=15)
        convert_lf.pack(pady=5, padx=10, fill="x")
        convert_lf.columnconfigure((0, 1, 2), weight=1)
        self.action_buttons['convert_img'] = ttk.Button(convert_lf, text="Convert Images", style="success.TButton", command=self.start_image_conversion)
        self.action_buttons['convert_img'].grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self.action_buttons['convert_vid'] = ttk.Button(convert_lf, text="Process Videos", style="success.TButton", command=self.start_video_processing)
        self.action_buttons['convert_vid'].grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.action_buttons['metadata'] = ttk.Button(convert_lf, text="Show Metadata", style="info.TButton", command=self.show_metadata)
        self.action_buttons['metadata'].grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        self.progress_bar = ttk.Progressbar(self, orient="horizontal", length=400, mode="determinate")
        self.progress_bar.pack(pady=5, padx=10, fill="x")
        self.progress_label = ttk.Label(self, text="", font=("Segoe UI", 10))
        self.progress_label.pack(pady=2, padx=10)
        self.status_bar_label = ttk.Label(self, text="0 files selected", anchor="w", padding=5, style="secondary.TLabel")
        self.status_bar_label.pack(side="bottom", fill="x")

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.drop)

    def toggle_theme(self):
        """Switches between light ('cosmo') and dark ('darkly') themes."""
        if self.style.theme.name == "cosmo":
            self.style.theme_use("darkly")
            self.file_listbox.config(bg="#343a40", fg="white")
        else:
            self.style.theme_use("cosmo")
            self.file_listbox.config(bg="#f8f9fa", fg="#343a40")

    def show_about_window(self):
        """Displays the about window with app info and links."""
        about = tk.Toplevel(self)
        about.title(f"About {self.APP_NAME}")
        about.geometry("450x250")
        about.transient(self)
        about.resizable(False, False)

        ttk.Label(about, text=self.APP_NAME, font=("Segoe UI", 20, "bold")).pack(pady=(15, 5))
        ttk.Label(about, text=f"Version {self.APP_VERSION}", style="secondary.TLabel").pack()
        ttk.Label(about, text=f"Created by {self.APP_AUTHOR}").pack(pady=(0, 20))
        ttk.Label(about, text="A super simple tool for batch processing media files.").pack() # Updated description
        link_label = ttk.Label(about, text="Support the developer", style="info.TLabel", cursor="hand2")
        link_label.pack(pady=10)
        link_label.bind("<Button-1>", lambda e: webbrowser.open(self.DONATION_LINK))
        close_button = ttk.Button(about, text="Close", command=about.destroy, style="primary.TButton")
        close_button.pack(pady=15)

    # ==================================
    # == File Handling & UI Methods
    # ==================================
    def on_file_select(self, event=None):
        """Triggers when a file is selected in the listbox."""
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            return
        
        file_path = self.selected_files[selected_indices[0]]
        
        # Start a thread to load the image preview to avoid UI freeze
        threading.Thread(target=self.update_image_preview, args=(file_path,), daemon=True).start()

    def update_image_preview(self, file_path):
        """Loads and displays an image thumbnail in the preview panel."""
        try:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ('.jpg', '.jpeg', '.png', '.heic', '.webp', '.bmp', '.gif', '.tiff'):
                self.after(0, self.image_preview_label.config, {"text": "No preview available\n(not a standard image)", "image": ""})
                return

            # Open image and create a thumbnail
            img = Image.open(file_path)
            
            # Get preview panel size for accurate thumbnailing
            preview_width = self.image_preview_label.winfo_width()
            preview_height = self.image_preview_label.winfo_height()
            if preview_width < 50 or preview_height < 50: # Handle initial zero-size case
                preview_width, preview_height = 400, 400

            img.thumbnail((preview_width - 20, preview_height - 20), Image.Resampling.LANCZOS)
            
            photo_image = ImageTk.PhotoImage(img)

            # Schedule UI update on main thread
            def set_image():
                self.image_preview_label.config(image=photo_image, text="")
                self.image_preview_label.image = photo_image # Keep a reference!
            
            self.after(0, set_image)

        except Exception as e:
            print(f"Error creating preview for {file_path}: {e}")
            self.after(0, self.image_preview_label.config, {"text": "Preview failed to load", "image": ""})

    def update_file_listbox(self):
        self.file_listbox.delete(0, tk.END)
        for f in self.selected_files:
            self.file_listbox.insert(tk.END, os.path.basename(f))
        count = len(self.selected_files)
        self.status_bar_label.config(text=f"{count} file{'s' if count != 1 else ''} selected")

    def select_files(self):
        files = filedialog.askopenfilenames()
        if files:
            current_files = set(self.selected_files)
            for f in files:
                if f not in current_files:
                    self.selected_files.append(f)
            self.update_file_listbox()

    def clear_file_list(self):
        self.selected_files.clear()
        self.update_file_listbox()

    def drop(self, event):
        files = self.tk.splitlist(event.data)
        current_files = set(self.selected_files)
        for f in files:
            if f not in current_files:
                self.selected_files.append(f)
        self.update_file_listbox()

    def delete_selected_files(self, event=None):
        selected_indices = self.file_listbox.curselection()
        for i in reversed(selected_indices):
            del self.selected_files[i]
        self.update_file_listbox()

    def set_ui_state(self, is_enabled):
        state = "normal" if is_enabled else "disabled"
        for button in self.action_buttons.values():
            button.config(state=state)

    # ==================================
    # == Metadata Reading
    # ==================================
    def show_metadata(self):
        if not self.selected_files:
            messagebox.showerror("Error", "Please select files first.")
            return
        
        def metadata_worker():
            combined_text = ""
            for f in self.selected_files:
                ext = os.path.splitext(f)[1].lower()
                if ext in ('.mp4', '.mov', '.avi', '.mkv'):
                    combined_text += self.read_video_metadata(f)
                else:
                    combined_text += self.read_photo_metadata(f)
                combined_text += "\n" + "="*40 + "\n\n"
            
            self.after(0, self.show_text_popup, "Metadata Viewer", combined_text)

        threading.Thread(target=metadata_worker, daemon=True).start()

    def read_photo_metadata(self, image_path):
        try:
            ext = os.path.splitext(image_path)[1].lower()
            if ext in ('.raf', '.cr2', '.cr3', '.arw', '.nef', '.dng') and rawpy:
                with rawpy.imread(image_path) as raw:
                    return f"File: {os.path.basename(image_path)}\n  Camera: {raw.camera_manufacturer} {raw.model}\n  Timestamp: {raw.timestamp}"
            
            img = Image.open(image_path)
            exif_data = img.getexif()
            text_content = f"File: {os.path.basename(image_path)}\n"
            if exif_data:
                for tag_id, value in exif_data.items():
                    tag = ExifTags.TAGS.get(tag_id, tag_id)
                    if isinstance(value, bytes): value = value.decode(errors='replace')
                    text_content += f"  {tag}: {value}\n"
            else:
                text_content += "  No EXIF metadata found."
            return text_content
        except Exception as e:
            return f"Error reading {os.path.basename(image_path)}: {e}"

    def read_video_metadata(self, video_path):
        if not self.ffprobe_path:
            return f"File: {os.path.basename(video_path)}\n  ffprobe not found."
        try:
            cmd = [self.ffprobe_path, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", video_path]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return json.dumps(json.loads(result.stdout), indent=4)
        except Exception as e:
            return f"Error reading video metadata for {os.path.basename(video_path)}: {e}"

    def show_text_popup(self, title, content):
        popup = tk.Toplevel(self)
        popup.title(title)
        popup.geometry("800x600")
        text_area = tk.Text(popup, wrap="word", bg="#2b2b2b", fg="white", font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(popup, command=text_area.yview, style="light.Vertical.TScrollbar")
        text_area.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        text_area.pack(side="left", fill="both", expand=True)
        text_area.insert("1.0", content)
        text_area.config(state="disabled")

    # ==================================
    # == Conversion Logic (Threaded)
    # ==================================
    def start_image_conversion(self):
        if not self.selected_files:
            messagebox.showerror("Error", "Please select files to convert.")
            return
        
        format_popup = tk.Toplevel(self)
        format_popup.title("Choose Format")
        format_popup.geometry("300x150")
        ttk.Label(format_popup, text="Select output format:").pack(pady=10)
        
        has_svg = any(f.lower().endswith(".svg") for f in self.selected_files)
        
        jpeg_radio = ttk.Radiobutton(format_popup, text="JPEG", variable=self.save_format_var, value="JPEG")
        jpeg_radio.pack(pady=5)
        png_radio = ttk.Radiobutton(format_popup, text="PNG", variable=self.save_format_var, value="PNG")
        png_radio.pack(pady=5)
        
        if has_svg:
            self.save_format_var.set("PNG")
            jpeg_radio.config(state="disabled")
            if not cairosvg:
                messagebox.showerror("Missing Dependency", "Please install 'cairosvg' to convert SVG files.\n(pip install cairosvg)")
                format_popup.destroy()
                return

        def on_confirm():
            format_popup.destroy()
            output_folder = filedialog.askdirectory(title="Select Output Folder")
            if output_folder:
                threading.Thread(target=self.image_conversion_worker, args=(output_folder,), daemon=True).start()
        
        ttk.Button(format_popup, text="Confirm & Continue", command=on_confirm, style="primary.TButton").pack(pady=10)

    def image_conversion_worker(self, output_folder):
        self.after(0, self.set_ui_state, False)
        skipped_files = []
        total_files = len(self.selected_files)
        target_format = self.save_format_var.get()

        for idx, path in enumerate(self.selected_files):
            filename = os.path.basename(path)
            self.after(0, self.progress_label.config, {"text": f"Processing {idx + 1}/{total_files}: {filename}"})
            self.after(0, self.progress_bar.config, {"value": idx})

            try:
                ext = os.path.splitext(path)[1].lower()
                out_filename = os.path.splitext(filename)[0] + "_processed." + target_format.lower()
                out_path = os.path.join(output_folder, out_filename)

                if ext == '.svg':
                    if target_format == "PNG" and cairosvg:
                        cairosvg.svg2png(url=path, write_to=out_path)
                        continue
                    else:
                        raise ValueError("SVG can only be converted to PNG.")

                if ext == '.heic':
                    heif_file = pillow_heif.read_heif(path)
                    img = Image.frombytes(heif_file.mode, heif_file.size, heif_file.data, "raw")
                else:
                    img = Image.open(path)

                if self.remove_metadata_var.get():
                    pixel_data = list(img.getdata())
                    img = Image.new(img.mode, img.size)
                    img.putdata(pixel_data)
                
                if self.resize_images_var.get():
                    w, h = img.size
                    img = img.resize((w // 2, h // 2), Image.Resampling.LANCZOS)

                if target_format == "JPEG":
                    if img.mode in ('RGBA', 'P'): img = img.convert('RGB')
                    img.save(out_path, 'JPEG', quality=95) # Fixed quality
                else:
                    img.save(out_path, 'PNG')

            except Exception as e:
                print(f"Error converting {filename}: {e}")
                skipped_files.append(filename)

        self.after(0, self.progress_bar.config, {"value": total_files})
        self.after(0, self.on_conversion_complete, skipped_files, "Images")

    def start_video_processing(self):
        if not self.ffmpeg_path:
            messagebox.showerror("Error", "FFmpeg is not installed or not in PATH.")
            return
        if not self.selected_files:
            messagebox.showerror("Error", "Please select video files to process.")
            return
        output_folder = filedialog.askdirectory(title="Select Output Folder")
        if output_folder:
            threading.Thread(target=self.video_processing_worker, args=(output_folder,), daemon=True).start()

    def video_processing_worker(self, output_folder):
        self.after(0, self.set_ui_state, False)
        skipped_files = []
        total_files = len(self.selected_files)

        for idx, path in enumerate(self.selected_files):
            filename = os.path.basename(path)
            ext = os.path.splitext(path)[1].lower()
            if ext not in ('.mp4', '.mov', '.avi', '.mkv'):
                continue

            self.after(0, self.progress_label.config, {"text": f"Processing {idx + 1}/{total_files}: {filename}"})
            self.after(0, self.progress_bar.config, {"value": idx})
            
            out_filename = os.path.splitext(filename)[0] + "_processed.mp4"
            out_path = os.path.join(output_folder, out_filename)

            try:
                cmd = [self.ffmpeg_path, '-i', path, '-y']
                if self.remove_metadata_var.get():
                    cmd.extend(['-map_metadata', '-1'])
                cmd.extend(['-c:v', 'copy', '-c:a', 'copy', out_path])
                
                subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            except Exception as e:
                print(f"Error processing video {filename}: {e}")
                skipped_files.append(filename)
        
        self.after(0, self.progress_bar.config, {"value": total_files})
        self.after(0, self.on_conversion_complete, skipped_files, "Videos")

    def on_conversion_complete(self, skipped_files, file_type):
        self.set_ui_state(True)
        self.progress_label.config(text="Done!")
        if skipped_files:
            message = f"Completed, but some {file_type.lower()} were skipped:\n\n{', '.join(skipped_files)}"
            messagebox.showwarning("Completed with Errors", message)
        else:
            messagebox.showinfo("Completed", f"All {file_type.lower()} processed successfully!")


if __name__ == "__main__":
    app = MediaConverterApp()
    app.mainloop()
