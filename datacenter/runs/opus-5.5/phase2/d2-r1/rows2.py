exec(open("/home/user/opus55poc/datacenter/runs/opus-5.5/phase2/d2-r1/design.py").read().replace(
    '("y", 14500, "E", 1000, 18650, []),',
    '("y", 14500, "E", 1000, 12000, []),\n    ("x", 12900, "N", 14500, 18800, []),\n    ("x", 15300, "S", 14500, 18800, []),\n    ("y", 15700, "E", 17400, 18600, []),'))
