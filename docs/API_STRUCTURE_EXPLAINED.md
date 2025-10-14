# Home Depot Workshop API Structure - Explained

## Real Example Data (October 13, 2025)

From the actual API response for "Build an Excavator" workshops:

```json
{
    "workshopEventWsDTO": [
        {
            "code": "KWBE0001",
            "workshopId": "KWBE0001",
            "startTime": "2025-11-08T08:30:00-0500",
            "workshopStatus": "ACTIVE",
            "workshopType": "KID",
            "attendeeLimit": 96,
            "remainingSeats": 0,
            "eventType": {
                "workshopEventId": "WS00029",
                "name": "Build an Excavator",
                "shortCode": "KWBE"
            }
        },
        {
            "code": "KWBE0002",
            "workshopId": "KWBE0002",
            "startTime": "2025-11-08T10:30:00-0500",
            "workshopStatus": "ACTIVE",
            "workshopType": "KID",
            "attendeeLimit": 96,
            "remainingSeats": 0,
            "eventType": {
                "workshopEventId": "WS00029",
                "name": "Build an Excavator",
                "shortCode": "KWBE"
            }
        }
    ]
}
```

## Key Understanding

### Multiple Workshop Codes, Same Event ID
- **Workshop Event ID**: `WS00029` (same for all "Build an Excavator" sessions)
- **Workshop Codes**: `KWBE0001`, `KWBE0002` (different for each time slot)

### Registration URL Structure
```
https://www.homedepot.ca/api/workshopsvc/v1/workshops/{workshopEventId}/events/{workshopId}/signups
```

**Example URLs:**
- For KWBE0001: `https://www.homedepot.ca/api/workshopsvc/v1/workshops/WS00029/events/KWBE0001/signups`
- For KWBE0002: `https://www.homedepot.ca/api/workshopsvc/v1/workshops/WS00029/events/KWBE0002/signups`

## How the Scraper Processes These

### KWBE0001 (8:30 AM Session)
```
✅ Workshop ID starts with "KW": KWBE0001 ✓
✅ Start time is 8:30 AM: 2025-11-08T08:30:00-0500 ✓
❌ At least 1 person registered: 0 seats taken (96 remaining) ✗

Decision: Skip (waiting for someone else to register first)
```

### KWBE0002 (10:30 AM Session)
```
✅ Workshop ID starts with "KW": KWBE0002 ✓
❌ Start time is 8:30 AM: 2025-11-08T10:30:00-0500 ✗

Decision: Skip (not 8:30 AM session)
```

## Registration Logic Flow

1. **Scraper runs every 15 minutes** (via cron)
2. **Fetches all workshops** from API
3. **For each workshop:**
   - Extract `workshopId` (e.g., "KWBE0001")
   - Extract `workshopEventId` from `eventType` (e.g., "WS00029")
   - Extract `startTime` (e.g., "2025-11-08T08:30:00-0500")
   - Check if it matches criteria

4. **If workshop matches all criteria:**
   - Workshop ID starts with "KW" ✓
   - Start time contains "08:30" ✓
   - At least 1 person has registered ✓

5. **Then register using:**
   ```python
   register_home_depot_workshop(
       event_code="KWBE0001",        # workshopId
       workshop_event_id="WS00029"   # eventType.workshopEventId
   )
   ```

6. **Registration request:**
   ```
   POST https://www.homedepot.ca/api/workshopsvc/v1/workshops/WS00029/events/KWBE0001/signups
   Body: {
       "customer": {...},
       "workshopEventCode": "KWBE0001",
       "store": "7265",
       "participantCount": 2,
       ...
   }
   ```

## Current Status (October 13, 2025)

Both workshops are **fully booked**:
- KWBE0001: 0 seats remaining (96/96 taken)
- KWBE0002: 0 seats remaining (96/96 taken)

The scraper would have sent alerts when these opened, but **would not have auto-registered** because the "don't be first" logic requires waiting until at least 1 person registers first.

## What Would Happen If These Were Available

### Scenario 1: KWBE0001 just opened (96 seats available)
```
⏭️ Skipping auto-registration:
• Event: Build an Excavator
• Workshop ID: KWBE0001
• Date: Saturday, November 08, 2025 at 08:30 AM
• Seats Left: 96
• Reason: No one has registered yet (seats taken: 0). Waiting for someone else to register first.
```

### Scenario 2: Someone registers, 95 seats left
```
🎯 Auto-registering for workshop:
• Event Code: WS00029
• Workshop ID: KWBE0001
• Title: Build an Excavator
• Date: Saturday, November 08, 2025 at 08:30 AM
• Seats Left: 95
• Reason: Workshop matches criteria: ID starts with 'KW', starts at 8:30 AM, and 1 person(s) already registered

✅ Successfully registered:
• Event: Build an Excavator
• Workshop ID: KWBE0001
• Workshop Event ID: WS00029
• Date: Saturday, November 08, 2025 at 08:30 AM
• Link: https://www.homedepot.ca/workshops?storeId=7265
```

## Testing

To test with this exact workshop:
```bash
cd /home/pi/Projects/pyppeteer-scraper
source venv/bin/activate
python scraper/home_depo.py
```

The scraper will process these workshops and send appropriate Slack notifications.

