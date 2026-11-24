"""
deterministic_rules.py - Step 8, layer 1: explainable, auditable, no ML, no LLM.

Each rule looks at the clause TEXT (Hindi or English) and either fires or doesn't.
Rules deliberately do NOT depend on the classifier's predicted category: the
classifier is right only about half the time right now, and a hard legal check
should not silently switch off because a different model mislabeled the clause.

A rule hit carries everything the user-facing verdict needs, so no LLM call is
required for it: severity, the rule id, the law it relates to (ids into
legal-corpus/), and a plain-language reason in English and Hindi.

What a rule does NOT do: it never states a legal conclusion as fact. Wording is
"this looks like..." / "is a serious warning sign". The product informs and
routes to humans; it does not give legal advice.

Legal numbers (the wage floor) come from law_thresholds.json, never from code.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Optional

HERE = Path(__file__).parent
SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}

# ---------------------------------------------------------------- text helpers

_DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def norm(text: str) -> str:
    """Lowercase, Devanagari digits -> ASCII, curly quotes -> straight, collapse whitespace."""
    t = text.translate(_DEVANAGARI_DIGITS).lower().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", t).strip()


def any_of(text: str, patterns: list[str]) -> Optional[str]:
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(0)
    return None


# ---------------------------------------------------------------- shared vocab

WORK = [r"\b(work|works|working|labou?r|serve|service|employ\w*|job|duty|duties)\b",
        r"(काम|सेवा|मजदूर|नौकरी|खेत में|ड्यूटी|चाकरी)"]
DEBT = [r"\b(debts?|loans?|advances?|owed|dues?|borrow\w*|repay\w*|repaid|principal)\b",
        r"(कर्ज|कर्जा|ऋण|उधार|पेशगी|अग्रिम|बकाया|रकम|पैसा चुक|पैसे चुक|चुकता|चुका)"]
CLEARED = [r"\b(repaid|paid (off|back|in full|up)|cleared|settled|recovered|discharged|fully paid|paid in full)\b",
           r"(चुक(?:\s|ा|ाया|ता|ती|े|\b)|चुकता|वसूल|पूरा (न )?चुक|पूरी तरह|खत्म न)"]
PROPERTY = [r"\b(land|house|home|farm|field|fields|crop|crops|livestock|cattle|animals|property|equipment|tools|belongings|harvest|plot|assets?)\b",
            r"(जमीन|जमीन|घर|खेत|फसल|पशु|मवेशी|सामान|संपत्ति|औजार|मकान|दुकान)"]


# ---------------------------------------------------------------- rule plumbing

@dataclass
class RuleHit:
    rule_id: str
    severity: str                 # high | medium | low
    provisions: list[str]         # provision_ids from legal-corpus/ (may be empty)
    reason_en: str
    reason_hi: str
    evidence: str = ""            # the matched text, so a reviewer can see WHY it fired


@dataclass
class Rule:
    rule_id: str
    detector: Callable[[str, dict], Optional[RuleHit]]


# ---------------------------------------------------------------- R1 bonded labour

def r_bonded(t: str, ctx: dict) -> Optional[RuleHit]:
    explicit = any_of(t, [r"\bbonded\b", r"बंधुआ", r"बंधक", r"गुलाम"])
    free_labor = any_of(t, [
        r"\b(free of charge|for free|unpaid|free labou?r|without (any )?(wage|wages|pay|payment|salary|remuneration)|no (wage|wages|pay|salary)\b)",
        r"(मुफ्त|मुफ़्त|बिना (किसी )?(मजदूरी|वेतन|पैसे|पैसा|भुगतान|तनख्वाह)|बगैर (मजदूरी|वेतन|पैसे)|कोई (मजदूरी|वेतन|तनख्वाह) नहीं|मजदूरी नहीं|वेतन नहीं|मजदूरी नही)"])
    has_work = any_of(t, WORK)
    has_debt = any_of(t, DEBT)
    until_cleared = None
    if has_work:
        until_cleared = (
            re.search(r"\b(until|till|unless)\b[^.;]{0,80}" + CLEARED[0], t) or
            re.search(r"(जब तक)[^।;]{0,80}" + CLEARED[1], t))
    cant_leave = any_of(t, [
        r"\b(cannot|can not|can't|not (be )?(allowed|permitted)|prohibited|barred|forbidden|no right|shall not|will not be able|not free)\b[^.;]{0,60}\b(work (elsewhere|anywhere|for (any|another|someone))|seek (other|another)|other employment|elsewhere|leave|quit|resign|go away)",
        r"(कहीं और|दूसरी जगह|और कहीं|अन्यत्र|दूसरे)[^।;]{0,40}(काम|नौकरी|जा)[^।;]{0,20}(नहीं|न )",
        r"(काम|नौकरी|मालिक|भट्टा|खेत)[^।;]{0,15}(छोड़|छोड़कर)[^।;]{0,15}(नहीं|न )",
        r"(छोड़ नहीं सकता|नहीं छोड़ सकता|जा नहीं सकता|नहीं जा सकता|बाहर नहीं जा)"])

    evidence = None
    if explicit:
        evidence = explicit
    elif free_labor and has_work and (has_debt or until_cleared):
        evidence = free_labor
    elif until_cleared and has_work:
        evidence = until_cleared.group(0)
    elif cant_leave and has_debt:
        evidence = cant_leave

    if not evidence:
        return None
    return RuleHit(
        "R1_BONDED_LABOUR", "high", ["bonded-labour-1976-core-prohibition"],
        "This clause ties a debt to working for the lender, or stops you from working elsewhere until it is paid. "
        "That looks like bonded labour, which is illegal in India - and the law cancels a debt of this kind. Get this checked before signing.",
        "इस शर्त में कर्ज को चुकाने के लिए कर्ज देने वाले के यहां काम करना पड़ता है, या कर्ज चुकने तक दूसरी जगह काम करने से रोका जाता है। "
        "यह बंधुआ मजदूरी जैसा लगता है, जो भारत में गैरकानूनी है। हस्ताक्षर से पहले इसकी जांच करवाएं।",
        evidence)


# ---------------------------------------------------------------- R2 unbounded interest

def r_interest(t: str, ctx: dict) -> Optional[RuleHit]:
    if not any_of(t, [r"\binterest\b", r"ब्याज"]):
        return None
    ev = any_of(t, [
        r"(lender|owner|creditor|moneylender|landlord|employer|sahukar|seth|contractor)('s)? ?(own )?(discretion|choice|decision|wish|will|word)",
        r"\bas (the )?(lender|owner|creditor|moneylender|seth|sahukar|landlord|employer) (says|decides|wishes|wants|may (decide|fix|determine)|will (decide|say|fix|determine))",
        r"whatever[^.]{0,50}(says|decides|wants)",
        r"\b(not|never|isn't|is not) (yet )?(fixed|specified|stated|defined|disclosed|mentioned|written|determined)\b",
        r"\b(unspecified|undefined|undisclosed)\b",
        r"\bno (fixed|set|defined) (rate|interest)\b",
        r"\b(increase|raise|change|vary|revise)d?\b[^.]{0,40}(at any time|anytime|at will|whenever|without (notice|asking))",
        r"\b(doubl(e|es|ing|ed)|compound(ed|ing)? (daily|every day|weekly))\b",
        r"(जो|जितना)[^।]{0,25}(कहेगा|कहेंगे|चाहे|चाहेगा|तय करेगा|तय करेंगे|बोलेगा|बोलेंगे)",
        r"मर्जी|मर्ज़ी|तय नहीं|निर्धारित नहीं|दर नहीं|बढ़ा (सकता|सकते)|कभी भी बढ़|दोगुन|दुगुन|हर (दिन|रोज़|रोज) (का )?ब्याज"])
    if not ev:
        return None
    provs = ["usurious-loans-1918-s3-reopening"]
    if ctx.get("doc_type") in (None, "loan_chit"):
        provs.insert(0, "mp-moneylenders-2020-interest-cap-mechanism")
    return RuleHit(
        "R2_UNBOUNDED_INTEREST", "high", provs,
        "The interest rate is not fixed - it depends on what the lender decides, or it can be raised later. "
        "In Madhya Pradesh a moneylender may not charge more than the rate notified by the State Government, and the rate must be written in the loan voucher.",
        "ब्याज की दर तय नहीं है - यह साहूकार की मर्जी पर है या बाद में बढ़ाई जा सकती है। "
        "मध्य प्रदेश में साहूकार राज्य सरकार की अधिसूचित दर से ज्यादा ब्याज नहीं ले सकता, और दर लिखित रसीद में होनी चाहिए।",
        ev)


# ---------------------------------------------------------------- R3 no-notice termination

def r_no_notice(t: str, ctx: dict) -> Optional[RuleHit]:
    no_notice = any_of(t, [
        r"\b(without|no) (any |prior |written |advance |previous )*(notice|warning|intimation)\b",
        r"(बिना (किसी )?(पूर्व )?(सूचना|नोटिस|चेतावनी)|बगैर (किसी )?(सूचना|नोटिस)|(कोई )?(सूचना|नोटिस) (दिए|दिये) बिना|कोई (सूचना|नोटिस) नहीं)"])
    if not no_notice:
        return None
    action = any_of(t, [
        r"\b(terminat\w*|evict\w*|vacat\w*|take back|reclaim\w*|repay\w*|demand\w*|remov\w*|seiz\w*|cancel\w*|end (the|this))\b",
        r"(निकाल|बेदखल|खाली|वापस (ले|मांग)|हटा|छीन|तुरंत|मांग|जब्त|खत्म|समाप्त|रद्द)"])
    if not action:
        return None
    return RuleHit(
        "R3_NO_NOTICE", "high", [],
        "This clause lets the other side end the arrangement, evict you or demand everything back without any notice, "
        "leaving you no time to respond. Ask for a written notice period before signing.",
        "इस शर्त के अनुसार दूसरा पक्ष बिना कोई सूचना दिए अनुबंध खत्म कर सकता है, आपको निकाल सकता है या सब कुछ वापस मांग सकता है। "
        "आपको जवाब देने का समय नहीं मिलेगा। हस्ताक्षर से पहले लिखित नोटिस की अवधि मांगें।",
        no_notice)


# ---------------------------------------------------------------- R4 self-help seizure / forfeiture

def r_seizure(t: str, ctx: dict) -> Optional[RuleHit]:
    prop = any_of(t, PROPERTY)
    if not prop:
        return None
    verb = any_of(t, [
        r"\b(seiz\w*|forfeit\w*|confiscat\w*|take (possession|over|away|permanent)|takes? (possession|permanent)|become[s]? (the )?(lender|owner|landlord|moneylender|creditor)'?s?|transfer\w*[^.]{0,40}(to (the )?(lender|owner|landlord|moneylender|creditor)|in (the )?(lender|owner)'?s? name)|(lender|owner|landlord|moneylender|creditor)[^.]{0,30}(can|may|will|has the right to) (take|keep|retain|sell))",
        r"(जब्त|कब्जा|कब्ज़ा|हो जाएगी|हो जाएगा|हो जायेगा|हो जाएंगे|मालिक की हो|साहूकार की हो|छीन|ले लेगा|ले लेंगे|ले सकता|नाम (कर|पर) (देना|करना)|नाम करना)"])
    trigger = any_of(t, [
        r"\b(if|unless|fail\w*|default\w*|not (paid|repaid|pay|able)|cannot (pay|repay)|miss\w*|late|delay\w*|unable|non-?payment)\b",
        r"(नहीं चुका|न चुका|नहीं दे|न दे|नहीं दिया|देर|समय पर|चूक|नहीं लौटा|न लौटा|अगर|यदि|तो)"])
    if not (verb and trigger):
        return None
    return RuleHit(
        "R4_SEIZURE_ON_DEFAULT", "high", ["usurious-loans-1918-s3-reopening"],
        "On a missed payment, this clause lets the lender or owner simply take your land, house, crop or belongings - "
        "with no court process. Automatic seizure like this is a serious warning sign; a court can set aside unfair terms of this kind.",
        "भुगतान चूकने पर इस शर्त के तहत साहूकार या मालिक आपकी जमीन, घर, फसल या सामान बिना अदालत की प्रक्रिया के सीधे ले सकता है। "
        "यह गंभीर खतरे का संकेत है; अदालत ऐसी अनुचित शर्तों को रद्द कर सकती है।",
        verb)


# ---------------------------------------------------------------- R5 no written record

def r_no_record(t: str, ctx: dict) -> Optional[RuleHit]:
    ev = any_of(t, [
        r"\b(no|without|never (given|provided)) (any |a |the |written |proper )*(receipt|paper|papers|document|documents|documentation|voucher|proof|written (agreement|record)|record)\b",
        r"\b(only|just) (verbal|oral|verbally|orally)\b|\bverbal(ly)? (agreement|agreed|promise)\b|\boral(ly)? (agreement|agreed)\b",
        r"\b(did not|didn't|not|never) (receive|get|given|provided)[^.]{0,30}(receipt|paper|document|copy)",
        r"(कोई )?(रसीद|कागज|कागज़|दस्तावेज|दस्तावेज़|लिखित|सबूत|पर्ची)[^।]{0,12}(नहीं|नही)\b",
        r"मौखिक|जुबानी|ज़ुबानी|मुंह ?ज़बानी|लिखा ?पढ़ी नहीं|बिना (रसीद|कागज|लिखा)"])
    if not ev:
        return None
    if ctx.get("doc_type") in (None, "loan_chit"):
        en = ("No proper written record is given. A moneylender in Madhya Pradesh must hand over a signed voucher stating the interest rate "
              "and any pledged property. Without it you cannot prove what you owe.")
        hi = ("कोई सही लिखित रिकॉर्ड नहीं दिया गया है। मध्य प्रदेश में साहूकार को हस्ताक्षर के साथ रसीद देनी होती है जिसमें ब्याज दर और गिरवी रखी चीजें लिखी हों। "
              "इसके बिना आप साबित नहीं कर सकते कि आपका कितना बकाया है।")
        provs = ["mp-moneylenders-1934-voucher-requirement"]
    else:
        en = "The terms are not written down or no copy is given. Agreements that exist only by word are very hard to prove later - ask for them in writing."
        hi = "शर्तें लिखित में नहीं हैं या कोई प्रति नहीं दी गई। केवल मौखिक समझौते को बाद में साबित करना बहुत कठिन होता है - इसे लिखित में मांगें।"
        provs = []
    return RuleHit("R5_NO_WRITTEN_RECORD", "high", provs, en, hi, ev)


# ---------------------------------------------------------------- R6 physical force

def r_force(t: str, ctx: dict) -> Optional[RuleHit]:
    ev = any_of(t, [
        r"\b(physical(ly)? (punish\w*|force|violence|harm|beat\w*|abus\w*|discipline)|corporal|beat(ing|en)?\b|flog\w*|whip\w*|assault\w*|use (of )?(any )?force|any force necessary)",
        r"(शारीरिक (दंड|दण्ड|सजा|रूप से (दंडित|पीट))|मारपीट|पिटाई|पीटा|पीटेंगे|पीटेगा|डंडे|बल प्रयोग|जोर जबरदस्ती|जबरदस्ती|जबरन)"])
    if not ev:
        return None
    return RuleHit(
        "R6_PHYSICAL_FORCE", "high", [],
        "This clause allows force or physical punishment. No contract can allow that - it is a crime. Do not sign, and ask for help.",
        "इस शर्त में मारपीट, जबरदस्ती या शारीरिक दंड की बात है। कोई भी अनुबंध इसकी अनुमति नहीं दे सकता - यह अपराध है। हस्ताक्षर न करें और मदद लें।",
        ev)


# ---------------------------------------------------------------- R7 waived recourse

def r_recourse(t: str, ctx: dict) -> Optional[RuleHit]:
    party = r"(lender|owner|employer|landlord|moneylender|seth|sahukar|contractor|creditor)"
    ev = any_of(t, [
        r"\b(no|waive[sd]?|give[s]? up|forfeit[s]?|surrender[s]?) (the |all |any |his |her |their |your )*rights?\b[^.]{0,50}\b(complain|sue|court|appeal|legal|dispute|approach|object|police|authority)",
        r"\b(decision|word|judgment|verdict|ruling)s? (of|by) (the )?" + party + r"[^.]{0,25}\b(final|binding)\b",
        r"\b" + party + r"'?s? (decision|word|judgment|verdict|ruling)s?[^.]{0,25}\b(final|binding)\b",
        r"\bsettled (only )?by (the )?" + party,
        r"\b(no|without) (court|legal (action|recourse|remedy))\b|\bcannot (go to|approach) (the )?(court|police)",
        r"(अधिकार|हक) नहीं[^।]{0,40}(शिकायत|अदालत|कोर्ट|मुकदमा|पुलिस|कानूनी|अपील)",
        r"(शिकायत|अदालत|कोर्ट|मुकदमा|पुलिस|अपील)[^।]{0,25}(नहीं कर सक|का अधिकार नहीं|का हक नहीं|नहीं जा सक)",
        r"(फैसला|फ़ैसला|निर्णय)[^।]{0,25}(अंतिम|आखिरी)",
        r"(अदालत|कानून)[^।]{0,12}(नहीं|का सहारा नहीं)",
        r"(साहूकार|मालिक|ठेकेदार|जमींदार)[^।]{0,20}(का|के) (फैसला|निर्णय|बात) ही"])
    if not ev:
        return None
    return RuleHit(
        "R7_RECOURSE_WAIVED", "high", ["usurious-loans-1918-s3-reopening"],
        "This clause takes away your right to complain or go to court, or makes the other side's decision final. "
        "Signing away that right is a serious red flag - one-sided terms like this are exactly what courts can set aside.",
        "यह शर्त आपसे शिकायत करने या अदालत जाने का अधिकार छीनती है, या दूसरे पक्ष के फैसले को ही अंतिम मानती है। "
        "यह गंभीर खतरे का संकेत है - ऐसी एकतरफा शर्तों को अदालत रद्द कर सकती है।",
        ev)


# ---------------------------------------------------------------- R8 auto-renewal

def r_autorenew(t: str, ctx: dict) -> Optional[RuleHit]:
    ev = any_of(t, [
        r"\bauto(matically)?[- ]?renew\w*|\brenews? automatically|\bextend(s|ed)? automatically|\bautomatically (extend|continue|roll)|\bautomatic(ally)? (extension|renewal)|\brolled? over\b",
        r"(अपने आप|स्वतः|खुद ही)[^।]{0,35}(बढ़|नवीनीकृत|नवीनीकरण|आगे बढ़|जारी|रिन्यू|अगले (साल|वर्ष|सीजन))|ऑटो ?रिन्यू|स्वतः नवीनीकरण"])
    if not ev:
        return None
    trap = any_of(t, [
        r"\b(until|till)\b|\b(indefinite\w*|forever|perpetual\w*|no (right|option|way)|cannot (cancel|leave|terminate|quit)|at (the )?(landlord|owner|lender)'?s? discretion)\b",
        r"(हमेशा|जब तक|कोई अधिकार नहीं|कोई विकल्प नहीं|नहीं छोड़|मर्जी)"])
    if trap:
        return RuleHit(
            "R8_AUTORENEW_TRAP", "high", [],
            "This agreement renews by itself and you have no clear way out until a debt is cleared - a common debt-trap pattern.",
            "यह अनुबंध अपने आप आगे बढ़ता रहता है और कर्ज चुकने तक निकलने का कोई साफ रास्ता नहीं है - यह कर्ज के जाल का आम तरीका है।", ev)
    return RuleHit(
        "R8_AUTORENEW", "medium", [],
        "This agreement renews automatically. Check how and when you can cancel it before you sign.",
        "यह अनुबंध अपने आप आगे बढ़ जाता है। हस्ताक्षर से पहले देखें कि आप इसे कब और कैसे रद्द कर सकते हैं।", ev)


# ---------------------------------------------------------------- R9 minimum wage

_THRESHOLDS = json.loads((HERE / "law_thresholds.json").read_text(encoding="utf-8"))["minimum_wage_mp_general"]

WAGE_WORDS = [r"\b(wage|wages|salary|pay|paid|payment|remuneration|per day|daily)\b",
              r"(मजदूरी|वेतन|तनख्वाह|तनख़्वाह|पगार|दिहाड़ी|भुगतान|मेहनताना)"]
CURRENCY = r"(rs\.?|₹|inr|rupees?|रुपये|रुपए|रु\.?)"
DAY_UNIT = r"(per day|a day|/ ?day|daily|per diem|each day|every day|प्रति ?दिन|प्रतिदिन|रोज़ाना|रोजाना|रोज|दैनिक|हर दिन)"
MONTH_UNIT = r"(per month|a month|/ ?month|monthly|each month|every month|प्रति ?माह|प्रतिमाह|प्रति महीन\w*|महीने|महीना|मासिक|हर माह|हर महीने)"
AGRI = [r"\b(farm|field|fields|crop|crops|harvest|agricultur\w*|cultivat\w*|sowing|weeding|paddy|wheat)\b",
        r"(खेत|फसल|खेती|कटाई|बुवाई|निराई|गुड़ाई|धान|गेहूं|गेहूँ)"]


def extract_wages(t: str) -> list[tuple[float, str]]:
    """Returns [(amount, 'day'|'month')] for amounts that have an explicit pay period."""
    found = []
    for m in re.finditer(r"(?<![\w.,])(\d{1,3}(?:,\d{2,3})+|\d+)(?:\.\d+)?", t):
        amount = float(m.group(1).replace(",", ""))
        s, e = m.span()
        before, after = t[max(0, s - 40):s], t[e:e + 40]
        if re.search(r"(interest|ब्याज|%|percent)\s*(of|@|at|:)?\s*$", before) or after.lstrip().startswith(("%", "percent")):
            continue
        if 1900 <= amount <= 2100 and not re.search(CURRENCY, before[-10:] + after[:10]):
            continue
        near = before[-14:] + " " + after[:16]
        if not (re.search(CURRENCY, near) or any_of(t, WAGE_WORDS)):
            continue
        best = None
        for unit, pat in (("day", DAY_UNIT), ("month", MONTH_UNIT)):
            for um in re.finditer(pat, t):
                dist = min(abs(um.start() - e), abs(s - um.end()))
                if dist <= 30 and (best is None or dist < best[0]):
                    best = (dist, unit)
        if best:
            found.append((amount, best[1]))
    return found


def r_wage(t: str, ctx: dict) -> Optional[RuleHit]:
    if ctx.get("doc_type") != "labor_contract":
        return None
    if not any_of(t, WAGE_WORDS):
        return None
    wages = extract_wages(t)
    if not wages:
        return None
    th = _THRESHOLDS
    floors = {"day": th["unskilled_per_day"], "month": th["unskilled_per_month"]}
    below = [(a, u) for a, u in wages if a < floors[u]]
    unit_en, unit_hi = {"day": ("day", "दिन"), "month": ("month", "माह")}, None
    if below:
        a, u = below[0]
        farm = any_of(t, AGRI) or (ctx.get("doc_text") and any_of(norm(ctx["doc_text"]), AGRI))
        ev = f"Rs {a:g} per {u}"
        en = (f"The wage stated (Rs {a:g} per {u}) is below the Madhya Pradesh minimum wage for unskilled work "
              f"(Rs {th['unskilled_per_day']} per day / Rs {th['unskilled_per_month']:,} per month from {th['valid_from']}). Employers must pay at least the minimum wage.")
        hi = (f"यहां बताई गई मजदूरी (₹{a:g} प्रति {'दिन' if u == 'day' else 'माह'}) मध्य प्रदेश में अकुशल श्रमिक की न्यूनतम मजदूरी "
              f"(₹{th['unskilled_per_day']} प्रति दिन / ₹{th['unskilled_per_month']:,} प्रति माह, {th['valid_from']} से) से कम है। नियोक्ता को कम से कम न्यूनतम मजदूरी देनी होती है।")
        if farm:
            en += " NOTE: farm work may fall under a separate agricultural schedule that this system has not verified - please check."
            hi += " ध्यान दें: खेती के काम की न्यूनतम मजदूरी अलग हो सकती है, जिसकी इस सिस्टम ने अभी जांच नहीं की है - कृपया जांच लें।"
            return RuleHit("R9_BELOW_MIN_WAGE_AGRI_UNVERIFIED", "medium", ["code-on-wages-2019-mp-wage-rate-apr2026"], en, hi, ev)
        return RuleHit("R9_BELOW_MIN_WAGE", "high", ["code-on-wages-2019-mp-wage-rate-apr2026"], en, hi, ev)
    a, u = wages[0]
    return RuleHit(
        "R9_WAGE_MEETS_FLOOR", "low", ["code-on-wages-2019-mp-wage-rate-apr2026"],
        f"The wage stated (Rs {a:g} per {u}) meets the general minimum wage for unskilled work in Madhya Pradesh "
        f"(Rs {th['unskilled_per_day']} per day). Skilled work has a higher floor.",
        f"यहां बताई गई मजदूरी (₹{a:g} प्रति {'दिन' if u == 'day' else 'माह'}) मध्य प्रदेश में अकुशल श्रमिक की न्यूनतम मजदूरी "
        f"(₹{th['unskilled_per_day']} प्रति दिन) के बराबर या उससे अधिक है। कुशल काम के लिए न्यूनतम मजदूरी अधिक होती है।",
        f"Rs {a:g} per {u}")


# ---------------------------------------------------------------- public API

RULES: list[Rule] = [
    Rule("R6", r_force), Rule("R1", r_bonded), Rule("R2", r_interest), Rule("R4", r_seizure),
    Rule("R7", r_recourse), Rule("R3", r_no_notice), Rule("R5", r_no_record),
    Rule("R8", r_autorenew), Rule("R9", r_wage),
]


def run_rules(text: str, doc_type: Optional[str] = None, doc_text: Optional[str] = None) -> list[RuleHit]:
    """All rule hits for one clause, most severe first (ties keep the RULES order above)."""
    t = norm(text)
    ctx = {"doc_type": doc_type, "doc_text": doc_text}
    hits = [h for r in RULES if (h := r.detector(t, ctx))]
    return sorted(hits, key=lambda h: -SEVERITY_ORDER[h.severity])


def thresholds_warning(today: Optional[date] = None) -> Optional[str]:
    """Non-None if the wage floor is past its validity window - surface this in every verdict."""
    today = today or date.today()
    valid_to = date.fromisoformat(_THRESHOLDS["valid_to"])
    if today > valid_to:
        return (f"Minimum-wage figures expired on {valid_to} (MP revises every 1 April / 1 October). "
                f"Update law_thresholds.json before trusting any wage verdict.")
    return None


if __name__ == "__main__":
    demos = [
        ("If I cannot pay the money back, my son will work on Natthu Seth's farm until the full amount is paid off.", "loan_chit"),
        ("ब्याज नत्थू सेठ जो बोलेगा वो देना पड़ेगा।", "loan_chit"),
        ("Wage: Rs. 200 per day (deducted from the advance).", "labor_contract"),
        ("मजदूरी: प्रतिदिन ५०० रुपये, हर सप्ताह भुगतान।", "labor_contract"),
        ("Witness: Mohanlal, resident of Khajuri", "loan_chit"),
    ]
    for text, dt in demos:
        hits = run_rules(text, dt)
        print(f"\n[{dt}] {text}")
        print("   ->", [f"{h.rule_id}:{h.severity}" for h in hits] or "no rule fired")
