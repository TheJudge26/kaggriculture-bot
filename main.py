# =============================================================================
# VERSION 6: THE GRAND ESTATE
# Uses ALL available game mechanics for maximum output:
#   - 3 Animals: COW (milk) + GOOSE (eggs daily) + SHEEP (wool)
#   - FREE fertilizer from animals -> applied to all crops (+$35-$50 per tile)
#   - STRAWBERRY (4x $120 = $480/plant) with fertilizer (doubles to $960/plant)
#   - CARROT + WHEAT fast-cycle crops filling remaining tiles
#   - BUY_LAND for NE quadrant when able (25 -> 50 tiles)
#   - Town-reactive crop pivot (Yarn Store -> Sheep, Pet Cafe -> Carrots)
#   - Central Job Dispatcher with collision prevention
#   - Shed overflow guard (100 item cap)
#   - Hand spawn path correction (spawns at locked tile, must walk west)
#   - Market inventory signal (obs[market][inventory] for price direction)
#   - Opponent scouting (detect melon flood -> hold our melons)
#   - Price-protected selling with smart last-day dump
# =============================================================================

# --- Farm Layout (NW Quadrant, 25 tiles total) ---
# Pasture row at y=4: tiles (0,4),(1,4),(2,4) = 3 animals
# Remaining 22 tiles = crops
PASTURE_TILES = [(0, 4), (1, 4), (2, 4)]
ANIMAL_TYPES  = ["COW", "GOOSE", "SHEEP"]   # matched 1:1 to PASTURE_TILES
STRUCTURE     = {"COW": "PASTURE", "GOOSE": "COOP", "SHEEP": "PASTURE"}

# Crops across all remaining NW tiles
CROP_TILES = [
    (4, 4), (4, 3), (4, 2), (4, 1), (4, 0),
    (3, 4), (3, 3), (3, 2), (3, 1), (3, 0),
    (2, 3), (2, 2), (2, 1), (2, 0),
    (1, 3), (1, 2), (1, 1), (1, 0),
    (0, 3), (0, 2), (0, 1), (0, 0),
]
# Dedicated slots for high-value crops (planted early for full season duration)
STRAWBERRY_TILES = [(4, 0), (3, 0), (2, 0), (1, 0), (0, 0)]  # 5 tiles
MELON_TILES      = [(4, 1), (3, 1), (2, 1)]                   # 3 tiles
CARROT_TILES     = [(4, 2), (3, 2), (2, 2), (1, 2), (0, 2),
                    (4, 3), (3, 3), (2, 3), (1, 3), (0, 3)]   # 10 tiles
WHEAT_TILES      = [(4, 4), (3, 4)]                            # 2 tiles (for feed + backup cash)

# When NE quadrant is unlocked, add 25 more crop tiles
NE_CROP_TILES = [
    (5, 4), (5, 3), (5, 2), (5, 1), (5, 0),
    (6, 4), (6, 3), (6, 2), (6, 1), (6, 0),
    (7, 4), (7, 3), (7, 2), (7, 1), (7, 0),
    (8, 4), (8, 3), (8, 2), (8, 1), (8, 0),
    (9, 4), (9, 3), (9, 2), (9, 1), (9, 0),
]

# Town shop -> which crop/animal to pivot toward
SHOP_PIVOT = {
    "YARN_STORE":    "SHEEP",       # Wool price spikes
    "PET_CAFE":      "CARROT",      # Carrot demand doubles
    "BAKERY":        "GOOSE",       # Egg demand
    "BRUNCH_SPOT":   "GOOSE",       # Egg demand
    "PIZZA_SHOP":    "COW",         # Milk demand
    "ICE_CREAM_SHOP":"COW",         # Milk demand
    "SMOOTHIE_SHOP": "COW",         # Milk demand
    "FARMERS_MARKET":"CARROT",      # Carrot demand
}

# Base prices for price-protection decisions
BASE_PRICES = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60,
    "STRAWBERRY": 120, "MELON": 250,
    "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}

