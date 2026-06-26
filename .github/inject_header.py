import glob, re

LOGO_BLOCK = (
    '<div style="text-align:center;margin-bottom:20px">'
    '<img src="/ch-tools/assets/logo-green.svg" alt="Cheshire Horse" '
    'style="height:72px;width:auto;display:inline-block">'
    '</div>'
)

EXTRA_CSS = """<style>
.staticrypt-page{background:#f6f8f6}
.staticrypt-form-wrapper{padding-top:24px !important}
#staticrypt-password:focus{border-color:#056A45;
  box-shadow:0 0 0 3px rgba(5,106,69,0.1);outline:none}
</style>
"""

files = glob.glob('**/*.html', recursive=True) + glob.glob('*.html')
seen = set()
for path in files:
    if path in seen:
        continue
    seen.add(path)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'staticrypt-html' not in content:
        continue

    # debug: print the body structure of the first encrypted file
    if path == 'index.html':
        body_start = content.find('<body')
        print('=== index.html body (first 800 chars) ===')
        print(content[body_start:body_start+800])
        print('==========================================')

    # inject logo before the first staticrypt div that wraps the form
    injected = re.sub(
        r'(<div[^>]*staticrypt-form[^>]*>)',
        LOGO_BLOCK + r'\1',
        content,
        count=1
    )
    if injected == content:
        print(f'WARNING: injection point not found in {path}')
    content = injected

    # fix button label (input type=submit value="DECRYPT")
    content = re.sub(r'value="DECRYPT"', 'value="LOGIN"', content, flags=re.IGNORECASE)

    # inject extra CSS
    content = content.replace('</head>', EXTRA_CSS + '</head>', 1)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Branded: {path}')
