from flask import Flask, request
import subprocess
import os
import hmac
import hashlib

app = Flask(__name__)

# Secret for GitHub Webhook (We will set this later)
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'my_secret_key')

def verify_signature(payload_body, secret_token, signature_header):
    """Verify that the payload was sent from GitHub by validating SHA256."""
    if not signature_header:
        return False
    hash_object = hmac.new(secret_token.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

@app.route('/webhook', methods=['POST'])
def webhook():
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_signature(request.data, WEBHOOK_SECRET, signature):
        return "Signature mismatch", 403

    if request.method == 'POST':
        # Execute the update script
        subprocess.Popen(['bash', 'deploy.sh'])
        return 'Update triggered', 200
    else:
        return 'Invalid method', 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
