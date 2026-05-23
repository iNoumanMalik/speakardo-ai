import 'package:shared_preferences/shared_preferences.dart';

class OnboardingStorage {
  OnboardingStorage._();

  static const _keyComplete = 'onboarding_complete';

  static Future<bool> isComplete() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_keyComplete) ?? false;
  }

  static Future<void> markComplete() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_keyComplete, true);
  }
}
