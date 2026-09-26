# Kaggriculture Bot: Autonomous Farming Simulation Agent

This repository contains the progression of autonomous agents developed for the Kaggle Kaggriculture Competition.

Competition URL: https://www.kaggle.com/competitions/kaggriculture

---

## 1. Project Overview

Kaggriculture is a two-player turn-based economic simulation where agents manage an expanding farm over a single season consisting of 30 in-game days, with 24 hourly turns per day (720 turns total). Both agents compete simultaneously in a dynamic marketplace with shifting supply and demand curves.

### Victory Condition
The agent with the highest bank balance at turn 720 wins the match. Produce, seeds, and livestock remaining in storage or on tiles at turn 720 do not count toward the final score; only liquid cash determines the winner.

### Key Game Systems
- Grid Map: 10x10 tile board split into four 5x5 quadrants (Northwest, Northeast, Southwest, Southeast). Players begin with only the Northwest quadrant (25 tiles) unlocked.
- Central Shed: Located at coordinates (4,4), (5,4), (4,5), and (5,5). Functions as the storage drop point and inventory hub with a strict 100-item capacity.
- Workforce: The primary farmer is available on turn 0. Additional farm hands can be hired daily via the market. Hiring costs follow a Fibonacci sequence (1, 1, 2, 3, 5...) that resets each morning.
- Dynamic Market: 10,000 baseline inventory per commodity. Prices move according to non-linear curve functions (linear, square, square root, log, hinge) influenced by player sales and town shop consumption.
- Town Economy: Up to 8 shops unlock at 3-day intervals, consuming specific resources every 4 turns and creating demand spikes.

---

## 2. Competition Resources and Kaggle Rules

The simulation engine, local environment assets, and proprietary game rules are not redistributed inside this repository to adhere strictly to Kaggle Competition Rules and terms of service.

To install the environment and acquire the official competition resources:
1. Visit the official competition page: https://www.kaggle.com/competitions/kaggriculture
2. Install the official Kaggle Environments package:
   ```bash
   pip install kaggle-environments
   ```
3. Run local benchmarks using the built-in specification:
   ```bash
   python -c "from kaggle_environments import make; env = make('kaggriculture'); print('Loaded successfully')"
   ```

---

## 3. Version Evolution and Benchmark Progression

Each iteration systematically addressed bottlenecks identified in previous replays, scaling from a stationary single-tile crop gatherer to an integrated multi-livestock, market-defensive enterprise.

| Version | File | Average Score | Win Rate vs Starter | Core Innovations |
|---|---|---|---|---|
| v1 | versions/v1_simple_wheat.py | ~$3,327 | 50% (Tie baseline) | Single-tile stationary Wheat planting, watering, and harvesting at age 2. |
| v2 | versions/v2_moving_farmer.py | ~$6,533 | 100% | 6-tile patrol route, maturity delay to age 4 for optimal yield. |
| v3 | versions/v3_workers_and_melons.py | ~$14,403 | 100% | First hired hand, expansion to 12 tiles, introduction of high-value Melons ($250 base). |
| v4 | versions/v4_plantation.py | ~$17,131 | 100% | 2 hired hands (3 workers total), 18 tiles, weed clearing (DIG), end-of-season seed cutoffs. |
| v5 | versions/v5_ultimate.py | ~$24,039 | 100% | Livestock introduction (Cow/Milk), centralized job dispatcher, market price floor defense (70%). |
| v6 | versions/v6_grand_estate.py | ~$26,887 | 100% (5/5 clean) | 3 animals (Cow, Goose, Sheep), animal fertilizer recycling, Strawberry integration, opponent scouting. |
| v7 | versions/v7_maximum_yield.py | ~$21,156 | 100% | Southwest land expansion ($2,000), 5 melon tiles, mid-day shed deposit detours, batch selling. |
| v7b | versions/v7b_corrected.py | ~$20,500 | 100% | Reverted melon tiles to 3, adjusted carrot ratio, maintained V7 architecture. |

---

## 4. Deep Dive: Attempt Details and Technical Post-Mortem

### Version 1: Simple Stationary Wheat
- Architecture: Hardcoded state machine on tile (4,4).
- Mechanics Used: BUY_SEED WHEAT, PLANT, WATER, HARVEST, SELL.
- Outcome: Scored ~$3,327 locally. Confirmed execution loop and basic timing rules.
- Bottleneck: The farmer never left the starting tile, leaving 24 available tiles idle.

### Version 2: Moving Farmer Patrol
- Architecture: Sequential waypoint loop over 6 tiles.
- Mechanics Used: Cardinal movement (NORTH, SOUTH, EAST, WEST), deferred harvesting at peak maturity (age 4).
- Outcome: Scored ~$6,533 locally. Doubled revenue by rotating between active plantings.
- Bottleneck: Single-worker bottleneck. Moving back and forth took excessive turns, limiting tile capacity.

### Version 3: Workers and Melons
- Architecture: Multi-agent coordination with 1 hired hand.
- Mechanics Used: HIRE market order, Melon cash crop integration.
- Outcome: Scored ~$14,403 locally; achieved score 600.0 on the live Kaggle leaderboard.
- Bottleneck: No collision avoidance or shared job scheduling; workers frequently attempted redundant actions on the same tile.

