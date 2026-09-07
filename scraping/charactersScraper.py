import re
import cv2
import time
import string
import logging
import numpy as np
from pathlib import Path
from difflib import SequenceMatcher, get_close_matches as getMatches
from collections import defaultdict

from scraping.utils import charactersID, weaponsID, definedText
from scraping.utils import (
    screenshot, convertToBlackWhite, imageToString,
    readTextBoxes, recognizeLine, WindowsInputController
)
from scraping.utils.common import loadFile

# user-editable corrections for stubborn OCR misreads (e.g. 秧秧 read as 秋秋)
nameAliases: dict = loadFile('./nameAliases.json')
from game.screenInfo import ScreenInfo
from properties.config import cfg

logger = logging.getLogger('CharacterScraper')

# Constants
SKILL_LEGENDS = {
    0: 'normal',
    1: 'resonance',
    2: 'forte',
    3: 'liberation',
    4: 'intro'
}
ASCENSION_LEVELS = [20, 40, 50, 60, 70, 80, 90]

# kanji that OCR confuses with identical-looking katakana
KANA_LOOKALIKES = str.maketrans('二工力口夕卜', 'ニエカロタト')

def matchName(name: str, candidates, cutoffs=(0.9, 0.7)) -> str | None:
    """Resolve an OCR'd name against known names: alias table, exact match,
    fuzzy match, then unique-substring containment (OCR often drops chars).
    A katakana-normalized variant is tried as well, since the recognizer
    reads e.g. モーニエ as モー二工."""
    name = name.replace('-', 'ー')
    for variant in dict.fromkeys((name, name.translate(KANA_LOOKALIKES))):
        result = _matchOne(variant, candidates, cutoffs)
        if result:
            return result
    return None

def _matchOne(name: str, candidates, cutoffs) -> str | None:
    if name in nameAliases:
        return nameAliases[name]
    if name in candidates:
        return name
    for cutoff in cutoffs:
        result = getMatches(name, candidates, 1, cutoff)
        if result:
            return result[0]
    # OCR misreads drift (秋秋・玄胡一 / 秋秋・玄舗一 / ...), so also match
    # fuzzily against known alias keys instead of listing every variant
    aliasHit = getMatches(name, nameAliases, 1, 0.8)
    if aliasHit:
        return nameAliases[aliasHit[0]]
    if len(name) >= 2:
        containing = [candidate for candidate in candidates if name in candidate]
        if len(containing) == 1:
            return containing[0]
    # trailing noise glyphs (ルパ・ア): a known name as unique prefix
    prefixes = [candidate for candidate in candidates if len(candidate) >= 2 and name.startswith(candidate)]
    if len(prefixes) == 1:
        return prefixes[0]
    return None

def splitLevel(text: str) -> list[str]:
    """Split an OCR'd "level/cap" string; the slash is often lost, in which
    case the last two digits are the (always two-digit) ascension cap."""
    text = text.strip()
    if '/' in text:
        return text.split('/')
    if len(text) > 2:
        return [text[:-2], text[-2:]]
    return [text]

