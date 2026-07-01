import 'dart:convert';

import 'package:http/http.dart' as http;

import 'auth_service.dart';
import 'auth_storage.dart';

typedef SessionExpiredCallback = void Function();

/// Shared authorized HTTP helper: attaches Bearer access token and refreshes on 401.
class AuthHttp {
  AuthHttp._();

  static SessionExpiredCallback? onSessionExpired;

  static Future<Map<String, String>> _jsonHeaders() async {
    final t = await AuthStorage.readAccessToken();
    return {
      'Content-Type': 'application/json',
      if (t != null && t.isNotEmpty) 'Authorization': 'Bearer $t',
    };
  }

  static Future<http.Response> get(Uri uri) => _withAuth(
        (h) => http.get(uri, headers: h),
      );

  static Future<http.Response> postJson(Uri uri, Map<String, dynamic> body) =>
      _withAuth(
        (h) => http.post(uri, headers: h, body: jsonEncode(body)),
      );

  static Future<http.Response> patchJson(
    Uri uri,
    Map<String, dynamic> body,
  ) =>
      _withAuth(
        (h) => http.patch(uri, headers: h, body: jsonEncode(body)),
      );

  static Future<http.Response> patch(Uri uri, {String? body}) => _withAuth(
        (h) => http.patch(uri, headers: h, body: body),
      );

  static Future<http.Response> delete(Uri uri) => _withAuth(
        (h) => http.delete(uri, headers: h),
      );

  static Future<http.Response> _withAuth(
    Future<http.Response> Function(Map<String, String> headers) send,
  ) async {
    var headers = await _jsonHeaders();
    var response = await send(headers).timeout(
      const Duration(seconds: 30),
      onTimeout: () => http.Response('', 408),
    );
    if (response.statusCode == 401) {
      final ok = await AuthService.tryRefresh();
      if (ok) {
        headers = await _jsonHeaders();
        response = await send(headers).timeout(
          const Duration(seconds: 30),
          onTimeout: () => http.Response('', 408),
        );
      } else {
        onSessionExpired?.call();
      }
    }
    return response;
  }
}
