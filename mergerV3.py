import sys
import logging
import subprocess
import threading
import queue
from pathlib import Path

# --- GUI Libraries ---
import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

# --- Configuration ---
CONFIG = {
    'VIDEO_EXTENSIONS': ['.mp4', '.mkv'],
    'SUBTITLE_EXTENSION': '.srt',
    'MKVMERGE_PATH': 'C:\Program Files\MKVToolNix\mkvmerge.exe',
    'OUTPUT_SUFFIX': '_subbed',
}

# --- Set up live logging to the terminal ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
)

# ====================================================
# Core Logic (Unchanged)
# ====================================================
def analyze_folder(folder_path):
    video_file, subtitle_files = None, []
    try:
        for file in Path(folder_path).iterdir():
            if file.is_file():
                if file.suffix.lower() in CONFIG['VIDEO_EXTENSIONS']:
                    if video_file:
                        logging.warning(f"Multiple videos found in {Path(folder_path).name}, using first found.")
                    else:
                        video_file = file
                elif file.suffix.lower() == CONFIG['SUBTITLE_EXTENSION']:
                    subtitle_files.append(file)
    except Exception as e:
        logging.error(f"Could not analyze folder {folder_path}: {e}")
    return video_file, subtitle_files

def merge_subtitles(video_file, subtitle_files, output_path):
    cmd = [CONFIG['MKVMERGE_PATH'], '-o', str(output_path), str(video_file)]
    for sub_file in subtitle_files:
        cmd.extend(['--language', '0:eng', str(sub_file)])

    logging.info(f"Executing command: {' '.join(cmd)}")
    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo)
        return True, None
    except Exception as e:
        error_msg = getattr(e, 'stderr', str(e))
        logging.error(f"Merge failed: {error_msg}")
        return False, error_msg

