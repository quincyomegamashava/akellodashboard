import re

# Read the original file
with open(r'c:\Users\quincy.mashava\Desktop\Akello\akellodashboard\app\templates\aplanforprojects.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract the main script section (everything between <script> and </script> after line 377)
# Find the large script block
script_pattern = r'<script>\s*/\* ---------- Configuration ---------- \*/.*?</script>'
script_match = re.search(script_pattern, content, re.DOTALL)

if script_match:
    main_script = script_match.group(0)
    
    # Extract the styles
    style_pattern = r'<style>(.*?)</style>'
    style_matches = re.findall(style_pattern, content, re.DOTALL)
    
    # Combine all styles except the first one (which is just :root)
    combined_styles = '\n'.join(style_matches)
    
    # Create the new template
    new_template = '''{% extends "base.html" %}

{% block head_extra %}
  <script src="https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js"></script>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.css">
  <script src="https://cdn.jsdelivr.net/npm/frappe-gantt@0.6.1/dist/frappe-gantt.min.js"></script>

  <script>
    const current_user = { username: "{{current_user.username}}", id: "{{ current_user.id }}" }; 
  </script>

  <style>
''' + combined_styles + '''
  </style>
{% endblock %}

{% block content %}
'''
    
    # Extract the main content (from line 214 to 363 approximately)
    # This is the main container with the project board
    content_pattern = r'<div class="w3-full login-container mx-auto">(.*?)</div>\s*<div id="modalBackdrop"'
    content_match = re.search(content_pattern, content, re.DOTALL)
    
    if content_match:
        main_content = content_match.group(1)
        # Replace w3-full login-container with max-w-[1800px]
        new_template += '''<div class="max-w-[1800px] mx-auto">
''' + main_content + '''
</div>

'''
    
    # Add the modal
    modal_pattern = r'(<div id="modalBackdrop".*?</div>\s*</div>)'
    modal_match = re.search(modal_pattern, content, re.DOTALL)
    if modal_match:
        new_template += modal_match.group(1) + '\n'
    
    new_template += '''{% endblock %}

{% block scripts %}
'''
    new_template += main_script
    new_template += '''
{% endblock %}
'''
    
    # Write the new template
    with open(r'c:\Users\quincy.mashava\Desktop\Akello\akellodashboard\app\templates\aplanforprojects.html', 'w', encoding='utf-8') as f:
        f.write(new_template)
    
    print("Template conversion completed successfully!")
    print(f"New template length: {len(new_template)} characters")
else:
    print("Could not find the main script section")
