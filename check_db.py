from app.db import get_client

def check():
    c = get_client()
    try:
        r = c.table('locations').select('id', count='exact').limit(1).execute()
        print("Locations count:", r.count)
    except Exception as e:
        print("Error locations:", e)

    try:
        r2 = c.table('listings').select('id', count='exact').limit(1).execute()
        print("Listings count:", r2.count)
    except Exception as e:
        print("Error listings:", e)

if __name__ == '__main__':
    check()
