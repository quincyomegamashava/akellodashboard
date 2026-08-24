"""Render standalone HBC HTML games and bank-item payloads from catalog specs."""

from __future__ import annotations

import json
import re
from typing import Any


ZIM_PLACES = [
    "Harare", "Bulawayo", "Mutare", "Gweru", "Masvingo", "Victoria Falls",
    "Kariba", "Hwange", "Chinhoyi", "Bindura",
]
ZIM_RIVERS = ["Zambezi", "Save", "Limpopo", "Mazowe", "Gwayi"]
ZIM_CROPS = ["maize", "tobacco", "cotton", "sugarcane", "groundnuts"]


def _pool_for(spec: dict) -> list[dict]:
    """Build ≥10 parameterized MCQ templates for a subject/topic."""
    subject = spec["subject"]
    topic = spec["topic_slug"]
    age = spec["age_range"]
    templates: list[dict] = []

    def add(qid, prompt, options, correct, explain, hint_key="generic"):
        templates.append({
            "id": qid,
            "prompt": prompt,
            "options": options,
            "correctIndex": correct,
            "explain": explain,
            "hintKey": hint_key,
        })

    if subject == "Mathematics":
        prompts = [
            ("A farmer near {place} packs {a} bags of maize with {b} cobs each. Total cobs?",
             lambda a, b: a * b, "Multiply bags × cobs.", "multiplied"),
            ("Learners share {a} pencils among {b} groups equally. How many each?",
             lambda a, b: a // b if b else 0, "Divide total by groups.", "divided"),
            ("What is {a} + {b}?", lambda a, b: a + b, "Add the numbers.", "added"),
            ("What is {a} − {b}?", lambda a, b: a - b, "Subtract the smaller from the larger.", "subtracted"),
            ("Find {a}% of {b}.", lambda a, b: (a * b) // 100, "Percent means parts per hundred.", "percent"),
            ("A rectangle is {a} m by {b} m. Area?", lambda a, b: a * b, "Area = length × width.", "area"),
            ("Perimeter of a {a} by {b} rectangle?", lambda a, b: 2 * (a + b), "Perimeter = 2(L+W).", "perimeter"),
            ("Ratio {a}:{b} simplified first term when gcd divides both — if equal parts of {a}+{b}, first share of {a}+{b}?",
             lambda a, b: a, "First part of the ratio.", "ratio"),
            ("Average of {a} and {b}?", lambda a, b: (a + b) // 2, "Add then divide by 2.", "average"),
            ("{a} × {b} = ?", lambda a, b: a * b, "Multiply.", "multiplied"),
            ("How many minutes in {a} hours and {b} minutes?", lambda a, b: a * 60 + b, "1 hour = 60 minutes.", "time"),
            ("Change for ${a} after buying goods of ${b}?", lambda a, b: a - b, "Subtract cost from cash.", "money"),
        ]
        for i, (tmpl, fn, explain, hint) in enumerate(prompts[:12], 1):
            add(
                f"math_{topic}_{i}",
                tmpl + " (use values shown on the card)",
                ["A", "B", "C", "D"],  # filled at runtime in JS
                0,
                explain,
                hint,
            )
        # Mark math as procedural so JS generates numbers
        for t in templates:
            t["mode"] = "math"
            t["topic"] = topic

    elif subject == "English Language":
        bank = [
            ("Which word is a noun?", ["Harare", "quickly", "run", "beautiful"], 0, "Harare names a place."),
            ("Which word is a verb?", ["dance", "happy", "red", "school"], 0, "Dance is an action."),
            ("Choose the correct sentence.", ["She go to school.", "She goes to school.", "She going school.", "She gone school."], 1, "Singular subject needs goes."),
            ("Pick the synonym of 'happy'.", ["sad", "joyful", "angry", "tired"], 1, "Joyful means happy."),
            ("Pick the antonym of 'hot'.", ["warm", "cold", "fire", "sun"], 1, "Cold is opposite of hot."),
            ("Correct punctuation: \"where is mutare\"", ["Where is Mutare?", "where is Mutare.", "Where is mutare!", "where Is Mutare?"], 0, "Capitalize and end with ?"),
            ("Fill: The ___ is flowing.", ["river", "run", "quickly", "blue"], 0, "River is the noun subject."),
            ("Which is a proper noun?", ["city", "mountain", "Zambezi", "river"], 2, "Zambezi is a named river."),
            ("Choose past tense of 'walk'.", ["walks", "walking", "walked", "walk"], 2, "Add -ed for past."),
            ("Best meaning of 'brave'.", ["afraid", "courageous", "sleepy", "noisy"], 1, "Brave means courageous."),
            ("Article: ___ apple", ["a", "an", "thee", "on"], 1, "Use an before vowel sounds."),
            ("Plural of 'child'.", ["childs", "children", "childes", "child"], 1, "Irregular plural: children."),
        ]
        for i, (p, opts, c, e) in enumerate(bank, 1):
            add(f"eng_{topic}_{i}", p, opts, c, e)

    elif subject in ("Social Science", "Geography"):
        bank = [
            ("Capital city of Zimbabwe?", ["Lusaka", "Harare", "Gaborone", "Maputo"], 1, "Harare is the capital."),
            ("Victoria Falls is on which river?", ["Save", "Limpopo", "Zambezi", "Nile"], 2, "Victoria Falls is on the Zambezi."),
            ("Great Zimbabwe is near which city?", ["Mutare", "Masvingo", "Kariba", "Hwange"], 1, "Near Masvingo."),
            ("Which is a highland area?", ["Eastern Highlands", "Save Valley floor only", "Kalahari centre", "Indian Ocean"], 0, "Eastern Highlands are elevated."),
            ("Main staple crop in many Zimbabwe farms?", ["maize", "pineapples only", "cocoa", "olives"], 0, "Maize is a staple."),
            ("Map scale 1:50 000 means 1 cm represents?", ["50 cm", "500 m", "50 km", "5 m"], 1, "50 000 cm = 500 m."),
            ("A contour line joins points of equal?", ["rainfall", "temperature", "height", "population"], 2, "Contours show height."),
            ("Kariba Dam is mainly for?", ["hydro-electric power", "desert sand", "airport", "football"], 0, "Kariba generates power."),
            ("Which direction is north of Bulawayo toward Victoria Falls roughly?", ["south", "north-west", "east only", "south-east"], 1, "Victoria Falls lies north-west of Bulawayo."),
            ("Hwange is known for?", ["national park wildlife", "deep ocean port", "ice skating", "oil wells only"], 0, "Hwange National Park."),
            ("A settlement with many shops and offices is often a?", ["city", "forest only", "glacier", "volcano"], 0, "Cities are urban settlements."),
            ("Trade across the Beitbridge border connects Zimbabwe with?", ["South Africa", "Canada", "Japan only", "Iceland"], 0, "Beitbridge links to South Africa."),
        ]
        for i, (p, opts, c, e) in enumerate(bank, 1):
            add(f"geo_{topic}_{i}", p, opts, c, e)

    elif subject in ("Science and Technology", "Combined Science"):
        bank = [
            ("Unit of force?", ["newton", "joule only", "watt only", "metre"], 0, "Force is measured in newtons."),
            ("F = m × a. If m=2 and a=3, F=?", ["5", "6", "1", "9"], 1, "Multiply mass × acceleration."),
            ("Solar panels convert sunlight mainly into?", ["electrical energy", "sound only", "smell", "gravity"], 0, "Photovoltaic conversion."),
            ("In a series circuit, current is?", ["the same through components", "always zero", "only in parallel paths", "random"], 0, "Series current is shared equally."),
            ("Water boiling point at standard pressure?", ["100°C", "0°C", "50°C", "200°C"], 0, "Water boils at 100°C."),
            ("Plants make food mainly by?", ["photosynthesis", "rusting", "evaporation only", "condensation only"], 0, "Photosynthesis."),
            ("A conductor of electricity?", ["copper wire", "dry wood", "rubber glove", "plastic ruler"], 0, "Metals like copper conduct."),
            ("Speed = distance ÷ time. 100 km in 2 h?", ["50 km/h", "200 km/h", "102 km/h", "25 km/h"], 0, "Divide distance by time."),
            ("States of matter include?", ["solid, liquid, gas", "hot and cold only", "north and south", "red and blue"], 0, "Three common states."),
            ("Renewable energy example?", ["hydro at Kariba", "coal only", "petrol only", "diesel only"], 0, "Hydro is renewable."),
            ("Mole is a unit of?", ["amount of substance", "length", "time", "temperature"], 0, "Amount of substance."),
            ("Friction usually?", ["opposes motion", "creates free energy", "removes gravity", "stops time"], 0, "Friction opposes motion."),
        ]
        for i, (p, opts, c, e) in enumerate(bank, 1):
            add(f"sci_{topic}_{i}", p, opts, c, e)

    elif subject == "ICT":
        bank = [
            ("CPU stands for?", ["Central Processing Unit", "Computer Personal User", "Cable Power Utility", "Copy Paste Undo"], 0, "Central Processing Unit."),
            ("Which stores data permanently until erased?", ["hard drive / SSD", "RAM only while powered", "CPU cache only", "monitor"], 0, "Secondary storage."),
            ("A strong password should be?", ["long and mixed characters", "your name only", "1234", "password"], 0, "Use length and mix."),
            ("HTTP is used to?", ["transfer web pages", "cook food", "measure rain", "paint walls"], 0, "Web protocol."),
            ("Input device example?", ["keyboard", "speaker", "monitor only", "printer only"], 0, "Keyboard inputs data."),
            ("Malware is?", ["harmful software", "a printer cable", "a school subject", "a river"], 0, "Malicious software."),
            ("Binary digit is called a?", ["bit", "byte only", "pixel only", "file"], 0, "Bit = binary digit."),
            ("LAN usually covers?", ["a small local area", "the whole planet only", "outer space", "one molecule"], 0, "Local Area Network."),
            ("Spreadsheet best for?", ["tables and calculations", "playing video only", "watering crops", "singing"], 0, "Rows, columns, formulas."),
            ("Cloud storage means?", ["data kept on remote servers", "data only on paper", "data in rain clouds", "data deleted forever"], 0, "Remote networked storage."),
            ("Algorithm is?", ["step-by-step instructions", "a type of monitor", "a virus only", "a keyboard key"], 0, "Ordered steps to solve a problem."),
            ("Phishing tries to?", ["steal information by deception", "speed up CPU", "charge a battery", "print faster"], 0, "Social engineering fraud."),
        ]
        for i, (p, opts, c, e) in enumerate(bank, 1):
            add(f"ict_{topic}_{i}", p, opts, c, e)

    else:
        for i in range(1, 13):
            add(f"gen_{i}", f"Practice item {i} for {subject}", ["Option A", "Option B", "Option C", "Option D"], 0, "Review the topic notes.")

    # Age-flavoured instruction tag
    for t in templates:
        t["ageRange"] = age
    return templates[:12]


def build_bank_items(spec: dict, pool: list[dict]) -> list[dict]:
    """One featured selectable quiz per game (ensures ≥5 bank items per subject×age)."""
    featured = pool[0] if pool else {
        "id": "q01",
        "prompt": f"Warm-up for {spec['title']}",
        "options": ["A", "B", "C", "D"],
        "correctIndex": 0,
        "explain": "See game for details.",
    }
    # Prefer a static (non-math procedural) item for race snapshot reliability
    static = next((p for p in pool if p.get("mode") != "math"), featured)
    if static.get("mode") == "math":
        # Provide a concrete snapshot for races
        prompt = "What is 6 + 7?"
        options = ["13", "12", "14", "11"]
        correct = 0
        explain = "6 + 7 = 13."
    else:
        prompt = static["prompt"]
        options = list(static["options"])
        correct = int(static["correctIndex"])
        explain = static.get("explain") or ""

    return [{
        "slug": "featured",
        "item_kind": "quiz",
        "title": f"{spec['topic_title']} — featured",
        "prompt": prompt,
        "payload_json": {
            "options": options,
            "correct_index": correct,
            "explain": explain,
        },
        "points_default": 5,
        "sort_order": 0,
    }]


def render_hbc_game_html(spec: dict) -> str:
    pool = _pool_for(spec)
    content = {
        "learningArea": spec["subject"],
        "topic": f"{spec['subject']} - {spec['topic_title']}",
        "ageRange": spec["age_range"],
        "totalRounds": 10,
        "maxScore": 10,
        "places": ZIM_PLACES,
        "rivers": ZIM_RIVERS,
        "crops": ZIM_CROPS,
        "questionPool": pool,
        "hints": {
            "generic": "Check the key idea and try again.",
            "multiplied": "You may have added instead of multiplying.",
            "divided": "You may have multiplied instead of dividing.",
            "added": "Check addition carefully.",
            "subtracted": "Check which number comes first in subtraction.",
            "percent": "Remember: percent means out of 100.",
            "area": "Area uses multiplication of sides.",
            "perimeter": "Perimeter adds all sides (or 2(L+W)).",
            "ratio": "Keep parts of the ratio in order.",
            "average": "Add values then divide by how many.",
            "time": "Convert hours to minutes first.",
            "money": "Change = money given − cost.",
        },
    }
    content_json = json.dumps(content, ensure_ascii=False)
    title = spec["title"]
    safe_title = re.sub(r"[<>]", "", title)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: "Segoe UI", system-ui, sans-serif;
      background: #ffffff;
      color: #0f172a;
      min-height: 100vh;
      padding: 16px;
    }}
    .wrap {{ max-width: 760px; margin: 0 auto; }}
    header {{ display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: flex-start; margin-bottom: 12px; }}
    h1 {{ font-size: 1.25rem; line-height: 1.3; }}
    .meta {{ font-size: .85rem; color: #64748b; margin-top: 4px; }}
    #scoreBox {{ background: #fff; padding: 8px 14px; border-radius: 12px; font-weight: 700; border: 1px solid #e2e8f0; }}
    .progress {{ display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }}
    .pip {{ width: 22px; height: 8px; border-radius: 99px; background: #e2e8f0; border: none; padding: 0; cursor: pointer; }}
    .pip.on {{ background: #0f172a; }}
    .pip.done {{ background: #64748b; }}
    .card {{ background: #fff; border-radius: 16px; padding: 18px; border: 1px solid #e2e8f0; }}
    #prompt {{ font-size: 1.15rem; line-height: 1.5; margin-bottom: 14px; font-weight: 600; }}
    .choices {{ display: grid; gap: 10px; }}
    .choice {{
      min-height: 52px; text-align: left; padding: 12px 14px; border: 2px solid #e2e8f0;
      border-radius: 12px; background: #fff; font-weight: 600; cursor: pointer; font-size: 1rem;
    }}
    .choice:hover {{ border-color: #94a3b8; }}
    .choice.sel {{ border-color: #0f172a; background: #f8fafc; }}
    .choice.ok {{ border-color: #334155; background: #f1f5f9; }}
    .choice.bad {{ border-color: #c62828; background: #ffcdd2; }}
    .feedback {{ min-height: 52px; margin-top: 12px; font-size: .95rem; line-height: 1.4; }}
    .actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
    .act {{
      min-height: 48px; padding: 10px 16px; border: none; border-radius: 12px;
      font-weight: 700; cursor: pointer;
    }}
    #prevBtn {{ background: #64748b; color: #fff; }}
    #nextBtn {{ background: #0f172a; color: #fff; }}
    #nextBtn:disabled, #checkBtn:disabled, #prevBtn:disabled {{ opacity: .4; cursor: not-allowed; }}
    #checkBtn {{ background: #1e293b; color: #fff; }}
    #hintBtn {{ background: #f1f5f9; }}
    .pip.draft {{ background: #cbd5e1; }}
    @media (max-width: 560px) {{ h1 {{ font-size: 1.05rem; }} }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <div>
        <h1 id="gameTitle">{safe_title}</h1>
        <p class="meta" id="metaLine"></p>
      </div>
      <div id="scoreBox">Score: 0 / 10</div>
    </header>
    <div class="progress" id="progress"></div>
    <div id="resultsPanel" class="card" style="display:none;margin-bottom:12px;"></div>
    <div class="card">
      <div id="prompt"></div>
      <div class="choices" id="choices"></div>
      <div class="feedback" id="feedback" aria-live="polite"></div>
      <div class="actions">
        <button type="button" class="act" id="hintBtn">Hint</button>
        <button type="button" class="act" id="prevBtn" disabled>Previous</button>
        <button type="button" class="act" id="nextBtn">Next</button>
        <button type="button" class="act" id="checkBtn" disabled>Submit answers</button>
      </div>
    </div>
  </div>
  <script>
    const CONTENT = {content_json};

    function initializeGameSession(pool) {{
      let shuffledPool = pool.slice();
      for (let i = shuffledPool.length - 1; i > 0; i--) {{
        const j = Math.floor(Math.random() * (i + 1));
        const t = shuffledPool[i];
        shuffledPool[i] = shuffledPool[j];
        shuffledPool[j] = t;
      }}
      return shuffledPool.slice(0, CONTENT.totalRounds);
    }}

    function rnd(min, max) {{
      return Math.floor(Math.random() * (max - min + 1)) + min;
    }}

    function pick(arr) {{
      return arr[Math.floor(Math.random() * arr.length)];
    }}

    function shuffleInPlace(arr) {{
      for (let i = arr.length - 1; i > 0; i--) {{
        const j = Math.floor(Math.random() * (i + 1));
        const t = arr[i]; arr[i] = arr[j]; arr[j] = t;
      }}
      return arr;
    }}

    function materialize(item) {{
      if (item.mode !== "math") {{
        return {{
          prompt: item.prompt,
          options: item.options.slice(),
          correctIndex: item.correctIndex,
          explain: item.explain,
          hintKey: item.hintKey || "generic"
        }};
      }}
      let a = rnd(2, 12);
      let b = rnd(2, 12);
      const place = pick(CONTENT.places || ["Harare"]);
      let answer = 0;
      let prompt = item.prompt;
      const id = item.id || "";
      if (id.indexOf("_1") >= 0 || /bags/.test(prompt)) {{
        answer = a * b;
        prompt = "A farmer near " + place + " packs " + a + " bags of maize with " + b + " cobs each. Total cobs?";
      }} else if (/share|among|groups/.test(prompt) || id.indexOf("_2") >= 0) {{
        a = rnd(12, 36); b = [2, 3, 4, 6][rnd(0, 3)];
        while (a % b !== 0) a++;
        answer = a / b;
        prompt = "Learners share " + a + " pencils among " + b + " groups equally. How many each?";
      }} else if (/\\+/.test(prompt) && !/%/.test(prompt)) {{
        answer = a + b;
        prompt = "What is " + a + " + " + b + "?";
      }} else if (/\\u2212|-/.test(prompt) && /What is/.test(prompt)) {{
        if (b > a) {{ const t = a; a = b; b = t; }}
        answer = a - b;
        prompt = "What is " + a + " − " + b + "?";
      }} else if (/%/.test(prompt)) {{
        a = [10, 20, 25, 50][rnd(0, 3)]; b = rnd(40, 200);
        answer = Math.round(a * b / 100);
        prompt = "Find " + a + "% of " + b + ".";
      }} else if (/Area/.test(prompt)) {{
        answer = a * b;
        prompt = "A rectangle is " + a + " m by " + b + " m. Area?";
      }} else if (/Perimeter/.test(prompt)) {{
        answer = 2 * (a + b);
        prompt = "Perimeter of a " + a + " by " + b + " rectangle?";
      }} else if (/Average/.test(prompt)) {{
        answer = Math.floor((a + b) / 2);
        prompt = "Average of " + a + " and " + b + "?";
      }} else if (/minutes/.test(prompt)) {{
        a = rnd(1, 4); b = rnd(0, 50);
        answer = a * 60 + b;
        prompt = "How many minutes in " + a + " hours and " + b + " minutes?";
      }} else if (/Change|\\$/.test(prompt)) {{
        a = rnd(20, 100); b = rnd(5, a - 1);
        answer = a - b;
        prompt = "Change for $" + a + " after buying goods of $" + b + "?";
      }} else {{
        answer = a * b;
        prompt = "What is " + a + " × " + b + "?";
      }}
      const distractors = new Set();
      while (distractors.size < 3) {{
        const d = answer + rnd(-5, 5);
        if (d !== answer && d >= 0) distractors.add(d);
      }}
      const options = shuffleInPlace([answer].concat(Array.from(distractors)).map(String));
      return {{
        prompt: prompt,
        options: options,
        correctIndex: options.indexOf(String(answer)),
        explain: item.explain + " Correct answer: " + answer + ".",
        hintKey: item.hintKey || "generic"
      }};
    }}

    function prepareMathText(text) {{
      var t = String(text || "");
      if (!t) return t;
      if (window.QuizMath && window.QuizMath.prepareMathText) return window.QuizMath.prepareMathText(t);
      if (t.indexOf("$") >= 0 || t.indexOf("\\\\(") >= 0 || t.indexOf("\\\\[") >= 0) return t;
      t = t.replace(/\\\\frac\\s*\\{{[^{{}}]*\\}}\\s*\\{{[^{{}}]*\\}}/g, function (m) {{ return "$" + m + "$"; }});
      return t;
    }}

    function typesetQuiz() {{
      var root = document.querySelector(".wrap") || document.body;
      if (window.QuizMath && window.QuizMath.typesetMath) {{
        window.QuizMath.typesetMath(root);
        return;
      }}
      if (window.renderMathInElement) {{
        window.renderMathInElement(root, {{
          delimiters: [
            {{left: "$$", right: "$$", display: true}},
            {{left: "\\\\[", right: "\\\\]", display: true}},
            {{left: "$", right: "$", display: false}},
            {{left: "\\\\(", right: "\\\\)", display: false}}
          ],
          throwOnError: false
        }});
      }}
    }}

    function escapeHtml(s) {{
      return String(s || "").replace(/[&<>"']/g, function (c) {{
        return {{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[c];
      }});
    }}

    let score = 0;
    let index = 0;
    let session = [];
    let materializedSession = [];
    let drafts = [];
    let finalized = false;
    let current = null;
    let selected = null;

    const els = {{
      scoreBox: document.getElementById("scoreBox"),
      prompt: document.getElementById("prompt"),
      choices: document.getElementById("choices"),
      feedback: document.getElementById("feedback"),
      prevBtn: document.getElementById("prevBtn"),
      nextBtn: document.getElementById("nextBtn"),
      checkBtn: document.getElementById("checkBtn"),
      hintBtn: document.getElementById("hintBtn"),
      progress: document.getElementById("progress"),
      meta: document.getElementById("metaLine")
    }};

    function draftCount() {{
      return drafts.filter(function (d) {{ return d !== null && d !== undefined; }}).length;
    }}

    function updateScore() {{
      if (finalized) {{
        els.scoreBox.textContent = "Score: " + score + " / " + CONTENT.maxScore;
      }} else {{
        els.scoreBox.textContent = "Answered: " + draftCount() + " / " + CONTENT.totalRounds;
      }}
    }}

    function allDraftsFilled() {{
      return draftCount() >= CONTENT.totalRounds;
    }}

    function updateActions() {{
      els.prevBtn.disabled = finalized ? index <= 0 : index <= 0;
      if (finalized) {{
        els.nextBtn.disabled = index >= CONTENT.totalRounds - 1;
        els.checkBtn.disabled = true;
        return;
      }}
      els.nextBtn.disabled = index >= CONTENT.totalRounds - 1;
      els.checkBtn.disabled = !allDraftsFilled();
    }}

    function renderProgress() {{
      els.progress.innerHTML = "";
      for (let i = 0; i < CONTENT.totalRounds; i++) {{
        const pip = document.createElement("button");
        pip.type = "button";
        pip.className = "pip"
          + (i === index ? " on" : "")
          + (drafts[i] !== null && drafts[i] !== undefined ? " draft" : "")
          + (finalized ? " done" : "");
        pip.title = "Question " + (i + 1);
        pip.addEventListener("click", function () {{
          if (index === i) return;
          saveDraft();
          index = i;
          showRound();
        }});
        els.progress.appendChild(pip);
      }}
    }}

    function saveDraft() {{
      if (finalized || selected === null) return;
      drafts[index] = selected;
      updateScore();
      renderProgress();
      updateActions();
    }}

    function showRound() {{
      selected = drafts[index];
      if (!finalized) {{
        els.feedback.textContent = drafts[index] !== null && drafts[index] !== undefined
          ? "Answer saved — you can change it until you submit."
          : "";
      }}
      if (!materializedSession[index]) {{
        materializedSession[index] = materialize(session[index]);
      }}
      current = materializedSession[index];
      els.prompt.textContent = prepareMathText(current.prompt);
      els.choices.innerHTML = "";
      current.options.forEach(function (opt, i) {{
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "choice";
        if (selected === i) btn.classList.add("sel");
        if (finalized) {{
          if (i === current.correctIndex) btn.classList.add("ok");
          if (i === drafts[index] && drafts[index] !== current.correctIndex) btn.classList.add("bad");
          btn.disabled = true;
        }}
        btn.textContent = prepareMathText(opt);
        btn.addEventListener("click", function () {{
          if (finalized) return;
          selected = i;
          Array.prototype.forEach.call(els.choices.children, function (c) {{ c.classList.remove("sel"); }});
          btn.classList.add("sel");
          saveDraft();
        }});
        els.choices.appendChild(btn);
      }});
      if (finalized && drafts[index] !== null && drafts[index] !== undefined) {{
        const ok = drafts[index] === current.correctIndex;
        if (ok) {{
          els.feedback.textContent = "Correct. " + current.explain;
        }} else {{
          const distractorHint = CONTENT.hints[current.hintKey] || CONTENT.hints.generic;
          els.feedback.textContent = "Not quite. " + distractorHint + " " + current.explain;
        }}
      }}
      renderProgress();
      updateScore();
      updateActions();
      typesetQuiz();
    }}

    function finalizeAll() {{
      if (finalized) return;
      score = 0;
      const reviewRows = [];
      for (let i = 0; i < CONTENT.totalRounds; i++) {{
        if (!materializedSession[i]) {{
          materializedSession[i] = materialize(session[i]);
        }}
        const q = materializedSession[i];
        const pick = drafts[i];
        const ok = pick === q.correctIndex;
        if (ok) score += 1;
        reviewRows.push({{
          n: i + 1,
          prompt: q.prompt,
          your: (pick !== null && pick !== undefined) ? q.options[pick] : "(blank)",
          correct: q.options[q.correctIndex],
          ok: ok,
          explain: q.explain
        }});
      }}
      finalized = true;
      index = 0;
      const panel = document.getElementById("resultsPanel");
      if (panel) {{
        const pct = CONTENT.maxScore ? Math.round((score / CONTENT.maxScore) * 100) : 0;
        panel.style.display = "block";
        panel.innerHTML = "<h2 style=\\"font-size:1.1rem;margin-bottom:8px;\\">Results: " + score + " / " + CONTENT.maxScore + " (" + pct + "%)</h2>"
          + "<p style=\\"margin-bottom:12px;color:#64748b;\\">Review each question below. Use Previous / Next or the progress dots.</p>"
          + "<ol style=\\"padding-left:1.2rem;display:grid;gap:10px;\\">"
          + reviewRows.map(function (r) {{
              return "<li style=\\"margin-bottom:4px;\\"><strong style=\\"color:" + (r.ok ? "#0f172a" : "#c62828") + ";\\">"
                + (r.ok ? "Correct" : "Incorrect") + "</strong> — " + escapeHtml(prepareMathText(r.prompt))
                + "<br/><span style=\\"font-size:.9rem;\\">Your answer: " + escapeHtml(prepareMathText(r.your))
                + (r.ok ? "" : (" · Correct: " + escapeHtml(prepareMathText(r.correct))))
                + "</span><br/><span style=\\"font-size:.85rem;color:#555;\\">" + escapeHtml(prepareMathText(r.explain)) + "</span></li>";
            }}).join("")
          + "</ol>";
      }}
      showRound();
      updateScore();
      const finalScore = score;
      const maxScore = CONTENT.maxScore;
      if (window.gameScoreSubmit) {{
        window.gameScoreSubmit(finalScore, maxScore);
      }} else if (window.parent && window.parent.submitGameScore) {{
        const gameIdMatch = window.location.pathname.match(/\\/play-game\\/(\\d+)/);
        if (gameIdMatch) {{
          window.parent.submitGameScore(parseInt(gameIdMatch[1], 10), finalScore, maxScore);
        }}
      }}
      els.feedback.textContent = "Submitted! Scroll up for the full review. Score: " + finalScore + " / " + maxScore;
    }}

    els.hintBtn.addEventListener("click", function () {{
      if (!current || finalized) return;
      els.feedback.textContent = CONTENT.hints[current.hintKey] || CONTENT.hints.generic;
    }});

    els.prevBtn.addEventListener("click", function () {{
      if (index <= 0) return;
      saveDraft();
      index -= 1;
      showRound();
    }});

    els.nextBtn.addEventListener("click", function () {{
      if (index >= CONTENT.totalRounds - 1) return;
      saveDraft();
      index += 1;
      showRound();
    }});

    els.checkBtn.addEventListener("click", function () {{
      saveDraft();
      if (!allDraftsFilled()) {{
        els.feedback.textContent = "Answer all questions before submitting.";
        return;
      }}
      finalizeAll();
    }});

    els.meta.textContent = CONTENT.learningArea + " · Ages " + CONTENT.ageRange;
    session = initializeGameSession(CONTENT.questionPool);
    materializedSession = new Array(CONTENT.totalRounds);
    drafts = new Array(CONTENT.totalRounds).fill(null);
    showRound();
    (function waitMath() {{
      if (window.renderMathInElement) typesetQuiz();
      else setTimeout(waitMath, 80);
    }})();
  </script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js"></script>
</body>
</html>
"""


def generate_game_bundle(spec: dict) -> dict[str, Any]:
    pool = _pool_for(spec)
    html = render_hbc_game_html(spec)
    bank = build_bank_items(spec, pool)
    return {"html": html, "bank_items": bank, "pool_size": len(pool)}
