import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import 'auth_http.dart';

class DeviceService {
  static final String _baseUrl = AppConfig.baseUrl;

  Future<void> registerDeviceToken({
    required String token,
    String? platform,
  }) async {
    final response = await AuthHttp.postJson(
      Uri.parse('$_baseUrl/register-device'),
      {
        'device_token': token,
        'platform': platform,
      },
    ).timeout(
      const Duration(seconds: 10),
      onTimeout: () => http.Response('', 408),
    );

    if (response.statusCode != 200) {
      final detail = _parseDetail(response.body);
      throw Exception(
        detail ??
            'Failed to register device: ${response.statusCode}',
      );
    }
  }

  static String? _parseDetail(String body) {
    try {
      final map = jsonDecode(body);
      if (map is Map && map['detail'] != null) {
        return map['detail'].toString();
      }
    } catch (_) {}
    return null;
  }
}