def scrapeResonator(image: np.ndarray, screenInfo: ScreenInfo, characters: dict, _cache: dict) -> tuple[str, bool]:
    # hash the binarized crop (stable against the animated background) but
    # OCR the color crop — binarization hurts the PP-OCRv5 recognizer
    resonatorNameImage = image[screenInfo.characters.resonatorName.y:screenInfo.characters.resonatorName.y + screenInfo.characters.resonatorName.h, screenInfo.characters.resonatorName.x:screenInfo.characters.resonatorName.x + screenInfo.characters.resonatorName.w]
    resonatorNameHash = hash(convertToBlackWhite(resonatorNameImage).tobytes())

    if resonatorNameHash in _cache:
        return None, True
    else:
        resonatorName = recognizeLine(resonatorNameImage).replace(' ', '').lower()
        if not resonatorName:
            # keep the crop so unreadable names can be diagnosed
            try:
                Path('logs/fail').mkdir(parents=True, exist_ok=True)
                cv2.imwrite(f'logs/fail/name_{abs(resonatorNameHash)}.png', resonatorNameImage)
            except Exception:
                pass
    
        result = matchName(resonatorName, charactersID)
        if result:
            resonatorName = result
        else:
            logger.debug(f'Unmatched resonator name: {resonatorName!r}')
            try:
                Path('logs/fail').mkdir(parents=True, exist_ok=True)
                cv2.imwrite(f'logs/fail/name_unmatched_{abs(resonatorNameHash)}.png', resonatorNameImage)
            except Exception:
                pass
        
        # a character named 漂泊者〜 is an event trial: the player's own Rover
        # always displays their custom name instead
        if result and result.startswith('漂泊者'):
            logger.debug(f'Skipping trial character {result!r}')
            _cache[resonatorNameHash] = ''
            return None, True

        roverName = cfg.get(cfg.roverName).replace(' ', '').lower()
        # OCR sometimes drops a trailing kana, so match the Rover name fuzzily
        isRover = resonatorName == roverName or SequenceMatcher(None, resonatorName, roverName).ratio() >= .7
        resonatorID = '1502' if isRover else charactersID.get(resonatorName, resonatorName)
        _cache[resonatorNameHash] = resonatorID

    if resonatorID in characters:
        return resonatorID, True

    # keep the level crop in color: the gray "/90" cap is lost by binarization
    levelImage = image[screenInfo.characters.resonatorLevel.y:screenInfo.characters.resonatorLevel.y + screenInfo.characters.resonatorLevel.h, screenInfo.characters.resonatorLevel.x:screenInfo.characters.resonatorLevel.x + screenInfo.characters.resonatorLevel.w]
    levelHash = hash(levelImage.tobytes())

    if levelHash in _cache:
        level = _cache[levelHash]
    else:
        # the level line mixes font sizes, which the recognizer alone garbles;
        # the full detection pipeline is more reliable here
        level = splitLevel(imageToString(levelImage, '', allowedChars=string.digits + '/'))
        _cache[levelHash] = level

    try: ascensionLvl = ASCENSION_LEVELS.index(int(level[1]))
    except: ascensionLvl = 0

    try: characterLvl = min(90, max(1, int(level[0])))
    except: characterLvl = 1

    characters[resonatorID]['level'] = characterLvl
    characters[resonatorID]['ascension'] = ascensionLvl
    characters[resonatorID]['stats'] = readTotalStats(image, screenInfo)

    return resonatorID, False

def scrapeWeapon(image: np.ndarray, screenInfo: ScreenInfo, characters: dict, resonatorID: str, _cache: dict):
    weaponNameImage = image[screenInfo.characters.weaponName.y:screenInfo.characters.weaponName.y + screenInfo.characters.weaponName.h, screenInfo.characters.weaponName.x:screenInfo.characters.weaponName.x + screenInfo.characters.weaponName.w]
    weaponNameHash = hash(convertToBlackWhite(weaponNameImage).tobytes())

    if weaponNameHash in _cache:
        weaponID = _cache[weaponNameHash]
    else:
        weaponName = recognizeLine(weaponNameImage).replace(' ', '').lower()
    
        result = matchName(weaponName, weaponsID, cutoffs=(0.9, 0.75, 0.6))
        if result:
            weaponName = result
        else:
            logger.debug(f'Unmatched weapon name: {weaponName!r}')

        weaponID = weaponsID.get(weaponName, {'id': weaponName})['id']
        _cache[weaponNameHash] = weaponID
    
    # keep the level crop in color: the gray "/90" cap is lost by binarization
    levelImage = image[screenInfo.characters.weaponLevel.y:screenInfo.characters.weaponLevel.y + screenInfo.characters.weaponLevel.h, screenInfo.characters.weaponLevel.x:screenInfo.characters.weaponLevel.x + screenInfo.characters.weaponLevel.w]
    levelHash = hash(levelImage.tobytes())
    
    if levelHash in _cache:
        level = _cache[levelHash]
    else:
        level = splitLevel(re.sub(r'[^0-9/]', '', recognizeLine(levelImage)))
        _cache[levelHash] = level

    rankImage = image[screenInfo.characters.weaponRank.y:screenInfo.characters.weaponRank.y + screenInfo.characters.weaponRank.h, screenInfo.characters.weaponRank.x:screenInfo.characters.weaponRank.x + screenInfo.characters.weaponRank.w]
    rankImage = convertToBlackWhite(rankImage)
    rankHash = hash(rankImage.tobytes())

    if rankHash in _cache:
        rank = _cache[rankHash]
    else:
        rank = re.sub(r'[^0-9]', '', recognizeLine(rankImage))
        _cache[rankHash] = rank

    try:
        rankValue = int(rank)
        if rankValue > 5:
            # OCR sometimes appends stray digits from the description below
            rankValue = int(rank[0])

        characters[resonatorID]['weapon']['id'] = weaponID
        characters[resonatorID]['weapon']['level'] = min(90, max(1, int(level[0])))
        characters[resonatorID]['weapon']['ascension'] = ASCENSION_LEVELS.index(int(level[1]))
        characters[resonatorID]['weapon']['rank'] = min(5, max(0, rankValue))
    except:
        logger.debug('Failed scraping the weapon')

