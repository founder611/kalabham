import os
import json
import random
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import requests
import razorpay
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from supabase import create_client

from myapp.delhivery_config import DelhiveryAPI

from django.conf import settings

# ==========================================
# CONFIGURATION
# ==========================================
PRICING_TIERS = {
    "115g": {1: 549, 2: 999, 4: 1899},
}

FREE_SHIPPING_THRESHOLD = 999
SHIPPING_CHARGE = 49

RAZORPAY_API_KEY = "rzp_live_Su35EVyNYFeKCF"
RAZORPAY_SECRET_KEY = "NQE3JfS6rdlmp8YtHrxF120H"

SUPABASE_URL = "https://fgikrpxjaskyduewekiu.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZnaWtycHhqYXNreWR1ZXdla2l1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODAzNTg3MDUsImV4cCI6MjA5NTkzNDcwNX0.kyIphJzU-gNIEvA2rXAWAKy6lC4Vur362U2lFWm6BtI"



WHATSAPP_API_KEY = "39832662461ae94fa94b03487c7866f3"
WHATSAPP_BASE_URL = "https://chatbot.digitalmbg.com/v1"


# ==========================================
# PAGE VIEWS
# ==========================================
def homepage(request):
    return render(request, 'updatehome.html')


def blog_page(request):
    return render(request, 'blog.html')


# ==========================================
# PRICING & SHIPPING HELPERS
# ==========================================
def calculate_price(quantity, pack_count):
    tiers = PRICING_TIERS.get(quantity)
    if not tiers:
        return 0

    if pack_count in tiers:
        return tiers[pack_count]

    tier_qtys = sorted(tiers.keys())
    highest = tier_qtys[-1]

    if pack_count > highest:
        per_unit = tiers[highest] / highest
        return round(per_unit * pack_count)

    lower_qty = tier_qtys[0]
    for tq in tier_qtys:
        if tq <= pack_count:
            lower_qty = tq
    per_unit = tiers[lower_qty] / lower_qty
    return round(per_unit * pack_count)


def calculate_shipping(subtotal):
    return 0 if subtotal >= FREE_SHIPPING_THRESHOLD else SHIPPING_CHARGE


def get_weight(quantity, pack_count):
    if quantity == "50g":
        return round(0.05 * pack_count, 3)
    if quantity == "115g":
        return round(0.115 * pack_count, 3)
    return 0.5


# ==========================================
# ORDER PROCESSING VIEWS
# ==========================================
def order_post(request):
    name = request.POST['name']
    email = request.POST['email']
    phone = request.POST['phone']
    address = request.POST['address']
    quantity = request.POST['quantity']
    city = request.POST.get('city', '')
    district = request.POST.get('district', '')
    state = request.POST.get('state', '')
    pincode = request.POST.get('pincode', '')

    try:
        pack_count = int(request.POST.get('pack_count', 1))
    except (TypeError, ValueError):
        pack_count = 1
    if pack_count < 1:
        pack_count = 1

    subtotal_rupees = calculate_price(quantity, pack_count)
    shipping_rupees = calculate_shipping(subtotal_rupees)
    total_rupees = subtotal_rupees + shipping_rupees
    amount = int(round(total_rupees * 100))  # paise for Razorpay

    return render(request, 'pp.html', {
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'quantity': quantity,
        'city': city,
        'district': district,
        'state': state,
        'pincode': pincode,
        'pack_count': pack_count,
        'subtotal_rupees': subtotal_rupees,
        'shipping_rupees': shipping_rupees,
        'price_rupees': total_rupees,
        'amount': amount,
        'razorpay_api_key': RAZORPAY_API_KEY,
        'currency': 'INR'
    })


def raz_pay(request, amount):
    razorpay_client = razorpay.Client(
        auth=(RAZORPAY_API_KEY, RAZORPAY_SECRET_KEY)
    )
    amount = float(amount)

    order_data = {
        'amount': amount,
        'currency': 'INR',
        'receipt': 'order_rcptid_11',
        'payment_capture': '1',
    }

    order = razorpay_client.order.create(data=order_data)

    return render(request, 'pp.html', {
        'razorpay_api_key': RAZORPAY_API_KEY,
        'amount': order_data['amount'],
        'currency': order_data['currency'],
        'order_id': order['id']
    })


