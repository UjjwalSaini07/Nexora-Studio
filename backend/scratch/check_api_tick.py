# backend/scratch/check_api_tick.py
import requests
import json

def main():
    url = "http://localhost:8080/v1/tick"
    payload = {
        "now": "2026-06-29T23:00:00Z",
        "available_triggers": ["trg_081_chronic_refill_due_m_011_dr_sameer_dent"]
    }
    
    print("Calling /v1/tick ...")
    resp = requests.post(url, json=payload)
    print(f"Status Code: {resp.status_code}")
    print("Response Headers:")
    for k, v in resp.headers.items():
        print(f"  {k}: {v}")
    try:
        data = resp.json()
        print(f"Response JSON: {json.dumps(data, indent=2)}")
    except Exception as exc:
        print(f"Failed to parse JSON: {exc}")
        print(f"Raw Text: {resp.text}")

if __name__ == "__main__":
    main()
