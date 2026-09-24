# Windows Bangla Font Replace (Nirmala UI Bengali Font Merger)

Seamlessly replace default Windows Bengali rendering fonts (**Nirmala UI** & **Segoe UI**) with your favorite Bengali fonts (*Kalpurush*, *SolaimanLipi*, *Noto Sans Bengali*, *Noto Serif Bengali*, etc.) across all Windows UI applications and web browsers, while preserving Latin, Devanagari, and system font metrics.

---

## 📖 The Problem

On Windows 10 and 11, the operating system uses **Nirmala UI** to render Bengali text across native system interfaces, File Explorer, settings, notifications, and web fallbacks. 

However:
- **Awkward Rendering:** Nirmala UI’s Bengali glyphs and conjunctive characters (*যুক্তবর্ণ*) often look unnatural or disproportionate compared to popular modern Bengali typefaces.
- **Segoe UI Conflicts:** Segoe UI embeds Bengali digits (`U+09E6`–`U+09EF`) and currency symbols (`৳`), which can conflict or override custom fonts with mismatched sizes.
- **Locked System Files:** Windows system fonts are locked in memory by the OS kernel and protected by Windows File Protection / TrustedInstaller, making direct file replacement difficult and prone to corruption.

---

## ✨ Features

- ⚡ **Automatic System Font Discovery:** Automatically locates `Nirmala.ttc` and Segoe UI fonts across standard font directories (`C:\Windows\Fonts`) and the WinSxS component store.
- 🛡️ **Zero-Risk Safe Backups:** Creates backups of original untouched Windows system fonts before making any modifications.
- 🎯 **Intelligent Font-Weight Matching:** Detects OpenType font weight classes (`usWeightClass` 100–900) to pair your custom font faces with Windows font weights:
  - **Nirmala UI Semilight** (Weight: 350) $\rightarrow$ *Light* / *Regular*
  - **Nirmala UI Regular** (Weight: 400) $\rightarrow$ *Regular* / *Normal* / *Book*
  - **Nirmala UI Bold** (Weight: 700) $\rightarrow$ *Bold* / *SemiBold* / *Black*
- 🧩 **Preserves All Other Scripts:** Only replaces Bengali glyphs (`U+0980`–`U+09FF`) and related OpenType shaping tables (`GSUB`/`GPOS`). English (Latin), Devanagari, Tamil, Telugu, and other languages remain untouched.
- 🔢 **Segoe UI Bengali Conflict Stripping:** Strips overlapping Bengali characters from Segoe UI so your chosen font renders consistently everywhere.
- 🔄 **Safe Win32 Delay-Until-Reboot:** Employs the Windows API `MoveFileEx` (`MOVEFILE_DELAY_UNTIL_REBOOT`) to safely replace in-memory system fonts during reboot without causing permission errors or file lock issues.
- ↩️ **1-Click Restore:** Includes a one-click rollback script to restore official Microsoft default fonts at any time.

---

## 📋 Requirements

- **Operating System:** Windows 10 or Windows 11 (64-bit or 32-bit)
- **Python:** [Python 3.8+](https://www.python.org/downloads/) (Make sure *"Add python.exe to PATH"* is checked during installation)
- **Dependencies:** `fonttools` (will be installed automatically on first run if not present)
- **Privileges:** Administrator access (batch launchers will prompt for UAC automatically)

---

## 🚀 Getting Started

### 1. Clone or Download

Clone this repository or download and extract the ZIP file:
```bash
git clone https://github.com/mistu01/Windows-Bangla-Font-Replace.git
cd Windows-Bangla-Font-Replace
```

### 2. Add Your Custom Bengali Font

Place your desired Bengali `.ttf` or `.otf` font file(s) into the `custom_font/` folder:

- **Single Font Example:**
  ```text
  custom_font/Kalpurush.ttf
  ```
- **Multi-Weight Family Example (Recommended for best results):**
  ```text
  custom_font/NotoSerifBengali-Light.ttf
  custom_font/NotoSerifBengali-Regular.ttf
  custom_font/NotoSerifBengali-Medium.ttf
  custom_font/NotoSerifBengali-Bold.ttf
  ```

### 3. Run the Merger

Double-click **`run_merger.bat`** (or right-click $\rightarrow$ **Run as administrator**).

The script will:
1. Back up your original Windows Nirmala UI and Segoe UI fonts into `backup/`.
2. Extract the faces from `Nirmala.ttc`.
3. Patch Segoe UI to remove conflicting Bengali digits.
4. Merge your custom Bengali glyphs into Nirmala UI.
5. Recompile the TrueType Collection (`Nirmala.ttc`).
6. Schedule system font replacement on the next reboot.

### 4. Restart Your Computer

Once the script finishes, **restart your PC** to allow Windows to load the new merged fonts.

---

## 🔄 How to Restore Original Windows Fonts

If you ever wish to revert back to default Microsoft fonts:

1. Double-click **`restore_original.bat`** (allow Administrator privileges).
2. The script will restore the original `Nirmala.ttc` and Segoe UI font files from the `backup/` folder.
3. **Restart your computer**, and Windows default typography will be restored.

Alternatively via command line:
```bash
python merge_nirmala.py --restore
```

---

## 📂 Repository Structure

```text
Windows-Bangla-Font-Replace/
├── custom_font/              # Place your custom .ttf / .otf fonts here
├── backup/                   # Untouched backup of original Windows system fonts (auto-created)
├── extracted_ttf/            # Extracted font faces (auto-created)
├── merged_ttf/               # Merged intermediate font faces (auto-created)
├── output/                   # Final compiled Nirmala.ttc and patched Segoe UI (auto-created)
├── merge_nirmala.py          # Core Python merger and Windows system patcher
├── run_merger.bat            # 1-click Administrator launcher for merging fonts
├── restore_original.bat      # 1-click Administrator launcher for restoring defaults
├── .gitignore                # Ignores font binaries, temporary builds, and caches
├── LICENSE                   # MIT License
└── README.md                 # Project documentation
```

---

## 🛠️ Command-Line Options

You can also run the Python script directly from an elevated terminal:

```bash
python merge_nirmala.py [OPTIONS]
```

| Option | Description |
| :--- | :--- |
| `-f`, `--font <path>` | Explicit path to a custom font file or directory |
| `-r`, `--restore` | Restore original Windows Nirmala and Segoe UI fonts from backup |
| `-h`, `--help` | Show help message and exit |

---

## ⚖️ License

Distributed under the [MIT License](LICENSE). See `LICENSE` for more information.
