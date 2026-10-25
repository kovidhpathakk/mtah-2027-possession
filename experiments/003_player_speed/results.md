# Experiment 003 results

Status: completed October 24, 2026. Fixed parameters are recorded in `README.md` and `metrics.json`.

| Version | Public spellF1 | Public macroF1 | Public D precision | Public D recall | Full-match possessions | Full-match D share |
|---|---:|---:|---:|---:|---:|---:|
| Official Smooth50 | 0.3256 | 0.6207 | 0.657 | 0.214 | 594 | 32.3% |
| Experiment 002: all long gaps | 0.3349 | 0.6522 | 0.716 | 0.282 | 532 | 37.3% |
| Experiment 003: require slow players | 0.3349 | 0.6522 | 0.716 | 0.282 | 555 | 35.5% |

## What changed

The speed rule accepted 50 of the 79 long gaps and rejected 29. Compared with Smooth50, it adds
5,000 dead-ball frames instead of Experiment 002's 7,850: 2,850 fewer added `D` labels, or 114
seconds of video. Accepted gaps contain 29,421 frames in total; most were already `D` in Smooth50.
Usable speeds from at least 12 players exist in 94.8% of graded frames.

The entire public prediction sequence is identical to Experiment 002. Both correct 100
Smooth50 frame errors in that window without introducing new ones. Both predict 26 public
possessions, with 26 spurious and 17 missed transitions at the 25-frame tolerance.

## Conclusion

No additional public score gain. The speed rule makes fewer extra dead-ball assignments while
retaining Experiment 002's public improvement, but the public window cannot judge the 29 rejected
gaps because those changes occur outside it. We cannot claim those rejections are correct.

The official scorer's 5th–95th percentile bootstrap ranges are 0.2140–0.4558 for both experiments
and 0.2140–0.4465 for Smooth50. These wide, overlapping ranges reinforce how little this small
sample establishes; they do not measure uncertainty on unseen match situations.

The rule only controls extra `D` labels around long gaps. Smooth50 still marks their interiors
dead even where the speed gate rejects them. Full-match accuracy remains unknown.

## Human review: general failure pattern

Local video review of the 29 rejected gaps found several different situations: stoppages after the
ball went out or a goal, pauses for VAR or substitutions, halftime, goalkeeper possession, and
windows that crossed from live play into a stoppage or restart. In particular, a goalkeeper holding
the ball after a save can be live possession even when nearby players move slowly. A goal makes the
ball dead only after it is scored; a penalty window can be dead before the kick and live after it.

These are qualitative observations about the speed rule, not frame labels or a measured accuracy
result. The review player adds five seconds of context on either side, so an event seen in a window
may fall outside the rejected tracking gap. Slow movement alone cannot decide whether a whole gap
is dead. A next experiment should look for automatic evidence of stoppage and restart boundaries,
such as Smart Tagging set pieces, while allowing live goalkeeper possession. Do not hard-code the
reviewed windows or use these observations as an answer key.

## Verification

Four synthetic scenario tests passed: the duration boundary, rejecting insufficient slow-motion
evidence, preserving halftime boundaries, and changing only the qualifying gap. The candidate
passed the official submission validator. Derived frame labels are in ignored
`data/derived/experiments/003_player_speed/speed_gated_dead.csv`; this folder contains code,
documentation and aggregates only.
