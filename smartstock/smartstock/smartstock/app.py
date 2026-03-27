from flask import Flask, request, jsonify, render_template, redirect, url_for, session, flash,  send_file
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
import jwt
import datetime
from functools import wraps
import smtplib
from email.mime.text import MIMEText
import random
import json
from bson import ObjectId
import os
import secrets
import time
import threading
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure

app = Flask(__name__, template_folder='templates')
CORS(app)

app.config["SECRET_KEY"] = "smartstock_secret_key"

# Global connection state
connection_state = {
    'client': None,
    'db': None,
    'is_connected': False,
    'last_check': None,
    'retry_count': 0,
    'max_retries': 5,
    'lock': threading.Lock()
}

def get_connection_string():
    """Get MongoDB connection string with fallback options"""
    return "mongodb://localhost:27017/"

def create_mongo_client():
    """Create MongoDB client with enhanced connection settings"""
    return MongoClient(
        get_connection_string(),
        maxPoolSize=100,  # Increased pool size
        minPoolSize=10,   # Minimum pool size
        maxIdleTimeMS=30000,  # Close idle connections after 30s
        serverSelectionTimeoutMS=10000,  # Increased timeout
        socketTimeoutMS=45000,  # Increased socket timeout
        connectTimeoutMS=10000,  # Increased connect timeout
        retryWrites=True,
        retryReads=True,
        w="majority",
        readPreference="secondaryPreferred",
        heartbeatFrequencyMS=10000,  # Check connection health every 10s
        appName="smartstock_inventory"  # Application identification
    )

def test_connection(mongo_client):
    """Test MongoDB connection with comprehensive checks"""
    try:
        # Basic ping test
        mongo_client.admin.command('ping')
        
        # Test database access
        mongo_client['smartstock'].list_collection_names()
        
        # Test write operation
        test_collection = mongo_client['smartstock']['connection_test']
        test_collection.insert_one({'test': True, 'timestamp': datetime.datetime.now()})
        test_collection.delete_many({'test': True})
        
        return True, "Connection successful"
    except ConnectionFailure as e:
        return False, f"Connection failed: {str(e)}"
    except ServerSelectionTimeoutError as e:
        return False, f"Server selection timeout: {str(e)}"
    except OperationFailure as e:
        return False, f"Operation failed: {str(e)}"
    except Exception as e:
        return False, f"Unknown error: {str(e)}"

def ensure_mongodb_running():
    """Ensure MongoDB is running before attempting connection"""
    try:
        # Check if MongoDB is accessible
        test_client = MongoClient(get_connection_string(), serverSelectionTimeoutMS=3000)
        test_client.admin.command('ping')
        test_client.close()
        return True
    except:
        print("🚀 MongoDB not running, attempting to start...")
        try:
            import subprocess
            import os
            
            # Create data directory
            data_path = "C:\\data\\db"
            if not os.path.exists(data_path):
                os.makedirs(data_path, exist_ok=True)
            
            # Start MongoDB in background
            subprocess.Popen([
                "mongod", 
                "--dbpath", data_path,
                "--logpath", os.path.join(data_path, "mongod.log")
            ], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)
            
            # Wait for startup
            time.sleep(5)
            
            # Test connection again
            test_client = MongoClient(get_connection_string(), serverSelectionTimeoutMS=5000)
            test_client.admin.command('ping')
            test_client.close()
            print("✅ MongoDB started successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to start MongoDB: {str(e)}")
            return False

