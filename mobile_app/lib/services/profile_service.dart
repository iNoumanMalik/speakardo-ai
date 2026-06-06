import 'dart:convert';

import '../config/app_config.dart';
import '../models/user_profile.dart';
import 'auth_http.dart';

class ProfileService {
  static final String _baseUrl = AppConfig.baseUrl;

  Future<UserProfile> fetchProfile() async {
    final response = await AuthHttp.get(Uri.parse('$_baseUrl/users/me'));

    if (response.statusCode != 200) {
      throw Exception('Failed to load profile');
    }

    return UserProfile.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<UserProfile> updateTimezone(String timezone) async {
    final response = await AuthHttp.patchJson(
      Uri.parse('$_baseUrl/users/me/timezone'),
      {'timezone': timezone},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update timezone');
    }

    return UserProfile.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }

  Future<UserProfile> updatePreferences({
    String? timezone,
    bool? notificationsEnabled,
  }) async {
    final body = <String, dynamic>{};
    if (timezone != null) {
      body['timezone'] = timezone;
    }
    if (notificationsEnabled != null) {
      body['notifications_enabled'] = notificationsEnabled;
    }

    final response = await AuthHttp.patchJson(
      Uri.parse('$_baseUrl/users/me/preferences'),
      body,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update preferences');
    }

    return UserProfile.fromJson(
      jsonDecode(response.body) as Map<String, dynamic>,
    );
  }
}
