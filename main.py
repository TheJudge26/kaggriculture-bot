def agent(obs):
    """
    Starter baseline: The Wheat Farming Loop
    """
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    
    # Farmer position and tile underneath the farmer
    fx, fy = me["farmer"]
    tile = me["tiles"][fy][fx]

    market = []

    # Market logic
    if private["seeds"].get("WHEAT", 0) == 0 and me["money"] >= 10:
        market.append(["BUY_SEED", "WHEAT", 1])

    wheat_in_shed = private["shed"].get("WHEAT", 0)
    if wheat_in_shed > 0:
        market.append(["SELL", "WHEAT", wheat_in_shed])

    # Farmer tile actions
    if tile is None and private["seeds"].get("WHEAT", 0) > 0:
        return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": market}

    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop_age = obs["day"] - tile["planted_day"]

        if crop_age >= 2:
            return {"farmer": ["HARVEST"], "hands": [], "market": market}

        if not tile["watered_today"]:
            return {"farmer": ["WATER"], "hands": [], "market": market}

    return {"farmer": ["PASS"], "hands": [], "market": market}