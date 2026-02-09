"""
Script to add ASL MTD settings card and modal to administration.html
"""

# Read the file
with open('app/templates/administration.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Settings card HTML to insert after the "System State" card
settings_card = '''
      <div class="minimal-card p-6" style="cursor: pointer;" onclick="document.getElementById('aslSettingsModal').style.display='block';">
        <div class="kpi-icon-minimal bg-purple-50 text-purple-600 mb-4">
          <i class="fas fa-sliders-h"></i>
        </div>
        <div class="text-2xl font-black text-slate-800">ASL MTD</div>
        <div class="text-xs font-bold text-slate-400 uppercase tracking-widest mt-1">Filter Settings</div>
      </div>'''

# Find the closing </div> after "System State" and insert the card
# Look for the pattern: System State</div>\n      </div>\n    </div>
search_pattern = 'System State</div>\n      </div>\n    </div>'
if search_pattern in content:
    replacement = f'System State</div>\n      </div>{settings_card}\n    </div>'
    content = content.replace(search_pattern, replacement, 1)
    print("OK: Added ASL MTD settings card")
else:
    print("ERROR: Could not find insertion point for settings card")

# Add modal include before {% endblock %}
modal_include = "\n{% include 'asl_settings_modal.html' %}\n\n"
if "{% include 'asl_settings_modal.html' %}" not in content:
    content = content.replace('{% endblock %}', modal_include + '{% endblock %}')
    print("OK: Added modal include statement")
else:
    print("INFO: Modal include already exists")

# Write back
with open('app/templates/administration.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nSUCCESS: Administration page updated!")
