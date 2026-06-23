"""Extract PM JS blocks from aplanforprojects.html into separate modules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
tpl_path = ROOT / "app/templates/aplanforprojects.html"
js_dir = ROOT / "app/static/js/pm"
lines = tpl_path.read_text(encoding="utf-8").splitlines()


def extract(start, end, name, header):
    chunk = "\n".join(lines[start - 1 : end])
    (js_dir / name).write_text(header + "\n" + chunk + "\n", encoding="utf-8")


extract(2128, 2355, "pm-calendar.js", "/** Calendar views — requires PM globals from template. */")
extract(2356, 2542, "pm-gantt-helpers.js", "/** Gantt helpers — requires PM globals from template. */")
extract(2544, 2765, "pm-gantt.js", "/** Gantt schedule render — requires PM globals from template. */")
extract(3409, 3720, "pm-board-render.js", "/** Board load/render — requires PM globals from template. */")
extract(4068, 4375, "pm-task-modal.js", "/** Task details modal — requires PM globals from template. */")

ranges = [(4068, 4375), (3409, 3720), (2544, 2765), (2356, 2542), (2128, 2355)]
for start, end in ranges:
    del lines[start - 1 : end]

text = "\n".join(lines)
needle = "<script src=\"{{ url_for('static', filename='js/pm/pm-export.js') }}\"></script>"
insert = needle + """
  <script src="{{ url_for('static', filename='js/pm/pm-gantt-helpers.js') }}"></script>
  <script src="{{ url_for('static', filename='js/pm/pm-calendar.js') }}"></script>
  <script src="{{ url_for('static', filename='js/pm/pm-gantt.js') }}"></script>
  <script src="{{ url_for('static', filename='js/pm/pm-board-render.js') }}"></script>
  <script src="{{ url_for('static', filename='js/pm/pm-task-modal.js') }}"></script>"""
if needle in text and "pm-board-render.js" not in text:
    text = text.replace(needle, insert)

tpl_path.write_text(text, encoding="utf-8")
print("Done — extracted", len(ranges), "modules")
