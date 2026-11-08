"""Normalize the App Store Connect .p8 key from the secret (pasted keys often lose line breaks)."""
import os, re, sys
def normalize(raw):
    body = re.sub(r'-----(BEGIN|END)[A-Z ]*-----', '', raw or '')
    body = re.sub(r'[^A-Za-z0-9+/=]', '', body)
    return '-----BEGIN PRIVATE KEY-----\n' + '\n'.join(body[i:i + 64] for i in range(0, len(body), 64)) + '\n-----END PRIVATE KEY-----\n'
if __name__ == '__main__':
    sys.stdout.write(normalize(os.environ.get('ASC_KEY_P8', '')))