def establish_connection():
    """Establish MongoDB connection with enhanced retry mechanism and auto-start"""
    with connection_state['lock']:
        if connection_state['is_connected'] and connection_state['client'] is not None:
            return connection_state['client'], connection_state['db']
        
        print("🔄 Establishing MongoDB connection...")
        
        # Ensure MongoDB is running first
        if not ensure_mongodb_running():
            print("❌ Cannot establish connection - MongoDB unavailable")
            return None, None
        
        for attempt in range(connection_state['max_retries']):
            try:
                client = create_mongo_client()
                is_connected, message = test_connection(client)
                
                if is_connected:
                    db = client["smartstock"]
                    
                    # Update connection state
                    connection_state['client'] = client
                    connection_state['db'] = db
                    connection_state['is_connected'] = True
                    connection_state['last_check'] = datetime.datetime.now()
                    connection_state['retry_count'] = 0
                    
                    print("✅ MongoDB connected successfully with strong protection")
                    return client, db
                else:
                    print(f"❌ Connection attempt {attempt + 1} failed: {message}")
                    
            except Exception as e:
                print(f"❌ Connection attempt {attempt + 1} error: {str(e)}")
            
            if attempt < connection_state['max_retries'] - 1:
                wait_time = min((2 ** attempt) + 1, 10)  # Cap wait time at 10s
                print(f"⏳ Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
        
        # All retries failed
        connection_state['retry_count'] = connection_state['max_retries']
        connection_state['is_connected'] = False
        print("❌ All connection attempts failed")
        return None, None

def get_robust_db():
    """Get database connection with automatic reconnection"""
    with connection_state['lock']:
        # Check if connection is still valid
        if (connection_state['is_connected'] and 
            connection_state['client'] is not None and
            connection_state['last_check'] and
            (datetime.datetime.now() - connection_state['last_check']).seconds < 30):
            
            try:
                # Quick connection test
                connection_state['client'].admin.command('ping')
                connection_state['last_check'] = datetime.datetime.now()
                return connection_state['db']
            except:
                print("⚠️ Connection lost, attempting reconnection...")
                connection_state['is_connected'] = False
        
        # Establish new connection if needed
        if not connection_state['is_connected']:
            client, db = establish_connection()
            return db
        
        return connection_state['db']

def check_robust_connection():
    """Check connection status with detailed information"""
    with connection_state['lock']:
        if connection_state['client'] is None:
            return False, "No client available"
        
        try:
            # Comprehensive connection test
            connection_state['client'].admin.command('ping')
            
            # Test database operations
            db = connection_state['db']
            if db is not None:
                db.list_collection_names()
            
            connection_state['last_check'] = datetime.datetime.now()
            return True, "Connection healthy"
        except Exception as e:
            connection_state['is_connected'] = False
            return False, f"Connection error: {str(e)}"

def close_connection():
    """Safely close MongoDB connection"""
    with connection_state['lock']:
        if connection_state['client'] is not None:
            try:
                connection_state['client'].close()
                print("✅ MongoDB connection closed safely")
            except Exception as e:
                print(f"⚠️ Error closing connection: {str(e)}")
            finally:
                connection_state['client'] = None
                connection_state['db'] = None
                connection_state['is_connected'] = False

# Initialize connection on startup with verification
print("🚀 SmartStock Application Starting...")
print("🔍 Verifying MongoDB connection before startup...")

# Multiple connection attempts with increasing timeouts
max_startup_attempts = 3
for attempt in range(max_startup_attempts):
    print(f"📡 Startup connection attempt {attempt + 1}/{max_startup_attempts}")
    
    client, db = establish_connection()
    if client is not None and db is not None:
        print("✅ MongoDB connection verified successfully!")
        break
    else:
        if attempt < max_startup_attempts - 1:
            print(f"⏳ Waiting 5 seconds before retry...")
            time.sleep(5)
        else:
            print("⚠️ Warning: Could not establish MongoDB connection after multiple attempts")
            print("🔄 Application will continue, but database features may be limited")

print("🎯 SmartStock initialization complete!")

# COLLECTIONS WITH ROBUST CONNECTION HANDLING
def get_collection(collection_name):
    """Get collection with automatic reconnection"""
    db = get_robust_db()
    if db is not None:
        return db[collection_name]
    return None

# Main collections
collection = get_collection("users")
users_collection = collection
products_collection = get_collection("products")
inventory_collection = get_collection("inventory")
sales_collection = get_collection("sales")
employee_sales_collection = get_collection("employee_sales")
alerts_collection = get_collection("alerts")
stock_updates_collection = get_collection("stock_updates")
reports_collection = get_collection("reports")
transactions_collection = get_collection("transactions")

# TEMP OTP STORAGE (NO DATABASE)
otp_storage = {}

# EMAIL CONFIG
EMAIL_ADDRESS = "smartstockinventory13@gmail.com"
EMAIL_PASSWORD = "mqba dccc kkls xnbs"

@app.route("/health")
def health_check():
    """Enhanced health check endpoint with detailed status"""
    try:
        is_connected, message = check_robust_connection()
        
        # Get connection statistics
        with connection_state['lock']:
            retry_count = connection_state['retry_count']
            last_check = connection_state['last_check']
            
        # Check database operations
        db_status = "operational"
        try:
            if products_collection is not None:
                products_collection.count_documents({})
        except:
            db_status = "limited"
        
        return jsonify({
            "status": "healthy" if is_connected else "unhealthy",
            "database": {
                "connected": is_connected,
                "status": db_status,
                "message": message,
                "last_check": last_check.isoformat() if last_check else None,
                "retry_count": retry_count
            },
            "collections": {
                "users": collection is not None,
                "products": products_collection is not None,
                "inventory": inventory_collection is not None,
                "sales": sales_collection is not None,
                "alerts": alerts_collection is not None,
                "reports": reports_collection is not None,
                "transactions": transactions_collection is not None
            },
            "timestamp": datetime.datetime.now().isoformat(),
            "uptime": "active" if is_connected else "disconnected"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Health check failed: {str(e)}",
            "timestamp": datetime.datetime.now().isoformat()
        }), 500

@app.route("/")
def home():
    try:
        return render_template("intro.html")
    except Exception as e:
        return f"Error loading intro.html: {str(e)}<br>Template folder: {app.template_folder}<br>Working dir: {os.getcwd()}"

@app.route("/test")
def test():
    return "Flask app is working! Current time: " + str(datetime.datetime.now())

@app.route("/intro")
def intro():
    return render_template("intro.html")

@app.route("/debug")
def debug():
    return jsonify({
        "status": "working",
        "templates": os.listdir("templates"),
        "intro_exists": os.path.exists("templates/intro.html")
    })

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register-page")
def register_page():
    return render_template("register.html")

@app.route("/reset-password-page")
def reset_password_page():
    token = request.args.get("token")
    return render_template("reset_password.html", token=token)

@app.route("/welcome")
def welcome():
    print(f"🔍 Welcome route accessed - Session data: {dict(session)}")
    
    # Check if user is logged in via session first
    if 'user_email' in session:
        print(f"✅ Found session data for: {session.get('user_email')}")
        return render_template("welcome.html")
    
    # Check for token in URL parameters (from login redirect)
    token = request.args.get('token')
    if not token:
        # Check for token in Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
    
    if token:
        try:
            print("🔍 Validating token...")
            data = jwt.decode(
                token,
                app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )
            print(f"✅ Token valid for user: {data.get('email')}")
            
            # Set session from token for future requests
            session['user_email'] = data.get('email', '')
            session['username'] = data.get('username', '')
            session['user_id'] = data.get('username', '')
            session.permanent = True
            
            print(f"✅ Session set for: {session.get('user_email')}")
            return render_template("welcome.html")
            
        except Exception as e:
            print(f"❌ Token validation failed: {e}")
    
    print("❌ No valid authentication found, redirecting to login")
    return redirect(url_for('login_page'))


# ---------------- TOKEN DECORATOR ----------------

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None

        if "Authorization" in request.headers:
            token = request.headers["Authorization"].split(" ")[1]

        if not token:
            return jsonify({"message": "Token missing"}), 401

        try:
            data = jwt.decode(
                token,
                app.config["SECRET_KEY"],
                algorithms=["HS256"]
            )
            current_user = data
        except:
            return jsonify({"message": "Token invalid"}), 401

        return f(current_user, *args, **kwargs)

    return decorated


# ---------------- ADDITIONAL PAGE ROUTES ----------------

@app.route("/admin")
def admin_page():
    return render_template("admin.html")

@app.route("/user")
def user_page():
    return render_template("dashboard.html")

# DATABASE HELPER FUNCTION
def get_db():
    """Get database connection with error handling (legacy support)"""
    db = get_robust_db()
    if db is None:
        raise Exception("Database not connected")
    return db

# Connection monitoring decorator
def with_db_check(f):
    """Decorator to ensure database connection before API calls"""
    def wrapper(*args, **kwargs):
        try:
            # Ensure we have a valid connection
            db = get_robust_db()
            if db is None:
                return jsonify({
                    "error": "Database connection failed",
                    "message": "Unable to connect to database"
                }), 503
            
            return f(*args, **kwargs)
        except Exception as e:
            print(f"❌ Database operation failed: {str(e)}")
            return jsonify({
                "error": "Database operation failed",
                "message": str(e)
            }), 500
    return wrapper

# Enhanced collection operations with error handling
def safe_collection_operation(collection_name, operation):
    """Safely perform collection operation with error handling"""
    try:
        collection = get_collection(collection_name)
        if collection is None:
            raise Exception(f"Collection {collection_name} not available")
        return operation(collection)
    except Exception as e:
        print(f"❌ Collection operation failed: {str(e)}")
        raise e

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@app.route("/employee-dashboard")
def employee_dashboard():
    return render_template("employee/employee_dashboard.html")

@app.route("/employee/products-view")
def employee_products_view():
    return render_template("employee/products_view.html")

@app.route("/employee/stock-update")
def employee_stock_update():
    return render_template("employee/stock_update.html")

@app.route("/employee/sales-entry")
def employee_sales_entry():
    return render_template("employee/sales_entry.html")

@app.route("/employee/alerts-view")
def employee_alerts_view():
    return render_template("employee/alerts_view.html")

@app.route("/employee/smart-assistant")
def employee_smart_assistant():
    return render_template("employee/smart_assistant.html")

@app.route("/employee/transaction-history")
def employee_transaction_history():
    return render_template("employee/transaction_history.html")

@app.route("/employee-profile")
def employee_profile():
    return render_template("employee/employee_profile.html")

@app.route("/products")
def products():
    return render_template("products.html")

@app.route("/inventory")
def inventory():
    return render_template("inventory.html")

@app.route("/sales")
def sales():
    return render_template("sales.html")

@app.route("/alerts")
def alerts():
    return render_template("alerts.html")

@app.route("/reports")
def reports():
    return render_template("reports.html")

@app.route("/transaction-history")
def transaction_history():
    return render_template("transaction_history.html")

@app.route("/smart-assistant")
def smart_assistant():
    return render_template("smart_assistant.html")

@app.route("/user-management")
def user_management():
    return render_template("user_management.html")

@app.route("/profile")
def profile():
    try:
        # Get current user from session or use default user
        # In a real app, this would get the logged-in user's ID from session
        # For now, we'll get the first user from database as an example
        user = collection.find_one()
        
        if not user:
            # Fallback to default user if no users in database
            user = {
                "username": "Admin User",
                "role": "Administrator", 
                "email": "admin@smartstock.com",
                "contactNumber": "+91-9876543210",
                "shopAddress": "123 Main Street, Shop No. 45",
                "city": "Hyderabad",
                "state": "Telangana",
                "pincode": "500001",
                "gstin": "Not provided",
                "lastLogin": "Never"
            }
        else:
            # Format real user data
            last_login = user.get("lastLogin", {})
            if last_login:
                last_login_str = last_login.get("timestamp", "Unknown").strftime("%Y-%m-%d %H:%M:%S") if hasattr(last_login.get("timestamp"), "strftime") else str(last_login.get("timestamp", "Unknown"))
            else:
                last_login_str = "Never"
                
            user_data = {
                "username": user.get("username", "Unknown User"),
                "role": user.get("role", "User"),
                "email": user.get("email", "No email"),
                "contactNumber": user.get("contactNumber", "Not provided"),
                "shopAddress": user.get("shopAddress", "Not provided"),
                "city": user.get("city", "Not provided"),
                "state": user.get("state", "Not provided"),
                "pincode": user.get("pincode", "Not provided"),
                "gstin": user.get("gstin", "Not provided"),
                "lastLogin": last_login_str,
                "loginCount": len(user.get("loginHistory", []))
            }
            user = user_data
            
        return render_template("profile.html", user=user)
    except Exception as e:
        # Fallback in case of database error
        user = {
            "username": "Admin User",
            "role": "Administrator",
            "email": "admin@smartstock.com", 
            "contactNumber": "+91-9876543210",
            "shopAddress": "123 Main Street, Shop No. 45",
            "city": "Hyderabad",
            "state": "Telangana",
            "pincode": "500001",
            "gstin": "Not provided",
            "lastLogin": "Never",
            "loginCount": 0
        }
        return render_template("profile.html", user=user)

@app.route("/settings")
def settings():
    user = users_collection.find_one({"username": session.get("username")})
    return render_template("settings.html", user=user)

@app.route("/api/reports/generate", methods=["POST"])
def generate_report():
    try:
        data = request.get_json()
        report_type = data.get("report_type")
        start_date = data.get("start_date")
        end_date = data.get("end_date")
        
        # Convert dates to proper format
        start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").strftime("%Y-%m-%d")
        
        # Generate report based on type
        if report_type == "sales":
            sales_data = list(sales_collection.find({
                "date": {"$gte": start_date, "$lte": end_date}
            }))
            total_sales = sum(sale.get("total_amount", 0) for sale in sales_data)
            
            # Format sales data for export
            formatted_data = []
            for sale in sales_data:
                formatted_data.append({
                    "date": sale.get("date", ""),
                    "product_name": sale.get("product_name", ""),
                    "quantity": sale.get("quantity", 0),
                    "unit_price": sale.get("unit_price", 0),
                    "total_amount": sale.get("total_amount", 0),
                    "customer_name": sale.get("customer_name", "")
                })
            
            report = {
                "type": "sales",
                "title": "Sales Report",
                "start_date": start_date,
                "end_date": end_date,
                "summary": {
                    "total_sales": total_sales,
                    "total_transactions": len(sales_data),
                    "avg_transaction": total_sales / len(sales_data) if sales_data else 0,
                    "top_product": max(sales_data, key=lambda x: x.get("total_amount", 0)).get("product_name", "N/A") if sales_data else "N/A"
                },
                "data": formatted_data,
                "generated_at": datetime.datetime.now()
            }
        
        elif report_type == "inventory":
            products = list(products_collection.find({}))
            
            # Format inventory data for export
            formatted_data = []
            for product in products:
                formatted_data.append({
                    "name": product.get("name", ""),
                    "category": product.get("category", ""),
                    "stock_quantity": product.get("stock_quantity", 0),
                    "min_stock_level": product.get("min_stock_level", 10),
                    "unit_price": product.get("price", 0),
                    "total_value": product.get("stock_quantity", 0) * product.get("unit_price", 0),
                    "status": "Low Stock" if product.get("stock_quantity", 0) < product.get("min_stock_level", 10) else "In Stock"
                })
            
            total_value = sum(p["total_value"] for p in formatted_data)
            
            report = {
                "type": "inventory",
                "title": "Inventory Report",
                "start_date": start_date,
                "end_date": end_date,
                "summary": {
                    "total_products": len(products),
                    "low_stock_items": len([p for p in formatted_data if p["status"] == "Low Stock"]),
                    "total_value": total_value,
                    "warehouse_capacity": f"{min(95, (len(products) / 100) * 100):.1f}%"
                },
                "data": formatted_data,
                "generated_at": datetime.datetime.now()
            }
        
        elif report_type == "products":
            products = list(products_collection.find({}))
            
            # Format products data for export
            formatted_data = []
            for product in products:
                formatted_data.append({
                    "name": product.get("name", ""),
                    "category": product.get("category", ""),
                    "description": product.get("description", ""),
                    "unit_price": product.get("price", 0),
                    "stock_quantity": product.get("stock_quantity", 0),
                    "min_stock_level": product.get("min_stock_level", 10),
                    "supplier": product.get("supplier", ""),
                    "sku": product.get("sku", "")
                })
            
            report = {
                "type": "products",
                "title": "Products Report",
                "start_date": start_date,
                "end_date": end_date,
                "summary": {
                    "total_products": len(products),
                    "categories": len(set(p.get("category", "") for p in products)),
                    "avg_price": sum(p.get("price", 0) for p in products) / len(products) if products else 0,
                    "total_stock_value": sum(p.get("stock_quantity", 0) * p.get("price", 0) for p in products)
                },
                "data": formatted_data,
                "generated_at": datetime.datetime.now()
            }
        
        elif report_type == "financial":
            # Get all sales data for financial summary
            all_sales = list(sales_collection.find({
                "date": {"$gte": start_date, "$lte": end_date}
            }))
            
            total_revenue = sum(sale.get("total_amount", 0) for sale in all_sales)
            total_transactions = len(all_sales)
            
            # Calculate profit (assuming 70% cost of goods sold)
            estimated_profit = total_revenue * 0.3
            
            report = {
                "type": "financial",
                "title": "Financial Summary",
                "start_date": start_date,
                "end_date": end_date,
                "summary": {
                    "total_revenue": total_revenue,
                    "total_transactions": total_transactions,
                    "avg_transaction_value": total_revenue / total_transactions if total_transactions > 0 else 0,
                    "estimated_profit": estimated_profit
                },
                "data": [{
                    "date": sale.get("date", ""),
                    "transaction_id": str(sale.get("_id", "")),
                    "amount": sale.get("total_amount", 0),
                    "items_count": sale.get("quantity", 0)
                } for sale in all_sales],
                "generated_at": datetime.datetime.now()
            }
        
        else:
            return jsonify({"error": "Invalid report type"}), 400
        
        result = reports_collection.insert_one(report)
        report['_id'] = str(result.inserted_id)
        return jsonify({"message": "Report generated successfully", "report": report})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- SEND OTP ----------------

@app.route("/send-otp", methods=["POST"])
def send_otp():

    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email required"}), 400

    otp = str(random.randint(100000, 999999))
    expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)

    otp_storage[email] = {
        "otp": otp,
        "otp_expiry": expiry
    }

    try:
        msg = MIMEText(f"Your SmartStock OTP is: {otp}\n\nValid for 5 minutes.")
        msg["Subject"] = "SmartStock OTP Verification"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, email, msg.as_string())
        server.quit()

        return jsonify({"message": "OTP sent successfully"}), 200

    except Exception as e:
        print("OTP email error:", e)
        return jsonify({"message": "Server error while sending OTP"}), 500

@app.route("/api/reports/recent", methods=["GET"])
def get_recent_reports():
    try:
        reports = list(reports_collection.find().sort("generated_at", -1).limit(5))

        for r in reports:
            r["_id"] = str(r["_id"])

        return jsonify({"reports": reports})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reports/get/<report_id>", methods=["GET"])
def get_report(report_id):
    try:
        report = reports_collection.find_one({"_id": ObjectId(report_id)})

        if not report:
            return jsonify({"error": "Report not found"}), 404

        report["_id"] = str(report["_id"])

        return jsonify({"report": report})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/reports/export/csv", methods=["POST", "OPTIONS"])
