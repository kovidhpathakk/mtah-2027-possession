# Football notes

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
