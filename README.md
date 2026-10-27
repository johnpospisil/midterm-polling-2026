# How Wrong Were the Polls? The 2026 Midterms

This project compares every public 2026 Senate, governor and House poll with the certified results. It asks how far off the polls were, whether they all missed in the same direction, and whether newer polling methods did better. It is the companion to [prediction-market-calibration](../prediction-market-calibration), which runs the "polls vs markets" comparison.

Status: in progress. A preliminary "first look" is planned for mid-November 2026 and the final post-mortem for after certification (mid-December).

## Reproduce

```bash
uv sync
make test
make all
```

Data sources and terms of use: see [DATA.md](DATA.md).
