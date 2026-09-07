import re
import cv2
import time
import logging
import numpy as np
from difflib import SequenceMatcher, get_close_matches as getMatches

from scraping.utils import (
    echoesID, echoStats, sonataName
)
from scraping.utils import (
    screenshot, imageToString, readTextBoxes, recognizeLine,
    WindowsInputController
)
from game.screenInfo import ScreenInfo
from properties.config import cfg
from scraping.utils.common import loadFile

logger = logging.getLogger('EchoScraper')

nameAliases: dict = loadFile('./nameAliases.json')
echoCosts: dict = loadFile('./data/echoCosts.json')

GRID_ROWS = 4

def normalizeValue(value: str) -> str:
    """Fix OCR decimal commas (44,0% -> 44.0%) without touching thousands."""
    return re.sub(r',(?=\d%?$)', '.', value.replace(' ', ''))

def gridColumns(screenInfo: ScreenInfo) -> int:
    """Number of grid columns that fit between the grid origin and the
    detail panel (6 at 16:9, more on ultrawide)."""
    grid = screenInfo.echoes.grid
    return int((screenInfo.echoes.panelLeft.x - grid.x) // grid.w) + 1

def cellCenter(screenInfo: ScreenInfo, col: int, row: int) -> tuple[float, float]:
    grid = screenInfo.echoes.grid
    return grid.x + grid.w * col, grid.y + grid.h * row - grid.h * 0.45

def capturePanel(screenInfo: ScreenInfo):
    return screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor,
                      originX=screenInfo.originX, originY=screenInfo.originY)

def cropROI(image: np.ndarray, roi):
    return image[int(roi.y):int(roi.y + roi.h), int(roi.x):int(roi.x + roi.w)]

# kanji that OCR confuses with identical-looking katakana
KANA_LOOKALIKES = str.maketrans('二工力口夕卜', 'ニエカロタト')

def matchEchoName(name: str) -> str | None:
    # the game renders full-width parentheses (（幼体）)
    name = name.replace('-', 'ー').replace('(', '（').replace(')', '）').lower().replace(' ', '')
    for variant in dict.fromkeys((name, name.translate(KANA_LOOKALIKES))):
        result = _matchEchoOne(variant)
        if result:
            return result
    return None

def _matchEchoOne(name: str) -> str | None:
    if name in nameAliases:
        return nameAliases[name]
    if name in echoesID:
        return name
    result = (getMatches(name, echoesID, 1, 0.85)
              or getMatches(name, echoesID, 1, 0.7)
              or getMatches(name, echoesID, 1, 0.65))
    if result:
        return result[0]
    aliasHit = getMatches(name, nameAliases, 1, 0.8)
    if aliasHit:
        return nameAliases[aliasHit[0]]
    if len(name) >= 3:
        containing = [candidate for candidate in echoesID if name in candidate]
        if len(containing) == 1:
            return containing[0]
    # trailing noise merged into the name box: a known name as unique prefix
    prefixes = [candidate for candidate in echoesID if len(candidate) >= 3 and name.startswith(candidate)]
    if len(prefixes) == 1:
        return prefixes[0]
    return None

def matchSonata(text: str) -> str:
    """Match a line of panel text against the known sonata names."""
    text = text.lower().replace(' ', '')
    if not text or len(text) > 16:
        return str()
    for variant in dict.fromkeys((text, text.translate(KANA_LOOKALIKES))):
        hit = getMatches(variant, sonataName, 1, 0.75) or getMatches(variant, sonataName, 1, 0.6)
        if hit:
            return hit[0]
        containing = [name for name in sonataName if name in variant or (len(variant) >= 4 and variant in name)]
        if len(containing) == 1:
            return containing[0]
    return str()

def matchStatName(text: str) -> str | None:
    """Resolve an OCR'd stat row label (often prefixed with the stat icon
    read as a stray glyph) to a canonical stat key."""
    text = text.lower().replace(' ', '').replace('.', '')
    for candidate in (text, text[1:]):
        if candidate in echoStats:
            return echoStats[candidate]
        hit = getMatches(candidate, echoStats, 1, 0.75)
        if hit:
            return echoStats[hit[0]]
    return None

RARITY_COLORS = {
    5: np.array([255, 205, 90]),
    4: np.array([205, 130, 255]),
    3: np.array([100, 180, 255]),
    2: np.array([120, 220, 120]),
}

def readRarity(image: np.ndarray, screenInfo: ScreenInfo) -> int:
    line = cropROI(image, screenInfo.echoes.rarityLine)
    if line.size == 0:
        return 5
    mean = line.reshape(-1, 3).mean(axis=0)
    rarity = min(RARITY_COLORS, key=lambda r: np.linalg.norm(RARITY_COLORS[r] - mean))
    logger.debug(f'Rarity line mean RGB={mean.astype(int)} -> {rarity}')
    return rarity

