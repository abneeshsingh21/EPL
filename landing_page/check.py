import re

with open('src/main.epl', 'r') as f:
    lines = f.readlines()

blocks = []
for i, line in enumerate(lines):
    line_clean = line.strip()
    if line_clean.startswith('Comment ') or line_clean.startswith('Note:'):
        continue
    
    # Blocks that take End
    if line_clean.startswith('Style '): blocks.append((i+1, 'Style'))
    elif line_clean.startswith('Route '): blocks.append((i+1, 'Route'))
    elif line_clean.startswith('Page '): blocks.append((i+1, 'Page'))
    elif line_clean.startswith('Script'): blocks.append((i+1, 'Script'))
    elif line_clean.startswith('Div '): blocks.append((i+1, 'Div'))
    elif line_clean.startswith('Section '): blocks.append((i+1, 'Section'))
    elif line_clean.startswith('Nav '): blocks.append((i+1, 'Nav'))
    elif line_clean.startswith('Flex '): blocks.append((i+1, 'Flex'))
    elif line_clean.startswith('Grid '): blocks.append((i+1, 'Grid'))
    elif line_clean == 'End':
        if blocks:
            print(f"Line {i+1}: End closes {blocks.pop()}")
        else:
            print(f"Line {i+1}: EXTRA END FOUND")

if blocks:
    print("UNCLOSED BLOCKS:", blocks)
