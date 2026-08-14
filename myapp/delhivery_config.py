import requests
import json
from datetime import datetime


class DelhiveryAPI:

    def __init__(self):

        print("=" * 80)
        print("Initializing Delhivery API")

        # Change to staging if testing
        # self.base_url = "https://staging-express.delhivery.com"

        # Production
        self.base_url = "https://track.delhivery.com"

        self.api_key = "f04f6bba55ca9b7346a7959b01da41182c786083"

        self.pickup_address = {
            "name": "yathisha",
            "address": "Global Avenue Opp SIB Aranattukara Branch Thoppinmoola Poothole",
            "city": "Thrissur",
            "state": "Kerala",
            "pincode": "680004",
            "phone": "7204610007"
        }

        print("Base URL :", self.base_url)
        print("Token    :", self.api_key[:8] + "********")
        print("=" * 80)

    # -------------------------------------------------------
    # COMMON HEADERS
    # -------------------------------------------------------

    def headers(self):

        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

    # -------------------------------------------------------
    # WAYBILL
    # -------------------------------------------------------

    def generate_waybill(self):

        url = f"{self.base_url}/waybill/api/fetch/json/"

        response = requests.get(
            url,
            params={"count": 1},
            headers=self.headers()
        )

        print(response.status_code)
        print(response.text)

        if response.status_code == 200:

            waybill = response.json()

            print("Waybill:", waybill)

            return waybill

        return None

    # -------------------------------------------------------
    # CREATE SHIPMENT
    # -------------------------------------------------------

    def create_shipment(self, order_data):

        url = f"{self.base_url}/api/cmu/create.json"

        shipment = {
            "name": order_data["customer_name"],
            "add": order_data["address"],

            "pin": order_data["pincode"],
            "city": order_data["city"],
            "state": order_data["state"],
            "country": "India",

            "phone": order_data["phone"],

            "order": order_data["order_id"],

            "payment_mode": "Prepaid",

            "return_pin": self.pickup_address["pincode"],
            "return_city": self.pickup_address["city"],
            "return_phone": self.pickup_address["phone"],
            "return_add": self.pickup_address["address"],
            "return_state": self.pickup_address["state"],
            "return_country": "India",

            "products_desc": f"Divya Kalabham ({order_data['pack_count']} Packs of {order_data['weight']}g)",
            "hsn_code": "",

            "cod_amount": "0",

            "order_date": datetime.now().strftime("%Y-%m-%d"),

            "total_amount": str(order_data["amount"]),

            "seller_add": self.pickup_address["address"],
            "seller_name": self.pickup_address["name"],
            "seller_inv": "",

            "quantity": "1",

            "waybill": order_data["waybill"],

            "shipment_width": "10",
            "shipment_height": "10",
            "shipment_length": "10",

            "weight": str(order_data["weight"]),

            "shipping_mode": "Surface",

            "address_type": "home"
        }

        payload = {
            "format": "json",
            "data": json.dumps({
                "shipments": [shipment],
                "pickup_location": {
                    "name": self.pickup_address["name"]
                }
            })
        }

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Accept": "application/json"
        }

        response = requests.post(
            url,
            data=payload,
            headers=headers,
            timeout=60
        )

        print(response.status_code)
        print(response.text)

        return response.json()

    # -------------------------------------------------------
    # PINCODE CHECK
    # -------------------------------------------------------

    def check_pincode(self, pincode):

        print("\nChecking Pincode")

        url = f"{self.base_url}/c/api/pin-codes/json/"

        params = {
            "filter_codes": pincode
        }

        print(url)

        try:

            response = requests.get(
                url,
                params=params,
                headers=self.headers(),
                timeout=30
            )

            print(response.status_code)
            print(response.text)

            return response.json()

        except Exception as e:

            print(e)

            return None

    # -------------------------------------------------------
    # SHIPPING CHARGES
    # -------------------------------------------------------

    def get_shipping_rates(self, pincode, weight=0.5):

        url = f"{self.base_url}/api/packing/charges"

        params = {
            "pickup_pincode": self.pickup_address["pincode"],
            "delivery_pincode": pincode,
            "weight": weight,
            "cod": 0
        }

        print("\nShipping Charges")

        print(url)

        try:

            response = requests.get(
                url,
                params=params,
                headers=self.headers(),
                timeout=30
            )

            print(response.status_code)
            print(response.text)

            return response.json()

        except Exception as e:

            print(e)

            return None

    # -------------------------------------------------------
    # LABEL
    # -------------------------------------------------------

    def print_label(self, waybill):

        url = f"{self.base_url}/api/p/packing/slip"

        params = {
            "wbns": waybill
        }

        print("\nGenerating Label")

        print(url)

        try:

            response = requests.get(
                url,
                params=params,
                headers=self.headers(),
                timeout=30
            )

            print(response.status_code)

            if response.status_code == 200:

                return response.content

            print(response.text)

            return None

        except Exception as e:

            print(e)

            return None