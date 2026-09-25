WHEAT_PLOT = [(4, 4), (4, 3), (3, 4), (3, 3), (4, 2), (3, 2), (2, 4), (2, 3), (2, 2)]
MELON_PLOT = [(4, 1), (3, 1), (2, 1)]

def agent(obs):
    """
    Version 3: Multi-worker farm with Wheat & Melons
    """
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    hour = obs["hour"]
    day = obs["day"]
    money = me["money"]
    
    market = []
    
    # HIRE 1 FARM HAND EVERY MORNING (Costs only 1 coin!)
    if hour == 0 and me["hires_today"] == 0 and money >= 50:
        market.append(["HIRE"])
        money -= 1
        
    # SEED PURCHASES
    empty_wheat = sum(1 for (x, y) in WHEAT_PLOT if me["tiles"][y][x] is None)
    wheat_seeds = private["seeds"].get("WHEAT", 0)
    needed_wheat = max(0, empty_wheat - wheat_seeds)
    if needed_wheat > 0 and money >= 10:
        qty = min(needed_wheat, int(money // 10))
        if qty > 0:
            market.append(["BUY_SEED", "WHEAT", qty])
            money -= qty * 10
            
    # Melon seeds for empty melon plot tiles (only plant if day <= 19 so they mature before day 30)
    if day <= 19:
        empty_melon = sum(1 for (x, y) in MELON_PLOT if me["tiles"][y][x] is None)
        melon_seeds = private["seeds"].get("MELON", 0)
        needed_melon = max(0, empty_melon - melon_seeds)
        if needed_melon > 0 and money >= 80:
            qty = min(needed_melon, int(money // 80))
            if qty > 0:
                market.append(["BUY_SEED", "MELON", qty])
                money -= qty * 80
                
    # SELL ALL HARVESTED PRODUCE IN SHED
    for prod in ["WHEAT", "MELON"]:
        cnt = private["shed"].get(prod, 0)
        if cnt > 0:
            market.append(["SELL", prod, cnt])
            
    #  WORKER AI LOGIC (Used by both Farmer and Farm Hand)
    def get_unit_action(pos, assigned_plot, preferred_crop):
        ux, uy = pos
        tile = me["tiles"][uy][ux]
        
        if (ux, uy) in assigned_plot:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crop = tile["crop"]
                age = day - tile["planted_day"]
                max_age = 10 if crop == "MELON" else 4
                if age >= max_age or (day >= 29 and age >= (10 if crop == "MELON" else 2)):
                    return ["HARVEST"]
                if not tile["watered_today"]:
                    return ["WATER"]
            elif tile is None:
                if private["seeds"].get(preferred_crop, 0) > 0:
                    return ["PLANT", preferred_crop]
                elif preferred_crop == "MELON" and private["seeds"].get("WHEAT", 0) > 0:
                    return ["PLANT", "WHEAT"]
                    
        target = None
        for (x, y) in assigned_plot:
            t = me["tiles"][y][x]
            if isinstance(t, dict) and t.get("kind") == "PLANT":
                crop = t["crop"]
                age = day - t["planted_day"]
                max_age = 10 if crop == "MELON" else 4
                if age >= max_age or not t["watered_today"]:
                    target = (x, y)
                    break
            elif t is None and (private["seeds"].get(preferred_crop, 0) > 0 or private["seeds"].get("WHEAT", 0) > 0):
                target = (x, y)
                break
                
        if target:
            tx, ty = target
            if tx < ux: return ["WEST"]
            if tx > ux: return ["EAST"]
            if ty < uy: return ["NORTH"]
            if ty > uy: return ["SOUTH"]
            
        return ["PASS"]

    farmer_act = get_unit_action(me["farmer"], WHEAT_PLOT + MELON_PLOT, "WHEAT")
    
    hands_acts = []
    for hpos in me["hands"]:
        h_act = get_unit_action(hpos, MELON_PLOT + WHEAT_PLOT, "MELON")
        hands_acts.append(h_act)
        
    return {"farmer": farmer_act, "hands": hands_acts, "market": market}