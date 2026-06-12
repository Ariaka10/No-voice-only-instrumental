# extracteur_audio_pro.spec
# Fichier de configuration PyInstaller
#
# UTILISATION :
#   py -m PyInstaller extracteur_audio_pro.spec
#
# AVANT de compiler :
#   1. py -m pip install pyinstaller
#   2. Place ffmpeg.exe et ffprobe.exe dans le même dossier que ce .spec
#      → https://www.gyan.dev/ffmpeg/builds/ (ffmpeg-release-essentials.zip)
#      → Extraire ffmpeg.exe et ffprobe.exe du dossier bin\
# ---------------------------------------------------------------------

import sys
import os
import pathlib
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

SCRIPT_PATH = 'extracteur_audio_pro.py'

# ── ffmpeg embarqué ──────────────────────────────────────────────────
binaries = []

for nom in ['ffmpeg.exe', 'ffprobe.exe']:
    chemin = os.path.join('.', nom)
    if os.path.isfile(chemin):
        binaries.append((chemin, '.'))
        print(f"   ✓ {nom} embarqué")
    else:
        print(f"⚠  {nom} introuvable — à placer à côté du .spec")

# ── Données des packages ─────────────────────────────────────────────
datas = []

# tkinterdnd2 — DLL tkdnd pour le drag & drop
datas += collect_data_files('tkinterdnd2')

# customtkinter — thèmes et assets
try:
    datas += collect_data_files('customtkinter')
except Exception:
    pass

# ── tkinter — DLLs et données TCL/TK ────────────────────────────────
python_dir = os.path.dirname(sys.executable)
dlls_dir   = os.path.join(python_dir, 'DLLs')
tcl_dir    = os.path.join(python_dir, 'tcl')

for dll_name in ['_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll']:
    chemin_dll = os.path.join(dlls_dir, dll_name)
    if os.path.isfile(chemin_dll):
        binaries.append((chemin_dll, '.'))

if os.path.isdir(tcl_dir):
    for sous_dossier in os.listdir(tcl_dir):
        chemin_sd = os.path.join(tcl_dir, sous_dossier)
        if os.path.isdir(chemin_sd):
            datas.append((chemin_sd, os.path.join('tcl', sous_dossier)))

# ── Imports cachés ───────────────────────────────────────────────────
hiddenimports = [
    # UI
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinterdnd2',
    'tkinterdnd2.TkinterDnD',
    'customtkinter',

    # Audio
    'pydub',
    'pydub.utils',

    # Demucs
    'demucs',
    'demucs.pretrained',
    'demucs.apply',

    # Divers
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'pkg_resources',
]

# ── Hook runtime — ffmpeg dans le PATH dès le démarrage ─────────────
runtime_hook_path = '_hook_ffmpeg.py'
with open(runtime_hook_path, 'w', encoding='utf-8') as fh:
    fh.write(
        "import os, sys\n"
        "if getattr(sys, 'frozen', False):\n"
        "    os.environ['PATH'] = sys._MEIPASS + os.pathsep + os.environ.get('PATH', '')\n"
    )

# ── Configuration principale ─────────────────────────────────────────
a = Analysis(
    [SCRIPT_PATH],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[runtime_hook_path],
    excludes=[
        # Spleeter et sa ménagerie — plus utilisés
        'spleeter',
        'tensorflow',
        'keras',
        'jax',
        'jaxlib',
        # Autres inutiles
        'matplotlib',
        'IPython',
        'notebook',
        'jupyter',
        'pytest',
        'sphinx',
        'yt_dlp',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ExtracteurAudioPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=None,
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='ExtracteurAudioPro',
)
