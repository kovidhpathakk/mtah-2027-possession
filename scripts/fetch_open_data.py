"""Download the open datasets from OTHER matches that we set thresholds on, and verify every byte.

The rules allow labelled data from other matches in any amount, provided the organisers can access
it (RULES.md; issues #8 and #10). Fetching it with a script, pinned to exact files and checked
against the checksums the hosts publish, is what lets them get the same bytes we used.

  dfl      Bassek et al. 2025, Scientific Data: 7 Bundesliga matches, 25 fps positions with a
           per-frame BallStatus (alive/dead) and BallPossession (home/away), plus official events.
           CC BY 4.0. figshare article 28196177, version 1. Checked by the MD5 figshare publishes.
  metrica  Metrica Sports sample data, Game 3: the same EPTS format as our match, with events.
           No formal licence; the README asks that public use acknowledges the source. Pinned to
           commit e706dd5 and checked by git's own blob hash.

    python scripts/fetch_open_data.py                 # both, ~2.7 GB
    python scripts/fetch_open_data.py --only metrica

Files land in data/external/<dataset>/ (gitignored, like all of data/). A file already there with
the right hash is not downloaded again. These are data files only: nothing in them is executed.
"""

import argparse
import hashlib
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Params
EXTERNAL_DIR = os.path.join(ROOT, "data", "external")
CHUNK = 1 << 20
FIGSHARE = "https://ndownloader.figshare.com/files/{}"
METRICA_COMMIT = "e706dd506b360d69d9d123d5b8026e7294b13996"
METRICA = "https://raw.githubusercontent.com/metrica-sports/sample-data/{}/{}"

# (figshare file id, name, size, md5)
DFL_FILES = [
    (51643472, "DFL_02_01_matchinformation_DFL-COM-000001_DFL-MAT-J03WN1.xml", 11722, "37b0f85588c0acfb995fe633c7ac2e0d"),
    (51643475, "DFL_02_01_matchinformation_DFL-COM-000001_DFL-MAT-J03WMX.xml", 11930, "bc5d5b21dbcf36aa30f4cd0428309f6b"),
    (51643478, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WOH.xml", 11745, "b9710781d400dd812f62b0a6e3d7bce8"),
    (51643490, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WR9.xml", 11823, "5e2d580d3d8ed97e32959de90d04992b"),
    (51643487, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WPY.xml", 11922, "65a4568e4f374af94d3c1015cbc7c4f5"),
    (51643484, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WQQ.xml", 11932, "5979209af316a914ce57347d0633df6c"),
    (51643481, "DFL_02_01_matchinformation_DFL-COM-000002_DFL-MAT-J03WOY.xml", 11952, "7b021e577fca917a63111d55cc29ae5b"),
    (51643493, "DFL_03_02_events_raw_DFL-COM-000001_DFL-MAT-J03WMX.xml", 776578, "2d88e180a1f63c7e4157feb980fc7255"),
    (51643496, "DFL_03_02_events_raw_DFL-COM-000001_DFL-MAT-J03WN1.xml", 612114, "83e8ed7ea8e8ebbbdc61f61ac3534008"),
    (51643499, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WOH.xml", 635747, "ab66e51512f39d06f49f27dd3b4c2f40"),
    (51643502, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WOY.xml", 683018, "64b1be01d6ff6848168efebd56f344b9"),
    (51643505, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WPY.xml", 698898, "f68482441d38723d69f244f896482803"),
    (51643508, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WQQ.xml", 732186, "b7e9d82af4034539d802319be6c57776"),
    (51643511, "DFL_03_02_events_raw_DFL-COM-000002_DFL-MAT-J03WR9.xml", 681050, "c13bc5efa5eca4a022cc678210b87d5f"),
    (51643514, "DFL_04_03_positions_raw_observed_DFL-COM-000001_DFL-MAT-J03WMX.xml", 418524833, "e4273a2adf5dbd9d4ec42def2f01905c"),
    (51643517, "DFL_04_03_positions_raw_observed_DFL-COM-000001_DFL-MAT-J03WN1.xml", 391722803, "bacb2f609c1d1b0bfc906f6b9d4109f2"),
    (51643520, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WOH.xml", 348945715, "3efff25a86a61768e7d253b4bba137a3"),
    (51643523, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WOY.xml", 362567859, "4e1063e0a0ae499920cf68ac1aa3ab4e"),
    (51643526, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WPY.xml", 371688499, "e56ff1336a334f8da51110fbe7cab764"),
    (51643529, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WQQ.xml", 356219423, "9105bad987191d3c3c362c1fce9a4fcd"),
    (51643532, "DFL_04_03_positions_raw_observed_DFL-COM-000002_DFL-MAT-J03WR9.xml", 372934140, "e060bb7d7a5a3bfbd15bbf9bc631024d"),
]

# (path in the repository, size, git blob sha1)
METRICA_FILES = [
    ("data/Sample_Game_3/Sample_Game_3_metadata.xml", 81806, "74b55a80f6aeeb8f8df7fd26e4b3a94e2cc1738d"),
    ("data/Sample_Game_3/Sample_Game_3_tracking.txt", 53443115, "7062b7ceaa44d53345a4625b8f447efc74895b1d"),
    ("data/Sample_Game_3/Sample_Game_3_events.json", 1709486, "992b4cb502f0b0bc1244174f014f3f7ecb6d38ef"),
    ("documentation/events-definitions.pdf", 802916, "5f0d279e6b5d3a8028727c129190245b4c5e13e8"),
]


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def git_blob_sha1(path):
    """The hash git gives a file: sha1 of 'blob <size>\\0' followed by the bytes."""
    digest = hashlib.sha1("blob {}\0".format(os.path.getsize(path)).encode())
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url, path, size, check):
    """Download url to path unless a verified copy is there. True if the file is good."""
    if os.path.isfile(path) and os.path.getsize(path) == size and check(path):
        print("  ok    {}".format(os.path.basename(path)))
        return True
    partial = path + ".part"
    with urllib.request.urlopen(url) as response, open(partial, "wb") as out:
        for block in iter(lambda: response.read(CHUNK), b""):
            out.write(block)
    if os.path.getsize(partial) != size or not check(partial):
        print("  BAD   {} (size or hash differs; left as .part)".format(os.path.basename(path)))
        return False
    os.replace(partial, path)
    print("  got   {} ({:.1f} MB)".format(os.path.basename(path), size / 1e6))
    return True


def fetch_dfl():
    folder = os.path.join(EXTERNAL_DIR, "dfl")
    os.makedirs(folder, exist_ok=True)
    print("dfl -> {}".format(os.path.relpath(folder, ROOT)))
    return all(fetch(FIGSHARE.format(file_id), os.path.join(folder, name), size,
                     lambda path, expected=digest: md5(path) == expected)
               for file_id, name, size, digest in DFL_FILES)


def fetch_metrica():
    folder = os.path.join(EXTERNAL_DIR, "metrica")
    os.makedirs(folder, exist_ok=True)
    print("metrica @ {} -> {}".format(METRICA_COMMIT[:7], os.path.relpath(folder, ROOT)))
    return all(fetch(METRICA.format(METRICA_COMMIT, repo_path),
                     os.path.join(folder, os.path.basename(repo_path)), size,
                     lambda path, expected=digest: git_blob_sha1(path) == expected)
               for repo_path, size, digest in METRICA_FILES)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", choices=("dfl", "metrica"))
    args = parser.parse_args()
    good = True
    if args.only in (None, "metrica"):
        good &= fetch_metrica()
    if args.only in (None, "dfl"):
        good &= fetch_dfl()
    sys.exit(0 if good else 1)