# ====================================================
# Main GUI Application (Corrected Structure)
# ====================================================
class SubtitleMergerApp(TkinterDnD.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # --- Theme and Styling ---
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.COLOR_PURPLE = "#8e44ad"
        self.COLOR_SUCCESS = "#2ecc71"
        self.COLOR_ERROR = "#e74c3c"
        self.COLOR_WARNING = "#f39c12"
        self.FONT_FAMILY = ("Segoe UI", 13)

        # --- Window Setup ---
        self.title("Johny's Subtitle Merger")
        self.geometry("850x600")

        # *** THE FIX: Get the correct single color for the current theme ***
        # CustomTkinter returns ('light_color', 'dark_color') for many theme values.
        # We need to pick the one that matches the current appearance mode.
        appearance_mode = ctk.get_appearance_mode()
        fg_color_tuple = ctk.ThemeManager.theme["CTkFrame"]["fg_color"]
        background_color = fg_color_tuple[1] if appearance_mode == "Dark" else fg_color_tuple[0]
        self.config(bg=background_color)

        self.log_queue = queue.Queue()
        self.is_processing = False
        self.folders_to_process = set()

        # --- Drag & Drop Setup ---
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_drop)

        # --- Layout ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Create a main CustomTkinter frame that holds everything ---
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(1, weight=1)

        self.create_widgets()
        self.update_folder_list_view() # Initial call to show placeholder
        self.process_log_queue()

    def create_widgets(self):
        # All widgets are now children of self.main_frame
        top_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        top_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="nsew")
        top_frame.grid_columnconfigure(0, weight=3)
        top_frame.grid_columnconfigure(1, weight=1)

        self.folder_list_frame = ctk.CTkScrollableFrame(top_frame, label_text="Folders to Process", label_font=(self.FONT_FAMILY[0], 14, "bold"))
        self.folder_list_frame.grid(row=0, column=0, padx=(0, 10), pady=0, sticky="nsew")
        self.folder_list_frame.grid_columnconfigure(0, weight=1)

        controls_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=1, sticky="nsew")
        controls_frame.grid_columnconfigure(0, weight=1)

        self.btn_add = ctk.CTkButton(controls_frame, text="Add Folder", font=self.FONT_FAMILY, command=self.browse_folder)
        self.btn_add.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.btn_clear = ctk.CTkButton(controls_frame, text="Clear List", font=self.FONT_FAMILY, command=self.clear_list)
        self.btn_clear.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.btn_start = ctk.CTkButton(controls_frame, text="🚀 Start Merging", font=(self.FONT_FAMILY[0], 14, "bold"),
                                       command=self.start_processing, fg_color=self.COLOR_PURPLE, hover_color="#732d91")
        self.btn_start.grid(row=2, column=0, padx=5, pady=(20, 5), sticky="ew", ipady=10)

        bottom_frame = ctk.CTkFrame(self.main_frame)
        bottom_frame.grid(row=1, column=0, padx=20, pady=(10, 20), sticky="nsew")
        bottom_frame.grid_columnconfigure(1, weight=1)
        bottom_frame.grid_rowconfigure(1, weight=1)

        self.progress_label = ctk.CTkLabel(bottom_frame, text="Status: Ready", font=self.FONT_FAMILY, anchor="w")
        self.progress_label.grid(row=0, column=0, padx=15, pady=(10, 5), sticky="w")
        self.progress_bar = ctk.CTkProgressBar(bottom_frame, progress_color=self.COLOR_PURPLE)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=1, padx=15, pady=(10, 5), sticky="ew")

        self.log_area = ctk.CTkTextbox(bottom_frame, state="disabled", font=self.FONT_FAMILY, activate_scrollbars=True, border_spacing=5)
        self.log_area.grid(row=1, column=0, columnspan=2, padx=15, pady=(5, 15), sticky="nsew")

    def handle_drop(self, event):
        paths = self.tk.splitlist(event.data)
        for path_str in paths:
            path = Path(path_str.strip())
            if path.is_dir():
                self.folders_to_process.add(str(path))
            else:
                self.log_queue.put((f"Skipped non-folder: {path.name}", self.COLOR_WARNING))
        self.update_folder_list_view()

    def browse_folder(self):
        folder = ctk.filedialog.askdirectory(title="Select Folder")
        if folder:
            self.folders_to_process.add(folder)
            self.update_folder_list_view()

    def update_folder_list_view(self):
        for widget in self.folder_list_frame.winfo_children():
            widget.destroy()

        if not self.folders_to_process:
            placeholder = ctk.CTkLabel(self.folder_list_frame, text="Drag folders here...", text_color="gray", anchor="w")
            placeholder.grid(row=0, column=0, padx=5, pady=2, sticky="ew")
            return

        for i, folder in enumerate(sorted(list(self.folders_to_process))):
            label = ctk.CTkLabel(self.folder_list_frame, text=f"📁 {Path(folder).name}", anchor="w", font=self.FONT_FAMILY)
            label.grid(row=i, column=0, padx=5, pady=2, sticky="ew")

    def clear_list(self):
        if self.is_processing: return
        self.folders_to_process.clear()
        self.update_folder_list_view()

    def log_message(self, message, color=None):
        self.log_area.configure(state="normal")
        tag = f"tag_{len(self.log_area.get('1.0', 'end-1c'))}"
        self.log_area.insert("end", message + "\n")
        if color:
            self.log_area.tag_add(tag, f"end-{len(message)+1}c", "end-1c")
            self.log_area.tag_config(tag, foreground=color)
        self.log_area.configure(state="disabled")
        self.log_area.yview_moveto(1.0)

    def process_log_queue(self):
        while not self.log_queue.empty():
            message, color = self.log_queue.get_nowait()
            self.log_message(message, color)
        self.after(100, self.process_log_queue)

    def set_ui_state(self, is_processing):
        self.is_processing = is_processing
        state = "disabled" if is_processing else "normal"
        self.btn_add.configure(state=state)
        self.btn_clear.configure(state=state)
        self.btn_start.configure(state=state)
        self.btn_start.configure(text="🔄 Processing..." if is_processing else "🚀 Start Merging")

    def start_processing(self):
        if not self.folders_to_process:
            self.log_queue.put(("Please add folders to process.", self.COLOR_WARNING))
            return

        self.set_ui_state(True)
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state="disabled")

        self.thread = threading.Thread(target=self.processing_thread, daemon=True)
        self.thread.start()

    def processing_thread(self):
        folders = list(self.folders_to_process)
        total = len(folders)
        success_count = 0

        for i, folder_path in enumerate(folders):
            self.progress_bar.set((i) / total)
            self.progress_label.configure(text=f"Processing {i+1}/{total}: {Path(folder_path).name}")

            self.log_queue.put((f"\n--- Analyzing: {folder_path} ---", None))
            video, subs = analyze_folder(folder_path)

            if not video or not subs:
                msg = "No video or subtitles found."
                self.log_queue.put((f"⚠️ WARNING: {msg}", self.COLOR_WARNING))
                continue

            output = video.with_stem(video.stem + CONFIG['OUTPUT_SUFFIX']).with_suffix('.mkv')
            success, error = merge_subtitles(video, subs, output)

            if success:
                success_count += 1
                self.log_queue.put((f"✅ SUCCESS: Created '{output.name}'", self.COLOR_SUCCESS))
            else:
                self.log_queue.put((f"❌ ERROR: {error}", self.COLOR_ERROR))

        self.progress_bar.set(1.0)
        summary = f"Complete! ✅ Processed {success_count}/{total} folders successfully."
        self.progress_label.configure(text=summary)
        self.log_queue.put(("\n" + summary, self.COLOR_SUCCESS))
        self.set_ui_state(False)


if __name__ == "__main__":
    app = SubtitleMergerApp()
    app.mainloop()