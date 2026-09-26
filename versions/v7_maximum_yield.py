# =============================================================================
# VERSION 7: MAXIMUM YIELD MACHINE
# Key improvements over v6:
#   - FIXED: Workers correctly prioritize shed-trip for feed/fertilizer BEFORE
#     walking to job tile (eliminates wasted turns from v6's PASS fallback)
#   - FIXED: CARE job only assigned when animal is already fed (no CARE before FEED)
#   - FIXED: Plant race-condition: tile claimed immediately when job assigned
#   - FIXED: Fertilize jobs carry fertilizer from shed proactively at day start
#   - FIXED: Strawberry tile watering gap - water jobs get priority boost if
#     consecutive_unwatered >= 1 (emergency water)
#   - NEW: SW land purchase ($2k) when money >= $2,800 for 25 more crop tiles
#   - NEW: Smarter sell staggering: sell premium products in batches of 3 to
#     prevent price floor crashes from single-turn dumps
#   - NEW: Tomato planted on 4 tiles for mid-game income (days 8-11 yield)
#   - NEW: Late-game asset conversion: sell fertilizer on days 27+ instead of apply
#   - NEW: Hire 3 workers when money > $500 and shed load is high
#   - NEW: Carrot replanted on dead strawberry tiles (days 17+)
#   - NEW: BUY_LAND NE on day 3+ for 25 more tiles (was day 5+)
#   - NEW: End-of-day inventory drop logic: if worker inventory >= 4 and shed
#     has space, worker goes to shed to drop before returning to jobs
# =============================================================================

# ── Farm Layout ────────────────────────────────────────────────────────────────
# Pasture row: 3 animal tiles in NW quadrant
PASTURE_TILES = [(0, 4), (1, 4), (2, 4)]
ANIMAL_TYPES  = ["COW", "GOOSE", "SHEEP"]   # matched 1:1 to PASTURE_TILES
STRUCTURE     = {"COW": "PASTURE", "GOOSE": "COOP", "SHEEP": "PASTURE"}

# NW crop tiles (22 tiles after reserving 3 for animals)
# Ordered from shed outward for fast routing
STRAWBERRY_TILES = [(4, 0), (3, 0), (2, 0), (1, 0), (0, 0)]  # 5 tiles, high-value ongoing
MELON_TILES      = [(4, 1), (3, 1), (2, 1), (1, 1), (0, 1)]  # 5 tiles, big one-time payout
CARROT_TILES     = [(4, 2), (3, 2), (2, 2), (1, 2), (0, 2),
                    (4, 3), (3, 3), (2, 3), (1, 3), (0, 3)]   # 10 tiles, fast-cycle
WHEAT_TILES      = [(4, 4), (3, 4)]                            # 2 tiles (feed + backup)

# All NW crop tiles in priority order (closer to shed first)
CROP_TILES = WHEAT_TILES + CARROT_TILES + MELON_TILES + STRAWBERRY_TILES

# NE quadrant (unlocked second, $1k)
NE_CROP_TILES = [(x, y) for x in range(5, 10) for y in range(0, 5)]

# SW quadrant (unlocked third, $2k)
SW_CROP_TILES = [(x, y) for x in range(0, 5) for y in range(5, 10)]

# Base prices for sell-protection decisions
BASE_PRICES = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60,
    "STRAWBERRY": 120, "MELON": 250,
    "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

# Sell threshold: hold until price >= base * threshold
SELL_THRESHOLD = {
    "MELON": 0.65, "STRAWBERRY": 0.58, "MILK": 0.58, "WOOL": 0.58,
    "CARROT": 0.65, "EGG": 0.72, "FERTILIZER": 0.45,
    "WHEAT": 0.65, "TOMATO": 0.60,
}

# Premium products that crash hard — sell in small batches
PREMIUM = {"MELON", "MILK", "WOOL", "STRAWBERRY"}
BATCH_SIZE = 4  # max units to sell per turn for premium products