# ==========================================
# PAYMENT CONFIRMATION VIEW
# ==========================================
def userpayment_post(request):
    if request.method != "POST":
        return HttpResponse("Invalid Request")

    # Extract form data
    name = request.POST.get('name')
    email = request.POST.get('email')
    phone = request.POST.get('phone')
    address = request.POST.get("address")
    city = request.POST.get("city")
    district = request.POST.get("district")
    state = request.POST.get("state")
    pincode = request.POST.get("pincode")
    quantity = request.POST.get('quantity')
    payment_id = request.POST.get('payment_id')
    amount = request.POST.get('amount')

    full_address = f"{address}, {district}, {city}, {state} - {pincode}"

    # Log received data
    print("Received payment POST:", {
        'name': name,
        'email': email,
        'phone': phone,
        'address': address,
        'quantity': quantity,
        'payment_id': payment_id,
        'amount': amount
    })

    # Parse pack count
    try:
        pack_count = int(request.POST.get('pack_count', 1))
    except (TypeError, ValueError):
        pack_count = 1
    if pack_count < 1:
        pack_count = 1

    # Parse amount
    try:
        amount = float(amount) / 100  # Paisa → Rupees
    except:
        amount = 0

    if not email:
        return HttpResponse("Email not found")

    # Success HTML response
    success_html = """
    <script>
    alert('Payment Successful!');
    window.location='/';
    </script>
    """

    # Process all post-payment actions
    try:
        # 1. Send emails
        _send_order_emails(name, email, phone, full_address, quantity, 
                          pack_count, amount, payment_id)

        # 2. Save to Supabase
        _save_order_to_supabase(name, email, phone, full_address, quantity, 
                               payment_id, amount, pack_count)

        # 3. Send WhatsApp notification
        _send_whatsapp_notification(name, phone, quantity, payment_id, amount)

        # 4. Create Delhivery shipment
        _create_delhivery_shipment(name, phone, address, district, city, state, 
                                  pincode, payment_id, amount, quantity, pack_count)

    except Exception as e:
        print(f"Post-payment processing error: {str(e)}")

    return HttpResponse(success_html)


# ==========================================
# POST-PAYMENT PROCESSING FUNCTIONS
# ==========================================
def _send_order_emails(name, email, phone, full_address, quantity, 
                       pack_count, amount, payment_id):
    """Send order confirmation emails to customer and admin"""
    try:
        # Customer HTML Email
        customer_html = f"""
        <html>
        <body style="font-family: Arial; background:#f4f4f4; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:15px; padding:30px;">
        <h1 style="color:#0b7d45; text-align:center;">🌿 ECOMONKS</h1>
        <h2>Thank You For Your Order</h2>
        <p>Dear <b>{name}</b>,</p>
        <p>Your payment has been received successfully and your order is confirmed.</p>
        <div style="background:#f7fff9; border:1px solid #d4f5dd; padding:20px; border-radius:10px;">
        <h3>🧾 Order Details</h3>
        <p><b>👤 Name:</b> {name}</p>
        <p><b>📧 Email:</b> {email}</p>
        <p><b>📞 Phone:</b> {phone}</p>
        <p><b>📍 Address:</b> {full_address}</p>
        <p><b>💰 Amount:</b> ₹{amount}</p>
        <p><b>📦 Quantity:</b> {quantity} × {pack_count} pack(s)</p>
        <p><b>💳 Payment ID:</b> {payment_id}</p>
        </div>
        </div>
        </body>
        </html>
        """

        # Admin HTML Email
        admin_html = f"""
        <html>
        <body>
        <h2>🚨 NEW ORDER RECEIVED</h2>
        <p><b>Customer:</b> {name}</p>
        <p><b>Email:</b> {email}</p>
        <p><b>Phone:</b> {phone}</p>
        <p><b>Address:</b> {full_address}</p>
        <p><b>Quantity:</b> {quantity} × {pack_count} pack(s)</p>
        <p><b>Amount:</b> ₹{amount}</p>
        <p><b>Payment ID:</b> {payment_id}</p>
        </body>
        </html>
        """

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)

        # Send customer email
        customer_msg = MIMEMultipart()
        customer_msg['From'] = settings.EMAIL_HOST_USER
        customer_msg['To'] = email
        customer_msg['Subject'] = "ECOMONKS Order Confirmation"
        customer_msg.attach(MIMEText(customer_html, 'html', 'utf-8'))
        server.sendmail(settings.EMAIL_HOST_USER, email, customer_msg.as_string())

        # Send admin email
        admin_msg = MIMEMultipart()
        admin_msg['From'] = settings.EMAIL_HOST_USER
        admin_msg['To'] = settings.EMAIL_HOST_USER
        admin_msg['Subject'] = "New ECOMONKS Order Received"
        admin_msg.attach(MIMEText(admin_html, 'html', 'utf-8'))
        server.sendmail(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_USER, admin_msg.as_string())

        server.quit()
        print("✅ Emails sent successfully")

    except Exception as e:
        print(f"❌ Email error: {str(e)}")


