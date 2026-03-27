"""
SmartStock Alert Management System
Handles stock alerts, notifications, and alert processing
"""

import datetime
import json
from bson import ObjectId
from pymongo.errors import ConnectionFailure, OperationFailure
from flask import jsonify
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class AlertManager:
    """Manages stock alerts and notifications"""
    
    def __init__(self, db_connection):
        self.db = db_connection
        self.alerts_collection = self.db["alerts"]
        self.products_collection = self.db["products"]
        self.users_collection = self.db["users"]
        
        # Alert configuration
        self.alert_thresholds = {
            "critical": 5,
            "low": 20,
            "moderate": 50
        }
        
        # Alert priorities
        self.priorities = {
            "critical": "high",
            "low": "medium", 
            "moderate": "low"
        }
    
    def check_stock_levels(self, product_id=None):
        """Check stock levels and generate alerts"""
        try:
            alerts_created = []
            
            if product_id:
                products = [self.products_collection.find_one({"_id": ObjectId(product_id)})]
            else:
                products = list(self.products_collection.find({"stock_quantity": {"$gt": 0}}))
            
            for product in products:
                if not product:
                    continue
                    
                alert = self._evaluate_stock_level(product)
                if alert:
                    self._create_alert(alert)
                    alerts_created.append(alert)
            
            return alerts_created
            
        except Exception as e:
            print(f"Error checking stock levels: {str(e)}")
            return []
    
    def _evaluate_stock_level(self, product):
        """Evaluate product stock level and determine if alert is needed"""
        try:
            stock_qty = product.get('stock_quantity', 0)
            product_name = product.get('name', 'Unknown Product')
            product_id = str(product['_id'])
            
            # Check for critical stock
            if stock_qty <= self.alert_thresholds["critical"]:
                return {
                    "product_id": product_id,
                    "product_name": product_name,
                    "alert_type": "critical",
                    "message": f"CRITICAL: {product_name} stock is critically low ({stock_qty} units)",
                    "stock_quantity": stock_qty,
                    "priority": self.priorities["critical"],
                    "threshold": self.alert_thresholds["critical"]
                }
            
            # Check for low stock
            elif stock_qty <= self.alert_thresholds["low"]:
                return {
                    "product_id": product_id,
                    "product_name": product_name,
                    "alert_type": "low",
                    "message": f"LOW STOCK: {product_name} stock is low ({stock_qty} units)",
                    "stock_quantity": stock_qty,
                    "priority": self.priorities["low"],
                    "threshold": self.alert_thresholds["low"]
                }
            
            # Check for moderate stock
            elif stock_qty <= self.alert_thresholds["moderate"]:
                return {
                    "product_id": product_id,
                    "product_name": product_name,
                    "alert_type": "moderate",
                    "message": f"MODERATE: {product_name} stock is moderate ({stock_qty} units)",
                    "stock_quantity": stock_qty,
                    "priority": self.priorities["moderate"],
                    "threshold": self.alert_thresholds["moderate"]
                }
            
            return None
            
        except Exception as e:
            print(f"Error evaluating stock level: {str(e)}")
            return None
    
    def _create_alert(self, alert_data):
        """Create a new alert in the database"""
        try:
            # Check if similar alert already exists
            existing_alert = self.alerts_collection.find_one({
                "product_id": alert_data["product_id"],
                "alert_type": alert_data["alert_type"],
                "status": "active"
            })
            
            if existing_alert:
                # Update existing alert
                self.alerts_collection.update_one(
                    {"_id": existing_alert["_id"]},
                    {
                        "$set": {
                            "message": alert_data["message"],
                            "stock_quantity": alert_data["stock_quantity"],
                            "updated_at": datetime.datetime.now()
                        }
                    }
                )
                return existing_alert["_id"]
            else:
                # Create new alert
                alert_document = {
                    "product_id": alert_data["product_id"],
                    "product_name": alert_data["product_name"],
                    "alert_type": alert_data["alert_type"],
                    "message": alert_data["message"],
                    "stock_quantity": alert_data["stock_quantity"],
                    "priority": alert_data["priority"],
                    "threshold": alert_data.get("threshold", 0),
                    "status": "active",
                    "created_at": datetime.datetime.now(),
                    "updated_at": datetime.datetime.now()
                }
                
                result = self.alerts_collection.insert_one(alert_document)
                return result.inserted_id
                
        except Exception as e:
            print(f"Error creating alert: {str(e)}")
            return None
    
    def get_alerts(self, status="active", limit=50, skip=0):
        """Get alerts with optional filtering"""
        try:
            query = {}
            if status and status != "all":
                query["status"] = status
            
            alerts = list(self.alerts_collection.find(query)
                         .sort("created_at", -1)
                         .skip(skip)
                         .limit(limit))
            
            # Convert ObjectId to string for JSON serialization
            for alert in alerts:
                alert["_id"] = str(alert["_id"])
                if "created_at" in alert:
                    alert["created_at"] = alert["created_at"].isoformat()
                if "updated_at" in alert:
                    alert["updated_at"] = alert["updated_at"].isoformat()
            
            return alerts
            
        except Exception as e:
            print(f"Error getting alerts: {str(e)}")
            return []
    
    def acknowledge_alert(self, alert_id):
        """Acknowledge an alert"""
        try:
            result = self.alerts_collection.update_one(
                {"_id": ObjectId(alert_id)},
                {
                    "$set": {
                        "status": "acknowledged",
                        "acknowledged_at": datetime.datetime.now(),
                        "updated_at": datetime.datetime.now()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error acknowledging alert: {str(e)}")
            return False
    
    def resolve_alert(self, alert_id):
        """Resolve an alert"""
        try:
            result = self.alerts_collection.update_one(
                {"_id": ObjectId(alert_id)},
                {
                    "$set": {
                        "status": "resolved",
                        "resolved_at": datetime.datetime.now(),
                        "updated_at": datetime.datetime.now()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error resolving alert: {str(e)}")
            return False
    
    def dismiss_alert(self, alert_id):
        """Dismiss an alert"""
        try:
            result = self.alerts_collection.update_one(
                {"_id": ObjectId(alert_id)},
                {
                    "$set": {
                        "status": "dismissed",
                        "dismissed_at": datetime.datetime.now(),
                        "updated_at": datetime.datetime.now()
                    }
                }
            )
            
            return result.modified_count > 0
            
        except Exception as e:
            print(f"Error dismissing alert: {str(e)}")
            return False
    
    def delete_alert(self, alert_id):
        """Delete an alert"""
        try:
            result = self.alerts_collection.delete_one({"_id": ObjectId(alert_id)})
            return result.deleted_count > 0
            
        except Exception as e:
            print(f"Error deleting alert: {str(e)}")
            return False
    
    def clear_all_alerts(self):
        """Clear all alerts"""
        try:
            result = self.alerts_collection.delete_many({})
            return result.deleted_count
            
        except Exception as e:
            print(f"Error clearing alerts: {str(e)}")
            return 0
    
    def cleanup_duplicate_alerts(self):
        """Remove duplicate alerts for the same product and alert type"""
        try:
            # Find all active alerts grouped by product_id and alert_type
            pipeline = [
                {"$match": {"status": "active"}},
                {"$group": {
                    "_id": {"product_id": "$product_id", "alert_type": "$alert_type"},
                    "count": {"$sum": 1},
                    "latest": {"$max": "$created_at"}
                }},
                {"$match": {"count": {"$gt": 1}}}
            ]
            
            duplicates = list(self.alerts_collection.aggregate(pipeline))
            removed_count = 0
            
            for duplicate in duplicates:
                # Keep only the latest alert, remove others
                product_id = duplicate["_id"]["product_id"]
                alert_type = duplicate["_id"]["alert_type"]
                latest_time = duplicate["latest"]
                
                # Remove all except the latest
                result = self.alerts_collection.delete_many({
                    "product_id": product_id,
                    "alert_type": alert_type,
                    "status": "active",
                    "created_at": {"$ne": latest_time}
                })
                
                removed_count += result.deleted_count
            
            return removed_count
            
        except Exception as e:
            print(f"Error cleaning up duplicates: {str(e)}")
            return 0
    
    def get_alert_statistics(self):
        """Get alert statistics"""
        try:
            stats = {}
            
            # Count by status
            status_pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]
            status_counts = list(self.alerts_collection.aggregate(status_pipeline))
            stats["by_status"] = {item["_id"]: item["count"] for item in status_counts}
            
            # Count by priority
            priority_pipeline = [
                {"$group": {"_id": "$priority", "count": {"$sum": 1}}}
            ]
            priority_counts = list(self.alerts_collection.aggregate(priority_pipeline))
            stats["by_priority"] = {item["_id"]: item["count"] for item in priority_counts}
            
            # Count by alert type
            type_pipeline = [
                {"$group": {"_id": "$alert_type", "count": {"$sum": 1}}}
            ]
            type_counts = list(self.alerts_collection.aggregate(type_pipeline))
            stats["by_type"] = {item["_id"]: item["count"] for item in type_counts}
            
            # Total counts
            stats["total"] = self.alerts_collection.count_documents({})
            stats["active"] = self.alerts_collection.count_documents({"status": "active"})
            
            return stats
            
        except Exception as e:
            print(f"Error getting alert statistics: {str(e)}")
            return {}
    
    def send_email_notification(self, alert_data, recipient_emails):
        """Send email notification for alert"""
        try:
            if not recipient_emails:
                return False
            
            # Email configuration (you should configure these properly)
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            smtp_username = "your-email@gmail.com"
            smtp_password = "your-app-password"
            
            # Create message
            msg = MIMEMultipart()
            msg['From'] = smtp_username
            msg['To'] = ', '.join(recipient_emails)
            msg['Subject'] = f"SmartStock Alert: {alert_data.get('alert_type', '').upper()}"
            
            # Email body
            body = f"""
            <html>
            <body>
                <h2>SmartStock Inventory Alert</h2>
                <p><strong>Product:</strong> {alert_data.get('product_name', 'Unknown')}</p>
                <p><strong>Alert Type:</strong> {alert_data.get('alert_type', '').upper()}</p>
                <p><strong>Priority:</strong> {alert_data.get('priority', '').upper()}</p>
                <p><strong>Current Stock:</strong> {alert_data.get('stock_quantity', 0)} units</p>
                <p><strong>Message:</strong> {alert_data.get('message', '')}</p>
                <p><strong>Time:</strong> {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <hr>
                <p><small>Please check your SmartStock dashboard for more details.</small></p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(body, 'html'))
            
            # Send email
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
            server.quit()
            
            return True
            
        except Exception as e:
            print(f"Error sending email notification: {str(e)}")
            return False


# Utility functions for Flask routes
def create_alert_manager(db_connection):
    """Create and return an AlertManager instance"""
    return AlertManager(db_connection)


def format_alert_for_response(alert):
    """Format alert document for API response"""
    if not alert:
        return None
    
    formatted = dict(alert)
    if "_id" in formatted:
        formatted["_id"] = str(formatted["_id"])
    if "created_at" in formatted and hasattr(formatted["created_at"], 'isoformat'):
        formatted["created_at"] = formatted["created_at"].isoformat()
    if "updated_at" in formatted and hasattr(formatted["updated_at"], 'isoformat'):
        formatted["updated_at"] = formatted["updated_at"].isoformat()
    
    return formatted


def validate_alert_data(alert_data):
    """Validate alert data structure"""
    required_fields = ["product_id", "product_name", "alert_type", "message"]
    
    for field in required_fields:
        if field not in alert_data:
            return False, f"Missing required field: {field}"
    
    # Validate alert type
    valid_types = ["critical", "low", "moderate"]
    if alert_data["alert_type"] not in valid_types:
        return False, f"Invalid alert type: {alert_data['alert_type']}"
    
    # Validate priority
    valid_priorities = ["high", "medium", "low"]
    if "priority" in alert_data and alert_data["priority"] not in valid_priorities:
        return False, f"Invalid priority: {alert_data['priority']}"
    
    return True, "Valid"
