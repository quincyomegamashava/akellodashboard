import sys

# Read the file in binary mode
with open('app/routes.py', 'rb') as f:
    data = f.read()

# Count null bytes
null_count = data.count(b'\x00')
print(f'File size: {len(data)} bytes')
print(f'Null bytes found: {null_count}')

if null_count > 0:
    # Remove null bytes
    cleaned = data.replace(b'\x00', b'')
    
    # Write back
    with open('app/routes.py', 'wb') as f:
        f.write(cleaned)
    
    print(f'✓ Removed {null_count} null bytes from routes.py')
else:
    print('✓ No null bytes found')