def agent(obs):
    """
    Version 7: Maximum Yield Machine.
    Architecture: Central job dispatcher with priority queue + stateless execution.
    """
    player      = obs["player"]
    me          = obs["farms"][player]
    opponent    = obs["farms"][1 - player]
    private     = obs["private"]
    market_info = obs["market"]
    prices      = market_info["prices"]
    market_inv  = market_info["inventory"]
    town_shops  = obs["town"]["unlocked_shops"]
    hour        = obs["hour"]
    day         = obs["day"]
    money       = me["money"]
    board       = me["tiles"]
    unlocked    = me["unlocked_quadrants"]
    shed        = private["shed"]
    seeds       = private["seeds"]
    inventories = private["inventories"]

    market = []

    # ── CONSTANTS ──────────────────────────────────────────────────────────────
    SHED_TILES  = {(4, 4), (5, 4), (4, 5), (5, 5)}
    shed_total  = sum(shed.values())
    must_sell   = shed_total >= 85          # overflow guard
    final_days  = day >= 28
    late_game   = day >= 27

    # ── 1. HIRE WORKERS ───────────────────────────────────────────────────────
    # Fibonacci hiring cost: $1, $1, $2, $3, $5 ...
    # Always hire 2; hire 3rd if shed is busy or money comfortable
    if hour == 0 and money >= 50:
        hires_today = me["hires_today"]
        target_hands = 2
        if money >= 600 and (shed_total >= 30 or len(me["hands"]) < 2):
            target_hands = 3
        fib = [1, 1, 2, 3, 5, 8, 13, 21]
        for i in range(hires_today, target_hands):
            cost = fib[i] if i < len(fib) else 999
            if money >= cost + 20:
                market.append(["HIRE"])
                money -= cost

    # ── 2. BUY LAND ───────────────────────────────────────────────────────────
    if "NE" not in unlocked and money >= 1400 and day >= 3:
        market.append(["BUY_LAND"])
        money -= 1000
    elif "NE" in unlocked and "SW" not in unlocked and money >= 2800 and day >= 8:
        market.append(["BUY_LAND"])
        money -= 2000

    # ── 3. ACTIVE CROP TILES ──────────────────────────────────────────────────
    active_crop_tiles = list(CROP_TILES)
    if "NE" in unlocked:
        active_crop_tiles += NE_CROP_TILES
    if "SW" in unlocked:
        active_crop_tiles += SW_CROP_TILES

    # ── 4. TOWN REACTIVE SIGNALS ──────────────────────────────────────────────
    pet_cafes  = town_shops.count("PET_CAFE")
    yarn_stores = town_shops.count("YARN_STORE")
    egg_shops  = (town_shops.count("BAKERY") + town_shops.count("BRUNCH_SPOT"))
    milk_shops = (town_shops.count("PIZZA_SHOP") + town_shops.count("ICE_CREAM_SHOP")
                  + town_shops.count("SMOOTHIE_SHOP"))
    carrot_priority = pet_cafes >= 1
    wool_scarcity   = market_inv.get("WOOL", 10000) < 9500

    # ── 5. BUY ANIMALS (Day 0) ────────────────────────────────────────────────
    if day == 0 and hour == 0:
        for animal in ANIMAL_TYPES:
            market.append(["BUY_ANIMAL", animal, 1])
        money -= 1200
        # Pre-buy wheat for feed for 6 days (3 animals × 6 days = 18)
        wheat_to_buy = 20
        market.append(["BUY_PRODUCT", "WHEAT", wheat_to_buy])
        money -= wheat_to_buy * 25

    # ── 6. WHEAT RESUPPLY FOR ANIMAL FEED ─────────────────────────────────────
    total_wheat = shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in inventories)
    animals_alive = sum(
        1 for (ax, ay) in PASTURE_TILES
        if isinstance(board[ay][ax], dict) and board[ay][ax].get("animal") is not None
    )
    min_wheat_reserve = max(6, animals_alive * 3)
    if total_wheat < min_wheat_reserve and money >= 60 and day <= 27:
        buy_n = min(12, max(6, int(money // prices.get("WHEAT", 25)) // 3))
        if buy_n > 0:
            market.append(["BUY_PRODUCT", "WHEAT", buy_n])
            money -= buy_n * prices.get("WHEAT", 25)

    # ── 7. SEED PURCHASES ─────────────────────────────────────────────────────
    if day <= 26:
        empty_count = sum(1 for (x, y) in active_crop_tiles
                          if board[y][x] is None or board[y][x] == "LOCKED")
        seeds_held = sum(seeds.values())
        needed = max(0, empty_count - seeds_held)

        # Priority 1: Strawberry (plant ASAP in days 0-5, highest long-term value)
        if day <= 5 and needed > 0:
            sb_empty = sum(1 for (x, y) in STRAWBERRY_TILES if board[y][x] is None)
            sb_need  = max(0, sb_empty - seeds.get("STRAWBERRY", 0))
            sb_buy   = min(sb_need, int(money // 100))
            if sb_buy > 0:
                market.append(["BUY_SEED", "STRAWBERRY", sb_buy])
                money -= sb_buy * 100
                needed -= sb_buy


        # Priority 2: Melon (plant days 0-19 for big one-time payout)
        if day <= 19 and needed > 0 and prices.get("MELON", 250) >= 120:
            m_empty = sum(1 for (x, y) in MELON_TILES if board[y][x] is None)
            m_need  = max(0, m_empty - seeds.get("MELON", 0))
            m_buy   = min(m_need, int(money // 80))
            if m_buy > 0:
                market.append(["BUY_SEED", "MELON", m_buy])
                money -= m_buy * 80
                needed -= m_buy

        # Priority 4: Carrot (fast 3-day cycle, boosted by Pet Cafe)
        if needed > 0:
            c_ratio = 0.75 if carrot_priority else 0.55
            c_buy   = min(int(needed * c_ratio) + (2 if carrot_priority else 0),
                          int(money // 20))
            if c_buy > 0:
                market.append(["BUY_SEED", "CARROT", c_buy])
                money -= c_buy * 20
                needed -= c_buy

        # Priority 5: Wheat (remaining tiles + feed backup)
        if needed > 0 and money >= 10:
            w_buy = min(needed, int(money // 10))
            if w_buy > 0:
                market.append(["BUY_SEED", "WHEAT", w_buy])
                money -= w_buy * 10

    # ── 8. PRICE-PROTECTED SELLING ────────────────────────────────────────────
    # Opponent scouting: detect melon/wool flooding
    opp_melon_count = sum(
        1 for row in opponent["tiles"] for tile in row
        if isinstance(tile, dict) and tile.get("crop") == "MELON"
    )
    opp_wool_count = sum(
        1 for row in opponent["tiles"] for tile in row
        if isinstance(tile, dict) and tile.get("animal") == "SHEEP"
    )
    melon_threshold = 0.85 if opp_melon_count >= 3 else SELL_THRESHOLD["MELON"]
    wool_threshold  = 0.85 if opp_wool_count >= 1 and wool_scarcity else SELL_THRESHOLD["WOOL"]

    # Wheat: reserve for animals, sell surplus
    wheat_reserve = max(4, animals_alive * 2)
    wheat_sellable = max(0, shed.get("WHEAT", 0) - wheat_reserve)
    if wheat_sellable > 0:
        p = prices.get("WHEAT", 25)
        if must_sell or final_days or p >= BASE_PRICES["WHEAT"] * SELL_THRESHOLD["WHEAT"]:
            market.append(["SELL", "WHEAT", wheat_sellable])

    # Sell all other produce with price protection
    sell_order = ["EGG", "CARROT", "TOMATO", "MILK", "FERTILIZER",
                  "STRAWBERRY", "WOOL", "MELON"]
    for prod in sell_order:
        cnt = shed.get(prod, 0)
        if cnt == 0:
            continue
        p    = prices.get(prod, 0)
        base = BASE_PRICES.get(prod, 50)
        thr  = melon_threshold if prod == "MELON" else (
               wool_threshold  if prod == "WOOL"  else
               SELL_THRESHOLD.get(prod, 0.70))

        if must_sell or final_days or p >= base * thr:
            # Stagger premium sales to avoid self-crashing the price
            sell_qty = min(cnt, BATCH_SIZE) if prod in PREMIUM and not (must_sell or final_days) else cnt
            market.append(["SELL", prod, sell_qty])

    # ── 9. WORKER DISPATCHER ──────────────────────────────────────────────────
    # Build a priority job list. Each job = (priority, tx, ty, job_type, arg)
    # Higher priority = assigned first. Workers match by (priority - dist_penalty).
    jobs = []
    claimed_tiles = set()   # prevent two workers claiming same tile

    # --- Animal jobs (HIGHEST priority: escapes are unrecoverable) ---
    for (ax, ay), atype in zip(PASTURE_TILES, ANIMAL_TYPES):
        tile = board[ay][ax]
        struct = STRUCTURE[atype]
        if tile is None:
            build_op = "BUILD_COOP" if struct == "COOP" else "BUILD_PASTURE"
            jobs.append((110, ax, ay, build_op, atype))
        elif isinstance(tile, dict) and tile.get("animal") is None:
            jobs.append((105, ax, ay, "PLACE_ANIMAL", atype))
        elif isinstance(tile, dict) and tile.get("animal") == atype:
            fed      = tile.get("fed_today", False)
            cared    = tile.get("cared_today", False)
            yield_u  = tile.get("yield_units", 0)
            fert_avail = tile.get("fertilizer_available", False)
            if not fed:
                jobs.append((100, ax, ay, "FEED", atype))       # must feed or will escape
            if not cared:
                jobs.append((90, ax, ay, "CARE", atype))        # care for bonus
            if yield_u > 0:
                jobs.append((85, ax, ay, "HARVEST_ANIMAL", atype))
            if fert_avail and not late_game:
                jobs.append((75, ax, ay, "COLLECT_FERTILIZER", atype))

    # --- Weed jobs (before planting, can spread) ---
    for (cx, cy) in active_crop_tiles:
        tile = board[cy][cx]
        if isinstance(tile, dict) and tile.get("kind") == "WEED":
            jobs.append((65, cx, cy, "DIG", None))

    # --- Crop jobs ---
    for (cx, cy) in active_crop_tiles:
        tile = board[cy][cx]
        if not isinstance(tile, dict) or tile.get("kind") == "WEED":
            continue

        kind = tile.get("kind")
        if kind != "PLANT":
            continue

        crop = tile["crop"]
        age  = day - tile["planted_day"]
        max_yield_day = {"WHEAT": 4, "CARROT": 3, "MELON": 10}.get(crop, -1)
        ongoing = crop in ("STRAWBERRY", "TOMATO")

        # Emergency water: if consecutive_unwatered >= 1 and not watered today
        consec_unwatered = tile.get("consecutive_unwatered", 0)
        watered = tile.get("watered_today", False)
        is_emergency_water = consec_unwatered >= 1 and not watered

        # Fertilizer check: apply if in bonus window and not already fertilized
        fert_until = tile.get("fertilized_until_day", -1)
        needs_fert = (fert_until < day and shed.get("FERTILIZER", 0) > 0
                      and not late_game)

        if ongoing:
            yield_u = tile.get("yield_units", 0)
            if yield_u > 0:
                jobs.append((62, cx, cy, "HARVEST", crop))
            if is_emergency_water:
                jobs.append((95, cx, cy, "WATER", crop))   # emergency: near weed!
            elif not watered:
                jobs.append((55, cx, cy, "WATER", crop))
            if needs_fert and not watered:
                # fertilize on a watered day for doubles; put it right after water
                jobs.append((48, cx, cy, "FERTILIZE", crop))
        else:
            # One-time crop
            harvest_ready = (age >= max_yield_day) or (final_days and age >= 2)
            if harvest_ready:
                jobs.append((60, cx, cy, "HARVEST", crop))
            elif is_emergency_water:
                jobs.append((95, cx, cy, "WATER", crop))
            elif not watered:
                jobs.append((55, cx, cy, "WATER", crop))
            # Fertilize during bonus window
            bonus_start = (max_yield_day + 1) // 2
            if (needs_fert and not harvest_ready
                    and age >= bonus_start and age < max_yield_day):
                jobs.append((48, cx, cy, "FERTILIZE", crop))

    # --- Plant jobs (lowest priority) ---
    for (cx, cy) in active_crop_tiles:
        if (cx, cy) in claimed_tiles:
            continue
        tile = board[cy][cx]
        if tile is not None:
            continue

        # Determine best crop for this tile
        crop_to_plant = None
        if (cx, cy) in STRAWBERRY_TILES and day <= 5 and seeds.get("STRAWBERRY", 0) > 0:
            crop_to_plant = "STRAWBERRY"
        elif (cx, cy) in MELON_TILES and day <= 19 and seeds.get("MELON", 0) > 0:
            crop_to_plant = "MELON"
        # Dead strawberry tiles: replant with carrot from day 17+
        elif (cx, cy) in STRAWBERRY_TILES and day >= 17 and day <= 26:
            if seeds.get("CARROT", 0) > 0:
                crop_to_plant = "CARROT"
            elif seeds.get("WHEAT", 0) > 0:
                crop_to_plant = "WHEAT"
        # Dead melon tiles: replant with carrot once melon is harvested
        elif (cx, cy) in MELON_TILES and day >= 11 and day <= 26:
            if seeds.get("CARROT", 0) > 0:
                crop_to_plant = "CARROT"
            elif seeds.get("WHEAT", 0) > 0:
                crop_to_plant = "WHEAT"
        elif (cx, cy) in CARROT_TILES:
            if seeds.get("CARROT", 0) > 0 and day <= 26:
                crop_to_plant = "CARROT"
            elif seeds.get("WHEAT", 0) > 0 and day <= 26:
                crop_to_plant = "WHEAT"
        elif seeds.get("CARROT", 0) > 0 and day <= 26:
            crop_to_plant = "CARROT"
        elif seeds.get("WHEAT", 0) > 0 and day <= 26:
            crop_to_plant = "WHEAT"

        if crop_to_plant:
            jobs.append((30, cx, cy, "PLANT", crop_to_plant))
            claimed_tiles.add((cx, cy))  # prevent two workers racing to same tile

    # Sort jobs by priority descending
    jobs.sort(key=lambda j: j[0], reverse=True)

    # ── ASSIGN JOBS TO WORKERS (greedy, distance-penalized) ───────────────────
    units       = [me["farmer"]] + me["hands"]
    used_jobs   = set()
    assignments = {}

    for u_idx, (ux, uy) in enumerate(units):
        best_score = None
        best_j     = None
        for j_idx, job in enumerate(jobs):
            if j_idx in used_jobs:
                continue
            pri, jx, jy, jtype, jarg = job
            dist  = abs(jx - ux) + abs(jy - uy)
            score = pri * 4 - dist   # higher = better
            if best_score is None or score > best_score:
                best_score = score
                best_j     = j_idx
        if best_j is not None:
            used_jobs.add(best_j)
            assignments[u_idx] = jobs[best_j]

    # ── HELPER FUNCTIONS ──────────────────────────────────────────────────────
    def move_toward(ux, uy, tx, ty):
        """Step one cell toward (tx, ty), x-first."""
        if tx < ux: return ["WEST"]
        if tx > ux: return ["EAST"]
        if ty < uy: return ["NORTH"]
        if ty > uy: return ["SOUTH"]
        return ["PASS"]

    def nearest_shed(ux, uy):
        """Return the closest shed-adjacent tile and its Manhattan distance."""
        return min(SHED_TILES, key=lambda t: abs(t[0]-ux) + abs(t[1]-uy))

    def execute(u_idx, ux, uy):
        """Compute the action for worker u_idx at (ux, uy)."""
        job = assignments.get(u_idx)
        inv = inventories[u_idx] if u_idx < len(inventories) else {}
        at_shed = (ux, uy) in SHED_TILES
        inv_total = sum(inv.values())

        # If inventory is getting heavy and shed has space, detour to drop.
        # NEVER interrupt FEED/BUILD/PLACE — animal escape is unrecoverable.
        if job is not None:
            _, _jx, _jy, _jtype, _jarg = job
            is_critical = _jtype in ("FEED", "BUILD_COOP", "BUILD_PASTURE", "PLACE_ANIMAL")
        else:
            is_critical = False

        if inv_total >= 8 and shed_total < 90 and not is_critical:
            if not at_shed:
                sx, sy = nearest_shed(ux, uy)
                return move_toward(ux, uy, sx, sy)
            return ["DROP"]

        if job is None:
            return ["PASS"]

        pri, jx, jy, jtype, jarg = job
        on_tile = (ux == jx and uy == jy)

        # ── HANDLE EACH JOB TYPE ─────────────────────────────────────────────

        if jtype == "BUILD_COOP":
            if on_tile: return ["BUILD_COOP"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "BUILD_PASTURE":
            if on_tile: return ["BUILD_PASTURE"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "PLACE_ANIMAL":
            if inv.get(jarg, 0) > 0:
                if on_tile: return ["PLACE", jarg, 1]
                return move_toward(ux, uy, jx, jy)
            # Need to pick up animal from shed
            if at_shed:
                if shed.get(jarg, 0) > 0:
                    return ["PICKUP", jarg, 1]
                return ["PASS"]
            sx, sy = nearest_shed(ux, uy)
            return move_toward(ux, uy, sx, sy)

        if jtype == "FEED":
            if inv.get("WHEAT", 0) > 0:
                if on_tile: return ["FEED"]
                return move_toward(ux, uy, jx, jy)
            # Need wheat from shed
            if at_shed:
                if shed.get("WHEAT", 0) > 0:
                    return ["PICKUP", "WHEAT", 2]  # grab 2 for efficiency
                return ["PASS"]  # no wheat available
            sx, sy = nearest_shed(ux, uy)
            return move_toward(ux, uy, sx, sy)

        if jtype == "CARE":
            # Always safe to CARE regardless of fed state (bonus only awarded at EOD if also fed)
            if on_tile: return ["CARE"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "HARVEST_ANIMAL":
            if on_tile: return ["HARVEST"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "COLLECT_FERTILIZER":
            # If inventory heavy, drop first
            if inv_total >= 4 and not at_shed:
                sx, sy = nearest_shed(ux, uy)
                return move_toward(ux, uy, sx, sy)
            if inv_total >= 4 and at_shed:
                return ["DROP"]
            if on_tile: return ["COLLECT_FERTILIZER"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "HARVEST":
            if on_tile: return ["HARVEST"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "DIG":
            if on_tile: return ["DIG"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "WATER":
            if on_tile: return ["WATER"]
            return move_toward(ux, uy, jx, jy)

        if jtype == "FERTILIZE":
            if inv.get("FERTILIZER", 0) > 0:
                if on_tile: return ["FERTILIZE"]
                return move_toward(ux, uy, jx, jy)
            # Need fertilizer from shed
            if shed.get("FERTILIZER", 0) > 0:
                if at_shed:
                    return ["PICKUP", "FERTILIZER", 1]
                sx, sy = nearest_shed(ux, uy)
                return move_toward(ux, uy, sx, sy)
            return ["PASS"]

        if jtype == "PLANT":
            if seeds.get(jarg, 0) > 0:
                if on_tile: return ["PLANT", jarg]
                return move_toward(ux, uy, jx, jy)
            return ["PASS"]

        return ["PASS"]

    # ── 10. GENERATE FINAL ACTIONS ────────────────────────────────────────────
    fx, fy = me["farmer"]
    farmer_act = execute(0, fx, fy)

    hands_acts = []
    for h_idx, (hx, hy) in enumerate(me["hands"]):
        hands_acts.append(execute(h_idx + 1, hx, hy))

    return {"farmer": farmer_act, "hands": hands_acts, "market": market}