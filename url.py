# app.py  –  full, self-contained URL shortener
# Works on Windows 7 + Python 3.8  (Flask 2.2.5 / Werkzeug 2.2.3)

from flask import Flask, request, redirect, render_template_string
import sqlite3
import string
import random
from datetime import datetime

app = Flask(__name__)
DB_NAME = "urls.db"

# ---------- AUTO-DETECT BASE URL ----------
def get_base_url():
    """Return the protocol + host the user is currently using."""
    if request:
        return f"{request.scheme}://{request.host}"
    return "http://localhost:5000"

# ---------- DATABASE ----------
def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            long_url TEXT NOT NULL,
            short_code TEXT UNIQUE NOT NULL,
            clicks INTEGER DEFAULT 0,
            expiration TEXT
        )
        """)

def generate_short_code(length=6):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def cleanup_expired():
    now = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute(
            "DELETE FROM urls WHERE expiration IS NOT NULL AND expiration <= ?",
            (now,)
        )

# ---------- ROUTES ----------
@app.route("/", methods=["GET", "POST"])
def index():
    cleanup_expired()
    error = None
    short_url = None
    base_url = get_base_url()

    if request.method == "POST":
        long_url = request.form["long_url"]
        custom_code = request.form.get("custom_code")
        expiration_date = request.form.get("expiration_date")

        short_code = custom_code if custom_code else generate_short_code()
        expiration = expiration_date if expiration_date else None

        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.execute(
                    "INSERT INTO urls (long_url, short_code, expiration) VALUES (?, ?, ?)",
                    (long_url, short_code, expiration)
                )
            return redirect("/?created=" + short_code)
        except sqlite3.IntegrityError:
            error = "Custom code already exists."

    created = request.args.get("created")
    if created:
        short_url = f"{base_url}/{created}"

    with sqlite3.connect(DB_NAME) as conn:
        history = conn.execute(
            "SELECT short_code, long_url, clicks, expiration FROM urls ORDER BY id DESC LIMIT 10"
        ).fetchall()

    return render_template_string(TEMPLATE,
                                  short_url=short_url,
                                  history=history,
                                  error=error)

# ---------- DELETE ----------
@app.route("/delete", methods=["POST"])
def delete_url():
    short_code = request.form["short_code"]
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("DELETE FROM urls WHERE short_code = ?", (short_code,))
    return redirect("/")

# ---------- REDIRECT + PREVIEW ----------
@app.route("/<path:short_code>")
def redirect_url(short_code):
    preview = short_code.endswith("+")
    short_code = short_code[:-1] if preview else short_code

    cleanup_expired()

    with sqlite3.connect(DB_NAME) as conn:
        cur = conn.execute(
            "SELECT long_url, clicks FROM urls WHERE short_code = ?",
            (short_code,)
        )
        row = cur.fetchone()
        if not row:
            return "URL not found", 404

        long_url, clicks = row

        if preview:
            return PREVIEW_TEMPLATE.format(long_url=long_url, clicks=clicks, short_code=short_code)

        conn.execute(
            "UPDATE urls SET clicks = clicks + 1 WHERE short_code = ?",
            (short_code,)
        )
        return redirect(long_url)

# ---------- HTML TEMPLATES ----------
TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>xq by ExploitZ3r0 – Compress That Address!</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body{margin:0;font-family:Verdana,Arial,Helvetica,sans-serif;background:#fff;color:#000;text-align:center}
        #logo{margin:60px 0 20px}
        #logo img{height:120px}
        #main{max-width:520px;margin:0 auto;padding:0 10px}
        #urlBox{width:100%;padding:6px;font-size:16px;border:1px solid #999;box-sizing:border-box}
        #shortenBtn{margin-top:8px;padding:4px 18px;font-size:14px;cursor:pointer}
        #optionsToggle{font-size:11px;margin-left:6px;cursor:pointer}
        #options{display:none;margin-top:8px;text-align:left;font-size:13px}
        #options label{display:block;margin-bottom:4px}
        #options input{width:100%;padding:4px;margin-bottom:8px;box-sizing:border-box}
        #result{margin-top:12px;font-size:14px;word-break:break-all}
        #result a{color:#c00;text-decoration:none}
        #result a:hover{text-decoration:underline}
        #error{margin-top:8px;color:#c00;font-size:13px}
        table{width:100%;margin-top:15px;font-size:.85rem;border-collapse:collapse}
        td,th{padding:6px;word-break:break-all;border-bottom:1px solid #ddd}
        th{color:#c00;text-align:left}
    </style>
</head>
<body>

<div id="logo">
    <img src="https://trejduu32-code.github.io/supreme-engine/xq.png" alt="xq by ExploitZ3r0">
</div>

<div id="main">
    <form method="post">
        <input id="urlBox" name="long_url" type="url" placeholder="Enter a long URL to shorten…" required>
        <br>
        <button id="shortenBtn" type="submit">Shorten!</button>
        <span id="optionsToggle">▼ Further options/custom URL</span>

        <div id="options">
            <label>Custom short code (optional)</label>
            <input id="customCode" name="custom_code" type="text" placeholder="e.g. mylink">
            <label>Expiration date (optional)</label>
            <input id="expDate" name="expiration_date" type="date">
        </div>
    </form>

    {% if error %}<div id="error">{{ error }}</div>{% endif %}
    {% if short_url %}
    <div id="result">
        <strong>Your shortened URL:</strong><br>
        <a href="{{ short_url }}" target="_blank">{{ short_url }}</a>
    </div>
    {% endif %}

    {% if history %}
    <table>
        <tr><th>Short</th><th>Clicks</th><th>Expires</th><th>Action</th></tr>
        {% for h in history %}
        <tr>
            <td>
                <a href="/{{ h[0] }}" target="_blank">{{ h[0] }}</a>
                <a href="/{{ h[0] }}+" title="Preview">+</a>
            </td>
            <td>{{ h[2] }}</td>
            <td>{{ h[3] if h[3] else "Never" }}</td>
            <td>
                <form method="post" action="/delete" style="display:inline;">
                    <input type="hidden" name="short_code" value="{{ h[0] }}">
                    <button style="padding:2px 6px;font-size:12px">Del</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
    {% endif %}
</div>

<script>
const optionsToggle=document.getElementById('optionsToggle');
const optionsDiv=document.getElementById('options');
optionsToggle.addEventListener('click',()=>{
    const open=optionsDiv.style.display==='block';
    optionsDiv.style.display=open?'none':'block';
    optionsToggle.textContent=open?'▼ Further options/custom URL':'▲ Hide options';
});
</script>

</body>
</html>
"""

PREVIEW_TEMPLATE = """
<html><body style="background:#fff;color:#000;font-family:Verdana,Arial,Helvetica,sans-serif;
display:flex;align-items:center;justify-content:center;height:100vh;">
<div style="border:1px solid #ccc;padding:25px;width:420px;text-align:center;">
<h2 style="color:#c00;">Link Preview</h2>
<p>Redirects to:</p>
<a href="{long_url}" style="color:#c00;" target="_blank">{long_url}</a>
<p>Clicks: {clicks}</p>
<a href="/{short_code}">
<button style="margin-top:15px;padding:8px 16px;">Continue →</button>
</a>
</div></body></html>
"""

# ---------- START ----------
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)