# Sell threshold: fraction of base price below which we hold
SELL_THRESHOLD = {
    "MELON": 0.65, "STRAWBERRY": 0.60, "MILK": 0.60, "WOOL": 0.60,
    "CARROT": 0.70, "EGG": 0.75, "FERTILIZER": 0.50,
    "WHEAT": 0.70,
}

def agent(obs):
    """
    Version 6: The Grand Estate - Full utilization of all game mechanics.
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

    # ------------------------------------------------------------------
    # 1. HIRE UP TO 2 HANDS EVERY MORNING (costs $1 + $1 = $2)
    # ------------------------------------------------------------------
    if hour == 0 and money >= 50:
        needed_hires = 2 - me["hires_today"]
        for _ in range(needed_hires):
            market.append(["HIRE"])
            money -= 1

    # ------------------------------------------------------------------
    # 2. BUY LAND (NE quadrant for $1000 when we have spare cash)
    # ------------------------------------------------------------------
    if "NE" not in unlocked and money >= 1500 and day >= 3:
        market.append(["BUY_LAND"])
        money -= 1000

    # ------------------------------------------------------------------
    # 3. ACTIVE CROP TILES (combine NW + NE if unlocked)
    # ------------------------------------------------------------------
    active_crop_tiles = list(CROP_TILES)
    if "NE" in unlocked:
        active_crop_tiles += NE_CROP_TILES

    # ------------------------------------------------------------------
    # 4. TOWN-REACTIVE CROP PRIORITY
    # ------------------------------------------------------------------
    # Count shop types active this season
    yarn_stores = town_shops.count("YARN_STORE")
    pet_cafes   = town_shops.count("PET_CAFE")

    # Carrot boost: if pet cafe is open, plant more carrots
    carrot_priority = pet_cafes > 0

    # ------------------------------------------------------------------
    # 5. BUY ANIMALS ON DAY 0
    # ------------------------------------------------------------------
    if day == 0 and hour == 0:
        for animal in ANIMAL_TYPES:
            market.append(["BUY_ANIMAL", animal, 1])
        money -= 300 + 400 + 500  # GOOSE + COW + SHEEP
        # Pre-buy wheat for feeding all 3 animals for 5 days
        market.append(["BUY_PRODUCT", "WHEAT", 20])
        money -= 20 * 25

    # ------------------------------------------------------------------
    # 6. WHEAT RESUPPLY FOR ANIMAL FEED
    # Keep at least 8 wheat in stock at all times (3 animals need daily feeding)
    # ------------------------------------------------------------------
    total_wheat = shed.get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in inventories)
    if total_wheat < 8 and money >= 100 and day <= 27:
        buy_n = min(10, int(money // prices.get("WHEAT", 25)))
        if buy_n > 0:
            market.append(["BUY_PRODUCT", "WHEAT", buy_n])
            money -= buy_n * prices.get("WHEAT", 25)

    # ------------------------------------------------------------------
    # 7. SEED PURCHASES (smart, prioritized)
    # ------------------------------------------------------------------
    if day <= 26:
        empty_crop_count = sum(1 for (x, y) in active_crop_tiles if board[y][x] is None)
        seeds_held = sum(seeds.values())
        needed = max(0, empty_crop_count - seeds_held)

        # Priority 1: Strawberries (highest value ongoing, plant very early)
        if day <= 5 and needed > 0:
            sb_empty = sum(1 for (x, y) in STRAWBERRY_TILES
                          if board[y][x] is None and seeds.get("STRAWBERRY", 0) == 0)
            sb_buy = min(sb_empty, needed, int(money // 100))
            if sb_buy > 0:
                market.append(["BUY_SEED", "STRAWBERRY", sb_buy])
                money -= sb_buy * 100
                needed -= sb_buy

        # Priority 2: Melons (high one-time value, plant early)
        if day <= 19 and needed > 0 and prices.get("MELON", 250) >= 130:
            m_empty = sum(1 for (x, y) in MELON_TILES if board[y][x] is None)
            m_needed = min(m_empty, needed, int(money // 80))
            if m_needed > 0:
                market.append(["BUY_SEED", "MELON", m_needed])
                money -= m_needed * 80
                needed -= m_needed

        # Priority 3: Carrots (fast 3-day cycle, boosted by pet cafe)
        if needed > 0:
            c_ratio = 0.7 if carrot_priority else 0.5
            c_buy = min(int(needed * c_ratio), int(money // 20))
            if c_buy > 0:
                market.append(["BUY_SEED", "CARROT", c_buy])
                money -= c_buy * 20
                needed -= c_buy

        # Priority 4: Wheat (remaining tiles + always need for feed backup)
        if needed > 0 and money >= 10:
            w_buy = min(needed, int(money // 10))
            if w_buy > 0:
                market.append(["BUY_SEED", "WHEAT", w_buy])
                money -= w_buy * 10

    # ------------------------------------------------------------------
    # 8. PRICE-PROTECTED SELLING
    # Check opponent farm for signs of crop flooding before selling
    # ------------------------------------------------------------------
    # Scout opponent: count melon tiles they have
    opp_melon_count = sum(
        1 for row in opponent["tiles"] for tile in row
        if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "MELON"
    )
    opp_has_many_melons = opp_melon_count >= 3

    # Shed overflow guard: if shed nearing 100, MUST sell everything
    shed_total = sum(shed.values())
    must_sell = shed_total >= 85

    # Reserve 4 wheat for animal feed
    wheat_sellable = max(0, shed.get("WHEAT", 0) - 4)
    if wheat_sellable > 0:
        p = prices.get("WHEAT", 25)
        if must_sell or day >= 28 or p >= BASE_PRICES["WHEAT"] * SELL_THRESHOLD.get("WHEAT", 0.70):
            market.append(["SELL", "WHEAT", wheat_sellable])

    # All other produce
    for prod in ["MILK", "EGG", "WOOL", "FERTILIZER", "CARROT", "STRAWBERRY", "MELON", "TOMATO"]:
        cnt = shed.get(prod, 0)
        if cnt == 0:
            continue
        p = prices.get(prod, 0)
        base = BASE_PRICES.get(prod, 50)
        threshold = SELL_THRESHOLD.get(prod, 0.70)

        # Extra caution for melon if opponent is flooding market
        if prod == "MELON" and opp_has_many_melons and not (must_sell or day >= 28):
            if p >= base * 0.85:  # higher bar when opponent has lots of melons
                market.append(["SELL", prod, cnt])
        elif must_sell or day >= 28 or p >= base * threshold:
            market.append(["SELL", prod, cnt])

    # ------------------------------------------------------------------
    # 9. WORKER DISPATCHER - CENTRAL JOB QUEUE
    # ------------------------------------------------------------------
    # --- Build job list for all tiles ---
    jobs = []   # (priority, x, y, action_type)
    claimed_plant_tiles = set()  # prevent seed race condition

    # Animal jobs (highest priority - animals must be fed daily or escape!)
    for (ax, ay), atype in zip(PASTURE_TILES, ANIMAL_TYPES):
        tile = board[ay][ax]
        structure_type = STRUCTURE[atype]
        if tile is None:
            # Need to build structure
            build_action = "BUILD_COOP" if structure_type == "COOP" else "BUILD_PASTURE"
            jobs.append((100, ax, ay, build_action, atype))
        elif isinstance(tile, dict) and tile.get("animal") is None:
            # Structure built, needs animal placed (pickup from shed -> walk -> place)
            jobs.append((99, ax, ay, "PLACE_ANIMAL", atype))
        elif isinstance(tile, dict) and tile.get("animal") == atype:
            # Animal is placed, do daily care
            if not tile.get("fed_today", False):
                jobs.append((95, ax, ay, "FEED", atype))
            if not tile.get("cared_today", False):
                jobs.append((85, ax, ay, "CARE", atype))
            if tile.get("yield_units", 0) > 0:
                jobs.append((80, ax, ay, "HARVEST", atype))
            if tile.get("fertilizer_available", False):
                jobs.append((70, ax, ay, "COLLECT_FERTILIZER", atype))

    # Crop jobs
    for (cx, cy) in active_crop_tiles:
        tile = board[cy][cx]
        if isinstance(tile, dict):
            kind = tile.get("kind")
            if kind == "WEED":
                jobs.append((60, cx, cy, "DIG", None))
            elif kind == "PLANT":
                crop = tile["crop"]
                age = day - tile["planted_day"]
                max_age = {
                    "MELON": 10, "CARROT": 3, "WHEAT": 4,
                    "STRAWBERRY": -1, "TOMATO": -1  # ongoing: check yield_units
                }.get(crop, 4)

                # For ongoing crops (strawberry/tomato), harvest when yield_units > 0
                if crop in ("STRAWBERRY", "TOMATO"):
                    if tile.get("yield_units", 0) > 0:
                        jobs.append((55, cx, cy, "HARVEST", crop))
                    elif not tile.get("watered_today", False):
                        jobs.append((50, cx, cy, "WATER", crop))
                    # FERTILIZE ongoing crops on production days for 2x yield
                    elif tile.get("fertilized_until_day", -1) < day and shed.get("FERTILIZER", 0) > 0:
                        jobs.append((45, cx, cy, "FERTILIZE", crop))
                else:
                    # One-time crops
                    if age >= max_age or (day >= 29 and age >= 2):
                        jobs.append((55, cx, cy, "HARVEST", crop))
                    elif not tile.get("watered_today", False):
                        jobs.append((50, cx, cy, "WATER", crop))
                    # FERTILIZE one-time crops during bonus window for +50% yield
                    elif (tile.get("fertilized_until_day", -1) < day
                          and shed.get("FERTILIZER", 0) > 0
                          and age >= (max_age // 2)
                          and age < max_age):
                        jobs.append((45, cx, cy, "FERTILIZE", crop))
        elif tile is None and day <= 26:
            # Determine what to plant here
            if (cx, cy) in STRAWBERRY_TILES and day <= 5 and seeds.get("STRAWBERRY", 0) > 0:
                crop_to_plant = "STRAWBERRY"
            elif (cx, cy) in MELON_TILES and day <= 19 and seeds.get("MELON", 0) > 0:
                crop_to_plant = "MELON"
            elif carrot_priority and seeds.get("CARROT", 0) > 0:
                crop_to_plant = "CARROT"
            elif seeds.get("CARROT", 0) > 0 and (cx, cy) not in STRAWBERRY_TILES and (cx, cy) not in MELON_TILES:
                crop_to_plant = "CARROT"
            elif seeds.get("WHEAT", 0) > 0:
                crop_to_plant = "WHEAT"
            else:
                crop_to_plant = None
            if crop_to_plant:
                jobs.append((30, cx, cy, "PLANT", crop_to_plant))
                claimed_plant_tiles.add((cx, cy))

    # Sort by priority descending
    jobs.sort(key=lambda j: j[0], reverse=True)

    # --- Assign jobs to workers ---
    units = [me["farmer"]] + me["hands"]
    n_units = len(units)
    used_job_idx = set()
    unit_assignments = {}

    for u_idx in range(n_units):
        ux, uy = units[u_idx]
        best_score = None
        best_j_idx = None
        for j_idx, job in enumerate(jobs):
            if j_idx in used_job_idx:
                continue
            pri, jx, jy, jtype, jarg = job
            dist = abs(jx - ux) + abs(jy - uy)
            # Score: higher priority = lower score value = picked first
            score = dist - pri * 3
            if best_score is None or score < best_score:
                best_score = score
                best_j_idx = j_idx
        if best_j_idx is not None:
            used_job_idx.add(best_j_idx)
            unit_assignments[u_idx] = jobs[best_j_idx]

    # --- Execute assigned job for a unit ---
    def execute(u_idx, ux, uy):
        job = unit_assignments.get(u_idx)
        inv = inventories[u_idx] if u_idx < len(inventories) else {}

        if job is None:
            return ["PASS"]

        pri, jx, jy, jtype, jarg = job
        tile = board[uy][ux]
        on_job_tile = (ux == jx and uy == jy)
        shed_tiles = [(4, 4), (5, 4), (4, 5), (5, 5)]
        at_shed = (ux, uy) in shed_tiles

        # --- EXECUTE ON TILE ---
        if on_job_tile:
            if jtype == "BUILD_COOP":
                return ["BUILD_COOP"]
            if jtype == "BUILD_PASTURE":
                return ["BUILD_PASTURE"]
            if jtype == "PLACE_ANIMAL":
                if inv.get(jarg, 0) > 0:
                    return ["PLACE", jarg, 1]
                # Need to pick up from shed first
                if shed.get(jarg, 0) > 0 and at_shed:
                    return ["PICKUP", jarg, 1]
                # Go to shed to pickup
                if not at_shed:
                    return move_toward(ux, uy, 4, 4)
                return ["PICKUP", jarg, 1]
            if jtype == "FEED":
                if inv.get("WHEAT", 0) > 0:
                    return ["FEED"]
                # Need wheat from shed
                if shed.get("WHEAT", 0) > 0 and at_shed:
                    return ["PICKUP", "WHEAT", 1]
                if not at_shed:
                    return move_toward(ux, uy, 4, 4)
                return ["PASS"]
            if jtype == "CARE":
                return ["CARE"]
            if jtype == "COLLECT_FERTILIZER":
                if inv and sum(inv.values()) >= 5:
                    # Inventory getting full, drop at shed first
                    if at_shed:
                        return ["DROP"]
                    return move_toward(ux, uy, 4, 4)
                return ["COLLECT_FERTILIZER"]
            if jtype == "HARVEST":
                return ["HARVEST"]
            if jtype == "DIG":
                return ["DIG"]
            if jtype == "WATER":
                return ["WATER"]
            if jtype == "FERTILIZE":
                # Need fertilizer in inventory
                if inv.get("FERTILIZER", 0) > 0:
                    return ["FERTILIZE"]
                if shed.get("FERTILIZER", 0) > 0 and at_shed:
                    return ["PICKUP", "FERTILIZER", 1]
                if not at_shed:
                    return move_toward(ux, uy, 4, 4)
                return ["PASS"]
            if jtype == "PLANT":
                if seeds.get(jarg, 0) > 0:
                    return ["PLANT", jarg]
                return ["PASS"]

        # --- MOVE TOWARD JOB TILE ---
        # Special: if FEED but no wheat in inventory, go to shed first
        if jtype == "FEED" and inv.get("WHEAT", 0) == 0:
            if shed.get("WHEAT", 0) > 0:
                if not at_shed:
                    return move_toward(ux, uy, 4, 4)
                return ["PICKUP", "WHEAT", 1]
            return ["PASS"]

        # Special: PLACE_ANIMAL - need to go pickup first
        if jtype == "PLACE_ANIMAL" and inv.get(jarg, 0) == 0:
            if shed.get(jarg, 0) > 0:
                if not at_shed:
                    return move_toward(ux, uy, 4, 4)
                return ["PICKUP", jarg, 1]
            return ["PASS"]

        # Special: FERTILIZE - need to go pickup fertilizer first
        if jtype == "FERTILIZE" and inv.get("FERTILIZER", 0) == 0:
            if shed.get("FERTILIZER", 0) > 0:
                if not at_shed:
                    return move_toward(ux, uy, 4, 4)
                return ["PICKUP", "FERTILIZER", 1]
            return ["PASS"]

        return move_toward(ux, uy, jx, jy)

    def move_toward(ux, uy, tx, ty):
        """Step toward (tx, ty) from (ux, uy), x-axis first."""
        if tx < ux: return ["WEST"]
        if tx > ux: return ["EAST"]
        if ty < uy: return ["NORTH"]
        if ty > uy: return ["SOUTH"]
        return ["PASS"]

    # ------------------------------------------------------------------
    # 10. GENERATE FINAL ACTIONS
    # ------------------------------------------------------------------
    farmer_act = execute(0, me["farmer"][0], me["farmer"][1])
    hands_acts = []
    for h_idx, hpos in enumerate(me["hands"]):
        # Hand spawn correction: hand 0 spawns at (5,4) if NE locked - move WEST
        hx, hy = hpos
        act = execute(h_idx + 1, hx, hy)
        hands_acts.append(act)

    return {"farmer": farmer_act, "hands": hands_acts, "market": market}