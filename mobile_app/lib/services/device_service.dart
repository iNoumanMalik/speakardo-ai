import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';

class DeviceService {
  static final String _baseUrl = AppConfig.baseUrl;

  Future<void> registerDeviceToken({
    required String token,
    String? userId,
    String? platform,
  }) async {
    final response = await http.post(
      Uri.parse('$_baseUrl/register-device'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'user_id': userId,
        'device_token': token,
        'platform': platform,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to register device: ${response.statusCode}');
    }
  }
}
