import requests
from django.conf import settings


def send_invite_email(to_email: str, invite_link: str, org_name: str):
    resp = requests.post(
        f"https://api.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": settings.MAILGUN_FROM,
            "to": [to_email],
            "subject": f"{org_name} daveti",
            "text": (
                f"{org_name} organizasyonuna davet edildin.\n"
                f"Davet linki: {invite_link}\n"
            ),
        },
        timeout=15,
    )

    resp.raise_for_status()
    return resp.json()
