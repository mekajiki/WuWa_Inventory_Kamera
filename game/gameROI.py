class Coordinates:
    def __init__(self, x: int | float = 0, y: int | float = 0, w: int | float = 0, h: int | float = 0):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def __repr__(self):
        return f"Coordinates(x={self.x}, y={self.y}, w={self.w}, h={self.h})"

    def __reduce__(self):
        return (self.__class__, (self.x, self.y, self.w, self.h))

# How UI elements are anchored horizontally on screens wider than 16:9
# (e.g. 21:9 / 32:13.5 ultrawide). The game scales its UI by height and pins
# panels to the screen edges. Longest-prefix match against the table path;
# anything not listed is left-anchored (x scales with height, like y).
ULTRAWIDE_ANCHORS = {
    'shell': 'right',
    'characters.rightSide': 'right',
    # the chain arc and echo slots wrap around the centered character model
    'characters.chainPositions': 'center',
    'characters.equipSlots': 'center',
    'characters.echoPanel': 'right',
    'characters.echoCost': 'right',
    'characters.echoLevel': 'right',
    'characters.skillStrip': 'center',
    'characters.skillColumns': 'center',
    'items.info': 'right',
    'items.description': 'right',
    'weapons.name': 'right',
    'weapons.value': 'right',
    'weapons.level': 'right',
    'weapons.rank': 'right',
    'echoes.panelLeft': 'right',
    'echoes.name': 'right',
    'echoes.level': 'right',
    'echoes.cost': 'right',
    'echoes.rarityLine': 'right',
    'echoes.statsArea': 'right',
    'echoes.panelScroll': 'right',
    'achievements.status': 'right',
    'achievements.achievementsButton': 'right',
}

