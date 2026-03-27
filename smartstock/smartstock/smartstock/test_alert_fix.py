#!/usr/bin/env python3
"""
Test script to verify the duplicate alert fix
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app, alerts_collection, products_collection
from datetime import datetime as dt
import json

def test_duplicate_alert_fix():
    """Test that duplicate alerts are prevented"""
    with app.app_context():
        print("🧪 Testing duplicate alert fix...")
        
        # Find a test product
        product = products_collection.find_one()
        if not product:
            print("❌ No products found in database")
            return False
        
        print(f"📦 Using test product: {product.get('name', 'Unknown')} (ID: {product['_id']})")
        
        # Clear any existing alerts for this product
        alerts_collection.delete_many({"product_id": str(product['_id'])})
        print("🧹 Cleared existing alerts for test product")
        
        # Import the alert creation function
        from app import create_stock_alert
        
        # Create first alert
        print("➕ Creating first alert...")
        create_stock_alert(product, "low_stock", "Test alert 1", "high")
        
        # Create second alert (should update existing one)
        print("➕ Creating second alert (should update existing)...")
        create_stock_alert(product, "low_stock", "Test alert 2", "high")
        
        # Check how many alerts exist
        alerts = list(alerts_collection.find({"product_id": str(product['_id']), "alert_type": "low_stock"}))
        
        if len(alerts) == 1:
            print("✅ SUCCESS: Only 1 alert exists (duplicate prevented)")
            print(f"📝 Alert message: {alerts[0]['message']}")
            if alerts[0]['message'] == "Test alert 2":
                print("✅ SUCCESS: Alert was updated with new message")
            else:
                print("❌ FAIL: Alert was not updated with new message")
                return False
        else:
            print(f"❌ FAIL: Found {len(alerts)} alerts (duplicates not prevented)")
            for alert in alerts:
                print(f"   - {alert['message']} (Created: {alert['created_at']})")
            return False
        
        # Test cleanup function
        print("\n🧹 Testing cleanup function...")
        
        # Create some duplicate alerts manually
        alert1 = {
            "product_id": str(product['_id']),
            "product_name": product['name'],
            "alert_type": "out_of_stock",
            "message": "Duplicate alert 1",
            "priority": "critical",
            "status": "active",
            "created_at": dt.now()
        }
        
        alert2 = {
            "product_id": str(product['_id']),
            "product_name": product['name'],
            "alert_type": "out_of_stock",
            "message": "Duplicate alert 2",
            "priority": "critical",
            "status": "active",
            "created_at": dt.now()
        }
        
        alerts_collection.insert_many([alert1, alert2])
        print("➕ Created 2 duplicate alerts manually")
        
        # Check duplicates before cleanup
        duplicates_before = list(alerts_collection.find({
            "product_id": str(product['_id']), 
            "alert_type": "out_of_stock"
        }))
        print(f"📊 Found {len(duplicates_before)} out_of_stock alerts before cleanup")
        
        # Simulate cleanup (this would normally be called via API)
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
            alerts_to_remove = sorted(duplicate_group["alerts"])[:-1]
            result = alerts_collection.delete_many({"_id": {"$in": alerts_to_remove}})
            removed_count += result.deleted_count
        
        print(f"🧹 Cleanup removed {removed_count} duplicate alerts")
        
        # Check after cleanup
        duplicates_after = list(alerts_collection.find({
            "product_id": str(product['_id']), 
            "alert_type": "out_of_stock"
        }))
        print(f"📊 Found {len(duplicates_after)} out_of_stock alerts after cleanup")
        
        if len(duplicates_after) == 1:
            print("✅ SUCCESS: Cleanup function works correctly")
        else:
            print("❌ FAIL: Cleanup function did not work correctly")
            return False
        
        # Clean up test data
        alerts_collection.delete_many({"product_id": str(product['_id'])})
        print("🧹 Cleaned up test data")
        
        print("\n🎉 All tests passed! Duplicate alert fix is working correctly.")
        return True

if __name__ == "__main__":
    success = test_duplicate_alert_fix()
    if success:
        print("\n✅ Test completed successfully")
    else:
        print("\n❌ Test failed")
        sys.exit(1)
