PLOT = [(4, 4), (4, 3), (3, 4), (3, 3), (4, 2), (3, 2)]

def agent(obs):
    """
    Version 2: Multi-tile Moving Farmer with Max-Yield Harvesting
    """
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    fx, fy = me["farmer"]
    
    market = []
    seeds = private["seeds"].get("WHEAT", 0)
    
    # MARKET LOGIC
    empty_plot_tiles = sum(1 for (x, y) in PLOT if me["tiles"][y][x] is None)
    needed_seeds = max(0, empty_plot_tiles - seeds)
    
    if needed_seeds > 0 and me["money"] >= 10:
        buy_qty = min(needed_seeds, int(me["money"] // 10))
        if buy_qty > 0:
            market.append(["BUY_SEED", "WHEAT", buy_qty])
            
    wheat_in_shed = private["shed"].get("WHEAT", 0)
    if wheat_in_shed > 0:
        market.append(["SELL", "WHEAT", wheat_in_shed])
        
    current_tile = me["tiles"][fy][fx]
    
    # IMMEDIATE ACTION ON CURRENT TILE
    if (fx, fy) in PLOT:
        if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT":
            crop_age = obs["day"] - current_tile["planted_day"]
            
            if crop_age >= 4:
                return {"farmer": ["HARVEST"], "hands": [], "market": market}
            if not current_tile["watered_today"]:
                return {"farmer": ["WATER"], "hands": [], "market": market}
        elif current_tile is None and seeds > 0:
            return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": market}
            
    # FIND NEAREST PLOT TILE THAT NEEDS ATTENTION
    target = None
    for (x, y) in PLOT:
        t = me["tiles"][y][x]
        if isinstance(t, dict) and t.get("kind") == "PLANT":
            crop_age = obs["day"] - t["planted_day"]
            if crop_age >= 4 or not t["watered_today"]:
                target = (x, y)
                break
        elif t is None and seeds > 0:
            target = (x, y)
            break
            
    # MOVE TOWARDS TARGET TILE
    if target:
        tx, ty = target
        if tx < fx:
            return {"farmer": ["WEST"], "hands": [], "market": market}
        elif tx > fx:
            return {"farmer": ["EAST"], "hands": [], "market": market}
        elif ty < fy:
            return {"farmer": ["NORTH"], "hands": [], "market": market}
        elif ty > fy:
            return {"farmer": ["SOUTH"], "hands": [], "market": market}
       
    return {"farmer": ["PASS"], "hands": [], "market": market}