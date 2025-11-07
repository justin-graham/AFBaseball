import requests
import pandas as pd
import urllib.parse
USERNAME = "Justin.Graham@afacademy.af.edu"
SITENAME = "airforce-ncaabaseball"
MASTER_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyIjoiZjZlZWEwYzViZmUwZTY4ZmEwZDUyMGQyMDU2NTNmYzciLCJpYXQiOjE3NTc0MjE1NjF9.p940yyxhsJZp_gZFX-4Y4U48WqZrvbylDyY8Oj2u9q0"
TEAM_ID = "4806"
url = "https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken"
response = requests.post(url, json={"username": USERNAME, "sitename": SITENAME, "token": MASTER_TOKEN})
token = response.json()["pbTempToken"]
season_year = 2025
team_Id = 730205440
columns = "[G],[PA],[MC#],[MC%],[CC#],[CC%],[FrmRAA]"

format = "RAW"
# filters = "&filters=((game.gameDate%20%3E%3D%20'2025-02-15')%20AND%20(game.gameDate%20%3C%3D%20'2025-02-19%2023%3A59%3A59'))"
filters = "&filters=((game.gameDate%20%3E%3D%20'2025-02-15')%20AND%20(game.gameDate%20%3C%3D%20'2025-02-19%2023%3A59%3A59')%20AND%20((event.top)))"
columns_encoded = urllib.parse.quote(columns)
api_url = (
f"https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/TeamGames.csv"
f"?seasonYear={season_year}&teamId={team_Id}&columns={columns_encoded}&token={token}"
f"&format={format}{filters}"
)
data = pd.read_csv(api_url)
print(data.head())
right_filters = "&filters=((game.gameDate%20%3E%3D%20'2025-04-05')%20AND%20(game.gameDate%20%3C%3D%20'2025-04-05%2023%3A59%3A59')%20AND%20((event.pitcherHand%20%3D%20'R')))"
left_filters = "&filters=((game.gameDate%20%3E%3D%20'2025-02-14')%20AND%20(game.gameDate%20%3C%3D%20'2025-02-19%2023%3A59%3A59')%20AND%20((event.pitcherHand%20%3D%20'L')))"
