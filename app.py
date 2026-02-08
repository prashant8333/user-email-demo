import os
import logging
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from jinja2 import Template

# Load environment variables (works locally; Render uses dashboard env vars)
load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")

# Log warning if env vars are missing
if not SENDGRID_API_KEY or not SENDER_EMAIL:
    logging.warning("SENDGRID_API_KEY or SENDER_EMAIL not set")

app = Flask(__name__)

# Health check
@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({"message": "Server is running!"}), 200


# Send email endpoint
@app.route("/send-email", methods=["POST"])
def send_email():
    data = request.get_json(silent=True) or {}

    recipient = data.get("email")
    name = data.get("name")

    if not recipient or not name:
        return jsonify({"error": "Missing email or name"}), 400

    # Load HTML email template
    try:
        with open("templates/email_template.html", "r", encoding="utf-8") as f:
            template = Template(f.read())
    except FileNotFoundError:
        return jsonify({"error": "Email template not found"}), 500

    html_content = template.render(name=name)

    try:
        if not SENDGRID_API_KEY:
            return jsonify({"error": "SendGrid API key not configured"}), 500

        sg = SendGridAPIClient(SENDGRID_API_KEY)

        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=recipient,
            subject="Personalized Email",
            html_content=html_content
        )

        response = sg.send(message)

        return jsonify({
            "message": "Email accepted",
            "status": response.status_code
        }), 202

    except Exception as e:
        logging.exception("SendGrid error")
        return jsonify({"error": "Failed to send email"}), 500


# Local run only (Render ignores this)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
