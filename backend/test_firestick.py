"""
Test script for Firestick Controller
Tests all Firestick control functions
"""

import time
from firestick_controller import firestick_controller, execute_firestick_command


def test_connection():
    """Test connection to Firestick"""
    print("\n" + "="*60)
    print("TEST 1: Firestick Connection")
    print("="*60)

    if firestick_controller.connect():
        print("✅ PASS: Connected to Firestick successfully")
        return True
    else:
        print("❌ FAIL: Could not connect to Firestick")
        print("\nTroubleshooting:")
        print(f"1. Check Firestick IP: {firestick_controller.firestick_ip}")
        print("2. Enable ADB Debugging on Firestick:")
        print("   Settings → My Fire TV → Developer Options → ADB Debugging")
        print("3. Ensure Firestick is on same network")
        print("4. Install ADB on your system:")
        print("   - Windows: Download ADB platform tools")
        print("   - Linux: sudo apt install adb")
        return False


def test_navigation():
    """Test navigation controls"""
    print("\n" + "="*60)
    print("TEST 2: Navigation Controls")
    print("="*60)

    tests = [
        ("home", "Go to home screen"),
        ("back", "Go back"),
        ("select", "Select/Enter"),
    ]

    passed = 0
    for command, description in tests:
        print(f"\nTesting: {description}")
        if execute_firestick_command(command):
            print(f"✅ PASS: {command}")
            passed += 1
        else:
            print(f"❌ FAIL: {command}")
        time.sleep(1)

    print(f"\nNavigation: {passed}/{len(tests)} tests passed")
    return passed == len(tests)


def test_playback():
    """Test playback controls"""
    print("\n" + "="*60)
    print("TEST 3: Playback Controls")
    print("="*60)

    tests = [
        ("play", "Play"),
        ("pause", "Pause"),
        ("play_pause", "Toggle play/pause"),
    ]

    passed = 0
    for command, description in tests:
        print(f"\nTesting: {description}")
        if execute_firestick_command(command):
            print(f"✅ PASS: {command}")
            passed += 1
        else:
            print(f"❌ FAIL: {command}")
        time.sleep(1)

    print(f"\nPlayback: {passed}/{len(tests)} tests passed")
    return passed == len(tests)


def test_apps():
    """Test app launching"""
    print("\n" + "="*60)
    print("TEST 4: App Launching")
    print("="*60)

    tests = [
        ("netflix", "Launch Netflix"),
        ("youtube", "Launch YouTube"),
        ("prime", "Launch Prime Video"),
    ]

    passed = 0
    for command, description in tests:
        print(f"\nTesting: {description}")
        if execute_firestick_command(command):
            print(f"✅ PASS: {command}")
            passed += 1
            time.sleep(3)  # Give app time to launch
            firestick_controller.home()  # Return to home
            time.sleep(1)
        else:
            print(f"❌ FAIL: {command}")

    print(f"\nApps: {passed}/{len(tests)} tests passed")
    return passed == len(tests)


def test_volume():
    """Test volume controls"""
    print("\n" + "="*60)
    print("TEST 5: Volume Controls")
    print("="*60)

    tests = [
        ("volume_up", "Volume up"),
        ("volume_down", "Volume down"),
    ]

    passed = 0
    for command, description in tests:
        print(f"\nTesting: {description}")
        if execute_firestick_command(command):
            print(f"✅ PASS: {command}")
            passed += 1
        else:
            print(f"❌ FAIL: {command}")
        time.sleep(0.5)

    print(f"\nVolume: {passed}/{len(tests)} tests passed")
    return passed == len(tests)


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("🎬 FIRESTICK CONTROLLER TEST SUITE")
    print("="*60)

    # Test connection first
    if not test_connection():
        print("\n❌ Connection failed. Cannot proceed with other tests.")
        return

    # Run all tests
    results = []
    results.append(("Navigation", test_navigation()))
    results.append(("Playback", test_playback()))
    results.append(("Apps", test_apps()))
    results.append(("Volume", test_volume()))

    # Disconnect
    firestick_controller.disconnect()

    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)

    total_passed = sum(1 for _, passed in results if passed)
    total_tests = len(results)

    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nTotal: {total_passed}/{total_tests} test suites passed")

    if total_passed == total_tests:
        print("\n🎉 ALL TESTS PASSED! Firestick control is working perfectly!")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    run_all_tests()
