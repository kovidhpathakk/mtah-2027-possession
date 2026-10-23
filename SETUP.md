# Team setup

About ten minutes, once per teammate.

## 1. Code

```bash
git clone https://github.com/kovidhpathakk/mtah-2027-possession.git
cd mtah-2027-possession
git config core.hooksPath .githooks          # turns on the data-leak guard
python3 -m venv .venv
source .venv/bin/activate                    # Windows: .venv\Scripts\activate
pip install -r requirements-lock.txt
```

`requirements-lock.txt` pins exact versions so everyone produces byte-identical submission files.

## 2. Data

The data is licensed to enrolled participants and **never goes in git**. Get it from your own
enrolment link, or from the team's restricted Drive folder.

Unpack it into `data/`, keeping these names:

```
data/
├─ tactical/
│  ├─ BAR-ATH_tactical.mp4                    optional, 5.2 GB
│  ├─ BAR-ATH_tactical_atd.txt
│  ├─ BAR-ATH_tactical_atd.xml
│  ├─ BAR-ATH_tactical_homography.csv
│  └─ BAR-ATH_tactical_smart_tagging.xml
└─ broadcast/                                 optional
   ├─ BAR-ATH_broadcast_atd.txt
   ├─ BAR-ATH_broadcast_atd.xml
   └─ BAR-ATH_broadcast_homography.csv
```

The download arrives as Google Drive split zips with a top-level folder; move the files out of it
into the layout above. The video arrives as `BAR-ATH_tactical-001.mp4.zip`; unzip it and rename it
to `BAR-ATH_tactical.mp4`. Low on disk? You only need the tactical files. The broadcast video
(14 GB) is not needed.

## 3. Check your copy

```bash
python scripts/check_data.py --baseline
```

Every line must say PASS or SKIP, ending in `ALL CHECKS PASSED`. The video check needs ffprobe
(`brew install ffmpeg`); without it, it says SKIP.

## 4. Rules that matter

- **Never commit anything from `data/`**, notebook outputs, screenshots or clips. The guard blocks
  the common cases; don't bypass it.
- **Never paste data rows into any AI tool**, Claude included. Share aggregate numbers only. See
  CLAUDE.md.
- **No hand labelling** of this match.
- Work on a branch and open a pull request. `main` must always produce a valid submission.
