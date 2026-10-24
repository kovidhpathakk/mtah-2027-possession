# Football notes

## From published research (web, 2026-10-24)

General football facts, not about our match. Use them as sanity ranges, not targets.

- **Ball in play is only ~54–56 minutes of a LaLiga match.** LaLiga's own figure is ~54 min of
  effective playing time; studies put La Liga at ~55% of match time, with Barcelona among the
  highest (~60%). So dead ball is likely **40–45% of a full match**, far more than the ~20% in
  our calm public 5 minutes. Our ball goes missing on 41% of graded frames, which fits the
  "tracker drops the ball when play stops" pattern.
  [Inside World Football](https://insideworldfootball.com/?p=109070),
  [Olive Press](https://theolivepress.es/spain-news/2023/10/17/footballs-90-minutes-why-are-they-not-equal-across-leagues),
  [Football España](https://www.football-espana.net/2021/10/26/valencia-real-madrid-la-liga)
- **How long restarts stop play (study averages):** throw-in ~12–13 s, goal kick ~15–17 s,
  free kick ~21–23 s, corner ~26–27 s. Most of our medium blackouts (5–20 s) are this length, so
  many of them are probably restarts, not hidden live play.
  [PMC study table](https://pmc.ncbi.nlm.nih.gov/articles/PMC10442814/table/T3)
- **Possessions per match:** one provider (ESPN/TruMedia) counts ~95 per team per match in the
  big five leagues, so ~190 per match. Definitions differ: ours also splits at every stoppage, so
  expect more, but probably a few hundred, not 500+.
  [TruMedia](https://www.trumedianetworks.com/analytics-news/tag/espn)
- **Prior work on exactly our problem:** Vidal-Codina et al. (MIT Sports Lab and FIFA, 2022)
  detect possession from tracking with a deterministic, decision-tree possession model, and also
  recognise dead-ball player configurations, reporting 90%+ event detection.
  [arXiv 2202.00804](https://arxiv.org/abs/2202.00804v2)
- Rule changes from 2026-27 add a 5-second countdown for throw-ins and goal kicks; our match is
  from 2024-25, so restarts there could take longer.
  [Eswatini Observer](https://www.eswatiniobserver.com/fifa-five-second-restart-rule/)

What our football eye sees that the tracking does not say. Each note should be general enough to
become a rule or a feature -- never a label for a specific moment of this match (that would be
hand labelling).

Format: the observation, how sure you are, and how we might detect it in tracking.

## Control and turnovers

-

## Restarts and stoppages

-

## How Barça play

-

## How Athletic play

-

## Ball blackouts (from the gap clips)

- The tracker usually drops the ball the moment play stops (ball over a line, whistle) and picks
  it up when play restarts, even though the ball is plainly visible on the spot or in a player's
  hands. Confidence: high (most of the 15 longest gaps). Detect: long gap + players walking.
- Typical stoppages behind long gaps: goals (celebration, walk back, kickoff wait), fouls and
  free kicks, penalties, drinks breaks, end of a half, goal kicks, corners, throw-ins.
- The restart edge is fuzzy: sometimes the ball reappears when the kick is taken, sometimes a
  little earlier while it is placed or rolled to the taker (play still stopped).
- Some long gaps contain live play: a corner is delivered and fought over, or a clearance goes
  high off-camera and comes down into a contest. Detect: player speed picks up inside the gap.
- Some gaps are real occlusions in live play: a defender steps between the camera and the ball
  during a tackle. These are usually shorter.
- After a goalkeeper catches the ball, play is live but slow; the tracker may still miss the ball
  until he releases it.
