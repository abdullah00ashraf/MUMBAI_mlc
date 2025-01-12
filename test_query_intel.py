import os
import sqlite3

def run_verification():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "clients_intelligence_db.sqlite")
    if not os.path.exists(db_path):
        print(f"[FATAL] SQLite database not found at: {db_path}")
        return

    print("-" * 75)
    print("SENTINEL V7: CLIENTS ENRICHED DATABASE VERIFICATION")
    print("-" * 75)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Verify counts
    tables = ["sectors", "clients", "contacts", "scraped_insights"]
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"Table '{table:18}' rows: {count}")

    print("-" * 75)
    print("SAMPLE ENRICHED RECORD EXTRACTION (1 CLIENT PER SECTOR)")
    print("-" * 75)

    # Query one client per sector with enriched fields
    query = """
        SELECT c.id, c.name, s.name, co.email, co.phone, 
               ci.commitments, ci.tech_shifts, ci.hurdles, ci.losses,
               ci.linkedin_url, ci.recent_news_headline, ci.recent_news_snippet,
               ci.financial_status, ci.esg_brsr_status
        FROM clients c
        JOIN sectors s ON c.sector_id = s.id
        JOIN contacts co ON c.id = co.client_id
        JOIN scraped_insights ci ON c.id = ci.client_id
        GROUP BY c.sector_id
    """
    cursor.execute(query)
    records = cursor.fetchall()

    for r in records:
        (c_id, name, sector, email, phone, commitments, tech_shifts, hurdles, losses,
         linkedin_url, recent_news_headline, recent_news_snippet, financial_status, esg_brsr_status) = r
        
        # Replace Rupee symbol with INR to prevent Windows encoding crashes
        commitments = commitments.replace('₹', 'INR')
        tech_shifts = tech_shifts.replace('₹', 'INR')
        hurdles = hurdles.replace('₹', 'INR')
        losses = losses.replace('₹', 'INR')
        recent_news_headline = recent_news_headline.replace('₹', 'INR')
        recent_news_snippet = recent_news_snippet.replace('₹', 'INR')
        financial_status = financial_status.replace('₹', 'INR')
        esg_brsr_status = esg_brsr_status.replace('₹', 'INR')

        print(f"Client ID      : {c_id}")
        print(f"Name           : {name}")
        print(f"Sector         : {sector}")
        print(f"Email Contact  : {email}")
        print(f"Phone Contact  : {phone}")
        print(f"LinkedIn Page  : {linkedin_url}")
        print(f"News Headline  : {recent_news_headline}")
        print(f"News Snippet   : {recent_news_snippet}")
        print(f"Financials     : {financial_status}")
        print(f"ESG BRSR State : {esg_brsr_status}")
        print(f"Commitments    : {commitments}")
        print(f"Tech Shifts    : {tech_shifts}")
        print(f"Hurdles        : {hurdles}")
        print(f"Losses         : {losses}")
        print("-" * 75)

    conn.close()

if __name__ == "__main__":
    run_verification()
