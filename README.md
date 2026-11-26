# makefun-news-image-20261125-v3

[![make.fun · news-image-20261125](https://make.fun/badge/news-image-20261125.svg)](https://make.fun/bounty/news-image-20261125?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261125)

One 1024x1024 poster summing up Wednesday **25 November 2026** — a lead story
panel, a drawn orthographic globe with numbered region markers, five
differently sized story cards and a 24-hour UTC timeline.

The six stories, in the order they appear on the timeline:

1. **13:10 UTC — Washington.** US tariffs target China, the EU and 12 more:
   new Section 301 duties over "overcapacity", and US stocks fall.
2. **02:00 — Middle East.** Houthi drones hit a Riyadh fund tower and threaten
   the Red Sea; Saudi jets bomb Hodeidah.
3. **08:00 — Europe.** Merz warns that Russia wants more than Ukraine, citing a
   700,000 dead estimate.
4. **17:00 — Global markets.** An AI-led selloff drags Wall Street lower as
   Nvidia doubts return and Asian markets dive.
5. **17:15 — Africa.** An Ebola outbreak disrupts eastern DR Congo; UN
   peacekeepers evacuate trapped health workers.
6. **21:25 — Climate.** A first six-day run above 2°C over pre-industrial levels
   as COP31 deadlocks.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out node main.ts
```

`main.ts` uses only the Node standard library. It creates the output directory,
copies the bundled `entry.png` to `entry.png` inside it, sets mode 0644, then
checks the size (≤ 1 MiB) and the PNG signature.

## Rebuild the image

The poster is drawn from scratch by `draw.py` (Pillow + numpy; build time only,
never run by the grader):

```sh
python3 draw.py
```

`landmask.png` is the 1-bit land mask used to project the globe.

## License

MIT — see `LICENSE`.
