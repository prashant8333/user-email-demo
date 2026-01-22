from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

from app import create_app

app = create_app()
print(app.url_map)

if __name__ == '__main__':
    app.run(debug=True, port=5002)
