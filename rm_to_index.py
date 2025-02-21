import os
import shutil
import markdown

# Create source/html directory if it doesn't exist
os.makedirs('source/html', exist_ok=True)

# Copy README.md to source/html/index.md
shutil.copy2('README.md', 'source/html/index.md')

# Read the content of index.md with UTF-8 encoding
with open('source/html/index.md', 'r', encoding='utf-8') as file:
    content = file.read()

# Replace 'source/' with '../'
modified_content = content.replace('source/', '../')

# Write the modified content back to index.md with UTF-8 encoding
with open('source/html/index.md', 'w', encoding='utf-8') as file:
    file.write(modified_content)

# Convert markdown to HTML and save as index.html
markdown.markdownFromFile(
    input='source/html/index.md',
    output='source/html/index.html',
    encoding='utf-8'
)

print("Files have been successfully created and modified.")
