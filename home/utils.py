import os
import requests


def format_ph_mobile(phone):
    phone = phone.strip()
    phone = phone.replace(" ", "")
    phone = phone.replace("-", "")

    if phone.startswith("+63"):
        phone = phone[1:]

    elif phone.startswith("09"):
        phone = "63" + phone[1:]

    return phone


def send_iprog_sms(phone_number, message):

    api_token = os.getenv(
        "IPROG_SMS_API_TOKEN"
    )

    url = "https://www.iprogsms.com/api/v1/sms_messages"

    data = {
        "api_token": api_token,
        "phone_number": phone_number,
        "message": message,
    }

    response = requests.post(
        url,
        json=data,
        timeout=15
    )

    return response