"""Our possession pipeline: tracking in, one H/A/D/X label per tactical video frame out.

Stages, each a module with one owner, each reading and writing per-frame arrays indexed by
tactical video frame 0..199318 (intermediate files live in data/derived/, never in git):

    clean       tracking to metres, ghost removal, short player gaps
    ball        ball position and confidence through the blackouts
    features    team-level per-frame signals, Smart Tagging priors
    decide      per-frame evidence to possessions that switch only on sustained control
    polish      stoppages, X outside the halves, D before the 2nd-half kickoff, sanity checks
"""
