from app import app

# Vercel expects this exact variable name: "application"
application = app

# Optional: For local testing
if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)