def scrapeSkills(image: np.ndarray, screenInfo: ScreenInfo, characters: dict, resonatorID: str, _cache: dict):
    # Since 3.6 the skill screen shows every level directly on the tree
    # ("Lv.X/10" under each node), so no clicking is needed. OCR one band
    # containing all five labels and assign each to the nearest column —
    # cropping the labels individually makes the OCR much less reliable.
    strip = screenInfo.characters.skillStrip
    stripImage = image[strip.y:strip.y + strip.h, strip.x:strip.x + strip.w]
    stripHash = hash(stripImage.tobytes())

    if stripHash in _cache:
        levels = _cache[stripHash]
    else:
        columns = [column.x for column in screenInfo.characters.skillColumns]
        levels = {}
        for x0, y0, x1, y1, text in readTextBoxes(stripImage):
            found = re.search(r'(\d+)\s*/\s*10', text)
            if not found:
                continue
            xCenter = strip.x + (x0 + x1) / 2
            index = min(range(len(columns)), key=lambda i: abs(columns[i] - xCenter))
            levels[index] = int(found.group(1))
        _cache[stripHash] = levels

    for index in range(5):
        if index not in levels:
            logger.debug(f'Failed scraping skill level for column {index}')
        characters[resonatorID]['skills'][SKILL_LEGENDS[index]] = levels.get(index, 1)

def readTotalStats(image: np.ndarray, screenInfo: ScreenInfo) -> dict:
    """Read the aggregate stat rows (HP through crit damage) from the status
    section — actual in-game totals including weapon substats, inherent
    skills, and stat-bonus nodes."""
    from scraping.echoesScraper import matchStatName, normalizeValue

    area = screenInfo.characters.totalStats
    boxes = readTextBoxes(image[int(area.y):int(area.y + area.h), int(area.x):int(area.x + area.w)])
    labels = [((y0 + y1) / 2, text) for x0, y0, x1, y1, text in boxes if x0 < area.w * 0.55]
    values = [((y0 + y1) / 2, text) for x0, y0, x1, y1, text in boxes if x0 >= area.w * 0.55]

    stats = {}
    for labelY, labelText in labels:
        statName = matchStatName(labelText)
        if not statName:
            continue
        value = next((t for y, t in values if abs(y - labelY) < area.h * 0.06), None)
        if value is None:
            continue
        value = normalizeValue(value)
        try:
            if value.endswith('%'):
                stats[f'{statName}%'] = float(value[:-1])
            else:
                stats[statName] = int(float(value))
        except ValueError:
            pass
    return stats