def export_csv():
    # Handle OPTIONS request for CORS
    if request.method == "OPTIONS":
        response = app.response_class()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        return response
    
    try:
        data = request.get_json()
        report_id = data.get("report_id")

        report = reports_collection.find_one({"_id": ObjectId(report_id)})

        if not report:
            return jsonify({"error": "Report not found"}), 404

        import csv
        from io import StringIO, BytesIO

        # Check if report has data
        if not report.get("data") or len(report["data"]) == 0:
            return jsonify({"error": "This report contains no data to export. Please generate a new report with data first."}), 400

        # Create CSV content
        output = StringIO()
        writer = csv.writer(output)

        headers = report["data"][0].keys()
        writer.writerow(headers)

        for row in report["data"]:
            writer.writerow(row.values())

        # Convert to bytes for send_file
        csv_content = output.getvalue()
        mem = BytesIO()
        mem.write(csv_content.encode('utf-8'))
        mem.seek(0)

        from flask import send_file
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'{report.get("type", "report")}_export.csv'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/reports/demo/csv", methods=["GET"])
def demo_csv():
    """Generate a demo CSV file with sample inventory data"""
    try:
        import csv
        from io import StringIO, BytesIO
        from flask import send_file
        
        # Create demo data
        demo_data = [
            ["Product Name", "Category", "Stock Quantity", "Unit Price", "Total Value", "Status"],
            ["Laptop Dell XPS", "Electronics", 15, 1200.00, 18000.00, "In Stock"],
            ["Wireless Mouse", "Electronics", 45, 25.99, 1169.55, "In Stock"],
            ["USB-C Cable", "Accessories", 8, 12.50, 100.00, "Low Stock"],
            ["Office Chair", "Furniture", 12, 299.99, 3599.88, "In Stock"],
            ["Notebook Set", "Stationery", 3, 15.00, 45.00, "Low Stock"],
            ["Desk Lamp", "Furniture", 22, 45.99, 1011.78, "In Stock"],
            ["Keyboard Mechanical", "Electronics", 18, 89.99, 1619.82, "In Stock"],
            ["Monitor 27\"", "Electronics", 7, 349.99, 2449.93, "Low Stock"],
            ["Printer Paper", "Stationery", 50, 8.99, 449.50, "In Stock"],
            ["Webcam HD", "Electronics", 11, 79.99, 879.89, "In Stock"]
        ]
        
        # Create CSV content
        output = StringIO()
        writer = csv.writer(output)
        
        for row in demo_data:
            writer.writerow(row)
        
        # Convert to bytes for send_file
        csv_content = output.getvalue()
        mem = BytesIO()
        mem.write(csv_content.encode('utf-8'))
        mem.seek(0)
        
        return send_file(
            mem,
            mimetype='text/csv',
            as_attachment=True,
            download_name='demo_inventory_report.csv'
        )
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/reports/export/pdf", methods=["POST"])
def export_pdf():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from io import BytesIO
        from bson import ObjectId

        data = request.get_json()
        report_id = data.get("report_id")

        report = reports_collection.find_one({"_id": ObjectId(report_id)})

        if not report:
            return jsonify({"error": "Report not found"}), 404

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)

        y = 750
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(50, y, report["title"])

        y -= 30
        pdf.setFont("Helvetica", 12)
        pdf.drawString(50, y, f"Date Range: {report['start_date']} to {report['end_date']}")

        y -= 40
        pdf.drawString(50, y, "Summary")

        y -= 20
        for key, value in report["summary"].items():
            pdf.drawString(60, y, f"{key.replace('_',' ').title()}: {value}")
            y -= 20

        y -= 20
        pdf.drawString(50, y, "Detailed Data")

        y -= 20
        for row in report["data"][:20]:  # limit rows to avoid overflow
            line = " | ".join(str(v) for v in row.values())
            pdf.drawString(60, y, line)
            y -= 20

            if y < 100:
                pdf.showPage()
                y = 750

        pdf.save()

        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="report.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- VERIFY OTP ----------------

@app.route("/verify-otp", methods=["POST"])
def verify_otp():

    data = request.get_json()
    email = data.get("email")
    otp = data.get("otp")

    if not email or not otp:
        return jsonify({"message": "Missing data"}), 400

    user = otp_storage.get(email)

    if not user:
        return jsonify({"message": "OTP not requested"}), 404

    if user.get("otp") != otp:
        return jsonify({"message": "Invalid OTP"}), 400

    if datetime.datetime.utcnow() > user.get("otp_expiry"):
        del otp_storage[email]
        return jsonify({"message": "OTP expired"}), 400

    del otp_storage[email]

    return jsonify({"message": "OTP verified"}), 200


# ---------------- REGISTER ----------------

@app.route("/register", methods=["POST"])
def register():

    data = request.get_json()

    username = data.get("username")
    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    # Validate mobile number length
    contact_number = data.get("contactNumber")
    if not contact_number or not contact_number.isdigit() or len(contact_number) != 10:
        return jsonify({"message": "Mobile number must be exactly 10 digits"}), 400

    # Check if mobile already exists
    existing_phone = collection.find_one({"contactNumber": contact_number})

    if existing_phone:
        return jsonify({"message": "Mobile number already registered"}), 400

    if not username or not email or not password or not role:
        return jsonify({"message": "Missing fields"}), 400

    if collection.find_one({"username": username}):
        return jsonify({"message": "Username already exists"}), 400

    if collection.find_one({"email": email}):
        return jsonify({"message": "Email already exists"}), 400

    hashed_password = generate_password_hash(password)

    collection.insert_one({
        "username": username,
        "email": email,
        "password": hashed_password,
        "role": role,
        "contactNumber": data.get("contactNumber"),
        "shopAddress": data.get("shopAddress"),
        "gstin": data.get("gstin"),
        "city": data.get("city"),
        "state": data.get("state"),
        "pincode": data.get("pincode")
    })

    return jsonify({"message": "Registration successful"}), 201


# ---------------- LOGIN ----------------

@app.route("/login", methods=["POST"])
def login():

    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    device_info = data.get("deviceInfo", {})
    location = data.get("location", {})

    if not username or not password:
        return jsonify({"message": "Missing credentials"}), 400

    user = collection.find_one({
        "$or": [{"username": username}, {"email": username}]
    })

    if not user:
        return jsonify({"message": "Account does not exist"}), 401

    if not check_password_hash(user["password"], password):
        return jsonify({"message": "Invalid password"}), 401

    # Update last login information
    login_session = {
        "timestamp": datetime.datetime.utcnow(),
        "deviceInfo": device_info,
        "location": location
    }
    
    collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "lastLogin": login_session,
                "loginHistory": user.get("loginHistory", [])[-9:] + [login_session]  # Keep last 10 logins
            }
        }
    )

    # Store user email in session for real-time alerts
    session['user_email'] = user.get("email", "")
    session['username'] = user.get("username", "")
    session['user_id'] = str(user["_id"])
    session.permanent = True  # Make session persist
    
    print(f"✅ User session created: {user.get('email')}")

    token = jwt.encode({
        "username": user["username"],
        "email": user["email"],  # Add email to token for alerts
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    },
        app.config["SECRET_KEY"],
        algorithm="HS256"
    )

    return jsonify({
        "message": "Login successful",
        "token": token,
        "role": user["role"],
        "user_name": user.get("username", ""),
        "user_email": user.get("email", ""),
        "currency": user.get("system_settings", {}).get("currency", "INR")
    })


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():
    """Logout user and clear session"""
    session.clear()
    return redirect(url_for('login_page'))

# ---------------- FORGOT PASSWORD ----------------

@app.route("/last-login/<username>", methods=["GET"])
def get_last_login(username):
    """Get last login information for a user"""
    try:
        user = collection.find_one({
            "$or": [{"username": username}, {"email": username}]
        })
        
        if not user:
            return jsonify({"message": "User not found"}), 404
            
        last_login = user.get("lastLogin")
        if not last_login:
            return jsonify({"lastLogin": None}), 200
            
        # Convert ObjectId to string for JSON serialization
        if "_id" in last_login:
            last_login["_id"] = str(last_login["_id"])
            
        return jsonify({"lastLogin": last_login}), 200
        
    except Exception as e:
        return jsonify({"message": "Error fetching last login"}), 500

@app.route("/forgot-password", methods=["POST"])
def forgot_password():

    data = request.get_json()
    email = data.get("email")

    if not email:
        return jsonify({"message": "Email required"}), 400

    user = collection.find_one({"email": email})
    if not user:
        return jsonify({"message": "Email not registered"}), 404

    reset_token = secrets.token_urlsafe(32)
    expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=15)

    collection.update_one(
        {"email": email},
        {"$set": {
            "reset_token": reset_token,
            "reset_token_expiry": expiry
        }}
    )

    reset_link = f"http://127.0.0.1:5000/reset-password-page?token={reset_token}"

    try:
        msg = MIMEText(f"""
Click below to reset password:

{reset_link}

Valid for 15 minutes.
""")

        msg["Subject"] = "SmartStock Password Reset"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, email, msg.as_string())
        server.quit()

        return jsonify({"message": "Password reset link sent"}), 200

    except Exception as e:
        print("Email error:", e)
        return jsonify({"message": "Failed to send email"}), 500


# ---------------- RESET PASSWORD (FIXED) ----------------

@app.route("/reset-password", methods=["POST"])
def reset_password():

    data = request.get_json()

    # Accept both newPassword and newpassword from frontend
    token = data.get("token")
    new_password = data.get("newPassword") or data.get("newpassword")

    if not token or not new_password:
        return jsonify({"message": "Missing data"}), 400

    user = collection.find_one({"reset_token": token})

    if not user:
        return jsonify({"message": "Invalid token"}), 400

    # Safe expiry check
    expiry = user.get("reset_token_expiry")
    if not expiry or datetime.datetime.utcnow() > expiry:
        return jsonify({"message": "Token expired"}), 400

    hashed_password = generate_password_hash(new_password)

    collection.update_one(
        {"reset_token": token},
        {
            "$set": {"password": hashed_password},
            "$unset": {"reset_token": 1, "reset_token_expiry": 1}
        }
    )

    return jsonify({"message": "Password updated successfully"}), 200


# ---------------- ADMIN VIEW USERS ----------------

@app.route("/admin/users", methods=["GET"])
@token_required
def get_users(current_user):

    if current_user["role"] != "admin":
        return jsonify({"message": "Admin access required"}), 403

    users = list(collection.find({}, {"_id": 0, "username": 1, "role": 1}))
    return jsonify({"users": users})


# ---------------- THRESHOLD MANAGEMENT & ALERT SYSTEM ----------------

def get_category_thresholds():
    """Get default stock thresholds based on product categories"""
    return {
        "Electronics": 5,
        "Food": 20,
        "Beverages": 15,
        "Clothing": 10,
        "Furniture": 3,
        "Books": 25,
        "Toys": 15,
        "Sports": 8,
        "Beauty": 12,
        "Health": 10,
        "Office": 15,
        "Cleaning": 20,
        "general": 10
    }

def check_and_create_stock_alert(product, old_stock=None):
    """Check stock levels and create alerts if needed"""
    try:
        stock_qty = product.get('stock_quantity', 0)
        min_level = product.get('min_stock_level', 10)
        max_level = product.get('max_stock_level', 50)
        alert_enabled = product.get('alert_enabled', True)
        
        if not alert_enabled:
            return
        
        alert_type = None
        alert_message = ""
        alert_priority = "medium"
        
        # Check for different stock conditions
        if stock_qty == 0:
            alert_type = "out_of_stock"
            alert_message = f"CRITICAL: {product['name']} is completely out of stock!"
            alert_priority = "critical"
        elif stock_qty <= min_level:
            alert_type = "low_stock"
            alert_message = f"WARNING: {product['name']} stock is low ({stock_qty} units, threshold: {min_level})"
            alert_priority = "high"
        elif stock_qty >= max_level:
            alert_type = "overstock"
            alert_message = f"INFO: {product['name']} stock is high ({stock_qty} units, max: {max_level})"
            alert_priority = "low"
        elif old_stock is not None and stock_qty < old_stock and stock_qty <= min_level * 1.2:
            alert_type = "stock_decrease"
            alert_message = f"CAUTION: {product['name']} stock decreased to {stock_qty} units"
            alert_priority = "medium"
        
        # Create alert if condition detected
        if alert_type:
            create_stock_alert(product, alert_type, alert_message, alert_priority)
            
    except Exception as e:
        print(f"Error checking stock alert: {str(e)}")

def create_stock_alert(product, alert_type, message, priority):
    """Create a stock alert in the database"""
    try:
        # Check if alert already exists for this product and alert type
        existing_alert = alerts_collection.find_one({
            "product_id": str(product['_id']),
            "alert_type": alert_type,
            "status": "active"
        })
        
        if existing_alert:
            # Update existing alert with new stock quantity and message
            alerts_collection.update_one(
                {"_id": existing_alert["_id"]},
                {
                    "$set": {
                        "message": message,
                        "stock_quantity": product.get('stock_quantity', 0),
                        "min_stock_level": product.get('min_stock_level', 10),
                        "created_at": datetime.datetime.now()  # Update timestamp
                    }
                }
            )
            print(f"Updated existing alert for product {product['name']} ({alert_type})")
            return
        
        # Create new alert if none exists
        alert = {
            "product_id": str(product['_id']),
            "product_name": product['name'],
            "product_sku": product.get('sku', ''),
            "alert_type": alert_type,
            "message": message,
            "priority": priority,
            "status": "active",
            "stock_quantity": product.get('stock_quantity', 0),
            "min_stock_level": product.get('min_stock_level', 10),
            "created_at": datetime.datetime.now(),
            "acknowledged_by": None,
            "acknowledged_at": None
        }
        
        alerts_collection.insert_one(alert)
        
        # Send notifications if configured
        send_stock_notification(product, alert_type, message, priority)
        
    except Exception as e:
        print(f"Error creating stock alert: {str(e)}")

