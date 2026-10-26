"""Map broadcast frames to tactical frames, and mark which broadcast frames show live play.

The broadcast recording runs on its own counter (DATA.md): 164,488 frames against 199,319, with
cuts and replays, and no mapping is provided. Its clock still runs in real time, so the mapping is
"tactical = broadcast + offset" with the offset constant over long stretches and jumping only
where the broadcast skips time (halftime). Replays and close-ups are inserted pictures, not
skipped time: they match nothing, which makes them detectable -- and broadcasters show replays
after the moments that stop play.

Both ATD files are in the same pitch coordinates, so the offset is found from the tracking alone,
per WINDOW of broadcast time, in three steps:
  coarse    slide the broadcast ball path along the whole tactical one (FFT, RMS distance)
  ball      within +/- REFINE frames of that, the offset with the smallest MEDIAN ball distance;
            the median ignores replays and tracker glitches inside the window
  players   the same with the players: mean distance from each broadcast object to the nearest
            tactical object of the same team, median over frames
Ball and players are separate detections, so two offsets within AGREE frames confirm each other.
The audio (crowd and whistle loudness, scripts/extract_audio.py) is reported as a third check:
the offset with the best correlation within +/- 10 s. It is weak -- the broadcast mix is mostly
commentary -- and sits a few frames off, as two microphones at different distances would.

Each broadcast frame then gets its window's agreed offset if its players fit the tactical ones
there (within LIVE_FIT m), and -1 otherwise (replay, close-up, crowd, studio).

    python scripts/align_broadcast.py

Writes data/derived/broadcast_offsets.npz (offset per broadcast frame, -1 where not live play).
Prints window-level offsets and shares only.
"""

import os
import sys
import wave

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
from games import GAME, GAMES  # noqa: E402

from possession.tracking import PITCH, load_tracking  # noqa: E402

# Params
FPS = GAMES[GAME]["fps"]
WINDOW = 3 * 60 * FPS        # broadcast frames per window
MIN_BALL = 30 * FPS          # frames with a ball needed in a window to trust the coarse match
REFINE = 12                  # frames either side of the coarse offset
AGREE = 1                    # frames: ball and players confirm each other if within this
AUDIO_SEARCH = 10 * FPS      # frames either side of the agreed offset for the audio check
LIVE_FIT = 1.5               # m: a frame whose players sit this close to tactical shows live play
MIN_OBJECTS = 8              # per frame, to judge the fit at all
BANDS = [(300, 3000), (3000, 4500)]  # Hz: crowd, whistle
HIGH_PASS = 10 * FPS         # remove loudness trends slower than this before correlating
DERIVED_DIR = os.path.join(ROOT, "data", "derived")


def coarse_offsets(ball_b, ball_t):
    """Per window: offset with the smallest RMS ball distance over the whole tactical timeline."""
    n = 1 << int(np.ceil(np.log2(len(ball_t) + WINDOW)))
    mg = ~np.isnan(ball_t[:, 0])
    g = np.where(mg[:, None], ball_t, 0.0)
    spectra = {"m": np.fft.rfft(mg.astype(float), n), "g2": np.fft.rfft((g ** 2).sum(1), n),
               "x": np.fft.rfft(g[:, 0], n), "y": np.fft.rfft(g[:, 1], n)}

    def xc(a, spectrum):
        return np.fft.irfft(np.conj(np.fft.rfft(a, n)) * spectrum, n)

    out = []
    for start in range(0, len(ball_b), WINDOW):
        f = ball_b[start:start + WINDOW]
        mf = ~np.isnan(f[:, 0])
        if mf.sum() < MIN_BALL:
            out.append(None)
            continue
        f = np.where(mf[:, None], f, 0.0)
        overlap = xc(mf.astype(float), spectra["m"])
        msd = (xc(mf.astype(float), spectra["g2"]) + xc((f ** 2).sum(1), spectra["m"])
               - 2 * (xc(f[:, 0], spectra["x"]) + xc(f[:, 1], spectra["y"]))) \
            / np.maximum(overlap, 1)
        valid = (overlap >= 0.5 * mf.sum()) & (np.arange(n) < len(ball_t))
        out.append(int(np.argmin(np.where(valid, msd, np.inf))) - start)
    return out