def parseEquippedEcho(image: np.ndarray, screenInfo: ScreenInfo):
    """Parse the right-hand panel of the echo swap screen (opened by clicking
    an equipped slot): name, +level, cost, two main stats, up to five
    substats, and the sonata name — all visible without scrolling."""
    from scraping.echoesScraper import matchEchoName, matchStatName, matchSonata, normalizeValue, echoCosts
    from scraping.utils import echoesID, sonataName

    panel = screenInfo.characters.echoPanel
    crop = image[int(panel.y):int(panel.y + panel.h), int(panel.x):int(panel.x + panel.w)]
    boxes = sorted(readTextBoxes(crop), key=lambda b: b[1])
    if not boxes:
        return None

    costY = next((y0 for x0, y0, x1, y1, text in boxes if 'COST' in text.upper()), panel.h * 0.12)

    level, sonata = 0, str()
    nameParts = []
    statRows = []
    harmonyY = None
    skillY = None
    for x0, y0, x1, y1, text in boxes:
        text = text.strip()
        if y0 < costY - 4:
            # name area: long names wrap onto a second line, and the +N
            # level marker sometimes merges into the same box as the name
            found = re.search(r'\+(\d+)$', text)
            if found:
                level = max(level, min(25, int(found.group(1))))
                text = text[:found.start()].strip()
            if text:
                nameParts.append((y0, x0, text))
            continue
        if found := re.fullmatch(r'\+(\d+)', text):
            level = max(level, min(25, int(found.group(1))))
            continue
        if '音骸スキル' in text:
            skillY = y0
            continue
        if 'ハーモニー効果' in text:
            harmonyY = y0
            continue
        if harmonyY is not None and y0 > harmonyY and not sonata:
            sonata = matchSonata(text)
            continue
        if skillY is None and harmonyY is None and 'COST' not in text.upper():
            statRows.append((x0, (y0 + y1) / 2, text))

    name = ''.join(text for _, _, text in sorted(nameParts))
    # short names sometimes merge with the COST row into one box
    # (黒棘熊cöST 3C); cut everything from a COST-like token onward
    name = re.split(r'c[oö0]st', name, maxsplit=1, flags=re.IGNORECASE)[0].strip()

    if level == 0:
        # the +N box occasionally goes unread entirely; retry with a
        # targeted crop next to the name
        roi = screenInfo.characters.echoLevel
        found = re.search(r'(\d+)', recognizeLine(image[int(roi.y):int(roi.y + roi.h), int(roi.x):int(roi.x + roi.w)]))
        if found:
            level = min(25, int(found.group(1)))

    if not sonata:
        # the ハーモニー効果 heading itself sometimes misreads; try every
        # remaining line against the known sonata names
        for x0, y0, x1, y1, text in boxes:
            sonata = matchSonata(text)
            if sonata:
                break

    matched = matchEchoName(name or '')
    if not matched:
        logger.debug(f'Unmatched equipped echo name: {name!r}')
        return None

    labels = [(y, t) for x, y, t in statRows if x < panel.w * 0.6]
    values = [(y, t) for x, y, t in statRows if x >= panel.w * 0.6]
    stats = {'main': {}, 'sub': {}}
    count = 0
    for labelY, labelText in labels:
        statName = matchStatName(labelText.lstrip('+十ト '))
        if not statName:
            continue
        value = next((t for y, t in values if abs(y - labelY) < panel.h * 0.03), None)
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

    # each echo species has a fixed cost (1, 3, or 4). The second main stat
    # pins the cost class exactly (flat HP -> 1; flat ATK is 30+4.8/lv for
    # cost 4 and 20+3.2/lv for cost 3), so use it to catch names that
    # matched the wrong variant (e.g. a （幼体） suffix lost by the OCR).
    main = stats['main']
    mainKeys = set(main)
    inferred = None
    if mainKeys & {'cr%', 'cd%', 'healing%'}:
        inferred = 4  # these primary mains exist only on cost-4 echoes
    elif mainKeys & {'glacio%', 'fusion%', 'electro%', 'aero%', 'spectro%', 'havoc%', 'er%'}:
        inferred = 3  # element damage and ER mains exist only on cost 3
    elif 'hp' in main:
        inferred = 1  # a flat-HP secondary main means cost 1
    elif main.get('atk'):
        inferred = min((4, 3), key=lambda c: abs(main['atk'] - ((30 + 4.8 * level) if c == 4 else (20 + 3.2 * level))))

    cost = echoCosts.get(str(echoesID[matched]))
    if inferred and cost != inferred:
        alternate = next((candidate for candidate in echoesID
                          if matched in candidate and candidate != matched
                          and echoCosts.get(str(echoesID[candidate])) == inferred), None)
        if alternate:
            logger.debug(f'Correcting {matched!r} to {alternate!r} (main stats say cost {inferred})')
            matched = alternate
        cost = inferred
    if cost not in (1, 3, 4):
        cost = inferred or 1

    return {
        'id': echoesID[matched],
        'name': matched,
        'level': level,
        'cost': cost,
        'sonata': sonata,
        'stats': stats
    }

def scrapeEquippedEchoes(controller: WindowsInputController, screenInfo: ScreenInfo, characters: dict, resonatorID: str):
    """Click each equipped echo slot and read the swap screen's detail panel.
    Skipped for low-level characters, which have nothing meaningful equipped."""
    if characters[resonatorID]['level'] < 40:
        return

    sawSwapScreen = False
    for slot, position in enumerate(screenInfo.characters.equipSlots):
        controller.leftClick(position.x, position.y, 1.3)
        image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor, originX=screenInfo.originX, originY=screenInfo.originY)

        echo = parseEquippedEcho(image, screenInfo)
        if echo:
            characters[resonatorID]['echoes'][str(slot)] = echo

        # only back out if the swap screen actually opened (trial characters
        # show a toast instead); a blind esc would exit the resonator screen
        marker = recognizeLine(image[int(50 * screenInfo.height / 1080):int(84 * screenInfo.height / 1080), int(screenInfo.width - 470 * screenInfo.height / 1080):int(screenInfo.width - 380 * screenInfo.height / 1080)])
        if echo or '簡' in marker or '略' in marker:
            sawSwapScreen = True
            controller.pressKey('esc', 1.0)

    if not sawSwapScreen:
        # the swap screen never opened: this is a trial character
        # (お試しキャラは音骸の詳細を確認できません) — drop it entirely so
        # trial presets don't pollute (or overwrite) real roster data
        logger.debug(f'Dropping trial character recorded as {resonatorID!r}')
        characters.pop(resonatorID, None)

