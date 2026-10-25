# Experiment 004 results

Status: completed October 24, 2026. Rules and the two motion sources are documented in `README.md`.

**No measured public gain.** The position-based version changes 500 frames (20 seconds) outside
the public sample. Its accuracy on those changes is unknown.

| Version | Public spellF1 | Public macroF1 | Full-match possessions | Full-match D share |
|---|---:|---:|---:|---:|
| Official Smooth50 | 0.3256 | 0.6207 | 594 | 32.3% |
| Experiment 003 | 0.3349 | 0.6522 | 555 | 35.5% |
| 004: provided ball speed | 0.3349 | 0.6522 | 555 | 35.5% |
| 004: motion from positions | 0.3349 | 0.6522 | 547 | 35.8% |

## What we learned

The first attempt found no qualifying restarts. An input audit showed that the supplied ball
speed is missing in 91.3% of frames where the ball is detected. Of 59 set-piece tags, only six
contained a sustained moving-ball run using those speeds, and none met the quiet-then-moving rule.

We then tested the same thresholds using motion calculated from consecutive detected positions.
Within graded frames, this provides a speed estimate for 99.5% of detected-ball frames, compared
with 7.8% for the supplied speeds. These estimates can contain coordinate noise and small timing
errors; they do not make the automatic tracking ground truth.

The position-based rule finds 30 distinct possible restarts supported by 32 tags. Its support
overlaps 30 of the 79 long gaps, including ten of the 29 rejected by Experiment 003's speed rule.
It marks 7,102 supported frames dead, of which 6,602 were already dead in Experiment 003. The
500 actual changes all occur where the ball is missing. Whole-match possession count falls by
eight, but we do not know whether those removed possessions were errors.

## Interpretation and review

The public predictions are identical to Experiment 003, so all public metrics are unchanged.
This is not evidence that the new changes are correct. It establishes that the new rule can act
on automatic restart evidence outside the public sample. Neither motion variant identifies live
goalkeeper possession: both only add `D` and preserve the existing labels elsewhere.

The ten changed sections are available in the
[shared clip reviewer](../../data/derived/clip_reviews/004_tagged_restarts/review.html), with
five seconds of context on each side. Review whether the general restart pattern makes sense;
do not turn the windows into a hand-labelled answer key. The hosted assistant has not viewed them.

## Verification

Six synthetic tests passed, covering bounded dead sections, absence of evidence, a one-frame
motion spike, half boundaries, review grouping, and metre-scaled motion without interpolation
across gaps. Both candidate CSVs passed the official submission validator. `metrics.json` stores
aggregate measurements, parameters, dependency versions, source hashes, and the primary candidate
hash. Generated predictions, timestamps, and HTML remain ignored under `data/derived/`.