def _save_order_to_supabase(name, email, phone, address, quantity, 
                            payment_id, amount, pack_count=1):
    """Save order to Supabase database"""
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

        # Get next order number
        try:
            response = supabase.table('orders').select('id', count='exact').execute()
            order_no = response.count + 1 if response.count else 1
        except Exception as e:
            print(f"Could not get count: {e}")
            order_no = 1

        # Insert order
        order_data = {
            "order_no": order_no,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "customer_name": name,
            "email": email,
            "phone": phone,
            "address": address,
            "quantity": quantity,
            "pack_count": pack_count,
            "amount": amount,
            "payment_id": payment_id,
            "payment_status": "paid"
        }

        supabase.table('orders').insert(order_data).execute()
        print(f"✅ Order #{order_no} saved to Supabase")

    except Exception as e:
        print(f"❌ Supabase error: {str(e)}")


def _send_whatsapp_notification(name, phone, quantity, payment_id, amount):
    """Send WhatsApp notification using template"""
    try:
        print("========== MBG WHATSAPP TEMPLATE ==========")

        phone = str(phone).replace(" ", "").replace("+", "").strip()
        if not phone.startswith("91"):
            phone = "91" + phone

        payload = {
            "templateName": "karpooram_orderconfirmation",
            "senderId": phone,
            "chatId": "1402050",
            "variables": {
                "header": [],
                "body": [
                    str(name),
                    str(quantity),
                    str(amount),
                    str(payment_id),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ]
            }
        }

        response = requests.post(
            f"{WHATSAPP_BASE_URL}/whatsapp/send_templet",
            headers={
                "Content-Type": "application/json",
                "x-api-key": WHATSAPP_API_KEY
            },
            json=payload,
            timeout=30
        )

        print("Status:", response.status_code)
        print("Response:", response.text)

    except Exception as e:
        print(f"❌ WhatsApp error: {str(e)}")


def _create_delhivery_shipment(name, phone, address, district, city, state, 
                               pincode, payment_id, amount, quantity, pack_count):
    """Create Delhivery shipment for the order"""
    try:
        print("=" * 70)
        print("DELIVERY ADDRESS")
        print("Address :", address)
        print("District:", district)
        print("City    :", city)
        print("State   :", state)
        print("Pincode :", pincode)
        print("=" * 70)

        delhivery = DelhiveryAPI()
        waybill = delhivery.generate_waybill()
        print(f"Generated waybill: {waybill}")

        order_data = {
            "customer_name": name,
            "phone": phone,
            "address": address,
            "district": district,
            "city": city,
            "state": state,
            "pincode": pincode,
            "order_id": payment_id,
            "amount": amount,
            "quantity": quantity,
            "waybill": waybill,
            "weight": get_weight(quantity, pack_count)
        }

        shipment_response = delhivery.create_shipment(order_data)

        if shipment_response:
            print(f"✅ Shipment created: {shipment_response}")
        else:
            print("❌ Shipment creation failed")

    except Exception as e:
        print(f"❌ Delhivery API error: {str(e)}")