def player_fit(players_b, team_b, players_t, team_t, rows, offset):
    """Per broadcast row: mean distance (m) from each broadcast object to the nearest tactical
    object of the same team at row + offset. NaN where either side has too few objects."""
    target = rows + offset
    ok = (target >= 0) & (target < len(players_t))
    fit = np.full(len(rows), np.nan)
    rows, target = rows[ok], target[ok]
    parts = []
    for code in (0, 1):
        a = players_b[rows][:, team_b == code]
        b = players_t[target][:, team_t == code]
        d = np.linalg.norm(a[:, :, None] - b[:, None], axis=3)
        nearest = np.nanmin(np.where(np.isnan(d), np.inf, d), axis=2)
        nearest[np.isnan(a[:, :, 0]) | np.isinf(nearest)] = np.nan
        parts.append(nearest)
    nearest = np.concatenate(parts, axis=1)
    counted = (~np.isnan(nearest)).sum(axis=1)
    fit[ok] = np.where(counted >= MIN_OBJECTS, np.nanmean(nearest, axis=1), np.nan)
    return fit


def refine(ball_b, ball_t, players, start, coarse):
    """(ball offset, ball median m, players offset, players median m) near the coarse offset."""
    rows = np.arange(start, min(start + WINDOW, len(ball_b)))
    lags = np.arange(coarse - REFINE, coarse + REFINE + 1)
    ball_med, player_med = [], []
    sample = rows[::10]
    for lag in lags:
        r = rows[(rows + lag >= 0) & (rows + lag < len(ball_t))]
        ball_med.append(np.nanmedian(np.linalg.norm(ball_b[r] - ball_t[r + lag], axis=1)))
        player_med.append(np.nanmedian(player_fit(*players, sample, lag)))
    i, j = int(np.nanargmin(ball_med)), int(np.nanargmin(player_med))
    return lags[i], ball_med[i], lags[j], player_med[j]


def loudness(source):
    """Per video frame, log energy in each band, slow trends removed. None if no WAV."""
    path = os.path.join(DERIVED_DIR, "{}_audio_16k.wav".format(source))
    if not os.path.isfile(path):
        return None
    with wave.open(path) as w:
        rate = w.getframerate()
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    per_frame = rate // FPS
    frames = len(samples) // per_frame
    freqs = np.fft.rfftfreq(per_frame, 1 / rate)
    out = np.zeros((frames, len(BANDS)), dtype=np.float32)
    taper = np.hanning(per_frame).astype(np.float32)
    for first in range(0, frames, 20000):
        chunk = samples[first * per_frame:min(frames, first + 20000) * per_frame]
        power = np.abs(np.fft.rfft(chunk.reshape(-1, per_frame).astype(np.float32) * taper,
                                   axis=1)) ** 2
        for k, (low, high) in enumerate(BANDS):
            band = (freqs >= low) & (freqs < high)
            out[first:first + len(power), k] = np.log10(power[:, band].sum(1) + 1e-6)
    kernel = np.ones(HIGH_PASS) / HIGH_PASS
    for k in range(len(BANDS)):
        out[:, k] -= np.convolve(out[:, k], kernel, mode="same")
    return out


def audio_check(loud_b, loud_t, start, offset):
    """(best offset within +/- AUDIO_SEARCH, its correlation) for one window."""
    f = loud_b[start:start + WINDOW].astype(float)
    best = (None, -np.inf)
    for lag in range(offset - AUDIO_SEARCH, offset + AUDIO_SEARCH + 1):
        if start + lag < 0 or start + lag + len(f) > len(loud_t):
            continue
        g = loud_t[start + lag:start + lag + len(f)].astype(float)
        r = np.mean([np.corrcoef(f[:, k], g[:, k])[0, 1] for k in range(f.shape[1])])
        if r > best[1]:
            best = (lag, r)
    return best


