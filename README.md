SafePock: Your Digital Medical ID
Ever had that fleeting thought—what would happen in an emergency? How would doctors know your blood type, your allergies, or who to call? We built SafePock to answer that question. It’s a simple, secure web app that keeps your most important medical information ready at a moment's notice, accessible through a QR code on your phone or in your wallet.

It's peace of mind, in your pocket.

What Can It Do?
Separate, Secure Logins: SafePock has two sides. A private one for patients to view their info, and another for an administrator who can help manage all the user profiles. It keeps everything organized and secure.

All Your Vital Info in One Place: You can store all the key details first responders need:

Your Name, Birthday, and Blood Type

Emergency Contacts

Allergies & Chronic Conditions

Current Medications & Implants

Your Doctor's Information

An Instant-Access QR Code: This is the core of SafePock. Every user gets a unique QR code. When scanned with any smartphone camera, it pulls up a simple, mobile-friendly page with their vital info. No logins, no passwords—just the information needed to help, right away.

How It's Built (The Tech Stuff)
Backend: Python and Flask. Flask is a fantastic framework that's lightweight but powerful enough to get the job done without extra bloat.

Database: MongoDB with a Zero-Config Fallback. We chose MongoDB for its flexibility with varied medical data. However, if the app can't connect to a MongoDB server, it seamlessly falls back to using a local JSON file (data/users.json) for storage. This means you can run the app immediately without any database setup.

Frontend: A dynamic, mobile-first public profile page is generated directly from the backend using styled HTML.

Handy Tools:

ngrok: Still a great tool for putting the app on the public internet for testing.

python-dotenv: To keep our secret keys and configuration out of the main code.

Werkzeug: We use its ProxyFix middleware to ensure URL generation for QR codes works correctly even when behind a proxy like ngrok.

Let's Get You Set Up
Want to run your own copy of SafePock? It's pretty straightforward.

What You'll Need:
Python (version 3.9 or newer is best)

Git (for cloning the project)

MongoDB (Recommended for full functionality, but the app will work without it!)

ngrok (Optional, for public testing)

Installation Steps:
First, grab the code:

Bash

git clone https://github.com/[your-username]/SafePock.git
cd SafePock
Create a cozy little virtual space for it:
This keeps its dependencies separate from your other Python projects.

Bash

# On macOS or Linux
python3 -m venv venv
source venv/bin/activate

# On Windows
python -m venv venv
venv\Scripts\activate
Install all the required packages:

Bash

pip install -r requirements.txt
Tell the app your secrets:
Create a .env file for your private settings. Just copy the example file to get started.

Bash

cp .env.example .env
Now, open that new .env file and fill in your details. Here's what they mean:

Ini, TOML

# A strong, random secret key for Flask sessions
SECRET_KEY="pick_a_really_good_secret_password_here"

# Your MongoDB connection string. 
# LEAVE THIS BLANK to use the simple JSON file database.
MONGO_URI="mongodb://localhost:2717"

# The name of the database to use in MongoDB. Defaults to "medapp" in the code.
MONGO_DB="medapp"

# (Optional) The port you want the app to run on.
PORT=5000

# (Optional) For advanced setups or deployment, you can force the base URL for QR codes.
# BASE_URL="https://your-domain.com"
Launch it!

Bash

python app.py
You will see a message in your terminal with the addresses where your app is running.

---
Your app is running and accessible at:
  Local:   http://localhost:5000
  Network: http://192.168.1.10:5000
---
Testing the QR Code
To test the QR code, you need to access the app from your phone. Here are a few ways to do it:

Option 1: Use the Network Link (Easiest)
As long as your phone is on the same Wi-Fi network as your computer, you can use the "Network" URL that appears when you launch the app (e.g., http://192.168.1.10:5000). The QR codes generated will automatically point to this address, so they'll work on your local network.

Option 2: Use ngrok (For Public Access)
If you need to test from a different network, ngrok is the perfect tool. Open a new terminal window and type:

Bash

ngrok http 5000
Use the https:// link ngrok gives you to access your app from anywhere. The app is smart enough to know it's behind a proxy and will generate the correct QR code URLs.
