PASTURE_TILE = (3, 4)
CROP_TILES = [
    (4, 4), (4, 3), (4, 2), (4, 1),
    (3, 3), (3, 2), (3, 1),
    (2, 4), (2, 3), (2, 2), (2, 1),
    (1, 4), (1, 3), (1, 2), (1, 1),
    (0, 4), (0, 3)
]
MELON_TILES = [(4, 1), (3, 1), (2, 1), (1, 1)]

def agent(obs):
    """
    Ultimate Version 5: Livestock (Cow), Coordinated Job Dispatcher,
    Multi-Crop Portfolio & Market Price Defense.
    """
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    market_info = obs["market"]
    prices = market_info["prices"]
    hour = obs["hour"]
    day = obs["day"]
    money = me["money"]
    board_tiles = me["tiles"]
    
    market = []
    
    # HIRE 2 WORKERS DAILY (Costs $1 + $1 = $2 total)
    if hour == 0 and money >= 50:
        needed_hires = 2 - me["hires_today"]
        for _ in range(needed_hires):
            market.append(["HIRE"])
            
    # LIVESTOCK PURCHASE (Day 0) & FEED RESUPPLY
    pasture_tile_state = board_tiles[PASTURE_TILE[1]][PASTURE_TILE[0]]
    if day == 0 and hour == 0:
        market.append(["BUY_ANIMAL", "COW", 1])
        market.append(["BUY_PRODUCT", "WHEAT", 15])  
        money -= 400 + 15 * 25
        
    # Maintain at least 5 wheat for cow feed
    total_wheat = private["shed"].get("WHEAT", 0) + sum(inv.get("WHEAT", 0) for inv in private["inventories"])
    if total_wheat < 5 and money >= 50 and day <= 27:
        market.append(["BUY_PRODUCT", "WHEAT", 5])
        money -= 5 * prices.get("WHEAT", 25)

    # SEED PURCHASES
    if day <= 26:
        empty_crops = sum(1 for (x, y) in CROP_TILES if board_tiles[y][x] is None)
        seeds_held = sum(private["seeds"].values())
        needed = max(0, empty_crops - seeds_held)
        
        # Melons (up to 4) - only when price is strong
        if day <= 19 and needed > 0 and prices.get("MELON", 250) >= 120 and money >= 80:
            m_needed = min(4, needed)
            m_buy = min(m_needed, int(money // 80))
            if m_buy > 0:
                market.append(["BUY_SEED", "MELON", m_buy])
                money -= m_buy * 80
                needed -= m_buy
                
        # Carrots (fast 3-day turnaround) & Wheat
        if needed > 0 and money >= 20:
            c_buy = min(needed // 2, int(money // 20))
            if c_buy > 0:
                market.append(["BUY_SEED", "CARROT", c_buy])
                money -= c_buy * 20
                needed -= c_buy
            w_buy = min(needed, int(money // 10))
            if w_buy > 0:
                market.append(["BUY_SEED", "WHEAT", w_buy])
                money -= w_buy * 10
                
    # PRICE PROTECTED SELLING
    BASE = {"MILK": 160, "FERTILIZER": 100, "MELON": 250, "CARROT": 35, "WHEAT": 25}
    wheat_in_shed = private["shed"].get("WHEAT", 0)
    wheat_to_sell = max(0, wheat_in_shed - 3)
    if wheat_to_sell > 0 and (prices.get("WHEAT", 25) >= 18 or day >= 28):
        market.append(["SELL", "WHEAT", wheat_to_sell])
        
    for prod in ["MILK", "FERTILIZER", "MELON", "CARROT"]:
        cnt = private["shed"].get(prod, 0)
        if cnt > 0:
            p = prices.get(prod, 0)
            base = BASE.get(prod, 50)
            if p >= base * 0.70 or day >= 28:
                market.append(["SELL", prod, cnt])
                
    # WORKER ACTIONS & DISPATCHER
    farmer_inv = private["inventories"][0]
    fx, fy = me["farmer"]
    
    # Priority A: Farmer manages the Cow in the morning
    farmer_act = None
    if pasture_tile_state is None:
        if (fx, fy) != PASTURE_TILE:
            farmer_act = ["WEST"] if fx > PASTURE_TILE[0] else ["EAST"]
        else:
            farmer_act = ["BUILD_PASTURE"]
    elif isinstance(pasture_tile_state, dict) and pasture_tile_state.get("animal") is None:
        if farmer_inv.get("COW", 0) > 0:
            if (fx, fy) != PASTURE_TILE: farmer_act = ["WEST"]
            else: farmer_act = ["PLACE", "COW", 1]
        elif private["shed"].get("COW", 0) > 0:
            if (fx, fy) != (4, 4): farmer_act = ["EAST"]
            else: farmer_act = ["PICKUP", "COW", 1]
    elif isinstance(pasture_tile_state, dict) and pasture_tile_state.get("animal") == "COW":
        if not pasture_tile_state.get("fed_today", False):
            if farmer_inv.get("WHEAT", 0) == 0:
                if (fx, fy) != (4, 4): farmer_act = ["EAST"]
                else: farmer_act = ["PICKUP", "WHEAT", 1]
            else:
                if (fx, fy) != PASTURE_TILE: farmer_act = ["WEST"]
                else: farmer_act = ["FEED"]
        elif not pasture_tile_state.get("cared_today", False):
            if (fx, fy) != PASTURE_TILE: farmer_act = ["WEST"]
            else: farmer_act = ["CARE"]
        elif pasture_tile_state.get("yield_units", 0) > 0:
            if (fx, fy) != PASTURE_TILE: farmer_act = ["WEST"]
            else: farmer_act = ["HARVEST"]
        elif pasture_tile_state.get("fertilizer_available", False):
            if (fx, fy) != PASTURE_TILE: farmer_act = ["WEST"]
            else: farmer_act = ["COLLECT_FERTILIZER"]
            
    # Priority B: Crop tasks across 16 crop tiles
    crop_jobs = []
    for (x, y) in CROP_TILES:
        t = board_tiles[y][x]
        if isinstance(t, dict):
            if t.get("kind") == "WEED":
                crop_jobs.append((x, y, "DIG", 10))
            elif t.get("kind") == "PLANT":
                crop = t["crop"]
                age = day - t["planted_day"]
                max_age = 10 if crop == "MELON" else (3 if crop == "CARROT" else 4)
                if age >= max_age or (day >= 29 and age >= 2):
                    crop_jobs.append((x, y, "HARVEST", 8))
                elif not t["watered_today"]:
                    crop_jobs.append((x, y, "WATER", 6))
        elif t is None:
            if day <= 26 and sum(private["seeds"].values()) > 0:
                crop_jobs.append((x, y, "PLANT", 4))
                
    crop_jobs.sort(key=lambda j: j[3], reverse=True)
    
    # Priority C: Assign unique, non-overlapping jobs to available workers
    used_jobs = set()
    def get_crop_action(ux, uy):
        t = board_tiles[uy][ux]
        if (ux, uy) in CROP_TILES:
            if isinstance(t, dict) and t.get("kind") == "WEED": return ["DIG"]
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                crop = t["crop"]
                age = day - t["planted_day"]
                max_age = 10 if crop == "MELON" else (3 if crop == "CARROT" else 4)
                if age >= max_age or (day >= 29 and age >= 2): return ["HARVEST"]
                if not t["watered_today"]: return ["WATER"]
            elif t is None:
                if (ux, uy) in MELON_TILES and day <= 19 and private["seeds"].get("MELON", 0) > 0:
                    return ["PLANT", "MELON"]
                elif private["seeds"].get("CARROT", 0) > 0: return ["PLANT", "CARROT"]
                elif private["seeds"].get("WHEAT", 0) > 0: return ["PLANT", "WHEAT"]
                
        # Find best nearest unassigned job
        best_j = None
        best_dist = 999
        for j_idx, job in enumerate(crop_jobs):
            if j_idx in used_jobs: continue
            jx, jy, _, pri = job
            d = abs(jx - ux) + abs(jy - uy) - pri * 2
            if d < best_dist:
                best_dist = d
                best_j = (j_idx, job)
        if best_j:
            used_jobs.add(best_j[0])
            jx, jy, _, _ = best_j[1]
            if jx < ux: return ["WEST"]
            if jx > ux: return ["EAST"]
            if jy < uy: return ["NORTH"]
            if jy > uy: return ["SOUTH"]
        return ["PASS"]

    final_farmer_act = farmer_act if farmer_act is not None else get_crop_action(fx, fy)
    hands_acts = [get_crop_action(hpos[0], hpos[1]) for hpos in me["hands"]]
    
    return {"farmer": final_farmer_act, "hands": hands_acts, "market": market}