def scrapeChain(image: np.ndarray, screenInfo: ScreenInfo, characters: dict, resonatorID: str):
    # Activated chain nodes glow cyan on the 3.6 chain screen; classify each
    # node by the amount of saturated cyan around its center.
    for position in screenInfo.characters.chainPositions:
        x, y = int(position.x), int(position.y)
        patch = image[max(0, y - 14):y + 14, max(0, x - 14):x + 14]
        hsv = cv2.cvtColor(patch, cv2.COLOR_RGB2HSV)
        glow = cv2.inRange(hsv, (75, 60, 140), (115, 255, 255)).mean()
        logger.debug(f'Chain node at ({x},{y}): glow={glow:.1f}')

        if glow < 8:
            break

        characters[resonatorID]['chain'] += 1

def resonatorScraper(controller: WindowsInputController, screenInfo: ScreenInfo):
    characters = defaultdict(
        lambda: defaultdict(
            int,
            {
                'level': 0,
                'ascension': 0,
                'weapon': defaultdict(
                    int,
                    {
                        'id': 0,
                        'level': 1,
                        'ascension': 0,
                        'rank': 0
                    }
                ),
                'echoes': dict(),
                'skills': defaultdict(
                    int,
                    {
                        'normal': 1,
                        'resonance': 1,
                        'forte': 1,
                        'liberation': 1,
                        'intro': 1,
                        'stats0': 0,
                        'stats1': 0,
                        'inherent': 0,
                        'stats3': 0,
                        'stats4': 0
                    }
                ),
                'chain': 0
            }
        )
    )
    _cache = dict()

    # give the resonator screen time to finish its opening animation, or the
    # first character's sections are captured before they render
    controller.pressKey(cfg.get(cfg.resonatorKeybind), 3, False)

    xLeftSide, yLeftSide = screenInfo.characters.leftSide.x, screenInfo.characters.leftSide.y
    xRightSide, yRightSide = screenInfo.characters.rightSide.x, screenInfo.characters.rightSide.y

    # The list scrolls by less than one page per pass so consecutive passes
    # overlap; already-scanned resonators are skipped after reading their
    # name, and the scan ends once a full pass finds nothing new. This keeps
    # the scan correct even when the scroll distance is imprecise.
    emptyPasses = 0
    for _ in range(40):
        newCount = 0

        for resonatorIndex in range(6):
            controller.leftClick(xRightSide, yRightSide + (screenInfo.characters.offsets.rightSide.y * resonatorIndex), .7)
            resonatorID = str()

            for section in range(5):
                # the chain screen (section 4) plays a slide-in animation
                controller.leftClick(xLeftSide, yLeftSide + (screenInfo.characters.offsets.leftSide.y * section), 1.5 if section == 4 else .8)

                image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor, originX=screenInfo.originX, originY=screenInfo.originY)

                match(section):
                    case 0:
                        resonatorID, alreadyScanned = scrapeResonator(image, screenInfo, characters, _cache)
                        if resonatorID == '' and not alreadyScanned:
                            # likely captured mid-transition; retry once
                            time.sleep(.6)
                            image = screenshot(width=screenInfo.width, height=screenInfo.height, monitor=screenInfo.monitor, originX=screenInfo.originX, originY=screenInfo.originY)
                            resonatorID, alreadyScanned = scrapeResonator(image, screenInfo, characters, _cache)
                        if alreadyScanned:
                            break
                        newCount += 1
                    case 1:
                        scrapeWeapon(image, screenInfo, characters, resonatorID, _cache)
                    case 2:
                        scrapeEquippedEchoes(controller, screenInfo, characters, resonatorID)
                    case 3:
                        scrapeSkills(image, screenInfo, characters, resonatorID, _cache)
                    case 4:
                        scrapeChain(image, screenInfo, characters, resonatorID)
                time.sleep(.5)

        if newCount == 0:
            # a scroll occasionally fails to move the list, making a pass all
            # duplicates; only stop after two empty passes in a row
            emptyPasses += 1
            if emptyPasses >= 2:
                break
        else:
            emptyPasses = 0

        controller.moveMouse(xRightSide, yRightSide, .3)
        controller.mouseScroll(screenInfo.scroll.characters.y, 1.2)

    del _cache
    return dict(characters)
