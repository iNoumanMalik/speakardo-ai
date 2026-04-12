import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config/app_config.dart';
import 'auth_storage.dart';

class AuthService {
  AuthService._();

  static final String _base = AppConfig.baseUrl;

  /// Returns `true` if new tokens were stored.
  static Future<bool> tryRefresh() async {
    final refresh = await AuthStorage.readRefreshToken();
    if (refresh == null || refresh.isEmpty) {
      await AuthStorage.clear();
      return false;
    }
    final response = await http
        .post(
          Uri.parse('$_base/auth/refresh'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'refresh_token': refresh}),
        )
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => http.Response('', 408),
        );

    if (response.statusCode != 200) {
      await AuthStorage.clear();
      return false;
    }
    final map = jsonDecode(response.body) as Map<String, dynamic>;
    final access = map['access_token'] as String?;
    final nextRefresh = map['refresh_token'] as String?;
    if (access == null ||
        access.isEmpty ||
        nextRefresh == null ||
        nextRefresh.isEmpty) {
      await AuthStorage.clear();
      return false;
    }
    await AuthStorage.saveTokens(
      accessToken: access,
      refreshToken: nextRefresh,
    );
    return true;
  }

  static Future<String?> register(String email, String password) async {
    final response = await http
        .post(
          Uri.parse('$_base/auth/register'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'email': email.trim(), 'password': password}),
        )
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => http.Response('', 408),
        );

    if (response.statusCode == 200) {
      await _storeTokensFromBody(response.body);
      return null;
    }
    if (response.statusCode == 409) {
      return 'That email is already registered.';
    }
    if (response.statusCode == 429) {
      return 'Too many attempts. Try again in a minute.';
    }
    return _errorMessage(response);
  }

  static Future<String?> login(String email, String password) async {
    final response = await http
        .post(
          Uri.parse('$_base/auth/login'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({'email': email.trim(), 'password': password}),
        )
        .timeout(
          const Duration(seconds: 15),
          onTimeout: () => http.Response('', 408),
        );

    if (response.statusCode == 200) {
      await _storeTokensFromBody(response.body);
      return null;
    }
    if (response.statusCode == 401) {
      return 'Incorrect email or password.';
    }
    if (response.statusCode == 429) {
      return 'Too many attempts. Try again in a minute.';
    }
    return _errorMessage(response);
  }

  static Future<void> logout() => AuthStorage.clear();

  static Future<void> _storeTokensFromBody(String body) async {
    final map = jsonDecode(body) as Map<String, dynamic>;
    final access = map['access_token'] as String;
    final refresh = map['refresh_token'] as String;
    await AuthStorage.saveTokens(accessToken: access, refreshToken: refresh);
  }

  static String? _errorMessage(http.Response response) {
    try {
      final map = jsonDecode(response.body);
      if (map is Map && map['detail'] != null) {
        return map['detail'].toString();
      }
    } catch (_) {}
    return 'Request failed (${response.statusCode}).';
  }
}