if __name__ == '__main__':
    import warnings
    warnings.simplefilter("ignore", RuntimeWarning)
    scale = np.array(PITCH)
    tactical, broadcast = load_tracking("tactical"), load_tracking("broadcast")
    ball_t, ball_b = tactical["ball"] * scale, broadcast["ball"] * scale
    players = (broadcast["players"] * scale, broadcast["team"],
               tactical["players"] * scale, tactical["team"])
    loud_t, loud_b = loudness("tactical"), loudness("broadcast")

    print("{:>11} | {:>7} | {:>7} {:>6} | {:>7} {:>6} | {:>7} {:>5} | {}".format(
        "broadcast", "coarse", "ball", "med m", "players", "med m", "audio", "corr", "agreed"))
    window_offset = []
    for w, coarse in enumerate(coarse_offsets(ball_b, ball_t)):
        start = w * WINDOW
        cells = ["{:>4.0f}-{:<4.0f} min".format(start / FPS / 60,
                                                min(start + WINDOW, len(ball_b)) / FPS / 60)]
        if coarse is None:
            window_offset.append(None)
            print(cells[0] + " | too little ball to match")
            continue
        b_off, b_med, p_off, p_med = refine(ball_b, ball_t, players, start, coarse)
        agreed = p_off if abs(b_off - p_off) <= AGREE else None
        window_offset.append(agreed)
        audio = audio_check(loud_b, loud_t, start, agreed) \
            if agreed is not None and loud_t is not None and loud_b is not None else (None, np.nan)
        print("{} | {:>7} | {:>7} {:>6.2f} | {:>7} {:>6.2f} | {:>7} {:>5.2f} | {}".format(
            cells[0], coarse, b_off, b_med, p_off, p_med,
            "-" if audio[0] is None else "{:+d}".format(audio[0] - agreed), audio[1],
            agreed if agreed is not None else "no"))

    # Offsets come in families, one per stretch of continuous broadcast time (a half). The offset
    # drifts by a frame or two inside a family -- the recording drops the odd frame -- so each
    # frame takes, per family, the offset of the nearest window in that family, and then the
    # family its players fit best. At the halftime splice that picks the right half.
    agreed = [(w, o) for w, o in enumerate(window_offset) if o is not None]
    families = []
    for w, o in sorted(agreed, key=lambda item: item[1]):
        if families and o - families[-1][-1][1] <= 2 * REFINE:
            families[-1].append((w, o))
        else:
            families.append([(w, o)])
    rows = np.arange(len(ball_b))
    window_of_row = rows // WINDOW
    per_family = []
    for family in families:
        windows = np.array([w for w, _ in family])
        values = np.array([o for _, o in family])
        nearest = np.abs(window_of_row[:, None] - windows[None, :]).argmin(axis=1)
        per_family.append(values[nearest])
    fits = np.stack([player_fit(*players, rows, family_offset) for family_offset in per_family])
    best = np.nanargmin(np.where(np.isnan(fits), np.inf, fits), axis=0)
    best_fit = fits[best, rows]
    live = best_fit < LIVE_FIT
    offset = np.full(len(ball_b), -1, dtype=np.int64)
    offset[live] = np.stack(per_family)[best, rows][live]

    os.makedirs(DERIVED_DIR, exist_ok=True)
    np.savez(os.path.join(DERIVED_DIR, "broadcast_offsets.npz"), offset=offset)
    judged = ~np.isnan(best_fit)
    print("\nbroadcast frames: {:,}".format(len(ball_b)))
    print("  live play, mapped to tactical:          {:.1%}".format(live.mean()))
    print("  players in view but not matching (replays and other inserts): {:.1%}".format(
        (judged & ~live).mean()))
    print("  too few players to judge (close-ups, crowd, studio): {:.1%}".format(
        (~judged).mean()))
    for k, family in enumerate(families):
        mapped = live & (best == k)
        if mapped.any():
            first, last = np.flatnonzero(mapped)[[0, -1]]
            print("  offsets {:+,}..{:+,}: {:,} live frames, broadcast {:,}..{:,} -> tactical"
                  " {:,}..{:,}".format(min(o for _, o in family), max(o for _, o in family),
                                       int(mapped.sum()), first, last, first + offset[first],
                                       last + offset[last]))
