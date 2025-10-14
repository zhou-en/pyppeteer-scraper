# Cron Schedule Recommendations for Home Depot Workshop Scraper

## Current Cron Schedule
```
0,30 7-17 * * 1,2,3 cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/home_depo.py > /tmp/stdout.log 2> /tmp/stderr.log
```

**Translation:** Runs every 30 minutes from 7 AM to 5 PM, only on Monday, Tuesday, and Wednesday.

## Issues with Current Schedule

1. **Limited Days**: Only runs Mon-Wed, but workshops can open any day of the week
2. **Limited Time Window**: 7 AM - 5 PM might miss early morning or evening openings
3. **30-minute interval**: Might be too infrequent if workshops fill up quickly
4. **Too Early**: Workshops open after 10 AM, so running at 6-7 AM wastes API calls

## Recommended Schedule

### Option 1: Balanced Approach (Recommended)
```
*/15 10-20 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/home_depo.py > /tmp/stdout.log 2> /tmp/stderr.log
```

**Benefits:**
- Runs every 15 minutes (4 times per hour)
- **10 AM to 8 PM coverage** (starts when workshops actually open)
- Every day of the week
- ~44 API calls per day
- Low risk of detection (reasonable frequency)
- No wasted calls before 10 AM

### Option 2: Conservative Approach
```
*/20 10-19 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/home_depo.py > /tmp/stdout.log 2> /tmp/stderr.log
```

**Benefits:**
- Runs every 20 minutes (3 times per hour)
- **10 AM to 7 PM coverage** (business hours)
- Every day of the week
- ~30 API calls per day
- Very low risk of detection
- Efficient timing

### Option 3: Aggressive Approach (Use with Caution)
```
*/10 10-20 * * * cd /home/pi/Projects/pyppeteer-scraper; venv/bin/python scraper/home_depo.py > /tmp/stdout.log 2> /tmp/stderr.log
```

**Benefits:**
- Runs every 10 minutes (6 times per hour)
- **10 AM to 8 PM coverage**
- Every day of the week
- ~66 API calls per day
- Higher detection risk, but faster response time

## How to Update Cron Job

1. Open crontab editor:
```bash
crontab -e
```

2. Replace the existing line with your chosen schedule

3. Save and exit

4. Verify the cron job is active:
```bash
crontab -l
```

## Monitoring

- Check logs regularly: `/tmp/stdout.log` and `/tmp/stderr.log`
- Watch Slack notifications for alerts
- If you receive rate limiting errors or API blocks, reduce frequency

## Notes

- The scraper now includes "don't be first to register" logic
- Slack notifications will be sent for both registered and skipped workshops
- The scraper waits until at least 1 person has registered before attempting to register
- **Workshops open after 10 AM**, so no need to start checking earlier
