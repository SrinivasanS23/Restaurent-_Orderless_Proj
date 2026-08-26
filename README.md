# EKNOW Restaurant — Modern Responsive Restaurant Ordering System

A fully functional, responsive restaurant ordering system supporting **Customer Check-In Sessions**, **Dual Checkout Flows (Pay at Desk vs Pay Online UPI)**, **Kitchen Display System with Web Audio 2-Beep Sound Alerts**, **Physical Payment Desk POS with Cash Change Calculator**, **Server-Side ReportLab PDF Receipts**, and **WhatsApp Receipt Delivery Architecture**.

---

## 🌟 Key Features

* **Table QR Identification & Customer Sessions**:
  * Scans table identifier (`/order/T01/` to `/order/T10/`).
  * Customer check-in captures and validates **Full Name** and normalized **Phone Number** (`+91XXXXXXXXXX`).
  * Customer phone is masked for privacy (`+91 ******1234`) across KDS and public views.
  * Supports multiple customer visits per table.
* **Dual Payment Flows**:
  * 🍽️ **Pay at Payment Desk (`PAY_AT_DESK`)**:
    * Order immediately dispatched to Kitchen Display.
    * Kitchen prepares and marks `SERVED`.
    * Customer eats and pays at the physical counter via **CASH**, **UPI**, or **CARD**.
    * Strict business rule: Payment is blocked at the desk before `SERVED`.
  * 📱 **Pay Online UPI (`ONLINE_UPI`)**:
    * Customer initiates instant UPI checkout.
    * Generates NPCI **UPI Intent Deep Link** (`upi://pay?...`) for mobile UPI apps (Google Pay, PhonePe, Paytm, BHIM) and dynamic **UPI QR Code** for desktop/tablet scanning.
    * Real payment verification architecture.
    * **Strict business rule**: Online orders are released to the kitchen **only after** successful payment confirmation.
* **Kitchen Display System (KDS)**:
  * 4-column live order board: `New Orders`, `Preparing`, `Ready`, `Served`.
  * Web Audio API multi-tone **2-beep notification** when new orders arrive.
  * Autoplay policy unlock banner (`[ 🔊 Enable Kitchen Alert Sound ]`), test tone, and persistent mute toggle.
  * Event de-duplication prevents duplicate audio triggers on reconnect.
  * Order cards show customer name, masked phone, and clear payment badges (`PAID (ONLINE UPI)` in green or `PAY AT DESK` in orange).
* **Payment Desk POS**:
  * Search bills by Order ID (`ORD-XXXX`).
  * Itemized breakdown with **GST Tax Calculation** (Subtotal, CGST 2.5%, SGST 2.5%, Grand Total).
  * Auto cash change calculator (`Cash Received` $\rightarrow$ `Change to Return`).
  * Duplicate payment prevention (HTTP 409 Conflict).
  * Split payment database architecture support.
* **Official PDF Receipts (ReportLab)**:
  * Authentic computer-generated PDF tax invoices stored securely in `media/receipts/`.
  * Secure download endpoint: `/api/orders/<order_number>/receipt/pdf/`.
* **WhatsApp Receipt Delivery**:
  * Configurable with environment variables (`WHATSAPP_PROVIDER`, `WHATSAPP_AUTH_TOKEN`, etc.).
  * Automatic delivery dispatch or clean fallback when credentials are not configured.

---

## 🛠️ Tech Stack

* **Backend**: Python 3.14, Django 5.1, Django REST Framework, Daphne (ASGI)
* **Real-time WebSockets**: Django Channels 4.3, Redis Channel Layer
* **Database**: MySQL 9.x (`orderless_db`)
* **PDF Generator**: ReportLab 5.0
* **Frontend**: Django Templates, HTML5, Modern CSS3 Custom Properties, Vanilla JavaScript, Bootstrap 5.3 & Bootstrap Icons
* **QR Codes**: `qrcode` + `Pillow`

---

## 🚀 Getting Started

### 1. Prerequisites

* Python 3.10+
* MySQL Server (`brew install mysql`)
* Redis Server (`brew install redis`)

### 2. Setup Environment & Install Dependencies

```bash
cd OrderLess-Project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Start Database & Redis Services

```bash
brew services start mysql
brew services start redis
```

Create MySQL database and grant privileges:
```sql
CREATE DATABASE IF NOT EXISTS orderless_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'orderless_user'@'localhost' IDENTIFIED BY 'OrderLess@2026';
GRANT ALL PRIVILEGES ON *.* TO 'orderless_user'@'localhost';
FLUSH PRIVILEGES;
```

### 4. Run Migrations & Seed Demo Data

```bash
python manage.py makemigrations tables menu orders payments
python manage.py migrate
python manage.py seed_data
```

### 5. Start Daphne ASGI Server

```bash
daphne -b 127.0.0.1 -p 8000 config.asgi:application
```

---

## 🌐 Application URLs & Credentials

| Interface | Live URL | Description / Access |
| :--- | :--- | :--- |
| **📱 Customer App (Table 05)** | [http://127.0.0.1:8000/order/T05/](http://127.0.0.1:8000/order/T05/) | Customer scan & order (Public) |
| **📱 Customer App (Table 01)** | [http://127.0.0.1:8000/order/T01/](http://127.0.0.1:8000/order/T01/) | Customer scan & order (Public) |
| **🍳 Kitchen Display (KDS)** | [http://127.0.0.1:8000/kitchen/](http://127.0.0.1:8000/kitchen/) | Login: `staff` / `staff123` |
| **💳 Payment Desk (POS)** | [http://127.0.0.1:8000/payment/](http://127.0.0.1:8000/payment/) | Login: `staff` / `staff123` |
| **🔐 Staff Login** | [http://127.0.0.1:8000/login/](http://127.0.0.1:8000/login/) | Login: `staff` / `staff123` |
| **⚙️ Django Admin** | [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/) | Login: `admin` / `admin123` |

---

## 🧪 Running Automated Tests

Run the full Django test suite:
```bash
python manage.py test tables menu orders payments --verbosity=2
```
