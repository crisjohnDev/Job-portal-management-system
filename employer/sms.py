import requests
from django.conf import settings


def send_sms(phone_number, message):
    url = "https://api.semaphore.co/api/v4/messages"

    data = {
        "apikey": settings.SEMAPHORE_API_KEY,
        "number": phone_number,
        "message": message,
    }

    response = requests.post(url, data=data)

    return response.json()