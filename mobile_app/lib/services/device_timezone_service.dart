import 'package:flutter/foundation.dart' show debugPrint, kIsWeb;
import 'package:flutter_timezone/flutter_timezone.dart';

import 'profile_service.dart';

/// Keeps server user timezone in sync with the device clock (travel-safe reminders).
class DeviceTimezoneService {
  DeviceTimezoneService._();

  static final ProfileService _profileService = ProfileService();

  /// Returns true if the server timezone was updated.
  static Future<bool> syncIfNeeded(String? profileTimezone) async {
    if (kIsWeb) return false;
    try {
      final deviceTz = await FlutterTimezone.getLocalTimezone();
      if (deviceTz.isEmpty) return false;
      if (profileTimezone != null &&
          profileTimezone.trim().isNotEmpty &&
          profileTimezone == deviceTz) {
        return false;
      }
      await _profileService.updateTimezone(deviceTz);
      debugPrint('Device timezone synced to server: $deviceTz');
      return true;
    } catch (e) {
      debugPrint('Device timezone sync skipped: $e');
      return false;
    }
  }
}
