import os
import sys
import shutil
import threading
import time
import unicodedata
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from pydub import AudioSegment


# ---------------------------------------------------------------------------
# Patch global subprocess — pas de fenêtre console sur Windows
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    _orig_popen = subprocess.Popen.__init__
    def _popen_no_window(self, *args, **kwargs):
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] |= subprocess.CREATE_NO_WINDOW
        _orig_popen(self, *args, **kwargs)
    subprocess.Popen.__init__ = _popen_no_window


# ---------------------------------------------------------------------------
# Détection / configuration automatique de ffmpeg
# ---------------------------------------------------------------------------
def _configurer_ffmpeg() -> None:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    for chemin in [
        os.path.join(base, "ffmpeg.exe"),
        os.path.join(base, "ffmpeg", "ffmpeg.exe"),
        os.path.join(base, "bin", "ffmpeg.exe"),
    ]:
        if os.path.isfile(chemin):
            AudioSegment.converter = chemin
            AudioSegment.ffprobe   = os.path.join(os.path.dirname(chemin), "ffprobe.exe")
            return

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        AudioSegment.ffprobe   = shutil.which("ffprobe") or ffmpeg_path
        return

    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            AudioSegment.converter = ffmpeg_path
            AudioSegment.ffprobe   = shutil.which("ffprobe") or ffmpeg_path
            return
    except ImportError:
        pass

    raise RuntimeError(
        "ffmpeg est introuvable.\n\n"
        "Placez ffmpeg.exe et ffprobe.exe dans le même dossier que l'application.\n"
        "Téléchargement : https://ffmpeg.org/download.html"
    )


try:
    _configurer_ffmpeg()
    _FFMPEG_ERREUR = None
except RuntimeError as _e:
    _FFMPEG_ERREUR = str(_e)


# ---------------------------------------------------------------------------
# Thème automatique
# ---------------------------------------------------------------------------
def detecter_theme() -> str:
    heure = time.localtime().tm_hour
    return "Dark" if (heure >= 20 or heure < 7) else "Light"

ctk.set_appearance_mode(detecter_theme())
ctk.set_default_color_theme("blue")


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
MODES_DEMUCS = {
    "Instrumental (toutes pistes sauf voix)": "instrumental",
    "Toutes les pistes séparées":             "separees",
}

QUALITES_MP3 = {
    "320k — Qualité maximale": "320k",
    "192k — Standard / Léger": "192k",
}

PISTES_VOIX = {"vocals"}

NOMS_PISTES = {
    "vocals":  "Voix",
    "drums":   "Batterie",
    "bass":    "Basse",
    "piano":   "Piano",
    "other":   "Reste",
    "guitar":  "Guitare",
}