def send_stock_notification(product, alert_type, message, priority):
    """Send email notifications to currently logged-in user from active session"""
    try:
        # Get current logged-in user's email from active session (REAL-TIME)
        recipient_email = None
        
        try:
            from flask import request, session
            print("🔍 Checking for active user session...")
            
            # Method 1: Get from active session (PRIORITY - Real-time)
            if 'user_email' in session and session['user_email']:
                recipient_email = session['user_email']
                print(f"✅ Found logged-in user from ACTIVE SESSION: {recipient_email}")
            
            # Method 2: Get from JWT token (fallback)
            if not recipient_email:
                auth_header = request.headers.get('Authorization')
                if auth_header and auth_header.startswith('Bearer '):
                    try:
                        token = auth_header.split(' ')[1]
                        decoded = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
                        recipient_email = decoded.get('email')
                        print(f"✅ Found logged-in user from JWT TOKEN: {recipient_email}")
                    except Exception as e:
                        print(f"⚠️ Could not decode token: {str(e)}")
            
            # Method 3: Get from session username (another fallback)
            if not recipient_email and 'username' in session:
                user = collection.find_one({"username": session['username']})
                if user:
                    recipient_email = user.get('email')
                    print(f"✅ Found logged-in user from SESSION USERNAME: {recipient_email}")
                    
        except Exception as e:
            print(f"⚠️ Error getting logged-in user: {str(e)}")
        
        # If no logged-in user found, do not send email
        if not recipient_email:
            print("❌ No logged-in user found in active session - NO EMAIL SENT")
            print("🔒 Alert restricted: Only active logged-in users receive notifications")
            print("🔍 DEBUG: This means you need to login first!")
            return
        
        # Validate email format
        if '@' not in recipient_email or '.' not in recipient_email:
            print(f"❌ Invalid email format: {recipient_email}")
            return
        
        print(f"📧 Sending alert to ACTIVE SESSION USER: {recipient_email}")
        print(f"🔒 Real-time notification: Only this user receives alert")
        
        # Prepare email content with professional headers
        subject = f"Stock Alert - {alert_type.replace('_', ' ').title()}: {product['name']}"
        
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="background-color: #f8f9fa; padding: 20px; border-left: 4px solid #dc3545; margin: 20px 0; border-radius: 4px;">
                <h2 style="color: #dc3545; margin-top: 0;">📦 SmartStock Inventory Alert</h2>
                <p><strong>Product:</strong> {product['name']}</p>
                <p><strong>SKU:</strong> {product.get('sku', 'N/A')}</p>
                <p><strong>Category:</strong> {product.get('category', 'N/A')}</p>
                <p><strong>Current Stock:</strong> <span style="color: #dc3545; font-weight: bold;">{product.get('stock_quantity', 0)} units</span></p>
                <p><strong>Minimum Threshold:</strong> {product.get('min_stock_level', 10)} units</p>
                <p><strong>Alert Type:</strong> {alert_type.replace('_', ' ').title()}</p>
                <p><strong>Priority:</strong> {priority.upper()}</p>
                <p><strong>Alert Message:</strong> {message}</p>
                <p><strong>Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <hr style="border: none; border-top: 1px solid #dee2e6; margin: 20px 0;">
                <p style="margin-bottom: 0;"><em>Please review your inventory levels and consider restocking soon.</em></p>
                <p style="margin-bottom: 0; font-size: 12px; color: #6c757d;">This is an automated message from SmartStock Inventory Management System</p>
            </div>
        </body>
        </html>
        """
        
        # Send email to single authenticated user only with professional headers
        try:
            msg = MIMEText(email_body, 'html')
            msg["Subject"] = subject
            msg["From"] = f"SmartStock System <{EMAIL_ADDRESS}>"
            msg["To"] = recipient_email
            msg["Reply-To"] = EMAIL_ADDRESS
            msg["Return-Path"] = EMAIL_ADDRESS
            msg["X-Mailer"] = "SmartStock Alert System v1.0"
            msg["X-Priority"] = "3"  # Normal priority
            msg["Importance"] = "normal"
            
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, recipient_email, msg.as_string())
            server.quit()
            
            print(f"✅ Alert email sent to logged-in user: {recipient_email}")
            print(f"🔒 Security: Only active user received this notification")
            
        except Exception as e:
            print(f"❌ Failed to send email to {recipient_email}: {str(e)}")
                
    except Exception as e:
        print(f"Error sending stock notification: {str(e)}")

# ---------------- THRESHOLD MANAGEMENT API ENDPOINTS ----------------

@app.route("/api/thresholds/categories", methods=["GET"])
def get_category_thresholds_api():
    """Get default thresholds for all categories"""
    try:
        return jsonify({"category_thresholds": get_category_thresholds()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/thresholds/update-batch", methods=["POST"])
def update_batch_thresholds():
    """Update thresholds for multiple products at once"""
    try:
        data = request.get_json()
        product_updates = data.get("products", [])
        
        updated_count = 0
        for update in product_updates:
            product_id = update.get("product_id")
            min_level = update.get("min_stock_level")
            threshold_type = update.get("threshold_type", "custom")
            
            if product_id and min_level is not None:
                products_collection.update_one(
                    {"_id": ObjectId(product_id)},
                    {
                        "$set": {
                            "min_stock_level": int(min_level),
                            "threshold_type": threshold_type,
                            "updated_at": datetime.datetime.now()
                        }
                    }
                )
                updated_count += 1
        
        return jsonify({
            "message": f"Updated thresholds for {updated_count} products",
            "updated_count": updated_count
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts", methods=["GET", "POST"])
def manage_alerts():
    if request.method == "GET":
        try:
            # Get query parameters for filtering
            status = request.args.get("status", "active")
            priority = request.args.get("priority", "")
            alert_type = request.args.get("type", "")
            
            # Build filter
            filter_query = {}
            if status and status != "all":
                filter_query["status"] = status
            if priority and priority != "all":
                filter_query["priority"] = priority
            if alert_type and alert_type != "all":
                filter_query["alert_type"] = alert_type
            
            alerts = list(alerts_collection.find(filter_query).sort("created_at", -1))
            for alert in alerts:
                alert['_id'] = str(alert['_id'])
                # Convert datetime to ISO string for proper JSON serialization
                if 'created_at' in alert and alert['created_at']:
                    if isinstance(alert['created_at'], datetime.datetime):
                        alert['created_at'] = alert['created_at'].isoformat()
                    else:
                        alert['created_at'] = str(alert['created_at'])
                
            return jsonify({"alerts": alerts})
        except Exception as e:
            print(f"Error loading alerts: {str(e)}")
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            alert = {
                "product_id": data.get("product_id"),
                "product_name": data.get("product_name"),
                "alert_type": data.get("alert_type"),
                "message": data.get("message"),
                "priority": data.get("priority", "medium"),
                "status": data.get("status", "active"),
                "created_at": datetime.datetime.now()
            }
            
            result = alerts_collection.insert_one(alert)
            alert['_id'] = str(result.inserted_id)
            
            return jsonify({"message": "Alert created successfully", "alert": alert}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/notifications", methods=["GET"])
def get_notifications():

    try:

        alerts_collection = get_collection("alerts")

        recent_alerts = list(
            alerts_collection.find(
                {"status": {"$ne": "resolved"}}
            ).sort("created_at", -1).limit(5)
        )

        notifications = []
        unread_count = 0

        for alert in recent_alerts:

            notification = {
                "id": str(alert["_id"]),
                "title": alert.get("alert_type", "Alert"),
                "message": alert.get("message", ""),
                "priority": alert.get("priority", "medium"),
                "read": alert.get("status") == "acknowledged"
            }

            notifications.append(notification)

            if alert.get("status") != "acknowledged":
                unread_count += 1

        return jsonify({
            "notifications": notifications,
            "unread_count": unread_count
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def get_time_ago(created_at):
    """Calculate time ago string"""
    if not created_at:
        return "Just now"
    
    now = datetime.datetime.now()
    if isinstance(created_at, str):
        created_at = datetime.datetime.fromisoformat(created_at.replace('Z', '+00:00'))
    
    diff = now - created_at
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"

@app.route("/api/notifications/<notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        alerts_collection = db["alerts"]
        result = alerts_collection.update_one(
            {"_id": ObjectId(notification_id)},
            {"$set": {"status": "acknowledged"}}
        )
        
        if result.modified_count > 0:
            return jsonify({"message": "Notification marked as read"}), 200
        else:
            return jsonify({"error": "Notification not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/notifications/clear", methods=["POST"])
def clear_all_notifications():
    """Clear all notifications"""
    try:
        alerts_collection = db["alerts"]
        result = alerts_collection.update_many(
            {"status": {"$ne": "resolved"}},
            {"$set": {"status": "acknowledged"}}
        )
        
        return jsonify({
            "message": f"Cleared {result.modified_count} notifications"
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/cleanup-duplicates", methods=["POST"])
def cleanup_duplicate_alerts():
    """Remove duplicate alerts for the same product and alert type"""
    try:
        # Find all active alerts grouped by product_id and alert_type
        pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {
                "_id": {"product_id": "$product_id", "alert_type": "$alert_type"},
                "alerts": {"$push": "$_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        
        duplicates = list(alerts_collection.aggregate(pipeline))
        
        removed_count = 0
        for duplicate_group in duplicates:
            # Keep the newest alert (highest _id in ObjectId comparison)
            alerts_to_remove = sorted(duplicate_group["alerts"])[:-1]  # Remove all except the last one
            
            result = alerts_collection.delete_many({"_id": {"$in": alerts_to_remove}})
            removed_count += result.deleted_count
        
        return jsonify({
            "message": f"Cleaned up {removed_count} duplicate alerts",
            "duplicate_groups": len(duplicates)
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/clear", methods=["POST"])
def clear_all_alerts():
    """Delete all alerts from database"""
    try:
        alerts_collection = db["alerts"]
        result = alerts_collection.delete_many({})
        
        return jsonify({
            "message": f"Deleted {result.deleted_count} alerts from database",
            "deleted_count": result.deleted_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/<alert_id>/acknowledge", methods=["POST"])
def acknowledge_alert(alert_id):
    """Acknowledge an alert"""
    try:
        alerts_collection.update_one(
            {"_id": ObjectId(alert_id)},
            {
                "$set": {
                    "status": "acknowledged",
                    "acknowledged_by": "admin",  # Should get from token in production
                    "acknowledged_at": datetime.datetime.now()
                }
            }
        )
        
        return jsonify({"message": "Alert acknowledged successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ---------------- DASHBOARD API ENDPOINTS ----------------

@app.route("/api/dashboard/stats", methods=["GET"])
def get_dashboard_stats():
    try:
        total_products = products_collection.count_documents({})
        
        # Calculate total stock and threshold-based stats
        products = list(products_collection.find({}, {
            'stock_quantity': 1, 
            'min_stock_level': 1, 
            'category': 1
        }))
        
        total_stock = sum(product.get('stock_quantity', 0) for product in products)
        
        # Calculate low stock items based on individual thresholds
        low_stock_items = [p for p in products if p.get('stock_quantity', 0) <= p.get('min_stock_level', 10)]
        out_of_stock_items = [p for p in products if p.get('stock_quantity', 0) == 0]
        
        # Get active alerts
        active_alerts = alerts_collection.count_documents({"status": "active"})
        critical_alerts = alerts_collection.count_documents({"status": "active", "priority": "critical"})
        
        # Sales stats
        now_utc = datetime.datetime.utcnow()
        today_start = datetime.datetime.combine(now_utc.date(), datetime.time.min)
        today_end = datetime.datetime.combine(now_utc.date(), datetime.time.max)
        today_sales = sales_collection.count_documents({
            "created_at": {
                "$gte": today_start,
                "$lte": today_end
            }
        })
        total_transactions = sales_collection.count_documents({})
        
        # Category breakdown
        category_stats = {}
        for product in products:
            category = product.get('category', 'general')
            if category not in category_stats:
                category_stats[category] = {'count': 0, 'stock': 0, 'low_stock': 0}
            category_stats[category]['count'] += 1
            category_stats[category]['stock'] += product.get('stock_quantity', 0)
            if product.get('stock_quantity', 0) <= product.get('min_stock_level', 10):
                category_stats[category]['low_stock'] += 1

        return jsonify({
            "total_products": total_products,
            "total_stock": total_stock,
            "low_stock_items": len(low_stock_items),
            "out_of_stock_items": len(out_of_stock_items),
            "active_alerts": active_alerts,
            "critical_alerts": critical_alerts,
            "today_sales": today_sales,
            "total_transactions": total_transactions,
            "category_stats": category_stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/products", methods=["GET", "POST"])
def manage_products():
    if request.method == "GET":
        try:
            products = list(products_collection.find({}))
            for product in products:
                product['_id'] = str(product['_id'])
                # Add stock status based on threshold
                stock_qty = product.get('stock_quantity', 0)
                min_level = product.get('min_stock_level', 10)
                
                if stock_qty == 0:
                    product['stock_status'] = 'out_of_stock'
                    product['stock_status_color'] = 'danger'
                elif stock_qty <= min_level:
                    product['stock_status'] = 'low_stock'
                    product['stock_status_color'] = 'warning'
                else:
                    product['stock_status'] = 'in_stock'
                    product['stock_status_color'] = 'success'
                    
            return jsonify({"products": products})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            
            # Enhanced threshold management
            category = data.get("category", "general")
            category_thresholds = get_category_thresholds()
            default_threshold = category_thresholds.get(category, 10)
            
            product = {
                "name": data.get("name"),
                "sku": data.get("sku"),
                "category": category,
                "supplier": data.get("supplier"),
                "price": float(data.get("price")),
                "stock_quantity": int(data.get("stock_quantity")),
                "min_stock_level": int(data.get("min_stock_level", default_threshold)),
                "threshold_type": data.get("threshold_type", "custom"),  # custom, category_based, auto
                "reorder_point": int(data.get("reorder_point", data.get("min_stock_level", default_threshold) * 1.5)),
                "max_stock_level": int(data.get("max_stock_level", data.get("min_stock_level", default_threshold) * 5)),
                "alert_enabled": data.get("alert_enabled", True),
                "alert_recipients": data.get("alert_recipients", []),
                "created_at": datetime.datetime.utcnow(),
                "updated_at": datetime.datetime.utcnow()
            }
            
            result = products_collection.insert_one(product)
            product['_id'] = str(result.inserted_id)
            
            # Check if stock is below threshold and create alert
            check_and_create_stock_alert(product)
            
            return jsonify({"message": "Product added successfully", "product": product}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/products/<product_id>", methods=["PUT", "DELETE"])
def manage_product(product_id):
    if request.method == "PUT":
        try:
            data = request.get_json()
            
            # Get current product to check stock changes
            current_product = products_collection.find_one({"_id": ObjectId(product_id)})
            if not current_product:
                return jsonify({"message": "Product not found"}), 404
            
            old_stock = current_product.get('stock_quantity', 0)
            new_stock = int(data.get("stock_quantity", old_stock))
            
            update_data = {
                "name": data.get("name", current_product.get("name")),
                "sku": data.get("sku", current_product.get("sku")),
                "category": data.get("category", current_product.get("category")),
                "supplier": data.get("supplier", current_product.get("supplier")),
                "price": float(data.get("price", current_product.get("price", 0))),
                "stock_quantity": new_stock,
                "min_stock_level": int(data.get("min_stock_level", current_product.get('min_stock_level', 10))),
                "threshold_type": data.get("threshold_type", current_product.get('threshold_type', 'custom')),
                "reorder_point": int(data.get("reorder_point", current_product.get('reorder_point', 15))),
                "max_stock_level": int(data.get("max_stock_level", current_product.get('max_stock_level', 50))),
                "alert_enabled": data.get("alert_enabled", current_product.get('alert_enabled', True)),
                "alert_recipients": data.get("alert_recipients", current_product.get('alert_recipients', [])),
                "updated_at": datetime.datetime.now()
            }
            
            products_collection.update_one({"_id": ObjectId(product_id)}, {"$set": update_data})
            
            # Get updated product for alert checking
            updated_product = products_collection.find_one({"_id": ObjectId(product_id)})
            updated_product['_id'] = str(updated_product['_id'])
            
            # Check for stock changes and create alerts
            if old_stock != new_stock:
                check_and_create_stock_alert(updated_product, old_stock)
            
            return jsonify({"message": "Product updated successfully", "product": updated_product})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "DELETE":
        try:
            products_collection.delete_one({"_id": ObjectId(product_id)})
            return jsonify({"message": "Product deleted successfully"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/sales", methods=["GET", "POST"])
def manage_sales():
    if request.method == "GET":
        try:
            sales = list(sales_collection.find({}))
            for sale in sales:
                sale['_id'] = str(sale['_id'])
            return jsonify({"sales": sales})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            sale = {
                "product_id": data.get("product_id"),
                "product_name": data.get("product_name"),
                "quantity": int(data.get("quantity")),
                "unit_price": float(data.get("unit_price")),
                "total_amount": float(data.get("total_amount")),
                "payment_method": data.get("payment_method"),
                "customer_name": data.get("customer_name"),
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "created_at": datetime.datetime.now()
            }
            
            # Update product stock
            products_collection.update_one(
                {"_id": ObjectId(data.get("product_id"))},
                {"$inc": {"stock_quantity": -int(data.get("quantity"))}}
            )
            
            result = sales_collection.insert_one(sale)
            sale['_id'] = str(result.inserted_id)
            return jsonify({"message": "Sale recorded successfully", "sale": sale}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/inventory/update", methods=["POST"])
def update_inventory():
    try:
        data = request.get_json()
        product_id = data.get("product_id")
        operation = data.get("operation")  # "stock_in" or "stock_out"
        quantity = int(data.get("quantity"))
        reason = data.get("reason", "Manual update")
        
        # Get product details for audit log
        product = products_collection.find_one({"_id": ObjectId(product_id)})
        if not product:
            return jsonify({"error": "Product not found"}), 404
        
        # Record transaction before update
        transaction = {
            "product_id": product_id,
            "product_name": product.get("name", "Unknown"),
            "product_sku": product.get("sku", "Unknown"),
            "transaction_type": operation,
            "quantity": quantity,
            "previous_stock": product.get("stock_quantity", 0),
            "reason": reason,
            "timestamp": datetime.datetime.now(),
            "date": datetime.datetime.now().strftime("%Y-%m-%d"),
            "time": datetime.datetime.now().strftime("%H:%M:%S")
        }
        
        if operation == "stock_in":
            products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$inc": {"stock_quantity": quantity}}
            )
            transaction["new_stock"] = product.get("stock_quantity", 0) + quantity
        elif operation == "stock_out":
            # Check if enough stock is available
            if product.get("stock_quantity", 0) < quantity:
                return jsonify({"error": "Insufficient stock available"}), 400
            products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$inc": {"stock_quantity": -quantity}}
            )
            transaction["new_stock"] = product.get("stock_quantity", 0) - quantity
        else:
            return jsonify({"error": "Invalid operation"}), 400
        
        # Save transaction to database
        result = transactions_collection.insert_one(transaction)
        
        # Convert ObjectId to string for JSON serialization
        response_transaction = transaction.copy()
        response_transaction["_id"] = str(result.inserted_id)
        
        return jsonify({"message": f"Stock {operation.replace('_', ' ')} successful", "transaction": response_transaction})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    try:
        # Get query parameters for filtering
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        product_id = request.args.get("product_id")
        transaction_type = request.args.get("transaction_type")
        
        # Build query
        query = {}
        if start_date and end_date:
            query["date"] = {"$gte": start_date, "$lte": end_date}
        if product_id:
            query["product_id"] = product_id
        if transaction_type:
            query["transaction_type"] = transaction_type
        
        transactions = list(transactions_collection.find(query).sort("timestamp", -1))
        for transaction in transactions:
            transaction['_id'] = str(transaction['_id'])
        
        return jsonify({"transactions": transactions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def check_all_products_for_low_stock():
    """Check all products for low stock and send alerts to user emails"""
    try:
        # Get all users to send alerts to
        users = list(collection.find({"email": {"$exists": True}}, {"email": 1, "username": 1}))
        user_emails = [user['email'] for user in users if 'email' in user]
        
        # Get all products
        products = list(products_collection.find({}))
        
        alerts_created = 0
        
        for product in products:
            stock_qty = product.get('stock_quantity', 0)
            min_level = product.get('min_stock_level', 10)
            alert_enabled = product.get('alert_enabled', True)
            
            # Check if product needs alert
            if alert_enabled and stock_qty <= min_level:
                # Check if alert already exists for this product and alert type
                alert_type = "out_of_stock" if stock_qty == 0 else "low_stock"
                existing_alert = alerts_collection.find_one({
                    "product_id": str(product['_id']),
                    "alert_type": alert_type,
                    "status": "active"
                })
                
                if not existing_alert:
                    # Create alert for this product
                    priority = "critical" if stock_qty == 0 else "high"
                    
                    alert = {
                        "product_id": str(product['_id']),
                        "product_name": product.get('name', 'Unknown'),
                        "product_sku": product.get('sku', ''),
                        "alert_type": alert_type,
                        "message": f"{'CRITICAL' if stock_qty == 0 else 'WARNING'}: {product.get('name', 'Unknown')} stock is {alert_type.replace('_', ' ')} ({stock_qty} units, threshold: {min_level})",
                        "priority": priority,
                        "status": "active",
                        "stock_quantity": stock_qty,
                        "min_stock_level": min_level,
                        "created_at": datetime.datetime.now(),
                        "acknowledged_by": None,
                        "acknowledged_at": None
                    }
                    
                    alerts_collection.insert_one(alert)
                    alerts_created += 1
                    
                    # Send email to all users
                    send_low_stock_email_to_users(product, alert_type, priority, user_emails)
        
        if alerts_created > 0:
            print(f"✅ Created {alerts_created} low stock alerts and sent emails to {len(user_emails)} users")
        
        return alerts_created
        
    except Exception as e:
        print(f"❌ Error checking products for low stock: {str(e)}")
        return 0

@app.route("/api/generate-alerts", methods=["POST"])
def generate_alerts():
    """Manually trigger alert generation for all products"""
    try:
        alerts_created = check_all_products_for_low_stock()
        return jsonify({
            "message": f"Alert generation completed successfully",
            "alerts_created": alerts_created
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def send_low_stock_email_to_users(product, alert_type, priority, user_emails):
    """Send low stock alert email to all users"""
    try:
        stock_qty = product.get('stock_quantity', 0)
        min_level = product.get('min_stock_level', 10)
        
        # Prepare email content
        subject = f"🚨 SmartStock Alert - {alert_type.replace('_', ' ').title()}: {product.get('name', 'Unknown')}"
        
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 10px; color: white;">
                <h2 style="margin: 0; text-align: center;">🚨 SmartStock Inventory Alert</h2>
                <p style="margin: 10px 0; text-align: center; font-size: 18px;">
                    {priority.upper()} PRIORITY ALERT
                </p>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h3 style="color: #dc3545; margin-top: 0;">Product Details:</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Product Name:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{product.get('name', 'Unknown')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">SKU:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{product.get('sku', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Category:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{product.get('category', 'N/A')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Current Stock:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #dc3545; font-weight: bold;">{stock_qty} units</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">Minimum Threshold:</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{min_level} units</td>
                    </tr>
                </table>
            </div>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <h4 style="color: #856404; margin-top: 0;">⚠️ Action Required:</h4>
                <p style="margin: 5px 0;">
                    {'Product is completely OUT OF STOCK! Immediate action required!' if stock_qty == 0 else f'Product stock is running low. Please reorder soon to avoid stockout.'}
                </p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://127.0.0.1:5000/products" style="background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    📦 Manage Inventory
                </a>
            </div>
            
            <div style="background: #e9ecef; padding: 15px; border-radius: 10px; text-align: center; font-size: 12px; color: #6c757d;">
                <p style="margin: 0;">
                    This is an automated alert from SmartStock Inventory Management System<br>
                    Alert Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                    📧 Sent to {len(user_emails)} registered users
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email to all users
        for recipient in user_emails:
            try:
                msg = MIMEText(email_body, 'html')
                msg["Subject"] = subject
                msg["From"] = EMAIL_ADDRESS
                msg["To"] = recipient
                
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.sendmail(EMAIL_ADDRESS, recipient, msg.as_string())
                server.quit()
                
                print(f"✅ Low stock alert email sent to {recipient}")
                
            except Exception as e:
                print(f"❌ Failed to send email to {recipient}: {str(e)}")
                
    except Exception as e:
        print(f"❌ Error sending low stock email: {str(e)}")

# Add automatic monitoring route
# Add test email route
@app.route("/api/test-user-email", methods=["POST"])
def test_user_email():
    """Test sending email to registered users"""
    try:
        # Get all users
        users = list(collection.find({"email": {"$exists": True}}, {"email": 1, "username": 1}))
        user_emails = [user['email'] for user in users if 'email' in user]
        
        if not user_emails:
            return jsonify({"message": "No users with email found"}), 404
        
        # Send test email
        subject = "🧪 SmartStock System Test - Email Notifications Working"
        
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: linear-gradient(135deg, #28a745 0%, #20c997 100%); padding: 20px; border-radius: 10px; color: white; text-align: center;">
                <h2 style="margin: 0;">✅ SmartStock Email System Test</h2>
                <p style="margin: 10px 0; font-size: 18px;">Your email notifications are working perfectly!</p>
            </div>
            
            <div style="background: #f8f9fa; padding: 20px; border-radius: 10px; margin: 20px 0;">
                <h3 style="color: #28a745; margin-top: 0;">🎉 Test Successful!</h3>
                <p style="margin: 10px 0;">
                    This email confirms that your SmartStock inventory alert system is working correctly.
                    When any product falls below its minimum stock level, you will receive automatic email alerts just like this one.
                </p>
                
                <div style="background: #d4edda; padding: 15px; border-radius: 10px; margin: 15px 0; border-left: 4px solid #28a745;">
                    <h4 style="color: #155724; margin-top: 0;">✅ What's Working:</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li>✅ User email registration</li>
                        <li>✅ Product threshold monitoring</li>
                        <li>✅ Automatic alert creation</li>
                        <li>✅ Email notification delivery</li>
                        <li>✅ Professional HTML formatting</li>
                    </ul>
                </div>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="http://127.0.0.1:5000/products" style="background: #007bff; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">
                    📦 Go to SmartStock
                </a>
            </div>
            
            <div style="background: #e9ecef; padding: 15px; border-radius: 10px; text-align: center; font-size: 12px; color: #6c757d;">
                <p style="margin: 0;">
                    This is a test email from SmartStock Inventory Management System<br>
                    Test Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}<br>
                    📧 Sent to {len(user_emails)} registered user(s)
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email to all users
        for recipient in user_emails:
            try:
                msg = MIMEText(email_body, 'html')
                msg["Subject"] = subject
                msg["From"] = EMAIL_ADDRESS
                msg["To"] = recipient
                
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
                server.sendmail(EMAIL_ADDRESS, recipient, msg.as_string())
                server.quit()
                
                print(f"✅ Test email sent to {recipient}")
                
            except Exception as e:
                print(f"❌ Failed to send test email to {recipient}: {str(e)}")
        
        return jsonify({
            "message": f"Test email sent to {len(user_emails)} users",
            "users_count": len(user_emails),
            "emails_sent": user_emails
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/check-low-stock", methods=["POST"])
def trigger_low_stock_check():
    """Manual trigger for low stock checking"""
    try:
        alerts_created = check_all_products_for_low_stock()
        return jsonify({
            "message": f"Low stock check completed. Created {alerts_created} alerts.",
            "alerts_created": alerts_created
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/clear-test-users", methods=["POST"])
def clear_test_users():
    """Clear test/demo users only"""
    try:
        # Clear test users (those with test emails)
        test_emails = ["testuser@example.com"]
        result = collection.delete_many({"email": {"$in": test_emails}})
        
        return jsonify({
            "message": f"Removed {result.deleted_count} test users",
            "users_removed": result.deleted_count
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/<alert_id>/resolve", methods=["POST"])
def resolve_alert(alert_id):
    """Resolve a specific alert"""
    try:
        # Convert string ID to ObjectId if needed
        from bson import ObjectId
        try:
            object_id = ObjectId(alert_id)
            query = {"_id": object_id}
        except:
            query = {"_id": alert_id}
        
        # Update alert status to resolved
        result = alerts_collection.update_one(
            query,
            {
                "$set": {
                    "status": "resolved",
                    "acknowledged_at": datetime.datetime.utcnow(),
                    "acknowledged_by": "user"  # You can get actual user from session
                }
            }
        )
        
        if result.modified_count > 0:
            return jsonify({
                "message": "Alert resolved successfully",
                "alert_id": alert_id
            }), 200
        else:
            return jsonify({"error": "Alert not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/<alert_id>/dismiss", methods=["POST"])
def dismiss_alert(alert_id):
    """Dismiss a specific alert"""
    try:
        # Convert string ID to ObjectId if needed
        from bson import ObjectId
        try:
            object_id = ObjectId(alert_id)
            query = {"_id": object_id}
        except:
            query = {"_id": alert_id}
        
        # Update alert status to dismissed
        result = alerts_collection.update_one(
            query,
            {
                "$set": {
                    "status": "dismissed",
                    "acknowledged_at": datetime.datetime.utcnow(),
                    "acknowledged_by": "user"  # You can get actual user from session
                }
            }
        )
        
        if result.modified_count > 0:
            return jsonify({
                "message": "Alert dismissed successfully",
                "alert_id": alert_id
            }), 200
        else:
            return jsonify({"error": "Alert not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/<alert_id>/delete", methods=["DELETE"])
def delete_alert(alert_id):
    """Delete a specific alert"""
    try:
        # Convert string ID to ObjectId if needed
        from bson import ObjectId
        try:
            object_id = ObjectId(alert_id)
            query = {"_id": object_id}
        except:
            query = {"_id": alert_id}
        
        # Delete the alert
        result = alerts_collection.delete_one(query)
        
        if result.deleted_count > 0:
            return jsonify({
                "message": "Alert deleted successfully",
                "alert_id": alert_id
            }), 200
        else:
            return jsonify({"error": "Alert not found"}), 404
            
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/alerts/statistics", methods=["GET"])
def get_alert_statistics():
    """Get alert statistics"""
    try:
        stats = {}
        
        # Count by status
        status_pipeline = [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
        status_counts = list(alerts_collection.aggregate(status_pipeline))
        stats["by_status"] = {item["_id"]: item["count"] for item in status_counts}
        
        # Count by priority
        priority_pipeline = [
            {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
        ]
        priority_counts = list(alerts_collection.aggregate(priority_pipeline))
        stats["by_priority"] = {item["_id"]: item["count"] for item in priority_counts}
        
        # Count by alert type
        type_pipeline = [
            {"$group": {"_id": "$alert_type", "count": {"$sum": 1}}}
        ]
        type_counts = list(alerts_collection.aggregate(type_pipeline))
        stats["by_type"] = {item["_id"]: item["count"] for item in type_counts}
        
        # Total counts
        stats["total"] = alerts_collection.count_documents({})
        stats["active"] = alerts_collection.count_documents({"status": "active"})
        stats["resolved"] = alerts_collection.count_documents({"status": "resolved"})
        stats["critical"] = alerts_collection.count_documents({"alert_type": "critical"})
        
        return jsonify(stats), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/clear-demo-data", methods=["POST"])
def clear_demo_data():
    """Clear all demo/test data from collections"""
    try:
        # Clear all products
        products_collection.delete_many({})
        
        # Clear all alerts
        alerts_collection.delete_many({})
        
        # Clear all sales
        sales_collection.delete_many({})
        
        # Clear all transactions
        transactions_collection.delete_many({})
        
        # Clear all reports
        reports_collection.delete_many({})
        
        return jsonify({
            "message": "All demo data cleared successfully",
            "cleared_collections": ["products", "alerts", "sales", "transactions", "reports"]
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/cleanup-duplicates", methods=["POST"])
def cleanup_all_duplicates():
    """Remove duplicate data across all collections"""
    try:
        cleanup_results = {}
        
        # Cleanup duplicate products
        product_pipeline = [
            {"$group": {
                "_id": {"name": "$name", "category": "$category"},
                "count": {"$sum": 1},
                "latest": {"$max": "$_id"}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        duplicate_products = list(products_collection.aggregate(product_pipeline))
        
        products_removed = 0
        for duplicate in duplicate_products:
            # Remove all except the latest
            result = products_collection.delete_many({
                "name": duplicate["_id"]["name"],
                "category": duplicate["_id"]["category"],
                "_id": {"$ne": duplicate["latest"]}
            })
            products_removed += result.deleted_count
        
        cleanup_results["products"] = products_removed
        
        # Cleanup duplicate alerts (already exists but we'll integrate here)
        alert_pipeline = [
            {"$group": {
                "_id": {"product_id": "$product_id", "alert_type": "$alert_type"},
                "count": {"$sum": 1},
                "latest": {"$max": "$created_at"}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        duplicate_alerts = list(alerts_collection.aggregate(alert_pipeline))
        
        alerts_removed = 0
        for duplicate in duplicate_alerts:
            # Remove all except the latest
            result = alerts_collection.delete_many({
                "product_id": duplicate["_id"]["product_id"],
                "alert_type": duplicate["_id"]["alert_type"],
                "created_at": {"$ne": duplicate["latest"]}
            })
            alerts_removed += result.deleted_count
        
        cleanup_results["alerts"] = alerts_removed
        
        # Cleanup duplicate sales
        sales_pipeline = [
            {"$group": {
                "_id": {"product_id": "$product_id", "timestamp": "$timestamp"},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        duplicate_sales = list(sales_collection.aggregate(sales_pipeline))
        
        sales_removed = 0
        for duplicate in duplicate_sales:
            # Keep only one record per product per timestamp
            result = sales_collection.delete_many({
                "product_id": duplicate["_id"]["product_id"],
                "timestamp": duplicate["_id"]["timestamp"]
            })
            sales_removed += result.deleted_count - 1  # Keep one, remove rest
        
        cleanup_results["sales"] = sales_removed
        
        # Cleanup duplicate transactions
        transaction_pipeline = [
            {"$group": {
                "_id": {"transaction_id": "$transaction_id"},
                "count": {"$sum": 1}
            }},
            {"$match": {"count": {"$gt": 1}}}
        ]
        duplicate_transactions = list(transactions_collection.aggregate(transaction_pipeline))
        
        transactions_removed = 0
        for duplicate in duplicate_transactions:
            # Keep only one record per transaction_id
            result = transactions_collection.delete_many({
                "transaction_id": duplicate["_id"]["transaction_id"]
            })
            transactions_removed += result.deleted_count - 1  # Keep one, remove rest
        
        cleanup_results["transactions"] = transactions_removed
        
        total_removed = sum(cleanup_results.values())
        
        return jsonify({
            "message": "Duplicate data cleanup completed successfully",
            "cleanup_results": cleanup_results,
            "total_duplicates_removed": total_removed
        }), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/data-integrity", methods=["GET"])
def check_data_integrity():
    """Check data integrity and report issues"""
    try:
        integrity_report = {}
        
        # Check products
        total_products = products_collection.count_documents({})
        products_with_invalid_stock = products_collection.count_documents({
            "$or": [
                {"stock_quantity": {"$lt": 0}},
                {"stock_quantity": {"$type": "null"}},
                {"price": {"$lt": 0}},
                {"price": {"$type": "null"}}
            ]
        })
        
        integrity_report["products"] = {
            "total": total_products,
            "invalid_records": products_with_invalid_stock,
            "valid": total_products - products_with_invalid_stock
        }
        
        # Check alerts
        total_alerts = alerts_collection.count_documents({})
        alerts_with_invalid_data = alerts_collection.count_documents({
            "$or": [
                {"product_id": {"$type": "null"}},
                {"alert_type": {"$type": "null"}},
                {"status": {"$type": "null"}}
            ]
        })
        
        integrity_report["alerts"] = {
            "total": total_alerts,
            "invalid_records": alerts_with_invalid_data,
            "valid": total_alerts - alerts_with_invalid_data
        }
        
        # Check sales
        total_sales = sales_collection.count_documents({})
        sales_with_invalid_data = sales_collection.count_documents({
            "$or": [
                {"product_id": {"$type": "null"}},
                {"quantity": {"$lt": 0}},
                {"total_amount": {"$lt": 0}}
            ]
        })
        
        integrity_report["sales"] = {
            "total": total_sales,
            "invalid_records": sales_with_invalid_data,
            "valid": total_sales - sales_with_invalid_data
        }
        
        # Check transactions
        total_transactions = transactions_collection.count_documents({})
        transactions_with_invalid_data = transactions_collection.count_documents({
            "$or": [
                {"transaction_id": {"$type": "null"}},
                {"amount": {"$lt": 0}},
                {"type": {"$type": "null"}}
            ]
        })
        
        integrity_report["transactions"] = {
            "total": total_transactions,
            "invalid_records": transactions_with_invalid_data,
            "valid": total_transactions - transactions_with_invalid_data
        }
        
        # Overall summary
        total_records = sum([report["total"] for report in integrity_report.values()])
        total_invalid = sum([report["invalid_records"] for report in integrity_report.values()])
        total_valid = total_records - total_invalid
        
        integrity_report["summary"] = {
            "total_records": total_records,
            "valid_records": total_valid,
            "invalid_records": total_invalid,
            "data_quality_percentage": round((total_valid / total_records * 100) if total_records > 0 else 100, 2)
        }
        
        return jsonify(integrity_report), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard/data")
def dashboard_data():

    from datetime import datetime, timedelta
    from flask import request, jsonify

    # Get range from frontend
    range_value = request.args.get("range", "7")

    if range_value == "30":
        days = 30
    elif range_value == "90":
        days = 90
    else:
        days = 7

    start_date = datetime.today() - timedelta(days=days)

    products = list(db.products.find())
    sales = list(db.sales.find())

    # -------- SALES OVERVIEW --------

    sales_by_date = {}
    for i in range(days):
        day = (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
        sales_by_date[day] = 0
    for s in sales:

        date_str = s.get("date")
        amount = s.get("total_amount", 0)

        if not date_str:
            continue

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            continue
        
        date_key = date_obj.strftime("%Y-%m-%d")

        if date_key in sales_by_date:
            sales_by_date[date_key] += amount

    # -------- INVENTORY STATUS --------

    in_stock = 0
    low_stock = 0
    out_stock = 0

    for p in products:

        stock = p.get("stock_quantity", 0)
        min_stock = p.get("min_stock_level", 5)

        if stock == 0:
            out_stock += 1

        elif stock <= min_stock:
            low_stock += 1

        else:
            in_stock += 1


    # -------- TOP PRODUCTS --------

    pipeline = [
        {
            "$group": {
                "_id": "$product_name",
                "total_sold": {"$sum": "$quantity"}
            }
        },
        {"$sort": {"total_sold": -1}},
        {"$limit": 5}
    ]

    top_products = list(db.sales.aggregate(pipeline))


    return jsonify({
        "sales_overview": sales_by_date,
        "inventory_status": {
            "in_stock": in_stock,
            "low_stock": low_stock,
            "out_stock": out_stock
        },
        "top_products": top_products
    })

@app.route("/api/dashboard/alerts")
def dashboard_alerts():

    products = list(db.products.find())
    alerts = list(db.alerts.find().sort("created_at", -1).limit(5))

    low_stock_products = []

    for p in products:

        stock = p.get("stock_quantity", 0)
        min_stock = p.get("min_stock_level", 5)

        if stock <= min_stock:

            low_stock_products.append({
                "name": p.get("name"),
                "stock": stock,
                "min_stock": min_stock
            })

    notifications = []

    for a in alerts:

        notifications.append({
            "title": a.get("alert_type", "Alert"),
            "message": a.get("message", ""),
            "time": str(a.get("created_at", ""))
        })

    return jsonify({
        "low_stock": low_stock_products,
        "notifications": notifications
    })

@app.route("/api/users", methods=["GET"])
def get_all_users():
    try:
        users = list(collection.find({}))

        formatted_users = []

        for user in users:
            formatted_users.append({
                "_id": str(user["_id"]),
                "username": user.get("username", ""),
                "email": user.get("email", ""),
                "role": user.get("role", "staff"),
                "status": "active",
                "contactNumber": user.get("contactNumber", ""),
                "created_at": user.get("created_at", datetime.datetime.now()),
                "last_login": user.get("lastLogin", {}).get("timestamp")
            })

        return jsonify({"users": formatted_users})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/users/delete/<user_id>", methods=["DELETE"])
def delete_user(user_id):

    from bson import ObjectId

    result = collection.delete_one({"_id": ObjectId(user_id)})

    if result.deleted_count == 1:
        return jsonify({"message": "User deleted"})
    else:
        return jsonify({"error": "User not found"}), 404

@app.route("/api/settings", methods=["GET"])
def get_settings():
    try:
        settings_collection = get_collection("settings")

        settings = settings_collection.find_one()

        if not settings:
            return jsonify({})

        settings["_id"] = str(settings["_id"])
        return jsonify(settings)

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/settings", methods=["POST"])
def update_settings():
    try:
        data = request.get_json()

        print("🔥 RECEIVED DATA:", data)   # 👈 ADD THIS

        settings_collection = get_collection("settings")

        existing = settings_collection.find_one()

        if existing:
            settings_collection.update_one(
                {"_id": existing["_id"]},
                {"$set": data}
            )
        else:
            settings_collection.insert_one(data)

        return jsonify({"message": "Settings updated successfully"})

    except Exception as e:
        print("❌ ERROR:", e)   # 👈 ADD THIS
        return jsonify({"error": str(e)}), 500

@app.route("/api/upload-profile-image", methods=["POST"])
def upload_profile_image():
    file = request.files.get("profileImage")

    if not file:
        return jsonify({"success": False})

    filename = file.filename
    filepath = os.path.join("static/uploads", filename)

    os.makedirs("static/uploads", exist_ok=True)
    file.save(filepath)

    image_url = f"/static/uploads/{filename}"

    users_collection.update_one(
        {"username": session.get("username")},
        {"$set": {"profile_image": image_url}}
    )

    return jsonify({"success": True, "imageUrl": image_url})
 
@app.route("/api/update-profile", methods=["POST"])
def update_profile():
    data = request.get_json()

    users_collection.update_one(
        {"username": session.get("username")},
        {"$set": {
            "full_name": data.get("fullName"),   # ✅ ADD THIS
            "contactNumber": data.get("phone"),
            "role": data.get("role"),
            "department": data.get("department")
        }}
    )

    return jsonify({"message": "Profile updated successfully"})

@app.route("/api/alert-settings", methods=["GET", "POST"])
def alert_settings():
    user = users_collection.find_one({"username": session.get("username")})

    if request.method == "POST":
        data = request.get_json()

        users_collection.update_one(
            {"username": session.get("username")},
            {
                "$set": {
                    "alert_settings": {
                        "low_stock": data.get("lowStockAlerts"),
                        "out_of_stock": data.get("outOfStockAlerts"),
                        "sales": data.get("salesAlerts"),
                        "email": data.get("emailNotifications")
                    }
                }
            }
        )

        return jsonify({"message": "Alert settings saved"})

    else:
        return jsonify(user.get("alert_settings", {}))
    
@app.route("/api/system-settings", methods=["GET", "POST"])
def system_settings():
    user = users_collection.find_one({"username": session.get("username")})

    if request.method == "POST":
        data = request.get_json()

        users_collection.update_one(
            {"username": session.get("username")},
            {
                "$set": {
                    "system_settings": {
                        "currency": data.get("currency"),
                        "timezone": data.get("timezone"),
                        "date_format": data.get("dateFormat"),
                        "language": data.get("language")
                    }
                }
            }
        )

        return jsonify({"message": "System settings saved"})

    else:
        settings = user.get("system_settings", {})
        
        # Ensure default currency is set
        if not settings.get("currency"):
            settings["currency"] = "INR"
            
        return jsonify(settings)
    
# Stock Update API Endpoints
@app.route("/api/stock-updates", methods=["GET"])
def get_stock_updates():
    """Get recent stock updates history"""
    try:
        # Get stock updates from the stock_updates collection
        stock_updates = list(stock_updates_collection.find({}).sort("timestamp", -1).limit(50))
        
        for update in stock_updates:
            update['_id'] = str(update['_id'])
            if 'timestamp' in update and hasattr(update['timestamp'], 'isoformat'):
                update['timestamp'] = update['timestamp'].isoformat()
                
        return jsonify(stock_updates)
    except Exception as e:
        # Fallback: return empty array if collection doesn't exist
        print(f"Error getting stock updates: {e}")
        return jsonify([])

@app.route("/api/stock-update", methods=["POST"])
def create_stock_update():
    """Create a new stock update record and update product stock"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['productId', 'productName', 'updateType', 'quantity', 'previousStock', 'newStock', 'reason']
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Update the product stock in the products collection
        product_id = ObjectId(data['productId'])
        result = products_collection.update_one(
            {"_id": product_id},
            {
                "$set": {
                    "stock_quantity": int(data['newStock']),
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        
        if result.matched_count == 0:
            return jsonify({"error": "Product not found"}), 404
        
        # Create stock update record
        stock_update = {
            "productId": data['productId'],
            "productName": data['productName'],
            "updateType": data['updateType'],
            "quantity": int(data['quantity']),
            "previousStock": int(data['previousStock']),
            "newStock": int(data['newStock']),
            "reason": data['reason'],
            "notes": data.get('notes', ''),
            "updatedBy": data.get('updatedBy', 'Unknown'),
            "timestamp": datetime.datetime.utcnow()
        }
        
        # Insert stock update record with current real time
        current_time = datetime.datetime.utcnow()
        stock_update['timestamp'] = current_time
        stock_updates_collection.insert_one(stock_update)
        
        print(f"Created stock update at: {current_time}")
        print(f"Stock update data: {stock_update}")
        
        # Check if new stock is below threshold and create alert if needed
        updated_product = products_collection.find_one({"_id": product_id})
        if updated_product:
            check_and_create_stock_alert(updated_product)
        
        # Convert ObjectId to string for response
        inserted_update = stock_updates_collection.find_one(stock_update)
        stock_update['_id'] = str(inserted_update['_id'])
        stock_update['timestamp'] = stock_update['timestamp'].isoformat()
        
        return jsonify({
            "message": "Stock updated successfully",
            "stockUpdate": stock_update
        }), 201
        
    except Exception as e:
        print(f"Error creating stock update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/stock-update/<update_id>", methods=["DELETE"])
def delete_stock_update(update_id):
    """Delete a stock update record"""
    try:
        # Convert string ID to ObjectId
        object_id = ObjectId(update_id)
        
        # Delete the stock update record
        result = stock_updates_collection.delete_one({"_id": object_id})
        
        if result.deleted_count > 0:
            return jsonify({"message": "Stock update deleted successfully"}), 200
        else:
            return jsonify({"error": "Stock update not found"}), 404
            
    except Exception as e:
        print(f"Error deleting stock update: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/products/stock-status", methods=["GET"])
def get_products_stock_status():
    """Get products with their current stock status for stock update page"""
    try:
        products = list(products_collection.find({}))
        
        # Format products for stock update dropdown
        formatted_products = []
        for product in products:
            formatted_products.append({
                "_id": str(product['_id']),
                "id": str(product['_id']),
                "name": product.get('name', 'Unknown Product'),
                "stock": product.get('stock_quantity', 0),
                "sku": product.get('sku', ''),
                "category": product.get('category', 'general')
            })
            
        return jsonify(formatted_products)
        
    except Exception as e:
        print(f"Error getting products stock status: {e}")
        return jsonify({"error": str(e)}), 500

# Sales API Endpoint
@app.route("/api/sales", methods=["POST"])
def create_sale():
    """Create a new sale record and update product stock"""
    print("=== SALES API CALLED ===")
    print("Request method:", request.method)
    
    try:
        data = request.get_json()
        print("Received data:", data)
        
        # Validate required fields
        required_fields = ['productId', 'productName', 'quantity', 'unitPrice', 'totalPrice']
        for field in required_fields:
            if field not in data:
                print(f"Missing field: {field}")
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        # Get product from database
        product_id = ObjectId(data['productId'])
        print(f"Looking for product with ID: {product_id}")
        
        product = products_collection.find_one({"_id": product_id})
        print("Product found:", product)
        
        if not product:
            print("Product not found")
            return jsonify({"error": "Product not found"}), 404
        
        # Check stock availability
        current_stock = product.get('stock_quantity', 0)
        sale_quantity = int(data['quantity'])
        print(f"Current stock: {current_stock}, Sale quantity: {sale_quantity}")
        
        if current_stock < sale_quantity:
            print(f"Insufficient stock error")
            return jsonify({"error": f"Insufficient stock. Only {current_stock} units available"}), 400
        
        # Update product stock
        new_stock = current_stock - sale_quantity
        print(f"Updating stock to: {new_stock}")
        
        result = products_collection.update_one(
            {"_id": product_id},
            {
                "$set": {
                    "stock_quantity": new_stock,
                    "updated_at": datetime.datetime.utcnow()
                }
            }
        )
        print(f"Stock update result: {result.matched_count}")
        
        # Create sale record
        sale_record = {
            "productId": data['productId'],
            "productName": data['productName'],
            "quantity": sale_quantity,
            "unitPrice": float(data['unitPrice']),
            "totalPrice": float(data['totalPrice']),
            "customerName": data.get('customerName', 'Walk-in Customer'),
            "paymentMethod": data.get('paymentMethod', 'cash'),
            "notes": data.get('notes', ''),
            "timestamp": datetime.datetime.utcnow(),
            "previousStock": current_stock,
            "newStock": new_stock
        }
        print("Creating sale record:", sale_record)
        
        # Insert sale record
        sales_result = sales_collection.insert_one(sale_record)
        print(f"Sale record inserted: {sales_result.inserted_id}")
        
        # Check if new stock is below threshold and create alert if needed
        updated_product = products_collection.find_one({"_id": product_id})
        if updated_product:
            print("Checking for stock alerts...")
            check_and_create_stock_alert(updated_product)
        
        # Convert ObjectId to string for response
        sale_record['_id'] = str(sales_result.inserted_id)
        sale_record['timestamp'] = sale_record['timestamp'].isoformat()
        
        print("Sale created successfully")
        return jsonify({
            "message": "Sale recorded successfully",
            "sale": sale_record
        }), 201
        
    except Exception as e:
        print(f"Error in create_sale: {e}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/sales", methods=["GET"])
def get_sales():
    """Get recent sales records"""
    try:
        # Get sales from the sales collection
        sales = list(sales_collection.find({}).sort("timestamp", -1).limit(50))
        
        for sale in sales:
            sale['_id'] = str(sale['_id'])
            if 'timestamp' in sale and hasattr(sale['timestamp'], 'isoformat'):
                sale['timestamp'] = sale['timestamp'].isoformat()
                
        return jsonify(sales)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/employee/sales", methods=["GET", "POST"])
def employee_sales():

    # ================= GET =================
    if request.method == "GET":
        try:
            sales = list(employee_sales_collection.find({}))
            
            for sale in sales:
                sale['_id'] = str(sale['_id'])
            
            return jsonify({"sales": sales})

        except Exception as e:
            return jsonify({"error": str(e)}), 500


    # ================= POST =================
    elif request.method == "POST":
        try:
            data = request.get_json()

            sale = {
                "product_id": data.get("product_id"),
                "product_name": data.get("product_name"),
                "quantity": int(data.get("quantity")),
                "unit_price": float(data.get("unit_price")),
                "total_amount": float(data.get("total_amount")),
                "payment_method": data.get("payment_method"),
                "customer_name": data.get("customer_name"),

                # ✅ SAME FORMAT AS YOUR DB
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "created_at": datetime.datetime.now()
            }

            # ✅ UPDATE STOCK (same as admin)
            products_collection.update_one(
                {"_id": ObjectId(data.get("product_id"))},
                {"$inc": {"stock_quantity": -int(data.get("quantity"))}}
            )

            # ✅ INSERT INTO NEW COLLECTION
            result = employee_sales_collection.insert_one(sale)
            sale['_id'] = str(result.inserted_id)

            return jsonify({
                "message": "Employee sale recorded successfully",
                "sale": sale
            }), 201

        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/api/products/download", methods=["GET"])
def download_products():
    try:
        format_type = request.args.get("format", "csv")

        products = list(products_collection.find({}))

        # Convert ObjectId to string
        for p in products:
            p["_id"] = str(p["_id"])

        # ---------- CSV DOWNLOAD ----------
        if format_type == "csv":
            import csv
            from io import StringIO, BytesIO

            output = StringIO()
            writer = csv.writer(output)

            # Headers
            writer.writerow([
                "Product ID", "Name", "Category",
                "Stock", "Min Stock", "Price", "Status"
            ])

            # Data
            for p in products:
                writer.writerow([
                    p.get("product_id", ""),
                    p.get("name", ""),
                    p.get("category", ""),
                    p.get("stock_quantity", 0),
                    p.get("min_stock_level", 10),
                    p.get("price", 0),
                    p.get("stock_status", "")
                ])

            mem = BytesIO()
            mem.write(output.getvalue().encode("utf-8"))
            mem.seek(0)

            return send_file(
                mem,
                mimetype="text/csv",
                as_attachment=True,
                download_name="products.csv"
            )

        # ---------- PDF DOWNLOAD ----------
        elif format_type == "pdf":
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from io import BytesIO

            buffer = BytesIO()
            pdf = canvas.Canvas(buffer, pagesize=letter)

            y = 750
            pdf.setFont("Helvetica-Bold", 14)
            pdf.drawString(50, y, "Products Report")

            y -= 30

            pdf.setFont("Helvetica", 10)

            for p in products:
                line = f"{p.get('name','')} | {p.get('category','')} | Stock: {p.get('stock_quantity',0)} | Price: {p.get('price',0)}"
                pdf.drawString(50, y, line)
                y -= 20

                if y < 100:
                    pdf.showPage()
                    y = 750

            pdf.save()
            buffer.seek(0)

            return send_file(
                buffer,
                as_attachment=True,
                download_name="products.pdf",
                mimetype="application/pdf"
            )

        else:
            return jsonify({"error": "Invalid format"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/employee/sales/today", methods=["GET"])
def get_employee_today_sales():
    try:
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        sales = list(sales_collection.find({
            "date": today
        }))

        for s in sales:
            s["_id"] = str(s["_id"])

        return jsonify({"sales": sales})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/employee/transactions", methods=["GET"])
def get_employee_transactions():
    try:
        sales = list(employee_sales_collection.find().sort("date", -1))

        for s in sales:
            s["_id"] = str(s["_id"])

        return jsonify({"transactions": sales})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/api/employee/transaction-stats", methods=["GET"])
def get_employee_transaction_stats():
    try:
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")

        sales = list(employee_sales_collection.find())

        total_transactions = len(sales)
        total_sales_today = 0
        items_sold_today = 0

        for s in sales:
            if s.get("date") == today:
                total_sales_today += float(s.get("total_amount", 0))
                items_sold_today += int(s.get("quantity", 0))

        avg_sale = total_sales_today / total_transactions if total_transactions > 0 else 0

        return jsonify({
            "total_sales_today": total_sales_today,
            "total_transactions": total_transactions,
            "items_sold_today": items_sold_today,
            "avg_sale": avg_sale
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/employee/transactions/download", methods=["GET"])
def download_employee_transactions():
    try:
        from flask import request, send_file
        from io import StringIO, BytesIO
        import csv
        from reportlab.pdfgen import canvas

        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")
        format_type = request.args.get("format")

        query = {}

        if start_date and end_date:
            query["date"] = {"$gte": start_date, "$lte": end_date}

        sales = list(employee_sales_collection.find(query))

        # ---------- CSV ----------
        if format_type == "csv":
            output = StringIO()
            writer = csv.writer(output)

            writer.writerow(["Date", "Product", "Qty", "Price", "Total", "Payment"])

            for s in sales:
                writer.writerow([
                    s.get("date", ""),
                    s.get("product_name", ""),
                    s.get("quantity", 0),
                    s.get("unit_price", 0),
                    s.get("total_amount", 0),
                    s.get("payment_method", "")
                ])

            mem = BytesIO()
            mem.write(output.getvalue().encode('utf-8'))
            mem.seek(0)

            return send_file(mem, mimetype='text/csv',
                             as_attachment=True,
                             download_name="transactions.csv")

        # ---------- PDF ----------
        elif format_type == "pdf":
            buffer = BytesIO()
            pdf = canvas.Canvas(buffer)

            y = 800
            pdf.setFont("Helvetica", 10)

            pdf.drawString(30, y, "Employee Transactions Report")
            y -= 30

            for s in sales:
                line = f"{s.get('date')} | {s.get('product_name')} | {s.get('quantity')} | ₹{s.get('total_amount')}"
                pdf.drawString(30, y, line)
                y -= 20

                if y < 50:
                    pdf.showPage()
                    y = 800

            pdf.save()
            buffer.seek(0)

            return send_file(buffer,
                             as_attachment=True,
                             download_name="transactions.pdf",
                             mimetype='application/pdf')

        else:
            return jsonify({"error": "Invalid format"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/employee/profile", methods=["GET"])
def get_employee_profile():
    try:
        if 'user_email' not in session:
            return jsonify({"error": "Not logged in"}), 401

        user = collection.find_one({"email": session['user_email']})

        if not user:
            return jsonify({"error": "User not found"}), 404

        # ✅ IMPORTANT LOGIC
        full_name = user.get("full_name") or user.get("username")

        return jsonify({
            "username": user.get("username"),
            "full_name": full_name,
            "email": user.get("email"),
            "phone": user.get("contactNumber"),
            "address": user.get("shopAddress"),
            "department": user.get("department"),
            "role": user.get("role"),
            "profile_image": user.get("profile_image", "/static/uploads/default.png")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
       
@app.route("/api/employee/profile/update", methods=["PUT"])
def update_employee_profile():
    try:
        if 'user_email' not in session:
            return jsonify({"error": "Not logged in"}), 401

        data = request.get_json()

        # ❌ Do NOT allow username, email, role
        update_data = {
            "full_name": data.get("full_name"),
            "contactNumber": data.get("phone"),
            "shopAddress": data.get("address"),
            "department": data.get("department")
        }

        collection.update_one(
            {"email": session['user_email']},
            {"$set": update_data}
        )

        return jsonify({"message": "Profile updated successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/employee/upload-profile", methods=["POST"])
def upload_employee_profile_image():
    try:
        if 'user_email' not in session:
            return jsonify({"error": "Not logged in"}), 401

        file = request.files.get("image")

        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        filename = str(int(time.time())) + "_" + file.filename
        filepath = os.path.join("static/uploads", filename)
        file.save(filepath)

        image_path = f"/static/uploads/{filename}"

        collection.update_one(
            {"email": session['user_email']},
            {"$set": {"profile_image": image_path}}
        )

        return jsonify({"image_url": image_path})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
