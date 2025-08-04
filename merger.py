import sys
import logging
import subprocess
import threading
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QPushButton, QTextEdit, QFileDialog, QLabel,
    QProgressBar, QFrame, QListWidgetItem
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent
import qdarkstyle

# --- Configuration ---
CONFIG = {
    'VIDEO_EXTENSIONS': ['.mp4', '.mkv'],
    'SUBTITLE_EXTENSION': '.srt',
    'MKVMERGE_PATH': 'C:\Program Files\MKVToolNix\mkvmerge.exe', # Ensure this is in your PATH or provide the full path
    'OUTPUT_SUFFIX': '_subbed',
}

# --- Set up live logging to the terminal ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
)

# ====================================================
# Core Logic (MKV Merging)
# ====================================================

def analyze_folder(folder_path):
    """Analyzes a folder to find a video file and subtitle files."""
    video_file = None
    subtitle_files = []
    folder = Path(folder_path)
    try:
        for file in folder.iterdir():
            if file.is_file():
                if file.suffix.lower() in CONFIG['VIDEO_EXTENSIONS']:
                    if video_file:
                        logging.warning(f"Multiple videos in {folder.name}. Using '{video_file.name}'.")
                    else:
                        video_file = file
                elif file.suffix.lower() == CONFIG['SUBTITLE_EXTENSION']:
                    subtitle_files.append(file)
    except FileNotFoundError:
        logging.error(f"Could not access folder: {folder_path}. It may have been moved or deleted.")
        return None, []
    return video_file, subtitle_files


def merge_subtitles(video_file, subtitle_files, output_path):
    """Merges subtitles into the video file using mkvmerge."""
    cmd = [
        CONFIG['MKVMERGE_PATH'],
        '-o', str(output_path),
        str(video_file)
    ]
    for sub_file in subtitle_files:
        cmd.extend(['--language', '0:eng', str(sub_file)])

    logging.info(f"Executing command: {' '.join(cmd)}")

    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        process = subprocess.run(
            cmd, check=True, capture_output=True, text=True, encoding='utf-8', startupinfo=startupinfo
        )
        logging.info(f"SUCCESS: Merged to '{output_path.name}'.")
        if process.stdout:
            logging.info(f"mkvmerge output:\n{process.stdout}")
        return True, None
    except subprocess.CalledProcessError as e:
        error_msg = f"mkvmerge error (Code {e.returncode}): {e.stderr}"
        logging.error(error_msg)
        return False, error_msg
    except FileNotFoundError:
        error_msg = "mkvmerge not found. Ensure MKVToolNix is installed and in your system's PATH."
        logging.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        logging.exception(error_msg)
        return False, error_msg

# ====================================================
# Worker (Handles processing in a separate thread)
# ====================================================

class ProcessingWorker(QObject):
    finished = Signal()
    log_message = Signal(str)
    progress = Signal(int, int, str) # current_folder_index, total_folders, folder_name
    summary = Signal(int, int) # success_count, total_count

    def __init__(self, folders):
        super().__init__()
        self.folders = folders

    def run(self):
        success_count = 0
        total_folders = len(self.folders)

        for i, folder_path in enumerate(self.folders):
            current_folder_index = i + 1
            self.progress.emit(current_folder_index, total_folders, Path(folder_path).name)

            self.log_message.emit(f"\n--- [{current_folder_index}/{total_folders}] Analyzing: {folder_path} ---")

            video_file, subtitle_files = analyze_folder(folder_path)

            if not video_file:
                self.log_message.emit("⚠️ WARNING: No video file found.")
                continue
            if not subtitle_files:
                self.log_message.emit("⚠️ WARNING: No subtitle files (.srt) found.")
                continue

            self.log_message.emit(f"Video: {video_file.name}")
            self.log_message.emit(f"Subtitles: {len(subtitle_files)} file(s) found.")

            output_file = video_file.with_stem(video_file.stem + CONFIG['OUTPUT_SUFFIX']).with_suffix('.mkv')

            success, error = merge_subtitles(video_file, subtitle_files, output_file)

            if success:
                success_count += 1
                self.log_message.emit(f"✅ SUCCESS: Created '{output_file.name}'")
            else:
                self.log_message.emit(f"❌ ERROR: Failed to merge. {error or 'Unknown reason.'}")

        self.summary.emit(success_count, total_folders)
        self.finished.emit()

# ====================================================
# Main GUI Application
# ====================================================