### Version 4: Plantation Scale
- Architecture: 18 dedicated crop slots, 2 hired farm hands (3 total active units).
- Mechanics Used: Tile maintenance (DIG weeds), strict seed purchasing limits stopping at day 26 to prevent unharvestable crops at turn 720.
- Outcome: Scored ~$17,131 locally.
- Bottleneck: Pure crop reliance. Re-buying seeds and daily watering consumed significant turn overhead without compounding assets.

### Version 5: Ultimate Livestock and Dispatcher
- Architecture: Centralized Manhattan-distance job dispatcher paired with a Cow Pasture.
- Mechanics Used: BUILD_PASTURE, BUY_ANIMAL COW, daily FEED with wheat, daily CARE bonus stacking, market price protection (holding inventory if sell price drops below 70% of base).
- Outcome: Scored ~$24,039 locally.
- Bottleneck: Only utilized a single Cow; ignored Goose and Sheep; collected animal fertilizer but never applied it back onto crop tiles.

### Version 6: The Grand Estate (Current Production Standard)
- Architecture: Full multi-tier estate engine operating across 3 livestock installations and 22 crop tiles.
- Mechanics Used:
  - Triple Livestock: Cow (Milk every 2 days), Goose (Eggs daily), Sheep (Wool every 3 days).
  - Closed-Loop Fertilizer Cycle: COLLECT_FERTILIZER from livestock tiles followed by FERTILIZE actions on crops, generating +50% to +100% yield multipliers from zero-cost inputs.
  - Crop Diversification: Strawberry tiles for high recurring value, protected Melon tiles (limited to 3 to prevent self-induced market collapse), fast 3-day Carrot cycles.
  - Opponent Scouting: Inspects opponent farm tiles to detect competitor melon gluts and holds inventory until prices stabilize.
  - Shed Overflow Guard: Automated bulk liquidation triggers if shed inventory exceeds 85/100 units.
- Outcome: Achieved an average benchmark of $26,887 across multiple seeds, with peak runs exceeding $30,200.

### Version 7 and 7b: Technical Post-Mortem and Bottleneck Analysis
Version 7 attempted to scale further by incorporating additional theoretical mechanics, but benchmarks revealed significant inefficiencies, scoring ~$19,900 to ~$21,100:

1. The Land Expansion Trap:
   V7 attempted to purchase the Southwest quadrant for $2,000 on day 8, expanding farmable area to 75 tiles. However, with only 2 to 3 workers, units spent up to 10 consecutive turns traversing the 10x10 grid. As a result, critical watering windows were missed, crops decayed into weeds, and the $2,000 capital investment never achieved positive return on investment.
2. Mid-Day Shed Detour Overhead:
   V7 instructed workers to walk to the shed whenever personal inventory reached 8 items. Because the game engine automatically deposits all worker inventories into the shed at midnight at zero turn cost, these manual mid-day trips wasted 6 to 8 action turns per worker per day.
3. Batch Sell Throttling:
   V7 throttled sales of premium commodities to 4 units per turn. This caused high-value goods to remain stuck in storage past peak price windows, leaving unliquidated assets at game end.

Conclusion: Version 6 remains the mathematically optimal and highest-scoring engine.

---

## 5. Repository Structure

```
├── main.py                     # Current active agent for local runs and Kaggle submission
├── versions/
│   ├── v1_simple_wheat.py      # Stationary single-tile baseline
│   ├── v2_moving_farmer.py     # 6-tile moving patrol
│   ├── v3_workers_and_melons.py# 1 hired hand + melon crop
│   ├── v4_plantation.py        # 2 hired hands + weed management
│   ├── v5_ultimate.py          # Cow pasture + central dispatcher
│   ├── v6_grand_estate.py      # 3 animals + closed-loop fertilizer + scouting (Recommended)
│   ├── v7_maximum_yield.py     # SW land expansion experiment
│   └── v7b_corrected.py        # Adjusted melon allocation experiment
├── replays/                    # Full turn-by-turn HTML match replays
│   ├── v1_vs_starter.html
│   ├── v2_vs_starter.html
│   ├── v3_vs_starter.html
│   ├── v4_vs_starter.html
│   ├── v5_vs_starter.html
│   ├── v6_vs_starter.html
│   ├── v7_vs_starter.html
│   └── v7b_vs_starter.html
└── README.md                   # Full documentation and project reference
```

---

## 6. How to Run and Evaluate

### Run Local Benchmark
To execute a match between the current agent (`main.py`) and the starter bot:
```bash
python -c "from kaggle_environments import make; env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True); env.run(['main.py', 'starter']); print('Your Score:', env.steps[-1][0]['reward']); print('Starter Score:', env.steps[-1][1]['reward'])"
```

### View Visual Replays
All match replays are saved in the `replays/` directory as self-contained HTML files. Open any file in a standard browser (Google Chrome, Microsoft Edge, Mozilla Firefox) to inspect the 10x10 farm grid, livestock actions, worker paths, and market price fluctuations across all 720 turns.

### Submit to Kaggle
Ensure `main.py` contains the target version (default: Version 6 Grand Estate), then submit via the Kaggle CLI:
```bash
kaggle competitions submit -c kaggriculture -f main.py -m "V6 Grand Estate - 3 animals, closed loop fertilizer, price protection"
```
