import subprocess
import json

def main():
    cmd = [
        r"C:\Users\Thiago\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd",
        "logging", "read",
        'resource.type="cloud_run_revision" AND resource.labels.service_name="flexflow-app"',
        "--limit=300",
        "--format=json"
    ]
    try:
        out = subprocess.check_output(cmd).decode('utf-8', errors='ignore')
        logs = json.loads(out)
        print(f"Total logs: {len(logs)}")
        for log in reversed(logs):
            timestamp = log.get('timestamp', '')
            payload = log.get('textPayload', '')
            if timestamp > "2026-06-09T04:25:30Z":
                print(f"[{timestamp}] {payload.strip()}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    main()
