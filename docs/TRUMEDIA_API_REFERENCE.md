# TruMedia API Reference

## Overview

This document explains the correct way to query the TruMedia Baseball API based on working examples.

---

## Authentication

All queries require a temporary token:

```typescript
const response = await fetch('https://api.trumedianetworks.com/v1/siteadmin/api/createTempPBToken', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    username: "Justin.Graham@afacademy.af.edu",
    sitename: "airforce-ncaabaseball",
    token: MASTER_TOKEN
  })
});
const { pbTempToken } = await response.json();
```

---

## Key Endpoints

### 1. PlayerTotals.csv - **For Team Rosters** ✅

**Use Case**: Get all players for a specific team with their aggregate stats

**URL Pattern**:
```
https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/PlayerTotals.csv
```

**Required Parameters**:
- `seasonYear` - e.g., 2025
- `seasonType` - REG (regular season) or PLY (playoffs)
- `token` - temporary auth token

**Optional Parameters**:
- `columns` - stats to include: `[PA],[AVG],[HR]` etc.
- `filters` - filter by team: `((team.teamId = 4806))`
- `qualification` - minimum stats: `[PA] >= 10`

**Example** (Team Roster):
```typescript
const columns = encodeURIComponent('[PA]');
const filters = encodeURIComponent('((team.teamId = 4806))');
const url = `PlayerTotals.csv?seasonYear=2025&seasonType=REG&columns=${columns}&filters=${filters}&token=${token}`;
```

**Returns**:
- `player.playerId` - TruMedia player ID
- `player.playerName` - Player full name
- `team.teamId` - Team ID
- `team.teamName` - Team name
- Plus any stats columns requested

---

### 2. AllTeams.csv - **For All Teams**

**Use Case**: Get list of all teams in a season

**URL Pattern**:
```
https://api.trumedianetworks.com/v1/mlbapi/custom/baseball/DirectedQuery/AllTeams.csv
```

**Required Parameters**:
- `seasonYear` - e.g., 2025
- `token` - temporary auth token

**Example**:
```typescript
const url = `AllTeams.csv?seasonYear=2025&token=${token}`;
```

**Returns**:
- `team.teamId` - Team ID (e.g., 4806 for Air Force)
- `team.teamName` - Team name
- `team.conference` - Conference
- Other team metadata

---

### 3. PlayerSeasons.csv - **For Individual Player Stats**

**Use Case**: Get season-by-season breakdown for specific players

**Required Parameters**:
- `seasonYear` - e.g., 2025
- `seasonType` - REG or PLY
- `playerId` OR `teamId` - to scope the query
- `token` - temporary auth token

**Example** (Air Force pitchers):
```typescript
const url = `PlayerSeasons.csv?seasonYear=2025&seasonType=REG&teamId=4806&token=${token}`;
```

---

### 4. PlayerGames.csv - **For Game-by-Game Stats**

**Use Case**: Get individual game performance for players

**Required Parameters**:
- `seasonYear` - e.g., 2025
- `playerId` - specific player ID
- `token` - temporary auth token

**Optional Filters**:
- Date range: `(game.gameDate >= '2025-04-01') AND (game.gameDate <= '2025-04-30')`
- Pitch type: `(event.pitchType IN ('FF','SI'))`

**Example** (Used in pitching reports):
```typescript
const filters = `(game.gameDate >= '2025-04-26') AND (game.gameDate <= '2025-04-26')`;
const url = `PlayerGames.csv?seasonYear=2025&playerId=1469809434&filters=${encodeURIComponent(filters)}&token=${token}`;
```

---

## Common Filters

### Filter by Team
```
((team.teamId = 4806))
```

### Filter by Date Range
```
(game.gameDate >= '2025-03-01') AND (game.gameDate <= '2025-05-31')
```

### Filter by Pitch Type
```
(event.pitchType IN ('FF','SI','FT'))  // Fastballs
(event.pitchType = 'SL')               // Sliders
```

### Filter by Count
```
(event.balls = 0 AND event.strikes = 0)  // First pitch
(event.balls = 3 AND event.strikes = 2)  // Full count
```

---

## Working Scripts

### Sync Team Roster (TypeScript)
See: [web/src/app/api/sync-roster/route.ts](../web/src/app/api/sync-roster/route.ts)

Uses `PlayerTotals.csv` with team filter to get Air Force roster.

### Fetch All Players (Python)
See: [scripts/utils/fetch_all_players.py](../scripts/utils/fetch_all_players.py)

Comprehensive example of using `PlayerTotals.csv` to fetch all players.

### Fetch All Teams (Python)
See: [scripts/utils/fetch_all_teams.py](../scripts/utils/fetch_all_teams.py)

Example of using `AllTeams.csv` to get team list.

---

## Key Learnings

### ✅ DO Use PlayerTotals.csv When:
- Getting a team roster
- Need aggregate season stats
- Want to filter by team or conference
- Building leaderboards

### ❌ DON'T Use PlayerSeasons.csv When:
- Just need a simple roster
- Don't need season-by-season breakdown
- Querying by team (use PlayerTotals instead)

### 🎯 Best Practice for Team Roster:
```typescript
// ✅ CORRECT - Simple and reliable
PlayerTotals.csv?seasonYear=2025&seasonType=REG&filters=((team.teamId=4806))

// ❌ AVOID - More complex, less reliable for rosters
PlayerSeasons.csv?seasonYear=2025&seasonType=REG&teamId=4806
```

---

## Air Force Specific

**Team ID**: `4806`
**Team Name**: Air Force Academy
**Conference**: Mountain West (typically)

**Common Queries**:

```typescript
// Get current roster
PlayerTotals.csv?seasonYear=2025&seasonType=REG&filters=((team.teamId=4806))

// Get pitching stats for a player
PlayerGames.csv?seasonYear=2025&playerId=1469809434&columns=[Vel],[Spin],[K|PIT]

// Get team schedule
AllGames.csv?seasonYear=2025&teamId=4806
```

---

## Column Reference

Common stat abbreviations (use in `columns` parameter):

**Hitting**: `[PA]`, `[AB]`, `[H]`, `[HR]`, `[RBI]`, `[AVG]`, `[OBP]`, `[SLG]`
**Pitching**: `[IP]`, `[ERA]`, `[K|PIT]`, `[BB|PIT]`, `[WHIP]`, `[Vel]`, `[Spin]`
**Advanced**: `[ExitVel]`, `[LaunchAngle]`, `[SpinRate]`, `[Extension]`

See full glossary: `https://airforce-ncaabaseball.trumedianetworks.com/baseball/glossary`

---

## Support

- **NCAA Support**: ncaasupport@trumedianetworks.com
- **Documentation**: PDF included in project root
- **Working Examples**: `fetch_all_*.py` scripts in project root

---

## Updated: 2025-10-28
Based on working scripts provided by user.
