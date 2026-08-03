---
title: Adjacency Autopsy
emoji: 🔎
colorFrom: blue
colorTo: red
sdk: gradio
sdk_version: 6.16.0
app_file: app.py
pinned: false
license: mit
---

# Adjacency Autopsy

Adjacency compiles advertiser prose into a typed policy, checks inventory with a confidence-gated judge, and passes every verdict through deterministic fail-closed gates. This public demo is fully offline. It replays the frozen corpus and never calls xAI or Temporal.

Run the Autopsy to compare the compiled engine with a keyword blocklist generated from the same advertiser prose. Inspect the `G1_SPAN_NOT_FOUND` case to see a proposed `ALLOW` changed to `REVIEW` before delivery.

Source: <https://github.com/arunshar/adjacency>
