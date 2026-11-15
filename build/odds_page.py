"""Write the public chest odds page (minifighter-site public/odds/index.html) from the game's own tables.
    python3 build/odds_page.py /home/claude/minifighter-source /home/claude/minifighter-site
Reads game/src/v2/meta.js with node (RARITIES, TAP_UP, DROP_TABLE, DROP_FIGHTER_CHANCE, CHESTS, dropFinalOdds,
dropPool), so the page shows exactly the odds the game uses. Head, header and footer come from the privacy page."""
import json, os, subprocess, sys

src, site = sys.argv[1], sys.argv[2]
JS = """const C=require(process.argv[1]);
console.log(JSON.stringify({rar:C.RARITIES.map(r=>r.name),taps:C.TAP_UP,pity:[C.PITY_N,C.PITY_MIN],table:C.DROP_TABLE,
fch:C.DROP_FIGHTER_CHANCE,dup:C.DROP_DUP_COINS,chests:C.CHESTS.map(c=>({title:c.title,min:c.min,price:c.price,perDay:c.perDay})),
odds:C.RARITIES.map((_,m)=>C.dropFinalOdds(m)),pool:C.dropPool().map(id=>[C.NAMES[id],C.FIGHTER_RARITY[id]])}));"""
D = json.loads(subprocess.run(['node', '-e', JS, os.path.join(src, 'game', 'src', 'v2', 'meta.js')], capture_output=True, text=True, check=True).stdout)
R = D['rar']
CHEST_F = ['בסיסית', 'אדירה', 'נדירה', 'אפית', 'מטורפת', 'אגדית']
ITEM = {'coins': 'מטבעות', 'pp': 'נקודות כוח', 'gems': 'יהלומים', 'passxp': 'נקודות כרטיס עונה'}
ITEM_EN = {'coins': 'coins', 'pp': 'power points', 'gems': 'gems', 'passxp': 'season pass XP'}
CUR = {'coins': 'מטבעות', 'gems': 'יהלומים'}


def pct(x):
    if x == 0:
        return '0%'
    s = f'{x * 100:.2f}'.rstrip('0').rstrip('.')
    return s + '%'


def fighter_chance(m, r=None):
    """chance that a chest starting at m gives a fighter (r=None: any rarity) / a given fighter of rarity r"""
    tot = 0.0
    for fin in range(len(R)):
        p = D['odds'][m][fin]
        n = sum(1 for _, fr in D['pool'] if fr <= fin)
        if not p or not n:
            continue
        if r is None:
            tot += p * D['fch'][fin]
        elif r <= fin:
            tot += p * D['fch'][fin] / n
    return tot


rows = []
for c in D['chests']:
    m = c['min']
    cells = ''.join(f'<td>{pct(D["odds"][m][i])}</td>' for i in range(len(R)))
    rows.append(f'<tr><th scope="row">{c["title"]}<br><small>{c["price"]["amount"]} {CUR[c["price"]["type"]]}, עד {c["perDay"]} ביום</small></th>{cells}<td>{pct(fighter_chance(m))}</td></tr>')
earned = ''.join(f'<td>{pct(x)}</td>' for x in D['odds'][0])
rows.insert(0, f'<tr><th scope="row">תיבה שמרוויחים במשחק<br><small>חינם, על ניצחונות, משימות ועליית רמה</small></th>{earned}<td>{pct(fighter_chance(0))}</td></tr>')
head_cells = ''.join(f'<th scope="col">{r}</th>' for r in R)

contents = ''.join(
    f'<tr><th scope="row">תיבה {CHEST_F[i]}</th><td>' + ', '.join(f'{a} עד {b} {ITEM[t]}' for t, a, b in D['table'][i]) +
    f'</td><td>{pct(D["fch"][i])}</td></tr>' for i in range(len(R)))
by_r = {}
for nm, fr in D['pool']:
    by_r.setdefault(fr, []).append(nm)
fighters = ''.join(
    f'<tr><th scope="row">{R[fr]}</th><td>{", ".join(by_r[fr])}</td>' +
    ''.join(f'<td>{pct(fighter_chance(c["min"], fr))}</td>' for c in D['chests']) + '</tr>' for fr in sorted(by_r))
chest_heads = ''.join(f'<th scope="col">{c["title"]}</th>' for c in D['chests'])
taps = ', '.join(f'{R[i]} → {R[i + 1]}: {pct(t)}' for i, t in enumerate(D['taps']))

