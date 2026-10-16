# Award submission: evidence gates

Primary conditions from assignment (10/8): Robot task execution video MP4 1–3 min; PDF report named `説明資料_PAI最終課題_<OmniCampusアカウント名>.pdf`; public GitHub repo URL; YouTube title `PAI最終課題_<OmniCampusアカウント名>` with at least unlisted setting; no personal data or confidential secrets. Deadline 2026-11-02 10:00 JST.

**Stop/go gates, in priority order:**

1. Physical simulation: Gazebo runs, all sensors publish, odometry changes while guard passes forward command. A static SDF or mock loop does not count.
2. Inference integration: actual Jev 1.14.0 + Qwen3.8 real responses to a post-arrival camera frame. Store hashes, stamps and model IDs without secrets.
3. Causal comparison: same environment, correct water station vs wrong station; robot proceeds only when dual decision permits. Record ROS bag and Gazebo actual screen.
4. Held-out experiment: count n, correct permits, false permits, abstentions, latencies with consistent ground truth. Include uncertainty and disclose any selected demonstration attempts.
5. Submission: 60–180s robot MP4; no fake simulated results; PDF updated; GitHub public; YouTube suitable settings; OmniCampus both URLs and PDF. Test the URL without signing in.

Fallback decision (engineering proposal, not a course rule): if custom scene cannot physically navigate within remaining schedule, switch to known working TurtleBot/official Nav2 simulation for motion while retaining original Jev/Qwen on-site safety checkpoint and distinct application. Do not merely resubmit a sample.
