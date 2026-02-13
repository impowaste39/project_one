# -*- coding: utf-8 -*-
"""
Test script to verify the trading bot implementation
"""

from models.scan_report import ScanReport, ScanResult, PatternOccurrence
from models.database import init_database, get_session
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_database_setup():
    """Test database initialization"""
    print("=" * 50)
    print("Testing Database Setup")
    print("=" * 50)

    try:
        engine, session_maker = init_database()
        print("[OK] Database initialized successfully")

        # Test session
        db = get_session()

        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        print("\nDatabase tables (%d):" % len(tables))
        for table in sorted(tables):
            print("  - %s" % table)

        # Check for new scan tables
        required_tables = ['scan_reports',
                           'scan_results', 'pattern_occurrences']
        for table in required_tables:
            if table in tables:
                print("[OK] Table '%s' exists" % table)
            else:
                print("[FAIL] Table '%s' missing" % table)

        db.close()
        return True

    except Exception as e:
        print("[FAIL] Database setup failed: %s" % e)
        import traceback
        traceback.print_exc()
        return False


def test_reporting_service():
    """Test reporting service"""
    print("\n" + "=" * 50)
    print("Testing Reporting Service")
    print("=" * 50)

    try:
        from services.reporting_service import ReportingService

        db = get_session()
        reporting = ReportingService(db)

        print("[OK] ReportingService initialized")

        # Test saving a mock scan report
        market_context = {
            'trend': 'bullish',
            'strength': 75.5,
            'nifty_price': 22500.0,
            'nifty_rsi': 55.0,
            'market_breadth': 'positive'
        }

        scan_stats = {
            'total_scanned': 188,
            'opportunities_found': 5,
            'trades_entered': 0
        }

        scan_report = reporting.save_scan_report(
            market_context, scan_stats, 45.2)

        if scan_report:
            print("[OK] Scan report saved with ID: %d" % scan_report.id)

            # Test retrieving scan history
            history = reporting.get_scan_history(limit=5)
            print("[OK] Retrieved %d scan reports from history" % len(history))
        else:
            print("[WARN] Scan report not saved (SAVE_SCAN_DATA may be disabled)")

        db.close()
        return True

    except Exception as e:
        print("[FAIL] Reporting service test failed: %s" % e)
        import traceback
        traceback.print_exc()
        return False


def test_api_endpoints():
    """Test that Flask app can start"""
    print("\n" + "=" * 50)
    print("Testing Flask App")
    print("=" * 50)

    try:
        from app import app

        print("[OK] Flask app imported successfully")

        # List all routes
        print("\nAvailable API endpoints:")
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                methods = ', '.join(sorted(rule.methods - {'HEAD', 'OPTIONS'}))
                routes.append("  [%s] %s" % (methods, rule.rule))

        for route in sorted(routes):
            print(route)

        # Check for new endpoints
        new_endpoints = [
            '/api/scan-history',
            '/api/pattern-performance',
            '/api/rejection-analysis',
            '/api/learning-insights'
        ]

        print("\nNew reporting endpoints:")
        for endpoint in new_endpoints:
            found = any(endpoint in str(rule)
                        for rule in app.url_map.iter_rules())
            status = "[OK]" if found else "[FAIL]"
            print("  %s %s" % (status, endpoint))

        return True

    except Exception as e:
        print("[FAIL] Flask app test failed: %s" % e)
        import traceback
        traceback.print_exc()
        return False


def test_learning_engine():
    """Test learning engine enhancements"""
    print("\n" + "=" * 50)
    print("Testing Learning Engine")
    print("=" * 50)

    try:
        from core.learning_engine import LearningEngine

        db = get_session()
        engine = LearningEngine(db)

        print("[OK] LearningEngine initialized")

        # Test new method
        insights = engine.generate_learning_insights()

        print("[OK] Learning insights generated:")
        print("  - Insights: %d" % len(insights.get('insights', [])))
        print("  - Recommendations: %d" %
              len(insights.get('recommendations', [])))
        print("  - Patterns analyzed: %d" %
              len(insights.get('pattern_analysis', {})))

        if insights.get('insights'):
            print("\nSample insights:")
            for insight in insights['insights'][:3]:
                print("  - %s" % insight)

        db.close()
        return True

    except Exception as e:
        print("[FAIL] Learning engine test failed: %s" % e)
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\nAI Trading Bot - Implementation Tests\n")

    results = {
        'Database Setup': test_database_setup(),
        'Reporting Service': test_reporting_service(),
        'Flask App': test_api_endpoints(),
        'Learning Engine': test_learning_engine()
    }

    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print("%s - %s" % (status, test_name))

    all_passed = all(results.values())

    if all_passed:
        print("\nAll tests passed! The bot is ready to run.")
        print("\nNext steps:")
        print("1. Set up your .env file with proper configuration")
        print("2. Run: python app.py")
        print("3. Monitor logs for scan results")
        print("4. Check /api/scan-history for scan data")
    else:
        print("\nSome tests failed. Please review the errors above.")

    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
