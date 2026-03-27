#!/usr/bin/env python3
"""
Quick Fix for Product Price Error
"""

import sys
sys.path.append('.')

from app import get_collection
from bson import ObjectId

def quick_fix_price_error():
    """Quick fix for undefined price values in products"""
    print("🚀 Quick Fix: Product Price Error")
    
    try:
        products_collection = get_collection("products")
        if products_collection is None:
            print("❌ Cannot access products collection")
            return False
        
        # Find products with null/undefined prices
        products_with_price_issues = list(products_collection.find({
            "$or": [
                {"price": None},
                {"price": {"$exists": False}}
            ]
        }))
        
        print(f"📊 Found {len(products_with_price_issues)} products with price issues")
        
        fixed_count = 0
        for product in products_with_price_issues:
            product_id = str(product['_id'])
            product_name = product.get('name', 'Unknown')
            
            print(f"🔧 Fixing product: {product_name} (ID: {product_id})")
            
            # Set a default price
            result = products_collection.update_one(
                {"_id": ObjectId(product_id)},
                {"$set": {"price": 0.00}}
            )
            
            if result.modified_count > 0:
                fixed_count += 1
                print(f"✅ Fixed price for product: {product_name}")
            else:
                print(f"⚠️ No changes needed for product: {product_name}")
        
        print(f"\n📋 Quick Fix Summary:")
        print(f"   🔧 Products checked: {len(products_with_price_issues)}")
        print(f"   ✅ Products fixed: {fixed_count}")
        
        if fixed_count > 0:
            print(f"\n🎉 Successfully fixed {fixed_count} products!")
            print("\n📋 Next Steps:")
            print("   1. Refresh browser (Ctrl+F5)")
            print("   2. Go to /products page")
            print("   3. Products should now display without errors")
        else:
            print("\n✅ No price issues found - all products have valid prices")
        
        return fixed_count > 0
        
    except Exception as e:
        print(f"❌ Error during quick fix: {str(e)}")
        return False

def verify_fix():
    """Verify the fix worked"""
    print("\n🔍 Verifying fix...")
    
    try:
        products_collection = get_collection("products")
        if products_collection is None:
            print("❌ Cannot access products collection")
            return False
        
        # Check for any remaining price issues
        remaining_issues = list(products_collection.find({
            "$or": [
                {"price": None},
                {"price": {"$exists": False}}
            ]
        }))
        
        if len(remaining_issues) == 0:
            print("✅ Verification successful - no price issues remain")
            return True
        else:
            print(f"⚠️ {len(remaining_issues)} products still have price issues")
            for product in remaining_issues:
                print(f"   - {product.get('name', 'Unknown')} (ID: {str(product['_id'])})")
            return False
            
    except Exception as e:
        print(f"❌ Error during verification: {str(e)}")
        return False

def main():
    """Main function"""
    print("=" * 50)
    
    # Step 1: Fix price issues
    fix_success = quick_fix_price_error()
    
    # Step 2: Verify fix
    if fix_success:
        verify_fix()
    
    print("\n" + "=" * 50)
    print("🏁 Quick Fix Complete!")
    
    if fix_success:
        print("\n🎯 The frontend should now work without the 'toFixed' error!")
        print("📋 Refresh your browser and test the products page")
    else:
        print("\n⚠️ Fix failed - check error messages above")

if __name__ == "__main__":
    main()
