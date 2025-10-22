# Subtitle Merger GUI ✨

A sleek, modern tool to easily merge subtitle files (`.srt`) into your video files (`.mp4`, `.mkv`). Built with Python and a beautiful CustomTkinter GUI.

![gui](https://raw.githubusercontent.com/JohnySir/Subtitle-Merger-GUI/refs/heads/V3/images/v3.png "gui") 

## 🚀 Features

* **Modern Dark UI** 🎨: A beautiful and easy-to-use interface.

* **Drag & Drop** 📁: Simply drag your folders into the app.

* **Batch Processing** ⚡: Merge subtitles for multiple folders at once.

* **Live Logging** 📝: See real-time progress and status updates.

* **Cross-Platform** 🖥️: Works on Windows, macOS, and Linux.

## 🛠️ Installation

1. **Get the code:**

`git clone` as usual


2. **Install dependencies:**
This script requires a few Python libraries. Install them with pip:

`pip install customtkinter tkinterdnd2`


3. **Install MKVToolNix:**
This tool relies on `mkvmerge`, which is part of the [MKVToolNix](https://mkvtoolnix.download/downloads.html) suite.

* Download and install it from the official website.

* **Important:** Make sure to add MKVToolNix to your system's PATH during installation so the script can find `mkvmerge`.

## ▶️ How to Run

Once everything is installed, just run the script from your terminal:

`python merger.py`


Then, simply drag the folders containing your video and subtitle files into the application window and click "Start Merging"!