class SubtitleMergerGUI(QMainWindow):
    PLACEHOLDER_TEXT = "Drag and Drop Folders Here"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("✨ Johny's Ultimate Subtitle Merger ✨")
        self.setGeometry(100, 100, 800, 600)
        self.setAcceptDrops(True)

        self.folders_to_process = set()
        self.is_processing = False
        self.thread = None
        self.worker = None

        self.init_ui()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # --- Top Section (Folder List and Controls) ---
        top_layout = QHBoxLayout()

        # Folder List
        self.folder_list = QListWidget()
        self.folder_list.setAlternatingRowColors(True)
        self.folder_list.setAcceptDrops(True) # Accept drops on the widget itself
        self.show_placeholder() # *** FIX: Manually set placeholder
        top_layout.addWidget(self.folder_list, 3)

        # Controls
        control_layout = QVBoxLayout()

        self.btn_add = QPushButton("➕ Add Folder(s)")
        self.btn_add.clicked.connect(self.browse_folders)
        self.btn_add.setMinimumHeight(40)

        self.btn_clear = QPushButton("🗑️ Clear List")
        self.btn_clear.clicked.connect(self.clear_list)
        self.btn_clear.setMinimumHeight(40)

        self.btn_start = QPushButton("🚀 Start Merging")
        self.btn_start.clicked.connect(self.start_processing)
        self.btn_start.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")
        self.btn_start.setMinimumHeight(50)

        control_layout.addWidget(self.btn_add)
        control_layout.addWidget(self.btn_clear)
        control_layout.addStretch()
        control_layout.addWidget(self.btn_start)

        top_layout.addLayout(control_layout, 1)
        self.layout.addLayout(top_layout, 1)

        # --- Progress Bar ---
        self.progress_frame = QFrame()
        self.progress_layout = QVBoxLayout(self.progress_frame)

        self.progress_label = QLabel("Status: Ready")
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)

        self.progress_layout.addWidget(self.progress_label)
        self.progress_layout.addWidget(self.progress_bar)
        self.layout.addWidget(self.progress_frame)

        # --- Log Area ---
        self.log_label = QLabel("Process Log:")
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.layout.addWidget(self.log_label)
        self.layout.addWidget(self.log_area, 1)

    # --- Placeholder Management (THE FIX) ---
    def show_placeholder(self):
        """Manually adds a disabled, styled item to act as a placeholder."""
        self.folder_list.clear()
        placeholder_item = QListWidgetItem(self.PLACEHOLDER_TEXT)
        placeholder_item.setFlags(placeholder_item.flags() & ~Qt.ItemIsSelectable & ~Qt.ItemIsEnabled)
        placeholder_item.setForeground(QColor('gray'))
        self.folder_list.addItem(placeholder_item)

    def remove_placeholder_if_exists(self):
        """Removes the placeholder item if it is currently displayed."""
        if self.folder_list.count() == 1 and self.folder_list.item(0).text() == self.PLACEHOLDER_TEXT:
            self.folder_list.clear()

    # --- Drag and Drop Handlers ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        if self.is_processing:
            self.log_message("⚠️ Please wait for the current process to finish.")
            return

        urls = event.mimeData().urls()
        self.remove_placeholder_if_exists()
        for url in urls:
            path = Path(url.toLocalFile())
            if path.is_dir():
                self.add_folder(str(path))
            else:
                self.log_message(f"Skipped (Not a folder): {path.name}")
        self.update_list_view()

    # --- UI Functions ---
    def add_folder(self, folder_path):
        self.folders_to_process.add(folder_path)
        logging.info(f"Added folder to queue: {folder_path}")

    def update_list_view(self):
        # We only update if there's something to show, otherwise show placeholder
        if not self.folders_to_process:
            self.show_placeholder()
            return
            
        self.folder_list.clear()
        for folder in sorted(list(self.folders_to_process)):
            self.folder_list.addItem(folder)

    def browse_folders(self):
        if self.is_processing:
            self.log_message("⚠️ Cannot add folders while processing.")
            return

        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self.remove_placeholder_if_exists()
            self.add_folder(folder)
            self.update_list_view()

    def clear_list(self):
        if self.is_processing:
            self.log_message("⚠️ Cannot clear list while processing.")
            return
        self.folders_to_process.clear()
        self.update_list_view() # This will now call show_placeholder automatically
        logging.info("Cleared folder list.")

    def log_message(self, message):
        self.log_area.append(message)
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def set_ui_state(self, processing):
        self.is_processing = processing
        self.btn_start.setDisabled(processing)
        self.btn_add.setDisabled(processing)
        self.btn_clear.setDisabled(processing)
        self.folder_list.setDisabled(processing)

        if processing:
            self.btn_start.setText("🔄 Processing...")
            self.btn_start.setStyleSheet("font-weight: bold; background-color: #FFA500; color: black;")
        else:
            self.btn_start.setText("🚀 Start Merging")
            self.btn_start.setStyleSheet("font-weight: bold; background-color: #4CAF50; color: white;")

    # --- Processing Logic ---
    def start_processing(self):
        if not self.folders_to_process:
            self.log_message("⚠️ No folders added. Please add folders to process.")
            return

        self.log_area.clear()
        self.set_ui_state(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Status: Initializing...")

        self.thread = QThread()
        self.worker = ProcessingWorker(list(self.folders_to_process))
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.worker.log_message.connect(self.log_message)
        self.worker.progress.connect(self.update_progress)
        self.worker.summary.connect(self.processing_finished)

        self.thread.start()

    def update_progress(self, current, total, folder_name):
        percentage = int((current / total) * 100)
        self.progress_label.setText(f"Processing {current}/{total}: {folder_name}")

        self.animation = QPropertyAnimation(self.progress_bar, b"value")
        self.animation.setDuration(300)
        self.animation.setStartValue(self.progress_bar.value())
        self.animation.setEndValue(percentage)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.start()

    def processing_finished(self, success_count, total_count):
        self.set_ui_state(False)
        self.progress_bar.setValue(100)
        self.progress_label.setText(f"Status: Complete! ✅ Processed {success_count}/{total_count} successfully.")
        self.log_message("\n====================\n🎉 Process Complete!\n====================")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Apply QDarkStyle for a modern dark theme
    try:
        import qdarkstyle
        app.setStyleSheet(qdarkstyle.load_stylesheet(qt_api='pyside6'))
    except ImportError:
        logging.warning("qdarkstyle not found. GUI will have a default system appearance.")
        logging.warning("Install it with: pip install qdarkstyle")


    window = SubtitleMergerGUI()
    window.show()
    sys.exit(app.exec())
