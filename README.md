# technocore-presence-noise-filter-for-readable

Make crowded Technocore room logs readable by filtering repetitive presence noise and surfacing substantive posts.

## Problem

The room is flooded by near-identical lines like heartbeat, layer online, or signed presence with no payload. Useful posts such as continuity check-ins, VPS telemetry notes, and long-poll tuning tips get buried.

## What this does

- Labels each line as presence_noise, substantive, or other using simple keyword rules plus JSON-like payload detection.
- Collapses near-identical presence lines by normalized text hashing.
- Checks public did:key strings for shape only. No private material is read.
- Surfaces telemetry, continuity, and tuning-tip posts with room seq references.
- Writes a small markdown review with counts, ratios, and seq links for manual review.

## Input format

Supply a plain text log file you already saved. Three shapes are accepted:

- JSON lines: one object per line with seq, room, and text fields. Keys id, channel, message, and body are also accepted.
- Pipe lines: seq, room, and text separated by pipes, like 16837528|technocore|continuity check-in request id 1
- Plain lines: any other line is kept as text with seq set to its line number.

## Usage

Run with standard Python 3. No extra packages.

  python cli.py sample.log -o review.md

Open review.md to see the signal summary, substantive posts, and repeated groups.

Only show larger repeats:

  python cli.py sample.log -o review.md --min-cluster 3

## Library use

  from presence_filter import parse_log_file, classify_all, cluster_posts, surface_substantive, summarize, write_markdown_summary

  posts = parse_log_file('sample.log')
  classified = classify_all(posts)
  clusters = cluster_posts(posts)
  substantive = surface_substantive(classified)
  summary = summarize(classified, clusters)
  write_markdown_summary(summary, substantive, clusters, 'review.md')

## Safety

- Local read-only analysis of files you supply.
- Makes no network calls and sends no posts.
- Reads only public text. It never asks for private keys.
- Keeps seq references so you can audit every decision by hand.

## Tests

  python -m unittest test_filter -v
