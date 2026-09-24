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

### 1. Download or Clone

- **Quick Download (Recommended):** Download the latest ready-to-use zip from the [Releases](https://github.com/mistu01/Windows-Bangla-Font-Replace/releases) page and extract it.
- **Or via Git:**
  ```bash
  git clone https://github.com/mistu01/Windows-Bangla-Font-Replace.git
  cd Windows-Bangla-Font-Replace
  ```

### 2. Add Your Custom Bengali Font

Place your desired Bengali `.ttf` or `.otf` font file(s) into the `custom_bangla/` folder:

- **Single Font Example:**
  ```text
  custom_bangla/Kalpurush.ttf
  ```
- **Multi-Weight Family Example (Recommended for best results):**
  ```text
  custom_bangla/NotoSerifBengali-Light.ttf
  custom_bangla/NotoSerifBengali-Regular.ttf
  custom_bangla/NotoSerifBengali-Medium.ttf
  custom_bangla/NotoSerifBengali-Bold.ttf
  ```

### 3. Run the Merger

Double-click **`run_bangla_merger.bat`** (or right-click $\rightarrow$ **Run as administrator**).

The script will:
1. Back up your original Windows Nirmala UI and Segoe UI fonts into `backup_bangla/`.
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

1. Double-click **`restore_bangla.bat`** (allow Administrator privileges).
2. The script will restore the original `Nirmala.ttc` and Segoe UI font files from the `backup_bangla/` folder.
3. **Restart your computer**, and Windows default typography will be restored.

Alternatively via command line:
```bash
python replace_bangla.py --restore
```

---

## 🔤 Segoe UI Family & Windows 11 Variable Font Replacer

Want to replace the entire Windows UI typeface (Segoe UI and Windows 11 Segoe UI Variable) with fonts like **Inter**, **Roboto**, **SF Pro**, or **Aptos**?

A dedicated workflow is included for this!

### How It Works:
- **Intelligent Closest-Weight Matching:** Matches your custom fonts to all 8+ Segoe UI faces (Light 300, Semilight 350, Regular 400, SemiBold 600, Bold 700, Black 900, plus Italics).
- **Windows 11 Segoe UI Variable (`SegUIVar.ttf`) Safe Patching:** Uses **OpenType Delta Nullification** to graft custom glyphs into `SegUIVar.ttf` while nullifying deltas for replaced characters. Windows DirectWrite and WinUI 3 (Start Menu, Taskbar, Settings) render your custom font cleanly without crashing or breaking variable font structures.
- **Preserves System Icons:** Preserves Segoe UI's Private Use Area (PUA) glyphs and native system UI icons so File Explorer, Task Manager, and system controls never show missing glyph boxes (`□`).

### How to Use:
1. Place your custom font(s) into **`custom_segoe/`** (e.g. `Inter-Regular.ttf`, `Inter-Bold.ttf`, etc.).
2. Double-click **`replace_segoe_font.bat`** (Run as administrator).
3. Restart your computer.

### How to Restore Segoe UI:
1. Double-click **`restore_segoe_font.bat`** (Run as administrator).
2. Restart your computer.

---

## 📂 Repository Structure

```text
Windows-Bangla-Font-Replace/
├── custom_bangla/            # Place custom Bengali fonts here (.ttf / .otf)
├── custom_segoe/             # Place custom Segoe UI replacement fonts here (.ttf / .otf)
├── backup_bangla/            # Untouched backup of original Nirmala/Segoe fonts (auto-created)
├── backup_segoe/             # Untouched backup of original Segoe family fonts (auto-created)
├── replace_bangla.py         # Nirmala UI Bengali replacer & Segoe patcher
├── replace_segoe.py          # Segoe UI static & variable font replacer
├── replace_bangla_font.bat   # 1-click launcher to replace Bengali fonts
├── replace_segoe_font.bat    # 1-click launcher to replace Segoe UI fonts
├── restore_bangla_font.bat   # 1-click restore for Nirmala fonts
├── restore_segoe_font.bat    # 1-click restore for Segoe UI fonts
├── .gitignore                # Ignores font binaries, temporary builds, and caches
├── LICENSE                   # MIT License
└── README.md                 # Project documentation
```

---

## 🛠️ Command-Line Options

### Windows Bangla Font Replacer (Nirmala UI):
```bash
python replace_bangla.py [OPTIONS]
```
| Option | Description |
| :--- | :--- |
| `-b`, `--bengali-font <path>` | Explicit path to a custom Bengali font file |
| `-r`, `--restore` | Restore original Windows Nirmala and Segoe UI fonts from backup |
| `-h`, `--help` | Show help message and exit |

### Segoe UI Family Replacer:
```bash
python replace_segoe.py [OPTIONS]
```
| Option | Description |
| :--- | :--- |
| `-r`, `--restore` | Restore original Windows Segoe UI and SegUIVar fonts from backup |
| `-h`, `--help` | Show help message and exit |

---

## ⚖️ License

Distributed under the [MIT License](LICENSE). See `LICENSE` for more information.
