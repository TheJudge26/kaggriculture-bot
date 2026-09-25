WHEAT_PLOT = [
    (4, 4), (4, 3), (4, 2),
    (3, 4), (3, 3), (3, 2),
    (2, 4), (2, 3), (2, 2),
    (1, 4), (1, 3), (1, 2),
    (0, 4), (0, 3)
]
MELON_PLOT = [(4, 1), (3, 1), (2, 1), (1, 1)]
ALL_PLOT = WHEAT_PLOT + MELON_PLOT

def agent(obs):
    """
    Version 4: 18-Tile Plantation with 2 Helpers, Weed Digging & Seed Cutoffs
    """
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    hour = obs["hour"]
    day = obs["day"]
    money = me["money"]
    
    market = []
    
    # HIRE 2 HANDS EVERY MORNING (Costs only $1 + $1 = $2 total!)
    if hour == 0 and money >= 50:
        needed_hires = 2 - me["hires_today"]
        for _ in range(needed_hires):
            market.append(["HIRE"])
            
    # SMART SEED PURCHASES

    if day <= 26:
        empty_wheat = sum(1 for (x, y) in WHEAT_PLOT if me["tiles"][y][x] is None)
        wheat_seeds = private["seeds"].get("WHEAT", 0)
        needed_wheat = max(0, empty_wheat - wheat_seeds)
        if needed_wheat > 0 and money >= 10:
            qty = min(needed_wheat, int(money // 10))
            if qty > 0:
                market.append(["BUY_SEED", "WHEAT", qty])
                money -= qty * 10

    # Stop buying melons after day 19 (needs 10 full days to mature)
    if day <= 19:
        empty_melon = sum(1 for (x, y) in MELON_PLOT if me["tiles"][y][x] is None)
        melon_seeds = private["seeds"].get("MELON", 0)
        needed_melon = max(0, empty_melon - melon_seeds)
        if needed_melon > 0 and money >= 80:
            qty = min(needed_melon, int(money // 80))
            if qty > 0:
                market.append(["BUY_SEED", "MELON", qty])
                money -= qty * 80
                
    # SELL ALL PRODUCE SITTING IN SHED
    for prod in ["WHEAT", "MELON"]:
        cnt = private["shed"].get(prod, 0)
        if cnt > 0:
            market.append(["SELL", prod, cnt])
            
    # WORKER LOGIC (Farmer + 2 Helpers)
    def get_unit_action(pos, preferred_plot, preferred_crop):
        ux, uy = pos
        tile = me["tiles"][uy][ux]
        
        if (ux, uy) in ALL_PLOT:
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                return ["DIG"]
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crop = tile["crop"]
                age = day - tile["planted_day"]
                max_age = 10 if crop == "MELON" else 4
                if age >= max_age or (day >= 29 and age >= (10 if crop == "MELON" else 2)):
                    return ["HARVEST"]
                if not tile["watered_today"]:
                    return ["WATER"]
            elif tile is None:
                if (ux, uy) in MELON_PLOT and day <= 19 and private["seeds"].get("MELON", 0) > 0:
                    return ["PLANT", "MELON"]
                elif day <= 26 and private["seeds"].get("WHEAT", 0) > 0:
                    return ["PLANT", "WHEAT"]
                    
        target = None
        for p in [preferred_plot, ALL_PLOT]:
            for (x, y) in p:
                t = me["tiles"][y][x]
                if isinstance(t, dict):
                    if t.get("kind") == "WEED":
                        target = (x, y)
                        break
                    elif t.get("kind") == "PLANT":
                        crop = t["crop"]
                        age = day - t["planted_day"]
                        max_age = 10 if crop == "MELON" else 4
                        if age >= max_age or not t["watered_today"]:
                            target = (x, y)
                            break
                elif t is None:
                    if (x, y) in MELON_PLOT and day <= 19 and private["seeds"].get("MELON", 0) > 0:
                        target = (x, y)
                        break
                    elif day <= 26 and private["seeds"].get("WHEAT", 0) > 0:
                        target = (x, y)
                        break
            if target:
                break
                
        if target:
            tx, ty = target
            if tx < ux: return ["WEST"]
            if tx > ux: return ["EAST"]
            if ty < uy: return ["NORTH"]
            if ty > uy: return ["SOUTH"]
            
        return ["PASS"]

    farmer_act = get_unit_action(me["farmer"], WHEAT_PLOT, "WHEAT")
    
    hands_acts = []
    for i, hpos in enumerate(me["hands"]):
        pref = MELON_PLOT if i == 0 else WHEAT_PLOT
        crop = "MELON" if i == 0 else "WHEAT"
        h_act = get_unit_action(hpos, pref, crop)
        hands_acts.append(h_act)
        
    return {"farmer": farmer_act, "hands": hands_acts, "market": market}