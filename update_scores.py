import requests
import json
import os
import subprocess
from datetime import datetime

# --- CONFIGURATION ---
# The leagues you want to track
# PL=Premier League, PD=La Liga, CL=Champions League, BL1=Bundesliga, SA=Serie A
LEAGUES = ["PL", "PD", "CL", "BL1", "SA"] 

def load_api_key(script_dir):
    """Safely loads the API Key from secrets.json"""
    secrets_path = os.path.join(script_dir, 'secrets.json')
    try:
        with open(secrets_path) as f:
            secrets = json.load(f)
            return secrets.get('api_key')
    except FileNotFoundError:
        print(f"CRITICAL ERROR: secrets.json not found at {secrets_path}")
        return None
    except json.JSONDecodeError:
        print(f"CRITICAL ERROR: secrets.json is not valid JSON.")
        return None

def run():
    # 1. Setup Paths
    # This ensures the script works even when run by Cron
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 2. Load Credentials
    api_key = load_api_key(script_dir)
    if not api_key:
        exit(1)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data...")
    
    # 3. Fetch Data from API
    # We fetch all matches for TODAY
    today = datetime.now().strftime("%Y-%m-%d")
    url = f"https://api.football-data.org/v4/matches?dateFrom={today}&dateTo={today}"
    headers = {"X-Auth-Token": api_key}
    
    try:
        response = requests.get(url, headers=headers)
        matches_out = []
        
        if response.status_code == 200:
            data = response.json()
            for match in data.get('matches', []):
                # Filter by our selected leagues
                if match['competition']['code'] in LEAGUES:
                    matches_out.append({
                        "league": match['competition']['name'],
                        "home": match['homeTeam']['name'],
                        "away": match['awayTeam']['name'],
                        "home_score": match['score']['fullTime']['home'],
                        "away_score": match['score']['fullTime']['away'],
                        "status": match['status'], # 'IN_PLAY', 'FINISHED', 'PAUSED', 'TIMED'
                        "minute": match.get('minute')
                    })
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return

        # 4. Save to JSON File
        data_folder = os.path.join(script_dir, 'data')
        os.makedirs(data_folder, exist_ok=True)
        
        json_path = os.path.join(data_folder, 'matches.json')
        
        # We overwrite the file every time
        with open(json_path, 'w') as f:
            json.dump({
                "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                "matches": matches_out
            }, f, indent=4)
        
        print(f"Saved {len(matches_out)} matches to {json_path}")

        # 5. Git Operations (Push to GitHub)
        # We change directory to the repo folder so git commands work
        os.chdir(script_dir)
        
        # Configure Git (Local only)
        subprocess.run(["git", "config", "user.email", "bot@soccerwidget.com"], check=False)
        subprocess.run(["git", "config", "user.name", "ScoreBot"], check=False)

        # Stage the data file
        subprocess.run(["git", "add", "data/matches.json"], check=True)
        
        # Check if there are changes to commit
        status = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        
        if not status.stdout.strip():
            print("No changes in data. Skipping push.")
            return

        # Intelligent Commit:
        # If the repo has history, we AMEND (overwrite) the last commit to keep history clean.
        # If it's the first time, we do a normal commit.
        try:
            # Check if HEAD exists
            subprocess.check_call(["git", "rev-parse", "--verify", "HEAD"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # If yes, overwrite previous commit
            subprocess.run(["git", "commit", "--amend", "-m", "Live Score Update", "--allow-empty"], check=True)
            subprocess.run(["git", "push", "-f", "origin", "main"], check=True)
            print("Successfully FORCE pushed update.")
            
        except subprocess.CalledProcessError:
            # If no HEAD (First run), normal commit
            subprocess.run(["git", "commit", "-m", "Initial Commit"], check=True)
            subprocess.run(["git", "push", "-u", "origin", "main"], check=True)
            print("Successfully pushed initial commit.")

    except Exception as e:
        print(f"Script Error: {e}")

if __name__ == "__main__":
    run()
