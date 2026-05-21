import sqlite3

conn = sqlite3.connect('leadforge.db')
cur = conn.cursor()

draft = """Subject: Quick question about your website

Hi there,

I noticed a few quick wins on your website that could bring in more leads without any ad spend.

Would it be worth a quick 10-minute chat?

Best,
Faizan"""

cur.execute('SELECT id, business_name, email FROM leads WHERE campaign_id=2 AND email IS NOT NULL')
rows = cur.fetchall()

for row in rows:
    cur.execute('UPDATE leads SET email_draft=?, status="audited" WHERE id=?', (draft, row[0]))
    print(f'Updated: {row[1]} -> {row[2]}')

conn.commit()
print(f'\nDone! Updated {len(rows)} leads')
conn.close()