COORDINATES = {
    (16, 9): {
        (1920, 1080): {
            "terminal": Coordinates(140, 40, 150, 40),
            "shell": Coordinates(1255, 38, 165, 50),
            "offsets": {
                "page": Coordinates(16, 24)
            },
            "scroll": {
                "page": Coordinates(y=-31.25),
                # ~3 list entries per pass, leaving generous overlap with the
                # previous page so the duplicate-skip logic never misses anyone
                "characters": Coordinates(y=-15),
                "sonata": Coordinates(y=70)
            },
            "scrapers": {
                "weapons": Coordinates(81.5, 191.5),
                "echoes": Coordinates(81.5, 326.5),
                "devItems": Coordinates(81.5, 596.5),
                "resources": Coordinates(81.5, 731.5),
            },
            "items": {
                "start": Coordinates(205, 122, 151, 181),
                "info": Coordinates(1296, 114, 558, 278),
                "description": Coordinates(1296, 114, 558, 820)
            },
            "weapons": {
                "page": Coordinates(200, 50, 130, 40),
                "start": Coordinates(205, 122, 151, 181),
                "name": Coordinates(1305, 116, 545, 55),
                "value": Coordinates(1655, 320, 190, 40),
                "level": Coordinates(1660, 235, 180, 45),
                "rank": Coordinates(1300, 530, 115, 50)
            },
            "echoes": {
                # 3.6 bag layout: cell "+N" label origin and pitch (x0, y0,
                # pitchX, pitchY); column count is derived from panelLeft
                "grid": Coordinates(307, 315.5, 188.85, 226.5),
                "panelLeft": Coordinates(x=1255),
                "name": Coordinates(1325, 118, 285, 50),
                "level": Coordinates(1325, 192, 130, 42),
                "cost": Coordinates(1400, 244, 140, 40),
                "rarityLine": Coordinates(1330, 402, 480, 16),
                "statsArea": Coordinates(1325, 440, 560, 470),
                "panelScroll": Coordinates(1600, 700),
                "sortButton": Coordinates(443, 988),
                "sortLevel": Coordinates(358, 625),
                "sortDirection": Coordinates(672, 988)
            },
            "achievements": {
                "status": Coordinates(1579, 230, 256, 65),
                "searchBar": Coordinates(388, 149),
                "searchButton": Coordinates(629, 149),
                "achievementsButton": Coordinates(1674, 790),
                "achievementsTab": Coordinates(835, 570),
            },
            "characters": {
                # Layout measured against the 3.6 client (2026-08). The skill
                # screen now shows levels directly on the tree, so skills and
                # chains are read from screenshots without clicking nodes.
                "offsets": {
                    "leftSide": Coordinates(y=136),
                    "rightSide": Coordinates(y=134)
                },
                "leftSide": Coordinates(82, 191),
                "rightSide": Coordinates(1819, 221),
                "resonatorName": Coordinates(200, 200, 300, 40),
                "resonatorLevel": Coordinates(200, 254, 150, 36),
                # aggregate stat rows (HP through crit damage) on the status
                # section — the ground truth the planners compare against
                "totalStats": Coordinates(180, 330, 400, 280),
                "weaponName": Coordinates(205, 204, 330, 38),
                "weaponLevel": Coordinates(200, 266, 150, 34),
                "weaponRank": Coordinates(210, 428, 120, 32),
                # One horizontal band containing all five "Lv.X/10" labels;
                # each label is assigned to the nearest column center.
                "skillStrip": Coordinates(300, 750, 1320, 280),
                "skillColumns": [
                    Coordinates(x=466),
                    Coordinates(x=691),
                    Coordinates(x=963),
                    Coordinates(x=1230),
                    Coordinates(x=1453)
                ],
                "chainPositions": [
                    Coordinates(1545, 282),
                    Coordinates(1519, 508),
                    Coordinates(1438, 680),
                    Coordinates(1309, 824),
                    Coordinates(1146, 924),
                    Coordinates(943, 963)
                ],
                # equipped echo slots on the echo section (top to bottom),
                # and the detail panel of the swap screen a slot click opens
                "equipSlots": [
                    Coordinates(1460, 275),
                    Coordinates(1527, 495),
                    Coordinates(1517, 635),
                    Coordinates(1487, 775),
                    Coordinates(1415, 905)
                ],
                "echoPanel": Coordinates(1500, 140, 360, 820),
                "echoCost": Coordinates(1500, 185, 150, 34),
                "echoLevel": Coordinates(1765, 140, 100, 42)
            }
        }
    },
    (16, 10): {
        (1680, 1050): {
            "terminal": Coordinates(125, 32, 150, 40),
            "shell": Coordinates(1100, 35, 145, 40),
            "offsets": {
                "page": Coordinates(16, 24),
                "characters": Coordinates(y=-56),
                "sonata": Coordinates(y=70),
            },
            "scroll": {
                "page": Coordinates(y=-31.70),
                "characters": Coordinates(y=-30),
                "sonata": Coordinates(y=70)
            },
            "scrapers": {
                "weapons": Coordinates(71.5, 167),
                "echoes": Coordinates(71.5, 285),
                "devItems": Coordinates(71.5, 521),
                "resources": Coordinates(71.5, 639),
            },
            "items": {
                "start": Coordinates(180, 104, 130, 162),
                "info": Coordinates(1136, 154, 485, 240),
                "description": Coordinates(1136, 154, 485, 715)
            },
            "weapons": {
                "page": Coordinates(175, 40, 130, 40),
                "start": Coordinates(180, 104, 130, 162),
                "name": Coordinates(1140, 152, 480, 50),
                "value": Coordinates(1430, 330, 190, 40),
                "level": Coordinates(1435, 255, 180, 45),
                "rank": Coordinates(1135, 510, 100, 50)
            },
            "echoes": {
                "grid": Coordinates(269, 307, 165, 220),
                "panelLeft": Coordinates(x=1098),
                "name": Coordinates(1159, 115, 249, 49),
                "level": Coordinates(1159, 187, 114, 41),
                "cost": Coordinates(1225, 237, 123, 39),
                "rarityLine": Coordinates(1164, 391, 420, 16),
                "statsArea": Coordinates(1159, 428, 490, 457),
                "panelScroll": Coordinates(1400, 680),
                "sortButton": Coordinates(388, 960),
                "sortLevel": Coordinates(313, 608),
                "sortDirection": Coordinates(588, 960)
            },
            "achievements": {
                "status": Coordinates(1579, 197, 256, 65),
                "searchBar": Coordinates(388, 129),
                "searchButton": Coordinates(550, 129),
                "achievementsButton": Coordinates(1465, 690),
                "achievementsTab": Coordinates(735, 570),
            },
            "characters": {
                # Rough 16:10 projection of the 3.6 16:9 layout (untested).
                "offsets": {
                    "leftSide": Coordinates(y=119),
                    "rightSide": Coordinates(y=130)
                },
                "leftSide": Coordinates(68, 167.5),
                "rightSide": Coordinates(1592, 215),
                "resonatorName": Coordinates(175, 194, 263, 39),
                "resonatorLevel": Coordinates(175, 247, 131, 35),
                "totalStats": Coordinates(158, 321, 350, 272),
                "weaponName": Coordinates(179, 198, 289, 37),
                "weaponLevel": Coordinates(175, 259, 131, 33),
                "weaponRank": Coordinates(184, 416, 105, 31),
                "skillStrip": Coordinates(263, 729, 1155, 272),
                "skillColumns": [
                    Coordinates(x=408),
                    Coordinates(x=605),
                    Coordinates(x=843),
                    Coordinates(x=1076),
                    Coordinates(x=1271)
                ],
                "chainPositions": [
                    Coordinates(1352, 274),
                    Coordinates(1329, 494),
                    Coordinates(1258, 661),
                    Coordinates(1145, 801),
                    Coordinates(1003, 898),
                    Coordinates(825, 936)
                ],
                "equipSlots": [
                    Coordinates(1278, 267),
                    Coordinates(1336, 481),
                    Coordinates(1327, 617),
                    Coordinates(1301, 753),
                    Coordinates(1238, 880)
                ],
                "echoPanel": Coordinates(1313, 136, 315, 797),
                "echoCost": Coordinates(1313, 180, 131, 33),
                "echoLevel": Coordinates(1544, 136, 88, 41)
            }
        }
    }
}