def readStats(image: np.ndarray, screenInfo: ScreenInfo) -> tuple[int, dict]:
    """Parse the stat rows of the detail panel by pairing left-hand labels
    with right-hand values on the same line, stopping at the skill section."""
    area = screenInfo.echoes.statsArea
    boxes = sorted(readTextBoxes(cropROI(image, area)), key=lambda b: b[1])

    rows = []
    for x0, y0, x1, y1, text in boxes:
        if '音骸スキル' in text or 'スキル' == text.strip():
            break
        rows.append((x0, (y0 + y1) / 2, text))

    labels = [(y, t) for x, y, t in rows if x < area.w * 0.6]
    values = [(y, t) for x, y, t in rows if x >= area.w * 0.6]

    stats = {'main': {}, 'sub': {}}
    count = 0
    for labelY, labelText in labels:
        statName = matchStatName(labelText)
        if not statName:
            continue
        value = next((t for y, t in values if abs(y - labelY) < area.h * 0.05), None)
        if value is None:
            continue
        value = normalizeValue(value)
        bucket = 'main' if count < 2 else 'sub'
        try:
            if value.endswith('%'):
                stats[bucket][f'{statName}%'] = float(value[:-1])
            else:
                stats[bucket][statName] = int(float(value))
        except ValueError:
            stats[bucket][statName] = value
        count += 1

    tuneLv = max(0, count - 2)
    return tuneLv, stats

def readSonata(controller: WindowsInputController, screenInfo: ScreenInfo) -> str:
    """Scroll the detail panel down to the harmony section and match any
    line against the known sonata names."""
    scrollPos = screenInfo.echoes.panelScroll
    controller.moveMouse(scrollPos.x, scrollPos.y, .2)
    controller.mouseScroll(-screenInfo.scroll.sonata.y, .5)

    image = capturePanel(screenInfo)
    area = screenInfo.echoes.statsArea
    sonata = str()
    for x0, y0, x1, y1, text in readTextBoxes(cropROI(image, area)):
        sonata = matchSonata(text)
        if sonata:
            break

    controller.moveMouse(scrollPos.x, scrollPos.y, .2)
    controller.mouseScroll(screenInfo.scroll.sonata.y, .3)
    return sonata

def clickSortByLevel(controller: WindowsInputController, screenInfo: ScreenInfo):
    controller.leftClick(screenInfo.echoes.sortButton.x, screenInfo.echoes.sortButton.y, 1.0)
    controller.leftClick(screenInfo.echoes.sortLevel.x, screenInfo.echoes.sortLevel.y, 1.2)

def readLevel(image: np.ndarray, screenInfo: ScreenInfo) -> int:
    text = re.sub(r'[^0-9]', '', recognizeLine(cropROI(image, screenInfo.echoes.level)))
    try:
        return min(25, int(text))
    except ValueError:
        return 0

def echoScraper(controller: WindowsInputController, x: float, y: float, screenInfo: ScreenInfo) -> list:
    echoes = list()
    seenPanels = set()
    minRarity = cfg.get(cfg.echoMinRarity)
    minLevel = cfg.get(cfg.echoMinLevel)

    controller.pressKey(cfg.get(cfg.inventoryKeybind), 2, False)
    controller.leftClick(x, y, 1.5)
    clickSortByLevel(controller, screenInfo)

    columns = gridColumns(screenInfo)
    logger.debug(f'Echo grid: {columns} columns x {GRID_ROWS} rows')

    # verify descending order; if the first echo is below the level filter
    # the sort direction is ascending, so flip it once
    cx, cy = cellCenter(screenInfo, 0, 0)
    controller.leftClick(cx, cy, 1.0)
    image = capturePanel(screenInfo)
    if readLevel(image, screenInfo) < minLevel:
        controller.leftClick(screenInfo.echoes.sortDirection.x, screenInfo.echoes.sortDirection.y, 1.2)

    lastPanelHash = None
    for page in range(200):
        newOnPage = 0
        for row in range(GRID_ROWS):
            for col in range(columns):
                cx, cy = cellCenter(screenInfo, col, row)
                controller.leftClick(cx, cy, .9)
                image = capturePanel(screenInfo)

                panelCrop = cropROI(image, screenInfo.echoes.statsArea)
                panelHash = hash(panelCrop.tobytes())
                if panelHash == lastPanelHash:
                    # clicking an empty slot leaves the panel unchanged:
                    # end of the list
                    logger.debug(f'End of echo list at page {page} row {row} col {col}')
                    return echoes
                lastPanelHash = panelHash

                level = readLevel(image, screenInfo)
                if level < minLevel:
                    logger.debug(f'Level {level} below threshold {minLevel}; stopping')
                    return echoes

                if panelHash in seenPanels:
                    continue
                seenPanels.add(panelHash)
                newOnPage += 1

                name = recognizeLine(cropROI(image, screenInfo.echoes.name))
                matched = matchEchoName(name)
                if not matched:
                    logger.debug(f'Unmatched echo name: {name!r}')
                    continue

                rarity = readRarity(image, screenInfo)
                if rarity < minRarity:
                    continue

                tuneLv, stats = readStats(image, screenInfo)
                sonata = readSonata(controller, screenInfo)

                echoes.append({
                    str(echoesID[matched]): {
                        'level': level,
                        'tuneLv': tuneLv,
                        'sonata': sonata,
                        'rarity': rarity,
                        'stats': stats
                    }
                })

        if newOnPage == 0:
            logger.debug(f'No new echoes on page {page}; stopping')
            break

        gridCenterX = screenInfo.echoes.grid.x + screenInfo.echoes.grid.w * (columns - 1) / 2
        controller.moveMouse(gridCenterX, screenInfo.echoes.grid.y + screenInfo.echoes.grid.h, .3)
        controller.mouseScroll(screenInfo.scroll.page.y, 1.2)

    return echoes
