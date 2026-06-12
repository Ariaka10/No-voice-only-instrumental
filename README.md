# 🎵 Extracteur Audio IA Pro

Séparez la voix de l'instrumental de vos fichiers MP3 en quelques clics, grâce à l'intelligence artificielle **Demucs**.

---

## ✨ Fonctionnalités

- Séparation voix / instrumental de haute qualité
- Extraction de toutes les pistes séparées (voix, batterie, basse, guitare, reste)
- File d'attente multi-fichiers avec glisser-déposer
- Export MP3 en 320k ou 192k
- Interface simple, thème clair/sombre automatique selon l'heure
- Fonctionne sans connexion internet (après installation)

---

## 🚀 Installation rapide (exe Windows)

1. Téléchargez la dernière version dans la section **[Releases](../../releases)**
2. Extrayez le `.zip`
3. Lancez `ExtracteurAudioPro.exe`

> ⚠️ **Note SmartScreen** : Si Windows affiche une fenêtre bleue au premier lancement, cliquez sur "Informations complémentaires" puis "Exécuter quand même". C'est normal pour un logiciel non signé par une grande entreprise.

> 💡 **Astuce** : Avant d'extraire le zip, faites clic droit → Propriétés → cochez "Débloquer" pour éviter l'alerte.

---

## 🛠️ Prérequis (pour lancer depuis le code source)

- Python 3.9+
- ffmpeg installé et dans le PATH (ou `ffmpeg.exe` à côté du script)

### Installation des dépendances Python

```bash
pip install customtkinter tkinterdnd2 pydub demucs
```

### Lancement

```bash
python extracteur_audio_pro.py
```

---

## 📦 Compiler soi-même l'exe

1. Installez PyInstaller :
```bash
pip install pyinstaller
```

2. Placez `ffmpeg.exe` et `ffprobe.exe` à côté du `.spec`
   → Téléchargement : https://www.gyan.dev/ffmpeg/builds/

3. Compilez :
```bash
pyinstaller extracteur_audio_pro.spec
```

4. L'exe est dans `dist\ExtracteurAudioPro\`

---

## 📋 Utilisation

1. Glissez-déposez vos fichiers MP3 (ou cliquez "Ajouter des fichiers")
2. Choisissez un dossier de destination
3. Sélectionnez le mode d'extraction et la qualité MP3
4. Cliquez "Lancer l'extraction"
5. Une fois terminé, cliquez "Ouvrir le dossier" pour accéder aux fichiers

### Modes disponibles

| Mode | Description |
|------|-------------|
| Instrumental (toutes pistes sauf voix) | Fusionne toutes les pistes sauf la voix en un seul MP3 |
| Toutes les pistes séparées | Exporte chaque piste dans un fichier MP3 distinct |

---

## ⚙️ Technologie

- [Demucs](https://github.com/facebookresearch/demucs) — séparation audio par Facebook Research
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) — interface graphique moderne
- [pydub](https://github.com/jiaaro/pydub) — manipulation audio
- [tkinterdnd2](https://github.com/pmgagne/tkinterdnd2) — glisser-déposer

---

## 📄 Licence

Projet personnel — usage libre et gratuit.
