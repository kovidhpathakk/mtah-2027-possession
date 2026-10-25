# Experiment 002 results

Status: first run complete, October 24, 2026.

| Version | Public spellF1 | Public macroF1 | Public D precision | Public D recall | Public possessions | Full-match possessions | Full-match D share |
|---|---:|---:|---:|---:|---:|---:|---:|
| Smooth50 baseline | 0.3256 | 0.6207 | 0.657 | 0.214 | 26 | 594 | 32.3% |
| Long gaps to D | 0.3349 | 0.6522 | 0.716 | 0.282 | 26 | 532 | 37.3% |

Long-gap coverage: 79 gaps of at least 10 seconds, totaling 55,103 frames or 85.2% of all
missing-ball time inside the two graded halves. Relative to smooth50, the rule changes 7,850
frames to `D`. In the public window, 366 frames fall in qualifying gaps; all 366 are `D` in
the public ground truth. At the 25-frame transition tolerance, spurious/missed transitions
move from 27/18 to 26/17.

Conclusion: the public score rises by 0.0093, while dead-ball precision and recall both rise.
This is a useful sign, not proof of a full-match improvement: the public window is small and its
qualifying gaps are all stoppages. The rule also raises the full-match predicted `D` share by
5.0 percentage points and cuts predicted possessions by 62. Some long gaps may contain live
play; without full-match ground truth, those changes are an unresolved risk. A next experiment
could use player movement or restart tags to distinguish long stoppages from long tracking losses.