main = f'''<main id="main"><section><div class="wrap prose legal"><h1>סיכויים בתיבות</h1>
<p class="upd">מיני פייטר 2.0 · הנתונים נלקחים ישירות מטבלאות המשחק</p>
<p>במיני פייטר יש תיבות פרסים עם תוכן אקראי. אפשר לקבל אותן בחינם על משחק (ניצחונות יומיים, משימות, עליית רמה, הדרך לפסגה וכרטיס העונה), ואפשר לקנות אותן בחנות של המשחק <b>רק במטבעות או ביהלומים</b> של המשחק, עם הגבלה יומית. <b>אי אפשר לקנות תיבה בכסף אמיתי</b>. שימו לב: יהלומים אפשר גם לקנות בכסף אמיתי, ולכן מי שקונה תיבה ביהלומים משלם בעקיפין בכסף. הסיכויים קבועים, זהים לכל השחקנים, ומוצגים גם בתוך המשחק לפני כל קנייה.</p>
<h2>איך תיבה עובדת</h2>
<p>תיבה מתחילה בדרגה שלה (תיבה שמרוויחים במשחק מתחילה בדרגה {R[0]}). בכל הקשה היא יכולה לעלות דרגה אחת, והפתיחה נגמרת בהקשה הראשונה שלא מעלה. הסיכוי לעלות מכל דרגה: {taps}. התוצאה נקבעת ונשמרת לפני שמשהו מוצג, כך שאין דרך להשפיע עליה.</p>
<p>הבטחה: בתיבות שמרוויחים במשחק, אם {D["pity"][0] - 1} תיבות ברצף נגמרו מתחת לדרגה {R[D["pity"][1]]}, התיבה הבאה תהיה לפחות {R[D["pity"][1]]}. תיבות שקונים בחנות לא משתמשות בהבטחה הזאת ולא משנות אותה.</p>
<h2>הסיכוי לסיים בכל דרגה</h2>
<div class="tbl"><table><thead><tr><th scope="col">התיבה</th>{head_cells}<th scope="col">סיכוי ללוחם</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<h2>מה יש בתיבה לפי הדרגה שבה היא נגמרת</h2>
<p>הכמות של כל פריט נבחרת באקראי בטווח, וכל מספר בטווח בסיכוי שווה. בנוסף, יש סיכוי לקבל לוחם.</p>
<div class="tbl"><table><thead><tr><th scope="col">דרגה</th><th scope="col">תמיד בתיבה</th><th scope="col">סיכוי ללוחם</th></tr></thead><tbody>{contents}</tbody></table></div>
<h2>הלוחמים שיכולים לצאת</h2>
<p>כשיוצא לוחם, הוא נבחר בסיכוי שווה מבין הלוחמים בדרגה של התיבה ומתחתיה. לוחם שכבר יש לכם מתחלף במטבעות ({", ".join(f"{R[i]}: {v}" for i, v in enumerate(D["dup"]) if i)}). ששת לוחמי העונה לא יוצאים מתיבות לעולם, והם נפתחים רק במשחק. בטבלה: הסיכוי לקבל לוחם מסוים אחד מהקבוצה, בכל סוג תיבה.</p>
<div class="tbl"><table><thead><tr><th scope="col">דרגת הלוחם</th><th scope="col">הלוחמים</th>{chest_heads}</tr></thead><tbody>{fighters}</tbody></table></div>
<p>שאלות על הסיכויים: <a href="mailto:social@sapirfamily.co.il">social@sapirfamily.co.il</a>. ראו גם את <a href="/terms/">תנאי השימוש</a>.</p>
<div class="en" lang="en" dir="ltr"><h1>Chest odds</h1>
<p>Mini Fighter 2.0 has reward chests with random contents. They are earned for free by playing, or bought in the in-game shop <b>only with in-game coins or gems</b>, with a daily limit. <b>Chests are never sold for real money.</b> Gems can also be bought with real money, so a chest bought with gems is indirectly paid for. The odds are fixed, the same for every player, and also shown in the game before every purchase.</p>
<p>A chest starts at its own rarity (earned chests start at Basic). Each tap may upgrade it one rarity, with the chance {", ".join(pct(t) for t in D["taps"])} from Basic upward; opening ends at the first tap that does not upgrade. The result is rolled and saved before anything is shown. Earned chests: after {D["pity"][0] - 1} chests in a row below Epic, the next one is at least Epic (shop chests do not use this). The tables above give the chance to end at each rarity (Basic, Great, Rare, Epic, Crazy, Legend, from left to right in Hebrew order), the contents by rarity ({"; ".join(", ".join(f"{a} to {b} {ITEM_EN[t]}" for t, a, b in D["table"][i]) for i in range(len(R)))}), and the fighter chances. A fighter you already own is replaced by coins. The six season fighters never come from chests.</p>
</div></div></section></main>'''

priv = open(os.path.join(site, 'public', 'privacy', 'index.html'), encoding='utf8').read()
i, j = priv.find('<main'), priv.find('</main>') + len('</main>')
head, tail = priv[:i], priv[j:]
head = (head.replace('<title>מדיניות פרטיות | מיני פייטר</title>', '<title>סיכויים בתיבות | מיני פייטר</title>')
        .replace('https://minifighter.co.il/privacy/', 'https://minifighter.co.il/odds/')
        .replace('מדיניות פרטיות | מיני פייטר', 'סיכויים בתיבות | מיני פייטר')
        .replace('מדיניות הפרטיות של מיני פייטר, באפליקציה, באתר ובמולטיפלייר, לפי חוק הגנת הפרטיות ותיקון 13.',
                 'הסיכויים בתיבות הפרסים של מיני פייטר 2.0: דרגות, תוכן ולוחמים, ישירות מטבלאות המשחק.'))
assert '/odds/' in head and 'סיכויים' in head
css = ('.tbl{overflow-x:auto;margin:12px 0 18px}.tbl table{border-collapse:collapse;min-width:100%;font-size:15px}'
       '.tbl th,.tbl td{border:1px solid var(--line);padding:7px 9px;text-align:center;vertical-align:middle}'
       '.tbl thead th{background:var(--card2);color:var(--gold)}.tbl tbody th{text-align:right;background:var(--card)}'
       '.tbl small{color:var(--muted);font-weight:400}')
head = head.replace('</style></head>', css + '</style></head>', 1)
tail = tail.replace('<a href="/terms/">תנאי שימוש</a>', '<a href="/terms/">תנאי שימוש</a><a href="/odds/">סיכויים</a>', 1)
os.makedirs(os.path.join(site, 'public', 'odds'), exist_ok=True)
open(os.path.join(site, 'public', 'odds', 'index.html'), 'w', encoding='utf8').write(head + main + tail)
print('written', os.path.join(site, 'public', 'odds', 'index.html'))