COULEURS_STATUT = {
    "attente":  ("gray",    "⏸  En attente"),
    "en_cours": ("#3498db", "⏳  En cours…"),
    "succes":   ("#2ecc71", "✅  Terminé"),
    "erreur":   ("#e74c3c", "❌  Erreur"),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def nettoyer_nom_fichier(nom: str) -> str:
    """Supprime accents et caractères interdits Windows."""
    nom = unicodedata.normalize('NFKD', nom)
    nom = nom.encode('ascii', 'ignore').decode('ascii')
    for car in r'\/:*?"<>|':
        nom = nom.replace(car, '_')
    nom = ' '.join(nom.split()).strip('. ')
    return nom or 'sans_titre'


def ouvrir_dossier_natif(chemin: str) -> None:
    if sys.platform == "win32":
        os.startfile(chemin)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", chemin])
    else:
        subprocess.Popen(["xdg-open", chemin])


def chemin_mp3_unique(dossier: str, nom_base: str, suffixe: str) -> str:
    chemin = os.path.join(dossier, f"{nom_base} ({suffixe}).mp3")
    compteur = 1
    while os.path.exists(chemin):
        chemin = os.path.join(dossier, f"{nom_base} ({suffixe}) ({compteur}).mp3")
        compteur += 1
    return chemin


# ---------------------------------------------------------------------------
# Ligne de file d'attente
# ---------------------------------------------------------------------------
class LigneFichier(ctk.CTkFrame):

    def __init__(self, parent, chemin: str, on_supprimer, **kwargs):
        super().__init__(parent, corner_radius=8, **kwargs)
        self.chemin = chemin
        self.on_supprimer = on_supprimer
        self.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self, text="🎵", font=ctk.CTkFont(size=16), width=30).grid(
            row=0, column=0, padx=(10, 6), pady=8)

        self.lbl_nom = ctk.CTkLabel(
            self, text=os.path.basename(chemin),
            font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_nom.grid(row=0, column=1, sticky="ew", pady=8)

        self.lbl_statut = ctk.CTkLabel(
            self, text="⏸  En attente",
            font=ctk.CTkFont(size=11), text_color="gray",
            width=120, anchor="e")
        self.lbl_statut.grid(row=0, column=2, padx=(6, 6), pady=8)

        self.btn_sup = ctk.CTkButton(
            self, text="✕", width=28, height=28,
            fg_color="transparent",
            hover_color=("gray80", "gray30"),
            text_color=("gray40", "gray60"),
            command=lambda: self.on_supprimer(self))
        self.btn_sup.grid(row=0, column=3, padx=(0, 8), pady=8)

    def set_statut(self, cle: str):
        couleur, texte = COULEURS_STATUT[cle]
        self.lbl_statut.configure(text=texte, text_color=couleur)
        self.btn_sup.configure(state="disabled" if cle == "en_cours" else "normal")


# ---------------------------------------------------------------------------
# Application principale
# ---------------------------------------------------------------------------
class ExtracteurAudioProApp(ctk.CTk, TkinterDnD.DnDWrapper):

    def __init__(self) -> None:
        super().__init__()
        self.TkdndVersion = TkinterDnD._require(self)
        self.title("Extracteur Audio IA Pro")
        self.geometry("680x700")
        self.resizable(False, False)
        self.dernier_dossier_cree = ""
        self._lignes: list[LigneFichier] = []
        self._construire_interface()
        if _FFMPEG_ERREUR:
            self.after(200, lambda: messagebox.showerror("ffmpeg introuvable", _FFMPEG_ERREUR))

    # ------------------------------------------------------------------
    # Interface
    # ------------------------------------------------------------------
    def _construire_interface(self) -> None:

        # En-tête
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 0))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="🎵  Extracteur Audio IA Pro",
            font=ctk.CTkFont(size=22, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header, text="Séparation voix / instrumental — propulsé par Demucs",
            font=ctk.CTkFont(size=12), text_color="gray", anchor="w",
        ).grid(row=1, column=0, sticky="w")

        ctk.CTkButton(
            header, text="☀ / ☾", width=80, height=28,
            fg_color="transparent", border_width=1,
            text_color=("gray30", "gray70"),
            command=self._basculer_theme,
        ).grid(row=0, column=1, rowspan=2, sticky="e")

        # Carte principale
        carte = ctk.CTkFrame(self, corner_radius=16)
        carte.pack(fill="both", expand=True, padx=24, pady=16)
        carte.grid_columnconfigure(0, weight=1)
        carte.grid_rowconfigure(3, weight=1)

        # Zone de dépôt
        self.zone_depot = ctk.CTkFrame(
            carte, corner_radius=12,
            border_width=2, border_color=("gray70", "gray40"), height=80)
        self.zone_depot.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 8))
        self.zone_depot.grid_propagate(False)
        self.zone_depot.grid_columnconfigure(0, weight=1)
        self.zone_depot.grid_rowconfigure(0, weight=1)

        ctk.CTkLabel(
            self.zone_depot,
            text="🎵  Glissez-déposez vos fichiers MP3 ici",
            font=ctk.CTkFont(size=13), text_color="gray",
        ).grid(row=0, column=0)

        self.zone_depot.drop_target_register(DND_FILES)
        self.zone_depot.dnd_bind("<<Drop>>", self._gestion_dnd)

        ctk.CTkButton(
            carte, text="➕  Ajouter des fichiers",
            height=34, width=180, command=self._choisir_fichiers,
        ).grid(row=1, column=0, sticky="w", padx=16, pady=(0, 8))

        ctk.CTkLabel(
            carte, text="File d'attente",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(0, 4))

        self.scroll_file = ctk.CTkScrollableFrame(carte, corner_radius=8, height=240)
        self.scroll_file.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 12))
        self.scroll_file.grid_columnconfigure(0, weight=1)

        self.lbl_file_vide = ctk.CTkLabel(
            self.scroll_file, text="Aucun fichier dans la file d'attente.",
            text_color="gray", font=ctk.CTkFont(size=12))
        self.lbl_file_vide.grid(row=0, column=0, pady=20)

        ctk.CTkFrame(carte, height=1, fg_color="gray40").grid(
            row=4, column=0, sticky="ew", padx=16, pady=(0, 12))

        # Destination
        ctk.CTkLabel(carte, text="Dossier de destination",
                     font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=5, column=0, sticky="w", padx=16, pady=(0, 4))

        row_dossier = ctk.CTkFrame(carte, fg_color="transparent")
        row_dossier.grid(row=6, column=0, sticky="ew", padx=16, pady=(0, 12))
        row_dossier.grid_columnconfigure(0, weight=1)

        self.var_dossier = ctk.StringVar()
        ctk.CTkEntry(
            row_dossier, textvariable=self.var_dossier,
            placeholder_text="Choisissez le dossier de destination…",
            height=36, state="readonly",
        ).grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkButton(
            row_dossier, text="Parcourir…", width=110, height=36,
            command=self._choisir_dossier,
        ).grid(row=0, column=1)

        # Options (mode + qualité — plus de sélecteur de moteur)
        options = ctk.CTkFrame(carte, fg_color="transparent")
        options.grid(row=7, column=0, sticky="ew", padx=16, pady=(0, 8))
        options.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(options, text="Mode d'extraction",
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        self.combo_mode = ctk.CTkComboBox(
            options, values=list(MODES_DEMUCS.keys()), width=280)
        self.combo_mode.grid(row=1, column=0, sticky="ew", padx=(0, 10))
        self.combo_mode.set(list(MODES_DEMUCS.keys())[0])

        ctk.CTkLabel(options, text="Qualité MP3",
                     font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", pady=(0, 4))
        self.combo_qualite = ctk.CTkComboBox(
            options, values=list(QUALITES_MP3.keys()), width=200)
        self.combo_qualite.grid(row=1, column=1, sticky="ew")
        self.combo_qualite.set(list(QUALITES_MP3.keys())[0])

        # Progression
        self.lbl_progression = ctk.CTkLabel(
            carte, text="", font=ctk.CTkFont(size=11), text_color="gray", anchor="w")
        self.lbl_progression.grid(row=8, column=0, sticky="w", padx=16, pady=(8, 2))

        self.progress = ctk.CTkProgressBar(carte, height=8)
        self.progress.grid(row=9, column=0, sticky="ew", padx=16, pady=(0, 4))
        self.progress.set(0)

        self.lbl_statut = ctk.CTkLabel(
            carte, text="Prêt.",
            font=ctk.CTkFont(size=11), text_color="gray", anchor="w")
        self.lbl_statut.grid(row=10, column=0, sticky="w", padx=16, pady=(0, 8))

        # Boutons
        row_boutons = ctk.CTkFrame(carte, fg_color="transparent")
        row_boutons.grid(row=11, column=0, sticky="ew", padx=16, pady=(0, 16))
        row_boutons.grid_columnconfigure((0, 1, 2), weight=1)

        self.btn_lancer = ctk.CTkButton(
            row_boutons, text="⚙  Lancer l'extraction",
            height=42, font=ctk.CTkFont(size=14, weight="bold"),
            command=self.demarrer_traitement,
        )
        self.btn_lancer.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.btn_vider = ctk.CTkButton(
            row_boutons, text="🗑  Vider la liste", height=42,
            fg_color=("gray80", "gray25"), hover_color=("gray70", "gray20"),
            text_color=("gray20", "gray80"), command=self._vider_file,
        )
        self.btn_vider.grid(row=0, column=1, sticky="ew", padx=(0, 6))

        self.btn_ouvrir = ctk.CTkButton(
            row_boutons, text="📁  Ouvrir le dossier", height=42,
            fg_color=("gray80", "gray25"), hover_color=("gray70", "gray20"),
            text_color=("gray20", "gray80"), state="disabled",
            command=self.ouvrir_explorateur,
        )
        self.btn_ouvrir.grid(row=0, column=2, sticky="ew")

    # ------------------------------------------------------------------
    # Gestion file d'attente
    # ------------------------------------------------------------------
    def _ajouter_fichier(self, chemin: str) -> None:
        if any(l.chemin == chemin for l in self._lignes):
            return
        if not chemin.lower().endswith(".mp3"):
            messagebox.showerror("Format invalide",
                f"Fichier ignoré (pas MP3) :\n{os.path.basename(chemin)}")
            return
        ligne = LigneFichier(
            self.scroll_file, chemin,
            on_supprimer=self._supprimer_ligne,
            fg_color=("gray90", "gray20"))
        ligne.grid(row=len(self._lignes), column=0, sticky="ew", pady=(0, 4))
        self._lignes.append(ligne)
        self._maj_file_vide()

    def _supprimer_ligne(self, ligne: LigneFichier) -> None:
        ligne.destroy()
        self._lignes.remove(ligne)
        for i, l in enumerate(self._lignes):
            l.grid(row=i, column=0, sticky="ew", pady=(0, 4))
        self._maj_file_vide()

    def _vider_file(self) -> None:
        for l in self._lignes[:]:
            l.destroy()
        self._lignes.clear()
        self._maj_file_vide()

    def _maj_file_vide(self) -> None:
        if self._lignes:
            self.lbl_file_vide.grid_remove()
        else:
            self.lbl_file_vide.grid(row=0, column=0, pady=20)

    # ------------------------------------------------------------------
    # Callbacks UI
    # ------------------------------------------------------------------
    def _gestion_dnd(self, event) -> None:
        import re
        raw = event.data.strip()
        chemins = re.findall(r'\{([^}]+)\}', raw) + re.sub(r'\{[^}]+\}', '', raw).split() \
            if raw.startswith("{") else raw.split()
        for chemin in chemins:
            chemin = chemin.strip('"').strip("'")
            if chemin:
                self._ajouter_fichier(chemin)

    def _choisir_fichiers(self) -> None:
        for f in filedialog.askopenfilenames(
                title="Choisir des fichiers MP3",
                filetypes=[("Fichiers MP3", "*.mp3")]):
            self._ajouter_fichier(f)

    def _choisir_dossier(self) -> None:
        d = filedialog.askdirectory(title="Choisir le dossier de destination")
        if d:
            self.var_dossier.set(d)

    def ouvrir_explorateur(self) -> None:
        if self.dernier_dossier_cree and os.path.exists(self.dernier_dossier_cree):
            ouvrir_dossier_natif(self.dernier_dossier_cree)

    def _basculer_theme(self) -> None:
        ctk.set_appearance_mode(
            "Light" if ctk.get_appearance_mode() == "Dark" else "Dark")

    def _set_statut(self, texte: str, couleur: str = "gray") -> None:
        self.lbl_statut.configure(text=texte, text_color=couleur)

    def _update_statut(self, texte: str) -> None:
        self.after(0, lambda: self._set_statut(texte, "gray"))

    # ------------------------------------------------------------------
    # Lancement
    # ------------------------------------------------------------------
    def demarrer_traitement(self) -> None:
        if _FFMPEG_ERREUR:
            messagebox.showerror("ffmpeg introuvable", _FFMPEG_ERREUR); return
        if not self._lignes:
            self._set_statut("⚠  Aucun fichier dans la file d'attente.", "#e67e22"); return
        if not self.var_dossier.get():
            self._set_statut("⚠  Aucun dossier de destination.", "#e67e22"); return

        self._file_en_cours = list(self._lignes)
        self.dernier_dossier_cree = ""
        self.progress.set(0)
        self.lbl_progression.configure(text="")
        self._ui_en_cours(True)
        threading.Thread(target=self._pipeline_file, daemon=True).start()

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------
    def _pipeline_file(self) -> None:
        total     = len(self._file_en_cours)
        nb_succes = 0
        nb_erreur = 0
        dossier   = self.var_dossier.get()

        for i, ligne in enumerate(self._file_en_cours):
            self.after(0, lambda l=ligne: l.set_statut("en_cours"))
            self.after(0, lambda i=i, t=total: self._maj_progression(i, t))

            try:
                nom_base = nettoyer_nom_fichier(
                    os.path.splitext(os.path.basename(ligne.chemin))[0])[:80]
                bitrate    = QUALITES_MP3[self.combo_qualite.get()]
                mode_label = self.combo_mode.get()

                self._separer_demucs(
                    ligne.chemin, dossier, nom_base,
                    MODES_DEMUCS[mode_label], bitrate)

                self.after(0, lambda l=ligne: l.set_statut("succes"))
                nb_succes += 1
                self.dernier_dossier_cree = dossier

            except Exception as exc:
                self.after(0, lambda l=ligne: l.set_statut("erreur"))
                nb_erreur += 1
                self._update_statut(f"❌  Erreur : {os.path.basename(ligne.chemin)} — {exc}")

        self.after(0, lambda: self._fin_pipeline(total, nb_succes, nb_erreur))

    def _maj_progression(self, index: int, total: int) -> None:
        self.progress.set(index / total)
        self.lbl_progression.configure(text=f"Traitement {index + 1} / {total}…")

    # ------------------------------------------------------------------
    # Séparation Demucs
    # ------------------------------------------------------------------
    def _separer_demucs(self, input_path, dossier_sortie, nom_base, mode, bitrate):
        self._update_statut(f"⏳  Demucs — {os.path.basename(input_path)}…")

        # Dans un exe PyInstaller sys.executable = l'exe lui-même → boucle infinie.
        # On cherche le vrai python.exe dans le PATH.
        if getattr(sys, "frozen", False):
            python_exe = shutil.which("python") or shutil.which("python3")
            if not python_exe:
                raise RuntimeError(
                    "Python est introuvable dans le PATH.\n"
                    "Installez Python et cochez 'Add to PATH' lors de l'installation.")
        else:
            python_exe = sys.executable

        cmd = [
            python_exe, "-m", "demucs",
            "--out", dossier_sortie,
            "--mp3", "--mp3-bitrate", bitrate.replace("k", ""),
            input_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Demucs a échoué :\n{result.stderr[-400:]}")

        # Localise le dossier de sortie Demucs
        dossier_demucs = os.path.join(dossier_sortie, "htdemucs", nom_base)
        if not os.path.exists(dossier_demucs):
            for sd in os.listdir(dossier_sortie):
                candidat = os.path.join(dossier_sortie, sd, nom_base)
                if os.path.isdir(candidat):
                    dossier_demucs = candidat
                    break
            else:
                raise FileNotFoundError("Dossier de sortie Demucs introuvable.")

        pistes = {
            os.path.splitext(f)[0]: os.path.join(dossier_demucs, f)
            for f in os.listdir(dossier_demucs) if f.endswith(".mp3")
        }

        if mode == "instrumental":
            self._update_statut("🎼  Fusion des pistes instrumentales…")
            a_mixer = [p for n, p in pistes.items() if n not in PISTES_VOIX]
            if not a_mixer:
                raise RuntimeError("Aucune piste instrumentale trouvée.")
            mix = AudioSegment.from_mp3(a_mixer[0])
            for p in a_mixer[1:]:
                mix = mix.overlay(AudioSegment.from_mp3(p))
            mix.export(
                chemin_mp3_unique(dossier_sortie, nom_base, "Instrumental"),
                format="mp3", bitrate=bitrate)
        else:
            for nom_piste, src in pistes.items():
                libelle = NOMS_PISTES.get(nom_piste, nom_piste.capitalize())
                self._update_statut(f"💾  Export : {libelle}…")
                shutil.copy2(src, chemin_mp3_unique(dossier_sortie, nom_base, libelle))

        shutil.rmtree(os.path.dirname(dossier_demucs), ignore_errors=True)

    # ------------------------------------------------------------------
    # Helpers UI
    # ------------------------------------------------------------------
    def _ui_en_cours(self, actif: bool) -> None:
        etat = "disabled" if actif else "normal"
        self.btn_lancer.configure(state=etat)
        self.btn_vider.configure(state=etat)
        self.combo_mode.configure(state=etat)
        self.combo_qualite.configure(state=etat)
        self.btn_ouvrir.configure(state="disabled")

    def _fin_pipeline(self, total: int, nb_succes: int, nb_erreur: int) -> None:
        self._ui_en_cours(False)
        self.progress.set(1)
        if nb_erreur == 0:
            self._set_statut(
                f"✅  {nb_succes}/{total} fichiers traités avec succès.", "#2ecc71")
            self.btn_ouvrir.configure(state="normal")
            messagebox.showinfo("Terminé !",
                f"{nb_succes} MP3 disponibles dans le dossier de destination.")
        else:
            self._set_statut(
                f"⚠  {nb_succes} succès, {nb_erreur} erreur(s) sur {total} fichiers.",
                "#e67e22")
            if nb_succes > 0:
                self.btn_ouvrir.configure(state="normal")
            messagebox.showwarning("Traitement terminé avec erreurs",
                f"{nb_succes} fichier(s) traité(s).\n"
                f"{nb_erreur} fichier(s) en erreur — vérifiez les statuts dans la liste.")


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app = ExtracteurAudioProApp()
    app.mainloop()