# ==========================================
# EMAIL SUBSCRIPTION
# ==========================================
def emailenquiry(request):
    """Handle email subscription"""
    if request.method != "POST":
        return HttpResponse("Invalid Request")

    email = request.POST.get('email')

    try:
        subscription_html = f"""
        <html>
        <body style="font-family: Arial; background:#f4f4f4; padding:30px;">
        <div style="max-width:600px; margin:auto; background:white; border-radius:15px; padding:30px;">
        <h1 style="color:#0b7d45; text-align:center;">🌿 Welcome to ECOMONKS</h1>
        <p>Thank you for subscribing to ECOMONKS.</p>
        <p>We are excited to have you as part of our growing family ❤️</p>
        </div>
        </body>
        </html>
        """

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)

        subscriber_msg = MIMEMultipart()
        subscriber_msg['From'] = settings.EMAIL_HOST_USER
        subscriber_msg['To'] = email
        subscriber_msg['Subject'] = "ECOMONKS Subscription"
        subscriber_msg.attach(MIMEText(subscription_html, 'html', 'utf-8'))
        server.sendmail(settings.EMAIL_HOST_USER, email, subscriber_msg.as_string())

        server.quit()

        return HttpResponse("""
        <script>
        alert('Subscribed Successfully');
        window.location='/';
        </script>
        """)

    except Exception as e:
        return HttpResponse(f"ERROR: {str(e)}")


# ==========================================
# OTP VERIFICATION (Email-based)
# ==========================================
def generate_otp():
    """Generate a 6-digit OTP"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])


def _send_email_otp(email, otp):
    """Send OTP via email"""
    try:
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background:#f4f4f4; padding:30px;">
            <div style="max-width:450px; margin:auto; background:white; border-radius:12px; padding:30px; text-align:center;">
                <h1 style="color:#0b7d45; margin-bottom:8px;">🌿 ECOMONKS</h1>
                <h2 style="color:#333; font-weight:300;">Your Verification Code</h2>
                <div style="background:#f7fff9; padding:20px; border-radius:10px; margin:20px 0;">
                    <div style="font-size:2.2rem; font-weight:700; letter-spacing:8px; color:#0b7d45; font-family:monospace;">
                        {otp}
                    </div>
                </div>
                <p style="color:#666; font-size:0.9rem;">
                    Enter this code to verify your email and complete your order.<br>
                    This code expires in 5 minutes.
                </p>
                <hr style="border:none; border-top:1px solid #eee; margin:20px 0;">
                <p style="color:#999; font-size:0.75rem;">
                    If you didn't request this, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart()
        msg['From'] = settings.EMAIL_HOST_USER
        msg['To'] = email
        msg['Subject'] = "🔐 ECOMONKS - Email Verification Code"
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
        server.sendmail(settings.EMAIL_HOST_USER, email, msg.as_string())
        server.quit()

        return True
    except Exception as e:
        print(f"Email OTP error: {e}")
        return False


@csrf_exempt
def send_otp(request):
    """Send OTP to user's email"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=405)

    try:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

        email = data.get('email', '').strip()

        if not email:
            return JsonResponse({'status': 'error', 'message': 'Email required'}, status=400)

        otp = generate_otp()
        cache_key = f"otp_{email}"
        cache.set(cache_key, otp, timeout=300)

        if _send_email_otp(email, otp):
            return JsonResponse({'status': 'success', 'message': 'OTP sent to email'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Failed to send email'}, status=500)

    except Exception as e:
        print(f"Send OTP error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def verify_otp(request):
    """Verify the OTP submitted by user"""
    if request.method != 'POST':
        return JsonResponse({'verified': False, 'message': 'Invalid method'}, status=405)

    try:
        try:
            data = json.loads(request.body.decode('utf-8'))
        except:
            return JsonResponse({'verified': False, 'message': 'Invalid JSON'}, status=400)

        otp_input = data.get('otp', '').strip()
        email = data.get('email', '').strip()

        if not email or not otp_input:
            return JsonResponse({'verified': False, 'message': 'Missing data'}, status=400)

        cache_key = f"otp_{email}"
        stored_otp = cache.get(cache_key)

        if not stored_otp:
            return JsonResponse({'verified': False, 'message': 'OTP expired or not found'}, status=400)

        if str(stored_otp) == str(otp_input):
            cache.delete(cache_key)
            return JsonResponse({'verified': True, 'message': 'OTP verified successfully'})
        else:
            return JsonResponse({'verified': False, 'message': 'Invalid OTP'}, status=400)

    except Exception as e:
        print(f"Verify OTP error: {e}")
        return JsonResponse({'verified': False, 'message': str(e)}, status=500)